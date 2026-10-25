#!/usr/bin/env python3
"""Fail-closed independent audit of original ENA-based single-sample gene-count artifact.

Does NOT assert RefSeq-v2 assembly compatibility, featureCounts equivalence,
biological replication, DESeq2 readiness or journal-level conclusions.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re

EXPECTED_SRR = "SRR33083355"
EXPECTED_GSM = "GSM8904963"
EXPECTED_RUN = 40222743342
EXPECTED_REFERENCE_SUBPATH = "/release-61/fasta/triticum_aestivum/cdna/Triticum_aestivum.IWGSC.cdna.all.fa.gz"

def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1048576), b""):
            h.update(block)
    return h.hexdigest()

def audit(folder, manifest_path):
    folder = Path(folder)
    required = ["conservative_one_sample_integer_counts.tsv", "provenance.json",
                "alignment_summary.txt", "verified_ena_download_provenance.json",
                "wheat_cdna.fa.gz.sha256"]
    for name in required:
        if not (folder / name).is_file():
            raise ValueError("Missing original artifact component: " + name)
    with Path(manifest_path).open(encoding="utf-8", newline="") as handle:
        manifest = list(csv.DictReader(handle, delimiter="\t"))
    if len(manifest) != 24 or len({r["run_accession"] for r in manifest}) != 24:
        raise ValueError("Official 24-run manifest missing/duplicate")
    source = [r for r in manifest if r["run_accession"] == EXPECTED_SRR]
    if len(source) != 1:
        raise ValueError("Missing unique SRR in official manifest")
    source = source[0]
    ena = json.loads((folder / "verified_ena_download_provenance.json").read_text())
    counts_prov = json.loads((folder / "provenance.json").read_text())
    if ena.get("run_accession") != EXPECTED_SRR or ena.get("geo_sample_label") != EXPECTED_GSM:
        raise ValueError("ENA provenance accession mismatch")
    if ena.get("sample_accession") != source["sample_accession"]:
        raise ValueError("ENA Biosample mismatch")
    if ena.get("manifest_sha256") != sha256(manifest_path):
        raise ValueError("Official manifest SHA256 mismatch")
    if EXPECTED_REFERENCE_SUBPATH not in ena.get("reference_url", ""):
        raise ValueError("Unexpected or changed pilot reference: audit again")
    ref_lines = (folder / "wheat_cdna.fa.gz.sha256").read_text().splitlines()
    if len(ref_lines) != 1:
        raise ValueError("Ambiguous reference SHA256 file")
    match = re.fullmatch(r"([0-9a-f]{64})\s+\*?wheat_cdna\.fa\.gz", ref_lines[0].strip())
    if not match or match.group(1) != ena.get("reference_fasta_gz_sha256"):
        raise ValueError("Reference hash does not match provenance")
    read_files = ena.get("read_files", [])
    if len(read_files) != 2 or {int(x["mate"]) for x in read_files} != {1, 2}:
        raise ValueError("Expected exactly two ENA FASTQ mates")
    for read in read_files:
        k = int(read["mate"])
        if int(read["bytes"]) != int(source[f"fastq{k}_bytes"]):
            raise ValueError(f"Mate {k} byte count mismatch")
        if read["md5"].lower() != source[f"fastq{k}_md5"].lower():
            raise ValueError(f"Mate {k} official MD5 mismatch")
        if read["ena_url"] != source[f"fastq{k}_url"]:
            raise ValueError(f"Mate {k} original source URL mismatch")
    if counts_prov.get("GSM") != EXPECTED_GSM or counts_prov.get("MAPQ_min") != 20:
        raise ValueError("Count provenance GSM/MAPQ mismatch")
    if counts_prov.get("not_equivalent_to_original_authors_raw_counts") is not True:
        raise ValueError("Missing non-equivalence disclosure")
    if counts_prov.get("not_a_complete_matrix_or_statistical_DESeq2_result") is not True:
        raise ValueError("Missing incomplete-matrix disclosure")
    nrows = 0
    total = 0
    ids = set()
    with (folder / "conservative_one_sample_integer_counts.tsv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != ["gene_id", EXPECTED_GSM]:
            raise ValueError("Unexpected count table columns")
        for row in reader:
            gene = row["gene_id"]
            value = row[EXPECTED_GSM]
            if not gene or gene in ids or not re.fullmatch(r"[0-9]+", value):
                raise ValueError("Missing/duplicate gene ID or noninteger count")
            count = int(value)
            if count < 1:
                raise ValueError("Unexpected zero/negative sparse count")
            ids.add(gene)
            total += count
            nrows += 1
    metrics = counts_prov.get("metrics", {})
    if nrows <= 1000 or nrows != int(counts_prov.get("counted_genes", -1)):
        raise ValueError("Gene row count/provenance mismatch")
    if total != int(metrics.get("gene_assigned_fragments", -1)):
        raise ValueError("Sum of gene counts differs from assigned fragments")
    if total > int(metrics.get("passing_mapping_quality", -1)):
        raise ValueError("Assigned fragments exceed MAPQ-passing alignments")
    if int(metrics.get("passing_mapping_quality", -1)) > int(metrics.get("SAM_records", -1)):
        raise ValueError("Filtered alignment metrics inconsistent")
    align = (folder / "alignment_summary.txt").read_text(errors="replace")
    rates = re.findall(r"([0-9]+(?:\.[0-9]+)?)% overall alignment rate", align)
    if len(rates) != 1 or not 0 <= float(rates[0]) <= 100:
        raise ValueError("Bowtie2 original overall alignment rate absent/invalid")
    raw = re.search(r"(?m)^(\d+) reads; of these:", align)
    no = re.search(r"(\d+) \([\d.]+%\) aligned concordantly 0 times", align)
    unique = re.search(r"(\d+) \([\d.]+%\) aligned concordantly exactly 1 time", align)
    multi = re.search(r"(\d+) \([\d.]+%\) aligned concordantly >1 times", align)
    if not all((raw, no, unique, multi)):
        raise ValueError("Missing original Bowtie2 multimapping categories")
    original_pairs = int(raw.group(1))
    zero_pairs, one_pairs, multi_pairs = int(no.group(1)), int(unique.group(1)), int(multi.group(1))
    if zero_pairs + one_pairs + multi_pairs != original_pairs:
        raise ValueError("Original Bowtie2 categories do not sum to input pairs")
    # MAPQ >=20 does NOT establish a uniquely concordant paired alignment.
    # Source counts exceed uniquely aligned concordant pairs by 11.2 million.
    lower_bound_multimapped_counted = max(0, total - one_pairs)
    uniqueness_refuted = lower_bound_multimapped_counted > 0
    return {
        "audit": "original artifact cross-file provenance and sparse integer count consistency",
        "source_workflow_run": EXPECTED_RUN,
        "sample": EXPECTED_GSM, "srr": EXPECTED_SRR,
        "verified_ena_fastq_bytes": sum(int(source[f"fastq{k}_bytes"]) for k in (1, 2)),
        "official_ena_mates_md5": [source[f"fastq{k}_md5"] for k in (1, 2)],
        "reference_url": ena["reference_url"],
        "reference_compressed_sha256": match.group(1),
        "mapped_reference_transcripts": counts_prov.get("reference_transcripts_mapped"),
        "observed_nonzero_genes": nrows,
        "sum_conservative_integer_gene_counts": total,
        "bowtie2_overall_alignment_rate_percent": float(rates[0]),
        "original_input_read_pairs": original_pairs,
        "concordant_zero_pairs": zero_pairs,
        "concordant_exactly_once_pairs": one_pairs,
        "concordant_more_than_once_pairs": multi_pairs,
        "minimum_counted_fragments_from_multimapping_category": lower_bound_multimapped_counted,
        "sparse_integer_table_integrity": "PASS",
        "unique_mapping_claim": "REFUTED_BY_ORIGINAL_BOWTIE2_SUMMARY" if uniqueness_refuted else "NOT_ESTABLISHED",
        "scientific_release_gate": "BLOCKED_MULTIMAPPING_AND_ASSEMBLY" if uniqueness_refuted else "BLOCKED_ASSEMBLY_AND_INCOMPLETE_MATRIX",
        "all_24_libraries_counted": False,
        "assembly_equivalence_to_Milec_RefSeqv2": "NOT VERIFIED",
        "publication_grade_DESeq2_matrix": False,
        "note": "Single sample, pilot transcriptome alignment only. Source-level MD5 checks verified against manifest and provenance; raw FASTQ bytes were not redownloaded for this audit."
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact-dir", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    result = audit(args.artifact_dir, args.manifest)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
