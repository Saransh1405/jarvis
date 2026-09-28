# JARVIS — Production Roadmap v2 (Mainstream-User Pivot)

**Supersedes:** JARVIS_Roadmap.md (v1, "learn by building" ordering)
**Why this exists:** v1 optimized phase order for *your* learning path (MCP → RAG → agents → integrations). v2 optimizes for *a stranger's* trust and time-to-value. Same 7-phase discipline, same monorepo/Go-Python split, same "unbuilt = stub with a TODO" rule — the *order* and *what counts as done* changed, not the engineering principles.

**Ground rule, unchanged:** every phase ends deployable and demoable — but "demoable" now means demoable *to someone who is not you and has never heard of JARVIS*, not just "works when I curl it."

---

## Phase Map

| # | Phase | Core Question It Answers | Status |
|---|-------|---------------------------|--------|
| 1 | Foundation | Can I talk to JARVIS, live? | ✅ Done |
| 2 | Memory & Persistence | Does JARVIS remember *me specifically*, across sessions? | ← current |
| 3 | Reach | Can a stranger reach JARVIS and get value in 2 minutes, no help from me? |  |
| 4 | Action | Can JARVIS touch my calendar/email, safely, with a real yes/no? |  |
| 5 | Proactive Value + Pilot | Does JARVIS reach out first, and do real users trust it? |  |
| 6 | Depth (pilot-driven) | What did real users actually ask for? |  |
| 7 | Voice & Hardening | Can it hear me, and can it hold up at scale? |  |

---

## Phase 1 — Foundation ✅ Done

Go gateway + Python AI service, streaming chat, Docker stack, real LLM provider wired in. No change here — carried forward as-is. Frontend/deploy/CI, previously listed as "remaining Phase 1 work," are **not lost** — they're absorbed into the new Phase 3 (Reach), which is a better home for them now that reach is a first-class goal instead of an afterthought.

---

## Phase 2 — Memory & Persistence

**Ships:** A multi-user JARVIS. Two different people can each have a private, persistent conversation with their own memory, and JARVIS can execute basic tools on their behalf.

**Build:**
- **Real user accounts** — signup/login replacing the dev-only JWT stub, sessions, and a `user_id` convention applied everywhere from here on
- **Postgres persistence** — `users`, `conversations`, `messages` tables, wired into the orchestrator so chat survives a restart
- **Tool-calling loop** — the LLM→tool→result→LLM cycle, starter tools (`calculator`, `save_note`, `get_note`, `set_reminder`), policy tiers *classified* (Safe/ConfirmRequired/AlwaysConfirm) but the actual approval-pause mechanism still deferred to Phase 4 — unchanged from the earlier decision, and now clearly justified: Phase 2's tools are all Safe-tier anyway, Phase 4's calendar/email tools are where "confirm" first has teeth
- **Graphiti memory, per-user scoped** — every memory node tied to a `user_id`, hooked into the orchestrator at two points: "save something worth remembering," "retrieve relevant memory before responding"

**Production-ready checklist:**
- [ ] Two different accounts see completely separate conversations and memory — no leakage
- [ ] Chat and memory both survive a full stack restart
- [ ] Tool calls execute, are logged, and are tied to the user who triggered them
- [ ] You can ask "what did I tell you last week" and get a correct, private-to-you answer

**Demo:** You and a second test account both talk to JARVIS. Each has a private history. You tell it something, restart the whole stack, it still knows — and the other account never sees it.

```
              USER A                          USER B
                │                                │
                ▼                                ▼
          ┌─────────────────────────────────────────┐
          │      Go Gateway (auth, real sessions)      │
          └───────────────────┬─────────────────────┘
                              │  user_id attached to every request
                    ┌─────────▼─────────┐
                    │  Python Orchestrator │
                    │  (tool-calling loop) │
                    └─────────┬─────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                  ▼
      ┌───────────┐   ┌───────────────┐   ┌─────────────┐
      │  Postgres  │   │ Tool Registry  │   │  Graphiti    │
      │ users,     │   │ (calculator,   │   │  Memory      │
      │ conversa-  │   │  notes,        │   │  (per-user   │
      │ tions,     │   │  reminders)    │   │  scoped,     │
      │ messages   │   │ Policy: Safe   │   │  Neo4j)      │
      │(per-user)  │   │ only enforced  │   │              │
      └───────────┘   └───────────────┘   └─────────────┘
```

---

## Phase 3 — Reach

**Ships:** JARVIS is reachable by an actual non-technical person, at a real URL, and they get to a useful first reply within about two minutes with zero explanation from you.

**Build:**
- Hosted deployment + HTTPS domain (Fly.io/Railway — same recommendation as before, just moved up in priority)
- **One channel**, chosen deliberately: a simple web chat is fastest to ship with no third-party approval wait; Telegram is a cheap second option if you want something that feels less like "a website" to a mainstream user. WhatsApp Business API is the most trusted channel for this audience but has an approval/setup lag — worth planning for later, not blocking Phase 3 on it.
- 2-minute onboarding: signup → first message → useful reply, no setup screens in between
- CI (GitHub Actions) — now genuinely needed, since there's a real deploy to protect
- Basic uptime monitoring on `/health`

