"""Explicit execution primitives. Registry labels alone are not proof of skill."""
from .executive_runtime import HANDLERS

PRIMITIVES = {
    'status','performance','product.audit','django.check','git.status','logs.read',
    'content.inventory','advisor.consult','internet.read','host.access',
    'host.status','host.execute','host.django_check','site.inventory',
    'finance.unit_economics','finance.funnel','finance.roi','finance.cashflow',
    'business.orders','business.revenue','business.offer','business.funnel',
}

def handlers(registry):
    return {**{k:registry[k] for k in PRIMITIVES if k in registry},**HANDLERS}

def classification(code):
    if code == 'advisor.consult': return 'advisory_only'
    if code == 'executive.submit': return 'queued_not_executed'
    if code == 'host.execute': return 'governed_mutation'
    if code.startswith('finance.'): return 'calculation_not_realized_income'
    return 'inspection'
