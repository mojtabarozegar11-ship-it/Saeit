<?php
/** CLI-only setup of a NEW private payment storage; never touches Django DB. */
declare(strict_types=1);
if (PHP_SAPI!=='cli' || !in_array($argv[1]??'', ['init','status','disable'],true)) {
    fwrite(STDERR,"Usage: php bootstrap.php init|status|disable\n"); exit(2);
}
$root='/home/zomorod2/.mojplaywin-crypto-payments-v1';
$action=$argv[1];
if(is_link($root))throw new RuntimeException('Private storage symlink refused');
if($action==='init'){
    umask(0077);
    if(!is_dir($root) && !mkdir($root,0700,true))throw new RuntimeException('Cannot create private storage');
    chmod($root,0700);
    $key=$root.'/rate.key';
    if(!is_file($key)){
        $handle=fopen($key,'x');
        if(!$handle)throw new RuntimeException('Unable to create throttle key');
        fwrite($handle,random_bytes(32));fclose($handle);chmod($key,0600);
    }
    $db=new PDO('sqlite:'.$root.'/payments.sqlite3',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
    $db->exec('PRAGMA journal_mode=DELETE');
    $db->exec('CREATE TABLE IF NOT EXISTS invoices (
        token TEXT PRIMARY KEY, asset TEXT NOT NULL CHECK(asset IN ("ETH","TRX")),
        base INTEGER NOT NULL, quote INTEGER NOT NULL, merchant TEXT NOT NULL,
        reference TEXT NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
        status TEXT NOT NULL CHECK(status IN ("awaiting_payment","confirming","paid")),
        tx_hash TEXT UNIQUE, block_height INTEGER, paid_at INTEGER
    )');
    $db->exec('CREATE INDEX IF NOT EXISTS idx_payment_quote ON invoices(merchant,quote,expires_at,status)');
    $db->exec('CREATE TABLE IF NOT EXISTS throttle (
        action TEXT NOT NULL, who TEXT NOT NULL, bucket INTEGER NOT NULL,
        n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(action,who,bucket)
    )');
    chmod($root.'/payments.sqlite3',0600);
    echo "MOJPLAYWIN_PRIVATE_CRYPTO_DB_INITIALIZED=true\n";
    echo "MOJPLAYWIN_PAYMENTS_ENABLED=false\n";
} elseif($action==='disable') {
    $flag=$root.'/enabled.flag';
    if(is_link($flag))throw new RuntimeException('Unsafe enable flag');
    if(is_file($flag))unlink($flag);
    echo "MOJPLAYWIN_PAYMENTS_ENABLED=false\n";
} else {
    echo "MOJPLAYWIN_PRIVATE_DB_PRESENT=".(is_file($root.'/payments.sqlite3')?'true':'false')."\n";
    echo "MOJPLAYWIN_PAYMENTS_ENABLED=".(is_file($root.'/enabled.flag')?'true':'false')."\n";
}
