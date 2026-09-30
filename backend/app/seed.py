"""Creates a realistic demo salon: team, menu, clients, 90 days of history,
upcoming bookings, waitlist and sample conversations.

    python -m app.seed          # only if the database is empty
    python -m app.seed --reset  # wipe and reseed
"""
import random
import sys
from datetime import datetime, timedelta

from sqlalchemy import select

from .db import Base, engine, session_scope
from .models import (AITrace, Appointment, Client, Conversation, Message, Salon, Service, Stylist,
                     WaitlistEntry)
from .timeutil import salon_now

POLICIES = """Cancellation: please give at least 24 hours' notice. Late cancellations and no-shows forfeit the deposit.

Deposits: services over 2 hours (color, balayage, extensions) need a deposit to hold the spot. It goes toward your service.

Late arrivals: we hold your spot for 15 minutes; after that we may need to reschedule.

Consultations: free 15-minute consultations for color corrections and extensions — a stylist will reach out.

Kids: children's cuts for under 12 are $35.

Payment: we accept all major cards, Apple Pay and cash. Gratuity is appreciated but never expected."""

FAQ = """Parking: free parking in the lot behind the building, plus street parking on Maple Ave.

Products: we use and sell Olaplex, Oribe and Davines.

Prep for color: come with dry, unwashed hair (1–2 days is perfect).

Patch test: if you've never had color with us, we do a quick patch test 48 hours before — free.

Curly hair: Maya is trained in curly cuts (DevaCut and Rezo). Please come with hair dry and in its natural state.

Gift cards: available in the salon or by phone in any amount."""

STYLISTS = [
    ("Jess Rivera", "Balayage, lived-in color, blonding", "#b86b77"),
    ("Maya Chen", "Precision cuts, curly cuts, glossing", "#7b8f6a"),
    ("Priya Patel", "Extensions, bridal styling, blowouts", "#c49a5a"),
    ("Andre Brooks", "Men's cuts, fades, beard shaping", "#5f7a94"),
]

# name, category, minutes, price, deposit, stylist idx (None = anyone), rebook days, description
SERVICES = [
    ("Women's Haircut", "Cut", 60, 85, 0, None, 56, "Consultation, wash, precision cut and style."),
    ("Men's Haircut", "Cut", 30, 45, 0, [1, 3], 28, "Classic or modern cut with a hot-towel finish."),
    ("Curly Cut", "Cut", 90, 110, 0, [1], 70, "Dry curl-by-curl cut with hydration treatment."),
    ("Blowout", "Style", 45, 55, 0, None, None, "Wash and bouncy blowout."),
    ("Root Touch-Up", "Color", 90, 110, 0, [0, 1], 42, "Single-process root color with gloss."),
    ("All-Over Color", "Color", 120, 150, 40, [0, 1], 49, "Single-process color from roots to ends."),
    ("Balayage", "Color", 180, 260, 60, [0], 90, "Hand-painted, lived-in highlights with toner and style."),
    ("Full Highlights", "Color", 150, 210, 50, [0], 70, "Foil highlights with toner and blowout."),
    ("Gloss & Tone", "Color", 45, 65, 0, [0, 1], 35, "Adds shine and refreshes tone between color visits."),
    ("Tape-In Extensions", "Extensions", 180, 450, 100, [2], 56, "Install of premium tape-in extensions."),
    ("Bridal Trial", "Style", 90, 150, 50, [2], None, "Updo or bridal style trial before the big day."),
    ("Beard Trim", "Cut", 15, 20, 0, [3], 21, "Line-up and beard shaping."),
]

FIRST = ["Olivia", "Emma", "Ava", "Sophia", "Mia", "Isabella", "Amelia", "Harper", "Evelyn", "Abigail", "Ella",
         "Scarlett", "Grace", "Chloe", "Camila", "Zoe", "Nora", "Lily", "Hannah", "Aaliyah", "Leah", "Riley",
         "Naomi", "Maya", "Sofia", "James", "Marcus", "Daniel", "Luis", "Kevin", "Jordan", "Tyler", "Chris",
         "Aisha", "Fatima", "Rosa", "Tessa", "Brooke", "Kayla", "Jasmine"]
