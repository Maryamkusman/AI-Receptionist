"""Booking-platform adapters.

The booking platform is the source of truth. `DemoBookingPlatform` treats
FullChair's own appointments table as the platform so the product works end to
end without any external account. Real platforms (Vagaro, Boulevard, Square
Appointments, Fresha, ...) plug in by implementing `BookingPlatform` and writing
the confirmed result into the appointments mirror.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Appointment, Salon, Service, Stylist
from ..timeutil import DAY_KEYS, salon_now

SLOT_STEP_MIN = 30
MIN_LEAD_MIN = 60
ACTIVE_STATUSES = ("booked", "pending_deposit", "completed")


class BookingError(Exception):
    """Raised when the platform refuses or cannot confirm an action."""


@dataclass
class Slot:
    start: datetime
    end: datetime
    stylist_id: int
    stylist_name: str


class BookingPlatform:
    def check_availability(
        self, db: Session, salon: Salon, service: Service, day_from: date, day_to: date,
        stylist_id: Optional[int] = None, limit: int = 12,
    ) -> List[Slot]:
        raise NotImplementedError

    def create_booking(
        self, db: Session, salon: Salon, service: Service, stylist_id: int, start: datetime,
        client_id: int, source: str, booked_by_ai: bool,
    ) -> Appointment:
        raise NotImplementedError

    def reschedule_booking(self, db: Session, salon: Salon, appt: Appointment, new_start: datetime,
                           stylist_id: Optional[int] = None) -> Appointment:
        raise NotImplementedError

    def cancel_booking(self, db: Session, salon: Salon, appt: Appointment) -> Appointment:
        raise NotImplementedError


def _eligible_stylists(db: Session, salon: Salon, service: Service, stylist_id: Optional[int]) -> List[Stylist]:
    q = select(Stylist).where(Stylist.salon_id == salon.id, Stylist.active.is_(True))
    stylists = list(db.scalars(q))
    if service.stylist_ids:
        stylists = [s for s in stylists if s.id in service.stylist_ids]
    if stylist_id:
        stylists = [s for s in stylists if s.id == stylist_id]
    return stylists


def _busy(db: Session, salon: Salon, stylist_id: int, start: datetime, end: datetime,
          ignore_id: Optional[int] = None) -> bool:
    now = salon_now(salon)
    q = select(Appointment).where(
        Appointment.salon_id == salon.id,
        Appointment.stylist_id == stylist_id,
        Appointment.status.in_(ACTIVE_STATUSES),
        Appointment.start < end,
        Appointment.end > start,
    )
    for appt in db.scalars(q):
        if ignore_id and appt.id == ignore_id:
            continue
        # An unpaid deposit hold that has expired no longer blocks the slot.
        if appt.status == "pending_deposit" and appt.hold_expires_at and appt.hold_expires_at < now:
            continue
        return True
    return False


def _hours_for(salon: Salon, stylist: Stylist, day: date):
    hours = stylist.hours or salon.hours or {}
    span = hours.get(DAY_KEYS[day.weekday()])
    salon_span = (salon.hours or {}).get(DAY_KEYS[day.weekday()])
    if not span or not salon_span:
        return None
    return max(span[0], salon_span[0]), min(span[1], salon_span[1])


class DemoBookingPlatform(BookingPlatform):
    def check_availability(self, db, salon, service, day_from, day_to, stylist_id=None, limit=12):
        now = salon_now(salon)
        earliest = now + timedelta(minutes=MIN_LEAD_MIN)
        slots: List[Slot] = []
        stylists = _eligible_stylists(db, salon, service, stylist_id)
        day = day_from
        while day <= day_to and len(slots) < limit:
            day_slots: List[Slot] = []
            for st in stylists:
                span = _hours_for(salon, st, day)
                if not span:
                    continue
                t = datetime.combine(day, datetime.min.time()).replace(hour=int(span[0]))
                close = datetime.combine(day, datetime.min.time()).replace(hour=int(span[1]))
                while t + timedelta(minutes=service.duration_min) <= close:
                    end = t + timedelta(minutes=service.duration_min)
                    if t >= earliest and not _busy(db, salon, st.id, t, end):
                        day_slots.append(Slot(t, end, st.id, st.name))
                    t += timedelta(minutes=SLOT_STEP_MIN)
            # Spread the day's options across the day instead of listing every half hour.
            day_slots.sort(key=lambda s: (s.start, s.stylist_name))
            seen_times = set()
            picked = []
            for s in day_slots:
                bucket = (s.start.hour // 2)
                if (bucket, s.stylist_id) in seen_times:
                    continue
                seen_times.add((bucket, s.stylist_id))
                picked.append(s)
            slots.extend(picked[: max(1, limit - len(slots))])
            day += timedelta(days=1)
        return slots[:limit]

    def create_booking(self, db, salon, service, stylist_id, start, client_id, source, booked_by_ai):
        end = start + timedelta(minutes=service.duration_min)
        stylists = _eligible_stylists(db, salon, service, stylist_id)
        if not stylists:
            raise BookingError("That stylist doesn't offer this service.")
        stylist = stylists[0]
        span = _hours_for(salon, stylist, start.date())
        if not span or start.hour < span[0] or (end.hour + end.minute / 60) > span[1]:
            raise BookingError("That time is outside working hours.")
        if start < salon_now(salon):
            raise BookingError("That time is in the past.")
        if _busy(db, salon, stylist.id, start, end):
            raise BookingError("That slot was just taken.")
        appt = Appointment(
            salon_id=salon.id, external_id=f"demo_{uuid.uuid4().hex[:10]}", client_id=client_id,
            service_id=service.id, stylist_id=stylist.id, start=start, end=end, status="booked",
            price=service.price, booked_by_ai=booked_by_ai, source=source,
        )
        db.add(appt)
        db.flush()
        return appt

    def reschedule_booking(self, db, salon, appt, new_start, stylist_id=None):
        duration = appt.end - appt.start
        new_end = new_start + duration
        sid = stylist_id or appt.stylist_id
        if new_start < salon_now(salon):
            raise BookingError("That time is in the past.")
        if _busy(db, salon, sid, new_start, new_end, ignore_id=appt.id):
            raise BookingError("That slot is taken.")
        appt.start, appt.end, appt.stylist_id = new_start, new_end, sid
        db.flush()
        return appt

    def cancel_booking(self, db, salon, appt):
        appt.status = "cancelled"
        appt.cancelled_at = datetime.utcnow()
        db.flush()
        return appt


class UnconnectedPlatform(DemoBookingPlatform):
    """Placeholder for a named platform whose API isn't wired up yet.

    It behaves like the demo platform so the salon can be onboarded and tested,
    and the dashboard shows the platform as 'not connected'.
    """


_PLATFORMS = {"demo": DemoBookingPlatform()}


def get_platform(salon: Salon) -> BookingPlatform:
    return _PLATFORMS.get(salon.booking_platform, UnconnectedPlatform())


def platform_connected(salon: Salon) -> bool:
    return salon.booking_platform in _PLATFORMS
