from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Any

import httpx

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

DEFAULT_NOAA_BASE_URL = "https://api.weather.gov"


class NOAAWeatherAdapter(BaseMarineAdapter):
    """Adapter for retrieving marine meteorological and weather forecasts from NOAA NWS API."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout_seconds: float = 12.0,
        verify_ssl: bool = True,
    ):
        super().__init__(timeout_seconds=timeout_seconds, verify_ssl=verify_ssl)
        self.base_url = (base_url or os.getenv("NOAA_BASE_URL", DEFAULT_NOAA_BASE_URL)).rstrip("/")

    @classmethod
    def get_source_metadata(cls, grid_id: str | None = None) -> SourceMetadata:
        dataset_label = f"NOAA NWS Marine & Coastal Weather ({grid_id})" if grid_id else "NOAA NWS Marine & Coastal Weather"
        return SourceMetadata(
            source_id="noaa_nws_weather",
            organization="NOAA National Weather Service",
            dataset=dataset_label,
            domain=["meteorology", "marine_weather", "wind", "temperature"],
            coverage="usa_coastal_waters",
            latency="hourly",
            resolution="2.5km",
            authority="official",
            access=AccessMethod.API,
            freshness_policy_hours=6.0,
        )

    def create_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout_seconds,
            verify=self.verify_ssl,
            follow_redirects=True,
            headers={
                "User-Agent": "ORCA-Marine-Intelligence/1.0 (Government-Research; contact@orca-marine.org)",
                "Accept": "application/geo+json, application/json",
            },
        )

    async def fetch_forecast(self, location: Geometry) -> Evidence:
        """Fetch current weather forecast for geographic coordinates from NOAA NWS."""
        # 1. Validate coordinates bounds
        lat, lon = validate_coordinates(location.lat, location.lon)

        # 2. Build and validate points URL against SSRF policy
        point_url = f"{self.base_url}/points/{lat:.4f},{lon:.4f}"
        if not point_url.startswith("mock://"):
            try:
                self.validate_target_url(point_url)
            except SSRFSecurityError as exc:
                raise SourceUnavailableError(f"NOAA point URL security policy violation: {exc}") from exc

        # 3. Retrieve point metadata
        async with self.create_client() as client:
            try:
                point_resp = await client.get(point_url)
            except httpx.TimeoutException as exc:
                raise NetworkTimeoutError(f"NOAA points request timed out: {exc}") from exc
            except httpx.RequestError as exc:
                raise SourceUnavailableError(f"NOAA points request network error: {exc}") from exc

            if point_resp.status_code == 404:
                raise SourceUnavailableError(
                    f"Coordinates ({lat}, {lon}) are outside NOAA NWS operational forecast coverage."
                )
            if point_resp.status_code != 200:
                raise SourceUnavailableError(
                    f"NOAA points endpoint returned HTTP {point_resp.status_code}: {point_resp.text}"
                )

            try:
                point_data = point_resp.json()
                properties = point_data.get("properties", {})
                forecast_url = properties.get("forecast")
                grid_id = properties.get("gridId", "UNKNOWN")
                grid_x = properties.get("gridX")
                grid_y = properties.get("gridY")
                if not forecast_url:
                    raise SchemaValidationError("NOAA points response missing 'properties.forecast' URL.")
            except Exception as exc:
                if isinstance(exc, SchemaValidationError):
                    raise
                raise SchemaValidationError(f"Failed to parse NOAA points JSON payload: {exc}") from exc

            # 4. Validate forecast URL against SSRF policy
            if not forecast_url.startswith("mock://"):
                try:
                    self.validate_target_url(forecast_url)
                except SSRFSecurityError as exc:
                    raise SourceUnavailableError(f"NOAA forecast URL security policy violation: {exc}") from exc

            # 5. Retrieve forecast periods
            try:
                forecast_resp = await client.get(forecast_url)
            except httpx.TimeoutException as exc:
                raise NetworkTimeoutError(f"NOAA forecast request timed out: {exc}") from exc
            except httpx.RequestError as exc:
                raise SourceUnavailableError(f"NOAA forecast request network error: {exc}") from exc

            if forecast_resp.status_code != 200:
                raise SourceUnavailableError(
                    f"NOAA forecast endpoint returned HTTP {forecast_resp.status_code}: {forecast_resp.text}"
                )

            try:
                forecast_data = forecast_resp.json()
                periods = forecast_data.get("properties", {}).get("periods", [])
                if not periods:
                    raise SchemaValidationError("NOAA forecast response contains empty 'periods' list.")
            except Exception as exc:
                if isinstance(exc, SchemaValidationError):
                    raise
                raise SchemaValidationError(f"Failed to parse NOAA forecast JSON payload: {exc}") from exc

            current_period = periods[0]
            temp = current_period.get("temperature")
            temp_unit = current_period.get("temperatureUnit", "F")
            wind_speed = current_period.get("windSpeed", "")
            wind_dir = current_period.get("windDirection", "")
            short_forecast = current_period.get("shortForecast", "")
            detailed_forecast = current_period.get("detailedForecast", "")
            start_time_str = current_period.get("startTime")

            # Parse start time
            observed_at: datetime | None = None
            if start_time_str:
                try:
                    observed_at = datetime.fromisoformat(start_time_str)
                    if observed_at.tzinfo is None:
                        observed_at = observed_at.replace(tzinfo=timezone.utc)
                except Exception:
                    observed_at = None

            # Convert Fahrenheit to Celsius if applicable
            temp_c: float | None = None
            if isinstance(temp, (int, float)):
                if temp_unit == "F":
                    temp_c = round((float(temp) - 32.0) * 5.0 / 9.0, 2)
                else:
                    temp_c = round(float(temp), 2)

            grid_label = f"{grid_id}:{grid_x},{grid_y}"

            return Evidence(
                source=self.get_source_metadata(grid_id=grid_label),
                variable="marine_weather_forecast",
                value={
                    "temperature_c": temp_c,
                    "temperature_f": float(temp) if isinstance(temp, (int, float)) else None,
                    "wind_speed": wind_speed,
                    "wind_direction": wind_dir,
                    "short_forecast": short_forecast,
                    "detailed_forecast": detailed_forecast,
                    "grid_id": grid_id,
                },
                unit="forecast_record",
                geometry=location,
                observed_at=observed_at,
                retrieved_at=utc_now(),
                quality=DataQuality.GOOD,
                method="noaa_nws_point_forecast",
                derived=False,
                estimated=False,
                derivation_details=f"noaa_nws_rest_grid_{grid_label}",
            )
