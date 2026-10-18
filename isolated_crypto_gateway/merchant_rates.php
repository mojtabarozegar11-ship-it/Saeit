<?php
/**
 * MojPlayWin fixed-USD product price conversion, NOT a general money gateway.
 *
 * Internal library only. This file never performs a transfer and never exposes
 * a quote if either independent price feed fails freshness or divergence checks.
 */
declare(strict_types=1);
if (!defined('MOJPLAYWIN_CRYPTO_INTERNAL')) {
    http_response_code(404);
    exit;
}

function mjwfx_http_json(string $url): array {
    $allow = [
        'https://api.coingecko.com/api/v3/simple/price?ids=ethereum%2Ctron&vs_currencies=usd&include_last_updated_at=true',
        'https://api.coinpaprika.com/v1/tickers/eth-ethereum?quotes=USD',
        'https://api.coinpaprika.com/v1/tickers/trx-tron?quotes=USD',
    ];
    if (!in_array($url, $allow, true)) throw new RuntimeException('Unapproved quotation endpoint');
    $ch=curl_init($url);
    curl_setopt_array($ch,[
        CURLOPT_RETURNTRANSFER=>true,
        CURLOPT_HTTPHEADER=>['Accept: application/json','Cache-Control: no-cache'],
        CURLOPT_USERAGENT=>'MojPlayWin-Checkout/1',
        CURLOPT_CONNECTTIMEOUT=>4, CURLOPT_TIMEOUT=>8,
        CURLOPT_SSL_VERIFYPEER=>true, CURLOPT_SSL_VERIFYHOST=>2,
        CURLOPT_FOLLOWLOCATION=>false
    ]);
    $body=curl_exec($ch);
    $code=(int)curl_getinfo($ch,CURLINFO_HTTP_CODE);
    $errno=curl_errno($ch);
    curl_close($ch);
    if ($errno!==0||$code!==200||!is_string($body)||strlen($body)>250000)
        throw new RuntimeException('Quote service unavailable');
    $obj=json_decode($body,true,32,JSON_THROW_ON_ERROR);
    if (!is_array($obj)) throw new RuntimeException('Quote response invalid');
    return $obj;
}

function mjwfx_price_usd(string $coin, ?callable $transport=null, ?int $now=null): float {
    if (!in_array($coin,['ETH','TRX'],true)) throw new InvalidArgumentException('Native asset only');
    $transport ??= 'mjwfx_http_json';
    $now ??= time();
    $asset=$coin==='ETH'?'ethereum':'tron';
    $paprika=$coin==='ETH'?'eth-ethereum':'trx-tron';
    $gecko=$transport('https://api.coingecko.com/api/v3/simple/price?ids=ethereum%2Ctron&vs_currencies=usd&include_last_updated_at=true');
    $pap=$transport('https://api.coinpaprika.com/v1/tickers/'.$paprika.'?quotes=USD');
    if (!is_array($gecko)||!is_array($pap)) throw new RuntimeException('Provider result missing');
    $g=$gecko[$asset]['usd']??null;
    $p=$pap['quotes']['USD']['price']??null;
    $g_updated=$gecko[$asset]['last_updated_at']??null;
    $p_updated=$pap['last_updated']??null;
    $p_time=is_string($p_updated)?strtotime($p_updated):false;
    if (!is_numeric($g)||!is_numeric($p)||!is_numeric($g_updated)||$p_time===false)
        throw new RuntimeException('Incomplete quote or freshness data');
    $x=(float)$g; $y=(float)$p;
    if (!is_finite($x)||!is_finite($y)||$x<=0||$y<=0)
        throw new RuntimeException('Invalid spot rate');
    if ($coin==='ETH'&&($x<50||$y<50)) throw new RuntimeException('ETH rate outside sanity bounds');
    if ($coin==='TRX'&&($x<0.001||$y<0.001)) throw new RuntimeException('TRX rate outside sanity bounds');
    if (abs($now-(int)$g_updated)>900 || abs($now-(int)$p_time)>900)
        throw new RuntimeException('Spot rate is stale or future-dated');
    if (abs($x-$y)/min($x,$y)>0.03)
        throw new RuntimeException('Independent spot prices disagree');
    return ($x+$y)/2;
}

function mjwfx_atomic_quote(string $coin,int $usdCents,?callable $transport=null,?int $now=null): int {
    if ($usdCents<=0||$usdCents>10000000) throw new InvalidArgumentException('Invalid USD price in cents');
    $usd=mjwfx_price_usd($coin,$transport,$now);
    $atomic=$coin==='ETH'?1e18:1e6;
    $units=(($usdCents/100.0)/$usd)*$atomic;
    if (!is_finite($units)||$units<=10000||$units>PHP_INT_MAX-10000)
        throw new RuntimeException('Unquotable product amount');
    return (int)round($units);
}