LAST = ["Johnson", "Williams", "Garcia", "Martinez", "Lee", "Walker", "Hall", "Young", "King", "Wright", "Lopez",
        "Hill", "Scott", "Green", "Adams", "Baker", "Nelson", "Carter", "Mitchell", "Perez", "Roberts", "Turner",
        "Phillips", "Campbell", "Parker", "Evans", "Edwards", "Collins", "Stewart", "Morris"]

SAMPLE_THREADS = [
    ("sms", "booked", [
        ("in", "Hi! Do you have anything Saturday for a balayage with Jess?"),
        ("out", "Hi Olivia! Jess has Saturday at 9:00 AM or 1:00 PM for balayage ($260, about 3 hours). Which works better?"),
        ("in", "1pm please!"),
        ("out", "Almost done! I'm holding Saturday 1:00 PM with Jess. Pop in the $60 deposit to lock it in — it goes toward your service."),
        ("in", "Paid! Thank you"),
        ("out", "You're all set ✨ See you Saturday at 1!"),
    ]),
    ("instagram", "booked", [
        ("in", "how much is a curly cut?? 🥺"),
        ("out", "A curly cut with Maya is $110 and takes about 90 minutes 🌀 Come with hair dry and in its natural state. Want me to check openings?"),
        ("in", "yes! anything thursday evening?"),
        ("out", "Maya has Thursday at 5:30 PM — want it?"),
        ("in", "yesss"),
        ("out", "Booked! Curly cut with Maya, Thursday 5:30 PM. See you then 💛"),
    ]),
    ("voice", "answered", [
        ("in", "Hi, do you guys have parking?"),
        ("out", "We do! There's free parking in the lot behind the building, plus street parking on Maple Avenue."),
        ("in", "Perfect, thanks."),
        ("out", "Anytime! Is there anything else I can help with?"),
    ]),
    ("sms", "handoff", [
        ("in", "My color from last week is way too orange and I'm really upset"),
        ("out", "I'm so sorry — that's not the result we want for you. I've let the team know and a stylist will reach out personally today to make it right."),
    ]),
    ("sms", "waitlisted", [
        ("in", "Any chance of a blowout tomorrow before 10?"),
        ("out", "Tomorrow morning is fully booked, but I've added you to the waitlist for early blowouts — I'll text you the moment something opens!"),
    ]),
    ("instagram", "answered", [
        ("in", "do you sell olaplex?"),
        ("out", "We do! We carry Olaplex, Oribe and Davines in the salon ✨"),
    ]),
    ("web", "booked", [
        ("in", "Need a men's cut this week, any time after 5"),
        ("out", "Andre has Wednesday at 5:30 PM or Friday at 6:00 PM. Which one?"),
        ("in", "friday"),
        ("out", "Done! Men's cut with Andre on Friday at 6:00 PM. See you then ✨"),
    ]),
    ("sms", "booked", [
        ("in", "YES"),
        ("out", "It's yours, Emma! Root touch-up with Jess on Tuesday 11:00 AM. See you then ✨"),
    ]),
]


