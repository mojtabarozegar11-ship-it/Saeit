"""Read-only ETH/TRX inbound transfer discovery; NEVER a payment confirmation.

Indexer responses supply candidate hashes, never proof. Production must run each
candidate through independent Ethereum/TRON finality checks before settlement.
Pagination is bounded; incomplete coverage fails closed instead of skipping.
"""
from dataclasses import dataclass
from datetime import datetime
import json
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from mojplaywin_native_chain_verify import tron_address_to_hex

ETH_WALLET = "0x89149b01f59115B86553561F12438D2ADF517E75"
TRX_WALLET = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"
ETH_URL = "https://eth.blockscout.com/api/v2/addresses/" + ETH_WALLET + "/transactions"
TRX_URL = "https://api.trongrid.io/v1/accounts/" + TRX_WALLET + "/transactions"
ETH_NEXT_KEYS = frozenset(("block_number", "index", "items_count", "transaction_index"))
MAX_BYTES = 300000


class IndexerUnavailable(ValueError):
    pass


class IncompleteDiscovery(IndexerUnavailable):
    pass


@dataclass(frozen=True)
class Candidate:
    network: str
    tx_hash: str
    sender: str
    recipient: str
    amount_atomic: str
    timestamp_ms: int


def fetch_indexer(url):
    try:
        req = Request(url, headers={"Accept": "application/json",
            "User-Agent": "MojPlayWin-ReadOnly-Indexer/1"}, method="GET")
        with urlopen(req, timeout=15) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise IndexerUnavailable("Indexer response size exceeded")
        result = json.loads(raw.decode("utf-8"))
        if not isinstance(result, dict):
            raise IndexerUnavailable("Invalid indexer JSON root")
        return result
    except (OSError, TimeoutError, UnicodeError, ValueError) as exc:
        raise IndexerUnavailable("Indexer did not return valid bounded data") from exc


def time_from_iso(s):
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if t.tzinfo is None: raise ValueError("No timestamp timezone")
        return int(t.timestamp() * 1000)
    except (TypeError, ValueError, OverflowError, AttributeError) as exc:
        raise IndexerUnavailable("Invalid Ethereum timestamp") from exc


def _safe_pages(now_ms, lookback_s, max_pages):
    if (type(now_ms) is not int or now_ms < 1_000_000_000_000
        or type(lookback_s) is not int or not 600 <= lookback_s <= 86400
        or type(max_pages) is not int or not 1 <= max_pages <= 20):
        raise IndexerUnavailable("Invalid scan bounds")
    return now_ms - lookback_s * 1000


def _parse_eth(item):
    if not isinstance(item, dict):
        raise IndexerUnavailable("Invalid ETH transaction item")
    h = item.get("hash")
    frm = item.get("from")
    to = item.get("to")
    value = item.get("value")
    if not (isinstance(h, str) and re.fullmatch(r"0x[0-9a-fA-F]{64}", h)
            and isinstance(frm, dict) and isinstance(to, dict)
            and isinstance(value, str) and re.fullmatch(r"[0-9]+", value)):
        raise IndexerUnavailable("Malformed ETH indexer transaction")
    sender, recipient = frm.get("hash"), to.get("hash")
    if not all(isinstance(v, str) and re.fullmatch(r"0x[0-9a-fA-F]{40}", v)
               for v in (sender, recipient)):
        raise IndexerUnavailable("Invalid indexed ETH address")
    stamp = time_from_iso(item.get("timestamp"))
    if recipient.lower() != ETH_WALLET.lower() or int(value) <= 0:
        return None, stamp
    return Candidate("ethereum-mainnet", h.lower(), sender.lower(),
                     recipient.lower(), str(int(value)), stamp), stamp


def _parse_trx(item):
    if not isinstance(item, dict):
        raise IndexerUnavailable("Invalid TRON transaction item")
    h = item.get("txID")
    raw = item.get("raw_data")
    if not (isinstance(h, str) and re.fullmatch(r"[0-9a-fA-F]{64}", h)
            and isinstance(raw, dict)):
        raise IndexerUnavailable("Malformed indexed TRON transaction")
    stamp = raw.get("timestamp")
    if type(stamp) is not int or stamp < 1_000_000_000_000:
        raise IndexerUnavailable("Invalid indexed TRON timestamp")
    contracts = raw.get("contract")
    if not isinstance(contracts, list) or len(contracts) != 1:
        return None, stamp
    c = contracts[0]
    if not isinstance(c, dict) or c.get("type") != "TransferContract":
        return None, stamp
    data = c.get("parameter", {}).get("value", {})
    if not isinstance(data, dict):
        raise IndexerUnavailable("Invalid TRON transfer")
    sender = data.get("owner_address")
    recipient = data.get("to_address")
    amount = data.get("amount")
    if not (all(isinstance(x, str) and re.fullmatch(r"41[0-9a-fA-F]{40}", x)
                for x in (sender, recipient)) and type(amount) is int and amount >= 0):
        raise IndexerUnavailable("Invalid TRX transfer fields")
    if recipient.lower() != tron_address_to_hex(TRX_WALLET).lower() or amount == 0:
        return None, stamp
    return Candidate("tron-mainnet", h.lower(), sender.lower(), recipient.lower(),
                     str(amount), stamp), stamp


