<?php
declare(strict_types=1);
/**
 * Zomorod Melal: independent, read-only accounting insights.
 * Intended public route: /business/insights.php
 * Uses the existing /business/ session and the *existing* private accounting DB.
 * Never creates, migrates or updates any financial record.
 */
ini_set('display_errors', '0');
ini_set('log_errors', '1');
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store, private, max-age=0');
header('Pragma: no-cache');
header('X-Robots-Tag: noindex, nofollow');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: no-referrer');
header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; form-action 'none'; base-uri 'none'; frame-ancestors 'none'");
header('Vary: Cookie');

function ziEsc(mixed $value): string {
    return htmlspecialchars((string)$value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}
function ziMoney(int $cents): string {
    return number_format($cents / 100, 2, '.', ',');
}
function ziRefuse(string $message, int $status): never {
    http_response_code($status);
    echo '<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>گزارش مالی زمرد ملل</title>';
    echo '<body style="font:16px Tahoma,Arial;background:#102018;color:#f1e6c5;padding:36px"><h1>'.ziEsc($message).'</h1><p><a href="/business/" style="color:#f3d58a">بازگشت به میز مدیریت و ورود</a></p></body></html>';
    exit;
}
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'GET') {
    header('Allow: GET');
    ziRefuse('این بخش فقط برای مشاهده است.', 405);
}

// Use exactly the main accounting application's session namespace and cookie path.
ini_set('session.use_strict_mode', '1');
ini_set('session.use_only_cookies', '1');
ini_set('session.use_trans_sid', '0');
session_name('ZM_BUSINESS');
session_set_cookie_params([
    'lifetime' => 0, 'path' => '/business/', 'secure' => true,
    'httponly' => true, 'samesite' => 'Strict',
]);
if (session_start() !== true) ziRefuse('نشست کاربری در دسترس نیست.', 503);
$actor = $_SESSION['uid'] ?? null;
session_write_close();
if (!is_int($actor) || $actor < 1) ziRefuse('برای دیدن گزارش ابتدا وارد حساب مجاز شوید.', 403);

