#!/usr/bin/env python3
"""Build six static buyer service pages from the exact Django catalogue.

No separate catalogue, no DB, no client records, no publishing; output
is deterministic and usable by a future collision-checked file-only release.
"""
from __future__ import annotations

import ast
from html import escape
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build" / "company-scope-static"
BASE = "https://zomorodmelal.ir"
CONTACT = "/ask-master/index.php?service=1"
CODES = ("AGR-01", "RS-01", "RS-02", "RS-03", "WEB-01", "SEO-01")

def literal(name: str, path: Path) -> dict:
    source = ast.parse(path.read_text(encoding="utf-8"))
    for item in source.body:
        if isinstance(item, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in item.targets
        ):
            value = ast.literal_eval(item.value)
            if not isinstance(value, dict):
                raise ValueError("catalogue must remain a literal dictionary")
            return value
    raise ValueError("missing literal source of truth: " + name)

def bullets(items) -> str:
    return "".join("<li>" + escape(str(item)) + "</li>" for item in items)

def html_page(code: str, offer: dict, guide: dict) -> str:
    title = escape(offer["title_fa"])
    pain = escape(guide["pain"])
    customer = escape(offer["customer"])
    limitation = escape(offer["limitation"])
    acceptance = escape(guide["acceptance"])
    schema = {
        "@context": "https://schema.org",
        "@type": "Service",
        "name": offer["title_fa"],
        "serviceType": offer["title_fa"],
        "url": f"{BASE}/services/scope/{code}/",
        "provider": {
            "@type": "Organization",
            "name": "شرکت کشت و صنعت زمرد ملل",
            "url": BASE + "/",
        },
        "areaServed": {"@type": "Country", "name": "ایران"},
        "description": guide["pain"],
    }
    jsonld = json.dumps(schema, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    brief = escape(
        f"کد خدمت: {code}\nخدمت درخواستی: {offer['title_fa']}\n"
        f"مسئله: {guide['pain']}\nخروجی مورد انتظار: {guide['acceptance']}\n"
        "این استعلام غیرتعهدآور است؛ قیمت و زمان پس از بررسی اعلام می‌شود."
    )
    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="index,follow">
  <title>{title} | دامنه بررسی تخصصی | زمرد ملل</title>
  <meta name="description" content="{pain}">
  <link rel="canonical" href="{BASE}/services/scope/{code}/">
  <script type="application/ld+json">{jsonld}</script>
  <style>
    :root {{ color-scheme:light; font-family:Tahoma,Arial,sans-serif }}
    body {{ color:#143a33; background:#f7faf8; margin:0; line-height:1.95 }}
    main {{ width:min(960px,calc(100% - 32px));margin:2rem auto; }}
    .card {{ background:#fff; border:1px solid #d5e5dc; border-radius:15px; padding:1.35rem; margin:1rem 0 }}
    h1 {{ font-size:clamp(1.45rem,4.5vw,2.25rem); line-height:1.5 }}
    h2 {{ font-size:1.25rem }} a {{ color:#115f4c }}
    .cta {{ display:inline-block;background:#125a4b;color:#fff;border-radius:10px;padding:.75rem 1.4rem;text-decoration:none }}
    textarea {{ display:block;width:100%;max-width:100%;box-sizing:border-box;min-height:170px; padding:1rem; font:inherit;color:inherit }}
    button {{ padding:.55rem 1rem;cursor:pointer }}
    small {{ font-size:.88rem }} :focus-visible {{ outline:3px solid #d4a855; outline-offset:3px }}
  </style>
</head>
<body><main>
<nav aria-label="مسیر"><a href="/services/">خدمات تخصصی زمرد ملل</a> / {escape(code)}</nav>
<header class="card">
  <small>کد {escape(code)} · استعلام اولیه غیرتعهدآور</small><h1>{title}</h1>
  <p>{pain}</p><p><strong>مناسب برای:</strong> {customer}</p>
  <a class="cta scope-primary-cta" href="{CONTACT}">ورود به فرم رسمی شرکت</a>
  <p><small>هنگام ثبت درخواست، کد {escape(code)} را در بخش توضیحات فرم درج کنید؛ انتقال خودکار اطلاعات در این نسخه تأیید نشده است.</small></p>
</header>
<section class="card"><h2>پرسش‌هایی که بررسی به آن‌ها پاسخ می‌دهد</h2><ul>{bullets(guide["questions"])}</ul></section>
<section class="card"><h2>مدارک و داده‌های اولیه موردنیاز</h2><ul>{bullets(guide["intake"])}</ul>
<p>از ارسال رمز عبور، اطلاعات پرداخت یا اسناد محرمانه در فرم عمومی خودداری کنید.</p></section>
<section class="card"><h2>خروجی‌های پیشنهادی</h2><ul>{bullets(offer["deliverables"])}</ul>
<p><strong>معیار بررسی خروجی:</strong> {acceptance}</p><p><strong>محدودیت:</strong> {limitation}</p></section>
<section class="card"><h2>متن آماده استعلام، بدون اطلاعات شخصی</h2>
<label for="inquiry-text">برای درج در توضیحات فرم اصلی</label>
<textarea id="inquiry-text" readonly>{brief}</textarea>
<button id="copy-brief" type="button">کپی متن استعلام</button>
<p id="copy-feedback" role="status" aria-live="polite">می‌توانید متن را دستی انتخاب و کپی کنید.</p></section>
<section class="card"><h2>مراحل همکاری</h2><ol>
<li>ارسال استعلام اولیه و شرح مسئله، بدون پرداخت</li>
<li>بررسی ظرفیت، داده‌ها، هزینه و الزامات حقوقی</li>
<li>تهیه پیشنهاد دامنه، قیمت و زمان فقط پس از تأیید مجاز</li>
<li>شروع خدمت صرفاً پس از توافق و ترتیبات پرداخت قانونی</li></ol>
<p><strong>تذکر:</strong> این صفحه سفارش، پیش‌فاکتور یا تضمین نتیجه نیست.</p>
<a class="cta" href="{CONTACT}">ثبت استعلام در مسیر اصلی شرکت</a></section>
<script>
(function(){{
  "use strict";
  const button=document.getElementById("copy-brief"), field=document.getElementById("inquiry-text");
  const output=document.getElementById("copy-feedback");
  if(!button||!field||!output)return;
  button.addEventListener("click",async function(){{
    try {{
      if(!navigator.clipboard?.writeText)throw Error("manual");
      await navigator.clipboard.writeText(field.value);
      output.textContent="متن کپی شد؛ آن را در فرم رسمی شرکت قرار دهید.";
    }}catch(e){{
      field.focus();field.select();
      output.textContent="متن انتخاب شد؛ آن را دستی کپی کنید.";
    }}
  }});
}})();
</script>
</main></body></html>
"""

def main() -> int:
    offers = literal("_SERVICES", ROOT / "core" / "service_sales_controls.py")
    guides = literal("SCOPE_GUIDES", ROOT / "core" / "service_scope_pages.py")
    if set(offers) != set(CODES) or set(guides) != set(CODES):
        raise ValueError("service catalogue mismatch; abort without partial release")
    pages = {
        code: html_page(code, offers[code], guides[code]).encode("utf-8")
        for code in CODES
    }
    for code, page in pages.items():
        if not page.startswith(b"<!doctype html>") or CONTACT.encode() not in page:
            raise ValueError("incomplete commercial page: " + code)
    for code, page in pages.items():
        dst = OUTPUT / code / "index.html"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(page)
    print(f"ZM_STATIC_SCOPE_GENERATED={len(pages)}")
    print("ZM_STATIC_SCOPE_SOURCE=EXACT_C12_CATALOGUE")
    print("ZM_STATIC_SCOPE_PUBLICATION=not_performed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
