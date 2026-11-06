"""Server-side native TRX receiver and fail-closed fresh USD quote.

Keep the existing price_usd() -> Decimal API. Never create an invoice
using a stale, redirected, malformed, or unverifiable market observation.
"""
import json
import time
from decimal import Decimal
from urllib.request import Request, urlopen

from mpw_commerce.invoicing import RECEIVERS
from scripts.mojplaywin_native_chain_verify import tron_address_to_hex

TRX_QUOTE_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=tron&vs_currencies=usd&include_last_updated_at=true"
)
MAX_QUOTE_AGE_SECONDS = 90
MAX_QUOTE_BYTES = 2048


def receive_wallet():
    chain, address, decimals = RECEIVERS.get("TRX", (None, None, None))
    if chain != "tron-mainnet" or decimals != 6 or not address:
        raise RuntimeError("TRX receiving wallet unavailable")
    tron_address_to_hex(address)
    return address


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate TRX quote key")
        result[key] = value
    return result


def price_usd():
    """Return USD/TRX Decimal only for an authenticated fresh API observation.

    Preserve the legacy Decimal return contract; the caller owns invoice
    creation and must abort on any exception. This function has no fallback.
    """
    request = Request(
        TRX_QUOTE_URL,
        headers={"Accept": "application/json", "User-Agent": "MojPlayWinGuestTRX/1"},
        method="GET",
    )
    with urlopen(request, timeout=9) as response:
        if response.geturl() != TRX_QUOTE_URL or response.status != 200:
            raise ValueError("Untrusted TRX quote response")
        raw = response.read(MAX_QUOTE_BYTES + 1)
    if not raw or len(raw) > MAX_QUOTE_BYTES:
        raise ValueError("Empty or oversized TRX quote")
    payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_keys)
    if type(payload) is not dict or type(payload.get("tron")) is not dict:
        raise ValueError("Missing TRX observation")
    observation = payload["tron"]
    value = observation.get("usd")
    if type(value) not in (int, float, str):
        raise ValueError("Invalid TRX quote")
    price = Decimal(str(value))
    if not price.is_finite() or not Decimal("0.001") <= price <= Decimal("100"):
        raise ValueError("TRX quote outside safety range")
    updated = observation.get("last_updated_at")
    if type(updated) is not int or updated <= 0:
        raise ValueError("Missing TRX observation time")
    age = int(time.time()) - updated
    if age < 0 or age > MAX_QUOTE_AGE_SECONDS:
        raise ValueError("Stale or future TRX observation")
    return price
