import numpy as np
import pytest
import xarray as xr

from orca.data.adapters.base import SchemaValidationError, SourceUnavailableError
from orca.data.adapters.copernicus_marine import CopernicusMarineAdapter
from orca.safety.sanitizer import CoordinateValidationError
from orca.schemas.orca_contract import DataQuality, Geometry


def _create_mock_copernicus_dataset():
    lats = np.linspace(-10.0, 30.0, 5)
    lons = np.linspace(60.0, 90.0, 5)
    # 28.5 Celsius in Kelvin is 301.65 K
    sst_vals = np.full((1, 1, len(lats), len(lons)), 301.65)
    return xr.Dataset(
        data_vars={"thetao": (("time", "depth", "latitude", "longitude"), sst_vals)},
        coords={
            "latitude": lats,
            "longitude": lons,
            "depth": [0.5],
            "time": [np.datetime64("2026-09-20T00:00:00")],
        },
    )


def test_copernicus_missing_credentials_raises(monkeypatch):
    monkeypatch.delenv("COPERNICUS_USERNAME", raising=False)
    monkeypatch.delenv("COPERNICUS_PASSWORD", raising=False)
    monkeypatch.delenv("COPERNICUS_ENDPOINT_URL", raising=False)

    adapter = CopernicusMarineAdapter()
    assert adapter.has_credentials is False
    with pytest.raises(SourceUnavailableError, match="credentials missing"):
        adapter.extract_sst(Geometry(lat=15.0, lon=75.0))


def test_copernicus_valid_extraction_with_mock_dataset(monkeypatch):
    mock_ds = _create_mock_copernicus_dataset()
    monkeypatch.setattr(xr, "open_dataset", lambda *args, **kwargs: mock_ds)

    adapter = CopernicusMarineAdapter(endpoint_url="mock://copernicus/sst.nc")
    evidence = adapter.extract_sst(Geometry(lat=15.0, lon=75.0))

    assert evidence.variable == "sea_surface_temperature"
    assert evidence.unit == "degC"
    assert evidence.value == 28.5  # 301.65 K - 273.15 = 28.5 C
    assert evidence.quality == DataQuality.GOOD
    assert evidence.derived is True
    assert evidence.estimated is False
    assert evidence.observed_at is not None
    assert "copernicus_marine_service" in evidence.source.source_id


def test_copernicus_out_of_bounds_coordinates(monkeypatch):
    mock_ds = _create_mock_copernicus_dataset()
    monkeypatch.setattr(xr, "open_dataset", lambda *args, **kwargs: mock_ds)

    adapter = CopernicusMarineAdapter(endpoint_url="mock://copernicus/sst.nc")
    # Dataset bounds are lat [-10..30], lon [60..90]
    # Query at lat=45.0, lon=-30.0 (North Atlantic)
    with pytest.raises(SourceUnavailableError, match="outside Copernicus dataset bounds"):
        adapter.extract_sst(Geometry(lat=45.0, lon=-30.0))


def test_copernicus_missing_lat_lon_schema(monkeypatch):
    broken_ds = xr.Dataset(
        data_vars={"thetao": (("x", "y"), [[300.0]])},
        coords={"x": [1], "y": [2]},
    )
    monkeypatch.setattr(xr, "open_dataset", lambda *args, **kwargs: broken_ds)

    adapter = CopernicusMarineAdapter(endpoint_url="mock://copernicus/broken.nc")
    with pytest.raises(SchemaValidationError, match="valid lat/lon dimensions"):
        adapter.extract_sst(Geometry(lat=15.0, lon=75.0))


def test_copernicus_missing_sst_variable(monkeypatch):
    missing_var_ds = xr.Dataset(
        data_vars={"salinity": (("latitude", "longitude"), [[35.0]])},
        coords={"latitude": [15.0], "longitude": [75.0]},
    )
    monkeypatch.setattr(xr, "open_dataset", lambda *args, **kwargs: missing_var_ds)

    adapter = CopernicusMarineAdapter(endpoint_url="mock://copernicus/nosst.nc")
    with pytest.raises(SchemaValidationError, match="No recognized SST variable"):
        adapter.extract_sst(Geometry(lat=15.0, lon=75.0))


def test_copernicus_invalid_coordinates():
    with pytest.raises(Exception):
        Geometry(lat=95.0, lon=75.0)

    adapter = CopernicusMarineAdapter(endpoint_url="mock://copernicus/sst.nc")
    invalid_geom = object.__new__(Geometry)
    object.__setattr__(invalid_geom, "lat", 95.0)
    object.__setattr__(invalid_geom, "lon", 75.0)
    with pytest.raises(CoordinateValidationError):
        adapter.extract_sst(invalid_geom)



def test_copernicus_ssrf_rejection():
    adapter = CopernicusMarineAdapter(endpoint_url="http://127.0.0.1:8080/sst.nc")
    with pytest.raises(SourceUnavailableError, match="security violation"):
        adapter.extract_sst(Geometry(lat=15.0, lon=75.0))
