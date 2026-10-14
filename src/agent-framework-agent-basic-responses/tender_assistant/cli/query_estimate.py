"""Query saved results locally without Azure or a model call."""
import argparse
import json
from pathlib import Path

from tender_assistant.paths import SERVICE_ROOT
from tender_assistant.services.estimates import EstimateService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--response", type=Path, action="append", help="Trusted saved export; repeat for multiple tenders.")
    parser.add_argument("--tender-id")
    parser.add_argument("--row", type=int)
    args = parser.parse_args()
    if args.row is not None and not args.tender_id:
        parser.error("--row requires --tender-id")
    service = EstimateService(args.response or [SERVICE_ROOT / "outputs/api/hopuhopu-2027-rev-0a.json"])
    if args.row is not None:
        result = service.get_item_details(args.tender_id, args.row)
    elif args.tender_id:
        result = service.get_estimate(args.tender_id)
    else:
        result = service.list_tenders()
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
