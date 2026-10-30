#!/usr/bin/env python3
"""Read-only integrity gate for authenticated ZM-R01 paired FASTQ files.
Usage: python zm_r01_fastq_byte_integrity_gate_C125.py manifest.tsv --data-root /trusted/data
Runs metadata gate first; then verifies actual bytes, gzip integrity and paired FASTQ read names.
This is NOT a sequencing quality-control, biological inference or factory operation.
"""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
from zm_r01_factorial_manifest_gate_C123 import assess as metadata_assess

def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def reads(path):
    with gzip.open(path,"rt",encoding="ascii",errors="strict") as f:
        while True:
            h=f.readline()
            if not h:
                return
            seq=f.readline(); plus=f.readline(); qual=f.readline()
            if not (h.startswith("@") and plus.startswith("+") and seq and qual):
                raise ValueError("malformed FASTQ record")
            if len(seq.rstrip("\r\n")) != len(qual.rstrip("\r\n")):
                raise ValueError("sequence/quality length mismatch")
            yield h.split()[0].removeprefix("@").removesuffix("/1").removesuffix("/2")

def safe_path(root,value):
    p=(root/value).resolve(strict=True)
    if not p.is_relative_to(root) or not p.is_file() or p.is_symlink():
        raise ValueError("path outside approved root or not a regular file")
    return p

def assess(manifest,root):
    meta=metadata_assess(manifest)
    if meta["decision"]=="BLOCK":
        return {"decision":"BLOCK","metadata_errors":meta["errors"],"checked_pairs":0}
    root=root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("approved data root must be directory")
    with manifest.open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f,delimiter="\t"))
    errors=[]; checked=0; reference_checks=set()
    for i,row in enumerate(rows,1):
        try:
            for k,sha in (("ref_fasta","ref_fasta_sha256"),("ref_gtf","ref_gtf_sha256")):
                if k not in row or not row[k].strip():
                    raise ValueError("missing "+k+" path")
                p=safe_path(root,row[k].strip())
                key=(str(p),row[sha].lower())
                if key not in reference_checks:
                    if digest(p)!=row[sha].lower():
                        raise ValueError("reference hash mismatch: "+k)
                    reference_checks.add(key)
            a=safe_path(root,row["fastq_r1"].strip())
            b=safe_path(root,row["fastq_r2"].strip())
            if a==b: raise ValueError("same mate file")
            if digest(a)!=row["fastq_r1_sha256"].lower() or digest(b)!=row["fastq_r2_sha256"].lower():
                raise ValueError("FASTQ hash mismatch")
            import itertools
            count=0
            for x,y in itertools.zip_longest(reads(a),reads(b)):
                if x is None or y is None or x!=y:
                    raise ValueError("paired read count or ID mismatch")
                count+=1
            if count==0: raise ValueError("empty FASTQ pair")
            checked+=1
        except (OSError,ValueError,UnicodeError,EOFError) as exc:
            errors.append("ROW_%d:%s"%(i,str(exc)))
    return {"schema":"ZM-R01-BYTE-C125","decision":"BYTE_INTEGRITY_VERIFIED" if not errors and checked==24 else "BLOCK",
            "checked_pairs":checked,"errors":errors,
            "limitation":"Only file integrity and pairing, not sequencing QC, biological authenticity, sample consent or treatment effects."}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifest",type=Path)
    ap.add_argument("--data-root",type=Path,required=True)
    args=ap.parse_args()
    try: result=assess(args.manifest,args.data_root)
    except (OSError,ValueError) as e: result={"decision":"BLOCK","errors":[str(e)]}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result["decision"]=="BYTE_INTEGRITY_VERIFIED" else 2)
if __name__=="__main__": main()
