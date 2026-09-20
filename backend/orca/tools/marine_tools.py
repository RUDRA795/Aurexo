from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from orca.data.adapters.copernicus_marine import CopernicusMarineAdapter
from orca.data.adapters.incois_chlorophyll import INCOISChlorophyllAdapter
from orca.data.adapters.incois_osf_weather import IMDMarineWeatherAdapter, INCOISOceanStateForecastAdapter
from orca.data.adapters.incois_sst import INCOISSSTAdapter
from orca.data.adapters.noaa_weather import NOAAWeatherAdapter
from orca.data.registry import TieredPFZProvider
from orca.safety.geographic_policy import is_within_operational_region
from orca.safety.sanitizer import validate_coordinates
from orca.schemas.orca_contract import (
    AccessMethod,
    DataQuality,
    Evidence,
    Geometry,
    SourceMetadata,
    utc_now,
)
from orca.schemas.pfz_contract import PFZPoint, PFZQuery, PFZQueryResult
from orca.services.geospatial import calculate_distance_postgis
from orca.tools.registry import BaseMarineTool, ToolExecutionResult, ToolRegistry, ToolStatus
from orca.translation.base import TranslationRequest
from orca.translation.service import TieredTranslationService


# ---------------------------------------------------------------------------
# 1. PFZ Retrieval Tool
# ---------------------------------------------------------------------------

class PFZToolParams(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    sector: str | None = None
    radius_km: float = Field(default=300.0, gt=0, le=2000)


class PFZRetrievalTool(BaseMarineTool):
    name = "pfz_retrieval"
    description = "Retrieve potential fishing zone advisories across operational tiers (WFS -> Text Bulletin -> Cache)."
    parameter_schema = PFZToolParams

    def __init__(self, provider: Any | None = None) -> None:
        self.provider = provider or TieredPFZProvider()

    async def execute(self, params: PFZToolParams) -> ToolExecutionResult:
        query = PFZQuery(
            location=Geometry(lat=params.lat, lon=params.lon),
            valid_at=utc_now(),
            radius_km=params.radius_km,
            sector=params.sector,
        )
        try:
            res: PFZQueryResult = await self.provider.fetch(query)
            fallback_applied = res.access_tier.value in ("text_advisory", "cached")
            evidence_quality = DataQuality.DEGRADED if fallback_applied else DataQuality.GOOD
            evidence_list = []
            for p in res.points:
                ev = Evidence(
                    source=res.source,
                    variable="pfz_point",
                    value={"pfz_id": p.pfz_id, "sector": p.sector, "landing_center": p.landing_center},
                    geometry=p.location,
                    observed_at=p.source_valid_from or utc_now(),
                    valid_from=p.source_valid_from,
                    valid_until=p.source_valid_until,
                    retrieved_at=res.retrieved_at,
                    quality=evidence_quality,
                )
                evidence_list.append(ev)

            status = ToolStatus.FALLBACK if fallback_applied else (ToolStatus.SUCCESS if res.points else ToolStatus.DEGRADED)

            return ToolExecutionResult(
                tool_name=self.name,
                status=status,
                evidence=evidence_list,
                provenance={"tier_used": res.access_tier.value, "source_id": res.source.source_id},
                quality=DataQuality.DEGRADED if fallback_applied else DataQuality.GOOD,
                fallback_applied=fallback_applied,
                metadata={"point_count": len(res.points), "sector": params.sector},
            )
        except Exception as exc:
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                errors=[f"PFZ retrieval failed: {exc}"],
                quality=DataQuality.UNRELIABLE,
            )


# ---------------------------------------------------------------------------
# 2. Sea Surface Temperature (SST) Tool
# ---------------------------------------------------------------------------

class SSTToolParams(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class SSTRetrievalTool(BaseMarineTool):
    name = "sst_retrieval"
    description = "Extract sea surface temperature (°C) via INCOIS dynamic THREDDS discovery and NetCDF slicing."
    parameter_schema = SSTToolParams

    def __init__(self, adapter: Any | None = None) -> None:
        self.adapter = adapter or INCOISSSTAdapter()

    async def execute(self, params: SSTToolParams) -> ToolExecutionResult:
        loc = Geometry(lat=params.lat, lon=params.lon)
        try:
            if hasattr(self.adapter, "resolve_endpoint"):
                await self.adapter.resolve_endpoint()
            ev = self.adapter.extract_sst(loc)
            is_degraded = getattr(ev, "quality", DataQuality.GOOD) == DataQuality.DEGRADED

            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.DEGRADED if is_degraded else ToolStatus.SUCCESS,
                evidence=[ev],
                provenance={"dataset": ev.source.dataset, "source_id": ev.source.source_id},
                quality=ev.quality,
                fallback_applied=is_degraded,
                metadata={"temperature_c": ev.value},
            )
        except Exception as exc:
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                errors=[f"SST extraction failed: {exc}"],
                quality=DataQuality.UNRELIABLE,
            )


