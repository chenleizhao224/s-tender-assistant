"""Read-only access to explicitly configured, saved API results. No model calls."""

import copy
import json
from pathlib import Path

from tender_assistant.api import build_tender_response


def load_api_response(path):
    """Load the existing API envelope without importing the agent SDK."""
    response = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"schema_version", "status", "currency", "indicative_value", "audit"}
    if not isinstance(response, dict) or required - response.keys():
        raise ValueError("API response is missing required fields.")
    # Reject NaN/Infinity even though Python's JSON reader accepts them.
    json.dumps(response, allow_nan=False)
    return response


def export_estimate(batch_path, output_path, **metadata):
    """Build and save the existing API contract; never overwrite an export."""
    batch = json.loads(Path(batch_path).read_text(encoding="utf-8"))
    response = build_tender_response(batch, **metadata)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(response, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    return response


class EstimateService:
    """Immutable in-process view of configured exports, keyed by saved tender ID.

    This is a local demo allowlist, NOT per-user authorization. Reload/restart
    after exports change. Never construct a filesystem path from tool arguments.
    """

    def __init__(self, paths):
        self._results = {}
        for path in paths:
            result = load_api_response(path)
            tender = result.get("tender")
            if not isinstance(tender, dict) or not isinstance(tender.get("id"), str) or not tender["id"].strip():
                raise ValueError("Saved response requires a tender ID.")
            tender_id = tender["id"]
            if tender_id in self._results:
                raise ValueError("Duplicate tender ID in configured exports.")
            for key in ("priced_items", "unpriced_items", "trade_subtotals", "warnings"):
                if not isinstance(result.get(key), list):
                    raise ValueError(f"Saved response requires a {key} list.")
            value = result["indicative_value"]
            if not isinstance(value, dict) or not {"amount", "scope", "is_full_tender_value", "review_status"} <= value.keys():
                raise ValueError("Saved response requires estimate scope and review status.")
            rows = []
            for item in result["priced_items"] + result["unpriced_items"]:
                row = item.get("schedule_row") if isinstance(item, dict) else None
                if type(row) is not int or row < 1 or row in rows:
                    raise ValueError("Saved response has an invalid or duplicate schedule row.")
                rows.append(row)
            self._results[tender_id] = result

    def list_tenders(self):
        return {"status": "ok", "tenders": [
            {**copy.deepcopy(data["tender"]), "result_status": data["status"]}
            for _, data in sorted(self._results.items())
        ]}

    def get_estimate(self, tender_id):
        data = self._results.get(tender_id) if isinstance(tender_id, str) else None
        if data is None:
            return {"status": "not_found", "message": "No configured saved estimate for this tender. Use list_tenders."}
        keys = ("tender", "currency", "indicative_value", "trade_subtotals", "warnings")
        return {"status": "ok", "result_status": data["status"],
                **{key: copy.deepcopy(data[key]) for key in keys}}

    def list_unpriced_items(self, tender_id):
        """Return unpriced evidence within the saved selection, not all source rows."""
        summary = self.get_estimate(tender_id)
        if summary["status"] != "ok":
            return summary
        data = self._results[tender_id]
        return {
            "status": "ok",
            "tender": copy.deepcopy(data["tender"]),
            "scope": "saved_selection_only",
            "count": len(data["unpriced_items"]),
            "items": copy.deepcopy(data["unpriced_items"]),
            "review_status": data["indicative_value"]["review_status"],
            "warnings": copy.deepcopy(data["warnings"]) + [
                "This list excludes source rows outside the saved selection; an empty list does not prove the full tender is priced."
            ],
        }

    def get_item_details(self, tender_id, row):
        summary = self.get_estimate(tender_id)
        if summary["status"] != "ok":
            return summary
        if type(row) is not int or row < 1:
            return {"status": "invalid_argument", "message": "row must be a positive Excel row number."}
        data = self._results[tender_id]
        for group, state in (("priced_items", "priced"), ("unpriced_items", "unpriced")):
            for item in data[group]:
                if item["schedule_row"] == row:
                    return {"status": "ok", "tender": copy.deepcopy(data["tender"]),
                            "currency": data["currency"], "item_status": state,
                            "item": copy.deepcopy(item),
                            "review_status": data["indicative_value"]["review_status"],
                            "warnings": copy.deepcopy(data["warnings"])}
        return {"status": "not_found", "message": "This row is not in the saved selection; no estimate is available. This does not mean zero cost."}
