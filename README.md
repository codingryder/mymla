# MyMLA WhatsApp Chatbot

Bilingual (Malayalam / English) WhatsApp chatbot connecting constituency
citizens to their elected MLA. Built per `MyMLA_Chatbot_Detailed_BRD.pdf` v1.0.

Reference architecture: sibling **Jantra Civic** bot.

## Features (per BRD)

**Phase 1 — Onboarding (5 steps):** Language → Aadhaar (opt) → Ward (26 list) →
Booth (opt, ward-scoped, paginated) → PIN (mandatory).

**Phase 2 — Main Menu:**
1. 📝 Complaint Registration (5-stage flow with voice + image support, max 5 images)
2. 🗓 Schedule a Meeting (agenda → summary → preferred window)
3. 📍 Where is my MLA (live status card)
4. ✉️ Invite for an Event (name → datetime → venue → asset upload)
5. 📊 View Program Chart (7-day public events)

**Cross-cutting:** 30-minute session retention guard, bilingual UI at every node,
voice notes via Sarvam STT (Malayalam + English), images via Meta Cloud media API.

## Stack

| Layer        | Tech                                            |
|--------------|-------------------------------------------------|
| Web          | FastAPI + Uvicorn                               |
| WhatsApp     | Meta Cloud API (Graph `/messages`)              |
| Storage      | Postgres (Neon) via psycopg2                    |
| Voice STT    | Sarvam AI `saarika:v2.5` (`ml-IN`, `en-IN`)     |
| Ops alerts   | SendGrid email                                  |
| Hosting      | Render (auto-deploy from `main`)                |

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill the values
uvicorn bot:app --reload --port 8000
```

Expose the local port to Meta via ngrok and register the webhook URL +
`META_WEBHOOK_VERIFY_TOKEN` in the Meta App dashboard.

## MLA office admin console

The bot mounts an HTTP Basic Auth-protected admin console at `/admin/*` for
the MLA's office to triage citizen submissions.

```
GET /admin/                    Landing page with links to each console
GET /admin/tickets             Citizen complaints, filterable by ?status= and ?ward_id=
                               status: ALL | OPEN | IN_PROGRESS | RESOLVED | CLOSED
                               limit:  1–500 (default 50)
```

Set `ADMIN_USERNAME` + `ADMIN_PASSWORD` in `.env` (and on Render) before going
live. If either is blank, every `/admin/*` request returns `503` — fail-closed.

## Seed demo data

The `📍 Where is my MLA` and `📊 Program Chart` menu options read from
`mla_location` and `mla_schedule`. Before the MLA's office supplies real
content, you can seed plausible demo rows:

```bash
# from repo root, with NEON_DSN populated in .env
PYTHONPATH=. python3 scripts/seed_demo_data.py            # idempotent for location, appends to schedule
PYTHONPATH=. python3 scripts/seed_demo_data.py --reset    # wipes both tables first
PYTHONPATH=. python3 scripts/seed_demo_data.py --only location
```

Replace with real entries once available — keep the script as the canonical
"what does fresh demo data look like" reference.

## Tests

```bash
pip install pytest
PYTHONPATH=. pytest tests/ -v
```

## Deploy to Render

1. Push the repo to GitHub.
2. Create a new Render Web Service pointing at the repo.
3. Build command: `pip install -r requirements.txt`.
4. Start command: from `Procfile` (`uvicorn bot:app --host 0.0.0.0 --port $PORT`).
5. Add every env var from `.env.example`.
6. After deploy, register the public URL `https://<service>.onrender.com/webhook`
   in Meta App → WhatsApp → Configuration.

## Repo layout

```
mymla-bot/
├── bot.py                # FastAPI app + webhook
├── cloud_api.py          # Meta WhatsApp Cloud API helpers
├── db.py                 # Postgres state + schema + ticket id generator
├── strings.py            # Bilingual ML/EN copy (STRINGS[lang][key])
├── wards.py              # 26-ward + booth master data (BRD §4)
├── session.py            # 30-min retention guard
├── media.py              # Inbound media downloader
├── voice.py              # Sarvam STT wrapper
├── alerts.py             # SendGrid ops alerts
├── admin.py              # MLA office admin console (Phase 3)
├── handlers/             # One module per BRD flow
│   ├── onboarding.py     # Phase 1
│   ├── menu.py           # Phase 2
│   ├── complaint.py      # §6 (5-stage)
│   ├── meeting.py        # §7.1
│   ├── location.py       # §7.2
│   ├── event.py          # §7.3
│   └── schedule.py       # §7.4
├── scripts/
│   └── seed_demo_data.py # Seed mla_location + mla_schedule with demo rows
└── tests/                # State-machine + security + seed-script tests
```