# ---------------------------------------------------------------------------
# 3. Chlorophyll-a Concentration Tool
# ---------------------------------------------------------------------------

class ChlorophyllToolParams(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class ChlorophyllRetrievalTool(BaseMarineTool):
    name = "chlorophyll_retrieval"
    description = "Extract ocean chlorophyll-a concentration (mg/m³) via INCOIS Ocean Color rolling datasets."
    parameter_schema = ChlorophyllToolParams

    def __init__(self, adapter: Any | None = None) -> None:
        self.adapter = adapter or INCOISChlorophyllAdapter()

    async def execute(self, params: ChlorophyllToolParams) -> ToolExecutionResult:
        loc = Geometry(lat=params.lat, lon=params.lon)
        try:
            if hasattr(self.adapter, "resolve_endpoint"):
                await self.adapter.resolve_endpoint()
            ev = self.adapter.extract_chlorophyll(loc)
            is_degraded = getattr(ev, "quality", DataQuality.GOOD) == DataQuality.DEGRADED

            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.DEGRADED if is_degraded else ToolStatus.SUCCESS,
                evidence=[ev],
                provenance={"dataset": ev.source.dataset, "source_id": ev.source.source_id},
                quality=ev.quality,
                fallback_applied=is_degraded,
                metadata={"chlorophyll_mg_m3": ev.value},
            )
        except Exception as exc:
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                errors=[f"Chlorophyll extraction failed: {exc}"],
                quality=DataQuality.UNRELIABLE,
            )


# ---------------------------------------------------------------------------
# 4. NOAA Weather Forecast Tool
# ---------------------------------------------------------------------------

class WeatherToolParams(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class NOAAWeatherTool(BaseMarineTool):
    name = "noaa_weather"
    description = "Retrieve marine coastal weather, wind speed, and sea state forecasts from NOAA National Weather Service (US waters only)."
    parameter_schema = WeatherToolParams

    def __init__(self, adapter: Any | None = None) -> None:
        self.adapter = adapter or NOAAWeatherAdapter()

    def is_applicable(self, lat: float | None = None, lon: float | None = None, **kwargs: Any) -> bool:
        """NOAA National Weather Service covers US coastal & territorial waters only."""
        if lat is None or lon is None:
            return False
        return (15.0 <= lat <= 72.0) and (-175.0 <= lon <= -60.0)

    async def execute(self, params: WeatherToolParams) -> ToolExecutionResult:
        if not self.is_applicable(params.lat, params.lon):
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.OUT_OF_DOMAIN,
                errors=[f"Location ({params.lat}, {params.lon}) is out of operational domain for NOAA National Weather Service (US waters only)"],
                quality=DataQuality.UNRELIABLE,
            )
        loc = Geometry(lat=params.lat, lon=params.lon)
        try:
            ev = await self.adapter.fetch_forecast(loc)
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                evidence=[ev],
                provenance={"dataset": ev.source.dataset, "source_id": ev.source.source_id},
                quality=ev.quality,
                metadata={"forecast": ev.value},
            )
        except Exception as exc:
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                errors=[f"NOAA weather fetch failed: {exc}"],
                quality=DataQuality.UNRELIABLE,
            )


