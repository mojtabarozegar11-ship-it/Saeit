#!/usr/bin/env python3
"""Read-only main-only template fingerprint tool for exact cPanel app root.

Reports no page contents, secrets, DB info, WSGI paths or customer data.
No filesystem writes, no imports of Django, no Passenger restart.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path

APP=Path("/home/zomorod2/Saeit-staging")
FILES=(
  "core/templates/mojplaywin/home.html",
  "core/templates/mojplaywin/store.html",
  "core/templates/mojplaywin/section.html",
  "core/templates/mojplaywin/theme.html",
  "core/templates/mojplaywin/footer.html",
  "core/templates/mojplaywin/founder_signature.html",
  "core/templates/mojplaywin/unified_visual_tokens.html",
)
SHARED=(
  "core/templates/base.html",
  "core/templates/brands/mojplaywin/base.html",
  "core/templates/brands/mojplaywin/home.html",
  "core/templates/brands/mojplaywin/page.html",
)
def analyze():
    result={}
    for path in FILES+SHARED:
        p=APP/path
        if p.is_symlink():
            result[path]={"state":"unsafe_symlink"}
        elif not p.exists():
            result[path]={"state":"missing"}
        elif not p.is_file() or p.stat().st_size>2000000:
            result[path]={"state":"unsafe_file"}
        else:
            blob=p.read_bytes()
            result[path]={"state":"file","bytes":len(blob),"sha256":hashlib.sha256(blob).hexdigest()}
    return {"classification":"MAINONLY_TEMPLATE_READONLY_FINGERPRINT",
            "files":result,"production_modified":False,
            "passenger_restart":False,"release_permitted":False}
if __name__=="__main__":
    print(json.dumps(analyze(),sort_keys=True))
