#!/usr/bin/env python3
"""Claim-specific arithmetic audit of printed numbers; no imputation of raw data.

Public primary sources:
Amini et al. 2025: https://doi.org/10.1038/s41598-025-26567-z
Cvejic et al. 2020: https://doi.org/10.3390/agronomy10091238
Car et al. 2012: https://doi.org/10.1016/j.compag.2012.03.003

Crucial limitation: Car Table 5 cell counts here are reproduced from a
machine-readable, coauthor-uploaded text copy; page-image checking is still
needed. We test internal consistency, NOT assert author error from OCR alone.
"""
from decimal import Decimal
import json


def dec(x):
    return Decimal(str(x))


def check():
    # Amini 2025 publisher Table 4 irrigation depth and Table 5 water productivity.
    amini = {
        "F5_depth_mm_treatment": "363.2",
        "F5_depth_mm_control": "616.8",
        "F7_depth_mm_treatment": "1057.6",
        "F7_depth_mm_control": "764.9",
        "F7_water_productivity_treatment": "4.6",
        "F7_water_productivity_control": "6.0",
        "F7_conclusion_claim_delta_kg_m3": "-0.1",
    }
    f5 = dec(amini["F5_depth_mm_treatment"]) - dec(amini["F5_depth_mm_control"])
    f7 = dec(amini["F7_depth_mm_treatment"]) - dec(amini["F7_depth_mm_control"])
    f7wp = dec(amini["F7_water_productivity_treatment"]) - dec(amini["F7_water_productivity_control"])
    assert f5 == dec("-253.6")
    assert f7 == dec("292.7")
    assert f7wp == dec("-1.4")
    assert f7wp != dec(amini["F7_conclusion_claim_delta_kg_m3"])

    # Car et al. 2012 publisher abstract has an internally consistent
    # engagement-duration tally. This does not establish independently
    # observed compliance with specific irrigation recommendations.
    car_abstract = {"all_season": 45, "half_season": 13, "never": 14, "total": 72}
    assert sum(car_abstract[k] for k in ("all_season", "half_season", "never")) == 72
    # Table 5 copied from machine-readable author-uploaded article text:
    # six categories: Close 26, Close with step 7, More 3, Much less 6,
    # Stopped 15, Never sent 17, total printed 72.
    car_table5_extracted = [26, 7, 3, 6, 15, 17]
    car_table5_total_printed = 72
    car_table5_sum = sum(car_table5_extracted)
    assert car_table5_sum == 74 and car_table5_sum != car_table5_total_printed
    # An inconsistent transcript cannot establish a corrected numerator,
    # category-level denominator, or an independently observed O outcome.

    # Cvejic 2020 2020 telephone-survey percentages, interpreted strictly
    # as conditional rounded percentages and NOT established response counts.
    reported_percent = [83, 71, 49, 40, 11, 6, 17, 66]
    hypothetical_n35 = [29, 25, 17, 14, 4, 2, 6, 23]
    assert all(round(100 * count / 35) == pct for count, pct in
               zip(hypothetical_n35, reported_percent))
    return {
        "sources": {
            "Amini": "https://doi.org/10.1038/s41598-025-26567-z",
            "Car": "https://doi.org/10.1016/j.compag.2012.03.003",
            "Cvejic": "https://doi.org/10.3390/agronomy10091238",
        },
        "Amini_displayed_arithmetic_only": {
            "F5_treatment_minus_control_depth_mm": str(f5),
            "F7_treatment_minus_control_depth_mm": str(f7),
            "F7_table5_treatment_minus_control_productivity_kg_m3": str(f7wp),
            "F7_conclusion_reported_productivity_delta_kg_m3": amini["F7_conclusion_claim_delta_kg_m3"],
            "status": "irreconcilable from displayed rounded values; do not silently fix",
        },
        "Car_abstract": car_abstract,
        "Car_machine_text_table5": {
            "extracted_cells": car_table5_extracted,
            "sum": car_table5_sum,
            "printed_total": car_table5_total_printed,
            "status": "unresolved transcription/source-table inconsistency; page-image check required; don't infer adherence",
        },
        "Cvejic_2020_hypothetical_denominator_check": {
            "percentages": reported_percent,
            "n": 35,
            "possible_numerators_if_common_denominator": hypothetical_n35,
            "status": "conditional rounding compatibility only; actual person-level denominator not recovered",
        },
        "inference_limit": "No new primary measurements, causal estimates, validated adherence metric, or externally peer-reviewed results.",
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, ensure_ascii=False))
