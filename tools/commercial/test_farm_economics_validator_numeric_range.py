import unittest
from farm_economics_validator import FIELDS, validate_csv
BASE=['farm01','wheat','2026-01-01','2026-06-30','USD','kg','80','80','800','20','300','200','50']
def sample(index,value):
    row=BASE.copy(); row[index]=value
    return ','.join(FIELDS)+'\n'+','.join(row)+'\n'
class NumericRangeContract(unittest.TestCase):
    def test_huge_revenue_rejected_without_decimal_overflow_leak(self):
        with self.assertRaisesRegex(ValueError,r'line 2: numeric magnitude/precision'):
            validate_csv(sample(8,'1e100000000'))
    def test_huge_cost_rejected_without_decimal_overflow_leak(self):
        with self.assertRaisesRegex(ValueError,r'line 2: numeric magnitude/precision'):
            validate_csv(sample(10,'1e100000000'))
    def test_huge_production_ratio_rejected_without_decimal_overflow_leak(self):
        with self.assertRaisesRegex(ValueError,r'line 2: numeric magnitude/precision'):
            validate_csv(sample(6,'1e100000000'))
    def test_normal_profit_and_break_even_remain_correct(self):
        record=validate_csv(sample(8,'800'))[0]
        self.assertEqual(record['economic_profit'],'270')
        self.assertEqual(record['break_even_units'],'32')
    def test_zero_input_no_exception_leak(self):
        r=validate_csv(sample(8,'0'))[0]
        self.assertEqual(r['break_even_units'],'NOT_ATTAINABLE')
if __name__=='__main__':unittest.main()
