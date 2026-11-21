#!/usr/bin/env python3
"""Import an owner-reviewed draft segment into private AGRI-001 storage, never publish.

No inference, network, credentials, payment, sales, or public manuscript files.
The source file must already exist on the authorized private factory filesystem.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat

SCHEMA = 'saeit.agri150k.private-chunk.v1'
CHUNK = re.compile(r'^chapter-(\d\d)-part-(\d\d\d)\.md$')


def gate_module():
    path = Path(__file__).with_name('factory_agri150k_english_private_gate_v1.py')
    spec = importlib.util.spec_from_file_location('agri150k_gate', path)
    if spec is None or spec.loader is None:
        raise ValueError('AGRI_GATE_MISSING')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def safe_dir(path):
    if path.is_symlink() or not path.is_dir() or path.resolve() != path:
        raise ValueError('UNSAFE_PRIVATE_DIRECTORY')


def safe_source(path):
    if path.is_symlink():
        raise ValueError('UNSAFE_SOURCE_LINK')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or not 1000 <= info.st_size <= 240000:
            raise ValueError('INVALID_CHUNK_SIZE')
        raw = os.read(fd, 240001)
        if len(raw) != info.st_size:
            raise ValueError('CHUNK_SIZE_CHANGED')
        return raw, raw.decode('utf-8')
    finally:
        os.close(fd)


def validate(text, gate):
    tokens = gate.prose_tokens(text)
    if not 600 <= len(tokens) <= 4500:
        raise ValueError('CHUNK_WORD_COUNT_OUTSIDE_600_4500')
    if len(set(tokens)) < 120:
        raise ValueError('CHUNK_LEXICAL_PADDING')
    shingles = [tuple(tokens[i:i + 12]) for i in range(0, len(tokens) - 11, 6)]
    if len(set(shingles)) / max(1, len(shingles)) < 0.85:
        raise ValueError('CHUNK_REPETITION')
    return len(tokens), shingles


def ingest(root, source, chapter, part):
    if not 1 <= chapter <= 30 or not 1 <= part <= 999:
        raise ValueError('INVALID_CHAPTER_OR_PART')
    root = Path(root)
    safe_dir(root)
    area = root / 'production-instructions'
    stage = area / 'stage-05'
    base = stage / 'doctoral-monographs-150k-en-v1'
    for d in (area, stage, base):
        safe_dir(d)
    plan_path = base / 'AGRI-001.json'
    if plan_path.is_symlink() or not plan_path.is_file():
        raise ValueError('AGRI_PLAN_NOT_INSTALLED')
    gate = gate_module()
    if plan_path.read_bytes() != (json.dumps(gate.plan(), ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode():
        raise ValueError('AGRI_PLAN_HASH_OR_SCHEMA_MISMATCH')
    raw, text = safe_source(Path(source))
    count, shingles = validate(text, gate)
    folder = base / 'authored-chunks'
    if not folder.exists():
        folder.mkdir(mode=0o700)
    safe_dir(folder)
    product = folder / 'AGRI-001'
    if not product.exists():
        product.mkdir(mode=0o700)
    safe_dir(product)
    lock = product / '.ingest.lock'
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('UNSAFE_LOCK')
        fcntl.flock(fd, fcntl.LOCK_EX)
        name = f'chapter-{chapter:02d}-part-{part:03d}.md'
        target = product / name
        digest = hashlib.sha256(raw).hexdigest()
        old_shingles = set()
        for p in sorted(product.glob('chapter-??-part-???.md')):
            if p.is_symlink() or not p.is_file() or not CHUNK.fullmatch(p.name):
                raise ValueError('UNSAFE_EXISTING_CHUNK')
            if p == target:
                if hashlib.sha256(p.read_bytes()).hexdigest() == digest:
                    return {'state':'EXISTING_IDENTICAL_PRIVATE_DRAFT','sha256':digest,
                            'unreviewed_words':count,'published':False}
                raise ValueError('IMMUTABLE_CHUNK_CONFLICT')
            previous = gate.prose_tokens(p.read_text(encoding='utf-8'))
            old_shingles.update(tuple(previous[i:i + 12]) for i in range(0, len(previous) - 11, 3))
        if old_shingles and sum(sh in old_shingles for sh in shingles) / len(shingles) > 0.10:
            raise ValueError('CHUNK_DUPLICATES_PRIOR')
        out = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            with os.fdopen(out, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return {'schema':SCHEMA,'state':'PRIVATE_QA_UNREVIEWED','product':'AGRI-001',
                'chapter':chapter,'part':part,'sha256':digest,
                'unreviewed_words':count,'independent_science_review':False,
                'qc1000_approved':False,'published':False}
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--factory-private',required=True)
    parser.add_argument('--source-file',required=True)
    parser.add_argument('--chapter',type=int,required=True)
    parser.add_argument('--part',type=int,required=True)
    args = parser.parse_args()
    print(json.dumps(ingest(args.factory_private,args.source_file,args.chapter,args.part),sort_keys=True))

if __name__ == '__main__':
    main()
