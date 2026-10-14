"""Small explicit row batches; reuse saved estimates and report coverage."""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from tender_assistant.paths import SERVICE_ROOT
from tender_assistant.pricing.snapshot import content_hash, load_snapshot, recalculate
from tender_assistant.pricing.summary import summarize
from tender_assistant.pricing.recommendations import validate_result


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
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--trade")
    selection.add_argument("--classification", type=Path)
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
    from tender_assistant.documents.inventory import sha256_file
    from tender_assistant.schedules.extraction import extract_schedule
    from tender_assistant.schedules.preparation import prepare_schedule

    root = SERVICE_ROOT
    load_dotenv(root / ".env")
    source = Path(os.environ["TENDER_INPUT_DIR"]) / "NTT 02" / "20260707 - Hopuhopu Development - Schedule of Prices [0A].xlsx"
    document = extract_schedule(source)
    items = {item["excel_row"]: item for item in prepare_schedule(document)}
    classification = None
    if args.classification:
        from tender_assistant.schedules.trades import load_classification
        classification = load_classification(args.classification)
        saved_items = {x['item']['excel_row']: x['item'] for x in classification['request']['items']}
        if any(items.get(row) != item for row, item in saved_items.items()):
            raise ValueError('Classification and current schedule differ.')
        decisions = {int(d['item_id'][1:]): d for d in classification['result']['decisions']}
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
            trade = args.trade
            if classification:
                decision = decisions.get(row)
                if decision is None:
                    raise ValueError('Row missing from classification.')
                trade = decision['trade']
                entry['classification'] = decision
            entry.update(allocated_trade=trade or 'Requires review', code=item['code'],
                         quantity=item['quantity_resolved'], unit=item['unit'])
            if not trade:
                entry.update(state='unpriced', reason=decision['reason'])
                entries.append(entry)
                continue
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
                command = [sys.executable, "-m", "tender_assistant.cli.match_rates",
                           "--row", str(row), "--save", str(path)]
                command += ['--classification', str(args.classification.resolve())] if classification else ['--trade', trade]
                if args.cross_trade:
                    command.append("--cross-trade")
                subprocess.run(command, check=True, timeout=300, cwd=root)
            if not path.exists():
                entry.update(state="unpriced", reason="No estimate saved; no candidates under the selected filter.")
            else:
                snapshot = checked_snapshot(path, item, trade, args.cross_trade)
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
    if classification:
        report['classification_coverage'] = {
            'fingerprint': content_hash(classification),
            'decisions': classification['result']['decisions'],
            'work_item_count': len(classification['request']['items']),
        }
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
