import unittest
from calculator import calculate

class WaterTests(unittest.TestCase):
    def test_reference(self):
        r = calculate('5','1.2','1','0','0.8',7,'2')
        self.assertEqual(r['gross_volume_m3'],'875.00')
