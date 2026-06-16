"""Dump the current room transcript to see what messages exist and their sender_names."""
import asyncio
from orchestrator.band_client import fetch_room_messages, ROOM_ID

async def main():
    msgs = await fetch_room_messages(ROOM_ID)
    print(f"Total messages: {len(msgs)}\n")
    for m in msgs[-20:]:  # last 20 messages
        ts = m.get("inserted_at")
        ts_str = ts.isoformat() if ts else "N/A"
        sender = m.get("sender_name") or m.get("sender_type") or "Unknown"
        content = (m.get("content") or "")[:120].replace("\n", " ")
        print(f"[{ts_str}] {sender!r}: {content}")

asyncio.run(main())
