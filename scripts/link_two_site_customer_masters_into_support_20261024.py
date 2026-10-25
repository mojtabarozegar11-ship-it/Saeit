#!/usr/bin/env python3
"""Guarded minimal customer entry links for two deployed site master portals.

Modify only the static Zomorod /contact/ page and the independent MojPlayWin
support.html template. Never edit the shared MPW shell, checkout, orders or cron.
Both original byte hashes are pinned; reject concurrent edits.
"""
from __future__ import annotations
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import time

HOME = Path("/home/zomorod2")
BACKUPS = HOME / ".private_mojplaywin_main_agents"
TARGETS = {
    "zomorod": (
        HOME / "public_html/contact/index.html",
        "9361c329df7cea36e604db137b39cddbcf5e6971f2d9dbc843ca4ddad898b22c",
        "https://zomorodmelal.ir/contact/"),
    "mojplaywin": (
        HOME / "mojplaywin.com/design-preview-20261017/_mpw_dynamic_main_shell_20261019.php",
        "0cc05393516e62d4bd263fbc3a121acf84ad912672edd800f06fefd634e325db",
        "https://mojplaywin.com/support/"),
}
ZM_ELEMENT = """
<section class="zm-master-customer-entry-20261024" aria-label="پشتیبانی مشتریان" style="margin:28px auto;padding:22px;max-width:980px;border:1px solid #a99562;border-radius:16px;background:#143d2e;color:#fdf6e4">
 <h2 style="margin-top:0;color:#f3d68a">پرسش، راهنمایی و پیگیری سفارش</h2>
 <p>پرسش خود را ثبت کنید و با شناسه پیگیری، وضعیت درخواست را مشاهده کنید.</p>
 <p style="display:flex;gap:12px;flex-wrap:wrap">
  <a href="/ask-master/index.php" style="display:inline-block;padding:10px 18px;border-radius:8px;background:#e8c77e;color:#172a21;font-weight:700;text-decoration:none">ثبت پرسش یا پیگیری سفارش</a>
  <a href="/ask-master/status.php" style="display:inline-block;padding:10px 18px;border:1px solid #e8c77e;border-radius:8px;color:#fff1c3;text-decoration:none">مشاهده وضعیت درخواست</a>
 </p>
</section>
""".strip()
MPW_ELEMENT = """
// MPW_MASTER_SUPPORT_NAV_20261024_BEGIN
// Agent entry affects only the existing GET /support/ page, never store or checkout.
if ($slug === 'support' &&
    strpos($rendered, 'id="mpw-master-support-entry-20261024"') === false &&
    strpos($rendered, 'Need a direct channel?') !== false &&
    substr_count($rendered, '</main>') === 1) {
    $masterSupportCard = <<<'MPW_MASTER_SUPPORT_CARD'
<section id="mpw-master-support-entry-20261024" aria-label="Customer questions and orders" style="margin:22px auto;padding:22px;border:1px solid #449f9b;border-radius:17px;background:#102c37;color:#e6f8fa">
 <h2 style="color:#ffe3a7">Ask the MojPlayWin site master</h2>
 <p>Questions, downloads and order-help requests: submit securely and track the result with your ticket ID.</p>
 <p><a href="/ask-master/index.php" style="display:inline-block;padding:12px 18px;border-radius:8px;background:#f7d18b;color:#163039;font-weight:800;text-decoration:none">Ask a question or request order help</a></p>
 <p><a href="/ask-master/status.php" style="color:#9bfce2">Track a support request</a></p>
</section>
MPW_MASTER_SUPPORT_CARD;
    $rendered = str_replace('</main>', "\\n" . $masterSupportCard . "\\n</main>", $rendered);
}
// MPW_MASTER_SUPPORT_NAV_20261024_END

""".rstrip()
ZM_MARKER = "zm-master-customer-entry-20261024"
MPW_MARKER = 'href="/ask-master/index.php"'

def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def require(flag, reason):
    if not flag:
        raise RuntimeError(reason)

def change(site: str, original: bytes) -> bytes:
    html = original.decode("utf-8")
    if site == "zomorod":
        require(ZM_MARKER not in html and html.lower().count("</main>")==1, "ZM_MAIN_NOT_UNIQUE")
        pos = re.search(r"</main>", html, flags=re.I)
        require(pos is not None, "ZM_MAIN_MISSING")
        output = html[:pos.start()] + ZM_ELEMENT + "\n" + html[pos.start():]
    elif site == "mojplaywin":
        hook_marker = "// MPW_MASTER_SUPPORT_NAV_20261024_BEGIN"
        needle = "\necho $rendered;"
        require(hook_marker not in html and html.count(needle)==1, "MPW_SHARED_SHELL_ENTRY_NOT_UNIQUE")
        require(html.strip().endswith("echo $rendered;"), "MPW_SHARED_SHELL_UNEXPECTED_TAIL")
        require("$slug=$_GET['__mpw_template_route']??null;" in html, "MPW_SUPPORT_ROUTE_GUARD_MISSING")
        pos=html.find(needle)
        output=html[:pos]+"\n"+MPW_ELEMENT+html[pos:]
    else:
        raise ValueError("UNKNOWN_TENANT")
    require(len(output)>len(html) and len(output)-len(html)<3600, "UNEXPECTED_CHANGE_SIZE")
    require(output.count('href="/ask-master/index.php"')>=1 and
            output.count('href="/ask-master/status.php"')>=1, "MISSING_SUPPORT_LINK")
    return output.encode("utf-8")

