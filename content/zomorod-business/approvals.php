<?php
declare(strict_types=1);
/** Isolated, read-only approvals register for the existing PHP business desk. */
ini_set('display_errors', '0');
ini_set('log_errors', '1');
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store, max-age=0');
header('X-Robots-Tag: noindex, nofollow');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: no-referrer');
header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'");

function zmApprovalEscape(mixed $s): string {
    return htmlspecialchars((string)$s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}
function zmApprovalStop(int $status, string $message): never {
    http_response_code($status);
    echo '<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><title>زمرد ملل · دفتر مصوبات</title><body style="font-family:Tahoma,Arial;background:#182b1e;color:#f4e5b3;padding:28px"><h1>دفتر مصوبات زمرد ملل</h1><p>'.zmApprovalEscape($message).'</p><a style="color:#f0d185" href="/business/">بازگشت به میز مدیریت</a></body></html>';
    exit;
}
if(($_SERVER['REQUEST_METHOD']??'GET')!=='GET')zmApprovalStop(405,'این صفحه فقط برای مشاهده است.');
if(!extension_loaded('session')||!class_exists('SQLite3'))zmApprovalStop(503,'بخش احراز هویت در دسترس نیست.');
if(session_status()!==PHP_SESSION_ACTIVE){
    session_name('ZM_BUSINESS');
    session_set_cookie_params(['lifetime'=>0,'path'=>'/business/','secure'=>true,'httponly'=>true,'samesite'=>'Strict']);
    session_start();
}
$uid=(int)($_SESSION['uid']??0);
if($uid<=0)zmApprovalStop(403,'ابتدا وارد میز مدیریت شوید.');
$root=dirname(__DIR__,3);
$private=$root.'/.private/zomorod-business';
$dbFile=$private.'/management.sqlite3';
$snapshotFile=$private.'/approvals_snapshot.json';
if(!is_dir($private)||is_link($private)||!is_file($dbFile)||is_link($dbFile))zmApprovalStop(503,'اطلاعات خصوصی دفتر در دسترس نیست.');
try{
    $db=new SQLite3($dbFile,SQLITE3_OPEN_READONLY);
    $query=$db->prepare('SELECT role,active FROM users WHERE id=:uid LIMIT 1');
    if($query===false)throw new RuntimeException('user query unavailable');
    $query->bindValue(':uid',$uid,SQLITE3_INTEGER);
    $result=$query->execute();
    $user=$result===false?false:$result->fetchArray(SQLITE3_ASSOC);
    $db->close();
    if(!$user||(int)($user['active']??0)!==1||!in_array((string)$user['role'],['admin','accountant','manager','viewer'],true)){
        zmApprovalStop(403,'حساب فعال و مجاز برای مشاهده شناسایی نشد.');
    }
    if(!is_file($snapshotFile)||is_link($snapshotFile))zmApprovalStop(503,'دفتر مصوبات هنوز در فضای خصوصی نصب نشده است.');
    $size=filesize($snapshotFile);
    if($size===false||$size<20||$size>2000000)zmApprovalStop(503,'اندازه پرونده مصوبات نامعتبر است.');
    $data=json_decode((string)file_get_contents($snapshotFile),true,128,JSON_THROW_ON_ERROR);
    if(!is_array($data)||($data['version']??null)!==1||!is_array($data['summary']??null)||!is_array($data['items']??null)){
        zmApprovalStop(503,'ساختار پرونده مصوبات نامعتبر است.');
    }
    $items=$data['items'];
    $summary=$data['summary'];
    if(count($items)!==(int)($summary['records']??-1))zmApprovalStop(503,'تعداد ردیف‌های پرونده با خلاصه آن سازگار نیست.');
    $count=['approved'=>0,'rejected'=>0,'undetermined'=>0];$jobs=0;$seen=[];
    foreach($items as $entry){
        if(!is_array($entry))zmApprovalStop(503,'ردیف نامعتبر در پرونده مصوبات.');
        $key=(string)($entry['external_key']??'');
        $decision=(string)($entry['decision']??'');
        if(!preg_match('/^ZM-(?:[0-9]{3}[A-Z]?|EX-[0-9]{2,3}-[A-Z])$/D',$key)||isset($seen[$key])||!isset($count[$decision])){
            zmApprovalStop(503,'شناسه یا تصمیم نامعتبر در پرونده مصوبات.');
        }
        $seen[$key]=true;$count[$decision]++;
        $n=$entry['planned_operational_jobs']??null;
        if($decision==='approved'){
            if(!is_int($n)||$n<0)zmApprovalStop(503,'اشتغال برنامه‌ای نامعتبر در پرونده.');
            $jobs+=$n;
        }elseif($n!==null)zmApprovalStop(503,'اشتغال تخصیص‌یافته به طرح غیرمصوب.');
        if(($entry['actual_employees_hired']??null)!==null)zmApprovalStop(503,'داده استخدام واقعی نباید از این پرونده خوانده شود.');
    }
    if($jobs!==(int)($summary['planned_operational_jobs']??-1))zmApprovalStop(503,'جمع اشتغال برنامه‌ای با ردیف‌ها تطبیق ندارد.');
    foreach($count as $decision=>$n)if($n!==(int)($summary[$decision]??-1))zmApprovalStop(503,'شمار مصوبات با خلاصه تطبیق ندارد.');
}catch(Throwable $e){
    error_log('ZM APPROVALS READ ERROR ['.get_class($e).']');
    zmApprovalStop(503,'نمایش دفتر مصوبات به دلیل خطای کنترل متوقف شد.');
}
$labels=['approved'=>'مصوب','rejected'=>'ردشده','undetermined'=>'نامشخص'];
echo '<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>زمرد ملل · دفتر مصوبات</title>';
echo '<style>:root{font-family:Tahoma,Arial,sans-serif;color:#f4ecd5;background:#172b1b}body{margin:0}header{padding:22px;background:#24462b;border-bottom:2px solid #cfad66}h1,h2{color:#e9cc87}main{max-width:1350px;margin:auto;padding:20px}a{color:#e9cc87}section{background:#203925;border:1px solid #806b48;border-radius:14px;padding:17px;margin:16px 0}.tiles{display:flex;flex-wrap:wrap;gap:12px}.tile{background:#2e5132;border:1px solid #b89555;border-radius:10px;padding:15px;min-width:145px}.number{font-size:24px;color:#ffdf9d;font-weight:bold}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:750px}th,td{padding:11px;text-align:right;border-bottom:1px solid #617354}th{color:#f2d08a;background:#2e5132}.warn{border-right:4px solid #d5a352;padding:10px;background:#50482e}small{color:#d5d8c5}</style>';
echo '<header><h1>شرکت کشت و صنعت زمرد ملل · دفتر مصوبات</h1><a href="/business/">بازگشت به میز مدیریت و حسابداری</a></header><main>';
echo '<section><h2>خلاصه ثبت طرح‌ها</h2><div class="tiles">';
foreach(['records'=>'ردیف دفتر','approved'=>'مصوب','rejected'=>'ردشده','undetermined'=>'نامشخص','planned_operational_jobs'=>'اشتغال برنامه‌ای'] as $key=>$title){
    echo '<div class="tile"><div class="number">'.zmApprovalEscape($summary[$key]??0).'</div>'.zmApprovalEscape($title).'</div>';
}
echo '</div><p class="warn">این اعداد برنامه و مصوبه‌اند؛ استخدام واقعی، مجوز هزینه، پرداخت یا سند حسابداری نیستند. تصمیم طرح ۱۴۲ نیازمند تطبیق با سابقه است.</p></section>';
echo '<section><h2>ردیف‌های دفتر</h2><div class="scroll"><table><tr><th>شناسه</th><th>عنوان</th><th>تصمیم</th><th>اشتغال برنامه‌ای</th><th>کنترل عنوان/تصمیم</th></tr>';
foreach($items as $entry){
    $decision=(string)$entry['decision'];
    $verified=($entry['official_title_verified']??false)===true;
    $review=($entry['review_required']??false)===true;
    $jobsText=$entry['planned_operational_jobs']===null?'—':(string)$entry['planned_operational_jobs'];
    $flag=$review?'نیازمند تطبیق تصمیم':($verified?'عنوان تأییدشده':'عنوان نیازمند راستی‌آزمایی');
    echo '<tr><td>'.zmApprovalEscape($entry['external_key']).'</td><td>'.zmApprovalEscape($entry['title']??'').'</td><td>'.zmApprovalEscape($labels[$decision]).'</td><td>'.zmApprovalEscape($jobsText).'</td><td>'.zmApprovalEscape($flag).'</td></tr>';
}
echo '</table></div></section></main></html>';
