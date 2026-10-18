"""Read-only and content-free inventory of V91 agent/robot code on cPanel."""
import json
import os
from pathlib import Path
import re
import stat

ROOT = Path("/home/zomorod2/saeit_v91")
KEYWORDS = re.compile(r"(?i)(agent|robot|master|bot\b|worker|orchestrat|autonom|factory|task|scheduler|evolution|self.improv|automation|مستر|ربات|ایجنت)")
DENY = re.compile(r"(?i)(^\.env|secret|token|password|credential|private.key|wallet|\.pem$|\.key$|^id_rsa|\.db$|\.sqlite|cache|log)")
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache", "dist", "build", ".next", ".cache", "staticfiles"}
records, roots, seen = [], [], 0

def examine(directory, depth=0):
    global seen
    if depth > 8 or seen >= 18000:
        return
    try:
        entries = sorted(os.scandir(directory), key=lambda e: e.name)
    except (OSError, PermissionError):
        return
    for entry in entries:
        if seen >= 18000:
            break
        seen += 1
        name = entry.name
        if DENY.search(name) or name in SKIP_DIRS or name.startswith("."):
            continue
        try:
            mode = entry.stat(follow_symlinks=False).st_mode
        except (OSError, PermissionError):
            continue
        if stat.S_ISLNK(mode):
            continue
        rel = str(Path(entry.path).relative_to(ROOT))
        isdir = stat.S_ISDIR(mode)
        if depth == 0:
            roots.append({"name": name[:110], "kind": "dir" if isdir else "file"})
        if KEYWORDS.search(rel) and len(records) < 600:
            records.append({"path": rel[:230], "kind": "dir" if isdir else "file",
                            "bytes": int(entry.stat(follow_symlinks=False).st_size) if not isdir else None})
        if isdir and depth < 8:
            examine(entry.path, depth+1)

if ROOT.is_dir() and not ROOT.is_symlink():
    examine(ROOT)
    print(json.dumps({"status": "ok", "root": "saeit_v91",
                      "root_entries": roots[:170], "agent_candidates": records[:600],
                      "scanned": seen, "truncated": seen >= 18000 or len(records)>=600}, ensure_ascii=False))
else:
    print(json.dumps({"status": "missing_or_symlink"}))
