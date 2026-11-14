"""Offline, internal farm economics validator; no network, storage or prices."""
import csv, io
from decimal import Decimal, InvalidOperation
from datetime import date

FIELDS = ("enterprise_id","enterprise_type","period_start","period_end","currency","output_unit","production_quantity","sold_quantity","sales_revenue","other_revenue","variable_cost","fixed_cost","opportunity_cost")
NUMBERS = FIELDS[6:]

def validate_csv(text):
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)) or set(reader.fieldnames) != set(FIELDS):
        raise ValueError("invalid CSV header")
    result = []
    # A single enterprise cannot be aggregated twice across overlapping periods.
    periods_by_enterprise = {}
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
        enterprise_key = row["enterprise_id"].strip().casefold()
        previous_periods = periods_by_enterprise.setdefault(enterprise_key, [])
        for prior_start, prior_end in previous_periods:
            if start <= prior_end and prior_start <= end:
                if start == prior_start and end == prior_end:
                    raise ValueError(f"line {line}: duplicate enterprise-period")
                raise ValueError(f"line {line}: overlapping enterprise-period")
        previous_periods.append((start, end))
        try:
            values = {key: Decimal(row[key]) for key in NUMBERS}
        except InvalidOperation as exc:
            raise ValueError(f"line {line}: invalid decimal") from exc
        if any(not value.is_finite() or value < 0 for value in values.values()):
            raise ValueError(f"line {line}: negative or nonfinite value")
        if values["sold_quantity"] > values["production_quantity"]:
            raise ValueError(f"line {line}: sold exceeds produced; inventory reconciliation required")
        if values["sold_quantity"] == 0 and values["sales_revenue"] != 0:
            raise ValueError(f"line {line}: sales revenue without sold quantity")
        revenue = values["sales_revenue"] + values["other_revenue"]
        contribution = revenue - values["variable_cost"]
        operating = contribution - values["fixed_cost"]
        economic = operating - values["opportunity_cost"]
        # Period-level other revenue has no proven per-unit basis.
        # If some output remains unsold, the costs of sold units cannot be
        # isolated from this aggregate CSV. Do not invent a break-even.
        fully_sold = values["sold_quantity"] == values["production_quantity"] and values["sold_quantity"] > 0
        margin = ((values["sales_revenue"] - values["variable_cost"]) / values["sold_quantity"]
                  if fully_sold else None)
        break_even = values["fixed_cost"] / margin if margin is not None and margin > 0 else None
        result.append({"enterprise_id":row["enterprise_id"],"currency":row["currency"],"contribution":str(contribution),"operating_surplus":str(operating),"economic_profit":str(economic),"break_even_units":str(break_even) if break_even is not None else "NOT_ATTAINABLE"})
    if not result:
        raise ValueError("empty dataset")
    return result
