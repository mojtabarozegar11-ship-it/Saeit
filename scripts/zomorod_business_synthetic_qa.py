#!/usr/bin/env python3
"""Synthetic-only Zomorod accounting QA; never opens production database."""
import os,pathlib,re,shutil,sqlite3,subprocess,sys,json
sha=sys.argv[1]
assert re.fullmatch(r'[a-f0-9]{40}',sha)
home=pathlib.Path.home()
source=home/'.private/zomorod-business/app.php'
dossier_source=home/'.private/zomorod-business/genetics-center.php'
entry=home/'public_html/business/index.php'
assert source.is_file() and entry.is_file() and dossier_source.is_file()
base=home/'.backups/zomorod-business-smoke'/sha
assert not base.exists()
private=base/'synthetic/.private/zomorod-business'
web=base/'synthetic/public_html/business'
private.mkdir(parents=True,mode=0o700)
web.mkdir(parents=True)
sessions=base/'sessions'
sessions.mkdir(mode=0o700)
shutil.copy2(source,private/'app.php')
shutil.copy2(dossier_source,private/'genetics-center.php')
shutil.copy2(entry,web/'index.php')
assert source.read_bytes()==(private/'app.php').read_bytes()
assert dossier_source.read_bytes()==(private/'genetics-center.php').read_bytes()
php=shutil.which('php') or '/opt/cpanel/ea-php82/root/usr/bin/php'
assert pathlib.Path(php).is_file()
assert subprocess.run([php,'-r','exit(extension_loaded("pdo_sqlite")?0:1);']).returncode==0
sid='zmtest'+sha[:12]
code="session_id(getenv('SID'));$_SERVER['REQUEST_METHOD']=getenv('REQ_METHOD');$_GET=json_decode(getenv('QUERY_JSON'),true);$_POST=json_decode(getenv('POST_JSON'),true);register_shutdown_function(function(){file_put_contents(getenv('SID_RESULT'),session_id());});require getenv('INDEX');"
def request(method='GET',page=None,post=None):
    global sid
    env=os.environ.copy()
    env.update({'SID':sid,'SID_RESULT':str(base/'sid.result'),'INDEX':str(web/'index.php'),'REQ_METHOD':method,'QUERY_JSON':json.dumps({'page':page} if page else {}),'POST_JSON':json.dumps(post or {})})
    result=subprocess.run([php,'-d','session.save_path='+str(sessions),'-r',code],env=env,capture_output=True,text=True,timeout=25)
    assert result.returncode==0,('PHP test failed',result.stderr[-400:])
    sid=(base/'sid.result').read_text().strip()
    assert sid
    return result.stdout
initial=request()
assert 'راه‌اندازی امن میز مدیریت' in initial
csrf=re.search(r'name="csrf" value="([0-9a-f]{64})"',initial)
assert csrf
csrf=csrf.group(1)
token=(private/'setup.token').read_text().strip()
assert len(token)==64
request('POST',post={'csrf':csrf,'setup_token':token,'username':'TestOnlyAdmin','password':'SyntheticOnlyPassword2026!'})
assert not (private/'setup.token').exists()
previous='SyntheticOnlyPassword2026!'
updated='SyntheticNewPassword2026!Changing'
changed=request('POST','security',{'csrf':csrf,'action':'password_change','previous_password':previous,'new_password':updated,'new_password_confirmation':updated})
assert not 'درخواست انجام نشد' in changed
dashboard=request('GET','dashboard')
assert 'اسناد حسابداری' in dashboard
assert '?page=genetics_center' in dashboard
assert 'آغاز از صفحه داخلی سایت میزبان' in dashboard
assert 'https://parswebserver.com/' in dashboard
assert 'rel="noopener noreferrer"' in dashboard
# Authenticated management and project navigation must expose the dossier without creating projects or journals.
with sqlite3.connect(str(private/'management.sqlite3')) as check:
    counts_before=[check.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('projects','journal_entries','invoices','audit_events')]
