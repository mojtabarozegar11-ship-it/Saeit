"""Offline CLI for validated agricultural economics CSV; no network or file writes."""
import argparse
import json
import sys
from pathlib import Path

from farm_economics_validator import validate_csv


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate farm economics CSV and print JSON to stdout")
    parser.add_argument("csv_file", help="Path to a local UTF-8 CSV input file")
    args = parser.parse_args(argv)
    try:
        source = Path(args.csv_file).read_text(encoding="utf-8-sig")
        results = validate_csv(source)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Input rejected: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"schema_version": 1, "records": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
