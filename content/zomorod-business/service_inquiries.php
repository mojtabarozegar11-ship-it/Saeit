<?php
declare(strict_types=1);
/** Authenticated read-only service inbox using the existing ZM_BUSINESS login.
 * Never modifies the customer inbox, management ledger or operator replies.
 */
ini_set('display_errors', '0');
ini_set('log_errors', '1');
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: private, no-store, max-age=0');
header('X-Robots-Tag: noindex, nofollow');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: no-referrer');
header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; form-action 'none'; base-uri 'none'; frame-ancestors 'none'");

function zmInquiryEscape(mixed $value): string {
    return htmlspecialchars((string)$value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}
function zmInquiryStop(int $code, string $message): never {
    http_response_code($code);
    echo '<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><title>زمرد ملل · درخواست‌ها</title>';
    echo '<body style="font:16px/1.8 Tahoma,Arial;background:#16291e;color:#f4e7bd;padding:30px">';
    echo '<h1>درخواست‌های خدمات تخصصی</h1><p>'.zmInquiryEscape($message).'</p>';
    echo '<a style="color:#edd18b" href="/business/">بازگشت به میز مدیریت</a></body></html>';
    exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'GET') {
    header('Allow: GET');
    zmInquiryStop(405, 'این بخش فقط برای مشاهده است.');
}
if (!extension_loaded('session') || !class_exists('SQLite3')) {
    zmInquiryStop(503, 'امکانات احراز هویت یا پایگاه داده در دسترس نیست.');
}
if (session_status() === PHP_SESSION_NONE) {
    session_name('ZM_BUSINESS');
    session_set_cookie_params([
        'lifetime' => 0, 'path' => '/business/', 'secure' => true,
        'httponly' => true, 'samesite' => 'Strict',
    ]);
    if (!session_start()) zmInquiryStop(503, 'نشست مدیریت در دسترس نیست.');
}
if (session_name() !== 'ZM_BUSINESS') zmInquiryStop(403, 'نشست معتبر نیست.');
$uid = (int)($_SESSION['uid'] ?? 0);
if ($uid <= 0) zmInquiryStop(403, 'ابتدا وارد میز مدیریت شوید.');

$home = dirname(__DIR__, 2);
$private = $home . '/.private/zomorod-business';
$ledgerPath = $private . '/management.sqlite3';
$pointerPath = $private . '/service_inquiries_source.path';
if (!is_file($ledgerPath) || is_link($ledgerPath) || !is_file($pointerPath) || is_link($pointerPath)) {
    zmInquiryStop(503, 'پرونده‌های خصوصی آماده نیستند.');
}

try {
    // Revalidate the role against the live ledger on every request. Session
    // role alone is insufficient after a staff member has been deactivated.
    $ledger = new SQLite3($ledgerPath, SQLITE3_OPEN_READONLY);
    $staff = $ledger->prepare('SELECT role, active FROM users WHERE id=:uid LIMIT 1');
    if ($staff === false) throw new RuntimeException('staff query unavailable');
    $staff->bindValue(':uid', $uid, SQLITE3_INTEGER);
    $staffResult = $staff->execute();
    $staffRow = $staffResult === false ? false : $staffResult->fetchArray(SQLITE3_ASSOC);
    $ledger->close();
    if (!$staffRow || (int)($staffRow['active'] ?? 0) !== 1 ||
        !in_array((string)($staffRow['role'] ?? ''), ['admin', 'manager'], true)) {
        zmInquiryStop(403, 'دسترسی صرفاً برای مدیران فعال مجاز است.');
    }

    $source = trim((string)file_get_contents($pointerPath));
    $real = realpath($source);
    $allowedPrefix = $home . '/.private/';
    if ($real === false || is_link($source) || !is_file($real) ||
        basename($real) !== 'master_customer_inbox.sqlite3' ||
        strncmp($real, $allowedPrefix, strlen($allowedPrefix)) !== 0) {
        throw new RuntimeException('private source identity invalid');
    }
    $inbox = new SQLite3($real, SQLITE3_OPEN_READONLY);
    $inbox->busyTimeout(3000);
    $prefix = '[SERVICE_INQUIRY] ';

    $countQuery = $inbox->prepare('SELECT COUNT(*) AS n FROM customer_questions WHERE tenant=:tenant AND kind=:kind AND substr(question,1,length(:prefix))=:prefix');
    if ($countQuery === false) throw new RuntimeException('count unavailable');
    $countQuery->bindValue(':tenant', 'zomorod', SQLITE3_TEXT);
    $countQuery->bindValue(':kind', 'question', SQLITE3_TEXT);
    $countQuery->bindValue(':prefix', $prefix, SQLITE3_TEXT);
    $countResult = $countQuery->execute();
    if ($countResult === false) throw new RuntimeException('count query failed');
    $countRow = $countResult->fetchArray(SQLITE3_ASSOC);
    $total = (int)($countRow['n'] ?? 0);

    $listQuery = $inbox->prepare('SELECT id,created_utc,full_name,email,question,processing_status,master_processed_utc FROM customer_questions WHERE tenant=:tenant AND kind=:kind AND substr(question,1,length(:prefix))=:prefix ORDER BY created_utc DESC,id DESC LIMIT 100');
    if ($listQuery === false) throw new RuntimeException('list unavailable');
    $listQuery->bindValue(':tenant', 'zomorod', SQLITE3_TEXT);
    $listQuery->bindValue(':kind', 'question', SQLITE3_TEXT);
    $listQuery->bindValue(':prefix', $prefix, SQLITE3_TEXT);
    $rowsResult = $listQuery->execute();
    if ($rowsResult === false) throw new RuntimeException('list query failed');
    $rows = [];
    while (($row = $rowsResult->fetchArray(SQLITE3_ASSOC)) !== false) $rows[] = $row;
    $inbox->close();
} catch (Throwable $error) {
    error_log('ZM SERVICE INBOX READ ERROR ['.get_class($error).']');
    zmInquiryStop(503, 'خواندن صندوق درخواست‌ها به‌طور ایمن متوقف شد.');
}

echo '<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">';
echo '<title>زمرد ملل · درخواست‌های تخصصی</title><style>body{font:16px/1.9 Tahoma,Arial;background:#10241a;color:#f0e7ca;margin:0}header,main{max-width:1120px;margin:auto;padding:22px}a{color:#e9cb84}h1,h2{color:#f2d28b}section{background:#1d3326;border:1px solid #697951;border-radius:12px;padding:18px;margin:18px 0}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;min-width:820px}th,td{border-bottom:1px solid #56654a;text-align:right;padding:12px;vertical-align:top}th{color:#ebd08e}.message{max-width:390px;white-space:pre-wrap;overflow-wrap:anywhere}.muted{color:#aebfae}</style></head><body>';
echo '<header><a href="/business/">میز مدیریت زمرد ملل</a><h1>صندوق درخواست خدمات تخصصی</h1><p class="muted">فقط نمایش امن اطلاعات ثبت‌شده؛ این صفحه هیچ وضعیت یا اطلاعات مشتری را تغییر نمی‌دهد.</p></header>';
echo '<main><section><h2>تعداد درخواست‌های تخصصی: '.zmInquiryEscape($total).'</h2>';
if ($total === 0) {
    echo '<p>هنوز درخواست خدمات تخصصی برای زمرد ملل ثبت نشده است.</p>';
} else {
    echo '<div class="scroll"><table><thead><tr><th>شناسه</th><th>زمان UTC</th><th>نام</th><th>ایمیل</th><th>درخواست</th><th>وضعیت پردازش</th><th>زمان پردازش UTC</th></tr></thead><tbody>';
    foreach ($rows as $row) {
        echo '<tr><td>'.zmInquiryEscape($row['id']).'</td><td>'.zmInquiryEscape($row['created_utc']).'</td>';
        echo '<td>'.zmInquiryEscape($row['full_name']).'</td><td>'.zmInquiryEscape($row['email']).'</td>';
        echo '<td class="message">'.zmInquiryEscape(substr((string)$row['question'], strlen($prefix))).'</td>';
        echo '<td>'.zmInquiryEscape($row['processing_status']).'</td><td>'.zmInquiryEscape($row['master_processed_utc']).'</td></tr>';
    }
    echo '</tbody></table></div>';
    if ($total > count($rows)) echo '<p class="muted">فقط ۱۰۰ درخواست تازه نمایش داده می‌شود.</p>';
}
echo '</section><p><a href="/business/">بازگشت به میز مدیریت</a></p></main></body></html>';
