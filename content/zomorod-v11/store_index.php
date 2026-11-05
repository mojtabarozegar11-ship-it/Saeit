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
echo <<<'STORE_HEADER'
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="/favicon.ico">
<link rel="canonical" href="https://zomorodmelal.ir/store/">
<meta name="description" content="فروشگاه محصولات و خدمات واقعی شرکت کشت و صنعت زمرد ملل">
<title>فروشگاه زمرد ملل | Zomorod Melal</title>
<style>
:root{font-family:Tahoma,"Vazirmatn","Segoe UI",Arial,sans-serif;color-scheme:dark}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;min-height:100vh;background:radial-gradient(ellipse at top,#2c5035 0,#182d20 47%,#102418 100%);color:#f2efdb}
a{color:#ffdf8c;text-underline-offset:3px}
a:focus-visible{outline:3px solid #ffdf8c;outline-offset:4px}
.skip-link{position:absolute;top:-80px;right:15px;z-index:10;background:#f3d485;color:#132216;padding:12px}
.skip-link:focus{top:12px}
.site-header{background:linear-gradient(110deg,#112b1c,#1f4830);padding:15px clamp(15px,5vw,70px);border-bottom:1px solid #bfaa67;display:flex;align-items:center;justify-content:space-between;gap:22px;flex-wrap:wrap}
.site-identity{display:flex;align-items:center;gap:14px;color:#f3d485;text-decoration:none;font-size:clamp(1rem,2vw,1.32rem);font-weight:750}
.site-identity img{width:50px;height:50px;object-fit:contain;border-radius:50%;background:#f8f4e4}
.site-identity small{display:block;color:#c9d5c6;font-size:.75rem;font-weight:400;margin-top:4px}
.site-nav{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.site-nav a{display:inline-flex;align-items:center;min-height:40px;padding:8px 12px;border:1px solid #d2b87680;border-radius:10px;text-decoration:none;color:#f5e9c8;font-weight:650;font-size:.9rem}
.site-nav a[aria-current="page"]{background:#e8c775;color:#16291b}
main{margin:auto;max-width:1180px;padding:clamp(20px,4vw,48px) 16px}
.breadcrumb{color:#b8d2bd;font-size:.85rem;margin-bottom:16px}
h1,h2{color:#efcf7e;line-height:1.3}
h1{font-size:clamp(1.75rem,3vw,2.5rem);margin:8px 0 25px}
h2{font-size:clamp(1.2rem,2vw,1.5rem)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:17px}
article,section{background:linear-gradient(135deg,#284b31,#1b3927);border:1px solid #b9a365;border-radius:18px;padding:clamp(18px,3vw,26px);margin:12px 0;box-shadow:0 10px 30px #08180d35}
article p,section p{line-height:1.9}
.muted{color:#cbd6c8}
.availability{border-right:5px solid #ddbd66}
.contact-action{display:inline-flex;padding:11px 15px;background:#e8c775;color:#152619;border-radius:9px;font-weight:750;text-decoration:none}
footer{background:#11271a;padding:25px 5%;border-top:1px solid #bfaa67;text-align:center;color:#cbd6c8;font-size:.85rem}
@media(max-width:640px){.site-header{align-items:stretch}.site-nav{flex-wrap:nowrap;overflow-x:auto;padding-bottom:7px}.site-nav a{white-space:nowrap;flex:none}main{padding:20px 12px}.grid{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
</style>
</head>
<body>
<a href="#main-content" class="skip-link">رفتن به محتوای اصلی</a>
<header class="site-header">
  <a class="site-identity" href="/"><img src="/static/site/zomorod-v7/company-logo.webp" alt="نشان شرکت"><span>شرکت کشت و صنعت زمرد ملل<small>پژوهش، کشاورزی و خدمات تخصصی</small></span></a>
  <nav class="site-nav" aria-label="ناوبری اصلی زمرد ملل">
    <a href="/">خانه</a><a href="/agriculture/">کشاورزی</a><a href="/research/">پژوهش‌ها</a><a href="/industry/">صنعت</a><a href="/store/" aria-current="page">فروشگاه</a><a href="/contact/">ارتباط</a>
  </nav>
</header>
<main id="main-content">
<div class="breadcrumb"><a href="/">خانه</a> / فروشگاه</div>
<h1>فروشگاه محصولات زمرد ملل</h1>
<section class="availability"><h2>وضعیت پرداخت بانک شهر</h2><p>اتصال درگاه بانک شهر در انتظار فعال‌سازی پذیرندگی و آزمون تسویه است. <strong>در این وضعیت خرید آنلاین و برداشت وجه غیرفعال است.</strong> محصولات فعال برای معرفی نمایش داده می‌شوند.</p><a href="/contact/">تماس با شرکت</a></section>
<div class="grid">
STORE_HEADER;
if(!$items && !$free) echo '<section><h2>کاتالوگ در حال تکمیل</h2><p>هنوز محصول آماده عرضه عمومی ثبت نشده است؛ پس از تأیید محصول در پنل مدیریت، این بخش خودکار تکمیل می‌شود.</p></section>';

foreach($free as $p){
 $url=(string)$p['download_path'];$sha=(string)$p['artifact_sha256'];
 if(!preg_match('#^/store/free-products/[a-z0-9-]+/index\\.html$#',$url)||!preg_match('/^[0-9a-f]{64}$/',$sha))continue;
 echo '<article><h2>'.storeEsc((string)$p['title']).'</h2><p>'.nl2br(storeEsc((string)$p['description'])).'</p><strong>رایگان — بدون پرداخت</strong><p><a href="'.storeEsc($url).'" download rel="noopener">دریافت ابزار دیجیتال آفلاین</a> · <a href="'.storeEsc($url).'">اجرای آنلاین</a></p><p class="muted">شناسه: '.storeEsc((string)$p['sku']).' | مجوز: '.storeEsc((string)$p['license_text']).'</p><small class="muted">SHA-256: '.storeEsc($sha).'</small></article>';
}
foreach($items as $p){echo '<article><h2>'.storeEsc($p['title']).'</h2><p>'.nl2br(storeEsc($p['description'])).'</p><strong>قیمت: '.number_format((int)$p['price_irr']).' ریال</strong><p class="muted">کد: '.storeEsc($p['sku']).'</p><p class="muted">پرداخت آنلاین تا اتصال درگاه غیرفعال است.</p></article>';}
echo <<<'STORE_FOOTER'
</div>
<section id="zm-store-inquiry" aria-labelledby="inquiry-title">
  <h2 id="inquiry-title">استعلام محصولات و درخواست همکاری</h2>
  <p>برای درخواست معرفی محصول، استعلام قیمت یا اعلام نیاز به ابزارهای دیجیتال کشاورزی، پیام خود را همراه نام محصول یا خدمت ثبت کنید.</p>
  <a class="contact-action" href="/ask-master/index.php">ثبت استعلام در سامانه مشتریان زمرد ملل</a>
  <p class="muted">ثبت استعلام رایگان است و به معنی سفارش قطعی، پرداخت یا تعهد تحویل نیست.</p>
</section>
<section id="zm-company-official-contacts">
  <h2>اطلاعات تماس رسمی شرکت</h2>
  <p>شماره تماس برای ارتباطات فضای مجازی: <a href="tel:+989022048691" dir="ltr">۰۹۰۲۲۰۴۸۶۹۱</a></p>
  <p>نشانی دفتر: استان فارس، شهرستان مرودشت، خیابان قدس، کوچه ۹۲، ساختمان گل‌یخ</p>
</section>
</main>
<footer>تمام حقوق مادی و معنوی سایت برای شرکت کشت و صنعت زمرد ملل محفوظ است . آبان ۱۳۹۸ مجتبی روزگار</footer>
</body></html>
STORE_FOOTER;
