from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from orca.data.discovery import INCOISTHREDDSCatalogDiscovery

DEFAULT_SST_CATALOG_URL = "https://incois.gov.in/thredds/catalog/osf/sst/catalog.xml"
DEFAULT_SST_OPENDAP_URL = "https://incois.gov.in/thredds/dodsC/osf/sst/SST_IO_20260915.nc"


class INCOISSSTAdapter(BaseMarineAdapter):
    """Adapter for retrieving physical Sea Surface Temperature from INCOIS THREDDS.
    
    Uses dynamic catalog discovery as primary resolution path with deterministic
    fallback to the static baseline dataset on failure.
    """

    def __init__(
        self,
        endpoint_url: str | None = None,
        *,
        timeout_seconds: float = 15.0,
        discovery: INCOISTHREDDSCatalogDiscovery | None = None,
    ):
        super().__init__(timeout_seconds=timeout_seconds)
        self.explicit_endpoint = endpoint_url or os.getenv("INCOIS_SST_URL")
        if discovery is None:
            from orca.data.discovery import INCOISTHREDDSCatalogDiscovery
            self.discovery = INCOISTHREDDSCatalogDiscovery(
                timeout_seconds=min(timeout_seconds, 6.0),
                verify_ssl=self.verify_ssl,
            )
        else:
            self.discovery = discovery
        self._resolved_endpoint: str | None = None
        self._is_fallback: bool = False
        self._fallback_reason: str | None = None
        self._resolved_via: str | None = None

    @property
    def endpoint_url(self) -> str:
        return self.get_effective_endpoint()

    @endpoint_url.setter
    def endpoint_url(self, value: str | None) -> None:
        self.explicit_endpoint = value
        self._resolved_endpoint = value
        self._is_fallback = False
        self._resolved_via = "explicit_override" if value else None

    @property
    def is_fallback(self) -> bool:
        return self._is_fallback

    @property
    def resolved_via(self) -> str | None:
        return self._resolved_via

    def get_effective_endpoint(self) -> str:
        """Resolve dataset URL via explicit override, dynamic discovery, or static fallback."""
        if self.explicit_endpoint is not None:
            self._resolved_endpoint = self.explicit_endpoint
            self._is_fallback = False
            self._resolved_via = "explicit_override"
            return self._resolved_endpoint

        if self._resolved_endpoint is not None:
            return self._resolved_endpoint

        # Primary resolution path: dynamic discovery
        try:
            discovered = self.discovery.discover_latest_sst_url_sync()
            self._resolved_endpoint = discovered
            self._is_fallback = False
            self._resolved_via = "dynamic_catalog_discovery"
        except Exception as exc:
            self._resolved_endpoint = DEFAULT_SST_OPENDAP_URL
            self._is_fallback = True
            self._fallback_reason = str(exc)
            self._resolved_via = "static_fallback"

        return self._resolved_endpoint

    async def resolve_endpoint(self, force_refresh: bool = False) -> str:
        """Asynchronously resolve dataset URL via discovery or fallback."""
        if self.explicit_endpoint is not None:
            self._resolved_endpoint = self.explicit_endpoint
            self._is_fallback = False
            self._resolved_via = "explicit_override"
            return self._resolved_endpoint

        if self._resolved_endpoint is not None and not force_refresh:
            return self._resolved_endpoint

        try:
            discovered = await self.discovery.discover_latest_sst_url()
            self._resolved_endpoint = discovered
            self._is_fallback = False
            self._resolved_via = "dynamic_catalog_discovery"
        except Exception as exc:
            self._resolved_endpoint = DEFAULT_SST_OPENDAP_URL
            self._is_fallback = True
            self._fallback_reason = str(exc)
            self._resolved_via = "static_fallback"

        return self._resolved_endpoint

    @classmethod
    def get_source_metadata(cls, dataset_name: str | None = None) -> SourceMetadata:
        label = f"Ocean State Forecast - SST ({dataset_name})" if dataset_name else "Ocean State Forecast - SST (Indian Ocean)"
        return SourceMetadata(
            source_id="incois_osf_sst",
            organization="INCOIS",
            dataset=label,
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
        active_endpoint = self.get_effective_endpoint()
        if not active_endpoint.startswith("mock://"):
            self.validate_target_url(active_endpoint)

        try:
            ds = xr.open_dataset(active_endpoint)
        except Exception as exc:
            raise SourceUnavailableError(f"Failed to open INCOIS SST dataset at {active_endpoint}: {exc}")

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
                ds = xr.open_dataset(active_endpoint)
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

        # Handle fallback provenance degradation
        if self._is_fallback:
            quality = DataQuality.DEGRADED
            estimated = True
            derivation_details = f"static_catalog_fallback ({self._fallback_reason or 'discovery_failed'}); {derivation_details}"

        # Convert Kelvin to Celsius if necessary (INCOIS provides Deg. C.)
        temp_c = val - 273.15 if val > 200.0 else val

        dataset_id = active_endpoint.rstrip("/").split("/")[-1]

        return Evidence(
            source=self.get_source_metadata(dataset_name=dataset_id),
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
