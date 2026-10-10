"""Resumable schedule-only trade classification, never pricing or approval."""
import argparse
from pathlib import Path
import subprocess
import sys

from tender_assistant.documents.inventory import sha256_file
from tender_assistant.schedules.extraction import extract_schedule
from tender_assistant.schedules.preparation import prepare_schedule
from tender_assistant.schedules.trades import (
    INSTRUCTIONS, TRADES, build_request, load_classification, save_classification,
)
from tender_assistant.pricing.snapshot import content_hash


def merge_saved(request, paths):
    """Reject stale or overlapping saved decisions instead of silently selecting one."""
    expected = {entry['item_id']: entry for entry in request['items']}
    decisions, models = {}, set()
    for path in paths:
        payload = load_classification(path)
        old = payload['request']
        if (old['schedule_sources'] != request['schedule_sources']
                or old['evidence'] != request['evidence']
                or payload['prompt_sha256'] != content_hash(INSTRUCTIONS)):
            raise ValueError(f'Saved context or prompt differs: {path}')
        for entry in old['items']:
            if expected.get(entry['item_id']) != entry:
                raise ValueError(f'Saved source item differs: {path}')
        for decision in payload['result']['decisions']:
            key = decision['item_id']
            if key in decisions:
                raise ValueError(f'Duplicate saved classification: {key}')
            decisions[key] = decision
        models.add(payload['model'])
    return decisions, models


def pending_batches(request, decisions, size):
    if not 1 <= size <= 30:
        raise ValueError('Batch size must be between 1 and 30.')
    rows = [entry['item']['excel_row'] for entry in request['items']
            if entry['item_id'] not in decisions]
    return [rows[index:index+size] for index in range(0, len(rows), size)]


def show_summary(request, decisions):
    print('Classified work items:', len(decisions), '/', len(request['items']))
    for trade in TRADES:
        matching = [entry for entry in request['items']
                    if decisions.get(entry['item_id'], {}).get('trade') == trade]
        ready = sum(entry['item']['ready_for_rate_matching'] for entry in matching)
        print(f'{trade}: {len(matching)} classified; {ready} quantity-ready (not priced)')
    review = [decisions[entry['item_id']] for entry in request['items']
              if decisions.get(entry['item_id'], {}).get('status') == 'requires_review']
    print('Requires review:', len(review))
    for decision in review:
        print(decision['item_id'], decision['reason'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schedule', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--reuse', type=Path, action='append', default=[])
    parser.add_argument('--batch-size', type=int, default=25)
    parser.add_argument('--run', action='store_true', help='Call the model only for unsaved rows.')
    args = parser.parse_args()
    document = extract_schedule(args.schedule)
    items = prepare_schedule(document)
    request = build_request(items)
    # Fixed complete-scope fingerprint binds this run directory to the input and prompt.
    run_id = content_hash({'request': request, 'prompt': INSTRUCTIONS})[:16]
    directory = args.output_dir / run_id
    parts = sorted(directory.glob('part-*.json'))
    paths = args.reuse + parts
    decisions, models = merge_saved(request, paths)
    batches = pending_batches(request, decisions, args.batch_size)
    print('Retained rows:', len(items), '; context-only:', len(items)-len(request['items']), flush=True)
    print('Reused:', len(decisions), '; pending:', sum(map(len, batches)), '; model calls:', len(batches), flush=True)
    if batches and not args.run:
        print('Preview only; add --run to classify the pending batches.')
        return
    for rows in batches:
        target = directory / f'part-{content_hash(rows)[:16]}.json'
        print('Classifying rows:', rows, flush=True)
        subprocess.run([sys.executable, '-m', 'tender_assistant.cli.classify_trades',
                        '--schedule', str(args.schedule.resolve()), '--rows', *map(str, rows),
                        '--run', '--output', str(target.resolve())], check=True, timeout=300)
        paths.append(target)
    if sha256_file(args.schedule) != document['source_sha256']:
        raise ValueError('Schedule changed during classification; do not merge these results.')
    decisions, models = merge_saved(request, paths)
    if len(decisions) != len(request['items']):
        raise ValueError('Incomplete classification.')
    result = {'decisions': [decisions[entry['item_id']] for entry in request['items']]}
    combined = directory / 'combined.json'
    if combined.exists():
        saved = load_classification(combined)
        if saved['request'] != request or saved['result'] != result:
            raise ValueError('Existing combined result differs; use a new output directory.')
    else:
        save_classification(combined, request, result, ', '.join(sorted(models)))
    show_summary(request, decisions)
    print('Saved combined classification:', combined)
    print('Pending human review; no prices calculated; external documents not attached.')


if __name__ == '__main__':
    main()
