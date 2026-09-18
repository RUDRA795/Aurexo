# ORCA PS 26176 — Research, Architecture & Build Blueprint

Date: 2026-09-18
Status: Engineering baseline after PFZ vertical-slice hardening

## 1. Requirement baseline

Problem Statement 26176, **ORCA Marine EcOsystem Reasoning with Collaborative Agents**, asks for a conversational Agentic-AI platform that can understand natural-language marine questions, autonomously decompose them into executable tasks, coordinate specialized agents, retrieve heterogeneous satellite/ocean/weather/GIS/advisory data, perform spatial-temporal reasoning, produce explainable evidence-backed recommendations, support Indian languages and multi-turn context, raise marine-safety alerts, enforce geofences, optimize routes, and visualize results through maps/charts.

Source of truth: attached PS document supplied by the team.

## 2. Core engineering invariant

**LLMs decide WHAT TO DO. Deterministic software decides WHAT THE DATA SAYS.**

LLM responsibilities:
- language/intent interpretation
- plan generation
- tool selection
- natural-language synthesis
- clarification questions
- evidence-grounded explanation

Deterministic responsibilities:
- coordinates and validation
- distance/bearing
- spatial joins and geofences
- time-window validity
- route cost and route constraints
- numerical statistics
- unit conversions
- safety thresholds / gates
- source freshness checks
- provenance / evidence linking

An LLM must never be able to overwrite a SafetyDecision, a computed distance, or source evidence.

## 3. Target runtime

```text
Client (Web / Android)
        |
 REST + WebSocket
        |
 FastAPI BFF / Gateway
        |
 LangGraph-style stateful ORCA runtime
        |
 +-----------------------------+
 | Understand -> Plan -> Execute|
 | -> Verify -> Replan once     |
 | -> Synthesize                |
 +-----------------------------+
        |
 Data Fusion / Provenance
        |
 PostgreSQL + PostGIS + pgvector
 Redis / object storage / raster tiles
        |
 Curated source registry + controlled search
```

### Deployment philosophy

Start as **one backend process** with typed nodes/functions. Do not create 15–20 microservices. Extract a component only when it has a real scaling or isolation requirement.

## 4. Agent architecture

### Supervisor / reasoning nodes

- QueryUnderstandingNode
- PlannerNode
- DialogueManagerNode
- SynthesisNode

### Domain nodes

- PFZAgent
- OceanAgent
- WeatherAgent
- TideAgent
- CycloneAgent
- LightningAgent
- HazardAgent
- GeospatialAgent
- RouteAgent
- ResearchAgent
- VisualizationAgent

### Verification nodes

- EvidenceVerifier
- FreshnessVerifier
- TemporalVerifier
- SpatialVerifier
- CitationVerifier
- SafetyGate

### Tools

Tools are typed deterministic functions, not autonomous microservices:

```text
get_pfz
get_sst
get_chlorophyll
get_wave_forecast
get_wind
get_tide
get_cyclone_alerts
get_lightning
get_eez
get_protected_areas
calculate_distance
calculate_bearing
calculate_route
query_postgis
retrieve_raster
search_marine_sources
fetch_advisory
```

## 5. Execution loop

```text
USER QUERY
  |
  v
Language + context
  |
  v
Intent + constraints
  |
  v
PLAN / DAG
  |
  +---- parallel tool/agent branches ----+
  |                                       |
  +---------------------------------------+
                    |
                    v
              DATA NORMALIZATION
                    |
                    v
              SPATIAL/TEMPORAL FUSION
                    |
                    v
                VERIFICATION
                    |
            +-------+-------+
            |               |
         BLOCKING         PASS
            |               |
        replan once         |
            |               |
            +-------+-------+
                    |
                 SAFETY GATE
                    |
                 SYNTHESIS
                    |
       text + map + charts + sources
```

Replanning is hard-capped at one attempt in v1.

## 6. Why a graph runtime is appropriate

LangGraph documentation describes nodes as discrete steps with shared state, checkpointing, resumability, streaming and inspectable execution. Checkpointers plus a stable thread identifier allow state to persist across execution. This matches ORCA's need for explicit plan/execution state rather than hidden prompt loops.

Recommended pattern:
- one graph per ORCA request
- stable session/thread identifier
- node-level tracing
- checkpoint after material state changes
- retries at tool boundary, not arbitrary LLM self-reflection
- one explicit recovery/replan branch

## 7. Evidence contract

