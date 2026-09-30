"""Channel webhooks: Twilio SMS + voice, Instagram DMs, Stripe, booking platform."""
import html
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..agent import handle_inbound, normalize_phone
from ..db import get_db
from ..integrations import messaging, payments
from ..integrations.booking import get_platform
from ..models import Appointment, Salon
from ..timeutil import fmt_slot
from ..workers.refill import start_refill
from .api import confirm_deposit

log = logging.getLogger("fullchair.webhooks")
router = APIRouter()


def _salon_for(db: Session, **match) -> Salon:
    for field, value in match.items():
        if value:
            salon = db.scalar(select(Salon).where(getattr(Salon, field) == value))
            if salon:
                return salon
    salon = db.scalar(select(Salon).order_by(Salon.id))
    if not salon:
        raise HTTPException(404, "No salon configured")
    return salon


def _twiml(inner: str) -> Response:
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><Response>{inner}</Response>', media_type="application/xml")


async def _twilio_form(request: Request) -> dict:
    form = {k: str(v) for k, v in (await request.form()).items()}
    url = config.PUBLIC_BASE_URL + request.url.path
    if not messaging.valid_twilio_signature(url, form, request.headers.get("X-Twilio-Signature", "")):
        raise HTTPException(403, "Invalid Twilio signature")
    return form


# ------------------------------------------------------------------ SMS

@router.post("/webhooks/twilio/sms")
async def twilio_sms(request: Request, db: Session = Depends(get_db)):
    form = await _twilio_form(request)
    salon = _salon_for(db, sms_number=normalize_phone(form.get("To", "")))
    # The reply goes back inline as TwiML, so Twilio delivers it on the same thread.
    reply, _ = handle_inbound(db, salon, "sms", form.get("From", ""), form.get("Body", "").strip())
    db.commit()
    return _twiml(f"<Message>{html.escape(reply)}</Message>" if reply else "")


# ------------------------------------------------------------------ Voice (speech in, speech out)

VOICE = 'voice="Polly.Joanna-Neural"'


def _gather(prompt: str) -> str:
    return (f'<Gather input="speech" action="/webhooks/twilio/voice/turn" method="POST" speechTimeout="auto" '
            f'language="en-US"><Say {VOICE}>{html.escape(prompt)}</Say></Gather>'
            f'<Say {VOICE}>Sorry, I didn\'t catch that. Feel free to text us anytime. Goodbye!</Say>')


@router.post("/webhooks/twilio/voice")
async def twilio_voice(request: Request, db: Session = Depends(get_db)):
    form = await _twilio_form(request)
    salon = _salon_for(db, sms_number=normalize_phone(form.get("To", "")))
    return _twiml(_gather(f"Thanks for calling {salon.name}! How can I help you today?"))


@router.post("/webhooks/twilio/voice/turn")
async def twilio_voice_turn(request: Request, db: Session = Depends(get_db)):
    form = await _twilio_form(request)
    salon = _salon_for(db, sms_number=normalize_phone(form.get("To", "")))
    speech = form.get("SpeechResult", "").strip()
    if not speech:
        return _twiml(_gather("Sorry, could you say that again?"))
    reply, conv = handle_inbound(db, salon, "voice", form.get("From", ""), speech)
    db.commit()
    if conv.status == "handoff":
        say = reply or "Let me get someone from the team to call you right back."
        if salon.handoff_phone:
            return _twiml(f"<Say {VOICE}>{html.escape(say)} Connecting you now.</Say><Dial>{html.escape(salon.handoff_phone)}</Dial>")
        return _twiml(f"<Say {VOICE}>{html.escape(say)}</Say><Hangup/>")
    return _twiml(_gather(reply or "Is there anything else I can help with?"))


# ------------------------------------------------------------------ Instagram

@router.get("/webhooks/instagram")
def instagram_verify(request: Request):
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == config.META_VERIFY_TOKEN:
        return PlainTextResponse(p.get("hub.challenge", ""))
    raise HTTPException(403, "Verification failed")


