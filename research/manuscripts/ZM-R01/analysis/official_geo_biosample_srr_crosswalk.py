#!/usr/bin/env python3
"""Fail-closed GEO GSM -> BioSample -> ENA SRR crosswalk; metadata only.
No accession-order inference, no FASTQ download, no expression or DEG claim.
"""
import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

GEO_SOFT = "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE294nnn/GSE294406/soft/GSE294406_family.soft.gz"
GEO_QUERY = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE294406&targ=gsm&view=full&form=text"
ENA_URL = ("https://www.ebi.ac.uk/ena/portal/api/filereport?"
           "accession=PRJNA1249400&result=read_run&"
           "fields=run_accession,sample_accession,experiment_accession&format=tsv")

def download(url, limit=30000000):
    last = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Academic-metadata-audit/1.0 (no-FASTQ)"})
            with urllib.request.urlopen(request, timeout=35) as response:
                body = response.read(limit + 1)
            if len(body) > limit:
                raise ValueError("metadata exceeds safe size limit")
            if not body:
                raise ValueError("empty source")
            return body
        except Exception as exc:
            last = exc
            if attempt < 2:
                time.sleep(attempt + 1)
    raise RuntimeError("primary metadata download failed: " + str(last))

def parse_geo_soft(text):
    records = {}
    current = None
    for line in text.splitlines():
        if line.startswith("^SAMPLE = "):
            gsm = line.partition("=")[2].strip()
            if not re.fullmatch(r"GSM\d+", gsm) or gsm in records:
                raise ValueError("invalid or duplicate GEO sample")
            current = {"gsm": gsm, "title": "", "biosamples": set(), "experiments": set()}
            records[gsm] = current
        elif line.startswith("^") and not line.startswith("^SAMPLE"):
            current = None
        elif current is not None:
            if line.startswith("!Sample_title = "):
                current["title"] = line.partition("=")[2].strip()
            elif line.startswith("!Sample_relation = "):
                relation = line.partition("=")[2].strip()
                current["biosamples"].update(re.findall(r"SAMN\d+", relation))
                current["experiments"].update(re.findall(r"SRX\d+", relation))
    return records

def read_ena_manifest(path):
    source = Path(path).read_bytes()
    rows = list(csv.DictReader(io.StringIO(source.decode("utf-8-sig")), delimiter="\t"))
    if len(rows) != 24:
        raise ValueError("ENA manifest must have exactly 24 runs")
    by_sample = defaultdict(list)
    runs = set()
    for row in rows:
        srr, sample = row["run_accession"], row["sample_accession"]
        if not re.fullmatch(r"SRR\d+", srr) or not re.fullmatch(r"SAMN\d+", sample) or srr in runs:
            raise ValueError("invalid or duplicate ENA SRR/SAMN")
        runs.add(srr)
        for field in ("fastq1_md5", "fastq2_md5"):
            if not re.fullmatch(r"[0-9a-fA-F]{32}", row[field]):
                raise ValueError("missing or malformed original ENA FASTQ MD5")
        by_sample[sample].append(row)
    if len(by_sample) != 24:
        raise ValueError("BioSample IDs are not one-to-one")
    return by_sample, hashlib.sha256(source).hexdigest()

def normalized(title):
    return re.sub(r"[^a-z0-9]+", "", title.lower())

