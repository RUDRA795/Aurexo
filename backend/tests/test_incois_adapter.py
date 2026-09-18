from datetime import datetime, timedelta, timezone
import pytest
import httpx

from orca.agents.pfz_pipeline import PFZSourceUnavailable
from orca.data.adapters.incois_pfz import INCOISPFZWebGISAdapter
from orca.data.adapters.incois_text_advisory import INCOISTextAdvisoryAdapter
from orca.schemas.orca_contract import AccessMethod, Geometry, utc_now
from orca.schemas.pfz_contract import PFZAccessTier, PFZQuery


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
        "Shape_Area": 2.9145,
        "State_Name": "GOA",
        "Julian_day": "261",
        "Year": 2026,
        "UID": "2026261001",
        "Length": 21.936,
    },
}

SAMPLE_WFS_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        SAMPLE_WFS_FEATURE,
        {
            "type": "Feature",
            "id": "pfzlines.2",
            "geometry": {
                "type": "MultiLineString",
                "coordinates": [
                    [
                        [72.42608614, 20.13159465],
                        [72.42561853, 20.13134941],
                    ]
                ],
            },
            "properties": {
                "Shape_Leng": 15.079,
                "State_Name": "MAHARASHTRA",
                "Julian_day": "261",
                "Year": 2026,
                "UID": "2026261002",
                "Length": 18.5,
            },
        },
    ],
}


def test_parse_valid_geojson_normalizes_to_pfz_point():
    adapter = INCOISPFZWebGISAdapter()
    now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
    query = PFZQuery(location=Geometry(lat=15.5, lon=73.5), valid_at=now)

    points = adapter.parse_geojson(SAMPLE_WFS_GEOJSON, query=query)
    assert len(points) == 2

    goa_pt = points[0]
    assert goa_pt.pfz_id == "incois_2026261001"
    assert goa_pt.sector == "GOA"
    assert 15.6 < goa_pt.location.lat < 15.7
    assert 73.2 < goa_pt.location.lon < 73.3
    assert goa_pt.forecast_date == datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=260)
    assert goa_pt.valid_until == goa_pt.valid_from + timedelta(hours=36)


def test_deduplication_of_duplicate_features():
    adapter = INCOISPFZWebGISAdapter()
    payload = {
        "type": "FeatureCollection",
        "features": [SAMPLE_WFS_FEATURE, SAMPLE_WFS_FEATURE],
    }
    points = adapter.parse_geojson(payload)
    assert len(points) == 1


def test_invalid_coordinates_handling():
    adapter = INCOISPFZWebGISAdapter()
    bad_coords_feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[999.0, -999.0], [73.0, 15.0]],
        },
        "properties": {"State_Name": "GOA", "UID": "bad_coord_1"},
    }
    nan_coords_feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[float("nan"), 15.0], [73.0, 15.0]],
        },
        "properties": {"State_Name": "GOA", "UID": "bad_coord_2"},
    }
    payload = {
        "type": "FeatureCollection",
        "features": [bad_coords_feature, nan_coords_feature, SAMPLE_WFS_FEATURE],
    }
    points = adapter.parse_geojson(payload)
    assert len(points) == 1
    assert points[0].pfz_id == "incois_2026261001"


def test_missing_fields_graceful_handling():
    adapter = INCOISPFZWebGISAdapter()
    missing_props = {"type": "Feature", "geometry": SAMPLE_WFS_FEATURE["geometry"]}
    missing_geom = {"type": "Feature", "properties": {"State_Name": "GOA"}}
    empty_feat = {}
    payload = {
        "type": "FeatureCollection",
        "features": [missing_props, missing_geom, empty_feat, SAMPLE_WFS_FEATURE],
    }
    points = adapter.parse_geojson(payload)
    # Only valid feature and valid geometry with default props are processed
    assert len(points) >= 1
    assert any(p.pfz_id == "incois_2026261001" for p in points)


def test_stale_data_rejection():
    adapter = INCOISPFZWebGISAdapter()
    stale_feature = {
        "type": "Feature",
        "geometry": SAMPLE_WFS_FEATURE["geometry"],
        "properties": {
            "State_Name": "GOA",
            "Year": 2025,  # previous year
            "Julian_day": "100",
            "UID": "stale_001",
        },
    }
    payload = {"type": "FeatureCollection", "features": [stale_feature]}
    now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
    query = PFZQuery(location=Geometry(lat=15.5, lon=73.5), valid_at=now)

    points = adapter.parse_geojson(payload, query=query)
    # Stale point must be rejected
    assert len(points) == 0


def test_malformed_response_raises():
    adapter = INCOISPFZWebGISAdapter()
    with pytest.raises(PFZSourceUnavailable, match="missing required 'features'"):
        adapter.parse_geojson({"status": "error", "message": "unauthorized"})


def test_evidence_provenance_metadata():
    metadata = INCOISPFZWebGISAdapter.get_source_metadata()
    assert metadata.source_id == "incois_pfz_webgis"
    assert metadata.organization == "INCOIS"
    assert metadata.authority == "official"
    assert metadata.access == AccessMethod.WEBGIS
    assert metadata.freshness_policy_hours == 36.0


@pytest.mark.asyncio
async def test_network_timeout_handling(monkeypatch):
    adapter = INCOISPFZWebGISAdapter(timeout_seconds=0.01)

    async def mock_get(*args, **kwargs):
        raise httpx.TimeoutException("Connection timed out")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    query = PFZQuery(location=Geometry(lat=15.5, lon=73.5), valid_at=utc_now())
    with pytest.raises(PFZSourceUnavailable, match="timed out"):
        await adapter.fetch(query)


@pytest.mark.asyncio
async def test_http_status_error_handling(monkeypatch):
    adapter = INCOISPFZWebGISAdapter()

    class MockResponse:
        status_code = 503
        text = "Service Unavailable"

    async def mock_get(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    query = PFZQuery(location=Geometry(lat=15.5, lon=73.5), valid_at=utc_now())
    with pytest.raises(PFZSourceUnavailable, match="HTTP 503"):
        await adapter.fetch(query)


def test_text_advisory_adapter_bulletin_parsing():
    bulletin_records = [
        {
            "sector": "GOA",
            "landing_center": "MALIM",
            "distance_km": 35.0,
            "bearing_deg": 265.0,
            "depth_m": 45.0,
            "wind_speed_ms": 6.5,
            "wind_direction_deg": 210.0,
        },
        {
            "sector": "MAHARASHTRA",
            "landing_center": "RATNAGIRI",
            "distance_km": 40.0,
            "bearing_deg": 250.0,
            "depth_m": 60.0,
        },
    ]
    adapter = INCOISTextAdvisoryAdapter(bulletins=bulletin_records)
    query = PFZQuery(location=Geometry(lat=15.5, lon=73.8), valid_at=utc_now(), sector="GOA")

    points = adapter.parse_bulletin_records(bulletin_records, query=query)
    assert len(points) == 1
    pt = points[0]
    assert pt.sector == "GOA"
    assert pt.landing_center == "MALIM"
    assert pt.depth_m == 45.0
    assert pt.wind_speed_ms == 6.5
    assert pt.location.lat > 0 and pt.location.lon > 0
