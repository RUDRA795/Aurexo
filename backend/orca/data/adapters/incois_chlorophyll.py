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

DEFAULT_CHL_CATALOG_URL = "https://incois.gov.in/thredds/catalog/osf/chl/catalog.xml"
DEFAULT_CHL_OPENDAP_URL = "https://incois.gov.in/thredds/dodsC/osf/chl/VIIRS-SNPP-Roll-20260912-20260914-4KM-PICountries-CHL.nc"


class INCOISChlorophyllAdapter(BaseMarineAdapter):
    """Adapter for retrieving physical Chlorophyll-a concentration from INCOIS THREDDS.
    
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
        self.explicit_endpoint = endpoint_url or os.getenv("INCOIS_CHL_URL")
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
            discovered = self.discovery.discover_latest_chl_url_sync()
            self._resolved_endpoint = discovered
            self._is_fallback = False
            self._resolved_via = "dynamic_catalog_discovery"
        except Exception as exc:
            self._resolved_endpoint = DEFAULT_CHL_OPENDAP_URL
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
            discovered = await self.discovery.discover_latest_chl_url()
            self._resolved_endpoint = discovered
            self._is_fallback = False
            self._resolved_via = "dynamic_catalog_discovery"
        except Exception as exc:
            self._resolved_endpoint = DEFAULT_CHL_OPENDAP_URL
            self._is_fallback = True
            self._fallback_reason = str(exc)
            self._resolved_via = "static_fallback"

        return self._resolved_endpoint

    @classmethod
    def get_source_metadata(cls, dataset_name: str | None = None) -> SourceMetadata:
        label = f"Ocean Colour VIIRS-SNPP Chlorophyll-a ({dataset_name})" if dataset_name else "Ocean Colour VIIRS-SNPP Chlorophyll-a"
        return SourceMetadata(
            source_id="incois_viirs_chl",
            organization="INCOIS",
            dataset=label,
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
        active_endpoint = self.get_effective_endpoint()
        if not active_endpoint.startswith("mock://"):
            self.validate_target_url(active_endpoint)

        try:
            ds = xr.open_dataset(active_endpoint)
        except Exception as exc:
            raise SourceUnavailableError(f"Failed to open INCOIS Chlorophyll dataset at {active_endpoint}: {exc}")

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

        quality = DataQuality.GOOD
        estimated = False
        derivation_details = "satellite_radiometry_point_interpolation"

        if self._is_fallback:
            quality = DataQuality.DEGRADED
            estimated = True
            derivation_details = f"static_catalog_fallback ({self._fallback_reason or 'discovery_failed'}); {derivation_details}"

        dataset_id = active_endpoint.rstrip("/").split("/")[-1]

        return Evidence(
            source=self.get_source_metadata(dataset_name=dataset_id),
            variable="chlorophyll_a",
            value=round(val, 3),
            unit="mg/m3",
            geometry=location,
            observed_at=parsed_observed_at,
            retrieved_at=utc_now(),
            quality=quality,
            method="satellite_radiometry_point_interpolation",
            derived=True,
            estimated=estimated,
            derivation_details=derivation_details,
        )
