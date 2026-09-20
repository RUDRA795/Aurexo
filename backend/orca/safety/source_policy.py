from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Mapping

from orca.schemas.orca_contract import Evidence


class SourceTrustTier(str, Enum):
    OPERATIONAL = "OPERATIONAL"    # Government/authorized operational agency (INCOIS, NOAA, CMEMS)
    SCIENTIFIC = "SCIENTIFIC"      # Research/academic institutions (NASA, ISRO science feeds)
    COMMERCIAL = "COMMERCIAL"      # Commercial/AIS data providers
    UNTRUSTED = "UNTRUSTED"        # Unverified, scraping, or unknown third-party


@dataclass(frozen=True)
class SourcePolicy:
    source_id: str
    organization: str
    trust_tier: SourceTrustTier
    authorized_variables: tuple[str, ...]
    max_freshness_hours: float
    description: str = ""


# Default policy configurations for certified marine data providers
DEFAULT_SOURCE_POLICIES: Mapping[str, SourcePolicy] = {
    "incois_wfs": SourcePolicy(
        source_id="incois_wfs",
        organization="INCOIS",
        trust_tier=SourceTrustTier.OPERATIONAL,
        authorized_variables=("pfz_point", "pfz_line", "pfz_zone"),
        max_freshness_hours=36.0,
        description="Official INCOIS WebGIS WFS Potential Fishing Zones",
    ),
    "incois_osf_sst": SourcePolicy(
        source_id="incois_osf_sst",
        organization="INCOIS",
        trust_tier=SourceTrustTier.OPERATIONAL,
        authorized_variables=("sea_surface_temperature", "sst"),
        max_freshness_hours=48.0,
        description="INCOIS Ocean State Forecast Sea Surface Temperature",
    ),
    "incois_viirs_chl": SourcePolicy(
        source_id="incois_viirs_chl",
        organization="INCOIS",
        trust_tier=SourceTrustTier.OPERATIONAL,
        authorized_variables=("chlorophyll_a", "chlorophyll_concentration", "chlorophyll"),
        max_freshness_hours=72.0,
        description="INCOIS Ocean Color Chlorophyll-a concentration",
    ),
    "incois_text_bulletin": SourcePolicy(
        source_id="incois_text_bulletin",
        organization="INCOIS",
        trust_tier=SourceTrustTier.OPERATIONAL,
        authorized_variables=("pfz_point", "advisory_bulletin", "advisory_context"),
        max_freshness_hours=48.0,
        description="INCOIS Multilingual Coastal Text Advisories",
    ),
    "incois_osf_ocean_state": SourcePolicy(
        source_id="incois_osf_ocean_state",
        organization="INCOIS",
        trust_tier=SourceTrustTier.OPERATIONAL,
        authorized_variables=(
            "ocean_state",
            "significant_wave_height",
            "wave_period",
            "swell",
            "swell_height",
            "surface_current",
            "wind",
            "wind_speed",
            "sea_surface_temperature",
        ),
        max_freshness_hours=24.0,
        description="INCOIS Ocean State Forecast (wind, waves, swell, currents)",
    ),
    "imd_marine_warning": SourcePolicy(
        source_id="imd_marine_warning",
        organization="India Meteorological Department",
        trust_tier=SourceTrustTier.OPERATIONAL,
        authorized_variables=(
            "fishermen_warning",
            "marine_warning",
            "coastal_weather",
            "meteorology",
            "marine_meteorology",
        ),
        max_freshness_hours=12.0,
        description="IMD Coastal Marine Weather Bulletin & Fishermen Warnings",
    ),
    "noaa_nws_weather": SourcePolicy(
        source_id="noaa_nws_weather",
        organization="NOAA National Weather Service",
        trust_tier=SourceTrustTier.OPERATIONAL,
        authorized_variables=("marine_weather_forecast", "wind_speed", "wave_height", "temperature"),
        max_freshness_hours=12.0,
        description="NOAA NWS Marine & Coastal Forecast",
    ),
    "noaa_weather": SourcePolicy(
        source_id="noaa_weather",
        organization="NOAA National Weather Service",
        trust_tier=SourceTrustTier.OPERATIONAL,
        authorized_variables=("marine_weather_forecast", "wind_speed", "wave_height", "temperature"),
        max_freshness_hours=12.0,
        description="NOAA NWS Marine & Coastal Forecast",
    ),
    "copernicus_marine_service": SourcePolicy(
        source_id="copernicus_marine_service",
        organization="Copernicus Marine Service (EUMETSAT/Mercator Ocean)",
        trust_tier=SourceTrustTier.OPERATIONAL,
        authorized_variables=("sea_surface_temperature", "salinity", "ocean_currents"),
        max_freshness_hours=48.0,
        description="CMEMS Global Ocean Physical Analysis and Forecast",
    ),
    "bhashini_nmt": SourcePolicy(
        source_id="bhashini_nmt",
        organization="Bhashini (National Language Translation Mission)",
        trust_tier=SourceTrustTier.OPERATIONAL,
        authorized_variables=("translation", "translated_text"),
        max_freshness_hours=720.0,
        description="Official Government of India Neural Machine Translation",
    ),
    "mock_marine_dictionary": SourcePolicy(
        source_id="mock_marine_dictionary",
        organization="ORCA Project",
        trust_tier=SourceTrustTier.SCIENTIFIC,
        authorized_variables=("translation", "translated_text"),
        max_freshness_hours=8760.0,
        description="Deterministic offline verified coastal lexicon fallback",
    ),
}


