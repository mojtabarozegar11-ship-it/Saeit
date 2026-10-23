#!/usr/bin/env python3
"""Read only checkout template and CSP metadata for adding a gated TRX button."""
from __future__ import annotations
import ast,hashlib,json,os,sys
from pathlib import Path
ROOT=Path("/home/zomorod2/Saeit-staging")
os.chdir(ROOT);sys.path.insert(0,str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.template.loader import get_template
from mpw_commerce import product_checkout_page
source=Path(product_checkout_page.__file__).read_text("utf8","replace")
tree=ast.parse(source)
templates=[]
for fn in tree.body:
    if isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)) and fn.name=="product_checkout_page":
        for call in ast.walk(fn):
            if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id=="render":
                if len(call.args)>1 and isinstance(call.args[1],ast.Constant) and type(call.args[1].value) is str:
                    templates.append(call.args[1].value)
info=[]
for name in templates:
    if not name.endswith(".html") or len(name)>160:
        continue
    templ=get_template(name)
    origin=Path(templ.origin.name)
    if not origin.resolve().is_relative_to(ROOT.resolve()) or not origin.is_file() or origin.is_symlink():
        continue
    txt=origin.read_text("utf8","replace")
    info.append({"relative":str(origin.relative_to(ROOT)),"sha256":hashlib.sha256(txt.encode()).hexdigest(),
      "bytes":len(txt),"csrf_tokens":txt.count("csrf_token"),"main_end_tags":txt.count("</main>"),
      "body_end_tags":txt.count("</body>"),"form_tags":txt.count("<form"),
      "form_self":("form-action 'self'" in source or "form-action \\"self\\"" in source),
      "form_none":("form-action 'none'" in source or "form-action \\"none\\"" in source),
      "has_trx_text":"TRX" in txt,"wallet_signature_text":"signature" in txt.lower(),
      "extends_base":"{% extends" in txt})
print("MPW_TRX_TEMPLATE_CONTRACT="+json.dumps({"files":info,"read_only":True},sort_keys=True))