def discover_eth(*, load=fetch_indexer, now_ms=None, lookback_s=3600, max_pages=4):
    if now_ms is None: now_ms = int(time.time() * 1000)
    cutoff = _safe_pages(now_ms, lookback_s, max_pages)
    cursor, seen, output = {}, set(), {}
    for _ in range(max_pages):
        page = load(ETH_URL + "?" + urlencode({"filter": "to", **cursor}))
        items = page.get("items")
        if not isinstance(items, list) or len(items) > 100:
            raise IndexerUnavailable("Invalid ETH result page")
        oldest = None
        for item in items:
            candidate, stamp = _parse_eth(item)
            if stamp > now_ms + 90000: raise IndexerUnavailable("Future ETH block time")
            oldest = stamp if oldest is None else min(oldest, stamp)
            if candidate and stamp >= cutoff: output[candidate.tx_hash] = candidate
        if oldest is not None and oldest < cutoff: return list(output.values())
        next_cursor = page.get("next_page_params")
        if not next_cursor: return list(output.values())
        if not isinstance(next_cursor, dict) or set(next_cursor)-ETH_NEXT_KEYS:
            raise IndexerUnavailable("Unsafe ETH page cursor")
        if not next_cursor or any(type(x) is not int or x < 0 for x in next_cursor.values()):
            raise IndexerUnavailable("Malformed ETH page cursor")
        cursor = next_cursor
        fingerprint = tuple(sorted(cursor.items()))
        if fingerprint in seen: raise IncompleteDiscovery("Repeated ETH page")
        seen.add(fingerprint)
    raise IncompleteDiscovery("ETH scan exceeded maximum pages")


def discover_trx(*, load=fetch_indexer, now_ms=None, lookback_s=3600, max_pages=4):
    if now_ms is None: now_ms = int(time.time() * 1000)
    cutoff = _safe_pages(now_ms, lookback_s, max_pages)
    cursor, seen, output = None, set(), {}
    for _ in range(max_pages):
        params = {"only_to":"true", "only_confirmed":"true", "limit":100,
                  "order_by":"block_timestamp,desc", "min_block_timestamp":cutoff}
        if cursor: params["fingerprint"] = cursor
        page = load(TRX_URL + "?" + urlencode(params))
        items = page.get("data")
        if not isinstance(items, list) or len(items)>100:
            raise IndexerUnavailable("Invalid TRON result page")
        oldest = None
        for item in items:
            candidate, stamp = _parse_trx(item)
            if stamp > now_ms + 90000: raise IndexerUnavailable("Future TRON block time")
            oldest = stamp if oldest is None else min(oldest, stamp)
            if candidate and stamp >= cutoff: output[candidate.tx_hash] = candidate
        if oldest is not None and oldest < cutoff: return list(output.values())
        meta = page.get("meta", {})
        if not isinstance(meta, dict): raise IndexerUnavailable("Invalid TRON page metadata")
        cursor = meta.get("fingerprint")
        if not cursor: return list(output.values())
        if not isinstance(cursor, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", cursor):
            raise IndexerUnavailable("Unsafe TRON page fingerprint")
        if cursor in seen: raise IncompleteDiscovery("Repeated TRON page")
        seen.add(cursor)
    raise IncompleteDiscovery("TRON scan exceeded maximum pages")


def match_unpaid_invoices(invoices, candidates):
    """Candidate matching only; a separate trusted RPC must confirm each match.

    Invoice rows must be server-loaded and have verified buyer sender, exact
    atomic amount and the pre-authorized receiving wallet. No state mutation.
    """
    table = {}
    for inv in invoices:
        if not inv.verified_sender_address or not inv.merchant_address:
            raise IncompleteDiscovery("Unverified invoice sender or recipient")
        key = (inv.network, inv.verified_sender_address.lower(),
               inv.merchant_address.lower(), str(inv.amount_atomic))
        if key in table: raise IncompleteDiscovery("Ambiguous matching invoices")
        table[key] = inv.pk
    matches = {}
    for candidate in candidates:
        key = (candidate.network, candidate.sender.lower(),
               candidate.recipient.lower(), candidate.amount_atomic)
        if key in table:
            matches[(candidate.network,candidate.tx_hash)] = (table[key],candidate.tx_hash)
    return list(matches.values())


if __name__ == "__main__":
    for label, fn in (("ETH",discover_eth),("TRX",discover_trx)):
        try:
            result = fn()
            print(label, "INDEX_READ_ONLY_OK", "candidates", len(result))
        except IndexerUnavailable as exc:
            print(label, "INDEX_NOT_READY", type(exc).__name__)
            raise SystemExit(1)
    print("NO_PAYMENT_OR_ORDER_MODIFICATIONS")
