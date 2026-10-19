#!/usr/bin/env python3
"""Six coordinated, reversible improvements to the MAIN MojPlayWin static site.

Files: 19 Apache-mapped informational HTML pages, its exact served homepage,
two new PHP topic/search views, one JSON index, and one additive block in the
MojPlayWin document-root .htaccess. Never modify Django, Passenger, child-site
routes or payment/account data. Uses pinned pre-edit fingerprints and backups.
"""
from pathlib import Path
import hashlib,html,json,os,pwd,re,stat,sys,tempfile,urllib.parse

HOME=Path("/home/zomorod2")
ROOT=HOME/"mojplaywin.com"
PRE=ROOT/"design-preview-20261017/mpw-ten-editorials-20261018/pages"
HOMEPAGE=ROOT/"design-preview-20261017/production-home-20261017.html"
HT=ROOT/".htaccess"
NEW=ROOT/"design-preview-20261017/mpw-site-integrity-20261019"
HT_SHA="2eb1087587880288219d8212b6785844aa094ed2b2c45aef52f701d82fd59017"
HOME_SHA="71d2127a272e8c9d9ca857120e59757e7a7fef2af1ec73e8be1c746a0d358bbc"
STATIC=[
("about-mojtaba-rozegar","40437c6364c6bc5ff62bfebbd5435ced5ba3acd62cca94e35053d6365c855eb7"),
("about","d81b515bfdaa4b3f1138593cb0b0c361f88569fafd4b77f3a9a610bc809dffe4"),
("agents","1a0f2880cf9bcbcf8c5a6078f47168cab36d3c532d4fd4055c8013750f7af727"),
("company","5db22af9954a63554f04ebf19ffbb689c48bc667a951cf72928de36df0323aa4"),
("economy","605d9aef099afb8bc5e2f224c8b5ab24c0b748357ab0ee8d46fee907b6021117"),
("industry","55b11e9d548a9b2d8132ef9f59b5af4a2dbb51bdb147ddb50d3396de41aec15c"),
("knowledge","57e23bc9a8859f7a3ae3873bafdf15545eeaf6bf3beb32b45febd5f057a42955"),
("market","854588ca38920b4c22d58d4be63e6934fb8b1bd8d4aa01a0cf63fbcd69a4d4c9"),
("research","1030bab41ff9965953c0309219f3e272edbf5b37377b8afe7bc67799511aaccd"),
("services","01e4bd0ccbdb409b3a55d8c5ab30a5e8e1a1043fa0a4ed2041c1bfc548bc2da9"),
("studio","3e51e4e45294c0defd3d4e6ddb208ea7417735b2f1f8ff6cdda38a5e8bd2a732"),
("ventures-agriculture","bb616fcf80e44d1842bd893a6a031e8cc3dd1f94fa7e775aa5944456ec20a612"),
("ventures-cafe-restaurant","37a8cb7b1dc03f02bd5ef5c4c310ff3b6cf8adc544b050f80a11a1d8f376c039"),
("ventures-carpets","28a41a6d2bcf6c3953be4f1cecf723c172c6b80a62350b97e9d0110c99851b20"),
("ventures-currency-crypto","b62b92f86a55d9b9448849e78cdf5d91a4655609445fd2ce9f257a18fb8981eb"),
("ventures-ecommerce","61e8cde2e054245faef50ee1742cbf0e7b7802dca4e20f26e5a7eb9bcfa86912"),
("ventures-fuel-station","07c8b510284e96173d14b0df224140771f789080543017827bc6d6517793b1dd"),
("ventures-hospitality","1bb5a80859b2d791b373b245a8dd447bdfdcb5970025da2fad483ba8d9f0c40c"),
("ventures-jewelry-gold","1816062d23544177005ee3df5b8ffa859a6dbfdd8ffa0fe06fdc6dcdac652f3f"),
]
BRAND_IMG="/design-preview-20261017/static/site/mojplaywin-atelier/official-coin-80.3ea52711f49d.webp"
MARK="# BEGIN MPW_SIX_MAIN_ONLY_20261019"
CLOSE="# END MPW_SIX_MAIN_ONLY_20261019"
RULES=f"""
{MARK}
# GET only; separate main MojPlayWin search/topic reader, no shared app restarts.
RewriteCond %{{REQUEST_METHOD}} ^GET$
RewriteCond %{{REQUEST_URI}} ^/search/$
RewriteRule ^.*$ /design-preview-20261017/mpw-site-integrity-20261019/search.php [END,QSA]
RewriteCond %{{REQUEST_METHOD}} ^GET$
RewriteCond %{{REQUEST_URI}} ^/topics/$
RewriteRule ^.*$ /design-preview-20261017/mpw-site-integrity-20261019/topic.php [END,QSA]
{CLOSE}
"""
CSS="""<style id="mpw-six-accessibility-20261019">
:where(.mw-site-nav,.mpw-header) a:focus-visible,
:where(.mw-site-footer,.mpw-footer) a:focus-visible,
.mpo-orbit-card:focus-visible {outline:3px solid #f3d38e;outline-offset:3px}
@media(prefers-reduced-motion:reduce){
.mpw-site *,.mpw-site *::before,.mpw-site *::after,
.mpo-orbit-track,.mpo-orbit-card,.mw-card {scroll-behavior:auto!important;animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}
}
@media(max-width:720px){.mw-site-footer{padding-inline:16px}.mw-site-nav{max-width:100%}}
</style>
"""
def sha(data):return hashlib.sha256(data).hexdigest()
def assert_runid(v):
    if not re.fullmatch(r"[0-9]{9,20}",v):raise RuntimeError("Bad run id")
    return v
