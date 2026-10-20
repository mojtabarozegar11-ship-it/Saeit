#!/usr/bin/env python3
"""Bounded MojPlayWin product buy CTA, metadata and account-signin template correction.
No modification to shared app code, payment/DB settings, root routing or sibling sites.
"""
import hashlib,json,os,re,stat,sys,tempfile
from pathlib import Path
ROOT=Path('/home/zomorod2')
APP=ROOT/'Saeit-staging'
SITE=ROOT/'mojplaywin.com'
FILES={
 'product':APP/'core/templates/brands/mojplaywin/product.html',
 'brandbase':APP/'core/templates/brands/mojplaywin/base.html',
 'login':APP/'mpw_commerce/templates/mpw_commerce/customer_login.html',
}
OLD_PRODUCT='<p>Live payment methods appear only after provider and market controls are configured.</p><a class="primary" href="/crypto-payments/">Payment options</a>'
NEW_PRODUCT='''{% if product.pk == 72 or product.pk == 225 %}
<p>Sign in to receive an order-specific secure invoice for this verified digital book. Private delivery is granted only after independently confirmed payment.</p>
<a class="primary" href="/store/product/{{ product.pk }}/checkout/">Secure checkout for this book</a>
<a href="/accounts/register/">New customer? Create an account</a>
{% else %}<p>Contact MojPlayWin to confirm purchasing and delivery availability for this product.</p><a href="/contact/">Enquire about this product</a>{% endif %}'''
OLD_LOGIN='{% csrf_token %}{{ form.as_p }}'
NEW_LOGIN='''{% csrf_token %}
{% if form.non_field_errors %}<div role="alert">{{ form.non_field_errors }}</div>{% endif %}
<label for="{{ form.username.id_for_label }}">Username</label>{{ form.username }}{{ form.username.errors }}
<label for="{{ form.password.id_for_label }}">Password</label>{{ form.password }}{{ form.password.errors }}
{% if next %}<input type="hidden" name="next" value="{{ next }}">{% endif %}'''
OLD_OG_TITLE='<meta property="og:title" content="MojPlayWin | Virtual Products, Games & Digital Innovation">'
NEW_OG_TITLE='<meta property="og:title" content="{% if product and product.title %}{{ product.title }} | MojPlayWin{% else %}MojPlayWin | Virtual Products, Games &amp; Digital Innovation{% endif %}">'
OLD_OG_DESC='<meta property="og:description" content="Explore original games, virtual products, software, AI tools and digital experiences. Learn about Web3 and available digital commerce services.">'
NEW_OG_DESC='<meta property="og:description" content="{% if product and product.metadata.summary %}{{ product.metadata.summary|striptags|truncatechars:155 }}{% else %}Explore original games, virtual products, software, AI tools and digital experiences. Learn about Web3 and available digital commerce services.{% endif %}">'
def fail(reason):raise RuntimeError(reason)
def sha(b):return hashlib.sha256(b).hexdigest()
def guard():
    if APP.is_symlink() or SITE.is_symlink() or SITE.resolve()!=SITE or not (SITE/'passenger_wsgi.py').is_file():fail('Unverified MojPlayWin app identity')
    wsgi=(SITE/'passenger_wsgi.py').read_text('utf8','replace')
    if "APP='/home/zomorod2/Saeit-staging'" not in wsgi:fail('Main Passenger app identity drifted')
    for p in FILES.values():
        if not p.is_file() or p.is_symlink() or p.parent.is_symlink():fail('Unsafe tenant template target')
def transform(name,original):
    text=original.decode('utf8')
    if name=='product':
        if text.count(OLD_PRODUCT)!=1 or 'Secure checkout for this book' in text:fail('Product template unknown or modified')
        updated=text.replace(OLD_PRODUCT,NEW_PRODUCT,1)
    elif name=='login':
        if text.count(OLD_LOGIN)!=1 or '<label for="{{ form.username.id_for_label }}">' in text:fail('Login form template drifted')
        updated=text.replace(OLD_LOGIN,NEW_LOGIN,1)
    elif name=='brandbase':
        if text.count(OLD_OG_TITLE)!=1 or text.count(OLD_OG_DESC)!=1:fail('Brand metadata drifted')
        updated=text.replace(OLD_OG_TITLE,NEW_OG_TITLE,1).replace(OLD_OG_DESC,NEW_OG_DESC,1)
    else:fail('Unknown template')
    if updated==text:fail('Empty patch')
    if any(x in updated for x in ('{% autoescape off %}','javascript:','onerror=')):fail('Unsafe template pattern')
    return updated.encode('utf8')
