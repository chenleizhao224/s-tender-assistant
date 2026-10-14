"""Build a deterministic, machine-readable response from a saved pricing batch."""

from collections import defaultdict
from decimal import Decimal

from tender_assistant.pricing.snapshot import content_hash, load_snapshot, recalculate
from tender_assistant.pricing.summary import sum_exact, summarize
from tender_assistant.schedules.trades import TRADES


SCHEMA_VERSION = "1.0"


def _money(value):
    if value is None:
        return None
    return format(Decimal(value).quantize(Decimal("0.01")), "f")


def _validate_batch(batch, verify_snapshots):
    calculated = summarize(batch["entries"])
    for field in (
        "requested_rows",
        "priced_rows",
        "unpriced_rows",
        "failed_rows",
        "indicative_subtotal",
    ):
        if calculated[field] != batch[field]:
            raise ValueError(f"Batch {field} does not match its entries.")

    for entry in batch["entries"]:
        if entry["state"] not in {"priced", "unpriced", "failed"}:
            raise ValueError(f"Row {entry['excel_row']}: unknown state.")
        if entry["state"] != "priced" and entry.get("amount") is not None:
            raise ValueError(f"Row {entry['excel_row']}: unpriced row contains an amount.")
        if entry["state"] == "priced":
            rate = (entry.get("selected_rate") or {}).get("rate")
            quantity = entry.get("quantity")
            if rate is None or quantity is None:
                raise ValueError(f"Row {entry['excel_row']}: priced row is missing quantity or rate.")
            if Decimal(quantity) * Decimal(rate) != Decimal(entry["amount"]):
                raise ValueError(f"Row {entry['excel_row']}: amount does not equal quantity times rate.")

        if not verify_snapshots or not entry.get("snapshot_sha256"):
            continue
        snapshot = load_snapshot(entry["snapshot_file"])
        if content_hash(snapshot) != entry["snapshot_sha256"]:
            raise ValueError(f"Row {entry['excel_row']}: snapshot has changed.")
        if recalculate(snapshot) != entry.get("amount"):
            raise ValueError(f"Row {entry['excel_row']}: snapshot amount differs from batch.")


def _reason_code(entry):
    if entry["state"] == "failed":
        return "PROCESSING_FAILED"
    classification = entry.get("classification") or {}
    if classification.get("status") == "requires_review" or not classification.get("trade"):
        return "TRADE_REVIEW_REQUIRED"
    recommendation = entry.get("recommendation") or {}
    if recommendation.get("status") == "no_suitable_candidate":
        return "NO_SUITABLE_HISTORICAL_RATE"
    reason = (entry.get("reason") or "").casefold()
    if "lump-sum" in reason or "lump sum" in reason or "pricing rule" in reason:
        return "PRICING_RULE_NOT_IMPLEMENTED"
    if "no candidates" in reason:
        return "NO_CANDIDATES_UNDER_FILTER"
    return "UNPRICED_REVIEW_REQUIRED"


def _trade_subtotals(batch):
    entries_by_trade = defaultdict(list)
    for entry in batch["entries"]:
        entries_by_trade[entry.get("allocated_trade") or "Requires review"].append(entry)

    classified_counts = defaultdict(int)
    coverage = batch.get("classification_coverage") or {}
    for decision in coverage.get("decisions", []):
        classified_counts[decision.get("trade") or "Requires review"] += 1

    known = list(TRADES) + ["Requires review"]
    extras = sorted(set(entries_by_trade) - set(known))
    result = []
    for trade in known + extras:
        entries = entries_by_trade.get(trade, [])
        amounts = [Decimal(entry["amount"]) for entry in entries if entry.get("amount") is not None]
        priced = len(amounts)
        selected = len(entries)
        if not selected:
            status = "not_selected"
        elif not priced:
            status = "not_estimated"
        elif priced < selected:
            status = "partially_estimated"
        else:
            status = "estimated_for_selected_items"
        result.append(
            {
                "trade": trade,
                "classified_items": classified_counts.get(trade, 0),
                "selected_items": selected,
                "priced_items": priced,
                "unpriced_items": selected - priced,
                "amount": _money(sum_exact(amounts)) if amounts else None,
                "status": status,
            }
        )
    return result


