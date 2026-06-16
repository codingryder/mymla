# MyMLA Build Plan

End goal: **live deployment for an actual MLA's office**. Cadence: 1-2 evenings/week,
~1-2 hours each. Each chunk below is sized to fit one session and end with something
runnable or verifiable.

Last updated: 2026-06-16.

---

## Phase 0 — Lock down the foundation _(~4 sessions)_

The scaffold is mostly wired but only 2 of 6 flows have tests. Don't extend on shaky
ground.

- [x] **0.1** Tests for **meeting + event** flows — `tests/test_meeting.py`,
      `tests/test_event.py` _(done 2026-06-16; 4 tests added, 6 total passing)_
- [x] **0.2** Tests for **location + schedule** flows + **session timeout** —
      `tests/test_location.py`, `tests/test_schedule.py`, `tests/test_session_timeout.py`
      _(done 2026-06-16; 10 tests added, 16 total)_
- [x] **0.3** Test for **webhook HMAC signature** + image cap (verify 6th image
      rejected) — `tests/test_webhook_security.py` _(done 2026-06-16; 7 tests added, 23 total)_
- [x] **0.4** **Seed scripts** for `mla_schedule` + `mla_location` —
      `scripts/seed_demo_data.py` _(done 2026-06-16; idempotent, --reset/--only
      flags, 5 tests added, 28 total)_

**Exit criteria:** `pytest tests/ -v` shows ~10+ passing, every BRD flow has at least
one test, demo data exists. **✅ MET (28 passing)**.

---

## Phase 1 — Real-phone smoke test _(~3 sessions)_

Meta is ready — get to a real conversation as fast as possible. This is where the BRD's
vague-but-confident prose meets reality.

- [ ] **1.1** Pick + deploy to a host (Render or Fly, with Neon Postgres) —
      public HTTPS URL, env vars set, `/webhook` verified by Meta
- [ ] **1.2** Walk through **onboarding + complaint** on real phone, log every bug
      to `docs/smoke-bugs.md` — voice transcription, image upload, ward list rendering
- [ ] **1.3** Walk through **meeting + event + location + schedule** on real phone

**Exit criteria:** end-to-end conversation works on the phone for all 5 menu options,
even if rough.

---

## Phase 2 — Fix what the smoke surfaced _(~2-4 sessions, variable)_

Whatever broke first — voice (Sarvam), images (Meta media URLs), session timeouts,
language toggling, etc. Cannot estimate until 1.2-1.3 produce the bug list.

---

## Phase 3 — MLA-office tooling _(~5 sessions)_ — non-negotiable for going live

The BRD doesn't mandate this, but you can't deploy without a way for the office to
actually handle tickets.

- [ ] **3.1** Ticket viewer — CLI command or `/admin/tickets` endpoint (HTTP basic
      auth) showing open tickets with filters
- [ ] **3.2** Ticket status updater — mark in_progress / resolved; send WhatsApp
      confirmation back to citizen
- [ ] **3.3** Schedule editor — insert/edit rows in `mla_schedule` (CLI first)
- [ ] **3.4** Location updater — set the "Where is my MLA" status card
- [ ] **3.5** Outbound status notifications — when a ticket changes state, notify
      the citizen via Cloud API

**Exit criteria:** the MLA's PA can do their job entirely from this tooling without
touching SQL.

---

## Phase 4 — Production hardening _(~4 sessions)_

- [ ] **4.1** Structured logging — replace `print(...)` with a proper logger, ship
      to a log aggregator
- [ ] **4.2** Rate limiting + abuse handling — per-phone floor, suspicious-content
      drop
- [ ] **4.3** Monitoring + alerting — uptime checks, error-rate alerts
      (UptimeRobot/Sentry)
- [ ] **4.4** Backups + secrets — Neon point-in-time recovery confirmed, secrets
      in a vault (not `.env`), rotation runbook

---

## Phase 5 — Pilot & launch _(~3 sessions)_

- [ ] **5.1** Closed pilot — MLA office + 5-10 trusted citizens use the bot for a
      week
- [ ] **5.2** Iterate on pilot feedback
- [ ] **5.3** Public soft launch — announce on MLA channels, monitor closely
      first 48h

---

## External dependencies (line these up in parallel)

- **MLA office input:** triage workflow, real `mla_schedule` + `mla_location`
  content, SendGrid alert recipients, local-leader directory
- **Branding/legal:** WhatsApp Business profile, privacy policy URL (required by
  Meta), data retention policy
- **Hosting decision:** Render vs Fly vs Railway — pick before 1.1
