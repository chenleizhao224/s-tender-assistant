"""Export a saved pricing batch using the Tender Assistant API contract."""

import argparse
from pathlib import Path

from tender_assistant.services.estimates import export_estimate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("batch", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tender-id", required=True)
    parser.add_argument("--tender-name", required=True)
    parser.add_argument("--schedule-revision", required=True)
    parser.add_argument("--currency", default="NZD")
    args = parser.parse_args()

    export_estimate(
        args.batch, args.output,
        tender_id=args.tender_id,
        tender_name=args.tender_name,
        schedule_revision=args.schedule_revision,
        currency=args.currency,
    )
    print("API response saved:", args.output.resolve())


if __name__ == "__main__":
    main()
