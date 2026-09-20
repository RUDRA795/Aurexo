from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping

from orca.safety.sanitizer import validate_coordinates


@dataclass(frozen=True)
class GeographicRegionPolicy:
    """Configurable operational bounding box policy for maritime intelligence operations."""
    region_id: str
    name: str
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

    def contains(self, lat: float, lon: float) -> bool:
        """Check if coordinates fall within this geographic region."""
        valid_lat, valid_lon = validate_coordinates(lat, lon)
        return (
            self.min_lat <= valid_lat <= self.max_lat
            and self.min_lon <= valid_lon <= self.max_lon
        )


# Predefined marine operational zones
PREDEFINED_REGIONS: Mapping[str, GeographicRegionPolicy] = {
    "INDIAN_OCEAN": GeographicRegionPolicy(
        region_id="INDIAN_OCEAN",
        name="Indian Ocean Maritime Region",
        min_lat=-15.0,
        max_lat=30.0,
        min_lon=50.0,
        max_lon=105.0,
    ),
    "ARABIAN_SEA": GeographicRegionPolicy(
        region_id="ARABIAN_SEA",
        name="Arabian Sea (West Coast India)",
        min_lat=8.0,
        max_lat=26.0,
        min_lon=60.0,
        max_lon=78.0,
    ),
    "BAY_OF_BENGAL": GeographicRegionPolicy(
        region_id="BAY_OF_BENGAL",
        name="Bay of Bengal (East Coast India)",
        min_lat=5.0,
        max_lat=23.0,
        min_lon=80.0,
        max_lon=98.0,
    ),
    "GLOBAL": GeographicRegionPolicy(
        region_id="GLOBAL",
        name="Global Maritime Region",
        min_lat=-90.0,
        max_lat=90.0,
        min_lon=-180.0,
        max_lon=180.0,
    ),
}


def get_operational_region_policy() -> GeographicRegionPolicy:
    """Get the active operational region policy based on environment configuration."""
    region_key = os.getenv("ORCA_OPERATIONAL_REGION", "INDIAN_OCEAN").strip().upper()
    return PREDEFINED_REGIONS.get(region_key, PREDEFINED_REGIONS["INDIAN_OCEAN"])


def is_within_operational_region(lat: float, lon: float) -> bool:
    """Check if coordinates fall within the currently configured operational region."""
    policy = get_operational_region_policy()
    return policy.contains(lat, lon)