Every factual result should carry:

```json
{
  "source": "NOAA",
  "dataset": "OISST",
  "variable": "sst",
  "value": 28.7,
  "unit": "degC",
  "geometry": {"lat": 15.4, "lon": 73.8},
  "reference_time": "...",
  "valid_from": "...",
  "valid_until": "...",
  "retrieved_at": "...",
  "method": "point_query"
}
```

For forecasts, distinguish:
- model/reference time
- valid-from time
- valid-until time
- retrieval time

This prevents forecast-run timestamps from being confused with forecast-validity timestamps.

## 8. Source strategy

### Tier 1 — Indian/official sources

**INCOIS**
- PFZ advisory
- PFZ WebGIS
- SST / chlorophyll layers
- EEZ / landing centres / bathymetry
- Ocean State Forecast
- high-wave / swell-surge alerts
- tides
- cyclone/storm-surge-related marine services
- ecosystem services such as tuna, coral bleaching, algal bloom, jellyfish

INCOIS currently exposes a PFZ WebGIS with SST, chlorophyll, PFZ advisory, EEZ, sectors, landing centres and bathymetry layers. Its PFZ service is organized around Indian coastal sectors and landing centres, and the official text advisory contains geographic PFZ information and wind context. The public surface should be treated as WebGIS/text-advisory infrastructure unless a deployment-specific machine-readable feature endpoint has been confirmed.

**IMD**
- fishermen warnings
- coastal weather
- port warnings
- sea-area bulletins
- GMDSS / marine bulletins
- cyclone and severe-weather warnings

IMD's marine forecast page explicitly includes North Maharashtra, South Maharashtra and Goa marine areas.

**ISRO / EOS-06 (Oceansat-3)**
- OCM-3 ocean colour/chlorophyll
- scatterometer surface winds
- SST continuity products

ISRO's 10 Sep 2026 release demonstrates use of EOS-06 chlorophyll-a plus surface-wind observations for marine productivity analysis.

### Tier 2 — Global authoritative/scientific sources

**NOAA OISST**
- global daily SST analysis
- 0.25-degree product family
- SST anomalies and quality metadata

**NOAA GFS**
- global numerical weather forecast
- multiple daily cycles
- wind and atmospheric fields for environmental context

**Copernicus Marine**
- ocean state, forecasts and reanalysis
- programmatic spatial/temporal subsetting
- NetCDF/Zarr/CSV/Parquet pathways depending dataset/access method

**NASA Earthdata CMR**
- dataset discovery and collection metadata
- REST and GraphQL search interfaces
- use it as a discovery layer rather than assuming every NASA dataset has the same delivery interface

**NOAA IBTrACS**
- global tropical-cyclone best-track archive
- historical analysis / climatology
- not a substitute for current official warning bulletins

**NDBC / buoy observations**
- in-situ ocean observations where coverage exists

**Protected Planet / WDPA API**
- protected-area polygons
- API requires an access token and its current v4 API is the supported interface
- verify usage/licensing constraints before production deployment

**Marine Regions**
- World EEZ and related maritime boundaries
- useful as a static geofence base layer
- current public downloads include World EEZ v12 and 12/24 NM zones

## 9. Important source caveats

1. **INCOIS PFZ is not a generic JSON endpoint in the public surface.** Keep the adapter swappable: WebGIS feature-service/structured layer when confirmed; HTML/text advisory fallback; cached verified data as a last read-only fallback.
2. **IBTrACS is not the live safety authority.** Use current IMD/INCOIS advisories for Indian operational warnings; use IBTrACS for historical track/context.
3. **GOES GLM is not an India-wide lightning solution.** Do not use an Americas-focused lightning product as the primary Indian coastal lightning source. Add an India-appropriate official lightning feed when the production adapter is chosen.
4. **Protected Planet API has current access/licensing restrictions.** Prefer a compliant downloadable format if the project use case permits it.
5. **Public data availability is not equivalent to a blanket commercial license.** Maintain source-specific license metadata in the registry.

## 10. Source Registry shape

Each source should be registered with:

```json
{
  "source_id": "incois_pfz",
  "organization": "INCOIS",
  "domain": ["pfz", "fisheries"],
  "coverage": "indian_coast",
  "access_methods": ["webgis", "scrape"],
  "authority": "official",
  "freshness_policy_hours": 24,
  "requires_credentials": false,
  "fallbacks": ["incois_pfz_cached"],
  "license_status": "verify_dataset_terms"
}
```

