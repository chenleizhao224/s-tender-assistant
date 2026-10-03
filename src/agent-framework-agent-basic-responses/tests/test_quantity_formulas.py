import unittest
from decimal import Decimal

from tender_assistant.schedules.quantity_formulas import (
    UnsupportedQuantityFormula,
    evaluate_quantity_formula,
)


class QuantityFormulaTests(unittest.TestCase):
    def test_actual_tender_formula(self):
        self.assertEqual(
            evaluate_quantity_formula("=25*0.6*0.55"),
            Decimal("8.25"),
        )

    def test_decimal_accuracy(self):
        self.assertEqual(
            evaluate_quantity_formula("=0.1*0.2"),
            Decimal("0.02"),
        )

    def test_spaces_are_allowed(self):
        self.assertEqual(
            evaluate_quantity_formula(" = 25 * 0.6 * 0.55 "),
            Decimal("8.25"),
        )

    def test_zero(self):
        self.assertEqual(
            evaluate_quantity_formula("=25*0"),
            Decimal("0"),
        )

    def test_long_numbers_are_not_rounded(self):
        self.assertEqual(
            evaluate_quantity_formula(
                "=123456789012345678901234567890*9"
            ),
            Decimal("1111111101111111110111111111010"),
        )

    def test_unsupported_expressions_are_rejected(self):
        for formula in [
            "=D10*F10",
            "=SUM(D1:D5)",
            "=1/0",
            "=2+3",
            "=-2*3",
            "=1**2",
            "=NaN",
            "=Infinity",
            "=__import__('os')",
            "=",
            "25*0.6",
        ]:
            with self.subTest(formula=formula):
                with self.assertRaises(UnsupportedQuantityFormula):
                    evaluate_quantity_formula(formula)

    def test_non_text_is_rejected(self):
        with self.assertRaises(UnsupportedQuantityFormula):
            evaluate_quantity_formula(None)

    def test_excessive_length_is_rejected(self):
        with self.assertRaises(UnsupportedQuantityFormula):
            evaluate_quantity_formula("=" + "1" * 1001)


if __name__ == "__main__":
    unittest.main()
