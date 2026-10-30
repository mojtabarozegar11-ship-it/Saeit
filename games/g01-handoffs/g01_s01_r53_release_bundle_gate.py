#!/usr/bin/env python3
"""Read-only G-01 -> S-01 offline ZIP release gate. No network or deployment."""
import hashlib, json, re, sys
from pathlib import PurePosixPath
from zipfile import ZipFile, BadZipFile

PREFIX = 'ramadan-war/'
RELEASE = 'R53'
MANIFEST = PREFIX + 'R53-MANIFEST-SHA256.json'

def verify(path):
    problems = []
    try:
        with ZipFile(path) as z:
            names = [i.filename for i in z.infolist() if not i.is_dir()]
            if len(names) != len(set(names)):
                problems.append('duplicate archive member')
            if any(not n.startswith(PREFIX) or '..' in PurePosixPath(n).parts or chr(92) in n for n in names):
                problems.append('unsafe archive member path')
            if MANIFEST not in names:
                return problems + ['missing exact R53 manifest']
            if z.testzip() is not None:
                problems.append('ZIP CRC mismatch')
            try:
                doc = json.loads(z.read(MANIFEST))
            except (ValueError, KeyError):
                return problems + ['invalid release manifest']
            if doc.get('release') != RELEASE or doc.get('status') != 'OFFLINE_REVIEW_NOT_LIVE' or doc.get('factory_hold') is not True:
                problems.append('release state or factory HOLD mismatch')
            files = doc.get('files')
            if not isinstance(files, dict) or not files:
                return problems + ['manifest files schema invalid']
            if set(files) != {n[len(PREFIX):] for n in names if n != MANIFEST}:
                problems.append('manifest does not cover exact archive members')
            for relative, entry in files.items():
                if not isinstance(relative, str) or not isinstance(entry, dict) or not isinstance(entry.get('bytes'), int) or isinstance(entry.get('bytes'), bool) or not isinstance(entry.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', entry['sha256']):
                    problems.append('invalid manifest entry: ' + str(relative))
                    continue
                name = PREFIX + relative
                if name not in names:
                    problems.append('missing: ' + relative)
                    continue
                blob = z.read(name)
                if len(blob) != entry['bytes'] or hashlib.sha256(blob).hexdigest() != entry['sha256']:
                    problems.append('hash/size mismatch: ' + relative)
            try:
                preview = json.loads(z.read(PREFIX + 'preview-manifest.json'))
                policy = z.read(PREFIX + 'moj1-commerce-policy.mjs').decode('utf-8')
                if preview.get('release') != RELEASE or preview.get('payment_status') != 'disabled':
                    problems.append('preview release or payment state mismatch')
                if 'checkoutEnabled:false' not in policy or 'ownerApproved:false' not in policy or 'verifiedBackend:false' not in policy:
                    problems.append('MOJ1 fail-closed policy not verified')
            except (KeyError, UnicodeError, ValueError):
                problems.append('preview or MOJ1 policy unavailable')
    except (OSError, BadZipFile) as exc:
        return ['archive unreadable: ' + type(exc).__name__]
    return problems

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python g01_s01_r53_release_bundle_gate.py FILE.zip')
    errors = verify(sys.argv[1])
    print('PASS: offline integrity/MOJ1 HOLD; NOT a live release' if not errors else 'BLOCKED: ' + '; '.join(errors))
    raise SystemExit(1 if errors else 0)
