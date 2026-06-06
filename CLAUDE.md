# Claude Code notes — MyMLA WhatsApp Chatbot

## What this repo is
A bilingual (Malayalam / English) WhatsApp chatbot for an MLA's constituency,
implementing `MyMLA_Chatbot_Detailed_BRD.pdf` v1.0. Modeled on the sibling
**Jantra Civic** bot's architecture (FastAPI + Meta Cloud API + Postgres).

## Conventions
- **Persistence**: a single `mymla_users` row per phone holds the active
  session state (`current_step`, `pending_flow`, `session_data` JSONB). Each
  flow lives in its own handler module; handlers mutate state via
  `db.set_field(phone, **fields)`.
- **Step naming**: `await_lang`, `await_aadhaar`, `await_ward`, `await_booth`,
  `await_pin` for onboarding; `complaint_*`, `meeting_*`, `event_*` for service
  flows. `handlers/__init__.py::dispatch` routes by prefix.
- **i18n**: every user-visible string lives in `strings.STRINGS[lang][key]`.
  Default `lang = "mal"`; English is the parallel path. Use the `t()` helper
  for safe lookups + `.format(**kwargs)` placeholders.
- **Logging**: `print(f"[Tag] ...", flush=True)` — no logging library, mirrors
  jantrabot. Common tags: `[Webhook]`, `[CloudAPI]`, `[Media]`, `[Voice]`,
  `[Session]`, `[DB]`, `[Alerts]`, `[Timing]`.
- **Session timeout**: 30 minutes (`SESSION_TIMEOUT_MINUTES` env override).
  Soft reset preserves profile (lang, ward, booth, PIN); hard reset wipes it.

## Webhook contract
- `GET  /webhook` — Meta subscription verify (`hub.verify_token`).
- `POST /webhook` — inbound; signature verified via HMAC-SHA256 against
  `META_APP_SECRET`. Real work runs in a FastAPI `BackgroundTask` so we ack 200
  within Meta's retry window.
- `POST /webhook/status` — message-status callback, currently a no-op log.

## Schema highlights (`db.py`)
- `mymla_users(phone PK, preferred_language, aadhaar_number, ward_id,
  booth_number, pin_code, onboarding_complete, current_step, pending_flow,
  session_data jsonb, session_last_active)`
- `mymla_complaints(ticket_id PK, phone, ward_id, booth_number, category,
  description_text, description_voice_url, image_media_ids text[],
  local_leader_ref, status)`
- `mymla_meetings`, `mymla_event_invites` — request queues for the MLA's office.
- `mla_schedule`, `mla_location` — read-only public-facing data.

## Ticket id format (BRD §6.5)
`MLA-GRI-WARD{NN}-{XXXXX}` where `XXXXX` is 5 random uppercase alphanumerics.
Generated in `db.generate_ticket_id`; uniqueness enforced via PK with 3-attempt
retry.

## Ward data
26 wards (Vanchiyoor → Attakulangara) with associated booth numbers in
`wards.py`. WhatsApp List Messages cap at 10 rows per section, so wards with
> 9 booths paginate (`paginate_booths`, `BOOTHS_PER_PAGE = 9`).

## Tests
`tests/conftest.py` mocks `psycopg2.connect` before importing `db`, so any
import-time SQL is a no-op. `tests/test_onboarding.py` patches `db.*` with an
in-memory fake store and `cloud_api.send_*` with an outbox capture to drive
end-to-end state-machine assertions.

```bash
PYTHONPATH=. pytest tests/ -v
```

## Things deliberately not in this repo
- A web admin / MLA's-office dashboard. Tickets are queryable directly via
  Postgres; a separate front-end can be added later.
- Gemini AI conversational fallback. The BRD is fully deterministic; `llm.py`
  is reserved for future enhancements only — it's not wired into the webhook.
- Twilio. Unlike the legacy Jantra Bot, this repo uses Meta Cloud API
  exclusively. Simpler, modern, full feature parity.

## Env vars
See `.env.example` — Meta Cloud API credentials, Neon DSN, Sarvam key,
SendGrid for alerts, plus a couple of MLA-identity fields.
