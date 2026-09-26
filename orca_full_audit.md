# ORCA — Full System & Antigravity Workstation Audit
**Generated**: 2026-09-22 | **Workspace**: `d:\ORCA` | **Corpus**: `RUDRA795/Aurexo`

---

## Table of Contents
1. [Antigravity IDE Setup](#1-antigravity-ide-setup)
2. [Workspace Customizations (.agents/)](#2-workspace-customizations-agents)
3. [ORCA Project Overview](#3-orca-project-overview)
4. [Backend — Python Stack](#4-backend--python-stack)
5. [Frontend — React/Vite/TypeScript Stack](#5-frontend--reactvitetypescript-stack)
6. [Rendering — WebGL / 3D Layer](#6-rendering--webgl--3d-layer)
7. [Infrastructure — Docker, Database, Redis, MinIO](#7-infrastructure--docker-database-redis-minio)
8. [Test Suite](#8-test-suite)
9. [Status Matrix (All Modules)](#9-status-matrix-all-modules)
10. [What Is Missing / Action Plan](#10-what-is-missing--action-plan)

---

## 1. Antigravity IDE Setup

### 1.1 Workspace Extensions — `.vscode/extensions.json`

> **Note**: The file currently contains the **old list** (30 extensions from Session 1), **not** the pruned list from Session 2. This is a discrepancy to fix.

| # | Extension ID | Category | Status | ORCA Relevance |
|---|---|---|---|---|
| 1 | `hansring.lottie-preview` | 3D/Media | ✅ Current | Lottie animation preview |
| 2 | `circlon.media-preview` | 3D/Media | ✅ Current | Video/audio/image preview |
| 3 | `simonsiefke.svg-preview` | 3D/Media | ✅ Current | SVG preview for UI icons |
| 4 | `cesium.gltf-vscode` | 3D/Media | ✅ Current | **Critical** — glTF aircraft model inspection |
| 5 | `slevesque.shader` | 3D/Media | ✅ Current | **Critical** — GLSL shader syntax for ocean shaders |
| 6 | `bradlc.vscode-tailwindcss` | Frontend | ✅ Current | Not used (no Tailwind in project yet) |
| 7 | `dsznajder.es7-react-js-snippets` | Frontend | ✅ Current | React component scaffolding |
| 8 | `formulahendry.auto-rename-tag` | Frontend | ✅ Current | JSX/HTML tag editing |
| 9 | `formulahendry.auto-close-tag` | Frontend | ✅ Current | JSX tag auto-close |
| 10 | `figma.figma-vscode` | Frontend | ⚠️ Requires paid seat | Design token extraction |
| 11 | `usernamehw.errorlens` | Productivity | ✅ Current | **Must-have** — inline diagnostics |
| 12 | `esbenp.prettier-vscode` | Productivity | ✅ Current | Code formatting |
| 13 | `christian-kohler.path-intellisense` | Productivity | ✅ Current | Import path autocomplete |
| 14 | `ChakrounAnas.turbo-console-log` | Productivity | ✅ Current | Quick console.log insertion |
| 15 | `mattpocock.ts-error-translator` | Productivity | ✅ Current | Human-readable TS errors |
| 16 | `streetsidesoftware.code-spell-checker` | Productivity | ✅ Current | Spelling in variable names |
| 17 | `eamodio.gitlens` | Git | ✅ Current | Line-by-line blame, worktrees |
| 18 | `mhutchie.git-graph` | Git | ⚠️ Optional | Overlap with GitLens |
| 19 | `Gruntfuggly.todo-tree` | Navigation | ✅ Current | TODO/FIXME scanning |
| 20 | `alefragnani.project-manager` | Navigation | ⚠️ Optional | Lower value with AGY 2.0 |
| 21 | `rangav.vscode-thunder-client` | Backend | ⚠️ Duplicates REST Client | Remove — keep `humao.rest-client` |
| 22 | `humao.rest-client` | Backend | ✅ Current | `.http` files in repo |
| 23 | `Prisma.prisma` | Backend | ⚠️ Not in use | No Prisma ORM in backend |
| 24 | `ms-azuretools.vscode-docker` | Infrastructure | ✅ Current | Docker container management |
| 25 | `cweijan.vscode-database-client2` | Backend | ✅ Current | PostgreSQL/Redis inspection |
| 26 | `PKief.material-icon-theme` | Aesthetics | ✅ Current | Icon theme |
| 27 | `enkia.tokyo-night` | Aesthetics | ⚠️ Optional | Pick one theme |
| 28 | `Catppuccin.catppuccin-vsc` | Aesthetics | ⚠️ Optional | Pick one theme |
| 29 | `johnpapa.vscode-peacock` | Aesthetics | ⚠️ Optional | Frame color per project |

> [!WARNING]
> **The `.vscode/extensions.json` was updated in Session 2 (Phase 2) but the file on disk still contains the OLD 29-extension list including `figma`, `git-graph`, `project-manager`, `thunder-client`, `Prisma`, multiple themes, and `peacock`.** The Phase 2 file (with `ms-python.python`, `charliermarsh.ruff`, `ms-playwright.playwright`, etc.) needs to be confirmed and rewritten.

**Missing from current file (recommended additions):**

| Extension ID | Why It Matters for ORCA |
|---|---|
| `ms-python.python` | Python backend IntelliSense |
| `ms-python.vscode-pylance` | Pydantic v2, FastAPI type inference |
| `charliermarsh.ruff` | Ruff linter (already in requirements) |
| `ms-toolsai.jupyter` | Scientific verification notebooks |
| `dbaeumer.vscode-eslint` | ESLint for frontend TypeScript |
| `ms-playwright.playwright` | Playwright test runner integration |
| `GitHub.vscode-pull-request-github` | GitHub PR + issue sidebar |
| `redhat.vscode-yaml` | YAML for docker-compose, configs |

---

### 1.2 Antigravity IDE — Loaded MCP Servers (Global Built-in)

These are already configured by the Antigravity IDE global install:

| MCP Server | Transport | Status | Purpose |
|---|---|---|---|
| `data-agent-kit` | Lazy | ✅ Available | GCP data editor context, resource templates |
| `github` | Lazy | ✅ Available | Repository, issues, PRs, commits |
| `memory` | Lazy | ✅ Available | Knowledge-graph persistent memory |
| `notebooks` | Lazy | ✅ Available | Jupyter notebook manipulation |
| `playwright` | Lazy | ✅ Available | Browser automation and testing |
| `sequential-thinking` | Lazy | ✅ Available | Structured multi-step reasoning |
| `visualization` | Lazy | ✅ Available | Chart rendering |

> [!NOTE]
> The global IDE already ships with `playwright`, `github`, `memory`, and `sequential-thinking`. The workspace `.agents/mcp_config.json` **adds workspace-scoped versions** of the same servers, which will be loaded with ORCA-specific arguments.

---

### 1.3 Antigravity IDE — Loaded Global Skills (Built-in)

Skills available globally across all workspaces (from `C:\Users\hp\.gemini\antigravity-ide\builtin\skills\`):

| Skill Name | Status | ORCA Relevance |
|---|---|---|
| `antigravity-guide` | ✅ Always available | Reference for IDE/AGY features |
| `agy-customizations` | ✅ Always available | Plugin/skill/rule authoring |
| `orca-postgis-spatial` | ✅ Workspace-scoped | **Project-specific — PostGIS** |
| `orca-webgl-shaders` | ✅ Workspace-scoped | **Project-specific — GLSL/Three.js** |
| `accidental-data-loss-prevention` | ✅ Global | Safety gate before destructive commands |
| `managing-python-dependencies` | ✅ Global | venv enforcement |
| `ml-best-practices` | ✅ Global | ML code quality |
| `notebook-guidance` | ✅ Global | Jupyter best practices |

---

## 2. Workspace Customizations (.agents/)

### 2.1 Directory Tree

```
d:\ORCA\
├── AGENTS.md                          ✅ Root Prime Directive (Prime Law)
├── .vscode/
│   └── extensions.json                ⚠️ Contains OLD list — needs update
└── .agents/
    ├── mcp_config.json                ✅ 5 workspace-scoped MCP servers
    ├── rules/
    │   ├── architecture.md            ✅ Spatial, failover, rendering rules
    │   └── verification.md            ✅ 5-tier verification protocol
    └── skills/
        ├── orca-postgis-spatial/
        │   └── SKILL.md               ✅ PostGIS 17, ST_Distance, pgvector HNSW
        └── orca-webgl-shaders/
            └── SKILL.md               ✅ Gerstner waves, Fresnel, glTF loading
```

**Missing from `.agents/`:**

| Component | Gap | Priority |
|---|---|---|
| `.agents/plugins/` | No plugin bundle created yet | Medium |
| `.agents/hooks.json` | No lifecycle hooks defined | Low |
| Skills: `orca-langgraph` | No skill for LangGraph agent graph authoring | High |
| Skills: `orca-incois-feeds` | No skill for INCOIS WFS/THREDDS/NetCDF patterns | High |
| Skills: `orca-fastapi-api` | No skill for FastAPI endpoint patterns | Medium |
| Skills: `orca-testing` | No skill for pytest/Playwright test authoring | Medium |
| Rules: `coding-standards.md` | Python/TS formatting, naming rules | Medium |
| Rules: `security.md` | SSRF, geographic policy, sanitizer usage | Medium |

---

### 2.2 Root `AGENTS.md`

| Field | Value |
|---|---|
| Location | `d:\ORCA\AGENTS.md` |
| Scope | All agents operating in this workspace |
| Prime Directive | LLM = orchestrator / Deterministic code = spatial truth |
| Tech Stack defined | ✅ Python 3.11+, FastAPI, Pydantic v2, PostgreSQL 17/PostGIS 3.5, pgvector, Vite/React/TS, MapLibre GL, Three.js, GLSL, Pytest, Playwright |
| References to rules | ✅ Links `architecture.md`, `verification.md`, `mcp_config.json`, both skills |

---

### 2.3 Workspace MCP Config — `.agents/mcp_config.json`

| Server | Command | Purpose | Activation |
|---|---|---|---|
| `playwright` | `npx -y @playwright/mcp@latest` | Browser automation, UI testing, network inspection | Auto on agent invocation |
| `github` | `npx -y @modelcontextprotocol/server-github` | Issues, PRs, commits, branch navigation | Requires `GITHUB_TOKEN` env var |
| `memory` | `npx -y @modelcontextprotocol/server-memory` | Knowledge-graph across turns | Auto |
| `sequential-thinking` | `npx -y @modelcontextprotocol/server-sequential-thinking` | Structured multi-step problem solving | Auto |
| `context7` | `npx -y @upstash/context7@latest` | Current library docs (FastAPI, Three.js, React, PostGIS) | Auto |

> [!IMPORTANT]
> `GITHUB_TOKEN` must be set in your environment for the GitHub MCP server to authenticate. Add it to a `.env` file or shell profile: `$env:GITHUB_TOKEN = "ghp_..."`.

---

### 2.4 Rules — `.agents/rules/`

#### `architecture.md`
- ✅ Golden Law enforced (LLM ≠ spatial calculator)
- ✅ WGS 84 EPSG:4326 coordinate mandate
- ✅ `ST_Distance(geography, geography)` — no Euclidean fallback
- ✅ `pgvector` HNSW cosine similarity mandated
- ✅ Failover ladder: `WEBGIS_LAYER → TEXT_ADVISORY → CACHED → UNAVAILABLE`
- ✅ No video proxy / GIF rule for WebGL rendering
- ✅ Pydantic v2 boundary enforcement
- ✅ UTC-aware timestamps

#### `verification.md`
- ✅ 5 verification tiers defined (VERIFIED / MOCKED / BLOCKED / NOT IMPLEMENTED / NOT VERIFIED)
- ✅ CI command documented (`cd backend && pytest -v`)
- ✅ E2E Playwright command documented

---

### 2.5 Skills — `.agents/skills/`

#### `orca-postgis-spatial` ✅
- Geography column types (`geography(Point, 4326)`)
- `ST_Distance` spherical formulation
- `ST_DWithin` proximity queries
- GiST spatial index creation pattern
- pgvector HNSW index creation
- Cosine similarity neighbor query template
- Docker container verification command

#### `orca-webgl-shaders` ✅
- No-proxy mandate
- Gerstner wave vertex shader description
- Fresnel fragment shader description
- PBR specular highlights
- `GLTFLoader` + `DRACOLoader` loading pattern
- Aircraft attitude update pattern
- Memory disposal on unmount

---

## 3. ORCA Project Overview

| Field | Value |
|---|---|
| Problem Statement | ISRO Problem Statement 26176 |
| Domain | Marine EcOsystem Reasoning with Collaborative Agents |
| Root | `d:\ORCA\` |
| GitHub | `RUDRA795/Aurexo` |
| Architecture Pattern | Multi-agent LangGraph orchestration + deterministic data layer |

### 3.1 Top-Level Directory Map

```
d:\ORCA\
├── AGENTS.md            Root Antigravity prime directive
├── README.md            Verification status reference (authoritative)
├── docker-compose.yml   Infrastructure definition (PostgreSQL, Redis, MinIO)
├── openapi.json         FastAPI OpenAPI schema
├── .gitignore
├── .vscode/             IDE configuration
├── .agents/             Antigravity agent customizations
├── apps/
│   └── web/             Vite + React + TypeScript frontend
├── backend/             FastAPI + Python backend
├── database/            SQL bootstrap scripts
├── docs/                Project documentation
├── infra/               Docker build infrastructure
├── landing/             Marketing/landing page (separate from app)
├── rendering/           WebGL shader prototypes (currently empty)
└── scripts/             Dev utility scripts
```

---

## 4. Backend — Python Stack

### 4.1 Tech Stack

| Dependency | Version | Role |
|---|---|---|
| FastAPI | ≥0.128,<1 | HTTP framework + SSE streaming |
| Uvicorn[standard] | ≥0.40,<1 | ASGI server |
| Pydantic | ≥2.13,<3 | Data contracts & validation (v2) |
| httpx | ≥0.28,<1 | Async HTTP client for external APIs |
| LangGraph | ≥1,<2 | Multi-agent graph orchestration |
| SQLAlchemy | ≥2.0,<3 | ORM (async) |
| asyncpg | ≥0.30,<1 | PostgreSQL async driver |
| GeoAlchemy2 | ≥0.18,<1 | PostGIS geography type mapping |
| pgvector | ≥0.3.6,<1 | Vector similarity (Python) |
| Alembic | ≥1.14,<2 | Schema migrations |
| Redis | ≥6,<8 | Cache / pub-sub event broker |
| NumPy | ≥2,<3 | Numerical arrays |
| SciPy | ≥1.15,<2 | Scientific computations |
| Pandas | ≥2.2,<3 | Tabular data |
| xarray | ≥2025,<2027 | NetCDF multi-dimensional arrays |
| GeoPandas | ≥1.1,<2 | Geospatial DataFrame operations |
| Shapely | ≥2.1,<3 | Vector geometry operations |
| pyproj | ≥3.7,<4 | Coordinate reference system transforms |
| rasterio | ≥1.4,<2 | Raster data I/O |
| rioxarray | ≥0.18,<1 | xarray + rasterio integration |
| NetCDF4 | ≥1.7,<2 | NetCDF I/O |
| opentelemetry-api/sdk | ≥1.37,<2 | Distributed tracing |
| pytest | ≥9,<10 | Test framework |
| pytest-asyncio | ≥1.3,<2 | Async test support |

---

### 4.2 Backend Module Breakdown — `backend/orca/`

#### `agents/` — LangGraph Multi-Agent Core
| File | Size | Status | Description |
|---|---|---|---|
| `graph.py` | 39 KB | ✅ Implemented | LangGraph StateGraph node/edge definitions |
| `runtime.py` | 37 KB | ✅ Implemented | Main agent execution runtime, gazetteer, tool invocation |
| `pfz_pipeline.py` | 25 KB | ✅ Implemented | Potential Fishing Zone agent pipeline |
| `persistence.py` | 14 KB | ✅ Implemented | Agent run state persistence |
| `state.py` | 3.5 KB | ✅ Implemented | Agent state schema |
| `pfz.py` | 28 B | ⚠️ Stub | Empty placeholder |

> [!NOTE]
> `runtime.py` includes a hardcoded deterministic Coastal Gazetteer for Indian ports (`MUMBAI`, etc.) and strictly enforces no LLM coordinate calculation — this is the Prime Directive in code.

#### `api/` — FastAPI HTTP Layer
| File | Status | Description |
|---|---|---|
| `main.py` | ✅ Implemented | FastAPI app factory, router registration |
| `events.py` | ✅ Implemented | SSE event stream endpoints |
| `streaming.py` | ✅ Implemented | Async streaming runner wiring |

#### `data/` — Environmental Data Adapters
| Adapter | Size | Status | Data Source |
|---|---|---|---|
| `incois_pfz.py` | 9.2 KB | ✅ Implemented | INCOIS GeoServer WFS Potential Fishing Zones |
| `incois_sst.py` | 10 KB | ✅ Implemented | INCOIS THREDDS Sea Surface Temperature |
| `incois_chlorophyll.py` | 8.3 KB | ✅ Implemented | INCOIS Chlorophyll concentration |
| `incois_text_advisory.py` | 8.3 KB | ✅ Implemented | INCOIS text bulletin parser |
| `incois_osf_weather.py` | 10.4 KB | ✅ Implemented | INCOIS OSF weather data |
| `copernicus_marine.py` | 9.1 KB | ✅ Implemented | Copernicus Marine Service |
| `noaa_weather.py` | 8.4 KB | ✅ Implemented | NOAA weather data |
| `cached_pfz.py` | 2.4 KB | ✅ Implemented | Cache fallback adapter |
| `base.py` | 2 KB | ✅ Implemented | Adapter abstract base class |
| `discovery.py` | 7.2 KB | ✅ Implemented | THREDDS catalog dynamic discovery seam |
| `registry.py` | 3.3 KB | ✅ Implemented | Adapter registry |

#### `database/` — PostgreSQL / PostGIS / pgvector
| Component | Status | Description |
|---|---|---|
| `models/advisory.py` | ✅ Implemented | Marine advisory SQLAlchemy model + PostGIS geometry |
| `models/pfz.py` | ✅ Implemented | PFZ SQLAlchemy model |
| `models/event_journal.py` | ✅ Implemented | Agent run event log model |
| `repositories/advisory_rag.py` | ✅ Implemented (38 KB) | Full hybrid RAG repository — PostGIS + pgvector |
| `repositories/event_journal_repo.py` | ✅ Implemented (14 KB) | Event journal queries |
| `repositories/pfz_repository.py` | ✅ Implemented | PFZ spatial queries |
| `session.py` | ✅ Implemented | Async SQLAlchemy engine factory |

#### `embeddings/` — Embedding Engine
| File | Status | Description |
|---|---|---|
| `bge_m3.py` | ✅ Implemented | BGE-M3 multilingual embedding model |
| `mock.py` | ✅ Implemented | Mock embedder for CI |
| `base.py` | ✅ Implemented | Abstract embedder interface |

#### `rag/` — Retrieval-Augmented Generation
| File | Status | Description |
|---|---|---|
| `chunking.py` | ✅ Implemented | Document chunking strategies |
| `reranker.py` | ✅ Implemented | Result re-ranking |

#### `schemas/` — Pydantic v2 Contracts
| File | Status | Description |
|---|---|---|
| `orca_contract.py` | ✅ Implemented (16 KB) | Core response/evidence contract |
| `pfz_contract.py` | ✅ Implemented | PFZ data contract |
| `agent_runtime.py` | ✅ Implemented | Agent runtime schema |

#### `safety/` — Input Validation & Security
| File | Status | Description |
|---|---|---|
| `ssrf.py` | ✅ Implemented | SSRF protection |
| `sanitizer.py` | ✅ Implemented | Text query sanitization & coordinate validation |
| `source_policy.py` | ✅ Implemented | Source trust tier policy |
| `geographic_policy.py` | ✅ Implemented | Operational region enforcement |

#### `services/` — Core Services
| File | Status | Description |
|---|---|---|
| `event_broker.py` | ✅ Implemented | Redis pub/sub event broker |
| `streaming_runner.py` | ✅ Implemented (25 KB) | Streaming agent execution orchestrator |
| `geospatial.py` | ✅ Implemented | Geospatial service utilities |
| `ingestion.py` | ✅ Implemented | Data ingestion pipeline |

#### `telemetry/` — Observability
| File | Status | Description |
|---|---|---|
| `tracer.py` | ✅ Implemented | OpenTelemetry span tracing |

#### `tools/` — LangGraph Tool Registry
| File | Status | Description |
|---|---|---|
| `marine_tools.py` | ✅ Implemented (28 KB) | All marine intelligence tools |
| `registry.py` | ✅ Implemented (10 KB) | Tool registration and execution engine |

#### `translation/` — Multilingual Support
| File | Status | Description |
|---|---|---|
| `bhashini.py` | ✅ Implemented | Bhashini API integration |
| `mock.py` | ✅ Implemented | Mock translator for CI |
| `base.py` | ✅ Implemented | Abstract translator interface |
| `service.py` | ✅ Implemented | Translation service orchestrator |

#### `verification/` — Scientific Verification
| File | Status | Description |
|---|---|---|
| `scientific.py` | ✅ Implemented (42 KB) | Full scientific verification pipeline, source arbitration |

#### `fusion/` — Data Fusion
| Status | `__init__.py` only | Empty — fusion logic not yet implemented |
|---|---|---|

---

### 4.3 Alembic Migrations

| Migration | Status | Description |
|---|---|---|
| `0001_initial_postgis_pgvector.py` | ✅ | PostGIS + pgvector extensions, advisory table, GiST index |
| `0002_add_advisory_language.py` | ✅ | Language column on advisories |
| `0003_add_advisory_chunks_and_production_embedding.py` | ✅ | RAG chunk table + HNSW embedding index |
| `0004_create_agent_run_events.py` | ✅ | Agent event journal table |

---

## 5. Frontend — React/Vite/TypeScript Stack

### 5.1 Tech Stack — `apps/web/`

| Dependency | Version | Role |
|---|---|---|
| Vite | latest | Build tool |
| React | latest | UI framework |
| React DOM | latest | DOM rendering |
| TypeScript | latest | Type safety |
| MapLibre GL | latest | **Interactive map** rendering |
| Three.js | latest | **3D WebGL** rendering |
| Motion | ^13.4.0 | Animation library |
| GSAP | latest | Advanced animation |
| Zustand | latest | State management |
| Lucide React | ^1.47.0 | Icon library |

### 5.2 Frontend Module Breakdown — `apps/web/src/orca/`

| Module | Files | Status | Description |
|---|---|---|---|
| `OrcaApp.tsx` | 6.6 KB | ✅ Implemented | Root app shell with routing |
| `OrcaCommandCenter.tsx` | 11.4 KB | ✅ Implemented | Main command center orchestrator |
| `MapLibreView.tsx` | 5.8 KB | ✅ Implemented | Top-level MapLibre view wrapper |
| `useAgentStream.ts` | 13.7 KB | ✅ Implemented | SSE agent stream hook (core) |
| `contracts.ts` | 873 B | ✅ Implemented | Frontend type contracts |
| `ocean/GerstnerOcean.ts` | 9.6 KB | ✅ Implemented | Gerstner wave mesh + animation |
| `ocean/oceanShaders.ts` | 6.9 KB | ✅ Implemented | GLSL vertex + fragment shaders |
| `ocean/OceanAtmosphere.ts` | 3.7 KB | ✅ Implemented | Atmosphere/sky rendering |
| `ocean/MarineParticles.ts` | 3 KB | ✅ Implemented | Particle spray system |
| `aircraft/SurveillanceAircraft.ts` | 7.7 KB | ✅ Implemented | 3D aircraft positioning/attitude |
| `aircraft/SensorCone.ts` | 3.4 KB | ✅ Implemented | Sensor/radar cone visualization |
| `command-center/CommandCenterShell.tsx` | 10.4 KB | ✅ Implemented | Command center outer shell |
| `command-center/EnvironmentalHUD.tsx` | 5.7 KB | ✅ Implemented | Environmental data HUD panel |
| `command-center/TacticalPlaybackBar.tsx` | 4.7 KB | ✅ Implemented | Temporal playback controls |
| `command-center/TopTelemetryBar.tsx` | 7.3 KB | ✅ Implemented | Top status/telemetry bar |
| `agent/AgentHUD.tsx` | 5.9 KB | ✅ Implemented | Agent reasoning display |
| `agent/AgentStateBadge.tsx` | 2.7 KB | ✅ Implemented | Agent state badge indicator |
| `agent/ExecutionPipeline.tsx` | 3.6 KB | ✅ Implemented | Pipeline step visualization |
| `agent/SynthesizedAdvisory.tsx` | 4 KB | ✅ Implemented | Advisory output display |
| `map/MapLibreView.tsx` | 8.6 KB | ✅ Implemented | Full map component with layers |
| `map/LayerManager.tsx` | 3.3 KB | ✅ Implemented | Map layer toggle controls |
| `map/mapStyles.ts` | 1 KB | ✅ Implemented | MapLibre style definitions |
| `ui/FloatingPanel.tsx` | 2.2 KB | ✅ Implemented | Floating panel container |
| `ui/Gauge.tsx` | 3.9 KB | ✅ Implemented | Circular gauge component |
| `ui/SectionHeader.tsx` | 1.4 KB | ✅ Implemented | Section header component |
| `ui/StatusIndicator.tsx` | 2.4 KB | ✅ Implemented | Status LED indicator |
| `ui/TelemetryValue.tsx` | 2 KB | ✅ Implemented | Telemetry readout component |

> [!NOTE]
> **The frontend has substantial working components.** Despite the README saying "NOT IMPLEMENTED — WebGL Procedural Ocean & Aircraft Scene," the source code in `apps/web/src/orca/ocean/` and `apps/web/src/orca/aircraft/` shows these are **actually implemented** in TypeScript. The "NOT IMPLEMENTED" note in README likely refers to the `rendering/` directory (pure WebGL prototypes), not the frontend components.

---

## 6. Rendering — WebGL / 3D Layer

### `rendering/` — Pure WebGL Prototype Directory

| Directory | Status | Description |
|---|---|---|
| `rendering/shaders/` | ❌ Empty | GLSL shader prototypes not created |
| `rendering/ocean/` | ❌ Empty | Ocean mesh prototype not created |
| `rendering/aircraft/` | — | Not checked yet |

> [!CAUTION]
> The `rendering/` directory is **empty across all subdirectories**. The actual working ocean shader implementation lives in `apps/web/src/orca/ocean/` as TypeScript/Three.js modules — not as standalone GLSL files. If `rendering/` is intended as a library of raw `.glsl` files for editor tooling (`slevesque.shader`), those still need to be created by extracting the template literals from `oceanShaders.ts`.

---

## 7. Infrastructure — Docker, Database, Redis, MinIO

### 7.1 Docker Compose Services

| Service | Image | Port | Volume | Status |
|---|---|---|---|---|
| `postgres` | `orca-postgis-pgvector:17-3.5` | `5432:5432` | `postgres_data` | ✅ Custom image |
| `redis` | `redis:8-alpine` | `6379:6379` | `redis_data` | ✅ Cache / pub-sub |
| `minio` | `quay.io/minio/minio:latest` | `9000/9001` | `minio_data` | ✅ Object storage |

### 7.2 Database Init Scripts — `database/`
| Script | Description |
|---|---|
| `001_extensions.sql` | Enables `postgis` and `vector` extensions |
| `POSTGIS_DISTANCE.sql` | Reference script for `ST_Distance` on geography |

---

## 8. Test Suite

### 8.1 Standard CI Tests — `backend/tests/`

| Test File | Size | Coverage Area |
|---|---|---|
| `test_agent_runtime.py` | 37 KB | LangGraph agent runtime execution |
| `test_scientific_verification.py` | 26 KB | Scientific verifier pipeline |
| `test_hybrid_rag.py` | 25 KB | RAG + pgvector hybrid retrieval |
| `test_graph_persistence.py` | 20 KB | LangGraph state persistence |
| `test_advisory_rag.py` | 11 KB | Advisory RAG queries |
| `test_agent_streaming.py` | 13 KB | SSE streaming pipeline |
| `test_langgraph_orchestration.py` | 12 KB | Agent orchestration sequences |
| `test_provenance.py` | 8 KB | Data provenance tracking |
| `test_incois_adapter.py` | 7.5 KB | INCOIS adapter parsing/normalization |
| `test_dynamic_discovery_wiring.py` | 7.5 KB | THREDDS discovery seam |
| `test_translation.py` | 7.4 KB | Bhashini multilingual translation |
| `test_telemetry.py` | 8.6 KB | OpenTelemetry tracing |
| `test_safety_ssrf.py` | 4.5 KB | SSRF protection |
| `test_orca_contract.py` | 4.6 KB | Pydantic v2 contract enforcement |
| `test_pfz_repository.py` | 5 KB | PFZ spatial repository |
| `test_pfz_slice.py` | 7 KB | PFZ NetCDF slice extraction |
| `test_copernicus_adapter.py` | 4.3 KB | Copernicus adapter |
| `test_noaa_adapter.py` | 6 KB | NOAA adapter |
| `test_sst_chlorophyll.py` | 2.7 KB | SST + Chlorophyll extraction |
| `test_cache_fallback.py` | 3.4 KB | Cache/failover ladder |
| `test_pgvector.py` | 2.8 KB | pgvector HNSW queries |
| `test_postgis_spatial.py` | 2.4 KB | PostGIS ST_Distance |

### 8.2 Live / Smoke Tests — `backend/tests/live/`
| Test File | Data Source |
|---|---|
| `test_incois_live_wfs.py` | INCOIS GeoServer WFS (HTTP 200 verified) |
| `test_incois_live_catalog.py` | INCOIS THREDDS rolling catalog |
| `test_copernicus_live.py` | Copernicus Marine Service |
| `test_noaa_live.py` | NOAA weather |
| `test_bhashini_live.py` | Bhashini translation API |

> Run live tests via: `ORCA_LIVE_SMOKE=1 pytest backend/tests/live/`

---

## 9. Status Matrix (All Modules)

| Module | Code Exists | Tests Exist | Live-Verified | Notes |
|---|---|---|---|---|
| PostGIS 17 + pgvector DB | ✅ | ✅ | ✅ | Verified on live container |
| INCOIS WFS PFZ adapter | ✅ | ✅ | ✅ | HTTP 200, valid GeoJSON confirmed |
| INCOIS THREDDS SST/Chl | ✅ | ✅ | ✅ | Dynamic catalog discovery verified |
| LangGraph agent graph | ✅ | ✅ | ⚠️ Mocked | Requires live DB container |
| Hybrid RAG (PostGIS+pgvector) | ✅ | ✅ | ⚠️ Mocked | Requires live DB container |
| Pydantic v2 contracts | ✅ | ✅ | ✅ | |
| SSRF / Safety layer | ✅ | ✅ | ✅ | |
| FastAPI HTTP / SSE streaming | ✅ | ✅ | ⚠️ Mocked | |
| Scientific verification | ✅ | ✅ | ⚠️ Mocked | |
| Bhashini translation | ✅ | ✅ | ⚠️ Live opt-in | |
| OpenTelemetry tracing | ✅ | ✅ | ⚠️ Mocked | |
| BGE-M3 embeddings | ✅ | ✅ | ⚠️ Mocked | |
| Data fusion (`fusion/`) | ❌ Empty | ❌ | ❌ | `__init__.py` only |
| Maritime Safety Engine | ❌ Empty | ❌ | ❌ | `safety/__init__.py` has policy, route logic missing |
| Frontend React/MapLibre | ✅ | ❌ No E2E | ❌ | node_modules not installed per README |
| Frontend Ocean Shaders (TS) | ✅ | ❌ | ❌ | Implemented but not E2E tested |
| Frontend Aircraft 3D | ✅ | ❌ | ❌ | Implemented but not E2E tested |
| `rendering/` GLSL prototypes | ❌ Empty | ❌ | ❌ | Directories exist, no `.glsl` files |
| Playwright E2E tests | ❌ | ❌ | ❌ | Not set up yet |
| IMD radar / ECMWF / NOAA wind+wave | ❌ | ❌ | ❌ | Not implemented |
| Indian EEZ boundary layer | ❌ | ❌ | ❌ | Not implemented |

---

## 10. What Is Missing / Action Plan

### Priority 1 — Immediate (Agent Workstation)

| # | Action | Why |
|---|---|---|
| 1 | **Fix `.vscode/extensions.json`** | Still contains old list; update to Phase 2 pruned list with Python, Pylance, Ruff, Playwright |
| 2 | **Set `GITHUB_TOKEN` in environment** | GitHub MCP server will not authenticate without it |
| 3 | **Create `.agents/rules/coding-standards.md`** | Missing Python/TS naming and formatting rules |
| 4 | **Create `.agents/rules/security.md`** | SSRF, geographic policy, and sanitizer usage guidance for agents |
| 5 | **Add `orca-langgraph` skill** | No agent-readable reference for LangGraph graph authoring patterns |
| 6 | **Add `orca-incois-feeds` skill** | No agent-readable reference for WFS/THREDDS/NetCDF adapter patterns |

### Priority 2 — Near-Term (Code Gaps)

| # | Gap | Status |
|---|---|---|
| 1 | `backend/orca/fusion/` is empty | Data fusion across sources not implemented |
| 2 | Maritime Safety / route geofencing | Only policy stubs; classification logic missing |
| 3 | `rendering/shaders/` is empty | Raw GLSL files not extracted from TS modules |
| 4 | Playwright E2E test suite | No frontend tests exist at all |
| 5 | `rendering/aircraft/` | Not confirmed if empty or populated |

### Priority 3 — Infrastructure / Tooling

| # | Action |
|---|---|
| 1 | Run `npm install` in `apps/web/` to install node_modules |
| 2 | Start Docker Compose for live test runs: `docker compose up -d` |
| 3 | Create `.agents/plugins/orca-agent-system/` to bundle all skills+rules+MCP into a portable plugin |
| 4 | Add `hooks.json` for pre-commit linting enforcement (Ruff + ESLint) |

### Long-Term (Full Agentic Architecture)

```
Recommended Plugin Structure:
.agents/plugins/orca-agent-system/
├── plugin.json
├── mcp_config.json          (scoped MCP - Playwright, Context7, GitHub, Memory)
├── rules/
│   ├── architecture.md
│   ├── verification.md
│   ├── coding-standards.md
│   └── security.md
└── skills/
    ├── orca-postgis-spatial/
    ├── orca-webgl-shaders/
    ├── orca-langgraph/          ← MISSING
    ├── orca-incois-feeds/       ← MISSING
    ├── orca-fastapi-api/        ← MISSING
    └── orca-testing/            ← MISSING
```

---

*Audit complete. All data sourced from live filesystem scan of `d:\ORCA` on 2026-09-22.*