def self_test():
    sample = """^SAMPLE = GSM1
!Sample_title = Alana_control_biol_rep1
!Sample_relation = BioSample: https://www.ncbi.nlm.nih.gov/biosample/SAMN123
!Sample_relation = SRA: https://www.ncbi.nlm.nih.gov/sra?term=SRX456
^SAMPLE = GSM2
!Sample_title = Alana_control_biol_rep2
!Sample_relation = BioSample: https://www.ncbi.nlm.nih.gov/biosample/SAMN124
^SERIES = GSE294406
"""
    p = parse_geo_soft(sample)
    assert len(p) == 2 and p["GSM1"]["biosamples"] == {"SAMN123"}
    assert p["GSM1"]["experiments"] == {"SRX456"}
    assert p["GSM2"]["biosamples"] == {"SAMN124"}
    print("SYNTHETIC PARSER SELF-TEST PASSED; not a real source mapping")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ena-manifest")
    ap.add_argument("--geo-manifest")
    ap.add_argument("--output-prefix")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    if not all((args.ena_manifest, args.geo_manifest, args.output_prefix)):
        ap.error("all three manifest/output arguments required")
    by_sample, ena_hash = read_ena_manifest(args.ena_manifest)
    with open(args.geo_manifest, newline="", encoding="utf-8") as f:
        geo_rows = list(csv.DictReader(f))
    if len(geo_rows) != 24 or len({r["accession"] for r in geo_rows}) != 24:
        raise ValueError("expected 24 distinct GEO manifest GSMs")
    raw = None
    source_url = None
    errors = []
    for url in (GEO_SOFT, GEO_QUERY):
        try:
            candidate = download(url)
            decoded = gzip.decompress(candidate) if candidate[:2] == b"\x1f\x8b" else candidate
            parsed = parse_geo_soft(decoded.decode("utf-8", errors="replace"))
            if set(parsed) != {r["accession"] for r in geo_rows}:
                raise ValueError("source GEO GSM set does not equal expected 24")
            raw, source_url, records = candidate, url, parsed
            break
        except Exception as exc:
            errors.append(url + ": " + str(exc))
    if raw is None:
        raise RuntimeError("GEO original metadata unavailable or inconsistent: " + " | ".join(errors))
    experiment_map = None
    if any(not rec["biosamples"] for rec in records.values()):
        ena_raw = download(ENA_URL)
        experiment_map = defaultdict(list)
        for row in csv.DictReader(io.StringIO(ena_raw.decode("utf-8-sig")), delimiter="\t"):
            if row.get("experiment_accession"):
                experiment_map[row["experiment_accession"]].append(row)
    result = []
    for row in geo_rows:
        gsm = row["accession"]
        rec = records[gsm]
        if normalized(rec["title"]) != normalized(row["sample_title"]):
            raise ValueError("GEO title differs from deposited manifest for " + gsm)
        biosamples = set(rec["biosamples"])
        evidence = "GEO SOFT !Sample_relation BioSample"
        if not biosamples and experiment_map is not None:
            matches = [x for sr in rec["experiments"] for x in experiment_map.get(sr, [])]
            biosamples = {x["sample_accession"] for x in matches}
            evidence = "GEO SOFT SRA experiment -> ENA experiment accession -> BioSample"
        if len(biosamples) != 1:
            raise ValueError("ambiguous or missing source BioSample for " + gsm)
        biosample = next(iter(biosamples))
        matched = by_sample.get(biosample, [])
        if len(matched) != 1:
            raise ValueError("GEO BioSample has zero/multiple ENA SRRs: " + gsm + " " + biosample)
        ena = matched[0]
        if experiment_map is not None and rec["experiments"]:
            # When experiment metadata was obtained, require its SRR to agree.
            experiment_runs = {x["run_accession"] for sr in rec["experiments"]
                               for x in experiment_map.get(sr, [])}
            if experiment_runs and ena["run_accession"] not in experiment_runs:
                raise ValueError("SRA experiment and BioSample disagree: " + gsm)
        result.append({"gsm": gsm, "geo_title": rec["title"],
                       "biosample": biosample, "srr": ena["run_accession"],
                       "D": row["drought"], "H": row["heat"], "C": row["co2"],
                       "biological_replicate": row["biological_replicate"],
                       "evidence": evidence,
                       "fastq1_md5": ena["fastq1_md5"], "fastq2_md5": ena["fastq2_md5"]})
    if len(result) != 24 or len({r["srr"] for r in result}) != 24:
        raise ValueError("crosswalk is not a one-to-one 24-sample mapping")
    anchor = next(x for x in result if x["gsm"] == "GSM8904963")
    if (anchor["srr"], anchor["biosample"]) != ("SRR33083355", "SAMN47891443"):
        raise ValueError("original independently verified pilot anchor mismatch")
    prefix = Path(args.output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    with open(str(prefix) + ".tsv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(result[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(result)
    report = {"status": "SOURCE-CROSSWALK-VERIFIED; NOT-COUNTS", "gsm_srr_pairs": 24,
              "paired_fastq_md5_entries": 48, "source_geo_url": source_url,
              "source_geo_sha256": hashlib.sha256(raw).hexdigest(),
              "ena_manifest_sha256": ena_hash, "anchor_gsm": anchor["gsm"],
              "anchor_srr": anchor["srr"], "counts_produced": False,
              "deseq2_performed": False, "assembly_equivalence_verified": False,
              "method": "GEO accession -> independently deposited BioSample/SRA relation -> ENA manifest; no accession order"}
    Path(str(prefix) + ".json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
