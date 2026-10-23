#!/usr/bin/env python3
"""Forward received supplier replies and permitted original catalogue attachments to account owner's Gmail.

Private sender server only. Never prints correspondence, supplier contact details, or file contents.
Idempotent per original Message-ID; unrelated mail is not forwarded.
"""
from __future__ import annotations
import email
import email.utils
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

SENDER = "moj_1ro_1@zomorodmelal.ir"
OWNER = "mojtaba.rozegar11@gmail.com"
BATCH = "supplier-replies-owner-delivery-20261023"
CUTOFF = datetime(2026, 10, 20, tzinfo=timezone.utc).timestamp()
MAILDIR = Path.home() / "mail" / "zomorodmelal.ir" / "moj_1ro_1"
PRIVATE = Path.home() / ".company-outreach-private"
MAX_REPLIES = 50
MAX_RAW = 19_000_000
MAX_SINGLE_ATTACHMENT = 13_000_000
MAX_TOTAL_ATTACHMENT = 17_000_000

class ToText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks = []
        self.silent = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"): self.silent += 1
        if tag in ("br", "p", "li", "tr", "div"): self.chunks.append("\n")
    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.silent: self.silent -= 1
        if tag in ("p", "li", "tr", "div"): self.chunks.append("\n")
    def handle_data(self, data):
        if not self.silent: self.chunks.append(data)

def message_text(original):
    plain, html = [], []
    for part in original.walk():
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        typ = part.get_content_type()
        if typ not in ("text/plain", "text/html"):
            continue
        try:
            data = part.get_content()
        except (ValueError, LookupError, UnicodeError, AttributeError):
            continue
        if not isinstance(data, str):
            continue
        if typ == "text/plain": plain.append(data)
        else:
            parser = ToText()
            parser.feed(data)
            html.append("".join(parser.chunks))
    text = "\n\n".join(plain) if plain else "\n\n".join(html)
    return text.replace("\x00", "").strip()

def safe_basename(name, index):
    name = os.path.basename(name or "").replace("\r", "_").replace("\n", "_")
    name = re.sub(r"[/\\\x00-\x1f]", "_", name)[:150]
    if not name:
        name = "catalogue_%02d.bin" % index
    return name

def included_attachments(original):
    attachments = []
    skipped = []
    total = 0
    for i,part in enumerate(original.walk(), 1):
        if part.is_multipart():
            continue
        name = part.get_filename()
        disposition = part.get_content_disposition()
        if not name and disposition != "attachment":
            continue
        filename = safe_basename(name, i)
        try:
            payload = part.get_payload(decode=True) or b""
        except (ValueError, TypeError):
            skipped.append("unsupported attachment")
            continue
        if payload.startswith(b"%PDF-"):
            mime = ("application", "pdf")
            if not filename.lower().endswith(".pdf"): filename += ".pdf"
        elif payload.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = ("image", "png")
            if not filename.lower().endswith(".png"): filename += ".png"
        elif payload.startswith(b"\xff\xd8\xff"):
            mime = ("image", "jpeg")
            if not filename.lower().endswith((".jpg",".jpeg")): filename += ".jpg"
        else:
            skipped.append("non-PDF/image file: " + filename)
            continue
        if not payload or len(payload) > MAX_SINGLE_ATTACHMENT or total + len(payload) > MAX_TOTAL_ATTACHMENT:
            skipped.append("large attachment not forwarded: " + filename)
            continue
        total += len(payload)
        attachments.append((filename, mime, payload))
    return attachments, skipped

def candidates():
    newest = {}
    for folder in ("new","cur"):
        location = MAILDIR / folder
        if not location.is_dir():
            continue
        for filepath in location.iterdir():
            if not filepath.is_file():continue
            stat = filepath.stat()
            if stat.st_mtime < CUTOFF: continue
            if stat.st_size > MAX_RAW: continue
            try:
                with filepath.open("rb") as f:
                    header = BytesParser(policy=policy.default).parse(f, headersonly=True)
                sender = parseaddr(str(header.get("From","")))[1].lower()
                subject = str(header.get("Subject","")).lower()
                auto = str(header.get("Auto-Submitted","")).lower()
                if not sender or sender.endswith("@zomorodmelal.ir"):
                    continue
                if any(p in sender for p in ("mailer-daemon","postmaster","no-reply","noreply")):
                    continue
                if any(p in subject for p in ("delivery status","undeliver","failure notice","returned mail")):
                    continue
                if auto and auto != "no":continue
                # Require thread evidence: previously identified external supplier replies,
                # not arbitrary marketing to the corporate address.
                if not (header.get("In-Reply-To") or header.get("References") or subject.startswith(("re:","回复","re：")) or "zomorod melal" in subject):
                    continue
                fingerprint = hashlib.sha256((
                    str(header.get("Message-ID","")).strip() or str(filepath)
                ).encode("utf-8","replace")).hexdigest()
                if sender not in newest or stat.st_mtime > newest[sender][0]:
                    newest[sender] = (stat.st_mtime, fingerprint, filepath)
            except (OSError, ValueError, UnicodeError):
                continue
    return sorted(newest.values(),key=lambda x:x[0])[:MAX_REPLIES]

def save_json(path, state):
    fd,name=tempfile.mkstemp(prefix=".supplier-forward-",dir=str(path.parent),text=True)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            os.chmod(name,0o600)
            json.dump(state,f,ensure_ascii=False,indent=2,sort_keys=True)
            f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)

