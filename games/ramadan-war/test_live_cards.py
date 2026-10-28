import json
import unittest
from urllib.error import URLError
from check_live_cards import check_live_cards, verify_cards


def html(cards=None):
    cards = cards or [
        {'id': 'ZM-R25-GAME-FARM-DOMINION-20261019'},
        {'id': 'ZM-R25-GAME-RAMADAN-WAR-20261022', 'canonicalUrl': '/ramadan-war/'},
        {'id': 'ZM-R25-GAME-ARROW-ESCAPE-20261022', 'canonicalUrl': '/arrow-escape/'},
        {'slug': 'website-design'}] + [{} for _ in range(20)]
    obj = {'rows': [{'id': 'ZM-R25', 'title': 'فناوری اطلاعات و خدمات دیجیتال', 'cards': cards}]}
    return b'<script>window.ZOMOROD_ORBIT_DATA=' + json.dumps(obj, ensure_ascii=False).encode() + b';</script>'


class Response:
    status = 200
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, *_): return self.body


class LiveCardsTests(unittest.TestCase):
    def test_valid_live_manifest(self):
        self.assertEqual(verify_cards(html()), 24)

    def test_dns_recovery_still_validates_live_manifest(self):
        calls, sleeps = [], []
        def opener(*_args, **_kwargs):
            calls.append(True)
            if len(calls) < 3: raise URLError('temporary DNS failure')
            return Response(html())
        self.assertEqual(check_live_cards(opener=opener, sleeper=sleeps.append), 24)
        self.assertEqual(len(calls), 3)
        self.assertEqual(sleeps, [8, 8])

    def test_persistent_dns_failure_never_passes(self):
        with self.assertRaises(URLError):
            check_live_cards(opener=lambda *_a, **_k: (_ for _ in ()).throw(URLError('DNS')),
                             sleeper=lambda *_: None, attempts=2)

    def test_wrong_card_fails_without_retry(self):
        cards = json.loads(html().split(b'=', 1)[1].split(b';</script>')[0])['rows'][0]['cards']
        cards[1]['canonicalUrl'] = '/wrong/'
        calls = []
        def opener(*_a, **_k):
            calls.append(True)
            return Response(html(cards))
        with self.assertRaises(AssertionError):
            check_live_cards(opener=opener, sleeper=lambda *_: None)
        self.assertEqual(len(calls), 1)

    def test_missing_manifest_fails_closed(self):
        with self.assertRaises(AssertionError): verify_cards(b'<html>empty</html>')


if __name__ == '__main__': unittest.main()
