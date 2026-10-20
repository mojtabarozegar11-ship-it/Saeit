#!/usr/bin/env python3
"""Atomic isolated static MojPlayWin free working tools release: 12 pages, 1 hub, JS/CSS."""
import io,tarfile,sys,json,hashlib,stat,os,re,tempfile
from pathlib import Path
ROOT=Path('/home/zomorod2/mojplaywin.com/mpw-editorial/revenue')
HOME=Path('/home/zomorod2')
SLUGS=('website-doctor','landing-page-studio','ai-automation','business-spreadsheets','website-templates','social-media-kits','resume-builder','logo-studio','browser-games','marketing-ai','business-calculators','website-care')
JS=ROOT/'assets/tools-v1.js'
CSS=ROOT/'assets/tools-v1.css'
HUB=ROOT/'index.html'
HEAD='<link rel="stylesheet" href="/mpw-editorial/revenue/assets/tools-v1.css">'
HUB_NOTICE='<section class="card" id="mpw-working-12-tools" style="margin:24px 0;border-color:#d6b577"><h2>12 working, free interactive tools</h2><p>All twelve offer pages now provide an interactive utility or editable downloadable result: website checklists, landing pages, workflow blueprints, spreadsheet CSVs, website starters, social captions, resumes, SVG logo concepts, a browser puzzle game, campaign plans, financial calculators and maintenance reports. Browser tools are free; paid custom orders and online payment are separate processes.</p><p><a href="#offers">Try all twelve tools ↗</a></p></section>'
def fail(message):raise RuntimeError(message)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def guard():
    if ROOT.is_symlink() or not ROOT.is_dir() or ROOT.resolve()!=ROOT:fail('Unexpected public tool root')
    if not (ROOT.parent/'index.html').is_file() or not HUB.is_file() or HUB.is_symlink():fail('Static revenue hub identity missing')
    for slug in SLUGS:
        p=ROOT/slug/'index.html'
        if not p.is_file() or p.is_symlink() or p.parent.is_symlink():fail('Missing revenue page: '+slug)
    if JS.exists() or JS.is_symlink() or CSS.exists() or CSS.is_symlink():fail('Tool version already installed')
def docs():
    content=sys.stdin.buffer.read(150000)
    if not content or len(content)>=150000:fail('Invalid toolkit archive')
    tf=tarfile.open(fileobj=io.BytesIO(content),mode='r:gz')
    expected={'toolkit.js','toolkit.css'}
    files=[m for m in tf.getmembers() if m.isfile()]
    if {m.name.removeprefix('./') for m in files}!=expected:fail('Toolkit file whitelist mismatch')
    if any(m.issym() or m.islnk() or not (m.isdir() or m.isfile()) for m in tf.getmembers()):fail('Unsafe archive')
    found={}
    for m in files:
        data=tf.extractfile(m).read()
        if len(data)!=m.size or m.size>120000:fail('Invalid size')
        found[m.name.removeprefix('./')]=data
    if b'const defs=' not in found['toolkit.js'] or b'getElementById("mpw-functional-tool")' not in found['toolkit.js']:fail('JS toolkit signature absent')
    if b'.mpw-functional-wrap' not in found['toolkit.css']:fail('CSS signature absent')
    return found
def stage_contents(slug,contents):
    text=contents.decode('utf8')
    if text.count('</main>')!=1 or text.count('</head>')!=1:fail('Unexpected static page structure '+slug)
    if 'id="mpw-functional-tool"' in text:fail('Tool already integrated '+slug)
    for sig in ('href="/mpw-editorial/revenue/index.html"','<html lang="en">'):
        if sig not in text:fail('Page lacks verified SEO origin '+slug)
    ui=('<section class="mpw-revenue-usable" aria-label="Interactive '+slug.replace('-',' ')+' tool">'
        '<div id="mpw-functional-tool" data-tool="'+slug+'"></div>'
        '<script defer src="/mpw-editorial/revenue/assets/tools-v1.js"></script>'
        '<noscript><p>Enable JavaScript to use this browser-based tool. You can still enquire through the contact form.</p></noscript>'
        '</section>')
    text=text.replace('</head>',HEAD+'</head>',1).replace('</main>',ui+'</main>',1)
    return text.encode('utf8')
def stage_hub(content):
    text=content.decode('utf8')
    if text.count('<section id="offers">')!=1 or 'id="mpw-working-12-tools"' in text:fail('Hub structure drift')
    text=text.replace('<section id="offers">',HUB_NOTICE+'<section id="offers">',1)
    return text.encode('utf8')
def backup_dir(run):
    if not re.fullmatch(r'[0-9]{8,20}',run):fail('Invalid run id')
    return HOME/('.mpw-functional12-'+run)
