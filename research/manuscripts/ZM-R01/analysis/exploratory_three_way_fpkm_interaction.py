#!/usr/bin/env python3
"""Hypothesis generation only: 3-way factorial log-FPKM contrasts, NOT DEGs, raw-count inference or a biological discovery.
Source: original GEO GSE294406 FPKM workbook. Eight D x heat x elevated-CO2 cells, three replicates per cell.
"""
import argparse, hashlib, json, re
from pathlib import Path
import numpy as np
from openpyxl import load_workbook
EXPECTED='751c80defdc09b180f6174d6bbb3c7234570e8f15725f4c47cfcc9565b2f7e7b'
GROUPS=['CTR','eT','eC','D','CT','CD','TD','CTD']
# [D:H interaction at elevated CO2] minus [D:H interaction at ambient CO2]
COEF=np.array([-1,1,1,1,-1,-1,-1,1],dtype=float)
def run(inp,out):
    assert hashlib.sha256(inp.read_bytes()).hexdigest()==EXPECTED
    wb=load_workbook(inp,read_only=True,data_only=True)
    it=wb.active.values
    header=next(it)
    assert header[0]=='gene_id' and len(header)==25
    group_idx={g:[] for g in GROUPS}
    for j,h in enumerate(header[1:]):
        m=re.fullmatch(r'(CTR|eT|eC|D|CT|CD|TD|CTD)(?:_R)?([123])_FL',str(h))
        assert m,h
        group_idx[m.group(1)].append((int(m.group(2)),j))
    idx=[]
    for g in GROUPS:
        pairs=sorted(group_idx[g])
        assert [k for k,_ in pairs]==[1,2,3],(g,pairs)
        idx.append([j for _,j in pairs])
    ids=[]; values=[]
    for row in it:
        if row and row[0] is not None:
            ids.append(str(row[0]));values.append(row[1:])
    wb.close()
    x=np.asarray(values,dtype=float)
    assert x.shape==(105200,24) and np.isfinite(x).all() and (x>=0).all()
    y=np.stack([x[:,ix] for ix in idx],axis=1)
    assert y.shape==(105200,8,3) and len(set(ids))==105200
    cells_ge1=((y>=1).sum(axis=2)>=2).sum(axis=1)
    eligible=(cells_ge1>=4)&((y.mean(axis=2)>=5).sum(axis=1)>=2)
    beta={}
    for p in (0.5,1.,2.):
        beta[p]=np.log2(y+p).mean(axis=2)@COEF
    b=beta[1.]
    stable=(np.sign(b)==np.sign(beta[.5]))&(np.sign(b)==np.sign(beta[2.]))
    stable&=(np.abs(beta[.5])>=.5*np.abs(b))&(np.abs(beta[2.])>=.5*np.abs(b))
    L=np.log2(y+1.)
    loo=np.stack([L[:,:,np.arange(3)!=k].mean(axis=2)@COEF for k in range(3)],axis=1)
    stable&=(np.sign(loo)==np.sign(b[:,None])).all(axis=1)
    selected=eligible&stable&(np.abs(b)>=2.)
    dh_ambient=L[:,6,:].mean(axis=1)-L[:,3,:].mean(axis=1)-L[:,1,:].mean(axis=1)+L[:,0,:].mean(axis=1)
    dh_elevated=L[:,7,:].mean(axis=1)-L[:,5,:].mean(axis=1)-L[:,4,:].mean(axis=1)+L[:,2,:].mean(axis=1)
    assert np.max(np.abs(dh_elevated-dh_ambient-b))<1e-10
    descriptive_se=np.sqrt(L.var(axis=2,ddof=1).sum(axis=1)/3)
    ranking=np.flatnonzero(selected)
    ranking=ranking[np.argsort(-np.abs(b[ranking]))]
    top=[{'gene_id':ids[i], 'three_way_contrast_log2_FPKM_plus1':round(float(b[i]),5),
          'DH_interaction_ambient_CO2':round(float(dh_ambient[i]),5),
          'DH_interaction_elevated_CO2':round(float(dh_elevated[i]),5),
          'pseudocount_0_5_contrast':round(float(beta[.5][i]),5),
          'pseudocount_2_contrast':round(float(beta[2.][i]),5),
          'min_abs_leave_one_replicate_out':round(float(np.min(np.abs(loo[i]))),5),
          'descriptive_SE_not_statistical_test':round(float(descriptive_se[i]),5),
          'cells_with_2_of_3_replicates_FPKM_ge1':int(cells_ge1[i])} for i in ranking[:30]]
    result={'accession':'GSE294406','source_sha256':EXPECTED,
       'design':'Alana GS61 leaf; 8 factorial cells x 3 biological replicates',
       'contrast':'(CTD-CD-CT+eC)-(TD-D-eT+CTR) of group means log2(FPKM+1)',
       'status':'DESCRIPTIVE HYPOTHESIS GENERATION ONLY; NOT DESeq2/edgeR, DEG, FDR, causal mechanism or count-based test',
       'thresholds':'At least 4 cells with 2/3 replicates FPKM>=1; >=2 cells mean FPKM>=5; abs contrast>=2; stable sign and >=50% magnitude under pseudocounts 0.5 and 2; leave-one-replicate-index-out sign stable',
       'genes_total':len(ids),'genes_expression_eligible':int(eligible.sum()),
       'genes_eligible_and_robust':int((eligible&stable).sum()),
       'hypothesis_candidates_not_DEGs':int(selected.sum()),'top_candidates':top}
    out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='top_candidates'},indent=2))
    print('TOP_FIVE_HYPOTHESIS_ONLY',json.dumps(top[:5]))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('xlsx',type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();run(a.xlsx,a.output)