## 11. PFZ vertical slice

The current PFZ slice is now contract-driven:

```text
PFZ request
  -> PFZ agent
  -> get_pfz ToolCall
  -> validity/freshness checks
  -> geospatial agent
  -> calculate_distance ToolCall
  -> radius filter
  -> rank by deterministic distance
  -> provenance/evidence
  -> verification
  -> FinalResponse + GeoJSON
```

The live INCOIS adapter remains the only deployment-specific part.

### Production geospatial implementation

Use PostGIS `ST_DWithin` for radius filtering and `ST_Distance` on `geography` for geodesic distance. `ST_DWithin` can use spatial indexes, making it preferable for candidate filtering before exact distance ordering.

Example:

```sql
SELECT
    id,
    ST_Distance(
        geom::geography,
        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
    ) / 1000.0 AS distance_km
FROM pfz_points
WHERE valid_from <= :valid_at
  AND (valid_until IS NULL OR valid_until >= :valid_at)
  AND ST_DWithin(
        geom::geography,
        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
        :radius_m
      )
ORDER BY distance_km
LIMIT :limit;
```

## 12. Full ORCA feature map

### Conversational intelligence
- automatic language detection
- Indian-language response in same language
- multi-turn context
- location and time resolution
- clarification requests for ambiguous queries
- remembered user preferences without contaminating scientific evidence

### Ocean intelligence
- SST
- chlorophyll
- significant wave height
- wave period
- swell
- surface currents
- wind
- mixed-layer depth
- marine heat waves
- bathymetry
- ocean-state forecast

### Fisheries intelligence
- PFZ lookup
- nearest PFZ
- PFZ explanation from environmental layers
- landing-centre proximity
- tuna/fishery-specific advisory hooks
- historical productivity analysis
- PFZ change/movement analysis

### Hazards
- cyclone warnings
- high-wave/swell alerts
- storm surge
- lightning
- severe weather
- tsunami/earthquake warning integration where available
- marine heat-wave / ecosystem alerts

### Geospatial safety
- EEZ
- territorial sea / 12 NM
- contiguous zone / 24 NM
- protected areas
- restricted operational zones
- ports / landing centres
- geofence crossing alerts
- point-in-polygon
- nearest feature
- buffer / proximity warning

### Decision support
- safe/unsafe-style risk state, not an unconstrained LLM judgment
- route alternatives
- route hazard cost
- ETA / distance
- what-if comparison
- explainable evidence panel
- uncertainty / conflict display

### Visualization
- interactive map
- PFZ layers
- SST/chlorophyll raster overlays
- cyclone tracks
- warning polygons
- vessel route
- geofences
- tide/SST/wave charts
- agent execution timeline
- source/evidence drawer

### Voice
- ASR
- language detection
- translation
- TTS
- domain glossary protection

## 13. Safety architecture

Never ask the LLM to decide marine operational safety directly.

```text
Official warnings
Forecasts
Observed conditions
Geofences
Freshness
Data completeness
      |
      v
Deterministic Safety Engine
      |
 SAFE / CAUTION / HIGH_RISK / UNKNOWN
      |
      v
LLM explanation only
```

Hard invariants:
- UNKNOWN does not become SAFE
- HIGH_RISK cannot permit route recommendations
- stale/missing critical data can force UNKNOWN
- official warnings can escalate the state
- user-facing output explicitly distinguishes ORCA analysis from official clearance

## 14. Route optimization

V1:

```text
candidate route graph
  + distance
  + wave penalty
  + wind penalty
  + hazard penalty
  + geofence penalty
  -> deterministic cost
  -> permitted minimum-cost route
```

V2:
- currents
- vessel class
- fuel
- engine characteristics
- sea-state limits
- weather uncertainty
- ETA / tide windows

## 15. Agentic safety and reliability controls

Every tool needs:
- typed request schema
- timeout
- bounded retry policy
- idempotency expectation
- source metadata
- structured output
- evidence IDs
- status
- duration

Every workflow needs:
- explicit plan
- bounded replan
- state persistence
- deterministic failure semantics
- graceful degradation
- trace ID/session ID

Web content is untrusted input. Never allow retrieved web content to redefine tool permissions, safety rules or system instructions.

## 16. Research agent behavior

The open-world research tool should be a **controlled fallback**, not the primary source for operational safety.

