<?php
declare(strict_types=1);
/**
 * Offline owner-password rotation. CLI only; run on authorized private host.
 * Password is read from STDIN; never pass it as a CLI argument, URL or GitHub
 * secret in this repository. Does not create/guess accounts or weaken policy.
 *
 * php scripts/zomorod_owner_password_rotate.php inspect /absolute/.private/zomorod-business USER
 * php scripts/zomorod_owner_password_rotate.php rotate /absolute/.private/zomorod-business USER
 *
 * For rotate, provide a fresh >=16 character password through a protected
 * terminal/secret-input channel. No plaintext or hash is echoed.
 */
function failSafe(string $reason): never {
    // Controlled error codes; never display DB paths, usernames or secrets.
    fwrite(STDERR,"OWNER_CREDENTIAL_ROTATION=BLOCKED ". $reason ."\n");
    exit(2);
}
if (PHP_SAPI !== 'cli') failSafe('CLI_ONLY');
if ($argc !== 4 || !in_array($argv[1],['inspect','rotate'],true))
    failSafe('ARGUMENTS');
$mode = $argv[1];
$dir = $argv[2];
$username = $argv[3];
if (!is_string($dir) || $dir==='' || $dir[0]!=='/' || !is_dir($dir) || is_link($dir))
    failSafe('UNSAFE_PRIVATE_DIRECTORY');
$real = realpath($dir);
if (!$real || basename($real)!=='zomorod-business' || basename(dirname($real))!=='.private')
    failSafe('UNEXPECTED_PRIVATE_DIRECTORY');
if ((fileperms($real)&0022)!==0) failSafe('PRIVATE_DIRECTORY_WRITABLE_BY_OTHERS');
if (!preg_match('/^[A-Za-z0-9_]{5,40}$/D',$username))
    failSafe('INVALID_USERNAME');
$dbfile=$real.'/management.sqlite3';
if (!is_file($dbfile) || is_link($dbfile) || (fileperms($dbfile)&0077)!==0)
    failSafe('UNSAFE_OR_MISSING_LEDGER_DB');
if (!extension_loaded('pdo_sqlite')) failSafe('SQLITE_DRIVER_MISSING');
try {
    $db = new PDO('sqlite:file:'.$dbfile.'?mode=rw',null,null,[
        PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,
        PDO::ATTR_TIMEOUT=>12,
    ]);
    $db->exec('PRAGMA busy_timeout=12000; PRAGMA foreign_keys=ON;');
    $rows=$db->prepare('SELECT id,role,active,password_hash FROM users WHERE username=?');
    $rows->execute([$username]);$user=$rows->fetch();
    if (!$user || $user['role']!=='admin' || (int)$user['active']!==1)
        failSafe('NO_ACTIVE_ADMIN_FOR_USERNAME');
    if($mode==='inspect'){
        echo "OWNER_LOGIN_ACCOUNT=FOUND_ACTIVE_ADMIN\n";
        echo "PASSWORD=NOT_READ_OR_CHANGED\n";
        exit(0);
    }
    $password=stream_get_contents(STDIN,512);
    if(!is_string($password))failSafe('SECRET_INPUT_MISSING');
    $password=rtrim($password,"\r\n");
    if(strlen($password)<16 || strlen($password)>200 ||
        preg_match('/[\x00-\x1f\x7f]/',$password)===1)
        failSafe('PASSWORD_POLICY_MIN_16_MAX_200');
    if (password_verify($password,(string)$user['password_hash']))
        failSafe('NEW_PASSWORD_EQUALS_OLD');
    $hashed=password_hash($password,PASSWORD_DEFAULT);
    unset($password);
    if(!is_string($hashed)||$hashed==='')failSafe('HASH_FAILED');
    $db->exec('BEGIN IMMEDIATE');
    try{
        $st=$db->prepare("UPDATE users SET password_hash=? WHERE id=? AND role='admin' AND active=1 AND password_hash=?");
        $st->execute([$hashed,(int)$user['id'],(string)$user['password_hash']]);
        if($st->rowCount()!==1)throw new RuntimeException('CONCURRENT_ACCOUNT_CHANGE');
        $db->prepare('INSERT INTO audit_events(user_id,verb,subject,entity_id) VALUES(?,?,?,?)')
           ->execute([(int)$user['id'],'security','owner-password-rotated-cli',(int)$user['id']]);
        $db->exec('COMMIT');
    } catch(Throwable $e){
        if($db->inTransaction())$db->exec('ROLLBACK');
        throw $e;
    }
    echo "OWNER_CREDENTIAL_ROTATION=SUCCESS\n";
    echo "PASSWORD_AND_HASH=NOT_LOGGED\n";
    echo "EXISTING_SESSIONS=VERIFY_APP_SESSION_REVOCATION\n";
} catch(Throwable $error) {
    failSafe('DATABASE_OR_UPDATE_ERROR');
}
