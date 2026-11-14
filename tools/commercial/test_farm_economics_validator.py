import unittest
from farm_economics_validator import validate_csv, FIELDS
BASE=["farm01","wheat","2026-01-01","2026-06-30","USD","kg","100","80","800","20","300","200","50"]
def sample(values=None, headers=FIELDS):
    return ",".join(headers)+"\n"+",".join(BASE if values is None else values)+"\n"
class FarmEconomicsTests(unittest.TestCase):
    def test_profit(self):
        result=validate_csv(sample())[0]
        self.assertEqual(result["economic_profit"],"270")
        self.assertEqual(result["break_even_units"],"32")
    def test_negative(self):
        row=BASE.copy();row[10]="-1"
        with self.assertRaises(ValueError):validate_csv(sample(row))
    def test_nan(self):
        row=BASE.copy();row[8]="NaN"
        with self.assertRaises(ValueError):validate_csv(sample(row))
    def test_sold_more_than_produced(self):
        row=BASE.copy();row[7]="101"
        with self.assertRaises(ValueError):validate_csv(sample(row))
    def test_reversed_period(self):
        row=BASE.copy();row[2]="2026-12-01"
        with self.assertRaises(ValueError):validate_csv(sample(row))
    def test_unsafe_label(self):
        row=BASE.copy();row[0]="=1+1"
        with self.assertRaises(ValueError):validate_csv(sample(row))
    def test_bad_currency(self):
        row=BASE.copy();row[4]="USDT"
        with self.assertRaises(ValueError):validate_csv(sample(row))
    def test_duplicate_header(self):
        with self.assertRaises(ValueError):validate_csv(sample(headers=FIELDS[:-1]+("fixed_cost",)))
    def test_empty(self):
        with self.assertRaises(ValueError):validate_csv(",".join(FIELDS)+"\n")
    def test_duplicate_enterprise_period_is_rejected(self):
        rows = sample() + ",".join(BASE) + "\n"
        with self.assertRaisesRegex(ValueError, "duplicate enterprise reporting period"):
            validate_csv(rows)
    def test_changed_amount_does_not_hide_duplicate_period(self):
        changed = BASE.copy(); changed[8] = "950"
        rows = sample() + ",".join(changed) + "\n"
        with self.assertRaisesRegex(ValueError, "duplicate enterprise reporting period"):
            validate_csv(rows)
    def test_distinct_enterprise_periods_are_allowed(self):
        changed = BASE.copy(); changed[2] = "2026-07-01"; changed[3] = "2026-12-31"
        rows = sample() + ",".join(changed) + "\n"
        self.assertEqual(len(validate_csv(rows)), 2)
    def test_zero_sales(self):
        row=BASE.copy();row[7]="0";row[8]="0"
        self.assertEqual(validate_csv(sample(row))[0]["break_even_units"],"NOT_ATTAINABLE")
if __name__=="__main__":unittest.main()
