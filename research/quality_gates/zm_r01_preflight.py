#!/usr/bin/env python3
"""Fail-closed ZM-R01 RNA-seq evidence preflight; checks files, not scientific validity.
Usage: python zm_r01_preflight.py /private/path/manifest.json
Never infer or invent genomic annotations, FASTQ reads, replicates or DEGs.
"""
import csv
import hashlib
import json
import pathlib
import re
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

def validate_refseq_accession(accession):
    """This ZM-R01 gate requires a versioned NCBI RefSeq assembly (GCF_).

    A GenBank GCA_ record is not silently interchangeable with a RefSeq GCF_
    assembly; this validates identifier syntax, NOT actual FASTA provenance.
    """
    if not isinstance(accession, str) or not re.fullmatch(r'GCF_[0-9]+\.[0-9]+', accession):
        raise GateError('Versioned NCBI RefSeq GCF_ assembly accession required')
    return accession


def validate_reference_identity(ref):
    """Reject known false assembly-version attribution; syntax alone is insufficient.

    NCBI identifies GCF_018294505.1 as IWGSC CS RefSeq v2.1, NOT v2.0.
    This limited guard does not authenticate other accessions, licensing,
    original FASTA/annotation bytes or release metadata.
    """
    accession = validate_refseq_accession(ref['assembly_accession'])
    version = ref.get('assembly_version')
    if not isinstance(version, str) or not version.strip():
        raise GateError('Non-empty assembly version string required')
    normalized = version.strip().lower().replace(' ', '')
    if accession == 'GCF_018294505.1' and re.search(r'(?:v)?2\.0(?!\d)', normalized):
        raise GateError('GCF_018294505.1 is IWGSC RefSeq v2.1, not v2.0; source-identity mismatch')
    return accession


IUPAC_DNA = frozenset('ACGTRYSWKMBDHVN')

def fasta_contigs(p):
    """Check reference syntax and return actual contig lengths, not just header names."""
    lengths={}
    current=None
    with p.open(encoding='utf-8') as f:
        for line_no, ln in enumerate(f, 1):
            if ln.startswith('>'):
                tokens=ln[1:].strip().split()
                if not tokens or tokens[0] in lengths:
                    raise GateError(f'Empty or duplicate FASTA sequence identifier at line {line_no}')
                current=tokens[0]
                lengths[current]=0
            elif ln.strip():
                if current is None:
                    raise GateError(f'FASTA sequence before header at line {line_no}')
                sequence=ln.strip().upper()
                if any(base not in IUPAC_DNA for base in sequence):
                    raise GateError(f'Invalid DNA alphabet in FASTA at line {line_no}')
                lengths[current]+=len(sequence)
    if not lengths or any(n==0 for n in lengths.values()):
        raise GateError('FASTA has no sequences or contains empty contigs')
    return lengths

def check_gtf(p, contigs):
    """Fail on invalid 1-based coordinates and annotation/FASTA contig mismatch."""
    seen=0; other=set()
    with p.open(encoding='utf-8') as f:
        for line_no, ln in enumerate(f, 1):
            if not ln.strip() or ln.startswith('#'):continue
            parts=ln.rstrip('\n').split('\t')
            if len(parts)!=9: raise GateError(f'GTF/GFF must have nine columns at line {line_no}')
            seen += 1
            if parts[0] not in contigs:
                other.add(parts[0]); continue
            if not parts[3].isascii() or not parts[3].isdecimal() or not parts[4].isascii() or not parts[4].isdecimal():
                raise GateError(f'Non-integer annotation coordinate at line {line_no}')
            start,end=int(parts[3]),int(parts[4])
            if start<1 or end<start or end>contigs[parts[0]]:
                raise GateError(f'Annotation interval outside FASTA contig at line {line_no}')
            if parts[6] not in ('+','-','.') or parts[7] not in ('.','0','1','2'):
                raise GateError(f'Invalid annotation strand/frame at line {line_no}')
            if not parts[2].strip() or not parts[8].strip() or parts[8].strip()=='.':
                raise GateError(f'Empty annotation feature/attributes at line {line_no}')
    if seen==0: raise GateError('No annotation records')
    if other: raise GateError(f'Annotation seqnames absent from FASTA: {sorted(other)[:8]}')
    return seen