genetics=request('GET','genetics_center')
projects_page=request('GET','projects')
assert 'ZM-AGRC-GEN-1405-001' in genetics
assert 'مرکز جامع تحقیقات ژنتیک و اصلاح نژاد جانوران زمرد ملل' in genetics
assert '۹۵ هکتار' in genetics
assert '۴٬۱۰۴' in genetics
assert '۶۵٫۴ میلیون USD' in genetics
assert '۰٪' in genetics
assert 'ZM-AGRC-GEN-1405-001' in projects_page
assert '?page=genetics_center' in projects_page
with sqlite3.connect(str(private/'management.sqlite3')) as check:
    counts_after=[check.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('projects','journal_entries','invoices','audit_events')]
assert counts_after==counts_before,('Read-only dossier changed data',counts_before,counts_after)
# A fresh, unauthenticated session may only see the login form.
signed_in_sid=sid
sid='anonymous'+sha[:12]
anonymous=request('GET','genetics_center')
assert 'ورود مدیر و حسابدار' in anonymous
assert 'ZM-AGRC-GEN-1405-001' not in anonymous
sid=signed_in_sid
# Ensure that releases cannot start from a PR merge and malformed dispatch cannot reach host.
root=pathlib.Path(__file__).resolve().parents[1]
deploy_workflow=(root/'.github/workflows/zomorod-business-update.yml').read_text(encoding='utf-8')
guard_script=root/'scripts/zomorod_business_genetics_guarded_install.sh'
preflight_script=root/'scripts/zomorod_business_genetics_readonly_preflight.sh'
assert preflight_script.is_file()
assert re.search(r'(?m)^  workflow_dispatch:$',deploy_workflow)
assert not re.search(r'(?m)^  push:$',deploy_workflow)
assert 'expected_current_app_sha256:' in deploy_workflow
assert 'expected_current_dossier_sha256:' in deploy_workflow
assert 'expected_merged_app_sha256:' in deploy_workflow
assert "cat > '$stage/app.php'" not in deploy_workflow
assert "cat > '$stage/proposed-app.php'" in deploy_workflow
assert "cat > '$stage/overlay.py'" in deploy_workflow
assert '--render-stage' in deploy_workflow
assert "'$EXPECTED_MERGED' '$dossier_hash'" in deploy_workflow
assert 'zomorod_business_genetics_overlay_preview.py' in deploy_workflow
assert 'verified_cpanel_ssh_port:' in deploy_workflow
assert "github.actor == 'mojtabarozegar11-ship-it'" in deploy_workflow
assert "github.ref == 'refs/heads/main'" in deploy_workflow
assert "github.event_name == 'workflow_dispatch'" in deploy_workflow
assert "runs-on: [self-hosted, factory-vps]" in deploy_workflow
assert 'runs-on: ubuntu-latest' not in deploy_workflow
assert 'DIRECT_CPANEL=verified' in deploy_workflow
assert 'DIRECT_CONFIG' in deploy_workflow
assert 'ProxyJump' not in deploy_workflow
assert 'saeit-vps' not in deploy_workflow
assert 'workflow_dispatch:' in deploy_workflow
assert 'genetics-center.php' in deploy_workflow
assert 'zomorod_business_genetics_guarded_install.sh' in deploy_workflow
assert 'zomorod_business_genetics_readonly_preflight.sh' in deploy_workflow
assert deploy_workflow.index('saeit-cpanel bash -s --') < deploy_workflow.index("install -d -m 700 '$stage'")
assert subprocess.run(['bash','-n',str(guard_script)],capture_output=True).returncode==0
assert subprocess.run(['bash','-n',str(preflight_script)],capture_output=True).returncode==0
bad_preflight=subprocess.run(['bash',str(preflight_script),'INVALID','ABSENT'],capture_output=True,text=True)
assert bad_preflight.returncode!=0
preflight_source=preflight_script.read_text(encoding='utf-8')
for clause in ('PREFLIGHT=PASS_READ_ONLY','PREFLIGHT=APP_DRIFT','PREFLIGHT=DISK_INSUFFICIENT','PREFLIGHT_DATABASE_WRITE=no'):
    assert clause in preflight_source
