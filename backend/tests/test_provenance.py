"""Unit tests verifying data provenance, timestamp integrity, SSL defaults, and verification rules."""
from datetime import datetime, timedelta, timezone
import pytest
import numpy as np
import xarray as xr

from orca.data.adapters.base import BaseMarineAdapter, SourceUnavailableError
from orca.data.adapters.incois_chlorophyll import INCOISChlorophyllAdapter
from orca.data.adapters.incois_pfz import INCOISPFZWebGISAdapter
from orca.data.adapters.incois_sst import INCOISSSTAdapter
from orca.data.adapters.incois_text_advisory import INCOISTextAdvisoryAdapter
from orca.data.discovery import INCOISTHREDDSCatalogDiscovery
from orca.database.models.pfz import PFZPointModel
from orca.schemas.orca_contract import DataQuality, Geometry, utc_now
from orca.schemas.pfz_contract import PFZPoint, PFZQuery


SAMPLE_WFS_FEATURE = {
    "type": "Feature",
    "id": "pfzlines.1",
    "geometry": {
        "type": "MultiLineString",
        "coordinates": [
            [
                [73.27840907, 15.6659412],
                [73.2788092, 15.66607439],
                [73.27920366, 15.66619898],
            ]
        ],
    },
    "properties": {
        "Shape_Leng": 8.58909,
        "State_Name": "GOA",
        "Julian_day": "261",
        "Year": 2026,
        "UID": "2026261001",
        "Length": 21.936,
    },
}


def test_pfz_original_geometry_preservation_and_midpoint():
    adapter = INCOISPFZWebGISAdapter()
    payload = {"type": "FeatureCollection", "features": [SAMPLE_WFS_FEATURE]}
    points = adapter.parse_geojson(payload)

    assert len(points) == 1
    pt = points[0]
    # Original geometry preserved
    assert pt.raw_geometry == SAMPLE_WFS_FEATURE["geometry"]
    # Midpoint derived
    assert pt.geometry_derivation == "line_midpoint_derived"
    assert 15.6 < pt.location.lat < 15.7
    assert 73.2 < pt.location.lon < 73.3


def test_pfz_validity_provenance_distinction():
    adapter = INCOISPFZWebGISAdapter()
    payload = {"type": "FeatureCollection", "features": [SAMPLE_WFS_FEATURE]}
    points = adapter.parse_geojson(payload)

    pt = points[0]
    expected_forecast_date = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=260)
    assert pt.forecast_date == expected_forecast_date
    assert pt.source_valid_from == expected_forecast_date
    # WFS provides no expiration: source_valid_until must be None (UNKNOWN)
    assert pt.source_valid_until is None
    # Derived validity horizon from ORCA freshness policy
    assert pt.validity_derivation == "orca_freshness_policy"
    assert pt.freshness_deadline == pt.valid_from + timedelta(hours=36)
    assert pt.valid_until == pt.freshness_deadline


def test_text_advisory_coordinate_and_validity_derivation():
    adapter = INCOISTextAdvisoryAdapter()
    # Case A: Explicit lat/lon given
    rec_explicit = {
        "sector": "GOA",
        "landing_center": "MALIM",
        "lat": 15.55,
        "lon": 73.75,
        "valid_until": datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc),
    }
    pt_a = adapter._record_to_point(rec_explicit)
    assert pt_a is not None
    assert pt_a.geometry_derivation == "original_point"
    assert pt_a.validity_derivation == "source_provided"
    assert pt_a.source_valid_until == datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)

    # Case B: Derived from landing center bearing/distance offset
    rec_derived = {
        "sector": "GOA",
        "landing_center": "MALIM",
        "bearing_deg": 270.0,
        "distance_km": 30.0,
    }
    pt_b = adapter._record_to_point(rec_derived)
    assert pt_b is not None
    assert pt_b.geometry_derivation == "landing_center_bearing_derived"
    assert pt_b.validity_derivation == "orca_freshness_policy"
    assert pt_b.source_valid_until is None


def test_ssl_verification_defaults_to_true():
    base = BaseMarineAdapter()
    assert base.verify_ssl is True

    pfz = INCOISPFZWebGISAdapter()
    assert pfz.verify_ssl is True

    txt = INCOISTextAdvisoryAdapter()
    assert txt.verify_ssl is True


