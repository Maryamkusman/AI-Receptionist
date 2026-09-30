"""Scripted receptionist used when no ANTHROPIC_API_KEY is set.

It is deliberately simple — keyword intents over the same tools the Claude agent
uses — so the whole product (booking, deposits, waitlist, handoff, dashboard)
can be tried end to end before connecting a model.
"""
import re
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Appointment, Client, Conversation, Salon, Service, Stylist
from ..timeutil import fmt_slot, salon_now
from .tools import ToolContext, ToolError, execute_tool

WEEKDAYS = {name: i for i, name in enumerate(
    ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])}
ORDINALS = {"1": 0, "first": 0, "one": 0, "2": 1, "second": 1, "two": 1, "3": 2, "third": 2, "three": 2}
HANDOFF_WORDS = ("human", "person", "manager", "owner", "complaint", "refund", "upset", "angry", "allerg",
                 "reaction", "burn", "correction", "speak to", "talk to someone", "real person")
YES = re.compile(r"^\s*(yes|yep|yeah|yup|sure|ok|okay|confirm|please do|do it|sounds good)\b", re.I)


def _has(text: str, *words: str) -> bool:
    return any(w in text for w in words)


def _match_service(db: Session, salon: Salon, text: str) -> Optional[Service]:
    services = list(db.scalars(select(Service).where(Service.salon_id == salon.id, Service.active.is_(True))))
    best, best_score = None, 0
    for s in services:
        tokens = [t for t in re.findall(r"[a-z]+", s.name.lower()) if len(t) > 2 and t not in ("and", "with")]
        score = sum(2 if t in text else 0 for t in tokens)
        if s.name.lower() in text:
            score += 5
        if score > best_score:
            best, best_score = s, score
    return best


def _match_stylist(db: Session, salon: Salon, text: str) -> Optional[Stylist]:
    for st in db.scalars(select(Stylist).where(Stylist.salon_id == salon.id, Stylist.active.is_(True))):
        if st.name.split()[0].lower() in text:
            return st
    return None


def _match_day(text: str, today: date) -> Optional[date]:
    if "today" in text or "tonight" in text:
        return today
    if "tomorrow" in text:
        return today + timedelta(days=1)
    if "weekend" in text:
        return today + timedelta(days=(5 - today.weekday()) % 7)
    for name, idx in WEEKDAYS.items():
        if name in text or re.search(rf"\b{name[:3]}\b", text):
            return today + timedelta(days=(idx - today.weekday()) % 7)
    return None


def _offer_text(offered) -> str:
    opts = [f"{i + 1}) {o['when']} with {o['stylist'].split()[0]}" for i, o in enumerate(offered)]
    return "I have " + ", ".join(opts) + ". Which works? Just reply with the number."


