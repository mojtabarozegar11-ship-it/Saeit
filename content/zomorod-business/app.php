<?php
declare(strict_types=1);
/** Zomorod Melal / isolated company management & double-entry accounting.
 * Data and this application are intentionally outside public_html.
 * This module does not read/write main-site or other subsite databases. */
ini_set('display_errors', '0');
ini_set('log_errors', '1');
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store, max-age=0');
header('X-Robots-Tag: noindex, nofollow');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: no-referrer');
header('Content-Security-Policy: default-src \'none\'; style-src \'unsafe-inline\'; img-src \'self\' data:; form-action \'self\'; base-uri \'none\'; frame-ancestors \'none\'');
if (extension_loaded('session')) {
    session_name('ZM_BUSINESS');
    session_set_cookie_params(['lifetime'=>0, 'path'=>'/business/', 'secure'=>true, 'httponly'=>true, 'samesite'=>'Strict']);
    session_start();
}
const APP_TITLE = 'میز مدیریت و حسابداری زمرد ملل';
$home = dirname(__DIR__, 2);
$private = $home.'/.private/zomorod-business';
if(is_file($private.'/site_agents.php')) require_once $private.'/site_agents.php';
if(is_file($private.'/site_store.php')) require_once $private.'/site_store.php';
function esc(mixed $s): string {return htmlspecialchars((string)$s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');}
function req(string $k, string $default=''): string {return trim((string)($_POST[$k]??$default));}
function bail(string $m, int $code=422): never {http_response_code($code); throw new RuntimeException($m);}
function cents(string $s): int {if(!preg_match('/^(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?$/',$s))bail('مبلغ نامعتبر است.'); $parts=explode('.',$s,2); return (int)$parts[0]*100+(int)str_pad($parts[1]??'',2,'0');}
function money(int $n): string {return number_format($n/100,2,'.',',');}
function today(): string {return gmdate('Y-m-d');}
function validDate(string $s): bool {$d=DateTimeImmutable::createFromFormat('!Y-m-d',$s);return $d!==false&&$d->format('Y-m-d')===$s;}
function inputDate(string $k): string {$s=req($k,today());if(!validDate($s))bail('تاریخ باید میلادی و به صورت YYYY-MM-DD باشد.');return $s;}
function currency(): string {$v=req('currency','IRR');if(!in_array($v,['IRR','USD','EUR','AED'],true))bail('ارز نامعتبر است.');return $v;}
function doCsrf(): string {if(empty($_SESSION['csrf']))$_SESSION['csrf']=bin2hex(random_bytes(32));return (string)$_SESSION['csrf'];}
function verifyCsrf(): void {if(!hash_equals(doCsrf(),req('csrf')))bail('اعتبار درخواست پایان یافته است. صفحه را تازه کنید.',403);}
function tokenInput(): string {return '<input type="hidden" name="csrf" value="'.esc(doCsrf()).'">';}
function db(string $private): PDO {
    if(!extension_loaded('pdo_sqlite'))throw new RuntimeException('SQLite driver is not available on this server');
    if(!is_dir($private))throw new RuntimeException('Private data directory not found');
    $file=$private.'/management.sqlite3';
    $db=new PDO('sqlite:'.$file, null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_TIMEOUT=>12]);
    $db->exec('PRAGMA journal_mode=WAL; PRAGMA busy_timeout=12000; PRAGMA foreign_keys=ON;');
    $db->exec("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','accountant','manager','viewer')), active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $db->exec("CREATE TABLE IF NOT EXISTS ledger_accounts (id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, type TEXT NOT NULL CHECK(type IN ('asset','liability','equity','income','expense')), active INTEGER NOT NULL DEFAULT 1)");
    $db->exec("CREATE TABLE IF NOT EXISTS journal_entries (id INTEGER PRIMARY KEY, doc_no TEXT NOT NULL UNIQUE, doc_date TEXT NOT NULL, note TEXT NOT NULL, entered_by INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $db->exec("CREATE TABLE IF NOT EXISTS journal_lines (id INTEGER PRIMARY KEY, entry_id INTEGER NOT NULL REFERENCES journal_entries(id), account_id INTEGER NOT NULL REFERENCES ledger_accounts(id), debit INTEGER NOT NULL DEFAULT 0 CHECK(debit>=0), credit INTEGER NOT NULL DEFAULT 0 CHECK(credit>=0), currency TEXT NOT NULL CHECK(currency IN ('IRR','USD','EUR','AED')), CHECK ((debit>0 AND credit=0) OR (credit>0 AND debit=0)))");
    $db->exec("CREATE TABLE IF NOT EXISTS parties (id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('customer','supplier','both')), phone TEXT NOT NULL DEFAULT '', details TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $db->exec("CREATE TABLE IF NOT EXISTS invoices (id INTEGER PRIMARY KEY, invoice_no TEXT UNIQUE NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('sale','purchase')), party_id INTEGER NOT NULL REFERENCES parties(id), invoice_date TEXT NOT NULL, due_date TEXT NOT NULL, description TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>0), currency TEXT NOT NULL, posted_entry INTEGER NOT NULL REFERENCES journal_entries(id), created_by INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $db->exec("CREATE TABLE IF NOT EXISTS invoice_payments (id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL REFERENCES invoices(id), amount INTEGER NOT NULL CHECK(amount>0), paid_on TEXT NOT NULL, entry_id INTEGER NOT NULL UNIQUE REFERENCES journal_entries(id), created_by INTEGER NOT NULL REFERENCES users(id))");
    $db->exec("CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY, sku TEXT UNIQUE NOT NULL, name TEXT NOT NULL, unit TEXT NOT NULL DEFAULT 'عدد', reorder_level INTEGER NOT NULL DEFAULT 0 CHECK(reorder_level>=0))");
    $db->exec("CREATE TABLE IF NOT EXISTS inventory_movements (id INTEGER PRIMARY KEY, inventory_id INTEGER NOT NULL REFERENCES inventory(id), movement_date TEXT NOT NULL, qty INTEGER NOT NULL CHECK(qty<>0), note TEXT NOT NULL, created_by INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $db->exec("CREATE TABLE IF NOT EXISTS employees (id INTEGER PRIMARY KEY, fullname TEXT NOT NULL, job_title TEXT NOT NULL, start_date TEXT NOT NULL, monthly_salary INTEGER NOT NULL DEFAULT 0 CHECK(monthly_salary>=0), active INTEGER NOT NULL DEFAULT 1)");
    $db->exec("CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL, body TEXT NOT NULL, created_by INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $db->exec("CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY, title TEXT NOT NULL, owner TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('planned','active','paused','done')), budget INTEGER NOT NULL DEFAULT 0 CHECK(budget>=0), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $db->exec("CREATE TABLE IF NOT EXISTS audit_events (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), verb TEXT NOT NULL, subject TEXT NOT NULL, entity_id INTEGER, occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $seed=['1000'=>['صندوق','asset'],'1010'=>['بانک','asset'],'1100'=>['حساب‌های دریافتنی','asset'],'1200'=>['موجودی کالا','asset'],'1500'=>['دارایی ثابت','asset'],'2000'=>['حساب‌های پرداختنی','liability'],'2100'=>['مالیات پرداختنی','liability'],'3000'=>['سرمایه','equity'],'4000'=>['درآمد فروش','income'],'5000'=>['بهای تمام‌شده','expense'],'5100'=>['هزینه عملیاتی','expense'],'5200'=>['هزینه حقوق','expense']];
    $s=$db->prepare('INSERT OR IGNORE INTO ledger_accounts(code,name,type) VALUES (?,?,?)');foreach($seed as $code=>$parts)$s->execute([$code,$parts[0],$parts[1]]);
    return $db;
}
function q(PDO $db,string $sql,array $args=[]): array {$s=$db->prepare($sql);$s->execute($args);return $s->fetchAll();}
function one(PDO $db,string $sql,array $args=[]): mixed {$s=$db->prepare($sql);$s->execute($args);return $s->fetchColumn();}
function actor(): int {return (int)($_SESSION['uid']??0);}
function role(): string {return (string)($_SESSION['role']??'');}
function authorize(string $access): void {$roles=['viewer'=>['view'],'manager'=>['view','manage'],'accountant'=>['view','manage','account'],'admin'=>['view','manage','account','users']];if(!in_array($access,$roles[role()]??[],true))bail('دسترسی کافی ندارید.',403);}
function audit(PDO $db,string $verb,string $subject,int $id=0):void {$db->prepare('INSERT INTO audit_events(user_id,verb,subject,entity_id) VALUES(?,?,?,?)')->execute([actor()?:null,$verb,$subject,$id?:null]);}
function record(PDO $db,string $number,string $date,string $note,string $cur,array $lines):int {
    if(strlen($number)>60||strlen($note)>800||!validDate($date))bail('اطلاعات سند نامعتبر است.');
    if(count($lines)<2||count($lines)>12)bail('سند باید بین دو تا دوازده ردیف داشته باشد.');
    $debits=0;$credits=0;
    foreach($lines as $row){[$code,$dr,$cr]=$row;if($dr<0||$cr<0||($dr>0)==($cr>0))bail('در هر ردیف فقط بدهکار یا بستانکار مجاز است.');$debits+=$dr;$credits+=$cr;}
    if($debits===0||$debits!==$credits)bail('جمع بدهکار و بستانکار برابر نیست.');
    $db->prepare('INSERT INTO journal_entries(doc_no,doc_date,note,entered_by) VALUES(?,?,?,?)')->execute([$number,$date,$note,actor()]);
    $id=(int)$db->lastInsertId();$insert=$db->prepare('INSERT INTO journal_lines(entry_id,account_id,debit,credit,currency) VALUES(?,?,?,?,?)');
    foreach($lines as [$code,$dr,$cr]){
        $account=one($db,'SELECT id FROM ledger_accounts WHERE code=? AND active=1',[$code]);
        if(!$account)bail('حساب فعال وجود ندارد: '.$code);
        $insert->execute([$id,(int)$account,$dr,$cr,$cur]);
    }
    audit($db,'post','journal',$id);return $id;
}
function uniqueNo(string $prefix):string {return $prefix.'-'.gmdate('YmdHis').'-'.strtoupper(substr(bin2hex(random_bytes(5)),0,8));}
function layoutStart(string $page,?array $user=null):void {
    $nav=['dashboard'=>'داشبورد','accounts'=>'کدینگ حساب‌ها','journal'=>'اسناد حسابداری','trial'=>'تراز و گزارش','parties'=>'اشخاص','invoices'=>'فروش و خرید','payments'=>'دریافت و پرداخت','inventory'=>'انبار','employees'=>'منابع انسانی','documents'=>'مکاتبات','projects'=>'پروژه‌ها','agent_center'=>'ربات‌ها و ایجنت‌ها','store_manager'=>'مدیریت فروشگاه','audit'=>'ردپای عملیات','security'=>'تغییر گذرواژه','users'=>'کاربران'];
    $navHtml='';foreach($nav as $key=>$label){if($key==='users'&&role()!=='admin')continue;$navHtml.='<a class="'.($page===$key?'sel':'').'" href="?page='.esc($key).'">'.esc($label).'</a>';}
    echo '<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'.esc(APP_TITLE).'</title><link rel="icon" type="image/webp" href="/static/site/zomorod-v7/company-logo.webp"><style>\n    :root{font-family:Tahoma,Arial,sans-serif;color:#e9e7d9;background:#0c1811}*{box-sizing:border-box}body{margin:0;background:#203b23;min-height:100vh}a{color:#d9bc72;text-decoration:none}header{padding:20px 4%;background:#1a341e;border-bottom:3px double #e5c374;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.brand{font-size:21px;color:#edcd79;font-weight:bold}.small{font-size:12px;color:#b9c0ae}nav{display:flex;overflow:auto;gap:8px;padding:16px 4%;background:#1a341e;scrollbar-width:thin}nav a{white-space:nowrap;padding:11px 13px;background:#284c30;border:1px solid #e1c47f;border-radius:12px}nav .sel{color:#081509;background:#d8ba6e;border-color:#f3d590}main{max-width:1260px;margin:auto;padding:26px 20px 70px}h1,h2,h3{color:#edcf88}h1{font-size:clamp(23px,3vw,32px)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(205px,1fr));gap:15px;margin:18px 0}.card,section{background:#18291e;border:1px solid #546545;border-radius:18px;padding:20px;margin:16px 0;box-shadow:0 8px 28px #0002}.metric{font-size:28px;color:#f1d68e;font-weight:bold}table{border-collapse:collapse;width:100%;min-width:580px}th,td{padding:12px;text-align:right;border-bottom:1px solid #405243}th{color:#e4cb83}.scroll{overflow:auto}label{display:block;color:#d1dcbf;margin:9px 0 5px}input,textarea,select{font:inherit;color:#f3eedc;background:#0c1a12;border:1px solid #647153;border-radius:9px;padding:11px;width:100%;max-width:440px}textarea{min-height:88px}button{background:linear-gradient(120deg,#a98741,#f3d584);border:1px solid #f8dd9a;color:#15200e;padding:12px 19px;border-radius:12px;cursor:pointer;font-weight:bold;margin-top:13px}button:hover{filter:brightness(1.1)}.form{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px 18px}.form .full{grid-column:1/-1}.notice{border:1px solid #b99550;background:#354027;padding:15px;border-radius:12px}.danger{background:#4d1e20;border-color:#c26b6b}.muted{color:#bec8b6}.account-line{display:grid;grid-template-columns:1fr 1fr 1fr;gap:7px;margin-bottom:8px}.sign{max-width:540px;margin:70px auto;padding:30px}footer{padding:24px 4%;border-top:1px solid #52613b;text-align:center;color:#bdc7ae;font-size:12px}.tags{display:flex;flex-wrap:wrap;gap:8px}.tags span{border:1px solid #6b7050;border-radius:15px;padding:4px 10px}@media(max-width:650px){.account-line{grid-template-columns:1fr 1fr}.account-line select{grid-column:1/-1}main{padding:14px 12px}header{padding:15px}}\n    </style></head><body><header><div><div class="brand"><img src="/static/site/zomorod-v7/company-logo.webp" alt="نشان شرکت زمرد ملل" width="48" height="48" style="width:48px;height:48px;border-radius:50%;border:2px solid #e5c377;vertical-align:middle;margin-left:12px;background:#fff">زمرد ملل · مدیریت جامع</div><div class="small">مدیریت سازمان · دفاتر مالی · ثبت عملیات با کنترل دسترسی</div></div><div><a href="https://zomorodmelal.ir/">بازگشت به سایت</a>';
    if($user)echo ' · <span class="small">'.esc($user['username']).' ('.esc($user['role']).')</span> · <a href="?page=logout">خروج</a>';
    echo '</div></header>';
    if($user)echo '<nav aria-label="پیمایش مدیریت">'.$navHtml.'</nav>';
    echo '<main>';
}
function layoutEnd():void {echo '</main><footer>تمام حقوق مادی و معنوی سایت برای شرکت کشت و صنعت زمرد ملل محفوظ است . آبان ۱۳۹۸ مجتبی روزگار</footer></body></html>';}
function options(PDO $db,string $sql,array $fields,string $selected=''):string{$out='';foreach(q($db,$sql) as $row){$key=(string)$row[$fields[0]];$out.='<option value="'.esc($key).'"'.($selected===$key?' selected':'').'>'.esc((string)$row[$fields[1]]).'</option>';}return $out;}
function formBegin(string $action):void {echo '<form method="post" autocomplete="off">'.tokenInput().'<input type="hidden" name="action" value="'.esc($action).'">';}
try {
    $db=db($private);
    if(empty($_SESSION['csrf']))doCsrf();
    $count=(int)one($db,'SELECT COUNT(*) FROM users');
    if($count===0){
        // First-owner credentials are provisioned privately; public visitors cannot claim the admin role.
        $receipt=$private.'/owner-first-login.txt';
        $createdReceipt=false;
        $setupTransaction=false;
        try {
            $db->exec('BEGIN IMMEDIATE');
            $setupTransaction=true;
            if((int)one($db,'SELECT COUNT(*) FROM users')===0){
                if(file_exists($receipt))throw new RuntimeException('Private owner receipt already exists; manual recovery required.');
                $username='09175814408';
                $password=rtrim(strtr(base64_encode(random_bytes(36)),'+/','-_'),'=');
                $hash=password_hash($password,PASSWORD_DEFAULT);
                if(!is_string($hash)||!password_verify($password,$hash))throw new RuntimeException('Password generation failed.');
                $previousUmask=umask(0077);
                $handle=@fopen($receipt,'x');
                umask($previousUmask);
                if($handle===false)throw new RuntimeException('Could not create private owner receipt.');
                $createdReceipt=true;
                if(!@chmod($receipt,0600)){fclose($handle);throw new RuntimeException('Could not protect private owner receipt.');}
                $body="ZOMOROD MELL PRIVATE OWNER LOGIN\nPortal: https://zomorodmelal.ir/business/\nUsername: ".$username."\nInitial password: ".$password."\nChange this password immediately under /business/?page=security.\nDelete this receipt after saving the changed credentials securely.\n";
                if(fwrite($handle,$body)!==strlen($body)){fclose($handle);throw new RuntimeException('Incomplete private owner receipt.');}
                fflush($handle);
                if(function_exists('fsync'))@fsync($handle);
                fclose($handle);
                $db->prepare("INSERT INTO users(username,password_hash,role,active) VALUES(?,?,'admin',1)")->execute([$username,$hash]);
                $db->prepare("INSERT INTO audit_events(user_id,verb,subject) VALUES(?,?,?)")->execute([(int)$db->lastInsertId(),'setup','first-owner-private']);
                unset($password,$hash,$body);
            }
            $db->exec('COMMIT');
            $setupTransaction=false;
            // Retire legacy one-time setup material only once an admin account exists.
            @unlink($private.'/setup.token');
        } catch(Throwable $setupError) {
            if($setupTransaction){try{$db->exec('ROLLBACK');}catch(Throwable $ignored){}}
            if($createdReceipt)@unlink($receipt);
            throw $setupError;
        }
    }
    if(($_GET['page']??'')==='logout'){$_SESSION=[];session_destroy();header('Location: /business/',true,303);exit;}
    $uid=actor();$user=$uid?q($db,'SELECT id,username,role,active FROM users WHERE id=?',[$uid])[0]??null:null;
    if(!$user||(int)$user['active']!==1){
        if($_SERVER['REQUEST_METHOD']==='POST'){
            verifyCsrf();$username=req('username');$pass=req('password');
            $attempts=(int)($_SESSION['failed_count']??0);$last=(int)($_SESSION['failed_at']??0);
            if($attempts>=5&&time()-$last<900)bail('ورود موقتاً محدود شده است. ۱۵ دقیقه دیگر تلاش کنید.',429);
            $acc=q($db,'SELECT * FROM users WHERE username=? AND active=1',[$username]);
            if(!$acc||!password_verify($pass,$acc[0]['password_hash'])){
                $_SESSION['failed_count']=$attempts+1;$_SESSION['failed_at']=time();bail('نام کاربری یا رمز عبور اشتباه است.',401);
            }
            $_SESSION['uid']=(int)$acc[0]['id'];$_SESSION['role']=$acc[0]['role'];$_SESSION['failed_count']=0;session_regenerate_id(true);
            header('Location: ?page=dashboard',true,303);exit;
        }
        layoutStart('login');echo '<section class="sign"><h1>ورود مدیر و حسابدار</h1><p>دسترسی فقط برای کاربران مجاز شرکت.</p>';formBegin('login');echo '<label>نام کاربری</label><input name="username" required autocomplete="username"><label>رمز عبور</label><input name="password" type="password" required autocomplete="current-password"><button>ورود امن</button></form></section>';layoutEnd();exit;
    }
    $page=(string)($_GET['page']??'dashboard');
    $post=$_SERVER['REQUEST_METHOD']==='POST';
    if($post){
        verifyCsrf();
        $action=req('action');
        $accountActions=['journal','invoice','payment','account'];
        if($action!=='password_change') authorize(in_array($action,$accountActions,true)?'account':($action==='user'?'users':'manage'));
        if($action==='password_change'){
            $previous=req('previous_password');
            $new=req('new_password');
            $confirmation=req('new_password_confirmation');
            if(strlen($new)<16||strlen($new)>200||$new!==$confirmation||hash_equals($previous,$new)) bail('گذرواژه جدید باید دست‌کم ۱۶ نویسه، متفاوت با قبلی و مطابق تکرار آن باشد.');
            $hash=one($db,'SELECT password_hash FROM users WHERE id=? AND active=1',[actor()]);
            if(!is_string($hash)||!password_verify($previous,$hash)) bail('گذرواژه فعلی صحیح نیست.',403);
            $db->prepare('UPDATE users SET password_hash=? WHERE id=?')->execute([password_hash($new,PASSWORD_DEFAULT),actor()]);
            audit($db,'security','password-change');
            session_regenerate_id(true);
        } elseif($action==='account'){
            $code=req('code');$name=req('name');$type=req('type');if(!preg_match('/^[0-9]{3,8}$/',$code)||$name===''||mbSafeLen($name)>120||!in_array($type,['asset','liability','equity','income','expense'],true))bail('مشخصات حساب نامعتبر است.');
            $db->prepare('INSERT INTO ledger_accounts(code,name,type) VALUES(?,?,?)')->execute([$code,$name,$type]);audit($db,'create','ledger-account',(int)$db->lastInsertId());
        } elseif($action==='journal'){
            $cur=currency();$date=inputDate('date');$note=req('note');$no=req('doc_no');if($no==='')$no=uniqueNo('JV');
            $lines=[];
            for($i=0;$i<6;$i++){
                $code=req('account_'.$i);$dr=req('debit_'.$i);$cr=req('credit_'.$i);
                if($code===''&&$dr===''&&$cr==='')continue;
                if($code===''||($dr===''&&$cr===''))bail('برای هر ردیف معتبر، حساب و مبلغ لازم است.');
                $lines[]=[$code,$dr!==''?cents($dr):0,$cr!==''?cents($cr):0];
            }
            $db->beginTransaction();try{record($db,$no,$date,$note,$cur,$lines);$db->commit();}catch(Throwable $e){$db->rollBack();throw $e;}
        } elseif($action==='party'){
            $name=req('name');$kind=req('kind');if($name===''||!in_array($kind,['customer','supplier','both'],true))bail('اطلاعات شخص نامعتبر است.');
            $db->prepare('INSERT INTO parties(name,kind,phone,details) VALUES(?,?,?,?)')->execute([$name,$kind,req('phone'),req('details')]);audit($db,'create','party',(int)$db->lastInsertId());
        } elseif($action==='invoice'){
            $kind=req('kind');if(!in_array($kind,['sale','purchase'],true))bail('نوع فاکتور نامعتبر است.');
            $party=(int)req('party');if(!one($db,'SELECT id FROM parties WHERE id=?',[$party]))bail('شخص پیدا نشد.');
            $amount=cents(req('amount'));if($amount<=0)bail('مبلغ باید مثبت باشد.');
            $cur=currency();$date=inputDate('date');$due=req('due_date',$date);if(!validDate($due))bail('سررسید نامعتبر است.');
            $desc=req('description');if($desc==='')bail('شرح فاکتور الزامی است.');
            $no=req('invoice_no');if($no==='')$no=uniqueNo('INV');if(strlen($no)>70)bail('شماره فاکتور طولانی است.');
            $db->beginTransaction();try{
                $j=record($db,uniqueNo('IV'),$date,'فاکتور '.$no.' | '.$desc,$cur,$kind==='sale'?[['1100',$amount,0],['4000',0,$amount]]:[['1200',$amount,0],['2000',0,$amount]]);
                $db->prepare('INSERT INTO invoices(invoice_no,kind,party_id,invoice_date,due_date,description,amount,currency,posted_entry,created_by) VALUES(?,?,?,?,?,?,?,?,?,?)')->execute([$no,$kind,$party,$date,$due,$desc,$amount,$cur,$j,actor()]);audit($db,'create','invoice',(int)$db->lastInsertId());$db->commit();
            }catch(Throwable $e){$db->rollBack();throw $e;}
        } elseif($action==='payment'){
            $invoice=(int)req('invoice_id');$db->beginTransaction();$rows=q($db,'SELECT i.*,COALESCE((SELECT SUM(amount) FROM invoice_payments WHERE invoice_id=i.id),0) AS paid FROM invoices i WHERE i.id=?',[$invoice]);
            if(!$rows)bail('فاکتور پیدا نشد.');$inv=$rows[0];$amount=cents(req('amount'));$remaining=(int)$inv['amount']-(int)$inv['paid'];
            if($amount<=0||$amount>$remaining)bail('مبلغ بیشتر از مانده فاکتور یا نامعتبر است.');
            $on=inputDate('date');
            try{
                $j=record($db,uniqueNo('PAY'),$on,'تسویه فاکتور '.$inv['invoice_no'],(string)$inv['currency'],$inv['kind']==='sale'?[['1010',$amount,0],['1100',0,$amount]]:[['2000',$amount,0],['1010',0,$amount]]);
                $db->prepare('INSERT INTO invoice_payments(invoice_id,amount,paid_on,entry_id,created_by) VALUES(?,?,?,?,?)')->execute([$invoice,$amount,$on,$j,actor()]);audit($db,'create','invoice-payment',(int)$db->lastInsertId());$db->commit();
            }catch(Throwable $e){$db->rollBack();throw $e;}
        } elseif($action==='inventory'){
            $sku=req('sku');$name=req('name');if($sku===''||$name==='')bail('شناسه کالا و نام لازم است.');
            $db->prepare('INSERT INTO inventory(sku,name,unit,reorder_level) VALUES(?,?,?,?)')->execute([$sku,$name,req('unit','عدد'),max(0,(int)req('reorder_level','0'))]);audit($db,'create','inventory',(int)$db->lastInsertId());
        } elseif($action==='stock'){
            $id=(int)req('inventory_id');$qty=(int)req('qty');if(!one($db,'SELECT id FROM inventory WHERE id=?',[$id])||$qty===0||abs($qty)>100000000)bail('مقدار کالا نامعتبر است.');
            $now=(int)one($db,'SELECT COALESCE(SUM(qty),0) FROM inventory_movements WHERE inventory_id=?',[$id]);if($now+$qty<0)bail('موجودی انبار منفی می‌شود.');
            $db->prepare('INSERT INTO inventory_movements(inventory_id,movement_date,qty,note,created_by) VALUES(?,?,?,?,?)')->execute([$id,inputDate('date'),$qty,req('note'),actor()]);audit($db,'move','inventory-stock',(int)$db->lastInsertId());
        } elseif($action==='employee'){
            $fullname=req('fullname');$job=req('job_title');if($fullname===''||$job==='')bail('نام و سمت لازم است.');
            $db->prepare('INSERT INTO employees(fullname,job_title,start_date,monthly_salary) VALUES(?,?,?,?)')->execute([$fullname,$job,inputDate('start_date'),cents(req('salary','0'))]);audit($db,'create','employee',(int)$db->lastInsertId());
        } elseif($action==='document'){
            $title=req('title');$body=req('body');if($title===''||$body==='')bail('عنوان و متن سند الزامی است.');
            $db->prepare('INSERT INTO documents(title,category,body,created_by) VALUES(?,?,?,?)')->execute([$title,req('category','اداری'),$body,actor()]);audit($db,'create','document',(int)$db->lastInsertId());
        } elseif($action==='project'){
            $title=req('title');$owner=req('owner');$state=req('state','planned');if($title===''||$owner===''||!in_array($state,['planned','active','paused','done'],true))bail('مشخصات پروژه ناقص است.');
            $db->prepare('INSERT INTO projects(title,owner,state,budget) VALUES(?,?,?,?)')->execute([$title,$owner,$state,cents(req('budget','0'))]);audit($db,'create','project',(int)$db->lastInsertId());
        } elseif(in_array($action,['agent_toggle','agent_run'],true)){
            if(role()!=='admin')bail('فقط مدیر اصلی مجاز است.',403);
            if(!function_exists('zmAgentDb'))bail('موتور ایجنت آماده نیست.',503);
            zmAgentHandle(zmAgentDb($private),$action,req('code'));
            audit($db,'agent',$action);
        } elseif(in_array($action,['product_create','product_toggle'],true)){
            if(role()!=='admin')bail('فقط مدیر اصلی مجاز است.',403);
            if(!function_exists('zmStoreDb'))bail('مدیریت فروشگاه آماده نیست.',503);
            zmStoreHandle(zmStoreDb($private),$action);
            audit($db,'store',$action);
        } elseif($action==='user'){
            $username=req('username');$pass=req('password');$newRole=req('role');if(!preg_match('/^[A-Za-z0-9_]{5,40}$/',$username)||strlen($pass)<14||!in_array($newRole,['admin','accountant','manager','viewer'],true))bail('کاربر، گذرواژه یا نقش نامعتبر است.');
            $db->prepare('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)')->execute([$username,password_hash($pass,PASSWORD_DEFAULT),$newRole]);audit($db,'create','user',(int)$db->lastInsertId());
        } else bail('عملیات مجاز نیست.',403);
        $_SESSION['flash']='عملیات با موفقیت ثبت شد.';
        header('Location: ?page='.rawurlencode($page),true,303);exit;
    }
    layoutStart($page,$user);
    if(isset($_SESSION['flash'])){echo '<div class="notice">'.esc($_SESSION['flash']).'</div>';unset($_SESSION['flash']);}
    echo '<h1>'.esc(APP_TITLE).'</h1><p class="muted">اطلاعات خصوصی شرکت. واحد مبالغ مطابق کد ارز انتخابی است؛ اسناد مالی ثبت‌شده حذف یا ویرایش نمی‌شوند.</p>';
    if($page==='dashboard'){
        $stats=['اسناد حسابداری'=>(int)one($db,'SELECT COUNT(*) FROM journal_entries'),'فاکتورها'=>(int)one($db,'SELECT COUNT(*) FROM invoices'),'اشخاص'=>(int)one($db,'SELECT COUNT(*) FROM parties'),'کالاها'=>(int)one($db,'SELECT COUNT(*) FROM inventory'),'کارکنان'=>(int)one($db,'SELECT COUNT(*) FROM employees'),'پروژه‌ها'=>(int)one($db,'SELECT COUNT(*) FROM projects')];
        echo '<div class="grid">';foreach($stats as $name=>$value)echo '<div class="card"><div class="metric">'.esc($value).'</div><h3>'.esc($name).'</h3></div>';echo '</div><section><h2>وضعیت بهره‌برداری</h2><p>دفترکل دوطرفه، فاکتور، دریافت و پرداخت، انبار، کارمندان، مکاتبات، پروژه‌ها، نقش‌های کاربران و گزارش حسابرسی در این سامانه ثبت می‌شوند. این پنل به بانک یا سامانه‌های دیگر وصل نیست؛ هیچ پرداخت خودکاری انجام نمی‌شود.</p></section>';
    } elseif($page==='agent_center'){
        authorize('view');
        if(!function_exists('zmAgentDb'))bail('موتور ایجنت در دسترس نیست.',503);
        zmAgentRender(zmAgentDb($private));
    } elseif($page==='store_manager'){
        authorize('view');
        if(!function_exists('zmStoreDb'))bail('فروشگاه در دسترس نیست.',503);
        zmStoreRender(zmStoreDb($private));
    } elseif($page==='accounts'){
        echo '<section><h2>کدینگ حساب‌ها</h2><div class="scroll"><table><tr><th>کد</th><th>نام</th><th>نوع</th></tr>';foreach(q($db,'SELECT * FROM ledger_accounts ORDER BY code') as $r)echo '<tr><td>'.esc($r['code']).'</td><td>'.esc($r['name']).'</td><td>'.esc($r['type']).'</td></tr>';echo '</table></div></section>';
        if(in_array(role(),['admin','accountant'],true)){echo '<section><h2>افزودن حساب جدید</h2>';formBegin('account');echo '<div class="form"><div><label>کد</label><input name="code" required pattern="[0-9]{3,8}"></div><div><label>عنوان حساب</label><input name="name" required></div><div><label>ماهیت</label><select name="type"><option value="asset">دارایی</option><option value="liability">بدهی</option><option value="equity">سرمایه</option><option value="income">درآمد</option><option value="expense">هزینه</option></select></div></div><button>ثبت حساب</button></form></section>';}
    } elseif($page==='journal'){
        echo '<section><h2>دفتر روزنامه</h2><div class="scroll"><table><tr><th>سند</th><th>تاریخ</th><th>شرح</th><th>بدهکار</th><th>ارز</th></tr>';
        foreach(q($db,'SELECT j.*,COALESCE(SUM(l.debit),0) total,MAX(l.currency) currency FROM journal_entries j LEFT JOIN journal_lines l ON j.id=l.entry_id GROUP BY j.id ORDER BY j.id DESC LIMIT 100') as $r)echo '<tr><td>'.esc($r['doc_no']).'</td><td>'.esc($r['doc_date']).'</td><td>'.esc($r['note']).'</td><td>'.money((int)$r['total']).'</td><td>'.esc($r['currency']).'</td></tr>';
        echo '</table></div></section>';
        if(in_array(role(),['admin','accountant'],true)){echo '<section><h2>ثبت سند دوطرفه (۲ تا ۶ ردیف)</h2>';formBegin('journal');echo '<div class="form"><div><label>شماره سند اختیاری</label><input name="doc_no" placeholder="خودکار در صورت خالی بودن"></div><div><label>تاریخ میلادی</label><input name="date" type="date" value="'.today().'" required></div><div><label>ارز</label><select name="currency"><option>IRR</option><option>USD</option><option>EUR</option><option>AED</option></select></div><div class="full"><label>شرح سند</label><input name="note" required></div></div><h3>آرتیکل‌های سند</h3>';
            for($i=0;$i<6;$i++)echo '<div class="account-line"><select name="account_'.$i.'"><option value="">انتخاب حساب</option>'.options($db,'SELECT code,code||" — "||name AS label FROM ledger_accounts WHERE active=1 ORDER BY code',['code','label']).'</select><input name="debit_'.$i.'" placeholder="بدهکار، 1000.00"><input name="credit_'.$i.'" placeholder="بستانکار، 1000.00"></div>';
            echo '<button>ثبت غیرقابل‌حذف سند</button></form></section>';}
    } elseif($page==='trial'){
        echo '<section><h2>تراز آزمایشی به تفکیک ارز</h2><div class="scroll"><table><tr><th>حساب</th><th>ارز</th><th>بدهکار</th><th>بستانکار</th><th>مانده</th></tr>';foreach(q($db,'SELECT a.code,a.name,l.currency,SUM(l.debit) AS dr,SUM(l.credit) AS cr FROM journal_lines l JOIN ledger_accounts a ON a.id=l.account_id GROUP BY a.id,l.currency ORDER BY a.code,l.currency') as $r)echo '<tr><td>'.esc($r['code'].' '.$r['name']).'</td><td>'.esc($r['currency']).'</td><td>'.money((int)$r['dr']).'</td><td>'.money((int)$r['cr']).'</td><td>'.money((int)$r['dr']-(int)$r['cr']).'</td></tr>';echo '</table></div></section>';
        echo '<section><h2>خلاصه سود و زیان (در هر ارز)</h2><div class="scroll"><table><tr><th>ارز</th><th>درآمد</th><th>هزینه</th><th>سود/زیان</th></tr>';foreach(q($db,"SELECT l.currency,SUM(CASE WHEN a.type='income' THEN l.credit-l.debit ELSE 0 END) income,SUM(CASE WHEN a.type='expense' THEN l.debit-l.credit ELSE 0 END) expenses FROM journal_lines l JOIN ledger_accounts a ON l.account_id=a.id WHERE a.type IN ('income','expense') GROUP BY l.currency") as $r)echo '<tr><td>'.esc($r['currency']).'</td><td>'.money((int)$r['income']).'</td><td>'.money((int)$r['expenses']).'</td><td>'.money((int)$r['income']-(int)$r['expenses']).'</td></tr>';echo '</table></div></section>';
    } elseif($page==='parties'){
        echo '<section><h2>مشتریان و تأمین‌کنندگان</h2><div class="scroll"><table><tr><th>نام</th><th>نوع</th><th>تلفن</th><th>توضیحات</th></tr>';foreach(q($db,'SELECT * FROM parties ORDER BY id DESC LIMIT 120') as $r)echo '<tr><td>'.esc($r['name']).'</td><td>'.esc($r['kind']).'</td><td>'.esc($r['phone']).'</td><td>'.esc($r['details']).'</td></tr>';echo '</table></div></section>';
        if(role()!=='viewer'){echo '<section><h2>ثبت شخص</h2>';formBegin('party');echo '<div class="form"><div><label>نام</label><input name="name" required></div><div><label>نوع</label><select name="kind"><option value="customer">مشتری</option><option value="supplier">تأمین‌کننده</option><option value="both">هر دو</option></select></div><div><label>تلفن</label><input name="phone"></div><div><label>یادداشت</label><input name="details"></div></div><button>ثبت شخص</button></form></section>';}
    } elseif($page==='invoices'){
        echo '<section><h2>فاکتورهای فروش و خرید</h2><div class="scroll"><table><tr><th>شماره</th><th>نوع</th><th>طرف حساب</th><th>مبلغ</th><th>دریافت/پرداخت</th><th>باقیمانده</th><th>ارز</th></tr>';
        foreach(q($db,'SELECT i.*,p.name AS party,COALESCE((SELECT SUM(amount) FROM invoice_payments WHERE invoice_id=i.id),0) paid FROM invoices i JOIN parties p ON p.id=i.party_id ORDER BY i.id DESC LIMIT 110') as $r)echo '<tr><td>'.esc($r['invoice_no']).'</td><td>'.($r['kind']==='sale'?'فروش':'خرید').'</td><td>'.esc($r['party']).'</td><td>'.money((int)$r['amount']).'</td><td>'.money((int)$r['paid']).'</td><td>'.money((int)$r['amount']-(int)$r['paid']).'</td><td>'.esc($r['currency']).'</td></tr>';echo '</table></div></section>';
        if(in_array(role(),['admin','accountant'],true)){echo '<section><h2>ثبت و صدور فاکتور با سند مالی هم‌زمان</h2><p class="muted">فروش: بدهکار دریافتنی/بستانکار درآمد. خرید: بدهکار موجودی/بستانکار پرداختنی. ارقام بدون مالیات خودکار.</p>';formBegin('invoice');echo '<div class="form"><div><label>شماره فاکتور (خودکار)</label><input name="invoice_no" placeholder="در صورت خالی بودن خودکار"></div><div><label>نوع</label><select name="kind"><option value="sale">فروش</option><option value="purchase">خرید</option></select></div><div><label>طرف حساب</label><select name="party" required>'.options($db,'SELECT id,name FROM parties ORDER BY name',['id','name']).'</select></div><div><label>مبلغ</label><input name="amount" required placeholder="150000.00"></div><div><label>ارز</label><select name="currency"><option>IRR</option><option>USD</option><option>EUR</option><option>AED</option></select></div><div><label>تاریخ میلادی</label><input name="date" type="date" value="'.today().'" required></div><div><label>سررسید میلادی</label><input name="due_date" type="date" value="'.today().'" required></div><div><label>شرح</label><input name="description" required></div></div><button>صدور فاکتور و ثبت سند</button></form></section>';}
    } elseif($page==='payments'){
        echo '<section><h2>دریافت‌ها و پرداخت‌های ثبت‌شده</h2><div class="scroll"><table><tr><th>شماره فاکتور</th><th>تاریخ</th><th>مبلغ</th><th>ارز</th></tr>';foreach(q($db,'SELECT p.*,i.invoice_no,i.currency FROM invoice_payments p JOIN invoices i ON i.id=p.invoice_id ORDER BY p.id DESC LIMIT 130') as $r)echo '<tr><td>'.esc($r['invoice_no']).'</td><td>'.esc($r['paid_on']).'</td><td>'.money((int)$r['amount']).'</td><td>'.esc($r['currency']).'</td></tr>';echo '</table></div></section>';
        if(in_array(role(),['admin','accountant'],true)){echo '<section><h2>ثبت دریافت یا پرداخت مرتبط با فاکتور</h2><p class="muted">ثبت نقدینگی از حساب بانک؛ مبلغ بیش از مانده رد می‌شود. این عملیات انتقال بانکی واقعی انجام نمی‌دهد.</p>';formBegin('payment');echo '<div class="form"><div><label>فاکتور</label><select name="invoice_id">'.options($db,'SELECT i.id,i.invoice_no||" / "||p.name AS label FROM invoices i JOIN parties p ON p.id=i.party_id ORDER BY i.id DESC',['id','label']).'</select></div><div><label>مبلغ</label><input name="amount" required></div><div><label>تاریخ</label><input name="date" type="date" value="'.today().'" required></div></div><button>ثبت تسویه و سند حسابداری</button></form></section>';}
    } elseif($page==='inventory'){
        echo '<section><h2>کالاها و موجودی تعدادی</h2><div class="scroll"><table><tr><th>کد</th><th>نام</th><th>واحد</th><th>موجودی</th><th>نقطه سفارش</th></tr>';foreach(q($db,'SELECT i.*,COALESCE(SUM(m.qty),0) stock FROM inventory i LEFT JOIN inventory_movements m ON i.id=m.inventory_id GROUP BY i.id ORDER BY i.id DESC') as $r)echo '<tr><td>'.esc($r['sku']).'</td><td>'.esc($r['name']).'</td><td>'.esc($r['unit']).'</td><td>'.(int)$r['stock'].'</td><td>'.(int)$r['reorder_level'].'</td></tr>';echo '</table></div></section>';
        if(role()!=='viewer'){echo '<section><h2>تعریف کالا</h2>';formBegin('inventory');echo '<div class="form"><div><label>شناسه</label><input name="sku" required></div><div><label>نام کالا</label><input name="name" required></div><div><label>واحد</label><input name="unit" value="عدد"></div><div><label>نقطه سفارش</label><input name="reorder_level" type="number" min="0" value="0"></div></div><button>ثبت کالا</button></form></section><section><h2>ورود یا خروج کالا</h2><p>ورود با عدد مثبت، خروج با عدد منفی. این فرم فقط کنترل تعداد است و خودکار سند ارزش ریالی ایجاد نمی‌کند.</p>';formBegin('stock');echo '<div class="form"><div><label>کالا</label><select name="inventory_id">'.options($db,'SELECT id,sku||" — "||name label FROM inventory ORDER BY name',['id','label']).'</select></div><div><label>تغییر تعداد (مثلاً 10 یا -5)</label><input type="number" name="qty" required></div><div><label>تاریخ</label><input type="date" name="date" value="'.today().'"></div><div><label>شرح</label><input name="note"></div></div><button>ثبت حرکت</button></form></section>';}
    } elseif($page==='employees'){
        echo '<section><h2>پرسنل</h2><div class="scroll"><table><tr><th>نام</th><th>سمت</th><th>شروع همکاری</th><th>حقوق پایه قراردادی (IRR)</th></tr>';foreach(q($db,'SELECT * FROM employees ORDER BY id DESC') as $r)echo '<tr><td>'.esc($r['fullname']).'</td><td>'.esc($r['job_title']).'</td><td>'.esc($r['start_date']).'</td><td>'.money((int)$r['monthly_salary']).'</td></tr>';echo '</table></div></section>';
        if(role()!=='viewer'){echo '<section><h2>افزودن کارمند</h2>';formBegin('employee');echo '<div class="form"><div><label>نام کامل</label><input name="fullname" required></div><div><label>سمت</label><input name="job_title" required></div><div><label>تاریخ شروع</label><input type="date" name="start_date" value="'.today().'" required></div><div><label>حقوق پایه (IRR)</label><input name="salary" value="0"></div></div><button>ثبت پرسنل</button></form></section>';}
    } elseif($page==='documents'){
        echo '<section><h2>نامه‌ها و مکاتبات اداری</h2>';foreach(q($db,'SELECT * FROM documents ORDER BY id DESC LIMIT 50') as $r)echo '<article class="card"><h3>'.esc($r['title']).' · '.esc($r['category']).'</h3><p>'.nl2br(esc($r['body'])).'</p><small class="muted">'.esc($r['created_at']).'</small></article>';echo '</section>';
        if(role()!=='viewer'){echo '<section><h2>ثبت نامه یا دستورکار</h2>';formBegin('document');echo '<label>عنوان</label><input name="title" required><label>دسته</label><input name="category" value="اداری"><label>متن</label><textarea name="body" required></textarea><br><button>ثبت سند اداری</button></form></section>';}
    } elseif($page==='projects'){
        echo '<section><h2>پروژه‌های شرکت</h2><div class="scroll"><table><tr><th>نام</th><th>مسئول</th><th>وضعیت</th><th>بودجه IRR</th></tr>';foreach(q($db,'SELECT * FROM projects ORDER BY id DESC') as $r)echo '<tr><td>'.esc($r['title']).'</td><td>'.esc($r['owner']).'</td><td>'.esc($r['state']).'</td><td>'.money((int)$r['budget']).'</td></tr>';echo '</table></div></section>';
        if(role()!=='viewer'){echo '<section><h2>افزودن پروژه</h2>';formBegin('project');echo '<div class="form"><div><label>عنوان پروژه</label><input name="title" required></div><div><label>مسئول</label><input name="owner" required></div><div><label>وضعیت</label><select name="state"><option value="planned">برنامه‌ریزی</option><option value="active">فعال</option><option value="paused">متوقف</option><option value="done">خاتمه‌یافته</option></select></div><div><label>بودجه IRR</label><input name="budget" value="0"></div></div><button>ثبت پروژه</button></form></section>';}
    } elseif($page==='audit'){
        echo '<section><h2>ردپای عملیات ثبت‌شده</h2><div class="scroll"><table><tr><th>زمان UTC</th><th>کاربر</th><th>عملیات</th><th>موضوع</th><th>شناسه</th></tr>';foreach(q($db,'SELECT e.*,u.username FROM audit_events e LEFT JOIN users u ON u.id=e.user_id ORDER BY e.id DESC LIMIT 150') as $r)echo '<tr><td>'.esc($r['occurred_at']).'</td><td>'.esc($r['username']).'</td><td>'.esc($r['verb']).'</td><td>'.esc($r['subject']).'</td><td>'.esc($r['entity_id']).'</td></tr>';echo '</table></div></section>';
    } elseif($page==='security'){
        echo '<section><h2>تغییر گذرواژه حساب</h2><p class="muted">برای حفاظت از اطلاعات مالی، پس از نخستین ورود رمز اولیه را تغییر دهید.</p>';
        formBegin('password_change');
        echo '<label>گذرواژه فعلی</label><input type="password" name="previous_password" required autocomplete="current-password"><label>گذرواژه جدید (دست‌کم ۱۶ نویسه)</label><input type="password" name="new_password" required minlength="16" autocomplete="new-password"><label>تکرار گذرواژه جدید</label><input type="password" name="new_password_confirmation" required minlength="16" autocomplete="new-password"><button>ذخیره گذرواژه جدید</button></form></section>';
    } elseif($page==='users'){
        authorize('users');echo '<section><h2>دسترسی کاربران</h2><div class="scroll"><table><tr><th>نام کاربری</th><th>سطح دسترسی</th><th>فعال</th></tr>';foreach(q($db,'SELECT username,role,active FROM users ORDER BY id') as $r)echo '<tr><td>'.esc($r['username']).'</td><td>'.esc($r['role']).'</td><td>'.($r['active']?'بله':'خیر').'</td></tr>';echo '</table></div></section><section><h2>ایجاد کاربر</h2>';formBegin('user');echo '<div class="form"><div><label>نام کاربری (انگلیسی)</label><input name="username" required></div><div><label>رمز دست‌کم ۱۴ نویسه</label><input name="password" type="password" required minlength="14"></div><div><label>نقش</label><select name="role"><option value="viewer">مشاهده‌گر</option><option value="manager">مدیر</option><option value="accountant">حسابدار</option><option value="admin">مدیر کل</option></select></div></div><button>ایجاد حساب کاربری</button></form></section>';
    } else{http_response_code(404);echo '<p class="notice danger">صفحه موجود نیست.</p>';}
    layoutEnd();
}catch(Throwable $e){
    $code=http_response_code();if($code<400)http_response_code(500);
    error_log('ZM BUSINESS ERROR ['.get_class($e).']: '.$e->getMessage());
    if(!headers_sent())header('Content-Type: text/html; charset=utf-8');
    echo '<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><title>زمرد ملل · خطا</title><body style="font-family:Tahoma;background:#112015;color:#e4c77f;padding:25px"><h1>درخواست انجام نشد</h1><p>لطفاً داده‌های ورودی یا دسترسی را بررسی کنید. خطا در گزارش خصوصی سامانه ثبت شد.</p><a href="/business/" style="color:#f2d38c">بازگشت به مدیریت</a></body></html>';
}
function mbSafeLen(string $s):int{return function_exists('mb_strlen')?mb_strlen($s,'UTF-8'):strlen($s);}