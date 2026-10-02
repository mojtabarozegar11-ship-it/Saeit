"""Sole primary robot: durable goals, bounded executors and honest outcomes."""
from __future__ import annotations
import hashlib, json, multiprocessing as mp, os, sqlite3, time
from decimal import Decimal
from pathlib import Path
from django.db import connections
from django.db.models import Sum
from core.models import Product, Order
from core.internet_gateway import InternetGateway
from .demand_source_registry import DEMAND_SOURCES
from .foundation_demand import analyse, proposal

ROOT = Path('/home/zomorod2/Saeit')
BASE = ROOT / 'var/foundation_v2'
DB = BASE / 'runtime.sqlite3'
VERSION = 'MOJ-FOUNDATION-V2'
LEASE = 60

def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    os.replace(tmp, path)

def connect(path=None):
    path = Path(path or DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.executescript("""
    CREATE TABLE IF NOT EXISTS goals(id TEXT PRIMARY KEY, state TEXT, baseline TEXT,
      last_snapshot TEXT, last_health REAL DEFAULT 0, updated REAL);
    CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, goal TEXT, kind TEXT,
      payload TEXT, state TEXT, attempts INTEGER DEFAULT 0, not_before REAL DEFAULT 0,
      lease_until REAL DEFAULT 0, result TEXT, dedupe TEXT UNIQUE, updated REAL);
    CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, task_id INTEGER,
      kind TEXT, payload TEXT, ts REAL);
    CREATE TABLE IF NOT EXISTS sources(url TEXT PRIMARY KEY, name TEXT, detail INTEGER,
      state TEXT, failures INTEGER DEFAULT 0, visits INTEGER DEFAULT 0,
      next_at REAL DEFAULT 0, parent TEXT, last_result TEXT);
    CREATE TABLE IF NOT EXISTS opportunities(url TEXT PRIMARY KEY, evidence TEXT,
      state TEXT, draft_path TEXT, updated REAL);
    CREATE TABLE IF NOT EXISTS customer_handoffs(url TEXT PRIMARY KEY,
      product_id INTEGER, state TEXT, artifact_path TEXT, updated REAL);
    """)
    return c

def business_snapshot():
    paid = Order.objects.filter(status__in=['paid', 'completed'])
    totals = {x['currency']: str(x['total'] or 0) for x in
              paid.values('currency').annotate(total=Sum('total'))}
    return {'orders': Order.objects.count(), 'paid_orders': paid.count(),
            'revenue_by_currency': totals,
            'revenue': next(iter(totals.values())) if len(totals) == 1 else '0'}

def active_offer():
    p = Product.objects.filter(active=True).order_by('id').first()
    return None if p is None else {'id': p.id, 'title': p.title,
            'type': p.product_type, 'price': str(p.price), 'currency': p.currency}

def offer_readiness(offer):
    if not offer:
        return {'purchasable': False, 'missing': ['no_active_offer']}
    try:
        from core.product_pipeline import can_publish
        product = Product.objects.get(pk=offer['id'], active=True)
        approved = can_publish(product)
    except ImportError:
        return {'purchasable': False, 'missing': ['quality_executor_unavailable']}
    except Product.DoesNotExist:
        return {'purchasable': False, 'missing': ['active_product_missing']}
    return {'purchasable': bool(approved),
            'missing': [] if approved else ['product_quality_approval']}

def outcome(before, after):
    return {'order_growth': after['orders'] > before['orders'],
            'paid_order_growth': after['paid_orders'] > before['paid_orders'],
            'revenue_growth': any(Decimal(v) > Decimal(before.get('revenue_by_currency', {}).get(k, '0'))
                                  for k, v in after.get('revenue_by_currency', {}).items())
                              if 'revenue_by_currency' in after else
                              Decimal(after['revenue']) > Decimal(before['revenue'])}

def enqueue(c, kind, payload, dedupe, now):
    c.execute("""INSERT OR IGNORE INTO tasks(goal,kind,payload,state,dedupe,updated)
                 VALUES('primary-income',?,?,'ready',?,?)""",
              (kind, json.dumps(payload), dedupe, now))

def plan(c, offer, snapshot, now):
    row = c.execute("SELECT * FROM goals WHERE id='primary-income'").fetchone()
    if row is None:
        c.execute("INSERT INTO goals(id,state,baseline,last_snapshot,updated) VALUES(?,?,?,?,?)",
                  ('primary-income', 'active', json.dumps(snapshot), json.dumps(snapshot), now))
    else:
        gains = outcome(json.loads(row['baseline']), snapshot)
        # Observed receipts are separate from attribution to the robot.
        c.execute("UPDATE goals SET state=?,last_snapshot=?,updated=? WHERE id='primary-income'",
                  ('payment_observed' if gains['paid_order_growth'] and gains['revenue_growth']
                   else 'active', json.dumps(snapshot), now))
    c.execute("""UPDATE tasks SET state='retry',lease_until=0,not_before=?,updated=?
      WHERE state='running' AND lease_until<?""", (now + 5, now, now))
    matched_sources = (
        ('Automation project requests', 'https://www.freelancer.com/jobs/automation/'),
        ('AI project requests', 'https://www.freelancer.com/jobs/artificial-intelligence/'),
        ('Workflow project requests', 'https://www.freelancer.com/jobs/ai-workflow-automation/'))
    sources = matched_sources if offer and offer.get('type') in ('ai_automation', 'ai_agent') else DEMAND_SOURCES
    allowed_roots = {url for _, url in sources}
    for name, url in sources:
        c.execute("INSERT OR IGNORE INTO sources(url,name,detail,state) VALUES(?,?,0,'ready')",
                  (url, name))
    row = c.execute("SELECT last_health FROM goals WHERE id='primary-income'").fetchone()
    if now - row[0] >= 300:
        enqueue(c, 'health', {}, 'health:' + str(int(now // 300)), now)
        c.execute("UPDATE goals SET last_health=? WHERE id='primary-income'", (now,))
    if offer:
        for op in c.execute("""SELECT o.url FROM opportunities o
            LEFT JOIN customer_handoffs h ON h.url=o.url
            WHERE o.state='draft_ready' AND h.url IS NULL LIMIT 3""").fetchall():
            enqueue(c, 'handoff', {'url': op['url'], 'offer': offer},
                    'handoff:' + op['url'] + ':' + str(offer['id']), now)
        # Persisted opportunity state drives the next action, not a decorative strategy label.
        for op in c.execute("SELECT url FROM opportunities WHERE state='candidate' LIMIT 3").fetchall():
            enqueue(c, 'draft', {'url': op['url'], 'offer': offer},
                    'draft:' + op['url'] + ':' + str(offer['id']), now)
        pending = c.execute("SELECT 1 FROM tasks WHERE kind='fetch' AND state IN ('ready','retry','running')").fetchone()
        if not pending:
            eligible = c.execute("""SELECT * FROM sources WHERE next_at<=?
                ORDER BY detail DESC,visits ASC,next_at ASC,url""", (now,)).fetchall()
            source = next((s for s in eligible if s['url'] in allowed_roots or
                           s['parent'] and any(s['url'].split('/')[2] == u.split('/')[2] for u in allowed_roots)), None)
            if source:
                enqueue(c, 'fetch', {'source': {k: source[k] for k in
                                      ('url','name','detail','failures','visits','parent')}, 'offer': offer},
                        'fetch:' + source['url'] + ':' + str(source['visits']), now)
    c.commit()

def claim(c, now):
    c.execute('BEGIN IMMEDIATE')
    row = c.execute("""SELECT * FROM tasks WHERE state IN ('ready','retry')
       AND not_before<=? ORDER BY CASE kind WHEN 'draft' THEN 0
       WHEN 'handoff' THEN 0 WHEN 'health' THEN 1 ELSE 2 END,id LIMIT 1""", (now,)).fetchone()
    if row:
        c.execute("UPDATE tasks SET state='running',attempts=attempts+1,lease_until=?,updated=? WHERE id=?",
                  (now + LEASE, now, row['id']))
    c.commit()
    return dict(row) if row else None

def _fetch_child(sender, url):
    try:
        connections.close_all()
        result = InternetGateway.fetch(url, timeout=8, max_bytes=750000)
        sender.send({'ok': True, 'data': result})
    except Exception as exc:
        sender.send({'ok': False, 'error': type(exc).__name__})
    finally:
        sender.close()

def bounded_fetch(url, deadline=15):
    ctx = mp.get_context('fork')
    receiver, sender = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_fetch_child, args=(sender, url), daemon=True)
    process.start()
    sender.close()
    try:
        if not receiver.poll(deadline):
            return {'ok': False, 'error': 'executor_timeout'}
        return receiver.recv()
    except (EOFError, OSError):
        return {'ok': False, 'error': 'executor_process_failed'}
    finally:
        receiver.close()
        if process.is_alive():
            process.terminate()
        process.join(2)

def execute(task):
    payload = json.loads(task['payload'])
    if task['kind'] == 'fetch':
        source = payload['source']
        result = bounded_fetch(source['url'])
        if not result['ok']:
            return {'state': 'blocked', 'reason': result['error'], 'source': source}
        page = result['data']
        if page['http_status'] != 200 or 'html' not in page['content_type'].lower():
            return {'state': 'blocked', 'reason': 'unsupported_response', 'source': source}
        evidence = analyse(page['body'], page['final_url'], payload['offer'], bool(source['detail']))
        return {'state': 'completed' if evidence['links'] or evidence['candidate'] or evidence.get('candidates') else 'no_effect',
                'reason': 'evidence_discovered' if evidence['links'] or evidence['candidate']
                          else 'no_specific_opportunity',
                'source': source, 'evidence': evidence}
    if task['kind'] == 'draft':
        return {'state': 'completed', 'reason': 'draft_prepared', 'draft_request': payload}
    if task['kind'] == 'handoff':
        return {'state': 'completed', 'reason': 'customer_handoff_prepared',
                'handoff_request': payload}
    if task['kind'] == 'health':
        from django.core.management import call_command
        from io import StringIO
        checks = {}
        try:
            call_command('check', stdout=StringIO(), stderr=StringIO())
            checks['django.check'] = True
        except Exception:
            checks['django.check'] = False
        checks['site.inventory'] = active_offer() is not None
        policy = ROOT / 'var/moj_host_control/authorization.json'
        try:
            authorization = json.loads(policy.read_text())
            checks['host.access'] = authorization.get('enabled') is True
        except (OSError, ValueError):
            checks['host.access'] = False
        return {'state': 'completed' if all(checks.values()) else 'blocked',
                'reason': 'health_only_no_repair_claim', 'checks': checks}
    return {'state': 'blocked', 'reason': 'unsupported_capability'}

def commit(c, task, result, now):
    if result['state'] not in ('completed', 'no_effect', 'blocked'):
        raise ValueError('invalid_executor_state')
    if task['kind'] == 'fetch':
        source = result['source']
        failed = result['state'] == 'blocked'
        failures = source['failures'] + 1 if failed else 0
        delay = min(86400, 300 * (2 ** min(failures, 8))) if failed else 1800
        c.execute("""UPDATE sources SET state=?,failures=?,visits=visits+1,next_at=?,
          last_result=? WHERE url=?""",
          (result['state'], failures, now + delay, json.dumps(result), source['url']))
        evidence = result.get('evidence', {})
        additions = 0
        for link in evidence.get('links', []):
            if c.execute('SELECT count(*) FROM sources').fetchone()[0] >= 200:
                break
            added = c.execute("""INSERT OR IGNORE INTO sources(url,name,detail,state,parent)
               VALUES(?,?,1,'ready',?)""", (link['url'], link['title'], source['url']))
            additions += added.rowcount
        candidates = list(evidence.get('candidates') or [])
        if evidence.get('candidate'):
            candidates.append(evidence['candidate'])
        for candidate in candidates:
            added = c.execute("""INSERT OR IGNORE INTO opportunities(url,evidence,state,updated)
               VALUES(?,?,'candidate',?)""", (candidate['url'], json.dumps(candidate), now))
            additions += added.rowcount
        result['new_evidence_items'] = additions
        if not failed and additions == 0:
            result.update(state='no_effect', reason='no_new_specific_evidence')
    if task['kind'] == 'draft':
        payload = result.pop('draft_request')
        row = c.execute("SELECT evidence FROM opportunities WHERE url=?", (payload['url'],)).fetchone()
        if not row:
            result = {'state': 'blocked', 'reason': 'opportunity_missing'}
        else:
            candidate = json.loads(row[0])
            draft = proposal(candidate, payload['offer'])
            path = BASE / 'drafts' / (hashlib.sha256(payload['url'].encode()).hexdigest() + '.json')
            atomic_json(path, draft)
            persisted = json.loads(path.read_text())
            if persisted != draft or persisted['sent']:
                raise ValueError('draft_verification_failed')
            result['artifact'] = str(path)
            result['artifact_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            c.execute("UPDATE opportunities SET state='draft_ready',draft_path=?,updated=? WHERE url=?",
                      (str(path), now, payload['url']))
    if task['kind'] == 'handoff':
        from .customer_path import prepare_handoff
        payload = result.pop('handoff_request')
        row = c.execute('SELECT evidence FROM opportunities WHERE url=?',
                        (payload['url'],)).fetchone()
        if not row:
            result = {'state': 'blocked', 'reason': 'opportunity_missing'}
        else:
            candidate = json.loads(row[0])
            if candidate.get('product_id', payload['offer']['id']) != payload['offer']['id']:
                result = {'state': 'blocked', 'reason': 'opportunity_offer_changed'}
            else:
                handoff = prepare_handoff(candidate, payload['offer'],
                                          offer_readiness(payload['offer']))
                path = BASE / 'customer_handoffs' / (hashlib.sha256(payload['url'].encode()).hexdigest() + '.json')
                atomic_json(path, handoff)
                if json.loads(path.read_text()) != handoff:
                    raise ValueError('handoff_verification_failed')
                c.execute('INSERT OR REPLACE INTO customer_handoffs VALUES(?,?,?,?,?)',
                          (payload['url'], payload['offer']['id'], handoff['state'], str(path), now))
                result.update(artifact=str(path), missing=handoff['missing'],
                              artifact_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                              sent=False, customer_verified=False)
    c.execute("UPDATE tasks SET state=?,result=?,lease_until=0,updated=? WHERE id=?",
              (result['state'], json.dumps(result), now, task['id']))
    c.execute("INSERT INTO events(task_id,kind,payload,ts) VALUES(?,?,?,?)",
              (task['id'], result['state'], json.dumps(result), now))
    c.commit()
    return result

def summary(c, cycle, snapshot, offer, result):
    counts = {r[0]: r[1] for r in c.execute('SELECT state,count(*) FROM tasks GROUP BY state')}
    goal = c.execute("SELECT * FROM goals WHERE id='primary-income'").fetchone()
    return {'architecture': VERSION, 'cycle': cycle, 'identity': 'moj_1ro_1',
            'goal': goal['state'], 'task_states': counts, 'business': snapshot,
            'business_delta': outcome(json.loads(goal['baseline']), snapshot),
            'robot_attributed_revenue': '0', 'revenue_attribution': 'not_established',
            'active_offer': offer, 'outcome': result,
            'offer_readiness': offer_readiness(offer),
            'customer_handoffs_prepared': c.execute('SELECT count(*) FROM customer_handoffs').fetchone()[0],
            'opportunity_candidates': c.execute("SELECT count(*) FROM opportunities WHERE state IN ('candidate','draft_ready')").fetchone()[0],
            'drafts_ready': c.execute("SELECT count(*) FROM opportunities WHERE state='draft_ready'").fetchone()[0],
            'source_count': c.execute('SELECT count(*) FROM sources').fetchone()[0],
            'execution_capabilities': ['public_page_fetch', 'opportunity_extraction',
                                       'proposal_draft', 'health_checks'],
            'missing_capabilities': ['verified_customer_contact', 'contract_submission',
                                      'general_code_repair'],
            'updated_at': time.time()}

def tick(cycle):
    c = connect()
    try:
        offer, snapshot, now = active_offer(), business_snapshot(), time.time()
        plan(c, offer, snapshot, now)
        task = claim(c, now)
        result = {'state': 'waiting', 'reason': 'source_backoff' if offer else 'no_active_offer'}
        if task:
            try:
                result = execute(task)
                result = commit(c, task, result, time.time())
            except Exception as exc:
                c.rollback()
                result = {'state': 'blocked', 'reason': type(exc).__name__}
                c.execute("UPDATE tasks SET state='retry',not_before=?,lease_until=0,result=?,updated=? WHERE id=?",
                          (time.time() + min(3600, 30 * 2 ** min(task['attempts'], 6)),
                           json.dumps(result), time.time(), task['id']))
                c.commit()
        row = summary(c, cycle, business_snapshot(), offer, result)
        atomic_json(BASE / 'state.json', row)
        atomic_json(ROOT / 'var/core100/state.json', row)
        return row
    finally:
        c.close()
