"""@PKPD -- Quantitative Systems Pharmacology Agent (Section 3.4).

Looks up curated one-compartment oral PK parameters for the case's drug, runs the
baseline-vs-combined simulation (applying @PatientProfile's clearance_modifier and
@StructuralBio's delta_g_kcal_mol/mechanism), and hands off to @EvidenceRAG and
@ComplianceGuard.

Run with:  uv run python -m agents.pkpd_agent
"""
from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from agents.common.adapter import FreshGraphAdapter as LangGraphAdapter

from agents.common.llm import get_deepseek_llm
from agents.common.pkpd import lookup_pk_params as _lookup_pk_params
from agents.common.pkpd import simulate_pk as _simulate_pk
from agents.common.runtime import create_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@tool
async def fetch_pipeline_context() -> str:
    """Fetch the full recent room transcript to find all prior agents' step reports.

    Call this as your FIRST action when the current message does not already
    contain BOTH @PatientProfile's {"step":"patient_profile",...} and
    @StructuralBio's {"step":"structural",...} reports.  Returns a
    chronological transcript of all room messages (newest agents first).
    """
    from orchestrator.band_client import fetch_room_messages

    room_id = os.getenv("BAND_ROOM_ID", "9b4efd3c-46d2-4c40-8b33-d75dda925b05")
    try:
        msgs = await fetch_room_messages(room_id=room_id)
    except Exception as exc:
        return f"Error fetching room context: {exc}"
    if not msgs:
        return "No messages in room yet."
    lines = [
        f"[{m.get('sender_name','?')}]: {m.get('content','')}"
        for m in msgs[-30:]
    ]
    return "\n\n---\n\n".join(lines)


@tool
def lookup_pk_params(drug_compound: str) -> dict:
    """Look up curated one-compartment oral PK parameters (dose_mg, ka_per_hr,
    ke_baseline_per_hr, v_l) for a drug, from data/case_studies.json.

    Args:
        drug_compound: The drug's canonical compound name as used by @Intake,
            e.g. "Warfarin", "Tacrolimus", "Digoxin", "Metformin", "Acetaminophen".
    """
    return _lookup_pk_params(drug_compound)


@tool
def simulate_pk(
    dose_mg: float,
    ka_per_hr: float,
    ke_baseline_per_hr: float,
    v_l: float,
    clearance_modifier: float,
    delta_g_kcal_mol: float | None = None,
    mechanism: str = "negligible",
) -> dict:
    """Run a one-compartment oral PK simulation comparing baseline vs. combined
    (with the herb's effect) kinetics, and return the % AUC change.

    `clearance_modifier` comes from @PatientProfile's pharmacogenomic baseline.
    `delta_g_kcal_mol` and `mechanism` come from @StructuralBio's structural
    finding ("inhibition" | "induction" | "negligible"; pass mechanism="negligible"
    and delta_g_kcal_mol=null if @StructuralBio reported "basis": "none").

    Sign convention: "inhibition" lowers ke (AUC increases -> toxicity risk);
    "induction" raises ke (AUC decreases -> subtherapeutic/efficacy-loss risk).

    Returns clearance_change_fraction, auc_baseline, auc_combined,
    auc_pct_change, and a concentration_curve (list of {t_hr, c_baseline,
    c_combined}) for the Physician dashboard chart.
    """
    return _simulate_pk(
        dose_mg=dose_mg,
        ka_per_hr=ka_per_hr,
        ke_baseline_per_hr=ke_baseline_per_hr,
        v_l=v_l,
        clearance_modifier=clearance_modifier,
        delta_g_kcal_mol=delta_g_kcal_mol,
        mechanism=mechanism,
    )


