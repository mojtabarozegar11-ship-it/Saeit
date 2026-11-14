import unittest
from farm_economics_validator import FIELDS, validate_csv
ROW=[' farm01 ','wheat','2026-01-01','2026-06-30','USD','kg','100','80','800','20','300','200','50']
def make(row): return ','.join(FIELDS)+'\n'+','.join(row)+'\n'
class ProvenanceContract(unittest.TestCase):
    def test_period_source_and_unit_captured(self):
        x=validate_csv(make(ROW))[0]
        self.assertEqual((x['enterprise_id'],x['enterprise_type'],x['period_start'],x['period_end'],x['output_unit']),
                         ('farm01','wheat','2026-01-01','2026-06-30','kg'))
        self.assertEqual(x['reported_profit_basis'],'PERIOD_RECEIPTS_LESS_TOTAL_RECORDED_COSTS')
    def test_unsold_quantity_and_inventory_caveat(self):
        x=validate_csv(make(ROW))[0]
        self.assertEqual(x['unsold_quantity'],'20')
        self.assertEqual(x['inventory_cost_allocation'],'REQUIRES_RECONCILIATION')
        self.assertEqual(x['break_even_units'],'NOT_ATTAINABLE')
    def test_fully_sold_avoids_inventory_warning(self):
        row=ROW.copy();row[6]='80'
        x=validate_csv(make(row))[0]
        self.assertEqual(x['unsold_quantity'],'0')
        self.assertEqual(x['inventory_cost_allocation'],'NO_UNSOLD_OUTPUT')
    def test_inputs_reconcile_with_original_financial_numbers(self):
        x=validate_csv(make(ROW))[0]
        self.assertEqual({k:x[k] for k in ('sales_revenue','other_revenue','variable_cost','fixed_cost','opportunity_cost')},
                         {'sales_revenue':'800','other_revenue':'20','variable_cost':'300','fixed_cost':'200','opportunity_cost':'50'})
if __name__=='__main__':unittest.main()
