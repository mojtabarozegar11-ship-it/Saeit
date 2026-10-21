#!/usr/bin/env python3
"""Surgically expose already-enabled Atelier 879 at the actual MojPlayWin PHP storefront.
Never touches .htaccess, database, billing, other sites, or Django templates.
"""
import hashlib,json,os,pwd,shutil,stat,subprocess,sys,tempfile
from pathlib import Path
APP=Path("/home/zomorod2/Saeit-staging")
DOMAIN=Path("/home/zomorod2/mojplaywin.com")
TARGET=DOMAIN/"design-preview-20261017/_mpw_dynamic_main_shell_20261019.php"
SAFE=Path("/home/zomorod2/.private_mojplaywin_digital_products")
BACKUP=SAFE/"atelier-879-actual-php-store-before-cta-20261022.php"
HOOK="echo $rendered;"
PHP_BLOCK=r"""
// ATELIER_879_STOREFRONT_ONLY_20261022_BEGIN
if ($slug === 'store' && strpos($rendered, 'atelier-original-vector-879') === false) {
    $atelier879Needle = '<!-- MPW_TWO_BOOKS_PUBLIC_CATALOG_V1_END -->';
    if (substr_count($rendered, $atelier879Needle) === 1) {
        $atelier879Card = <<<'ATELIER879'
<section class="mpw-two-books" id="atelier-original-vector-879" aria-label="Atelier Interior original digital website kit">
  <article class="mpw-sale-book">
    <div class="mpw-book-cover" aria-hidden="true"><span>ORIGINAL VECTOR EDITION</span><strong>ATELIER INTERIOR</strong></div>
    <div>
      <h3>Atelier Interior — Client-Ready Website Kit</h3>
      <p>Editable responsive interior-design portfolio, gallery, quote inquiry and WhatsApp handoff. Includes HTML/CSS/JavaScript, five original vector SVG interior illustrations, usage guide and a one-site/client license. Demo photographs are NOT included in the download.</p>
      <p class="mpw-book-price">US $6.80</p>
      <p class="mpw-book-cta"><a href="/store/product/879/checkout/">Buy website kit — secure ETH/TRX checkout ↗</a> <a href="/store/product/879/">Product specifications ↗</a></p>
      <p>Register or sign in to receive an order-specific payment invoice. The private ZIP is released only after verified payment. Never transfer TRX without the exact invoice.</p>
    </div>
  </article>
</section>
ATELIER879;
        $rendered = str_replace($atelier879Needle, $atelier879Needle . "\n" . $atelier879Card, $rendered);
    }
}
// ATELIER_879_STOREFRONT_ONLY_20261022_END
"""
def sha(x):return hashlib.sha256(x).hexdigest()
def transformed(before):
    s=before.decode("utf8")
    if s.count(HOOK)!=1 or "ATELIER_879_STOREFRONT_ONLY_20261022_BEGIN" in s:
        raise RuntimeError("PHP_HOOK_MISMATCH_OR_ALREADY_PATCHED")
    return s.replace(HOOK,PHP_BLOCK+"\n"+HOOK,1).encode("utf8")
def check():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":raise RuntimeError("UNTRUSTED_ACTOR")
    for path in (APP,DOMAIN):
        if path.is_symlink() or not path.is_dir():raise RuntimeError("UNTRUSTED_APP_ROOT")
    if not TARGET.is_file() or TARGET.is_symlink() or not TARGET.resolve().is_relative_to(DOMAIN.resolve()):
        raise RuntimeError("WRONG_PHP_TARGET")
    if not SAFE.is_dir() or SAFE.is_symlink() or stat.S_IMODE(SAFE.stat().st_mode)&0o077:
        raise RuntimeError("PRIVATE_BACKUP_LOCATION_UNSAFE")
    if not (APP/"manage.py").is_file():raise RuntimeError("DJANGO_APP_MISSING")
    php=shutil.which("php")
    if not php:raise RuntimeError("PHP_CLI_NOT_INSTALLED")
    return php
