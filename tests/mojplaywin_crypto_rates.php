<?php
/** Deterministic, no-network USD pricing regression tests. */
declare(strict_types=1);
define('MOJPLAYWIN_CRYPTO_INTERNAL',true);
require __DIR__.'/../isolated_crypto_gateway/merchant_rates.php';
function ensure(bool $value,string $message):void{
 if(!$value) throw new RuntimeException('FAILED: '.$message);
}
function denied(callable $run,string $why):void{
 try{$run();throw new RuntimeException('FAILED: expected '.$why);}
 catch(RuntimeException $e){
   if(str_starts_with($e->getMessage(),'FAILED:')) throw $e;
 }
}
$now=time();
$fixture=function(string $url)use($now):array{
 if(str_contains($url,'coingecko')) return [
    'ethereum'=>['usd'=>2378.10,'last_updated_at'=>$now-20],
    'tron'=>['usd'=>0.3316,'last_updated_at'=>$now-20],
 ];
 if(str_contains($url,'eth-ethereum'))return [
    'quotes'=>['USD'=>['price'=>2379.19]],'last_updated'=>gmdate('c',$now-90)
 ];
 if(str_contains($url,'trx-tron'))return [
    'quotes'=>['USD'=>['price'=>0.3317]],'last_updated'=>gmdate('c',$now-90)
 ];
 throw new RuntimeException('Unexpected endpoint');
};
$eth=mjwfx_atomic_quote('ETH',750,$fixture,$now);
$trx=mjwfx_atomic_quote('TRX',750,$fixture,$now);
ensure($eth>1000000000000000 && $eth<10000000000000000,'ETH $7.50 quote');
ensure($trx>20000000 && $trx<30000000,'TRX $7.50 quote');
ensure(abs(mjwfx_price_usd('ETH',$fixture,$now)-2378.645)<0.0001,'ETH rate average');
ensure(abs(mjwfx_price_usd('TRX',$fixture,$now)-0.33165)<0.000001,'TRX rate average');
denied(fn()=>mjwfx_atomic_quote('BTC',750,$fixture,$now),'unsupported asset');
denied(fn()=>mjwfx_atomic_quote('TRX',0,$fixture,$now),'zero USD price');
denied(fn()=>mjwfx_price_usd('TRX',function($url)use($fixture,$now){
    $r=$fixture($url);
    if(str_contains($url,'coingecko'))$r['tron']['last_updated_at']=$now-3000;
    return $r;
},$now),'stale rate');
denied(fn()=>mjwfx_price_usd('ETH',function($url)use($fixture){
    $r=$fixture($url);
    if(str_contains($url,'eth-ethereum'))$r['quotes']['USD']['price']=3210.0;
    return $r;
},$now),'rate disagreement');
denied(fn()=>mjwfx_price_usd('TRX',function($url)use($fixture){
    $r=$fixture($url);
    if(str_contains($url,'trx-tron'))unset($r['last_updated']);
    return $r;
},$now),'no timestamp');
denied(fn()=>mjwfx_price_usd('ETH',function($url)use($fixture){
    $r=$fixture($url);
    if(str_contains($url,'coingecko'))$r['ethereum']['usd']=-200;
    return $r;
},$now),'negative price');
echo "DOUBLE_PRICE_PROVIDER_UNIT_TESTS=passed\n";
echo "WRONG_ASSET_STALE_DISAGREEMENT_MISSING_RATE_FAIL_CLOSED=true\n";
echo "FIXED_STORE_PRICE_USD_CENTS=750\n";
echo "CUSTOMER_FUNDS_SENT=false\n";
