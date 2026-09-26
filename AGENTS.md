# ORCA Antigravity Agent Workspace Guidelines

Welcome to the **ORCA** (Marine EcOsystem Reasoning with Collaborative Agents) workspace.
This project is an ISRO Problem Statement 26176 implementation.

## 1. Prime Directive
> **LLM decides WHAT TO DO. Deterministic code decides WHAT THE DATA SAYS.**

- You act as an autonomous orchestrator, planner, code author, and reviewer.
- All spatial math, scientific unit conversions, and safety determinations must be performed by deterministic Python and PostGIS code. Do not hallucinate coordinates or distances.

## 2. Tech Stack Reference
- **Backend**: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy, Alembic, xarray, NetCDF4.
- **Spatial & Data**: PostgreSQL 17, PostGIS 3.5 (`ST_Distance` on geography), `pgvector` HNSW cosine similarity.
- **Frontend**: Vite, React, TypeScript, MapLibre GL, Lucide React, Zustand, Motion, GSAP.
- **3D & Shaders**: Three.js, WebGL GLSL procedural ocean shaders, glTF aircraft models. (No proxy video/GIFs).
- **Testing**: Pytest (unit/mock hermetic CI) and Playwright (E2E browser verification).

## 3. Workspace Customizations
- **Rules**: Located in [.agents/rules/](file:///d:/ORCA/.agents/rules)
  - [architecture.md](file:///d:/ORCA/.agents/rules/architecture.md): Strict spatial, failover ladder, and rendering rules.
  - [verification.md](file:///d:/ORCA/.agents/rules/verification.md): 5-tier system verification protocol.
- **Skills**: Located in [.agents/skills/](file:///d:/ORCA/.agents/skills)
  - `orca-postgis-spatial`: PostGIS geography and pgvector search patterns.
  - `orca-webgl-shaders`: Procedural GLSL Gerstner ocean waves and glTF loading.
- **MCP Config**: Configured in [.agents/mcp_config.json](file:///d:/ORCA/.agents/mcp_config.json) (Playwright, GitHub, Context7, Memory, Sequential Thinking).
