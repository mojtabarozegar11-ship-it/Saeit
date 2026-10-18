<?php
/** Independent MojPlayWin watch-only ETH/TRX service-payment gateway.
 * No shared Django files/DB, no wallet private keys, no automatic product claims.
 */
declare(strict_types=1);
const ROOT='https://mojplaywin.com/checkout/crypto/';
const DATA='/home/zomorod2/.mojplaywin-crypto-payments-v1';
const ETH_TO='0x89149b01f59115B86553561F12438D2ADF517E75';
const TRX_TO='THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73';
const TRX_HEX='414FD76FC6FB6370DCC86170E9695610EBF559DDAD';
const ETH_RPC='https://ethereum-rpc.publicnode.com';
const TRX_RPC='https://api.trongrid.io/walletsolidity/';
const MAX_ETH=1000000000000000000;
const MAX_TRX=10000000000;

header('Cache-Control: private, no-store');
header('Referrer-Policy: no-referrer');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
header('Content-Type: text/html; charset=utf-8');
if (strtolower(explode(':',$_SERVER['HTTP_HOST']??'')[0])!=='mojplaywin.com' &&
    strtolower(explode(':',$_SERVER['HTTP_HOST']??'')[0])!=='www.mojplaywin.com') {http_response_code(404); exit;}
if (($_SERVER['HTTPS']??'')==='off' || empty($_SERVER['HTTPS'])) {http_response_code(503); exit('HTTPS required');}
if (!is_file(DATA.'/enabled.flag')) {http_response_code(503); exit('Crypto checkout is not enabled yet.');}

