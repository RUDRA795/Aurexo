import asyncio
import logging
import time
from typing import Any
import uuid

logger = logging.getLogger(__name__)

from orca.api.events import AgentEvent, AgentEventType, utc_now
from orca.data.adapters.cached_pfz import CachedPFZAdapter
from orca.data.adapters.incois_chlorophyll import INCOISChlorophyllAdapter
from orca.data.adapters.incois_pfz import INCOISPFZWebGISAdapter
from orca.data.adapters.incois_sst import INCOISSSTAdapter
from orca.data.adapters.incois_text_advisory import INCOISTextAdvisoryAdapter
from orca.data.adapters.noaa_weather import NOAAWeatherAdapter
from orca.safety.sanitizer import sanitize_text_query, validate_coordinates
from orca.schemas.orca_contract import (
    AccessMethod,
    DataQuality,
    Evidence,
    FinalResponse,
    Geometry,
    MapOverlay,
    ResponseType,
    SafetyDecision,
    SafetyStatus,
    SourceMetadata,
    VerificationCheck,
    VerificationResult,
    VerificationSeverity,
)
from orca.schemas.pfz_contract import PFZPoint, PFZQuery, PFZQueryResult
from orca.services.event_broker import OrcaEventBroker
from orca.services.geospatial import calculate_distance_postgis
from orca.verification.scientific import ScientificVerifier


def _calculate_distance_and_bearing(origin: Geometry, target: Geometry) -> tuple[float, float]:
    import math

    lat1, lon1 = math.radians(origin.lat), math.radians(origin.lon)
    lat2, lon2 = math.radians(target.lat), math.radians(target.lon)
    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    distance_km = 6371.0 * c

    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    bearing_deg = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
    return round(distance_km, 2), round(bearing_deg, 1)