**Production-ready checklist:**
- [ ] A non-technical friend can sign up and get a useful reply in under 2 minutes, unassisted
- [ ] Live HTTPS domain, monitored
- [ ] CI blocks a broken build from reaching the deploy

**Demo:** Send a real non-technical friend a link or bot handle with zero instructions. Time how long until they get a useful reply. Target: under 2 minutes.

```
      Non-technical friend's phone
                  │
          (web link OR Telegram)
                  │
                  ▼
        ┌───────────────────┐
        │  HTTPS domain +     │
        │  Go Gateway (deployed)│
        └─────────┬──────────┘
                  │
                  ▼
         Python Orchestrator
         (Phase 2 stack, now
          reachable from outside)
                  │
                  ▼
          Signup → first message
          → reply, under 2 min

   CI: GitHub Actions gates every deploy
   Monitoring: uptime ping on /health
```

---

## Phase 4 — Action

**Ships:** JARVIS can read and act on calendar + email, with every write/send action shown to the user as a plain "Yes/No" — this is where the policy engine's ConfirmRequired/AlwaysConfirm tiers stop being log lines and start being a real UI gate.

**Build:**
- Real MCP server implementation (finally exercised, not just scaffolded) exposing calendar + email tools
- OAuth — start with Google (calendar + Gmail), since that covers the largest share of mainstream users
- Plain-language approval UI: "Send this reply? Yes/No" — the actual mechanism deferred from Phase 2, built now because it's finally load-bearing
- Tiers applied concretely: read calendar/email = Safe (auto-runs); draft a reply/create an event = ConfirmRequired; send an email = AlwaysConfirm

**Production-ready checklist:**
- [ ] User connects calendar + email through OAuth in the UI — no manual config, no `.env` editing by the user
- [ ] JARVIS answers real questions from real calendar/email data
- [ ] Any send/create action shows an actual approve/deny prompt, not just a log entry
- [ ] Revoking access in the Google account cleanly breaks the integration, no silent failure loop

**Demo:** "What's on my calendar today, anything important in my inbox?" — correct real answer. "Reply saying I'll be there" — approval prompt appears — user taps Yes — it sends.

```
        User (via Phase 3 channel)
                  │
                  ▼
         Python Orchestrator
                  │
                  ▼
       ┌─────────────────────┐
       │  Go MCP Server (real) │
       │  get_calendar()        │
       │  get_email()            │
       │  draft_reply()            │
       │  send_email()               │
       └──────────┬──────────────┘
                  │
        ┌──────────┴──────────┐
        ▼                     ▼
   Policy tier check     OAuth token store
   Safe → auto-run       (Google, encrypted,
   Confirm/Always →      refreshed)
   "Yes/No" prompt              │
        │                       ▼
        ▼                Google Calendar / Gmail API
   User taps Yes/No
        │
        ▼
   Execute → log → result back to user
```

---

## Phase 5 — Proactive Value + Pilot

**Ships:** JARVIS reaches out on its own, its memory is visible and editable (not a black box), and it's been used by 5–10 real people long enough to generate real feedback.

**Build:**
- Daily brief — scheduled job pulling from calendar + email (Phase 4), delivered through the Phase 3 channel, unprompted
- Reminders/follow-ups — proactive nudges, not just reactive replies
- **"What I know about you" screen** — a plain-language, editable view into Graphiti memory; this turns memory from backend infra (Phase 2) into a trust surface, which matters a lot for an audience that doesn't already trust AI assistants with their data
- Recruit and onboard 5–10 real pilot users; log usage and feedback deliberately, not just impressions

**Production-ready checklist:**
- [ ] Daily brief arrives without being asked
- [ ] The memory screen accurately reflects what's stored, and edits/deletes there actually change what JARVIS uses
- [ ] 5–10 real users are onboarded and have used it for multiple days
- [ ] Feedback is written down somewhere, not just remembered

**Demo:** A pilot user wakes up to an unprompted morning brief, opens "what I know about you," edits one entry themselves, and you have their written feedback in hand.

```
        Scheduled job (daily)
                  │
                  ▼
        Pull calendar + email (Phase 4)
                  │
                  ▼
        Deliver brief via channel (Phase 3)
                  │
                  ▼
              User's phone
                  │
                  ▼
     "What I know about you" screen
     (reads Graphiti memory, Phase 2)
                  │
        user edits/deletes an entry
                  │
                  ▼
     Change reflected back into Graphiti
                  │
                  ▼
     5-10 pilot users → feedback log
     (this feedback drives Phase 6)
```

---

## Phase 6 — Depth (pilot-driven)

**Ships:** Whatever the pilot actually asked for — RAG, more integrations, or planning/multi-agent — built because real users hit a real wall, not because the roadmap said so.

**Build:** Deliberately not pre-specified. Candidates from the old plan (document RAG, agentic multi-hop retrieval, multi-agent planning, a coding agent) all still live here conceptually, but nothing gets built until pilot feedback names it. This is the one phase whose *build* section should be written after Phase 5, not before.

