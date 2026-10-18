<?php
declare(strict_types=1);
/** One-time Zomorod first owner bootstrap; no plaintext credential ever logged. */
if (PHP_SAPI !== 'cli' || count($argv)!==3) exit(20);
$dbFile=$argv[1]; $receipt=$argv[2];
$expected=realpath(dirname($dbFile));
if ($expected===false || basename($expected)!=='zomorod-business' ||
    !str_ends_with($expected,'/.private/zomorod-business') ||
    !is_file($dbFile) || is_link($dbFile) || file_exists($receipt) ||
    dirname($receipt)!==$expected) exit(21);
$db=new PDO('sqlite:'.$dbFile,null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_TIMEOUT=>12]);
$db->exec('PRAGMA busy_timeout=12000; PRAGMA foreign_keys=ON');
$db->exec('BEGIN IMMEDIATE');
$fd=false;
try{
    $n=(int)$db->query('SELECT COUNT(*) FROM users')->fetchColumn();
    if($n>0){$db->exec('COMMIT');echo "OWNER_BOOTSTRAP=skipped_existing_user\n";exit(0);}
    $username='ZomorodOwner';
    $password=rtrim(strtr(base64_encode(random_bytes(36)),'+/','-_'),'=');
    $hash=password_hash($password,PASSWORD_DEFAULT);
    if(!is_string($hash) || !password_verify($password,$hash)) throw new RuntimeException('Secure hash failed');
    $stmt=$db->prepare('INSERT INTO users(username,password_hash,role,active) VALUES(?,?,"admin",1)');
    $stmt->execute([$username,$hash]);
    $user=(int)$db->lastInsertId();
    $entry=$db->prepare('INSERT INTO audit_events(user_id,verb,subject) VALUES(?,?,?)');
    $entry->execute([$user,'setup','first-owner-private']);
    $fd=fopen($receipt,'x');
    if($fd===false)throw new RuntimeException('Private receipt failed');
    chmod($receipt,0600);
    $body="ZOMOROD MELL PRIVATE OWNER LOGIN\nPortal: https://zomorodmelal.ir/business/\nUsername: ".$username."\nInitial password: ".$password."\nFor safety, rotate this password at /business/?page=security after first login.\nDelete this receipt after safely retaining the updated credentials.\n";
    $length=strlen($body);
    if(fwrite($fd,$body)!==$length){fclose($fd);@unlink($receipt);throw new RuntimeException('Incomplete credential write');}
    fflush($fd);fclose($fd);$fd=false;
    $db->exec('COMMIT');
    unset($body,$password,$hash);
    echo "OWNER_BOOTSTRAP=created\nOWNER_CREDENTIALS=private_cpanel_only\n";
}catch(Throwable $e){
    if($db->inTransaction())$db->exec('ROLLBACK');
    if(is_resource($fd))fclose($fd);
    @unlink($receipt);
    fwrite(STDERR,"OWNER_BOOTSTRAP_FAILED=".get_class($e)."\n");
    exit(22);
}