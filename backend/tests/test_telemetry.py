from __future__ import annotations

import os
import pytest
from opentelemetry.trace import StatusCode

from orca.telemetry.tracer import (
    InMemorySpanExporter,
    get_tracer,
    is_sensitive_key,
    redact_attribute_value,
    sanitize_attributes,
    sanitize_string,
    setup_telemetry,
    trace_span,
    traced,
)
from orca.schemas.orca_contract import Geometry
from orca.schemas.pfz_contract import PFZPoint, PFZQueryResult, PFZQuery, PFZAccessTier


@pytest.fixture(autouse=True)
def otel_test_environment():
    """Setup isolated in-memory OpenTelemetry tracer provider for each test."""
    exporter = InMemorySpanExporter()
    provider = setup_telemetry(service_name="orca-test-telemetry", exporter=exporter, force_reset=True)
    yield exporter
    exporter.clear()


def test_secret_redaction_unit():
    """Verify that sensitive key substrings and credentials in URLs/headers are reliably redacted."""
    # Key check
    assert is_sensitive_key("password") is True
    assert is_sensitive_key("COPERNICUS_PASSWORD") is True
    assert is_sensitive_key("bhashini_api_key") is True
    assert is_sensitive_key("auth_token") is True
    assert is_sensitive_key("session_cookie") is True
    assert is_sensitive_key("safe_parameter") is False

    # Value redaction
    assert redact_attribute_value("copernicus_password", "SuperSecret123!") == "[REDACTED]"
    assert redact_attribute_value("api_key", "sk-1234567890abcdef") == "[REDACTED]"

    # String sanitization in URLs
    dirty_url = "https://alice:supersecret99@thredds.copernicus.eu/dodsC/data?token=xyz123&api_key=456"
    clean_url = sanitize_string(dirty_url)
    assert "supersecret99" not in clean_url
    assert "xyz123" not in clean_url
    assert "456" not in clean_url
    assert clean_url == "https://alice:[REDACTED]@thredds.copernicus.eu/dodsC/data?token=[REDACTED]&api_key=[REDACTED]"

    # Bearer tokens
    header_val = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sensitive_payload"
    assert sanitize_string(header_val) == "Bearer [REDACTED]"


def test_span_recording_and_attributes(otel_test_environment):
    """Verify trace_span captures sanitized attributes and status deterministically."""
    exporter = otel_test_environment

    attrs = {
        "sector": "GOA",
        "api_key": "secret_key_to_mask",
        "nested_dict": {"token": "sub_token", "normal": "safe_val"},
        "url": "https://service.gov.in/query?token=secret_param",
    }

    with trace_span("test.manual_span", attributes=attrs) as span:
        span.set_attribute("runtime_attr", 42)

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span_data = spans[0]
    assert span_data.name == "test.manual_span"

    attributes = dict(span_data.attributes)
    assert attributes["sector"] == "GOA"
    assert attributes["api_key"] == "[REDACTED]"
    assert "secret_key_to_mask" not in str(attributes)
    assert "secret_param" not in str(attributes)
    assert attributes["runtime_attr"] == 42
    assert span_data.status.status_code == StatusCode.UNSET


def test_span_exception_capture(otel_test_environment):
    """Verify exceptions in trace_span set error status and record exception events without silencing."""
    exporter = otel_test_environment

    with pytest.raises(ValueError, match="simulated failure"):
        with trace_span("test.failing_operation", attributes={"operation": "critical_task"}):
            raise ValueError("simulated failure")

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span_data = spans[0]
    assert span_data.name == "test.failing_operation"
    assert span_data.status.status_code == StatusCode.ERROR
    assert "simulated failure" in span_data.status.description

    # Verify exception event recorded
    events = span_data.events
    assert len(events) >= 1
    assert any(e.name == "exception" for e in events)


@pytest.mark.asyncio
async def test_traced_decorator_sync_and_async(otel_test_environment):
    """Verify @traced decorator on both synchronous and asynchronous functions."""
    exporter = otel_test_environment

    @traced("sync.task")
    def sync_compute(x: int, password: str = "secret") -> int:
        return x * 2

    @traced("async.task")
    async def async_compute(y: int, auth_token: str = "token123") -> int:
        return y + 10

    res1 = sync_compute(5, password="my_password")
    res2 = await async_compute(20, auth_token="my_token")

    assert res1 == 10
    assert res2 == 30

    spans = exporter.get_finished_spans()
    assert len(spans) == 2
    span_names = [s.name for s in spans]
    assert "sync.task" in span_names
    assert "async.task" in span_names

    # Check argument redaction
    for s in spans:
        attrs = dict(s.attributes)
        for k, v in attrs.items():
            if "password" in k or "token" in k:
                assert v == "[REDACTED]"


