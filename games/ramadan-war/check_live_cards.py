"""Read-only, fail-closed homepage card gate for Ramadan War releases.

A temporary DNS outage may be retried; an incorrect live card manifest never
passes and is never treated as an offline preview success.
"""
import json
import re
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

URL = 'https://zomorodmelal.ir/'


def verify_cards(page):
    match = re.search(rb'window[.]ZOMOROD_ORBIT_DATA=([{].*?[}]);</script>', page, re.S)
    if not match:
        raise AssertionError('Cannot locate live homepage manifest')
    rows = json.loads(match.group(1))['rows']
    row = next((item for item in rows if item.get('id') == 'ZM-R25'), None)
    if row is None:
        raise AssertionError('Missing live IT cards row')
    cards = row['cards']
    assert row['title'] == 'فناوری اطلاعات و خدمات دیجیتال' and len(cards) >= 24
    assert cards[0]['id'] == 'ZM-R25-GAME-FARM-DOMINION-20261019'
    assert cards[1]['id'] == 'ZM-R25-GAME-RAMADAN-WAR-20261022'
    assert cards[1]['canonicalUrl'] == '/ramadan-war/'
    assert cards[2]['id'] == 'ZM-R25-GAME-ARROW-ESCAPE-20261022'
    assert cards[2]['canonicalUrl'] == '/arrow-escape/'
    assert cards[3]['slug'] == 'website-design'
    return len(cards)


def check_live_cards(opener=urlopen, sleeper=time.sleep, attempts=4):
    if attempts < 1:
        raise ValueError('attempts must be positive')
    request = Request(URL, headers={'Cache-Control': 'no-cache',
                                    'User-Agent': 'RamadanReadOnlyCardQA/2'})
    for attempt in range(1, attempts + 1):
        try:
            with opener(request, timeout=25) as response:
                if response.status != 200:
                    raise AssertionError('Live homepage did not return HTTP 200')
                page = response.read(3500000)
            # Parse and validate exactly once. Invalid live content fails closed.
            return verify_cards(page)
        except URLError as exc:
            if attempt == attempts:
                raise
            print(f'LIVE_CARD_NETWORK_RETRY {attempt}/{attempts}: {exc}', flush=True)
            sleeper(8)
    raise AssertionError('Unreachable')


if __name__ == '__main__':
    print('LIVE_IT_FIRST_FOUR_CARDS=PASS count=', check_live_cards())
