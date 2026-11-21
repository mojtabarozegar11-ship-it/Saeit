<?php
declare(strict_types=1);
/**
 * Independent site-local customer ingress for each site's private master agent.
 * No external API, LLM key, remote request or payment mutation.
 * Only the matching hard-pinned webroot may select a tenant.
 */
function masterSiteConfig(string $host,string $directory):array {
    $host=strtolower(preg_replace('/:\d+$/','',trim($host)));
    $config=[
      'zomorodmelal.ir'=>['tenant'=>'zomorod','locale'=>'fa','public'=>'/home/zomorod2/public_html/ask-master','private'=>'/home/zomorod2/.private/zomorod-business'],
      'www.zomorodmelal.ir'=>['tenant'=>'zomorod','locale'=>'fa','public'=>'/home/zomorod2/public_html/ask-master','private'=>'/home/zomorod2/.private/zomorod-business'],
      'mojplaywin.com'=>['tenant'=>'mojplaywin','locale'=>'en','public'=>'/home/zomorod2/mojplaywin.com/ask-master','private'=>'/home/zomorod2/.private_mojplaywin_main_agents'],
      'www.mojplaywin.com'=>['tenant'=>'mojplaywin','locale'=>'en','public'=>'/home/zomorod2/mojplaywin.com/ask-master','private'=>'/home/zomorod2/.private_mojplaywin_main_agents'],
    ];
    $target=$config[$host]??null;
    if(!$target || realpath($directory)!==$target['public'])throw new RuntimeException('Wrong site or tenant');
    return $target;
}
function masterOpenDb(string $root):PDO {
    if(!is_dir($root)||is_link($root)||(fileperms($root)&0007)!==0)throw new RuntimeException('Private storage unavailable');
    $file=$root.'/master_customer_inbox.sqlite3';
    if(is_link($file))throw new RuntimeException('Unsafe private database');
    $db=new PDO('sqlite:'.$file,null,null,[
      PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,
      PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,
      PDO::ATTR_TIMEOUT=>8
    ]);
    $db->exec('PRAGMA busy_timeout=8000;PRAGMA journal_mode=WAL;PRAGMA foreign_keys=ON');
    $db->exec('CREATE TABLE IF NOT EXISTS customer_questions(
      id TEXT PRIMARY KEY, tenant TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN (\'question\',\'order_question\')),
      full_name TEXT NOT NULL, email TEXT NOT NULL, question TEXT NOT NULL,
      claimed_order_ref TEXT NOT NULL DEFAULT "", initial_reply TEXT NOT NULL,
      processing_status TEXT NOT NULL DEFAULT "queued" CHECK(processing_status IN ("queued","handled","needs_review")),
      created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, master_processed_utc TEXT DEFAULT NULL
    )');
    $db->exec('CREATE INDEX IF NOT EXISTS idx_master_questions_queue ON customer_questions(processing_status,created_utc)');
    $db->exec('CREATE TABLE IF NOT EXISTS customer_order_events(
      id INTEGER PRIMARY KEY AUTOINCREMENT,tenant TEXT NOT NULL,source TEXT NOT NULL,
      source_id TEXT NOT NULL, source_status TEXT NOT NULL, event_digest TEXT NOT NULL,
      seen_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(tenant,source,source_id,event_digest)
    )');
    $db->exec('CREATE TABLE IF NOT EXISTS customer_rate_limit(
      visitor_digest TEXT NOT NULL,minute_window INTEGER NOT NULL,requests INTEGER NOT NULL,
      PRIMARY KEY(visitor_digest,minute_window)
    )');
    @chmod($file,0600);
    return $db;
}
function masterEscape(string $text):string {return htmlspecialchars($text,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
function masterTextLength(string $value):int {
    return function_exists('mb_strlen')?mb_strlen($value,'UTF-8'):strlen($value);
}
function masterLocalReply(string $site,string $kind,string $message):string {
    $fa=$site==='zomorod';
    $lower=function_exists('mb_strtolower')?mb_strtolower($message,'UTF-8'):strtolower($message);
    if($kind==='order_question'){
        return $fa
          ? 'درخواست پیگیری سفارش ثبت شد. وضعیت پرداخت فقط از سامانه معتبر فروشگاه بررسی می‌شود. هرگز رمز، عبارت بازیابی یا کلید خصوصی ارسال نکنید.'
          : 'Your order question is recorded. Payment status is checked only against the store ledger. Never share passwords, seed phrases, or private keys.';
    }
    if(preg_match('/(refund|return|استرداد|مرجوع|بازگشت وجه)/iu',$lower)){
        return $fa?'درخواست شما برای بررسی شرایط بازگشت وجه ثبت شد. تأیید استرداد فقط پس از بررسی مسئول مربوط انجام می‌شود.'
          :'Your refund question has been recorded for review. No refund is approved or executed by this reply.';
    }
    if(preg_match('/(discount|coupon|تخفیف|کد تخفیف)/iu',$lower)){
        return $fa?'قیمت معتبر در صفحه محصول درج شده است. اعمال هر تخفیف فقط با تأیید مدیریت انجام می‌شود.'
          :'The current product page displays the applicable price. Discounts require management approval.';
    }
    if(preg_match('/(download|file|delivery|دریافت|دانلود|فایل|تحویل)/iu',$lower)){
        return $fa?'پس از تأیید معتبر سفارش، روش تحویل فایل در مسیر خرید نمایش داده می‌شود. مشکل تحویل شما در صف بررسی قرار گرفت.'
          :'Delivery information is available after verified purchase. Your download or delivery issue is queued for review.';
    }
    return $fa?'پرسش شما دریافت و برای بررسی مسترایجنت سایت ثبت شد. پاسخ اختصاصیِ تأییدنشده ارائه نمی‌شود.'
       :'Your question was received for this site master agent to review. Unverified personalized answers are not generated.';
}
function masterSaveQuestion(PDO $db,string $tenant,string $kind,string $name,string $email,string $message,string $order):array {
    if(!in_array($tenant,['zomorod','mojplaywin'],true)||
       !in_array($kind,['question','order_question'],true))throw new InvalidArgumentException('Invalid request kind');
    if(masterTextLength($name)<2||masterTextLength($name)>120||
       !filter_var($email,FILTER_VALIDATE_EMAIL)||strlen($email)>250||
       masterTextLength($message)<5||masterTextLength($message)>2500||
       strlen($order)>90||preg_match('/[\x00-\x1f]/',$order))throw new InvalidArgumentException('Invalid request fields');
    if($kind==='order_question'&&$order==='')throw new InvalidArgumentException('Order reference required');
    $id=bin2hex(random_bytes(12));
    $reply=masterLocalReply($tenant,$kind,$message);
    $db->prepare('INSERT INTO customer_questions(id,tenant,kind,full_name,email,question,claimed_order_ref,initial_reply)
      VALUES(?,?,?,?,?,?,?,?)')->execute([$id,$tenant,$kind,$name,$email,$message,$order,$reply]);
    return ['id'=>$id,'reply'=>$reply,'status'=>'queued'];
}
function masterCheckLimit(PDO $db,string $visitor):bool {
    $minute=intdiv(time(),600);
    $hash=hash('sha256',$visitor);
    $db->beginTransaction();
    try{
        $db->prepare('INSERT INTO customer_rate_limit(visitor_digest,minute_window,requests) VALUES(?,?,1)
          ON CONFLICT(visitor_digest,minute_window) DO UPDATE SET requests=requests+1')->execute([$hash,$minute]);
        $stmt=$db->prepare('SELECT requests FROM customer_rate_limit WHERE visitor_digest=? AND minute_window=?');
        $stmt->execute([$hash,$minute]);$count=(int)$stmt->fetchColumn();
        $db->commit();
        return $count<=5;
    }catch(Throwable $e){$db->rollBack();throw $e;}
}
function masterWeb():void {
    if(PHP_SAPI==='cli'){http_response_code(404);return;}
    header('Content-Type: text/html; charset=utf-8');
    header('Cache-Control: no-store, private');
    header('X-Content-Type-Options: nosniff');
    header('X-Frame-Options: DENY');
    header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");
    try{$cfg=masterSiteConfig((string)($_SERVER['HTTP_HOST']??''),__DIR__);}
    catch(Throwable $e){http_response_code(404);echo 'Not found';return;}
    $fa=$cfg['locale']==='fa';
    if(!in_array($_SERVER['REQUEST_METHOD']??'GET',['GET','POST'],true)){
        http_response_code(405);header('Allow: GET, POST');return;
    }
    session_name($fa?'ZM_MASTER_SUPPORT':'MPW_MASTER_SUPPORT');
    session_set_cookie_params(['lifetime'=>0,'path'=>'/ask-master/','secure'=>true,'httponly'=>true,'samesite'=>'Strict']);
    if(!session_start()){http_response_code(503);return;}
    if(!isset($_SESSION['master_csrf']))$_SESSION['master_csrf']=bin2hex(random_bytes(24));
    $error='';$result=null;
    if($_SERVER['REQUEST_METHOD']==='POST'){
        try{
            if((int)($_SERVER['CONTENT_LENGTH']??0)>9000)throw new InvalidArgumentException('Form too large');
            if(!hash_equals((string)$_SESSION['master_csrf'],(string)($_POST['csrf']??'')))
                throw new InvalidArgumentException('Form token expired');
            if(trim((string)($_POST['website']??''))!=='')throw new InvalidArgumentException('Robot request rejected');
            $origin=(string)($_SERVER['HTTP_ORIGIN']??'');
            if($origin!==''&&!in_array(strtolower((string)parse_url($origin,PHP_URL_HOST)),
                 [$fa?'zomorodmelal.ir':'mojplaywin.com',$fa?'www.zomorodmelal.ir':'www.mojplaywin.com'],true))
                throw new InvalidArgumentException('Cross-site submission rejected');
            $db=masterOpenDb($cfg['private']);
            if(!masterCheckLimit($db,(string)($_SERVER['REMOTE_ADDR']??'unknown')))
                throw new InvalidArgumentException('Too many requests; try later');
            $result=masterSaveQuestion($db,$cfg['tenant'],
                 (string)($_POST['kind']??''),trim((string)($_POST['name']??'')),
                 trim((string)($_POST['email']??'')),trim((string)($_POST['question']??'')),
                 trim((string)($_POST['order']??'')));
            $_SESSION['master_csrf']=bin2hex(random_bytes(24));
        }catch(InvalidArgumentException $e){
            http_response_code(422);$error=$fa?'اطلاعات واردشده معتبر نیست یا محدودیت درخواست اعمال شده است.':'Please check the form or try later.';
        }catch(Throwable $e){
            http_response_code(503);$error=$fa?'ثبت درخواست موقتاً در دسترس نیست.':'Request intake is temporarily unavailable.';
        }
    }
    $dir=$fa?'rtl':'ltr';$lang=$fa?'fa':'en';$title=$fa?'پرسش از مسترایجنت زمرد ملل':'Ask MojPlayWin Master Agent';
    echo '<!doctype html><html lang="'.$lang.'" dir="'.$dir.'"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'.masterEscape($title).'</title>';
    echo '<style>body{margin:0;background:#10291f;color:#f6efd9;font:16px/1.8 system-ui,Tahoma,Arial,sans-serif}main{max-width:740px;margin:auto;padding:36px 18px}a{color:#f1d28b}h1{color:#f1d28b;font-size:clamp(25px,5vw,36px)}section{background:#1b3b2b;border:1px solid #bda16c;border-radius:18px;padding:24px;margin:20px 0}label{display:block;margin:13px 0 4px}input,select,textarea,button{box-sizing:border-box;width:100%;padding:12px;border-radius:9px;border:1px solid #9aaf96;font:inherit}input,textarea,select{background:#fafbf8;color:#12251b}button{background:#e5ca85;border:0;color:#1c271c;font-weight:700;cursor:pointer;margin-top:16px}.notice{border-inline-start:4px solid #e5ca85;padding:12px}.error{color:#ffb8a7}.honeypot{position:absolute;left:-99999px}</style></head><body><main>';
    echo '<p><a href="/">'.($fa?'بازگشت به سایت':'Back to website').'</a> · <a href="/ask-master/status.php">'.($fa?'پیگیری درخواست قبلی':'Track a previous request').'</a></p><h1>'.masterEscape($title).'</h1>';
    echo '<p>'.($fa?'پاسخ‌های عمومی بدون API خارجی ارائه می‌شوند. پرسش‌های اختصاصی برای بررسی ثبت خواهند شد.':'General guidance works without an external AI API. Specific questions are queued for review.').'</p>';
    if($error!=='')echo '<p class="error" role="alert">'.masterEscape($error).'</p>';
    if($result!==null){
        echo '<section role="status"><h2>'.($fa?'درخواست ثبت شد':'Request received').'</h2><p>'.masterEscape($result['reply']).'</p><p>'.($fa?'شناسه پیگیری: ':'Ticket: ').masterEscape($result['id']).'</p><p><a href="/ask-master/status.php">'.($fa?'پیگیری نتیجه با شناسه و ایمیل':'Check progress with your ticket ID and email').'</a></p></section>';
    }else{
        echo '<section><form method="post" action="/ask-master/index.php" accept-charset="utf-8">';
        echo '<input type="hidden" name="csrf" value="'.masterEscape((string)$_SESSION['master_csrf']).'">';
        echo '<div class="honeypot" aria-hidden="true"><label>Website <input tabindex="-1" autocomplete="off" name="website"></label></div>';
        echo '<label>'.($fa?'نوع درخواست':'Request type').'</label><select name="kind"><option value="question">'.($fa?'پرسش عمومی':'Question').'</option><option value="order_question">'.($fa?'پیگیری سفارش':'Order question').'</option></select>';
        echo '<label>'.($fa?'نام':'Name').'</label><input name="name" maxlength="120" required>';
        echo '<label>'.($fa?'ایمیل':'Email').'</label><input name="email" type="email" maxlength="250" required>';
        echo '<label>'.($fa?'شماره سفارش، فقط برای پیگیری':'Order reference (only if applicable)').'</label><input name="order" maxlength="90">';
        echo '<label>'.($fa?'پرسش شما':'Your question').'</label><textarea name="question" maxlength="2500" minlength="5" rows="5" required></textarea>';
        echo '<button type="submit">'.($fa?'ثبت و دریافت پاسخ اولیه':'Submit and receive initial guidance').'</button></form></section>';
    }
    echo '<p class="notice">'.($fa?'اطلاعات ورود، شماره کارت، رمز، کلید خصوصی یا عبارت بازیابی ارسال نکنید. پاسخ اولیه تأیید پرداخت یا سفارش نیست.':'Do not send passwords, payment card details, private keys, or recovery phrases. This response does not confirm payment or delivery.').'</p></main></body></html>';
}
if(!defined('MASTER_CUSTOMER_TEST_MODE'))masterWeb();
