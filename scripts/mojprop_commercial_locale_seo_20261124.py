#!/usr/bin/env python3
"""Prepare commercial-search copy for the 20 existing MOJ PROP locale pages.

Input must be the current verified locale tree; output is a separate release
candidate. No network, finance, secrets, server deployment or language URL changes.
"""
import argparse
import html
import json
import re
from pathlib import Path

ROWS = [
  [
    "en",
    "Prop Firm Challenge",
    "Explore the 60-day simulated Starter30 challenge, listed fee 30 TRX. Review official English rules and invoice eligibility.",
    "Review Starter30 challenge terms"
  ],
  [
    "zh",
    "自营交易考核（Prop Firm）",
    "了解60天模拟交易考核 Starter30，标示费用30 TRX。请查阅官方英文规则和发票资格。",
    "查看 Starter30 考核条款"
  ],
  [
    "hi",
    "प्रॉप फर्म चैलेंज",
    "60 दिन के सिम्युलेटेड Starter30 चैलेंज की सूचीबद्ध फीस 30 TRX है। आधिकारिक अंग्रेज़ी नियम और इनवॉइस पात्रता देखें।",
    "Starter30 चैलेंज की शर्तें देखें"
  ],
  [
    "es",
    "Prop Firm: desafío de trading",
    "Conoce Starter30, un desafío simulado de 60 días con tarifa publicada de 30 TRX. Consulta las reglas en inglés y los requisitos de facturación.",
    "Consultar condiciones de Starter30"
  ],
  [
    "ar",
    "شركات التداول الممول: تحدي تداول محاكى",
    "تعرّف على تحدي Starter30 المحاكى لمدة 60 يوماً برسوم معلنة قدرها 30 TRX. راجع الشروط الإنجليزية الرسمية وأهلية إصدار الفاتورة.",
    "اطّلع على شروط تحدي Starter30"
  ],
  [
    "fr",
    "Prop firm : challenge de trading",
    "Découvrez Starter30, un challenge simulé de 60 jours au tarif affiché de 30 TRX. Consultez les règles en anglais et les conditions de facturation.",
    "Consulter les conditions Starter30"
  ],
  [
    "bn",
    "প্রপ ফার্ম ট্রেডিং চ্যালেঞ্জ",
    "৬০ দিনের সিমুলেটেড Starter30 চ্যালেঞ্জের প্রকাশিত ফি ৩০ TRX। ইংরেজি নিয়ম ও ইনভয়েসের যোগ্যতা দেখুন।",
    "Starter30 চ্যালেঞ্জের শর্ত দেখুন"
  ],
  [
    "pt",
    "Mesa proprietária: desafio de trading",
    "Conheça o Starter30, desafio simulado de 60 dias com taxa anunciada de 30 TRX. Confira as regras em inglês e os requisitos de faturamento.",
    "Consultar condições do Starter30"
  ],
  [
    "id",
    "Prop Firm: tantangan trading",
    "Kenali Starter30, tantangan trading simulasi 60 hari dengan biaya tercantum 30 TRX. Lihat aturan bahasa Inggris dan kelayakan faktur.",
    "Lihat ketentuan Starter30"
  ],
  [
    "ur",
    "پراپ فرم ٹریڈنگ چیلنج",
    "Starter30 کا 60 روزہ سمیولیٹڈ ٹریڈنگ چیلنج، درج فیس 30 TRX۔ سرکاری انگریزی قواعد اور انوائس کی اہلیت دیکھیں۔",
    "Starter30 چیلنج کی شرائط دیکھیں"
  ],
  [
    "ru",
    "Проп-трейдинг: челлендж проп-фирмы",
    "Starter30 — симуляционный челлендж на 60 дней, заявленная цена 30 TRX. Проверьте официальные правила на английском и условия выставления счёта.",
    "Условия челленджа Starter30"
  ],
  [
    "de",
    "Prop Trading: Prop-Firm-Challenge",
    "Starter30 ist eine simulierte 60-Tage-Challenge mit ausgewiesener Gebühr von 30 TRX. Englische Regeln und Voraussetzungen zur Rechnungsstellung prüfen.",
    "Starter30-Bedingungen ansehen"
  ],
  [
    "ja",
    "プロップファームの取引チャレンジ",
    "Starter30は60日間の模擬取引チャレンジです。表示料金は30 TRX。公式英語版の規約と請求書発行条件をご確認ください。",
    "Starter30の規約を確認"
  ],
  [
    "pcm",
    "Prop firm trading challenge",
    "Starter30 na 60-day simulated trading challenge. Dem list fee as 30 TRX. Check official English rules and who fit get invoice.",
    "Check Starter30 challenge terms"
  ],
  [
    "ar-eg",
    "بروب فرم: تحدي التداول الممول المحاكى",
    "Starter30 تحدي تداول محاكى لمدة 60 يوم، والسعر المعلن 30 TRX. راجع الشروط الرسمية بالإنجليزي وأهلية إصدار الفاتورة.",
    "شوف شروط تحدي Starter30"
  ],
  [
    "mr",
    "प्रॉप फर्म ट्रेडिंग चॅलेंज",
    "Starter30 हे 60 दिवसांचे सिम्युलेटेड ट्रेडिंग चॅलेंज आहे; नमूद शुल्क 30 TRX. अधिकृत इंग्रजी नियम आणि इनव्हॉइस पात्रता पाहा.",
    "Starter30 च्या अटी पाहा"
  ],
  [
    "vi",
    "Prop Firm: thử thách giao dịch",
    "Starter30 là thử thách giao dịch mô phỏng 60 ngày, phí niêm yết 30 TRX. Xem quy định tiếng Anh và điều kiện xuất hóa đơn.",
    "Xem điều khoản Starter30"
  ],
  [
    "te",
    "ప్రాప్ ఫర్మ్ ట్రేడింగ్ ఛాలెంజ్",
    "Starter30 అనేది 60 రోజుల అనుకరణ ట్రేడింగ్ ఛాలెంజ్; ప్రకటిత రుసుము 30 TRX. అధికారిక ఆంగ్ల నియమాలు, ఇన్వాయిస్ అర్హత చూడండి.",
    "Starter30 నిబంధనలు చూడండి"
  ],
  [
    "sw",
    "Prop firm: changamoto ya biashara",
    "Starter30 ni changamoto ya biashara ya majaribio ya siku 60, ada iliyotajwa 30 TRX. Angalia masharti ya Kiingereza na ustahiki wa ankara.",
    "Soma masharti ya Starter30"
  ],
  [
    "tr",
    "Prop Firm: fonlu işlem değerlendirmesi",
    "Starter30, 60 günlük simülasyon işlem değerlendirmesidir; ilan edilen ücret 30 TRX. İngilizce kuralları ve fatura uygunluğunu inceleyin.",
    "Starter30 şartlarını inceleyin"
  ]
]
COPY = {code: (title, desc, cta) for code, title, desc, cta in ROWS}
BASE = "https://mojplaywin.com/moj-prop/languages/"
MARKER = 'id="mojprop-commercial-intro-20261124"'

