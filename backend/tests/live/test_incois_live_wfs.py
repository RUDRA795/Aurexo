"""Live operational smoke tests for INCOIS GeoServer WFS PFZ feature service.

OPT-IN ONLY:
These tests make real network requests to the live Indian National Centre
for Ocean Information Services (INCOIS) government servers.
They are executed ONLY when ORCA_LIVE_SMOKE=1.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
import pytest
import httpx

from orca.agents.pfz_pipeline import PFZSourceUnavailable
from orca.data.adapters.incois_pfz import DEFAULT_INCOIS_WFS_URL, INCOISPFZWebGISAdapter
from orca.schemas.orca_contract import Geometry
from orca.schemas.pfz_contract import PFZAccessTier, PFZPoint, PFZQuery

pytestmark = pytest.mark.skipif(
    os.getenv("ORCA_LIVE_SMOKE") != "1",
    reason="Live tests require ORCA_LIVE_SMOKE=1",
)


@pytest.mark.asyncio
async def test_live_incois_wfs_connectivity_and_ssl():
    """Verify live DNS, TLS/SSL certificate, HTTP 200, content-type, and latency."""
    url = os.getenv("INCOIS_PFZ_WFS_URL", DEFAULT_INCOIS_WFS_URL)
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": "pfzlines",
        "outputFormat": "application/json",
        "maxFeatures": "5",
    }

    start_time = time.perf_counter()
    async with httpx.AsyncClient(timeout=20.0, verify=True, follow_redirects=True) as client:
        response = await client.get(url, params=params)
    latency_ms = (time.perf_counter() - start_time) * 1000.0

    # 1. HTTP status
    assert response.status_code == 200, (
        f"INCOIS live WFS endpoint returned HTTP {response.status_code}: {response.text[:200]}"
    )

    # 2. Content-Type
    content_type = response.headers.get("content-type", "")
    assert "application/json" in content_type, (
        f"Unexpected Content-Type from INCOIS WFS: {content_type}"
    )

    # 3. Response size
    body = response.text
    assert len(body) > 200, f"Live response suspiciously short: {len(body)} bytes"

    # 4. Latency bound
    assert latency_ms < 20000.0, f"INCOIS live request exceeded 20s latency threshold: {latency_ms:.1f}ms"

    # 5. Parse JSON
    data = response.json()
    assert data.get("type") == "FeatureCollection"
    assert "features" in data
    assert isinstance(data["features"], list)
    assert len(data["features"]) > 0, "INCOIS live WFS returned empty features array"


@pytest.mark.asyncio
async def test_live_incois_wfs_schema_and_geometry():
    """Verify operational geometry structure and attribute schema on live INCOIS features."""
    url = os.getenv("INCOIS_PFZ_WFS_URL", DEFAULT_INCOIS_WFS_URL)
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": "pfzlines",
        "outputFormat": "application/json",
        "maxFeatures": "3",
    }

    async with httpx.AsyncClient(timeout=20.0, verify=True, follow_redirects=True) as client:
        response = await client.get(url, params=params)

    assert response.status_code == 200
    data = response.json()
    features = data["features"]
    assert len(features) > 0

    first_feat = features[0]
    # Geometry validation
    geom = first_feat.get("geometry", {})
    geom_type = geom.get("type")
    assert geom_type in ("MultiLineString", "LineString"), (
        f"Unexpected geometry type: {geom_type}"
    )
    coords = geom.get("coordinates")
    assert coords is not None and len(coords) > 0

    # Inspect coordinates to verify Indian Ocean bounds (approx lon 60-95, lat 5-30)
    flat_coords = coords[0] if geom_type == "MultiLineString" else coords
    assert len(flat_coords) > 0
    sample_pt = flat_coords[0]
    lon, lat = sample_pt[0], sample_pt[1]
    assert 50.0 <= lon <= 100.0, f"Live longitude out of Indian Ocean range: {lon}"
    assert 0.0 <= lat <= 35.0, f"Live latitude out of Indian coast range: {lat}"

    # Properties schema validation
    props = first_feat.get("properties", {})
    assert "State_Name" in props, f"Missing State_Name in properties: {props.keys()}"
    assert "Year" in props, f"Missing Year in properties: {props.keys()}"
    assert "Julian_day" in props, f"Missing Julian_day in properties: {props.keys()}"


@pytest.mark.asyncio
async def test_live_incois_adapter_fetch_and_provenance():
    """Verify that INCOISPFZWebGISAdapter successfully executes live with strict provenance."""
    adapter = INCOISPFZWebGISAdapter(verify_ssl=True, timeout_seconds=20.0)
    # Query across operational Indian waters without restricting to a single state sector
    query = PFZQuery(
        location=Geometry(lat=15.5, lon=73.5),
        valid_at=datetime.now(timezone.utc),
        sector=None,
    )

    result = await adapter.fetch(query)

    assert result.access_tier == PFZAccessTier.WEBGIS_LAYER
    assert result.source.organization == "INCOIS"
    assert result.source.authority == "official"
    assert len(result.points) > 0, "No operational PFZ points returned by live INCOIS WFS"

    sample_pt = result.points[0]
    assert sample_pt.raw_geometry is not None, "Original geometry not preserved in PFZPoint"
    assert sample_pt.geometry_derivation == "line_midpoint_derived"
    assert sample_pt.validity_derivation == "orca_freshness_policy"
    assert sample_pt.source_valid_until is None  # Accurately reflects that WFS has no expiry field
    assert sample_pt.freshness_deadline is not None  # ORCA-derived freshness deadline
    assert sample_pt.valid_until is not None    # Maintained for backward compatibility