invalid=subprocess.run(['bash',str(guard_script),'INVALID','ABSENT','0'*64,'0'*64,'0'*40,'/tmp/not-real-stage'],capture_output=True,text=True)
assert invalid.returncode!=0,('Malformed hash accepted',invalid.stdout,invalid.stderr)
guard_source=guard_script.read_text(encoding='utf-8')
assert "python3 -B \"$stage/public-references.py\" enforce" in guard_source
assert "'PUBLIC_REFERENCES_PROTECTED=VERIFIED'" in guard_source
assert "cat > '$stage/public-references.py'" in deploy_workflow
assert 'zomorod_business_public_reference_audit.py' in deploy_workflow
assert 'zomorod_business_public_surface_invariant.py' in deploy_workflow
for clause in ('GUARD=app_drift','GUARD=dossier_drift','source.backup(target','BUSINESS_GENETICS_ROLLBACK=restored'):
    assert clause in guard_source
print('GENETICS_DEPLOY_GUARD_SYNTHETIC=PASS')
print('GENETICS_DOSSIER_AUTH_READONLY_SYNTHETIC=PASS')
# Reject the reserved genetics dossier ID through the generic project form before or after registration.
for duplicate_title in (
    'ZM-AGRC-GEN-1405-001 | duplicate title',
    ' ZM-AGRC-GEN-1405-001 forged through general form',
):
    rejected=request('POST','projects',{
        'csrf':csrf,'action':'project','title':duplicate_title,
        'owner':'Unauthorized generic path','state':'active','budget':'99999'
    })
    assert 'درخواست انجام نشد' in rejected
with sqlite3.connect(str(private/'management.sqlite3')) as check:
    assert check.execute('SELECT COUNT(*) FROM projects').fetchone()[0]==0
print('GENETICS_GENERIC_FORM_DUPLICATE_GUARD=PASS')
# Legacy titles bearing the same stable ID must never trigger a second project.
with sqlite3.connect(str(private/'management.sqlite3')) as simulated_legacy:
    simulated_legacy.execute("INSERT INTO projects(title,owner,state,budget) VALUES(?,?,?,?)",
       ('ZM-AGRC-GEN-1405-001 | old display name','Legacy', 'planned', 2500))
legacy_dossier=request('GET','genetics_center')
assert 'عنوان ذخیره‌شده با نسخه جدید متفاوت است' in legacy_dossier
assert 'ثبت یک‌باره طرح در دفتر پروژه‌ها' not in legacy_dossier
request('POST','genetics_center',{'csrf':csrf,'action':'genetics_project_register'})
with sqlite3.connect(str(private/'management.sqlite3')) as simulated_legacy:
    assert simulated_legacy.execute('SELECT COUNT(*) FROM projects').fetchone()[0]==1
    assert simulated_legacy.execute("SELECT COUNT(*) FROM audit_events WHERE subject='genetics-project'").fetchone()[0]==0
    simulated_legacy.execute("INSERT INTO projects(title,owner,state,budget) VALUES(?,?,?,?)",
       ('ZM-AGRC-GEN-1405-001 | second legacy title','Legacy2','planned',0))
collision_dossier=request('GET','genetics_center')
assert 'تداخل شناسه' in collision_dossier
assert 'ثبت یک‌باره طرح در دفتر پروژه‌ها' not in collision_dossier
collision_action=request('POST','genetics_center',{'csrf':csrf,'action':'genetics_project_register'})
assert 'درخواست انجام نشد' in collision_action
with sqlite3.connect(str(private/'management.sqlite3')) as cleanup:
    assert cleanup.execute('SELECT COUNT(*) FROM projects').fetchone()[0]==2
    cleanup.execute("DELETE FROM projects WHERE title LIKE 'ZM-AGRC-GEN-1405-001%'")
    assert cleanup.execute('SELECT COUNT(*) FROM projects').fetchone()[0]==0
print('GENETICS_LEGACY_ID_COLLISION_GUARD=PASS')
# An explicit admin action registers a planned project with zero budget exactly once.
with sqlite3.connect(str(private/'management.sqlite3')) as check:
    financial_before=[check.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('journal_entries','journal_lines','invoices','invoice_payments')]
request('POST','genetics_center',{'csrf':csrf,'action':'genetics_project_register'})
recorded=request('GET','genetics_center')
assert 'ثبت‌شده با شناسه داخلی' in recorded
with sqlite3.connect(str(private/'management.sqlite3')) as check:
    project_rows=check.execute("SELECT title,owner,state,budget FROM projects WHERE title LIKE 'ZM-AGRC-GEN-1405-001%'").fetchall()
    assert len(project_rows)==1,project_rows
    assert project_rows[0][2:] == ('planned',0),project_rows
    assert check.execute("SELECT COUNT(*) FROM audit_events WHERE subject='genetics-project'").fetchone()[0]==1
