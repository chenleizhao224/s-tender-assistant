"""Export a saved pricing batch using the Tender Assistant API contract."""

import argparse
import json
from pathlib import Path

from tender_assistant.api import build_tender_response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("batch", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tender-id", required=True)
    parser.add_argument("--tender-name", required=True)
    parser.add_argument("--schedule-revision", required=True)
    parser.add_argument("--currency", default="NZD")
    args = parser.parse_args()

    with args.batch.open(encoding="utf-8") as stream:
        batch = json.load(stream)
    response = build_tender_response(
        batch,
        tender_id=args.tender_id,
        tender_name=args.tender_name,
        schedule_revision=args.schedule_revision,
        currency=args.currency,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(response, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print("API response saved:", args.output.resolve())


if __name__ == "__main__":
    main()
