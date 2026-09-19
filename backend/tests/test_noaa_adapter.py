import httpx
import pytest

from orca.data.adapters.base import (
    NetworkTimeoutError,
    SchemaValidationError,
    SourceUnavailableError,
)
from orca.data.adapters.noaa_weather import NOAAWeatherAdapter
from orca.safety.sanitizer import CoordinateValidationError
from orca.schemas.orca_contract import DataQuality, Geometry

MOCK_POINTS_PAYLOAD = {
    "properties": {
        "gridId": "MLB",
        "gridX": 45,
        "gridY": 70,
        "forecast": "https://api.weather.gov/gridpoints/MLB/45,70/forecast",
    }
}

MOCK_FORECAST_PAYLOAD = {
    "properties": {
        "periods": [
            {
                "number": 1,
                "name": "Today",
                "startTime": "2026-09-20T12:00:00-04:00",
                "endTime": "2026-09-20T18:00:00-04:00",
                "isDaytime": True,
                "temperature": 82,
                "temperatureUnit": "F",
                "windSpeed": "12 to 18 mph",
                "windDirection": "ENE",
                "shortForecast": "Partly Sunny then Isolated Showers",
                "detailedForecast": "Isolated showers after 2pm. Partly sunny, with a high near 82.",
            }
        ]
    }
}


@pytest.mark.asyncio
async def test_noaa_adapter_success():
    def custom_handler(request: httpx.Request):
        url = str(request.url)
        if "/points/" in url:
            return httpx.Response(200, json=MOCK_POINTS_PAYLOAD)
        if "/gridpoints/" in url:
            return httpx.Response(200, json=MOCK_FORECAST_PAYLOAD)
        return httpx.Response(404)

    transport = httpx.MockTransport(custom_handler)
    adapter = NOAAWeatherAdapter(base_url="https://api.weather.gov")
    adapter.create_client = lambda: httpx.AsyncClient(transport=transport)

    evidence = await adapter.fetch_forecast(Geometry(lat=28.39, lon=-80.60))

    assert evidence.variable == "marine_weather_forecast"
    assert evidence.unit == "forecast_record"
    assert evidence.quality == DataQuality.GOOD
    assert evidence.derived is False
    assert evidence.source.source_id == "noaa_nws_weather"

    val = evidence.value
    assert isinstance(val, dict)
    assert val["temperature_f"] == 82.0
    assert val["temperature_c"] == 27.78
    assert val["wind_speed"] == "12 to 18 mph"
    assert val["wind_direction"] == "ENE"
    assert val["short_forecast"] == "Partly Sunny then Isolated Showers"
    assert evidence.observed_at is not None


@pytest.mark.asyncio
async def test_noaa_outside_coverage_404():
    def custom_handler(request: httpx.Request):
        return httpx.Response(404, json={"detail": "Unable to provide data for requested point"})

    transport = httpx.MockTransport(custom_handler)
    adapter = NOAAWeatherAdapter(base_url="https://api.weather.gov")
    adapter.create_client = lambda: httpx.AsyncClient(transport=transport)

    with pytest.raises(SourceUnavailableError, match="outside NOAA NWS operational forecast coverage"):
        await adapter.fetch_forecast(Geometry(lat=15.0, lon=73.0))


@pytest.mark.asyncio
async def test_noaa_server_error_500():
    def custom_handler(request: httpx.Request):
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(custom_handler)
    adapter = NOAAWeatherAdapter(base_url="https://api.weather.gov")
    adapter.create_client = lambda: httpx.AsyncClient(transport=transport)

    with pytest.raises(SourceUnavailableError, match="returned HTTP 500"):
        await adapter.fetch_forecast(Geometry(lat=28.39, lon=-80.60))


@pytest.mark.asyncio
async def test_noaa_network_timeout():
    def custom_handler(request: httpx.Request):
        raise httpx.ReadTimeout("Connection timed out")

    transport = httpx.MockTransport(custom_handler)
    adapter = NOAAWeatherAdapter(base_url="https://api.weather.gov")
    adapter.create_client = lambda: httpx.AsyncClient(transport=transport)

    with pytest.raises(NetworkTimeoutError, match="timed out"):
        await adapter.fetch_forecast(Geometry(lat=28.39, lon=-80.60))


@pytest.mark.asyncio
async def test_noaa_malformed_points_schema():
    def custom_handler(request: httpx.Request):
        return httpx.Response(200, json={"properties": {"missing_forecast": True}})

    transport = httpx.MockTransport(custom_handler)
    adapter = NOAAWeatherAdapter(base_url="https://api.weather.gov")
    adapter.create_client = lambda: httpx.AsyncClient(transport=transport)

    with pytest.raises(SchemaValidationError, match="missing 'properties.forecast'"):
        await adapter.fetch_forecast(Geometry(lat=28.39, lon=-80.60))


@pytest.mark.asyncio
async def test_noaa_empty_periods_schema():
    def custom_handler(request: httpx.Request):
        url = str(request.url)
        if "/points/" in url:
            return httpx.Response(200, json=MOCK_POINTS_PAYLOAD)
        return httpx.Response(200, json={"properties": {"periods": []}})

    transport = httpx.MockTransport(custom_handler)
    adapter = NOAAWeatherAdapter(base_url="https://api.weather.gov")
    adapter.create_client = lambda: httpx.AsyncClient(transport=transport)

    with pytest.raises(SchemaValidationError, match="empty 'periods' list"):
        await adapter.fetch_forecast(Geometry(lat=28.39, lon=-80.60))


@pytest.mark.asyncio
async def test_noaa_invalid_coordinates():
    with pytest.raises(Exception):
        Geometry(lat=95.0, lon=-80.0)

    adapter = NOAAWeatherAdapter()
    invalid_geom = object.__new__(Geometry)
    object.__setattr__(invalid_geom, "lat", 95.0)
    object.__setattr__(invalid_geom, "lon", -80.0)
    with pytest.raises(CoordinateValidationError):
        await adapter.fetch_forecast(invalid_geom)



@pytest.mark.asyncio
async def test_noaa_ssrf_rejection():
    # Base URL pointing to malicious unauthorized host
    adapter = NOAAWeatherAdapter(base_url="http://169.254.169.254")
    with pytest.raises(SourceUnavailableError, match="security policy violation"):
        await adapter.fetch_forecast(Geometry(lat=28.39, lon=-80.60))
