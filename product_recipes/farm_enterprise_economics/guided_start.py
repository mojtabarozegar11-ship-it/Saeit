#!/usr/bin/env python3
"""Private, offline, guided data entry for the farm enterprise calculator.

No demo figures, network traffic, subprocesses, external dependencies, or
automatic commercial publication. A fresh output directory prevents accidental
replacement of a customer's older budget.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile

from calculator import decimal_number, evaluate, main as calculate_reports


INPUTS = (
    ("units_sold", "Units sold in the selected period", "0"),
    ("unit_price", "Received price per sold unit", "0"),
    ("variable_cost_per_unit", "Variable cost per unit sold", "0"),
    ("allocated_fixed_cost", "Allocated fixed costs for the period", "0"),
    ("selling_fee_percent", "Sales fee percentage (5 means 5%)", "0", "100"),
)
REPORT_FILES = (
    "my_farm.json", "results.json", "scenarios.csv",
    "joint-stress.csv", "management-report.html",
)
RECEIPT_FILE = "integrity-manifest.json"


class Cancelled(Exception):
    """The customer quit before creating a report."""


def prompt(message, *, read=input, write=print):
    try:
        value = read(message + ": ")
    except (EOFError, KeyboardInterrupt):
        raise Cancelled()
    if not isinstance(value, str):
        raise Cancelled()
    return value.strip()


def ask_currency(*, read=input, write=print):
    while True:
        value = prompt("Currency (e.g. USD, CAD, IRR)", read=read, write=write).upper()
        if (1 <= len(value) <= 12 and value.isascii()
                and re.fullmatch(r"[A-Z0-9_]+", value)
                and value.replace("_", "").isalnum()):
            return value
        write("Use 1–12 ASCII letters, digits or underscores; no currency sign.")


def ask_count(*, read=input, write=print):
    while True:
        raw = prompt("How many different farm enterprises? (1–100)", read=read, write=write)
        if raw.isascii() and raw.isdecimal() and 1 <= len(raw) <= 3:
            number = int(raw)
            if 1 <= number <= 100:
                return number
        write("Enter a whole number between 1 and 100.")


def ask_name(number, existing, *, read=input, write=print):
    while True:
        value = prompt("Enterprise {} name".format(number), read=read, write=write)
        if not value or len(value) > 120 or not value[0].isalnum() or any(
            ord(c) < 32 or ord(c) == 127 for c in value
        ):
            write("Use 1–120 characters, begin with a letter or digit, and no control characters.")
        elif value.casefold() in existing:
            write("Each enterprise must have a distinct name.")
        else:
            existing.add(value.casefold())
            return value


def ask_number(key, label, minimum, maximum=None, *, read=input, write=print):
    while True:
        raw = prompt(label + " (use a dot for decimals)", read=read, write=write)
        try:
            decimal_number(raw, key, min_value=minimum, max_value=maximum)
        except ValueError as error:
            write("Please correct this number: " + str(error))
        else:
            return raw


def collect_budget(*, read=input, write=print):
    write("Farm Enterprise Economics — guided offline budget")
    write("Have your period, selling units, prices and costs ready. No example amounts are inserted.")
    currency = ask_currency(read=read, write=write)
    count = ask_count(read=read, write=write)
    names = set()
    rows = []
    for number in range(1, count + 1):
        write("\nEnterprise {} of {}".format(number, count))
        entry = {"name": ask_name(number, names, read=read, write=write)}
        for field in INPUTS:
            key, label, minimum, *maximum = field
            entry[key] = ask_number(
                key, label, minimum, maximum[0] if maximum else None,
                read=read, write=write,
            )
        rows.append(entry)
    result = {"currency": currency, "enterprises": rows}
    # The production calculation engine is the authority for accepted inputs;
    # the wizard never reproduces financial formulas in a second code path.
    evaluate(result)
    return result


def create_private_reports(data, output_parent, *, report_runner=calculate_reports):
    """Create all exports in a new directory and write the completion receipt last."""
    candidate = Path(output_parent).expanduser()
    if candidate.is_symlink():
        raise ValueError("output parent must not be a symlink")
    parent = candidate.resolve()
    if not parent.is_dir():
        raise ValueError("output parent must be an existing ordinary directory")
    if not isinstance(data, dict) or not data.get("enterprises"):
        raise ValueError("budget input is incomplete")
    evaluate(data)
    result_dir = Path(tempfile.mkdtemp(prefix="farm-budget-", dir=str(parent)))
    source = result_dir / "my_farm.json"
    with source.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    paths = {
        "json": result_dir / "results.json",
        "csv": result_dir / "scenarios.csv",
        "stress": result_dir / "joint-stress.csv",
        "html": result_dir / "management-report.html",
    }
    code = report_runner([
        str(source), "--json-output", str(paths["json"]),
        "--csv-output", str(paths["csv"]),
        "--three-factor-csv-output", str(paths["stress"]),
        "--html-output", str(paths["html"]),
    ])
    if code != 0 or not all(path.is_file() and path.stat().st_size for path in paths.values()):
        raise RuntimeError("not all report files were created in " + str(result_dir))
    if any((result_dir / filename).is_symlink() for filename in REPORT_FILES):
        raise RuntimeError("report file is a symlink in " + str(result_dir))
    # An exit code and non-empty files alone do not prove the saved calculation
    # is the one obtained from the accepted customer input.
    actual = json.loads(paths["json"].read_text(encoding="utf-8"))
    if actual != evaluate(data):
        raise RuntimeError("saved results do not match the customer input in " + str(result_dir))
    receipt = {
        "schema": "saeit.f01.customer-offline-integrity.v1",
        "product_id": "farm_enterprise_economics",
        "files_sha256": {
            filename: hashlib.sha256((result_dir / filename).read_bytes()).hexdigest()
            for filename in REPORT_FILES
        },
        "independently_certified_quality_score": None,
        "commercial_release_allowed": False,
    }
    (result_dir / RECEIPT_FILE).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result_dir


def verify_private_reports(folder):
    """Read-only corruption/completeness check; not a signature or quality grade."""
    candidate = Path(folder).expanduser()
    if candidate.is_symlink() or not candidate.is_dir():
        raise ValueError("report folder is missing or a symlink")
    receipt_path = candidate / RECEIPT_FILE
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise ValueError("integrity manifest missing: report folder may be incomplete")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (not isinstance(receipt, dict)
            or receipt.get("schema") != "saeit.f01.customer-offline-integrity.v1"
            or receipt.get("product_id") != "farm_enterprise_economics"
            or receipt.get("independently_certified_quality_score", "invalid") is not None
            or receipt.get("commercial_release_allowed") is not False
            or not isinstance(receipt.get("files_sha256"), dict)
            or set(receipt["files_sha256"]) != set(REPORT_FILES)):
        raise ValueError("integrity manifest is invalid")
    for filename in REPORT_FILES:
        path = candidate / filename
        if path.is_symlink() or not path.is_file() or not path.stat().st_size:
            raise ValueError("report file is missing or unsafe: " + filename)
        expected = receipt["files_sha256"][filename]
        if (not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected)
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected):
            raise ValueError("report file checksum mismatch: " + filename)
    data = json.loads((candidate / "my_farm.json").read_text(encoding="utf-8"))
    saved = json.loads((candidate / "results.json").read_text(encoding="utf-8"))
    if saved != evaluate(data):
        raise ValueError("saved financial results do not match the original input")
    return len(REPORT_FILES)


def main(argv=None, *, read=input, write=print):
    parser = argparse.ArgumentParser(
        description="Private question-by-question entry for the offline farm budget"
    )
    parser.add_argument(
        "--output-parent", default=".",
        help="Existing writable folder for a fresh report directory (default: current folder)",
    )
    parser.add_argument(
        "--verify-folder", help="Read-only completeness and checksum check of a previously saved report folder",
    )
    args = parser.parse_args(argv)
    try:
        if args.verify_folder:
            count = verify_private_reports(args.verify_folder)
            write("VERIFIED: {} saved files match the integrity manifest and accepted inputs.".format(count))
            write("This detects accidental changes; it is not independent certification or a signature.")
            return 0
        data = collect_budget(read=read, write=write)
        preview = evaluate(data)["portfolio"]
        write("\nReview: {} enterprises in {}.".format(len(data["enterprises"]), data["currency"]))
        write("Modeled operating profit, BEFORE taxes/financing/depreciation: " +
              preview["operating_profit"])
        confirmation = prompt("Create private reports in a NEW folder? Type YES to proceed", read=read, write=write)
        if confirmation != "YES":
            write("Cancelled; no report folder created.")
            return 0
        folder = create_private_reports(data, args.output_parent)
        write("Reports saved: " + str(folder))
        write("Open management-report.html locally. Keep your original inputs and a backup.")
        write("To verify later: python guided_start.py --verify-folder \"{}\"".format(folder))
        write("These are scenarios, not forecasts, certified quality scores or a released product.")
        return 0
    except Cancelled:
        write("Cancelled; no report folder created.")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print("INPUT_ERROR: " + str(error), file=sys.stderr)
        sys.exit(2)
