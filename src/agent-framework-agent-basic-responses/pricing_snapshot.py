"""Versioned local estimates that can be replayed without model access."""

import hashlib
import json
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from pricing_engine import calculate_item_value
from rate_catalog import record_id
from rates_library import HistoricalRate


CALCULATION_VERSION = "quantity_times_rate_unrounded_v1"


def content_hash(value):
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def recalculate(snapshot):
    if snapshot.get("schema_version") != 1:
        raise ValueError("Unsupported snapshot schema version.")
    if snapshot.get("calculation_version") != CALCULATION_VERSION:
        raise ValueError("Unsupported calculation version.")
    if snapshot.get("review_status") != "Pending review":
        raise ValueError("Unsupported review status.")

    recommendation = snapshot["recommendation"]
    selected = snapshot["selected_rate"]
    status = recommendation["status"]
    if status in {"needs_review", "no_suitable_candidate"}:
        if selected is not None or recommendation["rate_id"] is not None:
            raise ValueError("Unpriced estimate must not contain a selected rate.")
        return None
    if status != "proposed_match" or not isinstance(selected, dict):
        raise ValueError("Invalid saved matching status or selected rate.")

    item = snapshot["item"]
    if item.get("ready_for_rate_matching") is not True:
        raise ValueError("Saved item was not ready for pricing.")
    quantity = item["quantity_resolved"]
    rate = selected["rate"]
    for name, value in (("quantity", quantity), ("rate", rate)):
        if not isinstance(value, str):
            raise ValueError(f"Saved {name} must be a decimal string.")
        number = Decimal(value)
        if not number.is_finite() or number < 0:
            raise ValueError(f"Saved {name} must be finite and non-negative.")
    if not item["unit"].strip() or item["unit"].strip() != selected["unit"].strip():
        raise ValueError("Saved quantity and rate units do not match.")

    record = HistoricalRate(**(selected | {"rate": Decimal(rate)}))
    if record_id(record) != recommendation["rate_id"]:
        raise ValueError("Selected rate does not match its saved rate ID.")
    if recommendation["rate_id"] not in snapshot["context"]["candidate_ids"]:
        raise ValueError("Selected rate was not in the saved candidate set.")
    return format(calculate_item_value(quantity, rate), "f")


def create_snapshot(item, recommendation, record, context):
    selected = None
    if record is not None:
        selected = asdict(record)
        selected["rate"] = format(record.rate, "f")
    snapshot = {
        "schema_version": 1,
        "calculation_version": CALCULATION_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "review_status": "Pending review",
        "item": deepcopy(item),
        "recommendation": deepcopy(recommendation),
        "selected_rate": selected,
        "context": deepcopy(context),
    }
    snapshot["indicative_value"] = recalculate(snapshot)
    return snapshot


def save_snapshot(path, snapshot):
    if recalculate(snapshot) != snapshot["indicative_value"]:
        raise ValueError("Saved amount does not match the calculated amount.")
    envelope = {"sha256": content_hash(snapshot), "snapshot": snapshot}
    text = json.dumps(envelope, ensure_ascii=False, indent=2, allow_nan=False)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never silently replace a previous estimate.
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text + "\n")


def load_snapshot(path):
    with Path(path).open(encoding="utf-8") as stream:
        envelope = json.load(stream)
    snapshot = envelope["snapshot"]
    if content_hash(snapshot) != envelope["sha256"]:
        raise ValueError("Snapshot checksum mismatch; file content has changed.")
    if recalculate(snapshot) != snapshot["indicative_value"]:
        raise ValueError("Recalculated amount differs from the saved amount.")
    return snapshot
