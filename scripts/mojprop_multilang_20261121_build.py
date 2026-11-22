#!/usr/bin/env python3
"""Publish localized MOJ PROP risk education pages with SHA-pinned edits and rollback."""
from __future__ import annotations
from pathlib import Path
import hashlib, html, json, os, re, stat, tempfile, shutil, sys
from datetime import date

SITE=Path('/home/zomorod2/mojplaywin.com')
PROP=SITE/'moj-prop'
BASE=PROP/'languages'
EN=PROP/'index.html'
SITEMAP=PROP/'sitemap.xml'
HOME=SITE/'design-preview-20261017/production-home-20261017.html'
PRIVATE=Path('/home/zomorod2/.private_mojplaywin_main_agents/mojprop_20_languages_20261121')
MANIFEST=PRIVATE/'receipt.json'
EXPECTED={
 str(EN):'c96c8f434c77682350deba12ba2916acc683779bfd345587944b699bad67c64c',
 str(SITEMAP):'9a28ab35f6e3940a80cbf7833b3495355cc524329e59506c44bd31f8996b769e',
 str(HOME):'9c891bd0ba42b19866db6c6cfc3867d3a26034eb116fefaa4d1226752eeac8b2'
}
L=json.loads(r'''[["zh","简体中文","MOJ PROP 模拟交易挑战与风险管理","了解以模拟账户开展的交易评估，学习如何在有限风险内记录和复盘交易，而不是追逐不切实际的收益承诺。","MOJ PROP 的公开介绍以模拟交易为核心。起始参考资金为 1,000 美元的虚拟余额；这不是可以提取或投入真实市场的客户资金。正式参与资格、规则和服务状态应以英文官方页面为准。","风险管理比单笔盈利更重要。举例来说，虚拟余额 1,000 美元的 1% 是 10 个模拟美元，3% 是 30 个模拟美元。交易前应写下入场依据、止损位置、最大可能损失，并检查每日及总回撤限制。","先阅读英文规则，再使用交易日志记录模拟订单，最后审查亏损、收益集中度与规则遵守情况。Starter30 是另一个单独说明的教育产品，不等于真实资金账户。","这是真实资金账户吗？不是。模拟挑战不意味着客户获得真实经纪商账户，也不保证利润或奖励。任何费用只能通过官网确认的服务器账单流程处理。","教育介绍，不构成投资建议或收益保证。当前购买条件和服务可用性以英文官方页面为准。","查看 MOJ PROP 英文官网"],["hi","हिन्दी","MOJ PROP सिम्युलेटेड ट्रेडिंग चुनौती और जोखिम प्रबंधन","नकली पूँजी वाले ट्रेडिंग मूल्यांकन को समझें, जहाँ उद्देश्य नियमों का पालन, जोखिम नियंत्रण और ट्रेडिंग डायरी बनाना है; सुनिश्चित लाभ का वादा नहीं।","MOJ PROP में 1,000 अमेरिकी डॉलर का प्रारंभिक वर्चुअल संदर्भ बैलेंस बताया गया है। यह ग्राहक का जमा धन या वास्तविक ब्रोकरेज खाता नहीं है। भागीदारी की शर्तें तथा उपलब्ध सेवाएँ आधिकारिक अंग्रेज़ी पृष्ठ पर जाँचें।","उदाहरण के लिए, 1,000 वर्चुअल डॉलर का 1% केवल 10 सिम्युलेटेड डॉलर है और 3% केवल 30 डॉलर। हर काल्पनिक सौदे से पहले प्रवेश कारण, स्टॉप-लॉस, संभावित हानि और दिन की अधिकतम गिरावट लिखें।","पहले नियम पढ़ें, फिर सिम्युलेटेड लेन-देन की डायरी रखें, उसके बाद हानि, लाभ की एकाग्रता और अनुशासन की समीक्षा करें। Starter30 का शैक्षिक उत्पाद मुख्य प्री-लॉन्च कार्यक्रम से अलग है।","क्या यह वास्तविक फंडेड अकाउंट है? नहीं। सिम्युलेशन से वास्तविक पूँजी, कमाई या पुरस्कार की गारंटी नहीं मिलती। भुगतान से पहले केवल आधिकारिक सर्वर-जनित इनवॉइस की पुष्टि करें।","यह शिक्षा के लिए है, निवेश सलाह या लाभ का आश्वासन नहीं। मौजूदा नियमों के लिए आधिकारिक अंग्रेज़ी संस्करण देखें।","MOJ PROP का आधिकारिक अंग्रेज़ी पृष्ठ खोलें"],["es","Español","MOJ PROP: desafío de trading simulado y gestión del riesgo","Descubre una evaluación de trading con capital virtual, diseñada para practicar disciplina, límites de pérdida y análisis de operaciones sin promesas de rentabilidad.","La propuesta de MOJ PROP parte de un saldo de referencia simulado de 1.000 USD. No se deposita capital del cliente ni se entrega automáticamente una cuenta real de bróker. La elegibilidad y el estado comercial se consultan en la página oficial en inglés.","Con 1.000 USD virtuales, un 1 % equivale a 10 USD simulados y un 3 % a 30 USD simulados. Antes de cada operación, registra el motivo de entrada, la invalidación, el nivel de salida y el riesgo acumulado. Una racha favorable no elimina los límites de pérdida.","Lee primero las reglas vigentes, registra tus decisiones en un diario y revisa las pérdidas diarias, la consistencia y las desviaciones. Starter30 es un producto educativo separado del programa principal anunciado.","¿Se opera con dinero real? No en la evaluación simulada. Ningún resultado garantiza beneficios, pagos o acceso a capital real. Si existe un pago disponible, utiliza solamente una factura verificada emitida por el servidor oficial.","Contenido informativo, no constituye asesoramiento de inversión. Las condiciones vinculantes y la disponibilidad se muestran en inglés.","Abrir la página oficial de MOJ PROP"],["ar","العربية الفصحى","MOJ PROP: تحدّي تداول مُحاكى وإدارة المخاطر","تعرّف على تقييم للتداول باستخدام رصيد افتراضي يركّز على الانضباط وتحديد الخسائر وتوثيق القرارات بعيداً عن الوعود بعوائد مضمونة.","يبدأ النموذج المُعلن لرصيد التقييم من ألف دولار افتراضي. هذا المبلغ ليس إيداعاً من العميل ولا حساب وساطة حقيقياً يُمنح تلقائياً. تُراجع شروط الأهلية وحالة الخدمات من خلال الصفحة الإنجليزية الرسمية.","للتوضيح، تساوي نسبة 1٪ من ألف دولار افتراضي عشرة دولارات محاكاة، وتساوي 3٪ ثلاثين دولاراً محاكاة. سجّل سبب الدخول ومستوى وقف الخسارة والحد الأقصى للخطر قبل كل صفقة، وراقب التراجع اليومي والإجمالي.","اطّلع على القواعد أولاً، ثم دوّن الصفقات الافتراضية، وراجع لاحقاً الانضباط والخسائر ومدى تركز النتائج. منتج Starter30 التعليمي منفصل عن برنامج التحدي الرئيسي قيد الإعلان.","هل هذا حساب ممول حقيقي؟ لا؛ التقييم افتراضي ولا يضمن أرباحاً أو مكافآت أو رأس مال فعلياً. لا تُرسل أي رسوم إلا عبر فاتورة رسمية صادرة من خادم الموقع بعد التحقق من توافر الخدمة.","هذه معلومات تعليمية وليست نصيحة استثمارية أو ضماناً للدخل؛ يُرجع إلى النص الإنجليزي الرسمي للشروط.","زيارة صفحة MOJ PROP الإنجليزية الرسمية"],["fr","Français","MOJ PROP : défi de trading simulé et gestion du risque","Découvrez une évaluation sur compte virtuel axée sur la discipline, la maîtrise des pertes et la tenue d’un journal de trading, sans promesse de rendement.","Le programme décrit un solde de référence virtuel de 1 000 USD. Il ne s’agit ni de fonds confiés par les clients ni de l’attribution automatique d’un compte réel de courtage. Les critères d’admission et la disponibilité doivent être vérifiés sur la page officielle anglaise.","Sur une base fictive de 1 000 USD, 1 % représente 10 USD simulés et 3 % représente 30 USD simulés. Avant toute opération, consignez la justification, le point d’invalidation, le risque maximal et les limites de perte quotidiennes.","Consultez d’abord les règles, entraînez-vous avec un journal d’opérations simulées, puis évaluez la régularité, les pertes et le respect du plan. Starter30 est une offre pédagogique distincte du programme principal annoncé.","S’agit-il d’un compte financé réel ? Non : l’évaluation est simulée et ne garantit ni bénéfice, ni paiement, ni accès à du capital réel. Ne payez que via une facture officielle générée par le serveur si le service est disponible.","Contenu éducatif, non un conseil financier. Les conditions et la disponibilité sont présentées dans la version officielle anglaise.","Consulter MOJ PROP en anglais"],["bn","বাংলা","MOJ PROP: সিমুলেটেড ট্রেডিং চ্যালেঞ্জ ও ঝুঁকি ব্যবস্থাপনা","ভার্চুয়াল মূলধন দিয়ে ট্রেডিং অনুশীলনের একটি মূল্যায়ন সম্পর্কে জানুন। এখানে গুরুত্বপূর্ণ বিষয় হলো নিয়মানুবর্তিতা, ক্ষতির সীমা এবং প্রতিটি সিদ্ধান্তের নথি রাখা।","MOJ PROP-এর বর্ণিত প্রাথমিক রেফারেন্স ব্যালান্স ১,০০০ মার্কিন ডলার, তবে এটি সম্পূর্ণ ভার্চুয়াল। গ্রাহকের জমা অর্থ বা স্বয়ংক্রিয়ভাবে দেওয়া প্রকৃত ব্রোকার অ্যাকাউন্ট নয়। অংশগ্রহণের যোগ্যতা ও সেবার অবস্থা ইংরেজি মূল পাতায় যাচাই করতে হবে।","উদাহরণস্বরূপ, ১,০০০ ভার্চুয়াল ডলারের ১ শতাংশ হলো ১০ সিমুলেটেড ডলার এবং ৩ শতাংশ হলো ৩০ ডলার। প্রতিটি অনুশীলনমূলক লেনদেনের আগে প্রবেশের কারণ, স্টপ-লস ও সম্ভাব্য ক্ষতি লিখুন। দৈনিক এবং সামগ্রিক ড্রডাউন পর্যবেক্ষণ করুন।","প্রথমে শর্ত পড়ুন, তারপর ট্রেডিং জার্নালে অনুশীলনের ফল লিখুন এবং শেষে ঝুঁকির নিয়ম মানা হয়েছে কি না পর্যালোচনা করুন। Starter30 আলাদা একটি শিক্ষামূলক পণ্য।","এটি কি বাস্তব অর্থের ফান্ডেড অ্যাকাউন্ট? না। অনুকরণভিত্তিক মূল্যায়ন থেকে মুনাফা, পুরস্কার বা প্রকৃত মূলধনের নিশ্চয়তা পাওয়া যায় না। কোনো ফি দেওয়ার আগে অফিসিয়াল সার্ভার-ইস্যু করা ইনভয়েস যাচাই করুন।","এটি কেবল শিক্ষামূলক তথ্য; বিনিয়োগ পরামর্শ বা নিশ্চিত আয়ের প্রতিশ্রুতি নয়। আনুষ্ঠানিক শর্ত ইংরেজি পাতায় দেখুন।","MOJ PROP-এর ইংরেজি মূল পাতা খুলুন"],["pt","Português","MOJ PROP: desafio de trading simulado e controle de risco","Conheça uma avaliação com saldo virtual voltada à disciplina, ao controle de perdas e ao registro de operações, sem promessas de lucro.","O programa apresenta um saldo virtual inicial de referência de US$ 1.000. Esse valor não corresponde a um depósito do cliente nem garante uma conta real de corretora. A elegibilidade, o regulamento e a disponibilidade devem ser confirmados na página oficial em inglês.","Em um exemplo de US$ 1.000 simulados, 1% significa US$ 10 virtuais e 3% significa US$ 30 virtuais. Antes de cada operação, registre o motivo de entrada, o stop, a perda possível e os limites de redução diária e total.","Leia as regras antes de participar, mantenha um diário de decisões e avalie as perdas, a concentração de resultados e a consistência. O Starter30 é um produto educacional separado do programa principal anunciado.","É uma conta financiada real? Não. A avaliação é simulada, sem garantia de lucros, pagamentos ou acesso a capital real. Utilize apenas faturas verificadas emitidas pelo servidor oficial, se o pagamento estiver disponível.","Material informativo, não é recomendação de investimento. Confira os termos atuais na página oficial em inglês.","Abrir o site oficial MOJ PROP"],["id","Bahasa Indonesia","MOJ PROP: tantangan trading simulasi dan manajemen risiko","Pelajari evaluasi trading dengan saldo virtual yang menekankan disiplin, pengendalian kerugian, dan jurnal transaksi tanpa janji keuntungan pasti.","Program MOJ PROP menjelaskan saldo referensi awal sebesar 1.000 dolar AS dalam bentuk virtual. Angka tersebut bukan dana nasabah yang disimpan dan bukan akun broker riil yang diberikan secara otomatis. Periksa persyaratan dan status layanan pada halaman resmi berbahasa Inggris.","Sebagai contoh, 1% dari 1.000 dolar virtual setara 10 dolar simulasi dan 3% setara 30 dolar simulasi. Sebelum membuka posisi, catat alasan masuk, batas kerugian, titik pembatalan strategi, serta penurunan harian dan keseluruhan.","Baca aturan terlebih dahulu, simpan jurnal trading simulasi, lalu tinjau kepatuhan, kerugian, dan konsistensi hasil. Starter30 adalah produk edukasi terpisah dari program utama yang masih diumumkan.","Apakah ini akun funded sungguhan? Tidak. Evaluasi simulasi tidak menjamin profit, pembayaran, atau akses ke modal riil. Jika pembayaran tersedia, gunakan hanya invoice resmi yang diterbitkan sistem situs.","Informasi edukatif, bukan saran investasi atau jaminan penghasilan. Ketentuan berlaku ada di halaman resmi bahasa Inggris.","Buka MOJ PROP versi Inggris"],["ur","اردو","MOJ PROP: نقلی تجارتی چیلنج اور رسک مینجمنٹ","ورچوئل بیلنس پر مبنی ٹریڈنگ کی جانچ کے بارے میں جانیں، جس میں نظم و ضبط، نقصان کی حد اور ہر فیصلے کا ریکارڈ اہم ہے، نہ کہ یقینی منافع کے دعوے۔","MOJ PROP میں ابتدائی حوالہ جاتی بیلنس ایک ہزار امریکی ڈالر ورچوئل بتایا گیا ہے۔ یہ صارف کی جمع کرائی ہوئی رقم نہیں اور نہ ہی خودکار طور پر حقیقی بروکر اکاؤنٹ فراہم کرتا ہے۔ اہلیت اور سروس کی دستیابی سرکاری انگریزی صفحے پر دیکھیں۔","مثال کے طور پر ایک ہزار ورچوئل ڈالر کا ایک فیصد دس نقلی ڈالر اور تین فیصد تیس نقلی ڈالر بنتا ہے۔ ہر مجازی ٹریڈ سے پہلے داخلے کی وجہ، اسٹاپ لاس، ممکنہ نقصان اور یومیہ مجموعی حد درج کریں۔","پہلے قواعد پڑھیں، پھر سمیولیٹڈ ٹریڈز کا جرنل رکھیں، اور آخر میں نقصان، مستقل مزاجی اور قواعد کی پابندی کا جائزہ لیں۔ Starter30 الگ تعلیمی پروڈکٹ ہے۔","کیا یہ حقیقی فنڈڈ اکاؤنٹ ہے؟ نہیں۔ نقلی جانچ سے منافع، ادائیگی یا حقیقی سرمایہ ملنے کی ضمانت نہیں۔ فیس صرف سرکاری سرور کی تصدیق شدہ انوائس کے ذریعے ادا کریں، اگر یہ سہولت دستیاب ہو۔","یہ مواد تعلیمی ہے، مالی مشورہ یا آمدنی کی ضمانت نہیں۔ موجودہ شرائط کے لیے سرکاری انگریزی صفحہ دیکھیں۔","MOJ PROP کا سرکاری انگریزی صفحہ دیکھیں"],["ru","Русский","MOJ PROP: симуляционная торговая задача и контроль риска","Узнайте о проверке торговой дисциплины на виртуальном балансе: с правилами ограничения убытков, журналом сделок и без обещаний гарантированной доходности.","В описании MOJ PROP используется стартовый виртуальный баланс 1 000 долларов США. Это не вклад клиента и не автоматически предоставляемый реальный брокерский счёт. Условия допуска и фактическую доступность услуги следует проверять на официальной англоязычной странице.","Для примера: 1% от 1 000 виртуальных долларов — 10 условных долларов, а 3% — 30 условных долларов. Перед каждой учебной сделкой фиксируйте причину входа, уровень стопа, возможный убыток и дневные ограничения просадки.","Сначала ознакомьтесь с правилами, затем ведите журнал операций в симуляторе и анализируйте потери, устойчивость результата и соблюдение лимитов. Starter30 — отдельный образовательный продукт.","Это реальный финансируемый счёт? Нет. Симуляция не гарантирует прибыль, выплаты или доступ к реальному капиталу. Платите только по проверенному счёту, созданному сервером официального сайта, если оплата доступна.","Материал носит учебный характер и не является инвестиционной рекомендацией. Актуальные условия опубликованы на английском языке.","Открыть официальную страницу MOJ PROP"],["de","Deutsch","MOJ PROP: simulierte Trading-Challenge und Risikomanagement","Informieren Sie sich über eine Trading-Evaluierung mit virtuellem Guthaben, dokumentierten Entscheidungen und Verlustgrenzen – ohne Gewinnversprechen.","MOJ PROP beschreibt einen virtuellen Start-Referenzsaldo von 1.000 US-Dollar. Das ist weder eine Kundeneinlage noch die automatische Bereitstellung eines echten Brokerkontos. Teilnahmevoraussetzungen und tatsächliche Verfügbarkeit stehen auf der offiziellen englischen Seite.","Zur Veranschaulichung: 1 % von 1.000 virtuellen Dollar entsprechen 10 simulierten Dollar, 3 % entsprechen 30. Dokumentieren Sie vor jedem Übungstrade Einstiegssignal, Stop-Loss, mögliches Verlustrisiko sowie tägliche und gesamte Drawdown-Grenzen.","Lesen Sie zunächst das aktuelle Regelwerk, führen Sie anschließend ein Journal und prüfen Sie danach Verluste, Ergebniskonzentration und Regelkonformität. Starter30 ist ein gesondertes Bildungsprodukt.","Handelt es sich um ein echtes finanziertes Konto? Nein. Die Simulation garantiert weder Gewinne noch Auszahlungen oder reales Handelskapital. Zahlungen dürfen nur über eine verifizierte, vom offiziellen Server erstellte Rechnung erfolgen, sofern verfügbar.","Reine Bildungsinformation, keine Anlageberatung oder Renditezusage. Maßgeblich sind die aktuellen englischen Bedingungen.","Offizielle englische MOJ PROP-Seite öffnen"],["ja","日本語","MOJ PROP：模擬トレードチャレンジとリスク管理","仮想資金を使うトレード評価の仕組みを解説します。重要なのは利益の保証ではなく、損失制限、取引記録、判断の一貫性です。","MOJ PROP が示す開始時の参考残高は1,000米ドル相当の仮想残高です。顧客から預かった資金や、自動的に提供される実際の証券・FX口座ではありません。参加条件とサービス提供状況は公式英語ページで確認してください。","例えば仮想残高1,000ドルの1％は模擬上の10ドル、3％は30ドルです。各取引の前に、エントリー理由、損切り水準、想定損失、日次および累計のドローダウンを記録します。","まず最新のルールを読み、模擬取引の日誌を作成し、損失・収益の偏り・ルール遵守を振り返ります。Starter30は主な事前案内プログラムとは別の教育商品です。","これは実資金の運用口座ですか。いいえ。模擬評価は利益、報酬の支払い、実資金へのアクセスを保証しません。料金の支払いは、提供中の場合に限り、公式サーバーが発行した請求書で確認してください。","教育目的の情報であり、投資助言または利益保証ではありません。正式条件は英語版をご確認ください。","MOJ PROP 英語公式ページを見る"],["pcm","Naijá Pidgin","MOJ PROP: trading challenge wey na simulation","Learn how virtual trading challenge dey work: you go practise how to control loss, write wetin happen for each trade and follow rules. Nobody dey promise sure profit.","For MOJ PROP, di starting reference balance na $1,000 virtual money. E no be customer deposit and e no mean say dem don give you real broker account. Check di official English page to sabi who fit join and whether any service don open.","For example, 1% of $1,000 virtual balance na $10 for simulation; 3% na $30. Before you enter any practice trade, write why you wan enter, where you go stop if market turn, and how much you fit lose. No forget daily loss limit.","Read di rules first. Keep trading journal for your practice positions, then check your losses and whether you follow your own plan. Starter30 na separate learning product; e no be the same thing as di main programme.","Na real funded trading account? No. This simulation no guarantee profit, reward or real trading capital. If dem open payment, use only correct invoice wey di official website server generate. No send money anyhow.","Na information for learning, no be investment advice or promise of earnings. Official terms dey di English page.","Open MOJ PROP official English page"],["ar-EG","العربية المصرية","MOJ PROP: تحدّي تداول تجريبي وإدارة مخاطرة","اعرف فكرة تقييم التداول بحساب افتراضي، وازاي تتابع خسارتك وتدوّن قراراتك بدل الاعتماد على وعود مكسب مضمون.","برنامج MOJ PROP بيشرح رصيد بداية مرجعي قيمته ألف دولار افتراضي. ده مش فلوس العميل ومش معناه إنك هتاخد حساب وساطة حقيقي بشكل تلقائي. لازم تراجع شروط المشاركة وحالة الخدمة من الصفحة الإنجليزية الرسمية.","كمثال بسيط، 1٪ من ألف دولار افتراضي يساوي عشرة دولارات في المحاكاة، و3٪ يساوي تلاتين دولار. قبل كل صفقة تدريب اكتب سبب الدخول، وقف الخسارة، وأقصى خسارة ممكنة، وخلي بالك من حدود التراجع اليومي والإجمالي.","اقرا القواعد الأول، وسجّل صفقاتك التجريبية في دفتر متابعة، وبعدها راجع الالتزام والخسائر وانتظام النتائج. Starter30 منتج تعليمي منفصل عن البرنامج الأساسي المعلن.","هو ده حساب ممول حقيقي؟ لأ. التحدي تجريبي ومفيش ضمان أرباح أو مدفوعات أو وصول لرأس مال حقيقي. لو الدفع متاح استخدم بس فاتورة موثقة طالعة من سيرفر الموقع الرسمي.","المحتوى للتعليم مش نصيحة استثمارية ولا وعد بدخل. الشروط الرسمية الحالية موجودة بالإنجليزي.","افتح صفحة MOJ PROP الإنجليزية الرسمية"],["mr","मराठी","MOJ PROP: सिम्युलेटेड ट्रेडिंग आव्हान आणि जोखीम व्यवस्थापन","आभासी भांडवलावर आधारित ट्रेडिंग मूल्यमापनाची माहिती घ्या. येथे निश्चित नफा मिळवण्यापेक्षा तोट्याच्या मर्यादा, व्यवहारांची नोंद आणि शिस्त महत्त्वाची आहे.","MOJ PROP मध्ये सुरुवातीचा संदर्भ शिल्लक १,००० अमेरिकी डॉलर आभासी स्वरूपात दाखवला आहे. ही ग्राहकाची ठेव नाही किंवा आपोआप मिळणारे प्रत्यक्ष ब्रोकरेज खाते नाही. पात्रता आणि सेवा सुरू आहे का हे अधिकृत इंग्रजी पानावर तपासा.","उदाहरणार्थ, १,००० आभासी डॉलरचे १ टक्के म्हणजे १० सिम्युलेटेड डॉलर आणि ३ टक्के म्हणजे ३० डॉलर. प्रत्येक सराव व्यवहाराआधी प्रवेशाचे कारण, स्टॉप-लॉस, संभाव्य तोटा आणि रोजच्या घटेची मर्यादा लिहा.","सर्वप्रथम नियम वाचा, नंतर सराव व्यवहारांची वही ठेवा आणि शेवटी नुकसान, सातत्य आणि नियमांचे पालन तपासा. Starter30 हा मुख्य प्रस्तावित कार्यक्रमापासून वेगळा शैक्षणिक पर्याय आहे.","हे खरे फंडेड खाते आहे का? नाही. या सिम्युलेशनमध्ये नफा, पैसे मिळणे किंवा प्रत्यक्ष भांडवल याची हमी नाही. पैसे भरण्याची सुविधा उपलब्ध असल्यास फक्त अधिकृत सर्व्हरने तयार केलेल्या पडताळलेल्या पावतीद्वारे भरा.","हा मजकूर शिक्षणासाठी आहे; गुंतवणूक सल्ला किंवा कमाईची हमी नाही. लागू अटी इंग्रजी पानावर आहेत.","MOJ PROP चे अधिकृत इंग्रजी पान उघडा"],["vi","Tiếng Việt","MOJ PROP: thử thách giao dịch mô phỏng và quản trị rủi ro","Tìm hiểu cách đánh giá kỷ luật giao dịch bằng số dư ảo, ghi nhật ký lệnh và giới hạn thua lỗ, thay vì dựa vào những lời hứa lợi nhuận chắc chắn.","MOJ PROP mô tả số dư tham chiếu ban đầu là 1.000 USD ảo. Đây không phải tiền khách hàng gửi vào và cũng không đồng nghĩa với việc tự động nhận tài khoản môi giới có tiền thật. Điều kiện tham gia và trạng thái dịch vụ cần được kiểm tra trên trang chính thức bằng tiếng Anh.","Ví dụ, 1% của 1.000 USD ảo là 10 USD mô phỏng và 3% là 30 USD mô phỏng. Trước mỗi lệnh thực hành, hãy ghi lý do vào lệnh, mức cắt lỗ, khoản lỗ tối đa dự kiến và giới hạn sụt giảm trong ngày.","Trước tiên đọc các quy tắc hiện hành, sau đó ghi nhật ký giao dịch mô phỏng và đánh giá mức độ tuân thủ, thua lỗ, sự ổn định của kết quả. Starter30 là sản phẩm giáo dục riêng biệt.","Đây có phải tài khoản cấp vốn thật không? Không. Đánh giá mô phỏng không bảo đảm lợi nhuận, khoản thanh toán hay quyền tiếp cận vốn thật. Chỉ sử dụng hóa đơn hợp lệ do máy chủ trang chính thức phát hành nếu hệ thống thanh toán khả dụng.","Thông tin dành cho giáo dục, không phải tư vấn đầu tư hay cam kết thu nhập. Điều khoản chính thức bằng tiếng Anh được ưu tiên.","Mở trang MOJ PROP tiếng Anh chính thức"],["te","తెలుగు","MOJ PROP: అనుకరణ ట్రేడింగ్ సవాలు మరియు రిస్క్ నిర్వహణ","వర్చువల్ బ్యాలెన్స్‌తో చేసే ట్రేడింగ్ మూల్యాంకనాన్ని తెలుసుకోండి. ఖచ్చితమైన లాభాల హామీల కంటే నష్ట పరిమితులు, క్రమశిక్షణ, ప్రతి ట్రేడ్‌ను నమోదు చేయడం ముఖ్యం.","MOJ PROPలో ప్రారంభ సూచన బ్యాలెన్స్ 1,000 అమెరికన్ డాలర్లు వర్చువల్ రూపంలో ఉంటుంది. ఇది కస్టమర్ జమ చేసిన డబ్బు కాదు; నిజమైన బ్రోకర్ ఖాతా ఆటోమేటిక్‌గా లభిస్తుందని అర్థం కూడా కాదు. అర్హత, సేవ అందుబాటులో ఉందో లేదో అధికారిక ఇంగ్లీష్ పేజీలో చూడండి.","ఉదాహరణకు 1,000 వర్చువల్ డాలర్లలో 1 శాతం అంటే 10 అనుకరణ డాలర్లు, 3 శాతం అంటే 30 అనుకరణ డాలర్లు. ప్రతి సాధన ట్రేడ్‌కు ముందు ప్రవేశ కారణం, స్టాప్‌లాస్, సాధ్యమైన నష్టం, రోజువారీ డ్రాడౌన్ పరిమితిని రాసుకోండి.","ముందుగా నియమాలు చదవండి. తర్వాత అనుకరణ ట్రేడింగ్ జర్నల్‌లో వివరాలు నమోదు చేసి, నష్టాలు, ఫలితాల స్థిరత్వం, నియమాల పాటింపును సమీక్షించండి. Starter30 ప్రధాన ప్రోగ్రామ్‌కు భిన్నమైన విద్యా ఉత్పత్తి.","ఇది నిజమైన ఫండెడ్ ఖాతానా? కాదు. ఈ సిమ్యులేషన్ లాభాలు, చెల్లింపులు లేదా నిజమైన మూలధనాన్ని హామీ ఇవ్వదు. చెల్లింపు అందుబాటులో ఉంటే అధికారిక సర్వర్ రూపొందించిన ధృవీకరిత ఇన్వాయిస్ మాత్రమే ఉపయోగించండి.","ఇది విద్యాపరమైన సమాచారం మాత్రమే; పెట్టుబడి సలహా లేదా ఆదాయ హామీ కాదు. పూర్తి అధికారిక నిబంధనలు ఇంగ్లీష్ పేజీలో ఉంటాయి.","MOJ PROP అధికారిక ఇంగ్లీష్ పేజీ"],["sw","Kiswahili","MOJ PROP: changamoto ya biashara ya majaribio na udhibiti wa hatari","Jifunze tathmini ya biashara ya masoko inayotumia salio pepe. Lengo ni nidhamu, kuweka kumbukumbu na kudhibiti hasara, si ahadi ya faida ya uhakika.","MOJ PROP inaeleza salio la kuanzia la marejeo la dola 1,000 za Marekani katika mfumo wa pepe. Hii si amana ya mteja wala akaunti halisi ya dalali inayotolewa moja kwa moja. Masharti ya ushiriki na upatikanaji wa huduma yapo kwenye ukurasa rasmi wa Kiingereza.","Kwa mfano, asilimia 1 ya dola 1,000 pepe ni dola 10 za majaribio, na asilimia 3 ni dola 30 za majaribio. Kabla ya kila biashara ya mazoezi, andika sababu ya kuingia, kiwango cha kusitisha hasara, hasara inayowezekana na mipaka ya kushuka kwa salio.","Soma kanuni kwanza, rekodi biashara za majaribio kwenye daftari, kisha kagua hasara, uthabiti na uzingatiaji wa mipaka. Starter30 ni bidhaa tofauti ya elimu, si programu kuu iliyo katika hatua ya utangulizi.","Je, hii ni akaunti halisi yenye mtaji? Hapana. Tathmini ya majaribio haitoi dhamana ya faida, malipo au mtaji halisi. Ikiwa malipo yanapatikana, tumia ankara halali inayotolewa na seva rasmi pekee.","Maelezo haya ni ya elimu, si ushauri wa uwekezaji wala ahadi ya mapato. Angalia masharti rasmi katika ukurasa wa Kiingereza.","Fungua ukurasa rasmi wa MOJ PROP kwa Kiingereza"],["tr","Türkçe","MOJ PROP: simülasyon işlem meydan okuması ve risk yönetimi","Sanal bakiye ile yapılan işlem değerlendirmesini keşfedin. Odak noktası garantili kazanç değil; zarar sınırları, işlem günlüğü ve disiplinli karar almaktır.","MOJ PROP, başlangıç referansı olarak 1.000 ABD doları tutarında sanal bakiye açıklar. Bu, müşteriden alınan bir mevduat veya otomatik sağlanan gerçek aracı kurum hesabı değildir. Katılım koşulları ve hizmet durumu resmi İngilizce sayfadan kontrol edilmelidir.","Örneğin 1.000 sanal doların %1'i 10, %3'ü 30 simülasyon dolarıdır. Her deneme işlemi öncesinde giriş gerekçesini, zarar durdurma noktasını, olası kaybı ve günlük toplam düşüş sınırlarını yazın.","Önce güncel kuralları okuyun, ardından simülasyon işlemlerini günlüğe kaydedin ve kayıpları, sonuçların tutarlılığını ve kurallara uyumu değerlendirin. Starter30, duyurulan ana programdan ayrı bir eğitim ürünüdür.","Bu gerçek fonlu hesap mı? Hayır. Simülasyon; kâr, ödeme veya gerçek sermayeye erişim garantisi vermez. Ödeme açıksa yalnızca resmi sunucunun oluşturduğu doğrulanmış faturayı kullanın.","Bu içerik eğitim amaçlıdır; yatırım tavsiyesi veya gelir garantisi değildir. Geçerli koşullar resmi İngilizce sayfadadır.","MOJ PROP resmi İngilizce sayfasını aç"]]''')
URL='https://mojplaywin.com'
VALID=['en','zh','hi','es','ar','fr','bn','pt','id','ur','ru','de','ja','ar-EG','mr','vi','te','sw','tr']
NAMES={'en':'English','zh':'简体中文','hi':'हिन्दी','es':'Español','ar':'العربية','fr':'Français','bn':'বাংলা','pt':'Português','id':'Bahasa Indonesia','ur':'اردو','ru':'Русский','de':'Deutsch','ja':'日本語','pcm':'Naijá Pidgin','ar-EG':'مصرى','mr':'मराठी','vi':'Tiếng Việt','te':'తెలుగు','sw':'Kiswahili','tr':'Türkçe'}