class INCOISOceanStateTool(BaseMarineTool):
    name = "incois_ocean_state"
    description = "Retrieve operational ocean state (wave height, wave period, swell, surface current, wind) from INCOIS OSF."
    parameter_schema = WeatherToolParams

    def __init__(self, adapter: Any | None = None) -> None:
        self.adapter = adapter or INCOISOceanStateForecastAdapter()

    def is_applicable(self, lat: float | None = None, lon: float | None = None, **kwargs: Any) -> bool:
        if lat is None or lon is None:
            return False
        return is_within_operational_region(lat, lon)

    async def execute(self, params: WeatherToolParams) -> ToolExecutionResult:
        if not self.is_applicable(params.lat, params.lon):
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.OUT_OF_DOMAIN,
                errors=[f"Location ({params.lat}, {params.lon}) is out of operational domain for INCOIS OSF"],
                quality=DataQuality.UNRELIABLE,
            )
        loc = Geometry(lat=params.lat, lon=params.lon)
        try:
            evs = await self.adapter.fetch_ocean_state(loc)
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                evidence=evs,
                provenance={"dataset": "INCOIS OSF", "source_id": "incois_osf_ocean_state"},
                quality=DataQuality.GOOD,
                metadata={"evidence_count": len(evs)},
            )
        except Exception as exc:
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                errors=[f"INCOIS OSF fetch failed: {exc}"],
                quality=DataQuality.UNRELIABLE,
            )


class IMDMarineWeatherTool(BaseMarineTool):
    name = "imd_marine_weather"
    description = "Retrieve official IMD fishermen warnings, coastal weather forecasts, and sea-area bulletins."
    parameter_schema = WeatherToolParams

    def __init__(self, adapter: Any | None = None) -> None:
        self.adapter = adapter or IMDMarineWeatherAdapter()

    def is_applicable(self, lat: float | None = None, lon: float | None = None, **kwargs: Any) -> bool:
        if lat is None or lon is None:
            return False
        return is_within_operational_region(lat, lon)

    async def execute(self, params: WeatherToolParams) -> ToolExecutionResult:
        if not self.is_applicable(params.lat, params.lon):
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.OUT_OF_DOMAIN,
                errors=[f"Location ({params.lat}, {params.lon}) is out of operational domain for IMD Marine"],
                quality=DataQuality.UNRELIABLE,
            )
        loc = Geometry(lat=params.lat, lon=params.lon)
        try:
            ev = await self.adapter.fetch_fishermen_warning(loc)
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                evidence=[ev],
                provenance={"dataset": "IMD Coastal Marine Bulletin", "source_id": "imd_marine_warning"},
                quality=DataQuality.GOOD,
                metadata={"warning_level": ev.value.get("warning_level") if isinstance(ev.value, dict) else None},
            )
        except Exception as exc:
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                errors=[f"IMD Marine fetch failed: {exc}"],
                quality=DataQuality.UNRELIABLE,
            )


class MarineWeatherRouterTool(BaseMarineTool):
    name = "marine_weather"
    description = "Intelligently route marine weather, ocean state (INCOIS OSF), and coastal warnings (IMD) according to geographic operational domain."
    parameter_schema = WeatherToolParams

    def __init__(
        self,
        incois_osf: Any | None = None,
        imd_adapter: Any | None = None,
        noaa_adapter: Any | None = None,
    ) -> None:
        self.incois_osf = incois_osf or INCOISOceanStateForecastAdapter()
        self.imd_adapter = imd_adapter or IMDMarineWeatherAdapter()
        self.noaa_adapter = noaa_adapter or NOAAWeatherAdapter()

    async def execute(self, params: WeatherToolParams) -> ToolExecutionResult:
        loc = Geometry(lat=params.lat, lon=params.lon)
        # 1. Indian Waters (INCOIS OSF ocean state + IMD Warnings)
        if is_within_operational_region(params.lat, params.lon):
            try:
                evidences: list[Evidence] = []
                osf_evs = await self.incois_osf.fetch_ocean_state(loc)
                evidences.extend(osf_evs)
                imd_ev = await self.imd_adapter.fetch_fishermen_warning(loc)
                evidences.append(imd_ev)

                return ToolExecutionResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    evidence=evidences,
                    provenance={"routing": "INDIAN_OPERATIONAL", "sources": ["incois_osf_ocean_state", "imd_marine_warning"]},
                    quality=DataQuality.GOOD,
                    metadata={"evidence_count": len(evidences), "lat": params.lat, "lon": params.lon},
                )
            except Exception as exc:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    errors=[f"Indian marine weather routing failed: {exc}"],
                    quality=DataQuality.UNRELIABLE,
                )

        # 2. US Waters (NOAA NWS)
        if (15.0 <= params.lat <= 72.0) and (-175.0 <= params.lon <= -60.0):
            try:
                noaa_ev = await self.noaa_adapter.fetch_forecast(loc)
                return ToolExecutionResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    evidence=[noaa_ev],
                    provenance={"routing": "US_NOAA_NWS", "source": "noaa_weather_forecast"},
                    quality=noaa_ev.quality,
                    metadata={"forecast": noaa_ev.value},
                )
            except Exception as exc:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    errors=[f"NOAA weather fetch failed: {exc}"],
                    quality=DataQuality.UNRELIABLE,
                )

        # 3. Outside active weather domains
        return ToolExecutionResult(
            tool_name=self.name,
            status=ToolStatus.OUT_OF_DOMAIN,
            errors=[f"Coordinates ({params.lat}, {params.lon}) are outside active marine weather domains (India / US)"],
            quality=DataQuality.UNRELIABLE,
        )


