from __future__ import annotations

import math
import os
from datetime import datetime, timezone

import numpy as np
import xarray as xr

from orca.data.adapters.base import BaseMarineAdapter, SourceUnavailableError
from orca.schemas.orca_contract import (
    AccessMethod,
    DataQuality,
    Evidence,
    Geometry,
    SourceMetadata,
    utc_now,
)

DEFAULT_SST_OPENDAP_URL = "https://incois.gov.in/thredds/dodsC/osf/sst/SST_IO_20260915.nc"


class INCOISSSTAdapter(BaseMarineAdapter):
    """Adapter for retrieving physical Sea Surface Temperature from INCOIS THREDDS."""

    def __init__(
        self,
        endpoint_url: str | None = None,
        *,
        timeout_seconds: float = 15.0,
    ):
        super().__init__(timeout_seconds=timeout_seconds)
        self.endpoint_url = endpoint_url or os.getenv("INCOIS_SST_URL", DEFAULT_SST_OPENDAP_URL)

    @classmethod
    def get_source_metadata(cls) -> SourceMetadata:
        return SourceMetadata(
            source_id="incois_osf_sst",
            organization="INCOIS",
            dataset="Ocean State Forecast - SST (Indian Ocean)",
            domain=["oceanography", "sst", "thermal_fronts"],
            coverage="indian_ocean",
            latency="daily",
            resolution="0.08deg (~9km)",
            authority="official",
            access=AccessMethod.ERDDAP,
            freshness_policy_hours=36.0,
        )

    def extract_sst(
        self,
        location: Geometry,
        observed_at: datetime | None = None,
    ) -> Evidence:
        """Extract sea surface temperature at the given geographic coordinate."""
        try:
            ds = xr.open_dataset(self.endpoint_url)
        except Exception as exc:
            raise SourceUnavailableError(f"Failed to open INCOIS SST dataset at {self.endpoint_url}: {exc}")

        parsed_observed_at: datetime | None = observed_at
        try:
            if parsed_observed_at is None and "TAXIS" in ds.coords:
                t_val = ds.coords["TAXIS"].values
                if hasattr(t_val, "__len__") and len(t_val) > 0:
                    t_val = t_val[-1]
                if isinstance(t_val, np.datetime64):
                    import pandas as pd
                    ts = pd.to_datetime(t_val)
                    parsed_observed_at = ts.to_pydatetime().replace(tzinfo=timezone.utc)
        except Exception:
            pass

        try:
            # Query point with nearest neighbor
            sst_data = ds["SST"].sel(
                LAT=location.lat,
                LON=location.lon,
                method="nearest",
            )
            if "DEPTH1_1" in sst_data.dims:
                sst_data = sst_data.isel(DEPTH1_1=0)
            if "TAXIS" in sst_data.dims:
                sst_data = sst_data.isel(TAXIS=-1)

            val = float(sst_data.values)
        except Exception as exc:
            raise SourceUnavailableError(f"Error querying SST grid coordinate ({location.lat}, {location.lon}): {exc}")
        finally:
            ds.close()

        # Handle INCOIS fill value (-999.9) as NaN
        if val <= -900.0:
            val = float("nan")

        # Handle land mask (NaN) by scanning adjacent ocean grid cells up to ~25km
        quality = DataQuality.GOOD
        estimated = False
        derivation_details = "opendap_nearest_grid_cell"

        if math.isnan(val):
            # Probe 0.15 deg (~16km) westward offshore into open water
            offshore_lon = location.lon - 0.15 if location.lon > 60.0 else location.lon + 0.15
            try:
                ds = xr.open_dataset(self.endpoint_url)
                sst_data = ds["SST"].sel(LAT=location.lat, LON=offshore_lon, method="nearest")
                if "DEPTH1_1" in sst_data.dims:
                    sst_data = sst_data.isel(DEPTH1_1=0)
                if "TAXIS" in sst_data.dims:
                    sst_data = sst_data.isel(TAXIS=-1)
                probe_val = float(sst_data.values)
                if probe_val > -900.0 and not math.isnan(probe_val):
                    val = probe_val
                    quality = DataQuality.DEGRADED
                    estimated = True
                    derivation_details = "offshore_probe_due_to_land_mask"
            except Exception:
                pass
            finally:
                ds.close()

        if math.isnan(val) or not math.isfinite(val):
            raise SourceUnavailableError(
                f"SST data at location ({location.lat}, {location.lon}) is over land or unresolvable."
            )

        # Convert Kelvin to Celsius if necessary (INCOIS provides Deg. C.)
        temp_c = val - 273.15 if val > 200.0 else val

        return Evidence(
            source=self.get_source_metadata(),
            variable="sea_surface_temperature",
            value=round(temp_c, 2),
            unit="degC",
            geometry=location,
            observed_at=parsed_observed_at,
            retrieved_at=utc_now(),
            quality=quality,
            method="opendap_grid_point_interpolation",
            derived=True,
            estimated=estimated,
            derivation_details=derivation_details,
        )