session_name('MOJCRYPTO');
session_set_cookie_params(['path'=>'/checkout/crypto/','secure'=>true,'httponly'=>true,'samesite'=>'Lax']);
session_start();
if (!isset($_SESSION['csrf'])) $_SESSION['csrf']=bin2hex(random_bytes(24));
function e(mixed $x):string{return htmlspecialchars((string)$x,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
function display(string $heading,string $body,int $status=200):never{
 http_response_code($status);
 echo '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'.e($heading).' | MojPlayWin</title><style>body{background:#101011;color:#e9dfc7;font:16px system-ui;line-height:1.5;margin:3em auto;padding:0 1em;max-width:720px}main{background:#1d1d20;padding:2em;border:1px solid #89703e;border-radius:15px}h1{color:#efd08d}a{color:#edca75}input,select{display:block;width:100%;box-sizing:border-box;padding:.7em;margin:.4em 0 1em;background:#29282b;color:#fff;border:1px solid #80683d}button{padding:.8em 1.3em;border:0;border-radius:6px;background:#edc875;color:#111;font-weight:bold}code{display:block;overflow-wrap:anywhere;padding:1em;color:#ffdc9a;background:#2a292b}small{color:#bbb}</style></head><body><main><p><a href="/store/">← Back to MojPlayWin Store</a></p><h1>'.e($heading).'</h1>'.$body.'<p><small>Only native ETH (Ethereum mainnet) and native TRX (TRON mainnet). No USDT, token transfers or other chains. No wallet seed phrase is ever required.</small></p></main></body></html>';exit;
}
function bad(string $s,int $status=400):never{display('Payment notice','<p role="alert">'.e($s).'</p><p><a href="'.ROOT.'">Start again</a></p>',$status);}
function db():PDO{return new PDO('sqlite:'.DATA.'/payments.sqlite3',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_TIMEOUT=>3]);}
function limit(PDO $db,string $action,int $max):void{
 $bucket=(int)floor(time()/600);
 $ip=hash_hmac('sha256',$action.':'.($_SERVER['REMOTE_ADDR']??''),file_get_contents(DATA.'/rate.key'));
 $db->exec('BEGIN IMMEDIATE');
 try{$q=$db->prepare('INSERT INTO throttle(action,who,bucket,n) VALUES(?,?,?,1) ON CONFLICT(action,who,bucket) DO UPDATE SET n=n+1');$q->execute([$action,$ip,$bucket]);
 $q=$db->prepare('SELECT n FROM throttle WHERE action=? AND who=? AND bucket=?');$q->execute([$action,$ip,$bucket]);$tooMany=(int)$q->fetchColumn()>$max;$db->commit();
 }catch(Throwable $x){$db->rollBack();throw $x;}
 if($tooMany)bad('Too many attempts. Please try later.',429);
}
function atomic(string $s,string $asset):int{
 $digits=$asset==='ETH'?18:6;
 if(!preg_match('/^(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,'.$digits.'})?$/D',$s))bad('Invalid native coin amount.');
 $parts=explode('.',$s,2);$whole=(int)$parts[0];$fraction=(int)str_pad($parts[1]??'',$digits,'0');
 $n=$whole*(10**$digits)+$fraction;
 $min=$asset==='ETH'?100000000000000:1000000;$max=$asset==='ETH'?MAX_ETH:MAX_TRX;
 if($n<$min||$n>$max)bad('For TRX select 1–10000 coins; for ETH select 0.0001–1 coin.');
 return $n;
}
function human(int $n,string $asset):string{
 $digits=$asset==='ETH'?18:6;$s=str_pad((string)$n,$digits+1,'0',STR_PAD_LEFT);
 $part=rtrim(substr($s,-$digits),'0');return substr($s,0,-$digits).($part===''?'':'.'.$part);
}
function remote(string $url,array $args):array{
 if(!in_array($url,[ETH_RPC,TRX_RPC.'gettransactionbyid',TRX_RPC.'gettransactioninfobyid',TRX_RPC.'getnowblock'],true))throw new RuntimeException('Unsupported chain source.');
 $curl=curl_init($url);curl_setopt_array($curl,[CURLOPT_POST=>true,CURLOPT_POSTFIELDS=>json_encode($args,JSON_THROW_ON_ERROR),CURLOPT_HTTPHEADER=>['Content-Type: application/json'],CURLOPT_RETURNTRANSFER=>true,CURLOPT_CONNECTTIMEOUT=>4,CURLOPT_TIMEOUT=>9,CURLOPT_SSL_VERIFYPEER=>true,CURLOPT_SSL_VERIFYHOST=>2,CURLOPT_FOLLOWLOCATION=>false]);
 $body=curl_exec($curl);$code=curl_getinfo($curl,CURLINFO_HTTP_CODE);$err=curl_errno($curl);curl_close($curl);
 if($err||$code!==200||!is_string($body)||strlen($body)>500000)throw new RuntimeException('Blockchain service unavailable.');
 $json=json_decode($body,true);if(!is_array($json)||isset($json['Error']))throw new RuntimeException('Unreliable blockchain response.');return $json;
}
function eth(string $method,array $params):mixed{
 $x=remote(ETH_RPC,['jsonrpc'=>'2.0','id'=>1,'method'=>$method,'params'=>$params]);
 if(isset($x['error'])||!array_key_exists('result',$x))throw new RuntimeException('ETH node rejected verification.');
 return $x['result'];
}
function check_chain(array $i,string $hash):array{
 $h=strtolower($hash);
 if(!preg_match('/^(?:0x)?[a-f0-9]{64}$/D',$h))throw new RuntimeException('Invalid transaction hash.');
 if($i['asset']==='ETH'){
  $h='0x'.substr($h,-64);
  if(eth('eth_chainId',[])!=='0x1')throw new RuntimeException('Wrong ETH network.');
  $t=eth('eth_getTransactionByHash',[$h]);$r=eth('eth_getTransactionReceipt',[$h]);
  if(!is_array($t)||!is_array($r)||empty($t['blockNumber'])||empty($r['blockNumber']))throw new RuntimeException('ETH transaction not mined.');
  if(strtolower((string)($t['hash']??''))!==$h||strtolower((string)($r['transactionHash']??''))!==$h)throw new RuntimeException('ETH transaction ID mismatch.');
  if(strtolower((string)($t['to']??''))!==strtolower(ETH_TO)||hexdec((string)($t['value']??''))!==(int)$i['quote'])throw new RuntimeException('ETH recipient or amount mismatch.');
  if(($r['status']??'')!=='0x1'||$t['blockNumber']!==$r['blockNumber'])throw new RuntimeException('ETH transfer failed.');
  $block=hexdec($t['blockNumber']);$head=eth('eth_getBlockByNumber',[$t['blockNumber'],false]);
  if(!is_array($head)||hexdec((string)($head['number']??''))!==$block)throw new RuntimeException('Invalid ETH block.');
  $bh=strtolower((string)($head['hash']??''));
  if(!preg_match('/^0x[a-f0-9]{64}$/D',$bh)||strtolower((string)($t['blockHash']??''))!==$bh||strtolower((string)($r['blockHash']??''))!==$bh)throw new RuntimeException('ETH block mismatch.');
  $confirmations=hexdec((string)eth('eth_blockNumber',[]))-$block+1;$when=hexdec((string)($head['timestamp']??''));$needed=12;
 }else{
  $h=substr($h,-64);$t=remote(TRX_RPC.'gettransactionbyid',['value'=>$h]);$r=remote(TRX_RPC.'gettransactioninfobyid',['value'=>$h]);$tip=remote(TRX_RPC.'getnowblock',[]);
  if(strtolower((string)($t['txID']??''))!==$h||strtolower((string)($r['id']??''))!==$h)throw new RuntimeException('TRX transaction not finalized.');
  $c=$t['raw_data']['contract']??[];
  if(!is_array($c)||count($c)!==1||($c[0]['type']??'')!=='TransferContract')throw new RuntimeException('Not native TRX.');
  $v=$c[0]['parameter']['value']??[];
  if(strtoupper((string)($v['to_address']??''))!==TRX_HEX||(int)($v['amount']??-1)!==(int)$i['quote'])throw new RuntimeException('TRX recipient or amount mismatch.');
  foreach([$r['result']??null,$r['receipt']['result']??null,$t['ret'][0]['contractRet']??null] as $result)if($result!==null&&$result!=='SUCCESS')throw new RuntimeException('TRX execution failed.');
  $block=(int)($r['blockNumber']??0);if($block<=0)throw new RuntimeException('Missing finalized TRX block.');
  $confirmations=(int)($tip['block_header']['raw_data']['number']??0)-$block+1;$when=(int)floor((int)($r['blockTimeStamp']??0)/1000);$needed=20;
 }
 if($confirmations<1)throw new RuntimeException('Chain inclusion not confirmed.');
 if($when<(int)$i['created_at']-60||$when>(int)$i['expires_at']+60||$when>time()+120)throw new RuntimeException('Transfer outside invoice payment window.');
 return ['hash'=>$h,'confirmations'=>$confirmations,'required'=>$needed,'height'=>$block];
}
function reconcile(PDO $db,array $invoice,string $tx):string{
 if($invoice['status']==='paid')return 'paid';
 if($invoice['tx_hash']!==null&&strtolower($tx)!==strtolower((string)$invoice['tx_hash']))throw new RuntimeException('This invoice is bound to another transaction.');
 $proof=check_chain($invoice,$tx);$status=$proof['confirmations']>=$proof['required']?'paid':'confirming';
 $db->exec('BEGIN IMMEDIATE');
 try{
  $q=$db->prepare('SELECT status,tx_hash FROM invoices WHERE token=?');$q->execute([$invoice['token']]);$latest=$q->fetch();
  if(!$latest)throw new RuntimeException('Invoice no longer exists.');
  if($latest['status']==='paid'){$db->commit();return 'paid';}
  if($latest['tx_hash']!==null&&$latest['tx_hash']!==$proof['hash'])throw new RuntimeException('Changed transaction claim.');
  $q=$db->prepare('UPDATE invoices SET status=?,tx_hash=?,block_height=?,paid_at=? WHERE token=?');
  $q->execute([$status,$proof['hash'],$proof['height'],$status==='paid'?time():null,$invoice['token']]);
  $db->commit();return $status;
 }catch(Throwable $x){$db->rollBack();throw $x;}
}
function csrf():string{return '<input type="hidden" name="csrf" value="'.e($_SESSION['csrf']).'">';}
function invoice_screen(array $i,string $msg=''):never{
 $paid=$i['status']==='paid';$s='<p>Reference: <strong>'.e($i['reference']).'</strong>. Status: <strong>'.e($i['status']).'</strong>.</p>';
 if($msg!=='')$s.='<p role="status">'.e($msg).'</p>';
 if($paid)$s.='<p>Payment confirmed on-chain and recorded. This is your receipt. Services are fulfilled separately under the agreed terms.</p>';
 else{
  if(time()>(int)$i['expires_at'])$s.='<p>Invoice expired. Do not send new funds. You can verify a previous transfer made during its valid window.</p>';
  else $s.='<p>Send exactly <strong>'.e(human((int)$i['quote'],$i['asset'])).' '.e($i['asset']).'</strong> on '.($i['asset']==='ETH'?'Ethereum Mainnet':'TRON Mainnet').' to:</p><code>'.e($i['merchant']).'</code>';
  $s.='<p>Invoice expiry: '.gmdate('Y-m-d H:i',(int)$i['expires_at']).' UTC.</p><form method="post">'.csrf().'<input type="hidden" name="action" value="verify"><input type="hidden" name="id" value="'.e($i['token']).'"><label>Your on-chain transaction hash</label><input name="tx_hash" maxlength="66" value="'.e($i['tx_hash']??'').'" required><button>Verify payment automatically</button></form>';
  if($i['status']==='confirming')$s.='<p>Network finality pending; refresh to retry confirmation. No merchant approval is needed.</p>';
 }
 display('Payment invoice #'.substr($i['token'],0,8),$s);
}
try{
 $db=db();$post=($_SERVER['REQUEST_METHOD']??'GET')==='POST';
 if($post&&!hash_equals($_SESSION['csrf'],(string)($_POST['csrf']??'')))bad('Invalid session; refresh the page.',403);
 if($post&&isset($_SERVER['HTTP_ORIGIN'])&&strtolower((string)parse_url((string)$_SERVER['HTTP_ORIGIN'],PHP_URL_HOST))!==strtolower($host??explode(':',$_SERVER['HTTP_HOST'])[0]))bad('Invalid browser origin.',403);
 if($post&&($_POST['action']??'')==='create'){
  limit($db,'create',5);
  $asset=(string)($_POST['asset']??'');if(!in_array($asset,['ETH','TRX'],true))bad('Unsupported native network.');
  $base=atomic(trim((string)($_POST['amount']??'')),$asset);
  $ref=trim((string)($_POST['reference']??''));
  if(strlen($ref)<3||strlen($ref)>80||preg_match('/[<>\x00-\x1f]/',$ref))bad('A short invoice reference is required.');
  $merchant=$asset==='ETH'?ETH_TO:TRX_TO;$token=bin2hex(random_bytes(24));$now=time();
  for($n=0;$n<16;$n++){
   $amount=$base+random_int(1,9999);
   $q=$db->prepare('SELECT 1 FROM invoices WHERE merchant=? AND quote=? AND (expires_at>=? OR status="confirming") LIMIT 1');
   $q->execute([$merchant,$amount,$now]);if($q->fetchColumn())continue;
   $q=$db->prepare('INSERT INTO invoices(token,asset,base,quote,merchant,reference,created_at,expires_at,status) VALUES(?,?,?,?,?,?,?,?,"awaiting_payment")');
   $q->execute([$token,$asset,$base,$amount,$merchant,$ref,$now,$now+1800]);
   header('Location: '.ROOT.'?id='.$token,true,303);exit;
  }
  bad('Unique invoice amount unavailable; retry later.',409);
 }
 $token=(string)($post?($_POST['id']??''):($_GET['id']??''));
 if($token!==''){
  if(!preg_match('/^[a-f0-9]{48}$/D',$token))bad('Unknown invoice.',404);
  $q=$db->prepare('SELECT * FROM invoices WHERE token=?');$q->execute([$token]);$i=$q->fetch();if(!$i)bad('Invoice not found.',404);
  $notice='';
  if($post&&($_POST['action']??'')==='verify'){
   limit($db,'verify',20);
   try{$result=reconcile($db,$i,trim((string)($_POST['tx_hash']??'')));$notice=$result==='paid'?'Payment confirmed successfully.':'Transfer detected; still waiting for confirmations.';}
   catch(Throwable $err){$notice=$err instanceof PDOException?'Unable to verify this invoice.':$err->getMessage();}
   $q=$db->prepare('SELECT * FROM invoices WHERE token=?');$q->execute([$token]);$i=$q->fetch();
  }
  invoice_screen($i,$notice);
 }
 if($post)bad('Invalid action.',405);
 display('MojPlayWin secure payments',
  '<p>For agreed custom services and project payments, create a native ETH or TRX invoice. You choose only the amount agreed with MojPlayWin; these transfers do not purchase a fixed-price catalog product. No merchant approval is required after network verification.</p><form method="post">'.csrf().'<input type="hidden" name="action" value="create"><label>Network</label><select name="asset"><option value="TRX">TRX — TRON mainnet</option><option value="ETH">ETH — Ethereum mainnet</option></select><label>Amount (TRX 1 to 10,000; ETH 0.0001 to 1)</label><input required name="amount" placeholder="10"><label>Agreed service reference</label><input required name="reference" maxlength="80" placeholder="Consulting project"><button>Create 30-minute payment invoice</button></form><p>Never send funds before receiving an active invoice. Cryptocurrency transfers are irreversible.</p>');
}catch(Throwable $x){error_log('MOJPLAYWIN_CRYPTO_INTERNAL '.get_class($x));display('Payment temporarily unavailable','<p>Verification is temporarily unavailable. Do not send funds without a valid invoice.</p>',503);}
