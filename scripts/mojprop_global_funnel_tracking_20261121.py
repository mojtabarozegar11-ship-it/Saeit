#!/usr/bin/env python3
"""Enable anonymous per-locale CTA click counters, only within MOJ PROP education pages.
One-shot, SHA-guarded cPanel release. No external trackers, cookies or payment writes.
"""
from __future__ import annotations
import os,sys,json,hashlib,tempfile,stat,getpass,urllib.request,urllib.error,subprocess
from pathlib import Path
from html.parser import HTMLParser
SITE=Path('/home/zomorod2/mojplaywin.com')
DIR=SITE/'moj-prop/languages'
METRICS=SITE/'moj-prop/metrics'
ENDPOINT=METRICS/'click.php'
ROBOTS=SITE/'robots.txt'
EVIDENCE=Path('/home/zomorod2/.private_mojplaywin_main_agents/mojprop_20_languages_equivalence_20261121/manifest.json')
PRIVATE=Path('/home/zomorod2/.private_mojplaywin_main_agents/mojprop_global_funnel_20261121')
RECEIPT=PRIVATE/'release_receipt.json'
REPORT=PRIVATE/'report_counts.py'
CODES=('en','zh','hi','es','ar','fr','bn','pt','id','ur','ru','de','ja','ar-eg','mr','vi','te','sw','tr','pcm')
ROBOTS_EXPECTED='487be476dda0922b535eea505709f27809973c9f7510a561f30e479335ae4b92'
PHP=r'''<?php
declare(strict_types=1);
// Aggregate click events only. Never record IP, user agent, request text, wallets or email.
header('Cache-Control: no-store, max-age=0');
header('Content-Type: text/plain; charset=UTF-8');
header('X-Robots-Tag: noindex, nofollow');
header('Referrer-Policy: no-referrer');
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST'); http_response_code(405); exit;
}
$size = (int)($_SERVER['CONTENT_LENGTH'] ?? 0);
if ($size < 1 || $size > 200) { http_response_code(413); exit; }
$ct = strtolower((string)($_SERVER['CONTENT_TYPE'] ?? ''));
if (strpos($ct, 'application/x-www-form-urlencoded') !== 0) {
    http_response_code(415); exit;
}
$origin = (string)($_SERVER['HTTP_ORIGIN'] ?? '');
$fetchSite = (string)($_SERVER['HTTP_SEC_FETCH_SITE'] ?? '');
if ($origin !== '' && $origin !== 'https://mojplaywin.com') { http_response_code(403); exit; }
if ($fetchSite !== '' && $fetchSite !== 'same-origin') { http_response_code(403); exit; }
if ($origin === '' && $fetchSite === '') { http_response_code(403); exit; }
$locale = $_POST['locale'] ?? '';
$action = $_POST['action'] ?? '';
$allowed = array('en','zh','hi','es','ar','fr','bn','pt','id','ur','ru','de','ja','ar-eg','mr','vi','te','sw','tr','pcm');
if (!is_string($locale) || !in_array($locale,$allowed,true) ||
    !is_string($action) || !in_array($action,array('program','starter30','probe'),true)) {
    http_response_code(400); exit;
}
$referer = (string)($_SERVER['HTTP_REFERER'] ?? '');
$parts = parse_url($referer);
if (!is_array($parts) || ($parts['scheme'] ?? '') !== 'https' ||
    ($parts['host'] ?? '') !== 'mojplaywin.com' ||
    ($parts['path'] ?? '') !== '/moj-prop/languages/'.$locale.'/') {
    http_response_code(403); exit;
}
// The probe checks that PHP executes on the live site. It never affects counters.
$dir = '/home/zomorod2/.private_mojplaywin_main_agents/mojprop_global_funnel_20261121';
if ($action === 'probe') {
    if (!is_dir($dir) || is_link($dir) || !is_writable($dir)) {
        http_response_code(503); exit;
    }
    header('X-MPW-Metrics-Probe: ok'); http_response_code(204); exit;
}
if (!is_dir($dir) || is_link($dir)) { http_response_code(503); exit; }
$day = gmdate('Ymd');
$file = $dir.'/events-'.$day.'.json';
if (is_link($file)) { http_response_code(503); exit; }
$oldMask = umask(0077);
$handle = @fopen($file, 'c+');
umask($oldMask);
if (!$handle) { http_response_code(503); exit; }
@chmod($file, 0600);
if (!flock($handle, LOCK_EX)) { fclose($handle); http_response_code(503); exit; }
$raw = stream_get_contents($handle, 8192);
$data = ($raw === '' || $raw === false)
    ? array('day_utc'=>$day,'counts'=>array(),'metric'=>'anonymous_cta_click_events_not_unique_visitors')
    : json_decode($raw,true);
if (!is_array($data) || ($data['day_utc'] ?? '') !== $day ||
    !is_array($data['counts'] ?? null)) {
    flock($handle,LOCK_UN); fclose($handle); http_response_code(503); exit;
}
$counts = $data['counts'][$locale] ?? array();
if (!is_array($counts)) { flock($handle,LOCK_UN); fclose($handle); http_response_code(503); exit; }
$current = $counts[$action] ?? 0;
if (!is_int($current) || $current < 0 || $current >= 100000) {
    flock($handle,LOCK_UN); fclose($handle); http_response_code(429); exit;
}
$data['counts'][$locale][$action] = $current + 1;
$out = json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
if ($out === false || strlen($out) > 8192 || fseek($handle,0) !== 0 ||
    !ftruncate($handle,0) || fwrite($handle,$out) !== strlen($out) ||
    !fflush($handle)) {
    flock($handle,LOCK_UN); fclose($handle); http_response_code(503); exit;
}
flock($handle,LOCK_UN); fclose($handle); http_response_code(204); exit;
'''
JS=r'''<script id="mojprop-global-cta-events-20261121">
(function(){
"use strict";
// No cookies, localStorage, third-party telemetry, or URL query changes.
// Counts interactions, not unique persons or completed sales.
var code=document.documentElement.lang.toLowerCase();
var supported="|en|zh|hi|es|ar|fr|bn|pt|id|ur|ru|de|ja|ar-eg|mr|vi|te|sw|tr|pcm|";
if(supported.indexOf("|"+code+"|")<0)return;
document.addEventListener("click",function(ev){
 if(!ev.isTrusted)return;
 var a=ev.target&&ev.target.closest?ev.target.closest("a[data-mpw-locale-event]"):null;
 if(!a)return;
 var type=a.getAttribute("data-mpw-locale-event");
 if(type!=="program"&&type!=="starter30")return;
 var body=new URLSearchParams({locale:code,action:type});
 try{
  if(navigator.sendBeacon&&navigator.sendBeacon("/moj-prop/metrics/click.php",body))return;
  if(window.fetch)fetch("/moj-prop/metrics/click.php",{method:"POST",body:body,keepalive:true,credentials:"omit",mode:"same-origin"}).catch(function(){});
 }catch(ignore){}
},true);
})();
</script>'''
REPORT_CONTENT=r'''#!/usr/bin/env python3
"""Report only aggregate program and Starter30 CTA event counts by UTC day and locale."""
import pathlib,json,collections
root=pathlib.Path("/home/zomorod2/.private_mojplaywin_main_agents/mojprop_global_funnel_20261121")
totals=collections.Counter()
seen=0
for p in sorted(root.glob("events-????????.json")):
 try:
  d=json.loads(p.read_text())
  if d.get("metric")!="anonymous_cta_click_events_not_unique_visitors" or not isinstance(d.get("counts"),dict):continue
  print("UTC_DAY",d["day_utc"])
  for lang,v in sorted(d["counts"].items()):
   for action in ("program","starter30"):
    n=v.get(action,0)
    if isinstance(n,int) and n>0:
     print("EVENT",lang,action,n)
     totals[action]+=n
  seen+=1
 except Exception as ex:print("INVALID",p.name,type(ex).__name__)
print("FILES",seen,"PROGRAM_CLICKS",totals['program'],"STARTER30_CLICKS",totals['starter30'])
print("INTERPRETATION: Events only. No proof of unique visitors, paid invoices or human-only traffic.")
'''
def sha(b):return hashlib.sha256(b).hexdigest()
def at_replace(p,data,mode=0o644):
 temp=None
 try:
  with tempfile.NamedTemporaryFile('wb',dir=p.parent,prefix='.mojprop-cta-',delete=False) as f:
   temp=Path(f.name);f.write(data);f.flush();os.fsync(f.fileno())
  os.chmod(temp,mode);os.replace(temp,p)
 finally:
  if temp and temp.exists():temp.unlink()
