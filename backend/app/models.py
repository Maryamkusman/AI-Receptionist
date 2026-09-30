"""Data model. Every table carries salon_id so one database serves all tenants.

Times on appointments are naive datetimes in the salon's local timezone;
created_at / audit timestamps are naive UTC.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.utcnow()


DEFAULT_HOURS = {
    "mon": None,
    "tue": [9, 19],
    "wed": [9, 19],
    "thu": [9, 20],
    "fri": [9, 20],
    "sat": [8, 17],
    "sun": None,
}


class Salon(Base):
    __tablename__ = "salons"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")
    booking_platform: Mapped[str] = mapped_column(String(40), default="demo")
    phone: Mapped[str] = mapped_column(String(40), default="")
    address: Mapped[str] = mapped_column(String(240), default="")
    voice_tone: Mapped[str] = mapped_column(Text, default="Warm, upbeat and concise.")
    policies: Mapped[str] = mapped_column(Text, default="")
    faq: Mapped[str] = mapped_column(Text, default="")
    hours: Mapped[dict] = mapped_column(JSON, default=lambda: dict(DEFAULT_HOURS))
    quiet_hours_start: Mapped[int] = mapped_column(Integer, default=20)
    quiet_hours_end: Mapped[int] = mapped_column(Integer, default=9)
    handoff_phone: Mapped[str] = mapped_column(String(40), default="")
    # Channel routing: which inbound number / Instagram account belongs to this salon
    sms_number: Mapped[str] = mapped_column(String(40), default="", index=True)
    ig_account_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    avg_ticket: Mapped[float] = mapped_column(Float, default=120.0)
    plan: Mapped[str] = mapped_column(String(20), default="pro")
    ai_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Stylist(Base):
    __tablename__ = "stylists"
    id: Mapped[int] = mapped_column(primary_key=True)
    salon_id: Mapped[int] = mapped_column(ForeignKey("salons.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    specialties: Mapped[str] = mapped_column(String(240), default="")
    color: Mapped[str] = mapped_column(String(16), default="#b86b77")
    hours: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # falls back to salon hours
    booking_platform_id: Mapped[str] = mapped_column(String(80), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Service(Base):
    __tablename__ = "services"
    id: Mapped[int] = mapped_column(primary_key=True)
    salon_id: Mapped[int] = mapped_column(ForeignKey("salons.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(60), default="Hair")
    description: Mapped[str] = mapped_column(Text, default="")
    duration_min: Mapped[int] = mapped_column(Integer, default=60)
    price: Mapped[float] = mapped_column(Float, default=0)
    deposit_required: Mapped[bool] = mapped_column(Boolean, default=False)
    deposit_amount: Mapped[float] = mapped_column(Float, default=0)
    stylist_ids: Mapped[list] = mapped_column(JSON, default=list)  # empty = any stylist
    rebook_interval_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Client(Base):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True)
    salon_id: Mapped[int] = mapped_column(ForeignKey("salons.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    phone: Mapped[str] = mapped_column(String(40), default="", index=True)
    ig_handle: Mapped[str] = mapped_column(String(80), default="", index=True)
    email: Mapped[str] = mapped_column(String(120), default="")
    preferred_stylist_id: Mapped[Optional[int]] = mapped_column(ForeignKey("stylists.id"), nullable=True)
    visit_interval_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    opt_in: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    last_nudged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    preferred_stylist = relationship("Stylist", lazy="joined")


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    salon_id: Mapped[int] = mapped_column(ForeignKey("salons.id"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20))  # sms | instagram | voice | web
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | handoff | closed
    handoff_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    handoff_summary: Mapped[str] = mapped_column(Text, default="")
    outcome: Mapped[str] = mapped_column(String(40), default="")  # booked | answered | handoff ...
    # Small scratchpad: slots offered in a nudge, demo-agent state, attribution hints
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    last_message_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    client = relationship("Client", lazy="joined")
    messages = relationship("Message", order_by="Message.id", lazy="selectin")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    salon_id: Mapped[int] = mapped_column(ForeignKey("salons.id"), index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    direction: Mapped[str] = mapped_column(String(4))  # in | out
    sender: Mapped[str] = mapped_column(String(10))  # client | ai | staff | system
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[int] = mapped_column(primary_key=True)
    salon_id: Mapped[int] = mapped_column(ForeignKey("salons.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(80), default="")
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    stylist_id: Mapped[int] = mapped_column(ForeignKey("stylists.id"))
    start: Mapped[datetime] = mapped_column(DateTime, index=True)
    end: Mapped[datetime] = mapped_column(DateTime)
    # booked | pending_deposit | completed | cancelled | no_show
    status: Mapped[str] = mapped_column(String(20), default="booked")
    price: Mapped[float] = mapped_column(Float, default=0)
    booked_by_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(20), default="staff")  # staff | ai | refill | nudge
    deposit_status: Mapped[str] = mapped_column(String(12), default="none")  # none | pending | paid
    deposit_url: Mapped[str] = mapped_column(String(300), default="")
    hold_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    client = relationship("Client", lazy="joined")
    service = relationship("Service", lazy="joined")
    stylist = relationship("Stylist", lazy="joined")


class WaitlistEntry(Base):
    __tablename__ = "waitlist"
    id: Mapped[int] = mapped_column(primary_key=True)
    salon_id: Mapped[int] = mapped_column(ForeignKey("salons.id"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    stylist_id: Mapped[Optional[int]] = mapped_column(ForeignKey("stylists.id"), nullable=True)
    preferred_times: Mapped[str] = mapped_column(String(200), default="")
    flexible: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    client = relationship("Client", lazy="joined")
    service = relationship("Service", lazy="joined")
    stylist = relationship("Stylist", lazy="joined")


class RefillOffer(Base):
    """An open slot being offered to waitlist clients after a cancellation."""

    __tablename__ = "refill_offers"
    id: Mapped[int] = mapped_column(primary_key=True)
    salon_id: Mapped[int] = mapped_column(ForeignKey("salons.id"), index=True)
    cancelled_appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"))
    stylist_id: Mapped[int] = mapped_column(ForeignKey("stylists.id"))
    start: Mapped[datetime] = mapped_column(DateTime)
    end: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(12), default="open")  # open | filled | expired
    contacted_client_ids: Mapped[list] = mapped_column(JSON, default=list)
    offered_service_ids: Mapped[dict] = mapped_column(JSON, default=dict)  # client_id -> service_id
    filled_by_client_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    filled_appointment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    stylist = relationship("Stylist", lazy="joined")


class OutboundMessage(Base):
    """Every text FullChair sends — used for daily caps and as the demo outbox."""

    __tablename__ = "outbound_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    salon_id: Mapped[int] = mapped_column(ForeignKey("salons.id"), index=True)
    client_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clients.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(20))
    to: Mapped[str] = mapped_column(String(80))
    text: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(String(20), default="reply")  # reply | refill | nudge | handoff
    status: Mapped[str] = mapped_column(String(20), default="sent")  # sent | simulated | failed | blocked
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AITrace(Base):
    __tablename__ = "ai_traces"
    id: Mapped[int] = mapped_column(primary_key=True)
    salon_id: Mapped[int] = mapped_column(ForeignKey("salons.id"), index=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("conversations.id"), nullable=True)
    model: Mapped[str] = mapped_column(String(60), default="")
    prompt: Mapped[str] = mapped_column(Text, default="")
    retrieved_context: Mapped[str] = mapped_column(Text, default="")
    tool_calls: Mapped[list] = mapped_column(JSON, default=list)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
