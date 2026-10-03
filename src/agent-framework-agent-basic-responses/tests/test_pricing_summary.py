import unittest
from decimal import Decimal

from tender_assistant.pricing.models import PricedItem
from tender_assistant.pricing.summary import summarize_by_trade


def make_item(item_id, trade, quantity, rate):
    return PricedItem(
        item_id=item_id,
        trade=trade,
        description="Synthetic test item",
        quantity=quantity,
        unit="m3",
        rate=rate,
        rate_unit="m3",
        price_basis="Schick Historical",
        rate_reference="Synthetic rate record",
        tender_reference=f"Synthetic schedule: {item_id}",
    )


class PricingSummaryTests(unittest.TestCase):
    def test_groups_items_by_trade(self):
        items = [
            make_item("EW-001", "Earthworks", "10", "20"),
            make_item("EW-002", "Earthworks", "5", "30"),
            make_item("DR-001", "Drainage", "2", "40"),
        ]

        self.assertEqual(
            summarize_by_trade(items),
            {
                "Drainage": Decimal("80"),
                "Earthworks": Decimal("350"),
            },
        )

    def test_duplicate_ids_are_rejected(self):
        items = [
            make_item("EW-001", "Earthworks", "10", "20"),
            make_item("EW-001", "Earthworks", "5", "30"),
        ]

        with self.assertRaises(ValueError):
            summarize_by_trade(items)

    def test_empty_input(self):
        self.assertEqual(summarize_by_trade([]), {})

    def test_zero_value_trade_is_preserved(self):
        items = [
            make_item("EW-001", "Earthworks", "0", "20"),
        ]

        self.assertEqual(
            summarize_by_trade(items),
            {"Earthworks": Decimal("0")},
        )

    def test_input_order_does_not_change_output(self):
        items = [
            make_item("EW-001", "Earthworks", "10", "20"),
            make_item("DR-001", "Drainage", "2", "40"),
            make_item("EW-002", "Earthworks", "5", "30"),
        ]

        forward = summarize_by_trade(items)
        backward = summarize_by_trade(reversed(items))

        self.assertEqual(
            list(forward.items()), list(backward.items())
        )

    def test_long_numbers_are_added_exactly(self):
        items = [
            make_item(
                "EW-001",
                "Earthworks",
                "12345678901234567890123456789",
                "1",
            ),
            make_item("EW-002", "Earthworks", "0.01", "1"),
        ]

        self.assertEqual(
            summarize_by_trade(items)["Earthworks"],
            Decimal("12345678901234567890123456789.01"),
        )


if __name__ == "__main__":
    unittest.main()
