#!/usr/bin/env python3
"""Read-only inventory of the existing MojPlayWin cPanel checkout source.

Reads a fixed, allowlisted set of Python source files from the verified staging
application root; no imports of application modules, Django initialization,
network requests, customer data, invoice access, checkout, file writes, or
wallet operations. Outputs only booleans and source-file SHA256 fingerprints.
"""
from __future__ import annotations

import ast
import hashlib
import json
import stat
from pathlib import Path

HOST_ROOT = Path('/home/zomorod2/Saeit-staging')
MAX_BYTES = 256 * 1024
EXPECTED = {
    'mpw_commerce/checkout_views.py': ('checkout_challenge', 'checkout_verify_signature', 'checkout_invoice', 'checkout_status'),
    'mpw_commerce/product_checkout_page.py': ('product_checkout_page',),
    'mpw_commerce/purchase_history.py': ('purchased_downloads',),
    'mpw_commerce/customer_auth.py': ('CustomerLogin', 'CustomerLogout', 'customer_register'),
    'mpw_commerce/policy.py': ('order_snapshot', 'CommercePolicyError'),
    'mpw_commerce/entitlements.py': ('can_access_purchased_digital_item',),
    'mpw_commerce/downloads.py': ('download_paid_item',),
    'mpw_commerce/urls.py': ('urlpatterns',),
    'services/mpw_trx_public_pages.py': (),
    'services/mpw_trx_commercial_web.py': (),
}
PREFIX = 'MPW_CPAN_MODULE_SOURCE_INVENTORY='


def exports_from_ast(tree):
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != '*':
                    names.add(alias.asname or alias.name)
    return names


def inspect_module(root, relative, required):
    result = {'present': False, 'regular': False, 'parseable': False,
              'exports_present': False, 'sha256': None}
    candidate = root
    for segment in Path(relative).parts:
        candidate = candidate / segment
        if candidate.is_symlink():
            return result
    try:
        if not candidate.is_file():
            return result
        result['present'] = True
        info = candidate.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            return result
        result['regular'] = True
        raw = candidate.read_bytes()
        if len(raw) > MAX_BYTES:
            return result
        text = raw.decode('utf-8')
        tree = ast.parse(text, filename=relative)
        result['parseable'] = True
        result['exports_present'] = all(name in exports_from_ast(tree) for name in required)
        result['sha256'] = hashlib.sha256(raw).hexdigest()
    except (OSError, UnicodeError, SyntaxError, ValueError):
        pass
    return result


def inspect_root(root):
    output = {'schema': 'mpw.cpanel.checkout.module-inventory.readonly.v1',
              'read_only': True, 'customer_data_read': False,
              'application_modules_imported': False,
              'payment_or_invoice_created': False,
              'host_changed': False,
              'root_valid': False, 'modules': {}}
    try:
        valid = (root == HOST_ROOT or root.name == 'fixture_checkout_root')
        valid = (valid and root.is_dir() and not root.is_symlink()
                 and root.resolve() == root)
        if not valid:
            return output
        output['root_valid'] = True
        for relative, required in EXPECTED.items():
            output['modules'][relative] = inspect_module(root, relative, required)
        output['four_customer_view_sources_present'] = all(
            output['modules'][x]['present'] for x in tuple(EXPECTED)[:4]
        )
        output['four_customer_view_exports_present'] = all(
            output['modules'][x]['exports_present'] for x in tuple(EXPECTED)[:4]
        )
    except (OSError, ValueError):
        output['root_valid'] = False
        output['modules'] = {}
    return output


def main():
    print(PREFIX + json.dumps(inspect_root(HOST_ROOT), sort_keys=True, separators=(',', ':')))


if __name__ == '__main__':
    main()
