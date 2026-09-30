"""The agent's tools. The agent (and the scheduled workers) act on bookings only
through these functions, so a slot is never booked two different ways."""
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..integrations import messaging, payments
from ..integrations.booking import BookingError, get_platform
from ..models import Appointment, Client, Conversation, Salon, Service, Stylist, WaitlistEntry
from ..timeutil import fmt_slot, salon_now


@dataclass
class ToolContext:
    db: Session
    salon: Salon
    client: Client
    conversation: Conversation


class ToolError(Exception):
    pass


def _parse_dt(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "")).replace(tzinfo=None, second=0, microsecond=0)
    except Exception:
        raise ToolError(f"Could not read the time '{value}'. Use ISO format like 2026-10-04T14:30.")


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value.strip()[:10])
    except Exception:
        raise ToolError(f"Could not read the date '{value}'. Use YYYY-MM-DD.")


def _service(ctx: ToolContext, service_id: int) -> Service:
    svc = ctx.db.get(Service, int(service_id))
    if not svc or svc.salon_id != ctx.salon.id or not svc.active:
        raise ToolError(f"No service with id {service_id}.")
    return svc


def _own_appointment(ctx: ToolContext, appointment_id: int) -> Appointment:
    appt = ctx.db.get(Appointment, int(appointment_id))
    if not appt or appt.salon_id != ctx.salon.id or appt.client_id != ctx.client.id:
        raise ToolError(f"No appointment {appointment_id} found for this client.")
    return appt


def _appt_dict(appt: Appointment) -> Dict[str, Any]:
    return {
        "appointment_id": appt.id,
        "service": appt.service.name,
        "stylist": appt.stylist.name,
        "start": appt.start.isoformat(timespec="minutes"),
        "when": fmt_slot(appt.start),
        "status": appt.status,
        "deposit_status": appt.deposit_status,
    }


# ---------------------------------------------------------------- tools

def check_availability(ctx: ToolContext, service_id: int, date_from: str, date_to: str = "",
                       stylist_id: int = 0) -> Dict[str, Any]:
    svc = _service(ctx, service_id)
    d_from = max(_parse_date(date_from), salon_now(ctx.salon).date())
    d_to = _parse_date(date_to) if date_to else d_from + timedelta(days=2)
    d_to = min(max(d_to, d_from), d_from + timedelta(days=21))
    slots = get_platform(ctx.salon).check_availability(
        ctx.db, ctx.salon, svc, d_from, d_to, stylist_id=int(stylist_id) or None, limit=10)
    return {
        "service": svc.name,
        "duration_min": svc.duration_min,
        "slots": [
            {"start": s.start.isoformat(timespec="minutes"), "when": fmt_slot(s.start),
             "stylist_id": s.stylist_id, "stylist": s.stylist_name}
            for s in slots
        ],
        "note": "No openings in that range — try other dates or offer the waitlist." if not slots else "",
    }


def create_booking(ctx: ToolContext, service_id: int, stylist_id: int, start: str,
                   client_name: str = "") -> Dict[str, Any]:
    svc = _service(ctx, service_id)
    if client_name and not ctx.client.name:
        ctx.client.name = client_name.strip()[:120]
    source = (ctx.conversation.state or {}).get("source_hint", "ai")
    try:
        appt = get_platform(ctx.salon).create_booking(
            ctx.db, ctx.salon, svc, int(stylist_id), _parse_dt(start), ctx.client.id,
            source=source, booked_by_ai=True)
    except BookingError as e:
        raise ToolError(f"Booking not confirmed: {e} Check availability again and offer other times.")
    result = _appt_dict(appt)
    if svc.deposit_required:
        appt.status = "pending_deposit"
        appt.deposit_status = "pending"
        appt.hold_expires_at = salon_now(ctx.salon) + timedelta(minutes=config.DEPOSIT_HOLD_MINUTES)
        result.update(status="pending_deposit", deposit_required=True, deposit_amount=svc.deposit_amount,
                      next_step="Call send_deposit_link; the slot is held for "
                                f"{config.DEPOSIT_HOLD_MINUTES} minutes until the deposit is paid.")
    ctx.conversation.outcome = "booked"
    ctx.db.flush()
    return result


