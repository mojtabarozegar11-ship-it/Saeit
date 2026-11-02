<?php
declare(strict_types=1);
/**
 * Standalone Zomorod Melal admin-only role controls.
 * Public route: /business/access.php; existing authenticated session required.
 * Never creates a DB, deletes a user or changes the financial ledger.
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
header('Vary: Cookie');
header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");

function zaEscape(mixed $value): string {
    return htmlspecialchars((string)$value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}
function zaAbort(string $message, int $status): never {
    http_response_code($status);
    echo '<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>کاربران زمرد ملل</title>';
    echo '<body style="font:16px Tahoma,Arial;background:#102018;color:#f1e6c5;padding:36px"><h1>'.zaEscape($message).'</h1><a href="/business/" style="color:#f3d58a">بازگشت به میز مدیریت</a></body></html>';
    exit;
}
function zaInput(string $key): string {
    $input = $_POST[$key] ?? null;
    if (!is_string($input)) zaAbort('ورودی نامعتبر است.', 422);
    return trim($input);
}
final class ZaUserError extends RuntimeException {}
function zaBail(string $message, int $status): never {
    throw new ZaUserError($message, $status);
}

$method = $_SERVER['REQUEST_METHOD'] ?? '';
if (!in_array($method, ['GET','POST'], true)) {
    header('Allow: GET, POST');
    zaAbort('روش درخواست مجاز نیست.', 405);
}
ini_set('session.use_strict_mode', '1');
ini_set('session.use_only_cookies', '1');
ini_set('session.use_trans_sid', '0');
session_name('ZM_BUSINESS');
session_set_cookie_params([
    'lifetime'=>0,'path'=>'/business/','secure'=>true,'httponly'=>true,'samesite'=>'Strict',
]);
if (session_start() !== true) zaAbort('نشست کاربر در دسترس نیست.', 503);
$actor = $_SESSION['uid'] ?? null;
if (!is_int($actor) || $actor < 1) zaAbort('ابتدا به‌عنوان مدیر مجاز وارد شوید.', 403);

try {
    if (!extension_loaded('pdo_sqlite')) throw new RuntimeException('sqlite-unavailable');
    $root = dirname(__DIR__, 2);
    $private = $root.'/.private/zomorod-business';
    $file = $private.'/management.sqlite3';
    if (!is_dir($private) || is_link($private) || is_link($file) || !is_file($file)
        || !is_readable($file) || filesize($file) < 4096 || (fileperms($file)&0777)!==0600) {
        throw new RuntimeException('private-ledger-unavailable');
    }
    // URI mode=rw refuses a missing database instead of silently creating one.
    $db = new PDO('sqlite:file:'.$file.'?mode=rw', null, null, [
        PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,
        PDO::ATTR_TIMEOUT=>12,
    ]);
    $db->exec('PRAGMA foreign_keys=ON; PRAGMA busy_timeout=12000;');
    $getActor = $db->prepare('SELECT username,role,active FROM users WHERE id=? LIMIT 1');
    $getActor->execute([$actor]);
    $current = $getActor->fetch();
    if (!$current || $current['role'] !== 'admin' || (int)$current['active'] !== 1) {
        zaAbort('شما اجازهٔ مدیریت کاربران را ندارید.', 403);
    }

    if (empty($_SESSION['csrf'])) $_SESSION['csrf'] = bin2hex(random_bytes(32));
    $csrf = (string)$_SESSION['csrf'];
    if ($method === 'POST') {
        $provided = zaInput('csrf');
        if (!hash_equals($csrf, $provided)) zaAbort('اعتبار درخواست پایان یافته است.', 403);
        if (zaInput('action') !== 'access_update') zaAbort('عملیات مجاز نیست.', 403);
        $targetText = zaInput('user_id');
        if (!preg_match('/^[1-9][0-9]{0,17}$/D', $targetText)) zaAbort('شناسهٔ کاربر نامعتبر است.', 422);
        $target = filter_var($targetText, FILTER_VALIDATE_INT, ['options'=>['min_range'=>1]]);
        if ($target === false) zaAbort('شناسهٔ کاربر نامعتبر است.', 422);
        if ($target === $actor) zaAbort('تغییر دسترسی حساب خود مدیر از این صفحه مجاز نیست.', 403);
        $role = zaInput('role');
        $active = zaInput('active');
        if (!in_array($role, ['admin','accountant','manager','viewer'], true)
            || !in_array($active, ['0','1'], true)) zaAbort('نقش یا وضعیت نامعتبر است.', 422);

        // Re-check the actor and the target while holding the single SQLite writer lock.
        $db->exec('BEGIN IMMEDIATE');
        try {
            $getActor->execute([$actor]);
            $inTransactionActor = $getActor->fetch();
            if (!$inTransactionActor || $inTransactionActor['role']!=='admin'
                || (int)$inTransactionActor['active']!==1) zaBail('مجوز مدیر لغو شده است.', 403);
            $find = $db->prepare('SELECT role,active FROM users WHERE id=?');
            $find->execute([$target]);
            $before = $find->fetch();
            if (!$before) zaBail('کاربر موردنظر وجود ندارد.', 404);
            if ($before['role']==='admin' && (int)$before['active']===1
                && ($role!=='admin' || $active==='0')) {
                $remaining = $db->prepare("SELECT COUNT(*) FROM users WHERE id<>? AND role='admin' AND active=1");
                $remaining->execute([$target]);
                if ((int)$remaining->fetchColumn()<1) zaBail('حداقل یک مدیر فعال باید باقی بماند.', 403);
            }
            $update = $db->prepare('UPDATE users SET role=?,active=? WHERE id=?');
            $update->execute([$role,(int)$active,$target]);
            $audit = $db->prepare('INSERT INTO audit_events(user_id,verb,subject,entity_id) VALUES(?,?,?,?)');
            $audit->execute([$actor,'update','user-access',$target]);
            $db->exec('COMMIT');
        } catch (Throwable $e) {
            try {$db->exec('ROLLBACK');} catch (Throwable $ignored) {}
            throw $e;
        }
        session_write_close();
        header('Location: /business/access.php?updated=1',true,303);
        exit;
    }
    $users = $db->query('SELECT id,username,role,active FROM users ORDER BY id')->fetchAll();
    session_write_close();
} catch (ZaUserError $exception) {
    zaAbort($exception->getMessage(), $exception->getCode());
} catch (Throwable $exception) {
    error_log('zm_access_server_error: '.get_class($exception));
    zaAbort('مدیریت کاربران موقتاً در دسترس نیست؛ هیچ تغییری ثبت نشد.', 503);
}
?><!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>مدیریت دسترسی کاربران | زمرد ملل</title>
<style>
:root{font-family:Tahoma,Arial,sans-serif;background:#102018;color:#f2ecd8;line-height:1.9}*{box-sizing:border-box}body{margin:0;background:linear-gradient(135deg,#12241a,#2a412f);min-height:100vh}header{padding:18px max(20px,calc((100vw - 1050px)/2));background:#15291d;border-bottom:1px solid #b79b5c;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:15px}a{color:#f2d18d}header strong{color:#f2d18d;font-size:21px}main{max-width:1050px;margin:auto;padding:28px 18px 80px}h1,h2{color:#f2d18d}p{color:#cbd3c4}.notice,.panel{border:1px solid #506c51;background:#1b2d22;border-radius:15px;padding:18px;margin:18px 0}.notice{border-right:4px solid #b9d49a}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}.user{border:1px solid #4f654d;border-radius:13px;padding:17px;background:#17281d}.user h2{font-size:17px;margin:0 0 8px}.muted{color:#bfcdbb;font-size:13px}label{display:block;margin:8px 0 4px}select{background:#102018;color:#f2ecd8;border:1px solid #809178;border-radius:8px;width:100%;font:inherit;padding:10px}button{margin-top:14px;background:#ebc878;color:#122018;font:inherit;font-weight:700;border:0;border-radius:9px;padding:10px 18px;cursor:pointer;min-height:44px}button:focus-visible,a:focus-visible,select:focus-visible{outline:3px solid #f2d18d;outline-offset:3px}.state{color:#e3d092;font-size:14px}footer{text-align:center;color:#aebfa9;font-size:12px;padding:30px}@media(max-width:600px){main{padding:17px 12px}header{padding:16px}}
</style></head><body>
<header><strong>زمرد ملل · کنترل کاربران</strong><div><span><?=zaEscape($current['username'])?></span> · <a href="/business/">میز مدیریت</a> · <a href="/business/insights.php">گزارش مالی</a></div></header>
<main><h1>مدیریت نقش و وضعیت کاربران</h1>
<p>فقط مدیر فعال مجاز است دسترسی دیگران را تغییر دهد. هویت، اسناد و ردپای عملیات حذف نمی‌شوند؛ تغییر نقش یا غیرفعال‌سازی در درخواست بعدی کاربر اعمال می‌شود.</p>
<?php if (($_GET['updated']??'')==='1'): ?><div class="notice">تغییر دسترسی با موفقیت ثبت شد.</div><?php endif; ?>
<div class="panel"><h2>کاربران ثبت‌شده</h2><div class="grid">
<?php foreach ($users as $row): ?>
<article class="user"><h2><?=zaEscape($row['username'])?></h2><div class="state">نقش فعلی: <?=zaEscape($row['role'])?> · وضعیت: <?=((int)$row['active']===1)?'فعال':'غیرفعال'?></div>
<?php if ((int)$row['id']===$actor): ?>
<p class="muted">حساب مدیرِ واردشده از این بخش قابل تغییر نیست.</p>
<?php else: ?>
<form method="post" action="/business/access.php" autocomplete="off">
<input type="hidden" name="action" value="access_update"><input type="hidden" name="csrf" value="<?=zaEscape($csrf)?>"><input type="hidden" name="user_id" value="<?=(int)$row['id']?>">
<label for="role-<?=(int)$row['id']?>">نقش</label><select id="role-<?=(int)$row['id']?>" name="role">
<?php foreach (['admin'=>'مدیر','accountant'=>'حسابدار','manager'=>'مدیر اجرایی','viewer'=>'مشاهده‌گر'] as $code=>$label): ?>
<option value="<?=zaEscape($code)?>"<?=$row['role']===$code?' selected':''?>><?=zaEscape($label)?></option>
<?php endforeach; ?></select>
<label for="active-<?=(int)$row['id']?>">وضعیت حساب</label><select id="active-<?=(int)$row['id']?>" name="active"><option value="1"<?=(int)$row['active']===1?' selected':''?>>فعال</option><option value="0"<?=(int)$row['active']===0?' selected':''?>>غیرفعال</option></select>
<button type="submit">ثبت تغییر دسترسی</button>
</form>
<?php endif; ?></article>
<?php endforeach; ?></div></div>
<p class="muted">برای ایجاد کاربر جدید یا تغییر گذرواژه از امکانات میز مدیریت اصلی استفاده کنید. هیچ تغییر خودکار در نقش کاربران انجام نمی‌شود.</p>
</main><footer>شرکت کشت و صنعت زمرد ملل · کنترل دسترسی داخلی · فقط مدیر مجاز</footer></body></html>
