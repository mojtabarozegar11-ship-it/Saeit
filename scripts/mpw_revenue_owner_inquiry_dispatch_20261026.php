<?php
declare(strict_types=1);
/* MojPlayWin privately stored customer inquiry -> owner notification, no payloads in CI logs. */
if (PHP_SAPI!=='cli' || ($argv[1]??'')!=='dispatch') {fwrite(STDERR,"CLI dispatch only\n");exit(2);}
umask(0077);
$root='/home/zomorod2/.private_mojplaywin_main_agents/revenue-inquiries';
$owner='mojtaba.rozegar11@gmail.com';
function refuse(string $msg):void {throw new RuntimeException($msg);}
function private_file(string $path):bool {return is_file($path) && !is_link($path);}
function safe(string $value,int $max=2200):string {
 $value=trim(preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/u','',$value)??'');
 return mb_substr($value,0,$max,'UTF-8');
}
function decode_record(string $path,string $key):?array {
 $raw=@file_get_contents($path);
 if ($raw===false || strlen($raw)>12000)return null;
 $obj=json_decode($raw,true);
 if (!is_array($obj)||($obj['v']??null)!==1)return null;
 foreach(['iv','tag','cipher'] as $name)if (!isset($obj[$name])||!is_string($obj[$name]))return null;
 $iv=base64_decode($obj['iv'],true);$tag=base64_decode($obj['tag'],true);$cipher=base64_decode($obj['cipher'],true);
 if ($iv===false||$tag===false||$cipher===false||strlen($iv)!==12||strlen($tag)!==16)return null;
 $plain=openssl_decrypt($cipher,'aes-256-gcm',$key,OPENSSL_RAW_DATA,$iv,$tag);
 if ($plain===false)return null;
 $lead=json_decode($plain,true);
 if (!is_array($lead)||($lead['source']??'')!=='first_party_mpw_revenue'||($lead['consent']??false)!==true)return null;
 return $lead;
}
$stats=['scanned'=>0,'already_queued'=>0,'queued_to_local_mta'=>0,'failed_queue'=>0,'invalid_private_record'=>0,'not_decrypted'=>0];
try {
 if (!is_dir($root)||is_link($root))refuse('Private inquiry directory missing');
 if (!extension_loaded('openssl')||!extension_loaded('mbstring'))refuse('PHP crypto prerequisites missing');
 $keyfile=$root.'/.inquiry-key';
 if (!private_file($keyfile))refuse('Private encryption key missing');
 $key=@file_get_contents($keyfile);
 if ($key===false||strlen($key)!==32)refuse('Invalid key length');
 if (is_link($root.'/.owner-dispatch.lock'))refuse('Unsafe dispatch lock');
 $fh=@fopen($root.'/.owner-dispatch.lock','c+');
 if (!$fh||!flock($fh,LOCK_EX|LOCK_NB))refuse('Dispatch already active');
 @chmod($root.'/.owner-dispatch.lock',0600);
 $all=scandir($root);
 if ($all===false)refuse('Private record listing failed');
 sort($all,SORT_STRING);
 $allow=['general','website-doctor','landing-page-studio','ai-automation','business-spreadsheets','website-templates','social-media-kits','resume-builder','logo-studio','browser-games','marketing-ai','business-calculators','website-care'];
 foreach ($all as $file) {
  if (!preg_match('/^[0-9]{8}-[A-F0-9]{18}\.json$/',$file))continue;
  if ($stats['scanned']>=25)break;
  $stats['scanned']++;
  $path=$root.'/'.$file;
  if (!private_file($path)){$stats['invalid_private_record']++;continue;}
  $marker=$root.'/.owner-dispatched-'.hash('sha256',$file).'.json';
  if (file_exists($marker)){$stats['already_queued']++;continue;}
  $lead=decode_record($path,$key);
  if (!$lead){$stats['not_decrypted']++;continue;}
  $slug=(string)($lead['service']??'');
  $email=(string)($lead['email']??'');
  if (!in_array($slug,$allow,true)||!filter_var($email,FILTER_VALIDATE_EMAIL)){$stats['invalid_private_record']++;continue;}
  $reference=substr($file,9,18);
  $subject='MojPlayWin owner inquiry '.$slug.' '.$reference;
  $body="MojPlayWin first-party inquiry | Owner notification\n".
        "Reference: ".$reference."\nService: ".$slug."\n".
        "Received UTC: ".safe((string)($lead['created_at']??''),80)."\n".
        "Name: ".safe((string)($lead['name']??''),120)."\n".
        "Contact email: ".safe($email,254)."\n".
        "Company: ".safe((string)($lead['company']??''),120)."\n".
        "Website: ".safe((string)($lead['website']??''),300)."\n".
        "Timeframe: ".safe((string)($lead['timeline']??''),120)."\n".
        "Project details:\n".safe((string)($lead['details']??''),2000)."\n\n".
        "This is an inquiry only; no quote, contract or payment is accepted.\n".
        "The encrypted original remains in private cPanel storage.\n";
  $headers="From: MojPlayWin Support <support@mojplaywin.com>\r\n".
           "MIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\n";
  if (!@mail($owner,$subject,$body,$headers)){$stats['failed_queue']++;continue;}
  $markerPayload=json_encode(['queued_at'=>gmdate('c'),'reference_hash'=>hash('sha256',$reference),'owner_channel'=>'gmail-local-mta'],JSON_THROW_ON_ERROR);
  $tmp=$root.'/.dispatch-new-'.hash('sha256',$file);
  $mf=@fopen($tmp,'x');
  if (!$mf)refuse('Marker reservation failed');
  @chmod($tmp,0600);
  fwrite($mf,$markerPayload);fflush($mf);fclose($mf);
  if (!rename($tmp,$marker))refuse('Marker commit failed');
  $stats['queued_to_local_mta']++;
 }
 flock($fh,LOCK_UN);fclose($fh);
 echo 'MPW_OWNER_INQUIRY_DISPATCH='.json_encode($stats,JSON_THROW_ON_ERROR)."\n";
} catch(Throwable $error) {
 error_log('MPW_OWNER_INQUIRY_DISPATCH_FAILED');
 fwrite(STDERR,"MPW_OWNER_DISPATCH_FAILED_SAFE\n");
 exit(2);
}
