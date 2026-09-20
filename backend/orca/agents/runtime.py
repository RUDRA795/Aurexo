from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import math
import os
import re
import time
from typing import Any, Mapping
import uuid

from orca.safety.geographic_policy import get_operational_region_policy, is_within_operational_region
from orca.safety.sanitizer import sanitize_text_query, validate_coordinates
from orca.safety.source_policy import SourcePolicyRegistry, SourceTrustTier
from orca.schemas.agent_runtime import (
    AgentRuntimeResult,
    ClaimGrounding,
    EvidenceRequirement,
    IntentEnum,
    PlanStep,
    SufficiencyEvaluationResult,
    TaskPlan,
)
from orca.schemas.orca_contract import (
    DataQuality,
    Evidence,
    FinalResponse,
    Geometry,
    MapOverlay,
    ResponseType,
    SourceMetadata,
    utc_now,
)
from orca.telemetry.tracer import trace_span
from orca.tools.marine_tools import create_default_tool_registry
from orca.tools.registry import ToolExecutionResult, ToolRegistry, ToolStatus

# Deterministic Gazetteer for Indian Coastal Ports & Landing Centers
COASTAL_GAZETTEER: Mapping[str, tuple[float, float, str]] = {
    "MUMBAI": (18.92, 72.83, "MAHARASHTRA"),
    "SASSOON": (18.91, 72.82, "MAHARASHTRA"),
    "GOA": (15.45, 73.80, "GOA"),
    "MALIM": (15.62, 73.55, "GOA"),
    "BETUL": (15.20, 73.70, "GOA"),
    "PANJIM": (15.50, 73.83, "GOA"),
    "COCHIN": (9.93, 76.26, "KERALA"),
    "KOCHI": (9.93, 76.26, "KERALA"),
    "MANGALORE": (12.87, 74.84, "KARNATAKA"),
    "MALPE": (13.35, 74.70, "KARNATAKA"),
    "KARWAR": (14.81, 74.13, "KARNATAKA"),
    "CHENNAI": (13.08, 80.27, "TAMIL NADU"),
    "KANYAKUMARI": (8.08, 77.54, "TAMIL NADU"),
    "TUTICORIN": (8.76, 78.13, "TAMIL NADU"),
    "VISAKHAPATNAM": (17.68, 83.21, "ANDHRA PRADESH"),
    "VIZAG": (17.68, 83.21, "ANDHRA PRADESH"),
    "VERAVAL": (20.90, 70.37, "GUJARAT"),
    "PORBANDAR": (21.64, 69.60, "GUJARAT"),
    "PARADIP": (20.31, 86.61, "ODISHA"),
    "DIGHA": (21.62, 87.51, "WEST BENGAL"),
    "KAVARATTI": (10.56, 72.64, "LAKSHADWEEP"),
    "PORT BLAIR": (11.62, 92.72, "ANDAMAN"),
}

