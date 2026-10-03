from dataclasses import dataclass
from typing import Iterable, Literal

from tender_assistant.pricing.rates_library import HistoricalRate


def normalize_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def normalize_trade(value: str) -> str:
    trade = normalize_text(value)
    return "pavement" if trade == "roading" else trade


@dataclass(frozen=True)
class ExactMatchResult:
    status: Literal[
        "Unique exact match",
        "Multiple exact matches",
        "No exact match",
    ]
    candidates: tuple[HistoricalRate, ...]


def find_exact_matches(
    records: Iterable[HistoricalRate],
    trade: str,
    description: str,
    unit: str,
) -> ExactMatchResult:
    for name, value in (
        ("trade", trade),
        ("description", description),
        ("unit", unit),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string.")

    candidates = tuple(
        record
        for record in records
        if normalize_trade(record.trade) == normalize_trade(trade)
        and normalize_text(record.description)
        == normalize_text(description)
        and record.unit.strip() == unit.strip()
    )

    if len(candidates) == 1:
        status = "Unique exact match"
    elif candidates:
        status = "Multiple exact matches"
    else:
        status = "No exact match"

    return ExactMatchResult(status=status, candidates=candidates)