def test_sst_provenance_and_observation_timestamp(monkeypatch):
    lats = np.linspace(10.0, 20.0, 5)
    lons = np.linspace(70.0, 80.0, 5)
    sst_vals = np.full((1, 1, len(lats), len(lons)), 29.0)

    dataset_time = np.datetime64("2026-09-17T06:00:00")
    mock_ds = xr.Dataset(
        data_vars={"SST": (("TAXIS", "DEPTH1_1", "LAT", "LON"), sst_vals)},
        coords={
            "LAT": lats,
            "LON": lons,
            "DEPTH1_1": [0.0],
            "TAXIS": [dataset_time],
        },
    )

    monkeypatch.setattr(xr, "open_dataset", lambda *args, **kwargs: mock_ds)
    adapter = INCOISSSTAdapter(endpoint_url="mock://sst")
    evidence = adapter.extract_sst(Geometry(lat=15.0, lon=75.0))

    assert evidence.observed_at == datetime(2026, 9, 17, 6, 0, tzinfo=timezone.utc)
    assert evidence.derived is True
    assert evidence.estimated is False
    assert evidence.quality == DataQuality.GOOD


def test_sst_land_mask_probe_marks_estimated_and_degraded(monkeypatch):
    lats = [15.0]
    lons = [73.5, 73.35]
    sst_vals = np.array([[[[np.nan, 28.2]]]])

    mock_ds = xr.Dataset(
        data_vars={"SST": (("TAXIS", "DEPTH1_1", "LAT", "LON"), sst_vals)},
        coords={
            "LAT": lats,
            "LON": lons,
            "DEPTH1_1": [0.0],
            "TAXIS": [np.datetime64("2026-09-18T00:00:00")],
        },
    )

    monkeypatch.setattr(xr, "open_dataset", lambda *args, **kwargs: mock_ds)
    adapter = INCOISSSTAdapter(endpoint_url="mock://sst")
    evidence = adapter.extract_sst(Geometry(lat=15.0, lon=73.5))

    assert evidence.value == 28.2
    assert evidence.estimated is True
    assert evidence.derivation_details == "offshore_probe_due_to_land_mask"
    assert evidence.quality == DataQuality.DEGRADED


def test_chlorophyll_missing_time_preserves_none_observed_at(monkeypatch):
    lats = np.linspace(10.0, 20.0, 5)
    lons = np.linspace(70.0, 80.0, 5)
    chl_vals = np.full((len(lats), len(lons)), 0.42)

    mock_ds = xr.Dataset(
        data_vars={"chlor_a": (("lat", "lon"), chl_vals)},
        coords={"lat": lats, "lon": lons},
    )

    monkeypatch.setattr(xr, "open_dataset", lambda *args, **kwargs: mock_ds)
    adapter = INCOISChlorophyllAdapter(endpoint_url="mock://chl")
    evidence = adapter.extract_chlorophyll(Geometry(lat=15.0, lon=75.0))

    assert evidence.observed_at is None
    assert evidence.derived is True
    assert evidence.estimated is False
    assert (utc_now() - evidence.retrieved_at).total_seconds() < 5.0


@pytest.mark.asyncio
async def test_catalog_discovery_failure_handling():
    discovery = INCOISTHREDDSCatalogDiscovery()
    with pytest.raises(SourceUnavailableError, match="request failed"):
        await discovery.discover_latest_sst_url(catalog_url="http://invalid-catalog-host.orca/catalog.xml")


def test_pfz_database_model_provenance_roundtrip():
    now = utc_now()
    pt = PFZPoint(
        pfz_id="pfz_roundtrip_test",
        location=Geometry(lat=15.5, lon=73.8),
        sector="GOA",
        raw_geometry={"type": "LineString", "coordinates": [[73.8, 15.5], [73.9, 15.6]]},
        geometry_derivation="line_midpoint_derived",
        source_valid_from=now,
        source_valid_until=None,
        validity_derivation="orca_freshness_policy",
        forecast_date=now,
        valid_from=now,
        valid_until=now + timedelta(hours=36),
        freshness_deadline=now + timedelta(hours=36),
    )

    model = PFZPointModel.from_pydantic(pt)
    reconstructed = model.to_pydantic()

    assert reconstructed.pfz_id == pt.pfz_id
    assert reconstructed.raw_geometry == pt.raw_geometry
    assert reconstructed.geometry_derivation == "line_midpoint_derived"
    assert reconstructed.validity_derivation == "orca_freshness_policy"
    assert reconstructed.source_valid_until is None
    assert reconstructed.freshness_deadline is not None