def build_forward(original, seq):
    external_from = str(original.get("From",""))
    external_subject = str(original.get("Subject",""))
    external_date = str(original.get("Date",""))
    text = message_text(original)
    attachments,skipped = included_attachments(original)
    out = EmailMessage()
    out["From"] = f"Zomorod Melal Supplier Archive <{SENDER}>"
    out["To"] = OWNER
    out["Date"] = email.utils.formatdate(localtime=False,usegmt=True)
    out["Message-ID"] = email.utils.make_msgid(domain="zomorodmelal.ir")
    out["Subject"] = f"[Zomorod Supplier Replies 2026-10-23] #{seq:02d}: {external_subject[:155]}"
    out["X-Zomorod-Private-Owner-Copy"]="supplier-mail-archive-20261023"
    header = (
        "Original supplier reply forwarded from the company's own cPanel mailbox.\n"
        "This is an archival copy for the verified mailbox owner; no message was sent to the supplier.\n\n"
        "Original From: " + external_from + "\n"
        "Original Date: " + external_date + "\n"
        "Original Subject: " + external_subject + "\n\n"
        "========== ORIGINAL MESSAGE TEXT ==========\n"
    )
    trailer = "\n\n========== END ORIGINAL MESSAGE ==========\n"
    if skipped:
        trailer += "\nATTACHMENT NOTES:\n" + "\n".join("- "+x for x in skipped)
    if not text:
        trailer += "\nOriginal message has no readable text/plain or text/html body."
    out.set_content(header + text + trailer, charset="utf-8")
    for filename,mime,contents in attachments:
        out.add_attachment(contents,maintype=mime[0],subtype=mime[1],filename=filename)
    return out, len(attachments), len(skipped)

def main():
    os.umask(0o077)
    if not MAILDIR.is_dir():
        raise SystemExit("ERROR=CORPORATE_MAILDIR_NOT_FOUND")
    inbox_list = subprocess.run(["uapi","--output=json","Email","list_pops"],capture_output=True,text=True,timeout=35,check=True)
    api=json.loads(inbox_list.stdout).get("result",{})
    owned={str(a.get("email","")).lower() for a in (api.get("data") or []) if isinstance(a,dict)}
    if api.get("status")!=1 or SENDER not in owned:raise SystemExit("ERROR=SENDER_MAILBOX_NOT_VERIFIED")
    if not Path("/usr/sbin/sendmail").exists():raise SystemExit("ERROR=SENDMAIL_MISSING")
    PRIVATE.mkdir(mode=0o700,parents=True,exist_ok=True);PRIVATE.chmod(0o700)
    ledger=PRIVATE/(BATCH+".json")
    lock=PRIVATE/(BATCH+".lock")
    replies=candidates()
    print("PRIVATE_OWNER_DELIVERY=true",flush=True)
    print("SENDER_VERIFIED=true",flush=True)
    print("OWNER_DELIVERY_TARGET=VERIFIED_CONNECTED_PRIMARY_GMAIL",flush=True)
    print("SUPPLIER_REPLY_CANDIDATES="+str(len(replies)),flush=True)
    sent=0;previous=0;failed=0;attachments=0;skipped=0
    with lock.open("a+") as lk:
        os.chmod(lock,0o600);fcntl.flock(lk,fcntl.LOCK_EX)
        state=json.loads(ledger.read_text(encoding="utf-8")) if ledger.exists() else {"campaign":BATCH,"entries":{}}
        for num,(_,fingerprint,path) in enumerate(replies,1):
            if fingerprint in state["entries"]:
                previous+=1
                continue
            try:
                with path.open("rb") as f:
                    original=BytesParser(policy=policy.default).parse(f)
                forward,ac,sc=build_forward(original,num)
                # Write audit marker before submission to avoid duplicate forwards after interrupted jobs.
                state["entries"][fingerprint]={"status":"attempt_started","attachments":ac,"skipped":sc}
                save_json(ledger,state)
                res=subprocess.run(["/usr/sbin/sendmail","-t","-i","-f",SENDER],input=forward.as_bytes(),capture_output=True,timeout=70)
                status="accepted_by_local_exim" if res.returncode==0 else "submission_failed"
                state["entries"][fingerprint]["status"]=status
                state["entries"][fingerprint]["exit_code"]=res.returncode
                if res.returncode==0:
                    sent+=1;attachments+=ac;skipped+=sc
                else:failed+=1
                save_json(ledger,state)
                print("FORWARDED_%02d="%num+status+";attachments="+str(ac)+";omitted="+str(sc),flush=True)
            except Exception as e:
                failed+=1
                state["entries"].setdefault(fingerprint,{})["status"]="exception"
                state["entries"][fingerprint]["error_type"]=type(e).__name__
                save_json(ledger,state)
                print("FORWARDED_%02d=exception_type_%s"%(num,type(e).__name__),flush=True)
    print("NEW_FORWARDED_ACCEPTED_BY_EXIM="+str(sent))
    print("PREVIOUSLY_ATTEMPTED="+str(previous))
    print("FAILED_OR_NOT_CONFIRMED="+str(failed))
    print("CATALOGUE_FILES_ATTACHED="+str(attachments))
    print("UNSAFE_OR_LARGE_FILES_SKIPPED="+str(skipped))
    print("REMOTE_GMAIL_DELIVERY_MUST_BE_CHECKED_SEPARATELY")
    if failed:raise SystemExit(1)

if __name__=="__main__":main()