request('POST','genetics_center',{'csrf':csrf,'action':'genetics_project_register'})
with sqlite3.connect(str(private/'management.sqlite3')) as check:
    assert check.execute("SELECT COUNT(*) FROM projects WHERE title LIKE 'ZM-AGRC-GEN-1405-001%'").fetchone()[0]==1
    assert check.execute("SELECT COUNT(*) FROM audit_events WHERE subject='genetics-project'").fetchone()[0]==1
    financial_after=[check.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('journal_entries','journal_lines','invoices','invoice_payments')]
assert financial_before==financial_after,('Registration wrote accounting data',financial_before,financial_after)
rejected_after=request('POST','projects',{'csrf':csrf,'action':'project',
    'title':'ZM-AGRC-GEN-1405-001 | repeated','owner':'Generic','state':'planned','budget':'1'})
assert 'درخواست انجام نشد' in rejected_after
with sqlite3.connect(str(private/'management.sqlite3')) as check:
    assert check.execute('SELECT COUNT(*) FROM projects').fetchone()[0]==1
# The dossier must reflect existing project data honestly, not falsely label changed rows as zero-budget.
with sqlite3.connect(str(private/'management.sqlite3')) as synthetic:
    synthetic.execute("UPDATE projects SET state='active',budget=12500 WHERE title LIKE 'ZM-AGRC-GEN-1405-001%'")
changed_dossier=request('GET','genetics_center')
assert 'وضعیت واقعی رکورد: active' in changed_dossier
assert 'نیازمند تطبیق مصوبه' in changed_dossier
with sqlite3.connect(str(private/'management.sqlite3')) as synthetic:
    synthetic.execute("UPDATE projects SET state='planned',budget=0 WHERE title LIKE 'ZM-AGRC-GEN-1405-001%'")
restored_dossier=request('GET','genetics_center')
assert 'بودجه ثبت‌شده صفر (غیرمصوب)' in restored_dossier
print('GENETICS_OWNER_ONLY_PROVIDER_INTERNAL_NAVIGATION=PASS')
print('GENETICS_PROJECT_RECORDED_STATE_BUDGET_REFLECTED=PASS')
print('GENETICS_PROJECT_ADMIN_IDEMPOTENT_ZERO_BUDGET=PASS')
request('POST','parties',{'csrf':csrf,'action':'party','name':'Synthetic Counterparty','kind':'customer'})
request('POST','invoices',{'csrf':csrf,'action':'invoice','kind':'sale','party':'1','invoice_no':'SMOKE-INV-1','amount':'125.50','currency':'USD','date':'2026-10-18','due_date':'2026-10-18','description':'Synthetic invoice'})
request('POST','payments',{'csrf':csrf,'action':'payment','invoice_id':'1','amount':'25.50','date':'2026-10-18'})
request('POST','journal',{'csrf':csrf,'action':'journal','currency':'USD','date':'2026-10-18','doc_no':'SMOKE-JV-1','note':'Balanced dummy','account_0':'1010','debit_0':'50.00','account_1':'3000','credit_1':'50.00'})
bad=request('POST','journal',{'csrf':csrf,'action':'journal','currency':'USD','date':'2026-10-18','doc_no':'SMOKE-BAD','note':'Invalid dummy','account_0':'1010','debit_0':'80.00','account_1':'3000','credit_1':'50.00'})
assert 'درخواست انجام نشد' in bad
db=sqlite3.connect('file:'+str(private/'management.sqlite3')+'?mode=ro',uri=True)
for table,n in [('users',1),('parties',1),('invoices',1),('invoice_payments',1),('journal_entries',3)]:
    rows=db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
    assert rows==n,(table,rows,n)
