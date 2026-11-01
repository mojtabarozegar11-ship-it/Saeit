<?php
declare(strict_types=1);
/**
 * Zomorod Melal / standalone private auction register.
 * Intended route: /business/auctions/ (additive, no live app replacement).
 * All decisions are internal records; NEVER submits bids or moves money.
 */
ini_set('display_errors','0');
ini_set('log_errors','1');
header('Cache-Control: no-store, max-age=0');
header('X-Robots-Tag: noindex, nofollow');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: no-referrer');
header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");

function aucEsc(mixed $value):string{return htmlspecialchars((string)$value,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
function aucFail(int $code,string $message):never{
    http_response_code($code);header('Content-Type: text/html; charset=utf-8');
    echo '<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><title>مزایده زمرد ملل</title><body style="font:16px Tahoma;background:#182e20;color:#f4e6c4;padding:24px"><h1>مدیریت مزایده‌ها</h1><p>'.aucEsc($message).'</p><a style="color:#ffe2a1" href="/business/">بازگشت به مدیریت</a></body></html>';
    exit;
}
function aucPost(string $field):string{return trim((string)($_POST[$field]??''));}
function aucDocumentAccess(string $role,string $category):bool{
    $roles=[
        'notice'=>['admin','manager','accountant','viewer'],
        'valuation'=>['admin','manager','accountant'],
        'deposit'=>['admin','accountant'],
        'technical'=>['admin','manager'],
        'contract'=>['admin','manager'],
        'receipt'=>['admin','manager','accountant'],
        'other'=>['admin','manager','accountant']
    ];
    return isset($roles[$category])&&in_array($role,$roles[$category],true);
}
function aucMinor(string $value):int{
    if(!preg_match('/\A(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?\z/D',$value))aucFail(422,'مبلغ باید عدد مثبت یا صفر با حداکثر دو رقم اعشار باشد.');
    $bits=explode('.',$value,2);return (int)$bits[0]*100+(int)str_pad($bits[1]??'',2,'0');
}
function aucFmt(int $value):string{return number_format($value/100,2,'.',',');}
function aucSql(SQLite3 $db,string $sql,array $values=[]):SQLite3Result{
    $statement=$db->prepare($sql);
    if($statement===false)throw new RuntimeException('prepare failed');
    foreach(array_values($values) as $i=>$value)$statement->bindValue($i+1,$value,is_int($value)?SQLITE3_INTEGER:SQLITE3_TEXT);
    $result=$statement->execute();
    if($result===false)throw new RuntimeException('execute failed');
    return $result;
}
function aucRows(SQLite3 $db,string $sql,array $values=[]):array{
    $out=[];$result=aucSql($db,$sql,$values);
    while($row=$result->fetchArray(SQLITE3_ASSOC))$out[]=$row;
    return $out;
}
function aucHasVerifiedDocument(SQLite3 $db,string $private,int $auctionId,array $categories):bool{
    if(!$categories)return false;
    $dir=$private.'/auction-documents';
    if(!is_dir($dir)||is_link($dir))return false;
    $marks=implode(',',array_fill(0,count($categories),'?'));
    $documents=aucRows($db,'SELECT storage_key,mime,size_bytes,sha256 FROM auction_documents WHERE auction_id=? AND category IN ('.$marks.') ORDER BY id DESC',array_merge([$auctionId],$categories));
    $types=['pdf'=>'application/pdf','jpg'=>'image/jpeg','png'=>'image/png'];
    foreach($documents as $document){
        $key=(string)$document['storage_key'];
        if(!preg_match('/\A[a-f0-9]{32}\.(pdf|jpg|png)\z/D',$key,$matches))continue;
        if(($types[$matches[1]]??null)!==(string)$document['mime'])continue;
        $path=$dir.'/'.$key;
        if(!is_file($path)||is_link($path))continue;
        $bytes=filesize($path);
        if($bytes===false||$bytes<1||$bytes>8388608||$bytes!==(int)$document['size_bytes'])continue;
        $recorded=(string)$document['sha256'];
        if(!preg_match('/\A[a-f0-9]{64}\z/D',$recorded))continue;
        $actual=hash_file('sha256',$path);
        if(is_string($actual)&&hash_equals($recorded,$actual))return true;
    }
    return false;
}
function aucState(array $events):array{
    $reviews=['technical'=>null,'financial'=>null,'legal'=>null];
    $executive=null;$submission=null;$outcome=null;
    foreach($events as $e){
        if(array_key_exists((string)$e['kind'],$reviews))$reviews[$e['kind']]=$e;
        elseif($e['kind']==='executive')$executive=$e;
        elseif($e['kind']==='submission')$submission=$e;
        elseif(in_array($e['kind'],['outcome','cancel'],true))$outcome=$e;
    }
    $allApproved=true;
    foreach($reviews as $r)if(!$r||$r['decision']!=='approved')$allApproved=false;
    $state='در حال ارزیابی';
    if($allApproved)$state='منتظر تصویب مدیرعامل';
    if($executive)$state='مصوب داخلی ـ بدون ارسال پیشنهاد';
    if($submission)$state='شرکت در مزایده (ثبت دستی رسید)';
    if($outcome)$state=['won'=>'برنده طبق مدرک ثبت‌شده','lost'=>'ناموفق طبق مدرک ثبت‌شده','cancelled'=>'مختومه بدون شرکت'][$outcome['decision']]??'مختومه';
    return ['reviews'=>$reviews,'executive'=>$executive,'submission'=>$submission,'outcome'=>$outcome,'label'=>$state];
}
if(!extension_loaded('session')||!class_exists('SQLite3'))aucFail(503,'احراز هویت/SQLite روی هاست آماده نیست.');
if(session_status()!==PHP_SESSION_ACTIVE){
    session_name('ZM_BUSINESS');
    session_set_cookie_params(['lifetime'=>0,'path'=>'/business/','secure'=>true,'httponly'=>true,'samesite'=>'Strict']);
    session_start();
}
$uid=(int)($_SESSION['uid']??0);
if($uid<1)aucFail(403,'ابتدا وارد میز مدیریت شوید.');
$home=dirname(__DIR__,3);
$private=$home.'/.private/zomorod-business';
$master=$private.'/management.sqlite3';
if(!is_dir($private)||is_link($private)||!is_file($master)||is_link($master))aucFail(503,'فضای خصوصی احراز هویت در دسترس نیست.');
try{
    $auth=new SQLite3($master,SQLITE3_OPEN_READONLY);
    $user=aucRows($auth,'SELECT id,role,active FROM users WHERE id=? LIMIT 1',[$uid])[0]??null;
    if(!$user||(int)$user['active']!==1||!in_array($user['role'],['admin','manager','accountant','viewer'],true))aucFail(403,'کاربر فعال و مجاز یافت نشد.');
    $role=(string)$user['role'];
    $projects=aucRows($auth,'SELECT id,title FROM projects ORDER BY id DESC LIMIT 100');
}catch(Throwable $e){
    error_log('ZM AUCTION AUTH ['.get_class($e).']');aucFail(503,'تأیید نقش کاربر ممکن نیست.');
}
if(empty($_SESSION['zm_auction_csrf']))$_SESSION['zm_auction_csrf']=bin2hex(random_bytes(32));
$csrf=(string)$_SESSION['zm_auction_csrf'];
$method=(string)($_SERVER['REQUEST_METHOD']??'GET');
if(!in_array($method,['GET','POST'],true))aucFail(405,'درخواست مجاز نیست.');
$file=$private.'/auctions_v1.sqlite3';
if(is_link($file)|| (file_exists($file)&&!is_file($file)))aucFail(503,'فایل ثبت مزایده معتبر نیست.');
if($method==='POST'){
    if($role==='viewer')aucFail(403,'کاربر فقط‌خواندنی مجوز ثبت ندارد.');
    if(!hash_equals($csrf,aucPost('csrf')))aucFail(403,'اعتبار فرم پایان یافته است.');
}
$db=null;
try{
    if(is_file($file)||$method==='POST'){
        $flags=$method==='POST'?(SQLITE3_OPEN_READWRITE|SQLITE3_OPEN_CREATE):SQLITE3_OPEN_READONLY;
        $db=new SQLite3($file,$flags);
        $db->busyTimeout(5000);
        if($method==='POST'){
            if(!chmod($file,0600))throw new RuntimeException('db private chmod failed');
            $db->exec('PRAGMA foreign_keys=ON');
            $db->exec("CREATE TABLE IF NOT EXISTS auctions(
                id INTEGER PRIMARY KEY,
                reference TEXT NOT NULL UNIQUE,
                direction TEXT NOT NULL CHECK(direction IN ('buy','sell')),
                title TEXT NOT NULL, organizer TEXT NOT NULL, asset_type TEXT NOT NULL,
                location TEXT NOT NULL DEFAULT '', notice_url TEXT NOT NULL DEFAULT '',
                deadline_utc TEXT NOT NULL, currency TEXT NOT NULL CHECK(currency IN ('IRR','USD','EUR','AED')),
                estimate_minor INTEGER NOT NULL CHECK(estimate_minor>=0),
                deposit_minor INTEGER NOT NULL CHECK(deposit_minor>=0),
                limit_minor INTEGER NOT NULL CHECK(limit_minor>=0),
                project_id INTEGER NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '',
                created_by INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )");
            $db->exec("CREATE TABLE IF NOT EXISTS auction_events(
                id INTEGER PRIMARY KEY, auction_id INTEGER NOT NULL REFERENCES auctions(id),
                kind TEXT NOT NULL CHECK(kind IN ('technical','financial','legal','executive','submission','outcome','cancel')),
                decision TEXT NOT NULL CHECK(decision IN ('approved','rejected','submitted','won','lost','cancelled')),
                actor_id INTEGER NOT NULL, evidence TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )");
            $db->exec('CREATE INDEX IF NOT EXISTS zm_auction_event_idx ON auction_events(auction_id,id)');
            if(!$db->exec("CREATE TABLE IF NOT EXISTS auction_documents(
                id INTEGER PRIMARY KEY, auction_id INTEGER NOT NULL REFERENCES auctions(id),
                category TEXT NOT NULL CHECK(category IN ('notice','valuation','deposit','technical','contract','receipt','other')),
                original_name TEXT NOT NULL, mime TEXT NOT NULL, storage_key TEXT NOT NULL UNIQUE,
                size_bytes INTEGER NOT NULL CHECK(size_bytes>0 AND size_bytes<=8388608),
                sha256 TEXT NOT NULL, actor_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"))throw new RuntimeException('documents schema failed');
            if(!$db->exec("CREATE TABLE IF NOT EXISTS auction_scenarios(
                id INTEGER PRIMARY KEY, auction_id INTEGER NOT NULL REFERENCES auctions(id),
                proceeds_minor INTEGER NOT NULL CHECK(proceeds_minor>=0),
                basis_minor INTEGER NOT NULL CHECK(basis_minor>=0),
                costs_minor INTEGER NOT NULL CHECK(costs_minor>=0),
                reserve_minor INTEGER NOT NULL CHECK(reserve_minor>=0),
                rationale TEXT NOT NULL, actor_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"))throw new RuntimeException('scenario schema failed');
        }
    }
}catch(Throwable $e){error_log('ZM AUCTION OPEN ['.get_class($e).']');aucFail(503,'دفتر خصوصی مزایده قابل بازکردن نیست.');}
if($method==='GET'&&isset($_GET['document'])){
    $documentId=filter_var($_GET['document'],FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
    if(!$db||!$documentId||!$db->querySingle("SELECT 1 FROM sqlite_master WHERE type='table' AND name='auction_documents'"))aucFail(404,'مدرک یافت نشد.');
    $document=aucRows($db,'SELECT * FROM auction_documents WHERE id=?',[(int)$documentId])[0]??null;
    if(!$document||!aucDocumentAccess($role,(string)$document['category'])||!preg_match('/\\A[a-f0-9]{32}\\.(pdf|jpg|png)\\z/D',(string)$document['storage_key']))aucFail(404,'مدرک یافت نشد.');
    $docDir=$private.'/auction-documents';$docFile=$docDir.'/'.(string)$document['storage_key'];
    if(!is_dir($docDir)||is_link($docDir)||!is_file($docFile)||is_link($docFile))aucFail(404,'فایل سند در دسترس نیست.');
    $mime=(string)$document['mime'];
    if(!in_array($mime,['application/pdf','image/jpeg','image/png'],true))aucFail(404,'نوع مدرک مجاز نیست.');
    $actual=hash_file('sha256',$docFile);
    if(!hash_equals((string)$document['sha256'],(string)$actual))aucFail(503,'یکپارچگی فایل سند تأیید نشد.');
    $extension=pathinfo($docFile,PATHINFO_EXTENSION);
    header('Content-Type: '.$mime);
    header('Content-Disposition: attachment; filename="zomorod-auction-document-'.(int)$document['id'].'.'.$extension.'"');
    header('Content-Length: '.(int)filesize($docFile));
    readfile($docFile);exit;
}
if($method==='POST'){
    $action=aucPost('action');
    if(!in_array($action,['create','review','executive','submission','outcome','cancel','document','scenario'],true))aucFail(403,'عملیات مجاز نیست.');
    $pendingUpload=null;
    try{
        if(!$db||!$db->exec('BEGIN IMMEDIATE'))throw new RuntimeException('transaction start failed');
        if($action==='create'){
            if(!in_array($role,['admin','manager'],true))aucFail(403,'ثبت مزایده تنها برای مدیر و مسئول پروژه مجاز است.');
            $reference=aucPost('reference');$direction=aucPost('direction');
            $title=aucPost('title');$organizer=aucPost('organizer');
            $asset=aucPost('asset_type');$location=aucPost('location');
            $notice=aucPost('notice_url');$deadline=aucPost('deadline_utc');
            $currency=aucPost('currency');$notes=aucPost('notes');
            $project=(int)aucPost('project_id');
            if(!preg_match('/\A[A-Za-z0-9_-]{4,50}\z/D',$reference)||
               !in_array($direction,['buy','sell'],true)||
               $title===''||strlen($title)>260||$organizer===''||strlen($organizer)>240||
               $asset===''||strlen($asset)>160||strlen($location)>240||
               strlen($notes)>2000||!in_array($currency,['IRR','USD','EUR','AED'],true))aucFail(422,'مشخصات مزایده ناقص یا نامعتبر است.');
            if($notice!==''&&(!filter_var($notice,FILTER_VALIDATE_URL)||!str_starts_with($notice,'https://')||strlen($notice)>500))aucFail(422,'نشانی آگهی باید HTTPS معتبر باشد.');
            $date=DateTimeImmutable::createFromFormat('!Y-m-d\TH:i',$deadline,new DateTimeZone('UTC'));
            if(!$date||$date->format('Y-m-d\TH:i')!==$deadline||$date->getTimestamp()<=time())aucFail(422,'مهلت باید تاریخ و ساعت آینده به وقت UTC باشد.');
            if($project<0)aucFail(422,'ارجاع پروژه نامعتبر است.');
            if($project>0&&!aucRows($auth,'SELECT id FROM projects WHERE id=?',[$project]))aucFail(422,'پروژه انتخاب‌شده وجود ندارد.');
            $estimate=aucMinor(aucPost('estimate'));$deposit=aucMinor(aucPost('deposit'));$limit=aucMinor(aucPost('limit'));
            if($direction==='buy'&&$limit>0&&$estimate>0&&$limit>$estimate*10)aucFail(422,'سقف پیشنهاد داخلی باید بررسی اقتصادی مجدد شود.');
            $exists=aucRows($db,'SELECT id FROM auctions WHERE reference=?',[$reference]);
            if($exists)aucFail(409,'این شماره مزایده قبلاً ثبت شده است.');
            aucSql($db,'INSERT INTO auctions(reference,direction,title,organizer,asset_type,location,notice_url,deadline_utc,currency,estimate_minor,deposit_minor,limit_minor,project_id,notes,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                [$reference,$direction,$title,$organizer,$asset,$location,$notice,$date->format('Y-m-d H:i:s'),$currency,$estimate,$deposit,$limit,$project,$notes,$uid]);
        }else{
            $id=(int)aucPost('auction_id');
            $auction=$id>0?(aucRows($db,'SELECT * FROM auctions WHERE id=?',[$id])[0]??null):null;
            if(!$auction)aucFail(404,'پرونده مزایده پیدا نشد.');
            $events=aucRows($db,'SELECT * FROM auction_events WHERE auction_id=? ORDER BY id',[$id]);
            $state=aucState($events);
            if($state['outcome']&&$action!=='document')aucFail(409,'پرونده مختومه است؛ تغییر جدید مجاز نیست.');
            $evidence=aucPost('evidence');
            if(!in_array($action,['document','scenario'],true)&&(strlen($evidence)<10||strlen($evidence)>1500))aucFail(422,'توضیح و مرجع تصمیم باید بین ۱۰ تا ۱۵۰۰ بایت باشد.');
            if($action==='review'){
                if($state['executive']||$state['submission'])aucFail(409,'پس از تصویب نهایی، بررسی‌های قبلی تغییر نمی‌کنند.');
                $kind=aucPost('kind');$decision=aucPost('decision');
                $permissions=['technical'=>['admin','manager'],'financial'=>['admin','accountant'],'legal'=>['admin','manager']];
                if(!isset($permissions[$kind])||!in_array($role,$permissions[$kind],true)||!in_array($decision,['approved','rejected'],true))aucFail(403,'نوع داوری یا نقش مجاز نیست.');
                if($kind==='financial'&&$uid===(int)$auction['created_by'])aucFail(403,'داور مالی باید مستقل از ثبت‌کننده باشد.');
                aucSql($db,'INSERT INTO auction_events(auction_id,kind,decision,actor_id,evidence) VALUES(?,?,?,?,?)',[$id,$kind,$decision,$uid,$evidence]);
            }elseif($action==='scenario'){
                if(!in_array($role,['admin','manager','accountant'],true))aucFail(403,'مجوز تحلیل اقتصادی ندارید.');
                $rationale=aucPost('rationale');
                if(strlen($rationale)<10||strlen($rationale)>1500)aucFail(422,'فرضیات تحلیل اقتصادی باید مستند باشد.');
                $proceeds=aucMinor(aucPost('proceeds'));
                $basis=aucMinor(aucPost('basis'));
                $costs=aucMinor(aucPost('costs'));
                $reserve=aucMinor(aucPost('reserve'));
                if($proceeds<=0||$basis<=0)aucFail(422,'جریان ورودی و بهای پایه پیش‌بینی‌شده باید مثبت باشد.');
                aucSql($db,'INSERT INTO auction_scenarios(auction_id,proceeds_minor,basis_minor,costs_minor,reserve_minor,rationale,actor_id) VALUES(?,?,?,?,?,?,?)',
                    [$id,$proceeds,$basis,$costs,$reserve,$rationale,$uid]);
            }elseif($action==='document'){
                if(!in_array($role,['admin','manager','accountant'],true))aucFail(403,'مجوز ثبت سند ندارید.');
                $category=aucPost('category');
                if(!aucDocumentAccess($role,$category))aucFail(403,'دسترسی به این نوع مدرک مجاز نیست.');
                $upload=$_FILES['document']??null;
                if(!is_array($upload)||($upload['error']??UPLOAD_ERR_NO_FILE)!==UPLOAD_ERR_OK||
                   !is_string($upload['tmp_name']??null)||!is_uploaded_file($upload['tmp_name']))aucFail(422,'فایل بارگذاری‌شده معتبر نیست.');
                $size=(int)($upload['size']??0);$original=(string)($upload['name']??'');
                if($size<1||$size>8388608||strlen($original)<1||strlen($original)>180||
                   preg_match('/[\\x00-\\x1f\\/\\\\]/',$original))aucFail(422,'اندازه یا نام فایل مجاز نیست.');
                $mime=(new finfo(FILEINFO_MIME_TYPE))->file($upload['tmp_name']);
                $allowed=['application/pdf'=>'pdf','image/jpeg'=>'jpg','image/png'=>'png'];
                if(!is_string($mime)||!isset($allowed[$mime]))aucFail(422,'تنها PDF، JPEG و PNG مجاز است.');
                $docDir=$private.'/auction-documents';
                if(!is_dir($docDir)&&!mkdir($docDir,0700))throw new RuntimeException('document directory create failed');
                if(is_link($docDir)||!is_dir($docDir)||!chmod($docDir,0700))throw new RuntimeException('document directory unsafe');
                $storageKey=bin2hex(random_bytes(16)).'.'.$allowed[$mime];
                $target=$docDir.'/'.$storageKey;
                if(!move_uploaded_file($upload['tmp_name'],$target))throw new RuntimeException('document move failed');
                $pendingUpload=$target;
                if(!chmod($target,0600))throw new RuntimeException('document chmod failed');
                $digest=hash_file('sha256',$target);
                if(!is_string($digest))throw new RuntimeException('document digest failed');
                aucSql($db,'INSERT INTO auction_documents(auction_id,category,original_name,mime,storage_key,size_bytes,sha256,actor_id) VALUES(?,?,?,?,?,?,?,?)',
                    [$id,$category,$original,$mime,$storageKey,$size,$digest,$uid]);
            }elseif($action==='executive'){
                if($role!=='admin'||$state['executive']||$state['submission'])aucFail(403,'تصویب نهایی فقط یک‌بار توسط مدیر اصلی مجاز است.');
                foreach($state['reviews'] as $review)if(!$review||$review['decision']!=='approved')aucFail(409,'سه داوری فنی، مالی و حقوقی مثبت لازم است.');
                if(!aucRows($db,'SELECT id FROM auction_scenarios WHERE auction_id=? LIMIT 1',[$id]))aucFail(409,'تحلیل اقتصادی مستند برای تصویب لازم است.');
                if(!aucHasVerifiedDocument($db,$private,$id,['notice','valuation']))aucFail(409,'پیوست آگهی یا ارزش‌گذاری باید موجود و از نظر یکپارچگی معتبر باشد.');
                if((int)$state['reviews']['financial']['actor_id']===$uid)aucFail(409,'داور مالی و تصویب‌کننده نهایی باید دو شخص مستقل باشند.');
                if(strtotime((string)$auction['deadline_utc'].' UTC')<=time())aucFail(409,'مهلت مزایده به پایان رسیده است.');
                aucSql($db,'INSERT INTO auction_events(auction_id,kind,decision,actor_id,evidence) VALUES(?,?,?,?,?)',[$id,'executive','approved',$uid,$evidence]);
            }elseif($action==='submission'){
                if($role!=='admin'||!$state['executive']||$state['submission'])aucFail(409,'فقط ثبت رسید شرکت در مزایده مصوب مجاز است.');
                if(!aucHasVerifiedDocument($db,$private,$id,['receipt']))aucFail(409,'فایل رسید رسمی شرکت در مزایده باید موجود و از نظر یکپارچگی معتبر باشد.');
                aucSql($db,'INSERT INTO auction_events(auction_id,kind,decision,actor_id,evidence) VALUES(?,?,?,?,?)',[$id,'submission','submitted',$uid,$evidence]);
            }elseif($action==='outcome'){
                $decision=aucPost('decision');
                if(!in_array($role,['admin','manager'],true)||!$state['submission']||!in_array($decision,['won','lost'],true))aucFail(409,'نتیجه تنها برای مزایده دارای رسید شرکت قابل ثبت است.');
                aucSql($db,'INSERT INTO auction_events(auction_id,kind,decision,actor_id,evidence) VALUES(?,?,?,?,?)',[$id,'outcome',$decision,$uid,$evidence]);
            }else{
                if(!in_array($role,['admin','manager'],true)||$state['submission'])aucFail(409,'مختومه کردن بدون شرکت، پس از ثبت رسید شرکت مجاز نیست.');
                aucSql($db,'INSERT INTO auction_events(auction_id,kind,decision,actor_id,evidence) VALUES(?,?,?,?,?)',[$id,'cancel','cancelled',$uid,$evidence]);
            }
        }
        if(!$db->exec('COMMIT'))throw new RuntimeException('commit failed');
        $_SESSION['zm_auction_flash']='اقدام داخلی با ثبت تاریخچه انجام شد؛ هیچ پیشنهاد یا پرداختی ارسال نشد.';
        header('Location: /business/auctions/',true,303);exit;
    }catch(Throwable $e){
        $db?->exec('ROLLBACK');
        if($pendingUpload!==null&&is_file($pendingUpload))@unlink($pendingUpload);
        error_log('ZM AUCTION WRITE ['.get_class($e).']');
        aucFail(503,'ثبت پرونده مزایده انجام نشد؛ تغییرات برگردانده شد.');
    }
}
$auctions=$db?aucRows($db,'SELECT * FROM auctions ORDER BY id DESC LIMIT 200'):[];
$eventMap=[];$stats=['total'=>count($auctions),'urgent'=>0,'approved'=>0,'submitted'=>0,'won'=>0];
foreach($auctions as $a){
    $ev=aucRows($db,'SELECT * FROM auction_events WHERE auction_id=? ORDER BY id',[(int)$a['id']]);
    $st=aucState($ev);$eventMap[(int)$a['id']]=['state'=>$st,'events'=>$ev];
    if(!$st['outcome']&&!$st['submission']&&strtotime((string)$a['deadline_utc'].' UTC')<=time()+7*86400)$stats['urgent']++;
    if($st['executive'])$stats['approved']++;
    if($st['submission'])$stats['submitted']++;
    if($st['outcome']&&$st['outcome']['decision']==='won')$stats['won']++;
}
$selectedId=(int)($_GET['id']??0);
$selected=null;
foreach($auctions as $a)if((int)$a['id']===$selectedId)$selected=$a;
$documents=[];$scenarios=[];
if($selected&&$db){
    if($db->querySingle("SELECT 1 FROM sqlite_master WHERE type='table' AND name='auction_documents'"))
        $documents=aucRows($db,'SELECT * FROM auction_documents WHERE auction_id=? ORDER BY id DESC LIMIT 100',[$selectedId]);
    if($db->querySingle("SELECT 1 FROM sqlite_master WHERE type='table' AND name='auction_scenarios'"))
        $scenarios=aucRows($db,'SELECT * FROM auction_scenarios WHERE auction_id=? ORDER BY id DESC LIMIT 30',[$selectedId]);
}
$auth->close();$db?->close();
header('Content-Type: text/html; charset=utf-8');
echo '<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>زمرد ملل · مدیریت مزایده‌ها</title><style>';
echo ':root{font-family:Tahoma,Arial,sans-serif;color:#f4ecd5;background:#172b1c}*{box-sizing:border-box}body{margin:0;line-height:1.65}header{background:#24412b;border-bottom:2px solid #e6c786;padding:20px}main{max-width:1250px;margin:auto;padding:18px}h1,h2,h3{color:#f7d991}a{color:#ffe2a1}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}.card,section{background:#213b29;border:1px solid #75865c;border-radius:15px;padding:18px;margin:18px 0}.metric{font-size:27px;font-weight:bold;color:#ffe3a0}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:900px}th,td{border-bottom:1px solid #657b55;padding:10px;text-align:right}th{color:#ffe2a1}label{display:block;margin:12px 0 5px;font-weight:bold}input,textarea,select{font:inherit;display:block;width:100%;max-width:650px;padding:10px;min-height:48px;background:#0d2116;color:#fff6e3;border:2px solid #a4b38c;border-radius:9px}textarea{min-height:90px}button{font:inherit;min-height:48px;margin-top:14px;padding:10px 19px;background:#f0cd82;color:#192918;border:0;border-radius:10px;font-weight:bold;cursor:pointer}:focus-visible{outline:3px solid #fff3b6;outline-offset:3px}.notice{border-right:4px solid #f6d282;background:#354b32;padding:12px}.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:10px 18px}small,p{color:#dbe5d4}';
echo '</style></head><body><header><h1>مدیریت جامع مزایده‌های زمرد ملل</h1><a href="/business/">بازگشت به میز مدیریت</a></header><main>';
echo '<p class="notice">این بخش فقط پرونده، ارزیابی، مصوبه و رسیدِ ثبت‌شده را مدیریت می‌کند. ثبت پیشنهاد رسمی، انتقال وجه، ضمانت‌نامه و خرید واقعی انجام نمی‌دهد.</p>';
if(isset($_SESSION['zm_auction_flash'])){echo '<p class="notice" role="status">'.aucEsc($_SESSION['zm_auction_flash']).'</p>';unset($_SESSION['zm_auction_flash']);}
echo '<div class="cards">';
foreach(['total'=>'کل مزایده‌ها','urgent'=>'مهلت در ۷ روز','approved'=>'مصوب داخلی','submitted'=>'دارای رسید شرکت','won'=>'برنده ثبت‌شده'] as $key=>$label)echo '<div class="card"><div class="metric">'.$stats[$key].'</div>'.aucEsc($label).'</div>';
echo '</div>';
$deadlineQueue=[];
foreach($auctions as $item){
    $info=$eventMap[(int)$item['id']]['state'];
    if($info['outcome']||$info['submission'])continue;
    $seconds=strtotime((string)$item['deadline_utc'].' UTC')-time();
    if($seconds<=7*86400){
        $label=$seconds<0?'مهلت گذشته؛ بررسی مختومه‌سازی':($seconds<=86400?'اقدام فوری؛ کمتر از ۲۴ ساعت':'اقدام در هفت روز آینده');
        $deadlineQueue[]=['id'=>(int)$item['id'],'title'=>(string)$item['title'],'reference'=>(string)$item['reference'],
            'deadline'=>(string)$item['deadline_utc'],'left'=>$seconds,'label'=>$label];
    }
}
usort($deadlineQueue,fn(array $a,array $b)=>$a['left']<=>$b['left']);
if($deadlineQueue){
    echo '<section aria-labelledby="deadlines"><h2 id="deadlines">کارتابل مهلت‌های مزایده و اقدام لازم</h2>';
    echo '<p>هشدار داخلی در هنگام بازکردن میز مدیریت؛ هیچ پیام یا پیشنهاد بیرونی ارسال نمی‌شود.</p><div class="scroll"><table><tr><th>شماره</th><th>موضوع</th><th>مهلت UTC</th><th>اولویت</th><th>اقدام</th></tr>';
    foreach(array_slice($deadlineQueue,0,20) as $due)
        echo '<tr><td>'.aucEsc($due['reference']).'</td><td>'.aucEsc($due['title']).'</td><td>'.aucEsc($due['deadline']).'</td><td>'.aucEsc($due['label']).'</td><td><a href="?id='.$due['id'].'">بررسی پرونده</a></td></tr>';
    echo '</table></div></section>';
}
if(in_array($role,['admin','manager'],true)){
    echo '<section><h2>ثبت فرصت جدید (خرید یا فروش)</h2><form method="post" action="/business/auctions/"><input type="hidden" name="csrf" value="'.aucEsc($csrf).'"><input type="hidden" name="action" value="create"><div class="row">';
    $fields=[
        ['reference','شناسه داخلی یا شماره آگهی', 'text'],['title','عنوان مزایده','text'],
        ['organizer','برگزارکننده','text'],['asset_type','موضوع/نوع مال','text'],
        ['location','موقعیت یا نشانی موضوع مزایده','text'],
        ['notice_url','پیوند HTTPS آگهی رسمی (اختیاری)','url'],
        ['deadline_utc','مهلت دقیق به وقت UTC','datetime-local'],
        ['estimate','ارزش برآوردی (واحد ارز)','text'],
        ['deposit','تضمین پیشنهادی (فقط ثبت عدد)','text'],
        ['limit','سقف پیشنهاد خرید / کف فروش پیشنهادی','text'],
    ];
    foreach($fields as [$name,$title,$type]){
        $required=in_array($name,['reference','title','organizer','asset_type','deadline_utc'],true)?' required':'';
        $value=in_array($name,['estimate','deposit','limit'],true)?' value="0"':'';
        echo '<div><label for="a-'.aucEsc($name).'">'.aucEsc($title).'</label><input id="a-'.aucEsc($name).'" type="'.$type.'" name="'.aucEsc($name).'"'.$required.$value.'></div>';
    }
    echo '<div><label for="a-direction">نقش شرکت</label><select id="a-direction" name="direction"><option value="buy">خریدار / شرکت‌کننده</option><option value="sell">فروشنده / برگزارکننده</option></select></div>';
    echo '<div><label for="a-currency">ارز</label><select id="a-currency" name="currency"><option value="IRR">IRR ریال</option><option value="USD">USD</option><option value="EUR">EUR</option><option value="AED">AED</option></select></div>';
    echo '<div><label for="a-project">پروژه مرتبط (اختیاری)</label><select id="a-project" name="project_id"><option value="0">بدون پروژه</option>';
    foreach($projects as $p)echo '<option value="'.(int)$p['id'].'">'.aucEsc($p['title']).'</option>';
    echo '</select></div></div><label for="a-notes">شرح شرایط و ریسک‌ها</label><textarea id="a-notes" name="notes" maxlength="1800"></textarea><button type="submit">ثبت پرونده بدون تعهد مالی</button></form></section>';
}
echo '<section><h2>دفتر مزایده‌ها</h2><div class="scroll"><table><thead><tr><th>شناسه</th><th>عنوان</th><th>نقش</th><th>برگزارکننده</th><th>مهلت UTC</th><th>ارزش</th><th>تضمین</th><th>وضعیت</th><th>پرونده</th></tr></thead><tbody>';
foreach($auctions as $a){
    $id=(int)$a['id'];$st=$eventMap[$id]['state'];
    echo '<tr><td>'.aucEsc($a['reference']).'</td><td>'.aucEsc($a['title']).'</td><td>'.($a['direction']==='buy'?'خریدار':'فروشنده').'</td><td>'.aucEsc($a['organizer']).'</td><td>'.aucEsc($a['deadline_utc']).'</td><td>'.aucFmt((int)$a['estimate_minor']).' '.aucEsc($a['currency']).'</td><td>'.aucFmt((int)$a['deposit_minor']).'</td><td>'.aucEsc($st['label']).'</td><td><a href="?id='.$id.'">جزئیات و داوری</a></td></tr>';
}
if(!$auctions)echo '<tr><td colspan="9">هیچ مزایده‌ای ثبت نشده است.</td></tr>';
echo '</tbody></table></div></section>';
if($selected){
    $id=(int)$selected['id'];$record=$eventMap[$id];$st=$record['state'];
    echo '<section><h2>پرونده '.aucEsc($selected['reference']).' — '.aucEsc($selected['title']).'</h2><p>'.aucEsc($selected['notes']).'</p><p>برگزارکننده: '.aucEsc($selected['organizer']).' | محل: '.aucEsc($selected['location']).' | سقف/کف داخلی: '.aucFmt((int)$selected['limit_minor']).' '.aucEsc($selected['currency']).' | پروژه: #'.(int)$selected['project_id'].'</p>';
    if($selected['notice_url']!=='')echo '<p><a href="'.aucEsc($selected['notice_url']).'" rel="noopener noreferrer">آگهی مرجع</a></p>';
    echo '<h3>تاریخچه ثبت تصمیم‌ها</h3><div class="scroll"><table><tr><th>مرحله</th><th>تصمیم</th><th>شناسه کاربر</th><th>مرجع/مدرک</th><th>زمان UTC</th></tr>';
    foreach($record['events'] as $e)echo '<tr><td>'.aucEsc($e['kind']).'</td><td>'.aucEsc($e['decision']).'</td><td>'.(int)$e['actor_id'].'</td><td>'.aucEsc($e['evidence']).'</td><td>'.aucEsc($e['created_at']).'</td></tr>';
    echo '</table></div>';
    echo '<h3>اسناد و قراردادهای پرونده</h3><div class="scroll"><table><tr><th>نوع</th><th>نام فایل</th><th>حجم</th><th>اثر انگشت SHA-256</th><th>ثبت‌کننده</th><th>دریافت امن</th></tr>';
    foreach($documents as $doc){
        if(!aucDocumentAccess($role,(string)$doc['category']))continue;
        echo '<tr><td>'.aucEsc($doc['category']).'</td><td>'.aucEsc($doc['original_name']).'</td><td>'.number_format((int)$doc['size_bytes']).' بایت</td><td><code>'.aucEsc(substr((string)$doc['sha256'],0,16)).'…</code></td><td>'.(int)$doc['actor_id'].'</td><td><a href="?document='.(int)$doc['id'].'">دریافت سند</a></td></tr>';
    }
    if(!$documents)echo '<tr><td colspan="6">هنوز مدرکی ثبت نشده است.</td></tr>';
    echo '</table></div>';
    if($role!=='viewer'){
        echo '<form method="post" action="/business/auctions/" enctype="multipart/form-data"><fieldset><legend>افزودن مدرک محرمانه (ثبت داخلی)</legend><input type="hidden" name="csrf" value="'.aucEsc($csrf).'"><input type="hidden" name="action" value="document"><input type="hidden" name="auction_id" value="'.$id.'">';
        echo '<label for="a-doc-category">نوع مدرک</label><select id="a-doc-category" name="category">';
        foreach(['notice'=>'آگهی','valuation'=>'کارشناسی ارزش','deposit'=>'مدارک تضمین','technical'=>'فنی و حقوقی','contract'=>'قرارداد','receipt'=>'رسید شرکت','other'=>'سایر'] as $category=>$label)
            if(aucDocumentAccess($role,$category))echo '<option value="'.aucEsc($category).'">'.aucEsc($label).'</option>';
        echo '</select>';
        echo '<label for="a-doc-upload">فایل PDF، JPEG یا PNG تا ۸ مگابایت</label><input id="a-doc-upload" type="file" name="document" accept="application/pdf,image/jpeg,image/png" required aria-describedby="doc-privacy">';
        echo '<p id="doc-privacy">مدرک فقط در فضای خصوصی سرور ذخیره می‌شود. ثبت فایل هیچ پرداخت یا قرارداد جدیدی ایجاد نمی‌کند.</p><button type="submit">ثبت مدرک و اثر انگشت</button></fieldset></form>';
    }
    echo '<h3>سناریوهای تحلیل اقتصادی (صرفاً پیش‌بینی، نه ثبت حسابداری)</h3><div class="scroll"><table><tr><th>ورودی پیش‌بینی</th><th>بهای پایه</th><th>هزینه جانبی</th><th>ذخیره ریسک</th><th>مازاد / کسری</th><th>بازده مبنا</th><th>فرضیات</th><th>تحلیلگر</th></tr>';
    foreach($scenarios as $sc){
        $net=(int)$sc['proceeds_minor']-(int)$sc['basis_minor']-(int)$sc['costs_minor']-(int)$sc['reserve_minor'];
        $base=(int)$sc['basis_minor']+(int)$sc['costs_minor']+(int)$sc['reserve_minor'];
        $percent=$base>0?number_format(100*$net/$base,1).'%':'—';
        echo '<tr><td>'.aucFmt((int)$sc['proceeds_minor']).'</td><td>'.aucFmt((int)$sc['basis_minor']).'</td><td>'.aucFmt((int)$sc['costs_minor']).'</td><td>'.aucFmt((int)$sc['reserve_minor']).'</td><td>'.aucFmt($net).' '.aucEsc($selected['currency']).'</td><td>'.aucEsc($percent).'</td><td>'.aucEsc($sc['rationale']).'</td><td>'.(int)$sc['actor_id'].'</td></tr>';
    }
    if(!$scenarios)echo '<tr><td colspan="8">هنوز تحلیل مستندی ثبت نشده است.</td></tr>';
    echo '</table></div>';
    if($role!=='viewer'&&!$st['outcome']){
        echo '<form method="post" action="/business/auctions/"><fieldset><legend>ثبت سناریوی جدید و فرضیات اقتصادی</legend><input type="hidden" name="csrf" value="'.aucEsc($csrf).'"><input type="hidden" name="action" value="scenario"><input type="hidden" name="auction_id" value="'.$id.'"><div class="row">';
        foreach([['proceeds','جریان ورودی / ارزش فروش مورد انتظار'],['basis','بهای پایه / خرید یا ارزش دفتری'],['costs','هزینه‌های انتقال، آماده‌سازی و جانبی'],['reserve','ذخیره ریسک و عدم قطعیت']] as [$field,$label]){
            echo '<div><label for="s-'.aucEsc($field).'">'.aucEsc($label).' ('.aucEsc($selected['currency']).')</label><input id="s-'.aucEsc($field).'" name="'.aucEsc($field).'" type="text" inputmode="decimal" pattern="[0-9]+(\\.[0-9]{1,2})?" value="0" required></div>';
        }
        echo '</div><label for="s-rationale">فرضیات و مستندات تحلیل</label><textarea id="s-rationale" name="rationale" minlength="10" maxlength="1400" required></textarea><button type="submit">ثبت تحلیل اقتصادی بدون اثر مالی</button></fieldset></form>';
    }
    if($role!=='viewer'&&!$st['outcome']){
        echo '<h3>ثبت تصمیم داخلی با مستندات</h3><form method="post" action="/business/auctions/"><input type="hidden" name="csrf" value="'.aucEsc($csrf).'"><input type="hidden" name="auction_id" value="'.$id.'">';
        echo '<label for="a-action">نوع اقدام</label><select id="a-action" name="action"><option value="review">داوری داخلی</option><option value="executive">تصویب مدیرعامل</option><option value="submission">ثبت دستی رسید شرکت در مزایده</option><option value="outcome">ثبت نتیجه</option><option value="cancel">مختومه بدون شرکت</option></select>';
        echo '<label for="a-kind">حوزه داوری</label><select id="a-kind" name="kind"><option value="technical">فنی</option><option value="financial">مالی</option><option value="legal">حقوقی داخلی</option></select>';
        echo '<label for="a-decision">نتیجه داوری / نتیجه مزایده</label><select id="a-decision" name="decision"><option value="approved">تأیید</option><option value="rejected">رد</option><option value="won">برنده</option><option value="lost">ناموفق</option></select>';
        echo '<label for="a-evidence">شرح مستند و شماره رسید/مرجع (الزامی)</label><textarea id="a-evidence" name="evidence" required minlength="10" maxlength="1400"></textarea>';
        echo '<button type="submit">ثبت داخلی با کنترل نقش</button></form>';
    }
    echo '</section>';
}
echo '</main></body></html>';
