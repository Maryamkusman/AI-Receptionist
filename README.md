# AI-Receptionist
FullChair — AI Front Desk for Beauty Salons
Sep 29, 2026 · @maryam
Overview
FullChair is an AI front desk that keeps salon chairs booked: it answers every call, text and Instagram DM, books into the salon's existing software, and refills cancellations automatically. It sells on one promise salon owners already measure: fewer empty chairs.

Salons lose revenue in three places no one on staff has time to fix — inquiries that go unanswered while stylists are mid-service, 
cancellations and no-shows that leave slots empty, 
and regulars who quietly stop rebooking. 
FullChair works all three, 24/7, in the salon's own voice.

"FullChair" is a working name; the product is a WDZ Solutions offering.
Target customer and problems

The first customer is an independent salon with 3–15 chairs and no full-time receptionist: the owner or stylists answer the phone between clients. Hair salons first, then lash, brow, nail and med-spa studios, which run the same appointment model.

Problem
What it looks like in the salon
What FullChair does
Missed inquiries
Phone rings during a color service; a DM sits unread overnight; the client books elsewhere
Answers calls, texts and DMs instantly, quotes services and books the slot
Empty slots
A same-day cancellation or no-show leaves a 1–3 hour gap
Takes deposits up front, then texts the waitlist and fills the gap
Lapsed regulars
A client due for a root touch-up never rebooks
Sends a personal nudge when each client's usual interval passes
Front-desk load
Stylists spend breaks confirming, rescheduling and answering "how much is balayage?"
Handles FAQs, confirmations and reschedules without staff
Why they buy: every row maps to a booked appointment, which the owner can see in their own booking software. The sale is about revenue recovered, not AI.
Open question: which of the four pains owners rank highest — validate in the first 10 discovery calls.
Product features
FullChair has five modules; each maps to one of the problems above and can be sold separately inside a tier.
1. AI receptionist (calls, SMS, Instagram DMs) — one agent across every channel, trained on the salon's service menu, prices, stylists, policies and tone. Answers questions, handles "can I get in Saturday with Jess?", and hands off to a human with a summary when it's unsure.
2. Direct booking and deposits — reads live availability from the salon's booking software, books the appointment, and sends a payment link for a deposit on long or high-value services.
3. Cancellation refill — when a slot opens, texts matching clients on the waitlist (right service length, preferred stylist, flexible-time flag) and books the first to confirm.
4. Rebooking nudges — tracks each client's typical visit interval by service and sends a personal message with two open times when they're due.
5. Owner dashboard — conversations handled, appointments booked by the AI, slots refilled, and estimated revenue recovered. This screen is what renews the subscription.
Out of scope for v1: marketing campaigns, reviews management, inventory and payroll. Salons already have tools for these, and they dilute the pitch.
Packaging and pricing
Three tiers, each a one-time setup plus a monthly subscription; prices below are proposed starting points to test in the first sales conversations.
Tier
Who it's for
Includes
Setup (USD)
Monthly (USD)
Starter
Solo studios, 1–3 chairs
Text + Instagram DM receptionist, direct booking, deposits, dashboard
500
199
Pro
Salons, 4–15 chairs
Starter + voice receptionist + cancellation refill
1,000
399
Growth
Busy or multi-location salons
Pro + rebooking nudges, multiple locations, monthly performance review
1,500
699
Setup covers loading the service menu, prices, policies and stylist rules; tuning the brand voice; connecting booking, phone and Instagram; and a two-week supervised launch.
ROI framing for the pitch. Use the owner's own numbers: recovered appointments per month × average ticket. For example, at an assumed $120 average ticket, one recovered booking per weekday (about 22 a month) is roughly $2,640 a month against a $399 Pro plan.
Risk reversal. Offer a 30-day pilot on Pro: if the dashboard doesn't show recovered bookings worth more than the monthly fee, the salon cancels and pays no setup.
System architecture
All three channels hit one FastAPI backend, which routes each message to a single AI agent; the agent acts only through tools that call the salon's booking platform and Stripe.
Workers run the same tools on a schedule for refill outreach, nudges and booking sync, so the agent and the jobs never book the same slot two different ways. The booking platform stays the source of truth; FullChair's appointments table is a mirror for the dashboard.
Agent tools: check_availability, create_booking, reschedule_booking, cancel_booking, send_deposit_link, add_to_waitlist, lookup_service_info (RAG over the salon's menu and policies), handoff_to_human.
Integration risk: booking-platform API access decides launch scope. Confirm which platforms your first salons use and whether each offers a public or partner API before building.
Data model and key workflows
Every table carries a salon_id so one database serves all tenants with row-level isolation.
Entity
Key fields
Purpose
salons
name, timezone, booking_platform, voice/tone settings, policies
Tenant config and the agent's persona
services
name, duration_min, price, deposit_required, stylist_ids
What the agent can quote and book
stylists
name, specialties, booking_platform_id
Matching "with Jess" requests
clients
name, phone, ig_handle, preferred_stylist, visit_interval_days, opt_in
Identity across channels, nudges, consent
conversations / messages
channel, direction, text, handoff_flag
Full history for context and audit
appointments
external_id, service_id, start, status, booked_by_ai
Mirror of the booking platform; drives the dashboard
waitlist
client_id, service_id, preferred_times, flexible
Refill candidates
ai_traces
prompt, retrieved_context, tool_calls, tokens, latency
Debugging, evals, cost tracking
Inbound booking
1. A call, SMS or DM arrives via its webhook; the backend matches or creates the client.
2. The agent loads salon config, the client's history and the conversation so far.
3. It calls check_availability, offers two or three times, then create_booking once the client confirms.
4. If the service needs a deposit, it sends a payment link; the slot is held until payment clears or a timeout releases it.
5. Unsure or upset client → human handoff: the salon gets a text with a summary and the thread is flagged.
Cancellation refill
1. The booking platform's webhook (or a sync poll) reports a cancellation.
2. A worker ranks waitlist clients by service fit, stylist preference and time flexibility.
3. It texts the top candidates in small batches; the first confirmation books the slot and the rest get a polite "it's taken" reply.
Rebooking nudge
1. A daily job finds clients past their usual interval with no future appointment.
2. It sends a personal message with two open times, respecting opt-outs and quiet hours.
Tech stack, security and reliability
The stack stays small: one Python backend, one Postgres database, one queue, and managed services for voice and messaging.
Layer
Choice
Why
Backend API + agent
FastAPI (Python), Anthropic SDK with tool use
Matches your existing agent work; tool calling fits booking actions
Database
Postgres (Supabase or Neon) with pgvector
Tenants, conversations and salon knowledge in one place
Jobs
Redis + a worker (RQ or Celery)
Refill outreach, nudges, booking sync
Voice
A managed voice-agent platform or Twilio Voice with streaming speech
Low-latency phone calls without building telephony
SMS
Twilio (with A2P 10DLC registration)
Required for business texting in the US
Instagram DMs
Meta Messenger / Instagram messaging API
Needs a business account and app review
Payments
Stripe payment links
Deposits without handling card data
Owner dashboard
Next.js on Vercel
Fast to build, easy to brand
Local dev / deploy
Docker Compose locally; Render, Railway or Fly.io for the API
Simple ops for a small team
Security and privacy
• Tenant isolation on every query; per-salon API credentials encrypted at rest.
• No card data touches FullChair: deposits go through Stripe-hosted links.
• SMS consent and opt-out ("STOP") honored on every outbound message; quiet hours by salon timezone.
• Client data is used only for that salon; nothing is shared across tenants or used for other clients.
Reliability
• The agent never confirms a booking until the platform API confirms it.
• If the booking API or model is down, the agent takes a message and alerts the salon rather than guessing.
• Every conversation is traced, so a complaint about a wrong answer can be replayed and fixed.
• Hard caps on messages per conversation and outbound texts per day per salon.