import unittest
from calculator import curve

class CurveTests(unittest.TestCase):
    def test_linear(self):
        assert curve(100,1,4,50)[-1] == (3,300,600,6.0)
