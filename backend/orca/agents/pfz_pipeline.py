"""PFZ vertical slice with typed tools, provenance, deterministic ranking,
one-replan recovery, and a swappable INCOIS adapter boundary.

The live INCOIS adapter is intentionally separated from the pipeline. The
current official surface exposes PFZ WebGIS and multilingual text advisories;
its public HTML does not expose a stable, documented JSON contract, so the
adapter should be configured against the concrete WebGIS/HTML endpoint found
in the deployment environment rather than inventing an API here.
"""
from __future__ import annotations

import math
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from time import perf_counter
from typing import Callable, Iterable

from orca.schemas.orca_contract import (
    AgentResult,
    AgentStatus,
    Evidence,
    FinalResponse,
    FusionResult,
    Geometry,
    Intent,
    MapOverlay,
    OrcaState,
    Plan,
    PlanStep,
    ResponseType,
    SourceMetadata,
    ToolCall,
    ToolName,
    ToolStatus,
    TraceStep,
    VerificationCheck,
    VerificationResult,
    VerificationSeverity,
    utc_now,
)
from orca.schemas.pfz_contract import (
    DistanceRequest,
    DistanceResult,
    PFZAccessTier,
    PFZPoint,
    PFZQuery,
    PFZQueryResult,
)
from orca.services.geospatial import calculate_distance_postgis


class PFZSourceUnavailable(Exception):
    pass


class PFZDataSource(ABC):
    tier: PFZAccessTier

    @abstractmethod
    async def fetch(self, query: PFZQuery) -> PFZQueryResult:
        raise NotImplementedError


class MockPFZDataSource(PFZDataSource):
    tier = PFZAccessTier.TEXT_ADVISORY

    def __init__(self, points: list[PFZPoint] | None = None, fail: bool = False):
        self._points = points if points is not None else self._default_points()
        self._fail = fail

    @staticmethod
    def _default_points() -> list[PFZPoint]:
        now = utc_now()
        return [
            PFZPoint(
                pfz_id="pfz_goa_001",
                location=Geometry(lat=15.62, lon=73.55),
                sector="GOA",
                depth_m=45.0,
                landing_center="Malim",
                forecast_date=now,
                valid_from=now - timedelta(minutes=1),
                valid_until=now + timedelta(hours=36),
                wind_speed_ms=6.2,
                wind_direction_deg=210,
            ),
            PFZPoint(
                pfz_id="pfz_goa_002",
                location=Geometry(lat=15.20, lon=73.70),
                sector="GOA",
                depth_m=60.0,
                landing_center="Betul",
                forecast_date=now,
                valid_from=now - timedelta(minutes=1),
                valid_until=now + timedelta(hours=36),
                wind_speed_ms=5.8,
                wind_direction_deg=205,
            ),
            PFZPoint(
                pfz_id="pfz_goa_003_expired",
                location=Geometry(lat=15.40, lon=73.60),
                sector="GOA",
                depth_m=50.0,
                landing_center="Panaji",
                forecast_date=now - timedelta(days=2),
                valid_from=now - timedelta(days=2),
                valid_until=now - timedelta(hours=6),
                wind_speed_ms=7.0,
                wind_direction_deg=200,
            ),
        ]

    async def fetch(self, query: PFZQuery) -> PFZQueryResult:
        if self._fail:
            raise PFZSourceUnavailable("mock source configured to fail")
        points = self._points
        if query.sector:
            points = [p for p in points if p.sector == query.sector]
        return PFZQueryResult(
            points=points,
            source=SourceMetadata(
                source_id="incois_pfz_mock",
                organization="INCOIS",
                dataset="PFZ Advisory (mock fixture)",
                domain=["pfz", "fisheries"],
                coverage="indian_coast",
                latency="daily",
                authority="official",
                access="scrape",
                freshness_policy_hours=24,
            ),
            access_tier=self.tier,
            retrieved_at=utc_now(),
            limitations=["Mock fixture data — not a live INCOIS retrieval."],
        )


class INCOISPFZAdapter(PFZDataSource):
    """Live adapter seam for the current INCOIS PFZ public surface.

    Implement concrete endpoint/parser details in deployment configuration.
    The official service exposes a PFZ WebGIS and multilingual text advisory;
    there is no stable documented JSON API in the public HTML used by this
    project, so this class intentionally refuses to guess an endpoint.
    """

    tier = PFZAccessTier.WEBGIS_LAYER

    def __init__(self, fetch_impl: Callable[[PFZQuery], PFZQueryResult] | None = None):
        self._fetch_impl = fetch_impl

    async def fetch(self, query: PFZQuery) -> PFZQueryResult:
        if self._fetch_impl is None:
            raise PFZSourceUnavailable(
                "INCOIS WebGIS adapter requires a deployment-specific feature-service/HTML parser."
            )
        result = await self._fetch_impl(query)
        return PFZQueryResult.model_validate(result)