def run_demo_agent(db: Session, salon: Salon, client: Client, conversation: Conversation) -> str:
    ctx = ToolContext(db, salon, client, conversation)
    state = dict(conversation.state or {})
    raw = conversation.messages[-1].text if conversation.messages else ""
    text = raw.lower().strip()
    now = salon_now(salon)
    first = client.name.split()[0] if client.name else ""

    def save(**kw):
        state.update(kw)
        conversation.state = dict(state)

    # Awaiting a name before booking
    if state.get("awaiting_name") and state.get("chosen"):
        name = re.sub(r"^(it'?s|i'?m|my name is|this is)\s+", "", raw.strip(), flags=re.I).strip(" .!")
        client.name = name.title()[:120]
        chosen = state["chosen"]
        save(awaiting_name=False)
        return _book(ctx, chosen, save)

    if _has(text, *HANDOFF_WORDS):
        execute_tool(ctx, "handoff_to_human", {"summary": f"Client asked: \"{raw[:200]}\"", "reason": "requested"})
        return "I completely understand — I've let the team know and someone will reach out to you personally very soon."

    # Picking one of the offered times
    offered = state.get("offered_slots") or []
    words = re.findall(r"[a-z0-9]+", text)
    if offered and len(words) <= 5:
        pick = next((ORDINALS[w] for w in words if w in ORDINALS), None)
        if pick is not None and pick < len(offered):
            chosen = offered[pick]
            if not client.name:
                save(awaiting_name=True, chosen=chosen)
                return f"Great choice! Can I get your first name to put the booking under?"
            return _book(ctx, chosen, save)

    # Cancellation
    upcoming = list(db.scalars(select(Appointment).where(
        Appointment.salon_id == salon.id, Appointment.client_id == client.id, Appointment.start >= now,
        Appointment.status.in_(("booked", "pending_deposit"))).order_by(Appointment.start)))
    if state.get("pending_cancel") and YES.match(text):
        execute_tool(ctx, "cancel_booking", {"appointment_id": state["pending_cancel"]})
        save(pending_cancel=None)
        return "All done — your appointment is cancelled. Want me to find you a new time?"
    if _has(text, "cancel"):
        if not upcoming:
            return "I don't see any upcoming appointments under this number. Anything else I can help with?"
        a = upcoming[0]
        save(pending_cancel=a.id)
        return (f"I see {a.service.name} with {a.stylist.name.split()[0]} on {fmt_slot(a.start)}. Just a heads-up: "
                f"cancellations with under 24 hours' notice may forfeit the deposit. Reply YES to cancel.")

    if text in ("stop", "unsubscribe"):
        client.opt_in = False
        return "You're unsubscribed and won't get any more texts from us. Reply START anytime to rejoin."

    service = _match_service(db, salon, text)
    stylist = _match_stylist(db, salon, text)

    if _has(text, "how much", "price", "cost", "pricing", "$"):
        if service:
            save(service_id=service.id)
            dep = f" A ${service.deposit_amount:.0f} deposit holds the spot." if service.deposit_required else ""
            return f"{service.name} is ${service.price:.0f} and takes about {service.duration_min} minutes.{dep} Want me to check openings?"
        info = execute_tool(ctx, "lookup_service_info", {"query": raw})
        return "Here's what I found: " + info["results"][0].split("] ", 1)[-1] + " Want me to check availability?"

    if _has(text, "hour", "open", "close"):
        hours = salon.hours or {}
        open_days = [f"{k.title()} {v[0]}–{v[1] - 12 if v[1] > 12 else v[1]}" for k, v in hours.items() if v]
        return f"We're open {', '.join(open_days)}. Want me to find you a time?"

    if _has(text, "where", "address", "parking", "located", "location"):
        extra = execute_tool(ctx, "lookup_service_info", {"query": "parking location address"})["results"][0]
        return f"We're at {salon.address}. {extra if not extra.startswith('No matching') else ''}".strip()

    wants_booking = _has(text, "book", "appointment", "available", "availability", "opening", "get in",
                         "come in", "slot", "schedule", "any time", "free")
    if wants_booking or service or state.get("service_id"):
        service = service or (db.get(Service, state["service_id"]) if state.get("service_id") else None)
        if not service:
            save(wants_booking=True)
            return "I'd love to get you in! What service are you looking for — cut, color, balayage, blowout, or something else?"
        day = _match_day(text, now.date()) or now.date()
        stylist_id = stylist.id if stylist else (client.preferred_stylist_id if "anyone" not in text else 0) or 0
        result = execute_tool(ctx, "check_availability", {
            "service_id": service.id, "date_from": day.isoformat(),
            "date_to": (day + timedelta(days=3)).isoformat(), "stylist_id": stylist_id})
        slots = result["slots"]
        if not slots and stylist_id:
            result = execute_tool(ctx, "check_availability", {
                "service_id": service.id, "date_from": day.isoformat(), "date_to": (day + timedelta(days=5)).isoformat()})
            slots = result["slots"]
        if not slots:
            execute_tool(ctx, "add_to_waitlist", {"service_id": service.id, "flexible": True, "stylist_id": stylist_id})
            save(service_id=None)
            return (f"We're fully booked for {service.name} around then, so I've added you to the waitlist — "
                    f"I'll text you the moment something opens up.")
        # Pick up to three options on different days/times.
        picks, used_days = [], set()
        for s in slots:
            if s["start"][:10] not in used_days or len(slots) <= 3:
                picks.append(s)
                used_days.add(s["start"][:10])
            if len(picks) == 3:
                break
        offered = [dict(s, service_id=service.id) for s in picks]
        save(offered_slots=offered, service_id=service.id)
        asked_day = _match_day(text, now.date())
        lead = f"{service.name} is ${service.price:.0f}. "
        if asked_day and picks[0]["start"][:10] != asked_day.isoformat():
            lead = f"{asked_day.strftime('%A')} is fully booked for {service.name}, but the next openings are close! "
        return lead + _offer_text(offered)

    if re.match(r"^\s*(hi|hey|hello|good (morning|afternoon|evening))\b", text):
        return f"Hi{' ' + first if first else ''}! Thanks for reaching out to {salon.name}. How can I help — would you like to book something?"

    info = execute_tool(ctx, "lookup_service_info", {"query": raw})["results"][0]
    if not info.startswith("No matching"):
        return info.split("] ", 1)[-1]
    return "I can help you book, reschedule or answer questions about our services. What can I do for you?"


def _book(ctx: ToolContext, chosen: dict, save) -> str:
    try:
        appt = execute_tool(ctx, "create_booking", {
            "service_id": chosen["service_id"], "stylist_id": chosen["stylist_id"], "start": chosen["start"]})
    except ToolError:
        save(offered_slots=[], chosen=None)
        return "Oh no, that time was just taken! Want me to look for another opening?"
    save(offered_slots=[], chosen=None, service_id=None)
    msg = f"You're booked, {ctx.client.name.split()[0]}! {appt['service']} with {appt['stylist'].split()[0]} on {appt['when']}."
    if appt.get("deposit_required"):
        link = execute_tool(ctx, "send_deposit_link", {"appointment_id": appt["appointment_id"]})
        if link.get("url"):
            return (f"Almost done, {ctx.client.name.split()[0]}! I'm holding {appt['service']} with "
                    f"{appt['stylist'].split()[0]} on {appt['when']} for 30 minutes. Pop in the "
                    f"${link['amount']:.0f} deposit to lock it in: {link['url']}")
        return msg + f" I've texted you a ${link['amount']:.0f} deposit link to lock it in."
    return msg + " See you then ✨"