assert db.execute('SELECT amount FROM invoices').fetchone()[0]==12550
assert db.execute('SELECT amount FROM invoice_payments').fetchone()[0]==2550
assert db.execute("SELECT COUNT(*) FROM journal_entries WHERE doc_no='SMOKE-BAD'").fetchone()[0]==0
entries=db.execute('SELECT entry_id,currency,SUM(debit),SUM(credit) FROM journal_lines GROUP BY entry_id,currency').fetchall()
assert len(entries)==3
assert all(dr==cr and dr>0 for _,_,dr,cr in entries)
assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
assert db.execute('SELECT length(password_hash) FROM users').fetchone()[0]>40
# Downgrading a user's live role must revoke the old admin session immediately.
with sqlite3.connect(str(private/'management.sqlite3')) as rw:
    rw.execute("UPDATE users SET role='viewer' WHERE username='TestOnlyAdmin'")
blocked=request('POST','projects',{'csrf':csrf,'action':'project','title':'Must not be created','owner':'Synthetic','state':'planned','budget':'0'})
assert 'درخواست انجام نشد' in blocked
assert db.execute('SELECT COUNT(*) FROM projects').fetchone()[0]==1
viewer_dossier=request('GET','genetics_center')
assert 'ZM-AGRC-GEN-1405-001' in viewer_dossier
viewer_dashboard=request('GET','dashboard')
assert 'آغاز از صفحه داخلی سایت میزبان' not in viewer_dashboard
assert 'https://parswebserver.com/' not in viewer_dashboard
viewer_forbidden=request('POST','genetics_center',{'csrf':csrf,'action':'genetics_project_register'})
assert 'درخواست انجام نشد' in viewer_forbidden
assert db.execute('SELECT COUNT(*) FROM projects').fetchone()[0]==1
assert 'درخواست انجام نشد' in request('GET','users')
with sqlite3.connect(str(private/'management.sqlite3')) as rw:
    rw.execute("UPDATE users SET role='admin' WHERE username='TestOnlyAdmin'")
assert 'درخواست انجام نشد' not in request('GET','users')
# The approvals page reads only a separately controlled private snapshot.
(private/'approvals_snapshot.json').write_text(json.dumps({
    'version':1,
    'summary':{'records':1,'approved':1,'rejected':0,'undetermined':0,'planned_operational_jobs':5},
    'items':[{'external_key':'ZM-001','title':'SyntheticOnlyProposalTitle',
              'decision':'approved','execution_state':'planned',
              'planned_operational_jobs':5,'official_title_verified':True,
              'review_required':False}]
},ensure_ascii=False),encoding='utf-8')
register=request('GET','approval_register')
assert 'SyntheticOnlyProposalTitle' in register
assert 'اشتغال برنامه‌ای' in register
print('APPROVAL_REGISTER_VIEW_SYNTHETIC=PASS')
# Exercise the new endpoint without replacing or importing production management.php.
approval_src=pathlib.Path(__file__).resolve().parents[1]/'content/zomorod-business/approvals.php'
approval_web=web/'approvals'
approval_web.mkdir()
shutil.copy2(approval_src,approval_web/'index.php')
isolated_code="session_id(getenv('SID'));$_SERVER['REQUEST_METHOD']='GET';require getenv('APPROVAL_INDEX');"
def isolated_approval_page(current_sid):
    env=os.environ.copy()
    env.update({'SID':current_sid,'APPROVAL_INDEX':str(approval_web/'index.php')})
    output=subprocess.run([php,'-d','session.save_path='+str(sessions),'-r',isolated_code],
                          env=env,capture_output=True,text=True,timeout=25)
    assert output.returncode==0,output.stderr[-250:]
    return output.stdout
assert 'SyntheticOnlyProposalTitle' in isolated_approval_page(sid)
assert 'SyntheticOnlyProposalTitle' not in isolated_approval_page('anonymous'+sha[:12])
print('ISOLATED_APPROVAL_ROUTE_AUTH=PASS')


print('ROLE_DOWNGRADE_REVOKES_EXISTING_SESSION=PASS')
print('ZOMOROD_ACCOUNTING_SYNTHETIC_QA=PASS')
print('TEST_USERS=1 PARTIES=1 INVOICES=1 PAYMENTS=1 JOURNALS=3')
print('BALANCED_ENTRIES=3')
print('PASSWORD_CHANGE_TEST=PASS')
print('UNBALANCED_ENTRY_REJECTED=yes')
print('PRODUCTION_DATABASE_TOUCHED=no')
