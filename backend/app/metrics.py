"""Owner dashboard numbers: the screen that renews the subscription."""
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Appointment, Conversation, Message, Salon
from .plans import PLANS
from .timeutil import DAY_KEYS, salon_now, utc_to_salon

AI_SOURCES = ("ai", "refill", "nudge")


def overview(db: Session, salon: Salon, days: int = 30) -> dict:
    now_utc = datetime.utcnow()
    since = now_utc - timedelta(days=days)
    prev_since = since - timedelta(days=days)

    appts = list(db.scalars(select(Appointment).where(
        Appointment.salon_id == salon.id, Appointment.created_at >= prev_since)))
    convs = list(db.scalars(select(Conversation).where(
        Conversation.salon_id == salon.id, Conversation.created_at >= prev_since)))

    def ai_booked(a):
        return a.booked_by_ai and a.status not in ("cancelled",)

    cur = [a for a in appts if a.created_at >= since]
    prev = [a for a in appts if a.created_at < since]
    cur_ai = [a for a in cur if ai_booked(a)]
    prev_ai = [a for a in prev if ai_booked(a)]

    def rev(items):
        return round(sum(a.price for a in items), 2)

    cur_convs = [c for c in convs if c.created_at >= since]
    prev_convs = [c for c in convs if c.created_at < since]

    after_hours = 0
    for c in cur_convs:
        local = utc_to_salon(salon, c.created_at)
        span = (salon.hours or {}).get(DAY_KEYS[local.weekday()])
        if not span or not (span[0] <= local.hour < span[1]):
            after_hours += 1

    # Daily series
    series = defaultdict(lambda: {"bookings": 0, "revenue": 0.0, "conversations": 0})
    for a in cur_ai:
        k = a.created_at.date().isoformat()
        series[k]["bookings"] += 1
        series[k]["revenue"] += a.price
    for c in cur_convs:
        series[c.created_at.date().isoformat()]["conversations"] += 1
    daily = []
    for i in range(days - 1, -1, -1):
        d = (now_utc - timedelta(days=i)).date().isoformat()
        row = series[d]
        daily.append({"date": d, "bookings": row["bookings"], "revenue": round(row["revenue"], 2),
                      "conversations": row["conversations"]})

    by_source = {s: {"count": 0, "revenue": 0.0} for s in AI_SOURCES}
    for a in cur_ai:
        s = a.source if a.source in by_source else "ai"
        by_source[s]["count"] += 1
        by_source[s]["revenue"] += a.price

    channels = defaultdict(int)
    for c in cur_convs:
        channels[c.channel] += 1

    now_local = salon_now(salon)
    upcoming = list(db.scalars(select(Appointment).where(
        Appointment.salon_id == salon.id, Appointment.start >= now_local,
        Appointment.start < now_local.replace(hour=0, minute=0) + timedelta(days=1),
        Appointment.status.in_(("booked", "pending_deposit"))).order_by(Appointment.start)))

    handoffs = list(db.scalars(select(Conversation).where(
        Conversation.salon_id == salon.id, Conversation.status == "handoff").order_by(Conversation.last_message_at.desc())))

    plan = PLANS.get(salon.plan, PLANS["pro"])
    monthly_equiv = plan["monthly"] * days / 30
    recovered = rev(cur_ai)

    return {
        "days": days,
        "kpis": {
            "conversations": {"value": len(cur_convs), "prev": len(prev_convs)},
            "ai_bookings": {"value": len(cur_ai), "prev": len(prev_ai)},
            "slots_refilled": {"value": by_source["refill"]["count"],
                               "prev": len([a for a in prev_ai if a.source == "refill"])},
            "revenue_recovered": {"value": recovered, "prev": rev(prev_ai)},
        },
        "roi": {
            "plan": plan["label"], "plan_cost": round(monthly_equiv, 2),
            "multiple": round(recovered / monthly_equiv, 1) if monthly_equiv else None,
        },
        "after_hours_share": round(after_hours / len(cur_convs), 2) if cur_convs else 0,
        "by_source": {k: {"count": v["count"], "revenue": round(v["revenue"], 2)} for k, v in by_source.items()},
        "channels": dict(channels),
        "daily": daily,
        "today": [{
            "id": a.id, "start": a.start.isoformat(timespec="minutes"), "client": a.client.name,
            "service": a.service.name, "stylist": a.stylist.name, "color": a.stylist.color,
            "booked_by_ai": a.booked_by_ai, "status": a.status,
        } for a in upcoming[:8]],
        "handoffs": [{
            "id": c.id, "client": c.client.name or c.client.phone, "channel": c.channel,
            "summary": c.handoff_summary, "at": c.last_message_at.isoformat() + "Z",
        } for c in handoffs[:5]],
    }


def conversation_row(c: Conversation) -> dict:
    last = c.messages[-1] if c.messages else None
    return {
        "id": c.id, "channel": c.channel, "status": c.status, "outcome": c.outcome,
        "handoff": c.handoff_flag, "handoff_summary": c.handoff_summary,
        "client": {"id": c.client.id, "name": c.client.name, "phone": c.client.phone, "ig": c.client.ig_handle},
        "last_message": last.text if last else "", "last_sender": last.sender if last else "",
        "last_message_at": c.last_message_at.isoformat() + "Z", "message_count": len(c.messages),
    }


def message_row(m: Message) -> dict:
    return {"id": m.id, "direction": m.direction, "sender": m.sender, "text": m.text,
            "at": m.created_at.isoformat() + "Z"}
