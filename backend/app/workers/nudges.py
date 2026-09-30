"""Rebooking nudges: a personal text with two open times once a client is due."""
from datetime import datetime, timedelta
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..integrations import messaging
from ..integrations.booking import get_platform
from ..models import Appointment, Client, Salon
from ..plans import has_feature
from ..timeutil import fmt_slot, salon_now

DEFAULT_INTERVAL = 42
RENUDGE_AFTER = timedelta(days=14)
MAX_PER_RUN = 25


def due_clients(db: Session, salon: Salon) -> List[dict]:
    """Clients past their usual interval with no future appointment."""
    now = salon_now(salon)
    out = []
    for client in db.scalars(select(Client).where(Client.salon_id == salon.id)):
        appts = list(db.scalars(select(Appointment).where(
            Appointment.client_id == client.id, Appointment.salon_id == salon.id,
            Appointment.status.in_(("booked", "pending_deposit", "completed"))).order_by(Appointment.start.desc())))
        if not appts or any(a.start >= now and a.status != "completed" for a in appts):
            continue
        last = next((a for a in appts if a.status == "completed"), None)
        if not last:
            continue
        interval = client.visit_interval_days or last.service.rebook_interval_days or DEFAULT_INTERVAL
        days_since = (now - last.start).days
        if days_since < interval:
            continue
        out.append({"client": client, "last": last, "interval": interval, "days_since": days_since})
    return out


def run_nudges(db: Session, salon: Salon, force: bool = False) -> dict:
    stats = {"due": 0, "sent": 0, "skipped": 0}
    if not has_feature(salon, "nudges"):
        return stats
    now = salon_now(salon)
    for item in due_clients(db, salon)[:MAX_PER_RUN]:
        client, last = item["client"], item["last"]
        stats["due"] += 1
        if client.last_nudged_at and datetime.utcnow() - client.last_nudged_at < RENUDGE_AFTER and not force:
            stats["skipped"] += 1
            continue
        if messaging.can_send_proactive(db, salon, client):
            stats["skipped"] += 1
            continue
        stylist_id = client.preferred_stylist_id or last.stylist_id
        platform = get_platform(salon)
        slots = platform.check_availability(db, salon, last.service, now.date() + timedelta(days=1),
                                            now.date() + timedelta(days=10), stylist_id=stylist_id, limit=10)
        if len(slots) < 2:
            slots = platform.check_availability(db, salon, last.service, now.date() + timedelta(days=1),
                                                now.date() + timedelta(days=10), limit=10)
        # Two options on different days
        picks = []
        for s in slots:
            if not picks or s.start.date() != picks[0].start.date():
                picks.append(s)
            if len(picks) == 2:
                break
        if len(picks) < 2:
            stats["skipped"] += 1
            continue
        first = client.name.split()[0] if client.name else "there"
        weeks = round(item["days_since"] / 7)
        text = (f"Hi {first}! It's been about {weeks} weeks since your {last.service.name.lower()} with "
                f"{last.stylist.name.split()[0]} — want me to save you a spot? I have "
                f"1) {fmt_slot(picks[0].start)} or 2) {fmt_slot(picks[1].start)} with {picks[0].stylist_name.split()[0]}. "
                f"Reply 1 or 2, or tell me a better time. (Reply STOP to opt out)")
        msg = messaging.send_text(db, salon, client, "sms", client.phone, text, purpose="nudge")
        if msg.status == "blocked":
            stats["skipped"] += 1
            continue
        from ..agent import add_message, get_conversation
        conv = get_conversation(db, salon, client, "sms")
        add_message(db, conv, "out", "ai", text)
        conv.state = dict(conv.state or {}, source_hint="nudge", service_id=last.service_id, offered_slots=[
            {"start": p.start.isoformat(timespec="minutes"), "when": fmt_slot(p.start), "stylist_id": p.stylist_id,
             "stylist": p.stylist_name, "service_id": last.service_id} for p in picks])
        client.last_nudged_at = datetime.utcnow()
        stats["sent"] += 1
    db.flush()
    return stats
