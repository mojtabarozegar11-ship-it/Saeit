"""Offline proof of the surgical paid-download response contract patch."""
import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/mpw_live_checkout_status_download_contract_20261020.py'
spec = importlib.util.spec_from_file_location('mpw_checkout_status_patch', SCRIPT)
fix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fix)

ORIGINAL = '''@login_required
@never_cache
@require_GET
def checkout_status(request,order_id):
    if not _ready(request):
        return _deny()
    if type(order_id) is not int or order_id<=0:
        return JsonResponse({"error":"Order not found"},status=404)
    invoice=CommerceInvoice.objects.select_related("order").filter(
        order_id=order_id,order__customer_id=request.user.pk,
    ).first()
    if invoice is None:
        return JsonResponse({"error":"Order not found"},status=404)
''' + fix.OLD + '''    return JsonResponse({
        "order_id":order_id,
        "state":invoice.status,
        "network":invoice.network,
        "asset":invoice.asset,
''' + fix.OLD_FIELD + '''    })
'''

def test_only_checkout_status_changes_and_payment_state_cannot_be_forged():
    before = ast.parse(ORIGINAL)
    patched = fix.changed(ORIGINAL.encode()).decode()
    after = ast.parse(patched)
    assert len(before.body) == len(after.body) == 1
    assert fix.NEW in patched
    assert fix.OLD not in patched
    assert '"download_paths":verified_download_paths' in patched
    assert '"can_access_purchased_items":bool(verified_download_paths)' in patched
    assert 'CommerceReceipt.objects.create' not in patched
    assert 'Order.objects.update' not in patched
    assert 'settle_order_invoice' not in patched

def test_paid_only_returns_its_own_entitled_file_and_unpaid_empty():
    root = ast.parse(fix.changed(ORIGINAL.encode()))
    def identity(fn):
        return fn
    class FakeReply:
        def __init__(self, data, status=200):
            self.data, self.status_code = data, status
    class FakeQuery:
        def __init__(self, invoice):
            self.invoice, self.filter_args = invoice, None
        def filter(self, **kwargs):
            self.filter_args = kwargs
            return self
        def first(self):
            return self.invoice
    invoice = SimpleNamespace(status='paid', network='ethereum-mainnet', asset='ETH',
         order=SimpleNamespace(status='paid',items=SimpleNamespace(values_list=lambda *a,**k:[3,4])))
    query = FakeQuery(invoice)
    manager=SimpleNamespace(select_related=lambda *a:query)
    model=SimpleNamespace(Status=SimpleNamespace(PAID='paid'),objects=manager)
    namespace=dict(__name__='mpw_status_test',__package__='mpw_status_test',
       login_required=identity,never_cache=identity,require_GET=identity,
       _ready=lambda request: True, _deny=lambda:FakeReply({'error':'blocked'},404),
       JsonResponse=FakeReply,CommerceInvoice=model)
    exec(compile(ast.Module(body=root.body,type_ignores=[]),'<offline-contract>','exec'),namespace)
    view=namespace['checkout_status']
    p=ModuleType('mpw_status_test')
    p.__path__=[]
    e=ModuleType('mpw_status_test.entitlements')
    e.can_access_purchased_digital_item=lambda item,user:item==3 and user==77
    r=SimpleNamespace(user=SimpleNamespace(pk=77))
    def reverse(name,kwargs):
       assert name=='mpw_commerce:download'
       return '/commerce/download/'+str(kwargs['item_id'])+'/'
    with patch.dict(sys.modules,{'mpw_status_test':p,'mpw_status_test.entitlements':e}):
        with patch('django.urls.reverse',side_effect=reverse):
            paid=view(r,99)
            assert paid.status_code==200
            assert paid.data['download_paths']==['/commerce/download/3/']
            assert paid.data['can_access_purchased_items'] is True
            assert query.filter_args=={'order_id':99,'order__customer_id':77}
            invoice.status='awaiting'
            unpaid=view(r,99)
            assert unpaid.data['download_paths']==[]
            assert unpaid.data['can_access_purchased_items'] is False
            query.invoice=None
            assert view(r,99).status_code==404

def test_drift_guard_blocks_unknown_source_and_duplicate_patch():
    for source in ('def other():\\n    return None\\n', ORIGINAL+ORIGINAL, fix.changed(ORIGINAL.encode()).decode()):
        try:
            fix.changed(source.encode())
        except RuntimeError:
            continue
        raise AssertionError('Unsafe overwrite would have been permitted')
