"""Bounded self-repair recipes and a measured, durable component improvement backlog."""
import ast, hashlib, json, time
from pathlib import Path
from .foundation_runtime import ROOT, connect
from .operational_law import current
OLD = "    if capability == \"git.status\":\n        output = str(result.get(\"output\", \"\")) if isinstance(result, dict) else str(result)\n        if not output.strip():\n            return \"✓ وضعیت کد بررسی شد؛ تغییر ثبت‌نشده‌ای در Git وجود ندارد.\"\n        return \"✓ وضعیت کد بررسی شد. تغییرات ثبت‌نشده وجود دارد:\\n\" + output[:1800]\n"
NEW = "    if capability == \"git.status\":\n        if isinstance(result, dict) and \"dirty\" in result:\n            if result[\"dirty\"]:\n                return \"وضعیت کد: تغییرات ثبت‌نشده وجود دارد؛ تعداد: \" + str(result.get(\"count\", \"نامشخص\"))\n            return \"وضعیت کد: تغییر ثبت‌نشده‌ای در Git وجود ندارد.\"\n        output = str(result.get(\"output\", \"\")) if isinstance(result, dict) else str(result)\n        if output.strip():\n            return \"وضعیت کد: تغییرات ثبت‌نشده وجود دارد:\\n\" + output[:1800]\n        return \"وضعیت Git از پاسخ دریافت‌شده قابل تأیید نیست.\"\n"
RECIPE = 'git_status_reporting_v1'
TARGET = 'core/chat_runtime.py'

def formatter(source):
    node = next(n for n in ast.parse(source).body
                if isinstance(n, ast.FunctionDef) and n.name == '_format_capability_result')
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<formatter-check>', 'exec'), namespace)
    return namespace['_format_capability_result']

def verified(source):
    f = formatter(source)
    dirty = f('git.status', {'ok':True, 'dirty':True, 'count':3})
    clean = f('git.status', {'ok':True, 'dirty':False, 'count':0})
    unknown = f('git.status', {'ok':True})
    return ('تعداد: 3' in dirty and 'وجود ندارد' in clean and 'قابل تأیید نیست' in unknown)

def candidate(source):
    if verified(source):
        return None
    if source.count(OLD) != 1:
        raise ValueError('repair_preimage_unknown')
    updated = source.replace(OLD, NEW, 1)
    if not verified(updated):
        raise ValueError('repair_behavior_not_verified')
    return updated

def repair(payload):
    if payload != {'recipe':RECIPE} or RECIPE not in current()['automatic_repairs']:
        raise PermissionError('repair_recipe_not_authorized')
    path = ROOT / TARGET
    source = path.read_text()
    updated = candidate(source)
    if updated is None:
        return {'state':'observed', 'recipe':RECIPE, 'behavior_verified':True,
                'changed':False, 'reason':'already_repaired'}
    from .orchestrator import Moj1roOrchestrator
    from .host_cycle_dispatch import execute
    robot = Moj1roOrchestrator()
    result = execute(robot, {'operation':'apply_patch','changes':[{
        'path':TARGET,'expected_sha256':hashlib.sha256(source.encode()).hexdigest(),
        'content':updated}]})
    try:
        if not result.get('ok') or path.read_text() != updated or not verified(path.read_text()):
            raise ValueError('deployed_behavior_not_verified')
    except Exception:
        execute(robot, {'operation':'apply_patch','changes':[{
            'path':TARGET,'expected_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'content':source}]})
        raise
    return {'state':'applied','recipe':RECIPE,'changed':True,'behavior_verified':True,
            'receipt':result,'verification':'dirty_clean_unknown_cases_and_django_check',
            'general_autonomous_coding_proven':False}

def audit():
    from .executive_runtime import submit
    c = connect()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS improvement_backlog(
            component TEXT PRIMARY KEY, objective TEXT, state TEXT, evidence TEXT,
            updated REAL)""")
        rows = list(c.execute('SELECT domain, last_result FROM executive_goals'))
        gaps = []
        for row in rows:
            if row['domain'] == 'self_improvement': continue
            result = json.loads(row['last_result'] or '{}')
            reasons = list(result.get('missing') or [])
            if row['domain'] == 'site' and result.get('authenticated_flows') == 'not_tested':
                reasons.append('authenticated_site_flows_not_verified')
            if row['domain'] == 'business' and result.get('contact_executor') == 'not_connected':
                reasons.append('authorized_customer_contact_executor_missing')
            for reason in reasons:
                gaps.append((row['domain']+':'+reason, 'develop_and_verify:'+reason, result))
        gaps.extend([
            ('primary:local_reasoning_model','install_and_validate_actual_reasoning_model',{}),
            ('primary:general_code_execution','develop_test_and_rollback_general_code_executor',{}),
        ])
        for component, objective, evidence in gaps:
            c.execute("""INSERT INTO improvement_backlog VALUES(?,?,'blocked',?,?)
              ON CONFLICT(component) DO UPDATE SET objective=excluded.objective,
              evidence=excluded.evidence,updated=excluded.updated""",
              (component,objective,json.dumps(evidence),time.time()))
        c.commit()
        source = (ROOT / TARGET).read_text()
        needs_repair = not verified(source)
        queued = None
        if needs_repair:
            queued = submit('self_improvement','repair',{'recipe':RECIPE},
                            automatic=True,priority=96,
                            request_id='constitution-v2:repair:'+RECIPE,connection=c)
        return {'state':'observed','constitution_sha256':current()['sha256'],
                'improvement_backlog':len(gaps),'repair_needed':needs_repair,
                'repair_task':queued,'repairs_applied':0,
                'general_autonomous_coding_proven':False}
    finally: c.close()