def page_route(name):
    if name.startswith("ventures-"):return "/ventures/"+name[len("ventures-"):]+"/"
    if name=="about-mojtaba-rozegar":return "/about/mojtaba-rozegar/"
    return "/"+name+"/"
def protect_env():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":raise RuntimeError("Unexpected cPanel account")
    for p in (ROOT,PRE,HOMEPAGE.parent):
        if not p.is_dir() or p.is_symlink():raise RuntimeError("Unsafe base directory")
    w=ROOT/"passenger_wsgi.py"
    if not w.is_file() or w.is_symlink() or "Saeit-staging" not in w.read_text(errors="replace"):raise RuntimeError("Passenger owner changed")
    if not HT.is_file() or HT.is_symlink():raise RuntimeError("Bad .htaccess")
    ht=HT.read_bytes()
    if sha(ht)!=HT_SHA or MARK.encode() in ht:raise RuntimeError("Routing changed; fail closed")
    rules=ht.decode("utf8","replace")
    for name,_ in STATIC:
        route=page_route(name)
        if "mpw-ten-editorials-20261018/pages/"+name+".html" not in rules:raise RuntimeError("Missing exact main-only target "+route)
    if NEW.exists() or NEW.is_symlink():raise RuntimeError("New scoped directory already exists")
    if "RewriteCond %{REQUEST_URI} ^/$" not in rules:raise RuntimeError("Root homepage ownership unverified")
def meta_patch(s,key,target):
    if key=="canonical":
        pattern=r'<link\b(?=[^>]*\brel\s*=\s*["\']canonical["\'])[^>]*>'
        replacement='<link rel="canonical" href="'+html.escape(target,quote=True)+'">'
    else:raise RuntimeError("unsupported meta")
    matches=list(re.finditer(pattern,s,re.I))
    if len(matches)!=1:raise RuntimeError("Expected one canonical, found "+str(len(matches)))
    m=matches[0]
    return s[:m.start()]+replacement+s[m.end():]
def strip_legacy(s):
    def drop(tag,klass,source):
        pattern=r'<'+tag+r'\b[^>]*class=["\']'+re.escape(klass)+r'["\'][^>]*>[\s\S]*?</'+tag+r'\s*>'
        replaced,n=re.subn(pattern,'',source,count=1,flags=re.I)
        if n!=1:raise RuntimeError("Missing isolated legacy "+klass)
        return replaced
    if '<header class="site-header"' in s:
        if '<header class="mw-site-nav"' not in s or '<footer class="mw-site-footer"' not in s:
            raise RuntimeError("Would remove header without replacement")
        s=drop("header","site-header",s)
    if '<footer class="site-footer"' in s:
        if '<footer class="mw-site-footer"' not in s:raise RuntimeError("Would remove footer without replacement")
        s=drop("footer","site-footer",s)
    return s