Research agent stages:
1. formulate search query
2. search trusted source domains first
3. collect candidate documents/datasets
4. extract claims
5. attach source URLs and timestamps
6. classify source authority
7. pass evidence to verifier
8. synthesize only verified claims

For operational marine warnings, official Indian sources should outrank generic web search.

## 17. Multilingual architecture

Recommended:

```text
Audio/text
  -> language detection
  -> preserve coordinates/numbers/units/domain terms
  -> translate to canonical internal language if needed
  -> ORCA reasoning
  -> translate response
  -> TTS
```

BHASHINI can supply government multilingual AI services for speech-to-text, translation, transliteration and text-to-speech, subject to current API onboarding/keys. IndicTrans2 is a useful self-hosted translation fallback covering Indian scheduled languages.

Do not translate scientific symbols such as `SST`, `SWH`, units or coordinates into free-form text tokens that could change semantics.

## 18. Web application architecture

Recommended:
- React + TypeScript
- MapLibre GL JS
- Three.js for the cinematic ocean/aircraft layers
- GSAP or CSS animations
- WebSocket for streamed agent progress
- worker/service separation for heavy geospatial processing

MapLibre GL JS uses WebGL and exposes custom layers, including 3D layers; the official examples show Three.js 3D models integrated through custom layers.

### Visual composition

```text
Sky / atmosphere
   |
surveillance aircraft / camera
   |
horizon
   |
shader-based ocean
   |
MapLibre operational layer
   |
glassmorphism panels
   |
ORCA chat / alerts / mission console
```

Do not block the render loop on API or LLM work.

## 19. Android architecture

Recommended:
- Kotlin
- Jetpack Compose
- MapLibre Native Android
- WebSocket client
- Room/local cache for recent mission state
- WorkManager for background refresh
- lightweight GPU effects

The Android app should share API schemas/design tokens with web but use native rendering instead of embedding the entire Three.js scene in a WebView.

## 20. Performance strategy

### Web
- keep animation at a controlled 30/60 FPS budget
- don't recompute full geospatial layers on every frame
- rasterize expensive backgrounds when not interactive
- lazy-load heavy 3D assets
- reduce blur/particles under GPU pressure
- use workers for large raster processing

### Android
- avoid expensive recomposition
- use release builds with R8
- use Baseline Profiles
- degrade blur effects on older devices
- cache tiles and recent queries
- keep background refresh bounded

## 21. Observability

Use OpenTelemetry for:
- request trace
- LLM generation span
- tool call span
- external API span
- database query span
- geospatial computation span
- verification span
- final synthesis span

Store correlation:

```text
session_id
trace_id
plan_id
step_id
tool_call_id
evidence_ids
```

This makes the ORCA live trace panel possible and allows post-hoc auditing.

## 22. Evaluation framework

### Agentic correctness
- intent classification accuracy
- plan validity rate
- tool-selection accuracy
- unnecessary-tool rate
- one-replan recovery rate
- workflow completion rate

### Retrieval
- source precision
- evidence coverage
- freshness accuracy
- citation correctness
- missing-data honesty

### Geospatial
- distance error versus PostGIS reference
- nearest-feature accuracy
- geofence boundary correctness
- coordinate transformation error

### Temporal
- timezone correctness
- forecast validity correctness
- stale-data rejection
- observation-vs-forecast distinction

### Safety
- safety false-negative rate: critical metric
- unsafe route recommendation rate: target zero in tested invariants
- official-warning override failures: target zero
- UNKNOWN default-to-SAFE failures: target zero

### System
- p50/p95 latency
- tool timeout recovery
- external-source outage handling
- WebSocket stability
- mobile frame-time / jank
- memory footprint

### Multilingual
- intent accuracy by language
- translation adequacy
- numeric/unit preservation
- domain terminology preservation
- ASR word-error rate for marine vocabulary

## 23. Adversarial test suite

1. LLM supplies a fake distance; deterministic distance must win.
2. LLM attempts to set HIGH_RISK -> route allowed; SafetyDecision must reject the path.
3. Expired PFZ is returned from source; verification must reject it for current time.
4. Primary source times out; exactly one fallback is attempted.
5. All sources fail; ORCA reports inability instead of guessing.
6. Two sources disagree; ORCA reports the spread and source metadata instead of inventing consensus.
7. Web page contains prompt injection; retrieved content cannot change tool permissions.
8. User asks safety question without location; ORCA asks for/derives location before claiming local conditions.
9. User supplies a naive datetime; request rejected/normalized only when timezone is explicit.
10. Route intersects protected/restricted polygon; safety/routing layer blocks the route.
11. Current official warning exists while model forecast looks benign; official warning must be represented in the safety state.
12. Unknown or stale critical fields; final state becomes UNKNOWN or otherwise conservative.

