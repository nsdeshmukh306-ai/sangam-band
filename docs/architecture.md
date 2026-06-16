# Architecture Notes & Spec Verification Log

This file tracks deviations between `PROJECT_SPEC.md`'s assumptions and what was
confirmed against `docs.band.ai` / `api-docs.deepseek.com`, plus design decisions
made while implementing each phase.

## Phase 0 verification results

### Band SDK / platform connection

- **Package**: `band-sdk` (PyPI, v1.0.0, requires Python >=3.11). Install the
  LangGraph integration with `uv add "band-sdk[langgraph]"`. Other extras exist
  (`[anthropic]`, `[crewai]`, `[pydantic-ai]`, etc.) but are not needed here.
- **`langchain-openai`**: not confirmed as a *direct* dependency of `band-sdk`, but
  the quickstart example imports `langchain_openai.ChatOpenAI` directly, so it is
  installed explicitly in `pyproject.toml` rather than relying on it being pulled in
  transitively.
- **Connection URLs** (confirmed defaults, safe to put in `.env.example` since they
  are not secrets):
  - REST: `https://app.band.ai` (no trailing slash)
  - WS: `wss://app.band.ai/api/v1/socket/websocket`
  - These are `band.Agent.create`'s own default parameter values (verified Phase 1
    by inspecting the installed package), so `.env.example` now leaves
    `BAND_REST_URL`/`BAND_WS_URL` blank/optional rather than hardcoding them — see
    "Phase 1 verification results" below.
- **Agent credentials**: `agent_id` + `api_key` per agent, loaded from
  `agent_config.yaml` (confirmed structure matches Section 6.2 of the spec exactly).
- **`BAND_USER_API_KEY`**: the orchestrator's personal/account-level REST key. The
  exact env var name used by Band's own examples was not confirmed from the docs
  excerpts fetched in Phase 0 — **still [VERIFY AGAINST DOCS] in Phase 3** when
  `orchestrator/band_client.py` is built (check
  `docs.band.ai/getting-started/setup` and `docs.band.ai/api/introduction`).

### DeepSeek

- Base URL confirmed: `https://api.deepseek.com` (OpenAI-compatible).
- **Model deprecation notice**: `deepseek-chat` and `deepseek-reasoner` are
  scheduled for deprecation on **2026-07-24**, after which they map to
  `deepseek-v4-flash` (non-thinking / thinking modes respectively). Since the
  hackathon submission deadline (2026-06-19) is well before that date, the spec's
  original choice of `deepseek-chat` (for most agents) and `deepseek-reasoner` (for
  `@StructuralBio` and `@ComplianceGuard`) remains valid for this build. No code
  change needed; noted here so a future maintainer knows why the model ids might
  look "legacy" after July 2026.

### Remaining [VERIFY AGAINST DOCS] items (deferred to Phase 1-3)

These were not addressed in Phase 0 because they don't affect the repo scaffold or
data files; each will be verified immediately before the relevant implementation
step:

- Exact REST endpoints/auth for listing room messages (`GET /me/chats/{id}/messages`)
  and an agent's own context (`GET /agent/chats/{id}/context`) — Phase 3.
- Whether `band-sdk` exposes a generic OpenAI-compatible adapter with a `base_url`
  param for the optional AI/ML API / Featherless stretch — Phase 2/4, optional.

## Phase 1 verification results — CORRECTED: package namespace is `band`, not `thenvoi`

PROJECT_SPEC.md (Section 3 code example, Section 10) and an earlier docs.band.ai
fetch both assumed the installed package's top-level import namespace was
`thenvoi`. **Live inspection of the actually-installed `band-sdk==1.0.0` package
shows this is wrong**: the importable package is `band`, not `thenvoi`.

```python
import band
band.__file__  # .../.venv/Lib/site-packages/band/__init__.py
# submodules: adapters, agent, cli, client, config, converters, core, docker,
#             integrations, mcp, platform, preprocessing, prompts, runtime, testing
```

Verified imports (all 3 Phase 1 agents now use these):

```python
from band import Agent
from band.adapters import LangGraphAdapter
from band.config import load_agent_config
```

