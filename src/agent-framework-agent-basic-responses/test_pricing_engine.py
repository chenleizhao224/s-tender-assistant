import unittest
from decimal import Decimal

from pricing_engine import calculate_item_value


class PricingEngineTests(unittest.TestCase):
    def test_quantity_times_rate(self):
        result = calculate_item_value("125.50", "18.2750")
        self.assertEqual(result, Decimal("2293.512500"))

    def test_decimal_accuracy(self):
        result = calculate_item_value("0.1", "0.2")
        self.assertEqual(result, Decimal("0.02"))

    def test_zero_quantity(self):
        result = calculate_item_value("0", "18.2750")
        self.assertEqual(result, Decimal("0"))

    def test_missing_quantity_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_item_value("", "18.2750")

    def test_non_finite_numbers_are_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    calculate_item_value(value, "10")
                with self.assertRaises(ValueError):
                    calculate_item_value("10", value)

    def test_preserves_long_decimal_values(self):
        result = calculate_item_value(
            "12345678901234567890123456789", "10"
        )
        self.assertEqual(
            result, Decimal("123456789012345678901234567890")
        )


if __name__ == "__main__":
    unittest.main()