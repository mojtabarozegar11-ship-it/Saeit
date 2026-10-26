<?php
declare(strict_types=1);
$home=dirname(__DIR__,2);
$private=$home.'/.private/zomorod-business';
$lib=$private.'/site_store.php';
header('Content-Type: text/html; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: public, max-age=60');
if(!is_file($lib)){http_response_code(503);echo 'Store module is not available';exit;}
require_once $lib;
try{$db=zmStoreDb($private);$items=$db->query('SELECT title,description,price_irr,sku FROM products WHERE enabled=1 ORDER BY id DESC LIMIT 100')->fetchAll();$free=$db->query('SELECT title,description,sku,download_path,artifact_sha256,license_text FROM free_digital_products WHERE enabled=1 ORDER BY id DESC LIMIT 100')->fetchAll();}
catch(Throwable $e){http_response_code(503);echo 'Store temporarily unavailable';exit;}
function storeEsc(string $x):string{return htmlspecialchars($x,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
echo '<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="/favicon.ico"><meta name="description" content="فروشگاه محصولات و خدمات واقعی شرکت کشت و صنعت زمرد ملل"><title>فروشگاه زمرد ملل | Zomorod Mell</title><style>:root{font-family:Tahoma,Arial,sans-serif;color-scheme:dark}body{margin:0;min-height:100vh;background:#203b23;color:#f2efdb}header,footer{background:#172e1c;padding:18px 5%;border-bottom:1px solid #bfaa67}header img{width:50px;height:50px;vertical-align:middle}main{margin:auto;max-width:1150px;padding:24px 16px}h1,h2{color:#efcf7e}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(255px,1fr));gap:15px}article,section{background:#284b31;border:1px solid #c6ab67;border-radius:16px;padding:20px;margin:12px 0}article p{line-height:1.9}a{color:#ffdf8c}.muted{color:#cbd6c8}</style></head><body><header><a href="/"><img src="/static/site/zomorod-v7/company-logo.webp" alt="لوگوی رسمی شرکت"></a> شرکت کشت و صنعت زمرد ملل — فروشگاه</header><main><h1>فروشگاه محصولات زمرد ملل</h1><section><h2>پرداخت بانک شهر</h2><p>اتصال درگاه بانک شهر در انتظار فعال‌سازی پذیرندگی و آزمون تسویه است. <strong>در این وضعیت خرید آنلاین و برداشت وجه غیرفعال است.</strong> محصولات فعال برای معرفی نمایش داده می‌شوند.</p><a href="/contact/">تماس با شرکت</a></section><div class="grid">';
if(!$items && !$free) echo '<section><h2>کاتالوگ در حال تکمیل</h2><p>هنوز محصول آماده عرضه عمومی ثبت نشده است؛ پس از تأیید محصول در پنل مدیریت، این بخش خودکار تکمیل می‌شود.</p></section>';

foreach($free as $p){
 $url=(string)$p['download_path'];$sha=(string)$p['artifact_sha256'];
 if(!preg_match('#^/store/free-products/[a-z0-9-]+/index\\.html$#',$url)||!preg_match('/^[0-9a-f]{64}$/',$sha))continue;
 echo '<article><h2>'.storeEsc((string)$p['title']).'</h2><p>'.nl2br(storeEsc((string)$p['description'])).'</p><strong>رایگان — بدون پرداخت</strong><p><a href="'.storeEsc($url).'" download rel="noopener">دریافت ابزار دیجیتال آفلاین</a> · <a href="'.storeEsc($url).'">اجرای آنلاین</a></p><p class="muted">شناسه: '.storeEsc((string)$p['sku']).' | مجوز: '.storeEsc((string)$p['license_text']).'</p><small class="muted">SHA-256: '.storeEsc($sha).'</small></article>';
}
foreach($items as $p){echo '<article><h2>'.storeEsc($p['title']).'</h2><p>'.nl2br(storeEsc($p['description'])).'</p><strong>قیمت: '.number_format((int)$p['price_irr']).' ریال</strong><p class="muted">کد: '.storeEsc($p['sku']).'</p><p class="muted">پرداخت آنلاین تا اتصال درگاه غیرفعال است.</p></article>';}
echo '</div><section id="zm-company-official-contacts"><h2>اطلاعات تماس رسمی شرکت</h2><p>شماره تماس برای ارتباطات فضای مجازی: <a href="tel:+989022048691" dir="ltr">۰۹۰۲۲۰۴۸۶۹۱</a></p><p>نشانی دفتر: استان فارس، شهرستان مرودشت، خیابان قدس، کوچه ۹۲، ساختمان گل‌یخ</p></section></main><footer>تمام حقوق مادی و معنوی سایت برای شرکت کشت و صنعت زمرد ملل محفوظ است . آبان ۱۳۹۸ مجتبی روزگار</footer></body></html>';