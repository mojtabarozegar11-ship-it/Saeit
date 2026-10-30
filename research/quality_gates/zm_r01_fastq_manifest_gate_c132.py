#!/usr/bin/env python3
"""ZM-R01 local read-only validation of a planned 24-library paired-end FASTQ manifest.
No expression analysis is run. Refuses absent evidence and ambiguous reference versions.
Manifest JSON: reference{assembly,annotation,fasta,gff,fasta_sha256,gff_sha256}, samples[24]{sample_id,r1,r2,r1_sha256,r2_sha256,treatment,replicate}.
"""
import argparse,hashlib,json,pathlib,re,sys
SHA=re.compile(r'^[a-f0-9]{64}$')
ASSEMBLY='GCF_018294505.1';ANNOT='GCF_018294505.1-RS_2025_04'

def filecheck(p,expected):
    if not isinstance(expected,str) or not SHA.fullmatch(expected):raise ValueError('missing/invalid sha256')
    path=pathlib.Path(p)
    if not path.is_file() or path.stat().st_size==0:raise ValueError('missing/empty file: '+str(path))
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    if h.hexdigest()!=expected:raise ValueError('sha mismatch: '+str(path))
    return path.stat().st_size

def check(data):
    ref=data['reference']
    if ref.get('assembly')!=ASSEMBLY or ref.get('annotation')!=ANNOT:raise ValueError('reference assembly/annotation mismatch')
    for typ in ('fasta','gff'):filecheck(ref[typ],ref[typ+'_sha256'])
    samples=data['samples']
    if not isinstance(samples,list) or len(samples)!=24:raise ValueError('requires exactly 24 biological libraries')
    seen=set();paths=set();groups=set()
    for s in samples:
        sid=s.get('sample_id')
        if not isinstance(sid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,60}',sid) or sid in seen:raise ValueError('invalid/duplicate sample id')
        seen.add(sid)
        if not s.get('treatment') or s.get('replicate') is None:raise ValueError('missing treatment/replicate')
        groups.add((str(s['treatment']),str(s['replicate'])))
        for read in ('r1','r2'):
            p=s[read]
            if p in paths:raise ValueError('duplicate FASTQ path')
            paths.add(p);filecheck(p,s[read+'_sha256'])
    return {'samples':len(samples),'paired_fastq_files':len(paths),'treatment_replicate_pairs':len(groups),'status':'FILE_INTEGRITY_PASS_NOT_BIOLOGICAL_QC'}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('manifest');args=ap.parse_args()
    try:print(json.dumps(check(json.loads(pathlib.Path(args.manifest).read_text(encoding='utf-8'))),indent=2))
    except Exception as e:print('BLOCKED: '+str(e),file=sys.stderr);sys.exit(2)