def sha(b): return hashlib.sha256(b).hexdigest()
def path(code): return '/moj-prop/' if code=='en' else '/moj-prop/languages/'+code.lower()+'/'
def esc(s):return html.escape(s,quote=True)
def once(s,a,b):
 n=s.count(a)
 if n!=1:raise RuntimeError('Unexpected anchor count='+str(n)+' '+a[:85])
 return s.replace(a,b,1)
def atom(p,data,mode=0o644):
 temp=None
 try:
  with tempfile.NamedTemporaryFile('wb',dir=p.parent,prefix='.mojprop-l10n-',delete=False) as f:
   temp=Path(f.name);f.write(data);f.flush();os.fsync(f.fileno())
  os.chmod(temp,mode)
  os.replace(temp,p)
 finally:
  if temp and temp.exists():temp.unlink()

def hreflangs():
 return '\n'.join('<link rel="alternate" hreflang="'+c+'" href="'+URL+path(c)+'">' for c in VALID)+'\n<link rel="alternate" hreflang="x-default" href="'+URL+'/moj-prop/">'
def links():
 return '\n'.join('<a href="'+path(code)+'" lang="'+code+'"'+(' aria-current="page"' if code=='en' else '')+'>'+esc(NAMES[code])+'</a>' for code in NAMES)
