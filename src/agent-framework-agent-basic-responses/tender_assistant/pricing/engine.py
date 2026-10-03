from decimal import Decimal, InvalidOperation, localcontext


def calculate_item_value(quantity: str, rate: str) -> Decimal:
    """Calculate quantity × rate without monetary rounding."""
    try:
        qty = Decimal(quantity)
        unit_rate = Decimal(rate)
    except InvalidOperation as exc:
        raise ValueError("Quantity and rate must be valid numbers.") from exc

    if not qty.is_finite() or not unit_rate.is_finite():
        raise ValueError("Quantity and rate must be finite numbers.")

    # Preserve enough precision for the exact multiplication.
    precision = max(
        28,
        len(qty.as_tuple().digits) + len(unit_rate.as_tuple().digits),
    )
    with localcontext() as context:
        context.prec = precision
        return qty * unit_rate
