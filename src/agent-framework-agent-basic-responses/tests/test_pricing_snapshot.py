import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

from tender_assistant.pricing.snapshot import create_snapshot, load_snapshot, recalculate, save_snapshot
from tender_assistant.pricing.rate_catalog import record_id
from tender_assistant.pricing.rates_library import HistoricalRate


class PricingSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "estimate.json"
        record = HistoricalRate("Earthworks", "Cut to waste", "m3", Decimal("45.0"), "Test", "Test project", "")
        self.item = {"row_id": "test:sheet:105", "quantity_resolved": "685", "unit": "m3", "ready_for_rate_matching": True}
        self.recommendation = {
            "status": "proposed_match", "rate_id": record_id(record),
            "match_basis": "direct_description", "reason": "Test match",
            "assumptions": ["Similar disposal conditions"],
            "differences": ["Haul distance unknown"],
        }
        self.snapshot = create_snapshot(self.item, self.recommendation, record, {"candidate_ids": [record_id(record)]})

    def test_roundtrip_recalculates_and_retains_risks(self):
        save_snapshot(self.path, self.snapshot)
        loaded = load_snapshot(self.path)
        self.assertEqual(loaded, self.snapshot)
        self.assertEqual(recalculate(loaded), "30825.0")
        self.assertEqual(recalculate(loaded), recalculate(loaded))
        self.assertEqual(loaded["recommendation"]["differences"], ["Haul distance unknown"])

    def test_existing_estimate_is_not_overwritten(self):
        save_snapshot(self.path, self.snapshot)
        with self.assertRaises(FileExistsError):
            save_snapshot(self.path, self.snapshot)

    def test_changed_content_is_detected(self):
        save_snapshot(self.path, self.snapshot)
        data = json.loads(self.path.read_text())
        data["snapshot"]["item"]["quantity_resolved"] = "999"
        self.path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "checksum"):
            load_snapshot(self.path)

    def test_rate_and_unit_changes_are_rejected(self):
        for field, value in (("rate", "46"), ("unit", "m"), ("rate", "NaN")):
            snapshot = deepcopy(self.snapshot)
            snapshot["selected_rate"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                recalculate(snapshot)

    def test_wrong_amount_and_version_are_rejected(self):
        snapshot = deepcopy(self.snapshot)
        snapshot["indicative_value"] = "0"
        with self.assertRaises(ValueError):
            save_snapshot(self.path, snapshot)
        snapshot["calculation_version"] = "unknown"
        with self.assertRaises(ValueError):
            recalculate(snapshot)

    def test_unpriced_remains_null(self):
        recommendation = self.recommendation | {"status": "needs_review", "rate_id": None, "match_basis": None}
        snapshot = create_snapshot(self.item, recommendation, None, {"candidate_ids": []})
        save_snapshot(self.path, snapshot)
        self.assertIsNone(load_snapshot(self.path)["indicative_value"])

    def test_replay_without_site_packages_or_credentials(self):
        save_snapshot(self.path, self.snapshot)
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-S", "-m", "tender_assistant.cli.match_rates", "--replay", str(self.path)],
            capture_output=True, text=True, env={}, check=True, cwd=root,
        )
        self.assertIn("Indicative value: 30825.0", result.stdout)
        self.assertIn("Offline replay", result.stdout)


if __name__ == "__main__":
    unittest.main()
