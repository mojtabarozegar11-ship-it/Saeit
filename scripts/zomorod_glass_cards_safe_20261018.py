#!/usr/bin/env python3
"""Reversible, CSS-only glass floating cards on the Zomorod root homepage."""
import hashlib,json,os,pwd,re,sys,tempfile
from pathlib import Path

HOME=Path('/home/zomorod2/public_html/index.html')
BACKUP=Path('/home/zomorod2/.backups/zomorod-glass-cards-20261018')
STYLE_ID='zm-glass-floating-cards-20261018'
STYLE=r'''<style id="zm-glass-floating-cards-20261018">
/* Only card surfaces: no change to .card-track, .orbit-shelf, row timing,
   cardinality, flex sizing, original transforms, or fixed page background. */
body .topic-card{
  background:linear-gradient(153deg,rgba(203,251,228,.22) 0%,rgba(35,117,96,.24) 26%,rgba(7,36,32,.71) 74%,rgba(8,22,28,.76) 100%)!important;
  border-color:rgba(249,224,155,.68);
  outline:1px solid rgba(244,238,208,.55);outline-offset:-2px;
  box-shadow:inset 1px 1px 0 rgba(255,255,255,.52),inset -1px -1px 0 rgba(126,233,206,.27),
    0 9px 18px rgba(0,9,15,.36),0 20px 35px rgba(0,10,19,.27),0 0 16px rgba(231,194,103,.26);
  transform-style:preserve-3d;
  -webkit-backdrop-filter:blur(7px) saturate(1.18);
  backdrop-filter:blur(7px) saturate(1.18);
  animation:zm-card-microfloat-20261018 7.8s ease-in-out infinite;
}
body .topic-card:nth-child(3n + 1){animation-delay:-2.4s;animation-duration:8.7s}
body .topic-card:nth-child(3n + 2){animation-delay:-5.5s;animation-duration:9.3s}
body .topic-card:nth-child(4n){animation-delay:-1.3s;animation-duration:7.3s}
@keyframes zm-card-microfloat-20261018{0%,100%{translate:0 0}50%{translate:0 -3px}}
/* All existing topic images cover the card: render the glass OVER images.
   This layer is positioned and pointer-transparent: no new flex item. */
body .topic-card::after{
  content:"";position:absolute;inset:0;z-index:1;pointer-events:none;
  border-radius:inherit;
  background:radial-gradient(ellipse 105% 58% at 13% -5%,rgba(255,251,225,.36),transparent 58%),
    linear-gradient(133deg,rgba(218,255,237,.21) 0%,rgba(96,201,191,.09) 30%,rgba(2,20,22,.10) 53%,rgba(2,19,24,.47) 100%);
  box-shadow:inset 1px 2px 0 rgba(255,255,255,.48),inset -1px -2px 0 rgba(124,209,184,.30);
  -webkit-backdrop-filter:blur(2.3px) saturate(1.16);
  backdrop-filter:blur(2.3px) saturate(1.16);
  transition:background-color .3s ease,box-shadow .3s ease,opacity .3s ease;
}
/* z-index on an existing flex item does not modify its positioning or size. */
body .topic-card>.topic-name,
body .topic-card>.topic-meta,
body .topic-card>.topic-label{z-index:2}
/* Larger existing information cards: glass depth without vertical movement. */
body #content .detail-card{
  background:linear-gradient(155deg,rgba(72,147,113,.36),rgba(5,39,32,.65) 62%,rgba(5,24,28,.71))!important;
  -webkit-backdrop-filter:blur(12px) saturate(1.16);
  backdrop-filter:blur(12px) saturate(1.16);
  border-color:rgba(238,219,158,.67);
  box-shadow:inset 1px 1px 0 rgba(255,250,224,.30),inset -1px -1px 0 rgba(111,206,178,.21),
    0 16px 34px rgba(0,13,19,.33),0 0 22px rgba(224,195,111,.17);
}
@media(hover:hover) and (pointer:fine){
  body .topic-card:is(:hover,:focus-visible,:focus-within){
    animation-play-state:paused;rotate:y -2deg;
    outline-color:rgba(255,244,209,.90);
    box-shadow:inset 1px 1px 0 rgba(255,255,255,.76),inset -1px -1px 0 rgba(168,236,215,.37),
      0 15px 27px rgba(0,9,15,.39),0 25px 42px rgba(0,9,12,.36),0 0 27px rgba(244,204,105,.54);
  }
  body .topic-card:is(:hover,:focus-visible,:focus-within)::after{
    background-color:rgba(237,248,224,.08);
    box-shadow:inset 1px 2px 0 rgba(255,255,255,.66),inset -1px -2px 0 rgba(171,239,211,.35);
  }
}
/* Preserve the existing Pause Motion button and reduced-motion preferences. */
.motion-paused .topic-card{animation-play-state:paused!important}
@media(max-width:700px){
  body .topic-card{-webkit-backdrop-filter:blur(3px);backdrop-filter:blur(3px);animation-duration:11s}
  body .topic-card::after{-webkit-backdrop-filter:blur(1.3px);backdrop-filter:blur(1.3px)}
  @keyframes zm-card-microfloat-20261018{0%,100%{translate:0 0}50%{translate:0 -2px}}
}
@media(prefers-reduced-motion:reduce){
  body .topic-card{animation:none!important;translate:none!important;rotate:none!important}
  body .topic-card::after{transition:none!important}
}
</style>
'''
def digest(b):return hashlib.sha256(b).hexdigest()
def folder(run):
    if not re.fullmatch(r'[0-9]{1,20}',run):raise RuntimeError('Invalid run ID')
    return BACKUP/run
