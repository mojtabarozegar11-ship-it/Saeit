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
    # Owner policy: no buyer email at all for new guest checkout. Inspect
    # reachable identity helpers, not unrelated historic recovery functions.
    # CSP/rights checks remain mandatory and independent of this policy.
    funcs = {node.name: node for node in tree.body
             if isinstance(node, ast.FunctionDef)}
    # Follow only helpers that the guest identity path actually calls.  Email
    # validation in an unrelated/dead helper must not clear this indicator.
    roots = ('_identity', '_new_user', '_bind_guest_email', '_dispatch')
    reached = set()
    pending = list(roots)
    while pending:
        name = pending.pop()
        if name not in funcs or name in reached:
            continue
        reached.add(name)
        for node in ast.walk(funcs[name]):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in funcs and node.func.id not in reached):
                pending.append(node.func.id)
    identity_nodes = [funcs[name] for name in sorted(reached)]
    identity_calls = [node for fn in identity_nodes for node in ast.walk(fn)
                      if isinstance(node, ast.Call)]
    email_validator_seen = any(
        (isinstance(call.func, ast.Name) and call.func.id == 'validate_email')
        or (isinstance(call.func, ast.Attribute) and call.func.attr == 'validate_email')
        for call in identity_calls)
    aliases = {'email', 'buyer_email', 'customer_email',
               'purchase_email', 'purchaser_email'}

    def reads_post_email(fn: ast.FunctionDef) -> bool:
        # Recognize both POST.get("email") and the safer bounded loop over
        # all supported field names using POST.getlist(key), including a local
        # alias established by posted = getattr(request, "POST", None).
        bounded_variables = set()
        post_aliases = set()
        for node in ast.walk(fn):
            if (isinstance(node, ast.For) and isinstance(node.target, ast.Name)
                    and isinstance(node.iter, (ast.Tuple, ast.List))):
                values = {item.value for item in node.iter.elts
                          if isinstance(item, ast.Constant) and isinstance(item.value, str)}
                if {'email', 'buyer_email'}.issubset(values) and values.issubset(aliases):
                    bounded_variables.add(node.target.id)
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == 'getattr'
                    and len(node.value.args) >= 2
                    and isinstance(node.value.args[0], ast.Name)
                    and node.value.args[0].id == 'request'
                    and isinstance(node.value.args[1], ast.Constant)
                    and node.value.args[1].value == 'POST'):
                post_aliases.add(node.targets[0].id)
        for call in ast.walk(fn):
            if (not isinstance(call, ast.Call)
                    or not isinstance(call.func, ast.Attribute)
                    or call.func.attr not in ('get', 'getlist', '__getitem__')
                    or not call.args):
                continue
            direct_post = (isinstance(call.func.value, ast.Attribute)
                           and call.func.value.attr == 'POST'
                           and isinstance(call.func.value.value, ast.Name)
                           and call.func.value.value.id == 'request')
            aliased_post = (isinstance(call.func.value, ast.Name)
                            and call.func.value.id in post_aliases)
            if not (direct_post or aliased_post):
                continue
            key = call.args[0]
            if ((isinstance(key, ast.Constant) and key.value in aliases)
                    or (isinstance(key, ast.Name) and key.id in bounded_variables)):
                return True
        return False

    post_email_seen = any(reads_post_email(fn) for fn in identity_nodes)
    email_stored_seen = any(
        isinstance(node, ast.Attribute) and node.attr == 'email'
        and isinstance(node.ctx, ast.Store)
        for fn in identity_nodes for node in ast.walk(fn))
    email_before_invoice_source_indicators = (
        email_validator_seen and post_email_seen and email_stored_seen)
    email_recovery_wired = any(
        (isinstance(node, ast.ImportFrom)
         and node.module == 'services.mpw_trx_email_recovery')
        or (isinstance(node, ast.Import)
            and any(alias.name == 'services.mpw_trx_email_recovery'
                    for alias in node.names))
        or (isinstance(node, ast.Constant)
            and node.value == 'services.mpw_trx_email_recovery')
        or (isinstance(node, ast.Name) and node.id == 'bound_checkout')
        for node in ast.walk(tree))
    # Missing email is now the *required* guest state, not a sales blocker.
    # Any visible attempt to collect/store/validate it in guest checkout
    # blocks the release. Historical email-claim code is not inspected here.
    guest_email_policy_violation = (
        email_validator_seen or post_email_seen or email_stored_seen
        or email_recovery_wired)
    return {'guest_handler_found': True, 'commercial_db_checked': True,
            'merchant_receiver_checked': True, 'rights_gate_checked': True,
            'strict_guest_csp': True, 'orders_created': 0, 'payments_created': 0,
            'buyer_email_validator_in_identity_source': email_validator_seen,
            'buyer_email_post_read_in_identity_source': post_email_seen,
            'buyer_email_stored_in_identity_source': email_stored_seen,
            'buyer_email_before_invoice_source_indicators': email_before_invoice_source_indicators,
            'guest_email_policy': 'no_buyer_email',
            'guest_email_recovery_wiring_in_adapter': email_recovery_wired,
            'email_based_recovery_end_to_end': 'disabled_for_new_guest_orders',
            'checkout_template_email_input': 'not_examined',
            'commercial_email_block': 'GUEST_EMAIL_COLLECTION_OR_RECOVERY_WIRING'
                if guest_email_policy_violation else None,
            'read_only': True}


def main() -> int:
    if (TARGET.is_symlink() or not TARGET.is_file()
            or not 0 < TARGET.stat().st_size <= 256 * 1024):
        raise RuntimeError('GUEST_CHECKOUT_SOURCE_MISSING_OR_UNSAFE')
    raw = TARGET.read_bytes()
    result = audit_source(raw.decode('utf8'))
    result['source_sha256'] = hashlib.sha256(raw).hexdigest()
    print('MPW_GUEST_CHECKOUT_SECURITY_PREFLIGHT=' + json.dumps(result, sort_keys=True))
    if result['commercial_email_block']:
        raise RuntimeError(result['commercial_email_block'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