def exactly(text,needle,new):
 if text.count(needle)!=1:raise RuntimeError('ANCHOR_DRIFT '+needle[:80]+' count '+str(text.count(needle)))
 return text.replace(needle,new,1)
def prepare():
 if getpass.getuser()!='zomorod2':raise RuntimeError('Wrong hosting account')
 if PRIVATE.exists() or PRIVATE.is_symlink() or METRICS.exists() or METRICS.is_symlink():
  raise RuntimeError('Tracking already initialized; refuse to overwrite')
 if not EVIDENCE.exists():raise RuntimeError('Missing previous SHA manifest')
 receipt=json.loads(EVIDENCE.read_text())
 if receipt.get('status')!='published':raise RuntimeError('Previous release not complete')
 targets={}
 for code in CODES:
  p=DIR/code/'index.html'
  if p.is_symlink() or not p.is_file() or sha(p.read_bytes())!=receipt['after'].get(str(p)):
   raise RuntimeError('LOCALIZED_PAGE_DRIFT '+code)
  s=p.read_text()
  a='class="cta" href="/moj-prop/"'
  b='class="secondary" href="/moj-prop/starter-30-trx/"'
  s=exactly(s,a,'class="cta" data-mpw-locale-event="program" href="/moj-prop/"')
  s=exactly(s,b,'class="secondary" data-mpw-locale-event="starter30" href="/moj-prop/starter-30-trx/"')
  s=exactly(s,'</body>'+chr(10)+'</html>',JS+chr(10)+'</body>'+chr(10)+'</html>') if '</body>'+chr(10)+'</html>' in s else exactly(s,'</body></html>',JS+chr(10)+'</body></html>')
  if s.count('id="mojprop-global-cta-events-20261121"')!=1:raise RuntimeError('JS insertion error')
  targets[p]=s.encode('utf8')
 if not ROBOTS.is_file() or ROBOTS.is_symlink() or sha(ROBOTS.read_bytes())!=ROBOTS_EXPECTED:
  raise RuntimeError('ROOT_ROBOTS_DRIFT')
 s=ROBOTS.read_text()
 s=exactly(s,'Sitemap: https://mojplaywin.com/moj-prop/sitemap.xml',
   'Disallow: /moj-prop/metrics/'+chr(10)+'Sitemap: https://mojplaywin.com/moj-prop/sitemap.xml')
 targets[ROBOTS]=s.encode('utf8')
 if 'fsync' in PHP:raise RuntimeError('Unexpected PHP feature')
 return targets

