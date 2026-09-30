"""JSON API for the owner dashboard."""
import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import config
from ..agent import add_message, find_or_create_client, get_conversation, handle_inbound, normalize_phone
from ..db import get_db
from ..integrations import messaging
from ..integrations.booking import get_platform, platform_connected
from ..metrics import conversation_row, message_row, overview
from ..models import (AITrace, Appointment, Client, Conversation, OutboundMessage, RefillOffer, Salon, Service,
                      Stylist, WaitlistEntry)
from ..plans import PLANS, has_feature
from ..timeutil import fmt_slot, salon_now
from ..workers.nudges import due_clients, run_nudges
from ..workers.refill import start_refill
from ..workers.scheduler import run_all_jobs

router = APIRouter(prefix="/api")


def current_salon(x_salon_id: Optional[int] = Header(default=None), db: Session = Depends(get_db)) -> Salon:
    salon = db.get(Salon, x_salon_id) if x_salon_id else db.scalar(select(Salon).order_by(Salon.id))
    if not salon:
        raise HTTPException(404, "No salon found. Run `python -m app.seed`.")
    return salon


def _own(db: Session, model, obj_id: int, salon: Salon):
    obj = db.get(model, obj_id)
    if not obj or obj.salon_id != salon.id:
        raise HTTPException(404, "Not found")
    return obj


# ------------------------------------------------------------------ status & salon

@router.get("/status")
def status(salon: Salon = Depends(current_salon)):
    return {
        "salon": {"id": salon.id, "name": salon.name, "plan": salon.plan},
        "ai": {"enabled": config.ai_enabled(), "model": config.MODEL if config.ai_enabled() else "demo",
               "paused": salon.ai_paused},
        "integrations": {
            "booking": {"platform": salon.booking_platform, "connected": platform_connected(salon)},
            "sms": messaging.twilio_enabled(),
            "voice": messaging.twilio_enabled(),
            "instagram": bool(config.META_PAGE_ACCESS_TOKEN),
            "payments": bool(config.STRIPE_SECRET_KEY),
        },
        "features": sorted(PLANS.get(salon.plan, PLANS["pro"])["features"]),
        "now": salon_now(salon).isoformat(timespec="minutes"),
    }


