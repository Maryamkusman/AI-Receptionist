"""Deposits via Stripe-hosted checkout. No card data ever touches FullChair."""
import hashlib
import hmac
import logging
import time

import httpx

from .. import config
from ..models import Appointment, Salon

log = logging.getLogger("fullchair.payments")


def create_deposit_link(salon: Salon, appt: Appointment, amount: float) -> str:
    if not config.STRIPE_SECRET_KEY:
        return f"{config.PUBLIC_BASE_URL}/pay/{appt.id}"
    data = {
        "mode": "payment",
        "success_url": f"{config.PUBLIC_BASE_URL}/pay/{appt.id}/done",
        "cancel_url": f"{config.PUBLIC_BASE_URL}/pay/{appt.id}",
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][unit_amount]": str(int(round(amount * 100))),
        "line_items[0][price_data][product_data][name]": f"Deposit — {appt.service.name} at {salon.name}",
        "metadata[appointment_id]": str(appt.id),
        "metadata[salon_id]": str(salon.id),
        "expires_at": str(int(time.time()) + 60 * 60),
    }
    resp = httpx.post(
        "https://api.stripe.com/v1/checkout/sessions", data=data,
        auth=(config.STRIPE_SECRET_KEY, ""), timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["url"]


def verify_stripe_signature(payload: bytes, header: str) -> bool:
    if not config.STRIPE_WEBHOOK_SECRET:
        return False
    try:
        parts = dict(p.split("=", 1) for p in header.split(","))
        signed = f"{parts['t']}.".encode() + payload
        expected = hmac.new(config.STRIPE_WEBHOOK_SECRET.encode(), signed, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, parts["v1"])
    except Exception:  # malformed header
        return False
