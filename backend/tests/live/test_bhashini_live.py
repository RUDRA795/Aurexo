"""Live operational smoke tests for Bhashini Indic translation services (opt-in via ORCA_LIVE_SMOKE=1)."""
import os
import pytest

from orca.translation.base import TranslationRequest
from orca.translation.bhashini import BhashiniTranslationAdapter

pytestmark = pytest.mark.skipif(
    os.getenv("ORCA_LIVE_SMOKE") != "1",
    reason="Live network smoke tests disabled. Enable by setting ORCA_LIVE_SMOKE=1.",
)


@pytest.mark.asyncio
async def test_bhashini_live_smoke():
    """Verify live connectivity against Government of India Bhashini NMT API if credentials exist."""
    api_key = os.getenv("BHASHINI_API_KEY") or os.getenv("ULCA_API_KEY")
    user_id = os.getenv("BHASHINI_USER_ID")

    if not api_key or not user_id:
        pytest.skip("BHASHINI_API_KEY and BHASHINI_USER_ID not configured; live Bhashini smoke skipped.")

    adapter = BhashiniTranslationAdapter(api_key=api_key, user_id=user_id)
    req = TranslationRequest(
        text="Potential Fishing Zone advisory for coastal fishermen.",
        source_language="en",
        target_language="hi",
    )
    result = await adapter.translate(req)

    assert result is not None
    assert len(result.translated_text) > 0
    assert result.is_mock is False
    assert result.provider == "bhashini"
