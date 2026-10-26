#!/usr/bin/env python3
"""Source-derived integer pilot counts from Bowtie2 transcriptome SAM (NOT unique mapping).

This is a REFERENCE-VALIDATION pilot. No FPKM/TPM or count imputation.
Input SAM should be primary alignments of proper read pairs to wheat cDNAs.
Each primary first mate contributes at most one fragment at MAPQ >= 20.
A MAPQ threshold does NOT establish a single concordant placement; original
Bowtie2 pilot QC found extensive multimapping. This is NOT a validated unique
fragment assignment or a publication-grade count pipeline.
Transcript-to-gene map is extracted from the exact reference FASTA headers.
The resulting conservative gene counts are not claimed identical to the
original genome-HISAT2/featureCounts matrix or a completed 24-sample study.
"""
import argparse
from collections import Counter
import csv
import gzip
import json
import re
import sys

def reference_gene_map(fasta_gz):
    mapping = {}
    with gzip.open(fasta_gz, "rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith(">"):
                continue
            head = line[1:].strip()
            transcript = head.split()[0]
            match = re.search(r"(?:^|\s)gene:([^\s]+)", head)
            if match:
                mapping[transcript] = match.group(1)
    if len(mapping) < 10000:
        raise RuntimeError("Fewer than 10,000 transcript-to-gene links; reject incompatible FASTA headers")
    return mapping

def count_fragments(mapping, threshold):
    gene_counts = Counter()
    stats = Counter()
    for line in sys.stdin:
        if line.startswith("@"): continue
        fields = line.rstrip("\n").split("\t")
        if len(fields) < 11:
            raise RuntimeError("Invalid SAM record")
        stats["SAM_records"] += 1
        flag = int(fields[1]); mapq = int(fields[4]); transcript = fields[2]
        if flag & (0x4 | 0x100 | 0x800 | 0x200): continue
        if not (flag & 0x1 and flag & 0x2 and flag & 0x40): continue
        stats["primary_proper_first_mates"] += 1
        if mapq < threshold: continue
        stats["passing_mapping_quality"] += 1
        gene = mapping.get(transcript)
        if gene is None:
            stats["missing_gene_annotation"] += 1
            continue
        gene_counts[gene] += 1
        stats["gene_assigned_fragments"] += 1
    return gene_counts, stats

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--reference-fasta-gz",required=True)
    ap.add_argument("--sample-gsm",required=True)
    ap.add_argument("--output-tsv",required=True)
    ap.add_argument("--provenance-json",required=True)
    ap.add_argument("--mapq",type=int,default=20)
    args=ap.parse_args()
    if not re.fullmatch(r"GSM\d+",args.sample_gsm):
        raise RuntimeError("Exact GEO GSM label required")
    mapping = reference_gene_map(args.reference_fasta_gz)
    counts, stats = count_fragments(mapping,args.mapq)
    if not counts:
        raise RuntimeError("No genuine gene-assigned fragments; do not generate a fabricated count matrix")
    with open(args.output_tsv,"w",newline="",encoding="utf-8") as f:
        w=csv.writer(f,delimiter="\t");w.writerow(["gene_id",args.sample_gsm])
        for gene,n in sorted(counts.items()):w.writerow([gene,n])
    with open(args.provenance_json,"w",encoding="utf-8") as f:
        json.dump({"GSM":args.sample_gsm,"reference_transcripts_mapped":len(mapping),
                   "MAPQ_min":args.mapq,"counts_type":"observed integer gene assignments from MAPQ-filtered primary first mates; strict concordant uniqueness NOT established",
                   "unique_concordant_mapping_verified":False,
                   "publication_grade_gene_counts":False,
                   "counted_genes":len(counts),"metrics":dict(stats),
                   "not_equivalent_to_original_authors_raw_counts":True,
                   "not_a_complete_matrix_or_statistical_DESeq2_result":True},f,indent=2)
    print("PILOT REAL COUNTS",args.sample_gsm,len(counts),dict(stats))
if __name__=="__main__":main()