def guard():
    if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':raise RuntimeError('Wrong hosting user')
    if not HOME.is_file() or HOME.is_symlink() or HOME.parent.is_symlink() or BACKUP.is_symlink():
        raise RuntimeError('Unsafe homepage/backup path')
def change(original):
    source=original.decode('utf-8')
    if 'id="'+STYLE_ID+'"' in source:raise RuntimeError('Glass style already installed')
    if len(original)<1500000 or source.count('</head>')!=1 or source.count('</body>')!=1:
        raise RuntimeError('Unexpected homepage')
    for k in ('id="zm-fixed-scientific-background-20261018"','id="solar-stage"',
              'id="orbital-cards"','id="site-footer"','ZOMOROD_ORBIT_DATA',
              '.card-track','.topic-card','.topic-card.is-featured','class="header-orbit wrap"'):
        if k not in source:raise RuntimeError('Missing required original feature: '+k)
    result=source.replace('</head>',STYLE+'</head>',1).encode('utf-8')
    if result.replace(STYLE.encode('utf-8'),b'',1)!=original:raise RuntimeError('Unrelated data changed')
    return result
def atomic(path,payload,mode):
    temp=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.zm-glass-',delete=False) as f:
            temp=Path(f.name);f.write(payload);f.flush();os.fsync(f.fileno())
        os.chmod(temp,mode);os.replace(temp,path)
    finally:
        if temp is not None and temp.exists():temp.unlink()
def selftest():
    sample=('<html><head></head><body><nav class="header-orbit wrap"></nav>'
            '<div id="solar-stage"></div><div id="orbital-cards"></div>'
            '<main id="content"><style>.card-track{}.topic-card{}.topic-card.is-featured{}</style></main>'
            '<footer id="site-footer"></footer><script>ZOMOROD_ORBIT_DATA</script>'
            '<style id="zm-fixed-scientific-background-20261018"></style></body></html>'+
            'X'*1600000).encode()
    assert change(sample).replace(STYLE.encode(),b'',1)==sample
    assert all(x not in STYLE for x in ('.card-track{','.orbit-shelf{','flex-basis:','grid-template-columns:','transform:scale('))
    assert all(x in STYLE for x in ('::after','backdrop-filter','microfloat','motion-paused','prefers-reduced-motion'))
    print('GLASS_CARDS_SELFTEST_PASSED=yes',flush=True)
def apply(run,expected):
    guard()
    if not re.fullmatch(r'[a-f0-9]{64}',expected):raise RuntimeError('Invalid baseline SHA')
    before=HOME.read_bytes()
    if digest(before)!=expected:raise RuntimeError('Concurrent homepage update; not overwriting')
    after=change(before)
    d=folder(run)
    if d.exists() or d.is_symlink():raise RuntimeError('Backup directory exists')
    d.mkdir(parents=True,mode=0o700)
    mode=HOME.stat().st_mode&0o777
    atomic(d/'index.before.html',before,0o600)
    if digest((d/'index.before.html').read_bytes())!=expected:raise RuntimeError('Backup invalid')
    manifest={'before':expected,'after':digest(after),'mode':mode}
    (d/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    if digest(HOME.read_bytes())!=expected:raise RuntimeError('Concurrent modification')
    atomic(HOME,after,mode)
    if digest(HOME.read_bytes())!=manifest['after']:raise RuntimeError('Post-write hash mismatch')
    print('GLASS_CARDS_PUBLISHED=yes',flush=True)
    print('GLASS_CARDS_PUBLISHED_SHA='+manifest['after'],flush=True)
def verify(run):
    guard();d=folder(run);m=json.loads((d/'manifest.json').read_text())
    before=(d/'index.before.html').read_bytes();now=HOME.read_bytes()
    assert digest(before)==m['before'] and digest(now)==m['after']
    assert now.replace(STYLE.encode(),b'',1)==before
    assert b'id="zm-fixed-scientific-background-20261018"' in now
    print('ONLY_GLASS_CARDS_CSS_CHANGED=yes',flush=True)
def rollback(run):
    guard();d=folder(run)
    if not (d/'manifest.json').is_file():
        print('NO_INSTALL_TO_RESTORE=yes',flush=True);return
    m=json.loads((d/'manifest.json').read_text())
    before=(d/'index.before.html').read_bytes()
    if digest(before)!=m['before']:raise RuntimeError('Backup corrupt')
    current=digest(HOME.read_bytes())
    if current==m['before']:
        print('ORIGINAL_UNCHANGED=yes',flush=True);return
    if current!=m['after']:raise RuntimeError('Concurrent homepage edit; unsafe rollback')
    atomic(HOME,before,m['mode'])
    assert digest(HOME.read_bytes())==m['before']
    print('ORIGINAL_ROOT_PAGE_RESTORED=yes',flush=True)
if __name__=='__main__':
    if sys.argv[1:]==['selftest']:selftest()
    elif len(sys.argv)==4 and sys.argv[1]=='apply':apply(sys.argv[2],sys.argv[3])
    elif len(sys.argv)==3 and sys.argv[1]=='verify':verify(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=='rollback':rollback(sys.argv[2])
    else:raise SystemExit('selftest | apply RUN_ID SHA256 | verify RUN_ID | rollback RUN_ID')
