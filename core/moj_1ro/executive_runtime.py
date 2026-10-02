"""One primary executive, multiple domains, explicit executable contracts."""
from __future__ import annotations
import hashlib, json, math, os, sqlite3, time, uuid
from decimal import Decimal
from pathlib import Path
from .foundation_runtime import ROOT, BASE, connect, atomic_json, business_snapshot

DOMAINS = {
    'global_commerce': {'repository':'Saeit','objective':'develop worldwide multilingual commercial infrastructure and evidence-led digital production with fair comparable competitor pricing'},
    'finance_commerce': {'repository':'Saeit','objective':'build and operate the economy financial section and e-commerce, including verified game payment and delivery integration'},
    'income_research': {'repository':'Saeit','objective':'continuously research online income methods and valuable content, products and digital assets; measure real revenue growth'},
    'self_improvement': {'repository':'Saeit','objective':'continuously upgrade the primary robot and every project component with verified execution'},
    'economics': {'repository':'Saeit','objective':'measure revenue, costs and unit economics'},
    'business': {'repository':'Saeit','objective':'connect qualified demand to delivered paid orders'},
    'site': {'repository':'Saeit','objective':'diagnose, apply authorized code changes and verify deployment'},
    'trading': {'repository':'Saeit','objective':'test strategies before broker execution'},
    'games': {'repository':'Bazei','objective':'research, build, quality-test, publish and maintain advanced games for USA and global gamers; events, expansions and measured income; game one approval before another'},
}
OPERATIONS = {
    ('global_commerce','audit'), ('global_commerce','price_compare'),
    ('finance_commerce','audit'),
    ('income_research','research'),
    ('self_improvement','audit'), ('self_improvement','repair'),
    ('economics','audit'), ('economics','unit_economics'),
    ('business','audit'), ('site','audit'), ('site','apply_patch'),
    ('trading','audit'), ('trading','backtest'), ('games','audit'),
}
LEASE_SECONDS = 300
EXECUTIVE_STATE = BASE / 'executive.json'

