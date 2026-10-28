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
shutil.copy2(entry,web/'index.php')
assert source.read_bytes()==(private/'app.php').read_bytes()
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
# The legacy setup token must never be required on the public form.
(private/'setup.token').write_text('synthetic-obsolete-token')
initial=request()
assert 'ورود مدیر و حسابدار' in initial
assert 'توکن فعال‌سازی' not in initial
assert not (private/'setup.token').exists()
receipt=private/'owner-first-login.txt'
assert receipt.is_file()
assert receipt.stat().st_mode & 0o777 == 0o600
credentials=receipt.read_text()
username=re.search(r'^Username: (.+)$',credentials,re.M).group(1)
previous=re.search(r'^Initial password: (.+)$',credentials,re.M).group(1)
assert username=='ZomorodOwner' and len(previous)>=40
assert previous not in initial
csrf=re.search(r'name="csrf" value="([0-9a-f]{64})"',initial)
assert csrf
csrf=csrf.group(1)
request('POST',post={'csrf':csrf,'username':username,'password':previous})
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
print('ZOMOROD_ACCOUNTING_SYNTHETIC_QA=PASS')
print('TEST_USERS=1 PARTIES=1 INVOICES=1 PAYMENTS=1 JOURNALS=3')
print('BALANCED_ENTRIES=3')
print('PASSWORD_CHANGE_TEST=PASS')
print('UNBALANCED_ENTRY_REJECTED=yes')
print('PRODUCTION_DATABASE_TOUCHED=no')
