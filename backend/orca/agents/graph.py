from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import math
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from orca.agents.state import OrcaGraphState
from orca.data.adapters.base import SourceUnavailableError
from orca.data.adapters.cached_pfz import CachedPFZAdapter
from orca.data.adapters.incois_chlorophyll import INCOISChlorophyllAdapter
from orca.data.adapters.incois_pfz import INCOISPFZWebGISAdapter
from orca.data.adapters.incois_sst import INCOISSSTAdapter
from orca.data.adapters.incois_text_advisory import INCOISTextAdvisoryAdapter
from orca.data.adapters.noaa_weather import NOAAWeatherAdapter
from orca.safety.sanitizer import sanitize_text_query, validate_coordinates
from orca.schemas.orca_contract import (
    DataQuality,
    Evidence,
    FinalResponse,
    Geometry,
    MapOverlay,
    ResponseType,
    SourceMetadata,
    VerificationCheck,
    VerificationResult,
    VerificationSeverity,
    utc_now,
)
from orca.schemas.pfz_contract import (
    PFZAccessTier,
    PFZPoint,
    PFZQuery,
    PFZQueryResult,
)
from orca.services.geospatial import calculate_distance_postgis


def _calculate_distance_and_bearing(origin: Geometry, target: Geometry) -> tuple[float, float]:
    """Calculate geodesic distance in km and initial bearing in degrees from origin to target."""
    lat1, lon1 = math.radians(origin.lat), math.radians(origin.lon)
    lat2, lon2 = math.radians(target.lat), math.radians(target.lon)
    dlon = lon2 - lon1
    dlat = lat2 - lat1

    # Haversine distance
    a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    distance_km = 6371.0 * c

    # Bearing
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    bearing_rad = math.atan2(y, x)
    bearing_deg = (math.degrees(bearing_rad) + 360.0) % 360.0

    return round(distance_km, 2), round(bearing_deg, 1)


