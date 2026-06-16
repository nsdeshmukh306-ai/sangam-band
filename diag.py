import asyncio
from datetime import datetime, timezone
from orchestrator.band_client import fetch_room_messages, ROOM_ID

SINCE = datetime(2026, 6, 16, 12, 24, 0, tzinfo=timezone.utc)

async def main():
    msgs = await fetch_room_messages(ROOM_ID)
    recent = [m for m in msgs if (m.get("inserted_at") or datetime.min.replace(tzinfo=timezone.utc)) >= SINCE]
    print(f"Total: {len(msgs)}, since {SINCE}: {len(recent)}\n")
    for m in recent:
        ts = m.get("inserted_at")
        sender = m.get("sender_name") or "Unknown"
        content = (m.get("content") or "")[:400].replace("\n", " ")
        print(f"[{ts}] {sender}:\n  {content}\n")

asyncio.run(main())