# Formal Intent-Specific Evidence Requirements
INTENT_EVIDENCE_REQUIREMENTS: Mapping[IntentEnum, list[EvidenceRequirement]] = {
    IntentEnum.FISHING_SUITABILITY: [
        EvidenceRequirement(
            variable="pfz_point",
            mandatory=True,
            description="Official Potential Fishing Zone coordinates and boundary",
        ),
        EvidenceRequirement(
            variable="sea_surface_temperature",
            mandatory=True,
            description="Sea surface temperature observation (°C)",
        ),
        EvidenceRequirement(
            variable="chlorophyll_a",
            mandatory=True,
            description="Chlorophyll-a ocean color concentration (mg/m³)",
        ),
        EvidenceRequirement(
            variable="marine_operational_conditions",
            mandatory=True,
            description="Operational marine weather, wind, waves, or sea state",
        ),
        EvidenceRequirement(
            variable="advisory_context",
            mandatory=False,
            description="Contextual bulletins and safety advisories",
        ),
    ],
    IntentEnum.PFZ_SEEKING: [
        EvidenceRequirement(
            variable="pfz_point",
            mandatory=True,
            description="Official Potential Fishing Zone coordinates",
        ),
        EvidenceRequirement(
            variable="advisory_context",
            mandatory=False,
            description="Contextual bulletins and safety advisories",
        ),
    ],
    IntentEnum.WEATHER_FORECAST: [
        EvidenceRequirement(
            variable="marine_operational_conditions",
            mandatory=True,
            description="Operational marine weather, wind, waves, or sea state",
        ),
    ],
    IntentEnum.OCEAN_METRICS: [
        EvidenceRequirement(
            variable="sea_surface_temperature",
            mandatory=True,
            description="Sea surface temperature",
        ),
        EvidenceRequirement(
            variable="chlorophyll_a",
            mandatory=False,
            description="Chlorophyll concentration",
        ),
    ],
    IntentEnum.ADVISORY_SEARCH: [
        EvidenceRequirement(
            variable="advisory_context",
            mandatory=True,
            description="Regional advisory bulletin",
        ),
    ],
    IntentEnum.SPATIAL_QUERY: [
        EvidenceRequirement(
            variable="spatial_geodesic_vector",
            mandatory=True,
            description="Geodesic distance and bearing vector",
        ),
    ],
    IntentEnum.TRANSLATION: [
        EvidenceRequirement(
            variable="translated_advisory_text",
            mandatory=True,
            description="Translated advisory text",
        ),
    ],
}


def evidence_matches_requirement(ev: Evidence, req: EvidenceRequirement) -> bool:
    """Evaluate whether an Evidence instance satisfies an EvidenceRequirement."""
    var = (ev.variable or "").lower().strip()
    target = req.variable.lower().strip()

    if target == "marine_operational_conditions":
        operational_vars = (
            "marine_weather_forecast",
            "significant_wave_height",
            "wind",
            "ocean_state",
            "fishermen_warning",
            "coastal_weather",
            "wave_height",
        )
        return any(v in var for v in operational_vars)

    if target == "sea_surface_temperature":
        return "surface_temperature" in var or "sst" in var or "thetao" in var

    if target == "chlorophyll_a":
        return "chlorophyll" in var or "chl" in var

    if target == "pfz_point":
        return "pfz" in var

    if target == "spatial_geodesic_vector":
        return "spatial" in var or "boundary" in var

    return target in var or var in target


def parse_intent(query_text: str) -> IntentEnum:
    """Classify user query into typed IntentEnum using deterministic pattern analysis."""
    q = query_text.lower().strip()

    # 1. Non-marine / unsupported intent gate
    unsupported_patterns = (
        "poem",
        "stock",
        "crypto",
        "bitcoin",
        "recipe",
        "movie",
        "football",
        "cricket",
        "president",
        "song",
        "novel",
    )
    if any(w in q for w in unsupported_patterns):
        return IntentEnum.UNSUPPORTED_INTENT

    # 2. Translation intent
    if "translate" in q or any(lang in q for lang in ("in hindi", "in malayalam", "in kannada", "in tamil", "in telugu")):
        return IntentEnum.TRANSLATION

    # 3. What-if / scenario simulation intent
    if any(w in q for w in ("what if", "simulate", "scenario", "hypothetical")):
        return IntentEnum.SCENARIO_SIMULATION

    # 4. Spatial / boundary query intent
    if any(w in q for w in ("distance", "bearing", "how far", "boundary", "eez", "protected area", "corridor")):
        return IntentEnum.SPATIAL_QUERY

    # 5. Advisory / text bulletin intent
    if any(w in q for w in ("advisory", "bulletin", "warning message", "notice")):
        if not any(w in q for w in ("pfz", "fishing", "suitab")):
            return IntentEnum.ADVISORY_SEARCH

    # 6. Fishing suitability (composite PFZ + environmental metrics)
    if any(w in q for w in ("pfz", "fishing", "fish aggregation", "where to fish")):
        if any(w in q for w in ("condition", "weather", "suitab", "temperature", "sst", "environment", "safe", "wind", "chlorophyll")):
            return IntentEnum.FISHING_SUITABILITY
        return IntentEnum.PFZ_SEEKING

    # 7. Weather forecast intent
    if any(w in q for w in ("weather", "wind", "wave", "sea state", "forecast", "swell", "cyclone")):
        return IntentEnum.WEATHER_FORECAST

    # 8. Ocean physical metrics intent
    if any(w in q for w in ("temperature", "sst", "chlorophyll", "salinity", "ocean current")):
        return IntentEnum.OCEAN_METRICS

    return IntentEnum.GENERAL_MARINE_QUERY


