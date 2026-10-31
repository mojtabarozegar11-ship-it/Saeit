#!/usr/bin/env python3
"""Fail-closed local 24-file paired-end FASTQ manifest gate; never infers expression.

CSV columns: sample_id,mate,path,sha256,bytes,assembly_accession,refseq_release
Each biological sample must have exactly R1 and R2. Run only on an authorized
non-factory machine with enough disk/IO; SHA-256 streams full files.
"""
import argparse
import csv
import gzip
import hashlib
from collections import defaultdict
from pathlib import Path

FIELDS = ('sample_id', 'mate', 'path', 'sha256', 'bytes', 'assembly_accession', 'refseq_release')


def validate_manifest(path: Path, expected_files=24, verify_bytes=True):
    with path.open(encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != list(FIELDS):
            raise ValueError('Unexpected columns; expected ' + ','.join(FIELDS))
        rows = list(reader)
    if len(rows) != expected_files:
        raise ValueError(f'Expected {expected_files} file records; found {len(rows)}')
    by_sample = defaultdict(set)
    seen_paths = set()
    references = set()
    for row in rows:
        sample, mate, filepath = row['sample_id'].strip(), row['mate'], row['path']
        if not sample or mate not in ('R1', 'R2') or not filepath:
            raise ValueError('Missing sample/mate/path')
        if mate in by_sample[sample] or filepath in seen_paths:
            raise ValueError('Duplicate mate or reused file path')
        by_sample[sample].add(mate)
        seen_paths.add(filepath)
        references.add((row['assembly_accession'], row['refseq_release']))
        if not row['assembly_accession'] or not row['refseq_release']:
            raise ValueError('Missing reference assembly/release')
        try:
            expected_size = int(row['bytes'])
        except ValueError as exc:
            raise ValueError('Invalid byte size') from exc
        expected_hash = row['sha256'].lower()
        if len(expected_hash) != 64 or any(c not in '0123456789abcdef' for c in expected_hash):
            raise ValueError('Invalid SHA-256')
        if expected_size <= 0:
            raise ValueError('Empty file forbidden')
        if verify_bytes:
            p = Path(filepath)
            if not p.is_file() or p.stat().st_size != expected_size:
                raise ValueError(f'Missing file or size mismatch: {filepath}')
            h = hashlib.sha256()
            with p.open('rb') as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b''):
                    h.update(block)
            if h.hexdigest() != expected_hash:
                raise ValueError(f'SHA mismatch: {filepath}')
            opener = gzip.open if p.suffix == '.gz' else open
            with opener(p, 'rt', encoding='ascii') as handle:
                a, b, c, d = [handle.readline().rstrip('\n\r') for _ in range(4)]
            if not a.startswith('@') or c != '+' or not b or len(b) != len(d):
                raise ValueError(f'Invalid first FASTQ record: {filepath}')
    if any(mates != {'R1', 'R2'} for mates in by_sample.values()):
        raise ValueError('Every sample must have exactly R1 and R2')
    if len(references) != 1:
        raise ValueError('Mixed reference assembly/release')
    return {'samples': len(by_sample), 'files': len(rows), 'reference': next(iter(references)),
            'full_sha_and_first_record_verified': verify_bytes,
            'biological_replicates_confirmed': False,
            'rna_seq_results_authorized': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest_csv', type=Path)
    parser.add_argument('--expected-files', type=int, default=24)
    parser.add_argument('--schema-only', action='store_true',
                        help='Do not read FASTQ bytes; result is NOT data verified')
    args = parser.parse_args()
    print(validate_manifest(args.manifest_csv, args.expected_files, not args.schema_only))


if __name__ == '__main__':
    main()
