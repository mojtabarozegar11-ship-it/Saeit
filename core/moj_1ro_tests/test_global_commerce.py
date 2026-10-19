import copy,time,tempfile,unittest
from pathlib import Path
from core.moj_1ro import global_commerce as gc
from core.moj_1ro import executive_runtime as ex
from core.moj_1ro.foundation_runtime import connect
from core.moj_1ro.operational_law import current

def payload():
    now=time.time()
    return {'currency':'USD','scope':'identical_licensed_template','unit':'single_license',
        'unit_cost':'50','fee_rate':'0.1','quotes':[
        {'competitor':'Primary A','price':'100','currency':'USD','scope':'identical_licensed_template',
         'unit':'single_license','main_competitor':True,'source_url':'https://example.com/a','quoted_at':now},
        {'competitor':'Primary B','price':'120','currency':'USD','scope':'identical_licensed_template',
         'unit':'single_license','main_competitor':True,'source_url':'https://example.org/b','quoted_at':now}]}

class GlobalCommerceTests(unittest.TestCase):
    def test_worldwide_scope_is_goal_not_claimed_access(self):
        law=current()['global_commerce']
        self.assertEqual(law['target_countries'],'all')
        self.assertEqual(law['target_languages'],'all')
        self.assertIn('global_commerce',ex.DOMAINS)
    def test_price_is_ten_percent_below_lowest_main_competitor(self):
        r=gc.price(payload())
        self.assertEqual(r['proposed_price'],'90.0')
        self.assertEqual(r['competitor_reference'],'100')
        self.assertFalse(r['price_applied']);self.assertIsNone(r['realized_profit'])
    def test_quote_sources_not_independently_verified_by_formula(self):
        self.assertEqual(gc.price(payload())['quote_verification'],'not_independently_verified')
    def test_target_below_cost_is_blocked(self):
        p=payload();p['unit_cost']='85'
        r=gc.price(p)
        self.assertEqual(r['state'],'blocked');self.assertIsNone(r['proposed_price'])
    def test_mixed_currency_requires_comparable_quotes_not_guessed_exchange(self):
        p=payload();p['quotes'][1]['currency']='TRX'
        with self.assertRaises(ValueError):gc.price(p)
    def test_different_scope_not_comparable(self):
        p=payload();p['quotes'][1]['scope']='different_license'
        with self.assertRaises(ValueError):gc.price(p)
    def test_stale_quote_rejected(self):
        p=payload();p['quotes'][1]['quoted_at']-=700000
        with self.assertRaises(ValueError):gc.price(p)
    def test_future_quote_rejected(self):
        p=payload();p['quotes'][0]['quoted_at']+=10000
        with self.assertRaises(ValueError):gc.price(p)
    def test_cost_missing_not_fabricated(self):
        p=payload();del p['unit_cost']
        with self.assertRaises(ValueError):gc.price(p)
    def test_duplicate_competitor_not_two_main_competitors(self):
        p=payload();p['quotes'][1]['competitor']=' primary a '
        with self.assertRaises(ValueError):gc.price(p)
    def test_invalid_numbers_rejected(self):
        for value in [True,'NaN','Infinity','-1','1e99999','1e-99999']:
            p=payload();p['quotes'][0]['price']=value
            with self.assertRaises(ValueError):gc.price(p)
    def test_formula_operation_does_not_allow_automatic_price_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=connect(Path(tmp)/'runtime.sqlite3')
            with self.assertRaises(PermissionError):
                ex.submit('global_commerce','price_compare',payload(),automatic=True,connection=c)
            c.close()
