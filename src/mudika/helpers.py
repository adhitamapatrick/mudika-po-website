"""Small helper functions shared by the customer and admin pages."""

import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

### Dates (always in Toronto time, even though Cloudflare's servers run on UTC) ###

try:
    from zoneinfo import ZoneInfo

    TORONTO = ZoneInfo("America/Toronto")
except Exception:  # time zone data not available; fall back to Eastern Standard Time
    TORONTO = timezone(timedelta(hours=-5))


def now_in_toronto():
    return datetime.now(TORONTO)


def today_in_toronto():
    return now_in_toronto().date()


def parse_date(value):
    """Turn 'YYYY-MM-DD' into a date. Returns None if the text isn't a valid date."""
    try:
        return date.fromisoformat(value or "")
    except ValueError:
        return None


def pretty_date(value):
    """'2026-12-05' -> 'Sat, Dec 5'"""
    parsed = parse_date(value) if isinstance(value, str) else value
    if not parsed:
        return value
    return f"{parsed.strftime('%a, %b')} {parsed.day}"


### Money (stored as whole cents, e.g. $10.50 -> 1050) ###


def dollars_to_cents(text):
    """'10.5' -> 1050. Raises ValueError for anything that isn't a non-negative amount."""
    try:
        amount = Decimal(str(text).strip())
    except InvalidOperation as error:
        raise ValueError("Enter a valid price.") from error
    if not amount.is_finite() or amount < 0:
        raise ValueError("Enter a valid price.")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def cents_to_dollars(cents):
    """1050 -> '10.50'"""
    return f"{Decimal(cents or 0) / 100:.2f}"


### Customer details ###

PAYMENT_METHODS = ("etransfer", "cash")
ADDITIONAL_INFO_MAX_LENGTH = 500


def is_valid_phone(phone):
    """Accept 10-digit numbers, or 11 digits starting with 1, in any format."""
    digits = re.sub(r"\D", "", phone or "")
    return len(digits) == 10 or (len(digits) == 11 and digits.startswith("1"))


def payment_label(method, etransfer_email):
    if method == "etransfer":
        return f"E-transfer to {etransfer_email}" if etransfer_email else "E-transfer"
    return "Cash"


def parse_optional_int(text):
    """'' -> None, '5' -> 5. Raises ValueError for negative or non-whole numbers."""
    text = (text or "").strip()
    if text == "":
        return None
    value = int(text)
    if value < 0:
        raise ValueError
    return value
