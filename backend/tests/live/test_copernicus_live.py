"""Live operational smoke tests for Copernicus Marine Service (opt-in via ORCA_LIVE_SMOKE=1)."""
import os
import pytest

from orca.data.adapters.copernicus_marine import CopernicusMarineAdapter
from orca.schemas.orca_contract import DataQuality, Geometry

pytestmark = pytest.mark.skipif(
    os.getenv("ORCA_LIVE_SMOKE") != "1",
    reason="Live network smoke tests disabled. Enable by setting ORCA_LIVE_SMOKE=1.",
)


def test_copernicus_live_smoke():
    """Verify live connectivity against Copernicus Marine OpenDAP service if credentials exist."""
    user = os.getenv("COPERNICUS_USERNAME")
    password = os.getenv("COPERNICUS_PASSWORD")

    if not user or not password:
        pytest.skip("COPERNICUS_USERNAME and COPERNICUS_PASSWORD not configured; live Copernicus smoke skipped.")

    adapter = CopernicusMarineAdapter(username=user, password=password)
    loc = Geometry(lat=15.0, lon=75.0)
    evidence = adapter.extract_sst(loc)

    assert evidence is not None
    assert evidence.variable == "sea_surface_temperature"
    assert evidence.quality == DataQuality.GOOD
    assert evidence.value > 0.0
