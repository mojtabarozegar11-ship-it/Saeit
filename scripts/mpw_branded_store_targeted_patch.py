"""Prepare a fail-closed, one-function patch for the EXISTING MojPlayWin brand view.

Only apply by a separately authorized, guarded on-host deployment. This code
NEVER connects to a server and NEVER activates any product on its own.
"""
from __future__ import annotations

import ast
import argparse
from pathlib import Path

EXPECTED = '''def branded_store(request):
    brand=brand_for_request(request)
    if not brand or brand.code!="mojplaywin":
        raise Http404
    try:
        products=list(Product.objects.filter(active=True).order_by("-id"))
    except Exception:
        products=[]
    return render(request,"brands/mojplaywin/store.html",{"brand":brand,"products":products})
'''

REPLACEMENT = '''def branded_store(request):
    brand=brand_for_request(request)
    if not brand or brand.code!="mojplaywin":
        raise Http404
    try:
        products=list(Product.objects.filter(active=True).order_by("-id"))
    except Exception:
        products=[]
    from core.brand_store_integration import safe_brand_store_context
    from django.template.loader import render_to_string
    context=safe_brand_store_context(brand, products)
    response=render(request,"brands/mojplaywin/store.html",context)
    fragment=render_to_string(
        "core/includes/mpw_verified_factory_cards.html", context, request=request
    )
    if fragment.strip():
        raw=response.content
        marker=b"</main>" if b"</main>" in raw else b"</body>"
    # The customer-facing page must remain available even on unfamiliar markup.
    if marker in raw and raw.count(marker)==1:
        response.content=raw.replace(marker,fragment.encode("utf-8")+marker,1)
    return response
'''


def target_function(source):
    tree=ast.parse(source)
    nodes=[x for x in tree.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) and x.name=="branded_store"]
    if len(nodes)!=1:
        raise ValueError("EXPECTED_ONE_BRANDED_STORE_FUNCTION")
    return nodes[0]


def prepare(original):
    """Return (patched_text, number_of_changes) or reject unfamiliar production code."""
    if not isinstance(original,str) or not original:
        raise ValueError("NO_SOURCE")
    old=target_function(original)
    expected=target_function(EXPECTED)
    if ast.dump(old,include_attributes=False)!=ast.dump(expected,include_attributes=False):
        raise ValueError("ACTIVE_BRANDED_STORE_DIFFERS_FROM_VERIFIED_BASELINE")
    if "mpw_verified_factory_cards.html" in original:
        raise ValueError("FACTORY_INSERTION_ALREADY_PRESENT")
    lines=original.splitlines(keepends=True)
    start=old.lineno-1
    stop=old.end_lineno
    replacement=REPLACEMENT.splitlines(keepends=True)
    result="".join(lines[:start]+replacement+lines[stop:])
    compile(result,"core/brand_views.py","exec")
    observed=target_function(result)
    assert ast.dump(observed,include_attributes=False)==ast.dump(target_function(REPLACEMENT),include_attributes=False)
    assert result.count('def branded_store(')==1
    return result, 1


def main():
    args=argparse.ArgumentParser()
    args.add_argument("--source",required=True,type=Path)
    args.add_argument("--output",required=True,type=Path)
    options=args.parse_args()
    src=options.source
    dst=options.output
    if src.is_symlink() or not src.is_file():
        raise ValueError("SOURCE_MISSING_OR_UNSAFE")
    if dst.exists() or dst.is_symlink():
        raise ValueError("REFUSING_OVERWRITE")
    patched,_=prepare(src.read_text(encoding="utf-8"))
    dst.write_text(patched,encoding="utf-8")
    print("MPW_STOREFRONT_TARGETED_PATCH_PREPARED=True")
    print("MPW_PRODUCTION_SOURCE_NOT_CHANGED=True")


if __name__=="__main__":
    main()