def localized(item):
 code,name,title,lead,about,risk,steps,faq,notice,cta=item
 code_html=code
 langdir='rtl' if code in ('ar','ar-EG','ur') else 'ltr'
 canonical=URL+path(code)
 desc=lead[:158].rstrip(' ,.')
 schema=json.dumps({'@context':'https://schema.org','@type':'WebPage','name':title,'url':canonical,'inLanguage':code,'description':desc,'about':{'@type':'Thing','name':'Simulated trading evaluation and risk education'}},ensure_ascii=False,separators=(',',':'))
 return ('''<!doctype html>
<html lang="'''+esc(code_html)+'''" dir="'''+langdir+'''">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>'''+esc(title)+''' | MOJ PROP</title>
<meta name="description" content="'''+esc(desc)+'''">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="'''+canonical+'''">
<meta property="og:type" content="article">
<meta property="og:title" content="'''+esc(title)+''' | MOJ PROP">
<meta property="og:description" content="'''+esc(desc)+'''">
<meta property="og:url" content="'''+canonical+'''">
<meta name="twitter:card" content="summary">
'''+(hreflangs() if code!='pcm' else '')+'''
<script type="application/ld+json">'''+schema+'''</script>
<style>
:root{color-scheme:dark;--gold:#e3c185;--ink:#f4eee4;--muted:#c8c6c1;--line:rgba(227,193,133,.38)}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 85% 5%,rgba(179,126,45,.15),transparent 45%),#090e14;color:var(--ink);font:16px/1.8 system-ui,Arial,sans-serif}
a{color:var(--gold)}.wrap{width:min(1040px,calc(100% - 38px));margin:auto}
header{padding:24px 0;display:flex;align-items:center;justify-content:space-between;gap:15px;border-bottom:1px solid var(--line)}
header strong{letter-spacing:.15em;color:var(--gold)}header a{text-decoration:none;font-weight:700}
main{padding:55px 0}.eyebrow{color:var(--gold);font-size:12px;font-weight:800;letter-spacing:.12em}
h1{font-size:clamp(32px,5vw,58px);line-height:1.25;letter-spacing:-.03em;margin:15px 0 22px;max-width:920px}
.lead{font-size:clamp(17px,2.2vw,22px);color:#e8e0d1;max-width:850px}
.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:30px 0}
.summary>div,.box{border:1px solid var(--line);border-radius:18px;background:rgba(22,31,41,.84);padding:clamp(19px,3vw,30px)}
.summary b{display:block;color:#f8dca0;font-size:clamp(24px,3vw,38px);line-height:1.3}.summary span{color:var(--muted);font-size:13px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:17px}
.box{margin:10px 0}.box h2{margin:0 0 15px;color:var(--gold);font-size:clamp(20px,2.7vw,26px);line-height:1.3}.box p{margin:0;color:#e0ddd6}
.actions{display:flex;flex-wrap:wrap;gap:12px;margin:26px 0}
.cta{background:linear-gradient(115deg,#ffe5a8,#c69b55);color:#151310;padding:14px 22px;border-radius:12px;text-decoration:none;font-weight:850}
.secondary{border:1px solid var(--gold);padding:13px 20px;border-radius:12px;text-decoration:none}
.notice{border-inline-start:4px solid var(--gold);padding:13px 17px;background:rgba(211,160,73,.08);font-size:14px;color:#dcd2c0}
.languages{display:flex;flex-wrap:wrap;gap:7px;margin:22px 0 0}
.languages a{border:1px solid #6b5a3e;border-radius:9px;padding:4px 9px;font-size:13px;text-decoration:none}
.languages a[aria-current=page]{background:#e3c185;color:#10151a}
footer{border-top:1px solid var(--line);padding:26px 0 46px;color:var(--muted);font-size:13px}
a:focus-visible{outline:3px solid white;outline-offset:3px}
@media(max-width:650px){.summary,.grid{grid-template-columns:1fr}}
</style>
</head><body>
<div class="wrap">
<header><strong>MOJ PROP · MOJPLAYWIN</strong><a href="/moj-prop/">Official English program</a></header>
<main>
<span class="eyebrow">MOJ PROP · '''+esc(name)+''' · SIMULATED TRADING EDUCATION</span>
<h1>'''+esc(title)+'''</h1>
<p class="lead">'''+esc(lead)+'''</p>
<div class="summary" aria-label="Example reference metrics">
<div><b>60</b><span>Day simulation reference</span></div>
<div><b>$1,000</b><span>Virtual reference balance</span></div>
<div><b>1% = $10</b><span>Illustrative demo risk</span></div>
</div>
<div class="grid">
<section class="box"><h2>01 / MOJ PROP</h2><p>'''+esc(about)+'''</p></section>
<section class="box"><h2>02 / Risk &amp; drawdown</h2><p>'''+esc(risk)+'''</p></section>
<section class="box"><h2>03 / How to prepare</h2><p>'''+esc(steps)+'''</p></section>
<section class="box"><h2>04 / Before you join</h2><p>'''+esc(faq)+'''</p></section>
</div>
<div class="actions"><a class="cta" href="/moj-prop/">'''+esc(cta)+''' →</a><a class="secondary" href="/moj-prop/starter-30-trx/">Starter30 · English terms</a></div>
<p class="notice">'''+esc(notice)+'''</p>
<h2>20 languages · choose another version</h2>
<nav class="languages" aria-label="Choose language">
'''+''.join('<a href="'+path(c)+'" lang="'+c+'"'+(' aria-current="page"' if c==code else '')+'>'+esc(NAMES[c])+'</a>' for c in NAMES)+'''
</nav>
</main>
<footer>MOJ PROP · MojPlayWin · Educational information · The English official page governs program availability and terms.</footer>
</div></body></html>
''')

