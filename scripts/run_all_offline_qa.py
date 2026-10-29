#!/usr/bin/env python3
"""Real offline validation runner; never reports a skipped PHP SQLite suite as passed."""
from __future__ import annotations
import json
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parent.parent
SUITES=[
 'scripts/test_zomorod_company_private_bridge_v4.py',
 'scripts/test_erp_offline_gate.py',
 'scripts/test_industry_sqlite_schema.py',
 'scripts/test_erp_static_integration.py',
 'scripts/test_period_closure_sqlite.py',
 'scripts/test_finance_invariants.py',
 'scripts/test_real_php_schema_sqlite_integration.py',
 'scripts/test_zomorod_owner_password_rotate.py',
 'scripts/zomorod_workflow_web_synthetic_qa.py',
]
PHP_SUITES=[
 'scripts/zomorod_command_center_synthetic_qa.php',
 'scripts/zomorod_command_quality_synthetic_qa.php',
 'scripts/zomorod_command_planner_synthetic_qa.php',
 'scripts/zomorod_workflow_desk_synthetic_qa.php',
 'scripts/zomorod_industry_synthetic_qa.php',
 'scripts/zomorod_finance_audit_synthetic_qa.php',
 'scripts/zomorod_period_controls_synthetic_qa.php',
 'scripts/zomorod_payroll_control_synthetic_qa.php',
 'scripts/zomorod_treasury_synthetic_qa.php',
]

def run(command:list[str])->tuple[bool,str]:
    try:
        result=subprocess.run(command,cwd=ROOT,timeout=35,capture_output=True,text=True)
        data=(result.stdout+'\n'+result.stderr).strip()
        return result.returncode==0, data[-1800:]
    except (OSError,subprocess.TimeoutExpired) as ex:
        return False, type(ex).__name__


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--report-out',type=Path,default=ROOT/'OFFLINE_QA_REPORT.json')
    options=parser.parse_args()
    status={'suite':'zomorod_erp_offline_v7','production_changed':False,'hourly_schedule_created':False,
            'tests':{},'php_sqlite_business_tests':'UNKNOWN','full_erp_readiness':False}
    allok=True
    for path in sorted((ROOT/'content/zomorod-business').glob('*.php'))+sorted((ROOT/'scripts').glob('*.php')):
        rel=str(path.relative_to(ROOT));ok,out=run(['php','-l',rel])
        status['tests']['php_lint:'+rel]={'status':'PASS' if ok else 'FAIL'}
        allok &= ok
    for suite in SUITES:
        ok,out=run([sys.executable,suite]);status['tests'][suite]={'status':'PASS' if ok else 'FAIL','detail':out[-300:]}
        allok &= ok
    with tempfile.TemporaryDirectory(prefix='zm-e2e-suite-') as temp:
        ok,out=run([sys.executable,'scripts/zomorod_bridge_v5_private_e2e.py',
                    'scripts/zomorod_company_private_bridge_v4.py',temp])
        status['tests']['bridge_synthetic_e2e']={'status':'PASS' if ok else 'FAIL','detail':out[-300:]}
        allok &= ok
    available,_=run(['php','-r',"exit(extension_loaded('pdo_sqlite')?0:1);"])
    if not available:
        status['php_sqlite_business_tests']='BLOCKED_MISSING_PDO_SQLITE_EXTENSION'
        for suite in PHP_SUITES:status['tests'][suite]={'status':'NOT_RUN_MISSING_PDO_SQLITE'}
    else:
        good=True
        for suite in PHP_SUITES:
            ok,out=run(['php',suite]);status['tests'][suite]={'status':'PASS' if ok else 'FAIL','detail':out[-400:]}
            good &= ok
        status['php_sqlite_business_tests']='PASS' if good else 'FAIL'
        allok &= good
    status['offline_checks_available_here']='PASS' if allok else 'FAIL'
    status['full_offline_database_tests_verified']=available and status['php_sqlite_business_tests']=='PASS'
    out=options.report_out
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(status,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print('OFFLINE_AVAILABLE_TESTS='+status['offline_checks_available_here'])
    print('PHP_DATABASE_BEHAVIOUR='+status['php_sqlite_business_tests'])
    print('FULL_ERP_PRODUCTION_READINESS=NO')
    print('REPORT='+str(out))
    return 0 if allok else 1

if __name__=='__main__':raise SystemExit(main())
