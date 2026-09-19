from __future__ import annotations

import math
import re


class PromptInjectionError(ValueError):
    """Raised when an input contains explicit prompt injection attack signatures."""
    pass


class CoordinateValidationError(ValueError):
    """Raised when coordinates fall outside physically valid or authorized ranges."""
    pass


# Prompt injection regex patterns
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|im_end\|>", re.IGNORECASE),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"\[/INST\]", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(in\s+)?developer\s+mode", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?guidelines?", re.IGNORECASE),
)


def validate_coordinates(lat: float, lon: float) -> tuple[float, float]:
    """Validate latitude and longitude ranges.
    
    Latitude must be in [-90.0, 90.0]
    Longitude must be in [-180.0, 180.0]
    Both must be finite numbers.
    """
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        raise CoordinateValidationError(f"Coordinates must be numbers, got lat={type(lat)}, lon={type(lon)}")

    if not math.isfinite(lat) or not math.isfinite(lon):
        raise CoordinateValidationError(f"Coordinates must be finite, got lat={lat}, lon={lon}")

    if not (-90.0 <= lat <= 90.0):
        raise CoordinateValidationError(f"Latitude {lat} is out of bounds [-90.0, 90.0].")

    if not (-180.0 <= lon <= 180.0):
        raise CoordinateValidationError(f"Longitude {lon} is out of bounds [-180.0, 180.0].")

    return float(lat), float(lon)


def is_within_indian_ocean(lat: float, lon: float) -> bool:
    """Check if coordinates fall within the broader Indian Ocean marine area.
    
    Approximated as:
    Latitude: -15.0° to 30.0° N
    Longitude: 50.0° to 100.0° E
    """
    lat, lon = validate_coordinates(lat, lon)
    return -15.0 <= lat <= 30.0 and 50.0 <= lon <= 100.0


def sanitize_text_query(query: str, *, max_length: int = 1000, reject_injection: bool = True) -> str:
    """Sanitize user query string, stripping control characters and checking for prompt injection.
    
    Raises:
        PromptInjectionError: If malicious injection keywords are detected and reject_injection is True.
        ValueError: If input is empty or exceeds max_length.
    """
    if not isinstance(query, str):
        raise ValueError("Query must be a string.")

    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Query cannot be empty.")

    # Remove null bytes and control chars
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)

    if len(cleaned) > max_length:
        raise ValueError(f"Query exceeds maximum allowed length of {max_length} characters.")

    if reject_injection:
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(cleaned):
                raise PromptInjectionError(f"Potential prompt injection pattern detected: '{pattern.pattern}'")

    return cleaned
