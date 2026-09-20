from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Any

import numpy as np
import xarray as xr

from orca.data.adapters.base import (
    BaseMarineAdapter,
    NetworkTimeoutError,
    SchemaValidationError,
    SourceUnavailableError,
)
from orca.safety.sanitizer import validate_coordinates
from orca.safety.ssrf import SSRFSecurityError
from orca.schemas.orca_contract import (
    AccessMethod,
    DataQuality,
    Evidence,
    Geometry,
    SourceMetadata,
    utc_now,
)
from orca.telemetry.tracer import trace_span

DEFAULT_COPERNICUS_DATASET_ID = "cmems_mod_glo_phy_anfc_0.083deg_P1D-m"
DEFAULT_COPERNICUS_THREDDS_BASE = "https://thredds.marine.copernicus.eu/thredds/dodsC"


class CopernicusMarineAdapter(BaseMarineAdapter):
    """Adapter for retrieving physical ocean variables from Copernicus Marine Service (CMEMS).
    
    Accesses Copernicus OpenDAP services using user credentials or pre-configured
    deterministic NetCDF endpoints/fixtures in offline environments.
    """

    def __init__(
        self,
        endpoint_url: str | None = None,
        *,
        username: str | None = None,
        password: str | None = None,
        dataset_id: str | None = None,
        timeout_seconds: float = 15.0,
        verify_ssl: bool = True,
    ):
        super().__init__(timeout_seconds=timeout_seconds, verify_ssl=verify_ssl)
        self.endpoint_url = endpoint_url or os.getenv("COPERNICUS_ENDPOINT_URL")
        self.username = username or os.getenv("COPERNICUS_USERNAME")
        self.password = password or os.getenv("COPERNICUS_PASSWORD")
        self.dataset_id = dataset_id or os.getenv("COPERNICUS_DATASET_ID", DEFAULT_COPERNICUS_DATASET_ID)

    @property
    def has_credentials(self) -> bool:
        return bool(self.username and self.password)

    @classmethod
    def get_source_metadata(cls, dataset_id: str | None = None) -> SourceMetadata:
        label = f"Copernicus Marine Ocean Physics ({dataset_id})" if dataset_id else "Copernicus Marine Ocean Physics"
        return SourceMetadata(
            source_id="copernicus_marine_service",
            organization="Copernicus Marine Service (EUMETSAT/Mercator Ocean)",
            dataset=label,
            domain=["oceanography", "sst", "salinity", "currents"],
            coverage="global",
            latency="daily",
            resolution="0.083deg (~9km)",
            authority="official",
            access=AccessMethod.ERDDAP,
            freshness_policy_hours=36.0,
        )

    def resolve_endpoint(self) -> str:
        """Resolve the effective OpenDAP endpoint or raise if credentials are required but absent."""
        if self.endpoint_url is not None:
            return self.endpoint_url

        if not self.has_credentials:
            raise SourceUnavailableError(
                "Copernicus Marine credentials missing. COPERNICUS_USERNAME and COPERNICUS_PASSWORD "
                "must be configured to access Copernicus live services."
            )

        return f"{DEFAULT_COPERNICUS_THREDDS_BASE}/{self.dataset_id}"

    def extract_sst(
        self,
        location: Geometry,
        observed_at: datetime | None = None,
    ) -> Evidence:
        """Extract sea surface temperature at the given geographic coordinate from Copernicus Marine."""
        with trace_span(
            "adapter.copernicus_marine.extract_sst",
            attributes={
                "lat": location.lat,
                "lon": location.lon,
                "dataset_id": self.dataset_id,
                "username": self.username,
                "password": self.password,
            },
        ):
            # 1. Validate coordinate bounds
            lat, lon = validate_coordinates(location.lat, location.lon)

            # 2. Resolve endpoint URL
            active_endpoint = self.resolve_endpoint()

            # 3. Enforce SSRF rules on live HTTP/HTTPS endpoints
            if not active_endpoint.startswith("mock://"):
                try:
                    self.validate_target_url(active_endpoint)
                except SSRFSecurityError as exc:
                    raise SourceUnavailableError(f"Copernicus endpoint security violation: {exc}") from exc

            # 4. Open dataset
            try:
                ds = xr.open_dataset(active_endpoint)
            except Exception as exc:
                raise SourceUnavailableError(f"Failed to open Copernicus dataset at {active_endpoint}: {exc}")

            parsed_observed_at: datetime | None = observed_at
            try:
                # Parse temporal coordinate
                if parsed_observed_at is None:
                    for time_var in ("time", "TAXIS", "TIME", "time_counter"):
                        if time_var in ds.coords:
                            t_vals = ds.coords[time_var].values
                            if hasattr(t_vals, "__len__") and len(t_vals) > 0:
                                t_val = t_vals[-1]
                            else:
                                t_val = t_vals
                            if isinstance(t_val, np.datetime64):
                                import pandas as pd
                                ts = pd.to_datetime(t_val)
                                parsed_observed_at = ts.to_pydatetime().replace(tzinfo=timezone.utc)
                                break
            except Exception:
                pass

            try:
                # Detect coordinate dimension names
                lat_name = next((dim for dim in ("latitude", "lat", "LAT") if dim in ds.coords or dim in ds.dims), None)
                lon_name = next((dim for dim in ("longitude", "lon", "LON") if dim in ds.coords or dim in ds.dims), None)

                if not lat_name or not lon_name:
                    raise SchemaValidationError(f"Could not find valid lat/lon dimensions in Copernicus dataset: {list(ds.coords.keys())}")

                # Spatial boundary check
                lat_arr = ds.coords[lat_name].values
                lon_arr = ds.coords[lon_name].values
                min_lat, max_lat = float(np.min(lat_arr)), float(np.max(lat_arr))
                min_lon, max_lon = float(np.min(lon_arr)), float(np.max(lon_arr))

                if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
                    raise SourceUnavailableError(
                        f"Coordinates ({lat}, {lon}) are outside Copernicus dataset bounds "
                        f"[lat: {min_lat}..{max_lat}, lon: {min_lon}..{max_lon}]."
                    )

                # Detect SST variable name ('thetao', 'analysed_sst', 'sst', 'sea_surface_temperature')
                var_name = next(
                    (v for v in ("thetao", "analysed_sst", "sst", "sea_surface_temperature", "to") if v in ds.data_vars),
                    None,
                )
                if not var_name:
                    raise SchemaValidationError(
                        f"No recognized SST variable found in Copernicus dataset. Available variables: {list(ds.data_vars.keys())}"
                    )

                sel_kwargs = {lat_name: lat, lon_name: lon}
                point_data = ds[var_name].sel(**sel_kwargs, method="nearest")

                # Collapse depth / vertical dimension if present
                for depth_dim in ("depth", "deptht", "lev", "DEPTH1_1"):
                    if depth_dim in point_data.dims:
                        point_data = point_data.isel({depth_dim: 0})

                # Collapse time dimension if present
                for t_dim in ("time", "TAXIS", "TIME", "time_counter"):
                    if t_dim in point_data.dims:
                        point_data = point_data.isel({t_dim: -1})

                val = float(point_data.values)
            except Exception as exc:
                if isinstance(exc, (SchemaValidationError, SourceUnavailableError)):
                    raise
                raise SourceUnavailableError(f"Error extracting Copernicus SST at ({lat}, {lon}): {exc}") from exc
            finally:
                ds.close()

            if math.isnan(val) or not math.isfinite(val) or val < -100.0:
                raise SourceUnavailableError(
                    f"Copernicus SST at ({lat}, {lon}) is unresolvable or land-masked."
                )

            # Convert Kelvin to Celsius if applicable
            temp_c = val - 273.15 if val > 100.0 else val

            return Evidence(
                source=self.get_source_metadata(dataset_id=self.dataset_id),
                variable="sea_surface_temperature",
                value=round(temp_c, 2),
                unit="degC",
                geometry=location,
                observed_at=parsed_observed_at,
                retrieved_at=utc_now(),
                quality=DataQuality.GOOD,
                method="copernicus_opendap_grid_point_interpolation",
                derived=True,
                estimated=False,
                derivation_details=f"copernicus_dataset_{self.dataset_id}",
            )
