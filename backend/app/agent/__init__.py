"""Inbound pipeline shared by every channel (SMS, Instagram, voice, web chat)."""
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..models import Client, Conversation, Message, Salon

STOP_WORDS = {"stop", "stopall", "unsubscribe", "cancel all", "end", "quit"}
START_WORDS = {"start", "unstop", "yes start"}
CONVERSATION_IDLE = timedelta(hours=24)


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"[^\d+]", "", phone or "")
    if digits and not digits.startswith("+"):
        digits = "+1" + digits if len(digits) == 10 else "+" + digits
    return digits


def find_or_create_client(db: Session, salon: Salon, channel: str, identity: str, name: str = "") -> Client:
    if channel == "instagram":
        client = db.scalar(select(Client).where(Client.salon_id == salon.id, Client.ig_handle == identity))
    else:
        identity = normalize_phone(identity)
        client = db.scalar(select(Client).where(Client.salon_id == salon.id, Client.phone == identity)) if identity else None
    if client:
        return client
    client = Client(salon_id=salon.id, name=name or "",
                    phone=identity if channel != "instagram" else "",
                    ig_handle=identity if channel == "instagram" else "")
    db.add(client)
    db.flush()
    return client


def get_conversation(db: Session, salon: Salon, client: Client, channel: str) -> Conversation:
    conv = db.scalar(
        select(Conversation).where(
            Conversation.salon_id == salon.id, Conversation.client_id == client.id,
            Conversation.channel == channel, Conversation.status != "closed",
        ).order_by(Conversation.last_message_at.desc()))
    if conv and datetime.utcnow() - conv.last_message_at < CONVERSATION_IDLE:
        return conv
    if conv and conv.status == "open":
        conv.status = "closed"
    conv = Conversation(salon_id=salon.id, client_id=client.id, channel=channel, state={})
    db.add(conv)
    db.flush()
    return conv


def add_message(db: Session, conv: Conversation, direction: str, sender: str, text: str) -> Message:
    msg = Message(salon_id=conv.salon_id, conversation_id=conv.id, direction=direction, sender=sender, text=text)
    db.add(msg)
    conv.last_message_at = datetime.utcnow()
    db.flush()
    db.refresh(conv, ["messages"])
    return msg


def generate_reply(db: Session, salon: Salon, client: Client, conv: Conversation) -> str:
    if config.ai_enabled():
        from .runner import run_claude_agent
        return run_claude_agent(db, salon, client, conv)
    from .demo import run_demo_agent
    return run_demo_agent(db, salon, client, conv)


def handle_inbound(db: Session, salon: Salon, channel: str, identity: str, text: str,
                   name: str = "") -> Tuple[Optional[str], Conversation]:
    """Store an inbound message and return the reply to send (None = stay silent)."""
    client = find_or_create_client(db, salon, channel, identity, name)
    conv = get_conversation(db, salon, client, channel)
    add_message(db, conv, "in", "client", text)
    lowered = text.strip().lower()

    if channel == "sms" and lowered in STOP_WORDS:
        client.opt_in = False
        reply = f"You're unsubscribed from {salon.name} texts. Reply START to resubscribe."
        add_message(db, conv, "out", "ai", reply)
        return reply, conv
    if channel == "sms" and lowered in START_WORDS:
        client.opt_in = True
        reply = f"You're resubscribed to {salon.name} texts. How can we help?"
        add_message(db, conv, "out", "ai", reply)
        return reply, conv

    # Replies to a cancellation-refill offer are handled deterministically so
    # the first "yes" wins the slot and everyone else hears it's taken.
    from ..workers.refill import handle_offer_reply
    refill_reply = handle_offer_reply(db, salon, client, text)
    if refill_reply:
        add_message(db, conv, "out", "ai", refill_reply)
        conv.outcome = conv.outcome or "booked"
        return refill_reply, conv

    if salon.ai_paused or conv.status == "handoff":
        return None, conv  # staff owns this thread

    if len(conv.messages) > config.MAX_MESSAGES_PER_CONVERSATION:
        conv.status, conv.handoff_flag = "handoff", True
        conv.handoff_summary = "Conversation hit the message cap — please take over."
        reply = "Let me get a team member to help you with this — they'll be in touch shortly!"
        add_message(db, conv, "out", "ai", reply)
        return reply, conv

    reply = generate_reply(db, salon, client, conv)
    add_message(db, conv, "out", "ai", reply)
    if not conv.outcome:
        conv.outcome = "answered"
    return reply, conv
