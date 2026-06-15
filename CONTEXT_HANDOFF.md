# Sangam — Session Handoff (end of Day 1, June 15, 2026)

Project: "Project Sangam" — Band of Agents Hackathon (lablab.ai), Track 3
(Regulated & High-Stakes Workflows). Submission deadline: **June 19, 2026**
(3 days remaining after today). Repo: `github.com/nsdeshmukh306-ai/sangam-band`
(public, MIT licensed, contains `PROJECT_SPEC.md` and `PROMPTS.md`).

This file is the "pick up here" status doc. `PROJECT_SPEC.md` (in the repo,
updated through Phase 2) remains the architectural source of truth — this
file summarizes what's actually been *built and proven live* vs. what's left.

---

## 1. Current status: Phases 0-2 complete and validated live on Band

**Stack confirmed working**: 6 agents, each its own process, using
`band-sdk[langgraph]` (PyPI package `band`, import as `band`/`thenvoi` per
SDK — see note below) → `LangGraphAdapter` → `ChatOpenAI` pointed at DeepSeek
(`base_url="https://api.deepseek.com"`, models `deepseek-chat` /
`deepseek-reasoner`). Band room: **"Sangam Case Room"**,
`https://app.band.ai/chat/9b4efd3c-46d2-4c40-8b33-d75dda925b05`.

Local environment: WSL2 Ubuntu (hostname `NSD306`), repo at
`~/sangam-band`, `uv` package manager, Python 3.12. `agent_config.yaml` and
`.env` are filled in locally (gitignored) with the 6 agents' UUID/API key
pairs and `DEEPSEEK_API_KEY`.

### How to run everything (6 terminals from `~/sangam-band`)
```bash
uv run python -m rag.build_index        # one-time, before EvidenceRAG
uv run python -m agents.intake_agent
uv run python -m agents.patient_profile_agent
uv run python -m agents.structural_agent
uv run python -m agents.pkpd_agent
uv run python -m agents.evidence_rag_agent
uv run python -m agents.compliance_agent
```
All 6 must be `cd ~/sangam-band` first (a common gotcha — WSL tabs often
open in `/mnt/c/Users/...`).

---

## 2. Two cases fully validated end-to-end, live, on real DeepSeek calls

