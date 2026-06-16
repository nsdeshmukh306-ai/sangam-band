# Sangam — Slide Deck Outline (8 slides)

---

## Slide 1: The Problem

**Title:** 70% of Indian patients receive both allopathic and Ayurvedic medicines —
but no one checks the interactions.

**Body:**
- Polypharmacy is the rule, not the exception: multiple chronic-disease drugs +
  daily Ayurvedic supplements for most patients at government hospitals.
- Drug–herb interaction data exists (pharmacognosy journals, structural biology,
  clinical case reports) but is fragmented across disciplines no single GP can span.
- Real consequences: warfarin + guggul → INR elevation; tacrolimus + St. John's
  Wort → transplant rejection; digoxin + licorice → hypokalemia + arrhythmia.
- Current state: no decision-support tool integrates structural, PK, and clinical
  evidence for drug–herb pairs in a single workflow.

**Visual:** Split image — a GP's prescription pad on one side, a pile of Ayurvedic
supplements on the other, overlapping danger zone highlighted red.

---

## Slide 2: Solution Overview

**Title:** Sangam — a six-agent council that replicates a multidisciplinary team
review in under three minutes.

**Body:**
- Six specialist AI agents, each owning exactly one layer of the safety review.
- Agents coordinate through a shared Band room via @mention routing — no central
  orchestrator, no shared memory, no single point of failure.
- Output: a structured RED/YELLOW/GREEN risk verdict with AUC change, mechanism,
  evidence citations, and a mandatory human escalation path.
- Built with Band SDK, DeepSeek, LangGraph, ChromaDB, and Streamlit.

**Visual:** Six agent avatars in a circle, connected by @mention arrows, with the
Band room chat shown as the backbone.

---

## Slide 3: How Band Enables It

**Title:** Band's @mention routing replaces a complex orchestration layer.

**Body:**
- Each agent subscribes to its own Band identity and wakes only when @mentioned.
- The pipeline is purely emergent: @Intake tags @PatientProfile, @PatientProfile
  tags @PKPD, @StructuralBio tags @PKPD — two messages arrive at @PKPD from
  independent paths and it waits for both before proceeding.
- `run_id` stamping (8-char hex in every case post) lets all agents filter a room
  with 100+ accumulated messages to only data from the current pipeline run.
- `FreshGraphAdapter` (custom `LangGraphAdapter` subclass): per-message thread
  isolation prevents InMemorySaver state from prior runs leaking into new cases.
- Auto-restart daemonizer: Band WebSocket closes with code 1000 (intentional) on
  idle timeout; a double-fork restart loop keeps agents live between cases.

**Visual:** Annotated Band room transcript screenshot showing @mention chains,
`[Run abc12345 — ...]` stamp, and JSON step blocks from each agent.

---

## Slide 4: Agent Pipeline

**Title:** Each agent owns one epistemic layer of the safety review.

**Agents (left to right):**

| Agent | Input | Tool(s) | Output |
|---|---|---|---|
| @Intake | Raw case text | (LLM parse only) | Drug/herb/patient structured JSON |
| @PatientProfile | Patient demographics | `compute_pgx_baseline` | `clearance_modifier`, risk flags |
| @StructuralBio | Drug + herb active compounds | `lookup_docking` | ΔG, target, mechanism, confidence |
| @PKPD | PK params + clearance modifier + ΔG | `lookup_pk_params`, `simulate_pk` | AUC change, concentration curve |
| @EvidenceRAG | Drug + herb names | `query_evidence` (ChromaDB) | Ranked findings + severity |
| @ComplianceGuard | All 5 reports | `fetch_full_room_context` | Risk tier, status, rationale, verdict |

