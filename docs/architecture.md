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
  - `THENVOI_REST_URL=https://app.band.ai/`
  - `THENVOI_WS_URL=wss://app.band.ai/api/v1/socket/websocket`
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
- Exact tool name for dynamically adding a human participant
  (`add_participant_service` vs `thenvoi_add_participant`) — Phase 2
  (`@ComplianceGuard` escalation).
- Whether `band-sdk` exposes a generic OpenAI-compatible adapter with a `base_url`
  param for the optional AI/ML API / Featherless stretch — Phase 2/4, optional.

## Design note: induction vs. inhibition in `docking_lookup.json`

The spec's PK heuristic (`inhibition_fraction = clamp((-delta_g - 6) / 4, 0, 0.7)`,
then `ke_patient = ke_baseline * clearance_modifier * (1 - inhibition_fraction)`)
only describes enzyme **inhibition** (lower clearance, higher AUC). Case 4
(Tacrolimus + St. John's Wort) is a CYP3A4 **induction** interaction (higher
clearance, lower AUC) — the opposite direction.

To keep `data/docking_lookup.json` usable for both without redesigning the spec's
tool signatures, each entry now carries a `"mechanism"` field:
`"inhibition" | "induction" | "negligible"`. Planned Phase 2 extension to
`simulate_pk` in `agents/common/pkpd.py`:

- `mechanism == "inhibition"`: use the spec's formula as-is.
- `mechanism == "induction"`: compute the same magnitude via
  `clamp((-delta_g - 6) / 4, 0, 0.7)`, but apply it as
  `ke_patient = ke_baseline * clearance_modifier * (1 + induction_fraction)`
  (clearance increases, AUC decreases).
- `mechanism == "negligible"` (or no docking data at all, e.g. case 3): treat as
  `inhibition_fraction = 0` (no PK-level change); any risk signal for that case
  comes from `@EvidenceRAG` / pharmacodynamic reasoning, not from `simulate_pk`.

This is additive (one extra field + one extra branch) and does not change the
spec's core formula or output schema.