def resolve_spatial_parameters(
    query_text: str,
    explicit_location: Geometry | None = None,
    explicit_sector: str | None = None,
) -> tuple[Geometry | None, str | None]:
    """Resolve geographic coordinates and maritime sector from explicit parameters or gazetteer."""
    if explicit_location is not None:
        validate_coordinates(explicit_location.lat, explicit_location.lon)
        return explicit_location, explicit_sector

    # Check query against gazetteer
    q_upper = query_text.upper()
    for name, (lat, lon, sector) in COASTAL_GAZETTEER.items():
        if re.search(r"\b" + re.escape(name) + r"\b", q_upper):
            return Geometry(lat=lat, lon=lon), explicit_sector or sector

    # Check for raw coordinate regex: e.g. "15.45, 73.80" or "lat: 15.45, lon: 73.80"
    coord_match = re.search(r"(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)", query_text)
    if coord_match:
        lat_f = float(coord_match.group(1))
        lon_f = float(coord_match.group(2))
        validate_coordinates(lat_f, lon_f)
        return Geometry(lat=lat_f, lon=lon_f), explicit_sector

    return None, explicit_sector


class OrcaAgentRuntime:
    """Production ORCA agent runtime governing planning, parallel supervisor execution,

    evidence sufficiency verification, and grounded synthesis.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry | None = None,
        source_registry: SourcePolicyRegistry | None = None,
        max_steps: int = 6,
    ) -> None:
        self.tools = tool_registry or create_default_tool_registry()
        self.sources = source_registry or SourcePolicyRegistry()
        self.max_steps = max_steps

    def generate_plan(
        self,
        intent: IntentEnum,
        query: str,
        location: Geometry | None,
        sector: str | None,
    ) -> TaskPlan:
        """Decompose user query intent into an ordered sequence of typed plan steps.

        Environmental retrieval steps (PFZ, SST, Chlorophyll, Weather) are configured
        with independent dependencies to allow concurrent execution.
        """
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        loc_dict = {"lat": location.lat, "lon": location.lon} if location else {"lat": 18.92, "lon": 72.83}

        steps: list[PlanStep] = []

        if intent == IntentEnum.UNSUPPORTED_INTENT:
            return TaskPlan(plan_id=plan_id, intent=intent, query=query, steps=[])

        elif intent == IntentEnum.FISHING_SUITABILITY:
            # Independent Environmental Retrieval Wave (No artificial dependencies)
            steps.append(
                PlanStep(
                    step_id="step_1_pfz",
                    tool_name="pfz_retrieval",
                    parameters={"lat": loc_dict["lat"], "lon": loc_dict["lon"], "sector": sector, "radius_km": 300.0},
                    dependencies=[],
                )
            )
            steps.append(
                PlanStep(
                    step_id="step_2_sst",
                    tool_name="sst_retrieval",
                    parameters=loc_dict,
                    dependencies=[],
                )
            )
            steps.append(
                PlanStep(
                    step_id="step_3_chl",
                    tool_name="chlorophyll_retrieval",
                    parameters=loc_dict,
                    dependencies=[],
                )
            )
            steps.append(
                PlanStep(
                    step_id="step_4_weather",
                    tool_name="marine_weather",
                    parameters=loc_dict,
                    dependencies=[],
                )
            )
            # Contextual Advisory RAG (can execute concurrently or contextually)
            steps.append(
                PlanStep(
                    step_id="step_5_advisory",
                    tool_name="advisory_rag",
                    parameters={"query": query, "sector": sector, "limit": 2},
                    dependencies=[],
                )
            )

        elif intent == IntentEnum.PFZ_SEEKING:
            steps.append(
                PlanStep(
                    step_id="step_1_pfz",
                    tool_name="pfz_retrieval",
                    parameters={"lat": loc_dict["lat"], "lon": loc_dict["lon"], "sector": sector, "radius_km": 300.0},
                    dependencies=[],
                )
            )
            steps.append(
                PlanStep(
                    step_id="step_2_advisory",
                    tool_name="advisory_rag",
                    parameters={"query": query, "sector": sector, "limit": 2},
                    dependencies=[],
                )
            )

        elif intent == IntentEnum.WEATHER_FORECAST:
            steps.append(
                PlanStep(
                    step_id="step_1_weather",
                    tool_name="marine_weather",
                    parameters=loc_dict,
                    dependencies=[],
                )
            )

        elif intent == IntentEnum.OCEAN_METRICS:
            steps.append(PlanStep(step_id="step_1_sst", tool_name="sst_retrieval", parameters=loc_dict, dependencies=[]))
            steps.append(PlanStep(step_id="step_2_chl", tool_name="chlorophyll_retrieval", parameters=loc_dict, dependencies=[]))

        elif intent == IntentEnum.ADVISORY_SEARCH:
            steps.append(
                PlanStep(
                    step_id="step_1_advisory",
                    tool_name="advisory_rag",
                    parameters={"query": query, "sector": sector, "limit": 3},
                    dependencies=[],
                )
            )

        elif intent == IntentEnum.SPATIAL_QUERY:
            steps.append(
                PlanStep(
                    step_id="step_1_spatial",
                    tool_name="spatial_query",
                    parameters={
                        "origin_lat": loc_dict["lat"],
                        "origin_lon": loc_dict["lon"],
                        "operation": "distance_and_bearing",
                    },
                    dependencies=[],
                )
            )

        elif intent == IntentEnum.TRANSLATION:
            target_lang = "hi"
            if "malayalam" in query.lower():
                target_lang = "ml"
            elif "kannada" in query.lower():
                target_lang = "kn"
            elif "tamil" in query.lower():
                target_lang = "ta"
            elif "telugu" in query.lower():
                target_lang = "te"

            steps.append(
                PlanStep(
                    step_id="step_1_translation",
                    tool_name="indic_translation",
                    parameters={"text": query, "target_language": target_lang},
                    dependencies=[],
                )
            )

        else:
            steps.append(
                PlanStep(
                    step_id="step_1_advisory",
                    tool_name="advisory_rag",
                    parameters={"query": query, "sector": sector, "limit": 2},
                    dependencies=[],
                )
            )

        return TaskPlan(plan_id=plan_id, intent=intent, query=query, steps=steps)

    def evaluate_evidence_sufficiency(
        self,
        intent: IntentEnum,
        evidence_list: list[Evidence],
    ) -> SufficiencyEvaluationResult:
        """Evaluate evidence sufficiency against intent-specific typed EvidenceRequirements.

        Consumes collected evidence and determines completeness, overall quality, and confidence.
        Missing mandatory variables strictly prevent sufficient status or good quality ratings.
        """
        if intent == IntentEnum.UNSUPPORTED_INTENT:
            return SufficiencyEvaluationResult(
                is_sufficient=False,
                evidence_quality=DataQuality.UNRELIABLE,
                evidence_completeness=0.0,
                answer_confidence=0.0,
                missing_mandatory=["unsupported_intent"],
                notes=["Query is outside ORCA maritime intelligence operational scope."],
            )

        requirements = INTENT_EVIDENCE_REQUIREMENTS.get(
            intent,
            [EvidenceRequirement(variable="advisory_context", mandatory=False)],
        )
        mandatory_reqs = [r for r in requirements if r.mandatory]
        optional_reqs = [r for r in requirements if not r.mandatory]

        # Check satisfaction of mandatory requirements
        missing_mandatory: list[str] = []
        for req in mandatory_reqs:
            satisfied = any(
                evidence_matches_requirement(ev, req) and ev.quality in (DataQuality.GOOD, DataQuality.DEGRADED)
                for ev in evidence_list
            )
            if not satisfied:
                missing_mandatory.append(req.variable)

        # Check satisfaction of optional requirements
        missing_optional: list[str] = []
        for req in optional_reqs:
            satisfied = any(
                evidence_matches_requirement(ev, req) and ev.quality in (DataQuality.GOOD, DataQuality.DEGRADED)
                for ev in evidence_list
            )
            if not satisfied:
                missing_optional.append(req.variable)

        total_mandatory = len(mandatory_reqs)
        satisfied_mandatory = total_mandatory - len(missing_mandatory)
        evidence_completeness = round(satisfied_mandatory / total_mandatory, 2) if total_mandatory > 0 else 1.0

        has_degraded = any(getattr(ev, "quality", DataQuality.GOOD) == DataQuality.DEGRADED for ev in evidence_list)

        notes: list[str] = []
        if missing_mandatory:
            notes.append(f"Missing mandatory evidence variables: {', '.join(missing_mandatory)}.")
        if missing_optional:
            notes.append(f"Optional contextual sources absent: {', '.join(missing_optional)}.")

        if not missing_mandatory:
            is_sufficient = True
            evidence_quality = DataQuality.DEGRADED if has_degraded else DataQuality.GOOD
            base_confidence = 0.85 if has_degraded else 1.0
            answer_confidence = round(base_confidence, 2)
        else:
            is_sufficient = False
            evidence_quality = DataQuality.DEGRADED if evidence_list else DataQuality.UNRELIABLE
            answer_confidence = round(evidence_completeness * 0.80, 2)

        return SufficiencyEvaluationResult(
            is_sufficient=is_sufficient,
            evidence_quality=evidence_quality,
            evidence_completeness=evidence_completeness,
            answer_confidence=answer_confidence,
            missing_mandatory=missing_mandatory,
            missing_optional=missing_optional,
            notes=notes,
        )

    def synthesize_grounded_response(
        self,
        intent: IntentEnum,
        query: str,
        evidence_list: list[Evidence],
        sufficiency: SufficiencyEvaluationResult,
        session_id: str,
    ) -> tuple[FinalResponse, list[ClaimGrounding]]:
        """Synthesize response text strictly bound to concrete evidence records."""
        claims: list[ClaimGrounding] = []
        overlays: list[MapOverlay] = []

        if intent == IntentEnum.UNSUPPORTED_INTENT:
            final_ans = FinalResponse(
                session_id=session_id,
                response_type=ResponseType.ERROR,
                answer_text="REFUSAL: The request is outside ORCA's authorized maritime ecosystem intelligence scope.",
                confidence=0.0,
                evidence_summary=[],
                limitations=["Out of domain query rejected by runtime gate."],
            )
            return final_ans, claims

        if not evidence_list:
            final_ans = FinalResponse(
                session_id=session_id,
                response_type=ResponseType.ERROR,
                answer_text="UNAVAILABLE: Required operational marine evidence could not be verified from official sources.",
                confidence=0.0,
                evidence_summary=[],
                limitations=["Insufficient or unverified official evidence for requested maritime intent."],
            )
            return final_ans, claims

        answer_parts: list[str] = []

        # 1. PFZ Point Grounding
        pfz_evs = [e for e in evidence_list if e.variable == "pfz_point"]
        if pfz_evs:
            top_pfz = pfz_evs[0]
            val = top_pfz.value or {}
            pfz_id = val.get("pfz_id", "Unknown")
            sec = val.get("sector", "Coastal")
            claim_txt = f"Potential Fishing Zone {pfz_id} identified in the {sec} sector."
            answer_parts.append(claim_txt)
            ev_id = f"{top_pfz.source.source_id}:{pfz_id}"
            claims.append(ClaimGrounding(claim_text=claim_txt, supporting_evidence_ids=[ev_id]))

            if top_pfz.geometry:
                overlays.append(
                    MapOverlay(
                        layer_id="pfz-candidates",
                        data={
                            "type": "FeatureCollection",
                            "features": [
                                {
                                    "type": "Feature",
                                    "geometry": {"type": "Point", "coordinates": [top_pfz.geometry.lon, top_pfz.geometry.lat]},
                                    "properties": {"pfz_id": pfz_id, "sector": sec},
                                }
                            ],
                        },
                        style_hint="pfz",
                    )
                )

        # 2. SST Grounding
        sst_evs = [e for e in evidence_list if "surface_temperature" in (e.variable or "")]
        if sst_evs:
            sst_ev = sst_evs[0]
            sst_val = sst_ev.value
            claim_txt = f"Sea surface temperature is measured at {sst_val}°C."
            answer_parts.append(claim_txt)
            claims.append(ClaimGrounding(claim_text=claim_txt, supporting_evidence_ids=[sst_ev.source.source_id]))

        # 3. Chlorophyll Grounding
        chl_evs = [e for e in evidence_list if "chlorophyll" in (e.variable or "")]
        if chl_evs:
            chl_ev = chl_evs[0]
            chl_val = chl_ev.value
            claim_txt = f"Chlorophyll-a concentration is recorded at {chl_val} mg/m³."
            answer_parts.append(claim_txt)
            claims.append(ClaimGrounding(claim_text=claim_txt, supporting_evidence_ids=[chl_ev.source.source_id]))

        # 4. Ocean State (Significant Wave Height, Swell, Currents)
        wave_evs = [e for e in evidence_list if e.variable == "significant_wave_height"]
        if wave_evs:
            w_ev = wave_evs[0]
            claim_txt = f"Significant wave height is reported at {w_ev.value} m."
            answer_parts.append(claim_txt)
            claims.append(ClaimGrounding(claim_text=claim_txt, supporting_evidence_ids=[w_ev.source.source_id]))

        # 5. Wind Conditions
        wind_evs = [e for e in evidence_list if e.variable == "wind"]
        if wind_evs:
            wnd_ev = wind_evs[0]
            val = wnd_ev.value or {}
            speed = val.get("wind_speed_knots", "N/A")
            direction = val.get("wind_direction_deg", "N/A")
            claim_txt = f"Coastal surface winds are {speed} knots at {direction}°."
            answer_parts.append(claim_txt)
            claims.append(ClaimGrounding(claim_text=claim_txt, supporting_evidence_ids=[wnd_ev.source.source_id]))

        # 6. IMD Fishermen Warning
        imd_evs = [e for e in evidence_list if e.variable == "fishermen_warning"]
        if imd_evs:
            imd_ev = imd_evs[0]
            val = imd_ev.value or {}
            msg = val.get("fishermen_warning") or val.get("weather_summary", "Operational bulletin active")
            claim_txt = f"IMD Coastal Bulletin: {msg}"
            answer_parts.append(claim_txt)
            claims.append(ClaimGrounding(claim_text=claim_txt, supporting_evidence_ids=[imd_ev.source.source_id]))

        # 7. Generic Weather Forecast (NOAA fallback or composite)
        weather_evs = [e for e in evidence_list if e.variable == "marine_weather_forecast"]
        if weather_evs and not (wave_evs or wind_evs):
            w_ev = weather_evs[0]
            w_val = w_ev.value or {}
            wind = w_val.get("wind_speed", "Normal breeze")
            forecast = w_val.get("short_forecast", "Clear")
            claim_txt = f"Coastal weather conditions: {forecast}, with wind {wind}."
            answer_parts.append(claim_txt)
            claims.append(ClaimGrounding(claim_text=claim_txt, supporting_evidence_ids=[w_ev.source.source_id]))

        # 8. Spatial Grounding
        spatial_evs = [e for e in evidence_list if "spatial" in (e.variable or "")]
        if spatial_evs:
            sp_ev = spatial_evs[0]
            dist = sp_ev.value.get("distance_km")
            bearing = sp_ev.value.get("bearing_deg")
            claim_txt = f"Calculated geodesic distance is {dist} km on initial bearing {bearing}°."
            answer_parts.append(claim_txt)
            claims.append(ClaimGrounding(claim_text=claim_txt, supporting_evidence_ids=[sp_ev.source.source_id]))

        # 9. Translation Grounding
        trans_evs = [e for e in evidence_list if "translated" in (e.variable or "")]
        if trans_evs:
            tr_ev = trans_evs[0]
            tr_text = tr_ev.value.get("translated_text", "")
            claim_txt = f"Translated text: {tr_text}"
            answer_parts.append(claim_txt)
            claims.append(ClaimGrounding(claim_text=claim_txt, supporting_evidence_ids=[tr_ev.source.source_id]))

        # 10. Advisory Context Grounding (Contextual only, does not fabricate observations)
        adv_evs = [e for e in evidence_list if "advisory" in (e.variable or "")]
        if adv_evs and not answer_parts:
            top_adv = adv_evs[0]
            title = top_adv.value.get("title", "Advisory Bulletin")
            content = top_adv.value.get("content", "")
            claim_txt = f"Official Marine Advisory ({title}): {content}"
            answer_parts.append(claim_txt)
            claims.append(ClaimGrounding(claim_text=claim_txt, supporting_evidence_ids=[top_adv.source.source_id]))

        # Grounding Limitation Notice when Mandatory Evidence is Missing
        limitations: list[str] = [
            f"Evidence completeness: {int(sufficiency.evidence_completeness * 100)}%.",
            f"Data quality state: {sufficiency.evidence_quality.value}.",
            f"Region: {get_operational_region_policy().name}.",
        ]
        if sufficiency.missing_mandatory:
            missing_str = ", ".join(sufficiency.missing_mandatory)
            limit_msg = f"LIMITATION: Marine operational evidence ({missing_str}) could not be verified from official operational sources for this sector; fishing suitability cannot be certified without verified sea-state conditions."
            answer_parts.append(limit_msg)
            limitations.append(f"Missing mandatory evidence: {missing_str}")

        final_text = " ".join(answer_parts) if answer_parts else "Verified marine intelligence observations retrieved."

        final_ans = FinalResponse(
            session_id=session_id,
            response_type=ResponseType.FACTUAL,
            answer_text=final_text,
            confidence=sufficiency.answer_confidence,
            evidence_summary=evidence_list,
            limitations=limitations,
            map_overlays=overlays,
        )
        return final_ans, claims

    async def _execute_single_step(self, step: PlanStep) -> ToolExecutionResult:
        """Execute a single plan step with schema validation, domain applicability check, and bounded retries."""
        step_res: ToolExecutionResult | None = None
        for attempt in range(step.max_retries + 1):
            step.retry_count = attempt
            if not self.tools.has(step.tool_name):
                step.status = "failed"
                step.error = f"Tool '{step.tool_name}' not registered in registry"
                return ToolExecutionResult(
                    tool_name=step.tool_name,
                    status=ToolStatus.ERROR,
                    errors=[step.error],
                    quality=DataQuality.UNRELIABLE,
                )

            step_res = await self.tools.execute_tool(step.tool_name, step.parameters)
            # Break immediately on success, fallback, out-of-domain, no-data, skipped, or auth-required (do not waste retries)
            if step_res.status in (
                ToolStatus.SUCCESS,
                ToolStatus.FALLBACK,
                ToolStatus.DEGRADED,
                ToolStatus.SKIPPED,
                ToolStatus.OUT_OF_DOMAIN,
                ToolStatus.NO_DATA,
                ToolStatus.AUTH_REQUIRED,
            ):
                break

        if step_res is not None:
            if step_res.status == ToolStatus.SUCCESS:
                step.status = "completed"
            elif step_res.status in (ToolStatus.FALLBACK, ToolStatus.DEGRADED):
                step.status = "fallback_applied"
            elif step_res.status == ToolStatus.OUT_OF_DOMAIN:
                step.status = "failed"
            elif step_res.status == ToolStatus.SKIPPED:
                step.status = "completed"
            else:
                step.status = "failed"

            if step_res.errors:
                step.error = "; ".join(step_res.errors)

        return step_res or ToolExecutionResult(
            tool_name=step.tool_name,
            status=ToolStatus.ERROR,
            errors=["Step execution returned empty result"],
            quality=DataQuality.UNRELIABLE,
        )

    async def run(
        self,
        user_query: str,
        coordinates: Geometry | None = None,
        sector: str | None = None,
        session_id: str | None = None,
        thread_id: str | None = None,
        plan: TaskPlan | None = None,
    ) -> AgentRuntimeResult:
        """Execute end-to-end agent runtime cycle with parallel environmental retrieval waves,

        strict domain routing, sufficiency verification, and claim-grounded synthesis.
        """
        start_time = time.perf_counter()
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        trace_id = f"trc_{uuid.uuid4().hex[:16]}"
        thread_id = thread_id or f"th_{uuid.uuid4().hex[:10]}"
        session_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"

        cleaned_query = sanitize_text_query(user_query)

        # 1. Parse Intent & Spatial context
        intent = parse_intent(cleaned_query)
        loc, resolved_sector = resolve_spatial_parameters(cleaned_query, coordinates, sector)

        # 2. Generate Plan (or use provided custom plan)
        if plan is None:
            plan = self.generate_plan(intent, cleaned_query, loc, resolved_sector)

        # 3. Parallel Supervisor Tool Execution Loop
        all_evidence: list[Evidence] = []
        execution_traces: list[dict[str, Any]] = []
        steps_executed = 0

        completed_step_ids: set[str] = set()
        remaining_steps = list(plan.steps)

        with trace_span("orca.runtime.execute", attributes={"intent": intent.value, "run_id": run_id}):
            while remaining_steps and steps_executed < self.max_steps:
                # Find all steps whose dependencies are satisfied
                ready_steps = [
                    s for s in remaining_steps
                    if all(dep in completed_step_ids for dep in s.dependencies)
                ]
                if not ready_steps:
                    ready_steps = [remaining_steps[0]]

                budget = self.max_steps - steps_executed
                current_batch = ready_steps[:budget]

                # Execute ready steps in parallel via asyncio.gather
                batch_results = await asyncio.gather(
                    *[self._execute_single_step(s) for s in current_batch]
                )

                for step, step_res in zip(current_batch, batch_results):
                    steps_executed += 1
                    completed_step_ids.add(step.step_id)
                    remaining_steps.remove(step)

                    if step_res is not None:
                        all_evidence.extend(step_res.evidence)
                        execution_traces.append(
                            {
                                "step_id": step.step_id,
                                "tool_name": step.tool_name,
                                "status": step_res.status.value,
                                "duration_ms": step_res.duration_ms,
                                "evidence_count": len(step_res.evidence),
                                "fallback": step_res.fallback_applied,
                            }
                        )

            # Record limit exceeded for any unreached steps
            for unreached in remaining_steps:
                unreached.status = "failed"
                unreached.error = f"Exceeded max runtime steps limit ({self.max_steps})"
                execution_traces.append({"step_id": unreached.step_id, "status": "limit_exceeded"})

            # 4. Evaluate Evidence Sufficiency
            sufficiency = self.evaluate_evidence_sufficiency(intent, all_evidence)

            # 5. Grounded Synthesis
            final_ans, claims = self.synthesize_grounded_response(
                intent=intent,
                query=cleaned_query,
                evidence_list=all_evidence,
                sufficiency=sufficiency,
                session_id=session_id,
            )

        total_duration = round((time.perf_counter() - start_time) * 1000.0, 2)

        return AgentRuntimeResult(
            run_id=run_id,
            trace_id=trace_id,
            session_id=session_id,
            thread_id=thread_id,
            intent=intent,
            plan=plan,
            final_response=final_ans,
            all_evidence=all_evidence,
            claims=claims,
            execution_metadata={
                "duration_ms": total_duration,
                "steps_planned": len(plan.steps),
                "steps_executed": steps_executed,
                "traces": execution_traces,
                "evidence_completeness": sufficiency.evidence_completeness,
                "answer_confidence": sufficiency.answer_confidence,
                "sufficiency_notes": sufficiency.notes,
                "missing_mandatory": sufficiency.missing_mandatory,
                "data_quality": sufficiency.evidence_quality.value,
            },
        )
