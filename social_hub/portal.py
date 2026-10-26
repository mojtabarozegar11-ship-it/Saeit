"""Authenticated, CSRF-protected operator console. No HTTP endpoint sends posts."""
from __future__ import annotations
from html import escape
import json
import os

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_GET

from .catalog import BRANDS, PLATFORMS, catalogue
from .store import Store
from .service import connection_status
from .adapters import Blocked

def _allowed(user):
    if not user.is_authenticated or not user.is_active or not user.is_staff:
        return set()
    if user.is_superuser or user.groups.filter(name="social_admin").exists():
        return set(BRANDS)
    return {b for b in BRANDS if user.groups.filter(name="social_"+b).exists()}

def _approve_allowed(user, brand):
    return user.is_superuser or user.groups.filter(name="social_approver_"+brand).exists()

def _db():
    path = os.getenv("SOCIAL_HUB_PRIVATE_DB", "")
    if not path:
        raise Blocked("Private database is not configured; no accounts connected")
    return Store(path)

def _no_cache(response):
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Referrer-Policy"] = "no-referrer"
    return response

@staff_member_required
@require_GET
def read_status(request):
    brands = _allowed(request.user)
    if not brands:
        return _no_cache(JsonResponse({"error":"Access denied"},status=403))
    try:
        db = _db()
        try:
            accounts = [x for x in connection_status(db) if x["brand"] in brands]
            info = {b:db.summary(b) for b in sorted(brands)}
        finally:
            db.close()
    except (Blocked,OSError) as exc:
        return _no_cache(JsonResponse({"error":str(exc)},status=503))
    return _no_cache(JsonResponse({"accounts":accounts,"summary":info,
                                    "outbound_allowed_by_ui":False}))