SYSTEM_PROMPT = """\
You are @PKPD, the Quantitative Systems Pharmacology Agent for Project Sangam, a
council of specialist agents that reviews a patient's combined allopathic +
Ayurvedic medication list for interaction risks.

CRITICAL: The ONLY way to communicate is by calling the `band_send_message` tool.
Any plain text you write that is not inside a `band_send_message` call is completely
invisible — no one will ever see it. You MUST call `band_send_message` with your
reply; outputting your analysis as plain text and stopping is always wrong.

CONTEXT RECOVERY — MANDATORY FIRST STEP:
Before doing ANYTHING else, call `fetch_pipeline_context()` to load the full
recent room transcript. Then:

1. Find the `run_id` for THIS case: look in the current triggering message for
   `"run_id": "XXXXXXXX"` in a `"step":"patient_profile"` or `"step":"structural"`
   block. That 8-character hex string is the run_id for this pipeline run.

2. From the transcript, collect ONLY messages whose JSON contains that SAME
   `"run_id"`. Look for:
   - A `"step": "patient_profile"` block with matching `run_id`
   - A `"step": "structural"` block with matching `run_id`
   - A `"step": "intake"` block with matching `run_id`

3. If EITHER patient_profile or structural is absent (wrong run_id or missing):
   → STOP IMMEDIATELY. Call NO further tools. Do NOT call band_send_message.
   The missing agent will post soon and @mention you again.
   → NEVER post a partial result without both reports matching the run_id.

Only proceed to the steps below when BOTH "step":"patient_profile" AND
"step":"structural" with the SAME run_id are visible in the transcript.

For every new case, once @PatientProfile's `{"step": "patient_profile", ...}` and
@StructuralBio's `{"step": "structural", ...}` replies are both visible:

1. Call `lookup_pk_params` with the case's drug compound (from @Intake's
   `{"step": "intake", ...}` reply) to get dose_mg, ka_per_hr, ke_baseline_per_hr,
   and v_l. If it returns `{"status": "no_data", ...}`, say so explicitly instead
   of guessing values, and skip step 2 (omit `auc_pct_change`/`concentration_curve`
   from your output, both null).
2. Call `simulate_pk` with those PK parameters, @PatientProfile's
   `clearance_modifier`, and @StructuralBio's `delta_g_kcal_mol`/`mechanism`
   (use `mechanism="negligible"` and `delta_g_kcal_mol=null` if @StructuralBio's
   `basis` was "none").

Sign convention (state this in your rationale, do not just report a number):
- `mechanism == "inhibition"`: ke decreases, AUC increases -> elevated exposure,
  **toxicity risk**.
- `mechanism == "induction"`: ke increases, AUC decreases -> reduced exposure,
  **subtherapeutic / efficacy-loss risk**.
- `mechanism == "negligible"` or no PK data: no PK-level change expected from this
  mechanism; any risk for this case is pharmacodynamic, not pharmacokinetic.

Then call `band_send_message` exactly once with a message containing ONLY the
following two things, in order:

A. A fenced ```json code block with EXACTLY this shape:
   {
     "step": "pkpd",
     "run_id": "<same run_id from the patient_profile and structural blocks>",
     "auc_pct_change": <number or null>,
     "clearance_change_fraction": <number or null>,
     "auc_baseline": <number or null>,
     "auc_combined": <number or null>,
     "concentration_curve": [{"t_hr": ..., "c_baseline": ..., "c_combined": ...}, ...] or null,
     "rationale": "<1-3 sentences stating the direction of risk (toxicity vs.
       subtherapeutic vs. none) and why, per the sign convention above>"
   }

B. On its own line, exactly: "@EvidenceRAG @ComplianceGuard please continue the
   assessment."

This is a simplified illustrative one-compartment PK model for a hackathon demo,
not validated for clinical decisions -- never present these numbers as a clinical
recommendation.

If you are @mentioned again for this case after you have already called
`band_send_message` for this case and have nothing new to add, stay silent.
"""


async def main() -> None:
    load_dotenv()

    adapter = LangGraphAdapter(
        llm=get_deepseek_llm("deepseek-reasoner"),
        checkpointer=InMemorySaver(),
        additional_tools=[fetch_pipeline_context, lookup_pk_params, simulate_pk],
        custom_section=SYSTEM_PROMPT,
    )

    agent = create_agent(adapter, "pkpd")

    logger.info("@PKPD agent is running. Press Ctrl+C to stop.")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
