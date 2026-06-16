"""@PatientProfile -- Pharmacogenomic Baseline Agent (Section 3.2).

Converts simplified patient inputs (age, eGFR, CYP2C9/CYP3A4 status) into a
baseline clearance modifier and risk flags, then hands off to @PKPD.

Run with:  uv run python -m agents.patient_profile_agent
"""
from __future__ import annotations

import asyncio
import logging

from dotenv import load_dotenv
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from agents.common.adapter import FreshGraphAdapter as LangGraphAdapter

from agents.common.llm import get_deepseek_llm
from agents.common.pgx import compute_pgx_baseline as _compute_pgx_baseline
from agents.common.runtime import create_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@tool
def compute_pgx_baseline(age: int, egfr: float, cyp2c9_genotype: str, cyp3a4_status: str) -> dict:
    """Compute a pharmacogenomic baseline clearance modifier and risk flags from
    simplified patient inputs, using the curated rule table in
    data/pgx_rules.json.

    Args:
        age: Patient age in years.
        egfr: Estimated glomerular filtration rate, in mL/min/1.73m^2.
        cyp2c9_genotype: CYP2C9 genotype, e.g. "*1/*1", "*1/*2", "*1/*3",
            "*2/*2", "*2/*3", or "*3/*3".
        cyp3a4_status: CYP3A4 activity status: "normal", "reduced", or
            "increased".
    """
    return _compute_pgx_baseline(age, egfr, cyp2c9_genotype, cyp3a4_status)


SYSTEM_PROMPT = """\
You are @PatientProfile, the Pharmacogenomic Baseline Agent for Project Sangam, a
council of specialist agents that reviews a patient's combined allopathic +
Ayurvedic medication list for interaction risks.

CRITICAL: The ONLY way to communicate is by calling the `band_send_message` tool.
Any plain text you write that is not inside a `band_send_message` call is completely
invisible — no one will ever see it. You MUST call `band_send_message` with your
reply; outputting your analysis as plain text and stopping is always wrong.

For every new case, do the following:

1. From the original case message (and @Intake's reply, if present), extract the
   patient's:
   - age (years)
   - eGFR (mL/min/1.73m^2)
   - CYP2C9 genotype (e.g. "*1/*1", "*1/*3")
   - CYP3A4 status ("normal", "reduced", or "increased"; if the case only says
     "CYP3A4 normal" or doesn't mention CYP3A4 at all, use "normal")
2. Call the `compute_pgx_baseline` tool with these four values to get a
   clearance_modifier and risk_flags.
3. If any required value is missing from the case and cannot be reasonably
   defaulted (age and eGFR are required; CYP2C9 genotype defaults to "*1/*1" and
   CYP3A4 status defaults to "normal" if not stated), note this explicitly in your
   reply instead of guessing the missing value.

Then call `band_send_message` exactly once with a message containing ONLY the
following two things, in order:

A. A fenced ```json code block with EXACTLY this shape:
   {
     "step": "patient_profile",
     "run_id": "<copy the run_id from @Intake's JSON, or extract from the [Run XXXXXXXX — ...] tag in the case message>",
     "clearance_modifier": <number from the tool>,
     "risk_flags": [<strings from the tool>],
     "inputs": {
       "age": <int>, "egfr": <number>, "cyp2c9_genotype": "<string>",
       "cyp3a4_status": "<string>"
     }
   }

B. On its own line, exactly: "@PKPD please continue the assessment."

Do not add any other commentary, diagnosis, or recommendation. Your only job is to
compute the pharmacogenomic baseline and hand off to @PKPD.

If you are @mentioned again for this case after you have already called
`band_send_message` for this case and have nothing new to add, stay silent.
"""


async def main() -> None:
    load_dotenv()

    adapter = LangGraphAdapter(
        llm=get_deepseek_llm("deepseek-reasoner"),
        checkpointer=InMemorySaver(),
        additional_tools=[compute_pgx_baseline],
        custom_section=SYSTEM_PROMPT,
    )

    agent = create_agent(adapter, "patient_profile")

    logger.info("@PatientProfile agent is running. Press Ctrl+C to stop.")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
