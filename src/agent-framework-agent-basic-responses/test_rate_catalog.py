import unittest
from dataclasses import replace
from decimal import Decimal

from rate_catalog import build_catalog, record_id
from rates_library import HistoricalRate


def sample_record():
    return HistoricalRate(
        trade="Earthworks",
        description="Synthetic excavation",
        unit="m3",
        rate=Decimal("20.00"),
        project_type="Subdivision",
        project="Synthetic project A",
        notes="Test data only",
    )


class RateCatalogTests(unittest.TestCase):
    def test_id_is_repeatable(self):
        record = sample_record()
        self.assertEqual(record_id(record), record_id(record))

    def test_equivalent_decimal_values_have_same_id(self):
        record = sample_record()
        other = replace(record, rate=Decimal("20"))
        self.assertEqual(record_id(record), record_id(other))

    def test_changed_price_changes_id(self):
        record = sample_record()
        other = replace(record, rate=Decimal("21"))
        self.assertNotEqual(record_id(record), record_id(other))

    def test_changed_project_changes_id(self):
        record = sample_record()
        other = replace(record, project="Synthetic project B")
        self.assertNotEqual(record_id(record), record_id(other))

    def test_order_does_not_change_catalog(self):
        first = sample_record()
        second = replace(first, rate=Decimal("21"))

        self.assertEqual(
            list(build_catalog([first, second]).items()),
            list(build_catalog([second, first]).items()),
        )

    def test_identical_duplicates_share_one_entry(self):
        record = sample_record()
        catalog = build_catalog([record, record])
        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog[record_id(record)], record)


if __name__ == "__main__":
    unittest.main()