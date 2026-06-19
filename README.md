<div align="center">

<!-- Animated title -->
<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=700&size=32&pause=1000&color=14B8A6&center=true&vCenter=true&width=700&lines=SANGAM+%E2%80%94+Polypharmacy+Safety+Council;Six+AI+Agents.+One+Verdict.;Zero+Missed+Interactions." alt="Sangam" />

<br/>

<!-- Badges row 1 -->
[![CI](https://github.com/nsdeshmukh306-ai/sangam-band/actions/workflows/ci.yml/badge.svg)](https://github.com/nsdeshmukh306-ai/sangam-band/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/Tests-75%20passing-22c55e?style=flat-square&logo=pytest&logoColor=white)](https://github.com/nsdeshmukh306-ai/sangam-band/blob/main/tests)
[![Release](https://img.shields.io/github/v/release/nsdeshmukh306-ai/sangam-band?color=6366f1&style=flat-square&logo=github)](https://github.com/nsdeshmukh306-ai/sangam-band/releases/tag/v1.0.0)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)

<!-- Badges row 2 -->
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3b82f6?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek--V3-8b5cf6?style=flat-square)](https://www.deepseek.com/)
[![Band SDK](https://img.shields.io/badge/Multi--Agent-Band%20SDK-f59e0b?style=flat-square)](https://band.ai)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%2018-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Deploy-Docker%20%2B%20Cloud%20Run-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/)

<!-- Hackathon badge -->
[![Hackathon](https://img.shields.io/badge/lablab.ai-Band%20of%20Agents%20%7C%20Track%203-ef4444?style=flat-square)](https://lablab.ai)

<br/>

> **"Sangam"** *(Sanskrit: confluence)* — A council of 6 specialist AI agents that deliberate together to catch dangerous drug–herb interactions before they reach a patient.

<br/>

---

</div>

## The Problem Nobody Is Solving

India runs on two parallel medicine systems — and nobody is checking where they collide.

**500 million Indians** regularly combine prescription drugs with Ayurvedic herbs. Up to **70% never tell their doctor**. The result is invisible: warfarin combined with Guggulu can raise drug exposure by 150%, tacrolimus combined with St. John's Wort can cause organ rejection, and phenytoin combined with Shankhpushpi can trigger breakthrough seizures.

Every drug interaction checker that exists — Drugs.com, Medscape, Epocrates — screens against the Western pharmacopoeia. Not one of them includes a single Ayurvedic herb.

**Sangam fixes this.**

---

## What Sangam Does

<table>
<tr>
<td width="50%">

**Input** — any free-text patient description:
```
68-year-old male, warfarin 5mg daily,
Guggulu 500mg twice daily,
CYP2C9 *1/*3, eGFR 55 mL/min
```

</td>
<td width="50%">

**Output** — a clinically grounded verdict:
```json
{
  "risk_tier": "RED",
  "confidence": "high",
  "auc_pct_change": 150.0,
  "delta_g_kcal_mol": -8.4,
  "mechanism": "CYP2C9 inhibition",
  "escalated_to_clinician": true
}
```

</td>
</tr>
</table>

Six Band AI agents collaborate in real time — each a specialist, each running as an independent process — to produce a **RED / YELLOW / GREEN** verdict backed by molecular docking data, pharmacokinetic modelling, patient pharmacogenomics, and peer-reviewed literature.

---

## Meet the Council

*Six agents. Each a domain expert. None of them guess.*

<table>
<thead>
<tr>
<th>Agent</th>
<th>Specialty</th>
<th>What It Does</th>
<th>Data Sources</th>
</tr>
</thead>
<tbody>
<tr>
<td>🔵 <b>@Intake</b></td>
<td>Drug &amp; Herb Resolution</td>
<td>Parses free text → fetches PubChem CIDs, IUPAC names, molecular formulae, Ayurvedic herb profiles</td>
<td>PubChem API, <code>herb_dictionary.json</code></td>
</tr>
<tr>
<td>🟣 <b>@PatientProfile</b></td>
<td>Pharmacogenomics</td>
<td>Computes CYP2C9/3A4 metabolizer status, eGFR clearance modifier, age adjustment → personalized PK baseline</td>
<td><code>pgx_rules.json</code></td>
</tr>
<tr>
<td>🩵 <b>@StructuralBio</b></td>
<td>Molecular Docking</td>
<td>Returns ΔG (kcal/mol), target enzyme, and inhibition/induction mechanism for all drug–herb pairs</td>
<td><code>docking_lookup.json</code> (26 pairs)</td>
</tr>
<tr>
<td>🟠 <b>@PKPD</b></td>
<td>PK/PD Simulation</td>
<td>One-compartment model → AUC % change, 48-hour concentration curve at 1-hour resolution</td>
<td>Docking + Patient outputs</td>
</tr>
<tr>
<td>🟢 <b>@EvidenceRAG</b></td>
<td>Literature Search</td>
<td>Retrieves supporting evidence: case reports, in-vitro studies, Dravyaguna pharmacology texts with severity grading</td>
<td>ChromaDB index (70 findings)</td>
</tr>
<tr>
<td>🔴 <b>@ComplianceGuard</b></td>
<td>Safety Arbiter</td>
<td>Synthesizes all 5 upstream reports → issues RED/YELLOW/GREEN verdict, escalation flag, regulatory disclaimer</td>
<td>All agent outputs</td>
</tr>
</tbody>
</table>

> Each agent is an independent Python process connected via the **Band multi-agent SDK**. They communicate through structured JSON messages in a shared Band room — no monolithic prompt chain, no single point of failure.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          USER INTERFACES                                │
│    React SPA (:8000/app)          CLI (orchestrator/run_case.py)        │
└──────────────────────┬──────────────────────────────────────────────────┘
                       │ POST /api/cases/run
                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (:8000)                               │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │  Job Queue  │  │  SQLite DB   │  │  WebSocket   │  │  NLP Parser │ │
│  │ (asyncio)   │  │  (aiosqlite) │  │  Streaming   │  │  (0.92 acc) │ │
│  └──────┬──────┘  └──────────────┘  └──────────────┘  └─────────────┘ │
└─────────┼───────────────────────────────────────────────────────────────┘
          │ Post case message + run_id
          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Band AI Multi-Agent Room                              │
│                                                                         │
│  🔵 @Intake ──────────────────────────────────────────────────────────  │
│       │ {step:"intake", run_id:"abc123", drugs:[...], herbs:[...]}      │
│       ▼                                                                 │
│  🟣 @PatientProfile ──────── 🩵 @StructuralBio                         │
│       │ {clearance_modifier:0.41}    │ {delta_g:-8.4, target:"CYP2C9"} │
│       └──────────────┬───────────────┘                                 │
│                      ▼                                                  │
│              🟠 @PKPD                                                   │
│                      │ {auc_pct_change:150.0, concentration_curve:[...]}│
│                      ▼                                                  │
│              🟢 @EvidenceRAG                                            │
│                      │ {findings:[{citation:..., severity:"high"},...]} │
│                      ▼                                                  │
│              🔴 @ComplianceGuard                                        │
│                      │ {risk_tier:"RED", confidence:"high", ...}        │
└──────────────────────┼──────────────────────────────────────────────────┘
                       │ FINAL_VERDICT JSON
                       ▼
              FastAPI → WebSocket → React UI
```

**Key design decision:** every pipeline run is tagged with a unique 8-character `run_id`. ComplianceGuard only accepts reports that share the same `run_id` — making concurrent multi-patient runs safe with no cross-contamination.

---

## Quick Start

### Prerequisites

- Python **3.11+** with [`uv`](https://docs.astral.sh/uv/) — `pip install uv`
- Node.js **20+** (React frontend only)
- A Band account with **6 registered External Agents** — see [`PROJECT_SPEC.md §7`](PROJECT_SPEC.md)

### 1. Clone & Install

```bash
git clone https://github.com/nsdeshmukh306-ai/sangam-band.git
cd sangam-band
uv sync
```

### 2. Configure Secrets

```bash
cp .env.example .env                            # fill: DEEPSEEK_API_KEY, BAND_ROOM_ID
cp agent_config.example.yaml agent_config.yaml  # fill: 6 agent UUIDs + API keys
```

### 3. Build Evidence Index (one-time)

```bash
uv run python -m rag.build_index
```

### 4. Launch Everything

```bash
bash scripts/start_agents.sh   # starts all 6 Band agents (logs → logs/)
bash scripts/start_backend.sh  # FastAPI on :8000

# Verify all 6 agents are live:
curl -s http://localhost:8000/health | python3 -m json.tool
```

### 5. Open the UI

```
http://localhost:8000/app/      ← React SPA with live WebSocket feed
http://localhost:8000/docs      ← FastAPI interactive API docs
```

### Docker (one command)

```bash
cp .env.example .env   # fill secrets
docker compose up --build
```

### CLI — Run a Case

```bash
# Named case
uv run python -m orchestrator.run_case --case case_1_warfarin_guggulu

# Combination screener (instant, no LLM)
curl -s -X POST http://localhost:8000/api/interactions/screen \
  -H "Content-Type: application/json" \
  -d '{"text": "warfarin aspirin guggulu garlic"}' | python3 -m json.tool
```

---

## Combination Screener — Instant Risk Triage

Beyond the full 6-agent pipeline, Sangam includes a **deterministic pairwise screener** for point-of-care use.

```bash
POST /api/interactions/screen
{"text": "warfarin aspirin guggulu garlic"}
```

Returns all pairwise combinations sorted by risk tier in milliseconds — no LLM call, no latency:

```json
{
  "substances": ["warfarin", "aspirin", "guggulu", "garlic"],
  "combination_count": 6,
  "combinations": [
    {
      "pair": "warfarin + guggulu",
      "tier": "RED",
      "mechanism": "CYP2C9 inhibition",
      "clinical_action": "Avoid co-administration. Monitor INR if unavoidable.",
      "confidence": 0.95,
      "source": "curated_case"
    },
    ...
  ]
}
```

**30+ substance profiles** covering CYP1A2, CYP2C9, CYP2C19, CYP3A4, P-gp, and OCT transporters.

---

## 25 Validated Drug–Herb Cases

> All 25 cases have pre-computed verdicts and pass the full data integrity test suite.

### 🔴 RED — Contraindicated · 10 Cases

| # | Drug | Herb | Key Mechanism | AUC Δ |
|---|------|------|---------------|-------|
| 1 | Warfarin 5mg | Guggulu | CYP2C9 inhibition → ↑INR, bleeding risk | **+150%** |
| 2 | Digoxin 0.25mg | Licorice | P-gp inhibition + hypokalemia | +78% |
| 4 | Tacrolimus 2mg | St. John's Wort | CYP3A4 induction → organ rejection | **-41.2%** |
| 7 | Atorvastatin 40mg | Brahmi | CYP3A4 inhibition → myopathy risk | +92% |
| 9 | Methotrexate 15mg | Neem | P-gp inhibition + hepatotoxicity | +65% |
| 13 | Phenytoin 200mg | Shankhpushpi | CYP2C9 induction → breakthrough seizures | -38% |
| 17 | Rifampicin 600mg | Turmeric | CYP3A4 inhibition + additive hepatotox | +45% |
| 21 | Prednisolone 10mg | Licorice | CYP3A4 + 11β-HSD2 inhibition | +88% |
| 22 | Cyclosporine 150mg | St. John's Wort | CYP3A4 induction (FDA/EMA contraindicated) | -55% |
| 24 | Amiodarone 200mg | Fenugreek | QT prolongation + CYP3A4 inhibition | +71% |

### 🟡 YELLOW — Monitor Closely · 10 Cases

| # | Drug | Herb | Key Mechanism |
|---|------|------|---------------|
| 3 | Metformin 500mg | Karela | Additive glucose lowering (PD) |
| 6 | Aspirin 75mg | Ashwagandha | COX-1 + CYP2C9 inhibition, additive bleed |
| 8 | Amlodipine 5mg | Arjuna | Additive Ca²⁺-channel antagonism |
| 10 | Ciprofloxacin 500mg | Licorice | CYP1A2 inhibition + QT risk |
| 11 | Omeprazole 20mg | Black Pepper | CYP2C19 inhibition (piperine) |
| 12 | Insulin Glargine 10IU | Fenugreek | Additive hypoglycaemia |
| 16 | Lithium 450mg | Dandelion | Natriuresis → Li⁺ accumulation |
| 18 | Clopidogrel 75mg | Ginger | Additive antiplatelet (6-gingerol) |
| 19 | Sildenafil 50mg | Ginkgo biloba | CYP3A4 + additive vasodilation |
| 20 | Clonazepam 1mg | Valerian | GABA-A potentiation → CNS depression |

### 🟢 GREEN — Safe · 5 Cases

| # | Drug | Herb | Reason |
|---|------|------|--------|
| 5 | Paracetamol 500mg | Tulsi | No clinically significant interaction |
| 14 | Amoxicillin 500mg | Garlic (culinary) | No significant PK interaction |
| 15 | Levothyroxine 100mcg | Shatavari | Theoretical only, no published data |
| 23 | Furosemide 40mg | Dandelion | Negligible additive diuresis |
| 25 | Cetirizine 10mg | Ashwagandha | No CYP interaction (renal elimination) |

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | System liveness + all 6 agent status |
| `GET` | `/api/cases/list` | All 25 case study metadata |
| `POST` | `/api/cases/run` | Submit case → returns `job_id` |
| `GET` | `/api/cases/{job_id}/status` | Poll job status + full verdict |
| `WS` | `/api/ws/{job_id}` | Stream live agent events |
| `GET` | `/api/room/transcript` | Full Band room message history |
| `POST` | `/api/cases/parse` | NLP free-text → matched case (scored) |
| `POST` | `/api/interactions/screen` | Instant pairwise combination screener |

Interactive docs: `http://localhost:8000/docs`

---

## Repository Structure

```
sangam-band/
│
├── agents/                         # One Python process per Band agent
│   ├── common/                     # Shared tools: pubchem, pgx, docking, pkpd, rag, llm
│   ├── intake_agent.py             # 🔵 @Intake — drug/herb resolution
│   ├── patient_profile_agent.py    # 🟣 @PatientProfile — PGx + clearance modifier
│   ├── structural_agent.py         # 🩵 @StructuralBio — molecular docking lookup
│   ├── pkpd_agent.py               # 🟠 @PKPD — one-compartment PK simulation
│   ├── evidence_rag_agent.py       # 🟢 @EvidenceRAG — ChromaDB literature search
│   └── compliance_agent.py         # 🔴 @ComplianceGuard — verdict + escalation
│
├── backend/
│   ├── main.py                     # FastAPI: all endpoints + WebSocket
│   ├── job_runner.py               # Async job queue (max 3 concurrent)
│   ├── db.py                       # SQLite via aiosqlite
│   ├── nlp_parser.py               # NLP case matcher (0.92 confidence)
│   └── interaction_screen.py       # Deterministic pairwise screener
│
├── frontend/
│   └── react/                      # Vite + React 18 + TypeScript
│       └── src/
│           ├── App.tsx             # Single-page dashboard
│           ├── components/
│           │   ├── CasePanel.tsx   # NLP input + pipeline stepper + combo cards
│           │   ├── RightPanel.tsx  # Chart.js PK curve + evidence table
│           │   ├── Sidebar.tsx     # Job history + agent status dots
│           │   └── JobHistory.tsx
│           ├── api.ts              # REST + WebSocket client
│           └── types.ts            # Full TypeScript type definitions
│
├── data/
│   ├── case_studies.json           # 25 validated cases (RED×10/YELLOW×10/GREEN×5)
│   ├── herb_dictionary.json        # 19 Ayurvedic herbs + CYP/P-gp profiles
│   ├── docking_lookup.json         # 26 drug–herb docking pairs + ΔG values
│   ├── pgx_rules.json              # CYP2C9, CYP3A4, CYP2C19 + eGFR rules
│   └── evidence_corpus/            # 20 JSON files → 70 RAG findings
│
├── orchestrator/
│   ├── band_client.py              # Band REST client: post/poll/fetch
│   └── run_case.py                 # CLI runner
│
├── rag/
│   └── build_index.py              # ChromaDB index builder
│
├── deployment/
│   ├── cloudrun-backend.yaml       # GCP Cloud Run (backend)
│   └── cloudrun-frontend.yaml      # GCP Cloud Run (frontend)
│
├── scripts/
│   ├── start_agents.sh             # Launch all 6 agents
│   ├── start_backend.sh            # Launch FastAPI
│   └── watchdog.sh                 # Monitor agent PIDs
│
├── tests/                          # 75 tests — zero live credentials required
├── .github/workflows/ci.yml        # GitHub Actions CI
├── Dockerfile.backend              # Multi-stage backend image
├── Dockerfile.react                # Multi-stage React image
├── docker-compose.yml              # Full stack in one command
├── nginx.conf                      # Production reverse proxy
├── pyproject.toml                  # Dependencies (uv)
├── .env.example                    # Environment template
└── agent_config.example.yaml       # Agent UUID + key template
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Agent Platform | [Band AI](https://band.ai) multi-agent SDK (LangGraph adapter) |
| LLM | DeepSeek-V3 via OpenAI-compatible API |
| Agent Orchestration | LangGraph state machine |
| Backend | FastAPI + aiosqlite + asyncio job queue |
| Frontend | React 18 + Vite + TypeScript + Chart.js |
| Vector Search | ChromaDB (70 curated evidence findings) |
| Containerisation | Docker multi-stage + docker-compose |
| Cloud Deploy | GCP Cloud Run + Cloud Build |
| CI/CD | GitHub Actions |
| Testing | pytest — 75 tests, zero API keys needed |

---

## Running Tests

```bash
uv run pytest tests/ -v --tb=short

# Covers:
#   PGx rules · docking lookup · herb dictionary · PubChem client
#   PK/PD math · RAG pipeline · 25-case data integrity
#   API endpoints · combination screener · NLP parser
#
# 75 tests — all green, no Band or DeepSeek credentials required
```

---

## Deployment

### Public URL (localhost tunnel)

```bash
bash scripts/start_agents.sh
bash scripts/start_backend.sh
ssh -R 80:localhost:8000 nokey@localhost.run
# React app → https://<hash>.lhr.life/app/
```

### GCP Cloud Run

```bash
gcloud builds submit --config deployment/cloudrun-backend.yaml
gcloud builds submit --config deployment/cloudrun-frontend.yaml
```

---

## Key Results

| Case | Combination | Verdict | Metric |
|------|-------------|---------|--------|
| Warfarin + Guggulu | CYP2C9 inhibition | 🔴 RED | AUC +150%, ΔG -8.4 kcal/mol |
| Tacrolimus + St. John's Wort | CYP3A4 induction | 🔴 RED | AUC -41.2%, ΔG -7.8 kcal/mol |
| Metformin + Karela | PD additive | 🟡 YELLOW | Glucose monitoring required |
| Paracetamol + Tulsi | Negligible | 🟢 GREEN | No significant interaction |

---

## Why This Matters

There are drug interaction checkers. None of them cover Ayurvedic herbs. Not one. The entire category is a blank space in clinical pharmacology tooling for Indian medicine.

Sangam is not a lookup table with an LLM on top. It is a pipeline where each agent contributes a different analytical layer — structural chemistry, patient genetics, pharmacokinetic modelling, clinical evidence — and ComplianceGuard synthesizes them into a verdict that shows its work. Every number in the output is traceable to a specific agent's reasoning.

That traceability is what makes it usable in a clinical context.

---

<div align="center">

**Built for the [lablab.ai Band of Agents Hackathon](https://lablab.ai) · Track 3: Regulated & High-Stakes Workflows**

[![MIT License](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)
[![Made in India](https://img.shields.io/badge/Made%20with%20%E2%9D%A4%EF%B8%8F-for%20India%20Health-f59e0b?style=flat-square)](https://github.com/nsdeshmukh306-ai/sangam-band)
[![Band of Agents](https://img.shields.io/badge/Track%203-Regulated%20%26%20High--Stakes-ef4444?style=flat-square)](https://lablab.ai)

<br/>

*Built by [Niraj Deshmukh](https://github.com/nsdeshmukh306-ai) · MSc Biological Data Science · IISER Tirupati*

*"The best drug interaction checker is the one that catches what the doctor didn't think to ask."*

</div>
