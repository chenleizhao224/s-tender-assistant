import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal

from pricing_models import PricedItem


class PricedItemTests(unittest.TestCase):
    def make_item(self, **changes):
        fields = {
            "item_id": "EW-001",
            "trade": "Earthworks",
            "description": "Synthetic excavation example",
            "quantity": "10",
            "unit": "m3",
            "rate": "20",
            "rate_unit": "m3",
            "price_basis": "Schick Historical",
            "rate_reference": "Synthetic library record TEST-001",
            "tender_reference": "Synthetic schedule row EW-001",
        }
        fields.update(changes)
        return PricedItem(**fields)

    def test_item_value(self):
        self.assertEqual(self.make_item().value, Decimal("200"))

    def test_unit_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            self.make_item(rate_unit="m2")

    def test_missing_source_is_rejected(self):
        with self.assertRaises(ValueError):
            self.make_item(rate_reference="")

    def test_special_pricing_units_are_rejected(self):
        for unit in ("LS", "%"):
            with self.subTest(unit=unit):
                with self.assertRaises(ValueError):
                    self.make_item(unit=unit, rate_unit=unit)

    def test_invalid_price_basis_is_rejected(self):
        with self.assertRaises(ValueError):
            self.make_item(price_basis="Guessed")

    def test_item_cannot_be_modified(self):
        item = self.make_item()
        with self.assertRaises(FrozenInstanceError):
            item.rate = "99"


if __name__ == "__main__":
    unittest.main()