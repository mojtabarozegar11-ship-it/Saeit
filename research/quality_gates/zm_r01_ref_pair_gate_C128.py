#!/usr/bin/env python3
"""ZM-R01 reference FASTA/GFF3 structural gate (not an experiment or accession certificate)."""
import argparse,gzip,hashlib,json,sys
from pathlib import Path

def open_text(p):
    return gzip.open(p,'rt',encoding='utf-8',errors='strict') if str(p).endswith('.gz') else open(p,'rt',encoding='utf-8')

def sha256(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def verify(fasta,gff):
    sequences={}; current=None; genes=0; seqids=set();bad=[]
    with open_text(fasta) as f:
        for line_no,line in enumerate(f,1):
            line=line.strip()
            if not line:continue
            if line.startswith('>'):
                current=line[1:].split()[0]
                if not current or current in sequences:bad.append(f'FASTA duplicate/empty identifier at line {line_no}: {current}')
                else:sequences[current]=0
            else:
                if current is None:bad.append(f'FASTA sequence before header at line {line_no}')
                elif any(c.upper() not in 'ACGTNRYKMSWBDHVU.-' for c in line):bad.append(f'FASTA invalid base at line {line_no}')
                else:sequences[current]+=len(line)
    with open_text(gff) as f:
        for line_no,line in enumerate(f,1):
            if line.startswith('##sequence-region '):
                p=line.split()
                if len(p)==4 and p[1] in sequences:
                    try:
                        if int(p[3])>sequences[p[1]]:bad.append(f'GFF sequence-region exceeds FASTA at line {line_no}')
                    except ValueError:bad.append(f'Invalid sequence-region at line {line_no}')
            if line.startswith('#') or not line.strip():continue
            c=line.rstrip('\n').split('\t')
            if len(c)!=9:bad.append(f'GFF not 9 columns at line {line_no}');continue
            sid,_,feature,start,end,_,_,_,_=c;seqids.add(sid)
            if sid not in sequences:bad.append(f'GFF seqid absent from FASTA at line {line_no}: {sid}');continue
            try:
                a,b=int(start),int(end)
                if not 1<=a<=b<=sequences[sid]:bad.append(f'GFF interval out of bounds at line {line_no}')
            except ValueError:bad.append(f'GFF invalid coordinate at line {line_no}')
            if feature=='gene':genes+=1
    if not sequences:bad.append('No FASTA sequences')
    if not seqids:bad.append('No GFF features')
    if not genes:bad.append('No gene features')
    return {'status':'PASS_STRUCTURAL_ONLY' if not bad else 'FAIL','fasta_sha256':sha256(fasta),'gff_sha256':sha256(gff),'fasta_sequence_count':len(sequences),'gff_sequence_count':len(seqids),'gff_gene_feature_count':genes,'errors':bad,'warning':'This does not establish assembly/annotation accession identity, transcript compatibility, or existence of experimental FASTQ.'}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('fasta',type=Path);ap.add_argument('gff3',type=Path);args=ap.parse_args()
    result=verify(args.fasta,args.gff3);print(json.dumps(result,indent=2));sys.exit(0 if result['status'].startswith('PASS') else 2)