def images(s):
    logo=r'(?<=src=")data:image/jpeg;base64,[A-Za-z0-9+/=]+(?=")'
    s,n=re.subn(logo,BRAND_IMG,s)
    if n>1:raise RuntimeError("Unexpected number of inlined logos")
    i=[0]
    def adjust(m):
        tag=m.group(0);i[0]+=1
        if i[0]<=2:return tag
        if not re.search(r'\bdecoding=',tag,re.I):tag=tag[:-1]+' decoding="async">'
        if not re.search(r'\bloading=',tag,re.I):tag=tag[:-1]+' loading="lazy">'
        return tag
    return re.sub(r'<img\b[^>]*>',adjust,s,flags=re.I)
def edit_static(name,data):
    s=data.decode("utf8","strict")
    if not s.lstrip().lower().startswith("<!doctype html>"):raise RuntimeError("Unexpected HTML document "+name)
    s=strip_legacy(s)
    s=re.sub(r'(<html\b[^>]*\blang=["\'])fa(["\'])',r'\1en\2',s,count=1,flags=re.I)
    s=re.sub(r'(<html\b[^>]*\bdir=["\'])rtl(["\'])',r'\1ltr\2',s,count=1,flags=re.I)
    s=meta_patch(s,"canonical","https://mojplaywin.com"+page_route(name))
    s=images(s)
    if "</head>" not in s.lower():raise RuntimeError("No document head")
    s=s.replace("</head>",CSS+"</head>",1)
    if name not in ("about","about-mojtaba-rozegar","services","studio"):
        if len(re.findall(r'<header class="mw-site-nav"',s))!=1 or len(re.findall(r'<footer class="mw-site-footer"',s))!=1:
            raise RuntimeError("Ununified navigation on "+name)
        if re.search(r'<(?:header|footer) class="site-(?:header|footer)"',s):
            raise RuntimeError("Old brand remained")
    if s.count('rel="canonical"')!=1 or 'lang="en"' not in s or 'Mojtaba Roozegar' not in s:
        raise RuntimeError("Static SEO/footer regression "+name)
    return s.encode("utf8")
def clean(t):return html.unescape(re.sub(r'<[^>]+>'," ",t)).strip()
def improve_home(data):
    s=data.decode("utf8","strict")
    card=re.compile(r'(<a\b[^>]*\bclass="mpo-orbit-card[^"]*"[^>]*\bhref=")([^"]+)("[^>]*>)([\s\S]*?)(</a>)',re.I)
    cards=[]
    def rep(m):
        content=m.group(4)
        strong=re.search(r'<strong\b[^>]*>([\s\S]*?)</strong>',content,re.I)
        small=re.search(r'<small\b[^>]*>([\s\S]*?)</small>',content,re.I)
        if not strong or not small:raise RuntimeError("Unrecognized carousel item")
        title=clean(strong.group(1));desc=clean(small.group(1));url=m.group(2)
        if not title or not desc or not (url.startswith("/") and not url.startswith("//")):
            raise RuntimeError("Unsafe topic card")
        number=len(cards)+1
        tid=f"{number:04d}"
        cards.append({"id":tid,"title":title,"summary":desc,"category":url})
        # Make each card open a distinct, useful topic record; the original
        # functional section destination remains available in that record.
        return m.group(1)+"/topics/?id="+tid+m.group(3)+content+m.group(5)
    s,n=card.subn(rep,s)
    if n!=340 or len(cards)!=340:raise RuntimeError("Expected exactly 340 unique card destinations")
    if len({c["id"] for c in cards})!=340:raise RuntimeError("Duplicate topic identity")
    if len(re.findall(r'class="mpo-orbit-track"',s))!=17:raise RuntimeError("Missing homepage carousel")
    s=images(s)
    if "</head>" not in s:raise RuntimeError("No home head")
    s=s.replace("</head>",CSS+"</head>",1)
    return s.encode("utf8"),cards
