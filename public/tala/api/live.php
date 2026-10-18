<?php
declare(strict_types=1);
// Public read-only source-attributed international rates; no sessions, no live DB writes.
ini_set('display_errors','0');
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, max-age=0');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
function output_live(array $data):void{
    echo json_encode($data,JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);
    exit;
}
if(($_SERVER['REQUEST_METHOD']??'GET')!=='GET'){
    header('Allow: GET');
    http_response_code(405);
    output_live(['ok'=>false,'scope'=>'tala','error'=>'GET only']);
}
$path=__DIR__.'/../../../.tala-secure/tala-live-market.json';
$fallback=['ok'=>true,'scope'=>'tala','market'=>'international_reference','mode'=>'unavailable',
           'generated_at'=>null,'quotes'=>new stdClass(),'stale'=>true,
           'notice'=>'منبع داده هنوز دریافت نشده؛ نرخ ساختگی نمایش داده نمی‌شود.'];
if(is_link($path)||!is_file($path)||!is_readable($path))output_live($fallback);
if(filesize($path)>120000||filesize($path)<30)output_live($fallback);
$raw=@file_get_contents($path,false,null,0,120001);
if(!is_string($raw)||strlen($raw)>120000)output_live($fallback);
$body=json_decode($raw,true);
if(!is_array($body)||($body['scope']??'')!=='tala'||($body['schema']??0)!==1||
   ($body['market']??'')!=='international_reference'||!is_array($body['quotes']??null)){
    output_live($fallback);
}
$generated=strtotime((string)($body['generated_at']??''));
$age=$generated===false?PHP_INT_MAX:time()-$generated;
if($age< -300||$age>2592000)output_live($fallback);
$approved=['xau','xag','xpt','xpd','btc','eth','usdt','trx','bnb','sol',
           'usd_usd','usd_eur','usd_gbp','usd_aed','usd_try','usd_cad','usd_irr'];
$quotes=[];
foreach($body['quotes'] as $symbol=>$row){
    if(!in_array($symbol,$approved,true)||!is_array($row))continue;
    $value=$row['price']??null;
    $unit=(string)($row['unit']??'');
    $currency=(string)($row['currency']??'');
    $source=(string)($row['source']??'');
    $stamp=(string)($row['observed_at']??'');
    $providerTime=strtotime($stamp);
    if(!is_numeric($value)||!is_finite((float)$value)||(float)$value<=0||
       !in_array($unit,['gram','coin','per_usd'],true)||
       !in_array($source,['Gold API','CoinGecko','ExchangeRate-API reference'],true)||
       !preg_match('/^[A-Z]{3}$/D',$currency)||
       $providerTime===false)continue;
    // 30 minutes metals/crypto; 48h FX references (daily data includes weekends).
    $maxAge=$unit==='per_usd'?172800:1800;
    $quotes[$symbol]=[
        'price'=>(float)$value,'currency'=>$currency,'unit'=>$unit,
        'source'=>$source,'source_url'=>(string)($row['source_url']??''),
        'observed_at'=>$stamp,
        'stale'=>time()-$providerTime>$maxAge || $age>1800,
        'group'=>(string)($row['group']??'')
    ];
}
output_live([
    'ok'=>true,'scope'=>'tala','market'=>'international_reference',
    'mode'=>'provider_snapshot','generated_at'=>$body['generated_at'],
    'quotes'=>$quotes,'stale'=>$age>1800,
    'partial'=>(bool)($body['partial']??false),
    'notice'=>'ارزش‌های بین‌المللی و نرخ‌های مرجع هستند، نه قیمت معامله بازار آزاد ایران.'
]);
