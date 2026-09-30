"""Cancellation refill: rank the waitlist, text small batches, first yes wins."""
import re
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..integrations import messaging
from ..integrations.booking import BookingError, get_platform
from ..models import Appointment, Client, RefillOffer, Salon, WaitlistEntry
from ..plans import has_feature
from ..timeutil import fmt_slot, salon_now

BATCH_SIZE = 3
BATCH_INTERVAL = timedelta(minutes=20)
MIN_NOTICE = timedelta(minutes=90)
AFFIRMATIVE = re.compile(r"^\s*(yes|yep|yeah|yup|y|sure|i'?ll take it|me|book (it|me)|please)\b", re.I)


def start_refill(db: Session, salon: Salon, appt: Appointment, slot_start: Optional[datetime] = None,
                 slot_stylist_id: Optional[int] = None) -> Optional[RefillOffer]:
    """Open a refill offer for a freed slot and text the first batch."""
    if not has_feature(salon, "refill"):
        return None
    start = slot_start or appt.start
    duration = appt.end - appt.start
    if start - salon_now(salon) < MIN_NOTICE:
        return None
    offer = RefillOffer(salon_id=salon.id, cancelled_appointment_id=appt.id,
                        stylist_id=slot_stylist_id or appt.stylist_id, start=start, end=start + duration,
                        contacted_client_ids=[], offered_service_ids={})
    db.add(offer)
    db.flush()
    contact_next_batch(db, salon, offer, exclude_client_id=appt.client_id)
    return offer


def rank_candidates(db: Session, salon: Salon, offer: RefillOffer,
                    exclude_client_id: Optional[int] = None) -> List[Tuple[int, WaitlistEntry]]:
    slot_minutes = (offer.end - offer.start).total_seconds() / 60
    entries = db.scalars(select(WaitlistEntry).where(
        WaitlistEntry.salon_id == salon.id, WaitlistEntry.active.is_(True)).order_by(WaitlistEntry.created_at))
    ranked = []
    for e in entries:
        if e.client_id in (offer.contacted_client_ids or []) or e.client_id == exclude_client_id:
            continue
        if not e.client.opt_in or not e.client.phone:
            continue
        svc = e.service
        if svc.duration_min > slot_minutes:
            continue  # service doesn't fit the gap
        if svc.stylist_ids and offer.stylist_id not in svc.stylist_ids:
            continue
        if e.stylist_id and e.stylist_id != offer.stylist_id and not e.flexible:
            continue
        score = 0
        score += 3 if svc.duration_min >= slot_minutes * 0.75 else 1  # fills most of the gap
        score += 3 if e.stylist_id == offer.stylist_id else 0
        score += 2 if e.flexible else 0
        score += _time_pref_score(e.preferred_times, offer.start)
        ranked.append((score, e))
    ranked.sort(key=lambda x: (-x[0], x[1].created_at))
    # One offer per client even if they're waitlisted for several services
    seen, unique = set(), []
    for score, e in ranked:
        if e.client_id not in seen:
            seen.add(e.client_id)
            unique.append((score, e))
    return unique


def _time_pref_score(pref: str, start: datetime) -> int:
    p = (pref or "").lower()
    if not p:
        return 0
    score = 0
    if start.strftime("%A").lower() in p or ("weekend" in p and start.weekday() >= 5) or \
            ("weekday" in p and start.weekday() < 5):
        score += 2
    period = "morning" if start.hour < 12 else "afternoon" if start.hour < 17 else "evening"
    if period in p:
        score += 2
    return score


