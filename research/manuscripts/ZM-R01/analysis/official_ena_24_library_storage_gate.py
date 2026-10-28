#!/usr/bin/env python3
"""No-download, fail-closed 24-library ENA/GEO paired-read capacity gate.

Reads the source-verified manifests. Does NOT fetch raw FASTQ, claim MD5
validation of bytes, build an index, or create gene counts.
"""
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parent.parent
ENA=ROOT/"ENA_PRJNA1249400_OFFICIAL_24_RUN_PAIRED_FASTQ_MD5_2026-10-25.tsv"
GEO=ROOT/"GSE294406_24_GSM_BIOSAMPLE_SRR_VERIFIED_CROSSWALK_2026-10-26.tsv"
OUT=ROOT/"GSE294406_24_LIBRARY_OFFICIAL_ENA_NO_DOWNLOAD_STORAGE_GATE_2026-10-26.json"
RESERVE=2*(1024**3)

def read_tsv(p):
    with p.open(encoding="utf-8",newline="") as fh:
        return list(csv.DictReader(fh,delimiter="\t"))

def main():
    en=read_tsv(ENA); ge=read_tsv(GEO)
    if len(en)!=24 or len(ge)!=24:
        raise RuntimeError("Expected exactly 24 source rows in both manifests")
    em={r["run_accession"]:r for r in en}
    if len(em)!=24 or len({r["srr"] for r in ge})!=24 or len({r["gsm"] for r in ge})!=24:
        raise RuntimeError("Duplicate SRR/GSM")
    if len({r["biosample"] for r in ge})!=24:
        raise RuntimeError("Duplicate BioSample")
    groups={}; rows=[]
    for g in ge:
        e=em.get(g["srr"])
        if not e or e["sample_accession"]!=g["biosample"]:
            raise RuntimeError("Source crosswalk mismatch for "+g["gsm"])
        if not all(g[k] in ("0","1") for k in ("D","H","C")):
            raise RuntimeError("Invalid factorial level")
        key="".join(g[k] for k in ("D","H","C"))
        for i in (1,2):
            if not re.fullmatch(r"[0-9a-fA-F]{32}",e[f"fastq{i}_md5"]):
                raise RuntimeError("Malformed MD5 string")
            if not e[f"fastq{i}_url"].startswith("https://ftp.sra.ebi.ac.uk/"):
                raise RuntimeError("Unexpected FASTQ host")
        size=sum(int(e[f"fastq{i}_bytes"]) for i in (1,2))
        if size<=0:
            raise RuntimeError("Invalid byte size")
        groups.setdefault(key,[]).append(size)
        rows.append({"gsm":g["gsm"],"srr":g["srr"],"biosample":g["biosample"],
                     "factorial_cell":key,"compressed_pair_bytes":size,
                     "md5_strings_present_not_verified":2})
    if set(groups)!={f"{d}{h}{c}" for d in "01" for h in "01" for c in "01"}:
        raise RuntimeError("Not all eight factorial cells present")
    if any(len(v)!=3 for v in groups.values()):
        raise RuntimeError("Not three biological replicates per cell")
    total=sum(x["compressed_pair_bytes"] for x in rows)
    largest=max(rows,key=lambda x:x["compressed_pair_bytes"])
    smallest=min(rows,key=lambda x:x["compressed_pair_bytes"])
    if total!=149540873452 or largest["compressed_pair_bytes"]!=7232544296:
        raise RuntimeError("Source manifest changed; update provenance after manual audit")
    disk=shutil.disk_usage("/")
    result={
      "source_provenance":{
          "ena_tsv_sha256":hashlib.sha256(ENA.read_bytes()).hexdigest(),
          "geo_crosswalk_tsv_sha256":hashlib.sha256(GEO.read_bytes()).hexdigest(),
          "source_fastq_files":48,"source_md5_strings":48,
          "actual_fastq_bytes_downloaded_or_md5_checked_by_this_script":0},
      "factorial_cell_replicates":{k:len(v) for k,v in sorted(groups.items())},
      "factorial_cell_compressed_bytes":{k:sum(v) for k,v in sorted(groups.items())},
      "compressed_total_bytes":total,
      "compressed_total_gib":total/1024**3,
      "largest_pair":largest,"smallest_pair":smallest,
      "runner_root_disk":{"total_bytes":disk.total,"free_bytes":disk.free,
                          "reserve_required_bytes":RESERVE},
      "gates":{
          "source_manifest_and_crosswalk":"PASS",
          "24_gsm_biosample_srr_unique":"PASS",
          "8_cells_three_replicates_each":"PASS",
          "bulk_48_fastq_download":"PROHIBITED",
          "single_pair_streaming_with_reference_index":"NOT_VALIDATED",
          "reference_assembly_annotation":"NOT_VALIDATED",
          "actual_48_fastq_md5":"NOT_DONE",
          "24_gene_integer_count_matrix":"NOT_DONE",
          "deseq2_and_fdr":"NOT_DONE"},
      "next_step":"Verify reference assembly and gene namespace; preflight a bounded streamed paired-end alignment/count with measured peak scratch, >=2 GiB reserve and actual FASTQ MD5; no raw FASTQ/BAM artifact or VPS transfer.",
      "rows":rows}
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"compressed_total_bytes":total,"largest_pair":largest,
       "runner_free_bytes":disk.free,"factorial_cell_replicates":result["factorial_cell_replicates"],
       "gates":result["gates"]},indent=2))

if __name__=="__main__":
    main()
