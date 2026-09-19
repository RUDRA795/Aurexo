"""Live operational smoke tests for NOAA Weather API (opt-in via ORCA_LIVE_SMOKE=1)."""
import os
import pytest

from orca.data.adapters.noaa_weather import NOAAWeatherAdapter
from orca.schemas.orca_contract import DataQuality, Geometry

pytestmark = pytest.mark.skipif(
    os.getenv("ORCA_LIVE_SMOKE") != "1",
    reason="Live network smoke tests disabled. Enable by setting ORCA_LIVE_SMOKE=1.",
)


@pytest.mark.asyncio
async def test_noaa_live_weather_smoke():
    """Verify live connectivity and forecast payload from NOAA NWS API for US coastal waters."""
    adapter = NOAAWeatherAdapter()

    # Miami coastal coordinates (within NOAA NWS operational grid)
    loc = Geometry(lat=25.7617, lon=-80.1918)
    evidence = await adapter.fetch_forecast(loc)

    assert evidence is not None
    assert evidence.variable == "marine_weather_forecast"
    assert evidence.quality == DataQuality.GOOD
    assert evidence.observed_at is not None

    val = evidence.value
    assert isinstance(val, dict)
    assert val["temperature_f"] is not None
    assert val["temperature_c"] is not None
    assert val["wind_speed"] is not None
    assert len(val["short_forecast"]) > 0