**Case 1 (Warfarin 5mg + Guggulu 500mg, 68F, CYP2C9 *1/*3, eGFR 55)**
→ `FINAL_VERDICT`: `risk_tier: RED`, `confidence: high`, `auc_pct_change: 150.0`,
`delta_g_kcal_mol: -8.4`, `mechanism: inhibition`, `escalated_to_clinician: true`.
Clean single-pass: Intake → PatientProfile + StructuralBio (parallel) → PKPD →
EvidenceRAG → ComplianceGuard. Good rationale, proper disclaimer.

**Case 3 (Metformin 500mg + Karela juice 100mL, 55F, CYP2C9 *1/*1, eGFR 75)**
→ `FINAL_VERDICT`: `status: PENDING_HUMAN_REVIEW`, `risk_tier: YELLOW`,
`confidence: low`, `auc_pct_change: 0.0`, `mechanism: negligible`. This one
exercised the **full two-round escalation**: StructuralBio first reported
"negligible/no_data" (correctly — Metformin isn't a CYP/P-gp/albumin
substrate). ComplianceGuard, on low confidence, `@mentioned @StructuralBio`
asking it to widen to OCT/MATE transporters. StructuralBio gave an honest
"low-confidence speculation" (charantin as sterol glycoside, possible
transporter modulation). EvidenceRAG re-queried for OCT/MATE literature,
found none. ComplianceGuard synthesized: PK ruled out (0% AUC), real risk is
pharmacodynamic (additive hypoglycemia, moderate-severity case reports). This
is the **stronger demo case** — shows discovery, re-tasking, honest
uncertainty, and synthesis across PK vs PD reasoning.

**Not yet tested**: human sign-off reply ("approved"/"confirmed" →
`FINAL_VERDICT` + `human_signoff` follow-up) — logic is built (Step 5 of
ComplianceGuard), just needs a live reply to confirm. Also Cases 4
(Tacrolimus+St. John's Wort, induction mechanism, expect
`auc_pct_change ≈ -41%`, RED) and 5 (Paracetamol+Tulsi, GREEN/negligible,
should be a clean no-escalation pass) are unrun.

---

## 3. Key bugs found and fixed (don't re-discover these)

1. **Import namespace**: package is `band-sdk`, imports as `band` (not
   `thenvoi` as early docs/spec assumed). Fixed in Phase 1, documented in
   `docs/architecture.md`.
2. **Env defaults confirmed**: `THENVOI_REST_URL=https://app.band.ai/`,
   `THENVOI_WS_URL=wss://app.band.ai/api/v1/socket/websocket`.
3. **Human escalation tool**: `band_add_participant` / `band_get_participants`
   / `band_lookup_peers` — verified via `band.CHAT_TOOL_NAMES`, no custom
   tool wiring needed.
4. **CRITICAL — silently-dropped responses (fixed)**: the LangGraph
   adapter's `astream_events` loop only posts to Band as a *side effect of
   the `band_send_message` tool call*. A plain-text-only LLM response (no
   tool call) is never relayed — silently dropped, "[DONE] processed
   successfully" with zero Band posts. Agents with a required domain tool
   (e.g. `lookup_pubchem`, `compute_pgx_baseline`) naturally get a 2nd
   LangGraph iteration where `band_send_message` gets called. `ComplianceGuard`
   has no required domain tool, so single-DeepSeek-call turns produced
   nothing. **Fix**: prompt now opens with a "CRITICAL" paragraph stating the
   agent has no way to communicate except `band_send_message`, plain text is
   invisible, even on a turn's first/only action. This class of bug could
   recur for any *future* agent without a required domain tool — keep that
   in mind for Phase 3 if any new agent personas are added.
5. **Persona refinement (all 6 agents)**: "if @mentioned again with nothing
   new to add, reply with ≤1 short line OR make no tool call at all (legit
   silence) — don't restate full analysis." StructuralBio has a carve-out:
   a re-mention from ComplianceGuard asking it to widen search IS new work
   and gets a full second `{"step": "structural", ...}` reply.

### Minor open items (low priority, fix when convenient)
- Typo: ComplianceGuard's final human `@mention` used `@nsdeshmuth306`
  instead of `@nsdeshmukh306` (it also correctly said `@Niraj Deshmukh`
  earlier in the same message, so not blocking, but worth a prompt tweak).
- On Case 3, ComplianceGuard initially claimed it couldn't see
  Intake/PatientProfile/StructuralBio's earlier messages (it self-corrected
  and proceeded anyway). Possibly a room-history loading cap
  (`Got N messages` — worth checking what N is and whether it's enough for a
  6-agent, multi-round case).
- EvidenceRAG's first run (Case 1) needed 2 round-trips asking `@Intake` to
  re-share drug/herb names instead of using room context directly — minor
  inefficiency, self-resolved.

---

## 4. Remaining work (3 days: June 16-19)

**Phase 3 — frontend + orchestrator** (per `PROJECT_SPEC.md` §8-9):
- `orchestrator/band_client.py` + `run_case.py` — post a new case message,
  poll the room transcript for the `FINAL_VERDICT` json block.
- Streamlit app, 3 tabs: Consumer (traffic light + plain summary), Physician
  (PK chart via Plotly, ΔG/AUC numbers), Agent Workspace (live transcript of
  the real Band room — this is the "Application of Technology" showcase).
- Deploy somewhere reachable (Streamlit Community Cloud / small VM — note
  the 6 agent processes also need to run continuously somewhere for the live
  demo, not just locally during dev).

**Validation**:
- Run Cases 4 and 5 through the full 6-agent chain.
- Test the human sign-off reply flow ("approved" → `human_signoff` follow-up).
- Fix the `@mention` typo and check the history-loading question above.

**Optional stretch**: AI/ML API / Featherless partner integration for 1-2
agents (only if time allows — don't let it displace core work).

**Submission assets** (Phase 4): video walkthrough, slide deck, cover image,
README polish, project title/description for lablab.ai submission form.

---

## 5. For a new Claude Code session

Paste this file's content plus:

```
Continue Project Sangam (repo: ~/sangam-band, already cloned, agent_config.yaml
and .env already filled in). Read PROJECT_SPEC.md and docs/architecture.md
for full context, plus this handoff doc for current status.

Phases 0-2 are complete and validated live (Cases 1 and 3 both produced
correct FINAL_VERDICT output through the real Band room with DeepSeek).
Proceed with Phase 3: orchestrator/band_client.py + run_case.py, then the
3-tab Streamlit frontend per PROJECT_SPEC.md §8. Work in the same
phase-by-phase style as before — pause for live testing against the real
Band room (I'll run the 6 agent processes and the Streamlit app locally and
report back, including screenshots/terminal output, since you can't access
Band or the browser directly).

Also on the list when convenient: fix the @mention typo
(@nsdeshmuth306 → @nsdeshmukh306) in compliance_agent.py, and check whether
room-history loading has a cap that caused ComplianceGuard's "I can't see
prior reports" confusion on Case 3.
```

---

## 6. For a new Claude.ai chat (guide role)

Paste this file's content plus:

```
I'm continuing the Band of Agents Hackathon project (Sangam) — see the
attached handoff doc for full status. I'd like you to keep acting as my
step-by-step guide: tell me one concrete thing to do at a time (terminal
commands, Band UI actions, Streamlit testing), I'll do it and send back
terminal output or screenshots, and you tell me what's next. Today's focus
is Phase 3 (frontend/orchestrator) plus validating Cases 4 and 5 and the
human sign-off reply flow.
```

(Memory/context from our prior conversation — the architecture decisions,
DeepSeek switch, debugging history — should carry over via Claude's memory
of past conversations, but this doc plus the prompt above ensures a clean
resume even in a fresh chat.)
