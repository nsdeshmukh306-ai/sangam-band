"""Tab 2 — Physician View.

Shows the full structured verdict, a Plotly PK concentration-time chart
(baseline vs. combined), and the evidence findings table.
"""
from __future__ import annotations

import json
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st
from orchestrator.band_client import run_async

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "case_studies.json"

_SEVERITY_COLOR = {"high": "#FF4B4B", "moderate": "#FFB100", "low": "#21C354"}


def _load_case_by_id(case_id: str) -> dict | None:
    with open(DATA_PATH, encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    for c in cases:
        if c["id"] == case_id:
            return c
    return None


def _pk_chart(curve: list[dict]) -> go.Figure:
    times = [p["t_hr"] for p in curve]
    baseline = [p["c_baseline"] for p in curve]
    combined = [p["c_combined"] for p in curve]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=times, y=baseline,
            name="Baseline (drug alone)",
            line=dict(color="#2EC4B6", width=2.5),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=times, y=combined,
            name="Combined (+ herb)",
            line=dict(color="#FF4B4B", width=2.5, dash="dot"),
        )
    )
    fig.update_layout(
        title="Plasma Concentration-Time (one-compartment, illustrative)",
        xaxis_title="Time (h)",
        yaxis_title="Concentration (mg/L)",
        template="plotly_white",
        legend=dict(x=0.6, y=0.95),
        margin=dict(l=40, r=20, t=50, b=40),
        height=380,
    )
    return fig


def _severity_badge(sev: str) -> str:
    color = _SEVERITY_COLOR.get(sev.lower(), "#888")
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:10px;font-size:0.82rem">{sev.upper()}</span>'


def render_physician_tab() -> None:
    st.header("Physician View")

    verdict: dict | None = st.session_state.get("verdict")
    case_data: dict | None = st.session_state.get("case_data")

    if not verdict:
        st.info(
            "No verdict available yet. Run a case from the **Case Submission** tab first.",
            icon="🩺",
        )
        return

    # --- Structured verdict metrics ---
    st.subheader("Verdict Summary")
    cols = st.columns(4)
    tier = verdict.get("risk_tier", "—")
    cols[0].metric("Risk Tier", tier)
    cols[1].metric("Confidence", str(verdict.get("confidence", "—")).capitalize())
    auc = verdict.get("auc_pct_change")
    cols[2].metric("AUC Change", f"{auc:+.1f}%" if auc is not None else "N/A")
    dg = verdict.get("delta_g_kcal_mol")
    cols[3].metric("ΔG (kcal/mol)", f"{dg:.2f}" if dg is not None else "N/A")

    mech = verdict.get("mechanism", "—")
    ccf = verdict.get("clearance_change_fraction")
    st.markdown(
        f"**Mechanism:** `{mech}` &nbsp;|&nbsp; "
        f"**Clearance change fraction:** `{ccf:+.3f}`" if ccf is not None
        else f"**Mechanism:** `{mech}`"
    )
    if verdict.get("rationale"):
        st.markdown(f"> {verdict['rationale']}")

    st.divider()

    # --- PK Chart ---
    st.subheader("PK Concentration-Time Curve")

    curve = None

    # Try to get curve from session state (stored after run) or recompute
    if st.session_state.get("pk_result"):
        pk = st.session_state["pk_result"]
        curve = pk.get("concentration_curve")

    if curve is None and case_data and dg is not None:
        # Recompute: use the case's pk_params + patient profile + verdict's dg/mechanism
        try:
            from agents.common.pkpd import simulate_pk
            from agents.common.pgx import compute_pgx_baseline

            patient = case_data.get("patient", {})
            pgx = compute_pgx_baseline(
                age=patient.get("age", 40),
                egfr=patient.get("egfr", 90),
                cyp2c9_genotype=patient.get("cyp2c9_genotype", "*1/*1"),
                cyp3a4_status=patient.get("cyp3a4_status", "normal"),
            )
            cm = pgx.get("clearance_modifier", 1.0) if pgx.get("status") == "ok" else 1.0
            pk_params = case_data.get("pk_params", {})
            pk = simulate_pk(
                dose_mg=pk_params.get("dose_mg", 5),
                ka_per_hr=pk_params.get("ka_per_hr", 1.0),
                ke_baseline_per_hr=pk_params.get("ke_baseline_per_hr", 0.02),
                v_l=pk_params.get("v_l", 10),
                clearance_modifier=cm,
                delta_g_kcal_mol=dg,
                mechanism=mech,
            )
            curve = pk.get("concentration_curve")
            st.session_state["pk_result"] = pk
        except Exception as exc:
            st.warning(f"Could not compute PK curve: {exc}")

    if curve:
        st.plotly_chart(_pk_chart(curve), use_container_width=True)
        st.caption(
            "⚠️ Simplified illustrative one-compartment PK model — "
            "not validated for clinical decisions."
        )
    else:
        st.info(
            "PK curve unavailable. Run a case from Case Submission to populate this chart.",
            icon="📉",
        )

    st.divider()

    # --- Evidence Findings ---
    st.subheader("Evidence Findings")

    # Pull evidence from room messages if available
    findings: list[dict] = []

    if st.button("🔄 Fetch latest evidence from room", key="fetch_evidence"):
        with st.spinner("Fetching room transcript…"):
            try:
                from orchestrator.band_client import fetch_room_messages, ROOM_ID
                import re, json as _json

                msgs = run_async(fetch_room_messages(ROOM_ID))
                fence_re = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
                for m in msgs:
                    if (m.get("sender_name") or "").lower() != "evidencerag":
                        continue
                    for match in fence_re.finditer(m.get("content", "")):
                        try:
                            data = _json.loads(match.group(1))
                            if data.get("step") == "evidence":
                                findings = data.get("findings", [])
                        except Exception:
                            pass
                st.session_state["evidence_findings"] = findings
            except Exception as exc:
                st.error(f"Could not fetch room messages: {exc}")

    findings = st.session_state.get("evidence_findings", findings)

    if findings:
        import pandas as pd

        df = pd.DataFrame(
            [
                {
                    "Severity": f["severity"].upper(),
                    "Summary": f["summary"],
                    "Citation": f.get("citation", "—"),
                }
                for f in findings
            ]
        )

        def _color_severity(val: str):
            colors = {"HIGH": "background-color:#FF4B4B;color:white",
                      "MODERATE": "background-color:#FFB100;color:white",
                      "LOW": "background-color:#21C354;color:white"}
            return colors.get(val, "")

        styled = df.style.applymap(_color_severity, subset=["Severity"])
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.info(
            "Click **Fetch latest evidence from room** to load @EvidenceRAG's findings.",
            icon="📚",
        )

    if verdict.get("disclaimer"):
        st.divider()
        st.caption(f"⚕️ {verdict['disclaimer']}")
