import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
MODEL = _env("FULLCHAIR_MODEL", "claude-opus-5-5")
DATABASE_URL = _env("DATABASE_URL", "sqlite:///./fullchair.db")

TWILIO_ACCOUNT_SID = _env("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = _env("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = _env("TWILIO_FROM_NUMBER")

META_VERIFY_TOKEN = _env("META_VERIFY_TOKEN", "fullchair-verify")
META_PAGE_ACCESS_TOKEN = _env("META_PAGE_ACCESS_TOKEN")

STRIPE_SECRET_KEY = _env("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = _env("STRIPE_WEBHOOK_SECRET")

# Public URL of this API — used in deposit links and Twilio signature checks
PUBLIC_BASE_URL = _env("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

JOBS_INTERVAL_MINUTES = int(_env("JOBS_INTERVAL_MINUTES", "15") or 0)
DASHBOARD_ORIGIN = _env("DASHBOARD_ORIGIN", "http://localhost:3000")

# Reliability caps from the README
MAX_MESSAGES_PER_CONVERSATION = 60
MAX_OUTBOUND_TEXTS_PER_DAY = 200
MAX_AGENT_TOOL_ROUNDS = 8
DEPOSIT_HOLD_MINUTES = 30


def ai_enabled() -> bool:
    return bool(ANTHROPIC_API_KEY)
