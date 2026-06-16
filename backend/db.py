"""
SQLite persistence layer for Sangam backend.
Tables:
  jobs          — one row per analysis job
  transcript_cache — Band room transcript snapshot per job
"""

import json
from pathlib import Path
from typing import Any

import aiosqlite

DB_PATH = Path(__file__).parent.parent / "data" / "sangam.db"


async def get_db() -> aiosqlite.Connection:
    """Return an open aiosqlite connection (caller must close / use as context manager)."""
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    return conn


async def init_db() -> None:
    """Create tables if they do not exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id          TEXT PRIMARY KEY,
                case_id         TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'queued',
                run_id          TEXT,
                verdict         TEXT,
                error           TEXT,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transcript_cache (
                job_id          TEXT NOT NULL,
                fetched_at      TEXT NOT NULL,
                messages        TEXT NOT NULL,
                PRIMARY KEY (job_id)
            )
        """)
        await db.commit()


async def create_job(job_id: str, case_id: str, now: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO jobs (job_id, case_id, status, created_at, updated_at) VALUES (?, ?, 'queued', ?, ?)",
            (job_id, case_id, now, now),
        )
        await db.commit()


async def update_job(job_id: str, now: str, **fields: Any) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [now, job_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE jobs SET {cols}, updated_at = ? WHERE job_id = ?", vals)
        await db.commit()


async def get_job(job_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)) as cur:
            row = await cur.fetchone()
    if row is None:
        return None
    d = dict(row)
    if d.get("verdict"):
        d["verdict"] = json.loads(d["verdict"])
    return d


async def list_jobs(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        if d.get("verdict"):
            d["verdict"] = json.loads(d["verdict"])
        result.append(d)
    return result


async def upsert_transcript(job_id: str, fetched_at: str, messages: list[dict]) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO transcript_cache (job_id, fetched_at, messages)
            VALUES (?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET fetched_at=excluded.fetched_at, messages=excluded.messages
            """,
            (job_id, fetched_at, json.dumps(messages)),
        )
        await db.commit()


async def get_transcript(job_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT messages FROM transcript_cache WHERE job_id = ?", (job_id,)
        ) as cur:
            row = await cur.fetchone()
    if row is None:
        return []
    return json.loads(row["messages"])
