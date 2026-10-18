<?php
declare(strict_types=1);
/** Self-contained Zomorod-only compatibility runtime. Historical Django/V91 roles are adapted
 * as *site audit* agents: no factory, payments, web publishing or AI provider calls. */
function zmAgentDb(string $private): PDO {
    if (!is_dir($private)) throw new RuntimeException('Private agent storage unavailable');
    $db = new PDO('sqlite:'.$private.'/site_agents.sqlite3',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_TIMEOUT=>10]);
    $db->exec('PRAGMA journal_mode=WAL; PRAGMA busy_timeout=10000;');
    $db->exec('CREATE TABLE IF NOT EXISTS agents (code TEXT PRIMARY KEY, title TEXT NOT NULL, mission TEXT NOT NULL, check_path TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)), created_at TEXT DEFAULT CURRENT_TIMESTAMP)');
    $db->exec('CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY, agent_code TEXT NOT NULL REFERENCES agents(code), status TEXT NOT NULL CHECK(status IN ("ok","warning","error")), http_code INTEGER NOT NULL DEFAULT 0, duration_ms INTEGER NOT NULL, detail TEXT NOT NULL, occurred_at TEXT DEFAULT CURRENT_TIMESTAMP)');
    $db->exec('CREATE INDEX IF NOT EXISTS ix_agent_runs ON runs(agent_code,id DESC)');
    $seed = [
        ['master','مستر ایجنت سایت','هماهنگی و پایش سلامت عمومی سایت؛ نسخه سازگار با چارچوب قدیمی','/'],
        ['content','ایجنت محتوا','پایش محتوای دانشنامه و تکمیل مقالات','/knowledge/'],
        ['seo','ایجنت سئو','بررسی دسترس‌پذیری جست‌وجو و مسیرهای مهم','/search/'],
        ['commerce','ایجنت فروشگاه','نظارت بر فروشگاه و نیازمندی درگاه بانک شهر','/store/'],
        ['agriculture','ایجنت کشاورزی','بررسی صفحه کشاورزی و راهنماهای فنی','/agriculture/'],
        ['research','ایجنت پژوهش','پایش مسیر تحقیقات و یادداشت‌های علمی','/research/'],
        ['economic','ایجنت اقتصاد','پایش محتوای اقتصادی و مدیریت تولید','/economy/'],
        ['weather','ایجنت هواشناسی','پایش صفحه راهنمای آب‌وهوا (بدون ادعای داده زنده)','/weather/'],
        ['quality','ایجنت کنترل کیفیت','بررسی وضعیت درباره ما و لینک‌های عمومی','/about/'],
        ['media','ایجنت رسانه','پایش اخبار شرکت و انتشارهای مستند','/news/'],
        ['security','ایجنت سلامت پنل','کنترل پاسخ صفحه ورود خصوصی؛ بدون ورود و بدون افشای داده','/business/']
    ];
    $stmt=$db->prepare('INSERT OR IGNORE INTO agents(code,title,mission,check_path) VALUES(?,?,?,?)');
    foreach($seed as $row) $stmt->execute($row);
    return $db;
}
function zmAgentCycle(PDO $db,?string $code=null): array {
    $rows=$code?$db->prepare('SELECT * FROM agents WHERE code=? AND enabled=1'):$db->prepare('SELECT * FROM agents WHERE enabled=1 ORDER BY code');
    $rows->execute($code?[$code]:[]);$results=[];
    foreach($rows->fetchAll() as $agent){
        $start=microtime(true);$http=0;$detail='';$status='error';
        try{
            $url='https://zomorodmelal.ir'.$agent['check_path'];
            if(function_exists('curl_init')){
                $ch=curl_init($url);
                curl_setopt_array($ch,[CURLOPT_RETURNTRANSFER=>true,CURLOPT_FOLLOWLOCATION=>false,CURLOPT_CONNECTTIMEOUT=>4,CURLOPT_TIMEOUT=>9,CURLOPT_USERAGENT=>'ZomorodSiteAgent/1.0 (site-local check)',CURLOPT_SSL_VERIFYPEER=>true,CURLOPT_SSL_VERIFYHOST=>2,CURLOPT_MAXREDIRS=>0]);
                $response=curl_exec($ch);$http=(int)curl_getinfo($ch,CURLINFO_HTTP_CODE);
                $err=curl_error($ch);curl_close($ch);
                $detail=$err?:'HTTP '.$http.' / '.(is_string($response)?strlen($response):0).' bytes';
            }else{$detail='PHP cURL unavailable';}
            $status=$http===200?'ok':($http>=300&&$http<500?'warning':'error');
        }catch(Throwable $e){$detail='Connection or site health error';}
        $elapsed=max(0,(int)((microtime(true)-$start)*1000));
        $db->prepare('INSERT INTO runs(agent_code,status,http_code,duration_ms,detail) VALUES(?,?,?,?,?)')->execute([$agent['code'],$status,$http,$elapsed,substr($detail,0,240)]);
        $results[]=[$agent['code'],$status,$http];
    }
    return $results;
}
function zmAgentHandle(PDO $db,string $action,string $code): void {
    if(!preg_match('/^[a-z]{3,25}$/',$code))throw new RuntimeException('Invalid agent');
    if($action==='agent_toggle'){
        $found=$db->prepare('SELECT enabled FROM agents WHERE code=?');$found->execute([$code]);$val=$found->fetchColumn();
        if($val===false)throw new RuntimeException('Agent not found');
        $db->prepare('UPDATE agents SET enabled=? WHERE code=?')->execute([((int)$val)===1?0:1,$code]);
    }elseif($action==='agent_run'){
        $out=zmAgentCycle($db,$code);
        if(count($out)!==1)throw new RuntimeException('Agent disabled or unavailable');
    }else throw new RuntimeException('Unsupported action');
}
function zmAgentChart(array $recent):string {
    $values=array_reverse(array_map(fn($r)=>(string)$r['status']==='ok'?95:((string)$r['status']==='warning'?55:10),array_slice($recent,0,14)));
    if(!$values)return '<p class="muted">هنوز داده واقعی برای نمودار ثبت نشده است.</p>';
    $n=count($values);$pts=[];
    foreach($values as $i=>$v){$x=10+($n===1?0:$i*220/($n-1));$y=99-$v*.82;$pts[]=round($x,1).','.round($y,1);}
    $poly=htmlspecialchars(implode(' ',$pts),ENT_QUOTES,'UTF-8');
    return '<svg viewBox="0 0 240 110" width="100%" height="112" role="img" aria-label="نمودار موفقیت چهارده اجرای آخر ایجنت"><rect x="1" y="1" width="238" height="108" rx="9" fill="#152c1d" stroke="#596a49"/><path d="M10 88H230 M10 55H230 M10 22H230" stroke="#4f6e49" fill="none" stroke-dasharray="3 6"/><polyline fill="none" stroke="#edcd7d" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" points="'.$poly.'"/></svg>';
}
function zmAgentRender(PDO $db):void {
    $agents=$db->query('SELECT * FROM agents ORDER BY CASE WHEN code="master" THEN 0 ELSE 1 END,code')->fetchAll();
    $n=(int)$db->query('SELECT COUNT(*) FROM runs')->fetchColumn();
    echo '<section><h2>مستر ایجنت و ایجنت‌های زمرد ملل</h2><p>این سامانه فقط داخل پنل مدیریت است؛ نسخه سازگار با نقش‌های قبلی و V91، با اندازه‌گیری واقعی HTTP. فعالیت فعلی پایش سایت است، نه تولید خودکار مقاله، تراکنش بانکی یا بازنویسی سایت.</p><p class="muted">گزارش‌های ثبت‌شده: '.(string)$n.' — هر نمودار بر اساس حداکثر ۱۴ اجرای واقعی همان ایجنت ترسیم می‌شود.</p></section>';
    echo '<div class="grid">';
    foreach($agents as $a){
        $code=(string)$a['code'];$stmt=$db->prepare('SELECT * FROM runs WHERE agent_code=? ORDER BY id DESC LIMIT 14');$stmt->execute([$code]);$runs=$stmt->fetchAll();
        $total=(int)($db->query('SELECT COUNT(*) FROM runs WHERE agent_code='.$db->quote($code))->fetchColumn());
        $ok=count(array_filter($runs,fn($x)=>$x['status']==='ok'));
        echo '<section class="card" style="min-width:0"><h3>'.esc($a['title']).'</h3><p>'.esc($a['mission']).'</p><p class="muted">'.($a['enabled']?'فعال':'متوقف').' · مجموع اجرا: '.$total.' · موفق در ۱۴ اجرای آخر: '.$ok.'</p>'.zmAgentChart($runs);
        if($runs)echo '<p class="muted">آخرین نتیجه: '.esc($runs[0]['status']).' — '.esc($runs[0]['detail']).' — '.esc($runs[0]['occurred_at']).'</p>';
        if(role()==='admin'){
            echo '<form method="post">'.tokenInput().'<input type="hidden" name="code" value="'.esc($code).'"><button name="action" value="agent_toggle">'.($a['enabled']?'توقف':'فعال‌سازی').'</button>';
            if($a['enabled'])echo ' <button name="action" value="agent_run">اجرای آزمون</button>';
            echo '</form>';
        }
        echo '</section>';
    }
    echo '</div>';
}