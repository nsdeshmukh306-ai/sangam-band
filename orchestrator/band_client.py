"""Thin async REST wrapper for Sangam orchestrator → Band room operations.

Pro-plan edition: human_api_messages returns 403 plan_required, so all calls
use agent-level API keys (loaded from agent_config.yaml via load_agent_config).

  - Posting a case message: ComplianceGuard key +
      agent_api_messages.create_agent_chat_message
  - Polling for verdict: ComplianceGuard key +
      agent_api_context.get_agent_chat_context  (includes messages CG sent)
  - Full room transcript: all 6 agents' get_agent_chat_context, merged & sorted
      (union covers every message in the pipeline; fetched in parallel)
  - Accessibility check: ComplianceGuard key + get_agent_chat_context page 1

Verified against installed band-sdk:
  list_agent_messages  → .data (list[ChatMessage]), .metadata (total_pages etc.)
  get_agent_chat_context → .data (list[ChatMessage]), .meta  (total_pages etc.)
  create_agent_chat_message → same ChatMessageRequest/Mentions schema as human API
  ChatMessage fields: id, content, sender_name, sender_type, inserted_at,
                      message_type, metadata
"""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv(override=True)

import asyncio
import concurrent.futures
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from band.client.rest import (
    AsyncRestClient,
    ChatMessageRequest,
    ChatMessageRequestMentionsItem,
    DEFAULT_REQUEST_OPTIONS,
)
from band.config import load_agent_config

ROOM_ID = os.getenv("BAND_ROOM_ID", "9b4efd3c-46d2-4c40-8b33-d75dda925b05")

logger = logging.getLogger(__name__)

# All 6 agent keys in agent_config.yaml
_ALL_AGENTS = ["intake", "patient_profile", "structural", "pkpd", "evidence_rag", "compliance"]

# Matches fenced ```json ... ``` blocks (case-insensitive, dotall)
_JSON_FENCE_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _make_client(agent_key: str = "compliance") -> AsyncRestClient:
    """Return an AsyncRestClient authenticated as the given agent."""
    _, api_key = load_agent_config(agent_key)
    base_url = os.getenv("THENVOI_REST_URL", "https://app.band.ai/").rstrip("/")
    return AsyncRestClient(api_key=api_key, base_url=base_url)


