# Project Sangam — Cross-System Polypharmacy Safety Council

> "Sangam" = confluence. A council of specialist AI agents, coordinating through
> [Band](https://band.ai), that reviews a patient's combined allopathic +
> Ayurvedic medication list and produces a clinician-reviewable polypharmacy
> safety verdict.

Built for the **Band of Agents Hackathon** (lablab.ai), Track 3: Regulated &
High-Stakes Workflows. Full design spec: [`PROJECT_SPEC.md`](PROJECT_SPEC.md).
Verification log / deviations from the spec: [`docs/architecture.md`](docs/architecture.md).

## Status

- [x] **Phase 0** — Repo scaffold, data files (5 case studies + supporting lookups)
- [x] **Phase 1** — Core agents (`@Intake`, `@PatientProfile`, `@StructuralBio`)
- [x] **Phase 2** — Reasoning agents + escalation loop (`@PKPD`, `@EvidenceRAG`, `@ComplianceGuard`)
- [ ] Phase 3 — Frontend + orchestrator
- [ ] Phase 4 — Submission assets

## Repository layout

```
data/                  curated case studies, herb/PGx/docking lookups, evidence corpus
agents/                one Python process per Band agent + shared "common" logic
rag/                   ChromaDB index builder for @EvidenceRAG
orchestrator/          REST client + CLI to drive a case through the Band room
frontend/              Streamlit app (Consumer / Physician / Agent Workspace tabs)
scripts/               helper scripts to launch all 6 agent processes
tests/                 unit tests for non-agent logic (PK/PD, PGx, docking, etc.)
docs/                  architecture notes, Band setup guide, submission assets
```

## Setup

1. **Python 3.11** and [`uv`](https://docs.astral.sh/uv/) package manager.
2. Install dependencies:
   ```bash
   uv sync
   ```
3. Copy the example env/config files and fill in your real values (never commit
   the originals — both are gitignored):
   ```bash
   cp .env.example .env
   cp agent_config.example.yaml agent_config.yaml
   ```
   - `.env` needs `DEEPSEEK_API_KEY` (from platform.deepseek.com) and, once you've
     done the Band manual setup below, `BAND_USER_API_KEY` / `BAND_ROOM_ID`.
   - `agent_config.yaml` needs the `agent_id` + `api_key` for each of the 6
     External Agents you create on Band.
4. **Band platform setup** (manual, ~30 min) — see `PROJECT_SPEC.md` Section 7:
   create a Band account, register the 6 External Agents
   (`Intake`, `PatientProfile`, `StructuralBio`, `PKPD`, `EvidenceRAG`,
   `ComplianceGuard`), and create the "Sangam Case Room" with all 6 as
   participants.

## Running tests

```bash
uv run pytest
```

33 tests cover the PGx rules, docking lookup, herb dictionary, PubChem wrapper,
PK/PD model, and RAG retrieval (all runnable without live Band/DeepSeek
credentials).

## Building the evidence index (Phase 2, do this once)

`@EvidenceRAG` needs a local ChromaDB index built from `data/evidence_corpus/*.json`
before it can answer. Rebuild it whenever that directory changes:

```bash
uv run python -m rag.build_index
```

## Running the agents

Each agent is its own long-running process, started from the repo root (so
`agents.common.*` imports resolve) with `.env` and `agent_config.yaml` already
filled in:

```bash
uv run python -m agents.intake_agent
uv run python -m agents.patient_profile_agent
uv run python -m agents.structural_agent
uv run python -m agents.pkpd_agent
uv run python -m agents.evidence_rag_agent
uv run python -m agents.compliance_agent
```

To test, open the "Sangam Case Room" on Band (with all 6 registered agents as
participants — see Section 7.3 of `PROJECT_SPEC.md` for the manual setup,
including optionally adding yourself as a `@Clinician` participant for the
escalation demo) and post Case 1's sample message:

```
@Intake @PatientProfile New case: 68F on Warfarin 5mg once daily (CYP2C9 *1/*3,
CYP3A4 normal, eGFR 55) has started taking Guggulu 500mg twice daily for
cholesterol. Please assess for interactions.
```

Expected behavior:
- `@Intake` replies with a ` ```json {"step": "intake", ...} ``` ` block (Warfarin +
  Guggulu resolved via PubChem/herb dictionary) and `@PatientProfile @StructuralBio
  please continue the assessment.`
- `@PatientProfile` replies with `{"step": "patient_profile", "clearance_modifier":
  ~0.41, "risk_flags": [...]}` and `@PKPD please continue the assessment.`
- `@StructuralBio` replies with `{"step": "structural", "delta_g_kcal_mol": -8.4,
  "target": "CYP2C9", "mechanism": "inhibition", ...}` and `@PKPD please continue
  the assessment.`
- `@PKPD` replies with `{"step": "pkpd", "auc_pct_change": 150.0,
  "clearance_change_fraction": -0.6, ...}` (AUC *increases* -> toxicity risk) and
  `@EvidenceRAG @ComplianceGuard please continue the assessment.`
- `@EvidenceRAG` replies with `{"step": "evidence", "findings": [...]}` (citations
  from `data/evidence_corpus/warfarin_guggulu.json`) and `@ComplianceGuard please
  continue the assessment.`
- `@ComplianceGuard` replies with `{"step": "FINAL_VERDICT", "status":
  "PENDING_HUMAN_REVIEW", "risk_tier": "RED", "confidence": "high", ...}` in the
  same message as an `@mention` to the human participant in the room (looked up
  via `band_get_participants`/`band_lookup_peers`/`band_add_participant`) asking
  for sign-off. Reply as that human with e.g. "approved" — `@ComplianceGuard`
  should then post one short follow-up with `"status": "FINAL_VERDICT"` and a
  `"human_signoff"` field referencing your reply.

Try Case 4 (Tacrolimus + St. John's Wort, in `data/case_studies.json`) too — it
should produce `"mechanism": "induction"` from `@StructuralBio`,
`"clearance_change_fraction": 0.7` / `"auc_pct_change": -41.2` (AUC *decreases* ->
subtherapeutic/efficacy-loss risk) from `@PKPD`, and `"status":
"PENDING_HUMAN_REVIEW"` / `"risk_tier": "RED"` from `@ComplianceGuard`.

Case 3 (Metformin + Karela, `"basis": "none"` from `@StructuralBio`) exercises the
two-round escalation: `@ComplianceGuard` will first re-mention `@StructuralBio`
asking it to widen its search, then -- once `@StructuralBio` posts a second
finding (still `"basis": "none"`, since Metformin has no relevant docking entry) --
post `{"step": "FINAL_VERDICT", "status": "PENDING_HUMAN_REVIEW", "risk_tier":
"YELLOW", "confidence": "low", ...}` and `@mention` the human for sign-off despite
the YELLOW tier, because confidence remained low after the second round.

## Data files (Phase 0)

- `data/case_studies.json` — 5 demo cases spanning GREEN/YELLOW/RED, each with a
  ready-to-paste `sample_message` for the Band room.
- `data/herb_dictionary.json` — Ayurvedic/herbal name → Latin binomial + active
  compounds, used by `@Intake`'s `lookup_herb` tool.
- `data/docking_lookup.json` — illustrative ΔG binding-affinity lookup for
  `@StructuralBio`, including an explicit `"no_data"` case (Metformin + Karela) to
  exercise the honest-reporting path.
- `data/pgx_rules.json` — rule-based genotype/eGFR/age → clearance modifier table for
  `@PatientProfile`.
- `data/evidence_corpus/*.json` — short, team-written paraphrased literature summaries
  + citations per case, for `@EvidenceRAG`.

## License

MIT — see [`LICENSE`](LICENSE).
