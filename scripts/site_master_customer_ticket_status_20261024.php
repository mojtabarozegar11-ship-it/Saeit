<?php
declare(strict_types=1);
/**
 * Customer ticket progress lookup for the two *independent*, API-free site masters.
 * A high-entropy ticket ID AND the request's email are required. No order,
 * payment, wallet, message body or another tenant's record is exposed.
 */
define('MASTER_CUSTOMER_TEST_MODE', true);
require __DIR__ . '/index.php';

function masterTrackTicket(PDO $db, string $tenant, string $ticket, string $email): ?array {
    if (!in_array($tenant, ['zomorod','mojplaywin'], true) ||
        preg_match('/\\A[a-f0-9]{24}\\z/D', $ticket) !== 1 ||
        !filter_var($email, FILTER_VALIDATE_EMAIL) || strlen($email) > 250) {
        return null;
    }
    $stmt = $db->prepare('SELECT email,processing_status,initial_reply,created_utc,master_processed_utc
                          FROM customer_questions WHERE id=? AND tenant=? LIMIT 1');
    $stmt->execute([$ticket, $tenant]);
    $row = $stmt->fetch(PDO::FETCH_ASSOC);
    if (!$row || !hash_equals(strtolower((string)$row['email']), strtolower($email))) {
        return null;
    }
    return [
        'status' => (string)$row['processing_status'],
        'reply' => (string)$row['initial_reply'],
        'created' => (string)$row['created_utc'],
        'processed' => (string)($row['master_processed_utc'] ?? ''),
    ];
}
function masterTicketStatusWeb(): void {
    if (PHP_SAPI === 'cli') { return; }
    header('Content-Type: text/html; charset=utf-8');
    header('Cache-Control: no-store, private');
    header('X-Content-Type-Options: nosniff');
    header('X-Frame-Options: DENY');
    header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");
    try { $cfg = masterSiteConfig((string)($_SERVER['HTTP_HOST'] ?? ''), __DIR__); }
    catch (Throwable $e) { http_response_code(404); echo 'Not found'; return; }
    if (!in_array($_SERVER['REQUEST_METHOD'] ?? 'GET', ['GET','POST'], true)) {
        http_response_code(405); header('Allow: GET, POST'); return;
    }
    $fa = $cfg['locale'] === 'fa';
    session_name($fa ? 'ZM_MASTER_SUPPORT' : 'MPW_MASTER_SUPPORT');
    session_set_cookie_params(['lifetime'=>0,'path'=>'/ask-master/','secure'=>true,'httponly'=>true,'samesite'=>'Strict']);
    if (!session_start()) { http_response_code(503); return; }
    if (!isset($_SESSION['master_csrf'])) { $_SESSION['master_csrf'] = bin2hex(random_bytes(24)); }
    $error = ''; $result = null;
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        try {
            if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 4500 ||
                !hash_equals((string)$_SESSION['master_csrf'], (string)($_POST['csrf'] ?? '')) ||
                trim((string)($_POST['website'] ?? '')) !== '') {
                throw new InvalidArgumentException('Invalid form');
            }
            $origin = (string)($_SERVER['HTTP_ORIGIN'] ?? '');
            if ($origin !== '' && !in_array(strtolower((string)parse_url($origin, PHP_URL_HOST)),
                [$fa ? 'zomorodmelal.ir' : 'mojplaywin.com',
                 $fa ? 'www.zomorodmelal.ir' : 'www.mojplaywin.com'], true)) {
                throw new InvalidArgumentException('Cross-origin form');
            }
            $db = masterOpenDb($cfg['private']);
            if (!masterCheckLimit($db, (string)($_SERVER['REMOTE_ADDR'] ?? 'unknown'))) {
                throw new InvalidArgumentException('Rate limit');
            }
            $result = masterTrackTicket($db, $cfg['tenant'],
                strtolower(trim((string)($_POST['ticket'] ?? ''))),
                trim((string)($_POST['email'] ?? '')));
            if ($result === null) {
                throw new InvalidArgumentException('No matching request');
            }
            $_SESSION['master_csrf'] = bin2hex(random_bytes(24));
        } catch (InvalidArgumentException $e) {
            http_response_code(422);
            $error = $fa ? 'شناسه و ایمیل مطابقت ندارند یا محدودیت درخواست اعمال شده است.'
                         : 'The ticket and email do not match, or the request limit was reached.';
        } catch (Throwable $e) {
            http_response_code(503);
            $error = $fa ? 'پیگیری موقتاً در دسترس نیست.' : 'Ticket lookup is temporarily unavailable.';
        }
    }
    $title = $fa ? 'پیگیری پرسش و درخواست' : 'Track your support request';
    $dir = $fa ? 'rtl' : 'ltr';
    $lang = $fa ? 'fa' : 'en';
    echo '<!doctype html><html lang="'.$lang.'" dir="'.$dir.'"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'.masterEscape($title).'</title>';
    echo '<style>body{margin:0;background:#10291f;color:#f6efd9;font:16px/1.8 system-ui,Tahoma,Arial,sans-serif}main{max-width:740px;margin:auto;padding:36px 18px}a,h1{color:#f1d28b}section{background:#1b3b2b;border:1px solid #bda16c;border-radius:18px;padding:24px;margin:20px 0}label{display:block;margin-top:14px}input,button{box-sizing:border-box;width:100%;padding:12px;border-radius:9px;font:inherit}input{background:#fafbf8;color:#12251b;border:1px solid #9aaf96}button{background:#e5ca85;border:0;color:#1c271c;font-weight:bold;cursor:pointer;margin-top:18px}.error{color:#ffb8a7}.honeypot{position:absolute;left:-99999px}</style></head><body><main>';
    echo '<p><a href="/ask-master/index.php">'.($fa ? 'ثبت پرسش جدید' : 'Ask another question').'</a></p><h1>'.masterEscape($title).'</h1>';
    if ($error !== '') { echo '<p role="alert" class="error">'.masterEscape($error).'</p>'; }
    if ($result !== null) {
        $status = $result['status'];
        $message = $status === 'queued'
            ? ($fa ? 'در صف مسترایجنت' : 'Queued for the site master')
            : ($status === 'needs_review'
                ? ($fa ? 'نیازمند بررسی اختصاصی؛ پاسخ نهایی هنوز تأیید نشده است' : 'Individual review required; no final answer verified')
                : ($fa ? 'راهنمایی خودکار بررسی شد؛ این وضعیت به معنی حل نهایی درخواست نیست' : 'Automated guidance processed; this does not mean the issue is fully resolved'));
        echo '<section role="status"><h2>'.masterEscape($message).'</h2><p>'.masterEscape($result['reply']).'</p>';
        echo '<p>'.($fa ? 'ثبت درخواست: ' : 'Request created: ').masterEscape($result['created']).' UTC</p></section>';
    }
    echo '<section><form method="post" action="/ask-master/status.php" accept-charset="utf-8">';
    echo '<input type="hidden" name="csrf" value="'.masterEscape((string)$_SESSION['master_csrf']).'">';
    echo '<div class="honeypot" aria-hidden="true"><label>Website<input name="website" tabindex="-1" autocomplete="off"></label></div>';
    echo '<label>'.($fa ? 'شناسه پیگیری' : 'Ticket ID').'</label><input name="ticket" required minlength="24" maxlength="24" pattern="[a-f0-9]{24}" autocomplete="off">';
    echo '<label>'.($fa ? 'ایمیل ثبت‌شده' : 'Email used in your request').'</label><input name="email" type="email" required maxlength="250" autocomplete="email">';
    echo '<button type="submit">'.($fa ? 'مشاهده وضعیت' : 'Check status').'</button></form></section>';
    echo '<p>'.($fa ? 'پیگیری درخواست، تأیید پرداخت یا تحویل کالا نیست.' : 'Ticket status does not verify a payment or product delivery.').'</p></main></body></html>';
}
if (!defined('MASTER_TICKET_STATUS_TEST_MODE')) { masterTicketStatusWeb(); }
