from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from pricing_engine import calculate_item_value


@dataclass(frozen=True)
class PricedItem:
    item_id: str
    trade: str
    description: str
    quantity: str
    unit: str
    rate: str
    rate_unit: str
    price_basis: Literal["Schick Historical", "Tender fallback"]
    rate_reference: str
    tender_reference: str

    def __post_init__(self):
        required_fields = (
            "item_id",
            "trade",
            "description",
            "quantity",
            "unit",
            "rate",
            "rate_unit",
            "rate_reference",
            "tender_reference",
        )

        for name in required_fields:
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string.")

        if self.price_basis not in (
            "Schick Historical",
            "Tender fallback",
        ):
            raise ValueError("Unsupported price basis.")

        if self.unit != self.rate_unit:
            raise ValueError(
                "Quantity unit and rate unit must match."
            )

        if self.unit.strip().lower() in ("ls", "%"):
            raise ValueError(
                "LS and percentage items require separate pricing rules."
            )

        # Validate the numbers when the item is created.
        calculate_item_value(self.quantity, self.rate)

    @property
    def value(self) -> Decimal:
        return calculate_item_value(self.quantity, self.rate)