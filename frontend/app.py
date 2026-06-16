"""Sangam — Cross-System Polypharmacy Safety Council | Streamlit Frontend.

Run with:
    streamlit run frontend/app.py

Three tabs:
  1. Case Submission  — consumer-facing traffic-light result
  2. Physician View   — structured output + PK chart + evidence table
  3. Agent Workspace  — live Band room transcript with pipeline progress
"""
from __future__ import annotations

import os
import sys

# Ensure repo root is on sys.path so agents/, orchestrator/, rag/ are importable
# when Streamlit is launched from any directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(override=True)

import streamlit as st

st.set_page_config(
    page_title="Sangam — Polypharmacy Safety Council",
    page_icon="⚕️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Design system: deep navy headings, teal accents (see PROJECT_SPEC.md Section 8)
st.markdown(
    """
    <style>
    h1, h2, h3 { color: #0B2545 !important; }
    .stTabs [data-baseweb="tab"] { font-weight: 600; font-size: 0.95rem; }
    .stTabs [data-baseweb="tab-highlight"] { background-color: #2EC4B6 !important; }
    div[data-testid="metric-container"] > label { color: #0B2545; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    "# ⚕️ Sangam — Cross-System Polypharmacy Safety Council",
)
st.markdown(
    "A council of six AI agents reviews combined allopathic + Ayurvedic medication "
    "lists for drug-herb interaction risks and produces a clinician-reviewable verdict. "
    "**For decision-support and research demonstration only — not a clinical tool.**"
)

# Initialise session state defaults
for key, default in [
    ("verdict", None),
    ("case_data", None),
    ("room_messages", None),
    ("pk_result", None),
    ("evidence_findings", []),
    ("analysis_error", None),
    ("room_ok", None),
    ("ws_last_fetch", 0.0),
]:
    if key not in st.session_state:
        st.session_state[key] = default

tab1, tab2, tab3 = st.tabs(
    ["🔍 Case Submission", "🩺 Physician View", "🤖 Agent Workspace"]
)

with tab1:
    from frontend.tabs.consumer import render_consumer_tab
    render_consumer_tab()

with tab2:
    from frontend.tabs.physician import render_physician_tab
    render_physician_tab()

with tab3:
    from frontend.tabs.agent_workspace import render_workspace_tab
    render_workspace_tab()