def atomic(path,contents):
    fd,temp=tempfile.mkstemp(dir=path.parent,prefix='.mpw-interactive-stage-')
    try:
        if path.exists():os.fchmod(fd,stat.S_IMODE(path.stat().st_mode))
        else:os.fchmod(fd,0o644)
        with os.fdopen(fd,'wb') as f:f.write(contents);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
def publish(run):
    guard()
    files=docs()
    old={'hub':HUB.read_bytes()}
    updates={'hub':stage_hub(old['hub'])}
    paths={'hub':HUB}
    for slug in SLUGS:
        key=slug;p=ROOT/slug/'index.html'
        old[key]=p.read_bytes()
        updates[key]=stage_contents(slug,old[key])
        paths[key]=p
    paths.update({'toolkit.js':JS,'toolkit.css':CSS})
    updates.update({'toolkit.js':files['toolkit.js'],'toolkit.css':files['toolkit.css']})
    d=backup_dir(run)
    if d.exists() or d.is_symlink():fail('Backup collision')
    d.mkdir(mode=0o700)
    manifest={}
    for key,contents in old.items():
        p=d/(key+'.bak')
        with p.open('xb') as out:os.fchmod(out.fileno(),0o600);out.write(contents)
        manifest[key]={'original':sha(contents),'new':sha(updates[key])}
    for key in ('toolkit.js','toolkit.css'):manifest[key]={'original':None,'new':sha(updates[key])}
    (d/'manifest.json').write_text(json.dumps({'run':run,'files':manifest},sort_keys=True))
    os.chmod(d/'manifest.json',0o600)
    changed=[]
    try:
        for key in ['toolkit.js','toolkit.css','hub',*SLUGS]:
            p=paths[key]
            if key in old and sha(p.read_bytes())!=manifest[key]['original']:fail('Concurrent live page edits')
            if key not in old and (p.exists() or p.is_symlink()):fail('New toolkit collision')
            atomic(p,updates[key]);changed.append(key)
            if sha(p.read_bytes())!=manifest[key]['new']:fail('Integrity check failed '+key)
    except BaseException:
        for key in reversed(changed):
            p=paths[key]
            if sha(p.read_bytes())!=manifest[key]['new']:continue
            if key in old:atomic(p,old[key])
            else:p.unlink()
        raise
    print('MPW_TWELVE_REAL_FREE_TOOLS_INSTALLED='+json.dumps({'working_pages':len(SLUGS),'new_scripts':2,'hub_updated':True,'digital_store_payment_modified':False,'other_domains_modified':False}))
def rollback(run):
    if ROOT.is_symlink() or not ROOT.is_dir():fail('Root unavailable')
    d=backup_dir(run)
    if d.is_symlink() or not d.is_dir():fail('Backup not found')
    doc=json.loads((d/'manifest.json').read_text())
    if doc.get('run')!=run:fail('Owner mismatch')
    paths={'hub':HUB,'toolkit.js':JS,'toolkit.css':CSS}
    for slug in SLUGS:paths[slug]=ROOT/slug/'index.html'
    old={}
    for key,path in paths.items():
        if not path.is_file() or path.is_symlink() or sha(path.read_bytes())!=doc['files'][key]['new']:fail('Concurrent release changed '+key)
        if key not in ('toolkit.js','toolkit.css'):
            source=d/(key+'.bak')
            if source.is_symlink() or not source.is_file() or sha(source.read_bytes())!=doc['files'][key]['original']:fail('Bad backup '+key)
            old[key]=source.read_bytes()
    for key,data in old.items():atomic(paths[key],data)
    for key in ('toolkit.js','toolkit.css'):paths[key].unlink()
    print('MPW_TWELVE_FUNCTIONAL_TOOLS_ROLLBACK=PASS')
def selftest():
    sample=b'<!doctype html><html lang="en"><head></head><body><main><a href="/mpw-editorial/revenue/index.html">Back</a><p>Original</p></main></body></html>'
    for slug in SLUGS:
        out=stage_contents(slug,sample)
        assert out.count(b'id="mpw-functional-tool"')==1 and b'<p>Original</p>' in out
    hub=b'<html><section id="offers">Find</section></html>'
    assert b'mpw-working-12-tools' in stage_hub(hub)
    print('MPW_12_FUNCTIONAL_TOOL_STRUCTURE_SELFTEST=PASS')
if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest':selftest()
    elif len(sys.argv)==3 and sys.argv[1] in ('publish','rollback'):(publish if sys.argv[1]=='publish' else rollback)(sys.argv[2])
    else:raise SystemExit('selftest|publish RUN_ID|rollback RUN_ID')
