from __future__ import annotations

import os
import pytest
import httpx

from orca.translation.base import (
    TranslationError,
    TranslationRequest,
    TranslationResult,
    TranslationUnavailableError,
    UnsupportedLanguageError,
)
from orca.translation.bhashini import BhashiniTranslationAdapter
from orca.translation.mock import MockTranslationAdapter
from orca.translation.service import TieredTranslationService


def test_bhashini_unconfigured_raises_unavailable(monkeypatch):
    """Missing Bhashini credentials must produce an explicit unavailable state, never fabricated output."""
    monkeypatch.delenv("BHASHINI_API_KEY", raising=False)
    monkeypatch.delenv("ULCA_API_KEY", raising=False)
    monkeypatch.delenv("BHASHINI_USER_ID", raising=False)

    adapter = BhashiniTranslationAdapter()
    assert adapter.is_available() is False

    req = TranslationRequest(
        text="Potential Fishing Zone advisory for South Goa coast.",
        source_language="en",
        target_language="ml",
    )

    with pytest.raises(TranslationUnavailableError, match="credentials.*not configured"):
        import asyncio
        asyncio.run(adapter.translate(req))


@pytest.mark.asyncio
async def test_bhashini_mocked_http_pipeline_success(monkeypatch):
    """Verify Bhashini response parsing, language metadata, and provenance preservation."""
    sample_response_payload = {
        "pipelineResponse": [
            {
                "taskType": "translation",
                "output": [
                    {
                        "source": "Potential Fishing Zone advisory",
                        "target": "സാധ്യതയുള്ള മത്സ്യബന്ധന മേഖല മുന്നറിയിപ്പ്",
                    }
                ],
            }
        ]
    }

    class MockTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            assert request.headers.get("Authorization") == "mock_key_123"
            assert request.headers.get("userID") == "mock_user_456"
            return httpx.Response(200, json=sample_response_payload, request=request)

    adapter = BhashiniTranslationAdapter(
        api_key="mock_key_123",
        user_id="mock_user_456",
        pipeline_id="mock_pipe_789",
    )
    assert adapter.is_available() is True

    # Monkeypatch httpx.AsyncClient to use MockTransport
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: real_async_client(*args, transport=MockTransport(), **kwargs),
    )

    req = TranslationRequest(
        text="Potential Fishing Zone advisory",
        source_language="en",
        target_language="ml",
    )

    result = await adapter.translate(req)

    assert result.original_text == "Potential Fishing Zone advisory"
    assert result.translated_text == "സാധ്യതയുള്ള മത്സ്യബന്ധന മേഖല മുന്നറിയിപ്പ്"
    assert result.source_language == "en"
    assert result.target_language == "ml"
    assert result.provider == "bhashini"
    assert result.is_mock is False
    assert result.provenance["data_quality"] == "OPERATIONAL"
    assert result.provenance["service"] == "Bhashini (National Language Translation Mission)"


@pytest.mark.asyncio
async def test_mock_adapter_deterministic_lexicon():
    """Verify deterministic coastal Indic lexicon mappings with degraded provenance."""
    adapter = MockTranslationAdapter()
    assert adapter.is_available() is True

    # Malayalam PFZ
    res_ml = await adapter.translate(
        TranslationRequest(text="Potential Fishing Zone (PFZ)", source_language="en", target_language="ml")
    )
    assert res_ml.translated_text == "സാധ്യതയുള്ള മത്സ്യബന്ധന മേഖല (PFZ)"
    assert res_ml.is_mock is True
    assert res_ml.provenance["data_quality"] == "DEGRADED"
    assert res_ml.target_language == "ml"

    # Kannada Sea Surface Temperature
    res_kn = await adapter.translate(
        TranslationRequest(text="Sea Surface Temperature", source_language="en", target_language="kn")
    )
    assert res_kn.translated_text == "ಸಮುದ್ರದ ಮೇಲ್ಮೈ ತಾಪಮಾನ"
    assert res_kn.target_language == "kn"

    # Hindi High Wind Warning
    res_hi = await adapter.translate(
        TranslationRequest(text="High Wind Warning", source_language="en", target_language="hi")
    )
    assert res_hi.translated_text == "तेज हवा की चेतावनी"
    assert res_hi.target_language == "hi"

    # Tamil Advisory Warning
    res_ta = await adapter.translate(
        TranslationRequest(text="Advisory Warning", source_language="en", target_language="ta")
    )
    assert res_ta.translated_text == "எச்சரிக்கை அறிவிப்பு"
    assert res_ta.target_language == "ta"


@pytest.mark.asyncio
async def test_tiered_translation_service_fallback_behavior(monkeypatch):
    """Verify TieredTranslationService transparently falls back to mock with explicit reason and provenance."""
    monkeypatch.delenv("BHASHINI_API_KEY", raising=False)
    monkeypatch.delenv("BHASHINI_USER_ID", raising=False)

    service = TieredTranslationService(allow_fallback=True)
    assert service.is_available() is True

    req = TranslationRequest(
        text="Potential Fishing Zone (PFZ)",
        source_language="en",
        target_language="ml",
    )

    result = await service.translate(req)
    assert result.is_mock is True
    assert result.translated_text == "സാധ്യതയുള്ള മത്സ്യബന്ധന മേഖല (PFZ)"
    assert result.provenance["data_quality"] == "DEGRADED"
    assert result.provenance["fallback_reason"] == "primary_bhashini_unavailable_or_failed"

    # Strict mode without fallback
    strict_service = TieredTranslationService(allow_fallback=False)
    assert strict_service.is_available() is False
    with pytest.raises(TranslationUnavailableError):
        await strict_service.translate(req)


@pytest.mark.asyncio
async def test_unsupported_language_rejection():
    """Verify adapter rejects unsupported non-Indic language targets."""
    adapter = MockTranslationAdapter()
    req = TranslationRequest(
        text="Safe to Navigate",
        source_language="en",
        target_language="fr",  # French not in Indic lexicon
    )
    with pytest.raises(UnsupportedLanguageError, match="not supported"):
        await adapter.translate(req)


@pytest.mark.asyncio
async def test_bhashini_live_smoke_skip_without_credentials(monkeypatch):
    """Opt-in live smoke test: skips honestly when BHASHINI_API_KEY is absent."""
    if os.getenv("ORCA_LIVE_SMOKE") != "1":
        pytest.skip("Set ORCA_LIVE_SMOKE=1 to run live smoke tests.")

    if not os.getenv("BHASHINI_API_KEY"):
        pytest.skip("BHASHINI_API_KEY is not configured in this environment.")

    adapter = BhashiniTranslationAdapter()
    req = TranslationRequest(
        text="Marine advisory for coastal fishermen.",
        source_language="en",
        target_language="hi",
    )
    res = await adapter.translate(req)
    assert len(res.translated_text) > 0
    assert res.is_mock is False