def seed(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    rnd = random.Random(7)
    with session_scope() as db:
        if db.scalar(select(Salon)) is not None:
            print("Database already has data — use --reset to reseed.")
            return

        salon = Salon(
            name="Juniper Hair Studio", timezone="America/New_York", booking_platform="demo",
            phone="(555) 214-8890", address="418 Maple Ave, Brooklyn, NY",
            voice_tone="Warm, upbeat and polished — like a favorite front-desk coordinator. Use first names, "
                       "keep it short, a light emoji on Instagram is fine.",
            policies=POLICIES, faq=FAQ, handoff_phone="+15552148890", avg_ticket=120, plan="growth",
        )
        db.add(salon)
        db.flush()

        stylists = []
        for name, spec, color in STYLISTS:
            st = Stylist(salon_id=salon.id, name=name, specialties=spec, color=color,
                         booking_platform_id=f"demo-{name.split()[0].lower()}")
            db.add(st)
            stylists.append(st)
        db.flush()

        services = []
        for name, cat, mins, price, dep, sidx, rebook, desc in SERVICES:
            svc = Service(salon_id=salon.id, name=name, category=cat, duration_min=mins, price=price,
                          deposit_required=dep > 0, deposit_amount=dep, description=desc,
                          stylist_ids=[stylists[i].id for i in sidx] if sidx else [], rebook_interval_days=rebook)
            db.add(svc)
            services.append(svc)
        db.flush()

        clients = []
        names = set()
        while len(clients) < 48:
            n = f"{rnd.choice(FIRST)} {rnd.choice(LAST)}"
            if n in names:
                continue
            names.add(n)
            c = Client(salon_id=salon.id, name=n, phone=f"+1555{rnd.randint(1000000, 9999999)}",
                       ig_handle=("@" + n.lower().replace(" ", ".")) if rnd.random() < .4 else "",
                       preferred_stylist_id=rnd.choice(stylists).id, opt_in=rnd.random() > .05,
                       created_at=datetime.utcnow() - timedelta(days=rnd.randint(30, 400)))
            db.add(c)
            clients.append(c)
        db.flush()

        now = salon_now(salon)
        hours = {1: (9, 19), 2: (9, 19), 3: (9, 20), 4: (9, 20), 5: (8, 17)}
        busy = {}  # (stylist_id, date) -> list of (start, end)

        def fits(st, start, end):
            for s, e in busy.get((st.id, start.date()), []):
                if s < end and e > start:
                    return False
            return True

        def eligible(svc):
            return [s for s in stylists if not svc.stylist_ids or s.id in svc.stylist_ids]

        def place(day, svc, client, prefer=None):
            if day.weekday() not in hours:
                return None
            open_h, close_h = hours[day.weekday()]
            sts = eligible(svc)
            if prefer and prefer in sts:
                sts = [prefer] + [s for s in sts if s is not prefer]
            for _ in range(10):
                st = sts[0] if rnd.random() < .7 else rnd.choice(sts)
                start = datetime.combine(day, datetime.min.time()).replace(
                    hour=rnd.randint(open_h, close_h - 1), minute=rnd.choice([0, 30]))
                end = start + timedelta(minutes=svc.duration_min)
                if end.hour + end.minute / 60 > close_h or not fits(st, start, end):
                    continue
                busy.setdefault((st.id, day), []).append((start, end))
                return st, start, end
            return None

        weights = [10, 6, 3, 4, 8, 5, 5, 3, 4, 1, 1, 3]

        # 90 days of history + 10 days ahead
        for offset in range(-90, 11):
            day = (now + timedelta(days=offset)).date()
            n_appts = rnd.randint(9, 14) if offset < 0 else max(2, 12 - offset)
            for _ in range(n_appts):
                svc = rnd.choices(services, weights=weights)[0]
                client = rnd.choice(clients)
                slot = place(day, svc, client, prefer=next((s for s in stylists if s.id == client.preferred_stylist_id), None))
                if not slot:
                    continue
                st, start, end = slot
                if start < now and offset <= 0 and end > now:
                    continue
                past = end < now
                roll = rnd.random()
                ai = roll < (.2 if offset > -30 else .13)
                source = "staff"
                if ai:
                    source = rnd.choices(["ai", "refill", "nudge"], weights=[70, 15, 15])[0]
                status = "completed" if past else "booked"
                if rnd.random() < .06:
                    status = "cancelled" if not past or rnd.random() < .5 else "no_show"
                created = datetime.utcnow() + timedelta(days=min(offset, 0) - rnd.randint(0, 6), hours=-rnd.randint(0, 12))
                appt = Appointment(
                    salon_id=salon.id, external_id=f"demo_{rnd.getrandbits(40):x}", client_id=client.id,
                    service_id=svc.id, stylist_id=st.id, start=start, end=end, status=status, price=svc.price,
                    booked_by_ai=ai, source=source,
                    deposit_status=("paid" if svc.deposit_required else "none"), created_at=created,
                    cancelled_at=created + timedelta(days=1) if status == "cancelled" else None,
                )
                db.add(appt)
        db.flush()

        # Visit intervals learned from history
        for c in clients:
            starts = sorted(db.scalars(select(Appointment.start).where(
                Appointment.client_id == c.id, Appointment.status == "completed")))
            if len(starts) >= 2:
                gaps = [(b - a).days for a, b in zip(starts, starts[1:]) if (b - a).days > 7]
                if gaps:
                    c.visit_interval_days = int(sum(gaps) / len(gaps))

        # Lapsed regulars ready for a nudge
        for c in clients[:4]:
            svc = services[4]
            start = datetime.combine((now - timedelta(days=rnd.randint(50, 70))).date(), datetime.min.time()).replace(hour=11)
            db.add(Appointment(salon_id=salon.id, client_id=c.id, service_id=svc.id, stylist_id=stylists[0].id,
                               start=start, end=start + timedelta(minutes=svc.duration_min), status="completed",
                               price=svc.price, source="staff", created_at=datetime.utcnow() - timedelta(days=80)))
            c.visit_interval_days = 42
            for a in db.scalars(select(Appointment).where(Appointment.client_id == c.id, Appointment.start > start)):
                a.status = "cancelled"

        # Waitlist
        for i, (svc_i, pref, flex, st_i) in enumerate([
            (3, "weekday mornings", True, None), (4, "Saturday", False, 0), (0, "evenings after 5", True, 1),
            (6, "any weekend", True, 0), (1, "lunchtime", True, 3), (8, "Friday afternoon", False, None),
        ]):
            db.add(WaitlistEntry(salon_id=salon.id, client_id=clients[10 + i].id, service_id=services[svc_i].id,
                                 stylist_id=stylists[st_i].id if st_i is not None else None,
                                 preferred_times=pref, flexible=flex,
                                 created_at=datetime.utcnow() - timedelta(days=rnd.randint(1, 20))))

        # Conversations
        for i in range(110):
            channel, outcome, msgs = SAMPLE_THREADS[(i * 3) % len(SAMPLE_THREADS)]
            client = clients[(i * 5) % len(clients)]
            started = datetime.utcnow() - timedelta(hours=i * 13 + rnd.randint(0, 5), minutes=rnd.randint(0, 59))
            conv = Conversation(salon_id=salon.id, client_id=client.id, channel=channel,
                                status="handoff" if outcome == "handoff" and i < 8 else "closed" if i >= 3 else "open",
                                handoff_flag=outcome == "handoff", outcome=outcome, state={},
                                handoff_summary="Client unhappy with color result from last week (too orange). "
                                                "Wants it fixed — needs a stylist callback." if outcome == "handoff" else "",
                                created_at=started, last_message_at=started)
            db.add(conv)
            db.flush()
            first = client.name.split()[0]
            for j, (direction, text) in enumerate(msgs):
                text = text.replace("Olivia", first).replace("Emma", first)
                ts = started + timedelta(minutes=j * 2 + rnd.randint(0, 1))
                db.add(Message(salon_id=salon.id, conversation_id=conv.id, direction=direction,
                               sender="client" if direction == "in" else "ai", text=text, created_at=ts))
                conv.last_message_at = ts
            db.add(AITrace(salon_id=salon.id, conversation_id=conv.id, model="claude-opus-5-5",
                           prompt="(seeded)", tool_calls=[{"name": "check_availability"}] if outcome == "booked" else [],
                           input_tokens=rnd.randint(2500, 4200), output_tokens=rnd.randint(80, 240),
                           latency_ms=rnd.randint(900, 2600), created_at=started))
        print(f"Seeded {salon.name}: {len(stylists)} stylists, {len(services)} services, {len(clients)} clients.")


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