**Production-ready checklist:**
- [ ] Every feature shipped here traces back to a specific pilot request or observed pain point
- [ ] The feature is validated with the pilot users who asked for it, not just shipped and assumed

**Demo:** Whatever the top pilot request was — solved, shipped, and shown back to the users who asked for it.

*(Architecture diagram deferred until scope is known — this phase's diagram gets written once Phase 5 feedback picks the direction.)*

---

## Phase 7 — Voice & Hardening

**Ships:** JARVIS can be talked to out loud, and the whole system holds up under real multi-user, concurrent load.

**Build:**
- Voice: STT in, TTS out, wired into the existing tool/agent loop (unchanged from v1)
- Multimodal (images/screenshots) if pilot feedback in Phase 6 didn't already pull it forward
- Full production hardening: real secrets vault, per-user rate limiting/queues, k8s + Terraform, backups with a tested restore, full eval suite (cost/latency/hallucination/tool-selection accuracy)

**Open question, flagging rather than deciding silently:** v1 had a computer-use / browser-control capstone (Phase 13) and a coding agent (part of old Phase 9/12). Neither serves a mainstream non-technical user directly, so they don't have an obvious home in v2. Options: drop them from the roadmap entirely, or keep computer-use folded into this phase as a stretch item, or keep the coding agent as a separate internal/developer-facing feature outside the main user-facing roadmap. Worth a decision before Phase 6 scoping, not urgent now.

**Production-ready checklist:** same as v1's Phase 7 (multi-user isolation proven, restore drill actually run, dashboards for cost/latency/errors, load-tested).

*(Diagram unchanged from v1 Phase 7 — voice/multimodal is a new input path into the same hardened core.)*

---

## What Changed vs. v1 — Full Diff

- **Frontend + deploy + CI**, previously scattered as "leftover Phase 1 work" with no real urgency, are now the explicit mission of **Phase 3 (Reach)**, moved immediately after memory instead of being indefinitely deferred.
- **User accounts + per-user memory scoping** are new — v1 never had multi-user as a concept until Phase 7 (Hardening). Now it's in Phase 2, because reach and pilots are meaningless without it.
- **Integration scope narrowed:** v1's Phase 4 said "start with GitHub or Calendar, Gmail last." v2's Phase 4 is calendar + email only, GitHub dropped from the near-term roadmap entirely — it doesn't serve the mainstream-user goal.
- **Approval mechanism placement is unchanged, but its *form* changed.** Both versions deferred the actual pause-and-wait mechanism to what's now Phase 4 — that earlier call holds up. What's new is that it must render as a plain "Yes/No" prompt, not a generic API confirmation endpoint.
- **Proactivity (daily brief, reminders) is entirely new** — v1 had no proactive behavior anywhere in the 7 phases.
- **The "what I know about you" memory screen is entirely new** — v1 treated Graphiti purely as backend infra with no required UI.
- **A 5–10 user pilot is a new, explicit gate** — v1 had no user-testing checkpoint; features were built in a fixed order regardless of demand.
- **RAG and multi-agent planning (old Phases 3 and 5) are merged into Phase 6 and made conditional on pilot feedback**, instead of being built on a fixed schedule.
- **Voice/multimodal and hardening (old Phases 6 and 7) are merged into Phase 7**, both pushed later since neither blocks reach or trust.
- **Computer-use and the coding agent lost their explicit home** — flagged above as an open question rather than silently dropped.
- **Unchanged, as requested:** monorepo structure, Go/Python boundary, "every phase independently deployable," unbuilt parts stay as stubs with phase-numbered TODOs.

---

## Phase 2 Task List — In Order of What Unblocks What

1. **Real user accounts & auth** (signup/login, sessions, `user_id` convention) — do this first because *everything else* in Phase 2 needs to know whose data it's touching. Building persistence or memory before this means retrofitting scoping into both later.
2. **Postgres schema + persistence wiring** (`users`, `conversations`, `messages`, all `user_id`-scoped) — depends on step 1 for the `user_id` to attach to. This is also where tool-call messages will get logged in step 3, so it needs to exist first.
3. **Tool-calling loop + starter tools + policy tier classification** — depends on step 2 existing so tool calls/results have somewhere to be persisted as part of conversation history. Policy tiers get *classified* here (Safe/ConfirmRequired/AlwaysConfirm labels on each tool) but only Safe-tier is actually enforced — no approval UI yet, that's Phase 4.
4. **Graphiti memory, per-user scoped** — depends on step 1 (needs `user_id` to scope memory nodes) and benefits from step 2/3 existing (conversation history and tool interactions are what memory will often be extracted from). Sequenced last because it's the most novel piece technically — better to build it on a stable, already-scoped foundation than debug auth, persistence, and a new memory library all at once.

Note: steps 3 and 4 don't strictly depend on *each other* — you could build them in parallel if you wanted. Sequencing memory last is a "reduce the number of unknowns you're debugging at once" choice, not a hard dependency.
