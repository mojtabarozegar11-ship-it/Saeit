#!/usr/bin/env python3
"""Descriptive per-sample FPKM coverage audit for NCBI GSE294406.
NOT a read-count, batch, or differential-expression analysis.
Input: original submitter workbook, checked against recorded source SHA256.
"""
import argparse, hashlib, json, re
from pathlib import Path
from openpyxl import load_workbook
import numpy as np

EXPECTED='751c80defdc09b180f6174d6bbb3c7234570e8f15725f4c47cfcc9565b2f7e7b'
p=argparse.ArgumentParser()
p.add_argument('xlsx',type=Path)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
sha=hashlib.sha256(a.xlsx.read_bytes()).hexdigest()
assert sha==EXPECTED,sha
wb=load_workbook(a.xlsx,read_only=True,data_only=True)
ws=wb.active
it=ws.values
header=next(it)
assert len(header)==25 and header[0]=='gene_id'
values=[]
ids=set()
for row in it:
    if not row or row[0] is None:
        continue
    gene=str(row[0])
    assert gene not in ids,gene
    ids.add(gene)
    v=np.asarray(row[1:],dtype=float)
    assert v.size==24 and np.all(np.isfinite(v)) and np.all(v>=0)
    values.append(v)
x=np.asarray(values,dtype=float)
assert x.shape==(105200,24)
recs=[]
for j,name in enumerate(header[1:]):
    name=str(name)
    m=re.fullmatch(r'(CTR|eT|eC|D|CT|CD|TD|CTD)(?:_R)?([123])_FL',name)
    assert m,name
    v=x[:,j]
    pos=v[v>0]
    recs.append(dict(sample=name,condition=m.group(1),replicate=int(m.group(2)),
        n_positive=int((v>0).sum()),n_ge1=int((v>=1).sum()),
        zero_fraction=round(float((v==0).mean()),6),
        positive_median_fpkm=round(float(np.median(pos)),6),
        positive_p99_fpkm=round(float(np.quantile(pos,.99)),6),
        total_fpkm=round(float(v.sum()),3)))
by={}
for group in ['CTR','eT','eC','D','CT','CD','TD','CTD']:
    r=[z for z in recs if z['condition']==group]
    assert len(r)==3 and {z['replicate'] for z in r}=={1,2,3}
    by[group]={'n_ge1_min':min(z['n_ge1'] for z in r),
        'n_ge1_max':max(z['n_ge1'] for z in r),
        'n_ge1_range':max(z['n_ge1'] for z in r)-min(z['n_ge1'] for z in r),
        'n_positive_min':min(z['n_positive'] for z in r),
        'n_positive_max':max(z['n_positive'] for z in r)}
res={'source_sha256':sha,'gene_rows':len(ids),'sample_columns':24,
    'metric_definition':'per-sample nonzero and FPKM >=1 counts; positive FPKM median/99th percentile; descriptive, no read-count inference',
    'samples':recs,'group_summary':by,
    'overall':{'min_ge1':min(z['n_ge1'] for z in recs),
        'max_ge1':max(z['n_ge1'] for z in recs),
        'min_positive':min(z['n_positive'] for z in recs),
        'max_positive':max(z['n_positive'] for z in recs),
        'min_total_fpkm':min(z['total_fpkm'] for z in recs),
        'max_total_fpkm':max(z['total_fpkm'] for z in recs)}}
a.output.write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps({'overall':res['overall'],'group_summary':by},indent=2))
