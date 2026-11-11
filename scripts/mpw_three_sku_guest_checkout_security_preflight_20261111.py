#!/usr/bin/env python3
"""Read-only security preflight for the actual guest TRX checkout route.

The owner-rights release must not depend on a source-string patch for the
unrelated authenticated-book checkout. This check inspects the deployed guest
route instead, and fails closed if the rights gate or its strict CSP is absent.
No database connection, invoice, payment, source edit, or restart is made.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


TARGET = Path('/home/zomorod2/Saeit-staging/services/mpw_trx_guest_commerce.py')
REQUIRED_CSP = (
    "default-src 'self'",
    "script-src 'none'",
    "form-action 'self'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
)


def audit_source(source: str) -> dict:
    tree = ast.parse(source)
    handlers = [node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == '_checkout_page']
    if len(handlers) != 1:
        raise RuntimeError('GUEST_CHECKOUT_HANDLER_MISSING_OR_DUPLICATED')
    handler = handlers[0]
    calls = [node for node in ast.walk(handler) if isinstance(node, ast.Call)]

    def has_call(name: str) -> bool:
        return any(isinstance(node.func, ast.Name) and node.func.id == name
                   for node in calls)

    for name in ('_host_ok', '_commercial_db', '_configured_receiver',
                 '_eligible', 'rights_cleared_for_sale'):
        if not has_call(name):
            raise RuntimeError('GUEST_CHECKOUT_SECURITY_CALL_MISSING:' + name)
    rights_denial_guard = False
    for node in ast.walk(handler):
        if not isinstance(node, ast.If):
            continue
        denies_rights = any(
            isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not)
            and isinstance(expr.operand, ast.Call)
            and isinstance(expr.operand.func, ast.Name)
            and expr.operand.func.id == 'rights_cleared_for_sale'
            for expr in ast.walk(node.test))
        denies_checkout = any(
            isinstance(stmt, ast.Raise) and isinstance(stmt.exc, ast.Name)
            and stmt.exc.id == 'Http404' for stmt in node.body)
        if denies_rights and denies_checkout:
            rights_denial_guard = True
            break
    if not rights_denial_guard:
        raise RuntimeError('GUEST_RIGHTS_DENIAL_GUARD_NOT_ENFORCED')
    csp_values = []
    for node in ast.walk(handler):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Subscript) or not isinstance(target.value, ast.Name):
            continue
        if target.value.id != 'response':
            continue
        if not isinstance(target.slice, ast.Constant) or target.slice.value != 'Content-Security-Policy':
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            raise RuntimeError('GUEST_CSP_NOT_STATIC_AND_AUDITABLE')
        csp_values.append(node.value.value)
    if len(csp_values) != 1:
        raise RuntimeError('GUEST_STRICT_CSP_NOT_SET_EXACTLY_ONCE')
    policy = csp_values[0]
    directives = {part.strip() for part in policy.split(';') if part.strip()}
    script_directives = [d for d in directives if d.startswith('script-src ')]
    if (not set(REQUIRED_CSP).issubset(directives)
            or len(script_directives) != 1
            or "'unsafe-inline'" in script_directives[0]
            or "'unsafe-eval'" in script_directives[0]):
        raise RuntimeError('GUEST_CSP_SECURITY_DIRECTIVES_INCOMPLETE')
    return {'guest_handler_found': True, 'commercial_db_checked': True,
            'merchant_receiver_checked': True, 'rights_gate_checked': True,
            'strict_guest_csp': True, 'orders_created': 0, 'payments_created': 0,
            'read_only': True}


def main() -> int:
    if (TARGET.is_symlink() or not TARGET.is_file()
            or not 0 < TARGET.stat().st_size <= 256 * 1024):
        raise RuntimeError('GUEST_CHECKOUT_SOURCE_MISSING_OR_UNSAFE')
    raw = TARGET.read_bytes()
    result = audit_source(raw.decode('utf8'))
    result['source_sha256'] = hashlib.sha256(raw).hexdigest()
    print('MPW_GUEST_CHECKOUT_SECURITY_PREFLIGHT=' + json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