try {
    if (!extension_loaded('pdo_sqlite')) throw new RuntimeException('sqlite-extension');
    $root = dirname(__DIR__, 2);
    $private = $root.'/.private/zomorod-business';
    $file = $private.'/management.sqlite3';
    if (!is_dir($private) || is_link($private) || is_link($file) || !is_file($file) || !is_readable($file) || filesize($file) < 4096) {
        throw new RuntimeException('private-accounting-db-unavailable');
    }
    // Explicit URI mode=ro prevents an accidental database creation or write.
    $database = new PDO('sqlite:file:'.$file.'?mode=ro', null, null, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_TIMEOUT => 10,
    ]);
    $database->exec('PRAGMA query_only=ON');
    $userQuery = $database->prepare('SELECT username,role FROM users WHERE id=? AND active=1 LIMIT 1');
    $userQuery->execute([$actor]);
    $user = $userQuery->fetch();
    if (!$user || !in_array($user['role'], ['viewer','manager','accountant','admin'], true)) {
        ziRefuse('حساب شما مجوز دیدن گزارش را ندارد.', 403);
    }
    $today = (new DateTimeImmutable('now', new DateTimeZone('Asia/Tehran')))->format('Y-m-d');
    $counts = [
        'اسناد حسابداری' => (int)$database->query('SELECT COUNT(*) FROM journal_entries')->fetchColumn(),
        'فاکتورهای ثبت‌شده' => (int)$database->query('SELECT COUNT(*) FROM invoices')->fetchColumn(),
        'اشخاص' => (int)$database->query('SELECT COUNT(*) FROM parties')->fetchColumn(),
        'کالاهای انبار' => (int)$database->query('SELECT COUNT(*) FROM inventory')->fetchColumn(),
    ];
    $totalsQuery = $database->prepare("SELECT i.currency,
        SUM(CASE WHEN i.kind='sale' THEN i.amount-COALESCE(pay.total,0) ELSE 0 END) receivable,
        SUM(CASE WHEN i.kind='purchase' THEN i.amount-COALESCE(pay.total,0) ELSE 0 END) payable,
        SUM(CASE WHEN i.kind='sale' AND i.due_date<? THEN i.amount-COALESCE(pay.total,0) ELSE 0 END) overdue_receivable,
        SUM(CASE WHEN i.kind='purchase' AND i.due_date<? THEN i.amount-COALESCE(pay.total,0) ELSE 0 END) overdue_payable
        FROM invoices i
        LEFT JOIN (SELECT invoice_id,SUM(amount) total FROM invoice_payments GROUP BY invoice_id) pay ON pay.invoice_id=i.id
        GROUP BY i.currency ORDER BY i.currency");
    $totalsQuery->execute([$today, $today]);
    $totals = $totalsQuery->fetchAll();
    $unpaidQuery = $database->prepare("SELECT i.invoice_no,i.kind,i.due_date,i.currency,
        p.name party, i.amount-COALESCE(pay.total,0) remainder
        FROM invoices i JOIN parties p ON p.id=i.party_id
        LEFT JOIN (SELECT invoice_id,SUM(amount) total FROM invoice_payments GROUP BY invoice_id) pay ON pay.invoice_id=i.id
        WHERE i.amount>COALESCE(pay.total,0)
        ORDER BY i.due_date ASC,i.id DESC LIMIT 80");
    $unpaidQuery->execute();
    $unpaid = $unpaidQuery->fetchAll();
    $database = null;
} catch (Throwable $exception) {
    // No private file paths, SQL, account names or amounts in an HTTP error.
    error_log('zm_business_insights_read_failed: '.get_class($exception));
    ziRefuse('گزارش موقتاً در دسترس نیست؛ داده‌های مالی تغییر نکرده‌اند.', 503);
}
?><!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>گزارش مدیریتی حسابداری | زمرد ملل</title>
<style>
:root{font-family:Tahoma,Arial,sans-serif;color:#f4ebd1;background:#101d16;line-height:1.8}*{box-sizing:border-box}body{margin:0;background:linear-gradient(145deg,#102018,#29422c);min-height:100vh}a{color:#f4d98a}header{background:#142a1c;border-bottom:1px solid #af955b;padding:20px max(18px,calc((100vw - 1160px)/2));display:flex;justify-content:space-between;align-items:center;gap:18px;flex-wrap:wrap}header strong{font-size:22px;color:#f5cf79}main{max-width:1160px;padding:25px 18px 70px;margin:auto}h1,h2{color:#f5d389;margin:0 0 13px}h1{font-size:clamp(24px,3vw,34px)}h2{font-size:20px}.muted{color:#c4cbb9;font-size:14px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin:22px 0}.panel,.metric{background:#192c20;border:1px solid #5a6f51;border-radius:16px;padding:18px;margin:20px 0;box-shadow:0 8px 25px #07130a4d}.metric{margin:0}.metric b{font-size:30px;display:block;color:#f6d781}.table-scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;min-width:680px}th,td{padding:11px 13px;text-align:right;border-bottom:1px solid #496044}th{color:#f2d493}td.amount{font-variant-numeric:tabular-nums;direction:ltr;text-align:right}tr:hover{background:#233b29}.warn{border-right:4px solid #d5a354;padding:12px 17px;background:#403925;margin:18px 0}.overdue{color:#ffc48b}.empty{padding:25px;color:#cedcc6}.pill{border:1px solid #ae9966;border-radius:100px;padding:8px 14px;display:inline-block;text-decoration:none}.pill:focus-visible{outline:3px solid #f4d98a;outline-offset:3px}footer{text-align:center;padding:30px;font-size:12px;color:#bac7b2}@media(max-width:650px){header{padding:16px}main{padding:18px 12px}td,th{padding:9px 10px}}
</style></head><body>
<header><div><strong>زمرد ملل · گزارش مالی</strong><div class="muted">نمای تصمیم‌گیری مدیریت و حسابداری</div></div><div><span><?=ziEsc($user['username'])?> · <?=ziEsc($user['role'])?></span> &nbsp; <a class="pill" href="/business/">بازگشت به میز مدیریت</a></div></header>
<main>
<h1>وضعیت مطالبات و تعهدات شرکت</h1>
<p class="muted">تاریخ محاسبه: <?=ziEsc($today)?> (به وقت ایران) · اطلاعات موجود در دفتر حسابداری داخلی</p>
<div class="warn">این ارقام از فاکتورها و پرداخت‌های ثبت‌شده توسط کاربران محاسبه می‌شوند؛ <strong>تأییدیه بانک، درگاه پرداخت یا تسویه واقعی محسوب نمی‌شوند.</strong> ارزهای مختلف عمداً با هم جمع نشده‌اند.</div>
<div class="grid">
<?php foreach ($counts as $title => $count): ?>
<div class="metric"><b><?=ziEsc(number_format($count))?></b><span><?=ziEsc($title)?></span></div>
<?php endforeach; ?>
</div>
<section class="panel"><h2>مانده به تفکیک ارز</h2><div class="table-scroll"><table><thead><tr><th>ارز</th><th>مطالبات باقیمانده</th><th>مطالبات سررسیدگذشته</th><th>بدهی باقیمانده</th><th>بدهی سررسیدگذشته</th></tr></thead><tbody>
<?php foreach ($totals as $row): ?>
<tr><td><?=ziEsc($row['currency'])?></td><td class="amount"><?=ziMoney((int)$row['receivable'])?></td><td class="amount"><?=ziMoney((int)$row['overdue_receivable'])?></td><td class="amount"><?=ziMoney((int)$row['payable'])?></td><td class="amount"><?=ziMoney((int)$row['overdue_payable'])?></td></tr>
<?php endforeach; ?>
</tbody></table></div><?php if (!$totals): ?><p class="empty">در دفتر فعلی فاکتوری ثبت نشده است.</p><?php endif; ?></section>
<section class="panel"><h2>فاکتورهای دارای مانده؛ مرتب‌شده بر اساس سررسید</h2><p class="muted">حداکثر ۸۰ ردیف نخست نمایش داده می‌شود. برای عملیات ثبت یا اصلاح، از میز مدیریت اصلی استفاده کنید.</p><div class="table-scroll"><table><thead><tr><th>شماره فاکتور</th><th>نوع</th><th>طرف حساب</th><th>تاریخ سررسید</th><th>وضعیت</th><th>ارز</th><th>مانده</th></tr></thead><tbody>
<?php foreach ($unpaid as $row): ?>
<tr><td><?=ziEsc($row['invoice_no'])?></td><td><?=$row['kind']==='sale'?'فروش':'خرید'?></td><td><?=ziEsc($row['party'])?></td><td><?=ziEsc($row['due_date'])?></td><td class="<?=((string)$row['due_date']<$today)?'overdue':''?>"><?=((string)$row['due_date']<$today)?'سررسیدگذشته':'در موعد'?></td><td><?=ziEsc($row['currency'])?></td><td class="amount"><?=ziMoney((int)$row['remainder'])?></td></tr>
<?php endforeach; ?>
</tbody></table></div><?php if (!$unpaid): ?><p class="empty">فاکتور دارای مانده‌ای ثبت نشده است.</p><?php endif; ?></section>
</main><footer>شرکت کشت و صنعت زمرد ملل · دسترسی فقط برای کاربران فعال و مجاز · گزارش صرفاً خواندنی</footer>
</body></html>
