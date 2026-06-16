"""@EvidenceRAG -- Translational Evidence Agent (Section 3.5).

Retrieves curated clinical literature findings for the case's drug-herb pair via a
local ChromaDB similarity search over data/evidence_corpus/*.json, then hands off
to @ComplianceGuard.

The index must be built first (and rebuilt whenever data/evidence_corpus/
changes):  uv run python -m rag.build_index

Run with:  uv run python -m agents.evidence_rag_agent
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
from agents.common.rag import query_evidence as _query_evidence
from agents.common.runtime import create_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@tool
async def fetch_pipeline_context() -> str:
    """Fetch the full recent room transcript to find all prior agents' step reports.

    Call this as your FIRST action to locate @Intake's {"step":"intake",...} report
    so you can extract the drug+herb pair needed for `query_evidence`.
    Returns a chronological transcript of the last 30 room messages.
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
def query_evidence(drug: str, herb: str) -> list[dict]:
    """Retrieve the most relevant curated clinical-literature findings for a
    drug + herb pair via similarity search over data/evidence_corpus/*.json.

    Returns a list of {"summary", "citation", "severity", "drug", "herb"} dicts
    (most relevant first), or [] if the index hasn't been built yet.

    Args:
        drug: The drug's canonical compound name, e.g. "Tacrolimus", "Warfarin".
        herb: The herb's common name, e.g. "St. John's Wort", "Guggulu".
    """
    return _query_evidence(drug, herb)


SYSTEM_PROMPT = """\
You are @EvidenceRAG, the Translational Evidence Agent for Project Sangam, a
council of specialist agents that reviews a patient's combined allopathic +
Ayurvedic medication list for interaction risks.

CRITICAL: The ONLY way to communicate is by calling the `band_send_message` tool.
Any plain text you write that is not inside a `band_send_message` call is completely
invisible — no one will ever see it. You MUST call `band_send_message` with your
reply; outputting your analysis as plain text and stopping is always wrong.

CONTEXT RECOVERY: Call `fetch_pipeline_context()` as your FIRST tool call. This
loads the recent room transcript. Then:
1. Find the `run_id` from the current triggering message (look for `"run_id"` in
   the `"step":"pkpd"` block or any other agent block in the message).
2. From the transcript, find @Intake's `"step":"intake"` block with the SAME
   `run_id` — that gives you the drug's canonical compound name and herb's
   common name.
Do NOT guess drug/herb names — always read them from @Intake's JSON for the same run_id.

For every new case, once @Intake's `{"step": "intake", ...}` reply is visible:

1. For each drug + herb pair in the case, call `query_evidence` with the drug's
   canonical compound name and the herb's common name (as written in the original
   case message, e.g. "St. John's Wort", "Guggulu", "Karela").
2. If `query_evidence` returns `[]` (no index built, or genuinely no matching
   evidence), say so explicitly -- do not invent citations or summaries.

Then call `band_send_message` exactly once with a message containing ONLY the
following two things, in order:

A. A fenced ```json code block with EXACTLY this shape:
   {
     "step": "evidence",
     "run_id": "<same run_id from the intake block for this case>",
     "findings": [
       {"summary": "...", "citation": "...", "severity": "low" | "moderate" | "high"}
     ]
   }
   ... where "findings" is the list returned by `query_evidence` (drop the
   "drug"/"herb" fields), or `[]` if none were found.

B. On its own line, exactly: "@ComplianceGuard please continue the assessment."

Do not add any other commentary, diagnosis, or recommendation. Never present a
paraphrased summary as a verbatim quotation.

If you are @mentioned again for this case after you have already called
`band_send_message` for this case and have nothing new to add, stay silent.
"""


async def main() -> None:
    load_dotenv()

    adapter = LangGraphAdapter(
        llm=get_deepseek_llm("deepseek-reasoner"),
        checkpointer=InMemorySaver(),
        additional_tools=[fetch_pipeline_context, query_evidence],
        custom_section=SYSTEM_PROMPT,
    )

    agent = create_agent(adapter, "evidence_rag")

    logger.info("@EvidenceRAG agent is running. Press Ctrl+C to stop.")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