# ---------------------------------------------------------------------------
# 5. Copernicus Marine Physical Ocean Tool
# ---------------------------------------------------------------------------

class CopernicusToolParams(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    variable: str = "thetao"


class CopernicusMarineTool(BaseMarineTool):
    name = "copernicus_marine"
    description = "Retrieve physical ocean variables (SST, salinity, currents) from Copernicus Marine Service."
    parameter_schema = CopernicusToolParams

    def __init__(self, adapter: Any | None = None) -> None:
        self.adapter = adapter or CopernicusMarineAdapter()

    async def execute(self, params: CopernicusToolParams) -> ToolExecutionResult:
        if not self.adapter.has_credentials and not getattr(self.adapter, "endpoint_url", None):
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.SKIPPED,
                errors=["Copernicus credentials unconfigured in environment"],
                quality=DataQuality.UNRELIABLE,
            )
        loc = Geometry(lat=params.lat, lon=params.lon)
        try:
            ev = self.adapter.extract_sst(loc)
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                evidence=[ev],
                provenance={"dataset": ev.source.dataset, "source_id": ev.source.source_id},
                quality=ev.quality,
                metadata={"copernicus_val": ev.value},
            )
        except Exception as exc:
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                errors=[f"Copernicus extraction failed: {exc}"],
                quality=DataQuality.UNRELIABLE,
            )


# ---------------------------------------------------------------------------
# 6. Advisory Vector RAG Tool
# ---------------------------------------------------------------------------

class AdvisoryRAGParams(BaseModel):
    query: str
    sector: str | None = None
    language: str | None = None
    limit: int = Field(default=3, ge=1, le=10)


class AdvisoryRAGTool(BaseMarineTool):
    name = "advisory_rag"
    description = "Perform semantic similarity retrieval over regional marine advisory bulletins using pgvector."
    parameter_schema = AdvisoryRAGParams

    def __init__(self, repository: Any | None = None) -> None:
        self.repository = repository

    async def execute(self, params: AdvisoryRAGParams) -> ToolExecutionResult:
        if self.repository is None:
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.SKIPPED,
                errors=["Advisory RAG repository unconfigured"],
                quality=DataQuality.UNRELIABLE,
            )
        try:
            search_results = await self.repository.search_advisories(
                query_text=params.query,
                sector=params.sector,
                language=params.language,
                limit=params.limit,
            )
            evidences = [r.evidence for r in search_results]
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS if evidences else ToolStatus.DEGRADED,
                evidence=evidences,
                provenance={"method": "pgvector_cosine_similarity"},
                metadata={"retrieved_count": len(evidences)},
            )
        except Exception as exc:
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                errors=[f"Advisory RAG retrieval failed: {exc}"],
                quality=DataQuality.UNRELIABLE,
            )


# ---------------------------------------------------------------------------
# 7. PostGIS / Spatial Intelligence Tool
# ---------------------------------------------------------------------------

class SpatialToolParams(BaseModel):
    origin_lat: float = Field(..., ge=-90, le=90)
    origin_lon: float = Field(..., ge=-180, le=180)
    target_lat: float | None = Field(default=None, ge=-90, le=90)
    target_lon: float | None = Field(default=None, ge=-180, le=180)
    operation: str = Field(default="distance_and_bearing", description="distance_and_bearing | region_check")


