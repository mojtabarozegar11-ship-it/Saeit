from decimal import Decimal
import unittest
from financial_core.domain import Environment, UnitKind, UnitSpec
from financial_core.risk import ExecutionRequest, RiskGate
from financial_core.execution import DemoConnector, ExecutionEngine
from financial_core.ledger import Ledger, JournalEntry, Posting
from financial_core.factory import EconomicFactory

class CoreTests(unittest.TestCase):
    def test_real_locked_by_default(self):
        r=ExecutionRequest('x',Environment.REAL,Decimal('1'),Decimal('1'),'buy')
        self.assertEqual(ExecutionEngine(RiskGate(),DemoConnector()).execute(r).status,'blocked')
    def test_demo_idempotent(self):
        r=ExecutionRequest('x',Environment.DEMO,Decimal('10'),Decimal('1'),'buy')
        e=ExecutionEngine(RiskGate(),DemoConnector()); a=e.execute(r); b=e.execute(r)
        self.assertEqual(a,b)
    def test_double_entry(self):
        l=Ledger(); e=JournalEntry('1',(Posting('cash',Decimal('5')),Posting('revenue',Decimal('-5'))))
        self.assertTrue(l.post(e)); self.assertFalse(l.post(e)); self.assertEqual(l.balance('cash'),Decimal('5'))
    def test_factory_requires_robot(self):
        f=EconomicFactory(); a=UnitSpec('a',1,UnitKind.AGENT,'find')
        with self.assertRaises(ValueError): f.create_team('o','m',a,[])

if __name__=='__main__': unittest.main()