def probe():
 data=b'locale=en&action=probe'
 req=urllib.request.Request('https://mojplaywin.com/moj-prop/metrics/click.php',
  data=data,headers={'Origin':'https://mojplaywin.com',
   'Referer':'https://mojplaywin.com/moj-prop/languages/en/',
   'Content-Type':'application/x-www-form-urlencoded',
   'User-Agent':'MOJPROP_OWNED_PHP_PROBE_NOT_A_CUSTOMER'},method='POST')
 with urllib.request.urlopen(req,timeout=12) as r:
  if r.status!=204 or r.headers.get('X-MPW-Metrics-Probe')!='ok' or r.read():
   raise RuntimeError('PHP endpoint did not execute safely')

def run():
 if len(sys.argv)!=2 or sys.argv[1] not in ('--check','--apply'):raise SystemExit('usage --check|--apply')
 mapping=prepare()
 print('GUARDED_PREPARED','PAGES',len(CODES),'FILES',len(mapping),'PRIVATE_NO_PII',True)
 if sys.argv[1]=='--check':return
 PRIVATE.mkdir(parents=True,mode=0o700);os.chmod(PRIVATE,0o700)
 copies=PRIVATE/'backups';copies.mkdir(mode=0o700)
 originals={}
 for i,p in enumerate(mapping):
  b=copies/('original_%02d.bin'%i)
  raw=p.read_bytes()
  b.write_bytes(raw);os.chmod(b,0o600)
  if sha(b.read_bytes())!=sha(raw):raise RuntimeError('Backup integrity error')
  originals[str(p)]={'sha':sha(raw),'backup':str(b),'mode':stat.S_IMODE(p.stat().st_mode)}
  if sha(p.read_bytes())!=originals[str(p)]['sha']:raise RuntimeError('Concurrent mutation')
 record={'status':'prepared','before':originals,'after':{str(p):sha(v) for p,v in mapping.items()},
  'created_endpoint':str(ENDPOINT),'metric':'click_event_only_no_unique_visitors_no_payment'}
 RECEIPT.write_text(json.dumps(record,indent=2)+chr(10));os.chmod(RECEIPT,0o600)
 REPORT.write_text(REPORT_CONTENT);os.chmod(REPORT,0o600)
 METRICS.mkdir(mode=0o755)
 completed=[]
 try:
  at_replace(ENDPOINT,PHP.encode('utf8'),0o644)
  completed.append(ENDPOINT)
  check=subprocess.run(['php','-l',str(ENDPOINT)],capture_output=True,text=True,timeout=8)
  if check.returncode!=0:raise RuntimeError('PHP lint failed '+check.stdout)
  probe()
  for p,data in mapping.items():
   if sha(p.read_bytes())!=originals[str(p)]['sha']:raise RuntimeError('Concurrent page edit '+str(p))
   at_replace(p,data,originals[str(p)]['mode'])
   completed.append(p)
  for p,data in mapping.items():
   if sha(p.read_bytes())!=sha(data):raise RuntimeError('Publish hash fail '+str(p))
  record['status']='published';record['php_lint']='success';record['live_probe']='HTTP_204_not_counted'
  RECEIPT.write_text(json.dumps(record,indent=2)+chr(10))
  print('LIVE_CTA_METRICS_PUBLISHED',len(CODES),'LOCALES','BACKUPS_VERIFIED','PHP_PROBE_204')
 except BaseException:
  for p in reversed(completed):
   if p==ENDPOINT:
    if p.exists() and sha(p.read_bytes())==sha(PHP.encode()):p.unlink()
    continue
   if p.exists() and sha(p.read_bytes())==record['after'][str(p)]:
    entry=originals[str(p)]
    at_replace(p,Path(entry['backup']).read_bytes(),entry['mode'])
  raise
if __name__=='__main__':run()