def index_data(cards):
    records=[]
    for name,_ in STATIC:
        title=name.replace("-"," ").title()
        if name=="about":title="About MojPlayWin"
        if name=="about-mojtaba-rozegar":title="Mojtaba Roozegar"
        records.append({"title":title,"description":title+" — MojPlayWin company research and information.","url":page_route(name),"type":"Section"})
    others=[
    ("MojPlayWin","MojPlayWin games, research, education, products and company home","/"),
    ("Chess improvement book","The Science and Practice of Chess Improvement — original chess study digital book","/store/"),
    ("Taniya and the Little Baker Worms","Illustrated children's storybook for families","/store/"),
    ("Digital Store","Books, chess, Taniya, original games and digital products","/store/"),
    ("Games","Original games including First Realm","/games/"),
    ("Artificial Intelligence","AI applications and responsible technology","/ai/"),
    ("Search","Search all MojPlayWin informational pages","/search/"),
    ("Education","Learning and study resources","/education/"),
    ("Weather","Weather insights","/weather/"),
    ("Professor Mojtaba Roozegar","Founder biography and scientific leadership","/about/mojtaba-rozegar/"),
    ("Privacy Policy","Privacy and user data guidelines","/privacy/"),
    ("Terms","Terms of service","/terms/"),
    ("Contact","Contact MojPlayWin","/contact/"),
    ("Support","Support MojPlayWin","/support/"),
    ]
    records += [{"title":t,"description":d,"url":u,"type":"Page"} for t,d,u in others]
    records += [{"title":c["title"],"description":c["summary"],"url":"/topics/?id="+c["id"],"type":"Topic"} for c in cards]
    return json.dumps({"version":"20261019","records":records,"topics":cards},ensure_ascii=False,separators=(",",":")).encode("utf8")
