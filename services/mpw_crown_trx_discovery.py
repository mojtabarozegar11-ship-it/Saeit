"""Read-only mainnet deposit *discovery* for a single Crown invoice.

TronGrid is only an index of possible TX hashes. A candidate can NEVER settle
without separate solidity receipts from the two independently audited operators.
The receiver and exact reserved SUN amount come exclusively from MariaDB.
No cron/worker is needed while a buyer's invoice page is open.
"""
from datetime import timezone
import json
import re
import urllib.parse
import urllib.request

from services.mpw_trx_walletless_core import InvoiceIntent, PaymentHold, TX_ID
from services.mpw_tron_independent_solidified_rpc import hex_to_tron_address

_BASE = "https://api.trongrid.io/v1/accounts/"
_FINGERPRINT = re.compile(r"^[A-Za-z0-9_-]{1,260}$")
_MAX_BYTES = 200_000


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise PaymentHold("Indexer redirect forbidden")


def discover_native_candidates(invoice: InvoiceIntent, api_key: str, *, transport=None):
    """Return at most 2 matching TX hashes. No observer can infer payment status.

    Caller must verify every candidate against BOTH independent SolidityNode
    operators via the mainnet settlement kernel (never trust indexer alone).
    """
    if not isinstance(invoice, InvoiceIntent) or invoice.network != "tron-mainnet":
        raise PaymentHold("Invoice is not native TRON mainnet")
    if (not isinstance(api_key, str) or not 10 <= len(api_key) <= 512
            or "\r" in api_key or "\n" in api_key):
        raise PaymentHold("Authenticated mainnet indexer required")
    params = {
        "only_to": "true", "only_confirmed": "true", "limit": "200",
        "order_by": "block_timestamp,desc",
        "min_timestamp": str(int(invoice.issued_at.timestamp() * 1000) - 60000),
        "max_timestamp": str(int(invoice.expires_at.timestamp() * 1000) + 60000),
    }
    found = []
    seen = set()
    for page in range(2):
        url = (_BASE + invoice.recipient + "/transactions?"
               + urllib.parse.urlencode(params))
        if transport is None:
            req = urllib.request.Request(url, headers={
                "TRON-PRO-API-KEY": api_key, "Accept": "application/json",
                "User-Agent": "MojPlayWin-Crown-ReadOnly-Indexer/1",
            })
            opener = urllib.request.build_opener(_NoRedirect())
            try:
                with opener.open(req, timeout=5) as response:
                    if response.status != 200:
                        raise PaymentHold("Indexer unavailable")
                    data = response.read(_MAX_BYTES + 1)
                if len(data) > _MAX_BYTES:
                    raise PaymentHold("Indexer response exceeds bounded size")
                doc = json.loads(data)
            except (ValueError, OSError, TimeoutError, UnicodeError) as exc:
                raise PaymentHold("Indexer response cannot be verified") from exc
        else:
            doc = transport(url)
        if not isinstance(doc, dict) or not isinstance(doc.get("data"), list):
            raise PaymentHold("Untrusted indexed transactions")
        for tx in doc["data"]:
            if not isinstance(tx, dict):
                continue
            txid = tx.get("txID")
            if not isinstance(txid, str) or TX_ID.fullmatch(txid) is None:
                continue
            stamp = tx.get("block_timestamp")
            if type(stamp) is not int:
                continue
            block_time = stamp / 1000
            if not invoice.issued_at.timestamp() <= block_time <= invoice.expires_at.timestamp():
                continue
            contracts = (tx.get("raw_data") or {}).get("contract")
            if not isinstance(contracts, list) or len(contracts) != 1:
                continue
            contract = contracts[0]
            if not isinstance(contract, dict) or contract.get("type") != "TransferContract":
                continue
            raw = ((contract.get("parameter") or {}).get("value") or {})
            if type(raw.get("amount")) is not int or raw.get("amount") != invoice.amount_sun:
                continue
            try:
                receiver = hex_to_tron_address(raw.get("to_address"))
            except PaymentHold:
                continue
            if receiver == invoice.recipient and txid not in seen:
                found.append(txid)
                seen.add(txid)
            if len(found) >= 2:
                return found
        fingerprint = (doc.get("meta") or {}).get("fingerprint")
        if not isinstance(fingerprint, str) or not _FINGERPRINT.fullmatch(fingerprint):
            break
        params["fingerprint"] = fingerprint
    return found
