"""Offline checks for exact scope of the one-card, 2D-to-3D upgrade."""
import json
import unittest

from upgrade import CARD_ID, PATTERN, edit_home


def homepage():
    cards = [{'id': 'ZM-R25-GAME-FARM-DOMINION-20261019'},
             {'id': 'ZM-R25-GAME-RAMADAN-WAR-20261022'},
             {'id': CARD_ID, 'slug': 'arrow-escape', 'canonicalUrl': '/arrow-escape/',
              'title': 'بازی هزارتوی پیکان‌ها', 'other': {'retain': True}},
             {'slug': 'website-design', 'title': 'کارت چهارم'}]
    cards.extend({'slug': f'card-{n}', 'title': f'کارت {n}'} for n in range(4, 24))
    payload = {'rows': [{'id': 'ZM-R25', 'title': 'فناوری اطلاعات و خدمات دیجیتال',
                        'cards': cards}, {'id': 'other', 'cards': [{'name': 'unrelated'}]}]}
    body = 'prefix\n<script>window.ZOMOROD_ORBIT_DATA=' + json.dumps(
        payload, ensure_ascii=False, separators=(',', ':')) + ';</script>\nsuffix'
    return body.encode('utf-8')


class UpgradeSafety(unittest.TestCase):
    def test_only_exact_card_title_changes(self):
        before = homepage()
        after = edit_home(before)
        a = json.loads(PATTERN.search(before.decode()).group(2))
        b = json.loads(PATTERN.search(after.decode()).group(2))
        assert a['rows'][0]['cards'][2]['title'] == 'بازی هزارتوی پیکان‌ها'
        assert b['rows'][0]['cards'][2]['title'] == 'بازی مکعب پیکان‌ها'
        b['rows'][0]['cards'][2]['title'] = a['rows'][0]['cards'][2]['title']
        self.assertEqual(a, b)
        self.assertTrue(after.startswith(b'prefix\n'))
        self.assertTrue(after.endswith(b'\nsuffix'))

    def test_wrong_or_missing_card_rejected(self):
        self.assertRaises(AssertionError, edit_home, homepage().replace(
            'بازی هزارتوی پیکان‌ها'.encode(), 'عنوان دیگر'.encode()))
        self.assertRaises(AssertionError, edit_home, homepage().replace(
            CARD_ID.encode(), b'wrong-card-id'))
        self.assertRaises(AssertionError, edit_home, b'<html>missing manifest</html>')


if __name__ == '__main__':
    unittest.main()
