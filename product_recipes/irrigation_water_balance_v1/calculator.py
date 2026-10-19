"""Offline irrigation accounting: FAO56 ETc = Kc * ETo; no field prescription."""
import argparse
import json
from decimal import Decimal, InvalidOperation


def number(value, name, low, high, open_low=False):
    try:
        n = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(name + ": invalid decimal") from error
    if not n.is_finite() or n < low or (open_low and n == low) or n > high:
        raise ValueError(name + ": out of range")
    return n


def calculate(eto, kc, rain, soil_credit, efficiency, days, hectares):
    eto = number(eto, "ETo", Decimal(0), Decimal(50))
    kc = number(kc, "Kc", Decimal(0), Decimal(3))
    rain = number(rain, "effective rain", Decimal(0), Decimal(500))
    soil_credit = number(soil_credit, "soil credit", Decimal(0), Decimal(1000))
    efficiency = number(efficiency, "efficiency", Decimal(0), Decimal(1), True)
    hectares = number(hectares, "hectares", Decimal(0), Decimal(1000000), True)
    if type(days) is not int or not 1 <= days <= 365:
        raise ValueError("days: out of range")
    crop_et = eto * kc * days
    net = max(Decimal(0), crop_et - rain * days - soil_credit)
    gross = net / efficiency
    return {"version": "1.0.0", "crop_et_mm": str(crop_et),
            "net_irrigation_mm": str(net), "gross_irrigation_mm": str(gross),
            "gross_volume_m3": str(gross * hectares * 10),
            "note": "Scenario only; measured inputs and independent field review required."}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for name in ("eto", "kc", "rain", "efficiency", "hectares"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--soil-credit", default="0")
    p.add_argument("--days", type=int, required=True)
    a = p.parse_args()
    try:
        print(json.dumps(calculate(a.eto, a.kc, a.rain, a.soil_credit,
                                   a.efficiency, a.days, a.hectares), indent=2))
    except ValueError as e:
        p.error(str(e))