def contact_next_batch(db: Session, salon: Salon, offer: RefillOffer, exclude_client_id: Optional[int] = None) -> int:
    ranked = rank_candidates(db, salon, offer, exclude_client_id)[:BATCH_SIZE]
    contacted = list(offer.contacted_client_ids or [])
    services = dict(offer.offered_service_ids or {})
    sent = 0
    for _, entry in ranked:
        client = entry.client
        first = client.name.split()[0] if client.name else "there"
        text = (f"Hi {first}! A spot just opened at {salon.name}: {fmt_slot(offer.start)} with "
                f"{offer.stylist.name.split()[0]} for your {entry.service.name}. Reply YES to grab it — "
                f"first reply gets it!")
        msg = messaging.send_text(db, salon, client, "sms", client.phone, text, purpose="refill")
        if msg.status == "blocked":
            continue
        _log_to_thread(db, salon, client, text)
        contacted.append(client.id)
        services[str(client.id)] = entry.service_id
        sent += 1
    offer.contacted_client_ids = contacted
    offer.offered_service_ids = services
    offer.created_at = offer.created_at or datetime.utcnow()
    db.flush()
    return sent


def _log_to_thread(db: Session, salon: Salon, client: Client, text: str) -> None:
    from ..agent import add_message, get_conversation
    conv = get_conversation(db, salon, client, "sms")
    add_message(db, conv, "out", "ai", text)


def handle_offer_reply(db: Session, salon: Salon, client: Client, text: str) -> Optional[str]:
    """If this client was offered a refill slot recently, resolve their reply."""
    since = datetime.utcnow() - timedelta(hours=12)
    offers = [o for o in db.scalars(select(RefillOffer).where(
        RefillOffer.salon_id == salon.id, RefillOffer.created_at >= since).order_by(RefillOffer.id.desc()))
        if client.id in (o.contacted_client_ids or [])]
    if not offers or not AFFIRMATIVE.match(text):
        return None
    offer = offers[0]
    if offer.status != "open" or offer.start <= salon_now(salon):
        if offer.filled_by_client_id == client.id:
            return None
        return ("So sorry — that spot was just taken! You're still on the waitlist and "
                "I'll text you as soon as another one opens.")

    service_id = (offer.offered_service_ids or {}).get(str(client.id))
    from ..models import Service
    service = db.get(Service, service_id)
    try:
        appt = get_platform(salon).create_booking(db, salon, service, offer.stylist_id, offer.start, client.id,
                                                  source="refill", booked_by_ai=True)
    except BookingError:
        offer.status = "filled"
        return "So sorry — that spot was just taken! You're still on the waitlist."

    offer.status = "filled"
    offer.filled_by_client_id = client.id
    offer.filled_appointment_id = appt.id
    for e in db.scalars(select(WaitlistEntry).where(WaitlistEntry.client_id == client.id,
                                                    WaitlistEntry.service_id == service.id,
                                                    WaitlistEntry.active.is_(True))):
        e.active = False

    # Let everyone else know, politely.
    for other_id in offer.contacted_client_ids or []:
        if other_id == client.id:
            continue
        other = db.get(Client, other_id)
        if other and other.opt_in:
            messaging.send_text(db, salon, other, "sms", other.phone,
                                f"Thanks for the quick reply! That {fmt_slot(offer.start)} spot has been taken, "
                                f"but you're still on our waitlist 💛", purpose="reply")
    db.flush()
    first = client.name.split()[0] if client.name else ""
    return (f"It's yours{', ' + first if first else ''}! {service.name} with {offer.stylist.name.split()[0]} "
            f"on {fmt_slot(offer.start)}. See you then ✨")


def run_refill_batches(db: Session, salon: Salon) -> dict:
    """Scheduled: expire stale offers and text the next batch where nobody bit."""
    now = salon_now(salon)
    stats = {"expired": 0, "contacted": 0}
    for offer in db.scalars(select(RefillOffer).where(RefillOffer.salon_id == salon.id, RefillOffer.status == "open")):
        if offer.start - now < timedelta(minutes=45):
            offer.status = "expired"
            stats["expired"] += 1
            continue
        if datetime.utcnow() - offer.created_at >= BATCH_INTERVAL * max(1, len(offer.contacted_client_ids or []) // BATCH_SIZE):
            stats["contacted"] += contact_next_batch(db, salon, offer)
    db.flush()
    return stats
