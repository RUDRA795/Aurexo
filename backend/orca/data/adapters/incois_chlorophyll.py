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

DEFAULT_CHL_OPENDAP_URL = "https://incois.gov.in/thredds/dodsC/osf/chl/VIIRS-SNPP-Roll-20260912-20260914-4KM-PICountries-CHL.nc"


class INCOISChlorophyllAdapter(BaseMarineAdapter):
    """Adapter for retrieving physical Chlorophyll-a concentration from INCOIS THREDDS."""

    def __init__(
        self,
        endpoint_url: str | None = None,
        *,
        timeout_seconds: float = 15.0,
    ):
        super().__init__(timeout_seconds=timeout_seconds)
        self.endpoint_url = endpoint_url or os.getenv("INCOIS_CHL_URL", DEFAULT_CHL_OPENDAP_URL)

    @classmethod
    def get_source_metadata(cls) -> SourceMetadata:
        return SourceMetadata(
            source_id="incois_viirs_chl",
            organization="INCOIS",
            dataset="Ocean Colour VIIRS-SNPP Chlorophyll-a",
            domain=["ocean_colour", "chlorophyll", "biological_productivity"],
            coverage="regional_indian_ocean",
            latency="daily",
            resolution="4km",
            authority="official",
            access=AccessMethod.ERDDAP,
            freshness_policy_hours=48.0,
        )

    def extract_chlorophyll(
        self,
        location: Geometry,
        observed_at: datetime | None = None,
    ) -> Evidence:
        """Extract chlorophyll-a concentration at the given geographic coordinate."""
        try:
            ds = xr.open_dataset(self.endpoint_url)
        except Exception as exc:
            raise SourceUnavailableError(f"Failed to open INCOIS Chlorophyll dataset at {self.endpoint_url}: {exc}")

        parsed_observed_at: datetime | None = observed_at
        try:
            if parsed_observed_at is None:
                for time_var in ("time", "TAXIS", "TIME"):
                    if time_var in ds.coords:
                        t_val = ds.coords[time_var].values
                        if hasattr(t_val, "__len__") and len(t_val) > 0:
                            t_val = t_val[-1]
                        if isinstance(t_val, np.datetime64):
                            import pandas as pd
                            ts = pd.to_datetime(t_val)
                            parsed_observed_at = ts.to_pydatetime().replace(tzinfo=timezone.utc)
                            break
        except Exception:
            pass

        try:
            # Check variable names ('chlor_a', 'CHL', 'chlorophyll')
            var_name = "chlor_a" if "chlor_a" in ds else "CHL" if "CHL" in ds else list(ds.data_vars.keys())[0]
            lat_dim = "lat" if "lat" in ds.dims else "LAT"
            lon_dim = "lon" if "lon" in ds.dims else "LON"

            sel_kwargs = {lat_dim: location.lat, lon_dim: location.lon}
            chl_data = ds[var_name].sel(**sel_kwargs, method="nearest")

            val = float(chl_data.values)
        except Exception as exc:
            raise SourceUnavailableError(f"Error querying Chlorophyll grid coordinate ({location.lat}, {location.lon}): {exc}")
        finally:
            ds.close()

        if math.isnan(val) or not math.isfinite(val) or val < 0:
            raise SourceUnavailableError(
                f"Chlorophyll-a data at ({location.lat}, {location.lon}) is unresolvable or out-of-bounds."
            )

        return Evidence(
            source=self.get_source_metadata(),
            variable="chlorophyll_a",
            value=round(val, 3),
            unit="mg/m3",
            geometry=location,
            observed_at=parsed_observed_at,
            retrieved_at=utc_now(),
            quality=DataQuality.GOOD,
            method="satellite_radiometry_point_interpolation",
            derived=True,
            estimated=False,
            derivation_details="satellite_radiometry_point_interpolation",
        )
