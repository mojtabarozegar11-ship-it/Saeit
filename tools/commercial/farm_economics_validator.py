"""Offline, internal farm economics validator; no network, storage or prices."""
import csv, io
from decimal import Decimal, InvalidOperation, DecimalException, getcontext
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
    dimensions_by_enterprise = {}
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
        if not enterprise_key or not row["enterprise_type"].strip() or not row["output_unit"].strip():
            raise ValueError(f"line {line}: empty enterprise identifier/type/unit")
        dimensions = (row["currency"], row["enterprise_type"].strip().casefold(), row["output_unit"].strip().casefold())
        previous_dimensions = dimensions_by_enterprise.setdefault(enterprise_key, dimensions)
        if dimensions != previous_dimensions:
            raise ValueError(f"line {line}: inconsistent enterprise currency/type/output unit across periods")
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
        # Reject exponents the active Decimal arithmetic context cannot represent,
        # including enormous quantities that would bypass money-only arithmetic.
        decimal_context = getcontext()
        if any(value and not (decimal_context.Emin <= value.adjusted() <= decimal_context.Emax)
               for value in values.values()):
            raise ValueError(f"line {line}: numeric magnitude/precision exceeds supported arithmetic")
        if values["sold_quantity"] > values["production_quantity"]:
            raise ValueError(f"line {line}: sold exceeds produced; inventory reconciliation required")
        if values["sold_quantity"] == 0 and values["sales_revenue"] != 0:
            raise ValueError(f"line {line}: sales revenue without sold quantity")
        try:
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
            # Unlike the operating threshold above, economic break-even also
            # recovers the disclosed opportunity cost; exclude unmatched other revenue.
            economic_break_even = ((values["fixed_cost"] + values["opportunity_cost"]) / margin
                                   if margin is not None and margin > 0 else None)
        except DecimalException as exc:
            raise ValueError(f"line {line}: numeric magnitude/precision exceeds supported arithmetic") from exc
        # Break-even may be mathematically defined yet exceed reported production.
        if break_even is None:
            break_even_feasibility = "NOT_CALCULABLE"
        elif break_even > values["production_quantity"]:
            break_even_feasibility = "EXCEEDS_REPORTED_PRODUCTION"
        else:
            break_even_feasibility = "WITHIN_REPORTED_PRODUCTION"
        # Keep the evidence dimensions and cost basis with each calculated result;
        # otherwise a downstream report cannot be tied to its source enterprise/period.
        unsold = values["production_quantity"] - values["sold_quantity"]
        result.append({
            "enterprise_id": row["enterprise_id"].strip(),
            "enterprise_type": row["enterprise_type"].strip(),
            "period_start": start.isoformat(), "period_end": end.isoformat(),
            "currency": row["currency"], "output_unit": row["output_unit"].strip(),
            "production_quantity": str(values["production_quantity"]),
            "sold_quantity": str(values["sold_quantity"]),
            "unsold_quantity": str(unsold),
            "inventory_cost_allocation": "REQUIRES_RECONCILIATION" if unsold > 0 else "NO_UNSOLD_OUTPUT",
            "sales_revenue": str(values["sales_revenue"]), "other_revenue": str(values["other_revenue"]),
            "variable_cost": str(values["variable_cost"]),
            "fixed_cost": str(values["fixed_cost"]),
            "opportunity_cost": str(values["opportunity_cost"]),
            "reported_profit_basis": "PERIOD_RECEIPTS_LESS_TOTAL_RECORDED_COSTS",
            "contribution": str(contribution), "operating_surplus": str(operating),
            "economic_profit": str(economic),
            "break_even_units": str(break_even) if break_even is not None else "NOT_ATTAINABLE",
            "break_even_feasibility": break_even_feasibility,
            "break_even_basis": "OPERATING_FIXED_COST_ONLY_EXCLUDES_OTHER_REVENUE",
            "economic_break_even_units": (str(economic_break_even) if economic_break_even is not None
                                           else "NOT_ATTAINABLE"),
            "economic_break_even_feasibility": (
                "NOT_CALCULABLE" if economic_break_even is None else
                "EXCEEDS_REPORTED_PRODUCTION" if economic_break_even > values["production_quantity"] else
                "WITHIN_REPORTED_PRODUCTION"),
            "economic_break_even_basis": "FIXED_AND_OPPORTUNITY_COST_EXCLUDES_OTHER_REVENUE",
        })
    if not result:
        raise ValueError("empty dataset")
    return result
