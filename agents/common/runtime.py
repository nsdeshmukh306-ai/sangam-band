"""Shared Band agent construction helper.

Centralizes Agent.create(...) + load_agent_config(...) so ws_url/rest_url are
only overridden when explicitly set in the environment -- passing None would
override the SDK's correct built-in defaults (see docs/architecture.md).
"""
from __future__ import annotations

import os

from band import Agent
from band.config import load_agent_config


def create_agent(adapter, agent_key: str) -> Agent:
    """Build a Band Agent for `agent_key` (as defined in agent_config.yaml).

    Reads BAND_WS_URL / BAND_REST_URL from the environment if set, otherwise
    falls back to Agent.create's own defaults (the production Band platform).
    """
    agent_id, api_key = load_agent_config(agent_key)

    kwargs = {}
    if ws_url := os.getenv("BAND_WS_URL"):
        kwargs["ws_url"] = ws_url
    if rest_url := os.getenv("BAND_REST_URL"):
        kwargs["rest_url"] = rest_url

    return Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key, **kwargs)
