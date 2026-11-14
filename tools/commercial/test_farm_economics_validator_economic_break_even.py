import unittest
from farm_economics_validator import FIELDS, validate_csv
BASE=['farm01','wheat','2026-01-01','2026-06-30','USD','kg','80','80','800','20','300','200','50']
def make(row):return ','.join(FIELDS)+'\n'+','.join(row)+'\n'
class EconomicBreakEvenContract(unittest.TestCase):
    def test_economic_break_even_includes_opportunity_cost(self):
        r=validate_csv(make(BASE))[0]
        self.assertEqual(r['break_even_units'],'32')
        self.assertEqual(r['economic_break_even_units'],'4E+1')
        self.assertEqual(r['economic_break_even_feasibility'],'WITHIN_REPORTED_PRODUCTION')
    def test_economic_threshold_exceeds_reported_output(self):
        row=BASE.copy();row[12]='400'
        r=validate_csv(make(row))[0]
        self.assertEqual(r['economic_break_even_units'],'96')
        self.assertEqual(r['economic_break_even_feasibility'],'EXCEEDS_REPORTED_PRODUCTION')
    def test_partial_sales_cannot_allocate_unit_cost(self):
        row=BASE.copy();row[6]='100'
        r=validate_csv(make(row))[0]
        self.assertEqual(r['economic_break_even_units'],'NOT_ATTAINABLE')
        self.assertEqual(r['economic_break_even_feasibility'],'NOT_CALCULABLE')
    def test_negative_contribution_has_no_positive_economic_break_even(self):
        row=BASE.copy();row[10]='1000'
        r=validate_csv(make(row))[0]
        self.assertEqual(r['economic_break_even_units'],'NOT_ATTAINABLE')
    def test_economic_basis_explicitly_excludes_period_other_revenue(self):
        r=validate_csv(make(BASE))[0]
        self.assertEqual(r['economic_break_even_basis'],'FIXED_AND_OPPORTUNITY_COST_EXCLUDES_OTHER_REVENUE')
if __name__=='__main__':unittest.main()
