# Sangam — 3-Minute Demo Video Script

**Total runtime:** ~3 minutes
**Format:** Screen recording with voiceover; no face camera required.

---

## Section 1: Problem Statement (0:00 – 0:30)

**[Screen: title card — "Sangam" in large text, subtitle "Cross-System Polypharmacy
Safety Council", Track 3 badge]**

> "In India, over 70% of patients take both prescription medicines and daily Ayurvedic
> supplements — but almost no one checks whether they interact. A patient on warfarin
> for a heart condition adds guggul from their local pharmacy. Their CYP2C9 enzyme,
> already slowed by a genetic variant, is inhibited further. Their INR climbs silently.
> This interaction is documented in the literature, calculable from structural data,
> and entirely preventable — but only if someone connects those dots at the point of
> prescription."

**[Screen: transition to three panels — a journal citation, a molecular structure,
a patient chart — converging on a question mark]**

> "Sangam is a six-agent AI council that does exactly that — in under three minutes,
> for any drug–herb pair."

---

## Section 2: Live Demo (0:30 – 2:00)

**[Screen: Streamlit app, Tab 1 — Case Submission]**

> "We're looking at the Sangam Streamlit frontend. Tab 1 is the consumer-facing view.
> I'll select Case 1 — Warfarin plus Guggulu — a 68-year-old female, intermediate
> CYP2C9 metaboliser, mild renal impairment."

**[Click "Case details" expander to show the structured case JSON briefly]**

> "The case details show the drug compound, the herb's active compound guggulsterone Z,
> and the patient's pharmacogenomic profile. Now I'll hit Run Analysis."

**[Click ▶ Run Analysis; spinner appears]**

> "Six Band agents are now running in parallel. You can switch to Tab 3 — Agent
> Workspace — to watch them in real time."

**[Switch to Tab 3 — Agent Workspace]**

> "Here's the live Band room transcript, polling every five seconds. You can see
> @Intake has already parsed the case. @PatientProfile just posted a clearance
> modifier of 0.41 — that's a substantially compromised baseline from the *1/*3
> genotype and eGFR of 55. @StructuralBio found a curated docking entry: ΔG minus
> 8.4 kilocalories per mole at CYP2C9, high confidence, mechanism inhibition."

**[Pause as @PKPD and @EvidenceRAG messages appear]**

> "@PKPD ran the one-compartment PK simulation: AUC plus 150 percent, clearance
> down 60 percent. @EvidenceRAG found two high-severity findings from the clinical
> literature — published case reports of INR elevation and an in vitro CYP2C9
> inhibition study."

**[Switch back to Tab 1 as verdict card appears]**

> "And here's the verdict — RED. High risk, clinician review strongly recommended.
> @ComplianceGuard synthesised all five reports into this card."

**[Switch to Tab 2 — Physician View]**

> "Tab 2 is the physician view. The Plotly chart shows the baseline warfarin
> concentration curve in blue — peak around 1.2 micrograms per millilitre — and
> the combined curve in red, peaking above 3. The evidence table below lists both
> citations with severity ratings. This is the level of detail a clinical pharmacist
> would want before countersigning the prescription."

---

## Section 3: Architecture (2:00 – 2:30)

**[Screen: architecture diagram from docs/architecture.md or a clean slide]**

> "How does this work? Each of the six agents is a standalone Python process
> connected to a shared Band room. The pipeline is purely @mention-driven — no
> central orchestrator. @Intake tags @PatientProfile and @StructuralBio in parallel.
> Both independently tag @PKPD, which waits for both reports before running its
> simulation. @ComplianceGuard waits for all five before posting the verdict."

**[Screen: zoom into Band room transcript showing run_id tag]**

> "Every case is stamped with a unique eight-character run ID. All agents filter
> the room history by that ID, so a busy room with a hundred accumulated messages
> from prior test runs never contaminates a live analysis. This is a key reliability
> feature for any production deployment where the room stays alive across shifts."

---

## Section 4: Business Value + Closing (2:30 – 3:00)

**[Screen: return to title card with key metrics overlaid]**

> "India has 600 million regular Ayurvedic supplement users and an Ayurvedic market
> growing at 15% per year. The government AYUSH programme is actively integrating
> herbal medicine into the primary health system — and with it comes a regulatory
> responsibility that no one is currently meeting at scale."

> "Sangam is a Track 3 submission because every high-risk verdict requires a human
> clinician to sign off before it's finalised. That signature becomes part of the
> Band room transcript — auditable, timestamped, and attached to the structured
> verdict JSON. The system doesn't make clinical decisions. It makes sure the right
> person does."

**[Screen: repo URL and run command]**

> "The full source is at github.com/Niraj3006/sangam-band. Thank you."

---

## Production Notes

- **Screen resolution:** record at 1920×1080; export at 1080p.
- **Voiceover pace:** ~130 words/minute to hit the 3-minute mark comfortably.
- **Background music:** optional, low-volume ambient track; silence is fine.
- **Captions:** add auto-captions in the video editor for accessibility.
- **Cut points:** hard cuts between sections (no fades) keep the demo feeling crisp
  and functional rather than polished-but-slow.
- **Demo prep:** have the Streamlit app already running at `localhost:8501` and all
  6 agents started via `bash scripts/start_agents.sh` before beginning the recording.
  Clear any lingering verdict from `st.session_state` by refreshing the page.
