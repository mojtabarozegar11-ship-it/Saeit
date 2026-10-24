"""Recompute arithmetic in Ding & Du (2024), not their field results."""
from decimal import Decimal, ROUND_HALF_UP

D = Decimal

def round2(value):
    return value.quantize(D('0.01'), rounding=ROUND_HALF_UP)

sim_et = D('195.26') * D('0.1021')
sim_sensor = D('195.26') * D('0.0393')
monthly_tree = D('11.3') * D('0.0952')
monthly_region = monthly_tree * D('600')
rounded_region = round2(monthly_tree) * D('600')
payback_months = D('294.8') / monthly_region

assert round2(sim_et) == D('19.94')
assert round2(sim_sensor) == D('7.67')
assert round2(monthly_tree) == D('1.08')
assert round2(monthly_region) == D('645.46')
assert rounded_region == D('648.00')
assert D('0.45') < payback_months < D('0.47')

print('PASS: independent arithmetic consistency checks')
for name, value in [('simulated ET billion gallons', sim_et),
                    ('simulated sensor billion gallons', sim_sensor),
                    ('conditional monthly saving per tree USD', monthly_tree),
                    ('conditional monthly saving per 600-tree region USD', monthly_region),
                    ('rounded intermediate regional estimate USD', rounded_region),
                    ('conditional payback months', payback_months)]:
    print(f'{name}: {value}')
