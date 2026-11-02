<?php
declare(strict_types=1);
/**
 * Explicit, non-transactional storefront cart HOLD.
 * Installed as public_html/store/cart/index.php only after guarded release.
 * No DB access, sessions, order creation, PSP callback, or outbound requests.
 */
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: private, no-store, max-age=0');
header('X-Robots-Tag: noindex, nofollow');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: no-referrer');
header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; form-action 'none'; base-uri 'none'; frame-ancestors 'none'");
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
if ($method !== 'GET' && $method !== 'HEAD') {
    header('Allow: GET, HEAD');
    http_response_code(405);
    exit;
}
http_response_code(200);
?><!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>سبد خرید | فروشگاه زمرد ملل</title>
<style>
:root{font-family:Tahoma,Arial,sans-serif;color-scheme:dark}
body{margin:0;min-height:100vh;background:#203b23;color:#f2efdb}
header,footer{background:#172e1c;padding:18px 5%;border-bottom:1px solid #bfaa67}
main{max-width:760px;margin:42px auto;padding:16px}
section{background:#284b31;border:1px solid #c6ab67;border-radius:16px;padding:24px;line-height:2}
h1{color:#efcf7e;margin-top:0}
a{color:#ffdf8c}
</style>
</head>
<body>
<header>شرکت کشت و صنعت زمرد ملل — فروشگاه</header>
<main><section>
<h1>سبد خرید</h1>
<p>ثبت سفارش و پرداخت اینترنتی در حال حاضر غیرفعال است. تا احراز پذیرندگی بانک شهر، امنیت تسویه و تحویل خودکار، این مسیر هیچ سفارش یا پرداختی دریافت نمی‌کند.</p>
<p>این صفحه فاکتور، پیش‌فاکتور یا رزرو کالا صادر نمی‌کند و هیچ تعهد خریدی ایجاد نمی‌شود.</p>
<p><a href="/store/">بازگشت به فروشگاه و مشاهده محصولات رایگان</a></p>
</section></main>
<footer>شرکت کشت و صنعت زمرد ملل</footer>
</body>
</html>
