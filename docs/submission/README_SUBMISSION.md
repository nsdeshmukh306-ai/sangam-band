# Sangam — Cross-System Polypharmacy Safety Council

**Track:** Track 3 — Regulated & High-Stakes Workflows
**Team:** Niraj Deshmukh (IISER Tirupati)

---

## The Problem

India has the world's largest co-prescription challenge: over 70% of patients
visiting government hospitals receive both allopathic and Ayurvedic medicines
simultaneously, yet drug–herb interaction data is scattered across pharmacognosy
journals, clinical case reports, and structural-biology databases that no single
practitioner can synthesise in a consultation window. The consequences — INR
elevation from warfarin + guggul, immunosuppressant failure from tacrolimus + St.
John's Wort, electrolyte crises from digoxin + licorice — are well-documented but
routinely missed at the point of prescription.

## The Solution

**Sangam** (Sanskrit: *confluence*) is a six-agent safety council that replicates
the reasoning of a multidisciplinary team review in under three minutes. Each agent
is a specialist: **@Intake** parses the prescription, **@PatientProfile** computes
a pharmacogenomic clearance baseline, **@StructuralBio** queries curated binding-
affinity data for drug–herb compound pairs, **@PKPD** runs a one-compartment PK
simulation and quantifies AUC change, **@EvidenceRAG** retrieves ranked clinical
literature findings from a local ChromaDB index, and **@ComplianceGuard** synthesises
all five reports into a RED/YELLOW/GREEN risk verdict with a mandatory human-in-the-
loop escalation path.

Agents coordinate entirely through a Band room: **@mention routing** chains the
pipeline without a central broker, and **run-ID stamping** prevents data from one
case bleeding into another in a busy shared room. A Streamlit frontend exposes three
views — a consumer-facing traffic-light card, a physician-level PK chart and evidence
table, and a live agent workspace showing the full Band transcript.

## Key Results

- **Case 1 (Warfarin + Guggulu):** RED tier, AUC +150%, confidence high —
  correctly identified CYP2C9 inhibition by guggulsterone Z at ΔG = −8.4 kcal/mol.
- **Case 3 (Metformin + Karela):** YELLOW tier with low confidence — triggered the
  two-round @StructuralBio re-mention escalation, then PENDING_HUMAN_REVIEW because
  Metformin has no known CYP/P-gp structural target.
- **Case 4 (Tacrolimus + St. John's Wort):** RED tier, AUC −41% (induction, not
  inhibition) — correctly flagged subtherapeutic exposure / efficacy-loss risk.
- End-to-end latency: ~90–150 s per case using DeepSeek-Reasoner for the two
  reasoning-heavy agents and DeepSeek-Chat for the three extraction agents.

## Technology Stack

| Layer | Technology |
|---|---|
| Agent coordination | [Band SDK](https://band.ai) v1.0.0 (`band-sdk[langgraph]`) |
| LLM backbone | DeepSeek-Chat (extraction agents) + DeepSeek-Reasoner (StructuralBio, ComplianceGuard) |
| Agent graph | LangGraph with per-message `FreshGraphAdapter` (custom subclass) |
| Evidence retrieval | ChromaDB PersistentClient + custom embedding over 15 curated findings |
| PK simulation | SciPy-free one-compartment oral model (`agents/common/pkpd.py`) |
| Frontend | Streamlit 1.x — 3 tabs: consumer, physician, agent workspace |
| Structural data | Curated `data/docking_lookup.json` (CYP2C9/CYP3A4/P-gp/albumin targets) |
| Pharmacogenomics | Curated `data/pgx_rules.json` (CYP2C9 genotype × eGFR × age rules) |

## Human-in-the-Loop Design

`@ComplianceGuard` never withholds a verdict pending sign-off. A RED tier or
persistently-low confidence produces a `"status": "PENDING_HUMAN_REVIEW"` JSON block
in the same Band message that @mentions a clinician participant, making escalation a
visible part of the room transcript. The clinician's affirmative reply triggers a
follow-up `"status": "FINAL_VERDICT"` with a `"human_signoff"` attestation field.
This satisfies Track 3's requirement that high-stakes outputs remain under human
authority without making the system unresponsive when a reviewer isn't immediately
available.

## Repository

`github.com/Niraj3006/sangam-band`

```
uv run python -m orchestrator.run_case --case case_1_warfarin_guggulu
```
