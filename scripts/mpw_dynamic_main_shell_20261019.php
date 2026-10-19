<?php
declare(strict_types=1);
/**
 * Site-only GET response renderer. Does not replace Django, forms, orders, or child sites.
 * Existing MojPlayWin same-origin canonical bridge is the proven deployment pattern.
 * The only public routing changes are 19 exact-root GET paths, with passthrough escape.
 */
ini_set('display_errors', '0');
ini_set('log_errors', '1');
$allowed = [
    'store' => '/store/',
    'games' => '/games/',
    'ai' => '/ai/',
    'contact' => '/contact/',
    'support' => '/support/',
    'privacy' => '/privacy/',
    'terms' => '/terms/',
    'cookies' => '/cookies/',
    'products' => '/products/',
    'blockchain' => '/blockchain/',
    'commerce' => '/commerce/',
    'crypto-payments' => '/crypto-payments/',
    'global-business' => '/global-business/',
    'research-lab' => '/research-lab/',
    'canada-vision' => '/canada-vision/',
    'agro-industry' => '/agro-industry/',
    'agriculture' => '/agriculture/',
    'education' => '/education/',
    'weather' => '/weather/',
];
const MPW_BRAND_ICON = '/design-preview-20261017/static/site/mojplaywin-atelier/official-coin-80.3ea52711f49d.webp';
const MPW_HTML_MAX = 2000000;
const MPW_STYLE = <<<'STYLE'
<style id="mpw-dynamic-unified-shell-20261019">
body.mpw-dynamic-main{color:#f4eedc;background:radial-gradient(ellipse at 95% 0%,#2d3023,transparent 55%),#090b0c;min-height:100vh}
body.mpw-dynamic-main>.topbar{display:none!important}
body.mpw-dynamic-main .mw-site-nav{position:relative;z-index:12;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;max-width:100%;padding:14px clamp(16px,4vw,42px);background:linear-gradient(115deg,#090d10ef,#22251ef2);border-bottom:1px solid #8b754c;box-shadow:0 12px 28px #0005;color:#efe7d1}
body.mpw-dynamic-main .mw-site-nav .mw-brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:#efca7d}
body.mpw-dynamic-main .mw-site-nav .mw-brand img{width:49px;height:49px;object-fit:contain}
body.mpw-dynamic-main .mw-site-nav .mw-brand-copy{display:flex;flex-direction:column;line-height:1.2}
body.mpw-dynamic-main .mw-site-nav .mw-brand-copy strong{font-size:1.2rem}
body.mpw-dynamic-main .mw-site-nav .mw-brand-copy small{font-size:.7rem;color:#bfb499}
body.mpw-dynamic-main .mw-site-nav nav{display:flex;align-items:center;flex-wrap:wrap;gap:10px 16px;flex:1}
body.mpw-dynamic-main .mw-site-nav nav>a{color:#f1e6c8;text-decoration:none;font-size:.89rem}
body.mpw-dynamic-main .mw-site-nav a:focus-visible,body.mpw-dynamic-main .mw-site-nav summary:focus-visible{outline:3px solid #f0cf84;outline-offset:3px}
body.mpw-dynamic-main .mw-nav-menu{position:relative;color:#e9c778}
body.mpw-dynamic-main .mw-nav-menu summary{cursor:pointer;list-style:none;border:1px solid #95784d;border-radius:9px;padding:7px 11px}
body.mpw-dynamic-main .mw-nav-panel{position:absolute;right:0;top:100%;z-index:20;width:min(680px,90vw);max-height:75vh;overflow:auto;background:#12191c;color:#eee;padding:18px;border:1px solid #b08d52;border-radius:12px;box-shadow:0 20px 45px #0009;display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px}
body.mpw-dynamic-main .mw-nav-menu:not([open]) .mw-nav-panel{display:none}
body.mpw-dynamic-main .mw-nav-panel section{display:flex;flex-direction:column;gap:7px}
body.mpw-dynamic-main .mw-nav-panel a{color:#f3d697;text-decoration:none;font-size:.9rem}
body.mpw-dynamic-main .mw-nav-panel h3{font-size:.9rem;color:#f6eccf}
body.mpw-dynamic-main .mw-site-footer{display:flex;flex-wrap:wrap;justify-content:space-between;gap:18px;background:linear-gradient(130deg,#111719,#090a0c);color:#f1e7ce;padding:32px clamp(18px,4vw,44px);border-top:1px solid #9f7e46}
body.mpw-dynamic-main .mw-site-footer>div,body.mpw-dynamic-main .mw-site-footer>nav{flex:1 1 200px}
body.mpw-dynamic-main .mw-site-footer a{color:#ecd09a;text-decoration:none}
body.mpw-dynamic-main .mw-site-footer nav,body.mpw-dynamic-main .mw-site-footer .mw-legal{display:flex;flex-direction:column;gap:10px}
body.mpw-dynamic-main .mw-site-footer .mpx-bottom-bar{flex:1 1 100%;display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;border-top:1px solid #564528;padding-top:16px;gap:12px}
body.mpw-dynamic-main .mw-site-footer .mpw-copyright-founder,body.mpw-dynamic-main .mw-site-footer [data-mpw-footer-only]{color:#f5ce76;font-weight:900;text-shadow:0 1px 0 #51361a,0 3px 9px #000}
body.mpw-dynamic-main .mw-site-nav a:hover,body.mpw-dynamic-main .mw-site-footer a:hover{color:#fff7de}
body.mpw-dynamic-main .mpw-skip{position:absolute;left:-10000px}
body.mpw-dynamic-main .mpw-skip:focus{position:fixed;left:12px;top:12px;z-index:100;padding:12px;background:#111;color:white}
@media(max-width:760px){body.mpw-dynamic-main .mw-site-nav{align-items:flex-start}body.mpw-dynamic-main .mw-site-nav nav{flex:1 1 100%}body.mpw-dynamic-main .mw-nav-panel{left:0;right:auto;width:min(90vw,500px)}}
@media(prefers-reduced-motion:reduce){body.mpw-dynamic-main *,body.mpw-dynamic-main *::after,body.mpw-dynamic-main *::before{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important;scroll-behavior:auto!important}}
</style>
STYLE;

function takeOne(string $subject, string $regex, string $replacement, string $description, bool $required): string {
    $count = 0;
    $out = preg_replace_callback($regex, static fn($m)=>$replacement, $subject, 1, $count);
    if (!is_string($out) || $count > 1 || ($required && $count !== 1)) {
        throw new RuntimeException('Unexpected HTML pattern: ' . $description);
    }
    return $out;
}

function countTagClass(string $body, string $tag, string $class): int {
    $n=0;
    $matched=[];
    if(!preg_match_all('~<'.preg_quote($tag,'~').'\b[^>]*>~i',$body,$matched))return 0;
    foreach($matched[0] as $opening){
        if(preg_match('~\bclass\s*=\s*["\']([^"\']*)["\']~i',$opening,$captured)){
            $parts=preg_split('/\s+/',trim($captured[1]));
            if(in_array($class,$parts,true))$n++;
        }
    }
    return $n;
}

function transformMain(string $body, string $path, string $newHeader, string $newFooter): string {
    if (!str_starts_with(strtolower(ltrim($body)), '<!doctype html')
        || substr_count(strtolower($body), '<html') !== 1
        || stripos($body, '<head') === false
        || stripos($body, '</head>') === false
        || stripos($body, '<main') === false
        || stripos($body, '<body') === false
        || stripos($body, '</body>') === false) {
        throw new RuntimeException('HTML is not expected page structure');
    }
    $heads = [
        'mw-site-nav'=>countTagClass($body,'header','mw-site-nav'),
        'mpw-header'=>countTagClass($body,'header','mpw-header'),
        'site-header'=>countTagClass($body,'header','site-header'),
    ];
    $footers = [
        'mw-site-footer'=>countTagClass($body,'footer','mw-site-footer'),
        'mpw-footer'=>countTagClass($body,'footer','mpw-footer'),
        'site-footer'=>countTagClass($body,'footer','site-footer'),
    ];
    if (array_sum($heads)<1 || array_sum($heads)>2 || array_sum($footers)<1 || array_sum($footers)>2
        || max($heads)>1 || max($footers)>1) {
        throw new RuntimeException('Incompatible original site shell: '.json_encode([$heads,$footers]));
    }
    if ($heads['mw-site-nav']===1) {
        if ($heads['site-header']===1) {
            $body=takeOne($body, '~<header\b[^>]*class=["\']site-header["\'][^>]*>[\s\S]*?</header\s*>~i', '', 'duplicate legacy header',true);
        }
        if ($heads['mpw-header']===1) {
            $body=takeOne($body, '~<header\b[^>]*class=["\']mpw-header["\'][^>]*>[\s\S]*?</header\s*>~i', '', 'duplicate brand header',true);
        }
    } elseif ($heads['mpw-header']===1) {
        $body=takeOne($body,'~<header\b[^>]*class=["\']mpw-header["\'][^>]*>[\s\S]*?</header\s*>~i',$newHeader,'brand header',true);
    } else {
        $body=takeOne($body,'~<header\b[^>]*class=["\']site-header["\'][^>]*>[\s\S]*?</header\s*>~i',$newHeader,'legacy header',true);
    }
    if ($footers['mw-site-footer']===1) {
        if ($footers['site-footer']===1) {
            $body=takeOne($body,'~<footer\b[^>]*class=["\']site-footer["\'][^>]*>[\s\S]*?</footer\s*>~i','','duplicate legacy footer',true);
        }
        if ($footers['mpw-footer']===1) {
            $body=takeOne($body,'~<footer\b[^>]*class=["\']mpw-footer["\'][^>]*>[\s\S]*?</footer\s*>~i','','duplicate brand footer',true);
        }
    } elseif ($footers['mpw-footer']===1) {
        $body=takeOne($body,'~<footer\b[^>]*class=["\']mpw-footer["\'][^>]*>[\s\S]*?</footer\s*>~i',$newFooter,'brand footer',true);
    } else {
        $body=takeOne($body,'~<footer\b[^>]*class=["\']site-footer["\'][^>]*>[\s\S]*?</footer\s*>~i',$newFooter,'legacy footer',true);
    }
    if (countTagClass($body,'header','mw-site-nav')!==1 || countTagClass($body,'footer','mw-site-footer')!==1
        || countTagClass($body,'header','site-header')!==0 || countTagClass($body,'footer','site-footer')!==0
        || countTagClass($body,'header','mpw-header')!==0 || countTagClass($body,'footer','mpw-footer')!==0) {
        throw new RuntimeException('Site header/footer are not unique');
    }

    $body=takeOne($body,'~<html\b[^>]*>~i','<html lang="en" dir="ltr">','English document language',true);
    $body=takeOne($body,'~<link\b(?=[^>]*\brel=["\']canonical["\'])[^>]*>~i',
        '<link rel="canonical" href="https://mojplaywin.com'.$path.'">','main-only canonical',true);
    $titleMap = [
        '/education/' => 'Education & Learning | MojPlayWin',
        '/weather/' => 'Weather and Agriculture | MojPlayWin',
        '/agriculture/' => 'Agriculture | MojPlayWin',
    ];
    if (isset($titleMap[$path])) {
        $body=takeOne($body,'~<title\b[^>]*>[\s\S]*?</title\s*>~i',
            '<title>'.$titleMap[$path].'</title>','main-only document title',true);
    }
    // The old shared Education template still emits a Zomorodmelal
    // meta description on the MojPlayWin host; keep course content intact.
    if ($path==='/education/') {
        $body=takeOne($body,
            '~<meta\b(?=[^>]*\bname=["\']description["\'])[^>]*>~i',
            '<meta name="description" content="Explore MojPlayWin education, practical skills, applied technology, research and learning resources.">',
            'Education-specific company metadata',true);
    }
    $ogTitle=(preg_match('~<title\b[^>]*>([\s\S]*?)</title\s*>~i',$body,$titleMatch)
        ? html_entity_decode(strip_tags($titleMatch[1]),ENT_QUOTES|ENT_HTML5,'UTF-8')
        : 'MojPlayWin');
    $ogName=htmlspecialchars($ogTitle,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');
    $ogUrl=htmlspecialchars('https://mojplaywin.com'.$path,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');
    foreach (['og:title'=>$ogName,'og:url'=>$ogUrl,'og:site_name'=>'MojPlayWin',
              'og:image'=>'https://mojplaywin.com'.MPW_BRAND_ICON] as $property=>$value) {
        $pat='~<meta\b(?=[^>]*\bproperty=["\']'.preg_quote($property,'~').'["\'])[^>]*>~i';
        $replace='<meta property="'.$property.'" content="'.$value.'">';
        if (preg_match($pat,$body)) {
            $body=takeOne($body,$pat,$replace,'social tag '.$property,true);
        } else {
            $body=takeOne($body,'~</head\s*>~i',$replace."\n</head>",'social tag insertion '.$property,true);
        }
    }
    $body=takeOne($body,'~<link\b(?=[^>]*\brel=["\']icon["\'])[^>]*>~i',
        '<link rel="icon" type="image/webp" href="'.MPW_BRAND_ICON.'">','brand icon',false);
    if (str_contains($body,'data:image/jpeg;base64,')) {
        $found=0;
        $body=(string)preg_replace('~src=["\']data:image/jpeg;base64,[A-Za-z0-9+/=]+["\']~',
            'src="'.MPW_BRAND_ICON.'"',$body,1,$found);
        if ($found!==1)throw new RuntimeException('Unknown embedded image');
    }
    if (in_array($path,['/education/','/weather/','/agriculture/'],true)) {
        // Keep Persian original scientific content semantically marked as Persian.
        $body=takeOne($body,'~<main\b([^>]*)>~i','<main lang="fa" dir="rtl"$1>', 'localized original content',true);
    }
    $body=(string)preg_replace_callback('~<body\b([^>]*)>~i',function($match){
        $tag=$match[0];
        if (preg_match('~\bclass=["\']([^"\']*)["\']~i',$tag)) {
            return (string)preg_replace('~\bclass=(["\'])([^"\']*)\1~i',
                'class="$2 mpw-dynamic-main"',$tag,1);
        }
        return substr($tag,0,-1).' class="mpw-dynamic-main">';
    },$body,1,$bodyCount);
    if ($bodyCount!==1 || !str_contains($body,'mpw-dynamic-main'))throw new RuntimeException('Body scope missing');
    $body=takeOne($body,'~</head\s*>~i',MPW_STYLE."\n</head>",'scoped appearance',true);
    if (!str_contains($body,'Mojtaba Roozegar')) throw new RuntimeException('Founder credit absent');
    return $body;
}

function layoutParts(): array {
    $source=__DIR__.'/mpw-ten-editorials-20261018/pages/research.html';
    if (!is_file($source) || is_link($source))throw new RuntimeException('Isolated research shell unavailable');
    $html=file_get_contents($source);
    if (!is_string($html))throw new RuntimeException('Invalid shell source');
    if (!preg_match('~<header\b[^>]*class=["\']mw-site-nav["\'][^>]*>[\s\S]*?</header\s*>~i',$html,$header)
        || !preg_match('~<footer\b[^>]*class=["\']mw-site-footer["\'][^>]*>[\s\S]*?</footer\s*>~i',$html,$footer)) {
        throw new RuntimeException('MojPlayWin standard shell not found');
    }
    if (!str_contains($header[0],'MojPlayWin') || !str_contains($footer[0],'Mojtaba Roozegar')) {
        throw new RuntimeException('Incomplete brand shell');
    }
    return [$header[0],$footer[0]];
}

if (PHP_SAPI==='cli' && ($argv[1]??'')==='selftest') {
    $h='<header class="mw-site-nav">MojPlayWin</header>';
    $f='<footer class="mw-site-footer">Mojtaba Roozegar</footer>';
    $prefix='<!doctype html><html lang="fa" dir="rtl"><head><title>Old</title>'
        .'<link rel="canonical" href="https://zomorodmelal.ir/store/"></head>'
        .'<body class="site-standard-v2">';
    $s=$prefix.'<header class="site-header">Legacy</header>'.$h.'<main><h1>Store</h1></main>'
        .$f.'<footer class="site-footer">Legacy footer</footer></body></html>';
    $result=transformMain($s,'/store/',$h,$f);
    if (str_contains($result,'Legacy') || countTagClass($result,'header','mw-site-nav')!==1
        || countTagClass($result,'footer','mw-site-footer')!==1
        || !str_contains($result,'https://mojplaywin.com/store/'))throw new RuntimeException('Store test failed');
    $g='<!doctype html><html lang="en"><head><title>Games</title>'
        .'<link rel="canonical" href="https://mojplaywin.com/games/"></head>'
        .'<body><header class="mpw-header">old</header><main><h1>Games</h1></main>'
        .'<footer class="mpw-footer">old footer</footer></body></html>';
    $result=transformMain($g,'/games/',$h,$f);
    if (!str_contains($result,'<h1>Games</h1>') || str_contains($result,'class="mpw-header"')) {
        throw new RuntimeException('Games test failed');
    }
    echo "MPW_MAIN_ONLY_BRIDGE_SELFTEST=PASS\n";
    exit(0);
}

$slug=$_GET['__mpw_template_route']??null;
$host=strtolower((string)($_SERVER['HTTP_HOST']??''));
if (!is_string($slug)||!isset($allowed[$slug])||!in_array($host,['mojplaywin.com','www.mojplaywin.com'],true)) {
    http_response_code(404);exit('Not found');
}
if (strtoupper((string)($_SERVER['REQUEST_METHOD']??''))!=='GET') {
    http_response_code(405);header('Allow: GET');exit;
}
$path=$allowed[$slug];
$forward=$_GET;
unset($forward['__mpw_template_route'],$forward['__mpw_template_passthru'],
    $forward['__mpw_canon_passthru'],$forward['__mpw_probe']);
foreach(array_keys($forward) as $key) {
    if (!is_string($key)||strlen($key)>90||preg_match('/[^a-zA-Z0-9_\.\[\]-]/',$key)) unset($forward[$key]);
}
$query=http_build_query($forward+[
    '__mpw_template_passthru'=>'1','__mpw_canon_passthru'=>'1'
],'','&',PHP_QUERY_RFC3986);
$origin='https://mojplaywin.com'.$path.'?'.$query;
header('X-Content-Type-Options: nosniff');
header('Cache-Control: private, no-store, max-age=0');
header('Vary: Cookie');
function passthrough(string $path,string $query): never {
    header('Location: '.$path.'?'.$query,true,307);exit;
}
try {
    [$headerHtml,$footerHtml]=layoutParts();
} catch(Throwable $e) {
    error_log('MPW dynamic shell: invalid layout source: '.get_class($e));
    passthrough($path,$query);
}
if (!function_exists('curl_init'))passthrough($path,$query);
$curl=curl_init($origin);
if ($curl===false)passthrough($path,$query);
$headers=['Accept: text/html','Accept-Encoding: identity','Cache-Control: no-cache'];
$cookie=$_SERVER['HTTP_COOKIE']??'';
if(is_string($cookie)&&$cookie!==''&&strlen($cookie)<=8192&&!preg_match('/[\r\n]/',$cookie)){
    $headers[]='Cookie: '.$cookie;
}
$lang=$_SERVER['HTTP_ACCEPT_LANGUAGE']??'';
if(is_string($lang)&&strlen($lang)<=240&&!preg_match('/[\r\n]/',$lang)){
    $headers[]='Accept-Language: '.$lang;
}
curl_setopt_array($curl,[
    CURLOPT_RETURNTRANSFER=>true,CURLOPT_HEADER=>true,CURLOPT_FOLLOWLOCATION=>false,
    CURLOPT_CONNECTTIMEOUT=>4,CURLOPT_TIMEOUT=>12,CURLOPT_SSL_VERIFYPEER=>true,
    CURLOPT_SSL_VERIFYHOST=>2,CURLOPT_PROTOCOLS=>CURLPROTO_HTTPS,
    CURLOPT_ENCODING=>'identity',CURLOPT_USERAGENT=>'MojPlayWin-main-shell-exact/1.0',
    CURLOPT_HTTPHEADER=>$headers,
]);
$response=curl_exec($curl);
$status=curl_getinfo($curl,CURLINFO_HTTP_CODE);
$mime=curl_getinfo($curl,CURLINFO_CONTENT_TYPE);
$hsize=curl_getinfo($curl,CURLINFO_HEADER_SIZE);
$error=curl_errno($curl);
curl_close($curl);
if (!is_string($response)||$error!==0||$status!==200||!is_int($hsize)||$hsize<=0
    ||!is_string($mime)||stripos($mime,'text/html')!==0)passthrough($path,$query);
$originalHeaders=substr($response,0,$hsize);
$html=substr($response,$hsize);
if (strlen($html)<900||strlen($html)>MPW_HTML_MAX)passthrough($path,$query);
try {
    $rendered=transformMain($html,$path,$headerHtml,$footerHtml);
} catch(Throwable $e) {
    error_log('MPW dynamic shell: original output variant refused for '.$slug.' '.get_class($e));
    passthrough($path,$query);
}
foreach(preg_split('/\r?\n/',$originalHeaders) as $line){
    if (!is_string($line)||strpos($line,':')===false||strpbrk($line,"\r\n")!==false)continue;
    [$key]=explode(':',$line,2);
    $name=strtolower(trim($key));
    if(in_array($name,['set-cookie','content-security-policy','x-frame-options',
        'referrer-policy','permissions-policy','strict-transport-security'],true)){
        header($line,$name!=='set-cookie');
    }
}
header('Content-Type: text/html; charset=utf-8');
header('X-MPW-Main-Shell: exact-owner-only');
echo $rendered;
