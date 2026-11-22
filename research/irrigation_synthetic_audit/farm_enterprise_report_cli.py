"""Offline agricultural enterprise budget report CLI for authorized scenarios.

No public web endpoint, email, payment, deployment, storage or network access.
Only a user-provided, bounded local JSON file can feed these calculations.
"""
from __future__ import annotations

import argparse
from dataclasses import fields
import json
from pathlib import Path
import sys

from .farm_enterprise_budget import (
    FarmBudgetError, FarmScenario, budget, compare_scenarios,
)

MAX_FILE_BYTES = 32768
EXPECTED_KEYS = frozenset(field.name for field in fields(FarmScenario))


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise FarmBudgetError("duplicate JSON scenario field")
        result[key] = value
    return result


def read_scenario(path):
    """Parse a bounded, no-follow local JSON scenario; all numeric inputs explicit."""
    item = Path(path)
    if item.is_symlink() or not item.is_file():
        raise FarmBudgetError("input must be a regular non-symlink file")
    if item.stat().st_size > MAX_FILE_BYTES:
        raise FarmBudgetError("scenario input exceeds the local safety ceiling")
    raw = item.read_bytes()
    if not raw or len(raw) > MAX_FILE_BYTES:
        raise FarmBudgetError("empty or oversized scenario input")
    try:
        obj = json.loads(
            raw.decode("utf-8"),
            parse_float=str, parse_int=str,
            parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite number")),
            object_pairs_hook=_unique_object,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise FarmBudgetError("invalid scenario JSON structure") from exc
    if type(obj) is not dict or frozenset(obj) != EXPECTED_KEYS:
        raise FarmBudgetError("missing or unknown scenario fields")
    return FarmScenario(**obj)


def build_report(baseline_path, alternative_path=None):
    baseline = read_scenario(baseline_path)
    result = {
        "schema": "zomorod.farm-education-cli.v1",
        "publication_allowed": False,
        "payment_collected": False,
        "source_inputs_verified": False,
        "baseline": budget(baseline),
    }
    if alternative_path is not None:
        alternative = read_scenario(alternative_path)
        result["alternative"] = budget(alternative)
        result["comparison"] = compare_scenarios(baseline, alternative)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline educational farm budget; no field performance claims."
    )
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--alternative")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.baseline, args.alternative)
    except (FarmBudgetError, OSError) as exc:
        # Public logs should not leak arbitrary source paths, names or data.
        print(json.dumps({"ok": False, "error": "scenario_preflight_failed",
                          "error_type": type(exc).__name__}), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