@pytest.mark.asyncio
async def test_langgraph_nodes_telemetry_emission(otel_test_environment):
    """Verify that OrcaGraph workflow execution emits spans for all agent nodes."""
    exporter = otel_test_environment
    from orca.agents.graph import create_orca_graph
    from orca.schemas.orca_contract import DataQuality, SourceMetadata, utc_now

    from datetime import timedelta
    now = utc_now()
    dummy_point = PFZPoint(
        pfz_id="PFZ_TEL_01",
        sector="GOA",
        location=Geometry(lat=15.2, lon=73.5),
        source_valid_from=now - timedelta(hours=2),
        source_valid_until=None,
        freshness_deadline=now + timedelta(hours=24),
    )

    class DummyPFZSource:
        async def fetch(self, query: PFZQuery) -> PFZQueryResult:
            return PFZQueryResult(
                points=[dummy_point],
                access_tier=PFZAccessTier.WEBGIS_LAYER,
                source=SourceMetadata(
                    source_id="test_pfz",
                    organization="INCOIS",
                    dataset="Test Dataset",
                    domain=["pfz"],
                    coverage="goa",
                    authority="official",
                    freshness_policy_hours=24.0,
                ),
                retrieved_at=utc_now(),
            )

    class DummySSTAdapter:
        def extract_sst(self, location: Geometry):
            return None

    class DummyCHLAdapter:
        def extract_chlorophyll(self, location: Geometry):
            return None

    class DummyWeatherAdapter:
        async def fetch_forecast(self, location: Geometry):
            return None

    graph = create_orca_graph(
        pfz_sources=[DummyPFZSource()],
        sst_adapter=DummySSTAdapter(),
        chl_adapter=DummyCHLAdapter(),
        weather_adapter=DummyWeatherAdapter(),
    )
    input_state = {
        "user_query": "PFZ near Goa with sea surface temperature",
        "coordinates": Geometry(lat=15.2, lon=73.5),
        "sector": "GOA",
    }

    result = await graph.ainvoke(input_state)
    assert result["final_answer"] is not None

    spans = exporter.get_finished_spans()
    span_names = [s.name for s in spans]

    assert "orca.graph.supervisor_node" in span_names
    assert "orca.graph.pfz_agent_node" in span_names
    assert "orca.graph.environment_agent_node" in span_names
    assert "orca.graph.safety_validation_node" in span_names
    assert "orca.graph.synthesizer_node" in span_names


def test_copernicus_adapter_trace_redaction(otel_test_environment, monkeypatch):
    """Verify CopernicusMarineAdapter emits trace spans with redacted password attributes."""
    exporter = otel_test_environment
    import xarray as xr
    import numpy as np
    from orca.data.adapters.copernicus_marine import CopernicusMarineAdapter

    mock_ds = xr.Dataset(
        data_vars={"thetao": (["lat", "lon"], np.array([[29.5, 29.8], [29.1, 29.4]], dtype=np.float32))},
        coords={"lat": [14.0, 16.0], "lon": [72.0, 74.0]},
    )
    monkeypatch.setattr(xr, "open_dataset", lambda *args, **kwargs: mock_ds)

    adapter = CopernicusMarineAdapter(
        endpoint_url="mock://copernicus/sst.nc",
        username="orca_scientist",
        password="TopSecretCopernicusPassword!",
    )

    ev = adapter.extract_sst(Geometry(lat=15.0, lon=73.0))
    assert ev.value > 0

    spans = exporter.get_finished_spans()
    copernicus_spans = [s for s in spans if s.name == "adapter.copernicus_marine.extract_sst"]
    assert len(copernicus_spans) == 1
    cop_attrs = dict(copernicus_spans[0].attributes)

    assert cop_attrs["username"] == "orca_scientist"
    assert cop_attrs["password"] == "[REDACTED]"
    assert "TopSecretCopernicusPassword!" not in str(cop_attrs)
