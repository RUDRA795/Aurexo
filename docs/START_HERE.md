# ORCA — Start Here

## What is live in this first commit-sized scaffold

- Hardened Pydantic v2 Agent Contract.
- PFZ vertical slice with typed source boundary.
- Deterministic distance/bearing calculation.
- One-replan execution policy.
- Evidence/provenance tracking.
- Verification and conservative no-data behavior.
- FastAPI `/health` and `/v1/pfz/query` endpoints.
- PostgreSQL/PostGIS, Redis and object-storage development services in Docker Compose.
- Web command-center shell with a real Three.js/WebGL procedural ocean shader.

## What is deliberately not faked

The live INCOIS parser is not mocked as if it were production. The aircraft/surveillance asset is also not represented with a fake GIF/video/stock animation. The final aircraft scene will use a real GLB/GLTF asset and procedural animation once an appropriate asset is selected/licensed.

## First local run

Windows PowerShell:

```powershell
cd ORCA
.\scripts\start-local.ps1
```

Or manual:

```powershell
docker compose up -d
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
python run.py
```

Then open:

- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`
- Web frontend after `npm install && npm run dev`: `http://localhost:5173`

## Immediate next gate

Connect the real INCOIS PFZ adapter. Do not expand to additional agents until the live adapter has passed the existing PFZ contract/invariant tests.
