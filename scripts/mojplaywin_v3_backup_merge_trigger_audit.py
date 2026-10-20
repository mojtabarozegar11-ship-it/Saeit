#!/usr/bin/env python3
"""Conservative, read-only analysis: does a backup-only merge trigger main workflows?

Overreports ambiguous trigger declarations and never performs deployments.
"""
import fnmatch
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGED = (
    ".github/workflows/mojplaywin-backup-crypto-unit.yml",
    ".github/workflows/mojplaywin-gzip-backup-readiness-v3.yml",
    ".github/workflows/mojplaywin-v3-owner-manual-backup.yml",
    ".github/workflows/mojplaywin-v3-synthetic-isolated-mariadb-restore.yml",
    "docs/MOJPLAYWIN_GZIP_BACKUP_V3.md",
    "scripts/mojplaywin_backup_encrypt_vps_gpg.py",
    "scripts/mojplaywin_backup_gzip_destination_preflight_v3.py",
    "scripts/mojplaywin_backup_gzip_recovery_v3.py",
    "scripts/mojplaywin_backup_gzip_runner_v3.py",
    "scripts/mojplaywin_backup_gzip_source_v3.py",
    "tests/test_mojplaywin_backup_destination_preflight_v3.py",
    "tests/test_mojplaywin_backup_gzip_v3.py",
    "tests/test_mojplaywin_backup_isolated_mariadb_v3.py",
    "tests/test_mojplaywin_backup_owner_manual_workflow_v3.py",
    "tests/test_mojplaywin_backup_pipeline_integration_v3.py",
    "tests/test_mojplaywin_backup_runner_v3.py",
    "scripts/mojplaywin_v3_backup_merge_trigger_audit.py",
)


def cleaned(raw):
    return raw.split("#", 1)[0].strip().strip("'\"")


def inline_list(value):
    x = value.strip()
    if not x:
        return []
    if x.startswith("[") and x.endswith("]"):
        return [cleaned(p) for p in x[1:-1].split(",") if cleaned(p)]
    return [cleaned(x)]


def event(text):
    lines = text.splitlines()
    header = next((i for i, l in enumerate(lines) if re.match(r"^on\s*:", l)), None)
    if header is None:
        return "unknown", []
    rest = lines[header].split(":", 1)[1].strip()
    if rest:
        return ("push_all" if "push" in rest else "none"), []
    section = []
    for l in lines[header + 1:]:
        if l and not l[0].isspace() and not l.lstrip().startswith("#"):
            break
        section.append(l)
    start = next((i for i, line in enumerate(section)
                  if re.match(r"^  push\s*:", line)), None)
    if start is None:
        return "none", []
    tail = []
    for l in section[start + 1:]:
        if re.match(r"^  [A-Za-z_-]+\s*:", l):
            break
        tail.append(l)
    branches = []
    excludes = []
    patterns = []
    block = None
    for line in tail:
        m = re.match(r"^    ([a-z-]+)\s*:\s*(.*)$", line)
        if m:
            block = m[1]
            vals = inline_list(m[2])
            if block == "branches": branches.extend(vals)
            elif block == "branches-ignore": excludes.extend(vals)
            elif block == "paths": patterns.extend(vals)
        elif re.match(r"^      -\s+", line):
            entry = cleaned(line.split("-", 1)[1])
            if block == "branches": branches.append(entry)
            elif block == "branches-ignore": excludes.append(entry)
            elif block == "paths": patterns.append(entry)
    if branches and not any(fnmatch.fnmatchcase("main", b) for b in branches):
        return "none", []
    if any(fnmatch.fnmatchcase("main", b) for b in excludes):
        return "none", []
    if not patterns:
        return "push_all", []
    hits = []
    for file in CHANGED:
        enabled = False
        for p in patterns:
            if p.startswith("!"):
                if fnmatch.fnmatchcase(file, p[1:]):
                    enabled = False
            elif fnmatch.fnmatchcase(file, p):
                enabled = True
        if enabled:
            hits.append(file)
    return ("push_matching" if hits else "none"), hits


def scan(root=ROOT):
    folder = Path(root) / ".github/workflows"
    risks = []
    for filename in sorted(folder.iterdir()):
        if filename.suffix not in (".yml", ".yaml") or not filename.is_file():
            continue
        try:
            outcome, matched = event(filename.read_text("utf8"))
        except (OSError, UnicodeError):
            outcome, matched = "unknown", []
        if outcome != "none":
            risks.append({"workflow": filename.name,
                          "trigger_scope": outcome,
                          "matching_changed_files": matched})
    return {"classification": "V3_MERGE_PUSH_WORKFLOW_TRIGGER_AUDIT",
            "changed_backup_paths": len(CHANGED),
            "potential_trigger_count": len(risks),
            "potential_triggers": risks,
            "approval_to_merge": False,
            "production_action_performed": False}


if __name__ == "__main__":
    print(json.dumps(scan(), sort_keys=True))
