import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from tender_assistant.pricing.rates_library import RateLibraryError, load_rates


class RateLibraryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "rates.json"

    def write_library(self, **changes):
        row = {
            "desc": "Synthetic excavation",
            "unit": "m3",
            "rate": 20,
            "proj_type": "Subdivision",
            "proj": "Synthetic project",
            "notes": "Test data only",
        }
        row.update(changes)
        self.path.write_text(
            json.dumps({"Earthworks": [row]}),
            encoding="utf-8",
        )

    def test_loads_complete_record(self):
        self.write_library()
        records = load_rates(self.path)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].trade, "Earthworks")
        self.assertEqual(records[0].rate, Decimal("20"))
        self.assertEqual(records[0].project, "Synthetic project")
        self.assertEqual(records[0].notes, "Test data only")

    def test_preserves_original_decimal_precision(self):
        self.path.write_text(
            '{"Earthworks": [{'
            '"desc": "Synthetic excavation",'
            '"unit": "m3",'
            '"rate": 0.12345678901234567890123456789,'
            '"proj_type": "Subdivision",'
            '"proj": "Synthetic project",'
            '"notes": ""'
            '}]}',
            encoding="utf-8",
        )

        self.assertEqual(
            load_rates(self.path)[0].rate,
            Decimal("0.12345678901234567890123456789"),
        )

    def test_missing_file_is_rejected(self):
        with self.assertRaises(RateLibraryError):
            load_rates(self.path)

    def test_invalid_json_is_rejected(self):
        self.path.write_text("{broken", encoding="utf-8")

        with self.assertRaises(RateLibraryError):
            load_rates(self.path)

    def test_blank_project_is_rejected(self):
        self.write_library(proj="")

        with self.assertRaises(RateLibraryError):
            load_rates(self.path)

    def test_invalid_rates_are_rejected(self):
        for rate in (None, True, "20", float("nan"), float("inf")):
            with self.subTest(rate=rate):
                self.write_library(rate=rate)
                with self.assertRaises(RateLibraryError):
                    load_rates(self.path)

    def test_empty_library_is_rejected(self):
        self.path.write_text("{}", encoding="utf-8")

        with self.assertRaises(RateLibraryError):
            load_rates(self.path)


if __name__ == "__main__":
    unittest.main()
