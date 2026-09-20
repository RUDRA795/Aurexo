from __future__ import annotations

import time
from typing import Any

from orca.telemetry.tracer import trace_span
from orca.translation.base import (
    TranslationProvider,
    TranslationRequest,
    TranslationResult,
    UnsupportedLanguageError,
)

# Verified marine intelligence terminology dictionary across coastal Indic languages
DETERMINISTIC_MARINE_LEXICON: dict[str, dict[str, str]] = {
    "potential fishing zone (pfz)": {
        "ml": "സാധ്യതയുള്ള മത്സ്യബന്ധന മേഖല (PFZ)",
        "kn": "ಸಂಭಾವ್ಯ ಮೀನುಗಾರಿಕಾ ವಲಯ (PFZ)",
        "hi": "संभावित मत्स्य पालन क्षेत्र (PFZ)",
        "ta": "சாத்தியமான மீன்பிடி மண்டலம் (PFZ)",
        "te": "సంభావ్య మత్స్య వేట ప్రాంతం (PFZ)",
    },
    "sea surface temperature": {
        "ml": "സമുദ്രോപരിതല താപനില",
        "kn": "ಸಮುದ್ರದ ಮೇಲ್ಮೈ ತಾಪಮಾನ",
        "hi": "समुद्र की सतह का तापमान",
        "ta": "கடல் மேற்பரப்பு வெப்பநிலை",
        "te": "సముద్ర ఉపరితల ఉష్ణోగ్రత",
    },
    "chlorophyll-a concentration": {
        "ml": "ക്ലോറോഫിൽ-എ സാന്ദ്രത",
        "kn": "ಕ್ಲೋರೊಫಿಲ್-ಎ ಸಾಂದ್ರತೆ",
        "hi": "क्लोरोफिल-ए सांद्रता",
        "ta": "குளோரோபில்-ஏ செறிவு",
        "te": "క్లోరోఫిల్-ఎ సాంద్రత",
    },
    "advisory warning": {
        "ml": "മുന്നറിയിപ്പ് സന്ദേശം",
        "kn": "ಎಚ್ಚರಿಕೆ ಸಂದೇಶ",
        "hi": "सलाहकार चेतावनी",
        "ta": "எச்சரிக்கை அறிவிப்பு",
        "te": "హెచ్చరిక ప్రకటన",
    },
    "high wind warning": {
        "ml": "ശക്തമായ കാറ്റ് മുന്നറിയിപ്പ്",
        "kn": "ಭಾರಿ ಗಾಳಿ ಎಚ್ಚರಿಕೆ",
        "hi": "तेज हवा की चेतावनी",
        "ta": "அதிவேக காற்று எச்சரிக்கை",
        "te": "తీవ్రమైన గాలి హెచ్చరిక",
    },
    "safe to navigate": {
        "ml": "യാത്ര സുരക്ഷിതമാണ്",
        "kn": "ಸಂಚಾರಕ್ಕೆ ಸುರಕ್ಷಿತ",
        "hi": "नेविगेशन के लिए सुरक्षित",
        "ta": "பயணம் செய்ய பாதுகாப்பானது",
        "te": "ప్రయాణానికి సురక్షితం",
    },
    "fish aggregation likely": {
        "ml": "മത്സ്യക്കൂട്ടം ഉണ്ടാകാൻ സാധ്യതയുണ്ട്",
        "kn": "ಮೀನುಗಳ ಗುಂಪು ಸೇರುವ ಸಾಧ್ಯತೆ ಇದೆ",
        "hi": "मछलियों का जमाव संभावित",
        "ta": "மீன்கள் திரள வாய்ப்புள்ளது",
        "te": "చేపల సమూహం ఏర్పడే అవకాశం ఉంది",
    },
}

SUPPORTED_MOCK_LANGUAGES = {"ml", "kn", "hi", "ta", "te", "en"}


class MockTranslationAdapter(TranslationProvider):
    """Deterministic offline translation provider for unit testing and degraded fallback."""

    def __init__(self, simulated_delay_ms: float = 0.0) -> None:
        self.simulated_delay_ms = simulated_delay_ms

    def is_available(self) -> bool:
        return True

    async def translate(self, request: TranslationRequest) -> TranslationResult:
        target_lang = request.target_language.lower()
        if target_lang not in SUPPORTED_MOCK_LANGUAGES:
            raise UnsupportedLanguageError(
                f"Target language '{request.target_language}' is not supported by Mock translation adapter."
            )

        start_time = time.perf_counter()

        with trace_span(
            "translation.mock.translate",
            attributes={
                "source_language": request.source_language,
                "target_language": request.target_language,
                "is_mock": True,
            },
        ):
            text_lower = request.text.strip().lower()

            # Exact dictionary match check
            if text_lower in DETERMINISTIC_MARINE_LEXICON and target_lang in DETERMINISTIC_MARINE_LEXICON[text_lower]:
                translated = DETERMINISTIC_MARINE_LEXICON[text_lower][target_lang]
            else:
                # Deterministic term replacement
                translated = request.text
                for phrase, translations in DETERMINISTIC_MARINE_LEXICON.items():
                    if phrase in translated.lower() and target_lang in translations:
                        import re
                        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
                        translated = pattern.sub(translations[target_lang], translated)

                # If no phrases were replaced and source != target, prefix with language tag
                if translated == request.text and target_lang != request.source_language:
                    translated = f"[{target_lang.upper()}] {request.text}"

            latency = (time.perf_counter() - start_time) * 1000.0

            return TranslationResult(
                original_text=request.text,
                translated_text=translated,
                source_language=request.source_language,
                target_language=request.target_language,
                provider="mock_marine_dictionary",
                is_mock=True,
                latency_ms=round(latency, 2),
                provenance={
                    "service": "ORCA Deterministic Offline Translation Lexicon",
                    "data_quality": "DEGRADED",
                    "is_mock": True,
                    "provider": "mock_marine_dictionary",
                },
            )
