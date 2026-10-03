import unittest
from decimal import Decimal

from tender_assistant.pricing.rate_matching import find_exact_matches
from tender_assistant.pricing.rates_library import HistoricalRate


def make_rate(trade="Earthworks", project="Synthetic project"):
    return HistoricalRate(
        trade=trade,
        description="Cut to waste",
        unit="m3",
        rate=Decimal("20"),
        project_type="Subdivision",
        project=project,
        notes="Test data only",
    )


class ExactMatchingTests(unittest.TestCase):
    def test_unique_match(self):
        record = make_rate()
        result = find_exact_matches(
            [record], "Earthworks", "Cut to waste", "m3"
        )
        self.assertEqual(result.status, "Unique exact match")
        self.assertEqual(result.candidates, (record,))

    def test_ignores_case_and_extra_spaces(self):
        result = find_exact_matches(
            [make_rate()], " earthworks ", " CUT  TO WASTE ", "m3"
        )
        self.assertEqual(result.status, "Unique exact match")

    def test_unit_mismatch_does_not_match(self):
        result = find_exact_matches(
            [make_rate()], "Earthworks", "Cut to waste", "m2"
        )
        self.assertEqual(result.status, "No exact match")
        self.assertEqual(result.candidates, ())

    def test_different_trade_does_not_match(self):
        result = find_exact_matches(
            [make_rate()], "Drainage", "Cut to waste", "m3"
        )
        self.assertEqual(result.status, "No exact match")

    def test_multiple_matches_preserve_all_candidates(self):
        records = [
            make_rate(project="Synthetic project A"),
            make_rate(project="Synthetic project B"),
        ]
        result = find_exact_matches(
            records, "Earthworks", "Cut to waste", "m3"
        )
        self.assertEqual(result.status, "Multiple exact matches")
        self.assertEqual(result.candidates, tuple(records))

    def test_roading_maps_to_pavement(self):
        result = find_exact_matches(
            [make_rate(trade="Pavement")],
            "Roading",
            "Cut to waste",
            "m3",
        )
        self.assertEqual(result.status, "Unique exact match")

    def test_similar_description_is_not_exact(self):
        result = find_exact_matches(
            [make_rate()], "Earthworks", "Excavate to waste", "m3"
        )
        self.assertEqual(result.status, "No exact match")

    def test_blank_description_is_rejected(self):
        with self.assertRaises(ValueError):
            find_exact_matches(
                [make_rate()], "Earthworks", "", "m3"
            )


if __name__ == "__main__":
    unittest.main()
