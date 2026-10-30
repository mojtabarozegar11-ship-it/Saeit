#!/usr/bin/env python3
"""Read-only Zomorod Melal bank reconciliation and receivables/payables aging.

Not a bank connection, legal account statement, payment, or audit opinion.
Statement CSV uses *signed integer minor units* and unique provider references;
ledger doc_no must match the provider reference exactly to reconcile. Unmatched
items are never silently marked as settled.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
from pathlib import Path
import re
import sqlite3
from collections import defaultdict

ALLOWED_CURRENCIES = frozenset(('IRR', 'USD', 'EUR', 'AED'))
FIELDS = ('reference', 'date', 'currency', 'amount_minor')
PERMITTED_TABLES = {'journal_entries', 'journal_lines', 'ledger_accounts',
                    'invoices', 'invoice_payments'}
MAX_CSV_BYTES = 2_000_000
MAX_ROWS = 15_000


class InputRejected(ValueError):
    pass


def iso_date(value: str) -> dt.date:
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise InputRejected('invalid_date')
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise InputRejected('invalid_calendar_date') from exc


def parse_statement(content: bytes) -> list[dict]:
    if not content or len(content) > MAX_CSV_BYTES or b'\x00' in content:
        raise InputRejected('statement_size_or_encoding')
    try:
        body = content.decode('utf-8-sig', errors='strict')
        reader = csv.DictReader(io.StringIO(body, newline=''), restkey='__EXTRA__')
        if reader.fieldnames != list(FIELDS):
            raise InputRejected('statement_header_mismatch')
        result, seen = [], set()
        for row in reader:
            if len(result) >= MAX_ROWS:
                raise InputRejected('statement_row_limit')
            if '__EXTRA__' in row or any(row.get(k) is None for k in FIELDS):
                raise InputRejected('statement_invalid_fields')
            ref = row['reference'].strip()
            # Forbid spreadsheet formulas, control chars, unsafe identifier prefixes.
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', ref):
                raise InputRejected('statement_invalid_reference')
            currency = row['currency'].strip()
            if currency not in ALLOWED_CURRENCIES:
                raise InputRejected('statement_invalid_currency')
            date = iso_date(row['date'].strip())
            amount = row['amount_minor'].strip()
            if not re.fullmatch(r'-?(?:0|[1-9][0-9]{0,14})', amount):
                raise InputRejected('statement_invalid_amount')
            minor = int(amount)
            if not minor or abs(minor) > 100_000_000_000_000:
                raise InputRejected('statement_zero_or_oversize')
            identity = (ref, currency)
            if identity in seen:
                raise InputRejected('statement_duplicate_reference')
            seen.add(identity)
            result.append({'reference': ref, 'date': date, 'currency': currency,
                           'amount_minor': minor})
        if not result:
            raise InputRejected('statement_empty')
        return result
    except (UnicodeError, csv.Error) as exc:
        raise InputRejected('statement_invalid_csv') from exc


def open_readonly(path: Path) -> sqlite3.Connection:
    if path.is_symlink() or not path.is_file() or not path.is_absolute():
        raise InputRejected('existing_absolute_database_required')
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')  # One snapshot for all checks; never writes.
        names = {row['name'] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not PERMITTED_TABLES.issubset(names):
            raise InputRejected('missing_treasury_schema')
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise InputRejected('accounting_db_integrity_check_failed')
        if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise InputRejected('accounting_db_fk_check_failed')
        return connection
    except BaseException:
        connection.close()
        raise


def bank_ledger(db: sqlite3.Connection, bank_code: str, as_of: dt.date | None = None) -> dict:
    if not re.fullmatch(r'[0-9]{3,8}', bank_code):
        raise InputRejected('invalid_bank_ledger_code')
    bank = db.execute('SELECT id,type,active FROM ledger_accounts WHERE code=?',
                      (bank_code,)).fetchone()
    if bank is None or bank['type'] != 'asset' or not bank['active']:
        raise InputRejected('inactive_or_non_asset_bank_account')
    # All supporting journals must balance in their *own* currency. There is no
    # currency conversion or cross-currency netting in this basic ERP model.
    invalid = db.execute('''SELECT j.id FROM journal_entries j
        JOIN journal_lines l ON l.entry_id=j.id
        GROUP BY j.id,l.currency HAVING SUM(l.debit) != SUM(l.credit)
        OR SUM(l.debit)=0 OR SUM(l.credit)=0 LIMIT 1''').fetchone()
    if invalid is not None:
        raise InputRejected('unbalanced_journal_present')
    entries = {}
    for row in db.execute('''SELECT j.doc_no, j.doc_date, l.currency,
                                SUM(l.debit-l.credit) AS net_minor
        FROM journal_entries j JOIN journal_lines l ON l.entry_id=j.id
        WHERE l.account_id=? AND (? IS NULL OR j.doc_date <= ?)
        GROUP BY j.id,l.currency ORDER BY j.id''',
        (bank['id'], as_of.isoformat() if as_of else None, as_of.isoformat() if as_of else None)):
        ref=(row['doc_no'],row['currency'])
        if ref in entries:
            raise InputRejected('duplicate_document_reference')
        if row['currency'] not in ALLOWED_CURRENCIES:
            raise InputRejected('unsupported_ledger_currency')
        val=int(row['net_minor'])
        if val == 0:
            continue
        entries[ref]={'reference':row['doc_no'],'date':iso_date(row['doc_date']),
                      'currency':row['currency'],'amount_minor':val}
    return entries


def reconcile(db: sqlite3.Connection, statement: list[dict], bank_code: str = '1010',
              max_date_lag: int = 7, as_of: dt.date | None = None) -> dict:
    if not isinstance(max_date_lag, int) or not 0 <= max_date_lag <= 31:
        raise InputRejected('invalid_date_lag')
    if as_of is not None and any(item['date'] > as_of for item in statement):
        raise InputRejected('statement_contains_future_records')
    ledger=bank_ledger(db,bank_code,as_of)
    matched=[]; differences=[]; statement_only=[]
    lookup={}
    for item in statement:
        identity=(item['reference'],item['currency'])
        if identity in lookup:
            raise InputRejected('duplicate_statement_item')
        lookup[identity]=item
        corresponding=ledger.get(identity)
        if corresponding is None:
            statement_only.append(identity)
        elif (item['amount_minor'] != corresponding['amount_minor'] or
              abs((item['date'] - corresponding['date']).days)>max_date_lag):
            differences.append({'reference':item['reference'],'currency':item['currency'],
                'statement_amount_minor':item['amount_minor'],
                'ledger_amount_minor':corresponding['amount_minor'],
                'date_lag_days':abs((item['date'] - corresponding['date']).days)})
        else:
            matched.append(identity)
    ledger_only=[ident for ident in ledger if ident not in lookup]
    currencies=sorted(set(item['currency'] for item in statement) |
                      set(ident[1] for ident in ledger))
    by_currency={}
    for currency in currencies:
        statement_total=sum(item['amount_minor'] for item in statement if item['currency']==currency)
        ledger_total=sum(item['amount_minor'] for item in ledger.values() if item['currency']==currency)
        by_currency[currency]={
            'statement_net_minor':statement_total,
            'ledger_net_minor':ledger_total,
            'unreconciled_difference_minor':statement_total-ledger_total,
            'matched_count':sum(x[1]==currency for x in matched),
        }
    status='BALANCED_MATCHED' if not (differences or statement_only or ledger_only) else 'REVIEW_REQUIRED'
    return {'status':status,'read_only':True,'bank_account_code':bank_code,
        'matched_count':len(matched), 'statement_only_count':len(statement_only),
        'ledger_only_count':len(ledger_only),'mismatch_count':len(differences),
        'mismatches':sorted(differences,key=lambda x:(x['currency'],x['reference'])),
        'statement_only':[{'reference':a,'currency':b} for a,b in sorted(statement_only)],
        'ledger_only':[{'reference':a,'currency':b} for a,b in sorted(ledger_only)],
        'currency_totals':by_currency,'represents_real_bank_authorization':False}


def aging(db: sqlite3.Connection, as_of: dt.date) -> dict:
    buckets=('not_due','days_1_30','days_31_60','days_61_90','days_over_90')
    result={'sale':{},'purchase':{}}
    for row in db.execute('''SELECT i.id,i.kind,i.invoice_date,i.due_date,i.amount,i.currency,
        COALESCE((SELECT SUM(p.amount) FROM invoice_payments p
                  WHERE p.invoice_id=i.id AND p.paid_on<=?),0) AS paid
        FROM invoices i WHERE i.invoice_date<=? ORDER BY i.id''',
        (as_of.isoformat(),as_of.isoformat())):
        if row['kind'] not in result or row['currency'] not in ALLOWED_CURRENCIES:
            raise InputRejected('invalid_invoice_classification')
        if iso_date(row['invoice_date'])>as_of:
            continue
        due=iso_date(row['due_date'])
        paid=int(row['paid']); amount=int(row['amount'])
        if amount<=0 or paid<0 or paid>amount:
            raise InputRejected('invalid_invoice_paid_balance')
        remaining=amount-paid
        if not remaining:continue
        days=(as_of-due).days
        bucket=('not_due' if days<=0 else 'days_1_30' if days<=30 else
                'days_31_60' if days<=60 else 'days_61_90' if days<=90 else 'days_over_90')
        data=result[row['kind']].setdefault(row['currency'], {b:0 for b in buckets})
        data[bucket]+=remaining
    for category in result:
        for currency in result[category]:
            result[category][currency]['total']=sum(result[category][currency][b] for b in buckets)
    return {'as_of':as_of.isoformat(),'receivables_payables_minor':result,
            'is_cash_forecast':False,'legal_audit':False,'read_only':True}


def run(db_path: Path, statement_path: Path, as_of: str, bank_code: str='1010') -> dict:
    date=iso_date(as_of)
    if statement_path.is_symlink() or not statement_path.is_file():
        raise InputRejected('missing_statement_file')
    if statement_path.stat().st_size > MAX_CSV_BYTES:
        raise InputRejected('oversize_statement')
    statement=parse_statement(statement_path.read_bytes())
    db=open_readonly(db_path)
    try:
        outcome={'reconciliation':reconcile(db,statement,bank_code,as_of=date),
                 'aging':aging(db,date),'source':'offline_only_not_bank_connected'}
        db.execute('COMMIT')
        return outcome
    except BaseException:
        if db.in_transaction:db.execute('ROLLBACK')
        raise
    finally:
        db.close()


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('accounting_sqlite',type=Path)
    p.add_argument('statement_csv',type=Path)
    p.add_argument('--as-of',required=True)
    p.add_argument('--bank-code',default='1010')
    args=p.parse_args()
    try:
        result=run(args.accounting_sqlite.resolve(),args.statement_csv.resolve(),args.as_of,args.bank_code)
        print(json.dumps(result,ensure_ascii=False,sort_keys=True))
        return 0 if result['reconciliation']['status']=='BALANCED_MATCHED' else 2
    except (InputRejected,sqlite3.Error,OSError):
        print(json.dumps({'status':'NOT_VERIFIED','read_only':True,'details_exposed':False}))
        return 3


if __name__=='__main__':
    raise SystemExit(main())