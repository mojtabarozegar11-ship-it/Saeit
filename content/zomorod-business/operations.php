<?php
declare(strict_types=1);
/** Private, strictly read-only operational overview for Zomorod Melal. */
ini_set('display_errors','0'); ini_set('log_errors','1');
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store, private, max-age=0');
header('X-Robots-Tag: noindex, nofollow');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: no-referrer');
header('Vary: Cookie');
header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'");
function zoEsc(mixed $v):string{return htmlspecialchars((string)$v,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
function zoStop(int $http,string $title):never{
 http_response_code($http);
 echo '<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><title>میز عملیات</title><body style="background:#17291d;color:#f3e3ba;font:16px Tahoma;padding:30px"><h1>'.zoEsc($title).'</h1><a style="color:#ffdb89" href="/business/">بازگشت به مدیریت</a></body></html>';exit;
}
if(($_SERVER['REQUEST_METHOD']??'GET')!=='GET'){header('Allow: GET');zoStop(405,'درخواست پشتیبانی نمی‌شود.');}
ini_set('session.use_strict_mode','1');
ini_set('session.use_only_cookies','1');
ini_set('session.use_trans_sid','0');
session_name('ZM_BUSINESS');
session_set_cookie_params(['lifetime'=>0,'path'=>'/business/','secure'=>true,'httponly'=>true,'samesite'=>'Strict']);
if(session_start()!==true)zoStop(503,'نشست در دسترس نیست.');
$uid=$_SESSION['uid']??null;
if(!is_int($uid)||$uid<1)zoStop(403,'ابتدا وارد میز مدیریت شوید.');
function zoRead(string $file):PDO{
 if(!is_file($file)||is_link($file)||!is_readable($file)||
    (fileperms($file)&0777)!==0600)throw new RuntimeException('Private source not available');
 $db=new PDO('sqlite:file:'.$file.'?mode=ro',null,null,[
   PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,
   PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,
   PDO::ATTR_TIMEOUT=>8]);
 $db->exec('PRAGMA query_only=ON; PRAGMA busy_timeout=8000;');
 return $db;
}
function zoCount(PDO $d,string $sql):int{return (int)$d->query($sql)->fetchColumn();}
function zoMoney(int $value):string{return number_format($value/100,2,'.',',');}
try{
 $root=dirname(__DIR__,2).'/.private/zomorod-business';
 if(!is_dir($root)||is_link($root))throw new RuntimeException('Unsafe private root');
 $fin=zoRead($root.'/management.sqlite3');
 $auth=$fin->prepare('SELECT role,active FROM users WHERE id=?');
 $auth->execute([$uid]);$user=$auth->fetch();
 if(!$user||(int)$user['active']!==1||
    !in_array((string)$user['role'],['admin','manager','accountant'],true))zoStop(403,'اجازه مشاهده گزارش عملیاتی ندارید.');
 $ledger=zoCount($fin,'SELECT COUNT(*) FROM journal_entries');
 $invoices=zoCount($fin,'SELECT COUNT(*) FROM invoices');
 $receipts=zoCount($fin,'SELECT COUNT(*) FROM invoice_payments');
 $registeredBanks=zoCount($fin,"SELECT COUNT(*) FROM ledger_accounts WHERE code IN ('1011','1012') AND active=1");
 $genericBank=zoCount($fin,"SELECT COUNT(*) FROM journal_lines l JOIN ledger_accounts a ON l.account_id=a.id WHERE a.code='1010'");
 $evidence=zoCount($fin,'SELECT COUNT(*) FROM bank_payment_evidence');
 $invoicing=$fin->query("SELECT i.currency,i.kind,COUNT(*) AS cnt,SUM(i.amount) AS total,
   SUM(i.amount-COALESCE((SELECT SUM(p.amount) FROM invoice_payments p WHERE p.invoice_id=i.id),0)) AS remaining
   FROM invoices i GROUP BY i.currency,i.kind ORDER BY i.currency,i.kind")->fetchAll();
 $store=zoRead($root.'/site_store.sqlite3');
 $paid=zoCount($store,'SELECT COUNT(*) FROM products WHERE enabled=1');
 $drafts=zoCount($store,'SELECT COUNT(*) FROM factory_drafts');
 $consumer=zoCount($store,'SELECT COUNT(*) FROM factory_consumer_candidates');
 $free=zoCount($store,'SELECT COUNT(*) FROM free_digital_products WHERE enabled=1');
 $payment=$store->query('SELECT provider,state FROM payment_state WHERE id=1')->fetch();
 $inbox=zoRead($root.'/master_customer_inbox.sqlite3');
 $questions=zoCount($inbox,"SELECT COUNT(*) FROM customer_questions WHERE tenant='zomorod'");
 $pendingQuestions=zoCount($inbox,"SELECT COUNT(*) FROM customer_questions WHERE tenant='zomorod' AND processing_status!='handled'");
 $control=zoRead($root.'/command-center.sqlite3');
 $openTasks=zoCount($control,"SELECT COUNT(*) FROM tasks WHERE state NOT IN ('done','closed','cancelled')");
 $taskRows=$control->query("SELECT title,priority,state,created_at FROM tasks WHERE state NOT IN ('done','closed','cancelled') ORDER BY id DESC LIMIT 7")->fetchAll();
 session_write_close();
}catch(Throwable $e){
 error_log('ZM_OPERATIONS_VIEW_READ_FAILURE: '.get_class($e));
 zoStop(503,'گردآوری داده‌های عملیاتی انجام نشد.');
}
$time=(new DateTimeImmutable('now',new DateTimeZone('Asia/Tehran')))->format('Y/m/d H:i');
$payConfigured=is_array($payment)&&($payment['state']??'')==='configured_verified';
?><!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>پایش یکپارچه عملیات | زمرد ملل</title>
<style>
:root{font:15px/1.8 Tahoma,Arial;color:#f1ead6;background:#112319}
*{box-sizing:border-box}body{margin:0}
header,main{max-width:1180px;margin:auto;padding:17px 18px}
header{border-bottom:1px solid #87764a}h1,h2{color:#e8c97d}a{color:#f2d388}
nav{display:flex;gap:12px;flex-wrap:wrap;padding:10px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(185px,1fr));gap:13px}
.card,section{background:#1c3223;border:1px solid #526b4c;border-radius:13px;padding:16px;margin:14px 0}
.metric{font-size:29px;font-weight:bold;color:#f1d48e}
.small{color:#ced7bd;font-size:13px}
.warn{border-color:#b18c4c;background:#383322}.stop{border-color:#a86f6b;background:#40272a}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:630px}
th,td{text-align:right;border-bottom:1px solid #52664e;padding:9px}
th{color:#f0ce88}code{color:#e8cf8f;overflow-wrap:anywhere}
a:focus-visible{outline:2px solid #f9e1a8;outline-offset:4px}
</style></head><body>
<header><nav aria-label="پیمایش"><a href="/business/">میز اصلی</a><a href="/business/insights.php">گزارش مالی</a><a href="/business/banking.php">دفتر بانک‌ها</a><a href="/business/customer_inbox.php">صندوق مشتریان</a><a href="/business/?page=command_center">مرکز فرمان</a><a href="/business/?page=store_manager">مدیریت فروشگاه</a></nav>
<h1>پایش یکپارچهٔ کسب‌وکار و حسابداری</h1>
<p class="small">آخرین بازخوانی اطلاعات داخلی: <?=zoEsc($time)?> به وقت ایران · اطلاعات صرفاً خواندنی است؛ هیچ فاکتور، دریافت یا سفارش خودکار ایجاد نمی‌شود.</p></header>
<main>
<div class="grid">
<div class="card"><div class="metric"><?=$invoices?></div>فاکتورهای دفتر حسابداری</div>
<div class="card"><div class="metric"><?=$receipts?></div>ثبت‌های دریافت یا پرداخت فاکتور <p class="small">نه تأیید مستقل بانک</p></div>
<div class="card"><div class="metric"><?=$paid?></div>کالای پولی فعال در کاتالوگ</div>
<div class="card"><div class="metric"><?=$questions?></div>درخواست‌های واقعی مشتریان زمرد ملل</div>
<div class="card"><div class="metric"><?=$openTasks?></div>وظیفه باز مرکز فرمان</div>
<div class="card"><div class="metric"><?=$drafts?></div>پیش‌نویس خصوصی کارخانه</div>
</div>
<section class="<?= $payConfigured?'':'stop' ?>"><h2>زنجیره فروش و دریافت وجه</h2>
<p><strong>درگاه:</strong> <?=zoEsc((string)($payment['provider']??'نامشخص'))?> ·
 <strong>وضعیت داخلی:</strong> <?=zoEsc((string)($payment['state']??'ناموجود'))?></p>
<p><?= $payConfigured ? 'وضعیت داخلی پذیرندگی «تأییدشده» گزارش شده؛ تأیید تراکنش و تسویه برای هر سفارش همچنان جداگانه لازم است.' :
 'درگاه بانکی معتبر و فرایند سفارش پولیِ متصل به دفتر کل هنوز برقرار نیست. هیچ استعلام یا پیش‌نویس کارخانه نباید فروش قطعی یا وصول وجه شمرده شود.' ?></p>
<p>محصول دیجیتال رایگان: <strong><?=$free?></strong> · بسته مصرف‌کننده در انتظار بازبینی: <strong><?=$consumer?></strong> · درخواست مشتری نیازمند رسیدگی: <strong><?=$pendingQuestions?></strong></p>
</section>
<section><h2>حسابداری، بانک و تسویه</h2>
<p>اسناد روزنامه: <strong><?=$ledger?></strong> · زیرحساب‌های بانکی فعال (ملت/شهر): <strong><?=$registeredBanks?> از ۲</strong> ·
مراجع بانکی ثبت‌شده: <strong><?=$evidence?></strong> · گردش‌های قدیمی حساب عمومی ۱۰۱۰: <strong><?=$genericBank?></strong></p>
<p class="small">این ارقام برگرفته از دفاتر داخلی‌اند؛ مانده حساب بانک و وصول واقعی را اثبات نمی‌کنند. ثبت‌های قدیمی ۱۰۱۰ نباید خودکار به ملت یا شهر تخصیص داده شوند.</p>
<div class="scroll"><table><tr><th>ارز</th><th>نوع فاکتور</th><th>تعداد</th><th>مبلغ دفتری</th><th>مانده ثبت‌نشده</th></tr>
<?php foreach($invoicing as $r): ?>
<tr><td><?=zoEsc($r['currency'])?></td><td><?=zoEsc($r['kind']==='sale'?'فروش':'خرید')?></td>
<td><?=(int)$r['cnt']?></td><td><?=zoMoney((int)$r['total'])?></td><td><?=zoMoney((int)$r['remaining'])?></td></tr>
<?php endforeach; ?>
<?php if(!$invoicing): ?><tr><td colspan="5">فعلاً فاکتوری در دفتر اصلی ثبت نشده است.</td></tr><?php endif; ?>
</table></div></section>
<section><h2>پیگیری عملیات و موانع</h2>
<div class="scroll"><table><tr><th>وظیفه داخلی</th><th>اولویت</th><th>وضعیت</th><th>زمان</th></tr>
<?php foreach($taskRows as $t): ?><tr><td><?=zoEsc($t['title'])?></td><td><?=zoEsc($t['priority'])?></td><td><?=zoEsc($t['state'])?></td><td><?=zoEsc($t['created_at'])?></td></tr><?php endforeach; ?>
<?php if(!$taskRows): ?><tr><td colspan="4">وظیفه بازی در مرکز فرمان ثبت نیست.</td></tr><?php endif; ?>
</table></div><p class="small">وظایف صرفاً موارد پیگیری‌اند؛ ایجاد آن‌ها به معنی حل مانع یا فروش واقعی نیست.</p></section>
<section class="warn"><h2>مراحل لازم برای بهره‌برداری درآمدزا</h2>
<ol><li>بازبینی مستقل یک محصول واقعی با کنترل علمی، حقوقی، فنی و مدارک تحویل.</li>
<li>ثبت کالای پذیرفته‌شده در فروشگاه با مجوز انتشار و روش تحویل اثبات‌شده.</li>
<li>فعال‌سازی پذیرندگی رسمی و احراز پرداخت از سمت سرور؛ هیچ تأیید دستیِ بدون مدرک بانکی جایگزین نمی‌شود.</li>
<li>صدور فاکتور برای سفارش قطعی، پیوند یکتای پرداخت و اسناد متوازن، سپس کنترل مغایرت بانکی و تحویل واقعی.</li></ol>
<p>در وضعیت فعلی، اتصال حسابداری و پایش <strong>فعال</strong> است اما کل زنجیره درآمدزایی <strong>تکمیل نشده</strong> است.</p></section>
</main></body></html>
