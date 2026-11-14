<?php
declare(strict_types=1);
/** Read-only commercial lead desk: never sends mail, creates orders or modifies inquiries. */
if (PHP_SAPI !== 'cli') { http_response_code(403); exit(2); }
umask(0077);
function abort_private(string $reason): never { fwrite(STDERR, 'MPW_LEAD_DESK_ABORT: '.$reason."\n"); exit(2); }
function secured(string $path, bool $dir=false): bool {
    if (is_link($path) || ($dir ? !is_dir($path) : !is_file($path))) return false;
    $mode=@fileperms($path);
    return $mode!==false && (($mode & 0077)===0);
}
function fixture_root(): ?string {
    if (getenv('MPW_INQUIRY_TEST_MODE')!=='1') return null;
    $root=getenv('MPW_INQUIRY_TEST_ROOT');
    if (!is_string($root) || $root==='') abort_private('FIXTURE_ROOT_REQUIRED');
    $resolved=realpath($root);
    $tmp=realpath(sys_get_temp_dir());
    if ($resolved===false || $tmp===false || !str_starts_with($resolved,$tmp.DIRECTORY_SEPARATOR)
        || !secured($resolved,true) || !secured($resolved.'/.mpw-fixture')) abort_private('INVALID_TEST_FIXTURE');
    return $resolved;
}
function lead_record(string $path,string $key): ?array {
    if (!secured($path)) return null;
    $len=@filesize($path);
    if ($len===false || $len<64 || $len>12000) return null;
    $raw=@file_get_contents($path);
    if ($raw===false || strlen($raw)>12000) return null;
    try { $envelope=json_decode($raw,true,16,JSON_THROW_ON_ERROR); } catch (Throwable $e) { return null; }
    if (!is_array($envelope)||($envelope['v']??null)!==1) return null;
    foreach (['iv','tag','cipher'] as $name) if (!isset($envelope[$name])||!is_string($envelope[$name])) return null;
    $iv=base64_decode($envelope['iv'],true);
    $tag=base64_decode($envelope['tag'],true);
    $cipher=base64_decode($envelope['cipher'],true);
    if ($iv===false||$tag===false||$cipher===false||strlen($iv)!==12||strlen($tag)!==16||strlen($cipher)>9000) return null;
    $plaintext=openssl_decrypt($cipher,'aes-256-gcm',$key,OPENSSL_RAW_DATA,$iv,$tag);
    if ($plaintext===false) return null;
    try { $record=json_decode($plaintext,true,16,JSON_THROW_ON_ERROR); } catch (Throwable $e) { return null; }
    if (!is_array($record)||($record['source']??'')!=='first_party_mpw_revenue'||($record['consent']??false)!==true) return null;
    return $record;
}
function eligible_service($slug): bool {
    static $allowed=['general','website-doctor','landing-page-studio','ai-automation','business-spreadsheets',
        'website-templates','social-media-kits','resume-builder','logo-studio','browser-games',
        'marketing-ai','business-calculators','website-care'];
    return is_string($slug) && in_array($slug,$allowed,true);
}
function main_cli(array $args): void {
    if (!extension_loaded('openssl')) abort_private('OPENSSL_UNAVAILABLE');
    if (!in_array(($args[1]??''),['summary','inspect'],true)) abort_private('USAGE_SUMMARY_OR_INSPECT');
    if (($args[1]??'')==='summary' && count($args)!==2) abort_private('EXTRA_ARGUMENTS');
    if (($args[1]??'')==='inspect' && (count($args)!==3 || !preg_match('/^[A-F0-9]{18}$/D',$args[2]))) abort_private('INVALID_REFERENCE');
    $root=fixture_root();
    if ($root===null) {
        if (getenv('GITHUB_ACTIONS')==='true' || !function_exists('posix_getpwuid') || !function_exists('posix_geteuid')) abort_private('UNSAFE_RUNTIME');
        $account=posix_getpwuid(posix_geteuid());
        if (!is_array($account) || ($account['name']??'')!=='zomorod2') abort_private('WRONG_OS_USER');
        $root='/home/zomorod2/.private_mojplaywin_main_agents/revenue-inquiries';
    }
    if (!secured($root,true)) abort_private('PRIVATE_DIRECTORY_UNSAFE');
    $keyfile=$root.'/.inquiry-key';
    if (!secured($keyfile) || @filesize($keyfile)!==32) abort_private('PRIVATE_KEY_UNSAFE');
    $key=@file_get_contents($keyfile);
    if ($key===false || strlen($key)!==32) abort_private('KEY_INVALID');
    $names=@scandir($root);
    if (!is_array($names)) abort_private('DIRECTORY_UNREADABLE');
    $files=array_values(array_filter($names,static fn($n)=>is_string($n)&&preg_match('/^[0-9]{8}-[A-F0-9]{18}\.json$/D',$n)));
    sort($files,SORT_STRING);
    $report=['version'=>1,'read_only'=>true,'emails_sent'=>0,'orders_created'=>0,'payments_created'=>0,
        'scanned'=>0,'valid'=>0,'invalid'=>0,'notified_to_local_mta'=>0,'not_yet_notified'=>0,
        'older_than_24h'=>0,'older_than_72h'=>0,'by_service'=>[], 'backlog_truncated'=>count($files)>500];
    if (($args[1]??'')==='inspect') {
        $reference=$args[2];$matches=array_values(array_filter($files,static fn($n)=>str_ends_with($n,'-'.$reference.'.json')));
        if (count($matches)!==1) abort_private('REFERENCE_NOT_FOUND');
        $files=$matches;
    } else $files=array_slice($files,0,500);
    foreach ($files as $name) {
        $report['scanned']++;
        $path=$root.'/'.$name;
        $lead=lead_record($path,$key);
        if ($lead===null || !eligible_service($lead['service']??null) || !filter_var($lead['email']??null,FILTER_VALIDATE_EMAIL)) {
            $report['invalid']++; continue;
        }
        $report['valid']++;
        $service=$lead['service'];
        $report['by_service'][$service]=($report['by_service'][$service]??0)+1;
        $ref=substr($name,9,18);
        $marker=$root.'/.owner-dispatched-'.hash('sha256',$name).'.json';
        $notified=secured($marker) && @filesize($marker)>0;
        $report[$notified?'notified_to_local_mta':'not_yet_notified']++;
        $ts=strtotime((string)($lead['created_at']??''));
        if ($ts!==false && $ts<=time() && $ts>=0) {
            $age=time()-$ts;
            if ($age>=86400)$report['older_than_24h']++;
            if ($age>=259200)$report['older_than_72h']++;
        }
        if (($args[1]??'')==='inspect') {
            // Deliberately omit contact details and project free text in machine output.
            $report['record']=['reference'=>$ref,'service'=>$service,'created_at'=>(string)($lead['created_at']??''),
                'notified_to_local_mta'=>$notified,'has_contact_email'=>true,
                'has_project_details'=>is_string($lead['details']??null) && trim($lead['details'])!=='',
                'quote_sent'=>'unknown','payment_received'=>'unverified'];
        }
    }
    ksort($report['by_service']);
    echo 'MPW_LEAD_DESK_READONLY='.json_encode($report,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR|JSON_INVALID_UTF8_SUBSTITUTE)."\n";
}
main_cli($argv);
