"""Tab 1 — Case Submission (Consumer-facing).

Dropdown to select one of the 5 case studies, "Run Analysis" button, live spinner,
and a traffic-light result card (RED/YELLOW/GREEN) once the verdict arrives.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import streamlit as st

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "case_studies.json"

_TIER_BG = {"RED": "#FF4B4B", "YELLOW": "#FFB100", "GREEN": "#21C354"}
_TIER_ICON = {"RED": "🔴", "YELLOW": "🟡", "GREEN": "🟢"}
_TIER_LABEL = {
    "RED": "High Risk — Clinician review strongly recommended",
    "YELLOW": "Moderate Risk — Clinician review advised",
    "GREEN": "Low Risk — No significant interaction detected",
}


def _load_cases() -> list[dict]:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)["cases"]


def _run_analysis(case_id: str) -> dict | None:
    """Synchronous wrapper: post case + poll for verdict.  Blocks until done."""
    from orchestrator.band_client import ROOM_ID, poll_for_verdict, post_case_message

    async def _inner():
        posted_at = await post_case_message(
            _load_case_by_id(case_id)["sample_message"], room_id=ROOM_ID
        )
        return await poll_for_verdict(
            room_id=ROOM_ID, posted_at=posted_at, timeout_s=120.0, poll_interval_s=3.0
        )

    return asyncio.run(_inner())


def _load_case_by_id(case_id: str) -> dict:
    for case in _load_cases():
        if case["id"] == case_id:
            return case
    raise KeyError(case_id)


def _verdict_card(verdict: dict) -> None:
    tier = verdict.get("risk_tier", "UNKNOWN")
    bg = _TIER_BG.get(tier, "#888888")
    icon = _TIER_ICON.get(tier, "⚪")
    label = _TIER_LABEL.get(tier, tier)
    rationale = verdict.get("rationale", "")
    disclaimer = verdict.get("disclaimer", "")
    status = verdict.get("status", "FINAL_VERDICT")

    st.markdown(
        f"""
        <div style="background:{bg};border-radius:12px;padding:24px 28px;color:white;">
          <div style="font-size:3rem;line-height:1">{icon}</div>
          <h2 style="color:white;margin:8px 0 4px 0">{label}</h2>
          <p style="font-size:1.05rem;margin:0">{rationale}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if status == "PENDING_HUMAN_REVIEW":
        st.warning(
            "⚠️ **Pending Clinician Sign-off** — @ComplianceGuard has flagged this "
            "case for human review. Check the Agent Workspace tab for details.",
            icon="⚠️",
        )

    cols = st.columns(3)
    with cols[0]:
        st.metric("Risk Tier", tier)
    with cols[1]:
        auc = verdict.get("auc_pct_change")
        st.metric("AUC Change", f"{auc:+.1f}%" if auc is not None else "N/A")
    with cols[2]:
        conf = verdict.get("confidence", "—")
        st.metric("Confidence", str(conf).capitalize())

    if disclaimer:
        st.caption(f"⚕️ {disclaimer}")


def render_consumer_tab() -> None:
    st.header("Case Submission")
    st.write("Select a pre-loaded demo case or enter a free-text description.")

    cases = _load_cases()
    case_labels = {c["id"]: f"{c['title']} (expected: {c['expected_tier']})" for c in cases}

    col_left, col_right = st.columns([1, 2])

    with col_left:
        mode = st.radio("Input mode", ["Demo case", "Free text"], horizontal=True)

    if mode == "Demo case":
        case_id = st.selectbox(
            "Select case",
            options=list(case_labels.keys()),
            format_func=lambda k: case_labels[k],
        )
        selected_case = _load_case_by_id(case_id)
        with st.expander("Case details"):
            st.json(
                {
                    "drugs": selected_case["drugs"],
                    "herbs": selected_case["herbs"],
                    "patient": selected_case["patient"],
                    "mechanism": selected_case["mechanism"],
                }
            )
        message_to_post = selected_case["sample_message"]
    else:
        case_id = None
        selected_case = None
        message_to_post = st.text_area(
            "Case description",
            placeholder="@Intake @PatientProfile New case: 68F on Warfarin 5mg once daily…",
            height=120,
        )

    # Check room connectivity once
    if "room_ok" not in st.session_state:
        try:
            from orchestrator.band_client import check_room_accessible, ROOM_ID
            st.session_state["room_ok"] = asyncio.run(check_room_accessible(ROOM_ID))
        except Exception:
            st.session_state["room_ok"] = False

    if not st.session_state.get("room_ok"):
        st.error(
            "⚠️ **Cannot reach Band room.** Check that `BAND_USER_API_KEY` is set "
            "in `.env` and you are connected to the internet.",
            icon="🔌",
        )

    run_disabled = not message_to_post or not st.session_state.get("room_ok", True)
    if st.button("▶ Run Analysis", type="primary", disabled=run_disabled):
        st.session_state["verdict"] = None
        st.session_state["case_data"] = selected_case
        st.session_state["analysis_error"] = None

        if case_id:
            with st.spinner(
                f"Agents are analysing **{case_labels[case_id]}**… "
                "(up to 120 s — watch the Agent Workspace tab for live updates)"
            ):
                try:
                    verdict = _run_analysis(case_id)
                except Exception as exc:
                    st.session_state["analysis_error"] = str(exc)
                    verdict = None
        else:
            st.warning(
                "Free-text submission: posting your message to the room. "
                "Note that the case ID used for PK chart lookup will be unavailable.",
                icon="ℹ️",
            )
            from orchestrator.band_client import ROOM_ID, poll_for_verdict, post_case_message

            async def _post_free():
                posted_at = await post_case_message(message_to_post, room_id=ROOM_ID)
                return await poll_for_verdict(ROOM_ID, posted_at=posted_at)

            with st.spinner("Posting case to Band room…"):
                try:
                    verdict = asyncio.run(_post_free())
                except Exception as exc:
                    st.session_state["analysis_error"] = str(exc)
                    verdict = None

        if verdict:
            st.session_state["verdict"] = verdict
        elif not st.session_state.get("analysis_error"):
            st.session_state["analysis_error"] = (
                "No verdict received within 120 s. "
                "Are all 6 agent processes running? Run: bash scripts/start_agents.sh"
            )

    # --- Display result ---
    if st.session_state.get("analysis_error"):
        st.error(st.session_state["analysis_error"], icon="❌")

    if st.session_state.get("verdict"):
        st.divider()
        st.subheader("Result")
        _verdict_card(st.session_state["verdict"])
        with st.expander("Raw verdict JSON"):
            st.json(st.session_state["verdict"])
    elif not st.session_state.get("analysis_error"):
        st.info(
            "Select a case and click **▶ Run Analysis** to start the agent council.",
            icon="ℹ️",
        )
