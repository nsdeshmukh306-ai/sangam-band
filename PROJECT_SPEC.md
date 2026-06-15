# Project Sangam — Cross-System Polypharmacy Safety Council
**Band of Agents Hackathon (lablab.ai) — Track 3: Regulated & High-Stakes Workflows**
Deadline: **June 19, 2026** (submission). Today: June 15, 2026. ~4 days remaining.

> "Sangam" = confluence. The product is a council of specialist AI agents, coordinating
> through **Band**, that reviews a patient's combined allopathic + Ayurvedic medication
> list and produces a clinician-reviewable polypharmacy safety verdict — live, visible,
> and auditable.

This document is the single source of truth for the build. Claude Code should treat
this file as the spec and work through it phase by phase (see Section 9). Anything
marked **[VERIFY AGAINST DOCS]** must be checked against `docs.band.ai` before
implementation, because exact endpoint/parameter names may differ slightly from what's
described here.

---

## 1. Why this design (hackathon alignment)

- **Application of Technology**: All 6 agents are real Band "External Agents" running
  in a shared chat room, coordinating via `@mention` routing (sequential + parallel +
  dynamic patterns). The compliance agent can re-open the conversation (escalation
  loop) and dynamically add a human reviewer participant — this is "task state +
  coordination," not a one-pass pipeline.
- **Presentation**: The "Agent Workspace" tab in the frontend renders the **real Band
  room transcript** (via the messages API), so judges see the actual coordination, not
  a simulated log.
- **Business Value**: Ayurvedic + allopathic co-prescription is extremely common in
  India and under-monitored for interactions. This is a real enterprise/clinical
  workflow problem (hospital pharmacy / e-pharmacy compliance teams, insurers,
  telemedicine platforms).
- **Originality**: Multi-round debate + dynamic escalation to a human "@Clinician"
  participant when confidence is low — goes beyond chatbot/linear automation.

---

## 2. System overview

```
                         ┌────────────────────────────┐
                         │   Streamlit Frontend        │
                         │  (Consumer / Physician /    │
                         │   Agent Workspace tabs)     │
                         └──────────────┬───────────────┘
                                        │ POST new case (REST)
                                        ▼
                         ┌────────────────────────────┐
                         │   Band Chat Room             │
                         │  ("Sangam Case Room")        │
                         └──────────────┬───────────────┘
            @Intake  @PatientProfile  @StructuralBio  @PKPD  @EvidenceRAG  @ComplianceGuard
                 (6 remote agents, each its own Python process, AnthropicAdapter)
                                        │
                                        ▼
                         ┌────────────────────────────┐
                         │ ComplianceGuard posts        │
                         │ FINAL_VERDICT (json block)   │
                         │ → may @mention @Clinician    │
                         │   (human, added dynamically) │
                         └────────────────────────────┘
```

Streamlit polls the room's message history (`GET /me/chats/{id}/messages` —
**[VERIFY AGAINST DOCS]**) to (a) render the live debate in the Agent Workspace tab,
and (b) detect the `FINAL_VERDICT` JSON block to populate the Consumer/Physician
dashboards.

---

## 3. The six agents

**Model provider: DeepSeek (not Anthropic).** Each agent is a **separate Python
process** using `band-sdk[langgraph]` → `LangGraphAdapter(llm=ChatOpenAI(...))`,
where `ChatOpenAI` is pointed at DeepSeek's OpenAI-compatible endpoint:

```python
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from thenvoi.adapters import LangGraphAdapter

llm = ChatOpenAI(
    model="deepseek-chat",                 # or "deepseek-reasoner" for harder reasoning steps
    base_url="https://api.deepseek.com",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
)
adapter = LangGraphAdapter(llm=llm, checkpointer=InMemorySaver(), custom_section="<persona>")
```

