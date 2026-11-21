"""Read-only TRON solidity client. Mainnet only, no signing or broadcast."""
import json
import re
from urllib.request import Request, urlopen
from .core import CheckoutError, TXID_PATTERN

MAINNET_SOLIDITY = 'https://api.trongrid.io'


def _post_solidified(endpoint: str, txid: str, *, opener=urlopen, api_key='') -> dict:
    if endpoint not in ('gettransactionbyid', 'gettransactioninfobyid'):
        raise CheckoutError('Unapproved RPC method')
    if not isinstance(txid, str) or not TXID_PATTERN.fullmatch(txid):
        raise CheckoutError('Invalid transaction hash')
    if api_key and (not isinstance(api_key, str) or len(api_key) > 512 or '\n' in api_key):
        raise CheckoutError('Invalid API key')
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json',
               'User-Agent': 'MojPlayWin-TRON-ReadOnly/1'}
    if api_key:
        headers['TRON-PRO-API-KEY'] = api_key
    req = Request(MAINNET_SOLIDITY + '/walletsolidity/' + endpoint,
                  json.dumps({'value': txid}).encode('ascii'), headers, method='POST')
    try:
        with opener(req, timeout=12) as response:
            if getattr(response, 'status', 200) != 200:
                raise CheckoutError('TRON node returned a non-success HTTP status')
            content = response.read(131073)
        if len(content) > 131072:
            raise CheckoutError('Oversized TRON node response')
        result = json.loads(content.decode('utf8'),
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid JSON value')))
        if not isinstance(result, dict) or 'Error' in result:
            raise CheckoutError('Unverifiable TRON node response')
        return result
    except (OSError, ValueError, UnicodeError, TimeoutError) as exc:
        raise CheckoutError('TRON solidity proof unavailable') from exc


def finalized_records(txid: str, *, opener=urlopen, api_key='') -> tuple[dict, dict]:
    """Run from a trusted backend only. Empty responses mean NOT YET verified."""
    body = _post_solidified('gettransactionbyid', txid, opener=opener, api_key=api_key)
    receipt = _post_solidified('gettransactioninfobyid', txid, opener=opener, api_key=api_key)
    return body, receipt