class OrcaGraphOrchestrator:
    """Multi-agent LangGraph coordinator for PFZ and marine environmental intelligence."""

    def __init__(
        self,
        *,
        pfz_sources: list[Any] | None = None,
        sst_adapter: Any | None = None,
        chl_adapter: Any | None = None,
        weather_adapter: Any | None = None,
        advisory_rag_repo: Any | None = None,
    ):
        self.pfz_sources = pfz_sources
        self.sst_adapter = sst_adapter or INCOISSSTAdapter()
        self.chl_adapter = chl_adapter or INCOISChlorophyllAdapter()
        self.weather_adapter = weather_adapter or NOAAWeatherAdapter()
        self.advisory_rag_repo = advisory_rag_repo

    async def supervisor_node(self, state: OrcaGraphState) -> dict[str, Any]:
        """SupervisorNode: Sanitizes input, checks coordinate bounds, and resolves spatial intent."""
        traces = list(state.get("provenance_traces", []))
        user_query = state.get("user_query", "")
        cleaned_query = sanitize_text_query(user_query) if user_query else ""

        coords = state.get("coordinates")
        if coords is not None:
            validate_coordinates(coords.lat, coords.lon)

        sector = state.get("sector")
        if not sector and cleaned_query:
            query_upper = cleaned_query.upper()
            for known_sector in ("GOA", "KERALA", "KARNATAKA", "MAHARASHTRA", "TAMIL NADU", "GUJARAT"):
                if known_sector in query_upper:
                    sector = known_sector
                    break

        traces.append({
            "node": "SupervisorNode",
            "timestamp": utc_now().isoformat(),
            "query": cleaned_query,
            "sector": sector,
        })

        return {
            "user_query": cleaned_query,
            "coordinates": coords,
            "sector": sector,
            "provenance_traces": traces,
            "evidence_list": list(state.get("evidence_list", [])),
            "verification_results": list(state.get("verification_results", [])),
        }

    async def pfz_agent_node(self, state: OrcaGraphState) -> dict[str, Any]:
        """PFZAgentNode: Retrieves PFZ candidates via tiered fallback (WFS -> Text Bulletin -> Cache)."""
        traces = list(state.get("provenance_traces", []))
        coords = state.get("coordinates")
        sector = state.get("sector")
        origin_loc = coords or Geometry(lat=15.0, lon=73.5)

        query = PFZQuery(
            location=origin_loc,
            valid_at=utc_now(),
            radius_km=300.0,
            sector=sector,
        )

        candidates: list[PFZPoint] = []
        tier_used: str | None = None
        evidence_records: list[Evidence] = []

        # If custom sources were injected (e.g. in test suites), iterate over them
        if self.pfz_sources is not None:
            for source in self.pfz_sources:
                try:
                    res: PFZQueryResult = await source.fetch(query)
                    if res.points:
                        candidates = res.points
                        tier_used = res.access_tier.value
                        for p in res.points:
                            ev = Evidence(
                                source=res.source,
                                variable="pfz_point",
                                value={"pfz_id": p.pfz_id, "sector": p.sector},
                                geometry=p.location,
                                observed_at=p.source_valid_from,
                                valid_from=p.source_valid_from,
                                valid_until=p.source_valid_until,
                                retrieved_at=res.retrieved_at,
                                quality=DataQuality.GOOD,
                            )
                            evidence_records.append(ev)
                        break
                except Exception as exc:
                    traces.append({"node": "PFZAgentNode", "tier_failed": str(source), "reason": str(exc)})
        else:
            # Default operational tiered fallback: WFS -> Text Bulletin -> PostGIS Cache
            tiers = [
                ("webgis_layer", INCOISPFZWebGISAdapter()),
                ("text_advisory", INCOISTextAdvisoryAdapter()),
                ("cached", CachedPFZAdapter()),
            ]
            for tier_name, adapter in tiers:
                try:
                    res = await adapter.fetch(query)
                    if res.points:
                        candidates = res.points
                        tier_used = tier_name
                        for p in res.points:
                            ev = Evidence(
                                source=res.source,
                                variable="pfz_point",
                                value={"pfz_id": p.pfz_id, "sector": p.sector},
                                geometry=p.location,
                                observed_at=p.source_valid_from,
                                valid_from=p.source_valid_from,
                                valid_until=p.source_valid_until,
                                retrieved_at=res.retrieved_at,
                                quality=DataQuality.GOOD,
                            )
                            evidence_records.append(ev)
                        break
                except Exception as exc:
                    traces.append({"node": "PFZAgentNode", "tier_failed": tier_name, "reason": str(exc)})

        if not candidates:
            traces.append({"node": "PFZAgentNode", "status": "no_candidates_found"})
            return {
                "candidate_pfz_points": [],
                "selected_pfz": None,
                "pfz_unavailable": True,
                "pfz_tier_used": None,
                "provenance_traces": traces,
            }

        # Spatial distance ranking to select nearest candidate
        nearest_point = candidates[0]
        min_dist = float("inf")
        for p in candidates:
            dist, _ = _calculate_distance_and_bearing(origin_loc, p.location)
            if dist < min_dist:
                min_dist = dist
                nearest_point = p

        traces.append({
            "node": "PFZAgentNode",
            "tier_used": tier_used,
            "candidate_count": len(candidates),
            "nearest_pfz_id": nearest_point.pfz_id,
        })

        existing_evidence = list(state.get("evidence_list", []))
        existing_evidence.extend(evidence_records)

        return {
            "candidate_pfz_points": candidates,
            "selected_pfz": nearest_point,
            "pfz_tier_used": tier_used,
            "pfz_unavailable": False,
            "evidence_list": existing_evidence,
            "provenance_traces": traces,
        }

    async def environment_agent_node(self, state: OrcaGraphState) -> dict[str, Any]:
        """EnvironmentAgentNode: Retrieves SST and Chlorophyll in parallel once PFZ is available."""
        traces = list(state.get("provenance_traces", []))
        selected_pfz = state.get("selected_pfz")
        query_loc = selected_pfz.location if selected_pfz else state.get("coordinates")

        if not query_loc:
            return {"provenance_traces": traces}

        async def _fetch_sst() -> Evidence | None:
            try:
                # Support both async resolve_endpoint + extract_sst or synchronous extract
                if hasattr(self.sst_adapter, "resolve_endpoint"):
                    await self.sst_adapter.resolve_endpoint()
                return self.sst_adapter.extract_sst(query_loc)
            except Exception as exc:
                traces.append({"node": "EnvironmentAgentNode", "task": "sst", "error": str(exc)})
                return None

        async def _fetch_chl() -> Evidence | None:
            try:
                if hasattr(self.chl_adapter, "resolve_endpoint"):
                    await self.chl_adapter.resolve_endpoint()
                return self.chl_adapter.extract_chlorophyll(query_loc)
            except Exception as exc:
                traces.append({"node": "EnvironmentAgentNode", "task": "chlorophyll", "error": str(exc)})
                return None

        async def _fetch_weather() -> Evidence | None:
            # Query weather if user requested or query explicitly mentions weather/wind/forecast
            query_str = (state.get("user_query") or "").lower()
            if any(k in query_str for k in ("weather", "wind", "forecast", "wave", "temp")):
                try:
                    return await self.weather_adapter.fetch_forecast(query_loc)
                except Exception as exc:
                    traces.append({"node": "EnvironmentAgentNode", "task": "weather", "error": str(exc)})
                    return None
            return None

        async def _fetch_advisories() -> list[Evidence]:
            if self.advisory_rag_repo is not None:
                try:
                    query_text = state.get("user_query") or ""
                    results = await self.advisory_rag_repo.search_advisories(
                        query_text=query_text,
                        sector=state.get("sector"),
                        limit=2,
                    )
                    return [r.evidence for r in results]
                except Exception as exc:
                    traces.append({"node": "EnvironmentAgentNode", "task": "advisory_rag", "error": str(exc)})
                    return []
            return []

        # Execute environmental and advisory retrieval tasks in parallel
        sst_res, chl_res, weather_res, adv_evidences = await asyncio.gather(
            _fetch_sst(),
            _fetch_chl(),
            _fetch_weather(),
            _fetch_advisories(),
        )

        evidence_list = list(state.get("evidence_list", []))
        if sst_res:
            evidence_list.append(sst_res)
        if chl_res:
            evidence_list.append(chl_res)
        if weather_res:
            evidence_list.append(weather_res)
        if adv_evidences:
            evidence_list.extend(adv_evidences)

        traces.append({
            "node": "EnvironmentAgentNode",
            "sst_retrieved": sst_res is not None,
            "chl_retrieved": chl_res is not None,
            "weather_retrieved": weather_res is not None,
            "advisories_retrieved": len(adv_evidences),
        })

        return {
            "sst_evidence": sst_res,
            "chlorophyll_evidence": chl_res,
            "weather_evidence": weather_res,
            "evidence_list": evidence_list,
            "provenance_traces": traces,
        }

    async def safety_validation_node(self, state: OrcaGraphState) -> dict[str, Any]:
        """SafetyValidationNode: Code-level deterministic enforcement of immutable safety rules."""
        traces = list(state.get("provenance_traces", []))
        now = utc_now()

        selected_pfz = state.get("selected_pfz")
        coords = state.get("coordinates")
        evidence_list = state.get("evidence_list", [])

        checks: dict[VerificationCheck, bool] = {
            VerificationCheck.EVIDENCE_PRESENT: True,
            VerificationCheck.FRESHNESS: True,
            VerificationCheck.SPATIAL_RELEVANCE: True,
            VerificationCheck.TEMPORAL_RELEVANCE: True,
            VerificationCheck.CITATION_VALID: True,
            VerificationCheck.SCIENTIFIC_CONSISTENCY: True,
        }
        missing: list[str] = []
        notes: list[str] = []

        # Rule 1: Minimum required PFZ evidence
        if selected_pfz is None or state.get("pfz_unavailable", False):
            checks[VerificationCheck.EVIDENCE_PRESENT] = False
            missing.append("pfz_point")
            notes.append("Required PFZ evidence could not be retrieved from any operational tier.")
        else:
            notes.append(f"PFZ candidate {selected_pfz.pfz_id} available.")

            # Rule 2: Freshness & Expiration Verification
            if selected_pfz.freshness_deadline and now > selected_pfz.freshness_deadline:
                checks[VerificationCheck.FRESHNESS] = False
                notes.append(f"PFZ point {selected_pfz.pfz_id} exceeds ORCA freshness policy deadline ({selected_pfz.freshness_deadline}).")
            elif selected_pfz.source_valid_until and now > selected_pfz.source_valid_until:
                checks[VerificationCheck.FRESHNESS] = False
                notes.append(f"PFZ point {selected_pfz.pfz_id} is expired past source_valid_until ({selected_pfz.source_valid_until}).")
            else:
                notes.append("PFZ point is within operational freshness window.")

            # Rule 3: Coordinate bounds
            try:
                validate_coordinates(selected_pfz.location.lat, selected_pfz.location.lon)
            except Exception as exc:
                checks[VerificationCheck.SPATIAL_RELEVANCE] = False
                notes.append(f"Coordinate validation failed: {exc}")

        # Rule 4: Provenance completeness across all evidence
        for ev in evidence_list:
            if not ev.source or not ev.source.source_id or not ev.retrieved_at:
                checks[VerificationCheck.CITATION_VALID] = False
                notes.append("Evidence record is missing mandatory source identifier or retrieval timestamp.")
                break

        all_passed = all(checks.values())
        severity = VerificationSeverity.BLOCKING if not all_passed else VerificationSeverity.INFO

        v_result = VerificationResult(
            passed=all_passed,
            severity=severity,
            checks=checks,
            missing=missing,
            notes=notes,
        )

        verification_results = list(state.get("verification_results", []))
        verification_results.append(v_result)

        traces.append({
            "node": "SafetyValidationNode",
            "passed": all_passed,
            "severity": severity.value,
        })

        return {
            "verification_results": verification_results,
            "provenance_traces": traces,
        }

    async def synthesizer_node(self, state: OrcaGraphState) -> dict[str, Any]:
        """SynthesizerNode: Combines verified evidence into an honest, structured answer."""
        traces = list(state.get("provenance_traces", []))
        verification_results = state.get("verification_results", [])
        v_passed = len(verification_results) > 0 and verification_results[-1].passed
        selected_pfz = state.get("selected_pfz")
        evidence_list = state.get("evidence_list", [])

        # Unverified / Rejected state -> Explicit UNAVAILABLE response
        if not v_passed or selected_pfz is None:
            limitations = []
            if verification_results:
                limitations = list(verification_results[-1].notes)

            final_ans = FinalResponse(
                session_id=f"orca_{utc_now().strftime('%Y%m%d_%H%M%S')}",
                response_type=ResponseType.ERROR,
                answer_text="UNAVAILABLE: I could not verify a current, operational PFZ advisory from official sources.",
                confidence=0.0,
                evidence_summary=evidence_list,
                limitations=limitations or ["No operational PFZ data available."],
            )
            traces.append({"node": "SynthesizerNode", "outcome": "unavailable"})
            return {"final_answer": final_ans, "provenance_traces": traces}

        # Verified state -> Synthesize structured answer
        coords = state.get("coordinates") or Geometry(lat=15.0, lon=73.5)
        dist_km, bearing_deg = _calculate_distance_and_bearing(coords, selected_pfz.location)

        if selected_pfz.source_valid_until:
            validity_str = f"source valid until {selected_pfz.source_valid_until.isoformat()}"
        elif selected_pfz.freshness_deadline:
            validity_str = f"ORCA freshness deadline: {selected_pfz.freshness_deadline.isoformat()} (source expiration unstated)"
        else:
            validity_str = "validity horizon unstated"

        answer_parts = [
            f"The nearest verified Potential Fishing Zone ({selected_pfz.pfz_id}) is approximately {dist_km:.1f} km away "
            f"on a bearing of {bearing_deg:.0f}° in the {selected_pfz.sector} sector ({validity_str})."
        ]

        if selected_pfz.geometry_derivation:
            answer_parts.append(f"Geometry derivation: {selected_pfz.geometry_derivation}.")

        sst_ev = state.get("sst_evidence")
        if sst_ev and isinstance(sst_ev.value, (int, float)):
            answer_parts.append(f"Surface sea temperature in this zone is {sst_ev.value:.1f}°C.")

        chl_ev = state.get("chlorophyll_evidence")
        if chl_ev and isinstance(chl_ev.value, (int, float)):
            answer_parts.append(f"Chlorophyll-a concentration is {chl_ev.value:.3f} mg/m³.")

        weather_ev = state.get("weather_evidence")
        if weather_ev and isinstance(weather_ev.value, dict):
            w_val = weather_ev.value
            wind = w_val.get("wind_speed", "")
            forecast = w_val.get("short_forecast", "")
            answer_parts.append(f"Marine weather: {forecast}, wind: {wind}.")

        # Contextual RAG advisory text distinction
        rag_evidences = [e for e in evidence_list if e.variable == "advisory_context"]
        if rag_evidences:
            top_advisory = rag_evidences[0].value
            if isinstance(top_advisory, dict) and top_advisory.get("title"):
                answer_parts.append(
                    f"Contextual Advisory ({top_advisory.get('title')}): {top_advisory.get('content')}"
                )

        geojson_feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [selected_pfz.location.lon, selected_pfz.location.lat]},
            "properties": {
                "pfz_id": selected_pfz.pfz_id,
                "sector": selected_pfz.sector,
                "distance_km": dist_km,
                "bearing_deg": bearing_deg,
                "depth_m": selected_pfz.depth_m,
            },
        }

        final_ans = FinalResponse(
            session_id=f"orca_{utc_now().strftime('%Y%m%d_%H%M%S')}",
            response_type=ResponseType.FACTUAL,
            answer_text=" ".join(answer_parts),
            confidence=0.85,
            evidence_summary=evidence_list,
            limitations=[
                f"Distance is deterministic geodesic calculation.",
                f"Retrieval tier: {state.get('pfz_tier_used')}.",
            ],
            map_overlays=[
                MapOverlay(
                    layer_id="nearest-pfz",
                    data={"type": "FeatureCollection", "features": [geojson_feature]},
                    style_hint="pfz",
                )
            ],
        )

        traces.append({"node": "SynthesizerNode", "outcome": "factual_synthesized"})
        return {"final_answer": final_ans, "provenance_traces": traces}