async def fetch_pfz_with_fallback(
    query: PFZQuery,
    sources: list[PFZDataSource],
) -> PFZQueryResult:
    errors: list[str] = []
    # Explicit caller ordering is honored; source registry can sort this list later.
    for source in sources:
        try:
            return await source.fetch(query)
        except PFZSourceUnavailable as exc:
            errors.append(f"{source.tier.value}: {exc}")
    raise PFZSourceUnavailable("All PFZ source tiers exhausted: " + " | ".join(errors))


def calculate_distance(request: DistanceRequest) -> DistanceResult:
    """Deterministic haversine fallback for development/tests.

    Production implementation should use PostGIS geography ST_Distance and
    ST_DWithin. Both are transparent swaps at the tool boundary.
    """
    earth_km = 6371.0088
    lat1 = math.radians(request.origin.lat)
    lon1 = math.radians(request.origin.lon)
    distances: list[float] = []
    bearings: list[float] = []

    for dest in request.destinations:
        lat2 = math.radians(dest.lat)
        lon2 = math.radians(dest.lon)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(min(1.0, math.sqrt(a)))
        distances.append(earth_km * c)
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        bearings.append((math.degrees(math.atan2(y, x)) + 360.0) % 360.0)

    return DistanceResult(
        distances_km=distances,
        bearings_deg=bearings,
        method="haversine_fallback",
    )


def _completed_tool_call(call: ToolCall, *, status: ToolStatus, output: dict | None = None,
                         evidence_ids: list[str] | None = None, error: str | None = None,
                         started: float | None = None) -> ToolCall:
    call.status = status
    call.finished_at = utc_now()
    if started is not None:
        call.duration_ms = (perf_counter() - started) * 1000.0
    call.output = output
    if evidence_ids:
        call.evidence_ids.extend(evidence_ids)
    call.error = error
    return call


async def pfz_agent(query: PFZQuery, sources: list[PFZDataSource]) -> AgentResult:
    tool_call = ToolCall(tool=ToolName.GET_PFZ, input=query.model_dump(mode="json"))
    started = perf_counter()
    tool_call.status = ToolStatus.RUNNING
    try:
        pfz_result = await fetch_pfz_with_fallback(query, sources)
    except PFZSourceUnavailable as exc:
        _completed_tool_call(tool_call, status=ToolStatus.FAILED, error=str(exc), started=started)
        return AgentResult(
            agent="pfz_agent",
            status=AgentStatus.FAILED,
            limitations=[str(exc)],
            tool_calls=[tool_call],
        )

    valid_points: list[PFZPoint] = []
    evidence: list[Evidence] = []
    now = utc_now()
    source = pfz_result.source

    for point in pfz_result.points:
        if not point.is_valid_at(query.valid_at):
            continue
        # The slice applies the requested sector at the normalized boundary,
        # not only inside source-specific retrieval implementations.
        if query.sector and point.sector != query.sector:
            continue
        valid_points.append(point)
        ev = Evidence(
            source=source,
            variable="pfz_candidate",
            value={
                "pfz_id": point.pfz_id,
                "sector": point.sector,
                "lat": point.location.lat,
                "lon": point.location.lon,
            },
            geometry=point.location,
            observed_at=point.forecast_date or pfz_result.retrieved_at,
            reference_time=point.forecast_date,
            valid_from=point.valid_from,
            valid_until=point.valid_until,
            retrieved_at=pfz_result.retrieved_at,
            method="official_advisory",
        )
        evidence.append(ev)

    limitations = list(pfz_result.limitations)
    excluded = len(pfz_result.points) - len(valid_points)
    if excluded:
        limitations.append(f"{excluded} PFZ candidate(s) excluded by requested time/sector validity.")

    if not valid_points:
        _completed_tool_call(
            tool_call,
            status=ToolStatus.SUCCESS,
            output={"candidate_count": 0, "access_tier": pfz_result.access_tier.value},
            started=started,
        )
        return AgentResult(
            agent="pfz_agent",
            status=AgentStatus.NO_DATA,
            result={},
            limitations=limitations + ["No currently valid PFZ candidates matched the request."],
            tool_calls=[tool_call],
        )

    # The tool output is only the normalized source facts; no distance is injected.
    _completed_tool_call(
        tool_call,
        status=ToolStatus.SUCCESS,
        output={"candidate_count": len(valid_points), "access_tier": pfz_result.access_tier.value},
        evidence_ids=[e.id for e in evidence],
        started=started,
    )

    return AgentResult(
        agent="pfz_agent",
        status=AgentStatus.SUCCESS,
        result={
            "candidates": [p.model_dump(mode="json") for p in valid_points],
            "access_tier": pfz_result.access_tier.value,
        },
        evidence=evidence,
        # Evidence quality, not probability of scientific correctness.
        confidence=0.0,
        limitations=limitations,
        tool_calls=[tool_call],
    )


