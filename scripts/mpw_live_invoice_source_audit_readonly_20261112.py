#!/usr/bin/env python3
"""Bounded, read-only, secret-minimal cPanel invoice source evidence.

This script must be streamed to "python3 -B -" on the authorized cPanel host.
It never imports project modules, initializes Django, executes SQL, invokes an
invoice, creates a payment or writes to the application. Output is JSON flags,
fixed source-relative names, SHA-256 digests and function names only.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import stat
import sys
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path("/home/zomorod2/Saeit-staging")
SOURCE_PATHS = (
    "services/mpw_trx_commercial_web.py",
    "services/mpw_trx_commercial_context.py",
    "mpw_commerce/buyer_orders.py",
    "services/mpw_trx_guest_commerce.py",
    # Exact path identified by authenticated live cPanel AST import:
    # services.mpw_trx_guest_delivery.record_invoice
    "services/mpw_trx_guest_delivery.py",
)
TEMPLATE = "mpw_commerce/templates/mpw_commerce/product_checkout.html"
MODEL_SOURCE = "mpw_commerce/models.py"  # Static definition only; no SQL or Django import.
MAX_FILE_BYTES = 400_000
MAX_HELPERS = 64
# The independently reviewed guest identity adapter used by the release guard.
APPROVED_GUEST_SHA256 = "b9e0b9b210fa2d36db96b91f596af91ccbfc5923338fd2eb3fc87e800ca0f957"


def source_bytes(root: Path, relative: str) -> bytes:
    if relative not in (*SOURCE_PATHS, TEMPLATE, MODEL_SOURCE):
        raise ValueError("OUTSIDE_ALLOWLIST")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("UNSAFE_APPLICATION_ROOT")
    # Reject symlink traversal at every level, including nested template roots.
    # Checking only the final parent can miss an ancestor such as
    # /home/zomorod2/Saeit-staging/mpw_commerce -> an outside directory.
    parts = Path(relative).parts
    path = root
    for component in parts:
        path = path / component
        if path.is_symlink():
            raise ValueError("SYMLINK_IN_SOURCE")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_FILE_BYTES:
        raise ValueError("INVALID_SOURCE_FILE")
    return path.read_bytes()


def folded_literal(node: ast.AST) -> str | None:
    """Fold only short static string expressions; do not evaluate code."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value if len(node.value) <= 256 else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = folded_literal(node.left), folded_literal(node.right)
        if left is not None and right is not None and len(left) + len(right) <= 256:
            return left + right
    if isinstance(node, ast.JoinedStr):
        parts = [folded_literal(part) for part in node.values]
        if all(part is not None for part in parts) and sum(map(len, parts)) <= 256:
            return "".join(parts)
    return None


def has_email_reference(node: ast.AST, constants: dict[str, str] | None = None) -> bool:
    aliases = constants or {}
    for part in ast.walk(node):
        if isinstance(part, ast.Name):
            if "email" in part.id.lower() or "email" in aliases.get(part.id, "").lower():
                return True
        if isinstance(part, ast.Attribute) and "email" in part.attr.lower():
            return True
        if isinstance(part, ast.keyword) and part.arg and "email" in part.arg.lower():
            return True
        if isinstance(part, ast.arg) and "email" in part.arg.lower():
            return True
        folded = folded_literal(part)
        if folded is not None and "email" in folded.lower():
            return True
    return False


