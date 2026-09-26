# ORCA Core Architecture & Engineering Integrity Rules

These rules apply across the entire ORCA codebase for all agents and automated processes.

## 1. Golden Law
> **LLM decides WHAT TO DO. Deterministic code decides WHAT THE DATA SAYS.**

- LLMs may parse user intent, generate task plans, choose tool sequences, and summarize verified findings.
- LLMs MUST NEVER calculate coordinates, calculate maritime distances, convert units, invent spatial bearings, or fabricate environmental values.
- All spatial math, scientific unit conversions (e.g., Kelvin to Celsius), data provenance tracking, and hazard classifications are computed exclusively by deterministic Python/PostGIS code.

## 2. Spatial & Database Invariants
- **Coordinate System**: All coordinates are strictly WGS 84 (EPSG:4326) formatted as `(longitude, latitude)`.
- **Spherical Calculation**: Distances must always be calculated using PostGIS native spherical geography methods (`ST_Distance(geography, geography)`), never Euclidean planar distance formulas on degrees.
- **HNSW Vector Search**: High-dimensional advisory similarity uses `pgvector` with `vector_cosine_ops`.
- **Failover Ladder**: Environmental feeds must follow the deterministic fallback sequence:
  `WEBGIS_LAYER` → `TEXT_ADVISORY` → `CACHED` → `UNAVAILABLE`.

## 3. Rendering & 3D Integrity
- **No Video Proxies**: For ocean and aircraft rendering, proxy videos, mock GIFs, and static placeholders are strictly prohibited.
- **WebGL & Shaders**: Visual simulation must use procedural GLSL shaders in Three.js and real glTF 3D models.

## 4. API & Data Contracts
- All external inputs and system boundaries must be validated with Pydantic v2.
- Timestamps must be timezone-aware UTC (`datetime.now(timezone.utc)`).