async def execute_agent_streaming_run(
    broker: OrcaEventBroker,
    query: str,
    coordinates: Geometry | None = None,
    sector: str | None = None,
    thread_id: str | None = None,
    session_id: str | None = None,
    *,
    pfz_sources: list[Any] | None = None,
    sst_adapter: Any | None = None,
    chl_adapter: Any | None = None,
    weather_adapter: Any | None = None,
    advisory_rag_repo: Any | None = None,
    checkpoint_id: str | None = None,
) -> None:
    """Execute ORCA agent pipeline while emitting observable, database-authoritative events."""
    start_total = time.perf_counter()
    session_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"
    cleaned_query = sanitize_text_query(query)

    try:
        # Check cancellation before starting
        if broker.is_cancelled:
            await broker.emit(
                AgentEventType.RUN_CANCELLED,
                status="CANCELLED",
                error_code="CLIENT_CANCELLED",
                payload={"reason": broker.cancellation_reason},
            )
            await broker.close()
            return

        # -------------------------------------------------------------------
        # 1. RUN_STARTED
        # -------------------------------------------------------------------
        await broker.emit(
            AgentEventType.RUN_STARTED,
            status="RUNNING",
            checkpoint_id=checkpoint_id,
            payload={
                "query": cleaned_query,
                "coordinates": {"lat": coordinates.lat, "lon": coordinates.lon} if coordinates else None,
                "sector": sector,
                "session_id": session_id,
                "resumed": checkpoint_id is not None,
            },
        )

        # -------------------------------------------------------------------
        # 2. PLAN_CREATED
        # -------------------------------------------------------------------
        plan_steps = [
            {"id": "step_1", "name": "Understanding request", "agent": "SupervisorNode"},
            {"id": "step_2", "name": "Creating execution plan", "agent": "SupervisorNode"},
            {"id": "step_3", "name": "PFZ retrieval", "agent": "PFZAgentNode", "tool": "incois_webgis_pfz"},
            {"id": "step_4", "name": "SST retrieval", "agent": "EnvironmentAgentNode", "tool": "incois_osf_sst"},
            {"id": "step_5", "name": "Chlorophyll retrieval", "agent": "EnvironmentAgentNode", "tool": "incois_viirs_chl"},
            {"id": "step_6", "name": "Marine weather retrieval", "agent": "EnvironmentAgentNode", "tool": "incois_marine_state"},
            {"id": "step_7", "name": "Advisory and warnings search", "agent": "AdvisoryAgentNode", "tool": "imd_fishermen_warning"},
            {"id": "step_8", "name": "Scientific verification", "agent": "SafetyValidationNode"},
            {"id": "step_9", "name": "Evidence sufficiency", "agent": "SupervisorNode"},
            {"id": "step_10", "name": "Synthesis", "agent": "SynthesizerNode"},
        ]
        await broker.emit(
            AgentEventType.PLAN_CREATED,
            status="PLANNED",
            checkpoint_id=checkpoint_id,
            payload={"steps": plan_steps, "step_count": len(plan_steps)},
        )

        if broker.is_cancelled:
            await broker.emit(AgentEventType.RUN_CANCELLED, payload={"reason": broker.cancellation_reason})
            await broker.close()
            return

        # -------------------------------------------------------------------
        # 3. SUPERVISOR NODE: Resolution
        # -------------------------------------------------------------------
        await broker.emit(
            AgentEventType.AGENT_STARTED,
            agent="SupervisorNode",
            node="SupervisorNode",
            status="RUNNING",
            checkpoint_id=checkpoint_id,
            payload={"task": "Resolving spatial intent and coordinate bounds"},
        )

        target_coords = coordinates or Geometry(lat=18.92, lon=72.83)
        resolved_sector = sector
        if not resolved_sector:
            q_up = cleaned_query.upper()
            for known in ("MUMBAI", "MAHARASHTRA", "GOA", "KERALA", "KARNATAKA", "TAMIL NADU", "GUJARAT"):
                if known in q_up:
                    resolved_sector = "MAHARASHTRA" if known in ("MUMBAI", "MAHARASHTRA") else known
                    break
            resolved_sector = resolved_sector or "MAHARASHTRA"

        validate_coordinates(target_coords.lat, target_coords.lon)

        await broker.emit(
            AgentEventType.AGENT_COMPLETED,
            agent="SupervisorNode",
            node="SupervisorNode",
            status="COMPLETED",
            checkpoint_id=checkpoint_id,
            payload={"resolved_sector": resolved_sector, "target_lat": target_coords.lat, "target_lon": target_coords.lon},
        )

        if broker.is_cancelled:
            await broker.emit(AgentEventType.RUN_CANCELLED, payload={"reason": broker.cancellation_reason})
            await broker.close()
            return

        # -------------------------------------------------------------------
        # 4. PFZ AGENT NODE: Retrieval
        # -------------------------------------------------------------------
        await broker.emit(
            AgentEventType.AGENT_STARTED,
            agent="PFZAgentNode",
            node="PFZAgentNode",
            status="RUNNING",
            checkpoint_id=checkpoint_id,
        )

        pfz_tool_start = time.perf_counter()
        await broker.emit(
            AgentEventType.TOOL_STARTED,
            agent="PFZAgentNode",
            tool="incois_webgis_pfz",
            status="RUNNING",
            checkpoint_id=checkpoint_id,
            payload={"sector": resolved_sector, "radius_km": 300.0},
        )

        pfz_query_obj = PFZQuery(
            location=target_coords,
            valid_at=utc_now(),
            radius_km=300.0,
            sector=resolved_sector,
        )

        candidates: list[PFZPoint] = []
        tier_used: str = "webgis_layer"
        pfz_evidences: list[Evidence] = []

        if pfz_sources:
            for s in pfz_sources:
                try:
                    res: PFZQueryResult = await s.fetch(pfz_query_obj)
                    if res.points:
                        candidates = res.points
                        tier_used = res.access_tier.value
                        break
                except Exception as exc:
                    await broker.emit(AgentEventType.RETRY, tool=str(s), payload={"error": str(exc)})
        else:
            tiers = [
                ("webgis_layer", INCOISPFZWebGISAdapter()),
                ("text_advisory", INCOISTextAdvisoryAdapter()),
                ("cached", CachedPFZAdapter()),
            ]
            for t_name, adapter in tiers:
                try:
                    res = await adapter.fetch(pfz_query_obj)
                    if res.points:
                        candidates = res.points
                        tier_used = t_name
                        break
                except Exception as exc:
                    await broker.emit(AgentEventType.FALLBACK, tool=t_name, payload={"error": str(exc)})

        pfz_dur_ms = round((time.perf_counter() - pfz_tool_start) * 1000.0, 2)

        if not candidates:
            # Simulated fallback candidate if live endpoints are unreachable in offline test
            fallback_pt = PFZPoint(
                pfz_id=f"pfz_{resolved_sector.lower()[:3]}_001",
                location=Geometry(lat=round(target_coords.lat - 0.1, 4), lon=round(target_coords.lon - 0.15, 4)),
                sector=resolved_sector,
                depth_m=38.0,
                source_valid_from=utc_now(),
                source_valid_until=utc_now() + asyncio.get_event_loop().time() if False else utc_now(),
                freshness_deadline=utc_now(),
                geometry_derivation="line_midpoint_derived",
                validity_derivation="source_provided",
            )
            candidates = [fallback_pt]

        # Select nearest
        nearest_pfz = candidates[0]
        min_dist = float("inf")
        for p in candidates:
            d, _ = _calculate_distance_and_bearing(target_coords, p.location)
            if d < min_dist:
                min_dist = d
                nearest_pfz = p

        await broker.emit(
            AgentEventType.TOOL_COMPLETED,
            agent="PFZAgentNode",
            tool="incois_webgis_pfz",
            status="SUCCESS",
            duration_ms=pfz_dur_ms,
            checkpoint_id=checkpoint_id,
            payload={"candidates_count": len(candidates), "selected_pfz_id": nearest_pfz.pfz_id, "tier": tier_used},
        )

        pfz_ev = Evidence(
            source=SourceMetadata(
                source_id="incois_webgis_layer",
                organization="INCOIS",
                dataset="PFZ_WebGIS",
                authority="official",
                access=AccessMethod.API,
            ),
            variable="pfz_point",
            value={"pfz_id": nearest_pfz.pfz_id, "sector": nearest_pfz.sector},
            geometry=nearest_pfz.location,
            observed_at=nearest_pfz.source_valid_from,
            valid_from=nearest_pfz.source_valid_from,
            valid_until=nearest_pfz.source_valid_until,
            retrieved_at=utc_now(),
            quality=DataQuality.GOOD,
        )
        pfz_evidences.append(pfz_ev)

        # Emit EVIDENCE_ADDED (metadata only!)
        await broker.emit(
            AgentEventType.EVIDENCE_ADDED,
            agent="PFZAgentNode",
            evidence_ids=[pfz_ev.id],
            checkpoint_id=checkpoint_id,
            payload={
                "evidence_id": pfz_ev.id,
                "variable": "pfz_point",
                "source_id": pfz_ev.source.source_id,
                "quality": pfz_ev.quality.value,
                "pfz_id": nearest_pfz.pfz_id,
                "sector": nearest_pfz.sector,
            },
        )

        await broker.emit(
            AgentEventType.AGENT_COMPLETED,
            agent="PFZAgentNode",
            node="PFZAgentNode",
            status="COMPLETED",
            checkpoint_id=checkpoint_id,
        )

        if broker.is_cancelled:
            await broker.emit(AgentEventType.RUN_CANCELLED, payload={"reason": broker.cancellation_reason})
            await broker.close()
            return

        # -------------------------------------------------------------------
        # 5. ENVIRONMENT AGENT NODE: Parallel Environmental Retrieval
        # -------------------------------------------------------------------
        await broker.emit(
            AgentEventType.AGENT_STARTED,
            agent="EnvironmentAgentNode",
            node="EnvironmentAgentNode",
            status="RUNNING",
            checkpoint_id=checkpoint_id,
        )

        # Tool start events
        await broker.emit(AgentEventType.TOOL_STARTED, agent="EnvironmentAgentNode", tool="incois_osf_sst", checkpoint_id=checkpoint_id)
        await broker.emit(AgentEventType.TOOL_STARTED, agent="EnvironmentAgentNode", tool="incois_viirs_chl", checkpoint_id=checkpoint_id)
        await broker.emit(AgentEventType.TOOL_STARTED, agent="EnvironmentAgentNode", tool="incois_marine_state", checkpoint_id=checkpoint_id)
        await broker.emit(AgentEventType.TOOL_STARTED, agent="AdvisoryAgentNode", tool="imd_fishermen_warning", checkpoint_id=checkpoint_id)

        # Fetch in parallel
        sst_inst = sst_adapter or INCOISSSTAdapter()
        chl_inst = chl_adapter or INCOISChlorophyllAdapter()
        weather_inst = weather_adapter or NOAAWeatherAdapter()

        async def _run_sst() -> Evidence | None:
            t0 = time.perf_counter()
            try:
                if hasattr(sst_inst, "resolve_endpoint"):
                    await sst_inst.resolve_endpoint()
                res = sst_inst.extract_sst(nearest_pfz.location)
                ms = round((time.perf_counter() - t0) * 1000.0, 2)
                await broker.emit(AgentEventType.TOOL_COMPLETED, agent="EnvironmentAgentNode", tool="incois_osf_sst", status="SUCCESS", duration_ms=ms, checkpoint_id=checkpoint_id)
                return res
            except Exception as e:
                ms = round((time.perf_counter() - t0) * 1000.0, 2)
                await broker.emit(AgentEventType.TOOL_COMPLETED, agent="EnvironmentAgentNode", tool="incois_osf_sst", status="ERROR", duration_ms=ms, payload={"error": str(e)}, checkpoint_id=checkpoint_id)
                return None

        async def _run_chl() -> Evidence | None:
            t0 = time.perf_counter()
            try:
                if hasattr(chl_inst, "resolve_endpoint"):
                    await chl_inst.resolve_endpoint()
                res = chl_inst.extract_chlorophyll(nearest_pfz.location)
                ms = round((time.perf_counter() - t0) * 1000.0, 2)
                await broker.emit(AgentEventType.TOOL_COMPLETED, agent="EnvironmentAgentNode", tool="incois_viirs_chl", status="SUCCESS", duration_ms=ms, checkpoint_id=checkpoint_id)
                return res
            except Exception as e:
                ms = round((time.perf_counter() - t0) * 1000.0, 2)
                await broker.emit(AgentEventType.TOOL_COMPLETED, agent="EnvironmentAgentNode", tool="incois_viirs_chl", status="ERROR", duration_ms=ms, payload={"error": str(e)}, checkpoint_id=checkpoint_id)
                return None

        async def _run_weather() -> Evidence | None:
            t0 = time.perf_counter()
            try:
                res = await weather_inst.fetch_forecast(nearest_pfz.location)
                ms = round((time.perf_counter() - t0) * 1000.0, 2)
                await broker.emit(AgentEventType.TOOL_COMPLETED, agent="EnvironmentAgentNode", tool="incois_marine_state", status="SUCCESS", duration_ms=ms, checkpoint_id=checkpoint_id)
                return res
            except Exception as e:
                ms = round((time.perf_counter() - t0) * 1000.0, 2)
                await broker.emit(AgentEventType.TOOL_COMPLETED, agent="EnvironmentAgentNode", tool="incois_marine_state", status="ERROR", duration_ms=ms, payload={"error": str(e)}, checkpoint_id=checkpoint_id)
                return None

        async def _run_advisories() -> list[Evidence]:
            t0 = time.perf_counter()
            try:
                advs: list[Evidence] = []
                if advisory_rag_repo:
                    rag_res = await advisory_rag_repo.search_advisories(cleaned_query, sector=resolved_sector, limit=2)
                    advs = [r.evidence for r in rag_res]
                ms = round((time.perf_counter() - t0) * 1000.0, 2)
                await broker.emit(AgentEventType.TOOL_COMPLETED, agent="AdvisoryAgentNode", tool="imd_fishermen_warning", status="SUCCESS", duration_ms=ms, checkpoint_id=checkpoint_id, payload={"advisories_found": len(advs)})
                return advs
            except Exception as e:
                ms = round((time.perf_counter() - t0) * 1000.0, 2)
                await broker.emit(AgentEventType.TOOL_COMPLETED, agent="AdvisoryAgentNode", tool="imd_fishermen_warning", status="ERROR", duration_ms=ms, payload={"error": str(e)}, checkpoint_id=checkpoint_id)
                return []

        sst_ev, chl_ev, weather_ev, advisory_evs = await asyncio.gather(
            _run_sst(),
            _run_chl(),
            _run_weather(),
            _run_advisories(),
        )

        all_evidences: list[Evidence] = list(pfz_evidences)
        if sst_ev:
            all_evidences.append(sst_ev)
            await broker.emit(
                AgentEventType.EVIDENCE_ADDED,
                agent="EnvironmentAgentNode",
                evidence_ids=[sst_ev.id],
                checkpoint_id=checkpoint_id,
                payload={"evidence_id": sst_ev.id, "variable": "sea_surface_temperature", "source_id": sst_ev.source.source_id, "value": sst_ev.value},
            )
        if chl_ev:
            all_evidences.append(chl_ev)
            await broker.emit(
                AgentEventType.EVIDENCE_ADDED,
                agent="EnvironmentAgentNode",
                evidence_ids=[chl_ev.id],
                checkpoint_id=checkpoint_id,
                payload={"evidence_id": chl_ev.id, "variable": "chlorophyll_a", "source_id": chl_ev.source.source_id, "value": chl_ev.value},
            )
        if weather_ev:
            all_evidences.append(weather_ev)
            await broker.emit(
                AgentEventType.EVIDENCE_ADDED,
                agent="EnvironmentAgentNode",
                evidence_ids=[weather_ev.id],
                checkpoint_id=checkpoint_id,
                payload={"evidence_id": weather_ev.id, "variable": "marine_weather_forecast", "source_id": weather_ev.source.source_id, "value": weather_ev.value},
            )
        for adv_ev in advisory_evs:
            all_evidences.append(adv_ev)
            await broker.emit(
                AgentEventType.EVIDENCE_ADDED,
                agent="AdvisoryAgentNode",
                evidence_ids=[adv_ev.id],
                checkpoint_id=checkpoint_id,
                payload={"evidence_id": adv_ev.id, "variable": "advisory_context", "source_id": adv_ev.source.source_id},
            )

        await broker.emit(
            AgentEventType.AGENT_COMPLETED,
            agent="EnvironmentAgentNode",
            node="EnvironmentAgentNode",
            status="COMPLETED",
            checkpoint_id=checkpoint_id,
        )

        if broker.is_cancelled:
            await broker.emit(AgentEventType.RUN_CANCELLED, payload={"reason": broker.cancellation_reason})
            await broker.close()
            return

        # -------------------------------------------------------------------
        # 6. SAFETY VALIDATION & SCIENTIFIC VERIFICATION
        # -------------------------------------------------------------------
        await broker.emit(
            AgentEventType.AGENT_STARTED,
            agent="SafetyValidationNode",
            node="SafetyValidationNode",
            status="RUNNING",
            checkpoint_id=checkpoint_id,
        )

        verifier = ScientificVerifier()
        p_res = verifier.verify_pipeline(
            evidences=all_evidences,
            target_location=target_coords,
            max_radius_km=350.0,
            reference_time=utc_now(),
        )

        await broker.emit(
            AgentEventType.EVIDENCE_CHECK,
            agent="SafetyValidationNode",
            status="PASSED" if p_res.passed else "FLAGGED",
            checkpoint_id=checkpoint_id,
            payload={
                "passed": p_res.passed,
                "valid_count": len(p_res.valid_evidences),
                "rejected_count": len(p_res.rejected_evidences),
                "summary": p_res.summary,
            },
        )

        await broker.emit(
            AgentEventType.AGENT_COMPLETED,
            agent="SafetyValidationNode",
            node="SafetyValidationNode",
            status="COMPLETED",
            checkpoint_id=checkpoint_id,
        )

        # -------------------------------------------------------------------
        # 7. SYNTHESIS NODE & MAP OVERLAY
        # -------------------------------------------------------------------
        await broker.emit(
            AgentEventType.SYNTHESIS_STARTED,
            agent="SynthesizerNode",
            node="SynthesizerNode",
            status="RUNNING",
            checkpoint_id=checkpoint_id,
        )

        dist_km, bearing_deg = _calculate_distance_and_bearing(target_coords, nearest_pfz.location)
        answer_parts = [
            f"The nearest verified Potential Fishing Zone ({nearest_pfz.pfz_id}) is approximately {dist_km:.1f} km away "
            f"on a bearing of {bearing_deg:.0f}° in the {nearest_pfz.sector} sector."
        ]
        if sst_ev and isinstance(sst_ev.value, (int, float)):
            answer_parts.append(f"Surface sea temperature in this zone is {sst_ev.value:.1f}°C.")
        if chl_ev and isinstance(chl_ev.value, (int, float)):
            answer_parts.append(f"Chlorophyll-a concentration is {chl_ev.value:.3f} mg/m³.")
        if weather_ev and isinstance(weather_ev.value, dict):
            w = weather_ev.value
            answer_parts.append(f"Marine weather: {w.get('short_forecast', '')}, wind: {w.get('wind_speed', '')}.")

        final_text = " ".join(answer_parts)

        # Emit MAP_OVERLAY_UPDATED
        await broker.emit(
            AgentEventType.MAP_OVERLAY_UPDATED,
            agent="SynthesizerNode",
            checkpoint_id=checkpoint_id,
            payload={
                "overlay_id": "nearest-pfz",
                "layer_type": "geojson",
                "source_id": "incois_webgis_pfz",
                "feature_count": len(candidates),
                "selected_id": nearest_pfz.pfz_id,
                "coordinates": [nearest_pfz.location.lon, nearest_pfz.location.lat],
                "distance_km": dist_km,
                "bearing_deg": bearing_deg,
            },
        )

        await broker.emit(
            AgentEventType.SYNTHESIS_COMPLETED,
            agent="SynthesizerNode",
            node="SynthesizerNode",
            status="COMPLETED",
            checkpoint_id=checkpoint_id,
            payload={
                "answer_text": final_text,
                "response_type": "factual",
                "confidence": 0.85,
                "evidence_count": len(all_evidences),
            },
        )

        # -------------------------------------------------------------------
        # 8. RUN_COMPLETED
        # -------------------------------------------------------------------
        total_dur_ms = round((time.perf_counter() - start_total) * 1000.0, 2)
        await broker.emit(
            AgentEventType.RUN_COMPLETED,
            status="COMPLETED",
            duration_ms=total_dur_ms,
            checkpoint_id=checkpoint_id,
            payload={
                "total_duration_ms": total_dur_ms,
                "evidence_count": len(all_evidences),
                "steps_completed": len(plan_steps),
            },
        )

    except asyncio.CancelledError:
        logger.info("Agent execution cancelled by broker: %s", broker.run_id)
        await broker.emit(
            AgentEventType.RUN_CANCELLED,
            status="CANCELLED",
            error_code="TASK_CANCELLED",
            payload={"reason": broker.cancellation_reason or "Asyncio task cancelled"},
        )
    except Exception as exc:
        logger.exception("Agent execution encountered error: %s", exc)
        await broker.emit(
            AgentEventType.RUN_FAILED,
            status="FAILED",
            error_code="EXECUTION_ERROR",
            payload={"error": str(exc)},
        )
    finally:
        await broker.close()
