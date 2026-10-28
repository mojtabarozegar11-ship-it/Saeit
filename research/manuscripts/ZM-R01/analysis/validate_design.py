#!/usr/bin/env python3
"""Reproducible, dependency-free GEO metadata design diagnostic.

Usage:
    python3 validate_design.py ../GEO_VERIFIED_SAMPLE_MANIFEST_27_SAMPLES_2026-10-25.csv
Prints JSON; does NOT download RNA-seq, estimate dispersion, or report DE genes.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def matrix_rank(rows, eps=1e-10):
    if not rows:
        return 0
    a = [list(map(float, row)) for row in rows]
    n, p = len(a), len(a[0])
    if any(len(row) != p for row in a):
        raise ValueError("ragged design matrix")
    k = 0
    for col in range(p):
        if k >= n:
            break
        pivot = max(range(k, n), key=lambda i: abs(a[i][col]))
        if abs(a[pivot][col]) < eps:
            continue
        a[k], a[pivot] = a[pivot], a[k]
        scale = a[k][col]
        a[k] = [x / scale for x in a[k]]
        for i in range(n):
            if i == k:
                continue
            scale = a[i][col]
            a[i] = [v - scale * b for v, b in zip(a[i], a[k])]
        k += 1
    return k


def design_a(row):
    g = int(row["cultivar"] == "TAM112")
    s = int(row["developmental_stage"] == "GrainFilling")
    d = int(row["treatment"] == "Dry")
    if row["cultivar"] not in {"TAM111", "TAM112"}:
        raise ValueError("unexpected cultivar " + row["cultivar"])
    if row["developmental_stage"] not in {"Heading", "GrainFilling"}:
        raise ValueError("unexpected stage " + row["developmental_stage"])
    if row["treatment"] not in {"Wet", "Dry"}:
        raise ValueError("unexpected water treatment " + row["treatment"])
    return [1, g, s, d, g*s, g*d, s*d, g*s*d]


def b_group(row):
    x = row["genotype"]
    if x == "WT":
        return "WT"
    if "BSMV empty vector" in x:
        return "BSMV"
    if x.startswith("Over-expressing"):
        return "OEX"
    if x.startswith("Under-expressing"):
        return "siRNA"
    raise ValueError("unexpected perturbation " + x)


def design_b(row):
    g = b_group(row)
    t = row["treatment"]
    if t == "well-watered 21 days":
        d = 0
    elif t == "well-watered 14 days and 7 days drought":
        d = 1
    else:
        raise ValueError("unexpected drought label " + t)
    levels = [int(g == x) for x in ("BSMV", "OEX", "siRNA")]
    return [1, *levels, d, *(x*d for x in levels)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    with args.manifest.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    expected_columns = {"study", "accession", "cultivar", "developmental_stage", "treatment", "genotype"}
    if not rows or not expected_columns.issubset(rows[0]):
        raise ValueError("manifest schema missing required columns")
    if len({r["accession"] for r in rows}) != len(rows):
        raise ValueError("duplicate GEO GSM accession")
    studies = {name: [r for r in rows if r["study"] == name] for name in ("GSE157033", "GSE226842")}
    if sum(len(s) for s in studies.values()) != len(rows):
        raise ValueError("unexpected study labels")
    a, b = studies["GSE157033"], studies["GSE226842"]
    if len(a) != 15 or len(b) != 12:
        raise ValueError("unexpected series sizes; update protocol before analysis")
    ma = [design_a(r) for r in a]
    mb = [design_b(r) for r in b]
    ca = Counter((r["cultivar"], r["developmental_stage"], r["treatment"]) for r in a)
    cb = Counter((b_group(r), "drought" if "drought" in r["treatment"] else "control") for r in b)
    result = {
        "source": str(args.manifest),
        "analysis_type": "metadata-only; no gene counts, QC or differential expression analyzed",
        "GSE157033": {
            "samples": len(a), "full_factorial_parameters": 8, "matrix_rank": matrix_rank(ma),
            "residual_degrees_of_freedom": len(a) - matrix_rank(ma),
            "cell_counts": {"|".join(k): v for k, v in sorted(ca.items())},
            "singleton_cells": ["|".join(k) for k, v in sorted(ca.items()) if v == 1],
            "warning": "Full 2x2x2 cell-means model is algebraically estimable (rank 8) but one cell has one biological library; only 7 residual df, low power, pooled variance assumptions and no independent per-cell variance for singleton."
        },
        "GSE226842": {
            "samples": len(b), "full_factorial_parameters": 8, "matrix_rank": matrix_rank(mb),
            "residual_degrees_of_freedom": len(b) - matrix_rank(mb),
            "cell_counts": {"|".join(k): v for k, v in sorted(cb.items())},
            "singleton_cells": ["|".join(k) for k, v in sorted(cb.items()) if v == 1],
            "warning": "4x2 cell-means model algebraically estimable (rank 8) but four singleton WT/BSMV cells; only 4 residual df, very low power. No within-cell dispersion from singleton; cross-study pooling forbidden."
        }
    }
    assert result["GSE157033"]["matrix_rank"] == 8 and result["GSE157033"]["residual_degrees_of_freedom"] == 7
    assert result["GSE226842"]["matrix_rank"] == 8 and result["GSE226842"]["residual_degrees_of_freedom"] == 4
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
