#!/usr/bin/env python3
"""Read-only structural comparison of the two MojProp drifted Python modules.

Emits identifiers and structural counts only. Never emits source, literals,
credentials, addresses, environment values, database rows, or file hashes.
"""
from __future__ import annotations

import ast
import copy
import hashlib
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


class MaskConstants(ast.NodeTransformer):
    def visit_Constant(self, node):
        return ast.copy_location(ast.Constant(value=type(node.value).__name__), node)


def safe_shape(node):
    masked = MaskConstants().visit(copy.deepcopy(node))
    return hashlib.sha256(ast.dump(masked, include_attributes=False).encode("utf-8")).hexdigest()


def behavior_summary(node):
    """Return identifier-only control-flow metadata; never emit literal values."""
    counts = {}
    calls = set()
    for item in ast.walk(node):
        kind = type(item).__name__
        if kind in {"If", "For", "AsyncFor", "While", "Try", "TryStar", "Return",
                    "Raise", "Assert", "BoolOp", "Compare", "Await", "Yield",
                    "YieldFrom", "Break", "Continue", "Match", "With", "AsyncWith"}:
            counts[kind] = counts.get(kind, 0) + 1
        if isinstance(item, ast.Call):
            name = dotted(item.func)
            if name and name != "Name" and len(name) <= 160:
                calls.add(name)
    args = getattr(node, "args", None)
    parameters = []
    if args is not None:
        parameters = [x.arg[:64] for x in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)]
        if args.vararg:
            parameters.append("*" + args.vararg.arg[:63])
        if args.kwarg:
            parameters.append("**" + args.kwarg.arg[:62])
    node_counts = {}
    operator_counts = {}
    branch_tests = []
    exception_types = set()
    keyword_names = set()
    operator_nodes = (ast.operator, ast.unaryop, ast.boolop, ast.cmpop)
    for item in ast.walk(node):
        kind = type(item).__name__
        node_counts[kind] = node_counts.get(kind, 0) + 1
        if isinstance(item, operator_nodes):
            operator_counts[kind] = operator_counts.get(kind, 0) + 1
        if isinstance(item, (ast.If, ast.While, ast.Assert)):
            branch_tests.append({"kind": kind, "shape_sha256": safe_shape(item.test)})
        elif isinstance(item, (ast.For, ast.AsyncFor)):
            branch_tests.append({"kind": kind, "shape_sha256": safe_shape(item.iter)})
        if isinstance(item, ast.ExceptHandler):
            exception_types.add(dotted(item.type) if item.type is not None else "bare")
        if isinstance(item, ast.Call):
            keyword_names.update(x.arg for x in item.keywords if x.arg)
    return {"parameters": parameters, "control_flow_counts": dict(sorted(counts.items())),
            "call_targets": sorted(calls)[:100],
            "node_type_counts": dict(sorted(node_counts.items())),
            "operator_counts": dict(sorted(operator_counts.items())),
            "branch_test_fingerprints": sorted(branch_tests, key=lambda x: (x["kind"], x["shape_sha256"])),
            "exception_handler_types": sorted(exception_types),
            "keyword_argument_names": sorted(keyword_names)}

def signature(path):
    result = {"file": Path(path).name, "exists": False, "regular": False,
              "parseable": False, "classes": [], "functions": [],
              "imports": [], "module_assignments": [], "decorators": [],
              "top_level_statement_counts": {}, "callable_fingerprints": [],
              "module_assignment_fingerprints": [], "literal_type_counts": {},
              "error": None}
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
        callable_rows = []
        behavior_rows = []
        assignment_rows = []
        literal_counts = {}
        for item in ast.walk(tree):
            if isinstance(item, ast.Constant):
                key = type(item.value).__name__
                literal_counts[key] = literal_counts.get(key, 0) + 1
        for node in tree.body:
            kind = type(node).__name__
            counts[kind] = counts.get(kind, 0) + 1
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs.add(node.name)
                decorators.update(dotted(x) for x in node.decorator_list)
                callable_rows.append({"kind": kind, "name": node.name, "shape_sha256": safe_shape(node)})
                behavior_rows.append({"kind": kind, "name": node.name, **behavior_summary(node)})
            elif isinstance(node, ast.ClassDef):
                classes.add(node.name)
                decorators.update(dotted(x) for x in node.decorator_list)
                callable_rows.append({"kind": kind, "name": node.name, "shape_sha256": safe_shape(node)})
                for member in ast.walk(node):
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        behavior_rows.append({"kind": type(member).__name__,
                                              "name": node.name + "." + member.name,
                                              **behavior_summary(member)})
            elif isinstance(node, ast.Import):
                imports.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add("." * node.level + (node.module or ""))
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        assignments.add(target.id)
                        value = getattr(node, "value", None)
                        if value is not None:
                            assignment_rows.append({"name": target.id, "shape_sha256": safe_shape(value)})
        result.update(classes=sorted(classes), functions=sorted(funcs),
                      imports=sorted(imports), module_assignments=sorted(assignments),
                      decorators=sorted(decorators), top_level_statement_counts=dict(sorted(counts.items())),
                      callable_fingerprints=sorted(callable_rows, key=lambda x: (x["kind"], x["name"])),
                      callable_behavior=sorted(behavior_rows, key=lambda x: (x["kind"], x["name"])),
                      module_assignment_fingerprints=sorted(assignment_rows, key=lambda x: x["name"]),
                      literal_type_counts=dict(sorted(literal_counts.items())))
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
