"""Build an informational Persian prop-program page from the canonical policy.

Not mounted on any live URL. No forms, payments, links to checkout or trades.
"""
from html import escape
from pathlib import Path
from .rules import LEVELS, POLICY

def render_site():
    p = POLICY
    levels = "".join(
        f'<li><span>ماه {i}</span><b dir="ltr">${int(v):,}</b></li>'
        for i, v in enumerate(LEVELS, 1)
    )
    metrics = (
        ("ورودی چالش", f"{p.entry_trx} TRX", "درگاه پرداخت فعال نیست"),
        ("هدف اول", f"{p.phase_one_goal_pct}%", "سود خالص تأییدشده"),
        ("هدف دوم", f"{p.phase_two_goal_pct}%", "بعد از قبولی در مرحله اول"),
        ("زیان روزانه", f"{p.max_daily_loss_pct}%", "افت سرمایه با احتساب سود و زیان شناور"),
        ("زیان کل", f"{p.max_total_loss_pct}%", "از سرمایه اولیه سطح"),
        ("ثبات سود", f"{p.best_day_share_pct}%", "سقف سهم بهترین روز"),
    )
    cards = "".join(
        f'<article class="stat"><span>{escape(label)}</span><strong dir="ltr">{escape(amount)}</strong><small>{escape(note)}</small></article>'
        for label, amount, note in metrics
    )
    return f'''<!doctype html><html lang="fa" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><meta name="color-scheme" content="dark">
<meta name="description" content="قوانین پیشنهادی پراپ و تأمین سرمایه پلکانی. فروش و معاملات واقعی هنوز فعال نیست.">
<title>قوانین پراپ پلکانی | پیش از راه‌اندازی</title>
<style>
:root {{font-family:Tahoma,"Segoe UI",sans-serif;color:#e9f0f8;background:#081221}}
*{{box-sizing:border-box}}body{{margin:0;line-height:1.9}}
header,main,footer{{margin:auto;max-width:1120px;padding:22px}}
header{{display:flex;justify-content:space-between;gap:16px;border-bottom:1px solid #344257}}
header strong{{color:#f3cb85}}header span{{color:#bdd0e3}}
.hero{{padding:62px 0 36px;max-width:850px}}h1{{font-size:clamp(2rem,5vw,3.5rem);line-height:1.4}}
h2{{font-size:1.5rem;margin:0 0 16px}}p{{color:#ccdaea}}
.notice{{background:#2c241c;border:1px solid #d0a66c;color:#ffe3b5;border-radius:12px;padding:18px}}
.stats{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:25px 0 48px}}
.stat{{display:flex;flex-direction:column;gap:5px;background:#102137;border:1px solid #334660;border-radius:14px;padding:22px}}
.stat strong{{font-size:1.9rem;color:#f9cc83}}.stat small{{color:#adbed1}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:30px 0 50px}}
.panel{{background:#0d1c2d;border:1px solid #344359;padding:24px;border-radius:16px}}
.steps{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:0;list-style:none}}
.steps li{{background:#172b43;border-radius:10px;padding:8px 12px;display:flex;justify-content:space-between;gap:6px}}
.steps b{{color:#99e4d1}}.rules li{{margin-bottom:14px}}
.split{{display:flex;overflow:hidden;border-radius:12px;font-weight:750;margin:18px 0}}
.split b{{padding:12px;text-align:center}}.trader{{width:70%;background:#166b50}}
.company{{width:30%;background:#48586f}}
details{{border:1px solid #35465b;border-radius:12px;padding:12px 18px;margin:12px 0}}
summary{{cursor:pointer;font-weight:700}}
footer{{color:#a9bed1;font-size:.83rem;border-top:1px solid #344257;margin-top:42px}}
@media(max-width:850px){{.grid{{grid-template-columns:1fr}}.stats{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:500px){{header{{flex-direction:column}}.stats{{grid-template-columns:1fr}}.steps{{grid-template-columns:1fr}}}}
</style></head>
<body><header><strong>پراپ پلکانی | برنامه پیشنهادی</strong>
<span>ربات سازمانی واحد: <b dir="ltr">{escape(p.canonical_bot)}</b></span></header>
<main><section class="hero"><small>ارزیابی واقعی مهارت · قوانین شفاف · مدیریت ریسک</small>
<h1>از سرمایه ۱۰۰ دلار تا سقف ۱۰۰٬۰۰۰ دلار</h1>
<p>چالش دومرحله‌ای با هزینه پیشنهادی ۳۰ ترون؛ پس از موفقیت، احراز هویت، صدور مجوزهای لازم و تأمین واقعی وجه، معاملات در حساب واقعی متعلق به شرکت انجام خواهد شد.</p>
<div class="notice" role="status"><b>پیش از راه‌اندازی:</b>
ثبت‌نام پولی، دریافت TRX، افتتاح حساب واقعی و پرداخت سود در این صفحه فعال نیستند.
هیچ وعده قطعی تخصیص سرمایه یا سود ارائه نمی‌شود.</div></section>
<section aria-labelledby="challenge"><h2 id="challenge">قوانین ارزیابی</h2>
<div class="stats">{cards}</div></section>
<div class="grid"><section class="panel" aria-labelledby="tiers"><h2 id="tiers">۱۴ سطح سرمایه واقعی</h2>
<ol class="steps">{levels}</ol><p>ارتقای ماهانه حداکثر یک سطح، منوط به احراز عملکرد و وجود وجه کافی در شرکت است.</p>
</section><section class="panel" aria-labelledby="promotion"><h2 id="promotion">شرایط ارتقا و برداشت</h2>
<ul class="rules"><li>حداقل {p.min_challenge_days} روز معاملاتی معتبر در هر مرحله.</li>
<li>برای هر روز معاملاتی معتبر از هر مرحله چالش، یک پست اصلی اینستاگرام و یک پست اصلی فیسبوک لازم است؛ پست‌ها باید شرط تبلیغاتی را شفاف اعلام کنند و توسط بررسی‌کننده مستقل تأیید شوند. شرط فقط برای خریداران جدید نسخه ۱٫۲ است.</li>
<li>هر دوره ارتقا {p.promotion_cycle_days} روز است؛ هدف سود خالص {p.promotion_goal_pct}% و حداقل {p.promotion_min_days} روز معاملاتی.</li>
<li>حداکثر ریسک هر سفارش {p.order_risk_pct}% و مجموع سفارش‌های باز {p.aggregate_risk_pct}% سرمایه سطح است.</li>
<li>تکمیل چالش بدون مهلت اجباری است؛ اخطار عدم‌فعالیت پس از {p.inactivity_notice_days} روز و مهلت بعدی {p.inactivity_grace_days} روز.</li>
<li>تسویه سود ماهانه فقط پس از تأیید حسابداری و جبران زیان انباشته است.</li></ul>
<h2>تقسیم سود</h2><div class="split"><b class="trader">۷۰٪ معامله‌گر</b><b class="company">۳۰٪ شرکت</b></div>
</section></div>
<section aria-labelledby="faq"><h2 id="faq">پرسش‌های متداول</h2>
<details><summary>آیا اصل سرمایه به معامله‌گر منتقل می‌شود؟</summary><p>خیر؛ سرمایه متعلق به شرکت باقی می‌ماند و دسترسی معاملاتی محدود و قراردادی است.</p></details>
<details><summary>آیا قبولی، افتتاح حساب واقعی را تضمین می‌کند؟</summary><p>خیر؛ سرمایه، شرایط قرارداد، مجوزهای قانونی و کارگزار باید قبلاً تأیید شده باشند.</p></details>
<details><summary>ربات معاملاتی مستقل وجود دارد؟</summary><p>خیر؛ تنها ربات سازمانی mojtaba.bot.ai است. فعالیت خودکار فقط با کنترل ریسک و مجوز کارگزار مجاز خواهد بود.</p></details>
</section></main>
<footer>نسخه {escape(p.version)} | صفحه اطلاع‌رسانیِ قبل از راه‌اندازی. هیچ قابلیت دریافت وجه یا انجام معامله در این صفحه وجود ندارد.</footer>
</body></html>'''

def build_site(output):
    path=Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_site(),encoding="utf-8")
    return path

if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    build_site(parser.parse_args().output)