This is the same `LangGraphAdapter` shown in Band's SDK overview (its quick example
uses `ChatOpenAI(model="gpt-4o")`) — `ChatOpenAI` natively supports any
OpenAI-compatible endpoint via `base_url`, and DeepSeek's API is OpenAI-compatible.
Use `deepseek-reasoner` for `@StructuralBio` and `@ComplianceGuard` (the two agents
doing the most multi-step reasoning/escalation logic) and `deepseek-chat` for the
rest, to balance quality, cost, and latency — adjust if `deepseek-reasoner` proves
too slow for a live demo.

**[VERIFIED — Phase 0, see `docs/architecture.md`]**: `band-sdk` (v1.0.0, PyPI)
installs via `uv add "band-sdk[langgraph]"`; `langchain-openai` is added as an
explicit direct dependency in `pyproject.toml` rather than relying on it being
transitive. DeepSeek's base URL `https://api.deepseek.com` is confirmed.
`deepseek-chat`/`deepseek-reasoner` are slated for deprecation 2026-07-24 (after
this hackathon's deadline), so they remain valid for this build.

Each agent is registered on Band as an "External Agent" (Section 7).

### 3.1 `@Intake` — Multilingual Intake & Nomenclature Agent
- **Job**: Parse the case description (drug names + herb/Ayurvedic names + dosages),
  normalize each to a standard identifier.
- **Custom tools**:
  - `lookup_pubchem(name: str) -> dict` — calls PubChem PUG REST
    (`https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/IUPACName,CanonicalSMILES,MolecularFormula/JSON`)
    for allopathic drugs.
  - `lookup_herb(name: str) -> dict` — looks up `data/herb_dictionary.json` (local,
    curated) mapping common Ayurvedic herb names → Latin binomial + active
    compound(s) (e.g., "Guggulu" → *Commiphora wightii* → guggulsterone E/Z).
- **Output**: posts a message with a fenced ` ```json ` block:
  ```json
  {"step": "intake", "drugs": [...], "herbs": [...]}
  ```
  then `@PatientProfile @StructuralBio` to start the next stage in parallel.

### 3.2 `@PatientProfile` — Pharmacogenomic Baseline Agent
- **Job**: Convert simplified patient inputs (age, eGFR, CYP2C9/CYP3A4 genotype
  selection from a dropdown — NOT a real VCF for MVP) into a baseline clearance
  modifier and risk flags.
- **Custom tool**: `compute_pgx_baseline(age, egfr, cyp2c9_genotype, cyp3a4_status) -> dict`
  — rule-based lookup against `data/pgx_rules.json` (no external API).
- **Output**: `{"step": "patient_profile", "clearance_modifier": 0.6, "risk_flags": [...]}`
  then `@PKPD`.

### 3.3 `@StructuralBio` — Structural Interaction Agent
- **Job**: Given a drug active compound + herb active compound, retrieve binding
  affinity (ΔG) at the relevant metabolic target (CYP2C9, CYP3A4, P-gp, albumin).
- **Custom tool**: `lookup_docking(drug_compound, herb_compound) -> dict` — reads
  `data/docking_lookup.json` (curated ΔG values for the demo case studies).
  - If pair not found → returns `{"status": "no_data"}`. The agent's system prompt
    must instruct it to be **honest about missing data** and offer a
    structural-analogy estimate ("Compound X is a furanocoumarin, structurally
    similar to bergamottin which is a known CYP3A4 inhibitor...") rather than
    inventing a number — this matters for both medical-safety correctness and for
    the escalation behavior in 3.6.
- **Output**: `{"step": "structural", "delta_g_kcal_mol": -8.4, "target": "CYP2C9", "confidence": "high|low", "basis": "lookup|analogy"}`
  then `@PKPD`.

### 3.4 `@PKPD` — Quantitative Systems Pharmacology Agent
- **Job**: Run a one-compartment oral PK model and report % AUC change.
- **Custom tool**: `simulate_pk(dose_mg, ka, ke_baseline, clearance_modifier, delta_g_kcal_mol) -> dict`
  - Map ΔG → `inhibition_fraction` via a documented simplified heuristic, e.g.
    `inhibition_fraction = clamp((-delta_g - 6) / 4, 0, 0.7)`.
  - `ke_patient = ke_baseline * clearance_modifier * (1 - inhibition_fraction)`
  - Analytical one-compartment AUC: `AUC = dose / (V * ke)`. Compute
    `auc_baseline` (no herb) vs `auc_combined` (with inhibition) and `pct_change`.
  - Also return a concentration-time curve (array) for the Physician tab chart.
  - **The system prompt must state this is a simplified illustrative PK model, not
    validated for clinical decisions** — this disclaimer must also propagate into
    the final verdict (regulatory honesty, Track 3 framing).
  - **Induction vs. inhibition**: `data/docking_lookup.json` entries carry a
    `"mechanism"` field (`"inhibition" | "induction" | "negligible"`). For
    `"induction"` (Case 4, Tacrolimus + St. John's Wort), apply the same
    `clamp((-delta_g - 6) / 4, 0, 0.7)` magnitude as an *increase* to `ke_patient`
    (`* (1 + induction_fraction)`) rather than a decrease — see
    `docs/architecture.md` for the full rationale.
- **Output**: `{"step": "pkpd", "auc_pct_change": 42.0, "concentration_curve": [...]}`
  then `@EvidenceRAG @ComplianceGuard`.

### 3.5 `@EvidenceRAG` — Translational Evidence Agent
- **Job**: Retrieve curated clinical literature evidence for the specific drug-herb
  pair via RAG over a small local corpus.
- **Custom tool**: `query_evidence(drug, herb) -> list[dict]` — ChromaDB similarity
  search over `data/evidence_corpus/*.json` (paraphrased summaries + citations the
  team writes themselves — see Section 6.4 on copyright).
- **Output**: `{"step": "evidence", "findings": [{"summary": "...", "citation": "...", "severity": "..."}]}`
  then `@ComplianceGuard`.

### 3.6 `@ComplianceGuard` — Regulatory Synthesis & Escalation Agent
- **Job**: Wait until it has received intake, patient profile, structural, PK/PD, and
  evidence messages for the case (it can track this with its own
  `thenvoi_send_event`/state, or simply re-read room context via
  `GET /agent/chats/{id}/context` **[VERIFY AGAINST DOCS]**). Then:
  1. Compute a confidence-weighted risk tier: `GREEN | YELLOW | RED`.
  2. **If confidence is low** (e.g., `@StructuralBio` returned `"basis": "analogy"`
     AND `@EvidenceRAG` found no direct evidence): `@mention @StructuralBio` again,
     asking it to widen the analogy search — a genuine second round.
  3. **If risk tier is RED** (or still low-confidence after the second round): use
     `add_participant_service`/`thenvoi_add_participant` to bring a human
     `@Clinician` participant into the room and `@mention` them with the case
     summary for sign-off — **[VERIFY AGAINST DOCS]** for exact tool name/usage.
  4. Post the final structured verdict:
     ```json
     {"step": "FINAL_VERDICT", "risk_tier": "RED", "confidence": 0.82,
      "auc_pct_change": 42.0, "delta_g_kcal_mol": -8.4,
      "rationale": "...", "disclaimer": "Decision-support only; not a diagnosis. ..."}
     ```
- **System prompt must include** the SaMD-style disclaimer language and an explicit
  instruction to *never* present the verdict as a diagnosis or prescription change —
  only as a flag for clinician review.

---

## 4. Demo case studies (curate as data, not live computation)

Build `data/case_studies.json` with **5 cases** spanning the risk spectrum so the
demo shows the system isn't just an alarm bell:

| # | Drug | Herb (common / Ayurvedic name) | Mechanism | Expected tier |
|---|------|---------------------------------|-----------|----------------|
| 1 | Warfarin | Guggulu (*Commiphora wightii*) | CYP2C9/3A4 inhibition → ↑bleeding | RED |
| 2 | Digoxin | Yashtimadhu / Licorice (*Glycyrrhiza glabra*) | Hypokalemia → digoxin toxicity | RED |
| 3 | Metformin | Karela / Bitter gourd (*Momordica charantia*) | Additive hypoglycemia | YELLOW |
| 4 | Tacrolimus | St. John's Wort (*Hypericum perforatum*) | CYP3A4 induction → ↓levels, rejection risk | RED |
| 5 | Paracetamol | Tulsi (*Ocimum sanctum*) | No significant known interaction | GREEN |

For each case, populate matching entries in `docking_lookup.json`, `pgx_rules.json`
(a couple of genotype variants per case), and a small `evidence_corpus/<case>.json`
with 2-4 **team-written paraphrased** summaries + citation strings (no copyrighted
text reproduction — see Section 6.4).

---

## 5. Repository structure

```
sangam-band/
├── README.md
├── LICENSE                       # MIT (required by hackathon rules)
├── pyproject.toml
├── .env.example
├── agent_config.example.yaml
├── .gitignore
├── data/
│   ├── case_studies.json
│   ├── herb_dictionary.json
│   ├── docking_lookup.json
│   ├── pgx_rules.json
│   └── evidence_corpus/
│       ├── warfarin_guggulu.json
│       ├── digoxin_licorice.json
│       ├── metformin_karela.json
│       ├── tacrolimus_sjw.json
│       └── paracetamol_tulsi.json
├── agents/
│   ├── common/
│   │   ├── __init__.py
│   │   ├── pubchem.py
│   │   ├── docking.py
│   │   ├── pgx.py
│   │   ├── pkpd.py
│   │   └── evidence_rag.py
│   ├── intake_agent.py
│   ├── patient_profile_agent.py
│   ├── structural_agent.py
│   ├── pkpd_agent.py
│   ├── evidence_rag_agent.py
│   └── compliance_agent.py
├── rag/
│   └── build_index.py            # builds Chroma index from evidence_corpus/
├── orchestrator/
│   ├── band_client.py            # REST helper: create room, post msg, poll msgs
│   └── run_case.py                # CLI: trigger a new case run end-to-end
├── frontend/
│   ├── app.py
│   ├── theme.py                   # navy/teal/amber design tokens
│   └── tabs/
│       ├── consumer.py
│       ├── physician.py
│       └── agent_workspace.py
├── scripts/
│   ├── start_all_agents.sh
│   └── start_all_agents.ps1       # PowerShell version for Windows dev box
├── tests/
│   ├── test_pubchem.py
│   ├── test_pkpd.py
│   ├── test_docking_lookup.py
│   └── test_pgx.py
└── docs/
    ├── architecture.md
    ├── band_room_setup.md
    └── submission/
        ├── long_description.md
        ├── video_script.md
        ├── slides_outline.md
        └── cover_image_brief.md
```

---

## 6. Tech stack & dependencies

- **Python 3.11**, `uv` package manager.
- `band-sdk[langgraph]` — agent runtime (`thenvoi` package namespace).
- `langchain-openai`, `langgraph` — LLM client; `ChatOpenAI` pointed at DeepSeek via
  `base_url="https://api.deepseek.com"` for all 6 agents (`DEEPSEEK_API_KEY`).
- `chromadb` — local vector store for `@EvidenceRAG`.
- `scipy`, `numpy` — PK/PD model.
- `requests` — PubChem REST + Band REST calls.
- `streamlit`, `plotly` — frontend + kinetic charts.
- `python-dotenv`, `pyyaml`.

### 6.1 Environment variables (`.env`)
```
DEEPSEEK_API_KEY=sk-...
THENVOI_REST_URL=https://app.band.ai/                              # [VERIFIED Phase 0]
THENVOI_WS_URL=wss://app.band.ai/api/v1/socket/websocket           # [VERIFIED Phase 0]
BAND_USER_API_KEY=...     # personal/account-level key for orchestrator REST calls — [VERIFY: docs.band.ai/getting-started/setup, deferred to Phase 3]
AIML_API_KEY=...          # optional, for partner-prize integration
FEATHERLESS_API_KEY=...   # optional, for partner-prize integration
```

### 6.2 `agent_config.yaml` (six entries, one per agent — NOT committed)
```yaml
intake:
  agent_id: "<uuid>"
  api_key: "<key>"
patient_profile:
  agent_id: "<uuid>"
  api_key: "<key>"
structural:
  agent_id: "<uuid>"
  api_key: "<key>"
pkpd:
  agent_id: "<uuid>"
  api_key: "<key>"
evidence_rag:
  agent_id: "<uuid>"
  api_key: "<key>"
compliance:
  agent_id: "<uuid>"
  api_key: "<key>"
```
Both `.env` and `agent_config.yaml` go in `.gitignore`; only `.env.example` and
`agent_config.example.yaml` are committed.

### 6.3 AI/ML API & Featherless (partner prize — Phase 4 stretch, optional)
Since the core LLM is now DeepSeek (via `ChatOpenAI` + custom `base_url`), the same
pattern can swap in AI/ML API or Featherless for 1-2 agents if you want a shot at the
partner prizes (`base_url`/`api_key` swap only — no code structure change). This is
purely optional and should not displace any core-loop work; skip it if Phase 1-3 run
late.

### 6.4 Copyright / data sourcing note
`evidence_corpus/*.json` entries must be **short, original paraphrases written by the
team**, each under ~2-3 sentences, with a citation string (e.g., "Smith et al., J Clin
Pharmacol 2019"). Do not paste abstract text verbatim from PubMed into the repo.

---

## 7. Band platform setup (manual, ~30 min — do this first)

1. Create a Band account at `app.band.ai` (use promo `BANDHACK26` for 1 month Pro per
   the hackathon page — **[VERIFY current redemption flow on band.ai/manage-billing]**).
2. Read `docs.band.ai/getting-started/setup` to get your **personal/account API key**
   for the orchestrator's REST calls (`BAND_USER_API_KEY`).
3. For **each of the 6 agents**, go to Agents → New Agent → "External Agent", name it
   exactly `Intake`, `PatientProfile`, `StructuralBio`, `PKPD`, `EvidenceRAG`,
   `ComplianceGuard` (so `@mentions` in prompts match), and save the displayed
   `agent_id` + `api_key` into `agent_config.yaml`.
4. Create one Chat Room ("Sangam Case Room") and add all 6 agents as participants
   (Remote section). Optionally add yourself as `@Clinician` (human participant) for
   the escalation demo.
5. Run each of the 6 agent processes locally (Section 9, Phase 1/2) and sanity-check
   with a manual `@Intake hello` message in the room before wiring the orchestrator.

---

## 8. Frontend spec (Streamlit)

Design system: deep navy (#0B2545) headings/nav, teal (#2EC4B6) accents/active
states, amber (#FFB100) callouts/warnings, clean sans-serif (Inter or system
default). Three tabs:

1. **Consumer tab** — simple form (pick a case study from the 5, or free-text drug +
   herb names + dosage), big traffic-light result (🟢🟡🔴), plain-language summary
   pulled from `FINAL_VERDICT.rationale`, and the disclaimer.
2. **Physician tab** — eGFR/genotype inputs, ΔG value + target enzyme, AUC %-change
   number, and a Plotly concentration-time curve (baseline vs combined).
3. **Agent Workspace tab** — live, auto-refreshing transcript of the Band room
   (poll every 2-3s), rendered as chat bubbles colored by agent (use the theme
   palette), showing the real `@mention` handoffs and the escalation round if it
   triggers. This is the "Application of Technology" showcase tab.

`orchestrator/run_case.py` posts the initial message
(`@Intake @PatientProfile New case: ...`) when the user clicks "Run Analysis" in the
Consumer tab; the frontend then polls until a `FINAL_VERDICT` json block appears.

---

## 9. Build phases (today is June 15; submission closes June 19)

### Phase 0 — Setup (few hours, June 15)
- Manual Band setup (Section 7). Create GitHub repo (MIT license, public).
- Scaffold repo structure (Section 5), `pyproject.toml`, `.env.example`,
  `agent_config.example.yaml`, `.gitignore`.
- Write `data/case_studies.json`, `herb_dictionary.json`, `docking_lookup.json`,
  `pgx_rules.json`, and all 5 `evidence_corpus/*.json` files (Section 4).

### Phase 1 — Core agents (June 16)
- Implement `agents/common/pubchem.py`, `pgx.py`, `docking.py`.
- Implement `@Intake`, `@PatientProfile`, `@StructuralBio` agents with their custom
  tools and system prompts (Section 3.1-3.3).
- Manual test in the Band room: send a case message, confirm the three agents hand
  off correctly via `@mention`.

### Phase 2 — Reasoning agents + escalation loop (June 17)
- Implement `agents/common/pkpd.py` (analytical one-compartment model + tests).
- Implement `@PKPD`, `@EvidenceRAG` (build `rag/build_index.py` first), and
  `@ComplianceGuard` including the second-round escalation and `@Clinician`
  dynamic-add logic.
- Run all 5 case studies end-to-end manually in the Band room; verify each produces
  a sensible `FINAL_VERDICT` and that case #1/#4 trigger escalation.
- Stretch: wire AI/ML API and/or Featherless into 1-2 agents (Section 6.3).

### Phase 3 — Frontend + orchestrator (June 18)
- Implement `orchestrator/band_client.py` and `run_case.py`
  (`[VERIFY AGAINST DOCS]` for the messages-list and context endpoints).
- Build the 3-tab Streamlit app (Section 8). Wire "Run Analysis" → post to room →
  poll → render.
- End-to-end test all 5 case studies through the UI. Deploy (Streamlit Community
  Cloud or Render) — note the 6 agent processes also need to run somewhere
  reachable (a small always-on VM or background processes; a single low-spec cloud
  VM is enough since there's no heavy local compute).

### Phase 4 — Submission assets (June 19)
- `README.md` with architecture diagram, setup instructions, and screenshots.
- `docs/submission/long_description.md`, `video_script.md` (2-3 min walkthrough:
  problem → architecture → live Band room demo on case #1 → escalation on case #4
  → consumer/physician views), `slides_outline.md`, `cover_image_brief.md`.
- Record demo video, build slide deck (Canva can help here), capture cover image.
- Final pass: confirm MIT LICENSE present, repo public, demo URL live, all 5 case
  studies work, AI/ML API & Featherless usage documented if used.
- Submit on lablab.ai.

---

## 10. Things Claude Code must verify before/while building (do not assume)

- ~~`THENVOI_WS_URL` / `THENVOI_REST_URL` defaults~~ — **VERIFIED Phase 0**:
  `THENVOI_REST_URL=https://app.band.ai/`,
  `THENVOI_WS_URL=wss://app.band.ai/api/v1/socket/websocket`. See
  `docs/architecture.md`.
- ~~Current DeepSeek model ids and base URL~~ — **VERIFIED Phase 0**:
  `base_url="https://api.deepseek.com"`; `deepseek-chat`/`deepseek-reasoner` valid
  until 2026-07-24 deprecation (after our deadline). `band-sdk[langgraph]` confirmed
  on PyPI; `langchain-openai` pinned explicitly as a direct dependency. See
  `docs/architecture.md`.
- Exact REST endpoints + auth for: listing room messages (`GET /me/chats/{id}/messages`),
  fetching an agent's own context (`GET /agent/chats/{id}/context`), and creating/
  posting to a room as the account owner (for the orchestrator) — check
  `docs.band.ai/api/introduction`. **Deferred to Phase 3.**
- Exact tool name for adding a participant to a room
  (`add_participant_service` vs `thenvoi_add_participant`) and whether a human
  participant can be added by `agent_id`/email — check
  `docs.band.ai/core-concepts/chat-rooms` and `/core-concepts/contacts`.
  **Deferred to Phase 2** (`@ComplianceGuard` escalation).
- Whether `band-sdk` has a generic OpenAI-compatible adapter with a `base_url` param
  for AI/ML API / Featherless — check `docs.band.ai/integrations/sdks/overview` and
  `/integrations/adapters`. **Deferred to Phase 2/4, optional stretch.**

When any of these differ from the spec, update this file and proceed — don't block on
a guess; implement the closest documented equivalent and note the deviation in
`docs/architecture.md`.