def reschedule_booking(ctx: ToolContext, appointment_id: int, new_start: str, stylist_id: int = 0) -> Dict[str, Any]:
    appt = _own_appointment(ctx, appointment_id)
    if appt.status in ("cancelled", "completed", "no_show"):
        raise ToolError("That appointment can no longer be changed.")
    old_start, old_stylist = appt.start, appt.stylist_id
    try:
        get_platform(ctx.salon).reschedule_booking(ctx.db, ctx.salon, appt, _parse_dt(new_start),
                                                   stylist_id=int(stylist_id) or None)
    except BookingError as e:
        raise ToolError(f"Reschedule not confirmed: {e}")
    from ..workers.refill import start_refill  # the old slot is now open
    start_refill(ctx.db, ctx.salon, appt, slot_start=old_start, slot_stylist_id=old_stylist)
    return _appt_dict(appt)


def cancel_booking(ctx: ToolContext, appointment_id: int) -> Dict[str, Any]:
    appt = _own_appointment(ctx, appointment_id)
    if appt.status == "cancelled":
        return {"appointment_id": appt.id, "status": "cancelled", "note": "Already cancelled."}
    get_platform(ctx.salon).cancel_booking(ctx.db, ctx.salon, appt)
    from ..workers.refill import start_refill
    start_refill(ctx.db, ctx.salon, appt)
    return {"appointment_id": appt.id, "status": "cancelled"}


def send_deposit_link(ctx: ToolContext, appointment_id: int) -> Dict[str, Any]:
    appt = _own_appointment(ctx, appointment_id)
    amount = appt.service.deposit_amount or round(appt.price * 0.25, 2)
    try:
        url = payments.create_deposit_link(ctx.salon, appt, amount)
    except Exception:
        raise ToolError("The payment system is unavailable. Tell the client the salon will follow up.")
    appt.deposit_url = url
    appt.deposit_status = "pending"
    if ctx.conversation.channel == "voice" and ctx.client.phone:
        messaging.send_text(ctx.db, ctx.salon, ctx.client, "sms", ctx.client.phone,
                            f"{ctx.salon.name}: here's your ${amount:.0f} deposit link to lock in "
                            f"{appt.service.name} on {fmt_slot(appt.start)}: {url}")
        return {"amount": amount, "sent_by_text": True}
    return {"amount": amount, "url": url, "note": "Include this link in your reply."}


def add_to_waitlist(ctx: ToolContext, service_id: int, preferred_times: str = "", flexible: bool = False,
                    stylist_id: int = 0) -> Dict[str, Any]:
    svc = _service(ctx, service_id)
    entry = WaitlistEntry(salon_id=ctx.salon.id, client_id=ctx.client.id, service_id=svc.id,
                          stylist_id=int(stylist_id) or None, preferred_times=preferred_times[:200],
                          flexible=bool(flexible))
    ctx.db.add(entry)
    ctx.conversation.outcome = ctx.conversation.outcome or "waitlisted"
    ctx.db.flush()
    return {"waitlist_id": entry.id, "service": svc.name, "status": "added"}


def lookup_service_info(ctx: ToolContext, query: str) -> Dict[str, Any]:
    """Lightweight retrieval over the salon's menu, policies and FAQ.

    Scores chunks by keyword overlap; swap for pgvector embeddings when the
    knowledge base outgrows keyword search.
    """
    chunks: List[str] = []
    for svc in ctx.db.scalars(select(Service).where(Service.salon_id == ctx.salon.id, Service.active.is_(True))):
        dep = f" Deposit required: ${svc.deposit_amount:.0f}." if svc.deposit_required else ""
        chunks.append(f"[service {svc.id}] {svc.name} ({svc.category}) — ${svc.price:.0f}, "
                      f"{svc.duration_min} min. {svc.description}{dep}")
    for st in ctx.db.scalars(select(Stylist).where(Stylist.salon_id == ctx.salon.id, Stylist.active.is_(True))):
        chunks.append(f"[stylist {st.id}] {st.name}: {st.specialties}")
    for block in (ctx.salon.policies, ctx.salon.faq):
        chunks.extend(p.strip() for p in re.split(r"\n\s*\n|\n(?=[-•*])", block or "") if p.strip())

    words = {w for w in re.findall(r"[a-z]+", query.lower()) if len(w) > 2}
    scored = []
    for c in chunks:
        lc = c.lower()
        score = sum(1 for w in words if w in lc)
        if score:
            scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    return {"results": [c for _, c in scored[:6]] or ["No matching info. Don't guess — offer a handoff."]}


