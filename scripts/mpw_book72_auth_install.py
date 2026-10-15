"""Fail-closed MojPlayWin-only deployment of customer auth and rate/RPC helpers.

Read new code from a pinned GitHub Actions source archive, never from the public site.
No payment settings or product activation are modified.
"""
import ast
import os
from pathlib import Path
import tarfile
import tempfile

ROOT=Path("/home/zomorod2/Saeit-staging")
NEW=(
    "mpw_commerce/customer_auth.py",
    "mpw_commerce/templates/mpw_commerce/customer_login.html",
    "mpw_commerce/templates/mpw_commerce/customer_register.html",
    "scripts/mojplaywin_direct_wallet_invoice.py",
    "scripts/mojplaywin_direct_wallet_rates.py",
    "scripts/mojplaywin_direct_wallet_discovery.py",
    "scripts/mojplaywin_native_rpc_clients.py",
)
REPLACE=(
    "mpw_commerce/product_checkout_page.py",
    "mpw_commerce/templates/mpw_commerce/product_checkout.html",
)
BASE_PREFIX="_baseline/"
ROUTE_FILE=ROOT/"mpw_commerce/urls.py"
ADDITION=(
    "\n# MojPlayWin customer access; checks host/TLS in every view.\n"
    "from .customer_auth import CustomerLogin, CustomerLogout, customer_register\n"
    "urlpatterns += [\n"
    '    path("accounts/login/", CustomerLogin.as_view(), name="customer_login"),\n'
    '    path("accounts/register/", customer_register, name="customer_register"),\n'
    '    path("accounts/logout/", CustomerLogout.as_view(), name="customer_logout"),\n'
    "]\n"
)


def replace_bytes(path,content):
    descriptor, temp_path=tempfile.mkstemp(prefix=".mpw-auth-",dir=str(path.parent))
    try:
        with os.fdopen(descriptor,"wb") as dest:
            dest.write(content)
            dest.flush()
            os.fsync(dest.fileno())
        os.chmod(temp_path,0o644)
        os.replace(temp_path,path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def install(archive_path, backup_directory):
    if ROOT.is_symlink() or not ROOT.is_dir() or ROUTE_FILE.is_symlink() or not ROUTE_FILE.is_file():
        raise RuntimeError("Expected authorized MojPlayWin codebase unavailable")
    archive_path=Path(archive_path)
    backup_directory=Path(backup_directory)
    if archive_path.is_symlink() or not archive_path.is_file() or backup_directory.is_symlink():
        raise RuntimeError("Unsafe install workspace")
    expected=set(NEW+REPLACE+tuple(BASE_PREFIX+n for n in REPLACE))
    with tarfile.open(archive_path,"r:gz") as bundle:
        members=bundle.getmembers()
        if set(m.name for m in members)!=expected or len(members)!=len(expected):
            raise RuntimeError("Unexpected installation archive")
        if any(not m.isfile() or m.size>200000 for m in members):
            raise RuntimeError("Untrusted archive member")
        data={m.name:bundle.extractfile(m).read() for m in members}
    for name in NEW+REPLACE:
        if name.endswith(".py"):
            ast.parse(data[name].decode("utf-8"),filename=name)

    url_before=ROUTE_FILE.read_bytes()
    if b'commerce/book/<int:product_id>/' not in url_before or b'commerce/my-purchases/' not in url_before:
        raise RuntimeError("Existing protected book paths must remain")
    if b'accounts/login/' in url_before or b'accounts/register/' in url_before:
        raise RuntimeError("Auth routes already exist: refuse incompatible patch")
    urls_after=url_before+ADDITION.encode("utf-8")
    ast.parse(urls_after.decode("utf-8"),filename=str(ROUTE_FILE))
    changed={}
    for name in NEW+REPLACE:
        target=ROOT/name
        if target.is_symlink() or not target.parent.is_dir() or target.parent.is_symlink():
            raise RuntimeError("Unsafe output path")
        previous=target.read_bytes() if target.is_file() else None
        if name in REPLACE:
            if previous not in (data[BASE_PREFIX+name],data[name]):
                raise RuntimeError("Live module drift: "+name)
        elif previous not in (None,data[name]):
            raise RuntimeError("Existing add-on differs: "+name)
        if previous!=data[name]:
            changed[name]=previous
    backup_directory.mkdir(mode=0o700,exist_ok=False)
    os.chmod(backup_directory,0o700)
    # Preserve full prior URLs and all replacements before touching any code.
    for name, prior in (("urls.py",url_before),)+tuple((n,p) for n,p in changed.items() if p is not None):
        safe_name=name.replace("/","__")
        dest=backup_directory/safe_name
        with dest.open("xb") as stream:
            stream.write(prior)
        os.chmod(dest,0o600)
    installed=[]
    try:
        for name,prior in changed.items():
            target=ROOT/name
            replace_bytes(target,data[name])
            installed.append((target,prior))
        replace_bytes(ROUTE_FILE,urls_after)
        import django
        django.setup()
        from django.urls import resolve,clear_url_caches
        clear_url_caches()
        checks=(("/accounts/login/","mpw_commerce:customer_login"),
                ("/accounts/register/","mpw_commerce:customer_register"),
                ("/commerce/book/72/","mpw_commerce:book"),
                ("/commerce/my-purchases/","mpw_commerce:purchases"))
        for url,expect in checks:
            if resolve(url).view_name!=expect:
                raise RuntimeError("Unexpected new route: "+url)
        print("MPW_AUTH_SIGNIN_REGISTER_INSTALLED=YES")
        print("MPW_BOOK72_DISCOUNT_DISPLAY_CODE_INSTALLED=YES")
        print("MPW_RATE_AND_RPC_HELPERS_INSTALLED=YES")
        print("MPW_PAYMENT_SWITCHES_UNTOUCHED=YES")
        print("MPW_AUTH_ROLLBACK_SAVED=YES")
    except BaseException:
        replace_bytes(ROUTE_FILE,url_before)
        for target,prior in reversed(installed):
            if prior is None:
                target.unlink(missing_ok=True)
            else:
                replace_bytes(target,prior)
        print("MPW_AUTH_INSTALL_ROLLED_BACK=YES")
        raise


if __name__=="__main__":
    import sys
    if len(sys.argv)!=3:
        raise SystemExit("Expected archive and backup folder")
    install(sys.argv[1],sys.argv[2])
