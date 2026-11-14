"""Offline, internal farm economics validator; no network, storage or prices."""
import csv, io
from decimal import Decimal, InvalidOperation
from datetime import date

FIELDS = ("enterprise_id","enterprise_type","period_start","period_end","currency","output_unit","production_quantity","sold_quantity","sales_revenue","other_revenue","variable_cost","fixed_cost","opportunity_cost")
NUMBERS = FIELDS[6:]

def validate_csv(text):
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)) or set(reader.fieldnames) != set(FIELDS):
        raise ValueError("invalid CSV header")
    result = []
    seen_enterprise_periods = set()
    for line, row in enumerate(reader, 2):
        if None in row or any(value is None or not value.strip() for value in row.values()):
            raise ValueError(f"line {line}: incomplete/extra field")
        try:
            start, end = date.fromisoformat(row["period_start"]), date.fromisoformat(row["period_end"])
        except ValueError as exc:
            raise ValueError(f"line {line}: invalid period") from exc
        if end < start:
            raise ValueError(f"line {line}: reversed period")
        if not (len(row["currency"]) == 3 and row["currency"].isascii() and row["currency"].isalpha() and row["currency"].isupper()):
            raise ValueError(f"line {line}: invalid currency")
        if any(row[key].lstrip().startswith(("=","+","-","@")) for key in ("enterprise_id","enterprise_type","output_unit")):
            raise ValueError(f"line {line}: unsafe label")
        try:
            values = {key: Decimal(row[key]) for key in NUMBERS}
        except InvalidOperation as exc:
            raise ValueError(f"line {line}: invalid decimal") from exc
        if any(not value.is_finite() or value < 0 for value in values.values()):
            raise ValueError(f"line {line}: negative or nonfinite value")
        if values["sold_quantity"] > values["production_quantity"]:
            raise ValueError(f"line {line}: sold exceeds produced; inventory reconciliation required")
        # A dataset row covers one enterprise/type/unit/currency/reporting period.
        # Repeated periods can silently double-count income and costs downstream.
        # Keep different enterprise types, units, currencies or periods independent.
        report_key = (
            row["enterprise_id"].strip(), row["enterprise_type"].strip(),
            start, end, row["currency"], row["output_unit"].strip(),
        )
        if report_key in seen_enterprise_periods:
            raise ValueError(f"line {line}: duplicate enterprise reporting period")
        seen_enterprise_periods.add(report_key)
        revenue = values["sales_revenue"] + values["other_revenue"]
        contribution = revenue - values["variable_cost"]
        operating = contribution - values["fixed_cost"]
        economic = operating - values["opportunity_cost"]
        margin = (values["sales_revenue"] - values["variable_cost"]) / values["sold_quantity"] if values["sold_quantity"] else None
        break_even = values["fixed_cost"] / margin if margin is not None and margin > 0 else None
        result.append({"enterprise_id":row["enterprise_id"],"currency":row["currency"],"contribution":str(contribution),"operating_surplus":str(operating),"economic_profit":str(economic),"break_even_units":str(break_even) if break_even is not None else "NOT_ATTAINABLE"})
    if not result:
        raise ValueError("empty dataset")
    return result
