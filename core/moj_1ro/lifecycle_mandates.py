"""Durable article-3 development milestones and read-only readiness observations."""
import ast, json, time
from pathlib import Path
from .foundation_runtime import connect, business_snapshot
from .operational_law import current

GAME_ROOT = Path('/home/zomorod2/Bazei')

def sync(c, law=None):
    law=law or current()
    article=law.get('article_3')
    if not article: raise PermissionError('article_three_not_registered')
    c.execute("""CREATE TABLE IF NOT EXISTS lifecycle_milestones(
      domain TEXT,phase TEXT,sequence INTEGER,objective TEXT,required_evidence TEXT,
      repository TEXT,state TEXT DEFAULT 'unverified',evidence TEXT DEFAULT '{}',
      law_sha256 TEXT,updated REAL,PRIMARY KEY(domain,phase))""")
    for domain,spec in [('games',article['games']),('finance_commerce',article['finance_commerce'])]:
        for index,phase in enumerate(spec['lifecycle']):
            c.execute("""INSERT INTO lifecycle_milestones
              (domain,phase,sequence,objective,required_evidence,repository,law_sha256,updated)
              VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(domain,phase) DO UPDATE SET
              sequence=excluded.sequence,objective=excluded.objective,
              required_evidence=excluded.required_evidence,repository=excluded.repository,
              law_sha256=excluded.law_sha256,updated=excluded.updated""",
              (domain,phase['key'],index,phase['goal'],phase['evidence'],spec['repository'],law['sha256'],time.time()))
    c.commit()

def roadmap(domain,c=None):
    own=c is None;c=c or connect()
    try:
        sync(c)
        return [dict(row) for row in c.execute(
            'SELECT phase,objective,required_evidence,repository,state FROM lifecycle_milestones WHERE domain=? ORDER BY sequence',
            (domain,))]
    finally:
        if own:c.close()

def games_audit():
    law=current();spec=law['article_3']['games']
    missing=['verified_playable_build','player_quality_acceptance','verified_global_distribution']
    workspace=GAME_ROOT.is_dir()
    if not workspace:missing.insert(0,'verified_game_workspace')
    parsed=0
    if workspace:
        # Syntax inventory is an observation, never proof of a working game.
        for p in list(GAME_ROOT.rglob('*.py'))[:500]:
            ast.parse(p.read_text(),filename=str(p.relative_to(GAME_ROOT)));parsed+=1
    return {'state':'blocked','repository':'Bazei','target_market':spec['primary_market'],
        'distribution':spec['distribution'],'audience':spec['audience'],
        'missing':missing,'workspace_exists':workspace,'python_files_parsed':parsed,
        'game_build_executed':False,'playability_verified':False,'game_two_allowed':False,
        'optional_digital_assets':spec['optional_digital_assets'],'roadmap':roadmap('games'),
        'constitution_sha256':law['sha256']}

def financial_inventory():
    from financial_core.models import Asset,Wallet,Journal,JournalEntry,Transaction,FinancialEvidence,Reconciliation
    from django.db.models import Sum
    groups=list(JournalEntry.objects.filter(journal__posted=True).values('journal_id','asset_id','side')
        .annotate(total=Sum('amount')).order_by('journal_id','asset_id','side')[:1001])
    balances={}
    for row in groups[:1000]:
        key=(row['journal_id'],row['asset_id'])
        balances[key]=balances.get(key,0)+(row['total'] if row['side']=='D' else -row['total'])
    complete=len(groups)<=1000
    return {'assets':Asset.objects.count(),'wallet_records':Wallet.objects.count(),
        'posted_journals':Journal.objects.filter(posted=True).count(),
        'ledger_groups_inspected':len(groups[:1000]),'ledger_inspection_complete':complete,
        'ledger_imbalance_groups':sum(v!=0 for v in balances.values()) if complete else None,
        'settled_transaction_records':Transaction.objects.filter(status='SETTLED').count(),
        'verified_financial_evidence_records':FinancialEvidence.objects.filter(verified=True).count(),
        'matched_reconciliation_records':Reconciliation.objects.filter(status='MATCHED').count(),
        'external_settlement_verified_by_this_audit':False}

def finance_audit():
    missing=['verified_checkout_payment_delivery_flow','verified_external_settlement',
             'tested_game_finance_integration','verified_cost_and_profit_measurement']
    try:
        inventory=financial_inventory()
        if inventory['ledger_imbalance_groups']:missing.append('posted_ledger_imbalance')
        if not inventory['ledger_inspection_complete']:missing.append('complete_ledger_inspection')
    except Exception as exc:
        inventory={'available':False,'error':type(exc).__name__}
        missing.append('financial_model_inventory_unavailable')
    return {'state':'blocked','repository':'Saeit','financial_inventory':inventory,
        'business':business_snapshot(),'missing':missing,'roadmap':roadmap('finance_commerce'),
        'constitution_sha256':current()['sha256'],'transactions_executed':0,
        'game_finance_connected':False,'production_readiness_verified':False}
