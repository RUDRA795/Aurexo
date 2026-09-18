from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from orca.agents.pfz_pipeline import MockPFZDataSource, run_pfz_query
from orca.schemas.orca_contract import Geometry


app = FastAPI(title="ORCA Marine Intelligence API", version="0.1.0")


class PFZRequest(BaseModel):
    query: str = "Where is the nearest PFZ today?"
    location: Geometry
    valid_at: datetime
    radius_km: float = Field(default=300.0, gt=0, le=2000)
    sector: str | None = None


@app.get("/health")
async def health() -> dict[str, Any]:
    try:
        from orca.database.session import check_database_health
        db_health = await check_database_health()
    except Exception as exc:
        db_health = {"status": "unreachable", "error": str(exc)}
    return {"status": "ok", "service": "orca-api", "database": db_health}


@app.post("/v1/pfz/query")
async def pfz_query(payload: PFZRequest):
    source = MockPFZDataSource()
    state = await run_pfz_query(
        query_text=payload.query,
        location=payload.location,
        valid_at=payload.valid_at,
        sources=[source],
        radius_km=payload.radius_km,
        sector=payload.sector,
    )
    if state.final_answer is None:
        raise HTTPException(status_code=500, detail="ORCA produced no final response")
    return state.final_answer.model_dump(mode="json")
