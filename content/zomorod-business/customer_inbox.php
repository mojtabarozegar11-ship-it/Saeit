<?php
declare(strict_types=1);
/** Zomorod Melal / authenticated, read-only private customer-inquiry inbox. */
ini_set('display_errors', '0');
ini_set('log_errors', '1');
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store, private, max-age=0');
header('X-Robots-Tag: noindex, nofollow');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: no-referrer');
header('Vary: Cookie');
header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'");

function ziEscape(mixed $value): string {
    return htmlspecialchars((string)$value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}
function ziStop(string $message, int $status): never {
    http_response_code($status);
    echo '<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><title>صندوق مشتریان</title>';
    echo '<body style="font:16px Tahoma;background:#142b1a;color:#f4e7cb;padding:2rem"><p>'.ziEscape($message).'</p>';
    echo '<a style="color:#e6c97b" href="/business/">بازگشت به مدیریت</a></body></html>';
    exit;
}
if (($_SERVER['REQUEST_METHOD']??'')!=='GET') {
    header('Allow: GET');
    ziStop('روش درخواست مجاز نیست.',405);
}
ini_set('session.use_strict_mode', '1');
ini_set('session.use_only_cookies', '1');
ini_set('session.use_trans_sid', '0');
session_name('ZM_BUSINESS');
session_set_cookie_params([
    'lifetime'=>0, 'path'=>'/business/', 'secure'=>true,
    'httponly'=>true, 'samesite'=>'Strict',
]);
if (session_start()!==true) ziStop('نشست در دسترس نیست.',503);
$uid=$_SESSION['uid']??null;
if (!is_int($uid) || $uid<1) ziStop('ابتدا وارد میز مدیریت شوید.',403);

try {
    if (!extension_loaded('pdo_sqlite')) throw new RuntimeException('sqlite missing');
    $root=dirname(__DIR__,2);
    $private=$root.'/.private/zomorod-business';
    $management=$private.'/management.sqlite3';
    $inbox=$private.'/master_customer_inbox.sqlite3';
    if (!is_dir($private) || is_link($private)) throw new RuntimeException('unsafe directory');
    foreach ([$management,$inbox] as $file) {
        if (!is_file($file) || is_link($file) || !is_readable($file) ||
            (fileperms($file)&0777)!==0600) throw new RuntimeException('private data unavailable');
    }
    $options=[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC, PDO::ATTR_TIMEOUT=>10];
    $users=new PDO('sqlite:file:'.$management.'?mode=ro',null,null,$options);
    $users->exec('PRAGMA query_only=ON; PRAGMA busy_timeout=10000;');
    $auth=$users->prepare('SELECT role,active FROM users WHERE id=? LIMIT 1');
    $auth->execute([$uid]);
    $actor=$auth->fetch();
    if (!$actor || (int)$actor['active']!==1 ||
        !in_array((string)$actor['role'],['admin','manager'],true)) ziStop('دسترسی به پیام‌های مشتریان مجاز نیست.',403);
    $db=new PDO('sqlite:file:'.$inbox.'?mode=ro',null,null,$options);
    $db->exec('PRAGMA query_only=ON; PRAGMA busy_timeout=10000;');
    $counts=$db->query("SELECT processing_status,COUNT(*) total FROM customer_questions WHERE tenant='zomorod' GROUP BY processing_status")->fetchAll();
    $all=(int)$db->query("SELECT COUNT(*) FROM customer_questions WHERE tenant='zomorod'")->fetchColumn();
    $rows=$db->query("SELECT id,kind,full_name,email,question,claimed_order_ref,processing_status,created_utc FROM customer_questions WHERE tenant='zomorod' ORDER BY created_utc DESC,id DESC LIMIT 50")->fetchAll();
} catch (Throwable $error) {
    ziStop('صندوق مشتریان موقتاً در دسترس نیست.',503);
}
$states=['queued'=>'جدید','needs_review'=>'نیازمند بررسی','handled'=>'پردازش داخلی'];
$kinds=['question'=>'پرسش و استعلام','order_question'=>'ادعای سفارش / پیگیری'];
echo '<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">';
echo '<title>صندوق درخواست‌های مشتریان — زمرد ملل</title><style>';
echo ':root{font-family:Tahoma,Arial,sans-serif;color-scheme:dark}body{margin:0;background:#17321d;color:#eee9d4}header,main{max-width:1200px;margin:auto;padding:22px 16px}h1,h2{color:#ebce80}a{color:#f2d38c}section{background:#243d29;border:1px solid #83744b;border-radius:15px;margin:15px 0;padding:18px}';
echo '.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}.metric{font-size:25px;color:#f6d88f}table{border-collapse:collapse;min-width:860px;width:100%}td,th{border-bottom:1px solid #657252;text-align:right;padding:11px;vertical-align:top}th{color:#edce80}.scroll{overflow-x:auto}';
echo 'details{max-width:520px}summary{cursor:pointer}p{line-height:1.8}.small{font-size:12px;color:#c6d4bc}code{overflow-wrap:anywhere;color:#e5d29b}</style></head><body><header>';
echo '<p><a href="/business/?page=dashboard">داشبورد مدیریت</a> · <a href="/business/?page=command_center">مرکز فرمان</a> · <a href="/store/">فروشگاه</a></p>';
echo '<h1>صندوق درخواست‌ها و استعلام‌های مشتریان زمرد ملل</h1><p>این قسمت فقط پیام‌های ثبت‌شده سایت زمرد ملل را می‌خواند؛ سفارش، پرداخت یا تعهد فروش ایجاد نمی‌کند.</p></header><main>';
echo '<section><h2>وضعیت درخواست‌ها</h2><div class="grid"><div><div class="metric">'.$all.'</div>مجموع پیام‌ها</div>';
foreach ($counts as $count) {
    echo '<div><div class="metric">'.(int)$count['total'].'</div>'.ziEscape($states[$count['processing_status']]??$count['processing_status']).'</div>';
}
echo '</div><p class="small">عبارت «پردازش داخلی» به‌معنای پاسخ انسانی، ارسال ایمیل یا انجام سفارش نیست.</p></section>';
echo '<section><h2>آخرین درخواست‌های واقعی</h2><p class="small">حداکثر ۵۰ مورد جدید نمایش داده می‌شود. اطلاعات تماس خصوصی و فقط برای مدیران مجاز است.</p>';
if (!$rows) echo '<p>هنوز پیام واقعی از بازدیدکنندگان ثبت نشده است.</p>';
else {
    echo '<div class="scroll"><table><thead><tr><th>شناسه / زمان</th><th>نوع و وضعیت</th><th>نام و راه ارتباط</th><th>متن درخواست</th></tr></thead><tbody>';
    foreach ($rows as $r) {
        echo '<tr><td><code>'.ziEscape($r['id']).'</code><p class="small">'.ziEscape($r['created_utc']).' UTC</p></td>';
        echo '<td>'.ziEscape($kinds[$r['kind']]??$r['kind']).'<p>'.ziEscape($states[$r['processing_status']]??$r['processing_status']).'</p></td>';
        echo '<td>'.ziEscape($r['full_name']).'<p><a href="mailto:'.ziEscape($r['email']).'">'.ziEscape($r['email']).'</a></p></td>';
        echo '<td><details><summary>نمایش متن درخواست</summary><p>'.nl2br(ziEscape($r['question'])).'</p>';
        if ((string)$r['claimed_order_ref']!=='') echo '<p>مرجع ادعایی سفارش: '.ziEscape($r['claimed_order_ref']).' — بدون تأیید پرداخت</p>';
        echo '</details></td></tr>';
    }
    echo '</tbody></table></div>';
}
echo '</section></main></body></html>';
