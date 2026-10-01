import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


class RateLibraryError(ValueError):
    """The historical rate library could not be read or validated."""


@dataclass(frozen=True)
class HistoricalRate:
    trade: str
    description: str
    unit: str
    rate: Decimal
    project_type: str
    project: str
    notes: str


def load_rates(path: str | Path) -> tuple[HistoricalRate, ...]:
    try:
        with Path(path).open(encoding="utf-8-sig") as source:
            data = json.load(
                source,
                parse_float=Decimal,
                parse_int=Decimal,
            )
    except (OSError, UnicodeError, ValueError) as exc:
        raise RateLibraryError(
            f"Historical rate source could not be read: {path}"
        ) from exc

    if not isinstance(data, dict) or not data:
        raise RateLibraryError(
            "Rate library must be a non-empty object grouped by Trade."
        )

    records = []

    for trade, rows in data.items():
        if not isinstance(trade, str) or not trade.strip():
            raise RateLibraryError("Trade must be a non-empty string.")

        if not isinstance(rows, list):
            raise RateLibraryError(f"{trade}: records must be a list.")

        for position, row in enumerate(rows, start=1):
            location = f"{trade}, record {position}"

            if not isinstance(row, dict):
                raise RateLibraryError(f"{location}: invalid record.")

            for field in ("desc", "unit", "proj_type", "proj", "notes"):
                if not isinstance(row.get(field), str):
                    raise RateLibraryError(
                        f"{location}: {field} must be a string."
                    )

            for field in ("desc", "unit", "proj"):
                if not row[field].strip():
                    raise RateLibraryError(
                        f"{location}: {field} must not be blank."
                    )

            rate = row.get("rate")
            if not isinstance(rate, Decimal) or not rate.is_finite():
                raise RateLibraryError(
                    f"{location}: rate must be a finite JSON number."
                )

            records.append(
                HistoricalRate(
                    trade=trade,
                    description=row["desc"],
                    unit=row["unit"],
                    rate=rate,
                    project_type=row["proj_type"],
                    project=row["proj"],
                    notes=row["notes"],
                )
            )

    if not records:
        raise RateLibraryError("Rate library contains no records.")

    return tuple(records)