"""User-approved reference-price estimates, not verified booking totals."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def amount(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and 0 <= result <= Decimal("1000000000") else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def estimate_stay(reference_price, nights: int) -> Decimal | None:
    price = amount(reference_price)
    if price is None:
        return None
    if type(nights) is not int or not 1 <= nights <= 28:
        raise ValueError("Invalid stay length")
    return (price * nights).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
