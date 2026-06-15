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
- [ ] Phase 2 — Reasoning agents + escalation loop (`@PKPD`, `@EvidenceRAG`, `@ComplianceGuard`)
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

18 tests cover the PGx rules, docking lookup, herb dictionary, and PubChem wrapper
(all runnable without live Band/DeepSeek credentials). Phase 2 will add tests for
the PK/PD model and RAG retrieval.

## Running the agents (Phase 1)

Each agent is its own long-running process, started from the repo root (so
`agents.common.*` imports resolve) with `.env` and `agent_config.yaml` already
filled in:

```bash
uv run python -m agents.intake_agent
uv run python -m agents.patient_profile_agent
uv run python -m agents.structural_agent
```

To test, open the "Sangam Case Room" on Band (with all 6 registered agents as
participants — `@PKPD`, `@EvidenceRAG`, `@ComplianceGuard` won't be running yet,
which is fine) and post Case 1's sample message:

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

Try Case 4 (Tacrolimus + St. John's Wort, in `data/case_studies.json`) too — it
should produce `"mechanism": "induction"` from `@StructuralBio` instead of
`"inhibition"`.

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
