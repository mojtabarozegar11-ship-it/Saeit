#!/usr/bin/env python3
"""Publish a *new* standalone Air Supremacy game without touching Crown Defender.

Only creates /home/zomorod2/mojplaywin.com/air-supremacy/index.html.
No existing path may be replaced, including parent .htaccess, games index,
Django, MariaDB, business pages or other game files.
Private staged source must match the SHA-256 of the approved repo bytes.
Smoke failure deletes only the exact new file/directory we created.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import stat
import sys

HOME=Path('/home/zomorod2')
ROOT=HOME/'mojplaywin.com'
NEW=ROOT/'air-supremacy'
HTML=NEW/'index.html'
MARKERS=(b'Air Supremacy',b'<canvas',b'<script',b'requestAnimationFrame',
         b'<!doctype html>',b'</body></html>')


def abort(message):
    raise RuntimeError('AIR_SUPREMACY_STANDALONE_SAFE_ABORT '+message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def inspect(run, sha):
    if not re.fullmatch(r'[0-9]{8,16}',run):
        abort('invalid run')
    if not re.fullmatch(r'[0-9a-f]{64}',sha):
        abort('invalid expected digest')
    for d in (HOME,ROOT):
        if not d.is_dir() or d.is_symlink():
            abort('unsafe parent '+str(d))
    if ROOT.stat().st_uid != os.getuid():
        abort('document root owned by another account')
    # The site root may be Django/Passenger rather than a static index.html.
    # Existing public page status is checked separately by the publish workflow.
    stage=HOME/('.mpw-air-supremacy-stage-'+run+'.html')
    if stage.is_symlink():
        abort('staging symlink forbidden')
    return stage


def source_check(raw, sha):
    if not 15_000 <= len(raw) <= 120_000:
        abort('unexpected source size')
    if digest(raw)!=sha or any(m not in raw for m in MARKERS):
        abort('source changed or HTML markers missing')
    if raw.count(b'<!doctype html>')!=1 or raw.count(b'<script')!=1:
        abort('HTML structure unexpected')
    return True


def install(run, sha):
    stage=inspect(run,sha)
    if NEW.exists() or NEW.is_symlink():
        abort('destination already exists, refuse replacement')
    if not stage.is_file() or not stat.S_ISREG(stage.stat().st_mode):
        abort('private staged source missing')
    raw=stage.read_bytes()
    source_check(raw,sha)
    # Exclusive creation, no truncation of any existing file.
    NEW.mkdir(mode=0o755)
    try:
        fd=os.open(str(HTML),os.O_WRONLY|os.O_CREAT|os.O_EXCL|
                   getattr(os,'O_NOFOLLOW',0),0o644)
        with os.fdopen(fd,'wb') as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        if digest(HTML.read_bytes())!=sha:
            abort('installed HTML mismatch')
        # Ensure it remains world-readable for the static origin.
        os.chmod(NEW,0o755)
        os.chmod(HTML,0o644)
    except BaseException:
        if HTML.exists() and not HTML.is_symlink() and digest(HTML.read_bytes())==sha:
            HTML.unlink()
        if NEW.is_dir() and not NEW.is_symlink() and not list(NEW.iterdir()):
            NEW.rmdir()
        raise
    print(json.dumps({'status':'AIR_SUPREMACY_SEPARATE_INSTALLED',
                      'target':str(HTML),'sha256':sha,'bytes':len(raw),
                      'original_crown_defender_untouched':True}))


def status(run,sha):
    inspect(run,sha)
    if NEW.is_symlink() or not NEW.is_dir() or HTML.is_symlink() or not HTML.is_file():
        abort('target not a normal file')
    if {p.name for p in NEW.iterdir()} != {'index.html'}:
        abort('unexpected new game directory contents')
    source_check(HTML.read_bytes(),sha)
    print('AIR_SUPREMACY_STANDALONE_SHA256_VERIFIED='+sha)


def rollback(run,sha):
    inspect(run,sha)
    if NEW.is_symlink() or not NEW.is_dir():
        abort('unsafe destination')
    if {p.name for p in NEW.iterdir()} != {'index.html'} or HTML.is_symlink():
        abort('destination contains unrecognized additions')
    source_check(HTML.read_bytes(),sha)
    HTML.unlink()
    NEW.rmdir()
    print('AIR_SUPREMACY_NEW_DIRECTORY_REMOVED_AFTER_FAILED_SMOKE=YES')


if __name__=='__main__':
    if len(sys.argv)!=4 or sys.argv[1] not in ('install','status','rollback'):
        abort('Usage: install|status|rollback RUN SHA256')
    {'install':install,'status':status,'rollback':rollback}[sys.argv[1]](*sys.argv[2:])
