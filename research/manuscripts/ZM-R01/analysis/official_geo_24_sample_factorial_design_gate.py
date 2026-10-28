#!/usr/bin/env python3
"""GSE294406 source-labeled 2x2x2 design preflight, not an RNA-seq analysis.

Source: https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE294406
Only GSM8904963 -> SRR33083355 / SAMN47891443 has been independently
matched through the original ENA/FASTQ artifact. Do not infer the other
GSM-to-SRR links from row order in the ENA manifest.
"""
import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path

GEO_URL = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE294406"
# GEO's displayed sample order, 8 treatments x 3 biological replicates.
TREATMENTS = (
    ("control", 0, 0, 0),
    ("drought", 1, 0, 0),
    ("elevated-temp", 0, 1, 0),
    ("elevated-CO2", 0, 0, 1),
    ("elevated-temp+drought", 1, 1, 0),
    ("elevated-CO2+drought", 1, 0, 1),
    ("elevated-CO2+elevated-temp", 0, 1, 1),
    ("elevated-CO2+elevated-temp+drought", 1, 1, 1),
)

def rank(matrix):
    a = [[float(v) for v in row] for row in matrix]
    rows, cols, pivot = len(a), len(a[0]), 0
    for col in range(cols):
        candidate = next((r for r in range(pivot, rows) if abs(a[r][col]) > 1e-9), None)
        if candidate is None:
            continue
        a[pivot], a[candidate] = a[candidate], a[pivot]
        div = a[pivot][col]
        a[pivot] = [x / div for x in a[pivot]]
        for r in range(rows):
            if r != pivot:
                factor = a[r][col]
                a[r] = [x - factor*y for x, y in zip(a[r], a[pivot])]
        pivot += 1
        if pivot == cols:
            break
    return pivot

def build():
    rows = []
    for index, (label, d, h, c) in enumerate(TREATMENTS):
        for replicate in (1, 2, 3):
            gsm = "GSM" + str(8904963 + index*3 + replicate - 1)
            rows.append(dict(gsm=gsm, treatment="Alana_"+label+"_biol_rep"+str(replicate),
                             D=d, H=h, C=c, biological_replicate=replicate,
                             srr="SRR33083355" if gsm == "GSM8904963" else "",
                             biosample="SAMN47891443" if gsm == "GSM8904963" else "",
                             gsm_to_srr_link_verified=(gsm == "GSM8904963")))
    return rows

def validate_ena_manifest(path):
    with open(path, newline="", encoding="utf-8") as handle:
        source = list(csv.DictReader(handle, delimiter="\t"))
    assert len(source) == 24 and len({r["run_accession"] for r in source}) == 24
    matches = [r for r in source if r["run_accession"] == "SRR33083355"]
    assert len(matches) == 1 and matches[0]["sample_accession"] == "SAMN47891443"
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ena-manifest")
    parser.add_argument("--output-prefix", required=True)
    args = parser.parse_args()
    rows = build()
    assert len(rows) == 24
    assert len({r["gsm"] for r in rows}) == 24
    assert len({r["treatment"] for r in rows}) == 24
    assert len({(r["D"], r["H"], r["C"]) for r in rows}) == 8
    assert all(sum((r["D"], r["H"], r["C"]) == cell for r in rows) == 3
               for cell in itertools.product((0, 1), repeat=3))
    # Full-rank eight-column model matrix for ~D*H*C.
    matrix = [[1, r["D"], r["H"], r["C"], r["D"]*r["H"],
               r["D"]*r["C"], r["H"]*r["C"], r["D"]*r["H"]*r["C"]]
              for r in rows]
    assert rank(matrix) == 8
    digest = validate_ena_manifest(args.ena_manifest) if args.ena_manifest else None
    prefix = Path(args.output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    with open(str(prefix)+".tsv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    result = {
        "source": GEO_URL, "project": "GSE294406", "genotype": "Alana",
        "gsm_samples": 24, "factorial_cells": 8, "replicates_per_cell": 3,
        "full_model": "~ D*H*C", "design_matrix_rank": rank(matrix),
        "model_columns": 8, "residual_degrees_of_freedom_before_filtering": 16,
        "ena_manifest_sha256": digest,
        "verified_gsm_srr_links": 1,
        "unverified_gsm_srr_links": 23,
        "raw_integer_count_matrix_available": False,
        "deseq2_performed": False,
        "assembly_equivalence_verified": False,
        "interpretation": "Design identifiability only; NO differential-expression or publication claim."
    }
    Path(str(prefix)+".json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