class EmailControlParser(HTMLParser):
    """Handle quoted '>' and arbitrary attribute order safely and read-only."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = False

    def handle_starttag(self, tag, attrs):
        if tag not in ("input", "textarea", "select", "button"):
            return
        for name, value in attrs:
            name = name.lower()
            value = (value or "").strip().lower()
            if ((name in ("name", "id") and "email" in value)
                    or (name in ("type", "autocomplete") and value == "email")):
                self.found = True


def template_email_controls(raw: bytes) -> bool:
    parser = EmailControlParser()
    parser.feed(raw.decode("utf-8"))
    parser.close()
    return parser.found



def safe_function_contract(fn: ast.AST) -> dict:
    """Only AST parameter names, required flags and call categories; no values.

    Never inspect parameter defaults, decorator values, source text, runtime
    objects, Django models or order records. A signature is NOT evidence that
    the database allows an empty buyer-email column.
    """
    positional = list(fn.args.posonlyargs) + list(fn.args.args)
    defaults = len(fn.args.defaults)
    all_args = []
    for index, arg in enumerate(positional[:20]):
        all_args.append({"name": arg.arg, "required": index < len(positional)-defaults,
                         "kind": "positional"})
    for arg, value in zip(fn.args.kwonlyargs, fn.args.kw_defaults):
        if len(all_args) >= 24:
            break
        all_args.append({"name": arg.arg, "required": value is None,
                         "kind": "keyword_only"})
    imports = set()
    calls = set()
    orm_operations = []
    user_attributes = set()
    for node in ast.walk(fn):
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id == "user"):
            user_attributes.add(node.attr)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("get_or_create", "create",
                                       "update_or_create", "filter")):
            manager = node.func.value
            model = "UNRESOLVED"
            if (isinstance(manager, ast.Attribute) and
                    manager.attr == "objects" and
                    isinstance(manager.value, ast.Name)):
                model = manager.value.id
            keyword_names = [item.arg for item in node.keywords if item.arg]
            default_names = []
            for item in node.keywords:
                if item.arg == "defaults" and isinstance(item.value, ast.Dict):
                    for key in item.value.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            default_names.append(key.value)
            orm_operations.append({
                "model": model, "operation": node.func.attr,
                "keyword_names": sorted(set(keyword_names))[:20],
                "default_field_names": sorted(set(default_names))[:20],
            })

        if isinstance(node, ast.ImportFrom) and not node.level and node.module:
            if node.module.startswith(("mpw_commerce.", "services.")):
                imports.add(node.module)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
    # Read-only structural hints, not proof of invoice state changes.
    return {"parameters": all_args, "has_varargs": fn.args.vararg is not None,
            "has_varkw": fn.args.kwarg is not None,
            "calls_normalize_email": "normalize_email" in calls,
            "calls_create": "create" in calls,
            "calls_get_or_create": "get_or_create" in calls,
            "calls_atomic": "atomic" in calls,
            "calls_reserve_commercial_intent": "reserve_commercial_intent" in calls,
            "raises_exception": any(isinstance(node, ast.Raise)
                                    for node in ast.walk(fn)),
            "local_import_modules": sorted(imports)[:16],
            "orm_operations": orm_operations[:12],
            "user_attribute_names": sorted(user_attributes)[:16]}


def module_report(relative: str, raw: bytes) -> dict:
    tree = ast.parse(raw.decode("utf-8"), filename=relative)
    definitions = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    functions = {node.name: node for node in definitions}
    names = [node.name for node in definitions]
    duplicate_functions = sorted(name for name in set(names) if names.count(name) > 1)
    # Identify only the ORM class import *origin*, never model source or data.
    # Keep aliases explicit: from X import GuestTrxDelivery as Delivery.
    recorder = functions.get("record_invoice") if relative == SOURCE_PATHS[4] else None
    model_names = set()
    if recorder is not None:
        model_names = {operation.get("model") for operation in
                       safe_function_contract(recorder)["orm_operations"]}
    model_import_origins = []
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom):
            for name in statement.names:
                local = name.asname or name.name
                if local in model_names:
                    model_import_origins.append({
                        "model": local, "import_name": name.name,
                        "module": statement.module or "",
                        "relative_level": statement.level
                    })
    aliases = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for item in node.names:
                aliases[item.asname or item.name] = (node.module or "") + "." + item.name
        elif isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[0]] = item.name
    constants = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = folded_literal(node.value) if node.value is not None else None
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            if value is not None:
                for target in targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = value
    roots = []
    if relative == SOURCE_PATHS[0]:
        roots = ["_start_order"]
    elif relative == SOURCE_PATHS[1]:
        roots = [name for name in functions if "invoice" in name.lower()]
    elif relative == SOURCE_PATHS[3]:
        roots = ["_new_user", "_identity", "patch_commercial"]
    elif relative == SOURCE_PATHS[4]:
        roots = ["record_invoice"]
    # Invoice recorders may reside in any of the three audited commerce modules.
    if relative in (*SOURCE_PATHS[:3], SOURCE_PATHS[4]) and "record_invoice" in functions:
        roots.append("record_invoice")
    explored = set()
    pending = list(roots)
    email_functions = []
    external_calls = []
    checkout_call_targets = set()
    dynamic_calls = False
    while pending and len(explored) < MAX_HELPERS:
        name = pending.pop(0)
        if name in explored:
            continue
        explored.add(name)
        fn = functions.get(name)
        if fn is None:
            continue
        if has_email_reference(fn, constants):
            email_functions.append(name)
        for part in ast.walk(fn):
            # Live handlers may import the invoice recorder inside the
            # handler rather than at module scope. Merely seeing the call
            # name without its local import must never certify the recorder.
            if isinstance(part, ast.ImportFrom):
                for alias in part.names:
                    if alias.name == "record_invoice":
                        origin = part.module or ""
                        if part.level == 0 and origin:
                            external_calls.append({
                                "caller": name,
                                "import": origin + ".record_invoice"
                            })
                        else:
                            external_calls.append({
                                "caller": name,
                                "import": "relative.record_invoice"
                            })
            if not isinstance(part, ast.Call):
                continue
            if isinstance(part.func, ast.Name):
                callee = part.func.id
                if relative == SOURCE_PATHS[0] and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", callee):
                    checkout_call_targets.add(callee)
                if callee in functions and callee not in explored:
                    pending.append(callee)
                if callee in aliases:
                    external_calls.append({"caller": name,
                                           "import": aliases[callee][:130]})
            elif isinstance(part.func, ast.Attribute):
                if (relative == SOURCE_PATHS[0] and
                        re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", part.func.attr) and
                        any(fragment in part.func.attr.lower()
                            for fragment in ("invoice", "order", "intent", "reserve", "payment", "ledger"))):
                    checkout_call_targets.add(part.func.attr)
                if part.func.attr == "record_invoice":
                    external_calls.append({"caller": name,
                                           "import": "qualified.record_invoice"})
            else:
                dynamic_calls = True
    return {
        "file": relative,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "root_functions_found": [name for name in roots if name in functions],
        "root_functions_missing": [name for name in roots if name not in functions],
        "analyzed_local_functions": len(explored),
        "email_referencing_functions": sorted(set(email_functions)),
        "record_invoice_present": "record_invoice" in functions,
        "invoice_recorder_definition_count": names.count("record_invoice"),
        "start_handler_definition_count": names.count("_start_order"),
        "duplicate_functions": duplicate_functions,
        "invoice_import_calls": [
            x for x in external_calls if "invoice" in x["import"].lower()
            or "record" in x["import"].lower()
        ][:15],
        "dynamic_call_observed": dynamic_calls,
        "helper_limit_hit": len(explored) >= MAX_HELPERS,
        # Identifiers only, not function bodies, request fields, buyer data or secrets.
        "checkout_call_targets": sorted(checkout_call_targets)[:48],
        "orm_model_import_origins": model_import_origins[:12],
        "invoice_contracts": {
            key: safe_function_contract(functions[key])
            for key in ("_start_order", "record_invoice", "normalize_email")
            if key in functions and names.count(key) == 1
        } if relative in (SOURCE_PATHS[0], SOURCE_PATHS[4]) else {},
    }


def guest_delivery_schema_contract(raw: bytes) -> dict:
    """Inspect only the local GuestTrxDelivery class declaration.

    This cannot establish the physical MariaDB column, constraints, migration
    history, data quality, or runtime behavior. Never print defaults or data.
    """
    tree = ast.parse(raw.decode("utf-8"), filename=MODEL_SOURCE)
    models = [node for node in tree.body if isinstance(node, ast.ClassDef)
              and node.name == "GuestTrxDelivery"]
    if len(models) != 1:
        origins = []
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "GuestTrxDelivery":
                        origins.append({"module": node.module or "",
                                        "relative_level": node.level})
        return {"status": "CLASS_NOT_DEFINED_HERE", "class_count": len(models),
                "reexport_origins": origins[:8], "fields": {}}
    cls = models[0]
    fields = {}
    for node in cls.body:
        target = None
        value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        if not (isinstance(target, ast.Name) and
                target.id in ("email", "order") and
                isinstance(value, ast.Call)):
            continue
        constructor = value.func
        field_type = constructor.attr if isinstance(constructor, ast.Attribute) else (
            constructor.id if isinstance(constructor, ast.Name) else "UNKNOWN")
        flags = {"null": None, "blank": None, "unique": None,
                 "db_index": None}
        default_defined = False
        for kw in value.keywords:
            if kw.arg in flags and isinstance(kw.value, ast.Constant) and (
                    type(kw.value.value) is bool):
                flags[kw.arg] = kw.value.value
            if kw.arg == "default":
                default_defined = True
        fields[target.id] = {"field_type": field_type, "flags": flags,
                             "default_defined": default_defined}
    constraint_fields = set()
    for node in ast.walk(cls):
        if isinstance(node, ast.Call):
            ctor = node.func
            name = ctor.attr if isinstance(ctor, ast.Attribute) else (
                ctor.id if isinstance(ctor, ast.Name) else "")
            if name != "UniqueConstraint":
                continue
            for kw in node.keywords:
                if kw.arg == "fields" and isinstance(kw.value, (ast.List, ast.Tuple)):
                    for value in kw.value.elts:
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            if value.value in ("email", "order"):
                                constraint_fields.add(value.value)
    return {"status": "CLASS_DECLARATION_FOUND", "class_count": 1,
            "fields": fields,
            "declared_unique_constraint_fields": sorted(constraint_fields),
            "reexport_origins": []}


def inspect(root: Path = ROOT) -> dict:
    files = []
    missing = []
    for relative in SOURCE_PATHS:
        try:
            raw = source_bytes(root, relative)
            files.append(module_report(relative, raw))
        except (OSError, UnicodeError, ValueError, SyntaxError) as exc:
            missing.append({"file": relative, "reason": type(exc).__name__})
    schema = {"status": "MODEL_SOURCE_UNVERIFIED", "fields": {}}
    try:
        schema = guest_delivery_schema_contract(source_bytes(root, MODEL_SOURCE))
        schema["source_sha256"] = hashlib.sha256(source_bytes(root, MODEL_SOURCE)).hexdigest()
    except (OSError, ValueError, UnicodeError, SyntaxError) as exc:
        schema = {"status": "MODEL_SOURCE_UNVERIFIED",
                  "reason": type(exc).__name__, "fields": {}}
    template = {}
    try:
        raw = source_bytes(root, TEMPLATE)
        # Display only source indicators, never render text, tokens or buyer data.
        lowered = raw.lower()
        template = {
            "exists": True, "sha256": hashlib.sha256(raw).hexdigest(),
            "legacy_email_input_marker": b"mpw-buy-email" in lowered,
            "email_name_marker": b'name="email"' in lowered
                                  or b"name='email'" in lowered,
            "email_control_marker": template_email_controls(raw),
            "csrf_template_marker": b"csrf_token" in lowered
                                    or b"csrfmiddlewaretoken" in lowered,
        }
    except (OSError, ValueError) as exc:
        template = {"exists": False, "reason": type(exc).__name__}
    start = next((f for f in files if f["file"] == SOURCE_PATHS[0]), None)
    email_hits = [
        {"file": f["file"], "functions": f["email_referencing_functions"]}
        for f in files if f["file"] in (*SOURCE_PATHS[:3], SOURCE_PATHS[4])
        and f["email_referencing_functions"]
    ]
    guest = next((f for f in files if f["file"] == SOURCE_PATHS[3]), None)
    guest_email_indicators = (
        guest["email_referencing_functions"] if guest is not None else []
    )
    # Only the exact reviewed synthetic-email auth adapter may have internal
    # email schema identifiers without being called buyer-email collection.
    reviewed_guest_source = bool(
        guest is not None and guest["sha256"] == APPROVED_GUEST_SHA256
    )
    missing_start = not start or start["start_handler_definition_count"] != 1
    recorder_count = sum(f["invoice_recorder_definition_count"] for f in files
                         if f["file"] in (*SOURCE_PATHS[:3], SOURCE_PATHS[4]))
    missing_recorder = recorder_count == 0
    # An imported recorder is not a missing invoice implementation: it is
    # outside this limited read-only source scope until inspected separately.
    inspected_recorders = {
        name[:-3].replace("/", ".") + ".record_invoice"
        for name in (*SOURCE_PATHS[:3], SOURCE_PATHS[4])
    }
    external_recorder = any(
        any(isinstance(call, dict) and
            isinstance(call.get("import"), str) and
            call["import"].endswith(".record_invoice") and
            call["import"] not in inspected_recorders
            for call in file.get("invoice_import_calls", []))
        for file in files if file["file"] in (*SOURCE_PATHS[:3], SOURCE_PATHS[4])
    )
    duplicate_recorder = recorder_count > 1
    duplicate_functions = any(f["duplicate_functions"] for f in files)
    truncated_graph = any(f["helper_limit_hit"] for f in files
                          if f["file"] in (*SOURCE_PATHS[:3], SOURCE_PATHS[4]))
    email_template = bool(
        template.get("legacy_email_input_marker")
        or template.get("email_name_marker")
        or template.get("email_control_marker")
    )
    missing_csrf = not template.get("csrf_template_marker")
    status = ("SOURCE_MISSING_OR_UNREADABLE" if missing or not template.get("exists")
              else "DUPLICATE_SOURCE_FUNCTIONS" if duplicate_functions
              else "START_HANDLER_NOT_FOUND" if missing_start
              else "INVOICE_RECORDER_EXTERNAL_UNVERIFIED" if missing_recorder and external_recorder
              else "INVOICE_RECORDER_NOT_FOUND" if missing_recorder
              else "INVOICE_RECORDER_DUPLICATED" if duplicate_recorder
              else "EMAIL_REFERENCES_PRESENT" if email_hits
              else "LEGACY_EMAIL_CHECKOUT_PRESENT" if email_template
              else "CHECKOUT_CSRF_MARKER_MISSING" if missing_csrf
              else "UNREVIEWED_GUEST_SOURCE" if not reviewed_guest_source
              else "SOURCE_HELPER_GRAPH_TRUNCATED" if truncated_graph
              else "DIRECT_SOURCE_CLEAN_EXTERNAL_HELPERS_UNVERIFIED")
    return {
        "mode": "readonly_ast_no_import_no_db_no_payment",
        "status": status,
        "safe_to_deploy": False,
        "real_invoice_post_tested": False,
        "paid_receipt_download_tested": False,
        "files": files,
        "source_problems": missing,
        "template": template,
        "checkout_source_requires_email": email_template,
        "invoice_recorder_found": recorder_count == 1,
        "invoice_recorder_external_unverified": bool(missing_recorder and external_recorder),
        "invoice_recorder_definition_count": recorder_count,
        "csrf_template_marker_found": not missing_csrf,
        "email_hit_functions": email_hits,
        "guest_delivery_model_source": schema,
        "guest_source_matches_reviewed_digest": reviewed_guest_source,
        "guest_internal_email_indicators_review_required": guest_email_indicators,
        "external_invoice_code_proven_email_free": False,
    }


REPORT_PREFIX = "MPW_LIVE_INVOICE_SOURCE_AUDIT="


def validate_remote_report(output: str) -> int:
    """Fail closed on a cPanel diagnostic: source-only evidence cannot clear sales."""
    matches = [
        line[len(REPORT_PREFIX):] for line in output.splitlines()
        if line.startswith(REPORT_PREFIX)
    ]
    if len(matches) != 1 or len(matches[0]) > 160_000:
        print("MPW_SOURCE_GATE=BLOCKED_MISSING_OR_DUPLICATE_REPORT")
        return 20
    try:
        report = json.loads(matches[0])
    except (ValueError, TypeError):
        print("MPW_SOURCE_GATE=BLOCKED_INVALID_JSON")
        return 20
    if not isinstance(report, dict) or report.get("mode") != "readonly_ast_no_import_no_db_no_payment":
        print("MPW_SOURCE_GATE=BLOCKED_UNTRUSTED_REPORT_MODE")
        return 20
    status = report.get("status")
    if not isinstance(status, str) or re.fullmatch(r"[A-Z_]{3,80}", status) is None:
        print("MPW_SOURCE_GATE=BLOCKED_INVALID_SOURCE_STATUS")
        return 20
    # Bounded, data-minimal owner evidence from an authenticated SSH report.
    # Never print raw source or arbitrary report strings (which could contain
    # accidental credentials or customer data). Use only fixed known file keys.
    modules = report.get("files", [])
    modules = modules if isinstance(modules, list) else []
    expected = set(SOURCE_PATHS)
    safe_modules = []
    for item in modules:
        if not isinstance(item, dict) or item.get("file") not in expected:
            continue
        digest = item.get("sha256", "")
        digest = digest[:16] if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) else "INVALID"
        calls = item.get("checkout_call_targets", [])
        safe_calls = sorted({v for v in calls if isinstance(v, str) and
                             re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", v)})[:35] if isinstance(calls, list) else []
        imports = item.get("invoice_import_calls", [])
        safe_imports = sorted({
            entry["import"] for entry in imports if isinstance(entry, dict)
            and isinstance(entry.get("import"), str)
            and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*){0,7}",
                             entry["import"])
            and len(entry["import"]) <= 140
        })[:15] if isinstance(imports, list) else []
        email_functions = item.get("email_referencing_functions", [])
        safe_email_functions = sorted({
            value for value in email_functions
            if isinstance(value, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", value)
        })[:20] if isinstance(email_functions, list) else []
        candidate_contracts = item.get("invoice_contracts", {})
        candidate_contracts = candidate_contracts if isinstance(candidate_contracts, dict) else {}
        safe_contracts = {}
        for fn_name in ("_start_order", "record_invoice", "normalize_email"):
            if fn_name not in candidate_contracts:
                continue
            contract = candidate_contracts[fn_name]
            if not isinstance(contract, dict):
                continue
            args = contract.get("parameters", [])
            safe_args = []
            for arg in args[:24] if isinstance(args, list) else []:
                if (isinstance(arg, dict) and
                        isinstance(arg.get("name"), str) and
                        re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", arg["name"]) and
                        type(arg.get("required")) is bool and
                        arg.get("kind") in ("positional", "keyword_only")):
                    safe_args.append({"name": arg["name"], "kind": arg["kind"],
                                      "required": arg["required"]})
            flag_names = ("has_varargs", "has_varkw", "calls_normalize_email",
                          "calls_create", "calls_get_or_create", "calls_atomic",
                          "calls_reserve_commercial_intent", "raises_exception")
            orm_ops = contract.get("orm_operations", [])
            safe_orm_ops = []
            for op in orm_ops[:12] if isinstance(orm_ops, list) else []:
                if not isinstance(op, dict) or op.get("operation") not in (
                        "create", "filter", "get_or_create", "update_or_create"):
                    continue
                model = op.get("model")
                if not isinstance(model, str) or re.fullmatch(
                        r"[A-Za-z_][A-Za-z0-9_]{0,79}", model) is None:
                    continue
                safe_orm_ops.append({
                    "model": model, "operation": op["operation"],
                    "keyword_names": sorted({
                        x for x in (op.get("keyword_names") or [])[:20]
                        if isinstance(x, str) and re.fullmatch(
                            r"[A-Za-z_][A-Za-z0-9_]{0,79}", x)
                    }),
                    "default_field_names": sorted({
                        x for x in (op.get("default_field_names") or [])[:20]
                        if isinstance(x, str) and re.fullmatch(
                            r"[A-Za-z_][A-Za-z0-9_]{0,79}", x)
                    }),
                })
            attributes = contract.get("user_attribute_names", [])
            safe_attributes = sorted({
                x for x in (attributes or [])[:16]
                if isinstance(x, str) and re.fullmatch(
                    r"[A-Za-z_][A-Za-z0-9_]{0,79}", x)
            })
            safe_contracts[fn_name] = {
                "orm_operations": safe_orm_ops,
                "user_attribute_names": safe_attributes,
                "parameters": safe_args,
                "flags": {key: contract.get(key) is True for key in flag_names},
                "local_import_modules": sorted({
                    value for value in (contract.get("local_import_modules") or [])
                    if isinstance(value, str) and len(value) <= 120 and
                    re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*){0,6}", value)
                })[:16],
            }
        origins = item.get("orm_model_import_origins", [])
        safe_origins = []
        for origin in origins[:12] if isinstance(origins, list) else []:
            if not isinstance(origin, dict):
                continue
            model = origin.get("model")
            imported = origin.get("import_name")
            module = origin.get("module")
            level = origin.get("relative_level")
            if (not all(isinstance(v, str) and
                        re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", v)
                        for v in (model, imported)) or
                    not isinstance(module, str) or len(module) > 130 or
                    (module and re.fullmatch(
                        r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*){0,7}",
                        module) is None) or
                    type(level) is not int or not 0 <= level <= 4):
                continue
            safe_origins.append({"model": model, "import_name": imported,
                                 "module": module, "relative_level": level})
        safe_modules.append({"file": item["file"], "sha16": digest,
                             "orm_model_import_origins": safe_origins,
                             "invoice_function_contracts": safe_contracts,
                             "email_referencing_functions": safe_email_functions,
                             "invoice_imports": safe_imports,
                             "start_definitions": int(item.get("start_handler_definition_count", 0)) if type(item.get("start_handler_definition_count")) is int else None,
                             "recorder_definitions": int(item.get("invoice_recorder_definition_count", 0)) if type(item.get("invoice_recorder_definition_count")) is int else None,
                             "checkout_calls": safe_calls})
    template = report.get("template", {})
    template = template if isinstance(template, dict) else {}
    model = report.get("guest_delivery_model_source", {})
    model = model if isinstance(model, dict) else {}
    fields = model.get("fields", {})
    fields = fields if isinstance(fields, dict) else {}
    safe_fields = {}
    for key in ("email", "order"):
        info = fields.get(key, {})
        if not isinstance(info, dict):
            continue
        name = info.get("field_type", "")
        if not isinstance(name, str) or re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]{0,79}", name) is None:
            name = "UNKNOWN"
        flags = info.get("flags", {})
        flags = flags if isinstance(flags, dict) else {}
        safe_fields[key] = {
            "type": name,
            "explicit_flags": {flag: flags.get(flag) if type(flags.get(flag)) is bool
                               else None
                               for flag in ("null", "blank", "unique", "db_index")},
            "default_declared": info.get("default_defined") is True,
        }
    origins = model.get("reexport_origins", [])
    safe_origins = []
    for item in origins[:8] if isinstance(origins, list) else []:
        if (isinstance(item, dict) and
                isinstance(item.get("module"), str) and
                re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*){0,7}",
                             item["module"]) and
                type(item.get("relative_level")) is int and
                0 <= item["relative_level"] <= 4):
            safe_origins.append(item)
    model_digest = model.get("source_sha256", "")
    if not isinstance(model_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", model_digest):
        model_digest = ""
    safe_model = {
        "status": model.get("status") if model.get("status") in (
            "CLASS_DECLARATION_FOUND", "CLASS_NOT_DEFINED_HERE",
            "MODEL_SOURCE_UNVERIFIED") else "UNKNOWN",
        "source_sha16": model_digest[:16] if model_digest else "UNKNOWN",
        "fields": safe_fields,
        "declared_unique_constraint_fields": [
            x for x in ("email", "order")
            if x in (model.get("declared_unique_constraint_fields") or [])],
        "reexport_origins": safe_origins,
        "database_schema_verified": False,
    }
    print("MPW_SOURCE_EVIDENCE=" + json.dumps({
        "status": status,
        "guest_delivery_model": safe_model,
        "modules": safe_modules[:len(SOURCE_PATHS)],
        "source_problem_count": len(report.get("source_problems", [])) if isinstance(report.get("source_problems"), list) else None,
        "template_exists": template.get("exists") is True,
        "template_email_field": template.get("email_control_marker") is True,
        "template_csrf_marker": template.get("csrf_template_marker") is True,
        "guest_exact_reviewed_digest": report.get("guest_source_matches_reviewed_digest") is True,
        "paid_order_verified": False, "production_changed": False
    }, sort_keys=True))
    if status != "DIRECT_SOURCE_CLEAN_EXTERNAL_HELPERS_UNVERIFIED":
        print("MPW_SOURCE_GATE=BLOCKED_" + status)
        return 21
    # This diagnostic never authenticates a buyer or verifies settlement:
    # a clean static snapshot is not a commercial release decision.
    print("MPW_SOURCE_GATE=UNVERIFIED_EXTERNAL_HELPERS_AND_PAID_RECEIPT")
    return 22


def main() -> int:
    if sys.argv[1:] == ["--validate-report"]:
        return validate_remote_report(sys.stdin.read())
    if sys.argv[1:] and sys.argv[1:] != ["-"]:
        print("MPW_SOURCE_GATE=BLOCKED_INVALID_INVOCATION")
        return 20
    report = inspect()
    print(REPORT_PREFIX + json.dumps(report, sort_keys=True))
    # Remote source inspection is not a sale test. The *local* validator
    # must consume this report and fail until external obligations are proven.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
