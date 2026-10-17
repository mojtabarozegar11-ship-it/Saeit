<?php
declare(strict_types=1);
ini_set('display_errors', '0');
ini_set('log_errors', '1');
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: no-referrer');

const TALA_BOOTSTRAP_TOKEN_SHA256 = '2546ea174f615e02a3b8e3159503b6ea77d7c322e90ffa27f1bb8aae5000c90d';
const TALA_DB_FILE = __DIR__ . '/.private/tala.sqlite3';

function respond(array $payload, int $status = 200): void {
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}
function fail(int $status, string $message): void {
    respond(['ok' => false, 'error' => $message], $status);
}
function db(): PDO {
    if (!is_dir(__DIR__ . '/.private') || !is_writable(__DIR__ . '/.private')) {
        fail(503, 'فضای امن ثبت اطلاعات آماده نیست.');
    }
    umask(0077);
    try {
        $pdo = new PDO('sqlite:' . TALA_DB_FILE, null, null, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES => false,
        ]);
        @chmod(TALA_DB_FILE, 0600);
        $pdo->exec('PRAGMA foreign_keys=ON');
        $pdo->exec('PRAGMA busy_timeout=5000');
        $pdo->exec('PRAGMA journal_mode=DELETE');
        $pdo->exec("CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','operator')),
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )");
        $pdo->exec("CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            created_by INTEGER NOT NULL REFERENCES users(id),
            kind TEXT NOT NULL CHECK(kind IN ('purchase','sale','production','expense','cash_in','cash_out','adjustment')),
            asset TEXT NOT NULL CHECK(asset IN ('gold_bullion','coin','jewelry','gemstone','cash','other')),
            title TEXT NOT NULL,
            weight_g REAL NOT NULL DEFAULT 0,
            amount_rial INTEGER NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            reversal_of INTEGER REFERENCES entries(id)
        )");
        $pdo->exec('CREATE UNIQUE INDEX IF NOT EXISTS one_reversal_per_entry ON entries(reversal_of) WHERE reversal_of IS NOT NULL');
        $pdo->exec('CREATE INDEX IF NOT EXISTS entries_created_at_idx ON entries(created_at DESC, id DESC)');
        $pdo->exec("CREATE TABLE IF NOT EXISTS login_attempts (
            bucket TEXT PRIMARY KEY,
            window_started INTEGER NOT NULL,
            attempts INTEGER NOT NULL
        )");
        $pdo->exec("CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            actor_id INTEGER REFERENCES users(id),
            event TEXT NOT NULL,
            entity_id INTEGER,
            details TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            entry_hash TEXT NOT NULL
        )");
        @chmod(TALA_DB_FILE, 0600);
        return $pdo;
    } catch (Throwable $e) {
        error_log('Tala database initialization failed: ' . get_class($e));
        fail(503, 'پایگاه‌دادهٔ تَلا آماده نیست.');
    }
}
function ensure_request_origin(): void {
    if (($_SERVER['HTTP_ORIGIN'] ?? '') !== 'https://zomorodmelal.ir') {
        fail(403, 'درخواست از مبدأ معتبر پذیرفته می‌شود.');
    }
    if (($_SERVER['HTTP_X_TALA_REQUEST'] ?? '') !== '1') {
        fail(403, 'درخواست معتبر نیست.');
    }
}
function body(): array {
    $raw = file_get_contents('php://input');
    $data = json_decode($raw ?: '', true);
    if (!is_array($data)) fail(400, 'ساختار درخواست درست نیست.');
    return $data;
}
function text_length(string $value): int {
    $count = preg_match_all('/./us', $value);
    return $count === false ? PHP_INT_MAX : $count;
}
function csv_safe(string $value): string {
    return preg_match('/^[\s\x00-\x1f]*[=+@-]/u', $value) ? "'" . $value : $value;
}
function digits(string $s): string {
    return strtr($s, [
        '۰'=>'0','۱'=>'1','۲'=>'2','۳'=>'3','۴'=>'4','۵'=>'5','۶'=>'6','۷'=>'7','۸'=>'8','۹'=>'9',
        '٠'=>'0','١'=>'1','٢'=>'2','٣'=>'3','٤'=>'4','٥'=>'5','٦'=>'6','٧'=>'7','٨'=>'8','٩'=>'9',
        '٬'=>'',','=>'','٫'=>'.',
    ]);
}
function start_session(): void {
    if (session_status() === PHP_SESSION_ACTIVE) return;
    ini_set('session.use_strict_mode', '1');
    ini_set('session.use_only_cookies', '1');
    session_name('TALA_SESSION');
    session_set_cookie_params([
        'lifetime' => 0,
        'path' => '/tala/',
        'secure' => true,
        'httponly' => true,
        'samesite' => 'Strict',
    ]);
    if (!@session_start()) fail(503, 'نشست امن در دسترس نیست.');
}
function current_user(PDO $pdo): array {
    start_session();
    $id = $_SESSION['tala_user_id'] ?? 0;
    if (!$id) fail(401, 'برای ادامه وارد شوید.');
    $q = $pdo->prepare('SELECT id, username, role, active FROM users WHERE id=?');
    $q->execute([(int)$id]);
    $user = $q->fetch();
    if (!$user || !(int)$user['active']) {
        $_SESSION = [];
        session_destroy();
        fail(401, 'نشست معتبر نیست؛ دوباره وارد شوید.');
    }
    return $user;
}
function csrf(array $data): void {
    start_session();
    if (($_SERVER['HTTP_X_TALA_REQUEST'] ?? '') !== '1'
        || !isset($_SESSION['csrf'])
        || !hash_equals((string)$_SESSION['csrf'], (string)($data['csrf'] ?? ''))) {
        fail(403, 'نشست امنیتی منقضی شده؛ صفحه را تازه کنید.');
    }
}
function audit(PDO $pdo, ?int $actor, string $event, ?int $entity, array $details): void {
    $created = gmdate('Y-m-d\TH:i:s\Z');
    $json = json_encode($details, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    $q = $pdo->query('SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1');
    $previous = (string)($q->fetchColumn() ?: str_repeat('0', 64));
    $hash = hash('sha256', $previous . '|' . ($actor ?? '') . '|' . $event . '|' . ($entity ?? '') . '|' . $created . '|' . $json);
    $q = $pdo->prepare('INSERT INTO audit_log(created_at,actor_id,event,entity_id,details,previous_hash,entry_hash) VALUES(?,?,?,?,?,?,?)');
    $q->execute([$created, $actor, $event, $entity, $json, $previous, $hash]);
}
function require_method(string $expected): void {
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== $expected) {
        header('Allow: ' . $expected);
        fail(405, 'روش درخواست پشتیبانی نمی‌شود.');
    }
}
function amount_summary(PDO $pdo): array {
    $row = $pdo->query("SELECT
        COALESCE(SUM(CASE WHEN kind='purchase' THEN amount_rial ELSE 0 END),0) purchases_rial,
        COALESCE(SUM(CASE WHEN kind='sale' THEN amount_rial ELSE 0 END),0) sales_rial,
        COALESCE(SUM(CASE WHEN kind='expense' THEN amount_rial ELSE 0 END),0) expenses_rial,
        COALESCE(SUM(CASE WHEN kind='purchase' THEN weight_g ELSE 0 END),0) bought_g,
        COALESCE(SUM(CASE WHEN kind='sale' THEN weight_g ELSE 0 END),0) sold_g
        FROM entries")->fetch();
    return $row ?: [];
}
function entry_rows(PDO $pdo, int $limit = 200): array {
    $q = $pdo->prepare('SELECT e.id,e.created_at,e.kind,e.asset,e.title,e.weight_g,e.amount_rial,e.note,e.reversal_of,u.username FROM entries e JOIN users u ON u.id=e.created_by ORDER BY e.id DESC LIMIT ?');
    $q->bindValue(1, $limit, PDO::PARAM_INT);
    $q->execute();
    return $q->fetchAll();
}

if (is_file(__DIR__ . '/.tala-maintenance')) fail(503, 'میزکار برای چند لحظه در حال به‌روزرسانی است؛ دوباره تلاش کنید.');
$action = (string)($_GET['action'] ?? '');
$method = (string)($_SERVER['REQUEST_METHOD'] ?? 'GET');

try {
    $pdo = db();

    if ($action === 'status' && $method === 'GET') {
        $count = (int)$pdo->query("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1")->fetchColumn();
        respond(['ok'=>true,'scope'=>'tala','setup_required'=>$count===0,'secure_transport'=>true]);
    }

    if ($action === 'setup' && $method === 'POST') {
        ensure_request_origin();
        $data = body();
        $token = (string)($data['setup_token'] ?? '');
        $username = trim((string)($data['username'] ?? ''));
        $password = (string)($data['password'] ?? '');
        if ($token === '' || strlen($token)>128 || !hash_equals(TALA_BOOTSTRAP_TOKEN_SHA256, hash('sha256',$token))) {
            fail(403, 'کد راه‌اندازی درست نیست.');
        }
        if (!preg_match('/^[A-Za-z0-9._@-]{4,40}$/D', $username)) fail(422, 'نام کاربری باید ۴ تا ۴۰ نویسهٔ لاتین باشد.');
        if (strlen($password)<16 || strlen($password)>200) fail(422, 'رمز عبور باید دست‌کم ۱۶ نویسه داشته باشد.');
        $pdo->exec('BEGIN IMMEDIATE');
        try {
            if ((int)$pdo->query("SELECT COUNT(*) FROM users WHERE role='admin'")->fetchColumn()!==0) {
                $pdo->exec('ROLLBACK');
                fail(409, 'راه‌اندازی اولیه قبلاً انجام شده است.');
            }
            $q=$pdo->prepare("INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,'admin',?)");
            $q->execute([$username,password_hash($password,PASSWORD_DEFAULT),gmdate('Y-m-d\TH:i:s\Z')]);
            $id=(int)$pdo->lastInsertId();
            audit($pdo,$id,'bootstrap_admin_created',$id,['username'=>$username]);
            $pdo->exec('COMMIT');
        } catch (Throwable $e) {
            if ($pdo->inTransaction()) $pdo->rollBack();
            if ($e instanceof PDOException) fail(409, 'این نام کاربری قبلاً ثبت شده یا راه‌اندازی هم‌زمان انجام شده است.');
            throw $e;
        }
        start_session();
        session_regenerate_id(true);
        $_SESSION['tala_user_id']=$id;
        $_SESSION['csrf']=bin2hex(random_bytes(32));
        respond(['ok'=>true,'user'=>['id'=>$id,'username'=>$username,'role'=>'admin'],'csrf'=>$_SESSION['csrf']]);
    }

    if ($action === 'login' && $method === 'POST') {
        ensure_request_origin();
        $data=body();
        $username=trim((string)($data['username']??''));
        $password=(string)($data['password']??'');
        if ($username==='' || strlen($username)>40 || strlen($password)>200) fail(422,'نام کاربری یا رمز عبور درست نیست.');
        $bucket=hash('sha256',($_SERVER['REMOTE_ADDR']??'unknown').'|'.strtolower($username));
        $now=time();
        $q=$pdo->prepare('SELECT window_started,attempts FROM login_attempts WHERE bucket=?');
        $q->execute([$bucket]);$attempt=$q->fetch();
        if ($attempt && $now-(int)$attempt['window_started']<900 && (int)$attempt['attempts']>=5) fail(429,'تلاش‌های ورود زیاد است؛ ۱۵ دقیقه بعد دوباره تلاش کنید.');
        if ($attempt && $now-(int)$attempt['window_started']>=900) {
            $q=$pdo->prepare('DELETE FROM login_attempts WHERE bucket=?');$q->execute([$bucket]);$attempt=false;
        }
        $q=$pdo->prepare('SELECT id,username,password_hash,role FROM users WHERE username=? COLLATE NOCASE AND active=1');
        $q->execute([$username]);$user=$q->fetch();
        if (!$user || !password_verify($password,(string)$user['password_hash'])) {
            if ($attempt) {
                $q=$pdo->prepare('UPDATE login_attempts SET attempts=attempts+1 WHERE bucket=?');$q->execute([$bucket]);
            } else {
                $q=$pdo->prepare('INSERT INTO login_attempts(bucket,window_started,attempts) VALUES(?,?,1)');$q->execute([$bucket,$now]);
            }
            fail(401,'نام کاربری یا رمز عبور درست نیست.');
        }
        $q=$pdo->prepare('DELETE FROM login_attempts WHERE bucket=?');$q->execute([$bucket]);
        start_session();session_regenerate_id(true);
        $_SESSION['tala_user_id']=(int)$user['id'];
        $_SESSION['csrf']=bin2hex(random_bytes(32));
        audit($pdo,(int)$user['id'],'login',(int)$user['id'],[]);
        respond(['ok'=>true,'user'=>['id'=>(int)$user['id'],'username'=>$user['username'],'role'=>$user['role']],'csrf'=>$_SESSION['csrf']]);
    }

    if ($action === 'me' && $method === 'GET') {
        $user=current_user($pdo);
        respond(['ok'=>true,'user'=>['id'=>(int)$user['id'],'username'=>$user['username'],'role'=>$user['role']],'csrf'=>$_SESSION['csrf']??'']);
    }

    if ($action === 'logout' && $method === 'POST') {
        $data=body();$user=current_user($pdo);csrf($data);
        audit($pdo,(int)$user['id'],'logout',(int)$user['id'],[]);
        $_SESSION=[];session_destroy();
        respond(['ok'=>true]);
    }

    if ($action === 'entries' && $method === 'GET') {
        $user=current_user($pdo);
        respond(['ok'=>true,'summary'=>amount_summary($pdo),'entries'=>entry_rows($pdo)]);
    }

    if ($action === 'entry' && $method === 'POST') {
        $data=body();$user=current_user($pdo);csrf($data);
        $types=['purchase','sale','production','expense','cash_in','cash_out','adjustment'];
        $assets=['gold_bullion','coin','jewelry','gemstone','cash','other'];
        $kind=(string)($data['kind']??'');$asset=(string)($data['asset']??'');
        $title=trim((string)($data['title']??''));$note=trim((string)($data['note']??''));
        $amount=digits((string)($data['amount_rial']??''));$weight=digits((string)($data['weight_g']??'0'));
        if (!in_array($kind,$types,true)||!in_array($asset,$assets,true)) fail(422,'نوع سند یا دارایی معتبر نیست.');
        if (text_length($title)<2||text_length($title)>120||text_length($note)>500) fail(422,'عنوان یا یادداشت معتبر نیست.');
        if (!preg_match('/^[0-9]{1,15}$/D',$amount)|| (float)$amount<=0) fail(422,'مبلغ ریالی باید عدد صحیح و بزرگ‌تر از صفر باشد.');
        if (!preg_match('/^[0-9]{1,8}(?:\.[0-9]{1,3})?$/D',$weight)|| (float)$weight>10000000) fail(422,'وزن باید عددی نامنفی با حداکثر سه رقم اعشار باشد.');
        if (in_array($kind,['purchase','sale','production'],true) && (float)$weight<=0) fail(422,'برای خرید، فروش و ساخت وزن را وارد کنید.');
        $created=gmdate('Y-m-d\TH:i:s\Z');
        $pdo->beginTransaction();
        try {
            $q=$pdo->prepare('INSERT INTO entries(created_at,created_by,kind,asset,title,weight_g,amount_rial,note) VALUES(?,?,?,?,?,?,?,?)');
            $q->execute([$created,(int)$user['id'],$kind,$asset,$title,(float)$weight,(int)$amount,$note]);
            $id=(int)$pdo->lastInsertId();audit($pdo,(int)$user['id'],'entry_created',$id,['kind'=>$kind,'asset'=>$asset,'amount_rial'=>$amount,'weight_g'=>$weight]);
            $pdo->commit();
        } catch (Throwable $e) { if ($pdo->inTransaction()) $pdo->rollBack(); throw $e; }
        respond(['ok'=>true,'id'=>$id],201);
    }

    if ($action === 'reverse' && $method === 'POST') {
        $data=body();$user=current_user($pdo);csrf($data);
        $id=(int)($data['id']??0);$reason=trim((string)($data['reason']??''));
        if ($id<1||text_length($reason)<4||text_length($reason)>300) fail(422,'شماره سند یا دلیل اصلاح معتبر نیست.');
        $q=$pdo->prepare('SELECT * FROM entries WHERE id=?');$q->execute([$id]);$row=$q->fetch();
        if (!$row) fail(404,'سند پیدا نشد.');
        if ($user['role']!=='admin') fail(403,'فقط مدیر اصلی می‌تواند سند اصلاحی ثبت کند.');
        if ($row['reversal_of']!==null) fail(409,'سند اصلاحی قابل برگشت دوباره نیست.');
        $q=$pdo->prepare('SELECT COUNT(*) FROM entries WHERE reversal_of=?');$q->execute([$id]);
        if ((int)$q->fetchColumn()>0) fail(409,'برای این سند قبلاً اصلاح ثبت شده است.');
        $pdo->beginTransaction();
        $q=$pdo->prepare('INSERT INTO entries(created_at,created_by,kind,asset,title,weight_g,amount_rial,note,reversal_of) VALUES(?,?,?,?,?,?,?,?,?)');
        $q->execute([gmdate('Y-m-d\TH:i:s\Z'),(int)$user['id'],$row['kind'],$row['asset'],'اصلاح سند شماره '.$id,-(float)$row['weight_g'],-(int)$row['amount_rial'],$reason,$id]);
        $reverseId=(int)$pdo->lastInsertId();audit($pdo,(int)$user['id'],'entry_reversed',$reverseId,['reversal_of'=>$id,'reason'=>$reason]);
        $pdo->commit();respond(['ok'=>true,'id'=>$reverseId]);
    }

    if ($action === 'users' && $method === 'GET') {
        $user=current_user($pdo);
        if ($user['role']!=='admin') fail(403,'فقط مدیر اصلی به کاربران دسترسی دارد.');
        $rows=$pdo->query('SELECT id,username,role,active,created_at FROM users ORDER BY id')->fetchAll();
        respond(['ok'=>true,'users'=>$rows]);
    }

    if ($action === 'user-create' && $method === 'POST') {
        $data=body();$user=current_user($pdo);csrf($data);
        if ($user['role']!=='admin') fail(403,'فقط مدیر اصلی می‌تواند کاربر بسازد.');
        $username=trim((string)($data['username']??''));$password=(string)($data['password']??'');
        if (!preg_match('/^[A-Za-z0-9._@-]{4,40}$/D',$username)) fail(422,'نام کاربری باید ۴ تا ۴۰ نویسهٔ لاتین باشد.');
        if (strlen($password)<16||strlen($password)>200) fail(422,'رمز عبور باید دست‌کم ۱۶ نویسه داشته باشد.');
        $q=$pdo->prepare("INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,'operator',?)");
        try {$q->execute([$username,password_hash($password,PASSWORD_DEFAULT),gmdate('Y-m-d\TH:i:s\Z')]);}
        catch(Throwable $e){fail(409,'نام کاربری قبلاً ثبت شده است.');}
        $id=(int)$pdo->lastInsertId();audit($pdo,(int)$user['id'],'operator_created',$id,['username'=>$username]);
        respond(['ok'=>true,'id'=>$id],201);
    }

    if ($action === 'password' && $method === 'POST') {
        $data=body();$user=current_user($pdo);csrf($data);
        $old=(string)($data['current_password']??'');$new=(string)($data['new_password']??'');
        if (strlen($new)<16||strlen($new)>200) fail(422,'رمز تازه باید دست‌کم ۱۶ نویسه داشته باشد.');
        $q=$pdo->prepare('SELECT password_hash FROM users WHERE id=?');$q->execute([(int)$user['id']]);$hash=(string)$q->fetchColumn();
        if (!password_verify($old,$hash)) fail(403,'رمز فعلی درست نیست.');
        $q=$pdo->prepare('UPDATE users SET password_hash=? WHERE id=?');$q->execute([password_hash($new,PASSWORD_DEFAULT),(int)$user['id']]);
        session_regenerate_id(true);$_SESSION['csrf']=bin2hex(random_bytes(32));
        audit($pdo,(int)$user['id'],'password_changed',(int)$user['id'],[]);
        respond(['ok'=>true,'csrf'=>$_SESSION['csrf']]);
    }

    if ($action === 'audit' && $method === 'GET') {
        $user=current_user($pdo);
        if ($user['role']!=='admin') fail(403,'فقط مدیر اصلی به ردپای حسابرسی دسترسی دارد.');
        $rows=$pdo->query('SELECT a.id,a.created_at,u.username,a.event,a.entity_id,a.details,a.previous_hash,a.entry_hash FROM audit_log a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 100')->fetchAll();
        respond(['ok'=>true,'audit'=>$rows]);
    }

    if ($action === 'export' && $method === 'GET') {
        $user=current_user($pdo);
        if ($user['role']!=='admin') fail(403,'فقط مدیر اصلی به خروجی کامل حسابداری دسترسی دارد.');
        header_remove('Content-Type');
        header('Content-Type: text/csv; charset=utf-8');
        header('Content-Disposition: attachment; filename="tala-ledger.csv"');
        $out=fopen('php://output','w');fwrite($out,"\xEF\xBB\xBF");
        fputcsv($out,['شناسه','زمان UTC','نوع سند','دارایی','عنوان','وزن گرم','مبلغ ریال','یادداشت','ثبت‌کننده','اصلاح سند']);
        foreach(entry_rows($pdo,10000) as $row) fputcsv($out,[$row['id'],$row['created_at'],$row['kind'],$row['asset'],csv_safe((string)$row['title']),$row['weight_g'],$row['amount_rial'],csv_safe((string)$row['note']),$row['username'],$row['reversal_of']]);
        fclose($out);exit;
    }

    fail(404,'مسیر درخواستی پیدا نشد.');
} catch (Throwable $e) {
    error_log('Tala API request failed: ' . get_class($e));
    fail(500,'درخواست کامل نشد؛ پس از بررسی اطلاعات دوباره تلاش کنید.');
}

