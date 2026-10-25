"""Fail-closed, server-to-server native TRX price discovery."""
import json
from decimal import Decimal, InvalidOperation
from urllib.request import Request, urlopen
from .core import CheckoutError

URL = 'https://api.coingecko.com/api/v3/simple/price?ids=tron&vs_currencies=usd'


def usd_per_trx(*, opener=urlopen) -> Decimal:
    request = Request(URL, headers={'Accept': 'application/json',
                                    'User-Agent': 'MojPlayWin-TRON-Quote/1'}, method='GET')
    try:
        with opener(request, timeout=10) as response:
            raw = response.read(4097)
        if len(raw) > 4096:
            raise CheckoutError('Oversized quote')
        data = json.loads(raw.decode('utf8'))
        value = data['tron']['usd']
        if type(value) not in (int, float, str):
            raise CheckoutError('Malformed TRX price')
        rate = Decimal(str(value))
        if not rate.is_finite() or not Decimal('.001') <= rate <= Decimal('100'):
            raise CheckoutError('TRX price outside controlled bounds')
        return rate
    except (KeyError, TypeError, ValueError, OSError, UnicodeError, InvalidOperation) as exc:
        raise CheckoutError('Reliable TRX price currently unavailable') from exc