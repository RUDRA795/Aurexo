from __future__ import annotations

import os
import time
from typing import Any

import httpx

from orca.safety.ssrf import SSRFSecurityError, validate_url_for_ssrf
from orca.telemetry.tracer import trace_span
from orca.translation.base import (
    TranslationError,
    TranslationProvider,
    TranslationRequest,
    TranslationResult,
    TranslationUnavailableError,
    UnsupportedLanguageError,
)

DEFAULT_BHASHINI_ENDPOINT = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
SUPPORTED_INDIC_LANGUAGES = {"hi", "ml", "kn", "ta", "te", "bn", "gu", "mr", "or", "pa", "as"}


class BhashiniTranslationAdapter(TranslationProvider):
    """Adapter for Government of India Bhashini (ULCA) neural machine translation services."""

    def __init__(
        self,
        api_key: str | None = None,
        user_id: str | None = None,
        pipeline_id: str | None = None,
        endpoint: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.api_key = api_key or os.getenv("BHASHINI_API_KEY") or os.getenv("ULCA_API_KEY")
        self.user_id = user_id or os.getenv("BHASHINI_USER_ID")
        self.pipeline_id = pipeline_id or os.getenv("BHASHINI_PIPELINE_ID", "643ba40cbdc8300c16767397")
        self.endpoint = endpoint or os.getenv("BHASHINI_INFERENCE_URL", DEFAULT_BHASHINI_ENDPOINT)
        self.timeout = timeout

    def is_available(self) -> bool:
        """Check if required Bhashini API credentials are present."""
        return bool(self.api_key and self.user_id)

    async def translate(self, request: TranslationRequest) -> TranslationResult:
        """Translate text using Bhashini NMT inference pipeline."""
        if not self.is_available():
            raise TranslationUnavailableError(
                "Bhashini API credentials (BHASHINI_API_KEY, BHASHINI_USER_ID) not configured in environment."
            )

        target_lang = request.target_language.lower()
        if target_lang not in SUPPORTED_INDIC_LANGUAGES and target_lang != "en":
            raise UnsupportedLanguageError(
                f"Target language '{request.target_language}' is not supported by Bhashini adapter."
            )

        # Validate endpoint against SSRF rules
        if not self.endpoint.startswith("mock://"):
            try:
                validate_url_for_ssrf(self.endpoint, check_dns=False)
            except SSRFSecurityError as err:
                raise TranslationError(f"Bhashini endpoint blocked by SSRF validation: {err}") from err

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": self.api_key or "",
            "userID": self.user_id or "",
            "ulcaApiKey": self.api_key or "",
        }

        payload: dict[str, Any] = {
            "pipelineTasks": [
                {
                    "taskType": "translation",
                    "config": {
                        "language": {
                            "sourceLanguage": request.source_language,
                            "targetLanguage": request.target_language,
                        }
                    },
                }
            ],
            "inputData": {
                "input": [
                    {
                        "source": request.text,
                    }
                ]
            },
        }

        start_time = time.perf_counter()
        with trace_span(
            "translation.bhashini.translate",
            attributes={
                "source_language": request.source_language,
                "target_language": request.target_language,
                "domain": request.domain,
                "endpoint": self.endpoint,
            },
        ):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(self.endpoint, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
            except httpx.HTTPStatusError as exc:
                raise TranslationError(f"Bhashini API HTTP error {exc.response.status_code}: {exc}") from exc
            except httpx.RequestError as exc:
                raise TranslationError(f"Bhashini API connection error: {exc}") from exc

            latency = (time.perf_counter() - start_time) * 1000.0

            try:
                pipeline_res = data.get("pipelineResponse", [])
                if not pipeline_res:
                    raise ValueError("No pipelineResponse found in Bhashini response")
                output_list = pipeline_res[0].get("output", [])
                if not output_list:
                    raise ValueError("No output found in Bhashini pipelineResponse")
                translated = output_list[0].get("target")
                if not translated:
                    raise ValueError("Empty target translation in Bhashini output")
            except Exception as exc:
                raise TranslationError(f"Failed to parse Bhashini translation response: {exc}") from exc

            return TranslationResult(
                original_text=request.text,
                translated_text=translated,
                source_language=request.source_language,
                target_language=request.target_language,
                provider="bhashini",
                is_mock=False,
                latency_ms=round(latency, 2),
                provenance={
                    "service": "Bhashini (National Language Translation Mission)",
                    "endpoint": self.endpoint,
                    "pipeline_id": self.pipeline_id,
                    "data_quality": "OPERATIONAL",
                },
            )
