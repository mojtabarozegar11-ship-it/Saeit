#!/usr/bin/env python3
"""Independent read-only synthetic/accounting reconciliation for the basic ZM ledger.

No changes to company data. A clean result validates only the listed internal
posting templates, NOT financial statements, tax compliance or a bank balance.
"""
from __future__ import annotations
import argparse
import json
import sqlite3
from pathlib import Path

INVOICE_TEMPLATE = {'sale': ('1100', '4000'), 'purchase': ('1200', '2000')}
PAYMENT_TEMPLATE = {'sale': ('1010', '1100'), 'purchase': ('2000', '1010')}
TABLES = ('ledger_accounts', 'journal_entries', 'journal_lines',
          'invoices', 'invoice_payments', 'inventory', 'inventory_movements')


def audit(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError('Explicit existing SQLite file required')
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=10)
    db.row_factory = sqlite3.Row
    result = {k: 0 for k in (
        'integrity', 'foreign_keys', 'unbalanced_entries', 'too_few_lines',
        'invoice_posting_mismatch', 'payment_posting_mismatch',
        'overpaid_invoices', 'negative_stock', 'posting_reuse', 'historical_negative_stock')}
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')  # Snapshot: one consistent view across every check.
        actual = {r['name'] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not set(TABLES).issubset(actual):
            raise ValueError('Required accounting schema missing')
        result['integrity'] = int(db.execute('PRAGMA quick_check').fetchone()[0] != 'ok')
        result['foreign_keys'] = len(db.execute('PRAGMA foreign_key_check').fetchall())
        for entry in db.execute('SELECT id FROM journal_entries ORDER BY id'):
            lines = list(db.execute('SELECT currency,debit,credit FROM journal_lines WHERE entry_id=?', (entry['id'],)))
            if len(lines) < 2:
                result['too_few_lines'] += 1
            by_currency: dict[str, list[int]] = {}
            for line in lines:
                pair = by_currency.setdefault(line['currency'], [0, 0])
                pair[0] += line['debit']; pair[1] += line['credit']
            if not by_currency or any(dr <= 0 or cr <= 0 or dr != cr for dr, cr in by_currency.values()):
                result['unbalanced_entries'] += 1
        # Basic seeded account templates: exact two-lines, one currency, posting date.
        def matches(entry_id: int, date: str, currency: str, amount: int, template: tuple[str, str]) -> bool:
            rows = db.execute('''SELECT j.doc_date,l.currency,l.debit,l.credit,a.code
                FROM journal_entries j JOIN journal_lines l ON l.entry_id=j.id
                JOIN ledger_accounts a ON a.id=l.account_id WHERE j.id=?''', (entry_id,)).fetchall()
            return (len(rows) == 2 and all(r['doc_date'] == date and r['currency'] == currency for r in rows)
                    and sorted((r['code'],r['debit'],r['credit']) for r in rows) ==
                    sorted(((template[0],amount,0),(template[1],0,amount))))
        for invoice in db.execute('SELECT id,kind,invoice_date,amount,currency,posted_entry FROM invoices ORDER BY id'):
            template = INVOICE_TEMPLATE.get(invoice['kind'])
            if not template or not matches(invoice['posted_entry'], invoice['invoice_date'], invoice['currency'], invoice['amount'],template):
                result['invoice_posting_mismatch'] += 1
            paid = db.execute('SELECT COALESCE(SUM(amount),0) FROM invoice_payments WHERE invoice_id=?', (invoice['id'],)).fetchone()[0]
            if paid > invoice['amount'] or paid < 0: result['overpaid_invoices'] += 1
        for payment in db.execute('''SELECT p.amount,p.paid_on,p.entry_id,i.kind,i.currency
            FROM invoice_payments p JOIN invoices i ON i.id=p.invoice_id ORDER BY p.id'''):
            template=PAYMENT_TEMPLATE.get(payment['kind'])
            if not template or not matches(payment['entry_id'],payment['paid_on'],payment['currency'],payment['amount'],template):
                result['payment_posting_mismatch'] += 1
        # Even a perfectly balanced document cannot substantiate two separate invoices.
        # Verify uniqueness across BOTH source document families, not only inside each.
        for reused in db.execute('''SELECT entry_id,COUNT(*) AS use_count FROM (
            SELECT posted_entry AS entry_id FROM invoices
            UNION ALL SELECT entry_id FROM invoice_payments
        ) GROUP BY entry_id HAVING COUNT(*) > 1'''):
            result['posting_reuse'] += 1
        # Verify all historical stock prefixes, not merely the final balance.
        # A later receipt must not hide an earlier negative stock ledger.
        for stock in db.execute('''SELECT i.id,COALESCE(SUM(m.qty),0) AS qty
            FROM inventory i LEFT JOIN inventory_movements m ON m.inventory_id=i.id GROUP BY i.id'''):
            if stock['qty'] < 0:result['negative_stock'] += 1
        movement_columns={c[1] for c in db.execute('PRAGMA table_info(inventory_movements)')}
        stock_order='movement_date,id' if 'movement_date' in movement_columns else 'id'
        for stock in db.execute('SELECT id FROM inventory'):
            qty=0; ever_negative=False
            for movement in db.execute('SELECT qty FROM inventory_movements WHERE inventory_id=? ORDER BY '+stock_order, (stock['id'],)):
                qty+=int(movement['qty'])
                if qty<0:ever_negative=True
            if ever_negative:result['historical_negative_stock']+=1
        db.execute('COMMIT')
        return {'status':'PASS_CHECKED_INVARIANTS' if not any(result.values()) else 'FAIL_REQUIRES_INVESTIGATION',
                'issues':result, 'readonly':True, 'financial_audit_opinion':False}
    except BaseException:
        if db.in_transaction:db.execute('ROLLBACK')
        raise
    finally:
        db.close()


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sqlite_database',type=Path)
    options=parser.parse_args()
    try:
        result=audit(options.sqlite_database)
        print(json.dumps(result,sort_keys=True))
        return 0 if result['status']=='PASS_CHECKED_INVARIANTS' else 2
    except (ValueError, sqlite3.Error, OSError):
        print(json.dumps({'status':'NOT_VERIFIED','readonly':True}))
        return 3


if __name__ == '__main__':raise SystemExit(main())