def _route_from_pfz(state: OrcaGraphState) -> str:
    """Conditional router: branches to parallel environment retrieval or safety validation."""
    if state.get("pfz_unavailable", False) or state.get("selected_pfz") is None:
        return "SafetyValidationNode"
    return "EnvironmentAgentNode"


def create_orca_graph(
    *,
    pfz_sources: list[Any] | None = None,
    sst_adapter: Any | None = None,
    chl_adapter: Any | None = None,
    weather_adapter: Any | None = None,
    advisory_rag_repo: Any | None = None,
) -> CompiledStateGraph:
    """Build and compile the multi-agent LangGraph workflow."""
    orchestrator = OrcaGraphOrchestrator(
        pfz_sources=pfz_sources,
        sst_adapter=sst_adapter,
        chl_adapter=chl_adapter,
        weather_adapter=weather_adapter,
        advisory_rag_repo=advisory_rag_repo,
    )

    workflow = StateGraph(OrcaGraphState)

    workflow.add_node("SupervisorNode", orchestrator.supervisor_node)
    workflow.add_node("PFZAgentNode", orchestrator.pfz_agent_node)
    workflow.add_node("EnvironmentAgentNode", orchestrator.environment_agent_node)
    workflow.add_node("SafetyValidationNode", orchestrator.safety_validation_node)
    workflow.add_node("SynthesizerNode", orchestrator.synthesizer_node)

    # Topology
    workflow.add_edge(START, "SupervisorNode")
    workflow.add_edge("SupervisorNode", "PFZAgentNode")
    workflow.add_conditional_edges(
        "PFZAgentNode",
        _route_from_pfz,
        {
            "EnvironmentAgentNode": "EnvironmentAgentNode",
            "SafetyValidationNode": "SafetyValidationNode",
        },
    )
    workflow.add_edge("EnvironmentAgentNode", "SafetyValidationNode")
    workflow.add_edge("SafetyValidationNode", "SynthesizerNode")
    workflow.add_edge("SynthesizerNode", END)

    return workflow.compile()
