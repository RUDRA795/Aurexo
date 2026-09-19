"""Live operational smoke tests for INCOIS THREDDS catalog dataset discovery.

OPT-IN ONLY:
Executed only when ORCA_LIVE_SMOKE=1.
"""
from __future__ import annotations

import os
import pytest

from orca.data.discovery import INCOISTHREDDSCatalogDiscovery

pytestmark = pytest.mark.skipif(
    os.getenv("ORCA_LIVE_SMOKE") != "1",
    reason="Live tests require ORCA_LIVE_SMOKE=1",
)


@pytest.mark.asyncio
async def test_live_incois_sst_catalog_discovery():
    """Verify live dynamic discovery of the latest operational SST NetCDF dataset."""
    discovery = INCOISTHREDDSCatalogDiscovery(verify_ssl=True, timeout_seconds=20.0)
    url = await discovery.discover_latest_sst_url()

    assert url.startswith("https://incois.gov.in/thredds/dodsC/osf/sst/SST_IO_")
    assert url.endswith(".nc")


@pytest.mark.asyncio
async def test_live_incois_chl_catalog_discovery():
    """Verify live dynamic discovery of the latest operational Chlorophyll NetCDF dataset."""
    discovery = INCOISTHREDDSCatalogDiscovery(verify_ssl=True, timeout_seconds=20.0)
    url = await discovery.discover_latest_chl_url()

    assert url.startswith("https://incois.gov.in/thredds/dodsC/osf/chl/VIIRS-SNPP-Roll-")
    assert url.endswith(".nc")
