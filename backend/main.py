"""
Sangam FastAPI backend.

Endpoints:
  POST   /api/cases/run             — enqueue a new analysis job
  GET    /api/cases/{job_id}/status — poll job status + verdict
  GET    /api/cases/list            — list recent jobs
  GET    /api/room/transcript       — live Band room transcript
  WS     /api/ws/{job_id}           — stream job events to browser

Start with: uvicorn backend.main:app --port 8000 --reload
"""

from __future__ import annotations

import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.db import get_job, get_transcript, init_db, list_jobs
from backend.job_runner import enqueue_job, subscribe_ws, unsubscribe_ws
from backend.logging_config import configure_logging

logger = logging.getLogger(__name__)

configure_logging()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    await init_db()
    logger.info("Sangam backend started — DB initialised")
    yield
    logger.info("Sangam backend shutting down")


app = FastAPI(
    title="Sangam API",
    description="Polypharmacy Safety Council — async job queue over Band multi-agent pipeline",
    version="1.0.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_cases() -> dict[str, Any]:
    import json
    from pathlib import Path

    path = Path(__file__).parent.parent / "data" / "case_studies.json"
    data = json.loads(path.read_text())
    return {c["id"]: c for c in data["cases"]}


# ---- request / response models ----

class RunRequest(BaseModel):
    case_id: str
    room_id: str | None = None


class RunResponse(BaseModel):
    job_id: str
    case_id: str
    status: str


class JobStatus(BaseModel):
    job_id: str
    case_id: str
    status: str
    run_id: str | None = None
    verdict: dict | None = None
    error: str | None = None
    created_at: str
    updated_at: str


# ---- routes ----

@app.get("/health")
async def health():
    """Liveness probe — also checks Band room accessibility when possible."""
    checks: dict[str, Any] = {"status": "ok", "version": "1.0.0"}
    try:
        from orchestrator.band_client import check_room_accessible
        checks["band_room"] = "ok" if await check_room_accessible() else "unreachable"
    except Exception as exc:
        checks["band_room"] = f"error: {exc}"
    return checks


@app.post("/api/cases/run", response_model=RunResponse)
async def run_case(body: RunRequest):
    cases = _load_cases()
    if body.case_id not in cases:
        raise HTTPException(status_code=404, detail=f"case_id '{body.case_id}' not found")

    case = cases[body.case_id]
    sample_message = case.get("sample_message", "")
    if not sample_message:
        raise HTTPException(status_code=422, detail="Case has no sample_message")

    import os
    room_id = body.room_id or os.getenv("BAND_ROOM_ID", "9b4efd3c-46d2-4c40-8b33-d75dda925b05")
    job_id = uuid.uuid4().hex

    logger.info(
        "Job enqueued",
        extra={"job_id": job_id, "case_id": body.case_id},
    )
    await enqueue_job(job_id=job_id, case_id=body.case_id, sample_message=sample_message, room_id=room_id)
    return RunResponse(job_id=job_id, case_id=body.case_id, status="queued")


@app.get("/api/cases/list")
async def list_cases_endpoint():
    """Return metadata for all case studies (no jobs)."""
    cases = _load_cases()
    return {
        "count": len(cases),
        "cases": [
            {
                "id": c["id"],
                "title": c["title"],
                "expected_tier": c.get("expected_tier"),
                "drug": c["drugs"][0]["name"] if c.get("drugs") else None,
                "herb": c["herbs"][0]["name"] if c.get("herbs") else None,
            }
            for c in cases.values()
        ],
    }


@app.get("/api/cases/{job_id}/status", response_model=JobStatus)
async def job_status(job_id: str):
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(**job)


@app.get("/api/jobs")
async def list_jobs_endpoint(limit: int = 20):
    jobs = await list_jobs(limit=limit)
    return {"jobs": jobs}


@app.get("/api/jobs/{job_id}/transcript")
async def job_transcript(job_id: str):
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    msgs = await get_transcript(job_id)
    return {"job_id": job_id, "count": len(msgs), "messages": msgs}


@app.get("/api/room/transcript")
async def room_transcript():
    """Fetch the live Band room transcript (all agents, merged + sorted)."""
    try:
        from orchestrator.band_client import fetch_room_messages

        msgs = await fetch_room_messages()

        def _serialise(m: dict) -> dict:
            ts = m.get("inserted_at")
            return {**m, "inserted_at": ts.isoformat() if hasattr(ts, "isoformat") else ts}

        return {"count": len(msgs), "messages": [_serialise(m) for m in msgs]}
    except Exception as exc:
        logger.exception("Failed to fetch room transcript")
        raise HTTPException(status_code=503, detail=f"Band room unavailable: {exc}")


@app.websocket("/api/ws/{job_id}")
async def websocket_job(websocket: WebSocket, job_id: str):
    """Stream job events to the browser.

    Events emitted (JSON):
      {"event": "status", "status": "running"}
      {"event": "posted", "run_id": "...", "posted_at": "..."}
      {"event": "verdict", "verdict": {...}}
      {"event": "timeout"}
      {"event": "error", "error": "..."}
      {"event": "done"}   — sent after terminal event; client should close
    """
    await websocket.accept()

    # If job is already terminal, send current state immediately and close
    job = await get_job(job_id)
    if job is not None and job["status"] in ("complete", "error", "timeout"):
        await websocket.send_text(json.dumps({"event": "status", "status": job["status"], "verdict": job.get("verdict")}))
        await websocket.send_text(json.dumps({"event": "done"}))
        await websocket.close()
        return

    q = subscribe_ws(job_id)
    try:
        while True:
            try:
                event = q.get_nowait()
            except Exception:
                import asyncio

                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Send keepalive ping
                    await websocket.send_text(json.dumps({"event": "ping"}))
                    continue

            # Serialise datetime objects if present
            def _fix(o):
                return o.isoformat() if hasattr(o, "isoformat") else o

            safe = {k: _fix(v) for k, v in event.items()}
            await websocket.send_text(json.dumps(safe))

            if event.get("event") in ("verdict", "error", "timeout"):
                await websocket.send_text(json.dumps({"event": "done"}))
                break
    except WebSocketDisconnect:
        pass
    finally:
        unsubscribe_ws(job_id)


# Serve React SPA at /app — mount last so API routes take priority
_dist = Path(__file__).parent.parent / "frontend" / "react" / "dist"
if _dist.exists():
    app.mount("/app", StaticFiles(directory=str(_dist), html=True), name="react")
