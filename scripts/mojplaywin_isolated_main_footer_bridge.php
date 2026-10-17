<?php
/** MojPlayWin exact-main-public-page footer PROTOTYPE, direct isolated URL only.
 * NO route rewrites. Does not replace store, checkout, orders or payment.
 * Original dynamic HTML and headers pass through unchanged except a gold
 * 1-line founder plaque and scoped CSS in the existing <footer>.
 */
declare(strict_types=1);
ini_set('display_errors','0');
ini_set('log_errors','1');
$routes=[
 "agriculture"=>"/agriculture/","industry"=>"/industry/",
 "research"=>"/research/","knowledge"=>"/knowledge/","economy"=>"/economy/",
 "studio"=>"/studio/","market"=>"/market/","agents"=>"/agents/","company"=>"/company/",
 "venture_agriculture"=>"/ventures/agriculture/",
 "venture_cafe"=>"/ventures/cafe-restaurant/",
 "venture_fuel"=>"/ventures/fuel-station/",
 "venture_jewelry"=>"/ventures/jewelry-gold/",
 "venture_carpets"=>"/ventures/carpets/",
 "venture_crypto"=>"/ventures/currency-crypto/",
 "venture_ecommerce"=>"/ventures/ecommerce/",
 "venture_hospitality"=>"/ventures/hospitality/"
];
$key=$_GET['__mpw_footer_section']??null;
$host=strtolower((string)($_SERVER['HTTP_HOST']??''));
if (!is_string($key) || !isset($routes[$key]) || !in_array($host,['mojplaywin.com','www.mojplaywin.com'],true)){
 http_response_code(404);exit;
}
if (($_SERVER['REQUEST_METHOD']??'')!=='GET'){
 header('Allow: GET');http_response_code(405);exit;
}
$path=$routes[$key];
$params=$_GET;
unset($params['__mpw_footer_section'],$params['__mpw_footer_passthru']);
foreach(array_keys($params) as $param){
 if(!is_string($param)||strlen($param)>90||!preg_match('/^[a-zA-Z0-9_\.\[\]-]+$/',$param))unset($params[$param]);
}
$params['__mpw_footer_passthru']='1';
$url='https://mojplaywin.com'.$path.'?'.http_build_query($params,'','&',PHP_QUERY_RFC3986);
$curl=curl_init($url);
if($curl===false){http_response_code(503);exit;}
$headers=['Accept: text/html','Accept-Encoding: identity','Cache-Control: no-cache'];
$cookie=$_SERVER['HTTP_COOKIE']??'';
if(is_string($cookie)&&strlen($cookie)<=8192&&$cookie!==''&&!preg_match('/[\r\n]/',$cookie))
 $headers[]='Cookie: '.$cookie;
$language=$_SERVER['HTTP_ACCEPT_LANGUAGE']??'';
if(is_string($language)&&strlen($language)<250&&!preg_match('/[\r\n]/',$language)&&$language!=='')
 $headers[]='Accept-Language: '.$language;
curl_setopt_array($curl,[
 CURLOPT_RETURNTRANSFER=>true,CURLOPT_HEADER=>true,
 CURLOPT_FOLLOWLOCATION=>false,CURLOPT_CONNECTTIMEOUT=>4,CURLOPT_TIMEOUT=>15,
 CURLOPT_SSL_VERIFYPEER=>true,CURLOPT_SSL_VERIFYHOST=>2,
 CURLOPT_PROTOCOLS=>CURLPROTO_HTTPS,CURLOPT_ENCODING=>'identity',
 CURLOPT_HTTPHEADER=>$headers,
 CURLOPT_USERAGENT=>'MojPlayWin-isolated-founder-footer-readonly/1.0',
]);
$response=curl_exec($curl);
$err=curl_errno($curl);
$status=(int)curl_getinfo($curl,CURLINFO_HTTP_CODE);
$mime=(string)curl_getinfo($curl,CURLINFO_CONTENT_TYPE);
$sz=(int)curl_getinfo($curl,CURLINFO_HEADER_SIZE);
curl_close($curl);
if(!is_string($response)||$err!==0||$status!==200||$sz<=0||stripos($mime,'text/html')!==0){
 http_response_code(503);header('Content-Type: text/plain; charset=utf-8');exit('Source unavailable');
}
$head=substr($response,0,$sz);
$body=substr($response,$sz);
$mw_count=preg_match_all('/<footer\b[^>]*class="mw-site-footer"[^>]*>/i',$body);
$legacy_count=preg_match_all('/<footer\b[^>]*class="mpw-footer"[^>]*>/i',$body);
if(strlen($body)<500||strlen($body)>1250000||
 $mw_count+$legacy_count!==1||
 preg_match_all('/<\/head\s*>/i',$body)!==1||
 strpos($body,'data-mpw-main-founder-edge')!==false||
 strpos($body,'Mojtaba Roozegar')!==false) {
 http_response_code(503);header('Content-Type: text/plain; charset=utf-8');exit('Unsupported original markup');
}
$target_class=($mw_count===1)?'mw-site-footer':'mpw-footer';
$style='<style id="mpw-main-footer-edge-css">'
.'.mpw-main-founder-edge{display:flex;justify-content:center;align-items:center;'
.'max-width:440px;margin:25px auto 12px;padding:17px 24px;text-align:center;'
.'border:2px solid #d6ad55;border-radius:16px;'
.'background:linear-gradient(135deg,#0c0b09,#272012 50%,#0d0c0a);'
.'box-shadow:0 12px 30px #0009,inset 0 0 18px #d6ad5540;}'
.'.mpw-main-founder-edge strong{color:#f4d68a;font:700 1.3rem/1.3 Georgia,serif;'
.'letter-spacing:.065em;text-shadow:0 1px 0 #6e511d,0 2px 0 #4b370f,0 3px 10px #c8a14570;}'
.'</style>';
$plaque='<div class="mpw-main-founder-edge" data-mpw-main-founder-edge="true"'
.' aria-label="Founder: Mojtaba Roozegar"><strong>Mojtaba Roozegar</strong></div>';
$body=preg_replace('/<\/head\s*>/i',$style.'</head>',$body,1,$countHead);
$rx='/(<footer\b[^>]*class="'.preg_quote($target_class,'/').'"[^>]*>.*?)<\/footer\s*>/is';
$body=preg_replace($rx,'$1'.$plaque.'</footer>',$body,1,$countFooter);
if(!is_string($body)||$countHead!==1||$countFooter!==1){
 http_response_code(503);exit;
}
// Forward only security and cookie-refresh headers from the same-site source.
foreach(preg_split('/\r?\n/',$head) as $line){
 if(!is_string($line)||strpos($line,':')===false||preg_match('/[\r\n]/',$line))continue;
 $name=strtolower(trim(explode(':',$line,2)[0]));
 if(in_array($name,['set-cookie','content-security-policy','x-frame-options',
  'referrer-policy','permissions-policy','strict-transport-security'],true)){
   header($line,$name!=='set-cookie');
 }
}
header('Content-Type: text/html; charset=utf-8');
header('X-MPW-Footer-Edge: main-only-stage');
header('Cache-Control: private,no-store,max-age=0');
header('Vary: Cookie');
echo $body;
