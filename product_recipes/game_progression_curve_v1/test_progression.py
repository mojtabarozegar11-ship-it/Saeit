import unittest
from calculator import curve

class CurveTests(unittest.TestCase):
    def test_linear(self):
        assert curve(100,1,4,50)[-1] == (3,300,600,6.0)

    def test_increasing_cost(self):
        rows = curve(100,1.5,40,25)
        assert all(a[1] < b[1] for a,b in zip(rows,rows[1:]))

    def test_reproducible(self):
        assert curve(80,1.2,20,10) == curve(80,1.2,20,10)

    def test_invalid_values(self):
        for invalid in (0,201,True,1.5):
            with self.assertRaises(ValueError):
                curve(100,1.5,invalid,50)
        for invalid in (float('nan'),float('inf'),-1):
            with self.assertRaises(ValueError):
                curve(invalid,1.5,20,50)