**Key design decision:** @PKPD and @EvidenceRAG run in parallel (both are triggered
by @StructuralBio's message); @ComplianceGuard waits for both before synthesising.

**Visual:** Horizontal pipeline swimlane diagram with arrows, tool names, and
data-flow annotations.

---

## Slide 5: Live Demo Results

**Title:** Three cases, three tiers — the model gets the pharmacology right.

**Case 1 — Warfarin + Guggulu (68F, CYP2C9 *1/*3, eGFR 55)**
- ΔG = −8.4 kcal/mol at CYP2C9, mechanism: inhibition
- AUC +150%, clearance −60%
- 2 × high-severity evidence findings
- Verdict: **RED** / PENDING_HUMAN_REVIEW ✓

**Case 3 — Metformin + Karela (55M, CYP2C9 *1/*1, eGFR 62)**
- No structural CYP/P-gp target for Metformin → confidence low
- @ComplianceGuard triggers two-round @StructuralBio re-mention escalation
- Evidence: 2 × moderate findings (hypoglycaemia risk)
- Verdict: **YELLOW** / PENDING_HUMAN_REVIEW (low confidence after round 2) ✓

**Case 4 — Tacrolimus + St. John's Wort (45M, CYP3A4 reduced, eGFR 38)**
- ΔG = −9.1 kcal/mol, mechanism: **induction** (opposite direction)
- AUC −41%, clearance +70% → subtherapeutic exposure, efficacy-loss risk
- Verdict: **RED** / PENDING_HUMAN_REVIEW ✓

**Visual:** Three traffic-light verdict cards side by side with the key numbers
annotated.

---

## Slide 6: Human-in-the-Loop Escalation

**Title:** High-stakes verdicts stay under human authority — by design.

**Flow:**
1. @ComplianceGuard determines `risk_tier` and `confidence`.
2. If RED or confidence-low: posts `"status": "PENDING_HUMAN_REVIEW"` JSON block
   and @mentions the clinician participant in the same Band message.
3. Clinician sees the full rationale + evidence citations and replies with
   "approved" / "confirmed" / etc.
4. @ComplianceGuard posts a final `"status": "FINAL_VERDICT"` block with a
   `"human_signoff"` attestation field referencing the clinician's reply.
5. `poll_for_verdict` in the orchestrator accepts either status as a completed run.

**Why this matters for Track 3:**
- No silent auto-approval: every RED verdict requires a human keystroke.
- The escalation is part of the Band room transcript — auditable, replayable.
- The `"human_signoff"` field creates a lightweight attestation chain without
  requiring a separate audit system.

**Visual:** Band room screenshot showing the PENDING_HUMAN_REVIEW message, the
clinician's reply, and the FINAL_VERDICT follow-up.

---

## Slide 7: Business Value

**Title:** A deployable safety layer for India's 600 million Ayurvedic supplement
users.

**Market context:**
- India's Ayurvedic market: USD 18 billion in 2023, growing 15% YoY.
- ~600 million regular supplement users, majority also on at least one allopathic
  chronic-disease drug (hypertension, diabetes, thyroid).
- Government AYUSH + NHP programs actively integrating Ayurvedic care into the
  primary health system, creating institutional demand for safety tooling.

**Track 3 fit:**
- High-stakes output (clinical safety decisions) with mandatory human sign-off.
- Structured, auditable verdict format (`run_id`, `confidence`, `rationale`,
  `human_signoff`).
- Graceful degradation: when structural data is absent, the pipeline escalates
  rather than guessing — a key requirement for regulated workflows.
- Jurisdiction-aware: `data/evidence_corpus/` and `data/docking_lookup.json` are
  replaceable with country-specific pharmacopoeia data without changing any agent
  code.

**Near-term path to production:**
1. Replace curated `docking_lookup.json` with live PubChem / ChEMBL API queries.
2. Expand evidence corpus with WHO adverse event reports and Indian pharmacovigilance
   data.
3. Add FHIR-compatible patient input schema for EHR integration.

**Visual:** India map + drug-herb interaction heat map by region; Band room shown
as the coordination layer connecting clinic, lab, and regulatory tiers.

---

## Slide 8: Team + Next Steps

**Title:** Built in 72 hours by one person with six AI colleagues.

**Team:**
- Niraj Deshmukh — M.Sc. student, IISER Tirupati
  (niraj_20254009@students.iisertirupati.ac.in)

**What was built:**
- 6 specialist agents, each with domain-specific tools and escalation logic
- Custom `FreshGraphAdapter` for per-message thread isolation
- Orchestrator CLI + Streamlit frontend (3 tabs)
- 5 validated case studies covering inhibition, induction, and
  pharmacodynamic-only interaction patterns

**Next steps:**
1. Live PubChem + ChEMBL docking queries (replace curated JSON lookup)
2. FHIR patient input schema for EHR drop-in
3. Expand evidence corpus to WHO PV database + Indian CDSCO adverse-event reports
4. Multilingual @Intake (Hindi, Tamil, Telugu) for government clinic deployment
5. Persistent audit log to relational DB for regulatory inspection

**Repository:** `github.com/Niraj3006/sangam-band`
**Demo:** `uv run python -m orchestrator.run_case --case case_1_warfarin_guggulu`
