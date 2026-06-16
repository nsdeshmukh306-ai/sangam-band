"""Stateless LangGraph adapter — each Band message gets its own fresh thread.

Drop-in replacement for LangGraphAdapter that avoids the state-accumulation
bug where prior-case history fills the InMemorySaver and causes the LLM to
stop calling band_send_message after a few messages.

Usage (in any agent):
    from agents.common.adapter import FreshGraphAdapter as LangGraphAdapter
"""
from __future__ import annotations

from typing import Any

from band.adapters.langgraph import LangGraphAdapter
from band.core.protocols import AgentToolsProtocol
from band.core.types import PlatformMessage
from band.converters.langchain import LangChainMessages


class FreshGraphAdapter(LangGraphAdapter):
    """LangGraph adapter that isolates every Band message in its own thread.

    By using ``msg.id`` as the LangGraph thread-id and always forcing
    ``is_session_bootstrap=True``, each incoming message starts with a clean
    ReAct agent (no accumulated prior-case state). The system prompt is always
    injected; room history is included only when the runtime provides it (true
    bootstrap after agent start), and empty otherwise — which is fine because
    the system prompt is self-contained.
    """

    async def on_message(
        self,
        msg: PlatformMessage,
        tools: AgentToolsProtocol,
        history: LangChainMessages,
        participants_msg: str | None,
        contacts_msg: str | None,
        *,
        is_session_bootstrap: bool,
        room_id: str,
    ) -> None:
        await super().on_message(
            msg,
            tools,
            [],                          # no room history — system prompt is self-contained
            participants_msg,
            contacts_msg,
            is_session_bootstrap=True,   # always bootstrap → always inject system prompt
            room_id=msg.id,              # unique thread per message → no accumulated state
        )