COMMON_CSS="""<style>html{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 80% -10%,#303020,transparent 60%),#090a0a;color:#f3ecd7;font:16px/1.6 system-ui,Arial,sans-serif}a{color:#e9c97d}a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid #efcd7f;outline-offset:3px}.shell{max-width:1120px;padding:22px;margin:auto}.nav{display:flex;flex-wrap:wrap;gap:18px;align-items:center;padding:20px 0;border-bottom:1px solid #635334}.nav strong{font-size:1.15rem;color:#efcb7b}.nav a{text-decoration:none}.panel{margin-top:24px;padding:clamp(20px,4vw,40px);background:linear-gradient(140deg,rgba(194,151,58,.12),rgba(17,20,19,.95));border:1px solid #66512c;border-radius:22px;box-shadow:0 18px 35px #0006}.eyebrow{color:#e6bd67;font-weight:650;letter-spacing:.13em;font-size:.78rem}h1{font-size:clamp(1.7rem,4vw,3rem);line-height:1.2}ul{list-style:none;padding:0;display:grid;gap:12px}li{padding:14px;border:1px solid #4b422a;border-radius:12px;background:#171a19}p{max-width:85ch}.go{display:inline-block;background:#c59d4d;color:#111;text-decoration:none;padding:11px 17px;border-radius:9px;font-weight:700}input{width:min(100%,700px);padding:16px;background:#101312;color:white;border:1px solid #8c7543;border-radius:10px;font:inherit}button{padding:15px 20px;background:#cfaa64;color:#15110b;border:none;border-radius:10px;font-weight:800;cursor:pointer}.footer{padding:36px 0;text-align:center;margin-top:30px;border-top:1px solid #493c25;color:#e9ca89;font-weight:800}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;animation:none!important;transition:none!important}}</style>"""
def php_shared():
    return r"""<?php
declare(strict_types=1);
header('Content-Type: text/html; charset=UTF-8');
header('X-Content-Type-Options: nosniff');
$payload=json_decode(file_get_contents(__DIR__.'/index.json'),true);
if (!is_array($payload) || !isset($payload['records'],$payload['topics'])){http_response_code(503);exit('Index temporarily unavailable');}
function safe($s){return htmlspecialchars((string)$s,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
function lower($v){return function_exists('mb_strtolower')?mb_strtolower((string)$v,'UTF-8'):strtolower((string)$v);}
function head_html($title,$description,$canonical){echo '<!doctype html><html lang="en" dir="ltr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="'.safe($description).'"><title>'.safe($title).'</title><link rel="canonical" href="'.safe($canonical).'">';}
function top_nav(){echo '</head><body><div class="shell"><nav class="nav" aria-label="MojPlayWin navigation"><strong>MojPlayWin</strong><a href="/">Home</a><a href="/store/">Digital Store</a><a href="/research/">Research</a><a href="/games/">Games</a><a href="/about/">About</a><a href="/search/">Search</a></nav>';}
function footer_html(){echo '<footer class="footer">Mojtaba Roozegar</footer></div></body></html>';}
"""
def php_search():
    return php_shared()+r"""
$q=substr(trim((string)($_GET['q']??'')),0,160);
$parts=preg_split('/\s+/u',lower($q),-1,PREG_SPLIT_NO_EMPTY);
$parts=array_slice(array_filter($parts,fn($part)=>strlen($part)>0),0,8);
$scores=[];
if ($q!=='')foreach($payload['records'] as $record){
   $title=lower($record['title']);$desc=lower($record['description']);
   $score=0;
   foreach($parts as $token){if(strpos($title,$token)!==false)$score+=5; if(strpos($desc,$token)!==false)$score+=2;}
   if($score>0)$scores[]=['score'=>$score,'record'=>$record];
}
usort($scores,fn($a,$b)=>$b['score']<=>$a['score']);
head_html('Search | MojPlayWin','Search MojPlayWin books, games, research and original topics','https://mojplaywin.com/search/');
echo '""" + COMMON_CSS + r"""';
top_nav();
echo '<main class="panel"><span class="eyebrow">MOJPLAYWIN / CONTENT INDEX</span><h1>Search MojPlayWin</h1><form method="get" action="/search/" role="search"><label for="q">Search books, games, research and topics</label><div style="display:flex;flex-wrap:wrap;gap:10px"><input id="q" type="search" name="q" value="'.safe($q).'" maxlength="160" placeholder="Chess, AI, MojPlayWin, research" required><button type="submit">Search</button></div></form>';
if($q===''){echo '<p>Try “chess”, “MojPlayWin”, “AI”, “research” or “Taniya”.</p>';}
else{
 echo '<h2>'.count($scores).' matches for “'.safe($q).'”</h2>';
 if(!$scores)echo '<p>No matching content was found. Try another topic or browse the categories.</p>';
 else{echo '<ul>';foreach(array_slice($scores,0,80) as $entry){$row=$entry['record'];echo '<li><small class="eyebrow">'.safe($row['type']).'</small><h3><a href="'.safe($row['url']).'">'.safe($row['title']).'</a></h3><p>'.safe($row['description']).'</p></li>';}echo '</ul>';}
}
echo '</main>';footer_html();
"""
def php_topic():
    return php_shared()+r"""
$id=(string)($_GET['id']??'');
if(!preg_match('/^\d{4}$/',$id)){http_response_code(404);exit('Topic not found');}
$selected=null;$related=[];
foreach($payload['topics'] as $item){if($item['id']===$id)$selected=$item;}
if(!$selected){http_response_code(404);exit('Topic not found');}
foreach($payload['topics'] as $item){if($item['category']===$selected['category'] && $item['id']!==$id && count($related)<6)$related[]=$item;}
head_html($selected['title'].' | MojPlayWin Topics',$selected['summary'],'https://mojplaywin.com/topics/?id='.$id);
echo '<meta name="robots" content="noindex,follow">""" + COMMON_CSS + r"""';
top_nav();
echo '<main class="panel"><span class="eyebrow">MOJPLAYWIN / TOPIC '.safe($selected['id']).'</span><h1>'.safe($selected['title']).'</h1><p>'.safe($selected['summary']).'</p><p>This is a topic overview from the MojPlayWin card library; explore the related section for current resources, materials and availability.</p><p><a class="go" href="'.safe($selected['category']).'">Explore related section →</a></p>';
if($related){echo '<h2>Related topics</h2><ul>';foreach($related as $item){echo '<li><a href="/topics/?id='.safe($item['id']).'">'.safe($item['title']).'</a></li>';}echo '</ul>';}
echo '</main>';footer_html();
"""
def compile_changes():
    protect_env()
    src=[(HOMEPAGE,HOME_SHA)]+[(PRE/(name+".html"),expected) for name,expected in STATIC]
    original=[]
    for p,expected in src:
        if not p.is_file() or p.is_symlink():raise RuntimeError("Missing or unsafe main source: "+str(p))
        raw=p.read_bytes()
        if sha(raw)!=expected:raise RuntimeError("Concurrent or unreviewed source: "+str(p))
        original.append((p,raw,stat.S_IMODE(p.stat().st_mode)))
    edited_home,cards=improve_home(original[0][1])
    rewritten=[(HOMEPAGE,original[0][1],edited_home,original[0][2])]
    for i,(name,_) in enumerate(STATIC):
        p,b,mode=original[i+1]
        rewritten.append((p,b,edit_static(name,b),mode))
    idx=index_data(cards)
    additions={NEW/"index.json":idx,NEW/"search.php":php_search().encode("utf8"),NEW/"topic.php":php_topic().encode("utf8")}
    before=HT.read_bytes()
    after=before.replace(b"RewriteEngine On",b"RewriteEngine On\n"+RULES.encode(),1)
    if after==before or after.count(MARK.encode())!=1 or len(rewritten)!=20 or len(additions)!=3:
        raise RuntimeError("Unexpected inventory")
    if before!=after.replace(b"\n"+RULES.encode(),b"",1):
        raise RuntimeError("Additive route patch mismatch")
    return rewritten,additions,(before,after)