def run(args, timeout=18):
    return subprocess.run(args,capture_output=True,text=True,timeout=timeout,check=False)

def write_new(path: Path, content: bytes, mode: int):
    flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(str(path),flags,mode)
    with os.fdopen(fd,"wb") as out:
        out.write(content)
        out.flush()
        os.fsync(out.fileno())
    os.chmod(path,mode)

def verify():
    import urllib.request
    for site,(path,old,url) in TARGETS.items():
        nonce=str(int(time.time()))
        with urllib.request.urlopen(urllib.request.Request(
                url+"?agent_customer_link_verify="+nonce,
                headers={"Cache-Control":"no-cache"}),timeout=22) as response:
            html=response.read(160000).decode("utf-8","replace")
            require(response.status==200,"HTTP_ROUTE_FAILED:"+site)
        require('href="/ask-master/index.php"' in html and
                'href="/ask-master/status.php"' in html, "LIVE_SUPPORT_LINK_NOT_VISIBLE:"+site)
        print("CUSTOMER_MASTER_SITE_NAV_VISIBLE="+site+":PASS")
        store=run(["curl","-fsS","--max-time","14","-o","/dev/null",url.split("/contact/")[0].split("/support/")[0]+"/store/"],18)
        require(store.returncode==0,"STORE_SMOKE_FAILED:"+site)

def install():
    require(sys.argv[1:]==["install"],"INSTALL_COMMAND_REQUIRED")
    require(pwd.getpwuid(os.geteuid()).pw_name=="zomorod2" and Path.home()==HOME, "CPANEL_IDENTITY_FAILED")
    require(BACKUPS.is_dir() and not BACKUPS.is_symlink() and BACKUPS.stat().st_mode & 0o007==0,
            "BACKUP_ROOT_UNSAFE")
    lock=BACKUPS/".site_master_customer_nav_upgrade.lock"
    require(not lock.is_symlink(),"SYMLINK_LOCK")
    fd=os.open(str(lock),os.O_CREAT|os.O_RDWR,0o600)
    backup=BACKUPS/("site_master_customer_nav_"+str(int(time.time())))
    stages=[];changed=[]
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        originals={};patched={}
        for site,(path,old,url) in TARGETS.items():
            require(path.is_file() and not path.is_symlink(), "TARGET_MISSING_OR_LINK:"+site)
            data=path.read_bytes()
            require(digest(data)==old,"REFUSE_MODIFIED_PUBLIC_PAGE:"+site)
            originals[site]=data
            patched[site]=change(site,data)
        require(not backup.exists() and not backup.is_symlink(),"BACKUP_COLLISION")
        os.mkdir(backup,0o700)
        for site,(path,old,url) in TARGETS.items():
            write_new(backup/(site+".original"+path.suffix),originals[site],0o600)
        for site,(path,old,url) in TARGETS.items():
            tmp=path.parent/(".master_customer_nav_"+str(os.getpid())+path.suffix)
            require(not tmp.exists() and not tmp.is_symlink(), "TEMP_EXISTS:"+site)
            write_new(tmp,patched[site],0o644)
            stages.append(tmp)
            if site=="mojplaywin":
                require(run(["php","-l",str(tmp)],18).returncode==0,"MPW_PHP_LINT_FAILED")
            require(digest(path.read_bytes())==old,"CONCURRENT_PAGE_EDIT:"+site)
            os.replace(tmp,path)
            changed.append((site,path,patched[site],originals[site]))
            require(digest(path.read_bytes())==digest(patched[site]),"READBACK_FAILED:"+site)
        verify()
        write_new(backup/"receipt.json",json.dumps({"sites":sorted(TARGETS),"scope":"support_entry_links_only",
                  "old_hashes":{k:digest(v) for k,v in originals.items()},
                  "new_hashes":{k:digest(v) for k,v in patched.items()},
                  "payment_changes":0,"master_cron_changes":0},sort_keys=True).encode(),0o600)
        print("TWO_SITE_CUSTOMER_SUPPORT_MASTER_DISCOVERABILITY_LIVE=PASS")
        print("EXISTING_CHECKOUT_OR_PAYMENT_CHANGED=NO")
    except BaseException:
        for site,path,new,old in reversed(changed):
            try:
                if path.is_file() and not path.is_symlink() and digest(path.read_bytes())==digest(new):
                    temp=path.parent/(".master_nav_restore_"+str(os.getpid())+path.suffix)
                    write_new(temp,old,0o644)
                    stages.append(temp)
                    os.replace(temp,path)
                else:
                    print("REQUIRES_MANUAL_RESTORE="+site)
            except Exception:
                print("REQUIRES_MANUAL_RESTORE="+site)
        raise
    finally:
        for tmp in stages:
            try:
                if tmp.is_file() and not tmp.is_symlink():tmp.unlink()
            except OSError:pass
        os.close(fd)

if __name__=="__main__":
    install()