def atomic(path,payload):
    mode=stat.S_IMODE(path.stat().st_mode)
    fd,tmp=tempfile.mkstemp(prefix='.mpw-safe-buyer-',dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def state_dir(run):
    if not re.fullmatch('[0-9]{8,20}',run):fail('Invalid run')
    return ROOT/('.mpw-buyercopy-'+run)
def validate_template_syntax(content):
    os.chdir(APP);sys.path.insert(0,str(APP));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
    import django;django.setup()
    from django.template import Template
    for b in content.values():Template(b.decode('utf8'))
def publish(run):
    guard()
    original={k:p.read_bytes() for k,p in FILES.items()}
    updated={k:transform(k,b) for k,b in original.items()}
    validate_template_syntax(updated)
    state=state_dir(run)
    if state.exists() or state.is_symlink():fail('Existing backup directory')
    state.mkdir(mode=0o700)
    records={}
    for k,old in original.items():
        records[k]={'path':str(FILES[k]),'before':sha(old),'after':sha(updated[k])}
        dest=state/(k+'.bak')
        with dest.open('xb') as f:os.fchmod(f.fileno(),0o600);f.write(old);f.flush();os.fsync(f.fileno())
    with (state/'manifest.json').open('x') as f:
        os.fchmod(f.fileno(),0o600);json.dump({'run':run,'files':records},f,sort_keys=True)
        f.flush();os.fsync(f.fileno())
    changed=[]
    try:
        for k,p in FILES.items():
            if sha(p.read_bytes())!=records[k]['before']:fail('Concurrent template edit '+k)
            atomic(p,updated[k]);changed.append(k)
            if sha(p.read_bytes())!=records[k]['after']:fail('Postwrite mismatch '+k)
    except BaseException:
        for k in reversed(changed):
            if sha(FILES[k].read_bytes())==records[k]['after']:atomic(FILES[k],original[k])
        raise
    print('MPW_BUYER_TEMPLATE_PATCH='+json.dumps({'run':run,'files':list(FILES),'main_only':True,'money_created':False,'shared_settings_untouched':True}))
def rollback(run):
    guard()
    d=state_dir(run)
    if not d.is_dir() or d.is_symlink():fail('Backup unavailable')
    doc=json.loads((d/'manifest.json').read_text('utf8'))
    if doc.get('run')!=run:fail('Wrong owner')
    backups={}
    for k,path in FILES.items():
        b=d/(k+'.bak');metadata=doc['files'][k]
        if b.is_symlink() or not b.is_file() or sha(b.read_bytes())!=metadata['before']:fail('Invalid backup')
        if str(path)!=metadata['path'] or sha(path.read_bytes())!=metadata['after']:fail('Concurrent edit; rollback denied')
        backups[k]=b.read_bytes()
    for k,path in FILES.items():atomic(path,backups[k])
    if any(sha(FILES[k].read_bytes())!=sha(x) for k,x in backups.items()):fail('Restore mismatch')
    print('MPW_BUYER_TEMPLATE_ROLLBACK=PASS')
def selftest():
    tests={
        'product':(OLD_PRODUCT+' hello').encode(),
        'login':('<form>'+OLD_LOGIN+'</form>').encode(),
        'brandbase':(OLD_OG_TITLE+OLD_OG_DESC).encode(),
    }
    for k,b in tests.items():
        result=transform(k,b)
        assert result!=b
        assert (b'secure invoice' in result) if k=='product' else len(result)>len(b)
    print('MPW_BUYER_TEMPLATE_BOUNDED_SELFTEST=PASS')
if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest':selftest()
    elif len(sys.argv)==3 and sys.argv[1] in ('publish','rollback'):(publish if sys.argv[1]=='publish' else rollback)(sys.argv[2])
    else:raise SystemExit('selftest|publish RUN_ID|rollback RUN_ID')