def atomic(path,data,mode):
    if path.is_symlink() or not path.is_file():raise RuntimeError("Unsafe overwrite")
    fd,temp=tempfile.mkstemp(prefix=".mpw-six-atomic-",dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
def folder(runid):
    if not re.fullmatch(r"[0-9]{9,20}",runid):raise RuntimeError("Unsafe workflow identifier")
    return HOME/(".mpw-six-mainonly-backup-"+runid)
def install(runid):
    changes,additions,(oldht,newht)=compile_changes()
    backup=folder(runid)
    if backup.exists() or backup.is_symlink():raise RuntimeError("Backup collision")
    backup.mkdir(mode=0o700)
    rows=[]
    for i,(p,old,new,mode) in enumerate(changes):
        b=backup/(f"{i:03d}.original")
        with b.open("xb") as f:f.write(old);f.flush();os.fsync(f.fileno())
        os.chmod(b,0o600)
        rows.append(dict(path=str(p),old=sha(old),new=sha(new),mode=mode,backup=b.name))
    with (backup/"routing.original").open("xb") as f:f.write(oldht)
    os.chmod(backup/"routing.original",0o600)
    meta={"files":rows,"ht_old":sha(oldht),"ht_new":sha(newht),"created":{str(k):sha(v) for k,v in additions.items()}}
    (backup/"manifest.json").write_text(json.dumps(meta),encoding="utf8")
    os.chmod(backup/"manifest.json",0o600)
    installed=[]
    try:
        NEW.mkdir(mode=0o755)
        for path,body in additions.items():
            with path.open("xb") as f:f.write(body);f.flush();os.fsync(f.fileno())
            if sha(path.read_bytes())!=sha(body):raise RuntimeError("Scoped view checksum failed")
            os.chmod(path,0o644)
        for p,old,new,mode in changes:
            if sha(p.read_bytes())!=sha(old):raise RuntimeError("Concurrent change during release: "+str(p))
            atomic(p,new,mode)
            installed.append((p,old,new,mode))
            if sha(p.read_bytes())!=sha(new):raise RuntimeError("Postwrite checksum wrong: "+str(p))
        if sha(HT.read_bytes())!=sha(oldht):raise RuntimeError("Routing changed during release")
        atomic(HT,newht,stat.S_IMODE(HT.stat().st_mode))
        if sha(HT.read_bytes())!=sha(newht):raise RuntimeError("Routing postwrite checksum wrong")
    except Exception:
        if HT.is_file() and sha(HT.read_bytes())==sha(newht):
            atomic(HT,oldht,stat.S_IMODE(HT.stat().st_mode))
        for p,old,new,mode in reversed(installed):
            if p.is_file() and sha(p.read_bytes())==sha(new):atomic(p,old,mode)
        for p,b in additions.items():
            if p.is_file() and sha(p.read_bytes())==sha(b):p.unlink()
        if NEW.is_dir() and not any(NEW.iterdir()):NEW.rmdir()
        (backup/"FAILED").write_text("rolled back after interrupted install")
        raise
    (backup/"INSTALLED").write_text("yes")
    print("MPW_SIX_ATOMIC_INSTALLED=PASS FILES="+str(len(changes))+" NEW_VIEWS=3 TOPICS=340 SAFE_SUBSITES=true NO_PASSENGER_RESTART=true BACKUP="+str(backup),flush=True)
def rollback(runid):
    backup=folder(runid)
    if not backup.is_dir() or backup.is_symlink():raise RuntimeError("Missing backup")
    info=json.loads((backup/"manifest.json").read_text("utf8"))
    htold=(backup/"routing.original").read_bytes()
    if sha(htold)!=info["ht_old"]:raise RuntimeError("Corrupt route backup")
    if sha(HT.read_bytes()) not in (info["ht_old"],info["ht_new"]):raise RuntimeError("Concurrent unrelated routing edit")
    # Preflight everything before restoring anything; never clobber another edit.
    for row in info["files"]:
        b=(backup/row["backup"]).read_bytes()
        if sha(b)!=row["old"] or sha(Path(row["path"]).read_bytes()) not in (row["old"],row["new"]):
            raise RuntimeError("Concurrent main content edit; unsafe rollback")
    for p,expected in info["created"].items():
        q=Path(p)
        if q.is_file() and (q.is_symlink() or sha(q.read_bytes())!=expected):raise RuntimeError("New view modified by another actor")
    if sha(HT.read_bytes())==info["ht_new"]:
        atomic(HT,htold,stat.S_IMODE(HT.stat().st_mode))
    for row in reversed(info["files"]):
        path=Path(row["path"])
        if sha(path.read_bytes())==row["new"]:
            atomic(path,(backup/row["backup"]).read_bytes(),row["mode"])
    for p in info["created"]:
        q=Path(p)
        if q.is_file():q.unlink()
    if NEW.is_dir() and not any(NEW.iterdir()):NEW.rmdir()
    (backup/"ROLLED_BACK").write_text("yes")
    print("MPW_SIX_ATOMIC_ROLLBACK=PASS RESTORED="+str(len(info["files"])),flush=True)
def selftest():
    assert len(STATIC)==19 and len({n for n,_ in STATIC})==19
    assert len(HOME_SHA)==64 and len(HT_SHA)==64
    for name,hashsum in STATIC:assert len(hashsum)==64 and page_route(name).startswith("/")
    a=b'<!doctype html><html lang="fa" dir="rtl"><head><link rel="canonical" href="https://zomorodmelal.ir/agents/"></head><body><header class="site-header">old</header><header class="mw-site-nav">new</header><footer class="mw-site-footer">Mojtaba Roozegar</footer><footer class="site-footer">old</footer></body></html>'
    result=strip_legacy(a.decode("utf8"))
    assert result.count('<header')==1 and result.count('<footer')==1
    result=meta_patch(result,"canonical","https://mojplaywin.com/agents/")
    assert "https://zomorodmelal.ir/agents/" not in result
    assert "Mojtaba Roozegar" in php_topic() and "Chess" in str(index_data([{"id":"0001","title":"Chess","summary":"Chess","category":"/store/"}]))
    assert len(RULES.split('RewriteRule'))==3
    print("MPW_SIX_SOURCE_SELFTEST=PASS")
if __name__=="__main__":
    arg=sys.argv[1] if len(sys.argv)>1 else ""
    if arg=="selftest":selftest()
    elif arg=="audit":
        changes,additions,(oldht,newht)=compile_changes()
        print("MPW_SIX_ATOMIC_AUDIT=PASS files="+str(len(changes))+" new="+str(len(additions))+" homepage="+sha(changes[0][2])+" content="+str(sum(len(c[2]) for c in changes)),flush=True)
    elif arg=="install" and len(sys.argv)==3:install(sys.argv[2])
    elif arg=="rollback" and len(sys.argv)==3:rollback(sys.argv[2])
    else:raise SystemExit("selftest|audit|install RUNID|rollback RUNID")
