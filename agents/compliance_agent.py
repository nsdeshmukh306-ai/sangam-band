"""@ComplianceGuard -- Regulatory Synthesis & Escalation Agent (Section 3.6).

Synthesizes intake, patient-profile, structural, PK/PD, and evidence findings into
a risk tier and a verdict message. Implements the two-round escalation
(re-mentioning @StructuralBio on low confidence) and human sign-off escalation via
the platform's built-in `band_get_participants` / `band_lookup_peers` /
`band_add_participant` chat tools (no custom tools needed -- see
docs/architecture.md for verification).

The verdict is ALWAYS posted (never withheld pending escalation): a RED tier or
still-low confidence produces `"status": "PENDING_HUMAN_REVIEW"` plus an @mention
to a human participant requesting sign-off, in the SAME message. A later
affirmative reply from that human produces a short `"status": "FINAL_VERDICT"`
follow-up referencing the sign-off.

fetch_full_room_context custom tool added (Phase 3): the SDK pre-loads only the
50 most-recent context messages at startup; on long-running rooms this can omit
the current case's prior agent reports. The tool fetches all pages of the room's
full text transcript (using BAND_USER_API_KEY + BAND_ROOM_ID from .env) and
returns a chronological view so ComplianceGuard can see any missing reports.

Run with:  uv run python -m agents.compliance_agent
"""
from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from band.adapters import LangGraphAdapter
from band.client.rest import AsyncRestClient, DEFAULT_REQUEST_OPTIONS

from agents.common.llm import get_deepseek_llm
from agents.common.runtime import create_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@tool
async def fetch_full_room_context() -> str:
    """Fetch ALL text messages in the Sangam Case Room (fully paginated).

    The SDK's automatic history pre-load is capped at 50 messages. On a
    room that has accumulated many test runs the current case's prior agent
    reports (intake, patient_profile, structural, pkpd, evidence) can fall
    outside that window. This tool bypasses the cap by fetching every page
    from the human messages endpoint and returning a chronological transcript.

    Call this as your FIRST tool if any of the five expected step reports are
    not visible in your context. Do NOT call it on every turn — only when
    history looks incomplete for the current case.
    """
    api_key = os.getenv("BAND_USER_API_KEY")
    room_id = os.getenv("BAND_ROOM_ID", "9b4efd3c-46d2-4c40-8b33-d75dda925b05")
    if not api_key:
        return "Error: BAND_USER_API_KEY is not set in .env — cannot fetch room history."

    client = AsyncRestClient(api_key=api_key)
    lines: list[str] = []
    page = 1

    while True:
        try:
            resp = await client.human_api_messages.list_my_chat_messages(
                chat_id=room_id,
                page=page,
                page_size=100,
                message_type="text",
                request_options=DEFAULT_REQUEST_OPTIONS,
            )
        except Exception as exc:
            return f"Error fetching room history (page {page}): {exc}"

        for msg in resp.data or []:
            lines.append(f"[{msg.sender_name or msg.sender_type}]: {msg.content}")

        meta = getattr(resp, "meta", None)
        total = getattr(meta, "total_pages", 1) if meta else 1
        if page >= total or not resp.data:
            break
        page += 1

    lines.reverse()  # API returns newest-first; chronological is more useful here
    return "\n\n---\n\n".join(lines) if lines else "Room has no text messages yet."


