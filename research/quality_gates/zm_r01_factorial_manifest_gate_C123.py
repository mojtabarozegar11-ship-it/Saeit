#!/usr/bin/env python3
"""Fail-closed metadata-only gate for the REAL ZM-R01 24-sample 8-cell design.

python zm_r01_factorial_manifest_gate_C123.py path/to/REAL_sample_manifest.tsv
No sequencing download, no factory operations and no biological inference.
Passing validates only declared metadata; it does NOT authenticate FASTQ bytes.
"""
import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

REQUIRED = ("sample_id", "factor_a", "factor_b", "factor_c", "replicate",
            "fastq_r1", "fastq_r2", "fastq_r1_sha256", "fastq_r2_sha256",
            "ref_fasta_sha256", "ref_gtf_sha256", "strandedness")
BANNED_ANNOTATION_IDS = {"SAMD00192732", "SAMD00192733", "SAMD00192734"}
SHA = re.compile(r"^[0-9a-fA-F]{64}$")


def assess(path: Path) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fields = reader.fieldnames or []
        rows = list(reader)
    errors = []
    if any(f not in fields for f in REQUIRED):
        errors.append("MISSING_COLUMNS:" + ",".join(f for f in REQUIRED if f not in fields))
    if len(rows) != 24:
        errors.append("EXPECTED_24_SAMPLES_GOT_" + str(len(rows)))
    cells, ids, fastqs, refs, stranded = Counter(), [], [], set(), set()
    for i, row in enumerate(rows, 1):
        for field in REQUIRED:
            if not (row.get(field) or "").strip():
                errors.append("ROW_" + str(i) + "_MISSING_" + field)
        sid = (row.get("sample_id") or "").strip()
        ids.append(sid)
        if sid in BANNED_ANNOTATION_IDS:
            errors.append("ROW_" + str(i) + "_ANNOTATION_SAMPLE_NOT_EXPERIMENT")
        cell = tuple((row.get(f) or "").strip() for f in ("factor_a", "factor_b", "factor_c"))
        if all(cell):
            cells[cell] += 1
        rep = (row.get("replicate") or "").strip()
        if rep and rep not in ("1", "2", "3"):
            errors.append("ROW_" + str(i) + "_INVALID_REPLICATE")
        for field in ("fastq_r1_sha256", "fastq_r2_sha256", "ref_fasta_sha256", "ref_gtf_sha256"):
            value = (row.get(field) or "").strip()
            if value and not SHA.fullmatch(value):
                errors.append("ROW_" + str(i) + "_INVALID_SHA_" + field)
        for field in ("fastq_r1", "fastq_r2"):
            fastqs.append((row.get(field) or "").strip())
        refs.add(((row.get("ref_fasta_sha256") or "").strip(),
                  (row.get("ref_gtf_sha256") or "").strip()))
        stranded.add((row.get("strandedness") or "").strip())
    if len(set(ids)) != len(ids):
        errors.append("DUPLICATE_SAMPLE_ID")
    if len(set(fastqs)) != len(fastqs):
        errors.append("DUPLICATE_FASTQ_PATH")
    if len(cells) != 8 or any(n != 3 for n in cells.values()):
        errors.append("EXPECTED_8_CELLS_WITH_3_REPLICATES")
    if len(refs) != 1:
        errors.append("INCONSISTENT_REFERENCE_CHECKSUMS")
    if len(stranded) != 1 or not stranded.issubset({"forward", "reverse", "unstranded"}):
        errors.append("INCONSISTENT_OR_UNKNOWN_STRANDEDNESS")
    for cell in cells:
        observed = {(r.get("replicate") or "").strip() for r in rows
                    if tuple((r.get(f) or "").strip() for f in ("factor_a", "factor_b", "factor_c")) == cell}
        if observed != {"1", "2", "3"}:
            errors.append("CELL_REPLICATE_IDS_NOT_1_2_3:" + "|".join(cell))
    return {"schema": "ZM-R01-METADATA-C123", "samples": len(rows),
            "factorial_cells": len(cells), "errors": sorted(set(errors)),
            "decision": "METADATA_ELIGIBLE_FOR_BYTE_VERIFICATION" if not errors else "BLOCK",
            "limitation": "No FASTQ file byte/hash validation, read quality, count matrix or DESeq2 analysis performed."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    report = assess(args.manifest)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["decision"] != "BLOCK" else 2)


if __name__ == "__main__":
    main()
