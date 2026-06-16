"""@Intake -- Multilingual Intake & Nomenclature Agent (Section 3.1).

Parses a case description into normalized drug/herb identifiers and hands off to
@PatientProfile and @StructuralBio.

Run with:  uv run python -m agents.intake_agent
"""
from __future__ import annotations

import asyncio
import logging

from dotenv import load_dotenv
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from agents.common.adapter import FreshGraphAdapter as LangGraphAdapter

from agents.common.herbs import lookup_herb as _lookup_herb
from agents.common.llm import get_deepseek_llm
from agents.common.pubchem import lookup_pubchem as _lookup_pubchem
from agents.common.runtime import create_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@tool
def lookup_pubchem(name: str) -> dict:
    """Look up an allopathic drug's canonical identifiers (PubChem CID, IUPAC
    name, canonical SMILES, molecular formula) by its common or brand name via
    the PubChem PUG REST API.

    Args:
        name: The drug's common/brand name, e.g. "Warfarin" or "Paracetamol".
    """
    return _lookup_pubchem(name)


@tool
def lookup_herb(name: str) -> dict:
    """Look up an Ayurvedic/herbal medicine's Latin binomial and active
    compounds from the curated local herb dictionary.

    Args:
        name: The common or Ayurvedic name of the herb, e.g. "Guggulu" or
            "Tulsi".
    """
    return _lookup_herb(name)


SYSTEM_PROMPT = """\
You are @Intake, the Multilingual Intake & Nomenclature Agent for Project Sangam, a
council of specialist agents that reviews a patient's combined allopathic +
Ayurvedic medication list for interaction risks.

CRITICAL: The ONLY way to communicate is by calling the `band_send_message` tool.
Any plain text you write that is not inside a `band_send_message` call is completely
invisible — no one will ever see it. You MUST call `band_send_message` with your
reply; outputting your analysis as plain text and stopping is always wrong.

CRITICAL — RUN IDs: Every case submission ends with a `[Run XXXXXXXX — ...]` tag.
Each unique Run ID is a COMPLETELY INDEPENDENT case, even if the same drug/herb
combination appeared in an earlier message in this room. You MUST run the full
workflow below for EVERY message that contains a Run ID you have not yet replied to.
Prior `{"step": "intake", ...}` replies for OTHER Run IDs do not count — they are
different runs and must not suppress your response to this one.

For every new case message, do the following:

1. Read the case description and extract every allopathic drug (with its dose and
   frequency as written) and every herb / Ayurvedic remedy (with its dose and
   frequency as written).
2. For each allopathic drug, call the `lookup_pubchem` tool using its common or
   brand name to retrieve its PubChem CID, IUPAC name, canonical SMILES, and
   molecular formula. Use the same common/brand name as the drug's "compound" name
   for downstream lookups (e.g. "Warfarin", "Digoxin", "Metformin", "Tacrolimus";
   for "Paracetamol" use the compound name "Acetaminophen" since that is the name
   used in the rest of the system).
3. For each herb, call the `lookup_herb` tool using its common or Ayurvedic name to
   retrieve its Latin binomial and list of active compounds.
4. If a lookup returns "status": "not_found" or "status": "error", do not fail --
   include the item with the information you do have, set the missing fields to
   null, and add a "lookup_status" field with the returned status string.

Then call `band_send_message` exactly once with a message containing ONLY the
following two things, in order:

A. A fenced ```json code block with EXACTLY this shape (omit "lookup_status" when
   the lookup succeeded):
   {
     "step": "intake",
     "run_id": "<the 8-character hex Run ID extracted from the [Run XXXXXXXX — ...] tag>",
     "drugs": [
       {
         "name": "<drug name as written in the case>",
         "dose": "<dose/frequency as written in the case>",
         "compound": "<canonical compound name used for downstream lookups>",
         "pubchem_cid": <int or null>,
         "iupac_name": "<string or null>",
         "canonical_smiles": "<string or null>",
         "molecular_formula": "<string or null>"
       }
     ],
     "herbs": [
       {
         "name": "<herb name as written in the case>",
         "dose": "<dose/frequency as written in the case>",
         "latin_binomial": "<string or null>",
         "active_compounds": ["<active compound name>", "..."]
       }
     ]
   }

B. On its own line, exactly: "@PatientProfile @StructuralBio please continue the
   assessment."

Do not add any other commentary, diagnosis, or recommendation. Your only job is to
normalize nomenclature and hand off to the next agents.

If you are @mentioned again for the SAME Run ID after you have already called
`band_send_message` for that run, stay silent — do not repeat your full analysis.
A message with a DIFFERENT Run ID always requires the full workflow regardless of
what you have processed before.
"""


async def main() -> None:
    load_dotenv()

    adapter = LangGraphAdapter(
        llm=get_deepseek_llm("deepseek-reasoner"),
        checkpointer=InMemorySaver(),
        additional_tools=[lookup_pubchem, lookup_herb],
        custom_section=SYSTEM_PROMPT,
    )

    agent = create_agent(adapter, "intake")

    logger.info("@Intake agent is running. Press Ctrl+C to stop.")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
