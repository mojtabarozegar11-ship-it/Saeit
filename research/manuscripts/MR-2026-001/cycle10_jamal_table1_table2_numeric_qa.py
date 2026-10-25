#!/usr/bin/env python3
"""Reproduce selected Jamal et al. (2023) Table 1/2 arithmetic.
Source: https://doi.org/10.1029/2023WR035810
CAUTION: optimized and workshop schedules are simulated/counterfactual, NOT
field-observed water savings attributable to DSS use.
"""
from decimal import Decimal

def D(value):
    return Decimal(str(value))

def percent_change_from_recorded(recorded, hypothetical):
    return (D(recorded) - D(hypothetical)) / D(recorded) * D(100)

def check(label, got, expected):
    assert abs(got - D(expected)) < D("0.000001"), (label, got, expected)
    print(f"PASS {label}: {got:.4f}% [arithmetic only]")

if __name__ == "__main__":
    check("Field A optimized vs actual (counterfactual)", percent_change_from_recorded("8.1","3.1"), "61.7283950617")
    check("Field B optimized vs actual (counterfactual)", percent_change_from_recorded("6.9","3.4"), "50.7246376812")
    check("Group 1 virtual vs actual reference", percent_change_from_recorded("7.00","2.29"), "67.2857142857")
    check("Group 2 virtual vs actual reference", percent_change_from_recorded("7.00","3.65"), "47.8571428571")
    check("Group 1 virtual rejections per 115 days", D(3)/D(115)*D(100), "2.6086956522")
    check("Group 2 virtual rejections per 115 days", D(9)/D(115)*D(100), "7.8260869565")
    print("6/6 arithmetic assertions passed. No experimental treatment effect established.")