(`from band.adapters import LangGraphAdapter` works despite `dir(band.adapters)`
only listing `TYPE_CHECKING`/`annotations` — it's a lazily-resolved export.)

Verified signatures:

```python
Agent.create(
    adapter: FrameworkAdapter | SimpleAdapter,
    agent_id: str,
    api_key: str,
    ws_url: str = "wss://app.band.ai/api/v1/socket/websocket",
    rest_url: str = "https://app.band.ai",
    config: AgentConfig | None = None,
    session_config: SessionConfig | None = None,
    contact_config: ContactEventConfig | None = None,
    on_participant_added: ParticipantAddedCallback | None = None,
    on_participant_removed: ParticipantRemovedCallback | None = None,
    preprocessor: Preprocessor | None = None,
) -> Agent

LangGraphAdapter.__init__(
    self, llm=None, checkpointer=None, graph_factory=None, graph=None,
    prompt_template='default', custom_section='', additional_tools=None,
    enable_memory_tools=False, enable_execution_reporting=False,
    history_converter=None, recursion_limit=50, features=None,
    inject_system_prompt=None,
)

load_agent_config(agent_key: str, *, config_path: str | Path | None = None) -> tuple[str, str]
# config_path=None -> reads ./agent_config.yaml (cwd), keyed format matches
# Section 6.2 exactly (agent_id + api_key per top-level key).
```

**Resulting changes**:

- `agents/intake_agent.py`, `agents/patient_profile_agent.py`,
  `agents/structural_agent.py`: fixed `thenvoi` → `band` imports.
- Added `agents/common/runtime.py::create_agent(adapter, agent_key)`, which calls
  `load_agent_config(agent_key)` then `Agent.create(...)`, only passing
  `ws_url`/`rest_url` if `BAND_WS_URL`/`BAND_REST_URL` are set in the environment
  (passing `None` explicitly would override the SDK's correct built-in defaults).
  All 3 agents now use this helper instead of constructing `Agent` directly.
- `.env.example`: renamed `THENVOI_REST_URL`/`THENVOI_WS_URL` → `BAND_REST_URL`/
  `BAND_WS_URL`, left blank/optional (SDK defaults are correct for the production
  Band platform).
- PROJECT_SPEC.md Section 3/10/12 updated to say `band` instead of `thenvoi`
  (see PROJECT_SPEC.md changelog).

### Resolved: human-escalation tool name for `@ComplianceGuard` (Phase 2)

`band.ALL_TOOL_NAMES` / `band.BASE_TOOL_NAMES` / `band.CHAT_TOOL_NAMES` (verified
Phase 1) all include `"band_add_participant"` and `"band_remove_participant"` —
this is the real tool name for the Phase 2 human-escalation feature, replacing the
spec's placeholder `add_participant_service` / `thenvoi_add_participant`. Full set
of chat tool names: `band_send_message`, `band_send_event`, `band_create_chatroom`,
`band_get_participants`, `band_add_participant`, `band_remove_participant`,
`band_lookup_peers`.

## Design note: induction vs. inhibition in `docking_lookup.json`

The spec's PK heuristic (`inhibition_fraction = clamp((-delta_g - 6) / 4, 0, 0.7)`,
then `ke_patient = ke_baseline * clearance_modifier * (1 - inhibition_fraction)`)
only describes enzyme **inhibition** (lower clearance, higher AUC). Case 4
(Tacrolimus + St. John's Wort) is a CYP3A4 **induction** interaction (higher
clearance, lower AUC) — the opposite direction.

To keep `data/docking_lookup.json` usable for both without redesigning the spec's
tool signatures, each entry now carries a `"mechanism"` field:
`"inhibition" | "induction" | "negligible"`. Planned Phase 2 extension to
`simulate_pk` in `agents/common/pkpd.py`, per user direction (2026-06-15):

- Compute a single signed `clearance_change_fraction` from `delta_g_kcal_mol` and
  `mechanism`:
  - `magnitude = clamp((-delta_g - 6) / 4, 0, 0.7)`
  - `mechanism == "inhibition"` -> `clearance_change_fraction = -magnitude`
    (ke decreases, AUC increases -> **toxicity risk**)
  - `mechanism == "induction"` -> `clearance_change_fraction = +magnitude`
    (ke increases, AUC decreases -> **subtherapeutic / efficacy-loss risk**)
  - `mechanism == "negligible"` (or no docking data, e.g. case 3) ->
    `clearance_change_fraction = 0` (no PK-level change); any risk signal for that
    case comes from `@EvidenceRAG` / pharmacodynamic reasoning, not `simulate_pk`.
- Apply uniformly: `ke_patient = ke_baseline * clearance_modifier * (1 + clearance_change_fraction)`.
- `@ComplianceGuard`'s rationale text must distinguish the two risk directions
  (toxicity vs. subtherapeutic) based on the sign of `clearance_change_fraction`,
  not just report a magnitude.
- Case 4 (Tacrolimus + St. John's Wort, `"mechanism": "induction"`) is the
  regression case exercising the positive-fraction / efficacy-loss path; Case 1
  (Warfarin + Guggulu, `"mechanism": "inhibition"`) exercises the negative-fraction
  / toxicity path.

This is additive (one extra field + one extra branch) and does not change the
spec's core formula or output schema.

## Design note: `@ComplianceGuard` risk tier, confidence, and escalation (Phase 2)

**Confidence is categorical (`"high" | "low"`), not the spec's illustrative
`"confidence": 0.82` float.** `@StructuralBio` already reports confidence as
`"high"|"low"` (Section 3.3), and the spec's own escalation trigger ("if
confidence is low") is binary. Asking an LLM to produce a calibrated 0-1 score it
then has to threshold anyway adds noise without adding information for this demo,
so `@ComplianceGuard` reuses the categorical convention:

- `confidence = "high"` if `@StructuralBio.confidence == "high"` (i.e.
  `basis == "lookup"`) OR `@EvidenceRAG` returned at least one `"severity": "high"`
  finding (independent confirmation even when structural data is missing).
- `confidence = "low"` otherwise.

**Risk tier rubric** (`GREEN | YELLOW | RED`), designed to be checkable against
the 5 case studies' `expected_tier`:

- **RED** if any evidence finding has `"severity": "high"`, OR `|auc_pct_change|
  >= 30` with at least one `"moderate"+` finding, OR `@StructuralBio.confidence ==
  "high"` with `|clearance_change_fraction| >= 0.4`.
- **YELLOW** if not RED but there's a plausible interaction: at least one
  `"moderate"` finding, or `10 <= |auc_pct_change| < 30`.
- **GREEN** otherwise.

Verified against `data/case_studies.json` + `data/docking_lookup.json` +
`data/evidence_corpus/*.json`:
- Case 1 (Warfarin+Guggulu): structural confidence high, evidence has `"high"`
  findings -> **RED** (matches `expected_tier`).
- Case 2 (Digoxin+Licorice): same shape -> **RED** (matches).
- Case 3 (Metformin+Karela): structural `basis == "none"` -> confidence low in
  round 1 -> triggers the `@StructuralBio` re-mention (genuine second round);
  Metformin has no CYP/P-gp/albumin docking entry at all, so round 2 still
  produces `basis == "none"` / confidence low; evidence findings are
  `["moderate", "low", "moderate"]` -> **YELLOW** (matches `expected_tier`), but
  confidence is *still* low after round 2 -> triggers the `band_add_participant`
  human-escalation path even though the tier itself is only YELLOW. This is the
  case that exercises **both** halves of the escalation design.
- Case 4 (Tacrolimus+SJW): structural confidence high (`basis: "lookup"`),
  `delta_g=-9.1` induction -> `clearance_change_fraction = +0.7` (clamped) ->
  `|...| >= 0.4` -> **RED** (matches), confidence already high in round 1 so no
  `@StructuralBio` re-mention; RED tier alone triggers human escalation. This is
  the case that exercises the PKPD induction sign convention end-to-end
  (`auc_pct_change < 0`, rationale must say subtherapeutic/efficacy-loss, not
  toxicity).
- Case 5 (Paracetamol+Tulsi): structural confidence high but `mechanism ==
  "negligible"` (`clearance_change_fraction = 0`), evidence findings all `"low"`
  -> **GREEN** (matches), no escalation.

**Human escalation** uses the platform's built-in `band_lookup_peers` /
`band_add_participant` tools (no `additional_tools=` needed — verified Phase 1,
see above). For the demo, add yourself (or a second Band account) to the Sangam
Case Room participants list with a display name containing "Clinician" so
`band_lookup_peers` can find it (per PROJECT_SPEC.md Section 7.3 step 4). If no
such contact is registered, `@ComplianceGuard` is instructed to note this in its
rationale rather than failing.

### Fix (live test, Case 1): the verdict must always be posted (Phase 2 follow-up)

A live Band-room test of Case 1 showed `@ComplianceGuard` correctly reasoning to a
RED tier + "needs human sign-off", then posting **nothing** — it treated sign-off
as a precondition for output rather than part of the output. Original Step 4/5
told it to escalate *then* post a verdict, which let the model end its turn after
the escalation reasoning without ever calling `send_message`.

Fixed by merging the old Step 4 (human escalation) and Step 5 (post verdict) into
a single Step 4 ("ALWAYS post your assessment") with an explicit "staying silent
is always wrong" instruction, and adding a `"status"` field to the verdict JSON:

- `"status": "FINAL_VERDICT"` — GREEN/YELLOW tier with high confidence. Posted
  directly, no escalation.
- `"status": "PENDING_HUMAN_REVIEW"` — RED tier, or confidence still low after
  round 2. Posted in the *same* message as the `@mention` requesting sign-off
  (previously these were sequenced as separate steps, which is what let the model
  stall between them).

To find the human to `@mention` (`send_message` requires >=1 mention — see
`band/runtime/tools.py::SendMessageInput`), `@ComplianceGuard` now calls
`band_get_participants` (returns all current room participants, including humans
already present, e.g. the room owner) first, falling back to
`band_lookup_peers`/`band_add_participant` only if no human is already in the
room. This replaced the original lookup-only approach, which assumed a dedicated
`@Clinician` contact that may not exist — the room owner (e.g. `@Niraj Deshmukh`)
is an acceptable sign-off target for the demo.

A new Step 5 handles the human's reply: an affirmative reply ("approved",
"confirmed", etc.) to a `PENDING_HUMAN_REVIEW` message produces one short
follow-up with `"status": "FINAL_VERDICT"` and a `"human_signoff"` field, reusing
the already-computed risk_tier/confidence/etc. (no re-analysis). This makes the
human-in-the-loop step an explicit, visible part of the transcript — a stronger
Track 3 demo moment than a silent internal gate.

### Root cause found (live test, Case 3): plain-text replies never reach Band

The previous fix above was necessary but not sufficient. A live test on Case 3
showed `@ComplianceGuard` reach a correct conclusion in exactly 1 DeepSeek call and
then post **nothing** — no `send_event`, no error, just `[DONE] ... processed
successfully`. The one time it *had* posted (Case 1), the log showed 2+ DeepSeek
calls with a `band_lookup_peers` tool call in between.

Reading `band/adapters/langgraph.py::on_message`/`_handle_stream_event` confirms
why: the adapter's `astream_events` loop only ever reacts to `on_tool_start` /
`on_tool_end` / `on_tool_error` (and only to emit `Emit.EXECUTION` telemetry, which
isn't even enabled here). There is **no code path that takes the graph's final
plain-text `AIMessage` and posts it to the room**. The *only* way a message
reaches Band is the `band_send_message` tool (`runtime/tools.py:641`,
`SendMessageInput`) — its docstring says outright: "plain text responses won't
reach users." Calling that tool is what performs the POST, as a side effect of
tool execution.

So every agent's "post a single reply containing ... then @mention ..." instruction
has *always* implicitly required a `band_send_message` tool call — `@Intake`,
`@PatientProfile`, `@StructuralBio`, `@PKPD`, and `@EvidenceRAG` all happen to call
at least one domain tool first (`lookup_pubchem`, `compute_pgx_baseline`,
`lookup_docking`, `lookup_pk_params`/`simulate_pk`, `query_evidence`), which forces
a second LangGraph loop iteration -- and the model reliably uses that second
iteration to call `band_send_message`. `@ComplianceGuard` has no required domain
tool, so on simple cases (no `@StructuralBio` re-mention, no participant lookup
needed) its first LLM call produces the whole analysis as plain text and the graph
ends immediately — silently dropped.

**Fix**: `agents/compliance_agent.py`'s system prompt now opens with an explicit
"CRITICAL" paragraph stating the agent has no way to communicate except by calling
`band_send_message`, that plain text is invisible, and that this applies even on
the first/only tool call of a turn. Every "post"/"reply"/"@mention" instruction in
Steps 2, 4, and 5 now explicitly says `band_send_message`. The "stay silent" option
(case-not-ready-yet, or re-mention-with-nothing-new) is preserved but clarified:
silence = no tool call at all, which is a legitimate choice, vs. a short
acknowledgement = an actual `band_send_message` call with brief content.

If `@ComplianceGuard` ever needs `additional_tools=` in a future iteration, this
class of bug (single-LLM-call turns silently dropping output) would re-appear for
any agent whose prompt doesn't force a tool call before its reply — worth keeping
in mind for Phase 3 if any new agent is added without a required domain tool.

## Phase 3 verification results — orchestrator + frontend

### Band REST client for orchestrator

The installed `thenvoi_rest.AsyncRestClient` (re-exported as
`band.client.rest.AsyncRestClient`) is the correct client for human-level (account
owner) REST operations. Verified:

```python
# Post a message as the account owner:
await client.human_api_messages.send_my_chat_message(
    chat_id=room_id,
    message=ChatMessageRequest(
        content="...",  # must include at least one @mention in the text
        mentions=[ChatMessageRequestMentionsItem(id=agent_id, handle="...", name="...")]
    ),
    request_options=DEFAULT_REQUEST_OPTIONS,
)

# List all room messages (newest-first, paginated):
resp = await client.human_api_messages.list_my_chat_messages(
    chat_id=room_id,
    page=1,                     # 1-based
    page_size=100,              # max 100
    message_type="text",        # optional filter: "text"|"tool_call"|"tool_result"|...
    since=<datetime>,           # optional: only messages after this timestamp
)
# resp.data = list[ChatMessage] — fields: id, content, sender_name, sender_type,
#             inserted_at (datetime), message_type, metadata
# resp.meta = ListMyChatMessagesResponseMetadata
#             — fields: page, page_size, total_count, total_pages
```

`ChatMessage.inserted_at` (not `created_at`) is the timestamp field. The API returns
newest-first; `orchestrator/band_client.py:fetch_room_messages` reverses to
chronological order for the frontend.

`BAND_USER_API_KEY` auth confirmed as the correct env var for account-level access.

### History pre-load cap (verified against SDK source)

`band/runtime/oneshot.py:_fetch_history` hardcodes `page=1, page_size=50` when
calling `agent_api_context.get_agent_chat_context`. The agent-context endpoint
returns ONLY messages the agent sent or that @mention the agent (oldest-first).
For a long-running demo room with many accumulated test cases, `page_size=50` can
mean the current case's messages (which would be near page 2 or beyond) are
missing when @ComplianceGuard processes its turn.

**Fix (Phase 3)**: `agents/compliance_agent.py` now includes a custom
`fetch_full_room_context` async tool (via `additional_tools=`) that calls the
human-level `list_my_chat_messages` endpoint with `page_size=100` and full
pagination, returning a complete chronological transcript. The system prompt
instructs @ComplianceGuard to call this tool (no arguments) as its first action
whenever any of the five expected step reports are missing from context.

Note: `fetch_full_room_context` requires `BAND_USER_API_KEY` (the account-level
key already in `.env`), which is available to all agent processes at runtime.

### @mention typo status

A search of all `.py` source files in `agents/` for `nsdeshmuth` returned no
matches — only stale compiled `.pyc` files (pre-existing from an older run)
contained the typo. The current source is clean; `.pyc` files are gitignored and
will be regenerated cleanly on the next run.

### Orchestrator files created (Phase 3)

- `orchestrator/__init__.py` — package marker
- `orchestrator/band_client.py` — async REST helpers: `post_case_message`,
  `fetch_room_messages`, `poll_for_verdict`, `check_room_accessible`
- `orchestrator/run_case.py` — CLI: `uv run python -m orchestrator.run_case --case <id>`

### Frontend created (Phase 3)

- `frontend/app.py` — Streamlit entry point (3 tabs, navy/teal design system)
- `frontend/tabs/consumer.py` — Case Submission tab with traffic-light card
- `frontend/tabs/physician.py` — Physician View with Plotly PK chart + evidence table
- `frontend/tabs/agent_workspace.py` — live Band room transcript + pipeline progress
- `scripts/start_agents.sh` — starts all 6 agent processes with nohup, logs to `logs/`
