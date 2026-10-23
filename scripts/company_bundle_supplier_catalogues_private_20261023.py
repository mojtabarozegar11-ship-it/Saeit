#!/usr/bin/env python3
"""Stream a ZIP of supplier response texts and safe catalogue attachments from PRIVATE cPanel Maildir.

Stdout = ZIP bytes only; stderr = non-confidential numeric diagnostics.
No message content may be written to GitHub logs or repository.
"""
import csv, hashlib, io, os, re, sys, zipfile
from pathlib import Path
from html import unescape
from html.parser import HTMLParser
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from datetime import datetime, timezone

MAILDIR=Path.home()/"mail"/"zomorodmelal.ir"/"moj_1ro_1"
CUTOFF=datetime(2026,10,20,tzinfo=timezone.utc).timestamp()
MAX_MESSAGE_BYTES=28_000_000
MAX_MESSAGES=50
class HTMLToText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out=[]
        self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"):self.hidden+=1
        elif tag in ("p","br","li","div","tr"):self.out.append("\n")
    def handle_endtag(self,tag):
        if tag in ("script","style") and self.hidden:self.hidden-=1
        elif tag in ("p","div","tr","li"):self.out.append("\n")
    def handle_data(self,data):
        if not self.hidden:self.out.append(data)
def extract_text(msg):
    plains=[];htmls=[]
    for part in msg.walk():
        if part.is_multipart() or part.get_content_disposition()=="attachment":continue
        typ=part.get_content_type()
        if typ not in ("text/plain","text/html"):continue
        try:content=part.get_content()
        except (ValueError,LookupError,UnicodeError,AttributeError):continue
        if not isinstance(content,str):continue
        if typ=="text/plain":plains.append(content)
        else:
            p=HTMLToText();p.feed(content);htmls.append("".join(p.out))
    return ("\n\n".join(plains) if plains else "\n\n".join(htmls)).replace("\x00","").strip()

def safe_filename(s, fallback):
    s=str(s or "").replace("\\","/").split("/")[-1]
    s=re.sub(r"[\x00-\x1f<>:\"|?*]","_",s)
    return s[:120] or fallback

def candidates():
    latest={}
    for status in ("new","cur"):
        folder=MAILDIR/status
        if not folder.is_dir():continue
        for fn in folder.iterdir():
            if not fn.is_file():continue
            try:
                st=fn.stat()
                if st.st_mtime<CUTOFF or st.st_size>MAX_MESSAGE_BYTES:continue
                with fn.open("rb") as f:
                    header=BytesParser(policy=policy.default).parse(f,headersonly=True)
                addr=parseaddr(str(header.get("From","")))[1].lower()
                subj=str(header.get("Subject","")).lower()
                if not addr or addr.endswith("@zomorodmelal.ir"):continue
                if any(p in addr for p in ("mailer-daemon","postmaster","noreply","no-reply")):continue
                if any(p in subj for p in ("delivery status","undeliver","failure notice","returned mail")):continue
                auto=str(header.get("Auto-Submitted","")).lower()
                if auto and auto!="no":continue
                if not (header.get("In-Reply-To") or header.get("References") or subj.startswith(("re:","回复","re：")) or "zomorod melal" in subj):continue
                if addr not in latest or st.st_mtime>latest[addr][0]:latest[addr]=(st.st_mtime,fn)
            except (OSError,ValueError,UnicodeError):continue
    return [row[1] for row in sorted(latest.values())[:MAX_MESSAGES]]

def main():
    if not MAILDIR.is_dir():
        print("FAILED_MAILDIR_MISSING",file=sys.stderr);sys.exit(1)
    refs=candidates()
    if not refs:print("FAILED_NO_SUPPLIER_REPLIES",file=sys.stderr);sys.exit(1)
    buf=io.BytesIO()
    index=[]
    total_files=0;omitted=0
    with zipfile.ZipFile(buf,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as archive:
        archive.writestr("README_FA.txt","بایگانی خصوصی پاسخ‌های واقعی تأمین‌کنندگان زمرد ملل\nحاوی متن کامل ایمیل‌های دریافتی و فایل‌های PDF/تصویر. اصالت و امنیت محتوای پیوست‌های خارجی مستقل تأیید نشده است.\n\nمحتوای آرشیو محرمانه است و نباید عمومی منتشر شود.\n")
        for n,path in enumerate(refs,1):
            try:
                with path.open("rb") as f:msg=BytesParser(policy=policy.default).parse(f)
            except (OSError,ValueError):continue
            sender=str(msg.get("From",""))
            subject=str(msg.get("Subject",""))
            date=str(msg.get("Date",""))
            address=parseaddr(sender)[1].lower()
            family=safe_filename(address.split("@")[-1],str(n))
            folder="%02d_%s"%(n,family)
            original="From: "+sender+"\nDate: "+date+"\nSubject: "+subject+"\nMessage-ID: "+str(msg.get("Message-ID",""))+"\n\n"+"="*24+"\n\n"+extract_text(msg)
            archive.writestr("texts/"+folder+".txt",original.encode("utf-8"),compress_type=zipfile.ZIP_DEFLATED)
            attach_names=[]
            local_seen={}
            for part in msg.walk():
                if part.is_multipart():continue
                fn=part.get_filename()
                if not fn and part.get_content_disposition()!="attachment":continue
                try:raw=part.get_payload(decode=True) or b""
                except (ValueError,TypeError):raw=b""
                if not raw:omitted+=1;continue
                fn=safe_filename(fn,"catalogue")
                if raw.startswith(b"%PDF-"):
                    if not fn.lower().endswith(".pdf"):fn+=".pdf"
                elif raw.startswith(b"\x89PNG\r\n\x1a\n"):
                    if not fn.lower().endswith(".png"):fn+=".png"
                elif raw.startswith(b"\xff\xd8\xff"):
                    if not fn.lower().endswith((".jpg",".jpeg")):fn+=".jpg"
                else:
                    omitted+=1;continue
                if len(raw)>18_000_000:omitted+=1;continue
                name_key=fn.casefold()
                if name_key in local_seen:
                    local_seen[name_key]+=1
                    base,ext=os.path.splitext(fn)
                    fn=base+"-"+str(local_seen[name_key])+ext
                else:local_seen[name_key]=1
                archive.writestr("catalogues/"+folder+"/"+fn,raw)
                attach_names.append(fn);total_files+=1
            index.append({"No":n,"Supplier":sender,"Original subject":subject,"Date":date,"Text file":"texts/"+folder+".txt","Catalogue files":" | ".join(attach_names),"Attachment count":len(attach_names)})
        records=io.StringIO()
        writer=csv.DictWriter(records,fieldnames=("No","Supplier","Original subject","Date","Text file","Catalogue files","Attachment count"))
        writer.writeheader();writer.writerows(index)
        archive.writestr("INDEX.csv","\ufeff"+records.getvalue())
    data=buf.getvalue()
    print("ARCHIVE_MAILS="+str(len(index)),file=sys.stderr,flush=True)
    print("ARCHIVE_CATALOGUE_FILES="+str(total_files),file=sys.stderr,flush=True)
    print("ARCHIVE_OMITTED_FILES="+str(omitted),file=sys.stderr,flush=True)
    print("ARCHIVE_ZIP_BYTES="+str(len(data)),file=sys.stderr,flush=True)
    sys.stdout.buffer.write(data);sys.stdout.buffer.flush()
if __name__=="__main__":main()
