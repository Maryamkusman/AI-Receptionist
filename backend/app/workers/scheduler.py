"""In-process job loop: holds, completions, refill batches and nudges.

For multi-instance deployments move `run_all_jobs` onto Redis + RQ/Celery so only
one worker runs it; the job functions are already idempotent per run.
"""
import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..db import session_scope
from ..models import Appointment, Salon
from ..timeutil import salon_now
from .nudges import run_nudges
from .refill import run_refill_batches, start_refill

log = logging.getLogger("fullchair.jobs")


def release_expired_holds(db: Session, salon: Salon) -> int:
    now = salon_now(salon)
    n = 0
    for appt in db.scalars(select(Appointment).where(
            Appointment.salon_id == salon.id, Appointment.status == "pending_deposit",
            Appointment.hold_expires_at < now)):
        appt.status = "cancelled"
        appt.cancelled_at = datetime.utcnow()
        appt.notes = (appt.notes + " Deposit not paid; hold released.").strip()
        start_refill(db, salon, appt)
        n += 1
    return n


def mark_completed(db: Session, salon: Salon) -> int:
    now = salon_now(salon)
    n = 0
    for appt in db.scalars(select(Appointment).where(
            Appointment.salon_id == salon.id, Appointment.status == "booked", Appointment.end < now)):
        appt.status = "completed"
        n += 1
    return n


def run_all_jobs(salon_id=None) -> dict:
    results = {}
    with session_scope() as db:
        q = select(Salon) if salon_id is None else select(Salon).where(Salon.id == salon_id)
        for salon in db.scalars(q):
            results[salon.id] = {
                "holds_released": release_expired_holds(db, salon),
                "completed": mark_completed(db, salon),
                "refill": run_refill_batches(db, salon),
                "nudges": run_nudges(db, salon),
            }
    return results


async def job_loop():
    if config.JOBS_INTERVAL_MINUTES <= 0:
        return
    while True:
        await asyncio.sleep(config.JOBS_INTERVAL_MINUTES * 60)
        try:
            await asyncio.to_thread(run_all_jobs)
        except Exception:
            log.exception("scheduled jobs failed")
