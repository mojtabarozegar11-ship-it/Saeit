"""Read-only S-01 checkout source drift triage; never emits source lines or paths."""
from __future__ import annotations
import difflib
import hashlib
import json
import pathlib
import sys

MAX_BYTES = 256 * 1024
MAX_LINES = 5000

def load(path: str) -> tuple[bytes, list[str]]:
    file = pathlib.Path(path)
    if file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_BYTES:
        raise ValueError('unsupported input')
    data = file.read_bytes()
    if len(data) > MAX_BYTES or b'\0' in data:
        raise ValueError('unsupported input')
    lines = data.decode('utf-8').splitlines(keepends=True)
    if len(lines) > MAX_LINES:
        raise ValueError('unsupported input')
    return data, lines

def compare(approved_path: str, observed_path: str) -> dict:
    approved, a = load(approved_path)
    observed, b = load(observed_path)
    hunks = []
    for kind, i1, i2, j1, j2 in difflib.SequenceMatcher(
            None, a, b, autojunk=True).get_opcodes():
        if kind != 'equal':
            hunks.append({'change': kind, 'approved_line_range': [i1 + 1, i2],
                          'observed_line_range': [j1 + 1, j2]})
    return {'status': 'MATCH' if approved == observed else 'SOURCE_SHA_DRIFT',
            'approved_sha256': hashlib.sha256(approved).hexdigest(),
            'observed_sha256': hashlib.sha256(observed).hexdigest(),
            'approved_lines': len(a), 'observed_lines': len(b),
            'hunk_count': len(hunks), 'hunks_first_40': hunks[:40],
            'truncated': len(hunks) > 40}

def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(json.dumps({'status': 'INVALID_INPUT'}))
        return 3
    try:
        report = compare(argv[1], argv[2])
    except (OSError, UnicodeError, ValueError):
        print(json.dumps({'status': 'INVALID_INPUT'}))
        return 3
    print(json.dumps(report, sort_keys=True))
    return 0 if report['status'] == 'MATCH' else 2

if __name__ == '__main__':
    sys.exit(main(sys.argv))