@router.post("/webhooks/instagram")
async def instagram_event(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    for entry in payload.get("entry", []):
        salon = _salon_for(db, ig_account_id=str(entry.get("id", "")))
        for event in entry.get("messaging", []):
            msg = event.get("message") or {}
            sender = (event.get("sender") or {}).get("id")
            if not sender or msg.get("is_echo") or not msg.get("text"):
                continue
            reply, conv = handle_inbound(db, salon, "instagram", sender, msg["text"])
            if reply:
                messaging.send_text(db, salon, conv.client, "instagram", sender, reply, purpose="reply")
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ Booking platform events

@router.post("/webhooks/booking/{salon_id}/cancelled")
async def booking_cancelled(salon_id: int, request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    salon = db.get(Salon, salon_id)
    if not salon:
        raise HTTPException(404)
    appt = db.scalar(select(Appointment).where(Appointment.salon_id == salon.id,
                                               Appointment.external_id == str(body.get("external_id", ""))))
    if not appt:
        raise HTTPException(404, "Unknown appointment")
    if appt.status != "cancelled":
        get_platform(salon).cancel_booking(db, salon, appt)
        start_refill(db, salon, appt)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ Stripe

@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    if not payments.verify_stripe_signature(raw, request.headers.get("Stripe-Signature", "")):
        raise HTTPException(400, "Bad signature")
    event = json.loads(raw)
    if event.get("type") == "checkout.session.completed":
        meta = event["data"]["object"].get("metadata", {})
        appt = db.get(Appointment, int(meta.get("appointment_id", 0) or 0))
        if appt:
            confirm_deposit(db, db.get(Salon, appt.salon_id), appt)
            db.commit()
    return {"received": True}


# ------------------------------------------------------------------ Demo checkout (no Stripe key)

PAY_PAGE = """<!doctype html><html><head><meta name=viewport content="width=device-width,initial-scale=1">
<title>Deposit · {salon}</title><style>
body{{margin:0;font-family:-apple-system,system-ui,sans-serif;background:#f7f2ee;color:#2a211d;display:grid;place-items:center;min-height:100vh}}
.card{{background:#fff;border-radius:20px;padding:32px;max-width:360px;width:calc(100% - 48px);box-shadow:0 10px 40px rgba(60,30,20,.08)}}
h1{{font-family:Georgia,serif;font-weight:500;margin:0 0 4px;font-size:24px}} .muted{{color:#8a7a72;font-size:14px}}
.amt{{font-size:40px;font-family:Georgia,serif;margin:20px 0}} button{{width:100%;padding:14px;border:0;border-radius:12px;
background:#2a211d;color:#fff;font-size:16px;cursor:pointer}} .ok{{color:#4c7a4f;font-weight:600}}
.tag{{display:inline-block;background:#f1e7e2;border-radius:99px;padding:3px 10px;font-size:12px;margin-bottom:16px}}
</style></head><body><div class=card><span class=tag>Demo checkout — no card needed</span>
<h1>{salon}</h1><div class=muted>{service} with {stylist}<br>{when}</div><div class=amt>${amount}</div>{action}</div></body></html>"""


def _appt_or_404(db: Session, appt_id: int) -> Appointment:
    a = db.get(Appointment, appt_id)
    if not a:
        raise HTTPException(404)
    return a


def _pay_page(db: Session, a: Appointment, action: str) -> HTMLResponse:
    salon = db.get(Salon, a.salon_id)
    amount = a.service.deposit_amount or round(a.price * .25)
    return HTMLResponse(PAY_PAGE.format(salon=html.escape(salon.name), service=html.escape(a.service.name),
                                        stylist=html.escape(a.stylist.name.split()[0]), when=fmt_slot(a.start),
                                        amount=f"{amount:.0f}", action=action))


@router.get("/pay/{appt_id}", response_class=HTMLResponse)
def demo_pay(appt_id: int, db: Session = Depends(get_db)):
    a = _appt_or_404(db, appt_id)
    if a.deposit_status == "paid":
        return _pay_page(db, a, "<p class=ok>✓ Deposit paid — you're confirmed.</p>")
    if a.status == "cancelled":
        return _pay_page(db, a, "<p class=muted>This hold has expired. Text us to rebook!</p>")
    return _pay_page(db, a, f'<form method=post action="/pay/{a.id}"><button>Pay deposit</button></form>')


@router.post("/pay/{appt_id}", response_class=HTMLResponse)
def demo_pay_submit(appt_id: int, db: Session = Depends(get_db)):
    a = _appt_or_404(db, appt_id)
    if config.STRIPE_SECRET_KEY:
        raise HTTPException(400, "Use the Stripe checkout link.")
    if a.status != "cancelled":
        confirm_deposit(db, db.get(Salon, a.salon_id), a)
        db.commit()
    return demo_pay(appt_id, db)


@router.get("/pay/{appt_id}/done", response_class=HTMLResponse)
def pay_done(appt_id: int, db: Session = Depends(get_db)):
    a = _appt_or_404(db, appt_id)
    return _pay_page(db, a, "<p class=ok>✓ Thanks! Your deposit is being confirmed.</p>")
