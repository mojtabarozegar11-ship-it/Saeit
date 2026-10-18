<?php
/** Read-only FX provider reachability test (no account, no payment data).
 * Prints only limited status and well-formed spot rates from whitelisted hosts.
 */
declare(strict_types=1);
function get_fx(string $url,string $provider): array {
 $ch=curl_init($url);
 curl_setopt_array($ch,[
    CURLOPT_RETURNTRANSFER=>true,CURLOPT_HTTPHEADER=>['Accept: application/json'],
    CURLOPT_CONNECTTIMEOUT=>4,CURLOPT_TIMEOUT=>9,CURLOPT_SSL_VERIFYPEER=>true,
    CURLOPT_SSL_VERIFYHOST=>2,CURLOPT_FOLLOWLOCATION=>false,
    CURLOPT_USERAGENT=>'MojPlayWin-Gateway-Readiness/1.0'
 ]);
 $result=curl_exec($ch);
 $status=(int)curl_getinfo($ch,CURLINFO_HTTP_CODE);$errno=curl_errno($ch);
 curl_close($ch);
 $j=($errno===0&&is_string($result)&&strlen($result)<250000)?json_decode($result,true):null;
 $eth=null;$trx=null;
 if($provider==='coingecko'&&is_array($j)) {
    $eth=$j['ethereum']['usd']??null;$trx=$j['tron']['usd']??null;
 } elseif($provider==='coinbase-eth'&&is_array($j)) {
    $eth=$j['data']['amount']??null;
 } elseif($provider==='coinbase-trx'&&is_array($j)) {
    $trx=$j['data']['amount']??null;
 } elseif($provider==='cryptocompare'&&is_array($j)) {
    $eth=$j['ETH']['USD']??null;$trx=$j['TRX']['USD']??null;
 } elseif($provider==='kraken-eth'&&is_array($j)) {
    foreach(($j['result']??[]) as $ticker) { $eth=$ticker['c'][0]??null; break; }
 } elseif($provider==='kraken-trx'&&is_array($j)) {
    foreach(($j['result']??[]) as $ticker) { $trx=$ticker['c'][0]??null; break; }
 }
 $valid=fn($v)=>is_numeric($v)&&(float)$v>0&&is_finite((float)$v);
 return ['provider'=>$provider,'http'=>$status,'connection_error'=>$errno!==0,
   'valid_eth_usd'=>$valid($eth),'valid_trx_usd'=>$valid($trx),
   'eth_usd'=>$valid($eth)?round((float)$eth,4):null,
   'trx_usd'=>$valid($trx)?round((float)$trx,7):null];
}
$result=[
    get_fx('https://api.coingecko.com/api/v3/simple/price?ids=ethereum%2Ctron&vs_currencies=usd','coingecko'),
    get_fx('https://api.coinbase.com/v2/prices/ETH-USD/spot','coinbase-eth'),
    get_fx('https://api.coinbase.com/v2/prices/TRX-USD/spot','coinbase-trx'),
    get_fx('https://min-api.cryptocompare.com/data/pricemulti?fsyms=ETH%2CTRX&tsyms=USD','cryptocompare'),
    get_fx('https://api.kraken.com/0/public/Ticker?pair=ETHUSD','kraken-eth'),
    get_fx('https://api.kraken.com/0/public/Ticker?pair=TRXUSD','kraken-trx'),
];
echo json_encode(['classification'=>'MOJPLAYWIN_CRYPTO_FX_READONLY','sources'=>$result,'transactions_created'=>false,'payments_enabled_by_probe'=>false],JSON_THROW_ON_ERROR),PHP_EOL;
