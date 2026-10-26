"""Public directory of explicitly verified profiles only (no staff fields)."""
from __future__ import annotations
from html import escape
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET
from .adapters import Blocked
from .public_links import official_links

def _read():
    from .portal import _db
    db=_db()
    try:
        return official_links(db)
    finally:
        db.close()

def _headers(response,has_links):
    # A suspended account must disappear on the next request, not remain in caches.
    response["Cache-Control"]="no-store, max-age=0, must-revalidate"
    response["Content-Security-Policy"]=(
        "default-src 'none'; style-src 'unsafe-inline'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
    response["X-Content-Type-Options"]="nosniff"
    response["Referrer-Policy"]="no-referrer"
    if not has_links:
        response["X-Robots-Tag"]="noindex,nofollow"
    return response

@require_GET
def public_channels_json(request):
    try:
        data=_read()
    except (Blocked,OSError):
        return _headers(JsonResponse({"error":"Directory temporarily unavailable"},status=503),False)
    return _headers(JsonResponse(data,json_dumps_params={"ensure_ascii":False}),data["total"]>0)

@require_GET
def public_channels(request):
    try:
        data=_read()
    except (Blocked,OSError):
        return _headers(HttpResponse("Public channels directory unavailable",status=503),False)
    sections=[]
    for brand in data["brands"]:
        links=[]
        for item in brand["links"]:
            label=escape(item["platform"])
            uri=escape(item["url"],quote=True)
            links.append('<li><a href="'+uri+
                '" target="_blank" rel="noopener noreferrer">'+label+
                '<span class="arrow" aria-hidden="true">↗</span></a></li>')
        if not links:
            links.append('<li class="empty">No ownership-verified public profiles have been listed yet.</li>')
        sections.append('<section aria-labelledby="h-'+escape(brand["key"])+
            '"><h2 id="h-'+escape(brand["key"])+'">'+escape(brand["title"])+
            '</h2><ul>'+"".join(links)+'</ul></section>')
    html='''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex" id="directory-robots">
<title>Verified Official Channels | Mojtaba Roozegar</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#111713;color:#efe7db;font:16px/1.7 system-ui,Arial}
main{max-width:1180px;padding:30px 16px;margin:auto}
h1{font:600 clamp(28px,4vw,45px)/1.2 Georgia,serif;color:#f0cf91}
p{max-width:820px;color:#d4cbbc}a{color:#f2d99b}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(265px,1fr));gap:16px}
section{background:#22251f;border:1px solid #786648;border-radius:15px;padding:18px}
h2{font:600 24px/1.4 Georgia,serif;color:#ebcc91}ul{list-style:none;padding:0}
li{border-top:1px solid #554b36;padding:9px 0}li a{display:flex;justify-content:space-between;gap:12px}
.empty{font-size:14px;color:#b6aa98}.arrow{font-size:19px}.note{font-size:14px}
</style></head><body><main>
<nav><a href="/mojtaba.roozegar/">← Back to main profile</a></nav>
<h1>Verified official channels</h1>
<p>One official directory for research, Zomorod Melal and MojPlayWin. We publish links only after administrative ownership attestation. A public link does not imply API authorization or endorsement by a social platform.</p>
<div class="grid">'''+"".join(sections)+'''</div>
<p class="note">For corrections and verification enquiries, use the contact page on the personal website. Account passwords, API tokens, private IDs and unverified profiles are never listed here.</p>
</main></body></html>'''
    if data["total"]:
        html=html.replace('<meta name="robots" content="noindex" id="directory-robots">',"")
    return _headers(HttpResponse(html,content_type="text/html; charset=utf-8"),data["total"]>0)
