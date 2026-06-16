"""Dump room messages since a given time and show all senders."""
import asyncio
from datetime import datetime, timezone
from orchestrator.band_client import fetch_room_messages, ROOM_ID

SINCE = datetime(2026, 6, 16, 11, 35, 0, tzinfo=timezone.utc)  # just before last post

async def main():
    msgs = await fetch_room_messages(ROOM_ID)
    print(f"Total messages in room: {len(msgs)}\n")
    recent = [m for m in msgs if (m.get("inserted_at") or datetime.min.replace(tzinfo=timezone.utc)) >= SINCE]
    print(f"Messages since {SINCE.isoformat()}: {len(recent)}\n")
    for m in recent:
        ts = m.get("inserted_at")
        ts_str = ts.isoformat() if ts else "N/A"
        sender = m.get("sender_name") or m.get("sender_type") or "Unknown"
        content = (m.get("content") or "")[:200].replace("\n", " ")
        print(f"[{ts_str}] {sender!r}:")
        print(f"  {content}")
        print()

asyncio.run(main())