def _priced_item(entry):
    rate = entry["selected_rate"]
    recommendation = entry["recommendation"]
    return {
        "schedule_row": entry["excel_row"],
        "code": entry.get("code"),
        "trade": entry.get("allocated_trade"),
        "description": entry.get("description"),
        "quantity": entry.get("quantity"),
        "unit": entry.get("unit"),
        "historical_rate": rate["rate"],
        "rate_unit": rate["unit"],
        "calculation": f"{entry['quantity']} x {rate['rate']}",
        "indicative_amount": _money(entry["amount"]),
        "match_basis": recommendation.get("match_basis"),
        "historical_project": rate.get("project"),
        "historical_description": rate.get("description"),
        "reason": recommendation.get("reason"),
        "assumptions": recommendation.get("assumptions", []),
        "differences": recommendation.get("differences", []),
        "review_status": "pending_review",
    }


def _unpriced_item(entry):
    recommendation = entry.get("recommendation") or {}
    classification = entry.get("classification") or {}
    return {
        "schedule_row": entry["excel_row"],
        "code": entry.get("code"),
        "trade": entry.get("allocated_trade"),
        "description": entry.get("description"),
        "quantity": entry.get("quantity"),
        "unit": entry.get("unit"),
        "reason_code": _reason_code(entry),
        "reason": recommendation.get("reason") or entry.get("reason") or "Review required.",
        "classification_reason": classification.get("reason"),
        "differences": recommendation.get("differences", []),
        "excluded_from_indicative_value": True,
        "not_zero_cost": True,
    }


def build_tender_response(
    batch,
    *,
    tender_id,
    tender_name,
    schedule_revision,
    currency="NZD",
    verify_snapshots=True,
):
    """Return the stable API contract; all monetary values are decimal strings."""
    _validate_batch(batch, verify_snapshots)
    if batch["failed_rows"]:
        status = "completed_with_errors"
    elif batch["unpriced_rows"]:
        status = "completed_with_unpriced_items"
    else:
        status = "completed"

    priced = [_priced_item(entry) for entry in batch["entries"] if entry["state"] == "priced"]
    unpriced = [_unpriced_item(entry) for entry in batch["entries"] if entry["state"] != "priced"]
    coverage = batch.get("classification_coverage") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "tender": {
            "id": tender_id,
            "name": tender_name,
            "schedule_revision": schedule_revision,
        },
        "status": status,
        "currency": currency,
        "indicative_value": {
            "amount": _money(batch["indicative_subtotal"]),
            "scope": "selected_items_only",
            "selected_items": len(batch["entries"]),
            "priced_items": batch["priced_rows"],
            "unpriced_items": batch["unpriced_rows"],
            "failed_items": batch["failed_rows"],
            "is_full_tender_value": False,
            "review_status": "pending_review",
        },
        "trade_subtotals": _trade_subtotals(batch),
        "priced_items": priced,
        "unpriced_items": unpriced,
        "calculation": {
            "engine": "python_decimal",
            "formula": "quantity x selected historical unit rate",
            "model_calculates_amounts": False,
        },
        "warnings": [
            "This is an indicative subtotal for selected items only, not the full tender value.",
            "Unpriced items are excluded from the subtotal and are not treated as zero cost.",
            "Historical rate recommendations and model explanations remain pending estimator review.",
        ],
        "audit": {
            "batch_created_at": batch["created_at"],
            "batch_sha256": content_hash(batch),
            "schedule_sha256": batch["source_sha256"],
            "classification_sha256": coverage.get("fingerprint"),
            "model_role": "trade classification and historical rate recommendation",
            "model_name": "GPT-luna",
            "replayable": True,
        },
    }
