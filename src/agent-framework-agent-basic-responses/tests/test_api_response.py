import copy
import unittest

from tender_assistant.api import build_tender_response
from tender_assistant.pricing.summary import summarize


def sample_batch():
    entries = [
        {
            "excel_row": 10,
            "state": "priced",
            "amount": "25.000",
            "allocated_trade": "Earthworks",
            "code": "1.1",
            "description": "Excavate",
            "quantity": "2.5",
            "unit": "m3",
            "selected_rate": {
                "rate": "10.00",
                "unit": "m3",
                "project": "Historical project",
                "description": "Excavate material",
            },
            "recommendation": {
                "status": "proposed_match",
                "match_basis": "comparable",
                "reason": "Closest historical scope.",
                "assumptions": ["Comparable ground conditions."],
                "differences": ["Haul distance is unknown."],
            },
        },
        {
            "excel_row": 11,
            "state": "unpriced",
            "amount": None,
            "allocated_trade": "P&G",
            "code": "1.2",
            "description": "Site establishment",
            "quantity": None,
            "unit": "LS",
            "reason": "Requires a separate lump-sum pricing rule.",
            "classification": {
                "status": "proposed_trade",
                "trade": "P&G",
                "reason": "General requirement.",
            },
        },
    ]
    batch = summarize(entries)
    batch.update(
        source_sha256="schedule-hash",
        created_at="2026-10-04T00:00:00+00:00",
        classification_coverage={
            "fingerprint": "classification-hash",
            "decisions": [
                {"trade": "Earthworks"},
                {"trade": "P&G"},
            ],
        },
    )
    return batch


class ApiResponseTests(unittest.TestCase):
    def build(self, batch=None):
        return build_tender_response(
            batch or sample_batch(),
            tender_id="demo-0a",
            tender_name="Demo Tender",
            schedule_revision="0A",
            verify_snapshots=False,
        )

    def test_indicative_value_and_decimal_strings(self):
        response = self.build()
        self.assertEqual(response["status"], "completed_with_unpriced_items")
        self.assertEqual(response["indicative_value"]["amount"], "25.00")
        self.assertFalse(response["indicative_value"]["is_full_tender_value"])
        self.assertEqual(response["priced_items"][0]["calculation"], "2.5 x 10.00")
        self.assertEqual(response["priced_items"][0]["indicative_amount"], "25.00")

    def test_unpriced_reason_is_machine_readable(self):
        item = self.build()["unpriced_items"][0]
        self.assertEqual(item["reason_code"], "PRICING_RULE_NOT_IMPLEMENTED")
        self.assertTrue(item["excluded_from_indicative_value"])
        self.assertTrue(item["not_zero_cost"])

    def test_trade_status_distinguishes_not_selected_and_not_estimated(self):
        trades = {item["trade"]: item for item in self.build()["trade_subtotals"]}
        self.assertEqual(trades["Earthworks"]["amount"], "25.00")
        self.assertEqual(trades["P&G"]["status"], "not_estimated")
        self.assertEqual(trades["Drainage"]["status"], "not_selected")

    def test_same_batch_produces_same_response(self):
        self.assertEqual(self.build(), self.build())

    def test_tampered_amount_is_rejected(self):
        batch = copy.deepcopy(sample_batch())
        batch["entries"][0]["amount"] = "26.00"
        batch["indicative_subtotal"] = "26.00"
        with self.assertRaisesRegex(ValueError, "quantity times rate"):
            self.build(batch)


if __name__ == "__main__":
    unittest.main()