async def geospatial_agent(
    origin: Geometry,
    candidates: list[PFZPoint],
    radius_km: float,
) -> AgentResult:
    """Execute the deterministic distance tool and expose its audit trail."""
    if not candidates:
        return AgentResult(
            agent="geospatial_agent",
            status=AgentStatus.NO_DATA,
            result={"candidates": [], "within_radius": []},
            confidence=0.0,
        )

    request = DistanceRequest(
        origin=origin,
        destinations=[p.location for p in candidates],
    )
    tool_call = ToolCall(
        tool=ToolName.CALCULATE_DISTANCE,
        input=request.model_dump(mode="json"),
        status=ToolStatus.RUNNING,
    )
    started = perf_counter()
    spatial_mode = os.getenv("ORCA_SPATIAL_MODE", "haversine").strip().lower()
    if spatial_mode == "postgis":
        distance_result = await calculate_distance_postgis(request)
    elif spatial_mode == "haversine":
        distance_result = calculate_distance(request)
    else:
        raise ValueError(
            "Unsupported ORCA_SPATIAL_MODE. Use 'postgis' or 'haversine'."
        )

    computed_evidence: list[Evidence] = []
    ranked_rows: list[tuple[PFZPoint, float, float, Evidence]] = []
    for point, distance_km, bearing_deg in zip(
        candidates, distance_result.distances_km, distance_result.bearings_deg
    ):
        evidence = Evidence(
            source=SourceMetadata(
                source_id="orca_geospatial_engine",
                organization="ORCA",
                dataset="Deterministic geospatial calculation",
                domain=["geospatial", "distance", "bearing"],
                coverage="request_scope",
                authority="internal",
                access="internal",
                freshness_policy_hours=1.0,
            ),
            variable="distance_and_bearing",
            value={
                "pfz_id": point.pfz_id,
                "distance_km": distance_km,
                "bearing_deg": bearing_deg,
            },
            unit="km;degrees",
            geometry=point.location,
            observed_at=utc_now(),
            reference_time=None,
            valid_from=None,
            valid_until=None,
            retrieved_at=utc_now(),
            method=distance_result.method,
        )
        computed_evidence.append(evidence)
        ranked_rows.append((point, distance_km, bearing_deg, evidence))

    ranked_rows.sort(key=lambda row: row[1])
    within = [row for row in ranked_rows if row[1] <= radius_km]
    output = {
        "candidate_count": len(candidates),
        "within_radius_count": len(within),
        "radius_km": radius_km,
        "distances_km": [row[1] for row in within],
        "bearings_deg": [row[2] for row in within],
        "pfz_ids": [row[0].pfz_id for row in within],
        "method": distance_result.method,
    }
    _completed_tool_call(
        tool_call,
        status=ToolStatus.SUCCESS,
        output=output,
        evidence_ids=[ev.id for _, _, _, ev in within],
        started=started,
    )

    return AgentResult(
        agent="geospatial_agent",
        status=AgentStatus.SUCCESS if within else AgentStatus.NO_DATA,
        result=output,
        evidence=[ev for _, _, _, ev in within],
        confidence=0.0,
        limitations=[] if within else [f"No PFZ is within the requested {radius_km:.0f} km radius."],
        tool_calls=[tool_call],
    )


