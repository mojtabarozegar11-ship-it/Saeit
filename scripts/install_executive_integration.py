"""Idempotent integration for the existing deployed Saeit commander."""
from pathlib import Path
import hashlib, json, os, py_compile, shutil, time
ROOT=Path(__file__).resolve().parent.parent

def prepare():
    candidates={}
    p=ROOT/'core/moj_1ro/orchestrator.py'
    if p.exists():
        s=p.read_text()
        if 'executable_catalog' not in s:
            s=s.replace('    def available_capabilities(self):\n        return sorted(CAPABILITIES)',
                '    def available_capabilities(self):\n        from .executable_catalog import handlers\n        return sorted(handlers(CAPABILITIES))')
            s=s.replace('        handler=CAPABILITIES.get(capability_code)',
                '        from .executable_catalog import handlers, classification\n        handler=handlers(CAPABILITIES).get(capability_code)')
            s=s.replace("        self.ledger.record(mission.id,'production.receipt',",
                "        if isinstance(result,dict):\n            result.setdefault('execution_mode',classification(capability_code))\n        self.ledger.record(mission.id,'production.receipt',")
            if 'handlers(CAPABILITIES).get' not in s:
                raise ValueError('orchestrator_integration_base_changed')
            candidates[p]=s
    p=ROOT/'core/chat_runtime.py'
    if p.exists():
        s=p.read_text()
        if 'EXECUTIVE_MANAGER_UPGRADE' not in s:
            s=s.replace('    rules = (',
                "    # EXECUTIVE_MANAGER_UPGRADE\n    rules = (\n        ((\"مدیریت کل\", \"مدیرکل\", \"توان ربات\"), \"executive.status\", {}),\n        ((\"سایت را ممیزی\", \"سلامت سایت\"), \"executive.submit\", {\"domain\":\"site\",\"operation\":\"audit\"}),\n        ((\"وضعیت معامله\", \"اتصال تریدر\"), \"executive.submit\", {\"domain\":\"trading\",\"operation\":\"audit\"}),\n        ((\"وضعیت بازی سازی\", \"مخزن بازی\"), \"executive.submit\", {\"domain\":\"games\",\"operation\":\"audit\"}),")
            s=s.replace('def _format_capability_result(capability, result):',
                'def _format_capability_result(capability, result):\n    if capability.startswith("executive."):\n        from .moj_1ro.executive_chat import format_result\n        return format_result(capability,result)')
            s=s.replace("    context=CognitiveStore().recall_recent('commander',100) or []",
                "    from .moj_1ro.executive_runtime import portfolio\n    live_management=portfolio()\n    context=[{'current_authoritative_management':live_management}]\n    # Historical narratives do not override measured executive receipts.")
            s=s.replace("    if any(x in q for x in ('آخرین تصمیم'",
                "    if any(x in q for x in ('وضعیت مدیریت کل','وضعیت مدیرکل','توان ربات','نسل ربات')):\n        from .moj_1ro.executive_chat import format_result\n        from .moj_1ro.executive_runtime import status_handler\n        return format_result('executive.status',status_handler())\n    if any(x in q for x in ('آخرین تصمیم'")
            start=s.find("    recent_commander=CognitiveStore().recall_recent('commander',1) or []")
            end=s.find('\nclass MasterAgentChat:',start)
            if start>=0 and end>start:
                s=s[:start]+"    from .moj_1ro.executive_chat import format_result\n    return format_result('executive.status',{'portfolio':live_management})\n"+s[end:]
            if 'live_management=portfolio()' not in s:
                raise ValueError('chat_integration_base_changed')
            candidates[p]=s
    p=ROOT/'core/moj_1ro/revenue_scheduler.py'
    s=p.read_text()
    if 'EXECUTIVE_SCHEDULER_INTEGRATION' not in s:
        old='        result = tick(count)'
        new="""        # EXECUTIVE_SCHEDULER_INTEGRATION
        from core.moj_1ro.executive_runtime import tick as executive_tick
        from core.moj_1ro.foundation_runtime import business_snapshot
        frame = executive_tick(count) if count % 3 == 0 else None
        if frame and frame['outcome']['state'] != 'idle':
            result = {'goal':'executive_portfolio','task_states':frame['states'],
                      'outcome':frame['outcome'],'business':business_snapshot()}
        else:
            result = tick(count)"""
        if old not in s:raise ValueError('scheduler_integration_base_changed')
        candidates[p]=s.replace(old,new)
    return candidates

def install():
    candidates=prepare()
    if not candidates:return {'changed':[]}
    backup=ROOT/'var/executive_upgrade_backup'/str(int(time.time()))
    for p,s in candidates.items():
        compile(s,str(p),'exec')
        target=backup/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,target)
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in candidates}
    (backup/'manifest.json').write_text(json.dumps(manifest))
    for p,s in candidates.items():
        tmp=p.with_suffix('.executive.tmp');tmp.write_text(s);os.replace(tmp,p)
        py_compile.compile(str(p),doraise=True)
    return {'changed':list(manifest),'backup':str(backup)}

if __name__=='__main__':
    print(json.dumps(install()))
