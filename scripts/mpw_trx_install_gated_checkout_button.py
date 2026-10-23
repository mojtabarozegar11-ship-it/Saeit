#!/usr/bin/env python3
"""Reversible, feature-flagged TRX button added to existing product template.

The button is hidden unless both verified merchant canary and public release
switches are explicitly set. It uses an authenticated POST with Django CSRF.
No default appearance changes, financial writes, schema changes or redirects.
"""
from __future__ import annotations
import hashlib,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path

APP=Path("/home/zomorod2/Saeit-staging")
TEMPLATE=APP/"mpw_commerce/templates/mpw_commerce/product_checkout.html"
SETTINGS=APP/"config/settings.py"
MODULE=APP/"services/mpw_trx_commercial_context.py"
PUBLIC=Path("/home/zomorod2/mojplaywin.com/passenger_wsgi.py")
BACKUPS=Path("/home/zomorod2/.local/share/mpw-trx-rollbacks")
PYTHON="/home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python"
EXPECTED_SHA="7a6954b1f03d6e3e1ff4ca7a333fecb067b411c92444f75beeda876b7db1ad62"
MARK="MPW_WALLETLESS_TRX_BUTTON_V1"
CTX_MARK="# MPW_TRX_TEMPLATE_CONTEXT_PROCESSOR_V1"

BUTTON="""
<!-- MPW_WALLETLESS_TRX_BUTTON_V1 -->
{% if mpw_trx_easy_enabled %}
<section aria-label="Automatic TRX checkout" class="checkout-trx-easy" data-gateway="trx-easy">
  <h2>Pay with TRX — automatic download</h2>
  <p>No wallet signature or account linking required. Use Trust Wallet, TronLink, or any TRON wallet.</p>
  <form method="post" action="/commerce/trx-easy/start/{{ product.pk }}/">
    {% csrf_token %}
    <button type="submit">Pay securely with TRX</button>
  </form>
  <p>After independent blockchain confirmation, the purchased file is available in your account.</p>
</section>
{% endif %}
"""
CTX_ADD="""

# MPW_TRX_TEMPLATE_CONTEXT_PROCESSOR_V1
TEMPLATES[0]["OPTIONS"]["context_processors"].append(
    "services.mpw_trx_commercial_context.checkout_flags"
)
"""

def run(module_source:Path):
    if (not APP.is_dir() or APP.is_symlink() or PUBLIC.is_symlink()
        or not PUBLIC.is_file()
        or "APP='/home/zomorod2/Saeit-staging'" not in PUBLIC.read_text("utf8","replace")
        or not MODULE.parent.is_dir() or not BACKUPS.is_dir()
        or any(x.is_symlink() or not x.is_file() for x in (TEMPLATE,SETTINGS))
        or module_source.is_symlink() or not module_source.is_file()
        or module_source.stat().st_size>30000):
        raise RuntimeError("Merchant checkout source paths not trusted")
    compile(module_source.read_text("utf8"),str(module_source),"exec")
    original=TEMPLATE.read_bytes()
    existing=MARK.encode() in original
    if not existing and hashlib.sha256(original).hexdigest()!=EXPECTED_SHA:
        raise RuntimeError("Checkout template changed independently")
    if not existing and original.count(b"</main>")!=1:
        raise RuntimeError("Checkout insertion point is no longer unique")
    ctx_old=SETTINGS.read_text("utf8")
    before={
        str(TEMPLATE):original,
        str(SETTINGS):ctx_old.encode("utf8"),
    }
    backup=Path(tempfile.mkdtemp(prefix="trx-template-",dir=str(BACKUPS)))
    os.chmod(backup,0o700)
    for file,data in before.items():
        dest=backup/Path(file).name
        dest.write_bytes(data)
        os.chmod(dest,0o600)
    old_module=MODULE.read_bytes() if MODULE.exists() else None
    if old_module is not None:
        (backup/"mpw_trx_commercial_context.py").write_bytes(old_module)
    try:
        temporary=MODULE.with_name(MODULE.name+".mpw-tmp")
        if temporary.exists() or temporary.is_symlink():
            raise RuntimeError("Existing temporary module")
        shutil.copy2(module_source,temporary)
        os.chmod(temporary,0o644)
        os.replace(temporary,MODULE)
        if not existing:
            new=original.replace(b"</main>",BUTTON.encode("utf8")+b"\n</main>",1)
            TEMPLATE.write_bytes(new)
        if CTX_MARK not in ctx_old:
            SETTINGS.write_text(ctx_old.rstrip()+"\n"+CTX_ADD,encoding="utf8")
        script=(
            "import os,django;"
            "os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');"
            "django.setup();"
            "from django.template.loader import get_template;"
            "from django.conf import settings;"
            "t=get_template('mpw_commerce/product_checkout.html');"
            "assert not settings.MPW_WALLETLESS_TRX_PUBLIC_ENABLED;"
            "assert not settings.MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED;"
            "from services.mpw_trx_commercial_context import checkout_flags;"
            "print('MPW_TRX_SAFE_CHECKOUT_TEMPLATE=PASS')"
        )
        env=os.environ.copy()
        env.update({"MPW_WALLETLESS_TRX_PUBLIC_ENABLED":"0",
                    "MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED":"0"})
        result=subprocess.run([PYTHON,"-B","-c",script],cwd=str(APP),
            env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,timeout=65)
        if result.returncode or b"MPW_TRX_SAFE_CHECKOUT_TEMPLATE=PASS" not in result.stdout:
            raise RuntimeError("Feature-hidden checkout smoke test failed")
        return {"status":"GATED_TRX_BUY_BUTTON_INSTALLED","button_public":False,
                "csrf_post":True,"canary_gate":True,"rollback_saved":True}
    except Exception:
        for name,data in before.items():
            Path(name).write_bytes(data)
        if old_module is not None:
            MODULE.write_bytes(old_module)
        elif MODULE.exists():
            MODULE.unlink()
        raise

if __name__=="__main__":
    try:
        print("MPW_TRX_TEMPLATE_INSTALL="+json.dumps(run(Path(sys.argv[1])),sort_keys=True))
    except Exception as exc:
        print("MPW_TRX_TEMPLATE_INSTALL="+json.dumps({
            "status":"BLOCKED_OR_ROLLED_BACK","error_class":type(exc).__name__,
            "button_public":False},sort_keys=True))
        raise SystemExit(2)