class SalonPatch(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    timezone: Optional[str] = None
    voice_tone: Optional[str] = None
    policies: Optional[str] = None
    faq: Optional[str] = None
    hours: Optional[dict] = None
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None
    handoff_phone: Optional[str] = None
    avg_ticket: Optional[float] = None
    plan: Optional[str] = None
    ai_paused: Optional[bool] = None
    booking_platform: Optional[str] = None
    sms_number: Optional[str] = None
    ig_account_id: Optional[str] = None


def _salon_dict(s: Salon) -> dict:
    return {k: getattr(s, k) for k in SalonPatch.model_fields} | {"id": s.id}


@router.get("/salon")
def get_salon(salon: Salon = Depends(current_salon)):
    return _salon_dict(salon)


@router.patch("/salon")
def patch_salon(body: SalonPatch, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    salon = db.merge(salon)
    data = body.model_dump(exclude_unset=True)
    if "plan" in data and data["plan"] not in PLANS:
        raise HTTPException(400, "Unknown plan")
    for k, v in data.items():
        setattr(salon, k, v)
    db.commit()
    return _salon_dict(salon)


@router.get("/overview")
def get_overview(days: int = 30, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    return overview(db, salon, max(1, min(days, 365)))


# ------------------------------------------------------------------ conversations

@router.get("/conversations")
def list_conversations(status: str = "", channel: str = "", q: str = "", limit: int = 100,
                       salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    stmt = select(Conversation).where(Conversation.salon_id == salon.id)
    if status:
        stmt = stmt.where(Conversation.status == status)
    if channel:
        stmt = stmt.where(Conversation.channel == channel)
    if q:
        stmt = stmt.join(Client).where(or_(Client.name.ilike(f"%{q}%"), Client.phone.ilike(f"%{q}%")))
    stmt = stmt.order_by(Conversation.last_message_at.desc()).limit(min(limit, 500))
    return [conversation_row(c) for c in db.scalars(stmt).unique()]


@router.get("/conversations/{conv_id}")
def get_conversation_detail(conv_id: int, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    c = _own(db, Conversation, conv_id, salon)
    traces = list(db.scalars(select(AITrace).where(AITrace.conversation_id == c.id).order_by(AITrace.id)))
    upcoming = list(db.scalars(select(Appointment).where(
        Appointment.client_id == c.client_id, Appointment.start >= salon_now(salon),
        Appointment.status.in_(("booked", "pending_deposit"))).order_by(Appointment.start)))
    return conversation_row(c) | {
        "messages": [message_row(m) for m in c.messages],
        "upcoming": [_appt(a) for a in upcoming],
        "traces": [{"id": t.id, "model": t.model, "tool_calls": t.tool_calls, "input_tokens": t.input_tokens,
                    "output_tokens": t.output_tokens, "latency_ms": t.latency_ms, "error": t.error,
                    "at": t.created_at.isoformat() + "Z"} for t in traces],
    }


class ReplyBody(BaseModel):
    text: str


@router.post("/conversations/{conv_id}/reply")
def staff_reply(conv_id: int, body: ReplyBody, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    c = _own(db, Conversation, conv_id, salon)
    add_message(db, c, "out", "staff", body.text)
    to = c.client.ig_handle if c.channel == "instagram" else c.client.phone
    channel = "sms" if c.channel == "voice" else c.channel
    messaging.send_text(db, salon, c.client, channel, to, body.text, purpose="reply")
    db.commit()
    return get_conversation_detail(conv_id, salon, db)


@router.post("/conversations/{conv_id}/resolve")
def resolve(conv_id: int, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    c = _own(db, Conversation, conv_id, salon)
    c.status, c.handoff_flag = "closed", False
    db.commit()
    return conversation_row(c)


@router.post("/conversations/{conv_id}/resume-ai")
def resume_ai(conv_id: int, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    c = _own(db, Conversation, conv_id, salon)
    c.status, c.handoff_flag = "open", False
    db.commit()
    return conversation_row(c)


@router.post("/conversations/{conv_id}/take-over")
def take_over(conv_id: int, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    c = _own(db, Conversation, conv_id, salon)
    c.status, c.handoff_flag = "handoff", True
    c.handoff_summary = c.handoff_summary or "Staff took over this conversation."
    db.commit()
    return conversation_row(c)


# ------------------------------------------------------------------ live chat simulator

class ChatBody(BaseModel):
    text: str
    phone: str = ""
    name: str = ""
    channel: str = "sms"


@router.post("/chat")
def chat(body: ChatBody, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    """Talk to the receptionist exactly as a client would, from the dashboard."""
    channel = body.channel if body.channel in ("sms", "instagram", "web", "voice") else "sms"
    identity = body.phone or f"+1555{uuid.uuid4().int % 10_000_000:07d}"
    if channel == "instagram" and not identity.startswith("@"):
        identity = "@" + identity.lstrip("+")
    salon = db.merge(salon)
    reply, conv = handle_inbound(db, salon, channel, identity, body.text, name=body.name)
    db.commit()
    return {"reply": reply, "identity": identity, "conversation": get_conversation_detail(conv.id, salon, db)}


class ChatReset(BaseModel):
    phone: str
    channel: str = "sms"


@router.post("/chat/reset")
def chat_reset(body: ChatReset, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    ident = body.phone if body.channel == "instagram" else normalize_phone(body.phone)
    col = Client.ig_handle if body.channel == "instagram" else Client.phone
    client = db.scalar(select(Client).where(Client.salon_id == salon.id, col == ident))
    if client:
        for c in db.scalars(select(Conversation).where(Conversation.client_id == client.id,
                                                       Conversation.status != "closed")):
            c.status = "closed"
        db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ appointments

def _appt(a: Appointment) -> dict:
    return {
        "id": a.id, "start": a.start.isoformat(timespec="minutes"), "end": a.end.isoformat(timespec="minutes"),
        "when": fmt_slot(a.start), "status": a.status, "price": a.price, "booked_by_ai": a.booked_by_ai,
        "source": a.source, "deposit_status": a.deposit_status, "deposit_url": a.deposit_url,
        "client": {"id": a.client.id, "name": a.client.name, "phone": a.client.phone},
        "service": {"id": a.service.id, "name": a.service.name, "duration_min": a.service.duration_min},
        "stylist": {"id": a.stylist.id, "name": a.stylist.name, "color": a.stylist.color},
        "created_at": a.created_at.isoformat() + "Z",
    }


@router.get("/appointments")
def list_appointments(start: Optional[date] = None, end: Optional[date] = None, ai_only: bool = False,
                      salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    today = salon_now(salon).date()
    start = start or today
    end = end or start + timedelta(days=7)
    stmt = select(Appointment).where(
        Appointment.salon_id == salon.id,
        Appointment.start >= datetime.combine(start, datetime.min.time()),
        Appointment.start < datetime.combine(end, datetime.min.time()) + timedelta(days=1),
    ).order_by(Appointment.start)
    if ai_only:
        stmt = stmt.where(Appointment.booked_by_ai.is_(True))
    return [_appt(a) for a in db.scalars(stmt).unique()]


@router.post("/appointments/{appt_id}/cancel")
def cancel_appointment(appt_id: int, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    salon = db.merge(salon)
    a = _own(db, Appointment, appt_id, salon)
    if a.status in ("cancelled", "completed"):
        raise HTTPException(400, f"Appointment is already {a.status}.")
    get_platform(salon).cancel_booking(db, salon, a)
    offer = start_refill(db, salon, a)
    db.commit()
    return {"appointment": _appt(a),
            "refill": {"offer_id": offer.id, "contacted": len(offer.contacted_client_ids or [])} if offer else None}


@router.post("/appointments/{appt_id}/mark-paid")
def mark_paid(appt_id: int, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    a = _own(db, Appointment, appt_id, salon)
    confirm_deposit(db, salon, a)
    db.commit()
    return _appt(a)


def confirm_deposit(db: Session, salon: Salon, a: Appointment) -> None:
    if a.deposit_status == "paid":
        return
    a.deposit_status = "paid"
    if a.status == "pending_deposit":
        a.status = "booked"
    a.hold_expires_at = None
    conv = get_conversation(db, salon, a.client, "sms")
    text = f"Deposit received — you're confirmed for {a.service.name} with {a.stylist.name.split()[0]} on {fmt_slot(a.start)} ✨"
    add_message(db, conv, "out", "ai", text)
    messaging.send_text(db, salon, a.client, "sms", a.client.phone, text, purpose="reply")


# ------------------------------------------------------------------ clients

def _client_row(db: Session, salon: Salon, c: Client) -> dict:
    now = salon_now(salon)
    appts = list(db.scalars(select(Appointment).where(Appointment.client_id == c.id).order_by(Appointment.start)))
    done = [a for a in appts if a.status == "completed"]
    nxt = next((a for a in appts if a.start >= now and a.status in ("booked", "pending_deposit")), None)
    last = done[-1] if done else None
    interval = c.visit_interval_days or (last.service.rebook_interval_days if last else None)
    due = bool(last and not nxt and interval and (now - last.start).days >= interval)
    return {
        "id": c.id, "name": c.name, "phone": c.phone, "ig": c.ig_handle, "email": c.email, "opt_in": c.opt_in,
        "notes": c.notes, "preferred_stylist": c.preferred_stylist.name if c.preferred_stylist else None,
        "preferred_stylist_id": c.preferred_stylist_id,
        "visits": len(done), "lifetime_value": round(sum(a.price for a in done), 2),
        "last_visit": last.start.date().isoformat() if last else None,
        "last_service": last.service.name if last else None,
        "next_visit": nxt.start.isoformat(timespec="minutes") if nxt else None,
        "visit_interval_days": c.visit_interval_days, "due_for_rebook": due,
        "last_nudged_at": c.last_nudged_at.isoformat() + "Z" if c.last_nudged_at else None,
    }


@router.get("/clients")
def list_clients(q: str = "", salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    stmt = select(Client).where(Client.salon_id == salon.id)
    if q:
        stmt = stmt.where(or_(Client.name.ilike(f"%{q}%"), Client.phone.ilike(f"%{q}%"), Client.ig_handle.ilike(f"%{q}%")))
    return [_client_row(db, salon, c) for c in db.scalars(stmt.order_by(Client.name)).unique()]


class ClientPatch(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    opt_in: Optional[bool] = None
    preferred_stylist_id: Optional[int] = None
    visit_interval_days: Optional[int] = None


@router.patch("/clients/{client_id}")
def patch_client(client_id: int, body: ClientPatch, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    c = _own(db, Client, client_id, salon)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(c, k, normalize_phone(v) if k == "phone" else v)
    db.commit()
    return _client_row(db, salon, c)


# ------------------------------------------------------------------ waitlist & refill

@router.get("/waitlist")
def list_waitlist(salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    rows = db.scalars(select(WaitlistEntry).where(WaitlistEntry.salon_id == salon.id, WaitlistEntry.active.is_(True))
                      .order_by(WaitlistEntry.created_at)).unique()
    return [{"id": w.id, "client": {"id": w.client.id, "name": w.client.name, "phone": w.client.phone},
             "service": w.service.name, "service_id": w.service_id,
             "stylist": w.stylist.name if w.stylist else None, "preferred_times": w.preferred_times,
             "flexible": w.flexible, "created_at": w.created_at.isoformat() + "Z"} for w in rows]


class WaitlistBody(BaseModel):
    client_id: int
    service_id: int
    stylist_id: Optional[int] = None
    preferred_times: str = ""
    flexible: bool = False


@router.post("/waitlist")
def add_waitlist(body: WaitlistBody, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    _own(db, Client, body.client_id, salon)
    _own(db, Service, body.service_id, salon)
    w = WaitlistEntry(salon_id=salon.id, **body.model_dump())
    db.add(w)
    db.commit()
    return {"id": w.id}


@router.delete("/waitlist/{entry_id}")
def remove_waitlist(entry_id: int, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    w = _own(db, WaitlistEntry, entry_id, salon)
    w.active = False
    db.commit()
    return {"ok": True}


@router.get("/refill-offers")
def list_offers(salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    rows = db.scalars(select(RefillOffer).where(RefillOffer.salon_id == salon.id).order_by(RefillOffer.id.desc()).limit(30))
    out = []
    for o in rows.unique():
        filled_by = db.get(Client, o.filled_by_client_id) if o.filled_by_client_id else None
        out.append({"id": o.id, "start": o.start.isoformat(timespec="minutes"), "when": fmt_slot(o.start),
                    "stylist": o.stylist.name, "status": o.status, "contacted": len(o.contacted_client_ids or []),
                    "filled_by": filled_by.name if filled_by else None,
                    "created_at": o.created_at.isoformat() + "Z"})
    return out


# ------------------------------------------------------------------ nudges & jobs

@router.get("/nudges/due")
def nudges_due(salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    return [{"client": _client_row(db, salon, d["client"]), "last_service": d["last"].service.name,
             "days_since": d["days_since"], "interval": d["interval"]} for d in due_clients(db, salon)]


@router.post("/nudges/run")
def nudges_run(force: bool = False, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    salon = db.merge(salon)
    if not has_feature(salon, "nudges"):
        raise HTTPException(400, "Rebooking nudges are part of the Growth plan.")
    stats = run_nudges(db, salon, force=force)
    db.commit()
    return stats


@router.post("/jobs/run")
def jobs_run(salon: Salon = Depends(current_salon)):
    return run_all_jobs(salon.id).get(salon.id, {})


@router.get("/outbox")
def outbox(limit: int = 50, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    rows = db.scalars(select(OutboundMessage).where(OutboundMessage.salon_id == salon.id)
                      .order_by(OutboundMessage.id.desc()).limit(min(limit, 200)))
    return [{"id": m.id, "channel": m.channel, "to": m.to, "text": m.text, "purpose": m.purpose,
             "status": m.status, "at": m.created_at.isoformat() + "Z"} for m in rows]


@router.get("/traces/summary")
def traces_summary(salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    since = datetime.utcnow() - timedelta(days=30)
    row = db.execute(select(func.count(AITrace.id), func.avg(AITrace.latency_ms), func.sum(AITrace.input_tokens),
                            func.sum(AITrace.output_tokens)).where(AITrace.salon_id == salon.id,
                                                                   AITrace.created_at >= since)).one()
    return {"turns": row[0] or 0, "avg_latency_ms": int(row[1] or 0), "input_tokens": int(row[2] or 0),
            "output_tokens": int(row[3] or 0)}


# ------------------------------------------------------------------ menu & team

class ServiceBody(BaseModel):
    name: str
    category: str = "Hair"
    description: str = ""
    duration_min: int = 60
    price: float = 0
    deposit_required: bool = False
    deposit_amount: float = 0
    stylist_ids: List[int] = []
    rebook_interval_days: Optional[int] = None
    active: bool = True


def _svc(s: Service) -> dict:
    return {k: getattr(s, k) for k in ServiceBody.model_fields} | {"id": s.id}


@router.get("/services")
def list_services(salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    return [_svc(s) for s in db.scalars(select(Service).where(Service.salon_id == salon.id, Service.active.is_(True))
                                        .order_by(Service.category, Service.name))]


@router.post("/services")
def create_service(body: ServiceBody, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    s = Service(salon_id=salon.id, **body.model_dump())
    db.add(s)
    db.commit()
    return _svc(s)


@router.put("/services/{svc_id}")
def update_service(svc_id: int, body: ServiceBody, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    s = _own(db, Service, svc_id, salon)
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    db.commit()
    return _svc(s)


@router.delete("/services/{svc_id}")
def delete_service(svc_id: int, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    s = _own(db, Service, svc_id, salon)
    s.active = False
    db.commit()
    return {"ok": True}


class StylistBody(BaseModel):
    name: str
    specialties: str = ""
    color: str = "#b86b77"
    active: bool = True


def _sty(s: Stylist) -> dict:
    return {"id": s.id, "name": s.name, "specialties": s.specialties, "color": s.color, "active": s.active}


@router.get("/stylists")
def list_stylists(salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    return [_sty(s) for s in db.scalars(select(Stylist).where(Stylist.salon_id == salon.id, Stylist.active.is_(True)))]


@router.post("/stylists")
def create_stylist(body: StylistBody, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    s = Stylist(salon_id=salon.id, **body.model_dump())
    db.add(s)
    db.commit()
    return _sty(s)


@router.put("/stylists/{sty_id}")
def update_stylist(sty_id: int, body: StylistBody, salon: Salon = Depends(current_salon), db: Session = Depends(get_db)):
    s = _own(db, Stylist, sty_id, salon)
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    db.commit()
    return _sty(s)
