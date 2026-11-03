#!/usr/bin/env python3
"""Synthetic-only Zomorod accounting QA; never opens production database."""
import os,pathlib,re,shutil,sqlite3,subprocess,sys,json
sha=sys.argv[1]
assert re.fullmatch(r'[a-f0-9]{40}',sha)
home=pathlib.Path.home()
source=home/'.private/zomorod-business/app.php'
entry=home/'public_html/business/index.php'
assert source.is_file() and entry.is_file()
base=home/'.backups/zomorod-business-smoke'/sha
assert not base.exists()
private=base/'synthetic/.private/zomorod-business'
web=base/'synthetic/public_html/business'
private.mkdir(parents=True,mode=0o700)
web.mkdir(parents=True)
sessions=base/'sessions'
sessions.mkdir(mode=0o700)
shutil.copy2(source,private/'app.php')
helper=pathlib.Path(__file__).resolve().parents[1]/'content/zomorod-business/chatgpt_reports.php'
assert helper.is_file()
shutil.copy2(helper,private/'chatgpt_reports.php')
shutil.copy2(entry,web/'index.php')
assert source.read_bytes()==(private/'app.php').read_bytes()
php=shutil.which('php') or '/opt/cpanel/ea-php82/root/usr/bin/php'
assert pathlib.Path(php).is_file()
assert subprocess.run([php,'-r','exit(extension_loaded("pdo_sqlite")?0:1);']).returncode==0
# The accounting DB must now be initialized explicitly; HTTP GET may never
# auto-create it. Initialize only this throwaway synthetic directory.
init=subprocess.run([php,str(private/'app.php'),'--initialize-private-db'],
                    cwd=str(base/'synthetic'),capture_output=True,text=True,timeout=25)
assert init.returncode==0,('Isolated PHP private setup failed',init.stderr[-400:])
assert (private/'management.sqlite3').is_file() and (private/'setup.token').is_file()
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
assert db.execute('SELECT COUNT(*) FROM projects').fetchone()[0]==0
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


# Read-only ChatGPT reporting screen must use the existing finance login and
# reject access after a role downgrade without mutating a financial table.
report_data={
    'version':1,'source':'github:mojtabarozegar11-ship-it/Saeit:issue:1725',
    'count':1,'items':[{
       'report_code':'05-0001','comment_id':987654,
       'occurred_at':'2026-11-01T16:04:00+00:00',
       'evidence_url':'https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1725#issuecomment-987654',
       'body':'Synthetic private work report <script>injected()</script> & safe',
    }]
}
report_file=private/'chatgpt_reports_snapshot.json'
report_file.write_text(json.dumps(report_data,ensure_ascii=False),encoding='utf-8')
report_file.chmod(0o600)
page=request('GET','chatgpt_reports')
assert 'گزارش‌های متنی اقدامات ChatGPT' in page
assert '05-0001' in page
assert '&lt;script&gt;' in page and '<script>injected()</script>' not in page
assert 'گزارش‌های متنی ChatGPT' in request('GET','dashboard')
with sqlite3.connect(str(private/'management.sqlite3')) as rw:
    rw.execute("UPDATE users SET role='viewer' WHERE username='TestOnlyAdmin'")
assert 'درخواست انجام نشد' in request('GET','chatgpt_reports')
assert 'گزارش‌های متنی ChatGPT' not in request('GET','dashboard')
with sqlite3.connect(str(private/'management.sqlite3')) as rw:
    rw.execute("UPDATE users SET role='admin' WHERE username='TestOnlyAdmin'")
report_file.write_text('{"version":999}',encoding='utf-8')
assert 'اعتبارسنجی پرونده گزارش ناموفق بود' in request('GET','chatgpt_reports')
report_file.unlink()
assert 'هنوز نصب نشده است' in request('GET','chatgpt_reports')
assert db.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0]==3
print('PHP_CHATGPT_REPORT_ADMIN_ONLY_ESCAPED_READONLY=PASS')

print('ROLE_DOWNGRADE_REVOKES_EXISTING_SESSION=PASS')
print('ZOMOROD_ACCOUNTING_SYNTHETIC_QA=PASS')
print('TEST_USERS=1 PARTIES=1 INVOICES=1 PAYMENTS=1 JOURNALS=3')
print('BALANCED_ENTRIES=3')
print('PASSWORD_CHANGE_TEST=PASS')
print('UNBALANCED_ENTRY_REJECTED=yes')
print('PRODUCTION_DATABASE_TOUCHED=no')
