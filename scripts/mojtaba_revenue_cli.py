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
from mojtaba_revenue_safeio import read_json, create_private_json

MAX_BYTES = 32768


def load_bounded_json(file_path: Path) -> dict:
    return read_json(file_path, limit=MAX_BYTES)


def output_private(target: Path, result: dict, input_path: Path) -> None:
    create_private_json(target, result, input_path=input_path)

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
    parser.add_argument("--output", type=Path, help="create a NEW private 0600 JSON file")
    args = parser.parse_args(argv)
    try:
        if args.catalog:
            result = catalog()
            if args.output:
                raise ValueError("CATALOG_FILE_EXPORT_DISABLED")
        elif args.qualify:
            result = evaluate(load_bounded_json(args.qualify))
        else:
            result = synthetic_kpis(load_bounded_json(args.synthetic_kpis))
        if args.output:
            output_private(args.output, result, args.qualify or args.synthetic_kpis)
        else:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (ValueError, OSError, PermissionError) as exc:
        # Do not reveal sensitive file paths, JSON content, or external tokens.
        print("MOJTABA_REVENUE_CLI=blocked_invalid_or_unsafe_input", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
