import asyncio, traceback
from band.client.rest import AsyncRestClient, DEFAULT_REQUEST_OPTIONS
from band.config import load_agent_config

ROOM_ID = "9b4efd3c-46d2-4c40-8b33-d75dda925b05"

async def main():
    agent_id, api_key = load_agent_config("compliance")
    print(f"Agent ID: {agent_id[:8]}...")
    print(f"API Key: {api_key[:20]}...")
    client = AsyncRestClient(api_key=api_key)

    # List available methods
    print("\nagent_api_context attrs:", [m for m in dir(client.agent_api_context) if not m.startswith('_')])
    print("agent_api_messages attrs:", [m for m in dir(client.agent_api_messages) if not m.startswith('_')])

    print("\n--- Testing get_agent_chat_context ---")
    try:
        resp = await client.agent_api_context.get_agent_chat_context(
            chat_id=ROOM_ID,
            page=1,
            page_size=1,
            request_options=DEFAULT_REQUEST_OPTIONS,
        )
        print("Success:", type(resp))
        print("data:", resp.data)
        print("meta:", getattr(resp, 'meta', 'N/A'))
    except Exception as e:
        traceback.print_exc()

    print("\n--- Testing list_agent_messages ---")
    try:
        resp2 = await client.agent_api_messages.list_agent_messages(
            chat_id=ROOM_ID,
            status="all",
            page=1,
            page_size=1,
            request_options=DEFAULT_REQUEST_OPTIONS,
        )
        print("Success:", type(resp2))
        print("data:", resp2.data)
        print("metadata:", getattr(resp2, 'metadata', 'N/A'))
    except Exception as e:
        traceback.print_exc()

asyncio.run(main())
