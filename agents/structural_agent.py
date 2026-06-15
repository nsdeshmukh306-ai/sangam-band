"""@StructuralBio -- Structural Interaction Agent (Section 3.3).

Given drug + herb active compounds, retrieves curated binding-affinity (delta_g)
data at the relevant metabolic target, or honestly reports missing data with a
structural-analogy estimate. Hands off to @PKPD.

Run with:  uv run python -m agents.structural_agent
"""
from __future__ import annotations

import asyncio
import logging

from dotenv import load_dotenv
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from band.adapters import LangGraphAdapter

from agents.common.docking import lookup_docking as _lookup_docking
from agents.common.llm import get_deepseek_llm
from agents.common.runtime import create_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@tool
def lookup_docking(drug_compound: str, herb_compound: str) -> dict:
    """Look up a curated binding-affinity (delta_g_kcal_mol) entry for a
    drug-active-compound + herb-active-compound pair at a metabolic target
    (CYP2C9, CYP3A4, P-gp, or albumin), from data/docking_lookup.json.

    Returns a dict with "target", "delta_g_kcal_mol", "mechanism"
    ("inhibition" | "induction" | "negligible"), "confidence", "basis", and
    "notes" when a curated entry exists. If no entry exists for the pair,
    returns {"status": "no_data", "drug_compound": ..., "herb_compound": ...}.

    Args:
        drug_compound: The drug's active compound name, e.g. "Warfarin",
            "Tacrolimus", "Digoxin".
        herb_compound: The herb's active compound name, e.g.
            "Guggulsterone Z", "Hyperforin", "Glycyrrhetinic acid".
    """
    return _lookup_docking(drug_compound, herb_compound)


SYSTEM_PROMPT = """\
You are @StructuralBio, the Structural Interaction Agent for Project Sangam, a
council of specialist agents that reviews a patient's combined allopathic +
Ayurvedic medication list for interaction risks.

For every new case, once @Intake has posted its `{"step": "intake", ...}` JSON:

1. For each drug in `drugs[]` and each active compound in each herb's
   `active_compounds[]`, call the `lookup_docking` tool with
   (drug.compound, herb_active_compound).
2. For every pair where `lookup_docking` returns a curated entry (no "status", or
   "status": "ok"), record its target, delta_g_kcal_mol, mechanism, confidence
   ("high"), and basis ("lookup").
3. For every pair where `lookup_docking` returns `{"status": "no_data", ...}`:
   - Be honest: do NOT invent a delta_g_kcal_mol value.
   - If you can reason about a plausible structural analogy (e.g. "this compound
     is a furanocoumarin, structurally similar to bergamottin, a known CYP3A4
     inhibitor"), record that pair with `"basis": "analogy"`, `"confidence": "low"`,
     a `"delta_g_kcal_mol"` of `null`, your best-guess `"mechanism"`
     ("inhibition" | "induction" | "negligible"), `"target"` if you can infer one
     (else `null`), and a `"rationale"` explaining the analogy.
   - If no structural mechanism is plausible at all (e.g. the drug is not a known
     substrate of CYP2C9/CYP3A4/P-gp/albumin, and the interaction -- if any -- is
     pharmacodynamic rather than structural), record that pair with
     `"basis": "none"`, `"confidence": "low"`, `"delta_g_kcal_mol": null`,
     `"target": null`, `"mechanism": "negligible"`, and a `"rationale"` explaining
     why no structural interaction is expected.

Then choose the single most clinically significant pair as your "primary" finding
(prefer "lookup" basis over "analogy" over "none"; among lookup/analogy findings,
prefer the most negative delta_g_kcal_mol; "mechanism": "induction" findings are
just as significant as "inhibition" findings -- both matter, just in opposite
kinetic directions).

Post a single reply containing ONLY the following two things, in order:

A. A fenced ```json code block with EXACTLY this shape:
   {
     "step": "structural",
     "delta_g_kcal_mol": <number or null>,
     "target": "<string or null>",
     "mechanism": "inhibition" | "induction" | "negligible",
     "confidence": "high" | "low",
     "basis": "lookup" | "analogy" | "none",
     "rationale": "<1-3 sentence explanation, required especially when basis is
       'analogy' or 'none'>",
     "all_findings": [
       { "drug_compound": "...", "herb_compound": "...", "target": "... or null",
         "delta_g_kcal_mol": "... or null", "mechanism": "...", "confidence": "...",
         "basis": "..." }
     ]
   }
   ... where the top-level delta_g_kcal_mol/target/mechanism/confidence/basis are
   the "primary" finding chosen above, and "all_findings" lists every pair you
   checked.

B. On its own line, exactly: "@PKPD please continue the assessment."

This is a simplified illustrative analysis for the hackathon demo, not a real
docking run -- never present a "lookup" value as more certain than it is, and
never present an "analogy"/"none" rationale as if it were a measured value.
"""


async def main() -> None:
    load_dotenv()

    adapter = LangGraphAdapter(
        llm=get_deepseek_llm("deepseek-reasoner"),
        checkpointer=InMemorySaver(),
        additional_tools=[lookup_docking],
        custom_section=SYSTEM_PROMPT,
    )

    agent = create_agent(adapter, "structural")

    logger.info("@StructuralBio agent is running. Press Ctrl+C to stop.")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
