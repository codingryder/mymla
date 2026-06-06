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
├── handlers/             # One module per BRD flow
│   ├── onboarding.py     # Phase 1
│   ├── menu.py           # Phase 2
│   ├── complaint.py      # §6 (5-stage)
│   ├── meeting.py        # §7.1
│   ├── location.py       # §7.2
│   ├── event.py          # §7.3
│   └── schedule.py       # §7.4
└── tests/                # Onboarding + complaint state-machine smoke tests
```
