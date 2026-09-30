"""Outbound messaging with consent, quiet hours and daily caps enforced in one place."""
import base64
import hashlib
import hmac
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..models import Client, OutboundMessage, Salon
from ..timeutil import in_quiet_hours, salon_now

log = logging.getLogger("fullchair.messaging")

PROACTIVE = {"refill", "nudge"}


def twilio_enabled() -> bool:
    return bool(config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN and config.TWILIO_FROM_NUMBER)


def _sent_today(db: Session, salon: Salon) -> int:
    since = datetime.utcnow() - timedelta(days=1)
    return db.scalar(
        select(func.count(OutboundMessage.id)).where(
            OutboundMessage.salon_id == salon.id,
            OutboundMessage.created_at >= since,
            OutboundMessage.status.in_(("sent", "simulated")),
        )
    ) or 0


def can_send_proactive(db: Session, salon: Salon, client: Client) -> Optional[str]:
    """Returns a reason string if a proactive text is not allowed right now."""
    if not client.opt_in:
        return "client opted out"
    if not client.phone:
        return "no phone number"
    if in_quiet_hours(salon, salon_now(salon)):
        return "quiet hours"
    if _sent_today(db, salon) >= config.MAX_OUTBOUND_TEXTS_PER_DAY:
        return "daily text cap reached"
    return None


def send_text(db: Session, salon: Salon, client: Optional[Client], channel: str, to: str, text: str,
              purpose: str = "reply") -> OutboundMessage:
    status = "simulated"
    if purpose in PROACTIVE and client is not None:
        reason = can_send_proactive(db, salon, client)
        if reason:
            status = "blocked"
            log.info("blocked %s text to %s: %s", purpose, to, reason)
    if status != "blocked" and channel == "sms" and twilio_enabled() and to:
        status = _send_twilio(to, text)
    elif status != "blocked" and channel == "instagram" and config.META_PAGE_ACCESS_TOKEN and to:
        status = _send_instagram(to, text)

    msg = OutboundMessage(
        salon_id=salon.id, client_id=client.id if client else None, channel=channel, to=to or "",
        text=text, purpose=purpose, status=status,
    )
    db.add(msg)
    db.flush()
    return msg


def notify_staff(db: Session, salon: Salon, text: str) -> None:
    send_text(db, salon, None, "sms", salon.handoff_phone, text, purpose="handoff")


def _send_twilio(to: str, body: str) -> str:
    try:
        r = httpx.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{config.TWILIO_ACCOUNT_SID}/Messages.json",
            data={"From": config.TWILIO_FROM_NUMBER, "To": to, "Body": body},
            auth=(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN), timeout=15,
        )
        r.raise_for_status()
        return "sent"
    except Exception:
        log.exception("twilio send failed")
        return "failed"


def _send_instagram(recipient_id: str, text: str) -> str:
    try:
        r = httpx.post(
            "https://graph.facebook.com/v21.0/me/messages",
            params={"access_token": config.META_PAGE_ACCESS_TOKEN},
            json={"recipient": {"id": recipient_id}, "message": {"text": text}}, timeout=15,
        )
        r.raise_for_status()
        return "sent"
    except Exception:
        log.exception("instagram send failed")
        return "failed"


def valid_twilio_signature(url: str, params: dict, signature: str) -> bool:
    if not config.TWILIO_AUTH_TOKEN:
        return True  # demo mode: nothing to verify against
    payload = url + "".join(k + params[k] for k in sorted(params))
    digest = hmac.new(config.TWILIO_AUTH_TOKEN.encode(), payload.encode(), hashlib.sha1).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), signature or "")
