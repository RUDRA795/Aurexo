# ORCA — Marine EcOsystem Reasoning with Collaborative Agents

ISRO Problem Statement 26176 implementation workspace.

## System Verification Status (Source of Truth)

In compliance with the **ORCA Engineering Integrity Protocol**, system capabilities are strictly partitioned by their verification level:

### 1. VERIFIED (Real Infrastructure / Live Source Tested)
* **PostGIS 17 Geography Engine**: Native spherical distance queries via `ST_Distance(geography, geography)` verified on live PostgreSQL 17 + PostGIS 3.5 container.
* **pgvector Embeddings**: High-dimensional advisory similarity search via HNSW vector indexing (`vector_cosine_ops`) verified on live PostgreSQL 17.
* **PostgreSQL Persistent Repositories**: Idempotent upsert, spatial proximity querying, and tiered cache fallback verified against database.
* **Live INCOIS GeoServer WFS**: Real-source verified via opt-in suite (`ORCA_LIVE_SMOKE=1 pytest backend/tests/live/test_incois_live_wfs.py`). Confirmed HTTP 200, valid TLS certificate (`verify=True`), GeoJSON schema, `MultiLineString` geometries, and property metadata.
* **Live INCOIS THREDDS Catalog Discovery**: Real-source verified dynamic discovery of operational SST and Chlorophyll rolling NetCDF datasets from `https://incois.gov.in/thredds/catalog/osf/`. Implemented as standalone discovery seam in `discovery.py` (not yet automatically injected into base adapters).
* **ORCA Agent Contract v2**: Deterministic Pydantic v2 boundary enforcement, timestamp timezone awareness, and invariant checks.

### 2. TESTED WITH MOCK / FIXTURE
* **INCOIS WFS Parsing & Normalization**: GeoJSON extraction, deduplication, Julian Day date calculation, and representative midpoint interpolation.
* **INCOIS Text Advisory Parser**: Multilingual bulletin regex parsing, landing center coordinates, and planar bearing offset projections.
* **SST & Chlorophyll Extraction**: xarray/NetCDF grid point extraction, Kelvin-to-Celsius conversion, and land-mask offshore probing (tested on synthetic datasets).
* **Tiered Failover Controller**: Deterministic fallback path (`WEBGIS_LAYER` → `TEXT_ADVISORY` → `CACHED` → `UNAVAILABLE`).

### 3. BLOCKED (When Prerequisites Missing)
* **Database & Vector Tests**: Require active PostGIS 17 container (`docker compose up -d`). If Docker Desktop is stopped, these tests fail with `ConnectionRefusedError`.

### 4. NOT IMPLEMENTED
* **Maritime Safety Engine**: Hazard threshold classification, route corridors, geofence violations (`backend/orca/safety/` is currently empty).
* **WebGL Procedural Ocean & Aircraft Scene**: Real-time GLSL ocean shaders and 3D aircraft model in Three.js (`rendering/` directories are currently empty). Proxy videos/GIFs are prohibited.
* **Web Frontend Dependencies**: Node modules are not installed (`apps/web/node_modules` missing).
* **Additional Environmental Feeds**: IMD radar, ECMWF/NOAA wind and wave forecasts, lightning strikes, and Indian EEZ boundary layers.

### 5. NOT VERIFIED
* **Operational OpenDAP Slicing Performance**: While remote OpenDAP array slicing was verified live, long-term network retry and latency benchmarking under degraded field conditions have not been measured.

---

## Architecture Rule

> **LLM decides WHAT TO DO. Deterministic code decides WHAT THE DATA SAYS.**

LLMs may interpret natural language, plan task sequences, select tools, and explain verified findings.
Deterministic software strictly calculates coordinates, distances, bearings, scientific unit conversions, data provenance, and safety decisions.

---

## Running Infrastructure & Tests

### 1. Start Infrastructure
```bash
docker compose up -d
docker compose ps
```

### 2. Standard CI Test Suite (Deterministic / Fast)
```bash
cd backend
.\.venv\Scripts\Activate.ps1
pytest -v
```
*(Standard CI skips live network calls to protect external servers and ensure reproducible runs).*

### 3. Real-Source Live Smoke Suite (Opt-in)
To verify live external connections to Indian Government marine servers (INCOIS):
```bash
$env:ORCA_LIVE_SMOKE="1"
pytest backend/tests/live/ -v
$env:ORCA_LIVE_SMOKE=""
```

