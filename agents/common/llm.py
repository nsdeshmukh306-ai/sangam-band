"""Shared DeepSeek LLM factory.

All 6 Sangam agents call DeepSeek's OpenAI-compatible API via ChatOpenAI with a
custom base_url -- see docs/architecture.md for verification notes.
"""
from __future__ import annotations

import os

from langchain_openai import ChatOpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def get_deepseek_llm(model: str = "deepseek-chat") -> ChatOpenAI:
    """Build a ChatOpenAI client pointed at DeepSeek.

    Args:
        model: "deepseek-chat" for routine agents, "deepseek-reasoner" for agents
            doing multi-step reasoning (e.g. @StructuralBio, @ComplianceGuard).
    """
    return ChatOpenAI(
        model=model,
        base_url=DEEPSEEK_BASE_URL,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
    )
