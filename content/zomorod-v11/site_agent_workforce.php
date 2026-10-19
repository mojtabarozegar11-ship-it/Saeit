<?php
declare(strict_types=1);
/**
 * Site-only, offline-testable operational evidence worker.
 * Writes ONLY to Zomorod's existing private site_agents.sqlite3.
 * Produces observed audits for owner review; never claims to publish,
 * synthesize a product, trade, send money, run VPS factory, or invoke an AI model.
 */
function zmWorkInitialize(PDO $db): void {
    $db->exec('CREATE TABLE IF NOT EXISTS site_work_state (
      agent_code TEXT PRIMARY KEY, last_check_at TEXT, last_status TEXT,
      last_artifact_id INTEGER, last_sha256 TEXT)');
    $db->exec('CREATE TABLE IF NOT EXISTS site_work_outputs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      agent_code TEXT NOT NULL, check_path TEXT NOT NULL,
      output_type TEXT NOT NULL DEFAULT "site_evidence_audit",
      status TEXT NOT NULL CHECK(status IN ("review","blocked","failed")),
      http_code INTEGER NOT NULL,
      quality_score INTEGER NOT NULL CHECK(quality_score BETWEEN 0 AND 100),
      title TEXT NOT NULL, findings_json TEXT NOT NULL,
      source_sha256 TEXT NOT NULL, elapsed_ms INTEGER NOT NULL,
      observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)');
    $db->exec('CREATE INDEX IF NOT EXISTS ix_site_work_outputs_agent_time ON site_work_outputs(agent_code,id DESC)');
    $db->exec('CREATE TABLE IF NOT EXISTS site_work_generation_evidence (
      id INTEGER PRIMARY KEY AUTOINCREMENT, agent_code TEXT NOT NULL,
      candidate_sha256 TEXT NOT NULL, baseline_sha256 TEXT NOT NULL,
      benchmark_before INTEGER NOT NULL, benchmark_after INTEGER NOT NULL,
      tests_passed INTEGER NOT NULL, accepted INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      CHECK(accepted=0 OR (tests_passed=1 AND benchmark_after>benchmark_before AND candidate_sha256!=baseline_sha256)))');
}
function zmWorkEscape(string $s): string {
    return htmlspecialchars($s,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');
}
function zmWorkSafePath(string $s): string {
    if (!preg_match('~^/[a-z0-9/_-]{0,119}$~iD',$s) ||
        str_contains($s,'..') || str_contains($s,'//')) {
        throw new InvalidArgumentException('Site route path refused');
    }
    return $s;
}
function zmWorkFetch(string $path, ?callable $transport=null): array {
    $path=zmWorkSafePath($path);
    $url='https://zomorodmelal.ir'.$path;
    if ($transport) {
        $out=$transport($url);
        if(!is_array($out))throw new UnexpectedValueException('Invalid source response');
        return $out;
    }
    if(!function_exists('curl_init'))
        return ['status'=>0,'type'=>'','body'=>'','error'=>'cURL unavailable'];
    $ch=curl_init($url);
    if($ch===false)return ['status'=>0,'type'=>'','body'=>'','error'=>'Cannot initialize cURL'];
    $bytes=0;$out='';$truncated=false;
    curl_setopt_array($ch,[
        CURLOPT_RETURNTRANSFER=>false,CURLOPT_FOLLOWLOCATION=>false,
        CURLOPT_CONNECTTIMEOUT=>3,CURLOPT_TIMEOUT=>11,
        CURLOPT_SSL_VERIFYPEER=>true,CURLOPT_SSL_VERIFYHOST=>2,
        CURLOPT_PROTOCOLS=>CURLPROTO_HTTPS,
        CURLOPT_USERAGENT=>'ZomorodSiteEvidenceWorker/1.0',
        CURLOPT_WRITEFUNCTION=>static function($handle,$chunk)use(&$out,&$bytes,&$truncated) {
            $size=strlen($chunk);$bytes+=$size;
            if($bytes>786432){$truncated=true;return 0;}
            $out.=$chunk;return $size;
        },
        CURLOPT_HTTPHEADER=>['Accept: text/html'],
    ]);
    $result=curl_exec($ch);
    $status=(int)curl_getinfo($ch,CURLINFO_HTTP_CODE);
    $type=(string)curl_getinfo($ch,CURLINFO_CONTENT_TYPE);
    $error=(string)curl_error($ch);
    curl_close($ch);
    if($truncated)$error='response exceeds 768 KiB audit limit';
    return ['status'=>$status,'type'=>$type,'body'=>$out,'error'=>$error];
}
/** Pure, deterministic and conservative: empty/partial pages fail closed. */
function zmWorkAssess(string $path,array $observation): array {
    $path=zmWorkSafePath($path);
    $http=(int)($observation['status']??0);
    $body=(string)($observation['body']??'');
    $type=(string)($observation['type']??'');
    $error=(string)($observation['error']??'');
    $findings=[
      'path'=>$path,'http'=>$http,'response_bytes'=>strlen($body),
      'observed_not_published'=>true,'external_sources_used'=>false,
      'type'=>substr($type,0,72)
    ];
    if($http!==200||$error!==''||!str_starts_with(strtolower($type),'text/html')
       ||strlen($body)<64){
       $findings['blocker']=($http!==200?'Non-200 response':
          ($error!==''?'Transport or size limit':'Invalid or short HTML'));
       return ['status'=>'blocked','score'=>0,'title'=>'بازرسی ناموفق مسیر '.$path,
         'findings'=>$findings,'sha'=>hash('sha256',$body)];
    }
    $matches=[];
    preg_match('~<title\b[^>]*>(.*?)</title\s*>~is',$body,$matches);
    $title=trim(preg_replace('/\s+/u',' ',strip_tags(html_entity_decode($matches[1]??'',ENT_QUOTES|ENT_HTML5,'UTF-8'))));
    $h1count=preg_match_all('~<h1(?:\s[^>]*)?>~i',$body);
    $desc='';
    if(preg_match('~<meta\b[^>]*\bname\s*=\s*(?:"description"|\'description\')[^>]*>~i',$body,$m) ||
       preg_match('~<meta\b[^>]*\bcontent\s*=\s*["\'][^"\']*["\'][^>]*\bname\s*=\s*["\']description["\'][^>]*>~i',$body,$m)){
        if(preg_match('~\bcontent\s*=\s*(["\'])(.*?)\1~is',$m[0],$c))
            $desc=trim(html_entity_decode($c[2],ENT_QUOTES|ENT_HTML5,'UTF-8'));
    }
    $linkCount=preg_match_all('~<a\b[^>]*\bhref\s*=~i',$body);
    $findings['title']=$title;
    $titleLength=function_exists('mb_strlen')?mb_strlen($title,'UTF-8'):strlen($title);
    $findings['title_length']=$titleLength;
    $findings['h1_count']=$h1count;
    $findings['meta_description_present']=$desc!=='';
    $findings['internal_link_candidates']=$linkCount;
    $findings['html_sha256']=hash('sha256',$body);
    $issues=[];
    if($title==='')$issues[]='missing_title';
    elseif($titleLength>100)$issues[]='title_over_100_chars';
    if($h1count!==1)$issues[]='h1_count_not_one';
    if($desc==='')$issues[]='missing_meta_description';
    if($linkCount===0)$issues[]='no_anchor_links';
    $findings['issues']=$issues;
    $score=max(0,100-25*count($issues));
    return ['status'=>'review','score'=>$score,'title'=>'ممیزی مستند '.$path,
        'findings'=>$findings,'sha'=>$findings['html_sha256']];
}
function zmWorkCycle(PDO $db,?callable $transport=null,int $max=2): array {
    zmWorkInitialize($db);
    $max=max(1,min(3,$max));
    // Deterministic scheduling: least recently checked first, no unrelated sites.
    $q=$db->prepare('SELECT a.code,a.check_path FROM agents a
        LEFT JOIN site_work_state s ON s.agent_code=a.code
        WHERE a.enabled=1
        ORDER BY COALESCE(s.last_check_at,"") ASC, a.code LIMIT ?');
    $q->bindValue(1,$max,PDO::PARAM_INT);$q->execute();
    $rows=$q->fetchAll(PDO::FETCH_ASSOC);$results=[];
    foreach($rows as $row){
        $start=microtime(true);$path=(string)$row['check_path'];
        try{
            $e=zmWorkAssess($path,zmWorkFetch($path,$transport));
        }catch(Throwable $err){
            $e=['status'=>'failed','score'=>0,'title'=>'بازرسی مسدود',
                'findings'=>['error_class'=>get_class($err),'path'=>'redacted'],
                'sha'=>hash('sha256','blocked')];
        }
        $elapsed=(int)round((microtime(true)-$start)*1000);
        $db->beginTransaction();
        try {
            $out=$db->prepare('INSERT INTO site_work_outputs
              (agent_code,check_path,status,http_code,quality_score,title,findings_json,source_sha256,elapsed_ms)
              VALUES (?,?,?,?,?,?,?,?,?)');
            $out->execute([(string)$row['code'],zmWorkSafePath($path),
                $e['status'],(int)($e['findings']['http']??0),$e['score'],$e['title'],
                json_encode($e['findings'],JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR),
                $e['sha'],$elapsed]);
            $id=(int)$db->lastInsertId();
            $state=$db->prepare('INSERT INTO site_work_state(agent_code,last_check_at,last_status,last_artifact_id,last_sha256)
              VALUES (?,CURRENT_TIMESTAMP,?,?,?)
              ON CONFLICT(agent_code) DO UPDATE SET
              last_check_at=excluded.last_check_at,last_status=excluded.last_status,
              last_artifact_id=excluded.last_artifact_id,last_sha256=excluded.last_sha256');
            $state->execute([$row['code'],$e['status'],$id,$e['sha']]);
            $db->commit();
            $results[]=['agent'=>$row['code'],'status'=>$e['status'],'artifact'=>$id,
                'quality_score'=>$e['score']];
        }catch(Throwable $err){$db->rollBack();throw $err;}
    }
    return $results;
}
function zmWorkDashboard(PDO $db):string {
    zmWorkInitialize($db);
    $total=(int)$db->query('SELECT COUNT(*) FROM site_work_outputs')->fetchColumn();
    $latest=$db->query('SELECT agent_code,check_path,status,quality_score,observed_at
        FROM site_work_outputs ORDER BY id DESC LIMIT 11')->fetchAll(PDO::FETCH_ASSOC);
    $out='<section class="card" aria-label="عملکرد مستند ایجنت‌های سایت"><h2>کارهای ثبت‌شده ایجنت‌ها</h2>'.
      '<p>خروجی‌های واقعی بررسی صفحات سایت؛ هیچ موردی بدون تأیید مالک «محصول منتشرشده» محسوب نمی‌شود.</p>'.
      '<p>تعداد گزارش‌های قابل پیگیری: '.number_format($total).'</p>'.
      '<table style="width:100%;font-size:.85rem"><thead><tr><th>ایجنت</th><th>صفحه</th><th>وضعیت</th><th>کیفیت بررسی</th><th>زمان</th></tr></thead><tbody>';
    foreach($latest as $x){
      $out.='<tr><td>'.zmWorkEscape((string)$x['agent_code']).'</td>'.
        '<td>'.zmWorkEscape((string)$x['check_path']).'</td>'.
        '<td>'.zmWorkEscape((string)$x['status']).'</td>'.
        '<td>'.(int)$x['quality_score'].'/100</td>'.
        '<td>'.zmWorkEscape((string)$x['observed_at']).'</td></tr>';
    }
    return $out.'</tbody></table></section>';
}