def directory_page():
 ss=''.join('<a href="'+path(c)+'" lang="'+c+'">'+esc(n)+'</a> ' for c,n in NAMES.items())
 return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MOJ PROP in 20 Languages | Trading Simulation Education</title><meta name="description" content="Choose one of 20 languages for MOJ PROP simulated trading education and risk management. Official program details remain in English."><meta name="robots" content="index,follow"><link rel="canonical" href="https://mojplaywin.com/moj-prop/languages/"><style>body{font:17px/1.8 system-ui;background:#0a1018;color:#f5eddc;margin:0}main{max-width:900px;margin:6vw auto;padding:30px}a{color:#ffe1a1;display:inline-block;padding:9px 14px;margin:6px;border:1px solid #8e764d;border-radius:12px}h1{font-size:clamp(27px,4vw,46px)}p{color:#ded6c6}</style></head><body><main><a href="/moj-prop/">MOJ PROP official English</a><h1>MOJ PROP simulated trading: 20 language editions</h1><p>Explore localized explanations of virtual trading evaluations and risk discipline. These are educational introductions, not offers of a funded account. The official English page explains current eligibility, terms and payment status.</p><nav aria-label="Languages">'''+ss+'''</nav><p>No guaranteed profits or trading access. Refer to the English program terms before making any purchase decision.</p></main></body></html>'''

def prepare():
 if len(L)!=19 or {x[0] for x in L}!={c for c in NAMES if c!='en'}:raise RuntimeError('Wrong locale coverage')
 if len(VALID)!=19 or 'pcm' in VALID or 'ar-EG' not in VALID:raise RuntimeError('Invalid hreflang cluster')
 src={}
 for p,h in EXPECTED.items():
  q=Path(p)
  if q.is_symlink() or not q.is_file() or sha(q.read_bytes())!=h:
   raise RuntimeError('SOURCE_DRIFT_OR_UNSAFE '+p)
  src[p]=q.read_text()
 if BASE.exists():raise RuntimeError('Language directory already exists; no overwrite')
 eng=src[str(EN)]
 eng=once(eng,'<link rel="canonical" href="https://mojplaywin.com/moj-prop/">','<link rel="canonical" href="https://mojplaywin.com/moj-prop/">\n'+hreflangs())
 english_nav='<div id="mojprop-languages-entry-20261121" style="max-width:1240px;margin:12px auto;padding:14px 28px;border:1px solid #7a663e;border-radius:12px;background:#121b24;color:#f2d59d"><strong>MOJ PROP worldwide:</strong> <a href="/moj-prop/" lang="en" aria-current="page" style="color:#f9d38a;text-decoration:underline">English</a> · <a href="/moj-prop/languages/" style="color:#f9d38a;text-decoration:underline">Read in 20 languages</a> · The official English terms and payment status apply.</div>\n'
 eng=once(eng,'<body>', '<body>\n'+english_nav)
 if eng.count('id="mojprop-languages-entry-20261121"')!=1:raise RuntimeError('English nav failed')
 sitemap=src[str(SITEMAP)]
 if sitemap.count('</urlset>')!=1:raise RuntimeError('Unrecognized sitemap')
 newxml=''.join('<url><loc>'+URL+path(code)+'</loc></url>' for code in [x[0] for x in L])
 newxml+='<url><loc>'+URL+'/moj-prop/languages/</loc></url>'
 sitemap=once(sitemap,'</urlset>',newxml+'</urlset>')
 homepage=src[str(HOME)]
 old='<a class="mpw-mojprop-secondary" href="/moj-prop/starter-30-trx/">Read Starter30 terms</a>'
 homepage=once(homepage,old,old+'\n      <a class="mpw-mojprop-secondary" href="/moj-prop/languages/">MOJ PROP · 20 languages</a>')
 mapping={EN:eng.encode(),SITEMAP:sitemap.encode(),HOME:homepage.encode(),BASE/'index.html':directory_page().encode()}
 for item in L:
  file=BASE/item[0].lower()/'index.html'
  data=localized(item).encode()
  if len(data)<3100 or len(data)>14000:raise RuntimeError('Unreasonable page size '+str(file))
  if b'html' not in data or b'canonical' not in data:raise RuntimeError('Page malformed '+str(file))
  mapping[file]=data
 return mapping

def apply():
 import getpass
 if getpass.getuser()!='zomorod2':raise RuntimeError('Wrong account')
 if not PROP.is_dir() or PROP.is_symlink():raise RuntimeError('Unsafe root')
 mapping=prepare()
 print('PREPARED',len(mapping),'FILES',len(L),'LOCALIZED','SIZE',sum(len(x) for x in mapping.values()))
 if sys.argv[1]=='--check':return
 if sys.argv[1]!='--apply':raise RuntimeError('Unknown mode')
 if PRIVATE.exists():raise RuntimeError('Do not reuse backup folder')
 PRIVATE.mkdir(parents=True,mode=0o700)
 os.chmod(PRIVATE,0o700)
 original={str(p):{'sha':sha(p.read_bytes()),'size':p.stat().st_size} for p in (EN,SITEMAP,HOME)}
 for i,p in enumerate((EN,SITEMAP,HOME)):
  b=PRIVATE/('original_'+str(i)+'.bin')
  b.write_bytes(p.read_bytes())
  os.chmod(b,0o600)
  if sha(b.read_bytes())!=original[str(p)]['sha']:raise RuntimeError('Backup verification failed')
 receipt={'original':original,'after':{str(p):sha(d) for p,d in mapping.items()},'new_directories':[str(BASE)],'status':'prepared'}
 MANIFEST.write_text(json.dumps(receipt,indent=2)+'\n')
 os.chmod(MANIFEST,0o600)
 staged=PRIVATE/'staged'
 staged.mkdir(mode=0o700)
 for p,data in mapping.items():
  if p in (EN,SITEMAP,HOME):continue
  rel=p.relative_to(BASE)
  dest=staged/rel
  dest.parent.mkdir(parents=True,exist_ok=True)
  dest.write_bytes(data)
  if sha(dest.read_bytes())!=sha(data):raise RuntimeError('Stage mismatch')
 for p in (EN,SITEMAP,HOME):
  if sha(p.read_bytes())!=original[str(p)]['sha']:raise RuntimeError('Concurrent change; reject')
 try:
  BASE.mkdir(mode=0o755)
  for p in [k for k in mapping if k not in (EN,SITEMAP,HOME)]:
   p.parent.mkdir(parents=True,mode=0o755,exist_ok=True)
   atom(p,(staged/p.relative_to(BASE)).read_bytes())
  for p in (EN,SITEMAP,HOME):
   atom(p,mapping[p],stat.S_IMODE(p.stat().st_mode))
  for p,data in mapping.items():
   if sha(p.read_bytes())!=sha(data):raise RuntimeError('SHA verification failed '+str(p))
  receipt['status']='published'
  MANIFEST.write_text(json.dumps(receipt,indent=2)+'\n')
  print('PUBLISHED',len(L),'LOCALE_PAGES','ENGLISH_HREFLANG','OK','BACKUP','VERIFIED')
 except Exception:
  for i,p in enumerate((EN,SITEMAP,HOME)):
   if sha((PRIVATE/('original_'+str(i)+'.bin')).read_bytes())==original[str(p)]['sha']:
    atom(p,(PRIVATE/('original_'+str(i)+'.bin')).read_bytes())
  raise

if __name__=='__main__':
 if len(sys.argv)!=2:raise SystemExit('Usage --check|--apply')
 apply()