class SpatialQueryTool(BaseMarineTool):
    name = "spatial_query"
    description = "Compute geodesic distances, bearings, and operational boundary checks."
    parameter_schema = SpatialToolParams

    async def execute(self, params: SpatialToolParams) -> ToolExecutionResult:
        import math
        origin = Geometry(lat=params.origin_lat, lon=params.origin_lon)
        in_operational_zone = is_within_operational_region(params.origin_lat, params.origin_lon)

        if params.target_lat is not None and params.target_lon is not None:
            # Geodesic Haversine calculation
            lat1, lon1 = math.radians(params.origin_lat), math.radians(params.origin_lon)
            lat2, lon2 = math.radians(params.target_lat), math.radians(params.target_lon)
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
            c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
            dist_km = round(6371.0 * c, 2)

            y = math.sin(dlon) * math.cos(lat2)
            x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
            bearing_deg = round((math.degrees(math.atan2(y, x)) + 360.0) % 360.0, 1)

            ev = Evidence(
                source=SourceMetadata(
                    source_id="orca_geospatial_engine",
                    organization="ORCA Core",
                    dataset="Geodesic Spherical Engine",
                    authority="official",
                    access=AccessMethod.API,
                ),
                variable="spatial_geodesic_vector",
                value={
                    "distance_km": dist_km,
                    "bearing_deg": bearing_deg,
                    "origin_in_operational_region": in_operational_zone,
                },
                geometry=origin,
                retrieved_at=utc_now(),
                quality=DataQuality.GOOD,
            )
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                evidence=[ev],
                metadata={"distance_km": dist_km, "bearing_deg": bearing_deg},
            )

        ev = Evidence(
            source=SourceMetadata(
                source_id="orca_geospatial_engine",
                organization="ORCA Core",
                dataset="Geographic Policy Boundary Engine",
                authority="official",
                access=AccessMethod.API,
            ),
            variable="geographic_boundary_check",
            value={"in_operational_region": in_operational_zone},
            geometry=origin,
            retrieved_at=utc_now(),
            quality=DataQuality.GOOD,
        )
        return ToolExecutionResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            evidence=[ev],
            metadata={"in_operational_region": in_operational_zone},
        )


# ---------------------------------------------------------------------------
# 8. Indic Translation Tool
# ---------------------------------------------------------------------------

class TranslationToolParams(BaseModel):
    text: str = Field(..., min_length=1)
    target_language: str = Field(..., min_length=2, max_length=5)
    source_language: str = "en"


class TranslationTool(BaseMarineTool):
    name = "indic_translation"
    description = "Translate marine advisories into coastal Indic languages (Malayalam, Kannada, Hindi, Tamil, Telugu)."
    parameter_schema = TranslationToolParams

    def __init__(self, service: Any | None = None) -> None:
        self.service = service or TieredTranslationService()

    async def execute(self, params: TranslationToolParams) -> ToolExecutionResult:
        req = TranslationRequest(
            text=params.text,
            source_language=params.source_language,
            target_language=params.target_language,
        )
        try:
            res = await self.service.translate(req)
            ev = Evidence(
                source=SourceMetadata(
                    source_id=res.provider,
                    organization="Bhashini / ORCA Lexicon",
                    dataset=f"NMT Translation ({params.target_language})",
                    authority="official",
                    access=AccessMethod.API,
                ),
                variable="translated_advisory_text",
                value={
                    "original_text": res.original_text,
                    "translated_text": res.translated_text,
                    "target_language": res.target_language,
                },
                retrieved_at=utc_now(),
                quality=DataQuality.DEGRADED if res.is_mock else DataQuality.GOOD,
            )
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.FALLBACK if res.is_mock else ToolStatus.SUCCESS,
                evidence=[ev],
                provenance=res.provenance,
                quality=ev.quality,
                fallback_applied=res.is_mock,
                metadata={"translated_text": res.translated_text},
            )
        except Exception as exc:
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                errors=[f"Translation failed: {exc}"],
                quality=DataQuality.UNRELIABLE,
            )


def create_default_tool_registry() -> ToolRegistry:
    """Instantiate and register all standard ORCA marine capability tools."""
    reg = ToolRegistry()
    reg.register_tool(PFZRetrievalTool())
    reg.register_tool(SSTRetrievalTool())
    reg.register_tool(ChlorophyllRetrievalTool())
    reg.register_tool(MarineWeatherRouterTool())
    reg.register_tool(INCOISOceanStateTool())
    reg.register_tool(IMDMarineWeatherTool())
    reg.register_tool(NOAAWeatherTool())
    reg.register_tool(CopernicusMarineTool())
    reg.register_tool(AdvisoryRAGTool())
    reg.register_tool(SpatialQueryTool())
    reg.register_tool(TranslationTool())
    return reg
