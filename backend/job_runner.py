"""
Async job queue for Sangam analysis runs.
- Max MAX_CONCURRENT jobs running simultaneously.
- Each job: post case message -> poll for verdict -> persist result.
- WebSocket clients are notified via per-job asyncio.Queue.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from backend.db import create_job, get_transcript, update_job, upsert_transcript
from orchestrator.band_client import fetch_room_messages, poll_for_verdict, post_case_message

MAX_CONCURRENT = 3

logger = logging.getLogger(__name__)

# job_id -> asyncio.Queue[dict]  (ws subscribers)
_ws_queues: dict[str, asyncio.Queue] = {}
_semaphore: asyncio.Semaphore | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    return _semaphore


def subscribe_ws(job_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _ws_queues[job_id] = q
    return q


def unsubscribe_ws(job_id: str) -> None:
    _ws_queues.pop(job_id, None)


def _notify_ws(job_id: str, event: dict) -> None:
    q = _ws_queues.get(job_id)
    if q is not None:
        q.put_nowait(event)


async def enqueue_job(job_id: str, case_id: str, sample_message: str, room_id: str) -> None:
    """Create the DB record and start the background task immediately."""
    await create_job(job_id, case_id, _now())
    asyncio.create_task(_run_job(job_id, case_id, sample_message, room_id))


async def _run_job(job_id: str, case_id: str, sample_message: str, room_id: str) -> None:
    sem = get_semaphore()
    async with sem:
        await _execute_job(job_id, case_id, sample_message, room_id)


async def _execute_job(job_id: str, case_id: str, sample_message: str, room_id: str) -> None:
    try:
        await update_job(job_id, _now(), status="running")
        _notify_ws(job_id, {"event": "status", "status": "running"})

        posted_at, run_id = await post_case_message(sample_message, room_id=room_id)
        await update_job(job_id, _now(), run_id=run_id)
        _notify_ws(job_id, {"event": "posted", "run_id": run_id, "posted_at": posted_at.isoformat()})

        verdict = await poll_for_verdict(
            room_id=room_id,
            posted_at=posted_at,
            timeout_s=300.0,
            poll_interval_s=3.0,
            expected_run_id=None,  # CG does not echo run_id
        )

        if verdict is None:
            await update_job(job_id, _now(), status="timeout", error="No verdict within 300 s")
            _notify_ws(job_id, {"event": "status", "status": "timeout"})
            return

        # Snapshot room transcript
        try:
            msgs = await fetch_room_messages(room_id=room_id)
            await upsert_transcript(job_id, _now(), msgs)
        except Exception:
            logger.exception("Failed to snapshot transcript for job %s", job_id)

        await update_job(job_id, _now(), status="complete", verdict=json.dumps(verdict))
        _notify_ws(job_id, {"event": "verdict", "verdict": verdict})

    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        await update_job(job_id, _now(), status="error", error=str(exc))
        _notify_ws(job_id, {"event": "error", "error": str(exc)})
