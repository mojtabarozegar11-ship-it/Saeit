"""Bounded, read-only incoming TRX discovery for reserved invoice addresses.

Only final, independent solidity proofs may mark a transaction paid. TronGrid's
address-history index is discovery ONLY. No withdrawals, signing or broadcasts.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .core import CheckoutError, TXID_PATTERN, SOLIDITY_GRACE_MS, tron_address_hex
from .rpc import MAINNET_SOLIDITY, finalized_records


def incoming_candidates(address: str, issued_ms: int, expires_ms: int, *, opener=urlopen,
                        api_key='', max_pages=3) -> list[str]:
    """Get all confirmed inbound hashes in an invoice's bounded time window.

    A truncated/incomplete index response NEVER certifies that there was no payment.
    """
    tron_address_hex(address)
    if not (type(issued_ms) is int and type(expires_ms) is int and
            0 < issued_ms < expires_ms <= issued_ms + 600000):
        raise CheckoutError('Invalid address-history scan window')
    if type(max_pages) is not int or not 1 <= max_pages <= 8:
        raise CheckoutError('Invalid scan page bound')
    filters = {
        'only_confirmed': 'true', 'only_to': 'true', 'min_timestamp': str(issued_ms - 120000),
        'max_timestamp': str(expires_ms + SOLIDITY_GRACE_MS),
        'order_by': 'block_timestamp,asc', 'limit': '200',
    }
    headers = {'Accept': 'application/json', 'User-Agent': 'MojPlayWin-TRON-Discovery/1'}
    if api_key:
        if not isinstance(api_key, str) or len(api_key) > 512 or '\n' in api_key:
            raise CheckoutError('Invalid API key')
        headers['TRON-PRO-API-KEY'] = api_key
    seen, found = set(), []
    fingerprint = None
    for page in range(max_pages):
        params = filters.copy()
        if fingerprint is not None:
            params['fingerprint'] = fingerprint
        url = MAINNET_SOLIDITY + '/v1/accounts/' + address + '/transactions?' + urlencode(params)
        req = Request(url, headers=headers, method='GET')
        try:
            with opener(req, timeout=12) as response:
                if getattr(response, 'status', 200) != 200:
                    raise CheckoutError('TRON indexer unavailable')
                raw = response.read(524289)
            if len(raw) > 524288:
                raise CheckoutError('Address history response too large')
            result = json.loads(raw.decode('utf8'))
        except (OSError, ValueError, UnicodeError) as exc:
            raise CheckoutError('TRON indexer not verifiable') from exc
        if (not isinstance(result, dict) or result.get('success') is not True or
            not isinstance(result.get('data'), list) or len(result['data']) > 200 or
            not isinstance(result.get('meta'), dict)):
            raise CheckoutError('Malformed TRON indexer result')
        for item in result['data']:
            if not isinstance(item, dict) or not isinstance(item.get('txID'), str) or not TXID_PATTERN.fullmatch(item['txID'].lower()):
                raise CheckoutError('Invalid discovered TRON transaction')
            txid = item['txID'].lower()
            if txid not in seen:
                found.append(txid)
                seen.add(txid)
        next_page = result['meta'].get('fingerprint')
        if not next_page or not result['data']:
            return found
        if not isinstance(next_page, str) or not 1 <= len(next_page) <= 512 or not re.fullmatch(r'[A-Za-z0-9_+./=-]+', next_page):
            raise CheckoutError('Malformed pagination cursor')
        if next_page == fingerprint:
            raise CheckoutError('Repeated pagination cursor')
        fingerprint = next_page
    raise CheckoutError('Address history exceeds bounded page limit; manual review required')


def reconcile_pending(ledger, *, max_invoices=20, api_key='', discover=incoming_candidates,
                      fetch=finalized_records):
    """Scan bounded pending invoices. Returns COUNTS, never buyer IDs or wallet data."""
    pending = ledger.pending(limit=max_invoices)
    counts = {'scanned': 0, 'settled': 0, 'underpaid': 0, 'overpaid': 0, 'requires_review': 0, 'failed_scans': 0}
    # A pilot runner only; production must use a durable cursor and alerting.
    for invoice in pending:
        counts['scanned'] += 1
        prior_failures = counts['failed_scans']
        try:
            candidates = discover(invoice['address'], invoice['issued_ms'], invoice['expires_ms'], api_key=api_key)
        except CheckoutError:
            counts['failed_scans'] += 1
            ledger.defer_scan(invoice['id'],failures=1)
            continue
        for txid in candidates:
            tx = receipt = None
            try:
                tx, receipt = fetch(txid, api_key=api_key)
                # The ledger requires the bearer capability; in server-side jobs
                # look up the locked invoice row by ID without retrieving secrets.
                ledger.settle_discovered(invoice['id'], txid, tx, receipt)
                counts['settled'] += 1
                break
            except CheckoutError:
                if tx is None or receipt is None:
                    counts['failed_scans'] += 1
                    continue
                try:
                    discrepancy = ledger.record_mismatched_payment(invoice['id'], txid, tx, receipt)
                    if discrepancy['new']:
                        counts[discrepancy['status']] += 1
                    # Existing invoice is NOT settled; buyer gets manual-review status.
                except CheckoutError:
                    counts['requires_review'] += 1
            except (OSError, TimeoutError):
                counts['failed_scans'] += 1
        ledger.defer_scan(invoice['id'],failures=1 if counts['failed_scans']>prior_failures else 0)
    return counts