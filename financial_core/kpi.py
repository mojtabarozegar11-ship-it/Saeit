from decimal import Decimal

def snapshot(registry):
    units=tuple(registry.units.values())
    revenue=sum((u.revenue for u in units),Decimal('0'))
    cost=sum((u.cost for u in units),Decimal('0'))
    return {'units':len(units),'active':len(registry.active()),'gross_revenue':revenue,'cost':cost,'net_profit':revenue-cost,'failures':sum(u.failures for u in units)}
