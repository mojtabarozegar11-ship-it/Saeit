<?php
/** MojPlayWin-only mainnet RPC reachability probe. No site reads/writes,
 * wallet secret access, transaction broadcast, balance reads, or transfers.
 */
declare(strict_types=1);
function probe(string $url, string $body, string $chain): array {
    $t = microtime(true);
    $c = curl_init($url);
    curl_setopt_array($c, [
        CURLOPT_POST=>true, CURLOPT_POSTFIELDS=>$body,
        CURLOPT_HTTPHEADER=>['Content-Type: application/json'],
        CURLOPT_RETURNTRANSFER=>true, CURLOPT_TIMEOUT=>9, CURLOPT_CONNECTTIMEOUT=>5,
        CURLOPT_SSL_VERIFYPEER=>true, CURLOPT_SSL_VERIFYHOST=>2,
        CURLOPT_FOLLOWLOCATION=>false, CURLOPT_MAXREDIRS=>0,
        CURLOPT_MAXFILESIZE=>1048576,
    ]);
    $res = curl_exec($c);
    $code = (int)curl_getinfo($c,CURLINFO_HTTP_CODE);
    $curlCode = curl_errno($c);
    curl_close($c);
    $json = is_string($res) && strlen($res)<1048576 ? json_decode($res,true) : null;
    $ok = false;
    if ($chain==='eth') {
        $ok = $code===200 && is_array($json) && ($json['result'] ?? null)==='0x1';
    } elseif ($chain==='tron') {
        $ok = $code===200 && is_array($json)
            && is_numeric($json['block_header']['raw_data']['number'] ?? null);
    }
    return [
        'target'=>parse_url($url, PHP_URL_HOST), 'mainnet'=>$chain,
        'http_code'=>$code, 'network_response_valid'=>$ok,
        'curl_errno'=>$curlCode, 'elapsed_s'=>round(microtime(true)-$t,2),
    ];
}
$r = [];
$r[] = probe('https://ethereum-rpc.publicnode.com',
  json_encode(['jsonrpc'=>'2.0','id'=>1,'method'=>'eth_chainId','params'=>[]]),'eth');
$r[] = probe('https://eth.llamarpc.com',
  json_encode(['jsonrpc'=>'2.0','id'=>1,'method'=>'eth_chainId','params'=>[]]),'eth');
$r[] = probe('https://api.trongrid.io/walletsolidity/getnowblock', '{}','tron');
$r[] = probe('https://api.trongrid.io/wallet/getnowblock', '{}','tron');
echo json_encode(['classification'=>'MOJPLAYWIN_CRYPTO_RPC_REACHABILITY_ONLY','endpoints'=>$r,'payment_received'=>false,
 'checkout_activated'=>false,'production_writes'=>false],JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR),PHP_EOL;
