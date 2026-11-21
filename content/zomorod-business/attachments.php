<?php
declare(strict_types=1);
/**
 * Zomorod Melal / private document vault.
 * Standalone additive route: /business/attachments/
 * Never edits the existing business app or accounting database.
 */
ini_set('display_errors', '0');
ini_set('log_errors', '1');
header('Cache-Control: no-store, max-age=0');
header('X-Robots-Tag: noindex, nofollow');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: no-referrer');
header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");

function vaultEsc(mixed $value): string {
    return htmlspecialchars((string)$value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}
function vaultFail(int $status, string $message): never {
    http_response_code($status);
    header('Content-Type: text/html; charset=utf-8');
    echo '<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>بایگانی زمرد ملل</title><body style="font:16px Tahoma,Arial;background:#172b1c;color:#f6e9c9;padding:24px"><h1>بایگانی اسناد زمرد ملل</h1><p>'.vaultEsc($message).'</p><a style="color:#ffe19d" href="/business/">بازگشت به مدیریت</a></body></html>';
    exit;
}
if(!extension_loaded('session') || !class_exists('SQLite3'))vaultFail(503, 'خدمات احراز هویت در دسترس نیست.');
if(session_status() !== PHP_SESSION_ACTIVE){
    session_name('ZM_BUSINESS');
    session_set_cookie_params(['lifetime'=>0, 'path'=>'/business/', 'secure'=>true, 'httponly'=>true, 'samesite'=>'Strict']);
    session_start();
}
$uid=(int)($_SESSION['uid'] ?? 0);
if($uid <= 0) vaultFail(403, 'ابتدا به میز مدیریت وارد شوید.');
$home=dirname(__DIR__, 3);
$private=$home.'/.private/zomorod-business';
$dbFile=$private.'/management.sqlite3';
if(!is_dir($private) || is_link($private) || !is_file($dbFile) || is_link($dbFile)){
    vaultFail(503, 'پایگاه اطلاعات خصوصی در دسترس نیست.');
}
try {
    $auth=new SQLite3($dbFile, SQLITE3_OPEN_READONLY);
    $auth->busyTimeout(3000);
    $statement=$auth->prepare('SELECT role,active FROM users WHERE id=:id LIMIT 1');
    if($statement === false) throw new RuntimeException('auth prepare failed');
    $statement->bindValue(':id', $uid, SQLITE3_INTEGER);
    $result=$statement->execute();
    $account=$result === false ? false : $result->fetchArray(SQLITE3_ASSOC);
    if(!$account || (int)$account['active'] !== 1 ||
       !in_array((string)$account['role'], ['admin','manager','accountant'], true)){
        vaultFail(403, 'مجوز دسترسی به بایگانی وجود ندارد.');
    }
} catch(Throwable $e) {
    error_log('ZM DOCUMENT VAULT AUTH ['.get_class($e).']');
    vaultFail(503, 'احراز هویت بایگانی امکان‌پذیر نیست.');
}
$vault=$private.'/document_vault_v1';
if(is_link($vault) || (file_exists($vault) && !is_dir($vault)))vaultFail(503, 'مسیر بایگانی خصوصی معتبر نیست.');
$types=[
    'pdf'=>['application/pdf'],
    'docx'=>['application/zip','application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    'xlsx'=>['application/zip','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
    'png'=>['image/png'],
    'jpg'=>['image/jpeg'],
    'jpeg'=>['image/jpeg'],
    'txt'=>['text/plain'],
];
$categories=['اداری','املاک','قرارداد','مالی','پروژه','پژوهش','سایر'];
if(empty($_SESSION['zm_vault_csrf']))$_SESSION['zm_vault_csrf']=bin2hex(random_bytes(32));
$csrf=(string)$_SESSION['zm_vault_csrf'];
$method=(string)($_SERVER['REQUEST_METHOD'] ?? 'GET');
if($method !== 'GET' && $method !== 'POST')vaultFail(405, 'روش درخواست مجاز نیست.');
if($method === 'GET' && isset($_GET['download'])){
    $id=(string)$_GET['download'];
    if(!preg_match('/\A[a-f0-9]{32}\z/D', $id) || !is_dir($vault))vaultFail(404, 'پیوست پیدا نشد.');
    $metaFile=$vault.'/'.$id.'.json';
    if(!is_file($metaFile) || is_link($metaFile) || filesize($metaFile)>4096)vaultFail(404, 'پیوست پیدا نشد.');
    $meta=json_decode((string)file_get_contents($metaFile), true);
    $ext=is_array($meta)?(string)($meta['extension']??''):'';
    if(!isset($types[$ext]))vaultFail(404, 'پیوست معتبر نیست.');
    $path=$vault.'/'.$id.'.'.$ext;
    if(!is_file($path) || is_link($path))vaultFail(404, 'فایل پیوست پیدا نشد.');
    $size=filesize($path);
    if($size === false || $size <= 0 || $size > 10485760)vaultFail(503, 'اندازه پیوست معتبر نیست.');
    if(!hash_equals((string)($meta['sha256']??''), (string)hash_file('sha256',$path)))vaultFail(503, 'یکپارچگی فایل قابل تأیید نیست.');
    header('Content-Type: application/octet-stream');
    header('Content-Disposition: attachment; filename="zm-document-'.$id.'.'.$ext.'"');
    header('Content-Length: '.$size);
    readfile($path);
    exit;
}
if($method === 'POST'){
    $length=(int)($_SERVER['CONTENT_LENGTH'] ?? 0);
    if($length > 12000000)vaultFail(413, 'حجم درخواست بیش از اندازه مجاز است.');
    if(!hash_equals($csrf, (string)($_POST['csrf']??'')))vaultFail(403, 'اعتبار فرم پایان یافته است.');
    $title=trim((string)($_POST['title']??''));
    $category=(string)($_POST['category']??'');
    if($title === '' || strlen($title)>300 || !in_array($category,$categories,true))vaultFail(422,'عنوان یا دسته‌بندی نامعتبر است.');
    $documentId=(int)($_POST['document_id']??0);
    $projectId=(int)($_POST['project_id']??0);
    if($documentId<0 || $projectId<0)vaultFail(422,'ارجاع پرونده نامعتبر است.');
    foreach([['documents',$documentId],['projects',$projectId]] as [$table,$id]){
        if($id===0)continue;
        $ref=$auth->prepare('SELECT id FROM '.$table.' WHERE id=:id LIMIT 1');
        if($ref===false) vaultFail(503, 'اعتبارسنجی ارجاع امکان‌پذیر نیست.');
        $ref->bindValue(':id', $id, SQLITE3_INTEGER);
        $found=$ref->execute();
        if($found === false || !$found->fetchArray(SQLITE3_NUM))vaultFail(422, 'نامه یا پروژه ارجاع‌داده‌شده یافت نشد.');
    }
    $up=$_FILES['attachment']??null;
    if(!is_array($up) || (int)($up['error']??-1)!==UPLOAD_ERR_OK ||
       !is_uploaded_file((string)($up['tmp_name']??'')))vaultFail(422,'بارگذاری کامل نشد.');
    $size=(int)($up['size']??0);
    if($size<=0 || $size>10485760)vaultFail(413, 'حداکثر حجم هر پیوست ۱۰ مگابایت است.');
    $filename=basename(str_replace('\\','/',(string)($up['name']??'')));
    if($filename==='' || strlen($filename)>180)vaultFail(422, 'نام فایل معتبر نیست.');
    $ext=strtolower(pathinfo($filename,PATHINFO_EXTENSION));
    if(!isset($types[$ext]))vaultFail(422, 'فقط PDF، DOCX، XLSX، تصویر و TXT مجازند.');
    $tmp=(string)$up['tmp_name'];
    $mime=(new finfo(FILEINFO_MIME_TYPE))->file($tmp);
    if(!in_array($mime,$types[$ext],true))vaultFail(422, 'نوع واقعی فایل با پسوند مطابقت ندارد.');
    $head=file_get_contents($tmp,false,null,0,8);
    if(($ext==='pdf' && !str_starts_with((string)$head,'%PDF-')) ||
       (in_array($ext,['docx','xlsx'],true) && !str_starts_with((string)$head,"PK\x03\x04")) ||
       ($ext==='png' && !str_starts_with((string)$head,"\x89PNG\r\n\x1a\n")) ||
       (in_array($ext,['jpg','jpeg'],true) && !str_starts_with((string)$head,"\xff\xd8")) ||
       ($ext==='txt' && str_contains((string)file_get_contents($tmp,false,null,0,1024),"\0"))){
        vaultFail(422, 'امضای فایل نامعتبر است.');
    }
    if(in_array($ext,['docx','xlsx'],true)){
        if(!class_exists('ZipArchive'))vaultFail(503,'بررسی ساختار Office روی سرور موجود نیست.');
        $zip=new ZipArchive();
        if($zip->open($tmp,ZipArchive::RDONLY)!==true)vaultFail(422,'ساختار فایل Office نامعتبر است.');
        $expected=$ext==='docx'?'word/document.xml':'xl/workbook.xml';
        $hasTypes=$zip->locateName('[Content_Types].xml')!==false;
        $hasMain=$zip->locateName($expected)!==false;
        $expanded=0;
        if($zip->numFiles>500){$zip->close();vaultFail(422,'فایل Office بیش از حد پیچیده است.');}
        for($i=0;$i<$zip->numFiles;$i++){
            $entry=$zip->statIndex($i);
            if(!is_array($entry) || !isset($entry['size'],$entry['name'])){$zip->close();vaultFail(422,'ساختار فایل Office معتبر نیست.');}
            $expanded+=(int)$entry['size'];
            $name=strtolower((string)$entry['name']);
            if($expanded>40000000 || str_contains($name,'vbaproject.bin') ||
               str_contains($name,'../') || str_starts_with($name,'/')){
                $zip->close();vaultFail(422,'فایل Office دارای محتوای ممنوع است.');
            }
        }
        $zip->close();
        if(!$hasTypes || !$hasMain)vaultFail(422,'فایل Office با قالب مورد انتظار مطابقت ندارد.');
    }
    if(!is_dir($vault) && !mkdir($vault,0700) && !is_dir($vault))vaultFail(503,'فضای خصوصی قابل ایجاد نیست.');
    if(is_link($vault) || !is_dir($vault) || !is_writable($vault))vaultFail(503,'فضای خصوصی امن نیست.');
    $id=bin2hex(random_bytes(16));
    $target=$vault.'/'.$id.'.'.$ext;
    $metaFile=$vault.'/'.$id.'.json';
    if(file_exists($target) || file_exists($metaFile))vaultFail(503,'شناسه تکراری بایگانی.');
    if(!move_uploaded_file($tmp,$target))vaultFail(503,'ذخیره پیوست امکان‌پذیر نیست.');
    try {
        if(!chmod($target,0600))throw new RuntimeException('private file chmod failed');
        $digest=hash_file('sha256',$target);
        if(!is_string($digest))throw new RuntimeException('digest failed');
        $meta=[
            'version'=>1, 'id'=>$id, 'title'=>$title, 'category'=>$category,
            'filename'=>$filename, 'extension'=>$ext, 'mime'=>$mime,
            'size'=>$size, 'sha256'=>$digest,
            'document_id'=>$documentId, 'project_id'=>$projectId,
            'uploaded_by'=>$uid, 'created_at'=>gmdate('c'),
        ];
        $json=json_encode($meta,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR);
        $handle=@fopen($metaFile,'x');
        if($handle===false)throw new RuntimeException('metadata create failed');
        $written=fwrite($handle,$json);
        $flushed=fflush($handle);
        fclose($handle);
        if(!chmod($metaFile,0600) || !$flushed || $written!==strlen($json)){
            throw new RuntimeException('metadata write failed');
        }
    } catch(Throwable $e) {
        if(is_file($metaFile) && !is_link($metaFile))unlink($metaFile);
        if(is_file($target) && !is_link($target))unlink($target);
        error_log('ZM DOCUMENT VAULT STORE ['.get_class($e).']');
        vaultFail(503,'ثبت امن پیوست کامل نشد.');
    }
    $_SESSION['zm_vault_success']='فایل در بایگانی خصوصی ذخیره شد.';
    header('Location: /business/attachments/',true,303);
    exit;
}
$recent=[];
if(is_dir($vault)){
    $files=glob($vault.'/*.json') ?: [];
    foreach($files as $file){
        if(is_link($file) || !is_file($file) || filesize($file)>4096)continue;
        $m=json_decode((string)file_get_contents($file),true);
        if(!is_array($m) || ($m['version']??null)!==1 ||
           !preg_match('/\A[a-f0-9]{32}\z/D',(string)($m['id']??'')) ||
           !isset($types[(string)($m['extension']??'')]))continue;
        $recent[]=$m;
    }
    usort($recent,fn($a,$b)=>strcmp((string)($b['created_at']??''),(string)($a['created_at']??'')));
    $recent=array_slice($recent,0,200);
}
$documents=[];
$projects=[];
foreach(['documents','projects'] as $table){
    $query=$auth->query('SELECT id,title FROM '.$table.' ORDER BY id DESC LIMIT 100');
    if($query!==false)while($r=$query->fetchArray(SQLITE3_ASSOC)){
        if($table==='documents')$documents[]=$r; else $projects[]=$r;
    }
}
$auth->close();
header('Content-Type: text/html; charset=utf-8');
echo '<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>بایگانی اسناد زمرد ملل</title><style>';
echo ':root{font-family:Tahoma,Arial,sans-serif;color:#f5ecd5;background:#172b1c}*{box-sizing:border-box}body{margin:0;line-height:1.65}header{padding:22px;background:#21412a;border-bottom:2px solid #d0b16c}main{max-width:1100px;margin:auto;padding:20px}h1,h2{color:#f5d88f}a{color:#ffe09a}section{background:#213a29;border:1px solid #74835a;border-radius:16px;padding:20px;margin:20px 0}label{display:block;font-weight:bold;margin-top:15px}input,select{display:block;width:100%;max-width:680px;min-height:48px;padding:10px;font:inherit;color:#fff5df;background:#0b2115;border:2px solid #a1ad83;border-radius:9px}button{font:inherit;min-height:48px;margin-top:20px;background:#e7c57d;color:#172b1c;border:0;border-radius:10px;padding:10px 22px;font-weight:bold;cursor:pointer}:focus-visible{outline:3px solid #fff4bf;outline-offset:3px}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:680px}th,td{text-align:right;padding:12px;border-bottom:1px solid #718165}th{color:#ffdf98}p,.muted{color:#e1e5d5}.notice{border-right:4px solid #f2d187;padding:12px;background:#354a30}small{color:#e1e5d5}';
echo '</style></head><body><header><h1>بایگانی امن اسناد و پیوست‌ها</h1><a href="/business/">بازگشت به میز مدیریت</a></header><main><p>اسناد فقط در فضای خصوصی هاست ذخیره می‌شوند؛ این قسمت ارسال پیام یا پرداخت انجام نمی‌دهد.</p>';
if(isset($_SESSION['zm_vault_success'])){echo '<p class="notice" role="status">'.vaultEsc($_SESSION['zm_vault_success']).'</p>';unset($_SESSION['zm_vault_success']);}
echo '<section><h2>بارگذاری پرونده</h2><form method="post" action="/business/attachments/" enctype="multipart/form-data">';
echo '<input type="hidden" name="csrf" value="'.vaultEsc($csrf).'"><label for="vault-title">عنوان پرونده *</label><input id="vault-title" name="title" required maxlength="100" autocomplete="off">';
echo '<label for="vault-category">دسته‌بندی *</label><select id="vault-category" name="category">';
foreach($categories as $cat)echo '<option value="'.vaultEsc($cat).'">'.vaultEsc($cat).'</option>';
echo '</select><label for="vault-document">اتصال به نامه موجود (اختیاری)</label><select id="vault-document" name="document_id"><option value="0">بدون اتصال</option>';
foreach($documents as $d)echo '<option value="'.(int)$d['id'].'">'.vaultEsc($d['title']).'</option>';
echo '</select><label for="vault-project">اتصال به پروژه موجود (اختیاری)</label><select id="vault-project" name="project_id"><option value="0">بدون اتصال</option>';
foreach($projects as $p)echo '<option value="'.(int)$p['id'].'">'.vaultEsc($p['title']).'</option>';
echo '</select><label for="vault-file">فایل پیوست *</label><input id="vault-file" type="file" name="attachment" required accept=".pdf,.docx,.xlsx,.png,.jpg,.jpeg,.txt" aria-describedby="vault-help">';
echo '<p id="vault-help">حداکثر ۱۰ مگابایت؛ فایل‌های اجرایی و Office دارای ماکرو پذیرفته نمی‌شوند. فایل‌ها به‌صورت پیوست دانلود می‌شوند و در سایت عمومی نمایش داده نخواهند شد.</p><button type="submit">ثبت امن پیوست</button></form></section>';
echo '<section><h2>آخرین فایل‌های خصوصی</h2><div class="scroll"><table><thead><tr><th>عنوان</th><th>دسته</th><th>نام فایل</th><th>مرجع</th><th>زمان UTC</th><th>دریافت</th></tr></thead><tbody>';
foreach($recent as $m){
    $id=(string)$m['id'];
    echo '<tr><td>'.vaultEsc($m['title']??'').'</td><td>'.vaultEsc($m['category']??'').'</td><td>'.vaultEsc($m['filename']??'').'</td><td>نامه #'.(int)($m['document_id']??0).' / پروژه #'.(int)($m['project_id']??0).'</td><td>'.vaultEsc($m['created_at']??'').'</td><td><a href="?download='.$id.'">دانلود</a></td></tr>';
}
if(!$recent)echo '<tr><td colspan="6">هنوز فایلی ثبت نشده است.</td></tr>';
echo '</tbody></table></div></section></main></body></html>';
