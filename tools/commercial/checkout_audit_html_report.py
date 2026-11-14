"""RTL offline review sheet for the structurally audited checkout event trail.
This is neither payment verification nor evidence of fulfillment or settlement.
"""
import argparse
from html import escape
import json
import re
import sys
from pathlib import Path

ISSUE_LABELS={
 'EVENT_ID_COLLISION':'برخورد شناسه رویداد',
 'ORDER_AMOUNT_OR_CURRENCY_CHANGED':'تغییر مبلغ یا ارز یک سفارش',
 'MULTIPLE_CHECKOUT_CREATIONS':'ایجاد مکرر درخواست سفارش',
 'CHECKOUT_CREATION_AFTER_PAYMENT_OR_DELIVERY':'ایجاد سفارش پس از ثبت پرداخت یا تحویل',
 'PAYMENT_BEFORE_CHECKOUT_CREATION':'ادعای پرداخت پیش از ایجاد سفارش',
 'PAYMENT_NOT_GATEWAY_ATTESTED_IN_TRACE':'فقدان اعلام تأیید درگاه در گزارش',
 'POSSIBLE_MULTIPLE_PAYMENT_REFERENCES':'چند شناسه پرداخت متفاوت',
 'FAILURE_AFTER_CONFIRMATION_REQUIRES_REVIEW':'تعارض رویداد شکست پس از تأیید',
 'REFUND_WITHOUT_MATCHED_GATEWAY_PAYMENT':'استرداد بدون پرداخت متناظر',
 'REFUND_AFTER_FULFILLMENT_ACCESS_REVIEW':'لزوم بررسی دسترسی پس از استرداد',
 'FULFILLMENT_AFTER_REFUND_REQUIRES_REVIEW':'تحویل پس از استرداد',
 'FULFILLMENT_WITHOUT_TRUSTED_PAYMENT_IN_TRACE':'تحویل بدون تأیید ثبت‌شده درگاه',
 'MULTIPLE_FULFILLMENTS':'تحویل چندباره',
 'MISSING_CHECKOUT_CREATION':'نبود رویداد ایجاد سفارش',
 'PAYMENT_WITHOUT_FULFILLMENT_IN_TRACE':'تأیید پرداخت بدون ثبت تحویل',
}
HASH=re.compile(r'[0-9a-f]{64}\Z')


def render_checkout_report(data):
    if not isinstance(data,dict) or data.get('schema_version') != 1 or data.get('report_scope') != 'STRUCTURAL_ONLY_NOT_PAYMENT_OR_DELIVERY_PROOF':
        raise ValueError('invalid checkout audit report schema')
    orders=data.get('orders')
    if not isinstance(orders,list) or not (1<=len(orders)<=2000):
        raise ValueError('missing order summaries')
    sections=[]
    for i,item in enumerate(orders,1):
        if (not isinstance(item,dict) or not HASH.fullmatch(str(item.get('order_ref','')))
                or item.get('status') not in {'REVIEW_REQUIRED','NO_STRUCTURAL_ISSUES'}
                or not isinstance(item.get('issues'),list) or any(code not in ISSUE_LABELS for code in item['issues'])
                or not isinstance(item.get('fulfillment_events'),int) or not isinstance(item.get('payment_references_seen'),int)):
            raise ValueError(f'order {i}: incomplete or unsafe audit summary')
        ref=escape(item['order_ref'])
        problems=''.join('<li>'+escape(ISSUE_LABELS[x])+' <code>'+escape(x)+'</code></li>' for x in item['issues'])
        if not problems: problems='<li>در فهرست رویدادها ناسازگاری ساختاری ثبت نشد؛ صحت پرداخت و تحویل همچنان نیازمند شاهد مستقل است.</li>'
        sections.append('<section class="case"><h2>سفارش بی‌نام '+str(i)+'</h2><p class="trace" dir="ltr">'+ref+'</p>'+
                        '<p>رویداد تحویل: '+str(item['fulfillment_events'])+' · شناسه پرداخت متفاوت: '+str(item['payment_references_seen'])+'</p>'+
                        '<ul>'+problems+'</ul></section>')
    return '''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>گزارش داخلی بررسی Checkout — زمرد ملل</title><style>html{font-family:Tahoma,Arial,sans-serif;background:#f7f8f5;color:#203a2b}body{max-width:900px;margin:auto;padding:16px}.notice{background:#fff1d9;border-right:5px solid #a86b13;padding:12px}.case{background:#fff;border:1px solid #ccd8cf;border-radius:12px;padding:18px;margin:15px 0;page-break-inside:avoid}.trace,code{overflow-wrap:anywhere;word-break:break-word}.trace{font-size:.8rem;direction:ltr;text-align:left}ul{padding-right:22px}li{line-height:1.8;margin-bottom:8px}@media(max-width:600px){body{padding:8px}.case{padding:10px}}@media print{html{background:white}}</style></head><body><h1>گزارش ساختاری مسیر سفارش و تحویل دیجیتال</h1><p class="notice">فقط ممیزی ساختار رویدادهای بی‌نام‌سازی‌شده؛ این خروجی اثبات پرداخت، تسویه، مالکیت سفارش، وقوع استرداد یا تحویل نیست. نیازمند تطبیق سمت سرور و شواهد مستقل است.</p>''' + ''.join(sections) + '</body></html>'


def main(argv=None):
    ap=argparse.ArgumentParser(description='Render sanitized checkout audit JSON as local RTL report')
    ap.add_argument('audit_json');args=ap.parse_args(argv)
    try:
        data=json.loads(Path(args.audit_json).read_text(encoding='utf-8-sig'))
        html=render_checkout_report(data)
    except (OSError,UnicodeError,ValueError) as exc:
        print(f'Audit report rejected: {exc}',file=sys.stderr)
        return 2
    print(html)
    return 0


if __name__=='__main__':raise SystemExit(main())
