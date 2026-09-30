from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _tz(salon) -> ZoneInfo:
    try:
        return ZoneInfo(salon.timezone)
    except Exception:
        return ZoneInfo("UTC")


def salon_now(salon) -> datetime:
    """Current wall-clock time in the salon's timezone, as a naive datetime."""
    return datetime.now(_tz(salon)).replace(tzinfo=None, second=0, microsecond=0)


def utc_to_salon(salon, dt: datetime) -> datetime:
    """Naive UTC -> naive salon-local."""
    return dt.replace(tzinfo=timezone.utc).astimezone(_tz(salon)).replace(tzinfo=None)


def fmt_slot(dt: datetime) -> str:
    """'Sat Oct 4, 2:30 PM'"""
    hour = dt.strftime("%I").lstrip("0")
    return f"{dt.strftime('%a %b')} {dt.day}, {hour}:{dt.strftime('%M %p')}"


def in_quiet_hours(salon, now: datetime) -> bool:
    start, end = salon.quiet_hours_start, salon.quiet_hours_end
    h = now.hour
    if start == end:
        return False
    if start > end:  # wraps midnight, e.g. 20 -> 9
        return h >= start or h < end
    return start <= h < end
