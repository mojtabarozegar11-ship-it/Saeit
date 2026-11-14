#!/usr/bin/env python3
"""Manual offline adapter for the ONLY Mojtaba.bot.ai commercial policy.

No network, no lead submission, no payment, no invoice, no broker calls.
Only synthetic sample metrics and PII-free structured metadata are accepted.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys

from mojtaba_revenue_portfolio import (CANONICAL_BOT, OFFERS, evaluate,
                                        synthetic_kpis)
from mojtaba_revenue_margin import estimate as estimate_synthetic_margin
from mojtaba_farm_break_even import model as farm_model

MAX_BYTES = 32768


def load_bounded_json(file_path: Path) -> dict:
    if file_path.is_symlink() or not file_path.is_file():
        raise ValueError("INPUT_NOT_A_REGULAR_FILE")
    st = file_path.stat()
    if not 0 < st.st_size <= MAX_BYTES:
        raise ValueError("INPUT_SIZE_NOT_ALLOWED")
    raw = file_path.read_bytes()
    if len(raw) != st.st_size:
        raise ValueError("INPUT_CHANGED_DURING_READ")
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("INPUT_JSON_INVALID") from exc
    if type(obj) is not dict:
        raise ValueError("INPUT_MUST_BE_OBJECT")
    return obj


def output_private(target: Path, result: dict, input_path: Path) -> None:
    if target.is_symlink() or target.resolve() == input_path.resolve():
        raise ValueError("OUTPUT_PATH_REJECTED")
    if not target.parent.is_dir() or target.parent.is_symlink():
        raise ValueError("OUTPUT_DIRECTORY_INVALID")
    text = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    # Exclusive creation avoids overwrites, including race-created symlinks.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(target, flags, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)


def catalog() -> dict:
    return {
        "schema": "mojtaba.bot.ai.revenue-catalog.v1",
        "canonical_bot": CANONICAL_BOT,
        "offers": [
            {"offer_id": offer.code, "domain": offer.domain,
             "source": offer.source, "proof": offer.proof,
             "commercial_mode": offer.commercial_mode}
            for offer in OFFERS.values()
        ],
        "deployed": False,
        "actual_orders": None,
        "actual_revenue": None,
        "no_other_bot_created": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    cmd = parser.add_mutually_exclusive_group(required=True)
    cmd.add_argument("--catalog", action="store_true", help="show source-only catalog")
    cmd.add_argument("--qualify", type=Path, help="PII-free local intake metadata")
    cmd.add_argument("--synthetic-kpis", type=Path, help="synthetic counts only")
    cmd.add_argument("--synthetic-margin", type=Path, help="synthetic currency-safe cost model; NEVER a quote")
    cmd.add_argument("--farm-analysis", type=Path, help="farm break-even and 27 sensitivities on aggregate numbers; not a quote")
    parser.add_argument("--output", type=Path, help="create a NEW private 0600 JSON file")
    args = parser.parse_args(argv)
    try:
        if args.catalog:
            result = catalog()
            if args.output:
                raise ValueError("CATALOG_FILE_EXPORT_DISABLED")
        elif args.qualify:
            result = evaluate(load_bounded_json(args.qualify))
        elif args.synthetic_margin:
            result = estimate_synthetic_margin(load_bounded_json(args.synthetic_margin))
        elif args.farm_analysis:
            result = farm_model(load_bounded_json(args.farm_analysis))
        else:
            result = synthetic_kpis(load_bounded_json(args.synthetic_kpis))
        if args.output:
            output_private(args.output, result, args.qualify or args.synthetic_margin or args.farm_analysis or args.synthetic_kpis)
        else:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (ValueError, OSError, PermissionError) as exc:
        # Do not reveal sensitive file paths, JSON content, or external tokens.
        print("MOJTABA_REVENUE_CLI=blocked_invalid_or_unsafe_input", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
