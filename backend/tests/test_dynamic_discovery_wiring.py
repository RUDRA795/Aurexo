import numpy as np
import pytest
import xarray as xr

from orca.data.adapters.base import SourceUnavailableError
from orca.data.adapters.incois_chlorophyll import (
    DEFAULT_CHL_OPENDAP_URL,
    INCOISChlorophyllAdapter,
)
from orca.data.adapters.incois_sst import (
    DEFAULT_SST_OPENDAP_URL,
    INCOISSSTAdapter,
)
from orca.data.discovery import INCOISTHREDDSCatalogDiscovery
from orca.safety.ssrf import SSRFSecurityError
from orca.schemas.orca_contract import DataQuality, Geometry


class MockDiscoverySuccess(INCOISTHREDDSCatalogDiscovery):
    async def discover_latest_sst_url(self, *args, **kwargs) -> str:
        return "https://incois.gov.in/thredds/dodsC/osf/sst/SST_IO_20260920.nc"

    def discover_latest_sst_url_sync(self, *args, **kwargs) -> str:
        return "https://incois.gov.in/thredds/dodsC/osf/sst/SST_IO_20260920.nc"

    async def discover_latest_chl_url(self, *args, **kwargs) -> str:
        return "https://incois.gov.in/thredds/dodsC/osf/chl/VIIRS-SNPP-Roll-20260918-20260920-4KM-PICountries-CHL.nc"

    def discover_latest_chl_url_sync(self, *args, **kwargs) -> str:
        return "https://incois.gov.in/thredds/dodsC/osf/chl/VIIRS-SNPP-Roll-20260918-20260920-4KM-PICountries-CHL.nc"


class MockDiscoveryFailure(INCOISTHREDDSCatalogDiscovery):
    async def discover_latest_sst_url(self, *args, **kwargs) -> str:
        raise SourceUnavailableError("Simulated THREDDS timeout")

    def discover_latest_sst_url_sync(self, *args, **kwargs) -> str:
        raise SourceUnavailableError("Simulated THREDDS timeout")

    async def discover_latest_chl_url(self, *args, **kwargs) -> str:
        raise SourceUnavailableError("Simulated THREDDS 503 error")

    def discover_latest_chl_url_sync(self, *args, **kwargs) -> str:
        raise SourceUnavailableError("Simulated THREDDS 503 error")


def _create_mock_sst_dataset():
    lats = [15.0]
    lons = [75.0]
    return xr.Dataset(
        data_vars={"SST": (("TAXIS", "DEPTH1_1", "LAT", "LON"), [[[[28.5]]]])},
        coords={
            "LAT": lats,
            "LON": lons,
            "DEPTH1_1": [0.0],
            "TAXIS": [np.datetime64("2026-09-20T00:00:00")],
        },
    )


def _create_mock_chl_dataset():
    lats = [15.0]
    lons = [75.0]
    return xr.Dataset(
        data_vars={"chlor_a": (("lat", "lon"), [[0.35]])},
        coords={"lat": lats, "lon": lons},
    )


def test_sst_explicit_override_skips_discovery():
    adapter = INCOISSSTAdapter(endpoint_url="mock://explicit_sst.nc")
    assert adapter.endpoint_url == "mock://explicit_sst.nc"
    assert adapter.is_fallback is False
    assert adapter.resolved_via == "explicit_override"


def test_chl_explicit_override_skips_discovery():
    adapter = INCOISChlorophyllAdapter(endpoint_url="mock://explicit_chl.nc")
    assert adapter.endpoint_url == "mock://explicit_chl.nc"
    assert adapter.is_fallback is False
    assert adapter.resolved_via == "explicit_override"


def test_sst_dynamic_discovery_success(monkeypatch):
    mock_ds = _create_mock_sst_dataset()
    monkeypatch.setattr(xr, "open_dataset", lambda *args, **kwargs: mock_ds)

    adapter = INCOISSSTAdapter(discovery=MockDiscoverySuccess())
    assert adapter.endpoint_url == "https://incois.gov.in/thredds/dodsC/osf/sst/SST_IO_20260920.nc"
    assert adapter.is_fallback is False
    assert adapter.resolved_via == "dynamic_catalog_discovery"

    ev = adapter.extract_sst(Geometry(lat=15.0, lon=75.0))
    assert ev.quality == DataQuality.GOOD
    assert ev.estimated is False
    assert "SST_IO_20260920.nc" in ev.source.dataset


