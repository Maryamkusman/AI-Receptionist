# FullChair: AI Front Desk for Salons

An AI receptionist that answers salon clients over SMS, voice, and Instagram DMs, books and reschedules appointments, collects deposits, and automatically refills cancelled slots from a waitlist. Salon owners see everything in a live dashboard.

Built with **FastAPI**, **SQLAlchemy**, the **Anthropic SDK** (Claude tool use), and a **Next.js + TypeScript** dashboard.

<!-- Add a screenshot of the dashboard here -->
<!-- ![FullChair dashboard](docs/dashboard.png) -->

## What it does

- **AI receptionist.** One Claude-powered agent handles conversations across SMS, voice, and Instagram DMs. It answers questions about services and prices, checks real availability, and books appointments. When it isn't sure, it hands the conversation to a human with a summary.
- **Deposits.** Sends a Stripe payment link for long or high-value services.
- **Cancellation refill.** When a slot opens, it texts matching waitlisted clients and books the first one to confirm.
- **Rebooking nudges.** Tracks each client's usual visit interval and messages them when they're due.
- **Owner dashboard.** Shows conversations handled, AI-booked appointments, refilled slots, and outbound messages.

## How the agent works

The receptionist runs a **Claude tool-use loop** (`backend/app/agent/runner.py`). Each incoming message goes to Claude along with the salon's context and eight tools it can call:

| Tool | Purpose |
|---|---|
| `check_availability` | Find open slots for a service and date range |
| `create_booking` | Book an appointment with a stylist |
| `reschedule_booking` | Move an existing appointment |
| `cancel_booking` | Cancel an appointment |
| `send_deposit_link` | Send a Stripe deposit link |
| `add_to_waitlist` | Add a client to the waitlist for a service |
| `lookup_service_info` | Answer questions from the salon's service menu and FAQs |
| `handoff_to_human` | Escalate to staff with a conversation summary |

Claude decides which tools to call, the backend executes them against the database, and the results go back to Claude until it has a final reply for the client. Every tool scopes its queries to the current salon.

## Architecture

```
SMS / voice (Twilio) ─┐
Instagram DMs (Meta) ─┼──► FastAPI webhooks ──► Claude agent ──► tools ──► database
Dashboard (Next.js) ──┘                              │
                                                     └──► Stripe deposit links

Background jobs (in-process scheduler): cancellation refill, rebooking nudges, hold expiry
```

| Folder | What's inside |
|---|---|
| `backend/app/agent/` | System prompt, tool definitions, tool-use loop, offline demo agent |
| `backend/app/integrations/` | Adapters for booking platforms, payments, and messaging |
| `backend/app/workers/` | Cancellation refill, rebooking nudges, job scheduler |
| `backend/app/routes/` | Dashboard API and channel webhooks |
| `dashboard/src/app/` | One folder per dashboard page |

Integrations sit behind adapter interfaces. For example, supporting a new booking system means implementing the `BookingPlatform` interface, with no changes to the agent.

## Tech stack

- **Backend:** Python, FastAPI, SQLAlchemy, Pydantic, Uvicorn
- **AI:** Anthropic SDK with Claude tool use
- **Database:** SQLite by default, PostgreSQL supported
- **Integrations:** Twilio (SMS and voice), Meta (Instagram DMs), Stripe (deposits)
- **Dashboard:** Next.js, React, TypeScript, Tailwind CSS

## Run it locally

Requires Python 3 and Node.js.

```bash
./dev.sh
```

Then open http://localhost:3000. The API runs on http://localhost:8000.

The first run installs dependencies and seeds a demo salon with stylists, a service menu, clients, 90 days of history, and sample conversations.

**No API keys needed to try it.** Without keys, the app runs in demo mode: a scripted agent stands in for Claude, texts are logged in the dashboard instead of sent, deposits open a demo checkout page, and the built-in calendar acts as the booking system.

To use real services, copy `backend/.env.example` to `backend/.env` and add any of the following:

| Setting | Enables |
|---|---|
| `ANTHROPIC_API_KEY` | The real Claude receptionist |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` | Real SMS and voice |
| `META_PAGE_ACCESS_TOKEN`, `META_VERIFY_TOKEN` | Instagram DMs |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Real deposit checkout |
| `DATABASE_URL` | PostgreSQL instead of SQLite |

See [SETUP.md](SETUP.md) for webhook setup and other details.

## Roadmap

- A connector for a real booking platform (such as Square or Vagaro)
- Move background jobs to a queue (Redis with RQ or Celery) to support multiple API instances
- Replace keyword search in `lookup_service_info` with pgvector embeddings as FAQ content grows
- Dashboard login and multi-salon switching (the API already scopes every query by salon)

## Author

Built by [Maryam Usman](https://maryamusman.com).
