import tempfile
import unittest
from pathlib import Path

from tender_assistant.schedules.trades import (
    build_request, validate_decisions, save_classification, load_classification,
    decision_for_item,
)


class TradeClassificationTests(unittest.TestCase):
    def setUp(self):
        self.item = dict(excel_row=105, row_id="hash:sheet:105", source_file="schedule.xlsx",
                         code="5.1", description="Cut to waste", unit="m3", category="measured_item",
                         ready_for_rate_matching=True)
        self.request = build_request([self.item])
        self.result = {"decisions": [dict(item_id="R105", status="proposed_trade", trade="Earthworks",
                                         reason="Excavation scope.", assumptions=[], source_ids=["R105"])]}

    def test_valid(self):
        self.assertEqual(validate_decisions(self.result, self.request), self.result)

    def test_invalid_trade(self):
        self.result["decisions"][0]["trade"] = "Invented"
        with self.assertRaises(ValueError):
            validate_decisions(self.result, self.request)

    def test_missing_and_duplicate_rows(self):
        for decisions in ([], self.result["decisions"] * 2):
            with self.assertRaises(ValueError):
                validate_decisions({"decisions": decisions}, self.request)

    def test_unknown_source(self):
        self.result["decisions"][0]["source_ids"] = ["invented.pdf"]
        with self.assertRaises(ValueError):
            validate_decisions(self.result, self.request)

    def test_notes_are_context_only(self):
        note = self.item | {"excel_row": 104, "category": "note"}
        request = build_request([note, self.item])
        self.assertEqual(len(request["items"]), 1)
        self.assertIn("R104", request["schedule_sources"])

    def test_review_cannot_progress(self):
        self.result["decisions"][0].update(status="requires_review", trade=None)
        validate_decisions(self.result, self.request)
        with self.assertRaises(ValueError):
            decision_for_item({"request": self.request, "result": self.result}, self.item)

    def test_changed_item_rejected(self):
        with self.assertRaises(ValueError):
            decision_for_item({"request": self.request, "result": self.result}, self.item | {"unit": "m"})

    def test_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trades.json"
            save_classification(path, self.request, self.result, "test-model")
            saved = load_classification(path)
            self.assertEqual(decision_for_item(saved, self.item)["trade"], "Earthworks")
            with self.assertRaises(FileExistsError):
                save_classification(path, self.request, self.result, "test-model")
            text = path.read_text().replace("Excavation scope.", "Altered scope.")
            path.write_text(text)
            with self.assertRaises(ValueError):
                load_classification(path)

    def test_classification_does_not_make_special_item_priceable(self):
        item = self.item | {"category": "lump_sum_or_item", "ready_for_rate_matching": False}
        request = build_request([item])
        validate_decisions(self.result, request)
        self.assertFalse(request["items"][0]["item"]["ready_for_rate_matching"])

    def test_explicit_external_citation(self):
        request = build_request([self.item], evidence={"E0001": {"text": "Excavate and dispose off site"}})
        self.result["decisions"][0]["source_ids"] = ["R105", "E0001"]
        validate_decisions(self.result, request)

    def test_missing_evidence_file_rejected(self):
        from tender_assistant.schedules.trades import check_saved_evidence
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                check_saved_evidence({"E0001": {"source_file": "missing.pdf", "source_sha256": "abc"}}, directory)

    def test_unknown_requested_row_rejected(self):
        with self.assertRaises(ValueError):
            build_request([self.item], rows=[999])


if __name__ == "__main__":
    unittest.main()
