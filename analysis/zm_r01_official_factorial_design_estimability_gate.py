#!/usr/bin/env python3
"""ZM-R01: audit GEO manifest factorial estimability, NOT expression or DEGs."""
import argparse,csv,hashlib,itertools,json,pathlib
from collections import Counter

def rank(matrix,eps=1e-10):
    a=[list(map(float,row)) for row in matrix]
    if not a:return 0
    m,n=len(a),len(a[0]);p=0
    for col in range(n):
        pivot=next((i for i in range(p,m) if abs(a[i][col])>eps),None)
        if pivot is None:continue
        a[p],a[pivot]=a[pivot],a[p]
        scale=a[p][col]
        a[p]=[v/scale for v in a[p]]
        for i in range(m):
            if i!=p:
                v=a[i][col]
                a[i]=[x-v*y for x,y in zip(a[i],a[p])]
        p+=1
        if p==m:break
    return p

def design(d,h,c):
    return [1,d,h,c,d*h,d*c,h*c,d*h*c]

def audit(p):
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    with p.open(encoding="utf-8-sig",newline="") as f:
        rd=csv.DictReader(f)
        needed={"study","accession","cultivar","stage","tissue","drought","heat","co2","biological_replicate"}
        if not needed.issubset(rd.fieldnames or []):raise ValueError("manifest columns missing")
        rows=list(rd)
    if len(rows)!=24:raise ValueError("Expected 24 GEO samples, got "+str(len(rows)))
    accessions=[r["accession"] for r in rows]
    if len(set(accessions))!=24 or not all(x.startswith("GSM") for x in accessions):
        raise ValueError("Duplicate/invalid GSM accession")
    if {r["study"] for r in rows}!={"GSE294406"}:raise ValueError("Mixed GEO studies")
    for k in ("cultivar","stage","tissue"):
        if len({r[k] for r in rows})!=1:raise ValueError("Confounded or inconsistent "+k)
    counts=Counter()
    design_rows=[]
    for r in rows:
        if any(r[x] not in ("0","1") for x in ("drought","heat","co2")):
            raise ValueError("Nonbinary factor level")
        d,h,c=(int(r[x]) for x in ("drought","heat","co2"))
        rep=int(r["biological_replicate"])
        if rep not in (1,2,3):raise ValueError("Unexpected biological replicate index")
        counts[(d,h,c,rep)]+=1
        design_rows.append(design(d,h,c))
    expected=list(itertools.product((0,1),repeat=3))
    if any(counts[(d,h,c,rep)]!=1 for d,h,c in expected for rep in (1,2,3)):
        raise ValueError("Not exactly one sample per cell and replicate index")
    full=rank(design_rows)
    loo=[rank(design_rows[:i]+design_rows[i+1:]) for i in range(len(rows))]
    dropped_cell=[rank([design(*tuple(int(r[x]) for x in ("drought","heat","co2"))) for r in rows if tuple(int(r[x]) for x in ("drought","heat","co2"))!=cell]) for cell in expected]
    return {
        "source_manifest_sha256":digest,
        "source_rows":len(rows),
        "cells":len(expected),
        "replicates_per_cell":3,
        "design_formula":"~ drought*heat*co2",
        "columns":["Intercept","D","H","C","D:H","D:C","H:C","D:H:C"],
        "matrix_rank":full,
        "n_coefficients":8,
        "residual_degrees_of_freedom_if_independent":len(rows)-full,
        "single_sample_dropout_min_rank":min(loo),
        "single_sample_dropout_max_rank":max(loo),
        "whole_cell_dropout_min_rank":min(dropped_cell),
        "whole_cell_dropout_max_rank":max(dropped_cell),
        "biological_independence_verified":False,
        "gene_counts_available":False,
        "deseq2_performed":False,
        "fdr_performed":False,
        "publication_gate":"BLOCKED_COUNTS_REFERENCE_INDEPENDENCE"
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest",type=pathlib.Path,required=True)
    ap.add_argument("--out",type=pathlib.Path,required=True)
    a=ap.parse_args()
    report=audit(a.manifest)
    if report["matrix_rank"]!=8 or report["single_sample_dropout_min_rank"]!=8 or report["whole_cell_dropout_max_rank"]!=7:
        raise ValueError("Unexpected design estimability; stop")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
