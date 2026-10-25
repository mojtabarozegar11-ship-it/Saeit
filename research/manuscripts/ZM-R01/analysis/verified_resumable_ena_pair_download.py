#!/usr/bin/env python3
"""Download ONE public ENA paired FASTQ run, with strict actual-byte/MD5 provenance.

Never derive counts from FPKM. This script only retrieves original FASTQ bytes.
Runs on ephemeral standard GitHub Actions runner; no paid service or VPS.
The SHA-256 of the source reference is included for reproducibility.
"""
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

MANIFEST = "research/manuscripts/ZM-R01/ENA_PRJNA1249400_OFFICIAL_24_RUN_PAIRED_FASTQ_MD5_2026-10-25.tsv"

def hash_file(path, algorithm):
    h = hashlib.new(algorithm)
    with Path(path).open("rb") as f:
        while True:
            chunk = f.read(8 * 1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def run():
    root = Path(os.environ["GITHUB_WORKSPACE"])
    scratch = Path(os.environ["RUNNER_TEMP"]) / "zm_counts"
    scratch.mkdir(parents=True, exist_ok=True)
    srr = os.environ["SRR"]
    gsm = os.environ["GSM"]
    manifest_path = root / MANIFEST
    with manifest_path.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f, delimiter="\t") if r["run_accession"] == srr]
    if len(rows) != 1:
        raise RuntimeError(f"Expected exactly one official manifest record for {srr}")
    row = rows[0]
    expected = sum(int(row[f"fastq{k}_bytes"]) for k in (1, 2))
    if shutil.disk_usage(scratch).free < expected + 3_000_000_000:
        raise RuntimeError("Insufficient free ephemeral disk before any FASTQ transfer")
    ref = scratch / "wheat_cdna.fa.gz"
    if not ref.is_file():
        raise RuntimeError("Reference must be independently downloaded and checked before FASTQ transfer")
    provenance = {
        "run_accession": srr,
        "geo_sample_label": gsm,
        "sample_accession": row["sample_accession"],
        "manifest_sha256": hash_file(manifest_path, "sha256"),
        "reference_fasta_gz_sha256": hash_file(ref, "sha256"),
        "reference_url": os.environ["REFERENCE_URL"],
        "git_sha": os.environ.get("GITHUB_SHA", ""),
        "utc": datetime.now(timezone.utc).isoformat(),
        "read_files": [],
        "provenance_type": "verified original public ENA compressed paired FASTQ; not derived expression",
    }
    for k in (1, 2):
        url = row[f"fastq{k}_url"]
        if not url.startswith("https://ftp.sra.ebi.ac.uk/vol1/fastq/"):
            raise RuntimeError("Unexpected URL host/path: refuse transfer")
        out = scratch / f"R{k}.fastq.gz"
        length = int(row[f"fastq{k}_bytes"])
        digest = row[f"fastq{k}_md5"].lower()
        if len(digest) != 32 or not all(c in "0123456789abcdef" for c in digest):
            raise RuntimeError("Missing or malformed official MD5")
        for attempt in range(1, 4):
            current = out.stat().st_size if out.exists() else 0
            if current > length:
                raise RuntimeError("Partial file larger than official size; do not truncate/retry silently")
            if current == length:
                break
            cmd = [
                "curl", "--fail", "--location", "--silent", "--show-error",
                "--connect-timeout", "40", "--max-time", "6000",
                "--speed-time", "300", "--speed-limit", "4096",
                "--continue-at", "-", "--output", str(out), url
            ]
            print(f"ENA transfer mate={k}, attempt={attempt}, existing_bytes={current}, expected={length}", flush=True)
            p = subprocess.run(cmd, check=False)
            if p.returncode != 0:
                print(f"curl returned {p.returncode}, resuming if partial is valid", flush=True)
                time.sleep(10)
            if out.exists() and out.stat().st_size == length:
                break
        if not out.is_file() or out.stat().st_size != length:
            raise RuntimeError(f"Incomplete ENA transfer mate {k}: {out.stat().st_size if out.exists() else 0}/{length}")
        observed = hash_file(out, "md5")
        if observed != digest:
            raise RuntimeError(f"ENA MD5 mismatch mate {k}: observed={observed} expected={digest}")
        print(f"OFFICIAL MD5 VERIFIED mate={k} bytes={length} md5={observed}", flush=True)
        provenance["read_files"].append({
            "mate": k, "ena_url": url, "bytes": length, "md5": observed
        })
    if len(provenance["read_files"]) != 2:
        raise RuntimeError("Both original mates required")
    (scratch / "verified_ena_download_provenance.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("ENA PAIR FULLY VERIFIED", srr, gsm, "bytes", expected, flush=True)

if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("FATAL SOURCE INTEGRITY GATE:", repr(exc), file=sys.stderr)
        raise