def geospatial_rank_by_distance(
    origin: Geometry,
    candidates: list[PFZPoint],
) -> tuple[list[PFZPoint], DistanceResult]:
    """Compatibility helper for deterministic unit tests and non-agent callers."""
    if not candidates:
        return [], DistanceResult(distances_km=[], bearings_deg=[], method="haversine_fallback")
    distance_result = calculate_distance(
        DistanceRequest(origin=origin, destinations=[p.location for p in candidates])
    )
    ranked = sorted(
        zip(candidates, distance_result.distances_km, distance_result.bearings_deg),
        key=lambda item: item[1],
    )
    return (
        [x[0] for x in ranked],
        DistanceResult(
            distances_km=[x[1] for x in ranked],
            bearings_deg=[x[2] for x in ranked],
            method=distance_result.method,
        ),
    )


def verify_pfz_result(
    agent_result: AgentResult,
    *,
    requested_time: datetime,
) -> VerificationResult:
    checks: dict[VerificationCheck, bool] = {}
    checks[VerificationCheck.EVIDENCE_PRESENT] = bool(agent_result.evidence) if agent_result.status != AgentStatus.NO_DATA else True
    checks[VerificationCheck.FRESHNESS] = all(e.is_fresh() for e in agent_result.evidence) if agent_result.evidence else agent_result.status == AgentStatus.NO_DATA
    checks[VerificationCheck.SPATIAL_RELEVANCE] = all(e.geometry is not None for e in agent_result.evidence) if agent_result.evidence else agent_result.status == AgentStatus.NO_DATA
    checks[VerificationCheck.TEMPORAL_RELEVANCE] = all(e.is_valid_at(requested_time) for e in agent_result.evidence) if agent_result.evidence else agent_result.status == AgentStatus.NO_DATA
    checks[VerificationCheck.CITATION_VALID] = all(bool(e.source.source_id) for e in agent_result.evidence) if agent_result.evidence else agent_result.status == AgentStatus.NO_DATA

    missing = [name.value for name, ok in checks.items() if not ok]
    if agent_result.status == AgentStatus.FAILED:
        return VerificationResult(
            passed=False,
            severity=VerificationSeverity.BLOCKING,
            checks=checks,
            missing=missing or ["pfz_retrieval_failed"],
            notes=["PFZ source retrieval failed."],
        )
    if agent_result.status == AgentStatus.NO_DATA:
        return VerificationResult(
            passed=True,
            severity=VerificationSeverity.INFO,
            checks=checks,
            notes=["Source was queried successfully but returned no valid matching PFZ."],
        )
    return VerificationResult(
        passed=not missing,
        severity=VerificationSeverity.INFO if not missing else VerificationSeverity.BLOCKING,
        checks=checks,
        missing=missing,
    )


def _build_plan() -> Plan:
    return Plan(
        steps=[
            PlanStep(step_id="pfz_retrieval", agent="pfz_agent", goal="retrieve and normalize current PFZ candidates"),
            PlanStep(
                step_id="geospatial_ranking",
                agent="geospatial_agent",
                goal="filter by radius and rank by deterministic geodesic distance",
                depends_on=["pfz_retrieval"],
            ),
        ],
        rationale="Retrieve official PFZ facts first, then perform deterministic spatial ranking.",
    )


