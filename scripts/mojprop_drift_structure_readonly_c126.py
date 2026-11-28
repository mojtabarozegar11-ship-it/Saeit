#!/usr/bin/env python3
"""Read-only structural comparison of the two MojProp drifted Python modules.

Emits identifiers and structural counts only. Never emits source, literals,
credentials, addresses, environment values, database rows, or file hashes.
"""
from __future__ import annotations

import ast
import json
import os
import stat
import sys
from pathlib import Path

FILES = (
    "prop_firm/starter30_paid_admission.py",
    "prop_firm/starter30_receiver_pool.py",
)
LIVE_ROOT = Path("/home/zomorod2/Saeit-mojprop-candidate-20261122")


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted(node.value)
        return (parent + "." if parent else "") + node.attr
    if isinstance(node, ast.Call):
        return dotted(node.func)
    return type(node).__name__


def signature(path):
    result = {"file": path, "exists": False, "regular": False,
              "parseable": False, "classes": [], "functions": [],
              "imports": [], "module_assignments": [], "decorators": [],
              "top_level_statement_counts": {}, "error": None}
    try:
        p = Path(path)
        st = p.lstat()
        result["exists"] = True
        result["regular"] = stat.S_ISREG(st.st_mode) and not stat.S_ISLNK(st.st_mode) and st.st_nlink == 1
        if not result["regular"]:
            result["error"] = "unsafe_file_type"
            return result
        tree = ast.parse(p.read_text(encoding="utf-8"))
        result["parseable"] = True
        classes, funcs, imports, assignments, decorators = set(), set(), set(), set(), set()
        counts = {}
        for node in tree.body:
            kind = type(node).__name__
            counts[kind] = counts.get(kind, 0) + 1
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs.add(node.name)
                decorators.update(dotted(x) for x in node.decorator_list)
            elif isinstance(node, ast.ClassDef):
                classes.add(node.name)
                decorators.update(dotted(x) for x in node.decorator_list)
            elif isinstance(node, ast.Import):
                imports.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add("." * node.level + (node.module or ""))
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        assignments.add(target.id)
        result.update(classes=sorted(classes), functions=sorted(funcs),
                      imports=sorted(imports), module_assignments=sorted(assignments),
                      decorators=sorted(decorators), top_level_statement_counts=dict(sorted(counts.items())))
    except (OSError, UnicodeError, SyntaxError, ValueError):
        result["error"] = "unreadable_or_invalid_python"
    return result


def main():
    if sys.argv[1:] == ["--expected"]:
        root = Path.cwd()
    elif sys.argv[1:] == ["--live"]:
        root = LIVE_ROOT
        if os.geteuid() == 0:
            print(json.dumps({"schema":"mojprop.ast.structure.c126.v1","read_only":True,
                              "error":"unexpected_privileged_identity","files":[]}, sort_keys=True))
            return 2
    else:
        print("usage: --expected | --live", file=sys.stderr)
        return 64
    rows = [signature(str(root / name)) for name in FILES]
    report = {"schema":"mojprop.ast.structure.c126.v1","read_only":True,
              "source_values_emitted":False,"secrets_emitted":False,
              "database_accessed":False,"customer_data_accessed":False,
              "files_modified":False,"service_restarted":False,
              "payment_created":False,"email_sent":False,"cost_incurred":False,
              "files":rows}
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if all(x["parseable"] and x["regular"] for x in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