@staff_member_required
@csrf_protect
@require_http_methods(["GET","POST"])
def dashboard(request):
    brands = _allowed(request.user)
    if not brands:
        return _no_cache(HttpResponse("Access denied to social brands",status=403))
    message, level = "", "info"
    try:
        db = _db()
    except (Blocked,OSError) as exc:
        return _no_cache(HttpResponse("<h1>Social Command Center</h1><p>" + escape(str(exc)) +
                           "</p><p>No external network activity is possible.</p>",status=503))

    try:
        if request.method == "POST":
            operation = request.POST.get("operation","")
            actor = "django:" + str(request.user.pk)
            try:
                brand = request.POST.get("brand","")
                if operation == "register":
                    if not request.user.is_superuser or brand not in brands:
                        raise Blocked("Owner administrator required")
                    aid = db.add_account(
                        brand=brand,platform_key=request.POST.get("platform",""),
                        destination=request.POST.get("destination",""),
                        public_url=request.POST.get("public_url",""),
                        instance=request.POST.get("instance",""),actor=actor)
                    message = "Account registered as unverified: " + aid
                elif operation == "verify":
                    aid = request.POST.get("account_id","")
                    account = db.account(aid)
                    if not request.user.is_superuser or not account or account["brand"] not in brands:
                        raise Blocked("Owner administrator required")
                    db.verify_account(aid,proof=request.POST.get("proof",""),actor=actor)
                    message = "Ownership evidence recorded. API token still required."
                elif operation == "draft":
                    aid = request.POST.get("account_id","")
                    account = db.account(aid)
                    if not account or account["brand"] not in brands:
                        raise Blocked("Account outside permitted brand")
                    if len(request.POST.get("text","")) > 120000:
                        raise Blocked("Draft text is too large")
                    content = {"text":request.POST.get("text",""),
                               "title":request.POST.get("title","")}
                    media_url = request.POST.get("media_url","").strip()
                    if media_url:
                        if account["platform"] == "tiktok":
                            content["video_url"] = media_url
                        else:
                            content["image_url"] = media_url
                    extra = request.POST.get("advanced_json","").strip()
                    if extra:
                        decoded = json.loads(extra)
                        if not isinstance(decoded,dict) or len(extra) > 100000:
                            raise Blocked("Additional JSON must be a bounded object")
                        content.update(decoded)
                    pid = db.draft(account_id=aid,content=content,
                             schedule_at=request.POST.get("scheduled_at",""),actor=actor)
                    message = "Draft saved; not published: " + pid
                elif operation in ("approve","cancel"):
                    pid = request.POST.get("post_id","")
                    post = db.post(pid)
                    if not post or post["brand"] not in brands:
                        raise Blocked("Post outside permitted brands")
                    if operation == "approve":
                        if not _approve_allowed(request.user, post["brand"]):
                            raise Blocked("Brand approver privilege required")
                        db.approve(pid,actor)
                        message = "Approved and queued; outbound worker still disabled."
                    else:
                        db.revoke(pid,actor)
                        message = "Publication cancelled."
                else:
                    raise Blocked("Unsupported operation")
                level = "success"
            except (Blocked, ValueError, OSError, json.JSONDecodeError) as exc:
                message, level = str(exc), "error"
        registered = [a for a in db.accounts() if a["brand"] in brands]
        posts = [p for p in db.posts(limit=200) if p["brand"] in brands]
        statuses = {s["account_id"]:s for s in connection_status(db) if s["brand"] in brands}
        summary = {brand:db.summary(brand) for brand in sorted(brands)}
    finally:
        db.close()

    token = escape(get_token(request), quote=True)
    action_url = escape(request.path, quote=True)
    opt_platforms = "".join("<option value='"+escape(p.key)+"'>"+
                            escape(p.label)+" · "+escape(p.capability)+"</option>"
                            for p in PLATFORMS.values())
    opt_brands = "".join("<option value='"+escape(b)+"'>"+escape(b)+"</option>"
                         for b in sorted(brands))
    opt_accounts = "".join("<option value='"+escape(a["id"])+"'>"+
                            escape(a["brand"]+" / "+a["platform"]+" / "+a["destination"][:45])+
                            "</option>" for a in registered if PLATFORMS[a["platform"]].sendable)
    def csrf(): return '<input type="hidden" name="csrfmiddlewaretoken" value="'+token+'">'
    def form(name,body,button):
        return ('<form method="post" action="'+action_url+'">' + csrf() +
                '<input type="hidden" name="operation" value="'+escape(name)+'">' +
                body + '<button type="submit">'+escape(button)+'</button></form>')
    def inp(name,placeholder="",type_="text",required=False):
        return ('<label>'+escape(name)+'<input name="'+escape(name)+'" placeholder="'+escape(placeholder)+
                '" type="'+escape(type_)+'" maxlength="1600"'+(' required' if required else '')+'></label>')
    register = form("register",
        '<label>Brand<select name="brand">'+opt_brands+'</select></label>'+
        '<label>Platform<select name="platform">'+opt_platforms+'</select></label>'+
        inp("destination","Official account / channel ID",required=True)+
        inp("public_url","https://…")+inp("instance","Mastodon https://instance…")+
        '<p class="hint">Profiles remain unverified until ownership evidence and API access are established.</p>',
        "Register planned account") if request.user.is_superuser else ""
    verify = form("verify",
        '<label>Account<select name="account_id">'+
        "".join('<option value="'+escape(a["id"])+'">'+escape(a["brand"]+" "+a["platform"]+" "+a["destination"][:35])+'</option>' for a in registered if not a["verified"]) +
        '</select></label>'+
        inp("proof","Independent ownership receipt reference",required=True),
        "Record verified ownership") if request.user.is_superuser else ""
    composer = form("draft",
        '<label>Target<select name="account_id">'+opt_accounts+'</select></label>'+
        inp("title","Title for video/article/pin")+
        '<label>Text<textarea name="text" rows="6" maxlength="120000" required></textarea></label>'+
        inp("media_url","https://official-site/media.jpg")+
        '<label>Schedule UTC (ISO 8601)<input name="scheduled_at" placeholder="2026-11-01T12:00:00Z"></label>'+
        '<label>Advanced platform JSON<textarea name="advanced_json" rows="4" placeholder=\'{"privacy":"private"}\'></textarea></label>',
        "Save draft (no publishing)")
    account_rows = []
    for a in registered:
        status = statuses.get(a["id"],{})
        state = "Verified" if a["verified"] else "Unverified"
        token_state = "Present" if status.get("token_present") else "Not connected"
        account_rows.append('<tr><td>'+escape(a["brand"])+'</td><td>'+escape(a["platform"])+'</td><td>'+
                            escape(a["destination"])+'</td><td>'+escape(state)+'</td><td>'+escape(token_state)+'</td></tr>')
    post_rows = []
    for p in posts:
        actions = ""
        if p["state"] == "draft":
            if _approve_allowed(request.user,p["brand"]):
                actions += form("approve",'<input type="hidden" name="post_id" value="'+escape(p["id"])+'">',"Approve")
            actions += form("cancel",'<input type="hidden" name="post_id" value="'+escape(p["id"])+'">',"Cancel")
        post_rows.append('<tr><td>'+escape(p["brand"])+'</td><td>'+escape(p["platform"])+'</td><td>'+
                         escape(p["state"])+'</td><td>'+escape(p["scheduled_at"])+'</td><td>'+
                         escape(p["remote_id"] or "—")+'</td><td>'+actions+'</td></tr>')
    stats = "".join('<article class="mini"><strong>'+escape(b)+'</strong><div>'+
                    str(s["accounts"])+' accounts · '+str(s["verified_accounts"])+' verified</div><div>'+
                    str(s["states"].get("published",0))+' confirmed published</div></article>'
                    for b,s in summary.items())
    msg = '<div class="notice '+level+'">'+escape(message)+'</div>' if message else ""
    page = ("""<!doctype html><html lang="fa" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>فرماندهی شبکه‌ها | وب مجتبی روزگار</title>
<style>
:root{color-scheme:dark}body{background:#111611;color:#f5ebda;font:15px/1.75 system-ui;margin:0}
header,main{max-width:1200px;margin:auto;padding:22px}a{color:#f0c576}
h1,h2{color:#efd09e}h1{font-size:clamp(25px,4vw,39px)}.sub{color:#cfc1a9}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:15px}
section,.mini{background:#20251f;border:1px solid #756445;border-radius:15px;padding:20px}
label{display:block;font-size:13px;color:#dbceb3;margin:9px 0}
input,select,textarea{width:100%;box-sizing:border-box;background:#131a15;border:1px solid #826d4a;
border-radius:8px;padding:10px;color:#fff;font:inherit;direction:auto}
button{background:#dfbd7a;border:0;padding:10px 17px;color:#181b16;font:700 14px system-ui;border-radius:8px;cursor:pointer}
form{margin:10px 0}.hint,.sub{font-size:13px}.notice{border-radius:9px;padding:12px;background:#263b2c;margin-bottom:16px}
.notice.error{background:#442b2b}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;min-width:680px}
td,th{padding:10px;border-bottom:1px solid #625940;text-align:right;word-break:break-word}
.mini{padding:15px}footer{font-size:12px;color:#b6aa90;margin:22px 0}
</style></head><body>
<header><h1>مرکز فرماندهی شبکه‌های اجتماعی و فعالیت‌های حرفه‌ای</h1>
<p class="sub">شخصی · زمرد ملل · MojPlayWin | پیش‌نویس، مجوز انتشار، حساب رسمی، وضعیت اتصال و رسید</p>
<nav><a href="/mojtaba.roozegar/">وب مرکزی</a> · <a href="status/">وضعیت JSON امن</a></nav></header>
<main>""" + msg + '<div class="grid">'+stats+'</div><br><div class="grid">'+(
'<section><h2>ثبت حساب رسمی</h2>'+register+'</section>' if register else "")+(
'<section><h2>ثبت شاهد مالکیت</h2>'+verify+'</section>' if verify else "")+(
'<section><h2>تهیه محتوای جدید</h2>'+composer+'</section>')+'</div>'+
'<section><h2>حساب‌ها</h2><div class="scroll"><table><thead><tr><th>مجموعه</th><th>شبکه</th><th>شناسه</th><th>مالکیت</th><th>API</th></tr></thead><tbody>'+
"".join(account_rows)+'</tbody></table></div></section>'+
'<section><h2>صف انتشار و رسیدها</h2><div class="scroll"><table><thead><tr><th>مجموعه</th><th>شبکه</th><th>وضعیت</th><th>زمان UTC</th><th>رسید</th><th>اقدام</th></tr></thead><tbody>'+
"".join(post_rows)+'</tbody></table></div></section>'+
'<footer>هیچ عملیات انتشار خارجی از پنل HTTP انجام نمی‌شود. انتشار تنها از worker خصوصی، با مجوز مستقل و کلیدهای بعدی فعال می‌شود. تبلیغ در dr.mojtaba.rozegar ممنوع است.</footer>'+
'</main></body></html>')
    return _no_cache(HttpResponse(page,content_type="text/html; charset=utf-8"))
