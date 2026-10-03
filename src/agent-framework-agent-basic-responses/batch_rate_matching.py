"""Small explicit row batches; reuse saved estimates and report coverage."""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from pricing_snapshot import content_hash, load_snapshot, recalculate
from pricing_summary import sum_exact
from try_rate_matching import validate_result


def checked_snapshot(path, item, trade, cross_trade):
    snapshot = load_snapshot(path)
    if snapshot["item"] != item:
        raise ValueError("Saved source/quantity differs from the current prepared row.")
    context = snapshot["context"]
    if context["trade_filter"].casefold() != trade.casefold() or context["cross_trade"] != cross_trade:
        raise ValueError("Saved matching scope differs from the requested filters.")
    selected = snapshot["selected_rate"]
    candidates = {snapshot["recommendation"]["rate_id"]: selected} if selected else {}
    validate_result(json.dumps(snapshot["recommendation"]), candidates)
    return snapshot


def summarize(entries):
    rows = [entry["excel_row"] for entry in entries]
    if len(rows) != len(set(rows)):
        raise ValueError("Duplicate rows would double-count the subtotal.")
    amounts = [Decimal(entry["amount"]) for entry in entries if entry["amount"] is not None]
    return {
        "scope": "Selected rows only; not the full tender value",
        "review_status": "Pending review",
        "requested_rows": rows,
        "priced_rows": len(amounts),
        "unpriced_rows": sum(entry["state"] == "unpriced" for entry in entries),
        "failed_rows": sum(entry["state"] == "failed" for entry in entries),
        "indicative_subtotal": format(sum_exact(amounts), "f") if amounts else None,
        "entries": entries,
    }


def parse_overrides(values, rows):
    overrides = {}
    for value in values:
        row_text, separator, filename = value.partition("=")
        if not separator or not filename.strip():
            raise ValueError("Use --snapshot ROW=PATH.")
        row = int(row_text)
        if row not in rows:
            raise ValueError(f"Snapshot row {row} is not in --rows.")
        if row in overrides:
            raise ValueError(f"Multiple snapshots specified for row {row}.")
        path = Path(filename).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"Explicit snapshot does not exist: {path}")
        overrides[row] = path
    return overrides


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", nargs="+", type=int, required=True)
    parser.add_argument("--trade", required=True)
    parser.add_argument("--cross-trade", action="store_true")
    parser.add_argument("--version", default="v1", help="Saved selection set, e.g. v1 or v2.")
    parser.add_argument("--offline", action="store_true", help="Use saved results only; never call the model.")
    parser.add_argument("--snapshot", action="append", default=[], metavar="ROW=PATH",
                        help="Use a specific existing snapshot for a row; repeat for multiple rows.")
    args = parser.parse_args()
    if len(args.rows) != len(set(args.rows)):
        parser.error("Duplicate row numbers are not allowed.")
    if not args.version.isalnum():
        parser.error("Version must contain only letters and numbers.")
    try:
        overrides = parse_overrides(args.snapshot, args.rows)
    except ValueError as error:
        parser.error(str(error))

    from dotenv import load_dotenv
    from document_inventory import sha256_file
    from schedule_extraction import extract_schedule
    from schedule_preparation import prepare_schedule

    root = Path(__file__).parent
    load_dotenv(root / ".env")
    source = Path(os.environ["TENDER_INPUT_DIR"]) / "NTT 02" / "20260707 - Hopuhopu Development - Schedule of Prices [0A].xlsx"
    document = extract_schedule(source)
    items = {item["excel_row"]: item for item in prepare_schedule(document)}
    library_hash = sha256_file(Path(os.environ["SCHICK_RATES_PATH"]))
    entries = []

    for row in sorted(args.rows):
        path = overrides.get(row, root / "outputs" / "matches" / f"row-{row}-{args.version}.json")
        entry = {"excel_row": row, "amount": None, "state": "failed", "snapshot_file": str(path)}
        item = items.get(row)
        print(f"\nProcessing row {row}", flush=True)
        try:
            if item is None:
                raise ValueError("Row not found in schedule.")
            entry["description"] = item["description"]
            if not item["ready_for_rate_matching"]:
                entry.update(state="unpriced", reason=item["reason"])
                entries.append(entry)
                continue
            reused = path.exists()
            if not reused:
                if row in overrides:
                    raise ValueError("Explicit snapshot disappeared; refusing to substitute another estimate.")
                if args.offline:
                    raise ValueError("No saved estimate available in offline mode.")
                command = [sys.executable, str(root / "try_rate_matching.py"),
                           "--row", str(row), "--trade", args.trade, "--save", str(path)]
                if args.cross_trade:
                    command.append("--cross-trade")
                subprocess.run(command, check=True, timeout=300)
            if not path.exists():
                entry.update(state="unpriced", reason="No estimate saved; no candidates under the selected filter.")
            else:
                snapshot = checked_snapshot(path, item, args.trade, args.cross_trade)
                amount = recalculate(snapshot)
                entry.update(
                    state="priced" if amount is not None else "unpriced",
                    amount=amount, reused=reused,
                    recommendation=snapshot["recommendation"],
                    selected_rate=snapshot["selected_rate"],
                    quantity=item["quantity_resolved"], unit=item["unit"],
                    snapshot_sha256=content_hash(snapshot),
                    explicit_selection=row in overrides,
                    evidence_sha256=snapshot["context"].get("evidence_sha256"),
                    saved_rate_library_sha256=snapshot["context"]["rate_library_sha256"],
                    library_changed_since_selection=(snapshot["context"]["rate_library_sha256"] != library_hash),
                )
                print(f"Row {row}: {'reused' if reused else 'saved'}; amount={amount or 'UNPRICED'}", flush=True)
        except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
            entry["reason"] = str(error)
            print(f"Row {row}: FAILED — {error}", flush=True)
        entries.append(entry)

    # Detect edits during the batch before presenting a combined estimate.
    if sha256_file(source) != document["source_sha256"]:
        raise ValueError("Schedule changed during this batch; rerun against a stable source.")
    report = summarize(entries)
    report["source_sha256"] = document["source_sha256"]
    report["created_at"] = datetime.now(timezone.utc).isoformat()
    report["trade_for_this_batch"] = args.trade
    report["selection"] = {
        "default_version": args.version,
        "overrides": {str(row): str(path) for row, path in sorted(overrides.items())},
    }
    target = root / "outputs" / "batches" / f"batch-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid4().hex[:8]}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print("\nScope:", report["scope"])
    print("Priced / unpriced / failed:", report["priced_rows"], report["unpriced_rows"], report["failed_rows"])
    print("Indicative subtotal:", report["indicative_subtotal"] or "UNPRICED")
    print("Review status: Pending review")
    print("Report:", target)
    if report["failed_rows"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
