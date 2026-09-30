# Running FullChair

FullChair has two parts:

| Folder | What it is | Runs on |
|---|---|---|
| `backend/` | FastAPI API, the Claude receptionist agent, channel webhooks, refill + nudge jobs | http://localhost:8000 |
| `dashboard/` | Next.js owner dashboard | http://localhost:3000 |

## Quick start

```bash
./dev.sh
```

Then open **http://localhost:3000**. The first run installs dependencies and seeds a demo salon
("Juniper Hair Studio") with a team, service menu, clients, 90 days of history and sample conversations.

Everything works without any accounts — FullChair runs in **demo mode**:

- **No `ANTHROPIC_API_KEY`** → a simple scripted receptionist answers so you can click through every flow.
- **No Twilio** → outbound texts are recorded in *Refill & nudges → Texts sent* instead of delivered.
- **No Stripe** → deposit links open a built-in demo checkout page.
- **Booking platform `demo`** → FullChair's own calendar acts as the booking system.

## Going live

Copy `backend/.env.example` to `backend/.env` and fill in what you have:

| Setting | Turns on |
|---|---|
| `ANTHROPIC_API_KEY` | The real Claude receptionist (`claude-opus-5-5` by default, `FULLCHAIR_MODEL` to change) |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` | Real SMS + voice. Point the Twilio number's webhooks at `PUBLIC_BASE_URL/webhooks/twilio/sms` and `/webhooks/twilio/voice` |
| `META_PAGE_ACCESS_TOKEN`, `META_VERIFY_TOKEN` | Instagram DMs via `PUBLIC_BASE_URL/webhooks/instagram` |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Real deposit checkout; send `checkout.session.completed` to `/webhooks/stripe` |
| `DATABASE_URL` | Postgres instead of SQLite (`postgresql+psycopg://…`, install `psycopg[binary]`) |
| `PUBLIC_BASE_URL` | Your public API URL (ngrok locally; Render/Railway/Fly in production) |

Restart the API after changing `.env`. The dashboard's **Settings → Plan & connections** shows what's connected.

## Handy commands

```bash
cd backend
.venv/bin/python -m app.seed --reset   # wipe and reseed the demo salon
curl -X POST localhost:8000/api/jobs/run   # run refill batches, nudges, hold expiry now
```

## Where things live

- `backend/app/agent/` — system prompt, the 8 agent tools, the Claude tool-use loop, and the demo agent
- `backend/app/integrations/` — booking platform, payments and messaging adapters (add a real booking platform by implementing `BookingPlatform`)
- `backend/app/workers/` — cancellation refill, rebooking nudges, scheduler
- `backend/app/routes/` — dashboard API and channel webhooks
- `dashboard/src/app/` — one folder per dashboard page

## Not yet built

- A real booking-platform connector (Vagaro, Boulevard, Square…) — confirm which platforms your first salons use, then implement `BookingPlatform` for it.
- Jobs run in-process on a timer; for multiple API instances, move `run_all_jobs` onto Redis + RQ/Celery.
- Knowledge lookup is keyword search; switch to pgvector embeddings once salons' FAQs grow.
- Dashboard login / multi-salon switching (the API already scopes every query by salon).