def lint(php,path):
    r=subprocess.run([php,"-l",str(path)],capture_output=True,text=True,timeout=20,check=False)
    if r.returncode!=0:raise RuntimeError("PHP_SYNTAX_LINT_FAILED")
def atomic_set(path,data,php):
    current=path.stat()
    fd,name=tempfile.mkstemp(prefix=".atelier-879-",suffix=".php",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as f:
            os.fchmod(f.fileno(),stat.S_IMODE(current.st_mode))
            f.write(data);f.flush();os.fsync(f.fileno())
        lint(php,Path(name))
        if path.is_symlink():raise RuntimeError("PHP_TARGET_BECAME_SYMLINK")
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)
def buyer_gate():
    os.chdir(APP);sys.path.insert(0,str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    os.environ["PYTHONDONTWRITEBYTECODE"]="1"
    import django;django.setup()
    from core.models import Product
    from mpw_commerce.product_checkout_page import approved_for_checkout
    from types import SimpleNamespace
    prod=Product.objects.select_related("knowledge_article").get(pk=879)
    req=SimpleNamespace(is_secure=lambda:True,get_host=lambda:"mojplaywin.com",
          user=SimpleNamespace(is_authenticated=True,is_active=True))
    if prod.product_type!="digital" or str(prod.price)!="6.80" or not approved_for_checkout(req,prod):
        raise RuntimeError("PRODUCT_NOT_CURRENTLY_SELLABLE")
def activate():
    if os.environ.get("ATELIER_OWNER_PHP_STOREFRONT")!="20261022-owner-879":
        raise PermissionError("NOT_OWNER_APPROVED")
    php=check();buyer_gate()
    before=TARGET.read_bytes();after=transformed(before)
    if BACKUP.is_symlink():raise RuntimeError("UNTRUSTED_BACKUP")
    if BACKUP.exists():
        if not BACKUP.is_file() or BACKUP.read_bytes()!=before:raise RuntimeError("BACKUP_CONFLICT")
    else:
        with BACKUP.open("xb") as f:
            os.fchmod(f.fileno(),0o600);f.write(before);f.flush();os.fsync(f.fileno())
    if TARGET.read_bytes()!=before:raise RuntimeError("CONCURRENT_PHP_EDIT")
    atomic_set(TARGET,after,php)
    print("ATELIER_ACTUAL_PHP_STORE_CTA_INSTALLED="+json.dumps({"exact_path":"mojplaywin.com/design-preview-20261017/_mpw_dynamic_main_shell_20261019.php",
       "price_usd":"6.80","product_id":879,"protected_checkout":True,"other_pages_unchanged_by_guard":True,
       "rollback_sha":sha(before)[:18],"new_sha":sha(after)[:18],"real_paid_buyer_tested":False},sort_keys=True))
def rollback():
    if os.environ.get("ATELIER_OWNER_PHP_STOREFRONT_ROLLBACK")!="20261022-owner-879":
        raise PermissionError("ROLLBACK_NOT_OWNER_APPROVED")
    php=check()
    if not BACKUP.is_file() or BACKUP.is_symlink():raise RuntimeError("MISSING_BACKUP")
    before=BACKUP.read_bytes();after=transformed(before);current=TARGET.read_bytes()
    if current==after:atomic_set(TARGET,before,php)
    elif current!=before:raise RuntimeError("CONCURRENT_CHANGE_REFUSE_ROLLBACK")
    print("ATELIER_ACTUAL_PHP_STORE_CTA_ROLLED_BACK=EXACT_PRIOR_BYTES")
if __name__=="__main__":
    arg=sys.argv[1] if len(sys.argv)==2 else ""
    if arg=="activate":activate()
    elif arg=="rollback":rollback()
    elif arg=="selftest":
        sample=b"<?php\n$slug='store';\necho $rendered;"
        assert b"ATELIER_879_STOREFRONT_ONLY_20261022_BEGIN" in transformed(sample)
        assert "ATELIER879;" in PHP_BLOCK and '/store/product/879/checkout/' in PHP_BLOCK
        print("ATELIER_ACTUAL_PHP_STORE_SELFTEST=PASS")
    else:raise SystemExit("selftest|activate|rollback")