def handoff_to_human(ctx: ToolContext, summary: str, reason: str = "") -> Dict[str, Any]:
    conv = ctx.conversation
    conv.handoff_flag = True
    conv.status = "handoff"
    conv.handoff_summary = summary[:1000]
    conv.outcome = "handoff"
    who = ctx.client.name or ctx.client.phone or ctx.client.ig_handle or "A client"
    messaging.notify_staff(ctx.db, ctx.salon, f"FullChair handoff — {who} ({conv.channel}): {summary}"[:600])
    ctx.db.flush()
    return {"status": "handed_off", "note": "Tell the client a team member will follow up shortly."}


TOOL_FUNCS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "check_availability": check_availability,
    "create_booking": create_booking,
    "reschedule_booking": reschedule_booking,
    "cancel_booking": cancel_booking,
    "send_deposit_link": send_deposit_link,
    "add_to_waitlist": add_to_waitlist,
    "lookup_service_info": lookup_service_info,
    "handoff_to_human": handoff_to_human,
}


def execute_tool(ctx: ToolContext, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    fn = TOOL_FUNCS.get(name)
    if not fn:
        raise ToolError(f"Unknown tool {name}")
    try:
        return fn(ctx, **(args or {}))
    except TypeError as e:
        raise ToolError(f"Bad arguments for {name}: {e}")


def _obj(props: Dict[str, Any], required: List[str]) -> Dict[str, Any]:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


TOOL_SCHEMAS = [
    {
        "name": "check_availability",
        "description": "Find open appointment times for a service from the salon's live booking system. "
                       "Always call this before offering times; never invent availability.",
        "input_schema": _obj({
            "service_id": {"type": "integer", "description": "Service id from the menu."},
            "date_from": {"type": "string", "description": "First day to search, YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Last day to search, YYYY-MM-DD. Defaults to date_from + 2 days."},
            "stylist_id": {"type": "integer", "description": "Only this stylist. 0 for anyone."},
        }, ["service_id", "date_from"]),
    },
    {
        "name": "create_booking",
        "description": "Book a slot returned by check_availability, after the client has clearly confirmed "
                       "the exact time. The booking only counts once this tool returns successfully.",
        "input_schema": _obj({
            "service_id": {"type": "integer"},
            "stylist_id": {"type": "integer"},
            "start": {"type": "string", "description": "Slot start from check_availability, e.g. 2026-10-04T14:30."},
            "client_name": {"type": "string", "description": "Client's name if newly learned, else empty."},
        }, ["service_id", "stylist_id", "start"]),
    },
    {
        "name": "reschedule_booking",
        "description": "Move one of this client's upcoming appointments to a new open time.",
        "input_schema": _obj({
            "appointment_id": {"type": "integer"},
            "new_start": {"type": "string", "description": "New start, ISO format."},
            "stylist_id": {"type": "integer", "description": "New stylist, or 0 to keep the same one."},
        }, ["appointment_id", "new_start"]),
    },
    {
        "name": "cancel_booking",
        "description": "Cancel one of this client's appointments after they confirm. Mention the cancellation policy first.",
        "input_schema": _obj({"appointment_id": {"type": "integer"}}, ["appointment_id"]),
    },
    {
        "name": "send_deposit_link",
        "description": "Create a secure deposit payment link for an appointment that requires a deposit.",
        "input_schema": _obj({"appointment_id": {"type": "integer"}}, ["appointment_id"]),
    },
    {
        "name": "add_to_waitlist",
        "description": "Add the client to the waitlist for a service when nothing suitable is open.",
        "input_schema": _obj({
            "service_id": {"type": "integer"},
            "preferred_times": {"type": "string", "description": "e.g. 'weekday evenings', 'Saturday mornings'."},
            "flexible": {"type": "boolean", "description": "True if they can come in on short notice."},
            "stylist_id": {"type": "integer", "description": "Preferred stylist, or 0 for anyone."},
        }, ["service_id"]),
    },
    {
        "name": "lookup_service_info",
        "description": "Search the salon's service menu, policies and FAQ. Use for prices, prep, parking, "
                       "cancellation rules, or anything you are not sure about.",
        "input_schema": _obj({"query": {"type": "string"}}, ["query"]),
    },
    {
        "name": "handoff_to_human",
        "description": "Hand the conversation to salon staff. Use when the client is upset, asks for a person, "
                       "has a complaint, a medical/allergy question, a color correction, or anything you can't "
                       "answer confidently.",
        "input_schema": _obj({
            "summary": {"type": "string", "description": "One or two sentences staff can act on."},
            "reason": {"type": "string"},
        }, ["summary"]),
    },
]


def as_tool_result_text(result: Dict[str, Any]) -> str:
    return json.dumps(result, default=str)
