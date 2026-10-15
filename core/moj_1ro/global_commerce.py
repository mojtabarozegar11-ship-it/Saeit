"""Global commercial readiness and explicit-input comparable-competitor pricing."""
import json,time
from decimal import Decimal,InvalidOperation,ROUND_FLOOR
from urllib.parse import urlparse
from .foundation_runtime import ROOT,connect
from .operational_law import current

def number(value):
    if isinstance(value,bool): raise ValueError('invalid_price_number')
    if len(str(value))>64:raise ValueError('invalid_price_number')
    try:n=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError):raise ValueError('invalid_price_number')
    if not n.is_finite() or n<0 or n>Decimal('1e18') or n and n<Decimal('1e-12'):raise ValueError('invalid_price_number')
    return n

def validate_price(payload,now=None):
    now=time.time() if now is None else now
    spec=current()['global_commerce']['pricing']
    currency,scope,unit=(payload.get(k) for k in ('currency','scope','unit'))
    if not all(isinstance(x,str) and x.strip() for x in (currency,scope,unit)):
        raise ValueError('comparable_product_definition_required')
    quotes=payload.get('quotes')
    if not isinstance(quotes,list) or not 2<=len(quotes)<=20:
        raise ValueError('at_least_two_main_competitor_quotes_required')
    identities=set()
    for q in quotes:
        if not isinstance(q,dict):raise ValueError('invalid_competitor_quote')
        if any(q.get(k)!=payload[k] for k in ('currency','scope','unit')):
            raise ValueError('competitor_quote_not_comparable')
        if q.get('main_competitor') is not True or not isinstance(q.get('competitor'),str) or not q['competitor'].strip():
            raise ValueError('main_competitor_identity_required')
        identity=q['competitor'].strip().casefold()
        if identity in identities:raise ValueError('duplicate_competitor')
        identities.add(identity)
        url=urlparse(str(q.get('source_url','')))
        if url.scheme!='https' or not url.hostname or url.username or url.password:
            raise ValueError('https_quote_source_required')
        date=q.get('quoted_at')
        if isinstance(date,bool) or not isinstance(date,(int,float)) or not 0<=now-date<=spec['max_quote_age_seconds']:
            raise ValueError('stale_or_invalid_quote_date')
        if number(q.get('price'))<=0:raise ValueError('competitor_price_must_be_positive')
    if 'unit_cost' not in payload or 'fee_rate' not in payload:
        raise ValueError('measured_unit_cost_and_fee_required')
    number(payload['unit_cost'])
    if number(payload['fee_rate'])>=1:raise ValueError('invalid_fee_rate')
    quantum=number(payload.get('quantum','0.01'))
    if not 0<quantum<=1:raise ValueError('invalid_price_quantum')
    return payload

def price(payload):
    validate_price(payload)
    policy=current()['global_commerce']['pricing']
    reference=min(number(q['price']) for q in payload['quotes'])
    target=reference*(1-number(policy['competitor_discount_percent'])/100)
    quantum=number(payload.get('quantum','0.01'))
    target=(target/quantum).to_integral_value(rounding=ROUND_FLOOR)*quantum
    net=target*(1-number(payload['fee_rate']))
    viable=target>0 and net>=number(payload['unit_cost'])
    return {'state':'calculated' if viable else 'blocked','currency':payload['currency'],
        'competitor_reference':str(reference),'discount_percent':policy['competitor_discount_percent'],
        'proposed_price':str(target) if viable else None,'target_price':str(target),
        'estimated_net_after_fees':str(net),'unit_cost':str(number(payload['unit_cost'])),
        'reason':'explicit_input_calculation' if viable else 'target_price_does_not_cover_measured_costs',
        'quote_verification':'not_independently_verified','source':'explicit_quote_inputs',
        'price_applied':False,'sales_executed':0,'realized_profit':None}

def audit():
    law=current();mandate=law['global_commerce']
    c=connect()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS commercial_readiness(
          capability TEXT PRIMARY KEY,state TEXT,evidence TEXT,updated REAL)""")
        from core.economic_trade_email import mailbox_status
        email=mailbox_status()
        observations={
          'public_research':{'state':'available','mode':'bounded_public_reads'},
          'commercial_email':{'state':'not_verified','address_configured':email['configured'],
                              'send_gate_enabled':email['active'],'smtp_imap_verified':False},
          'contact_number':{'state':'not_verified','number_provisioned':False},
          'platform_accounts':{'state':'not_verified','authenticated_provider_accounts_verified':False},
          'multilingual_localization':{'state':'not_verified','all_languages_quality_verified':False},
          'production_delivery':{'state':'not_verified','general_production_and_delivery_verified':False},
          'competitor_pricing':{'state':'available','mode':'validated_input_calculation',
                              'live_competitor_price_collector_verified':False},
          'payment_reconciliation':{'state':'not_verified','external_settlement_verified':False},
        }
        try:
            policy=json.loads((ROOT/'var/moj_host_control/authorization.json').read_text())
            observations['host_execution']={'state':'configured' if policy.get('enabled') is True else 'not_verified',
                                            'mode':'existing_governed_host_operations'}
        except (OSError,ValueError):
            observations['host_execution']={'state':'not_verified'}
        for capability,item in observations.items():
            c.execute("""INSERT INTO commercial_readiness VALUES(?,?,?,?)
              ON CONFLICT(capability) DO UPDATE SET state=excluded.state,
              evidence=excluded.evidence,updated=excluded.updated""",
              (capability,item['state'],json.dumps(item),time.time()))
        c.commit()
        missing=[k for k,v in observations.items() if v['state']=='not_verified']
        missing.append('verified_live_comparable_competitor_quotes')
        return {'state':'blocked' if missing else 'observed','repository':'Saeit',
            'target_countries':mandate['target_countries'],'target_languages':mandate['target_languages'],
            'target_platforms':mandate['target_platforms'],'infrastructure':observations,
            'missing':missing,'worldwide_access_verified':False,'new_external_accounts_created':0,
            'prices_changed':0,'constitution_sha256':law['sha256']}
    finally:c.close()