def schema(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS executive_goals(domain TEXT PRIMARY KEY,objective TEXT,
      repository TEXT,last_result TEXT,last_run REAL DEFAULT 0,updated REAL);
    CREATE TABLE IF NOT EXISTS executive_tasks(id TEXT PRIMARY KEY,domain TEXT,
      operation TEXT,payload TEXT,priority INTEGER, state TEXT,attempts INTEGER DEFAULT 0,
      not_before REAL DEFAULT 0,lease_until REAL DEFAULT 0,request_id TEXT UNIQUE,
      fingerprint TEXT,result TEXT,owner_id INTEGER,created REAL,updated REAL);
    CREATE TABLE IF NOT EXISTS executive_events(id INTEGER PRIMARY KEY,task_id TEXT,
      event TEXT,payload TEXT,ts REAL);
    """)
    for domain, spec in DOMAINS.items():
        c.execute("""INSERT INTO executive_goals(domain,objective,repository,updated) VALUES(?,?,?,?)
          ON CONFLICT(domain) DO UPDATE SET objective=excluded.objective,repository=excluded.repository""",
                  (domain,spec['objective'],spec['repository'],time.time()))
    c.commit()

def validate(domain, operation, payload):
    if (domain,operation) not in OPERATIONS:
        raise ValueError('unsupported_executable_operation')
    if not isinstance(payload,dict) or len(json.dumps(payload)) > 600000:
        raise ValueError('invalid_payload')
    if operation == 'price_compare':
        from .global_commerce import validate_price
        validate_price(payload)
    if operation == 'repair':
        from .operational_law import automatic_allowed
        if not automatic_allowed(domain,operation,payload):
            raise ValueError('unsupported_repair_recipe')
    if operation == 'unit_economics':
        required = {'price','variable_cost','fixed_cost','units','currency'}
        if not required <= payload.keys():
            raise ValueError('economic_inputs_missing')
        for key in required - {'currency'}:
            x = Decimal(str(payload[key]))
            if not x.is_finite() or x < 0:
                raise ValueError('invalid_economic_input')
    if operation == 'backtest':
        prices = payload.get('prices')
        window = payload.get('window',5)
        cost = payload.get('cost_rate',0)
        if (not isinstance(prices,list) or not 20 <= len(prices) <= 10000 or
                type(window) is not int or not 2 <= window < len(prices)):
            raise ValueError('invalid_backtest_data')
        if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x <= 0 for x in prices):
            raise ValueError('invalid_backtest_prices')
        if isinstance(cost,bool) or not isinstance(cost,(int,float)) or not math.isfinite(cost) or not 0 <= cost < .1:
            raise ValueError('invalid_backtest_cost')
    if operation == 'apply_patch':
        changes = payload.get('changes')
        if not isinstance(changes,list) or not 1 <= len(changes) <= 10:
            raise ValueError('invalid_patch_batch')
        for item in changes:
            if not isinstance(item,dict) or not {'path','expected_sha256','content'} <= item.keys():
                raise ValueError('patch_preimage_required')
    return payload

def submit(domain, operation, payload=None, *, owner=None, request_id=None,
           priority=50, automatic=False, connection=None):
    payload = validate(domain,operation,payload or {})
    if not automatic and not (owner and (getattr(owner,'is_staff',False) or getattr(owner,'is_superuser',False))):
        raise PermissionError('executive_owner_authority_required')
    from .operational_law import automatic_allowed
    if automatic and not automatic_allowed(domain,operation,payload):
        raise PermissionError('automatic_operation_not_authorized')
    c = connection or connect()
    try:
        schema(c)
        rid = request_id or uuid.uuid4().hex
        fp = hashlib.sha256(json.dumps([domain,operation,payload],sort_keys=True).encode()).hexdigest()
        old = c.execute("SELECT id,fingerprint,state FROM executive_tasks WHERE request_id=?",(rid,)).fetchone()
        if old:
            if old['fingerprint'] != fp:
                raise ValueError('idempotency_request_changed')
            return {'ok':True,'task_id':old['id'],'state':old['state'],'executed':False,'existing':True}
        tid,now = uuid.uuid4().hex,time.time()
        c.execute("""INSERT INTO executive_tasks(id,domain,operation,payload,priority,state,
          request_id,fingerprint,owner_id,created,updated) VALUES(?,?,?,?,?,'ready',?,?,?,?,?)""",
          (tid,domain,operation,json.dumps(payload),max(0,min(100,int(priority))),rid,fp,
           getattr(owner,'pk',None),now,now))
        c.commit()
        return {'ok':True,'task_id':tid,'state':'ready','executed':False}
    finally:
        if connection is None: c.close()

def backtest(payload):
    prices,window = payload['prices'],payload.get('window',5)
    fee = payload.get('cost_rate',0)
    equity,peak,drawdown,position,trades = 1.,1.,0.,0,0
    for i in range(window,len(prices)):
        # Choose exposure using only prices known BEFORE the next return.
        average = sum(prices[i-window:i])/window
        chosen = int(prices[i-1] > average)
        if chosen != position:
            equity *= 1-fee
            trades += 1
        equity *= 1 + chosen*(prices[i]/prices[i-1]-1)
        position = chosen
        peak = max(peak,equity)
        drawdown = max(drawdown,1-equity/peak)
    if position:
        equity *= 1-fee
        drawdown = max(drawdown,1-equity/peak)
    return {'state':'calculated','mode':'offline_backtest','return_pct':round((equity-1)*100,6),
            'max_drawdown_pct':round(drawdown*100,6),'position_changes':trades,
            'sample_count':len(prices),'cost_rate':fee,'live_trades':0,
            'live_profit':None,'limitations':['input data quality unverified','no slippage model',
                                            'single dataset is not out-of-sample proof']}

def perform(domain, operation, payload):
    if domain == 'global_commerce':
        from .global_commerce import audit, price
        return price(payload) if operation == 'price_compare' else audit()
    if domain in ('games','finance_commerce'):
        from .lifecycle_mandates import games_audit, finance_audit
        return games_audit() if domain == 'games' else finance_audit()
    if domain == 'income_research':
        from .income_research import research
        return research()
    if domain == 'self_improvement':
        from .self_improvement import audit, repair
        return repair(payload) if operation == 'repair' else audit()
    if operation == 'unit_economics':
        from .finance_toolkit import unit_economics
        return {'state':'calculated','currency':payload['currency'],'calculation':unit_economics(payload),
                'realized_profit':None,'source':'explicit_inputs'}
    if operation == 'backtest': return backtest(payload)
    if operation == 'apply_patch':
        from .orchestrator import Moj1roOrchestrator
        from .host_cycle_dispatch import execute as deploy
        result = deploy(Moj1roOrchestrator(),{'operation':'apply_patch','changes':payload['changes']})
        if not result.get('ok'): raise RuntimeError('deployment_not_verified')
        return {'state':'applied','receipt':result,'repository':'Saeit',
                'verification':'preimage_syntax_django_check_static_restart',
                'visual_acceptance':'not_tested'}
    if domain == 'economics':
        from core.models import Product
        return {'state':'observed','business':business_snapshot(),
                'offers':list(Product.objects.filter(active=True).values('id','title','price','currency'))[:20],
                'profit_known':False,'missing':['verified_cost_ledger','customer_acquisition_cost'],
                'next_operation':'unit_economics_when_measured_inputs_exist'}
    if domain == 'business':
        from .customer_path import snapshot as customer_snapshot
        from .foundation_runtime import active_offer, offer_readiness
        c=connect()
        try:
            counts={r[0]:r[1] for r in c.execute('SELECT state,count(*) FROM opportunities GROUP BY state')}
            customer_path=customer_snapshot(c)
        finally: c.close()
        b=business_snapshot()
        readiness=offer_readiness(active_offer())
        return {'state':'blocked' if readiness['missing'] or b['orders']==0 else 'observed',
                'business':b,'opportunity_states':counts,
                'bottleneck':readiness['missing'][0] if readiness['missing'] else
                    ('customer_contact_and_contract' if b['orders']==0 else 'payment_conversion'),
                'offer_readiness':readiness,'customer_path':customer_path,
                'contact_executor':'not_connected','draft_is_customer':False}
    if domain == 'site':
        from django.core.management import call_command
        from io import StringIO
        from core.internet_gateway import InternetGateway
        call_command('check',stdout=StringIO(),stderr=StringIO())
        pages={}
        for path in ('/','/personnel/','/admin/'):
            try:
                h=InternetGateway.health_check('https://zomorodmelal.ir'+path)
                pages[path]={'http_status':h['http_status'],'healthy':h['status']=='healthy'}
            except Exception as exc:
                pages[path]={'healthy':False,'error':type(exc).__name__}
        healthy=all(r['healthy'] for r in pages.values())
        return {'state':'observed' if healthy else 'blocked','django_check':True,'public_pages':pages,
                'repairs_applied':0,'authenticated_flows':'not_tested',
                'next_operation':'apply_patch_with_verified_preimage' if not healthy else 'monitor'}
    if domain == 'trading':
        from financial_core.mt5_readiness import readiness
        r=readiness(live_probe=False)
        if r.get('bridge_url') == 'configured':
            r=readiness(live_probe=True)
        connected=r.get('live_connected') is True
        return {'state':'observed' if connected else 'blocked','mode':'connection_readiness',
                'broker_connected':connected,'live_execution_enabled':r.get('trading_enabled') is True,
                'bridge_url':r.get('bridge_url'),'next_operation':'backtest',
                'missing':['verified_broker_transport'] if not connected else []}
    raise ValueError('unimplemented_domain')

def run_one(c, now):
    c.execute("""UPDATE executive_tasks SET state='retry',lease_until=0,not_before=?
       WHERE state='running' AND lease_until<?""",(now+10,now))
    c.commit()
    c.execute('BEGIN IMMEDIATE')
    row=c.execute("""SELECT * FROM executive_tasks WHERE state IN ('ready','retry')
      AND not_before<=? ORDER BY priority DESC,created,id LIMIT 1""",(now,)).fetchone()
    if row:
        c.execute("UPDATE executive_tasks SET state='running',attempts=attempts+1,lease_until=?,updated=? WHERE id=?",
                  (now+LEASE_SECONDS,now,row['id']))
    c.commit()
    if not row: return {'state':'idle'}
    task=dict(row)
    try:
        result=perform(task['domain'],task['operation'],json.loads(task['payload']))
        if result.get('state') not in ('observed','calculated','applied','blocked'):
            raise ValueError('executor_outcome_not_proven')
        path=BASE/'executive_evidence'/(task['id']+'.json')
        atomic_json(path,result)
        if json.loads(path.read_text()) != json.loads(json.dumps(result,default=str)):
            raise ValueError('receipt_verification_failed')
        result['evidence_path']=str(path)
        result['evidence_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        c.execute("UPDATE executive_tasks SET state=?,result=?,lease_until=0,updated=? WHERE id=?",
                  (result['state'],json.dumps(result,default=str),time.time(),task['id']))
        c.execute("UPDATE executive_goals SET last_result=?,last_run=?,updated=? WHERE domain=?",
                  (json.dumps(result,default=str),time.time(),time.time(),task['domain']))
    except Exception as exc:
        result={'state':'blocked','error':type(exc).__name__}
        c.execute("UPDATE executive_tasks SET state='blocked',result=?,lease_until=0,updated=? WHERE id=?",
                  (json.dumps(result),time.time(),task['id']))
        c.execute("UPDATE executive_goals SET last_result=?,last_run=?,updated=? WHERE domain=?",
                  (json.dumps(result),time.time(),time.time(),task['domain']))
    c.execute("INSERT INTO executive_events(task_id,event,payload,ts) VALUES(?,?,?,?)",
              (task['id'],result['state'],json.dumps(result,default=str),time.time()))
    c.commit()
    return {'task_id':task['id'],'domain':task['domain'],'operation':task['operation'],**result}

def portfolio(c=None):
    own=c is None
    c=c or connect()
    try:
        schema(c)
        domains={}
        for row in c.execute('SELECT * FROM executive_goals'):
            result=json.loads(row['last_result'] or '{}')
            domains[row['domain']]={'objective':row['objective'],'repository':row['repository'],
                'last_checked':row['last_run'],'evidence_status':result.get('state','untested'),
                'result':result}
        from .operational_law import current
        return {'constitution':current(),'identity':'moj_1ro_1','management_mode':'multi_domain_execution',
                'domains':domains,'states':{r[0]:r[1] for r in c.execute(
                    'SELECT state,count(*) FROM executive_tasks GROUP BY state')},
                'local_reasoning_model':'not_configured','general_autonomous_coding':'not_proven',
                'live_trading_proven':False,'game_build_proven':False,'updated_at':time.time()}
    finally:
        if own:c.close()

def tick(cycle):
    c=connect()
    try:
        schema(c)
        from .operational_law import current, priority
        law = current()
        if law.get('article_3'):
            from .lifecycle_mandates import sync
            sync(c,law)
        atomic_json(BASE/'constitution_active.json',{'version':law['version'],
            'sha256':law['sha256'],'read_at':time.time(),'cycle':cycle})
        interval = max(30, int(law.get('continuous_income_research',{}).get('interval_seconds',900)))
        now = time.time()
        for domain in DOMAINS:
            goal=c.execute('SELECT last_run FROM executive_goals WHERE domain=?',(domain,)).fetchone()
            pending = c.execute("""SELECT 1 FROM executive_tasks WHERE domain=?
                AND operation IN ('audit','research') AND state IN ('ready','retry','running')""",
                (domain,)).fetchone()
            if now-goal[0]>=interval and not pending:
                operation = 'research' if domain == 'income_research' else 'audit'
                submit(domain,operation,request_id='audit:'+domain+':'+str(int(now//interval)),
                       priority=priority(domain),automatic=True,connection=c)
        result=run_one(c,time.time())
        status=portfolio(c)
        status.update(cycle=cycle,outcome=result)
        atomic_json(EXECUTIVE_STATE,status)
        return status
    finally:c.close()

def status_handler(payload=None, **kwargs):
    return {'ok':True,'mode':'observed_state','executed':False,'portfolio':portfolio()}

def submit_handler(payload=None, owner=None, **kwargs):
    p=payload or {}
    return submit(p.get('domain'),p.get('operation'),p.get('input',{}),owner=owner,
                  request_id=p.get('request_id'),priority=p.get('priority',50))

HANDLERS={'executive.status':status_handler,'executive.submit':submit_handler}