## 24. Differentiation from existing INCOIS services

INCOIS already exposes many marine services, including PFZ, forecasts, multi-hazard advisories and ecosystem products. ORCA's differentiator should therefore **not** be another dashboard that simply displays those products.

ORCA's differentiated capability is:

```text
Natural-language question
        -> autonomous task graph
        -> cross-service retrieval
        -> spatial/temporal reasoning
        -> evidence fusion
        -> deterministic safety gate
        -> explainable answer
        -> map/chart/voice result
```

## 25. Build sequence

### Stage 0 — Contract
- hardened Pydantic v2 models
- invariant tests
- typed status model
- evidence schema
- source metadata

### Stage 1 — PFZ slice
- real INCOIS adapter
- PFZ normalization
- deterministic distance
- GeoJSON response
- evidence/verification

### Stage 2 — Ocean context
- SST
- chlorophyll
- bathymetry
- wind
- PFZ explanation

### Stage 3 — Safety
- INCOIS OSF
- IMD marine warnings
- wave/swell
- cyclone
- lightning adapter
- deterministic SafetyEngine

### Stage 4 — Geospatial
- EEZ
- territorial waters
- protected areas
- restricted polygons
- route solver

### Stage 5 — Research agent
- controlled web/dataset discovery
- source ranking
- evidence extraction
- citation/provenance

### Stage 6 — UI
- operational map
- glass UI
- ocean background
- aircraft / surveillance animation
- trace panel
- evidence drawer

### Stage 7 — Android
- native Compose mission UI
- offline/cache mode
- voice
- alerts

### Stage 8 — Hardening
- observability
- load tests
- adversarial tests
- mobile profiling
- failure injection
- source outage simulation

## 26. What must be live versus simulated in a hackathon

### Must be live
- one real INCOIS PFZ path
- one real SST/chlorophyll path
- one real Indian marine-warning path
- deterministic PostGIS or equivalent reference computation
- actual agent/tool execution trace
- evidence/provenance

### Can be simulated initially
- aircraft animation telemetry
- non-essential 3D effects
- historical route playback
- some global source adapters not available under demo credentials
- synthetic adverse-source outages for resilience demonstration

Never label simulated environmental observations as live observations.

## 27. Current engineering status

The local PFZ/contract implementation now passes **25 tests** after hardening.

Included:
- safety computed fields
- forbidden extra fields
- timezone-aware datetimes
- plan DAG validation
- separate tool status
- explicit forecast validity timestamps
- evidence-required factual results
- bounded replanning
- NO_DATA vs FAILED
- PFZ radius filtering
- sector filtering
- separate geospatial agent
- deterministic distance tool trace
- GeoJSON output
- provenance tests

Remaining deployment-specific work:
- connect `INCOISPFZAdapter` to the live WebGIS/structured layer or text parser discovered in the target environment
- replace haversine fallback with production PostGIS implementation
- add real credentials/API adapters where required

## 28. Recommended first production tool registry

```text
TOOL                  CLASS                  LIVE FIRST?
---------------------------------------------------------
get_pfz               source adapter         YES
get_sst               source adapter         YES
get_chlorophyll       source adapter         YES
get_wave_forecast     marine forecast        YES
get_wind              marine forecast        YES
get_cyclone_alerts    official warnings      YES
get_tide              marine forecast        YES
get_lightning         regional source        YES
get_eez               PostGIS                YES
get_protected_areas   PostGIS                YES
calculate_distance    PostGIS                YES
calculate_bearing     geometry               YES
calculate_route       deterministic solver   YES
query_postgis         controlled repository  YES
retrieve_raster       raster service         LATER
search_marine_sources research agent         LATER
fetch_advisory        official bulletin       YES
```

## 29. Final architecture decision

The winning implementation pattern for ORCA is not "many LLMs talking to each other".

It is:

**one stateful supervisor + typed domain nodes + deterministic tools + a source registry + explicit verification + a hard safety gate + streamed evidence-backed visualization.**

That architecture gives the team a credible agentic system while keeping the codebase small enough to debug under hackathon conditions.
