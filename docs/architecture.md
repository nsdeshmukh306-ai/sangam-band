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
