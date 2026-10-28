#!/usr/bin/env python3
"""Independent exploratory PCA/nearest-neighbor QC of GSE294406 FPKM, NOT DE analysis.
Requires numpy and the companion audit_fpkm_matrix.py in this directory.
Usage: python exploratory_filtered_fpkm_qc.py ORIGINAL.xlsx --output qc.json
"""
import argparse,hashlib,json,zipfile
from pathlib import Path
import numpy as np
from audit_fpkm_matrix import shared_strings,worksheet_rows,EXPECTED_SHA
p=argparse.ArgumentParser();p.add_argument("xlsx",type=Path);p.add_argument("--output",required=True,type=Path);a=p.parse_args()
assert hashlib.sha256(a.xlsx.read_bytes()).hexdigest()==EXPECTED_SHA
with zipfile.ZipFile(a.xlsx) as z:
    it=worksheet_rows(z,shared_strings(z));header=next(it);rows=list(it)
data=np.asarray([r[1:] for r in rows],dtype=float)
assert data.shape==(105200,24) and np.isfinite(data).all() and (data>=0).all()
keep=(data>=1).sum(axis=1)>=3
x=np.log2(data[keep]+1)
xc=x-x.mean(axis=1,keepdims=True)
gram=xc.T@xc/(xc.shape[0]-1)
vals,vecs=np.linalg.eigh(gram);order=np.argsort(vals)[::-1];vals=vals[order];vecs=vecs[:,order]
pc=vecs[:,:3]*np.sqrt(np.maximum(vals[:3],0))
for i in range(3):
    if pc[0,i]<0:pc[:,i]*=-1
cor=np.corrcoef(x,rowvar=False)
groups=[g for g in ("CTR","eT","eC","D","CT","CD","TD","CTD") for _ in range(3)]
within=[];between=[];neighbors=[]
for i in range(24):
    near=int(np.argsort(cor[i])[-2])
    neighbors.append({"sample":header[i+1],"group":groups[i],"nearest_sample":header[near+1],"nearest_group":groups[near],"nearest_r":float(cor[i,near]),"same_group":groups[i]==groups[near]})
    for j in range(i+1,24):
        (within if groups[i]==groups[j] else between).append(float(cor[i,j]))
report={"accession":"GSE294406","sha256":EXPECTED_SHA,"gene_rows":105200,"sample_columns":24,
"expression_filter":"FPKM>=1 in at least 3 samples","retained_genes":int(keep.sum()),
"excluded_genes":int((~keep).sum()),"pc_variance_fraction":list(map(float,vals[:3]/vals.sum())),
"within_corr_min":min(within),"within_corr_median":float(np.median(within)),
"between_corr_max":max(between),"between_corr_median":float(np.median(between)),
"nearest_neighbor_same_group":sum(n["same_group"] for n in neighbors),
"nearest_neighbor_total":24,"nearest_neighbors":neighbors,
"pcs":[{"sample":header[i+1],"group":groups[i],"pc1":float(pc[i,0]),"pc2":float(pc[i,1]),"pc3":float(pc[i,2])} for i in range(24)],
"limitations":["FPKM not raw counts","nearest-neighbor matching does not prove biological independence","sample-to-GSM mapping and batch QC pending","no DEGs, p-values, FDR, or biological mechanism"]}
assert report["retained_genes"]==45359
assert report["nearest_neighbor_same_group"]==24
a.output.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({k:report[k] for k in ("retained_genes","excluded_genes","pc_variance_fraction","within_corr_min","nearest_neighbor_same_group")},indent=2))
