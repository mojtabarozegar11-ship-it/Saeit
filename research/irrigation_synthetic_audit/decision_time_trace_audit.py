"""Fail-closed, dependency-free ex-ante information audit for synthetic R01.

This checks trace structure and timestamps only. It cannot prove that the
provided timestamps, rainfall, or controller implementation are authentic.
No production controller, payment, or field measurement is involved.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re

class TraceError(ValueError):
    pass

KEYS = ("scenario_id", "path_id", "policy", "decision_at",
        "forecast_issued_at", "forecast_valid_at", "rainfall_observed_at",
        "forecast_rain_mm", "realized_rain_mm", "rainfall_input_kind")
IDENT = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
NUM = re.compile(r"(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,6})?\Z")
KINDS = {"issued_forecast", "realized_observation"}


def _instant(value, label):
    if type(value) is not str or not value.endswith("Z"):
        raise TraceError(label + ": UTC Z timestamp required")
    try:
        instant = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise TraceError(label + ": invalid timestamp") from exc
    if instant.utcoffset().total_seconds() != 0:
        raise TraceError(label + ": UTC required")
    return instant


def _mm(value, label):
    if type(value) is not str or NUM.fullmatch(value) is None:
        raise TraceError(label + ": nonnegative canonical decimal mm required")
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise TraceError(label + ": invalid decimal") from exc


def audit_trace(records):
    """Require comparable information and reject future-observation leakage.

    Every policy in a matched scenario must use the same decision instant,
    forecast issue/valid instant and forecast amount. This conservative rule
    rejects incomparable information sets rather than imputing missing values.
    """
    if type(records) is not list or not records or len(records) > 100000:
        raise TraceError("nonempty bounded records list required")
    seen = set()
    groups = {}
    for index, row in enumerate(records):
        if type(row) is not dict or set(row) != set(KEYS):
            raise TraceError(f"row {index}: exact trace schema required")
        for key in ("scenario_id", "path_id", "policy"):
            if type(row[key]) is not str or IDENT.fullmatch(row[key]) is None:
                raise TraceError(f"row {index}: invalid {key}")
        key = (row["scenario_id"], row["path_id"], row["policy"])
        if key in seen:
            raise TraceError("duplicate matched policy trace")
        seen.add(key)
        decision = _instant(row["decision_at"], "decision_at")
        issued = _instant(row["forecast_issued_at"], "forecast_issued_at")
        valid = _instant(row["forecast_valid_at"], "forecast_valid_at")
        observed = _instant(row["rainfall_observed_at"], "rainfall_observed_at")
        if issued > decision:
            raise TraceError("forecast issued after decision")
        if valid < issued:
            raise TraceError("forecast valid before issue")
        if row["rainfall_input_kind"] not in KINDS:
            raise TraceError("unknown rainfall information source")
        forecast = _mm(row["forecast_rain_mm"], "forecast_rain_mm")
        _mm(row["realized_rain_mm"], "realized_rain_mm")
        if row["rainfall_input_kind"] == "realized_observation" and observed > decision:
            raise TraceError("future realized rainfall leaked into decision")
        group = (row["scenario_id"], row["path_id"])
        signature = (decision, issued, valid, forecast, row["rainfall_input_kind"])
        if group in groups and groups[group] != signature:
            raise TraceError("policies lack equal ex-ante information")
        groups[group] = signature
    return {
        "schema": "r01.ex-ante-trace-structure.v1",
        "synthetic_only": True,
        "source_timestamps_authenticated": False,
        "controller_code_verified": False,
        "field_efficacy_verified": False,
        "rows_checked": len(records),
        "matched_scenario_paths": len(groups),
        "structural_checks_passed": True,
    }
