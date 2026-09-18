# ORCA — Marine EcOsystem Reasoning with Collaborative Agents

ISRO Problem Statement 26176 implementation workspace.

## Current milestone

The repository begins with the hardened ORCA Agent Contract and PFZ vertical slice. The live INCOIS adapter is intentionally left behind a swappable `PFZDataSource` boundary until the deployment environment can inspect the current WebGIS/feature-service response.

## Start local infrastructure

```bash
docker compose up -d
```

## Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pytest
python run.py
```

API: http://localhost:8000
Docs: http://localhost:8000/docs
Health: http://localhost:8000/health

## Current PFZ endpoint

`POST /v1/pfz/query`

The endpoint currently uses the deterministic PFZ fixture so the runtime can be developed before the real INCOIS adapter is connected.

## Architecture rule

LLMs may understand, plan, select tools and synthesize language. Deterministic software owns distances, geometry, validity, thresholds, safety decisions and other numerical/spatial results.

## Next implementation gates

1. Connect the real INCOIS PFZ adapter.
2. Add SST and chlorophyll adapters.
3. Replace haversine fallback with PostGIS geography calculations.
4. Add the safety engine.
5. Add WebSocket execution traces.
6. Build the real WebGL ocean/aircraft scene — no proxy video/GIF background.