def test_chl_dynamic_discovery_success(monkeypatch):
    mock_ds = _create_mock_chl_dataset()
    monkeypatch.setattr(xr, "open_dataset", lambda *args, **kwargs: mock_ds)

    adapter = INCOISChlorophyllAdapter(discovery=MockDiscoverySuccess())
    assert "VIIRS-SNPP-Roll-20260918-20260920-4KM-PICountries-CHL.nc" in adapter.endpoint_url
    assert adapter.is_fallback is False
    assert adapter.resolved_via == "dynamic_catalog_discovery"

    ev = adapter.extract_chlorophyll(Geometry(lat=15.0, lon=75.0))
    assert ev.quality == DataQuality.GOOD
    assert ev.estimated is False
    assert "VIIRS-SNPP-Roll-20260918-20260920-4KM-PICountries-CHL.nc" in ev.source.dataset


def test_sst_discovery_failure_triggers_static_fallback(monkeypatch):
    mock_ds = _create_mock_sst_dataset()
    monkeypatch.setattr(xr, "open_dataset", lambda *args, **kwargs: mock_ds)

    adapter = INCOISSSTAdapter(discovery=MockDiscoveryFailure())
    assert adapter.endpoint_url == DEFAULT_SST_OPENDAP_URL
    assert adapter.is_fallback is True
    assert adapter.resolved_via == "static_fallback"

    ev = adapter.extract_sst(Geometry(lat=15.0, lon=75.0))
    assert ev.quality == DataQuality.DEGRADED
    assert ev.estimated is True
    assert "static_catalog_fallback" in ev.derivation_details


def test_chl_discovery_failure_triggers_static_fallback(monkeypatch):
    mock_ds = _create_mock_chl_dataset()
    monkeypatch.setattr(xr, "open_dataset", lambda *args, **kwargs: mock_ds)

    adapter = INCOISChlorophyllAdapter(discovery=MockDiscoveryFailure())
    assert adapter.endpoint_url == DEFAULT_CHL_OPENDAP_URL
    assert adapter.is_fallback is True
    assert adapter.resolved_via == "static_fallback"

    ev = adapter.extract_chlorophyll(Geometry(lat=15.0, lon=75.0))
    assert ev.quality == DataQuality.DEGRADED
    assert ev.estimated is True
    assert "static_catalog_fallback" in ev.derivation_details


@pytest.mark.asyncio
async def test_async_resolve_endpoint():
    adapter = INCOISSSTAdapter(discovery=MockDiscoverySuccess())
    resolved = await adapter.resolve_endpoint()
    assert resolved == "https://incois.gov.in/thredds/dodsC/osf/sst/SST_IO_20260920.nc"
    assert adapter.is_fallback is False

    fail_adapter = INCOISSSTAdapter(discovery=MockDiscoveryFailure())
    fallback = await fail_adapter.resolve_endpoint()
    assert fallback == DEFAULT_SST_OPENDAP_URL
    assert fail_adapter.is_fallback is True


def test_malformed_catalog_xml_fails_gracefully():
    from orca.data.discovery import parse_thredds_catalog_xml

    with pytest.raises(SourceUnavailableError) as exc_info:
        parse_thredds_catalog_xml(
            b"<broken><a></b>",
            dataset_prefix="SST_",
            opendap_base="https://incois.gov.in/",
            variable_name="SST",
        )
    assert "XML parse error" in str(exc_info.value)


def test_empty_catalog_fails_gracefully():
    from orca.data.discovery import parse_thredds_catalog_xml

    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <catalog xmlns="http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0">
        <dataset name="unrelated_file.txt" />
    </catalog>"""
    with pytest.raises(SourceUnavailableError) as exc_info:
        parse_thredds_catalog_xml(
            xml,
            dataset_prefix="SST_IO_",
            opendap_base="https://incois.gov.in/",
            variable_name="SST",
        )
    assert "No matching datasets" in str(exc_info.value)


def test_discovery_ssrf_protection():
    discovery = INCOISTHREDDSCatalogDiscovery()
    with pytest.raises(SourceUnavailableError, match="security policy violation"):
        discovery._discover_latest_url_sync(
            catalog_url="http://169.254.169.254/latest/meta-data",
            dataset_prefix="SST",
            opendap_base="http://169.254.169.254/",
            variable_name="SST",
        )

