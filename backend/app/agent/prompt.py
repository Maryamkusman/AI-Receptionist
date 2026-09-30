from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Appointment, Client, Conversation, Salon, Service, Stylist
from ..timeutil import DAY_KEYS, fmt_slot, salon_now

CHANNEL_STYLE = {
    "sms": "You are texting. Keep replies to 1–3 short sentences. No markdown, no bullet lists.",
    "instagram": "You are replying to an Instagram DM. Friendly and brief, 1–3 sentences, an emoji is fine. No markdown.",
    "voice": "You are on a phone call; your words are spoken aloud. Short, natural sentences. Never read out "
             "URLs, ids or symbols. Say times like 'two thirty on Saturday'.",
    "web": "You are chatting on the salon's website. 1–3 short sentences. No markdown.",
}


def _hours_text(hours: dict) -> str:
    parts = []
    for k in DAY_KEYS:
        span = (hours or {}).get(k)
        parts.append(f"{k.title()}: {'closed' if not span else f'{span[0]}:00–{span[1]}:00'}")
    return ", ".join(parts)


def stable_system_prompt(db: Session, salon: Salon) -> str:
    """Everything that changes rarely — kept first so it can be prompt-cached."""
    services: List[Service] = list(db.scalars(
        select(Service).where(Service.salon_id == salon.id, Service.active.is_(True)).order_by(Service.category, Service.id)))
    stylists: List[Stylist] = list(db.scalars(
        select(Stylist).where(Stylist.salon_id == salon.id, Stylist.active.is_(True))))
    by_id = {s.id: s.name for s in stylists}

    menu = "\n".join(
        f"- id {s.id}: {s.name} ({s.category}) — ${s.price:.0f}, {s.duration_min} min"
        + (f", ${s.deposit_amount:.0f} deposit required" if s.deposit_required else "")
        + (f", only with {', '.join(by_id.get(i, '?') for i in s.stylist_ids)}" if s.stylist_ids else "")
        for s in services
    )
    team = "\n".join(f"- id {s.id}: {s.name} — {s.specialties}" for s in stylists)

    return f"""You are the front desk for {salon.name}, a beauty salon. You answer calls, texts and Instagram DMs on the salon's behalf and your job is to get clients booked.

Voice and tone: {salon.voice_tone}
Never say you are an AI unless asked directly; if asked, say you're the salon's virtual assistant.

Salon details
- Address: {salon.address or 'ask the team'}
- Phone: {salon.phone or 'n/a'}
- Hours: {_hours_text(salon.hours)}

Service menu
{menu}

Team
{team}

Policies
{salon.policies or 'None listed.'}

How to work
- To book: identify the service (ask if unclear), call check_availability, offer two or three specific times, and call create_booking only after the client picks one. Only say "you're booked" after create_booking succeeds.
- If a service needs a deposit, call send_deposit_link right after create_booking and share the link; explain the slot is held briefly until it's paid.
- If nothing works, offer the waitlist (add_to_waitlist) and ask if they can come in on short notice.
- For reschedules and cancellations use the client's upcoming appointments below. Mention the cancellation policy before cancelling.
- For prices, prep, policies or anything else you're not sure of, call lookup_service_info. Never invent prices, services or policies.
- Hand off to a human (handoff_to_human) when the client is upset, asks for a person, mentions a complaint, allergy or medical issue, needs a color correction, or you're unsure. Then tell them someone from the team will follow up soon.
- Ask for the client's first name before booking if you don't have it.
- If the client texts STOP or asks not to be contacted, confirm they're unsubscribed and stop."""


def dynamic_context(db: Session, salon: Salon, client: Client, conversation: Conversation) -> str:
    now = salon_now(salon)
    upcoming = list(db.scalars(
        select(Appointment).where(
            Appointment.salon_id == salon.id, Appointment.client_id == client.id,
            Appointment.start >= now, Appointment.status.in_(("booked", "pending_deposit")),
        ).order_by(Appointment.start)))
    history = list(db.scalars(
        select(Appointment).where(
            Appointment.salon_id == salon.id, Appointment.client_id == client.id,
            Appointment.start < now, Appointment.status == "completed",
        ).order_by(Appointment.start.desc()).limit(3)))

    lines = [
        f"Right now it is {now.strftime('%A, %B')} {now.day}, {now.year} at {fmt_slot(now).split(', ')[1]} salon time "
        f"(today's date: {now.date().isoformat()}).",
        f"Channel: {conversation.channel}. {CHANNEL_STYLE.get(conversation.channel, '')}",
        "",
        "Client",
        f"- Name: {client.name or 'unknown — ask for it'}",
        f"- Phone: {client.phone or 'unknown'}",
    ]
    if client.preferred_stylist:
        lines.append(f"- Usually sees: {client.preferred_stylist.name} (id {client.preferred_stylist.id})")
    if client.notes:
        lines.append(f"- Notes: {client.notes}")
    if history:
        lines.append("- Recent visits: " + "; ".join(f"{a.service.name} with {a.stylist.name} on {a.start.date()}" for a in history))
    if upcoming:
        lines.append("- Upcoming appointments:")
        lines += [f"  - appointment_id {a.id}: {a.service.name} with {a.stylist.name}, {fmt_slot(a.start)} "
                  f"({a.start.isoformat(timespec='minutes')}), status {a.status}" for a in upcoming]
    else:
        lines.append("- No upcoming appointments.")
    offered = (conversation.state or {}).get("offered_slots")
    if offered:
        lines.append("- Times we already offered in this thread (still need a fresh check before booking): "
                     + "; ".join(f"{o['when']} with {o['stylist']} (service_id {o['service_id']}, stylist_id "
                                 f"{o['stylist_id']}, start {o['start']})" for o in offered))
    return "\n".join(lines)
