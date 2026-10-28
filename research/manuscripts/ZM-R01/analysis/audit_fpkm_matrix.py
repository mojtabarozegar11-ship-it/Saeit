#!/usr/bin/env python3
"""Reproducible, non-inferential QC for GSE294406 FPKM XLSX. No DESeq2, DEGs or raw counts."""
import argparse
import collections
import hashlib
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
EXPECTED_SHA = "751c80defdc09b180f6174d6bbb3c7234570e8f15725f4c47cfcc9565b2f7e7b"
GROUPS = ("CTR", "eT", "eC", "D", "CT", "CD", "TD", "CTD")

def column_number(cell_address):
    letters = re.match(r"[A-Z]+", cell_address).group()
    out = 0
    for letter in letters:
        out = out * 26 + ord(letter) - 64
    return out - 1

def shared_strings(archive):
    result = []
    with archive.open("xl/sharedStrings.xml") as stream:
        for _, node in ET.iterparse(stream, events=("end",)):
            if node.tag == NS + "si":
                result.append("".join((t.text or "") for t in node.iter(NS + "t")))
                node.clear()
    return result

def worksheet_rows(archive, strings):
    with archive.open("xl/worksheets/sheet1.xml") as stream:
        for _, node in ET.iterparse(stream, events=("end",)):
            if node.tag != NS + "row":
                continue
            values = [None] * 25
            for cell in node.findall(NS + "c"):
                col = column_number(cell.attrib["r"])
                if col >= 25:
                    raise ValueError("Unexpected expression column")
                v = cell.find(NS + "v")
                if v is None:
                    continue
                values[col] = strings[int(v.text)] if cell.attrib.get("t") == "s" else float(v.text)
            yield values
            node.clear()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("xlsx", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    h = hashlib.sha256()
    with args.xlsx.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1048576), b""):
            h.update(chunk)
    if h.hexdigest() != EXPECTED_SHA:
        raise ValueError("Original GEO source SHA256 mismatch")
    with zipfile.ZipFile(args.xlsx) as archive:
        strings = shared_strings(archive)
        rows = worksheet_rows(archive, strings)
        headers = next(rows)
        if headers[0] != "gene_id" or len(headers) != 25:
            raise ValueError("Not the expected GEO gene-by-sample workbook")
        gene_ids = []
        matrix = []
        for row in rows:
            if not isinstance(row[0], str) or not row[0]:
                raise ValueError("Missing gene identifier")
            gene_ids.append(row[0])
            matrix.append([float(x) if x is not None else float("nan") for x in row[1:]])
    data = np.asarray(matrix, dtype=np.float64)
    if data.shape != (105200, 24):
        raise ValueError(f"Unexpected GEO matrix dimensions {data.shape}")
    if len(set(gene_ids)) != len(gene_ids):
        raise ValueError("Duplicated gene identifiers")
    if not np.isfinite(data).all() or (data < 0).any():
        raise ValueError("Non-finite or negative FPKM values")
    corr = np.corrcoef(np.log2(data + 1), rowvar=False)
    groups = []
    for k, name in enumerate(GROUPS):
        idx = list(range(k*3, k*3+3))
        values = [float(corr[idx[i], idx[j]]) for i in range(3) for j in range(i+1, 3)]
        groups.append({"condition": name, "sample_headers": headers[1+k*3:1+k*3+3],
                       "within_condition_log2_fpkm_correlation_min": min(values),
                       "within_condition_log2_fpkm_correlation_mean": sum(values)/3})
    report = {"accession": "GSE294406", "source_sha256": h.hexdigest(),
              "file_size_bytes": args.xlsx.stat().st_size,
              "gene_rows": int(data.shape[0]), "sample_columns": int(data.shape[1]),
              "expression_cells": int(data.size),
              "missing_cells": 0, "negative_cells": 0,
              "zero_cells": int((data == 0).sum()),
              "zero_fraction": float((data == 0).mean()),
              "gene_ids_unique": True, "groups": groups,
              "per_sample": [{"header": headers[j+1],
                              "zero_genes": int((data[:,j] == 0).sum()),
                              "genes_fpkm_ge_1": int((data[:,j] >= 1).sum()),
                              "fpkm_sum": float(data[:,j].sum())}
                             for j in range(24)],
              "interpretation": "Descriptive FPKM QC only; NOT raw counts, differential expression, independent sample identity verification, gene mechanism, or publication.",
              "raw_count_model_permitted": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"source_sha256": h.hexdigest(), "gene_rows": report["gene_rows"],
                      "expression_cells": report["expression_cells"], "zero_cells": report["zero_cells"],
                      "group_correlation_min": min(g["within_condition_log2_fpkm_correlation_min"] for g in groups),
                      "report": str(args.output)}, indent=2))

if __name__ == "__main__":
    main()
