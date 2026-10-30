import unittest
from g01_s01_checkout_accessibility_r34 import inspect
class OfflinePreflight(unittest.TestCase):
    def test_named_controls(self):
        r=inspect('<form><label for="mail">Email</label><input id="mail"><button>Continue</button></form>')
        self.assertTrue(r['passed']);self.assertEqual(r['counts']['inputs'],1)
    def test_missing_label_is_detected_without_values(self):
        r=inspect('<form><input name="secret" value="PRIVATE_VALUE"><button>Go</button></form>')
        self.assertFalse(r['passed']);self.assertNotIn('PRIVATE_VALUE',str(r))
    def test_wrapping_label_and_hidden_input(self):
        r=inspect('<form><input type="hidden" value="PRIVATE"><label>Code <input type="text"></label></form>')
        self.assertTrue(r['passed']);self.assertEqual(r['counts']['inputs'],1)
    def test_duplicate_id(self):
        r=inspect('<form><label for="a">A</label><input id="a"><input id="a" aria-label="B"></form>')
        self.assertFalse(r['passed']);self.assertIn('DUPLICATE_IDS',[i['code'] for i in r['issues']])
if __name__=='__main__':unittest.main()
