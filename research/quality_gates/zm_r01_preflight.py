#!/usr/bin/env python3
"""Fail-closed ZM-R01 RNA-seq evidence preflight; checks files, not scientific validity.
Usage: python zm_r01_preflight.py /private/path/manifest.json
Never infer or invent genomic annotations, FASTQ reads, replicates or DEGs.
"""
import csv
import hashlib
import json
import pathlib
import sys
from collections import Counter

REQUIRED_REF = ('species','assembly_accession','assembly_version','fasta','fasta_sha256','gtf','gtf_sha256','reference_license_url')
REQUIRED_LIB = ('library_id','condition','biological_replicate_id','fastq_r1','md5_r1','fastq_r2','md5_r2','strandedness','strandedness_evidence')

class GateError(ValueError):
    pass

EXPECTED_CONDITIONS = {format(i, '03b') for i in range(8)}

def validate_factorial_design(conditions):
    """Metadata-only 2x2x2 layout check; does NOT establish biological independence."""
    if set(conditions) != EXPECTED_CONDITIONS:
        missing = sorted(EXPECTED_CONDITIONS - set(conditions))
        extra = sorted(str(x) for x in set(conditions) - EXPECTED_CONDITIONS)
        raise GateError(f'Expected exactly eight 2x2x2 factorial cells; missing={missing}, extra={extra}')
    if any(conditions[c] != 3 for c in EXPECTED_CONDITIONS):
        raise GateError('Each of eight factorial cells requires exactly three recorded libraries')

def sha_file(p, name):
    h = hashlib.new(name)
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def file_with_digest(root, raw_path, expected, digest):
    if not isinstance(raw_path,str) or not raw_path.strip():
        raise GateError('Missing path')
    p = pathlib.Path(raw_path).expanduser()
    if not p.is_absolute():
        p = root / p
    if not p.is_file():
        raise GateError(f'Not a real file: {p}')
    if not isinstance(expected,str) or len(expected) != (64 if digest=='sha256' else 32) or any(c not in '0123456789abcdefABCDEF' for c in expected):
        raise GateError(f'Invalid expected {digest} for {p}')
    actual = sha_file(p,digest)
    if actual.lower() != expected.lower():
        raise GateError(f'{digest} mismatch for {p}: {actual}')
    return p

def fasta_contigs(p):
    contigs=set()
    with p.open(encoding='utf-8') as f:
        for ln in f:
            if ln.startswith('>'):
                name=ln[1:].strip().split()[0]
                if not name or name in contigs: raise GateError('Empty or duplicate FASTA sequence identifier')
                contigs.add(name)
    if not contigs: raise GateError('FASTA has no sequences')
    return contigs

def check_gtf(p, contigs):
    seen=0; other=set()
    with p.open(encoding='utf-8') as f:
        for ln in f:
            if not ln.strip() or ln.startswith('#'):continue
            parts=ln.rstrip('\n').split('\t')
            if len(parts)<9: raise GateError('GTF/GFF has fewer than nine columns')
            seen += 1
            if parts[0] not in contigs: other.add(parts[0])
    if seen==0: raise GateError('No annotation records')
    if other: raise GateError(f'Annotation seqnames absent from FASTA: {sorted(other)[:8]}')
    return seen

def valid_raw_integer_count(cell):
    """Only ASCII base-10 counts are portable to downstream R/DESeq2 readers."""
    return isinstance(cell, str) and cell.isascii() and cell.isdecimal()


def validate(manifest_file):
    root=manifest_file.parent
    m=json.loads(manifest_file.read_text(encoding='utf-8'))
    ref=m.get('reference',{})
    missing=[k for k in REQUIRED_REF if not ref.get(k)]
    if missing: raise GateError('Missing reference metadata: '+', '.join(missing))
    if not str(ref['assembly_accession']).startswith(('GCF_','GCA_')):
        raise GateError('RefSeq/GenBank assembly accession required, not invented')
    fasta=file_with_digest(root,ref['fasta'],ref['fasta_sha256'],'sha256')
    gtf=file_with_digest(root,ref['gtf'],ref['gtf_sha256'],'sha256')
    check_gtf(gtf, fasta_contigs(fasta))
    libs=m.get('libraries',[])
    if len(libs)!=24: raise GateError(f'Expected 24 documented libraries, got {len(libs)}')
    used_files=set(); ids=set(); reps=set(); conditions=Counter()
    for lib in libs:
        missing=[k for k in REQUIRED_LIB if not lib.get(k)]
        if missing: raise GateError(f'Incomplete library metadata: {missing}')
        lid=lib['library_id']
        if lid in ids: raise GateError(f'Duplicate library ID: {lid}')
        ids.add(lid)
        key=(lib['condition'],lib['biological_replicate_id'])
        if key in reps: raise GateError(f'Potentially repeated biological replicate identity: {key}')
        reps.add(key);conditions[lib['condition']]+=1
        if lib['strandedness'] not in ('forward','reverse','unstranded'):
            raise GateError('Strandedness needs forward/reverse/unstranded and QC evidence')
        for fn,expected in ((lib['fastq_r1'],lib['md5_r1']),(lib['fastq_r2'],lib['md5_r2'])):
            p=file_with_digest(root,fn,expected,'md5')
            if p.resolve() in used_files: raise GateError('Reused FASTQ file: '+str(p))
            used_files.add(p.resolve())
    validate_factorial_design(conditions)
    if not m.get('multimapping_policy') or not m.get('independence_documentation'):
        raise GateError('Multimapping policy and biological provenance documentation required')
    counts=m.get('raw_integer_counts')
    if not counts: raise GateError('No actual raw integer count matrix; cannot run DESeq2')
    cpath=file_with_digest(root,counts.get('path'),counts.get('sha256'),'sha256')
    with cpath.open(encoding='utf-8',newline='') as f:
        reader=csv.reader(f,delimiter='\t')
        header=next(reader,[])
        if not header or header[0].lower() not in ('gene_id','geneid') or set(header[1:])!=ids or len(header)!=25:
            raise GateError('Raw matrix columns must contain exactly the 24 library IDs')
        genes=set(); n=0
        for row in reader:
            if len(row)!=25:raise GateError('Count-matrix row width mismatch')
            if not row[0] or row[0] in genes: raise GateError('Missing or duplicate gene ID')
            genes.add(row[0]); n+=1
            if any(not valid_raw_integer_count(x) for x in row[1:]):
                raise GateError('Non-integer, negative or missing raw counts')
    if n==0:raise GateError('Empty count matrix')
    return {'manifest':'FILE_INTEGRITY_AND_METADATA_PASS_ONLY','libraries':24,'fastq_files':48,'genes':n,'conditions':dict(conditions),
            'scientific_gates_remaining':['independent biological provenance verification','alignment/QC reports','design specification','valid DESeq2 execution','FDR provenance']}

if __name__=='__main__':
    try:
        if len(sys.argv)!=2:raise GateError('Usage: python zm_r01_preflight.py <manifest.json>')
        result=validate(pathlib.Path(sys.argv[1]).resolve())
        print(json.dumps(result,indent=2,ensure_ascii=False))
    except (GateError, ValueError, OSError, StopIteration) as exc:
        print('BLOCKED: '+str(exc),file=sys.stderr)
        sys.exit(2)
