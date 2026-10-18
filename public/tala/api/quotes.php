<?php
declare(strict_types=1);
// Tala-only public price board. Rates are entered and attributed by an authenticated manager.
ini_set('display_errors','0');
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, max-age=0');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');

function answer(array $data,int $status=200):void {
    http_response_code($status);
    echo json_encode($data,JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);
    exit;
}
function error_out(int $status,string $message):void { answer(['ok'=>false,'error'=>$message],$status); }
function database():PDO {
    $file=__DIR__ . '/../../../.tala-secure/tala.sqlite3';
    $folder=dirname($file);
    if (!is_dir($folder)||is_link($folder)||is_link($file)||!is_writable($folder)) error_out(503,'فضای خصوصی تلا آماده نیست.');
    try {
        $db=new PDO('sqlite:'.$file,null,null,[
            PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES=>false
        ]);
        $db->exec('PRAGMA busy_timeout=5000');
        $db->exec('PRAGMA foreign_keys=ON');
        $db->exec("CREATE TABLE IF NOT EXISTS tala_quotes(
            symbol TEXT PRIMARY KEY CHECK(symbol IN ('gold18','gold24','melted','coin')),
            amount_rial INTEGER NOT NULL CHECK(amount_rial>0),
            source_name TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            updated_by INTEGER NOT NULL REFERENCES users(id)
        )");
        $db->exec("CREATE TABLE IF NOT EXISTS tala_quote_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            amount_rial INTEGER NOT NULL,
            source_name TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            updated_by INTEGER NOT NULL REFERENCES users(id)
        )");
        // Added categories live in separate tables: existing gold quote constraints and data stay untouched.
        $db->exec("CREATE TABLE IF NOT EXISTS tala_market_quotes(
            symbol TEXT PRIMARY KEY,
            amount_rial INTEGER NOT NULL CHECK(amount_rial>0),
            source_name TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            updated_by INTEGER NOT NULL REFERENCES users(id)
        )");
        $db->exec("CREATE TABLE IF NOT EXISTS tala_market_quote_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            amount_rial INTEGER NOT NULL CHECK(amount_rial>0),
            source_name TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            updated_by INTEGER NOT NULL REFERENCES users(id)
        )");
        @chmod($file,0600);
        return $db;
    } catch(Throwable $e){
        error_log('Tala quote board database error: '.get_class($e));
        error_out(503,'تابلوی قیمت موقتاً در دسترس نیست.');
    }
}
function manager(PDO $db):array {
    if(($_SERVER['HTTP_ORIGIN']??'')!=='https://zomorodmelal.ir'
        ||($_SERVER['HTTP_X_TALA_REQUEST']??'')!=='1')
        error_out(403,'درخواست معتبر نیست.');
    ini_set('session.use_strict_mode','1');
    ini_set('session.use_only_cookies','1');
    session_name('TALA_SESSION');
    session_set_cookie_params([
        'lifetime'=>0,'path'=>'/tala/','secure'=>true,'httponly'=>true,'samesite'=>'Strict'
    ]);
    if(!@session_start())error_out(503,'نشست امن برقرار نشد.');
    $id=(int)($_SESSION['tala_user_id']??0);
    if($id===0)error_out(401,'ورود مدیر اصلی لازم است.');
    $q=$db->prepare('SELECT id,role,active FROM users WHERE id=?');
    $q->execute([$id]);$user=$q->fetch();
    if(!$user||$user['role']!=='admin'||(int)$user['active']!==1)error_out(403,'فقط مدیر اصلی می‌تواند نرخ ثبت کند.');
    $request=json_decode((string)file_get_contents('php://input'),true);
    if(!is_array($request))error_out(400,'درخواست JSON معتبر نیست.');
    if(!isset($_SESSION['csrf'])||!hash_equals((string)$_SESSION['csrf'],(string)($request['csrf']??'')))
        error_out(403,'نشست یا کد امنیتی معتبر نیست.');
    return [$user,$request];
}
// Approved symbols, fixed valuation unit and age thresholds; no client-defined symbols or units.
const TALA_MARKET_SYMBOLS = [
    'silver999'=>['unit'=>'گرم نقره ۹۹۹','group'=>'metals','max_age'=>3600],
    'silver925'=>['unit'=>'گرم نقره ۹۲۵','group'=>'metals','max_age'=>3600],
    'platinum'=>['unit'=>'گرم پلاتین','group'=>'metals','max_age'=>3600],
    'palladium'=>['unit'=>'گرم پالادیوم','group'=>'metals','max_age'=>3600],
    'usd'=>['unit'=>'یک دلار آمریکا','group'=>'forex','max_age'=>3600],
    'eur'=>['unit'=>'یک یورو','group'=>'forex','max_age'=>3600],
    'gbp'=>['unit'=>'یک پوند بریتانیا','group'=>'forex','max_age'=>3600],
    'aed'=>['unit'=>'یک درهم امارات','group'=>'forex','max_age'=>3600],
    'try'=>['unit'=>'یک لیر ترکیه','group'=>'forex','max_age'=>3600],
    'cad'=>['unit'=>'یک دلار کانادا','group'=>'forex','max_age'=>3600],
    'btc'=>['unit'=>'یک BTC','group'=>'crypto','max_age'=>900],
    'eth'=>['unit'=>'یک ETH','group'=>'crypto','max_age'=>900],
    'usdt'=>['unit'=>'یک USDT','group'=>'crypto','max_age'=>900],
    'trx'=>['unit'=>'یک TRX','group'=>'crypto','max_age'=>900],
    'bnb'=>['unit'=>'یک BNB','group'=>'crypto','max_age'=>900],
    'sol'=>['unit'=>'یک SOL','group'=>'crypto','max_age'=>900]
];
$method=$_SERVER['REQUEST_METHOD']??'GET';
if($method!=='GET'&&$method!=='POST')error_out(405,'روش درخواست مجاز نیست.');
if($method==='POST'&&is_file(__DIR__.'/.tala-maintenance'))error_out(503,'تابلو در حال به‌روزرسانی است.');
$db=database();
if($method==='GET'){
    $data=[];
    $now=time();
    foreach($db->query('SELECT symbol,amount_rial,source_name,observed_at,updated_at FROM tala_quotes') as $row){
        $timestamp=strtotime($row['observed_at']);
        $age=$timestamp===false?PHP_INT_MAX:max(0,$now-$timestamp);
        $data[$row['symbol']]=[
            'amount_rial'=>(int)$row['amount_rial'],
            'source'=>(string)$row['source_name'],
            'observed_at'=>$row['observed_at'],
            'updated_at'=>$row['updated_at'],
            'stale'=>$age>3600
        ];
    }
    foreach($db->query('SELECT symbol,amount_rial,source_name,observed_at,updated_at FROM tala_market_quotes') as $row){
        $symbol=(string)$row['symbol'];
        if(!isset(TALA_MARKET_SYMBOLS[$symbol]))continue;
        $definition=TALA_MARKET_SYMBOLS[$symbol];
        $timestamp=strtotime((string)$row['observed_at']);
        $age=$timestamp===false?PHP_INT_MAX:max(0,$now-$timestamp);
        $data[$symbol]=[
            'amount_rial'=>(int)$row['amount_rial'],
            'source'=>(string)$row['source_name'],
            'observed_at'=>$row['observed_at'],
            'updated_at'=>$row['updated_at'],
            'stale'=>$age>$definition['max_age'],
            'unit'=>$definition['unit'],
            'group'=>$definition['group']
        ];
    }
    answer(['ok'=>true,'scope'=>'tala','mode'=>'manager_verified','currency'=>'IRR','quotes'=>$data,'updated_automatically'=>false]);
}
[$user,$body]=manager($db);
$symbol=(string)($body['symbol']??'');
$legacy=in_array($symbol,['gold18','gold24','melted','coin'],true);
$extended=isset(TALA_MARKET_SYMBOLS[$symbol]);
if(!$legacy&&!$extended)error_out(422,'نماد نرخ پشتیبانی نمی‌شود.');
$amount=(string)($body['amount_rial']??'');
// Extended rates such as BTC/IRR require more than twelve digits; keep legacy gold validation unchanged.
$maxDigits=$legacy?12:15;
if(!preg_match('/^[1-9][0-9]{0,'.($maxDigits-1).'}$/D',$amount))error_out(422,'نرخ باید عدد صحیح ریالی معتبر باشد.');
$source=trim((string)($body['source']??''));
if(strlen($source)<3||strlen($source)>140||preg_match('/[\x00-\x1F\x7F]/',$source))error_out(422,'مرجع نرخ باید نام مشخص و معتبر داشته باشد.');
// The timestamp is server time. "Source" is operator attestation, not a licensed automatic feed.
$now=gmdate('Y-m-d\TH:i:s\Z');
try {
    $db->exec('BEGIN IMMEDIATE');
    $historyTable=$legacy?'tala_quote_history':'tala_market_quote_history';
    $quoteTable=$legacy?'tala_quotes':'tala_market_quotes';
    // Identifiers below are chosen from fixed server-side literals, never the request.
    $q=$db->prepare('INSERT INTO '.$historyTable.'(symbol,amount_rial,source_name,observed_at,updated_at,updated_by) VALUES(?,?,?,?,?,?)');
    $q->execute([$symbol,(int)$amount,$source,$now,$now,(int)$user['id']]);
    $q=$db->prepare('INSERT INTO '.$quoteTable.'(symbol,amount_rial,source_name,observed_at,updated_at,updated_by) VALUES(?,?,?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET amount_rial=excluded.amount_rial,source_name=excluded.source_name,observed_at=excluded.observed_at,updated_at=excluded.updated_at,updated_by=excluded.updated_by');
    $q->execute([$symbol,(int)$amount,$source,$now,$now,(int)$user['id']]);
    $db->commit();
} catch(Throwable $e){
    if($db->inTransaction())$db->rollBack();
    error_log('Tala quote update error: '.get_class($e));
    error_out(503,'ثبت نرخ انجام نشد.');
}
answer(['ok'=>true,'symbol'=>$symbol,'observed_at'=>$now,'mode'=>'manager_verified']);
