#!/usr/bin/env python3
"""C15 real public ticket-tracking form fidelity, GET only and PII free.

Observes only fixed HTTPS public PHP pages. Never submits, follows external
redirects, reads private customer records or prints form content/field values.
Identical form *structures* are a diagnostic, not proof of failed tracking.
"""
from __future__ import annotations

from html.parser import HTMLParser
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler
from urllib.error import HTTPError, URLError
import ssl

BASE="https://zomorodmelal.ir"
ROUTES={
    "inquiry": "/ask-master/index.php?service=1",
    "status": "/ask-master/status.php",
}
MAX_BYTES=128*1024
TRACK_NAMES={"ticket","ticket_id","tracking","tracking_code","request_id",
             "reference","receipt","receipt_id","case_id","code","status_code"}
PRIVACY_NAMES={"consent","privacy_consent","accept_terms","agreement","agree"}
CSRF_NAMES={"_csrf","csrf_token","csrfmiddlewaretoken","form_token","nonce"}

class NoFollow(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, url):
        return None

class Structural(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms=[]
        self.current=None
        self.title=False
        self.title_parts=[]
        self.hidden_values_read=False

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=="title":
            self.title=True
        if tag=="form":
            self.current={
                "method":str(attrs.get("method") or "get").casefold(),
                "input_names":set(),
                "csrf":False,
                "consent":False,
                "tracking":False,
                "email":False,
            }
            self.forms.append(self.current)
        if self.current is not None and tag in ("input","textarea","select"):
            name=str(attrs.get("name") or "").strip().casefold()
            typ=str(attrs.get("type") or "text").strip().casefold()
            # Never access or store input 'value', placeholder or text body.
            if name:
                self.current["input_names"].add(name[:60])
            if name in TRACK_NAMES:self.current["tracking"]=True
            if name in PRIVACY_NAMES:self.current["consent"]=True
            if name in CSRF_NAMES:self.current["csrf"]=True
            if typ=="email" or name=="email":self.current["email"]=True

    def handle_endtag(self,tag):
        if tag=="title":self.title=False
        if tag=="form":self.current=None

    def handle_data(self,data):
        if self.title and len(self.title_parts)<5:
            # Only lengths, never title strings (could theoretically embed user data)
            self.title_parts.append(str(len(data)))

    def signature(self):
        # Hashing and outputs are limited to structural metadata only.
        return tuple(sorted(
            (f["method"], tuple(sorted(f["input_names"]))) for f in self.forms
        ))

def collect(label, path, opener):
    req=Request(BASE+path,headers={
        "User-Agent":"ZM-C15-Public-Ticket-Diagnostic/1",
        "Accept":"text/html",
    },method="GET")
    out={"http":"UNKNOWN","form_count":0,"status_code_input":False,
         "email_input":False,"consent_input":False,"csrf_named":False,
         "post_form":False,"structure":None,"title_length_parts":()}
    try:
        with opener.open(req,timeout=12) as r:
            out["http"]=str(r.status)
            if r.status!=200 or "text/html" not in str(r.headers.get("Content-Type","")).casefold():
                return out
            data=r.read(MAX_BYTES+1)
            if len(data)>MAX_BYTES:
                out["http"]="TRUNCATED_HTML"
                return out
    except HTTPError as ex:
        out["http"]=str(ex.code)
        return out
    except (URLError,TimeoutError,OSError):
        return out
    doc=Structural()
    try:
        doc.feed(data.decode("utf-8","replace"))
    except Exception:
        out["http"]="HTML_PARSE_FAILED"
        return out
    out["form_count"]=len(doc.forms)
    out["status_code_input"]=any(f["tracking"] for f in doc.forms)
    out["email_input"]=any(f["email"] for f in doc.forms)
    out["consent_input"]=any(f["consent"] for f in doc.forms)
    out["csrf_named"]=any(f["csrf"] for f in doc.forms)
    out["post_form"]=any(f["method"]=="post" for f in doc.forms)
    out["structure"]=doc.signature()
    out["title_length_parts"]=tuple(doc.title_parts)
    return out

def main():
    opener=build_opener(HTTPSHandler(context=ssl.create_default_context()),NoFollow)
    readings={k:collect(k,v,opener) for k,v in ROUTES.items()}
    for key,value in readings.items():
        prefix="ZM_C15_PUBLIC_"+key.upper()+"_"
        print(prefix+"HTTP="+value["http"])
        print(prefix+"FORM_COUNT="+str(value["form_count"]))
        for label in ("status_code_input","email_input","consent_input","csrf_named","post_form"):
            print(prefix+label.upper()+"="+str(value[label]).lower())
    comparable=all(readings[k]["http"]=="200" for k in ROUTES)
    print("ZM_C15_PUBLIC_BOTH_PAGES_HTML_200="+str(comparable).lower())
    print("ZM_C15_PUBLIC_SAME_FORM_STRUCTURE="+(
        str(readings["inquiry"]["structure"]==readings["status"]["structure"]).lower()
        if comparable else "unknown"
    ))
    print("ZM_C15_PUBLIC_SAME_TITLE_LENGTH_FINGERPRINT="+(
        str(readings["inquiry"]["title_length_parts"]==readings["status"]["title_length_parts"]).lower()
        if comparable else "unknown"
    ))
    print("ZM_C15_PUBLIC_REAL_TICKET_LOOKUP_PROVEN=unknown")
    print("ZM_C15_PUBLIC_PERSISTED_REQUESTS_VERIFIED=unknown")
    print("ZM_C15_PUBLIC_PERSONAL_RECORDS_ACCESSED=false")
    print("ZM_C15_PUBLIC_POST_REQUESTS_SENT=0")

if __name__=="__main__":
    main()
