from __future__ import annotations
from decimal import Decimal, InvalidOperation

def _d(v, default='0'):
    try:
        return Decimal(str(v if v is not None else default))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f'invalid_number:{v}')

def unit_economics(payload=None, **kwargs):
    p=payload or {}
    price=_d(p.get('price')); variable=_d(p.get('variable_cost'))
    fixed=_d(p.get('fixed_cost')); units=_d(p.get('units'))
    revenue=price*units; variable_total=variable*units
    gross_profit=revenue-variable_total; profit=gross_profit-fixed
    margin=(gross_profit/revenue*100) if revenue else Decimal('0')
    contribution=price-variable
    breakeven=(fixed/contribution) if contribution>0 else None
    return {'ok':True,'revenue':str(revenue),'variable_cost_total':str(variable_total),
      'fixed_cost':str(fixed),'gross_profit':str(gross_profit),'profit':str(profit),
      'gross_margin_pct':str(round(margin,4)),'contribution_per_unit':str(contribution),
      'breakeven_units':None if breakeven is None else str(round(breakeven,4))}

def funnel_metrics(payload=None, **kwargs):
    p=payload or {}
    visitors=_d(p.get('visitors')); leads=_d(p.get('leads')); orders=_d(p.get('orders'))
    paid=_d(p.get('paid_orders',p.get('paid'))); revenue=_d(p.get('revenue'))
    spend=_d(p.get('acquisition_cost',p.get('spend')))
    pct=lambda a,b: str(round((a/b*100),4)) if b else '0'
    return {'ok':True,'lead_rate_pct':pct(leads,visitors),
      'order_conversion_pct':pct(orders,visitors),'lead_to_order_pct':pct(orders,leads),
      'payment_success_pct':pct(paid,orders),
      'average_order_value':str(round(revenue/paid,4)) if paid else '0',
      'cac':str(round(spend/paid,4)) if paid else None,
      'roas':str(round(revenue/spend,4)) if spend else None}

def investment_metrics(payload=None, **kwargs):
    p=payload or {}
    investment=_d(p.get('investment')); gain=_d(p.get('gain',p.get('net_gain')))
    revenue=_d(p.get('revenue')); cost=_d(p.get('cost'))
    net=(revenue-cost) if ('revenue' in p or 'cost' in p) else gain
    roi=(net/investment*100) if investment else None
    return {'ok':True,'investment':str(investment),'net_gain':str(net),
      'roi_pct':None if roi is None else str(round(roi,4))}

def cashflow(payload=None, **kwargs):
    p=payload or {}
    opening=_d(p.get('opening_cash'))
    inflows=sum((_d(x) for x in (p.get('inflows') or [])),Decimal('0'))
    outflows=sum((_d(x) for x in (p.get('outflows') or [])),Decimal('0'))
    closing=opening+inflows-outflows
    return {'ok':True,'opening_cash':str(opening),'inflows':str(inflows),
      'outflows':str(outflows),'net_cashflow':str(inflows-outflows),'closing_cash':str(closing)}
