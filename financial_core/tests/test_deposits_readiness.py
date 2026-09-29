from decimal import Decimal
import pytest

from financial_core.assets import Asset, AssetRegistry
from financial_core.deposits import DepositEvent, DepositProcessor
from financial_core.readiness import ProductionReadiness


class Store:
    def __init__(self): self.keys=set()
    def exists(self, key): return key in self.keys
    def reserve(self, key):
        if key in self.keys: return False
        self.keys.add(key); return True
    def commit(self, key): pass
    def release(self, key): self.keys.discard(key)


def test_confirmed_deposit_is_credited_once():
    registry=AssetRegistry([Asset('USDT','tron',6,20,False,True,Decimal('1'))])
    store=Store(); credits=[]
    processor=DepositProcessor(registry,store,credits.append)
    event=DepositEvent('0','u1','USDT','tron',Decimal('10'),'abc',20)
    assert processor.process(event)==(True,'credited')
    assert processor.process(event)==(False,'duplicate-event')
    assert len(credits)==1


def test_unconfirmed_deposit_is_not_credited():
    registry=AssetRegistry([Asset('USDT','tron',6,20,False,True,Decimal('1'))])
    processor=DepositProcessor(registry,Store(),lambda event: None)
    event=DepositEvent('0','u1','USDT','tron',Decimal('10'),'abc',19)
    assert processor.process(event)==(False,'awaiting-confirmations')


def test_production_gate_fails_closed():
    with pytest.raises(RuntimeError, match='financial-production-not-ready'):
        ProductionReadiness().require_ready()


def test_production_gate_requires_every_control():
    state=ProductionReadiness(True,True,True,True,True,True,True)
    assert state.ready and state.require_ready()
