#!/usr/bin/env python3
"""Metadata-only MojPlayWin staging readiness check. NO DATABASE WRITES.

Outputs booleans and public route identifiers, never credentials, addresses,
customer data, amounts, database names or private file paths.
"""
import json
import os
import re
import sys
from pathlib import Path

STAGE = Path('/home/zomorod2/Saeit-staging')
ROOT = Path('/home/zomorod2/mojplaywin.com')


def check():
    if STAGE.is_symlink() or ROOT.is_symlink() or not STAGE.is_dir():
        raise RuntimeError('Unexpected cPanel staging environment')
    passenger = ROOT / 'passenger_wsgi.py'
    if passenger.is_symlink() or not passenger.is_file():
        raise RuntimeError('Passenger root not verified')
    if "APP='/home/zomorod2/Saeit-staging'" not in passenger.read_text('utf8', 'replace'):
        raise RuntimeError('Passenger source does not match expected staging code')

    os.chdir(STAGE)
    sys.path.insert(0, str(STAGE))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    from django.conf import settings
    from django.db import connection
    from django.db.models import UniqueConstraint
    from django.urls import resolve
    from django.apps import apps
    from core.models import Order, OrderItem, PaymentIntent, LedgerEntry, PaymentWebhookEvent
    from mpw_commerce.models import CommerceInvoice, CommerceReceipt, CommerceFulfillment

    names = set(connection.introspection.table_names())
    db_name = str(connection.settings_dict.get('NAME', ''))
    invoice_fields = {f.name for f in CommerceInvoice._meta.get_fields()}
    receipt_fields = {f.name for f in CommerceReceipt._meta.get_fields()}
    order_fields = {f.name for f in Order._meta.get_fields()}
    ledger_fields = {f.name for f in LedgerEntry._meta.get_fields()}
    fulfillment_fields = {f.name for f in CommerceFulfillment._meta.get_fields()}
    with connection.cursor() as cur:
        cur.execute('SHOW DATABASES')  # metadata only; do not print names
        schemas = [str(row[0]) for row in cur.fetchall()]
        cur.execute('SHOW GRANTS')  # read only; do not print grant strings
        grants = [str(row[0]).upper() for row in cur.fetchall()]
    test_dbs = sum(name.lower().startswith('test_') for name in schemas)
    may_create_db = any(' ON *.* ' in item and (
        'ALL PRIVILEGES' in item or 'CREATE' in item) for item in grants)
    # DDL on the *existing* schema is distinct from global CREATE DATABASE.
    # Read grants, not data rows. Do not print account/db identifiers.
    safe_name = re.escape(db_name.upper())
    current_scopes = re.compile(r'\bON\s+(?:`?' + safe_name + r'`?)\.\*\s+TO\b')
    scoped = [g for g in grants if current_scopes.search(g)]
    globals_ = [g for g in grants if ' ON *.* TO ' in g]
    relevant_grants = scoped + globals_
    can_create_table = any('ALL PRIVILEGES' in g or
        re.search(r'\bCREATE\b', g.split(' ON ', 1)[0]) for g in relevant_grants)
    can_alter_table = any('ALL PRIVILEGES' in g or
        re.search(r'\bALTER\b', g.split(' ON ', 1)[0]) for g in relevant_grants)
    native_model_fields = {}
    native_field_nullability = {}
    native_has_records = {}
    for model_name in ('NativeInvoice', 'NativeChainTransfer', 'MerchantWalletProof'):
        try:
            native = apps.get_model('mpw_native_checkout', model_name)
            native_model_fields[model_name] = [f.name for f in native._meta.fields][:40]
            native_has_records[model_name] = native.objects.exists()
            native_field_nullability[model_name] = {
                f.name: bool(f.null) for f in native._meta.fields
                if f.name in ('verified_sender_address','wallet_challenge',
                    'sender_signature_verified_at','merchant_ownership_verified_at',
                    'invoice','tx_hash','amount_atomic')
            }
        except LookupError:
            native_model_fields[model_name] = []
            native_has_records[model_name] = False
            native_field_nullability[model_name] = {}

    def reusable_table_shape(model):
        # Only Django declared constraints and field names, no customer rows.
        return {
            'fields': [f.name for f in model._meta.fields],
            'unique_fields': [f.name for f in model._meta.fields if f.unique],
            'unique_together': [list(x) for x in model._meta.unique_together],
            'explicit_unique_constraints': [list(c.fields)
                for c in model._meta.constraints if isinstance(c,UniqueConstraint)],
            'indexed_fields': [f.name for f in model._meta.fields if f.db_index],
            'nullable_business_fields': {f.name: bool(f.null) for f in model._meta.fields
                if f.name in ('expected_sender','sender_challenge','sender_challenge_id',
                    'sender_signature_verified_at','verified_sender_address',
                    'payment_intent','recipient','amount_atomic','invoice',
                    'tx_hash','reference','metadata','provider_reference')},
            'status_values': list(dict(model._meta.get_field('status').choices or []).keys())
                if any(f.name=='status' for f in model._meta.fields) else [],
        }

    try:
        checkout = resolve('/store/product/72/checkout/')
        checkout_module = str(getattr(checkout.func, '__module__', ''))
    except Exception:
        checkout_module = ''

    # Only present/absent configuration signals; never log keys or addresses.
    possible_cred_names = (
        'TRON_PRO_API_KEY', 'TRONGRID_API_KEY', 'NODIT_API_KEY',
        'MPW_TRON_RPC_PRIMARY_API_KEY', 'MPW_TRON_RPC_SECONDARY_API_KEY',
    )
    configured_cred_count = sum(bool(os.environ.get(k)) for k in possible_cred_names)
    dual_rpc_required = (
        'MPW_TRON_RPC_A_SOURCE_ID', 'MPW_TRON_RPC_A_OPERATOR_ID',
        'MPW_TRON_RPC_A_ENDPOINT', 'MPW_TRON_RPC_A_API_KEY',
        'MPW_TRON_RPC_A_AUTH_HEADER', 'MPW_TRON_RPC_B_SOURCE_ID',
        'MPW_TRON_RPC_B_OPERATOR_ID', 'MPW_TRON_RPC_B_ENDPOINT',
        'MPW_TRON_RPC_B_API_KEY', 'MPW_TRON_RPC_B_AUTH_HEADER',
    )
    dual_rpc_canary = (
        'MPW_TRON_RPC_CANARY_TXID', 'MPW_TRON_RPC_CANARY_SENDER',
        'MPW_TRON_RPC_CANARY_RECEIVER', 'MPW_TRON_RPC_CANARY_AMOUNT_SUN',
    )
    return {
        'probe': 'READ_ONLY_GATEWAY_STAGING_CONTRACT',
        'db_backend_mysql': connection.vendor == 'mysql',
        'db_name_is_isolated_test_prefix': db_name.lower().startswith('test_'),
        'stage_models_loaded': True,
        'walletless_table_count': sum(name in names for name in (
            'mpw_walletless_trx_allocator_v1',
            'mpw_walletless_trx_reservation_v1',
            'mpw_walletless_trx_receipt_v1',
            'mpw_walletless_trx_guest_claim_v1',
        )),
        'legacy_invoice_signing_fields': {
            field: field in invoice_fields for field in (
                'expected_sender', 'sender_challenge', 'sender_signature_verified_at')},
        'real_model_contracts': {
            'order_owner_status_currency': {'customer', 'status', 'currency'} <= order_fields,
            'receipt_invoice_network_tx': {'invoice', 'network', 'tx_hash'} <= receipt_fields,
            'ledger_order_reference_metadata': {'order', 'reference', 'metadata'} <= ledger_fields,
            'fulfillment_item_kind_status': {'item', 'kind', 'status'} <= fulfillment_fields,
            'invoice_order_recipient_amount': {'order', 'recipient', 'amount_atomic'} <= invoice_fields,
        },
        'isolated_test_db_visible_count': test_dbs,
        'privilege_to_create_new_db_detected': may_create_db,
        'existing_schema_create_table_grant_detected': bool(can_create_table),
        'existing_schema_alter_table_grant_detected': bool(can_alter_table),
        'native_checkout_model_fields': native_model_fields,
        'native_checkout_field_nullable': native_field_nullability,
        'native_checkout_has_existing_records': native_has_records,
        'existing_financial_table_shapes': {
            'PaymentIntent': reusable_table_shape(PaymentIntent),
            'LedgerEntry': reusable_table_shape(LedgerEntry),
            'PaymentWebhookEvent': reusable_table_shape(PaymentWebhookEvent),
            'CommerceInvoice': reusable_table_shape(CommerceInvoice),
            'CommerceReceipt': reusable_table_shape(CommerceReceipt),
        },
        'no_ddl_walletless_model_tables_present': all(
            model._meta.db_table in names for model in (
                Order, OrderItem, PaymentIntent, LedgerEntry, PaymentWebhookEvent,
                CommerceFulfillment, CommerceInvoice, CommerceReceipt)),
        'commerce_execution_flags': {flag: bool(getattr(settings, flag, False)) for flag in (
            'MPW_COMMERCE_RELEASE_READY',
            'MPW_COMMERCE_REAL_RPC_ENABLED',
            'MPW_COMMERCE_AUTORECONCILE_ENABLED',
            'MPW_COMMERCE_INVOICING_ENABLED',
            'MPW_COMMERCE_SETTLEMENT_ENABLED',
            'MPW_COMMERCE_DOWNLOADS_ENABLED',
            'MPW_COMMERCE_BUYER_SIGNATURE_ENABLED',
        )},
        'all_core_model_checks': all((
            {'customer', 'status', 'currency'} <= order_fields,
            {'invoice', 'network', 'tx_hash'} <= receipt_fields,
            {'order', 'reference', 'metadata'} <= ledger_fields,
            {'item', 'kind', 'status'} <= fulfillment_fields,
            {'order', 'recipient', 'amount_atomic'} <= invoice_fields,
        )),
        'checkout_django_handler_found': bool(checkout_module),
        'merchant_rpc_credential_candidates_present': configured_cred_count,
        'dual_rpc_config_fields_all_present': all(bool(os.environ.get(k)) for k in dual_rpc_required),
        'dual_rpc_canary_fields_all_present': all(bool(os.environ.get(k)) for k in dual_rpc_canary),
        'dual_rpc_independence_reviewed': os.environ.get('MPW_TRON_RPC_INDEPENDENCE_REVIEWED') == '1',
        'feature_flag_public_walletless': bool(getattr(settings,
            'MPW_WALLETLESS_TRX_PUBLIC_ENABLED', False)),
        'feature_flag_test_adapter': bool(getattr(settings,
            'MPW_WALLETLESS_TRX_TEST_ADAPTER', False)),
        'no_sql_mutation': True,
        'no_customer_data_collected': True,
        'no_financial_writes': True,
    }


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
