import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name('irrigation_source_gate.py')
spec = importlib.util.spec_from_file_location('irrigation_source_gate', MODULE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class SourceGateTests(unittest.TestCase):
    def data(self, rows=None):
        return {'source_id':'unverified-source', 'verified_by':'claimed-reviewer', 'rows': rows or [{'id':'DSS','yield_kg':'12','water_m3':'3'}]}

    def test_exact_decimal_arithmetic_and_provenance_flag(self):
        out = gate.validate(self.data())
        self.assertEqual(out['computed'], [{'id':'DSS','wue_kg_per_m3':'4'}])
        self.assertIs(out['source_authenticity_independently_verified'], False)
        self.assertEqual(out['reviewer_claim'], 'claimed-reviewer')

    def test_reject_unsupported_expected_wue(self):
        d=self.data(); d['expected_wue']='4'
        with self.assertRaises(ValueError): gate.validate(d)

    def test_reject_whitespace_duplicate_ids(self):
        d=self.data([{'id':'DSS ','yield_kg':1,'water_m3':1},{'id':' DSS','yield_kg':2,'water_m3':1}])
        with self.assertRaises(ValueError): gate.validate(d)

    def test_reject_invalid_measurements(self):
        for value in [0,-1,True,None,'NaN','Infinity','nope']:
            with self.subTest(value=value):
                d=self.data([{'id':'DSS','yield_kg':value,'water_m3':3}])
                with self.assertRaises(ValueError): gate.validate(d)

    def test_reject_missing_source_claims(self):
        for key in ['source_id','verified_by']:
            d=self.data();d[key]=' '
            with self.assertRaises(ValueError): gate.validate(d)

    def test_no_unit_conversion_inferred(self):
        d=self.data([{'id':'DSS','yield_kg':'0.3','water_m3':'0.2'}])
        self.assertEqual(gate.validate(d)['computed'][0]['wue_kg_per_m3'],'1.5')

if __name__=='__main__':
    unittest.main()