MAX_R_INTEGER = 2147483647

def valid_raw_integer_count(cell):
    """Accept nonnegative ASCII integer strings representable as R 32-bit integers.

    This is a parser/integrity guard, not evidence of true biological counts.
    Avoid converting unbounded digit strings to Python ints (3.11 digit limit).
    """
    if not isinstance(cell, str) or not cell or not cell.isascii() or not cell.isdecimal():
        return False
    significant = cell.lstrip('0') or '0'
    limit = str(MAX_R_INTEGER)
    return len(significant) < len(limit) or (len(significant) == len(limit) and significant <= limit)


def check_count_matrix(cpath, library_ids):
    """Validate an existing TSV count matrix without estimating any expression values."""
    with cpath.open(encoding='utf-8', newline='') as f:
        reader = csv.reader(f, delimiter='\t')
        header = next(reader, [])
        if (not header or header[0].lower() not in ('gene_id', 'geneid')
                or len(header) != len(library_ids) + 1
                or len(set(header[1:])) != len(library_ids)
                or set(header[1:]) != library_ids):
            raise GateError('Raw matrix columns must contain each library ID exactly once')
        genes = set()
        n = 0
        for row in reader:
            if len(row) != len(library_ids) + 1:
                raise GateError('Count-matrix row width mismatch')
            gene = row[0]
            if (not gene or gene != gene.strip() or any(ch.isspace() for ch in gene)
                    or gene in genes):
                raise GateError('Missing, malformed or duplicate gene ID')
            genes.add(gene)
            n += 1
            if any(not valid_raw_integer_count(x) for x in row[1:]):
                raise GateError('Non-integer, negative, missing or >32-bit raw counts')
    if n == 0:
        raise GateError('Empty count matrix')
    return n


def validate(manifest_file):
    root=manifest_file.parent
    m=json.loads(manifest_file.read_text(encoding='utf-8'))
    if not isinstance(m, dict):
        raise GateError('Manifest root must be a JSON object')
    ref=m.get('reference',{})
    if not isinstance(ref, dict):
        raise GateError('Reference metadata must be a JSON object')
    missing=[k for k in REQUIRED_REF if not ref.get(k)]
    if missing: raise GateError('Missing reference metadata: '+', '.join(missing))
    validate_reference_identity(ref)
    fasta=file_with_digest(root,ref['fasta'],ref['fasta_sha256'],'sha256')
    gtf=file_with_digest(root,ref['gtf'],ref['gtf_sha256'],'sha256')
    check_gtf(gtf, fasta_contigs(fasta))
    libs=m.get('libraries',[])
    if not isinstance(libs, list) or any(not isinstance(lib, dict) for lib in libs):
        raise GateError('Libraries must be an array of metadata objects')
    if len(libs)!=24: raise GateError(f'Expected 24 documented libraries, got {len(libs)}')
    used_files=set(); ids=set(); reps=set(); conditions=Counter()
    for lib in libs:
        missing=[k for k in REQUIRED_LIB if not lib.get(k)]
        if missing: raise GateError(f'Incomplete library metadata: {missing}')
        lid=lib['library_id']
        if not isinstance(lid,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',lid):
            raise GateError('Library ID contains invalid characters or exceeds 128 characters')
        if lid in ids: raise GateError(f'Duplicate library ID: {lid}')
        ids.add(lid)
        condition=lib['condition']
        if condition not in EXPECTED_CONDITIONS:
            raise GateError(f'Invalid 2x2x2 factorial condition: {condition}')
        rep=lib['biological_replicate_id']
        if not isinstance(rep,str) or not rep.strip():
            raise GateError('Biological replicate identity must be a nonempty string')
        if rep in reps:
            raise GateError(f'Reused biological replicate identity across libraries: {rep}; repeated-measures designs require a separately reviewed protocol')
        reps.add(rep);conditions[condition]+=1
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
    if not isinstance(counts, dict):
        raise GateError('No valid raw integer count-matrix metadata; cannot run DESeq2')
    cpath=file_with_digest(root,counts.get('path'),counts.get('sha256'),'sha256')
    n=check_count_matrix(cpath, ids)
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
