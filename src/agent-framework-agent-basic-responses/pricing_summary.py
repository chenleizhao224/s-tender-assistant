from collections import defaultdict
from decimal import Decimal, localcontext
from typing import Iterable

from pricing_models import PricedItem


def sum_exact(values: list[Decimal]) -> Decimal:
    """Add finite Decimal values without losing decimal precision."""
    if not values:
        return Decimal("0")

    minimum_exponent = min(
        value.as_tuple().exponent for value in values
    )
    maximum_digits = max(
        len(value.as_tuple().digits)
        + value.as_tuple().exponent
        - minimum_exponent
        for value in values
    )

    with localcontext() as context:
        context.prec = max(
            28, maximum_digits + len(str(len(values)))
        )
        return sum(values, Decimal("0"))


def summarize_by_trade(
    items: Iterable[PricedItem],
) -> dict[str, Decimal]:
    grouped = defaultdict(list)
    seen_ids = set()

    for item in items:
        if item.item_id in seen_ids:
            raise ValueError(
                f"Duplicate item ID: {item.item_id}"
            )

        seen_ids.add(item.item_id)
        grouped[item.trade].append(item.value)

    return {
        trade: sum_exact(grouped[trade])
        for trade in sorted(grouped)
    }