async def run_pfz_query(
    query_text: str,
    location: Geometry,
    valid_at: datetime,
    sources: list[PFZDataSource] | None = None,
    fallback_sources: list[PFZDataSource] | None = None,
    *,
    radius_km: float = 300.0,
    sector: str | None = None,
) -> OrcaState:
    if sources is None:
        from orca.data.registry import TieredPFZProvider
        sources = [TieredPFZProvider()]

    state = OrcaState(query=query_text, location=location, language="en", intent=Intent.PFZ_LOOKUP)
    state.plan = _build_plan()
    query = PFZQuery(location=location, valid_at=valid_at, radius_km=radius_km, sector=sector)

    trace: list[TraceStep] = []

    async def attempt(src_list: list[PFZDataSource]) -> tuple[AgentResult, VerificationResult]:
        t0 = perf_counter()
        result = await pfz_agent(query, src_list)
        trace.append(TraceStep(node="pfz_agent", duration_ms=(perf_counter() - t0) * 1000))
        verification = verify_pfz_result(result, requested_time=valid_at)
        trace.append(TraceStep(node="pfz_verification", duration_ms=0.0, status="passed" if verification.passed else "failed"))
        return result, verification

    agent_result, verification = await attempt(sources)
    state.agent_results.append(agent_result)
    state.verification = verification

    # One and only one recovery attempt.
    if verification.severity == VerificationSeverity.BLOCKING and state.can_replan() and fallback_sources:
        state.register_replan()
        agent_result, verification = await attempt(fallback_sources)
        state.agent_results.append(agent_result)
        state.verification = verification

    if agent_result.status == AgentStatus.FAILED:
        state.final_answer = FinalResponse(
            session_id=state.session_id,
            response_type=ResponseType.ERROR,
            answer_text="I could not verify a current PFZ advisory from the available official sources.",
            confidence=0.0,
            limitations=agent_result.limitations,
            trace=trace,
        )
        return state

    if agent_result.status == AgentStatus.NO_DATA:
        state.final_answer = FinalResponse(
            session_id=state.session_id,
            response_type=ResponseType.ERROR,
            answer_text="No currently valid PFZ matched the requested location, time, sector, and radius.",
            confidence=0.0,
            limitations=agent_result.limitations + [
                "The source responded successfully; no matching PFZ was returned."
            ],
            trace=trace,
        )
        return state

    candidates = [PFZPoint.model_validate(c) for c in agent_result.result["candidates"]]

    geo_t0 = perf_counter()
    geo_result = await geospatial_agent(location, candidates, query.radius_km)
    trace.append(TraceStep(
        node="geospatial_agent",
        duration_ms=(perf_counter() - geo_t0) * 1000.0,
        status=geo_result.status.value,
    ))
    state.agent_results.append(geo_result)

    if geo_result.status == AgentStatus.NO_DATA:
        state.final_answer = FinalResponse(
            session_id=state.session_id,
            response_type=ResponseType.ERROR,
            answer_text=f"No valid PFZ was found within {query.radius_km:.0f} km of the requested location.",
            confidence=0.0,
            evidence_summary=agent_result.evidence,
            limitations=agent_result.limitations + geo_result.limitations,
            trace=trace,
        )
        return state

    pfz_by_id = {p.pfz_id: p for p in candidates}
    ranked_ids = geo_result.result["pfz_ids"]
    distances_km = geo_result.result["distances_km"]
    bearings_deg = geo_result.result["bearings_deg"]
    nearest = pfz_by_id[ranked_ids[0]]
    nearest_km = distances_km[0]
    nearest_bearing = bearings_deg[0]

    source_evidence = {e.value.get("pfz_id"): e for e in agent_result.evidence}
    computation_evidence = {e.value.get("pfz_id"): e for e in geo_result.evidence}
    evidence = [source_evidence[pfz_id] for pfz_id in ranked_ids if pfz_id in source_evidence]
    evidence.extend(computation_evidence[pfz_id] for pfz_id in ranked_ids if pfz_id in computation_evidence)
    state.fusion = FusionResult(evidence=evidence, conflicts=[])

    geojson_features = []
    for pfz_id, distance, bearing in zip(ranked_ids, distances_km, bearings_deg):
        point = pfz_by_id[pfz_id]
        geojson_features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [point.location.lon, point.location.lat]},
            "properties": {
                "pfz_id": point.pfz_id,
                "sector": point.sector,
                "distance_km": round(distance, 2),
                "bearing_deg": round(bearing, 1),
                "is_nearest": point.pfz_id == nearest.pfz_id,
            },
        })

    validity = nearest.valid_until.isoformat() if nearest.valid_until else "unspecified"
    answer = (
        f"The nearest verified Potential Fishing Zone is approximately {nearest_km:.1f} km away "
        f"on a bearing of {nearest_bearing:.0f}°, in the {nearest.sector} sector "
        f"(valid until {validity})."
    )

    try:
        from orca.services.ingestion import sample_environmental_context
        env_evidence = sample_environmental_context(nearest.location)
        if env_evidence:
            evidence.extend(env_evidence)
            sst_ev = next((e for e in env_evidence if e.variable == "sea_surface_temperature"), None)
            if sst_ev and isinstance(sst_ev.value, (int, float)):
                answer += f" Surface sea temperature in this zone is {sst_ev.value:.1f}°C."
    except Exception:
        pass

    state.final_answer = FinalResponse(
        session_id=state.session_id,
        response_type=ResponseType.FACTUAL,
        answer_text=answer,
        confidence=0.0,
        evidence_summary=evidence,
        limitations=agent_result.limitations + [
            f"Distance is deterministic; calculation method: {geo_result.result['method']}."
        ],
        map_overlays=[
            MapOverlay(
                layer_id="nearest-pfz",
                data={"type": "FeatureCollection", "features": geojson_features},
                style_hint="pfz",
            )
        ],
        trace=trace,
    )
    return state
