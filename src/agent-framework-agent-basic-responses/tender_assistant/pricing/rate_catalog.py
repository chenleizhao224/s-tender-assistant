import hashlib
import json
from typing import Iterable

from tender_assistant.pricing.rates_library import HistoricalRate


def decimal_key(value):
    """Canonical decimal text without rounding."""
    if value == 0:
        return "0"

    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def record_id(record: HistoricalRate) -> str:
    payload = {
        "trade": record.trade,
        "description": record.description,
        "unit": record.unit,
        "rate": decimal_key(record.rate),
        "project_type": record.project_type,
        "project": record.project,
        "notes": record.notes,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return "rate-" + hashlib.sha256(encoded).hexdigest()


def build_catalog(
    records: Iterable[HistoricalRate],
) -> dict[str, HistoricalRate]:
    catalog = {}

    for record in records:
        key = record_id(record)
        if key in catalog and catalog[key] != record:
            raise ValueError("Historical record ID collision.")
        catalog[key] = record

    return dict(sorted(catalog.items()))
