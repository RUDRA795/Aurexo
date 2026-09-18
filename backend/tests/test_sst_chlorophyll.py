import pytest
import numpy as np
import xarray as xr

from orca.data.adapters.incois_chlorophyll import INCOISChlorophyllAdapter
from orca.data.adapters.incois_sst import INCOISSSTAdapter
from orca.schemas.orca_contract import AccessMethod, DataQuality, Geometry, utc_now


def test_sst_adapter_metadata():
    meta = INCOISSSTAdapter.get_source_metadata()
    assert meta.source_id == "incois_osf_sst"
    assert meta.organization == "INCOIS"
    assert meta.authority == "official"
    assert meta.access == AccessMethod.ERDDAP
    assert meta.freshness_policy_hours == 36.0


def test_chlorophyll_adapter_metadata():
    meta = INCOISChlorophyllAdapter.get_source_metadata()
    assert meta.source_id == "incois_viirs_chl"
    assert meta.organization == "INCOIS"
    assert meta.authority == "official"
    assert meta.access == AccessMethod.ERDDAP
    assert "chlorophyll" in meta.domain


def test_sst_extraction_from_mock_xarray(monkeypatch):
    # Construct a synthetic in-memory xarray dataset matching INCOIS grid
    lats = np.linspace(10.0, 20.0, 11)
    lons = np.linspace(70.0, 80.0, 11)
    # 28.5 deg C grid
    sst_vals = np.full((1, 1, len(lats), len(lons)), 28.5)

    mock_ds = xr.Dataset(
        data_vars={"SST": (("TAXIS", "DEPTH1_1", "LAT", "LON"), sst_vals)},
        coords={
            "LAT": lats,
            "LON": lons,
            "DEPTH1_1": [0.0],
            "TAXIS": [np.datetime64("2026-09-18T12:00:00")],
        },
    )

    monkeypatch.setattr(xr, "open_dataset", lambda *args, **kwargs: mock_ds)

    adapter = INCOISSSTAdapter(endpoint_url="mock://sst")
    evidence = adapter.extract_sst(Geometry(lat=15.0, lon=73.0))

    assert evidence.variable == "sea_surface_temperature"
    assert evidence.unit == "degC"
    assert evidence.value == 28.5
    assert evidence.quality == DataQuality.GOOD
    assert evidence.source.source_id == "incois_osf_sst"


def test_chlorophyll_extraction_from_mock_xarray(monkeypatch):
    lats = np.linspace(10.0, 20.0, 11)
    lons = np.linspace(70.0, 80.0, 11)
    chl_vals = np.full((len(lats), len(lons)), 0.35)

    mock_ds = xr.Dataset(
        data_vars={"chlor_a": (("lat", "lon"), chl_vals)},
        coords={"lat": lats, "lon": lons},
    )

    monkeypatch.setattr(xr, "open_dataset", lambda *args, **kwargs: mock_ds)

    adapter = INCOISChlorophyllAdapter(endpoint_url="mock://chl")
    evidence = adapter.extract_chlorophyll(Geometry(lat=15.0, lon=73.0))

    assert evidence.variable == "chlorophyll_a"
    assert evidence.unit == "mg/m3"
    assert evidence.value == 0.35
    assert evidence.quality == DataQuality.GOOD
    assert evidence.source.source_id == "incois_viirs_chl"