class SourcePolicyRegistry:
    """Registry evaluating trust tier and authorized variables per evidence source."""

    def __init__(self, custom_policies: Mapping[str, SourcePolicy] | None = None) -> None:
        self._policies: dict[str, SourcePolicy] = dict(DEFAULT_SOURCE_POLICIES)
        if custom_policies:
            self._policies.update(custom_policies)

    def get_policy(self, source_id: str) -> SourcePolicy:
        """Look up policy for a source identifier, or return UNTRUSTED fallback."""
        cleaned_id = source_id.lower().strip()
        for k, pol in self._policies.items():
            if k in cleaned_id or cleaned_id in k:
                return pol
        return SourcePolicy(
            source_id=source_id,
            organization="Unknown / Third Party",
            trust_tier=SourceTrustTier.UNTRUSTED,
            authorized_variables=(),
            max_freshness_hours=0.0,
            description="Unregistered or unverified source",
        )

    def validate_evidence(self, evidence: Evidence) -> tuple[bool, str]:
        """Validate if evidence source is authorized for the reported variable."""
        if not evidence.source or not evidence.source.source_id:
            return False, "Evidence is missing mandatory source identifier."

        policy = self.get_policy(evidence.source.source_id)
        if policy.trust_tier == SourceTrustTier.UNTRUSTED:
            return False, f"Source '{evidence.source.source_id}' is UNTRUSTED under current source policy."

        var = (evidence.variable or "").lower().strip()
        if policy.authorized_variables and not any(v in var or var in v for v in policy.authorized_variables):
            return False, f"Source '{policy.source_id}' is not authorized to emit variable '{evidence.variable}'."

        return True, f"Verified against policy for {policy.source_id} ({policy.trust_tier.value})"

    def is_authorized_variable(self, source_id: str, variable: str) -> bool:
        """Check if a source is authorized to emit a specific variable."""
        policy = self.get_policy(source_id)
        if policy.trust_tier == SourceTrustTier.UNTRUSTED:
            return False
        var = variable.lower().strip()
        return any(v in var or var in v for v in policy.authorized_variables)

    def get_trust_tier(self, source_id: str) -> tuple[SourceTrustTier, timedelta]:
        """Return the trust tier and max freshness timedelta for a source."""
        policy = self.get_policy(source_id)
        return policy.trust_tier, timedelta(hours=policy.max_freshness_hours)
