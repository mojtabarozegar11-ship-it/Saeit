<?php
declare(strict_types=1);
/**
 * Bank-specific invoice receipt book for the existing private Zomorod ledger.
 * No PAN, account number, SHABA, bank secrets or live funds are stored here.
 * A receipt is a human-declared accounting event, NOT a bank confirmation.
 */
ini_set('display_errors', '0');
ini_set('log_errors', '1');
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store, private, max-age=0');
header('X-Robots-Tag: noindex, nofollow');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: no-referrer');
header('Vary: Cookie');
header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");

function zbEsc(mixed $v): string { return htmlspecialchars((string)$v, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function zbStop(string $message, int $status): never {
    http_response_code($status);
    echo '<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><title>حساب‌های بانکی زمرد ملل</title>';
    echo '<body style="background:#102018;color:#f3e5c6;font:16px Tahoma;padding:2rem"><h1>'.zbEsc($message).'</h1><a style="color:#ecc97e" href="/business/">بازگشت به مدیریت</a></body></html>';
    exit;
}
final class ZbUserError extends RuntimeException {}
function zbReject(string $message, int $status=422): never { throw new ZbUserError($message, $status); }
function zbPost(string $name): string {
    $v=$_POST[$name]??null;
    if(!is_string($v))zbReject('ساختار ورودی نامعتبر است.');
    return trim($v);
}
function zbCents(string $value): int {
    if(!preg_match('/^(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?$/D',$value))zbReject('مبلغ نامعتبر است.');
    $parts=explode('.',$value,2);
    return ((int)$parts[0])*100+(int)str_pad($parts[1]??'',2,'0');
}
function zbMoney(int $value): string {return number_format($value/100,2,'.',',');}
function zbTableExists(PDO $db,string $table): bool {
    $s=$db->prepare("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?");
    $s->execute([$table]); return (int)$s->fetchColumn()===1;
}
function zbAccounts(PDO $db): array {
    $s=$db->query("SELECT id,code,name,type,active FROM ledger_accounts WHERE code IN ('1011','1012') ORDER BY code");
    $rows=$s->fetchAll();
    if(count($rows)===0)return [];
    if(count($rows)!==2 || $rows[0]['code']!=='1011' || $rows[1]['code']!=='1012'
        || $rows[0]['type']!=='asset' || $rows[1]['type']!=='asset'
        || (int)$rows[0]['active']!==1 || (int)$rows[1]['active']!==1) {
        zbReject('کدینگ حساب‌های بانکی نیازمند بازبینی حسابدار است.',409);
    }
    return $rows;
}
function zbRequireActor(PDO $db,int $id): array {
    $s=$db->prepare('SELECT username,role,active FROM users WHERE id=?');$s->execute([$id]);
    $actor=$s->fetch();
    if(!$actor || (int)$actor['active']!==1 || !in_array($actor['role'],['admin','accountant','manager','viewer'],true))
        zbReject('اجازه دسترسی به دفتر بانکی وجود ندارد.',403);
    return $actor;
}

$method=$_SERVER['REQUEST_METHOD']??'';
if(!in_array($method,['GET','POST'],true)) {header('Allow: GET, POST');zbStop('روش درخواست پشتیبانی نمی‌شود.',405);}
ini_set('session.use_strict_mode','1');
ini_set('session.use_only_cookies','1');
ini_set('session.use_trans_sid','0');
session_name('ZM_BUSINESS');
session_set_cookie_params(['lifetime'=>0,'path'=>'/business/','secure'=>true,'httponly'=>true,'samesite'=>'Strict']);
if(session_start()!==true)zbStop('نشست در دسترس نیست.',503);
$actorId=$_SESSION['uid']??null;
if(!is_int($actorId)||$actorId<1)zbStop('ابتدا وارد میز مدیریت شوید.',403);

try {
    if(!extension_loaded('pdo_sqlite'))throw new RuntimeException('sqlite-unavailable');
    $root=dirname(__DIR__,2);
    $private=$root.'/.private/zomorod-business';
    $dbPath=$private.'/management.sqlite3';
    if(!is_dir($private)||is_link($private)||is_link($dbPath)||!is_file($dbPath)
        || !is_readable($dbPath)||filesize($dbPath)<4096||(fileperms($dbPath)&0777)!==0600)
        throw new RuntimeException('private-db-unavailable');
    $db=new PDO('sqlite:file:'.$dbPath.'?mode=rw',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_TIMEOUT=>12]);
    $db->exec('PRAGMA foreign_keys=ON; PRAGMA busy_timeout=12000;');
    foreach(['users','ledger_accounts','journal_entries','journal_lines','invoices','invoice_payments','audit_events'] as $required)
        if(!zbTableExists($db,$required))throw new RuntimeException('schema-incomplete');
    $actor=zbRequireActor($db,$actorId);
    if(empty($_SESSION['csrf']))$_SESSION['csrf']=bin2hex(random_bytes(32));
    $csrf=(string)$_SESSION['csrf'];
    $accounts=zbAccounts($db);
    $registryReady=zbTableExists($db,'bank_payment_evidence');
    if($accounts!==[] && !$registryReady)zbReject('دفتر پیوست بانکی کامل نیست؛ اصلاح دستی لازم است.',409);

    if($method==='POST') {
        if(!hash_equals($csrf,zbPost('csrf')))zbReject('اعتبار درخواست پایان یافته است.',403);
        $action=zbPost('action');
        if($action==='configure') {
            if($actor['role']!=='admin')zbReject('فقط مدیر سامانه مجاز است.',403);
            if($accounts!==[] || $registryReady)zbReject('حساب‌ها از قبل تنظیم شده‌اند.',409);
            $db->exec('BEGIN IMMEDIATE');
            try {
                if(zbRequireActor($db,$actorId)['role']!=='admin')zbReject('مجوز مدیر لغو شده است.',403);
                if(zbAccounts($db)!==[] || zbTableExists($db,'bank_payment_evidence'))zbReject('تنظیم قبلاً انجام شده است.',409);
                $insert=$db->prepare('INSERT INTO ledger_accounts(code,name,type,active) VALUES(?,?,?,1)');
                $insert->execute(['1011','بانک ملت - حساب جاری و دسته‌چک','asset']);
                $insert->execute(['1012','بانک شهر - حساب پس‌انداز و کارت','asset']);
                $db->exec('CREATE TABLE bank_payment_evidence (
                    id INTEGER PRIMARY KEY,
                    payment_id INTEGER NOT NULL UNIQUE REFERENCES invoice_payments(id),
                    bank_account_id INTEGER NOT NULL REFERENCES ledger_accounts(id),
                    evidence TEXT NOT NULL,
                    created_by INTEGER NOT NULL REFERENCES users(id),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(bank_account_id,evidence))');
                $audit=$db->prepare('INSERT INTO audit_events(user_id,verb,subject,entity_id) VALUES(?,?,?,NULL)');
                $audit->execute([$actorId,'configure','bank-subledgers']);
                $db->exec('COMMIT');
            } catch(Throwable $e) {try{$db->exec('ROLLBACK');}catch(Throwable $ignored){}throw $e;}
        } elseif($action==='payment') {
            if(!in_array($actor['role'],['admin','accountant'],true))zbReject('فقط حسابدار یا مدیر مجاز است.',403);
            if($accounts===[] || !$registryReady)zbReject('ابتدا حساب‌های بانکی را تنظیم کنید.',409);
            $invoiceText=zbPost('invoice_id');
            if(!preg_match('/^[1-9][0-9]{0,17}$/D',$invoiceText))zbReject('شناسه فاکتور نامعتبر است.');
            $invoiceId=filter_var($invoiceText,FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
            if($invoiceId===false)zbReject('شناسه فاکتور نامعتبر است.');
            $bankCode=zbPost('bank_code');
            if(!in_array($bankCode,['1011','1012'],true))zbReject('حساب بانکی نامعتبر است.');
            $bankId=(int)($accounts[$bankCode==='1011'?0:1]['id']);
            $amount=zbCents(zbPost('amount'));
            if($amount<1)zbReject('مبلغ باید مثبت باشد.');
            $date=zbPost('date');
            $when=DateTimeImmutable::createFromFormat('!Y-m-d',$date);
            if(!$when || $when->format('Y-m-d')!==$date)zbReject('تاریخ نامعتبر است.');
            $evidence=zbPost('evidence');
            $length=function_exists('mb_strlen')?mb_strlen($evidence,'UTF-8'):strlen($evidence);
            if($length<6||$length>100||preg_match('/[\x00-\x1f\x7f]/',$evidence))zbReject('شناسه مدرک باید ۶ تا ۱۰۰ نویسه و بدون کاراکتر کنترلی باشد.');
            $db->exec('BEGIN IMMEDIATE');
            try {
                $active=zbRequireActor($db,$actorId);
                if(!in_array($active['role'],['admin','accountant'],true))zbReject('مجوز ثبت مالی لغو شده است.',403);
                $already=$db->prepare('SELECT id FROM bank_payment_evidence WHERE bank_account_id=? AND evidence=? LIMIT 1');
                $already->execute([$bankId,$evidence]);
                if($already->fetchColumn()!==false)zbReject('این مرجع قبلاً برای همین بانک ثبت شده است.',409);
                $s=$db->prepare("SELECT i.id,i.invoice_no,i.kind,i.currency,i.amount,
                    COALESCE((SELECT SUM(p.amount) FROM invoice_payments p WHERE p.invoice_id=i.id),0) AS paid
                    FROM invoices i WHERE i.id=?");
                $s->execute([$invoiceId]);$invoice=$s->fetch();
                if(!$invoice)zbReject('فاکتور وجود ندارد.',404);
                if($invoice['currency']!=='IRR')zbReject('این دو حساب فقط برای فاکتور ریالی هستند.');
                $remaining=(int)$invoice['amount']-(int)$invoice['paid'];
                if($amount>$remaining)zbReject('مبلغ از مانده فاکتور بیشتر است.');
                $docNo='BP-'.gmdate('YmdHis').'-'.strtoupper(bin2hex(random_bytes(6)));
                $note='ثبت دستی و تأییدنشده '.$invoice['invoice_no'].' | '.($invoice['kind']==='sale'?'دریافت':'پرداخت').
                    ' | حساب '.($bankCode==='1011'?'ملت':'شهر');
                $db->prepare('INSERT INTO journal_entries(doc_no,doc_date,note,entered_by) VALUES(?,?,?,?)')
                    ->execute([$docNo,$date,$note,$actorId]);
                $entryId=(int)$db->lastInsertId();
                $offsetCode=$invoice['kind']==='sale'?'1100':'2000';
                $offset=$db->prepare('SELECT id FROM ledger_accounts WHERE code=? AND active=1');
                $offset->execute([$offsetCode]);$offsetId=$offset->fetchColumn();
                if($offsetId===false)zbReject('حساب مقابلِ فاکتور فعال نیست.',409);
                $lines=$db->prepare('INSERT INTO journal_lines(entry_id,account_id,debit,credit,currency) VALUES(?,?,?,?,?)');
                $sale=$invoice['kind']==='sale';
                $lines->execute([$entryId,$bankId,$sale?$amount:0,$sale?0:$amount,'IRR']);
                $lines->execute([$entryId,(int)$offsetId,$sale?0:$amount,$sale?$amount:0,'IRR']);
                $db->prepare('INSERT INTO invoice_payments(invoice_id,amount,paid_on,entry_id,created_by) VALUES(?,?,?,?,?)')
                    ->execute([$invoiceId,$amount,$date,$entryId,$actorId]);
                $paymentId=(int)$db->lastInsertId();
                $db->prepare('INSERT INTO bank_payment_evidence(payment_id,bank_account_id,evidence,created_by) VALUES(?,?,?,?)')
                    ->execute([$paymentId,$bankId,$evidence,$actorId]);
                $db->prepare('INSERT INTO audit_events(user_id,verb,subject,entity_id) VALUES(?,?,?,?)')
                    ->execute([$actorId,'create','bank-invoice-payment',$paymentId]);
                $db->exec('COMMIT');
            } catch(Throwable $e) {try{$db->exec('ROLLBACK');}catch(Throwable $ignored){}throw $e;}
        } else zbReject('عملیات ناشناخته است.',403);
        session_write_close();
        header('Location: /business/banking.php?saved=1',true,303);
        exit;
    }
    $accounts=zbAccounts($db);
    $registryReady=zbTableExists($db,'bank_payment_evidence');
    $balances=[];
    if($accounts!==[]) {
        $s=$db->query("SELECT a.code,COALESCE(SUM(l.debit-l.credit),0) AS balance
            FROM ledger_accounts a LEFT JOIN journal_lines l ON l.account_id=a.id AND l.currency='IRR'
            WHERE a.code IN ('1011','1012') GROUP BY a.id");
        foreach($s as $item)$balances[$item['code']]=(int)$item['balance'];
    }
    $invoices=$db->query("SELECT i.id,i.invoice_no,i.kind,i.amount,i.currency,
        COALESCE((SELECT SUM(amount) FROM invoice_payments WHERE invoice_id=i.id),0) AS paid
        FROM invoices i WHERE i.currency='IRR' ORDER BY i.id DESC LIMIT 100")->fetchAll();
    $history=[];
    if($registryReady) {
        $history=$db->query('SELECT b.id,b.evidence,b.created_at,a.name,i.invoice_no,p.amount,p.paid_on
            FROM bank_payment_evidence b JOIN ledger_accounts a ON a.id=b.bank_account_id
            JOIN invoice_payments p ON p.id=b.payment_id JOIN invoices i ON i.id=p.invoice_id
            ORDER BY b.id DESC LIMIT 100')->fetchAll();
    }
    session_write_close();
} catch(ZbUserError $e) {zbStop($e->getMessage(),$e->getCode());
} catch(Throwable $e) {error_log('zm_banking_error: '.get_class($e));zbStop('دفتر بانکی در دسترس نیست؛ هیچ پرداختی ثبت نشد.',503);}
?><!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>بانک‌ها و دریافت‌های فاکتور | زمرد ملل</title>
<style>
:root{font:16px/1.9 Tahoma,Arial;background:#102018;color:#f3ecd8}*{box-sizing:border-box}body{margin:0}main{max-width:1000px;margin:auto;padding:20px 16px 70px}header{background:#1c3223;border-bottom:1px solid #a9905c;padding:18px}a{color:#f3d289}h1,h2{color:#eacb87}.panel,.warning{background:#1b3023;border:1px solid #547053;border-radius:13px;padding:18px;margin:18px 0}.warning{border-color:#bc9251}label{display:block;margin-top:12px}input,select{font:inherit;padding:10px;color:#f9f2dc;background:#102018;border:1px solid #668368;border-radius:8px;max-width:100%;width:480px}button{padding:11px 20px;margin-top:16px;font:inherit;font-weight:bold;border:0;border-radius:8px;background:#e9cd83;color:#172418;cursor:pointer}table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #47614d;text-align:right;padding:10px}.scroll{overflow-x:auto}.muted{color:#c2cdbc;font-size:14px}:focus-visible{outline:3px solid #f3d289;outline-offset:3px}
</style></head><body><header><a href="/business/">میز مدیریت</a> · <a href="/business/insights.php">گزارش مالی</a> · <strong>دفتر حساب‌های بانکی</strong></header>
<main><h1>بانک ملت و بانک شهر</h1>
<div class="warning">ثبت‌های این صفحه صرفاً <strong>اظهار حسابداری</strong> هستند؛ موجودی واقعی، تسویه، وصول چک و موفقیت پرداخت بانکی را اثبات نمی‌کنند. هیچ تراکنش بانکی اجرا نمی‌شود.</div>
<?php if(($_GET['saved']??'')==='1'): ?><div class="panel">عملیات در دفتر خصوصی ثبت شد.</div><?php endif; ?>
<?php if($accounts===[]): ?>
<div class="panel"><h2>راه‌اندازی کدینگ دو بانک</h2><p>حساب ۱۰۱۱: بانک ملت، جاری و دسته‌چک. حساب ۱۰۱۲: بانک شهر، پس‌انداز و کارت. این مرحله بدون ورود شماره حساب یا کارت، فقط دو زیرحساب دفتری می‌سازد و مانده افتتاحیه تعیین نمی‌کند.</p>
<?php if($actor['role']==='admin'): ?><form method="post" action="/business/banking.php"><input type="hidden" name="csrf" value="<?=zbEsc($csrf)?>"><input type="hidden" name="action" value="configure"><button type="submit">ایجاد دو زیرحساب و دفتر رسیدها</button></form><?php endif; ?></div>
<?php else: ?>
<div class="panel"><h2>مانده دفتری ثبت‌شده (ریال)</h2><div class="scroll"><table><tr><th>کد</th><th>حساب</th><th>مانده حسابداری</th></tr>
<?php foreach($accounts as $account): ?><tr><td><?=zbEsc($account['code'])?></td><td><?=zbEsc($account['name'])?></td><td><?=zbMoney($balances[$account['code']]??0)?></td></tr><?php endforeach; ?></table></div><p class="muted">ارقام صرفاً گردش اسناد ثبت‌شده هستند؛ حساب ۱۰۱۰ عمومی جداست و برای تفکیک مانده‌های قبلی به بازبینی مستند نیاز دارد.</p></div>
<?php if(in_array($actor['role'],['admin','accountant'],true)): ?>
<section class="panel"><h2>ثبت دستی دریافت یا پرداختِ مستند فاکتور</h2><p class="muted">فقط فاکتور ریالی و تا سقف مانده پرداخت‌نشده. مرجع یکسان در همان بانک دوباره پذیرفته نمی‌شود. مدرک باید مستقل از بانک بررسی شود.</p>
<form method="post" action="/business/banking.php" autocomplete="off">
<input type="hidden" name="csrf" value="<?=zbEsc($csrf)?>"><input type="hidden" name="action" value="payment">
<label for="invoice">فاکتور</label><select name="invoice_id" id="invoice" required>
<?php foreach($invoices as $invoice): $left=(int)$invoice['amount']-(int)$invoice['paid'];if($left<=0)continue; ?>
<option value="<?=(int)$invoice['id']?>"><?=zbEsc($invoice['invoice_no'])?> · <?=$invoice['kind']==='sale'?'فروش':'خرید'?> · مانده <?=zbMoney($left)?> ریال</option>
<?php endforeach; ?></select>
<label for="bank">حساب بانکی</label><select id="bank" name="bank_code" required><option value="1011">ملت ـ جاری و دسته‌چک</option><option value="1012">شهر ـ پس‌انداز و کارت</option></select>
<label for="amount">مبلغ ریالی (تا دو رقم اعشار مطابق دفتر)</label><input id="amount" name="amount" inputmode="decimal" required placeholder="100000.00">
<label for="evidence">مرجع مستند انتقال یا رسید (۶ تا ۱۰۰ نویسه)</label><input id="evidence" name="evidence" maxlength="100" minlength="6" required>
<label for="date">تاریخ سند میلادی</label><input id="date" name="date" type="date" value="<?=(new DateTimeImmutable('now',new DateTimeZone('Asia/Tehran')))->format('Y-m-d')?>" required>
<button type="submit">ثبت سند متوازن با حساب بانکی انتخاب‌شده</button></form></section><?php endif; ?>
<section class="panel"><h2>سابقه ثبت‌های بانکی مستندشده</h2><div class="scroll"><table><tr><th>فاکتور</th><th>حساب</th><th>تاریخ</th><th>مبلغ ریال</th><th>مرجع اعلامی</th></tr>
<?php foreach($history as $row): ?><tr><td><?=zbEsc($row['invoice_no'])?></td><td><?=zbEsc($row['name'])?></td><td><?=zbEsc($row['paid_on'])?></td><td><?=zbMoney((int)$row['amount'])?></td><td><?=zbEsc($row['evidence'])?></td></tr><?php endforeach; ?></table></div></section>
<?php endif; ?>
</main></body></html>
