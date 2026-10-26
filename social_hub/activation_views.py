"""Owner/staff authenticated setup screen. GET only; no social provider calls."""
from __future__ import annotations

from html import escape

from django.http import HttpResponse,JsonResponse
from django.views.decorators.http import require_GET

from .adapters import Blocked
from .activation import build_activation_matrix
from .portal import _allowed,_db,_no_cache,staff_member_required_personal


def _data(user):
    brands=_allowed(user)
    if not brands:
        raise Blocked("No permitted social brand scope")
    db=_db()
    try:
        return build_activation_matrix(db,brands=brands)
    finally:
        db.close()


@staff_member_required_personal
@require_GET
def activation_json(request):
    if not _allowed(request.user):
        return _no_cache(JsonResponse({"error":"Brand permission denied"},status=403))
    try:
        result=_data(request.user)
    except (Blocked,OSError) as e:
        return _no_cache(JsonResponse({"error":str(e)},status=503))
    return _no_cache(JsonResponse(result,json_dumps_params={"ensure_ascii":False}))


@staff_member_required_personal
@require_GET
def activation_page(request):
    if not _allowed(request.user):
        return _no_cache(HttpResponse("Access denied",status=403))
    try:
        result=_data(request.user)
    except (Blocked,OSError) as e:
        return _no_cache(HttpResponse(
            "<h1>ماتریس آماده‌سازی API</h1><p>"+escape(str(e))+"</p>",
            status=503,content_type="text/html; charset=utf-8"))
    esc=lambda x:escape(str(x),quote=True)
    names={"personal":"شخصی و پژوهشی","zomorod":"کشت‌وصنعت زمرد ملل",
           "mojplaywin":"MojPlayWin"}
    counts=(
        ("پلتفرم‌ها",result["catalogue_platform_count"]),
        ("حساب‌های ثبت‌شده",result["registered_account_count"]),
        ("مالکیت تأییدشده",result["owner_attested_account_count"]),
        ("کلید خصوصی تنظیم‌شده",result["accounts_with_privately_configured_keys"]),
        ("مجوز انتشار تأییدشده",result["provider_posting_permissions_confirmed"]),
    )
    counters="".join("<article class='metric'><b>"+esc(n)+"</b><strong>"+str(v)+"</strong></article>"
                     for n,v in counts)
    sections=[]
    for brand in result["brands"]:
        records=[x for x in result["entries"] if x["brand"]==brand]
        def table(items):
            out=[]
            for item in items:
                status=(str(item["registered_accounts"])+" حساب · "+
                        str(item["attested_accounts"])+" تأیید مالکیت")
                capability=("آماده‌سازی API" if item["write_adapter_implemented_locally"]
                            else "نمایه/فرایند دستی")
                read=("آزمون خواندنی موجود" if item["read_only_probe_implemented_locally"]
                      else "آزمون خواندنی عمومی ندارد")
                if item["accounts"]:
                    next_step="؛ ".join(dict.fromkeys(
                        row["next_action_label"] for row in item["accounts"]))
                else: next_step=item["next_action_label"]
                documentation=esc(item["documentation_url"])
                out.append("<tr><td><b>"+esc(item["label"])+"</b>"+
                           "<small>"+esc(item["platform"])+"</small></td>"+
                           "<td>"+esc(status)+"</td><td>"+esc(capability)+
                           "<small>"+esc(read)+"</small></td>"+
                           "<td>"+esc(next_step)+"</td>"+
                           '<td><a rel="noopener noreferrer" target="_blank" href="'+
                           documentation+'">مستندات رسمی</a></td></tr>')
            return ('<div class="scroll"><table><thead><tr><th>شبکه / سرویس</th>'
                    '<th>ثبت حساب واقعی</th><th>قابلیت داخلی</th>'
                    '<th>گام بعدی</th><th>راهنمای API</th></tr></thead><tbody>'+
                    "".join(out)+'</tbody></table></div>')
        selected=[x for x in records if x["priority"]]
        rest=[x for x in records if not x["priority"]]
        sections.append(
            "<section><h2>"+esc(names[brand])+"</h2>"+
            "<p class='muted'>اولویت‌های پیشنهادی، نه الزام ایجاد حساب در همه سرویس‌ها.</p>"+
            table(selected)+
            "<details><summary>سایر "+str(len(rest))+
            " پلتفرم ثبت‌شده در کاتالوگ</summary>"+table(rest)+"</details></section>"
        )
    page="""<!doctype html><html lang="fa" dir="rtl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>فعال‌سازی شبکه‌ها | وب شخصی مجتبی روزگار</title>
<style>
:root{color-scheme:dark}body{background:#101610;color:#eee7d8;font:15px/1.7 system-ui;margin:0}
main,header{max-width:1180px;margin:auto;padding:18px}h1,h2{color:#eecf98}a{color:#f1c576}
p,small,.muted{color:#c7c4b8}small{display:block;font-size:12px}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.metric,section{border:1px solid #66583e;border-radius:12px;padding:16px;background:#1d251d}
.metric{display:flex;flex-direction:column}.metric strong{font-size:26px;color:#f0d398}
section{margin:16px 0}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;min-width:760px}
td,th{text-align:right;padding:11px;border-bottom:1px solid #4e533e;vertical-align:top}
th{color:#f6dbae}details{margin-top:15px}summary{cursor:pointer;color:#f6dbae}
aside{padding:16px 18px;background:#243025;border:1px solid #647d63;border-radius:12px}
</style></head><body><header><h1>نقشه فعال‌سازی شبکه‌های رسمی</h1>
<p>سه مجموعه مستقل · شواهد مالکیت · مجوز ارائه‌دهنده · اتصال امن و بدون انتشار خودکار</p>
<nav><a href="/mojtaba.roozegar/social-command/">بازگشت به پنل</a> ·
<a href="/mojtaba.roozegar/social-command/connection-plan/">برنامه خصوصی اتصال حساب‌های ثبت‌شده</a> ·
<a href="/mojtaba.roozegar/social-command/activation.json">خروجی JSON مدیریتی</a></nav></header><main>
<div class="metrics">"""+counters+"""</div>
<aside><p><b>فرایند واقعی اتصال:</b> ابتدا حساب موجود را در مرکز مدیریت ثبت کنید؛ سپس سند کنترل و مالکیت آن،
مجوز رسمی برنامه یا ربات، و کلید مربوط به همان حساب را به‌شکل خصوصی تأمین کنید. در ادامه آزمون خواندنی انجام می‌شود.
وجود کدِ اتصال‌دهنده به معنی ایجاد حساب، صدور OAuth یا مجوز انتشار نیست.</p>
<p>هیچ حسابی به‌صورت مصنوعی ایجاد نمی‌شود؛ حساب ممنوع Instagram نیز خارج از محدوده همه عملیات است.
همه درخواست‌ها GET و فاقد ارسال پیام، پست و تبلیغات هستند.</p></aside>"""+\
        "".join(sections)+"""<p>حساب‌ها و مجوزهای شبکه‌ها فقط از مسیرهای رسمی ارائه‌دهنده ثبت می‌شوند.
رمز عبور یا API Token را در سایت و چت ارسال نکنید.</p></main></body></html>"""
    return _no_cache(HttpResponse(page,content_type="text/html; charset=utf-8"))
