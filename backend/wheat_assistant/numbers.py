"""Bound input magnitudes so Decimal operations remain exact and resource bounded."""
from decimal import Decimal, InvalidOperation

def positive_decimal(value, maximum):
    raw = str(value).strip()
    if len(raw) > 80:
        raise ValueError("Numeric representation is too long")
    try:
        amount = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("Invalid number") from exc
    if not amount.is_finite() or amount <= 0 or amount > maximum:
        raise ValueError("Number is outside the supported positive range")
    if amount.as_tuple().exponent < -6:
        raise ValueError("At most six decimal places are supported")
    return amount
