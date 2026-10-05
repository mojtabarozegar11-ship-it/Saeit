import hashlib, io, os, re, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PRODUCT_FILES=('index.html','style.css','calc.js','app.js','GUIDE.html','LICENSE.txt')
TERMS_VERSION='costkit-1.0-20261005'

def package():
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for n in PRODUCT_FILES:
            info=zipfile.ZipInfo(n,date_time=(2026,10,5,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,(ROOT/'product'/n).read_bytes())
    return out.getvalue()

def artifact_hash(): return hashlib.sha256(package()).hexdigest()

def archive_package():
    content=package();digest=hashlib.sha256(content).hexdigest()
    folder=data_path().parent/'artifacts';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    target=folder/(digest+'.zip')
    try:
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:f.write(content)
    except FileExistsError:
        if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raise ValueError('artifact_corrupted')
    return digest

def archived(digest):
    if not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('artifact_hash')
    content=(data_path().parent/'artifacts'/(digest+'.zip')).read_bytes()
    if hashlib.sha256(content).hexdigest()!=digest:raise ValueError('artifact_corrupted')
    return content
def price():
    try:
        p=int(os.getenv('ZM_COSTKIT_PRICE_IRR','1490000'))
        return p if 10000<=p<=1000000000 and p%10==0 else 0
    except ValueError: return 0

def readiness():
    from django.conf import settings
    missing=[]
    checks={
      'ZARINPAL_MERCHANT_ID':bool(re.fullmatch(r'[A-Fa-f0-9-]{36}',os.getenv('ZARINPAL_MERCHANT_ID',''))),
      'SECRET_KEY':len(settings.SECRET_KEY)>=40 and settings.SECRET_KEY not in ('change-me','change-me-before-production'),
      'ZM_COSTKIT_SELLER':bool(os.getenv('ZM_COSTKIT_SELLER','').strip()),
      'ZM_COSTKIT_SUPPORT_EMAIL':bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',os.getenv('ZM_COSTKIT_SUPPORT_EMAIL',''))),
      'ZM_COSTKIT_TERMS_APPROVED':os.getenv('ZM_COSTKIT_TERMS_APPROVED')==TERMS_VERSION,
      'ZM_COSTKIT_RELEASE_SHA256':os.getenv('ZM_COSTKIT_RELEASE_SHA256')==artifact_hash(),
      'ZM_COSTKIT_PRICE_IRR':price()>0,
      'ZM_COSTKIT_APPROVED_PRICE_IRR':os.getenv('ZM_COSTKIT_APPROVED_PRICE_IRR')==str(price()),
      'ZM_COSTKIT_LIVE':os.getenv('ZM_COSTKIT_LIVE')=='1',
      'production_gateway':os.getenv('ZARINPAL_SANDBOX','0')=='0',
      'secure_sessions':settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE and not settings.DEBUG,
    }
    return [k for k,v in checks.items() if not v]

def data_path():
    from django.conf import settings
    return Path(os.getenv('ZM_COSTKIT_DATA_DIR',str(settings.BASE_DIR/'var/moj/costkit')))/'orders.sqlite3'
