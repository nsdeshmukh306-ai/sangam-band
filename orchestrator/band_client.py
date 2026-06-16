"""Thin async REST wrapper for Sangam orchestrator → Band room operations.

Uses thenvoi_rest.AsyncRestClient (re-exported via band.client.rest) with
BAND_USER_API_KEY for all human-level room interactions: posting a case message,
polling the room transcript, and listing participants.

Verified against the installed band-sdk package:
  - list_my_chat_messages: page/page_size/message_type/since params, newest-first
  - send_my_chat_message: requires ChatMessageRequest with content + mentions list
  - ChatMessage fields: id, content, sender_name, sender_type, inserted_at, message_type
  - ListMyChatMessagesResponseMetadata: page, page_size, total_count, total_pages
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

from band.client.rest import (
    AsyncRestClient,
    ChatMessageRequest,
    ChatMessageRequestMentionsItem,
    DEFAULT_REQUEST_OPTIONS,
)
from band.config import load_agent_config
from dotenv import load_dotenv

load_dotenv()

ROOM_ID = os.getenv("BAND_ROOM_ID", "9b4efd3c-46d2-4c40-8b33-d75dda925b05")

# Matches fenced ```json ... ``` blocks (case-insensitive, dotall)
_JSON_FENCE_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _make_client() -> AsyncRestClient:
    key = os.getenv("BAND_USER_API_KEY")
    if not key:
        raise RuntimeError(
            "BAND_USER_API_KEY is not set. "
            "Add it to .env (see docs.band.ai/getting-started/setup)."
        )
    return AsyncRestClient(api_key=key)


def _extract_verdict(content: str) -> dict | None:
    """Return the parsed verdict dict if content contains a FINAL_VERDICT JSON block."""
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


async def post_case_message(content: str, room_id: str = ROOM_ID) -> datetime:
    """Post a case message to the room, @mentioning @Intake and @PatientProfile.

    Returns the UTC timestamp just before posting — use this as the lower-bound
    timestamp when polling for ComplianceGuard's reply.
    """
    client = _make_client()
    intake_id, _ = load_agent_config("intake")
    pp_id, _ = load_agent_config("patient_profile")

    posted_at = datetime.now(timezone.utc)
    await client.human_api_messages.send_my_chat_message(
        chat_id=room_id,
        message=ChatMessageRequest(
            content=content,
            mentions=[
                ChatMessageRequestMentionsItem(
                    id=intake_id, handle="Intake", name="Intake"
                ),
                ChatMessageRequestMentionsItem(
                    id=pp_id, handle="PatientProfile", name="PatientProfile"
                ),
            ],
        ),
        request_options=DEFAULT_REQUEST_OPTIONS,
    )
    return posted_at


async def fetch_room_messages(
    room_id: str = ROOM_ID,
    message_type: str | None = "text",
    max_pages: int = 20,
) -> list[dict[str, Any]]:
    """Fetch all room messages (all pages), returned in chronological order.

    Each dict has: sender_name, sender_type, content, inserted_at, message_type.
    The API returns newest-first; this function reverses to oldest-first.
    """
    client = _make_client()
    all_msgs: list[dict] = []
    page = 1
    page_size = 100

    while page <= max_pages:
        try:
            resp = await client.human_api_messages.list_my_chat_messages(
                chat_id=room_id,
                page=page,
                page_size=page_size,
                message_type=message_type,
                request_options=DEFAULT_REQUEST_OPTIONS,
            )
        except Exception:
            break

        batch = resp.data or []
        for msg in batch:
            all_msgs.append(
                {
                    "sender_name": msg.sender_name or msg.sender_type,
                    "sender_type": msg.sender_type,
                    "content": msg.content,
                    "inserted_at": msg.inserted_at,
                    "message_type": msg.message_type,
                }
            )

        meta = getattr(resp, "meta", None)
        total_pages = getattr(meta, "total_pages", 1) if meta else 1
        if page >= total_pages or len(batch) < page_size:
            break
        page += 1

    all_msgs.reverse()  # newest-first → chronological
    return all_msgs


async def poll_for_verdict(
    room_id: str = ROOM_ID,
    posted_at: datetime | None = None,
    timeout_s: float = 120.0,
    poll_interval_s: float = 3.0,
) -> dict | None:
    """Poll the room until ComplianceGuard posts a FINAL_VERDICT or PENDING_HUMAN_REVIEW.

    Only considers ComplianceGuard text messages posted at or after `posted_at`.
    Returns the parsed verdict dict, or None if timeout_s is exceeded.
    """
    if posted_at is None:
        posted_at = datetime.now(timezone.utc)

    client = _make_client()
    deadline = time.monotonic() + timeout_s

    while time.monotonic() < deadline:
        try:
            resp = await client.human_api_messages.list_my_chat_messages(
                chat_id=room_id,
                page=1,
                page_size=50,
                message_type="text",
                request_options=DEFAULT_REQUEST_OPTIONS,
            )
            for msg in resp.data or []:
                if (msg.sender_name or "").lower() != "complianceguard":
                    continue
                ts = msg.inserted_at
                if ts:
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts < posted_at:
                        continue
                verdict = _extract_verdict(msg.content)
                if verdict:
                    return verdict
        except Exception:
            pass

        await asyncio.sleep(poll_interval_s)

    return None


async def check_room_accessible(room_id: str = ROOM_ID) -> bool:
    """Return True if the room is readable (BAND_USER_API_KEY valid, room exists)."""
    try:
        client = _make_client()
        resp = await client.human_api_messages.list_my_chat_messages(
            chat_id=room_id,
            page=1,
            page_size=1,
            request_options=DEFAULT_REQUEST_OPTIONS,
        )
        return resp is not None
    except Exception:
        return False