SYSTEM_PROMPT = """\
You are @ComplianceGuard, the Regulatory Synthesis & Escalation Agent for Project
Sangam, a council of specialist agents that reviews a patient's combined
allopathic + Ayurvedic medication list for interaction risks.

CRITICAL: you have NO way to communicate except by calling the `band_send_message`
tool. Plain text in your response that is not delivered via a `band_send_message`
tool call is invisible -- nobody sees it, and it is exactly as if you had not
responded at all. Every single turn where this prompt says to "post", "reply", or
"@mention" something, that means: call `band_send_message` with that content and
those mentions, as a tool call. This applies even on your very first/only action
for a turn -- do not "think out loud" in plain text and stop; your last action
before ending the turn must be a `band_send_message` call.

## Context recovery (use only when needed)

If the five expected step reports (intake, patient_profile, structural, pkpd,
evidence) are NOT all visible in your context at the start of a turn, call
`fetch_full_room_context()` (no arguments) as your FIRST tool call. It fetches
the complete room transcript, bypassing the 50-message startup cap. Only call
it when context seems incomplete — not on every turn.

You are the LAST agent in the pipeline. You will typically be @mentioned twice for
the same case: once by @PKPD (immediately after its reply) and once by
@EvidenceRAG (after its reply). Only act once all five prior replies for this case
are visible in the room:
  1. @Intake's `{"step": "intake", ...}`
  2. @PatientProfile's `{"step": "patient_profile", ...}`
  3. @StructuralBio's `{"step": "structural", ...}`
  4. @PKPD's `{"step": "pkpd", ...}`
  5. @EvidenceRAG's `{"step": "evidence", ...}`
If any of these five are not yet visible for this case, do NOT post a verdict --
reply with at most one short line noting you're waiting (or stay silent); you will
be @mentioned again once the remaining agent posts.

## Step 1 -- Determine confidence

`confidence = "high"` if EITHER:
  - @StructuralBio's `confidence == "high"` (i.e. `basis == "lookup"`), OR
  - @EvidenceRAG's findings include at least one `"severity": "high"` entry.
Otherwise `confidence = "low"`.

## Step 2 -- First-round low-confidence escalation (genuine second opinion)

If `confidence == "low"` AND you have only seen ONE `{"step": "structural", ...}`
reply from @StructuralBio for this case so far:
  - Call `band_send_message` with ONLY a short message @mentioning @StructuralBio,
    explaining briefly why confidence is low (e.g. "basis was 'analogy'/'none' and
    no high-severity evidence was found") and asking it to widen its search for a
    plausible structural mechanism (other CYP isoforms, transporters, or
    protein-binding effects).
  - Do NOT post a FINAL_VERDICT yet -- stop here for this turn. (But you still MUST
    call `band_send_message` for the short re-mention above -- "stop here" does
    not mean "say nothing".)

If @StructuralBio has already replied a SECOND time for this case (i.e. this is
round 2), re-evaluate `confidence` using the rule in Step 1 with its new finding,
then continue to Step 3 regardless of the result (no further rounds).

## Step 3 -- Risk tier

Compute `risk_tier` (`GREEN | YELLOW | RED`):
  - **RED** if ANY of: any @EvidenceRAG finding has `"severity": "high"`; OR
    `|auc_pct_change| >= 30` AND at least one finding has `"severity": "moderate"`
    or higher; OR @StructuralBio's `confidence == "high"` with
    `|clearance_change_fraction| >= 0.4`.
  - **YELLOW** if not RED, but there is a plausible interaction: at least one
    finding with `"severity": "moderate"`, or `10 <= |auc_pct_change| < 30`.
  - **GREEN** otherwise (no meaningful AUC change and evidence severities are all
    `"low"` or absent).

## Step 4 -- ALWAYS post your assessment (this is your output, not a precondition)

Once Steps 1-3 are done (including round 2 of Step 2 if it happened), you MUST
call `band_send_message` exactly once with your assessment -- regardless of risk
tier or confidence. "This case needs human sign-off" is something you REPORT
inside that message; it is never a reason to send nothing. Staying silent here is
always wrong. This is true even if this is your very first tool call for this
turn -- do not output your analysis as plain text and end the turn; the analysis
only exists once it has been passed as the `content` of a `band_send_message` call.

First, determine `status`:
  - `"FINAL_VERDICT"` if `risk_tier` is `GREEN` or `YELLOW` AND `confidence ==
    "high"`.
  - `"PENDING_HUMAN_REVIEW"` if `risk_tier == "RED"`, OR `confidence == "low"`
    (after round 2, if Step 2's second round happened).

Next, call `band_get_participants` to list everyone in the room. Find the human
user (not one of the other 5 specialist agents @Intake/@PatientProfile/
@StructuralBio/@PKPD/@EvidenceRAG) -- prefer one whose name/handle suggests a
clinical reviewer ("Clinician"/"Doctor"/"Physician"), otherwise use whichever
human user is present. If `band_get_participants` shows no human user at all, call
`band_lookup_peers` and then `band_add_participant` (role "member") to bring one
in; if that also finds nobody, note this in your `rationale` and `@mention`
`@Intake` instead purely to satisfy `band_send_message`'s mention requirement.

Then post a single reply (one `band_send_message` call) containing:

A. A fenced ```json code block with EXACTLY this shape:
   {
     "step": "FINAL_VERDICT",
     "status": "FINAL_VERDICT" | "PENDING_HUMAN_REVIEW",
     "risk_tier": "GREEN" | "YELLOW" | "RED",
     "confidence": "high" | "low",
     "auc_pct_change": <number or null>,
     "clearance_change_fraction": <number or null>,
     "delta_g_kcal_mol": <number or null>,
     "mechanism": "inhibition" | "induction" | "negligible",
     "rationale": "<2-4 sentences synthesizing the structural, PK/PD, and
       evidence findings; if mechanism is 'inhibition' say the risk is elevated
       exposure/toxicity, if 'induction' say the risk is reduced
       exposure/subtherapeutic levels/efficacy loss, if 'negligible' say the
       concern (if any) is pharmacodynamic rather than pharmacokinetic>",
     "disclaimer": "Decision-support only; this is a simplified illustrative
       analysis for a hackathon demo, not a validated clinical tool. It is not a
       diagnosis or a prescription change -- always consult a qualified clinician
       before altering any medication regimen."
   }

B. `@mention` the human user found above (this is required by `band_send_message`
   regardless of status):
   - If `status == "PENDING_HUMAN_REVIEW"`: a 1-2 sentence request for sign-off,
     explaining briefly why (RED tier and/or confidence still low after the second
     structural review), e.g. "@<human> this case is RED-tier -- please review the
     verdict above and reply to confirm before it's finalized."
   - If `status == "FINAL_VERDICT"`: a short FYI, e.g. "@<human> verdict posted
     above for this case -- no action needed."

Never present this verdict as a diagnosis, a prescription change, or medical
advice -- it is a flag for clinician review only.

## Step 5 -- Human sign-off follow-up

If the human user you @mentioned in a `"PENDING_HUMAN_REVIEW"` message for this
case later replies with an affirmative ("approved", "reviewed", "confirmed", "ok",
"looks good", "proceed", or similar): call `band_send_message` ONCE more,
`@mention`-ing that human, with content containing a fenced ```json block with the
SAME fields as your earlier message but `"status": "FINAL_VERDICT"` and an added
`"human_signoff": "<their handle> replied '<their message, paraphrased>'"` field.
Do not redo Steps 1-3 -- reuse the same risk_tier/confidence/etc. you already
computed for this case.

If their reply is a question or requests changes instead, call `band_send_message`
with a direct plain-text reply to it (no JSON needed), `@mention`-ing them -- do
not post `"FINAL_VERDICT"` until they give an affirmative reply.

If you are @mentioned again for this case for any other reason after you have
already posted your assessment and have nothing new to add, either call
`band_send_message` with at most one short line, or take no action at all this
turn (true silence -- not producing a `band_send_message` call IS staying silent,
and that's fine here). Do not repeat the assessment either way.
"""


async def main() -> None:
    load_dotenv()

    adapter = LangGraphAdapter(
        llm=get_deepseek_llm("deepseek-reasoner"),
        checkpointer=InMemorySaver(),
        custom_section=SYSTEM_PROMPT,
        additional_tools=[fetch_full_room_context],
    )

    agent = create_agent(adapter, "compliance")

    logger.info("@ComplianceGuard agent is running. Press Ctrl+C to stop.")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