def run_async(coro):
    """Run an async coroutine safely from a sync Streamlit context.

    Streamlit runs its own event loop, so asyncio.run() raises
    'This event loop is already running'. This helper runs the coroutine
    in a fresh thread that has no existing loop.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(asyncio.run, coro)
        return fut.result()


def _extract_verdict(content: str) -> dict | None:
    """Return parsed verdict dict if content has a FINAL_VERDICT JSON block."""
    for m in _JSON_FENCE_RE.finditer(content):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        step = data.get("step", "")
        status = data.get("status", "")
        if step == "FINAL_VERDICT" or status in ("FINAL_VERDICT", "PENDING_HUMAN_REVIEW"):
            return data
    return None


def _msg_to_dict(msg: Any) -> dict[str, Any]:
    """Normalise a ChatMessage object or raw dict into a plain dict."""
    if isinstance(msg, dict):
        return {
            "id": msg.get("id"),
            "sender_name": msg.get("sender_name") or msg.get("sender_type") or "Unknown",
            "sender_type": msg.get("sender_type") or "Unknown",
            "content": msg.get("content", ""),
            "inserted_at": msg.get("inserted_at"),
            "message_type": msg.get("message_type", "text"),
        }
    return {
        "id": getattr(msg, "id", None),
        "sender_name": getattr(msg, "sender_name", None) or getattr(msg, "sender_type", "Unknown"),
        "sender_type": getattr(msg, "sender_type", "Unknown"),
        "content": getattr(msg, "content", ""),
        "inserted_at": getattr(msg, "inserted_at", None),
        "message_type": getattr(msg, "message_type", "text"),
    }


async def _with_retry(coro_fn, max_retries: int = 3, base_delay: float = 1.0):
    """Call an async zero-argument coroutine with exponential-backoff retry.

    Retries on any exception; re-raises after max_retries exhausted.
    This makes Band API calls resilient to transient network blips and the
    intermittent 5xx responses observed in Phase 2 testing.
    """
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as exc:
            if attempt == max_retries:
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning(
                "Band API call failed (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1, max_retries + 1, delay, exc,
            )
            await asyncio.sleep(delay)


async def _get_agent_context_all_pages(
    client: AsyncRestClient,
    room_id: str,
    page_size: int = 100,
) -> list[dict[str, Any]]:
    """Fetch all pages of get_agent_chat_context with per-page retry."""
    all_msgs: list[dict] = []
    page = 1
    while True:
        try:
            resp = await _with_retry(
                lambda p=page: client.agent_api_context.get_agent_chat_context(
                    chat_id=room_id,
                    page=p,
                    page_size=page_size,
                    request_options=DEFAULT_REQUEST_OPTIONS,
                ),
                max_retries=2,
            )
        except Exception:
            break
        for msg in resp.data or []:
            all_msgs.append(_msg_to_dict(msg))
        meta = getattr(resp, "meta", None)
        total_pages = getattr(meta, "total_pages", 1) if meta else 1
        if page >= total_pages or not resp.data:
            break
        page += 1
    return all_msgs


async def post_case_message(content: str, room_id: str = ROOM_ID) -> tuple[datetime, str]:
    """Post a case message to the room using EvidenceRAG's agent key.

    EvidenceRAG is used as the posting identity because:
    - Band rejects self-mentions (Intake can't @mention @Intake)
    - ComplianceGuard posting keeps the case message in CG's context,
      which can confuse poll_for_verdict
    - EvidenceRAG is not @mentioned in the initial message, so it
      won't receive it back or trigger a self-loop
    @mentions @Intake and @PatientProfile to kick off the pipeline.
    Returns (posted_at, run_id) — both needed by poll_for_verdict.
    """
    client = _make_client("evidence_rag")
    intake_id, _ = load_agent_config("intake")
    pp_id, _ = load_agent_config("patient_profile")

    # Stamp every submission with a unique run ID so agents with long-context
    # memory don't silently skip it as a duplicate of a prior run in the same room.
    run_id = uuid.uuid4().hex[:8]
    posted_at = datetime.now(timezone.utc)
    stamped = f"{content}\n\n[Run {run_id} — {posted_at.strftime('%Y-%m-%dT%H:%M:%SZ')}]"

    await client.agent_api_messages.create_agent_chat_message(
        chat_id=room_id,
        message=ChatMessageRequest(
            content=stamped,
            mentions=[
                ChatMessageRequestMentionsItem(id=intake_id, handle="Intake", name="Intake"),
                ChatMessageRequestMentionsItem(id=pp_id, handle="PatientProfile", name="PatientProfile"),
            ],
        ),
        request_options=DEFAULT_REQUEST_OPTIONS,
    )
    return posted_at, run_id


async def fetch_room_messages(
    room_id: str = ROOM_ID,
    max_pages_per_agent: int = 5,
) -> list[dict[str, Any]]:
    """Return a full room transcript in chronological order.

    Merges get_agent_chat_context from all 6 agents in parallel, then deduplicates
    by message ID and sorts by inserted_at. Covers every message in the pipeline
    (each message @mentions at least one agent and/or is sent by one).
    """
    async def _fetch_one(agent_key: str) -> list[dict]:
        try:
            client = _make_client(agent_key)
            return await _get_agent_context_all_pages(client, room_id)
        except Exception:
            return []

    results = await asyncio.gather(*[_fetch_one(k) for k in _ALL_AGENTS])

    # Deduplicate by message ID
    seen: set[str | None] = set()
    merged: list[dict] = []
    for batch in results:
        for msg in batch:
            mid = msg.get("id")
            if mid not in seen:
                seen.add(mid)
                merged.append(msg)

    # Sort chronologically; messages with no timestamp go last
    def _ts(m: dict) -> datetime:
        t = m.get("inserted_at")
        if t is None:
            return datetime(9999, 1, 1, tzinfo=timezone.utc)
        if t.tzinfo is None:
            return t.replace(tzinfo=timezone.utc)
        return t

    merged.sort(key=_ts)
    return merged


async def poll_for_verdict(
    room_id: str = ROOM_ID,
    posted_at: datetime | None = None,
    timeout_s: float = 180.0,
    poll_interval_s: float = 3.0,
    expected_run_id: str | None = None,
) -> dict | None:
    """Poll for a ComplianceGuard FINAL_VERDICT or PENDING_HUMAN_REVIEW.

    Uses ComplianceGuard's agent_api_context (which includes messages CG sent)
    and scans for a JSON block with step/status == FINAL_VERDICT or
    PENDING_HUMAN_REVIEW, posted after `posted_at`.

    If `expected_run_id` is set, only accepts verdicts whose JSON contains
    `"run_id": expected_run_id` — rejects stale verdicts from prior runs.

    Returns the parsed verdict dict, or None on timeout.
    """
    if posted_at is None:
        posted_at = datetime.now(timezone.utc)

    client = _make_client("compliance")
    deadline = time.monotonic() + timeout_s

    while time.monotonic() < deadline:
        try:
            msgs = await _get_agent_context_all_pages(client, room_id)
            for msg in msgs:
                # Only consider messages ComplianceGuard itself sent
                sender = (msg.get("sender_name") or "").lower()
                if sender != "complianceguard":
                    continue
                ts = msg.get("inserted_at")
                if ts:
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts <= posted_at:
                        continue
                verdict = _extract_verdict(msg.get("content", ""))
                if verdict is None:
                    continue
                # If caller supplied a run_id, reject verdicts that don't match
                if expected_run_id and verdict.get("run_id") != expected_run_id:
                    continue
                return verdict
        except Exception:
            pass

        await asyncio.sleep(poll_interval_s)

    return None


async def check_room_accessible(room_id: str = ROOM_ID) -> bool:
    """Return True if ComplianceGuard's key can read the room context."""
    try:
        client = _make_client("compliance")
        resp = await client.agent_api_context.get_agent_chat_context(
            chat_id=room_id,
            page=1,
            page_size=1,
            request_options=DEFAULT_REQUEST_OPTIONS,
        )
        return resp is not None
    except Exception:
        return False