def replace_one(source, pattern, value):
    result, count = re.subn(pattern, lambda m: value(m), source, flags=re.S)
    if count != 1:
        raise ValueError(f"Expected one element, got {count}: {pattern}")
    return result

def transform(source, code):
    title, description, cta = COPY[code]
    canonical = BASE + code + "/"
    if source.count('rel="canonical" href="' + canonical + '"') != 1:
        raise ValueError("Unexpected locale canonical: " + code)
    if not re.search(r'<meta name="robots" content="index,follow(?:,[^"]*)?">', source):
        raise ValueError("Locale is not explicitly indexable: " + code)
    if MARKER in source:
        raise ValueError("Already revised: " + code)
    heading = "MOJ PROP | " + title
    t, d = html.escape(heading, quote=True), html.escape(description, quote=True)
    source = replace_one(source, r'<title>[^<]*</title>', lambda m: '<title>' + t + '</title>')
    for attr in ('name="description"', 'property="og:description"'):
        source = replace_one(source, r'<meta '+attr+r' content="[^"]*">', lambda m: '<meta '+attr+' content="'+d+'">')
    source = replace_one(source, r'<meta property="og:title" content="[^"]*">', lambda m: '<meta property="og:title" content="'+t+'">')
    source = replace_one(source, r'<h1>[^<]*</h1>', lambda m: '<h1>'+t+'</h1>\n<p '+MARKER+'>'+d+' <a href="/moj-prop/starter-30-trx/">'+html.escape(cta)+' →</a></p>')
    def structured(match):
        obj = json.loads(match.group(1))
        if obj.get("@type") != "WebPage" or obj.get("url") != canonical:
            raise ValueError("Unexpected structured data")
        obj.update(name=heading, description=description)
        return '<script type="application/ld+json">'+json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")+'</script>'
    return replace_one(source, r'<script type="application/ld\+json">(.*?)</script>', structured)

def build(source_dir, output_dir):
    if source_dir.resolve() == output_dir.resolve() or output_dir.exists():
        raise ValueError("Output must be a new, separate release directory")
    candidates = {}
    for code in COPY:
        p = source_dir / code / "index.html"
        if p.is_symlink() or p.parent.is_symlink():
            raise ValueError("Unsafe locale path")
        before = p.read_text(encoding="utf-8")
        after = transform(before, code)
        # Preserve original links, including analytics attribution, hreflang and terms.
        for pattern in (r'<link[^>]*rel="alternate"[^>]*>', r'<link[^>]*rel="canonical"[^>]*>', r'<script[^>]*src="[^"]+"[^>]*>'):
            if re.findall(pattern, before) != re.findall(pattern, after):
                raise ValueError("Preserved element changed: " + code)
        candidates[code] = after
    output_dir.mkdir(parents=True)
    for code, data in candidates.items():
        target = output_dir / code / "index.html"
        target.parent.mkdir()
        target.write_text(data, encoding="utf-8")
    print("COMMERCIAL_LOCALE_CANDIDATES", len(candidates))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    build(args.source_dir, args.output_dir)
