import unittest
from calculator import calculate

class WaterTests(unittest.TestCase):
    def test_reference(self):
        r = calculate('5','1.2','1','0','0.8',7,'2')
        self.assertEqual(r['gross_volume_m3'],'875.00')

    def test_rain_reduces_demand(self):
        r = calculate('5','1.2','20','0','0.8',7,'2')
        self.assertEqual(r['gross_volume_m3'],'0')

    def test_soil_water_credit(self):
        r = calculate('5','1.2','1','14','0.8',7,'2')
        self.assertEqual(r['net_irrigation_mm'],'21.0')

    def test_input_validation(self):
        for bad in ('NaN','Infinity','-1'):
            with self.assertRaises(ValueError):
                calculate(bad,'1','0','0','0.8',7,'1')
        with self.assertRaises(ValueError):
            calculate('5','1','0','0','0',7,'1')

    def test_area_scaling(self):
        one = calculate('5','1.2','1','0','0.8',7,'1')
        three = calculate('5','1.2','1','0','0.8',7,'3')
        self.assertEqual(float(three['gross_volume_m3']),3*float(one['gross_volume_m3']))
