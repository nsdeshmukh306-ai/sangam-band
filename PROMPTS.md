# Kickoff Prompts

Two prompts: one to paste into **Claude Code** (does the actual building), one to
give **Cowork** (keeps the 4-day sprint organized — daily logs, deliverable
checklist, file/asset management). Use them together: Cowork tracks progress across
sessions, Claude Code does the engineering inside each session.

Both assume `PROJECT_SPEC.md` (the companion file) is sitting in the repo root.

---

## A. Claude Code kickoff prompt

Run this from inside your new repo folder (after `git init`, after you've completed
the **Phase 0 manual Band setup** in PROJECT_SPEC.md Section 7, and after copying
`PROJECT_SPEC.md` into the repo root). Paste the whole block as your first message to
`claude`:

```
You are building "Project Sangam," a Band-of-Agents-Hackathon submission. The full
spec is in ./PROJECT_SPEC.md — read it completely before writing any code, and treat
it as the source of truth for architecture, agent roles, data schemas, repo
structure, and the phased timeline (Section 9).

Ground rules:
1. Work phase by phase exactly as laid out in Section 9 (Phase 0 → 4). After
   finishing each phase, stop, summarize what was built and tested, and wait for my
   go-ahead before starting the next phase.
2. Anything marked [VERIFY AGAINST DOCS] in the spec: before implementing that piece,
   fetch the relevant page(s) on docs.band.ai, confirm the actual API/SDK shape, and
   update PROJECT_SPEC.md + docs/architecture.md with what you found (including any
   deviation from the spec's assumptions). Don't guess and move on silently.
3. Never put real API keys, agent_ids, or secrets in any committed file. .env and
   agent_config.yaml must be in .gitignore from the very first commit. I will fill in
   the real values myself.
4. I'm on Windows 11 with WSL2 available, 8GB RAM. Prefer lightweight
   dependencies — no local LLMs, no heavy ML frameworks. All 6 agents call DeepSeek
   via its OpenAI-compatible API (cloud, `ChatOpenAI` + custom `base_url`), so each
   agent process itself should be lightweight.
5. Write small, runnable tests for the non-agent logic (PK/PD model, PGx rules,
   docking lookup, PubChem wrapper, RAG retrieval) as you build each piece — these
   don't require Band credentials and should pass without any live agent running.
6. Commit incrementally with clear messages. Keep README.md updated as you go (setup
   instructions should always reflect the current state of the repo).
7. For Phase 1-2, once an agent is implemented, tell me exactly how to start it
   (command) and what message to send in the Band room to test it — I'll run it
   locally and report back what happened, since you can't access my Band account.
8. If at any point the remaining scope looks too large for the time left (today is
   June 15, submission closes June 19), proactively propose what to cut (e.g., drop
   to 4 case studies, skip the AI/ML API / Featherless stretch, simplify the escalation
   to one round) rather than silently under-delivering on the core Band-coordination
   requirement — that part must work end to end no matter what gets cut.

Start with Phase 0: scaffold the repo exactly per Section 5, write the .gitignore,
.env.example, agent_config.example.yaml, LICENSE (MIT), pyproject.toml, and produce
the 5 case studies + supporting data files per Section 4. Show me the data files for
review before moving to Phase 1.
```

### Follow-up prompts for later sessions
When you come back for the next phase, just say:

```
Continue with Phase <N> of PROJECT_SPEC.md. Here's what happened when I tested the
previous phase: <paste your test results / errors / Band room transcript snippets>.
```

This keeps Claude Code anchored to the spec and gives it real feedback from the
actual Band platform (which it can't access directly).

---

## B. Cowork setup prompt

Use this once, at the start, to get a tracked project with a daily checklist for the
remaining 4 days. Paste into Cowork:

```
Set up a new project called "Project Sangam — Band Hackathon" for a 4-day sprint
(June 15-19, 2026, hard deadline June 19 for the lablab.ai Band of Agents Hackathon).

Project overview: a 6-agent system on Band (band.ai) that reviews Ayurvedic +
allopathic drug combinations for interactions and produces a clinician-reviewable
risk verdict, with a Streamlit frontend (Consumer / Physician / Agent Workspace
tabs). Full technical spec is in PROJECT_SPEC.md (I'll attach/paste it).

Please:
1. Break the work into the 5 phases from PROJECT_SPEC.md Section 9 (Phase 0-4), one
   per day, and create a checklist for each phase's deliverables as listed in that
   section.
2. Track the submission checklist separately: public MIT-licensed GitHub repo, live
   demo URL, cover image, video presentation, slide deck, project title + short/long
   description + tech tags — these are all due Phase 4 but I want them visible from
   day one so I don't forget.
3. Track the 7 manual Band-setup steps from Section 7 as a one-time checklist item
   for today, since Claude Code can't do those itself (account creation, agent
   registration in the Band UI, getting API keys).
4. At the end of each work session, run the end-of-day log so the next session picks
   up cleanly — note which phase we're on, what's blocked, and what Claude Code is
   waiting on from me (e.g., test results, Band credentials).
5. Each morning, give me a quick status: what's done, what's today's phase, and
   whether we're on track for June 19 — flag early if something needs to be cut per
   the spec's Phase 0-rule-8 fallback plan.
```

---

## Quick reference: what you (Niraj) must do manually, in order

1. Band account + promo code + personal API key (Spec §7.1-7.2).
2. Create 6 External Agents on Band, save their `agent_id`/`api_key` pairs into your
   local `agent_config.yaml` (not committed) (Spec §7.3).
3. Create the "Sangam Case Room" and add all 6 agents (+ yourself as `@Clinician`)
   (Spec §7.4).
4. Create the public GitHub repo (MIT license).
5. Get/confirm your `DEEPSEEK_API_KEY` (platform.deepseek.com).
6. (Optional, Phase 2 stretch) Claim AI/ML API ($10) and Featherless ($25) credits via
   the lablab.ai hackathon page.

Everything else — code, data, frontend, tests, docs — is Claude Code's job per
PROJECT_SPEC.md.
