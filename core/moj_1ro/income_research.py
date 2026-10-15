"""Recurring evidence-led income research; no API, publication, sales or invented profit."""
import hashlib, json, time
from .foundation_runtime import connect, bounded_fetch, business_snapshot
from .foundation_demand import analyse
from .operational_law import current

# Public customer request categories are research seeds, not endorsed income methods.
SEEDS = [
 ('internet_income_methods','ai_automation','https://www.freelancer.com/jobs/automation/','service'),
 ('valuable_content','online_education','https://www.freelancer.com/jobs/elearning/','content'),
 ('digital_products','digital_products','https://www.freelancer.com/jobs/excel/','product'),
 ('digital_assets','design_studio','https://www.freelancer.com/jobs/graphic-design/','asset'),
 ('real_revenue_growth','marketing_sales','https://www.freelancer.com/jobs/internet-marketing/','growth'),
]
QUALITY = {
 'service':['agreed_scope','working_delivery','customer_acceptance','support_terms'],
 'content':['source_accuracy','originality_and_rights','useful_learning_outcome','reader_review'],
 'product':['measurable_customer_problem','functional_test','documentation','rights_and_licensing'],
 'asset':['clear_ownership_and_rights','usable_format','technical_validation','customer_use_case'],
 'growth':['verified_baseline','controlled_experiment','measured_cost','paid_conversion_and_receipts'],
}

def schema(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS income_research_sources(
      topic TEXT PRIMARY KEY,visits INTEGER DEFAULT 0,failures INTEGER DEFAULT 0,
      next_at REAL DEFAULT 0,last_result TEXT);
    CREATE TABLE IF NOT EXISTS income_research_cycles(
      id INTEGER PRIMARY KEY,topic TEXT,url TEXT,state TEXT,result TEXT,created REAL);
    CREATE TABLE IF NOT EXISTS income_research_briefs(
      fingerprint TEXT PRIMARY KEY,topic TEXT,evidence TEXT,brief TEXT,updated REAL);
    CREATE TABLE IF NOT EXISTS income_research_metrics(
      id INTEGER PRIMARY KEY,snapshot TEXT,created REAL);
    """)
    for topic,_,_,_ in SEEDS:
        c.execute('INSERT OR IGNORE INTO income_research_sources(topic) VALUES(?)',(topic,))
    c.commit()

def receipt_delta(before, after):
    from decimal import Decimal
    currencies=set(before.get('revenue_by_currency',{})) | set(after.get('revenue_by_currency',{}))
    return {'paid_order_change':after['paid_orders']-before.get('paid_orders',0),
        'revenue_change_by_currency':{k:str(Decimal(after.get('revenue_by_currency',{}).get(k,'0'))-
            Decimal(before.get('revenue_by_currency',{}).get(k,'0'))) for k in currencies},
        'robot_attribution':'not_established','verified_profit':None}

def brief(candidate, topic, kind):
    return {'topic':topic,'customer_problem':candidate['title'],
        'source_url':candidate['url'],'evidence_status':'unverified_public_request',
        'artifact_type':kind,'state':'internal_production_plan',
        'target_customer':'request author; identity and eligibility require verification',
        'monetization_hypothesis':'paid_delivery_or_license_after_fit_and_terms_validation',
        'price':None,'cost':None,'profit':None,'quality_checks':QUALITY[kind],
        'experiment':{'action':'validate_fit_then_build_testable_sample',
            'measure':'customer_acceptance_and_paid_order','paid_target':None},
        'missing':['validated_scope','working_production_executor','verified_sales_and_payment_path'],
        'produced':False,'published':False,'sent':False,'revenue_realized':False}

def research():
    law=current()
    mandate=law.get('continuous_income_research')
    if not mandate: raise PermissionError('income_research_not_authorized')
    c=connect()
    try:
        schema(c)
        now=time.time()
        previous=c.execute('SELECT snapshot FROM income_research_metrics ORDER BY id DESC LIMIT 1').fetchone()
        snapshot=business_snapshot()
        baseline=json.loads(previous[0]) if previous else snapshot
        c.execute('INSERT INTO income_research_metrics(snapshot,created) VALUES(?,?)',(json.dumps(snapshot),now))
        eligible=c.execute('SELECT * FROM income_research_sources WHERE next_at<=? ORDER BY visits,topic',(now,)).fetchall()
        if not eligible:
            c.commit()
            return {'state':'observed','reason':'all_research_sources_in_backoff',
                'receipt_delta':receipt_delta(baseline,snapshot),'new_briefs':0,'products_produced':0}
        row=eligible[0]
        topic,domain,url,kind=next(x for x in SEEDS if x[0]==row['topic'])
        fetched=bounded_fetch(url)
        result={'state':'blocked','topic':topic,'source_url':url,'researched_at':now,
            'constitution_sha256':law['sha256'],'new_briefs':0,'products_produced':0,
            'receipt_delta':receipt_delta(baseline,snapshot),'publication_performed':False}
        page=fetched.get('data') or {}
        valid=(fetched.get('ok') and page.get('http_status')==200 and
               'html' in page.get('content_type','').lower() and bool(page.get('body','').strip()))
        if valid:
            evidence=analyse(page['body'],page['final_url'],{'id':None,'type':domain},False)
            items=evidence.get('candidates') or []
            for candidate in items[:12]:
                fp=hashlib.sha256(json.dumps([topic,candidate['url'],candidate['title']],sort_keys=True).encode()).hexdigest()
                added=c.execute('INSERT OR IGNORE INTO income_research_briefs VALUES(?,?,?,?,?)',
                    (fp,topic,json.dumps(candidate),json.dumps(brief(candidate,topic,kind)),now))
                result['new_briefs']+=added.rowcount
            result.update(state='observed',source_sha256=evidence['source_sha256'],
                relevant=evidence['relevant'],public_request_candidates=len(items),
                reason='research_evidence_only' if items else 'no_specific_matching_request',
                next_step='validate_brief_and_delivery_capacity' if items else 'rotate_to_next_research_topic',
                verified_buyer=False)
        else:
            result['reason']=fetched.get('error') or 'unsupported_research_response'
        failures=0 if valid else row['failures']+1
        delay=mandate['interval_seconds'] if valid else min(86400,300*2**min(failures,8))
        c.execute('UPDATE income_research_sources SET visits=visits+1,failures=?,next_at=?,last_result=? WHERE topic=?',
            (failures,now+delay,json.dumps(result),topic))
        c.execute('INSERT INTO income_research_cycles(topic,url,state,result,created) VALUES(?,?,?,?,?)',
            (topic,url,result['state'],json.dumps(result),now))
        c.commit()
        return result
    finally:c.close()
