# ORCA PS 26176 — PFZ Vertical Slice

This package contains the hardened ORCA Agent Contract and PFZ vertical slice used as the engineering baseline.

## What is included

- `orca_contract.py` — hardened Pydantic v2 contract
- `pfz_contract.py` — typed PFZ request/result models
- `pfz_pipeline.py` — PFZ retrieval, validation, deterministic geospatial agent, verification, one-replan path and GeoJSON response
- `test_orca_contract.py` — contract invariant tests
- `test_pfz_slice.py` — PFZ vertical-slice acceptance tests
- `ORCA_RESEARCH_BUILD_BLUEPRINT.md` — full research/architecture/build plan
- `POSTGIS_DISTANCE.sql` — production distance/radius SQL reference
- `requirements.txt` / `pyproject.toml` — local test environment

## Current test status

The local implementation passes:

```text
25 passed
```

## Run

```bash
python -m venv .venv
# activate the environment
pip install -r requirements.txt
pytest -q
```

## Important limitation

`MockPFZDataSource` is a test fixture. `INCOISPFZAdapter` deliberately does not guess an undocumented endpoint. Connect it in the deployment environment to the current INCOIS WebGIS/structured service or a robust official advisory parser.

The test implementation uses a deterministic haversine calculation as a development fallback. Production should use PostGIS `geography` with `ST_DWithin` and `ST_Distance`.

## Architecture invariant

LLMs decide what to do. Deterministic code decides what the data says.
