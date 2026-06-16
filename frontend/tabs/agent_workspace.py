"""Tab 3 — Agent Workspace.

Live transcript of the real Band room (polls every 5 s), styled chat bubbles
per agent, and a pipeline progress indicator.
"""
from __future__ import annotations

import asyncio
import json
import re
import time

import streamlit as st

# Avatar colours per agent (and human fallback)
_AGENT_COLORS: dict[str, str] = {
    "intake": "#1E88E5",          # blue
    "patientprofile": "#8E24AA",  # purple
    "structuralbio": "#00897B",   # teal
    "pkpd": "#FB8C00",            # orange
    "evidencerag": "#43A047",     # green
    "complianceguard": "#E53935", # red
}
_HUMAN_COLOR = "#757575"  # grey

# Expected pipeline steps in order
_PIPELINE: list[tuple[str, str]] = [
    ("Intake", "intake"),
    ("PatientProfile", "patient_profile"),
    ("StructuralBio", "structural"),
    ("PKPD", "pkpd"),
    ("EvidenceRAG", "evidence"),
    ("ComplianceGuard", "FINAL_VERDICT"),
]

_JSON_FENCE_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _agent_color(sender_name: str) -> str:
    key = (sender_name or "").lower().replace(" ", "").replace("_", "")
    return _AGENT_COLORS.get(key, _HUMAN_COLOR)


def _step_found(step_key: str, messages: list[dict]) -> bool:
    """Return True if any message contains a JSON block with step == step_key."""
    for msg in messages:
        for m in _JSON_FENCE_RE.finditer(msg.get("content", "")):
            try:
                data = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
            if data.get("step") == step_key or data.get("status") == step_key:
                return True
    return False


def _render_bubble(msg: dict) -> None:
    sender = msg.get("sender_name") or msg.get("sender_type") or "Unknown"
    color = _agent_color(sender)
    content = msg.get("content", "")
    ts = msg.get("inserted_at")
    time_str = ts.strftime("%H:%M:%S") if ts and hasattr(ts, "strftime") else ""

    # Truncate very long messages for display
    display_content = content if len(content) <= 1200 else content[:1200] + "\n…[truncated]"

    st.markdown(
        f"""
        <div style="margin:8px 0;padding:10px 14px;border-left:4px solid {color};
                    background:#F8F9FA;border-radius:0 8px 8px 0">
          <div style="font-weight:700;color:{color};margin-bottom:4px">
            {sender}
            <span style="font-weight:400;color:#999;font-size:0.78rem;margin-left:8px">
              {time_str}
            </span>
          </div>
          <pre style="white-space:pre-wrap;word-break:break-word;font-size:0.85rem;
                      margin:0;color:#333;font-family:inherit">{display_content}</pre>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_pipeline_progress(messages: list[dict]) -> None:
    st.subheader("Pipeline Progress")
    cols = st.columns(len(_PIPELINE))
    for i, (label, step_key) in enumerate(_PIPELINE):
        done = _step_found(step_key, messages)
        icon = "✅" if done else "⏳"
        cols[i].markdown(
            f"<div style='text-align:center'>{icon}<br/>"
            f"<span style='font-size:0.8rem;color:#555'>{label}</span></div>",
            unsafe_allow_html=True,
        )


def _fetch_messages() -> list[dict]:
    from orchestrator.band_client import ROOM_ID, fetch_room_messages
    return asyncio.run(fetch_room_messages(ROOM_ID))


def render_workspace_tab() -> None:
    st.header("Agent Workspace")
    st.write("Live transcript of the Sangam Case Room. Messages are polled from Band's REST API.")

    col_refresh, col_auto = st.columns([1, 2])
    with col_refresh:
        manual_refresh = st.button("🔄 Refresh Now", key="ws_refresh")
    with col_auto:
        auto_refresh = st.toggle("Auto-refresh every 5 s", key="ws_auto", value=False)

    # Fetch on manual refresh, or if auto-refresh is on and enough time has passed
    last_fetch: float = st.session_state.get("ws_last_fetch", 0.0)
    should_fetch = manual_refresh or (
        auto_refresh and (time.monotonic() - last_fetch) >= 5.0
    )

    if should_fetch or "room_messages" not in st.session_state:
        with st.spinner("Fetching room messages…"):
            try:
                msgs = _fetch_messages()
                st.session_state["room_messages"] = msgs
                st.session_state["ws_last_fetch"] = time.monotonic()
            except Exception as exc:
                err = str(exc)
                if "BAND_USER_API_KEY" in err or "not set" in err.lower():
                    st.error(
                        "⚠️ **Agents offline / API key missing.** "
                        "Set `BAND_USER_API_KEY` in `.env` and restart Streamlit.",
                        icon="🔌",
                    )
                else:
                    st.error(f"Could not fetch room messages: {exc}", icon="❌")
                st.session_state["room_messages"] = []

    messages: list[dict] = st.session_state.get("room_messages", [])

    if not messages:
        st.info(
            "No messages yet — or agents are offline. "
            "Start all agents with `bash scripts/start_agents.sh`, "
            "then submit a case from the **Case Submission** tab.",
            icon="💬",
        )
    else:
        _render_pipeline_progress(messages)
        st.divider()
        st.subheader(f"Transcript ({len(messages)} messages)")

        # Show all messages; newest are at the bottom (chronological order from band_client)
        for msg in messages:
            _render_bubble(msg)

        # Auto-scroll hint
        st.markdown(
            "<div id='ws-bottom'></div>"
            "<script>document.getElementById('ws-bottom').scrollIntoView();</script>",
            unsafe_allow_html=True,
        )

    # Schedule next auto-refresh by triggering a rerun after 5 s
    if auto_refresh:
        time.sleep(5)
        st.rerun()
