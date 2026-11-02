<?php
declare(strict_types=1);
/**
 * Private text report viewer for the existing authenticated PHP business desk.
 * No direct entrypoint: this script is only called from app.php *after* the
 * currently active role is re-read from the existing company user database.
 */

/**
 * Structured operational receipts are untrusted claims, not independent proof.
 * Read-only command panel; never consult the financial database or make calls.
 */
function zmBusinessActionReceipt(string $body,string $reportCode):array {
    $none=['state'=>'missing','actions'=>[]];
    if(!str_contains($body,'ZM_ACTIONS_V1_START'))return $none;
    $matches=[];
    $found=preg_match_all('/(?:^|\n)ZM_ACTIONS_V1_START\r?\n([^\x00]{1,7800}?)\r?\nZM_ACTIONS_V1_END(?=\r?\n|$)/u',$body,$matches);
    if($found!==1)return ['state'=>'invalid','actions'=>[]];
    try {$data=json_decode($matches[1][0],true,16,JSON_THROW_ON_ERROR);}
    catch(Throwable $e){return ['state'=>'invalid','actions'=>[]];}
    if(!is_array($data)||($data['version']??null)!==1||
       ($data['report_code']??null)!==$reportCode||
       !isset($data['actions'])||!is_array($data['actions'])||
       !array_is_list($data['actions'])||count($data['actions'])>20){
        return ['state'=>'invalid','actions'=>[]];
    }
    $ids=[];$actions=[];
    foreach($data['actions'] as $item){
        if(!is_array($item))return ['state'=>'invalid','actions'=>[]];
        $id=$item['id']??null;$title=$item['title_fa']??null;
        $status=$item['status']??null;$url=$item['evidence_url']??null;
        $impact=$item['impact_fa']??'';
        if(!is_string($id)||!preg_match('/^[A-Za-z0-9][A-Za-z0-9_-]{7,79}$/D',$id)||isset($ids[$id])||
           !is_string($title)||strlen($title)<8||strlen($title)>350||
           !is_string($impact)||strlen($impact)>500||
           !in_array($status,['completed','partial','blocked','not_started'],true)||
           !is_string($url)||strlen($url)>350||
           ($url!==''&&!preg_match('~^https://github\.com/mojtabarozegar11-ship-it/Saeit/(?:commit/[a-f0-9]{40}|actions/runs/[1-9][0-9]*|pull/[1-9][0-9]*|issues/[1-9][0-9]*(?:#issuecomment-[1-9][0-9]*)?)$~D',$url))||
           ($status==='completed'&&$url==='')){
            return ['state'=>'invalid','actions'=>[]];
        }
        $ids[$id]=true;
        $actions[]=['id'=>$id,'title'=>$title,'status'=>$status,'url'=>$url,'impact'=>$impact];
    }
    return ['state'=>'valid','actions'=>$actions];
}


/**
 * Optional derived, non-financial action index. The report source remains
 * authoritative; the index only rejects replay and malformed machine receipts.
 * Never upgrade an imported claim to an independently verified business act.
 */
function zmBusinessReportVisibleFa(string $body,string $code):string {
    // Keep immutable machine evidence in SQLite and the original GitHub link,
    // while showing only Persian prose in the human-readable report card.
    $parsed=zmBusinessActionReceipt($body,$code);
    if($parsed['state']!=='valid')return $body;
    $visible=preg_replace('/(?:^|\n)ZM_ACTIONS_V1_START\r?\n[^\x00]{1,7800}?\r?\nZM_ACTIONS_V1_END(?=\r?\n|$)/u',
        "\n[فهرست ساختاریافتهٔ اقدامات در جدول اتاق فرمان نمایش داده می‌شود.]",$body,1);
    return is_string($visible)?$visible:$body;
}

function zmBusinessActionIndexStatus(string $private,string $code):array {
    $missing=['state'=>'missing','unique_total'=>0,'latest_total'=>0,'latest_completed'=>0,'rejections'=>0,'latest_rejection'=>''];
    $path=$private.'/chatgpt_actions_index.sqlite3';
    if(!file_exists($path)&&!is_link($path))return $missing;
    try{
        if(is_link($private)||is_link($path)||!is_file($path)||!is_readable($path))throw new RuntimeException('unsafe action index path');
        $stat=lstat($path);
        if($stat===false||!is_int($stat['size'])||$stat['size']<4096||$stat['size']>500000000||(((int)$stat['mode'])&0077)!==0)throw new RuntimeException('unsafe action index permissions');
        $index=new SQLite3($path,SQLITE3_OPEN_READONLY);
        $index->busyTimeout(1500);
        try{
            if((int)$index->querySingle('PRAGMA user_version')!==1||
               $index->querySingle("SELECT value FROM metadata WHERE name='source'")!=='github:mojtabarozegar11-ship-it/Saeit:issue:1725'||
               $index->querySingle("SELECT value FROM metadata WHERE name='verification'")!=='not_checked')throw new RuntimeException('index identity mismatch');
            $built=$index->querySingle("SELECT value FROM metadata WHERE name='built_at'");
            $checked=is_string($built)?strtotime($built):false;
            if($checked===false||$checked>time()+300)throw new RuntimeException('index timestamp mismatch');
            $total=(int)$index->querySingle('SELECT COUNT(*) FROM actions');
            $rejected=(int)$index->querySingle('SELECT COUNT(*) FROM rejected');
            if($total<0||$total>2000000||$rejected<0||$rejected>100000)throw new RuntimeException('index count invalid');
            $p=$index->prepare('SELECT COUNT(*) AS n,COALESCE(SUM(CASE WHEN action_status="completed" THEN 1 ELSE 0 END),0) AS completed FROM actions WHERE report_code=:code');
            if($p===false)throw new RuntimeException('index query failed');
            $p->bindValue(':code',$code,SQLITE3_TEXT);
            $result=$p->execute();
            if($result===false)throw new RuntimeException('index query execution failed');
            $r=$result->fetchArray(SQLITE3_ASSOC);
            $check=$index->prepare('SELECT reason FROM rejected WHERE report_code=:code');
            if($check===false)throw new RuntimeException('index rejection query failed');
            $check->bindValue(':code',$code,SQLITE3_TEXT);
            $flag=$check->execute();
            $reason=$flag===false?false:$flag->fetchArray(SQLITE3_ASSOC);
            return ['state'=>time()-$checked>10800?'stale':'ready',
                    'unique_total'=>$total,'latest_total'=>(int)$r['n'],
                    'latest_completed'=>(int)$r['completed'],
                    'rejections'=>$rejected,'latest_rejection'=>is_array($reason)?(string)$reason['reason']:''];
        } finally {$index->close();}
    }catch(Throwable $e){
        error_log('ZM ACTION INDEX REJECTED ['.get_class($e).']');
        return ['state'=>'invalid','unique_total'=>0,'latest_total'=>0,'latest_completed'=>0,'rejections'=>0,'latest_rejection'=>''];
    }
}

/** Independent reference-availability audit, never financial/business proof. */
function zmBusinessEvidenceAttestation(string $private):array {
    $empty=['state'=>'missing','checked'=>0,'ci_success'=>0,'source_exists'=>0];
    $path=$private.'/chatgpt_evidence_attestations.json';
    if(!file_exists($path)&&!is_link($path))return $empty;
    try{
        $index=$private.'/chatgpt_actions_index.sqlite3';
        if(is_link($private)||is_link($path)||is_link($index)||!is_file($path)||!is_file($index))throw new RuntimeException('unsafe evidence paths');
        $stat=lstat($path);
        if($stat===false||!is_int($stat['size'])||$stat['size']<100||$stat['size']>2000000||(((int)$stat['mode'])&0077)!==0)throw new RuntimeException('unsafe evidence attestation');
        $raw=file_get_contents($path);
        if($raw===false||strlen($raw)!==$stat['size'])throw new RuntimeException('short attestation read');
        $data=json_decode($raw,true,20,JSON_THROW_ON_ERROR);
        if(!is_array($data)||($data['schema_version']??null)!==1||
           ($data['source']??'')!=='github:mojtabarozegar11-ship-it/Saeit:issue:1725'||
           ($data['business_effect_verified']??null)!==false||
           !is_string($data['index_sha256']??null)||
           !hash_equals(hash_file('sha256',$index),(string)$data['index_sha256'])||
           !is_array($data['results']??null)||!array_is_list($data['results']))throw new RuntimeException('attestation identity mismatch');
        $checkedAt=strtotime((string)($data['checked_at']??''));
        if($checkedAt===false||$checkedAt>time()+300)throw new RuntimeException('invalid evidence timestamp');
        $allowed=['not_checked','invalid_reference','unavailable','source_exists','mismatch','ci_success','ci_not_successful','merged_source','proposal_only','issue_exists'];
        $count=0;$green=0;$sources=0;$ids=[];
        foreach($data['results'] as $row){
            if(!is_array($row)||!is_string($row['action_id']??null)||
               !preg_match('/^[A-Za-z0-9][A-Za-z0-9_-]{7,79}$/D',$row['action_id'])||
               isset($ids[$row['action_id']])||
               !is_string($row['receipt_sha256']??null)||
               !preg_match('/^[a-f0-9]{64}$/D',$row['receipt_sha256'])||
               !in_array($row['reference_status']??null,$allowed,true))throw new RuntimeException('invalid evidence row');
            $ids[$row['action_id']]=true;
            if($row['reference_status']!=='not_checked')$count++;
            if($row['reference_status']==='ci_success')$green++;
            if(in_array($row['reference_status'],['source_exists','merged_source','issue_exists'],true))$sources++;
        }
        return ['state'=>time()-$checkedAt>10800?'stale':'ready','checked'=>$count,'ci_success'=>$green,'source_exists'=>$sources];
    }catch(Throwable $e){
        error_log('ZM EVIDENCE ATTESTATION REJECTED ['.get_class($e).']');
        return ['state'=>'invalid','checked'=>0,'ci_success'=>0,'source_exists'=>0];
    }
}

function zmBusinessCommandCenter(SQLite3 $db,string $private):void {
    $latest=$db->query('SELECT report_code,occurred_at,body,evidence_url FROM reports WHERE substr(report_code,1,2)="05" ORDER BY seq DESC LIMIT 1');
    if($latest===false)throw new RuntimeException('command center latest query failed');
    $report=$latest->fetchArray(SQLITE3_ASSOC);
    $contract=is_array($report)?zmBusinessActionReceipt((string)$report['body'],(string)$report['report_code']):['state'=>'missing','actions'=>[]];
    $labels=['completed'=>'انجام واقعی (ادعای گزارش؛ نیازمند راستی‌آزمایی)','partial'=>'بخشی انجام‌شده','blocked'=>'مسدود','not_started'=>'انجام‌نشده'];
    $claimed=count(array_filter($contract['actions'],static fn($a)=>$a['status']==='completed'));
    $actionIndex=zmBusinessActionIndexStatus($private,is_array($report)?(string)$report['report_code']:'');
    $referenceAudit=zmBusinessEvidenceAttestation($private);
    echo '<section aria-labelledby="zm-command-title"><h2 id="zm-command-title">اتاق فرمان چرخهٔ ساعتی ۰۵</h2>';
    echo '<p class="muted">فرمانده اجرایی این طرح وظیفهٔ زمان‌بندی‌شدهٔ ChatGPT است؛ این صفحه فقط وضعیت و شواهد آن را نمایش می‌دهد. مشاهدهٔ گزارش یا پیوند مدرک، اجرای واقعی و نتیجهٔ تجاری را اثبات نمی‌کند.</p>';
    echo '<div class="grid"><div class="card"><h3>هدف هر اجرای چرخهٔ ۰۵</h3><div class="metric">۲۰ اقدام</div><p class="muted">مستقل، ضروری و غیرتکراری</p></div>';
    echo '<div class="card"><h3>ردیف‌های «انجام‌شده» در رسید ساختاریافتهٔ اخیر</h3><div class="metric">'.$claimed.' / ۲۰</div><p class="muted">صرفاً خوداظهاری منبع؛ نه تأیید مستقل</p></div>';
    echo '<div class="card"><h3>عملیات مستقلاً تأییدشده از این قالب</h3><div class="metric">۰</div><p class="muted">راستی‌آزمای بیرونی به این نسخه متصل نیست؛ صفر به معنی نبود عملیات واقعی نیست.</p></div>';
    echo '<div class="card"><h3>اقدامات با شناسه یکتای ثبت‌شده</h3><div class="metric">'.(int)$actionIndex['unique_total'].'</div><p class="muted">منبع خوداظهاری؛ کنترل تکرار، نه اثبات مستقل</p></div></div>';
    if($actionIndex['state']==='missing')echo '<div class="notice">نمایهٔ مستقل کنترل تکرار هنوز نصب نشده است؛ گزارش‌های متنی قبلی مبنای شمارش قطعی اقدام نیستند.</div>';
    if($actionIndex['state']==='invalid')echo '<div class="notice danger">نمایهٔ اقدامات نامعتبر است؛ اطلاعات آن شمرده نشد.</div>';
    if($actionIndex['state']==='stale')echo '<div class="notice danger">نمایهٔ اقدامات بیش از سه ساعت به‌روزرسانی نشده؛ دادهٔ آن قدیمی است.</div>';
    if($actionIndex['state']==='ready'){
        echo '<p class="muted">نمایهٔ جلوگیری از تکرار: '.(int)$actionIndex['unique_total'].' شناسهٔ یکتا از کل تاریخچه · '.(int)$actionIndex['rejections'].' گزارش دارای رسید نامعتبر یا تکراری · '.(int)$actionIndex['latest_completed'].' ردیف کامل اظهاریِ غیرتکراری در گزارش آخر (بدون تأیید مستقل).</p>';
        if($actionIndex['latest_rejection']!=='')echo '<div class="notice danger">رسید جدید به علت ناسازگاری یا تکرار شناسه در تاریخچه رد شد؛ هیچ ردیف آن در نمایه یکتا محاسبه نشده است.</div>';
    }
    if($referenceAudit['state']==='ready'){
        echo '<p class="muted">بازبینی جداگانهٔ پیوندهای GitHub: '.(int)$referenceAudit['checked'].' مرجع بررسی‌شده · '.(int)$referenceAudit['ci_success'].' اجرای CI موفق · '.(int)$referenceAudit['source_exists'].' مرجع منبع موجود. این‌ها اثبات انجام فعالیت تجاری، تسویه، استقرار زنده یا تأیید مستقل ۲۰ اقدام نیستند.</p>';
    }elseif($referenceAudit['state']==='invalid'){
        echo '<div class="notice danger">فایل بازبینی مستقل منابع معتبر نیست؛ هیچ نتیجه‌ای از آن نمایش داده نمی‌شود.</div>';
    }elseif($referenceAudit['state']==='stale'){
        echo '<div class="notice danger">بازبینی پیوندهای منبع بیش از سه ساعت به‌روزرسانی نشده است؛ نتایج قدیمی محاسبه نمی‌شوند.</div>';
    }
    if(is_array($report))echo '<p class="muted">مبنای نمایش: '.esc((string)$report['report_code']).' · '.esc((string)$report['occurred_at']).' · <a href="'.esc((string)$report['evidence_url']).'" target="_blank" rel="noopener noreferrer">منبع شماره‌دار</a></p>';
    if($contract['state']==='missing')echo '<div class="notice">در گزارش اخیر هنوز دفتر اقدامات با قالب استاندارد ثبت نشده است؛ تعداد اقدامات واقعی نامعلوم است. گزارش‌های قبلی به‌صورت خودکار به ۲۰ اقدام تبدیل نمی‌شوند.</div>';
    if($contract['state']==='invalid')echo '<div class="notice danger">رسید ساختاریافته ناسازگار یا ناقص است؛ از شمارش و نمایش ادعاهای آن خودداری شد.</div>';
    if($contract['state']==='valid'){
        echo '<div class="scroll"><table><caption>ردیف‌های گزارش‌شده؛ تأیید مستقل این ردیف‌ها انجام نشده است</caption><tr><th>شناسه یکتا</th><th>اقدام</th><th>وضعیت اظهاری</th><th>اثر ادعایی</th><th>مدرک اولیه</th></tr>';
        foreach($contract['actions'] as $a){
            $link=$a['url']!==''?'<a target="_blank" rel="noopener noreferrer" href="'.esc($a['url']).'">بررسی شاهد</a>':'در دسترس نیست';
            echo '<tr><td>'.esc($a['id']).'</td><td>'.esc($a['title']).'</td><td>'.esc($labels[$a['status']]).'</td><td>'.esc($a['impact']).'</td><td>'.$link.'</td></tr>';
        }
        echo '</table></div>';
        if(count($contract['actions'])<20)echo '<p class="notice">کسری ردیف‌های عملیاتی ثبت‌شده نسبت به هدف: '.(20-count($contract['actions'])).'؛ این کسری را با اقدام انجام‌شده اشتباه نگیرید.</p>';
    }
    echo '<h3>معماری پنج حوزهٔ فرماندهی</h3><div class="scroll"><table><tr><th>حوزه</th><th>داده و مسئولیت</th><th>مرز کنترل</th></tr>';
    $areas=[
        ['رهبری و ۴ چرخهٔ دیگر','تجمیع گزارش‌های ۰۱، ۰۲، ۰۳، ۰۴ و اولویت‌های چرخهٔ ۰۵','چرخهٔ ۰۳ هنوز اتصال امن خودکار ندارد'],
        ['فروش، مشتری و رشد','سرنخ، سفارش، محصول قابل تحویل، رضایت و نرخ تبدیل','تراکنش بانکی و فروش واقعی بدون سند ثبت نمی‌شود'],
        ['مالی و حسابداری','دفتر کل، صورت‌حساب، بودجه و گزارش نقدینگی','نوشتن مالی فقط از مجرای کنترل‌شده و تأییدشده'],
        ['سایت و فناوری','نسخه، آزمون، وضعیت انتشار، ریسک و بازیابی','انتشار حساس با تأیید بازیابی و MFA'],
        ['عملیات و نیروی انسانی','کارخانه، تأمین، لجستیک، طرح‌ها و ظرفیت','پروژه و استخدام بدون تأیید واقعی محقق تلقی نمی‌شوند']
    ];
    foreach($areas as $a)echo '<tr><td>'.esc($a[0]).'</td><td>'.esc($a[1]).'</td><td>'.esc($a[2]).'</td></tr>';
    echo '</table></div><p class="muted">وضعیت چرخه‌ها و تاریخچهٔ مستند در ادامهٔ همین صفحه حفظ شده است. دریافت گزارش ساعتی از طریق همگام‌ساز انجام می‌شود؛ وجود پنل، به‌خودی‌خود اختیار بانکی یا فرمان اجرایی به سرور نمی‌دهد.</p></section>';
}

function zmBusinessChatgptReports(string $private):void {
    if(role()!=='admin')bail('دسترسی فقط برای مدیرکل مجاز است.',403);
    if(zmBusinessChatgptReportsArchive($private))return;
    $path=$private.'/chatgpt_reports_snapshot.json';
    echo '<section lang="fa" dir="rtl"><h2>گزارش‌های متنی اقدامات ChatGPT</h2>';
    echo '<p class="muted">تاریخچه شماره‌دار برگرفته از دفتر مدیریت؛ وجود گزارش به‌تنهایی اثبات فروش، پرداخت، انتشار یا اجرای عملیات نیست. دسترسی فقط‌خواندنی است.</p>';
    if(!is_file($path)){
        echo '<div class="notice">پرونده خصوصی گزارش‌ها هنوز نصب نشده است؛ هیچ گزارش فرضی نمایش داده نمی‌شود.</div></section>';
        return;
    }
    if(is_link($path)||is_link($private)||!is_readable($path)){
        echo '<div class="notice danger">مسیر پرونده خصوصی گزارش نامعتبر است.</div></section>';
        return;
    }
    try {
        $stat=lstat($path);
        if($stat===false||!is_int($stat['size'])||$stat['size']<32||$stat['size']>2000000||
           (((int)$stat['mode'])&0077)!==0){
            throw new RuntimeException('unsafe snapshot metadata');
        }
        $raw=file_get_contents($path);
        if($raw===false||strlen($raw)!==$stat['size'])throw new RuntimeException('short read');
        $payload=json_decode($raw,true,32,JSON_THROW_ON_ERROR);
        $rows=$payload['items']??null;
        if(!is_array($payload)||($payload['version']??null)!==1||
           ($payload['source']??'')!=='github:mojtabarozegar11-ship-it/Saeit:issue:1725'||
           !is_array($rows)||!array_is_list($rows)||count($rows)>100||
           ($payload['count']??null)!==count($rows)){
            throw new RuntimeException('invalid report set');
        }
        $seen=[];
        foreach($rows as $row){
            if(!is_array($row))throw new RuntimeException('invalid report row');
            $code=$row['report_code']??null;
            $id=$row['comment_id']??null;
            $body=$row['body']??null;
            $url=$row['evidence_url']??null;
            $at=$row['occurred_at']??null;
            if(!is_string($code)||!preg_match('/^[0-9]{2}-[0-9]{4,8}$/D',$code)||
               isset($seen[$code])||!is_int($id)||$id<1||
               !is_string($body)||strlen($body)<20||strlen($body)>32000||
               !is_string($at)||strlen($at)>40||
               !is_string($url)||$url!=='https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1725#issuecomment-'.$id){
                throw new RuntimeException('invalid report receipt');
            }
            $seen[$code]=true;
        }
        // Optional Persian rendering pack is independent of the immutable source.
        // It is private, read-only and matched to the original GitHub comment ID.
        $faRows=[];
        $faPath=$private.'/chatgpt_reports_fa.json';
        if(is_file($faPath)){
            if(is_link($faPath)||!is_readable($faPath))throw new RuntimeException('unsafe Persian report pack');
            $faStat=lstat($faPath);
            if($faStat===false||!is_int($faStat['size'])||$faStat['size']<32||
               $faStat['size']>100000||(((int)$faStat['mode'])&0077)!==0){
                throw new RuntimeException('invalid Persian pack metadata');
            }
            $faRaw=file_get_contents($faPath);
            if($faRaw===false||strlen($faRaw)!==$faStat['size'])throw new RuntimeException('short Persian pack read');
            $faPayload=json_decode($faRaw,true,32,JSON_THROW_ON_ERROR);
            $faItems=$faPayload['items']??null;
            if(!is_array($faPayload)||($faPayload['version']??null)!==1||
               ($faPayload['source']??'')!==$payload['source']||
               ($faPayload['kind']??'')!=='persian_management_rendering'||
               !is_array($faItems)||count($faItems)>100){
                throw new RuntimeException('invalid Persian report pack');
            }
            foreach($faItems as $faCode=>$fa){
                if(!is_string($faCode)||!preg_match('/^[0-9]{2}-[0-9]{4,8}$/D',$faCode)||
                   !is_array($fa)||!is_int($fa['comment_id']??null)||($fa['comment_id']??0)<1||
                   !is_string($fa['text_fa']??null)||strlen($fa['text_fa'])<20||
                   strlen($fa['text_fa'])>8000||!preg_match('/[\x{0600}-\x{06FF}]/u',$fa['text_fa'])){
                    throw new RuntimeException('invalid Persian report entry');
                }
                $faRows[$faCode]=$fa;
            }
        }
        echo '<p class="notice">گزارش شماره‌دار قابل مشاهده: '.count($rows).' · بررسی مستقل محتوای ادعاها انجام نشده است.</p>';
        // Exact receipt coverage, not a claim that the five automations ran.
        // Other-cycle reports stay explicitly unverified until a source is connected.
        $cycleNames=['01'=>'مقالات علمی','02'=>'کتاب‌ها','03'=>'کارخانه و فروشگاه‌ها','04'=>'بازی‌ها','05'=>'فرماندهی کسب‌وکار'];
        $coverage=[];
        foreach($cycleNames as $key=>$name)$coverage[$key]=['count'=>0,'latest'=>'—'];
        foreach($rows as $row){
            $key=substr($row['report_code'],0,2);
            if(isset($coverage[$key])){
                $coverage[$key]['count']++;
                $coverage[$key]['latest']=$row['report_code'].' · '.$row['occurred_at'];
            }
        }
        echo '<section><h3>پایش پنج چرخهٔ ساعتی</h3>';
        echo '<p class="muted">این جدول تعداد گزارش‌های دریافت‌شده را می‌شمارد، نه تعداد اقدامات یا عملکرد تأییدشده. هدف چرخهٔ پنجم ۲۰ اقدام واقعی در هر اجراست؛ شمارش تحقق آن مستلزم بررسی مستقل مدارک است.</p>';
        echo '<div class="scroll"><table><tr><th>چرخه</th><th>گزارش ثبت‌شده</th><th>آخرین رسید معتبر</th><th>هدف اقدامات</th></tr>';
        foreach($cycleNames as $key=>$name){
            $data=$coverage[$key];
            echo '<tr><td>'.esc($key.' · '.$name).'</td><td>'.(int)$data['count'].'</td><td>'.esc($data['latest']).'</td><td>'.($key==='05'?'۲۰ اقدام / تحقق احرازنشده':'—').'</td><td>'.($key==='05'?'دفتر مدیریتی ۰۵ · متصل':'فاقد اتصال خودکار و خصوصی').'</td></tr>';
        }
        echo '</table></div>';
        echo '<p class="muted">آخرین تغییر پرونده گزارش روی هاست: '.esc(gmdate('Y-m-d H:i', (int)$stat['mtime'])).' UTC؛ ظرفیت این نسخه از نمای گزارش ۱۰۰ رسید است.</p></section>';
        if(!$rows)echo '<p>گزارش قابل نمایش وجود ندارد.</p>';
        foreach(array_reverse($rows) as $row){
            echo '<article class="card"><h3>'.esc($row['report_code']).'</h3><p class="muted">زمان ثبت‌شده: '.esc($row['occurred_at']).'</p>';
            $fa=$faRows[$row['report_code']]??null;
            if($fa!==null && $fa['comment_id']!==$row['comment_id']){
                throw new RuntimeException('Persian receipt does not match original');
            }
            $visible=$fa!==null?$fa['text_fa']:$row['body'];
            if($fa===null){
                preg_match_all('/[\x{0600}-\x{06FF}]/u',$row['body'],$persianChars);
                preg_match_all('/[A-Za-z]/',$row['body'],$latinChars);
                if(count($latinChars[0])>count($persianChars[0])){
                    $visible='ترجمه فارسی این گزارش هنوز تأیید و نصب نشده است. متن اصلی از پیوند مدرک اولیه در دسترس است.';
                }
            }
            echo '<details open><summary>متن گزارش به فارسی</summary><p lang="fa" dir="rtl" style="white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.9">'.esc($visible).'</p></details>';
            echo '<p><a href="'.esc($row['evidence_url']).'" target="_blank" rel="noopener noreferrer">مشاهده مدرک اولیه در GitHub</a></p></article>';
        }
    }catch(Throwable $e){
        error_log('ZM REPORT SNAPSHOT REJECTED ['.get_class($e).']');
        echo '<div class="notice danger">اعتبارسنجی پرونده گزارش ناموفق بود؛ نمایش داده‌ها متوقف شد.</div>';
    }
    echo '</section>';
}


/**
 * Paginated, non-financial, read-only archive. The legacy JSON remains an
 * immutable compatibility snapshot of the earliest 100 validated receipts.
 */
function zmBusinessChatgptReportsArchive(string $private):bool {
    $path=$private.'/chatgpt_reports_archive.sqlite3';
    if(!file_exists($path) && !is_link($path))return false;
    echo '<section lang="fa" dir="rtl"><h2>گزارش‌های متنی اقدامات ChatGPT</h2>';
    echo '<p class="muted">آرشیو شماره‌دار، قابل صفحه‌بندی و فقط برای مدیرکل. متن گزارش اثبات مستقل اجرای کار، پرداخت یا درآمد نیست.</p>';
    try {
        if(is_link($private)||is_link($path)||!is_file($path)||!is_readable($path)||!class_exists('SQLite3'))throw new RuntimeException('unsafe report archive');
        $stat=lstat($path);
        if($stat===false||!is_int($stat['size'])||$stat['size']<4096||$stat['size']>500000000||(((int)$stat['mode'])&0077)!==0){
            throw new RuntimeException('invalid report archive metadata');
        }
        $db=new SQLite3($path,SQLITE3_OPEN_READONLY);
        $db->busyTimeout(1500);
        if((int)$db->querySingle('PRAGMA user_version')!==1||
           $db->querySingle("SELECT value FROM metadata WHERE name='source'")!=='github:mojtabarozegar11-ship-it/Saeit:issue:1725'){
            throw new RuntimeException('invalid report archive identity');
        }
        $mainTotal=(int)$db->querySingle('SELECT COUNT(*) FROM reports');
        if($mainTotal<0||$mainTotal>100000)throw new RuntimeException('invalid report archive count');
        $publicDb=null;
        $publicPath=$private.'/chatgpt_reports_public_cycles.sqlite3';
        if(is_file($publicPath)||is_link($publicPath)){
            if(is_link($publicPath)||!is_readable($publicPath))throw new RuntimeException('unsafe public-cycle archive');
            $pubStat=lstat($publicPath);
            if($pubStat===false||!is_int($pubStat['size'])||$pubStat['size']<4096||
               $pubStat['size']>500000000||(((int)$pubStat['mode'])&0077)!==0){
                throw new RuntimeException('invalid public-cycle archive permissions');
            }
            $publicDb=new SQLite3($publicPath,SQLITE3_OPEN_READONLY);
            $publicDb->busyTimeout(1500);
            if((int)$publicDb->querySingle('PRAGMA user_version')!==1||
               $publicDb->querySingle("SELECT value FROM metadata WHERE name='source'")!=='github:mojtabarozegar11-ship-it/Saeit:issue:1514'){
                throw new RuntimeException('invalid public-cycle source identity');
            }
        }
        $cycle=$_GET['cycle']??'05';
        if(!is_string($cycle)||!in_array($cycle,['01','02','03','04','05'],true))throw new RuntimeException('invalid report cycle');
        $activeDb=$cycle==='05'?$db:$publicDb;
        $total=0;
        if($activeDb!==null){
            $countQuery=$activeDb->prepare("SELECT COUNT(*) FROM reports WHERE substr(report_code,1,2)=:cycle");
            if($countQuery===false)throw new RuntimeException('invalid cycle count preparation');
            $countQuery->bindValue(':cycle',$cycle,SQLITE3_TEXT);
            $countRow=$countQuery->execute();
            if($countRow===false)throw new RuntimeException('cycle count failed');
            $total=(int)$countRow->fetchArray(SQLITE3_NUM)[0];
        }
        if($total<0||$total>100000)throw new RuntimeException('invalid report cycle count');
        $checked=$db->querySingle("SELECT value FROM metadata WHERE name='last_checked_at'");
        if(!is_string($checked)||strlen($checked)>48)throw new RuntimeException('invalid refresh timestamp');
        $checkedTime=strtotime($checked);
        if($checkedTime===false||$checkedTime>time()+300)throw new RuntimeException('invalid refresh clock');
        $age=max(0,time()-$checkedTime);
        $pageRaw=$_GET['p']??'1';
        if(!is_string($pageRaw)||!preg_match('/^[1-9][0-9]{0,4}$/D',$pageRaw))throw new RuntimeException('invalid page');
        $page=(int)$pageRaw;
        $pageCount=max(1,(int)ceil($total/25));
        if($page>$pageCount)throw new RuntimeException('page outside archive');
        $faRows=[];
        $faPath=$private.'/chatgpt_reports_fa.json';
        if(is_file($faPath)){
            if(is_link($faPath)||!is_readable($faPath))throw new RuntimeException('unsafe Persian translations');
            $faStat=lstat($faPath);
            if($faStat===false||!is_int($faStat['size'])||$faStat['size']<32||$faStat['size']>100000||(((int)$faStat['mode'])&0077)!==0)throw new RuntimeException('invalid Persian translation metadata');
            $faPayload=json_decode((string)file_get_contents($faPath),true,32,JSON_THROW_ON_ERROR);
            if(!is_array($faPayload)||($faPayload['source']??'')!=='github:mojtabarozegar11-ship-it/Saeit:issue:1725'||($faPayload['version']??null)!==1||($faPayload['kind']??'')!=='persian_management_rendering'||!is_array($faPayload['items']??null)||count($faPayload['items'])>100)throw new RuntimeException('invalid Persian translations');
            $faRows=$faPayload['items'];
        }
        $publicFaRows=[];
        $publicFaPath=$private.'/chatgpt_reports_public_fa.json';
        if(is_file($publicFaPath)||is_link($publicFaPath)){
            if(is_link($publicFaPath)||!is_readable($publicFaPath))throw new RuntimeException('unsafe public translations');
            $publicFaStat=lstat($publicFaPath);
            if($publicFaStat===false||!is_int($publicFaStat['size'])||$publicFaStat['size']<64||$publicFaStat['size']>200000||(((int)$publicFaStat['mode'])&0077)!==0)throw new RuntimeException('invalid public translation permissions');
            $publicFaPayload=json_decode((string)file_get_contents($publicFaPath),true,32,JSON_THROW_ON_ERROR);
            if(!is_array($publicFaPayload)||($publicFaPayload['source']??'')!=='github:mojtabarozegar11-ship-it/Saeit:issue:1514'||($publicFaPayload['version']??null)!==1||($publicFaPayload['kind']??'')!=='persian_public_cycle_summaries'||!is_array($publicFaPayload['items']??null)||count($publicFaPayload['items'])>100)throw new RuntimeException('invalid public translation metadata');
            $publicFaRows=$publicFaPayload['items'];
        }
        echo '<p class="notice">تعداد گزارش‌های بایگانی‌شده: '.$total.' · صفحه '.$page.' از '.$pageCount.' · راستی‌آزمایی مستقل محتوا انجام نشده است.</p>';
        echo '<p class="muted">آخرین دریافت منبع: '.esc(gmdate('Y-m-d H:i',(int)$checkedTime)).' UTC · تأخیر: '.(int)floor($age/60).' دقیقه</p>';
        if($age>7200)echo '<div class="notice danger">هشدار: از آخرین دریافت موفق گزارش بیش از دو ساعت گذشته است؛ وضعیت اجراکنندهٔ ساعتی باید بررسی شود.</div>';
        if($publicDb!==null){
            $publicChecked=$publicDb->querySingle("SELECT value FROM metadata WHERE name='last_checked_at'");
            $publicCheckedTime=is_string($publicChecked)?strtotime($publicChecked):false;
            if($publicCheckedTime===false||$publicCheckedTime>time()+300)throw new RuntimeException('invalid public-cycle refresh timestamp');
            $publicAge=max(0,time()-$publicCheckedTime);
            echo '<p class="muted">آخرین دریافت چرخه‌های ۰۱، ۰۲ و ۰۴: '.esc(gmdate('Y-m-d H:i',(int)$publicCheckedTime)).' UTC</p>';
            if($publicAge>7200)echo '<div class="notice danger">هشدار: دریافت گزارش چرخه‌های ۰۱، ۰۲ و ۰۴ بیش از دو ساعت به‌روزرسانی نشده است.</div>';
        }
        echo '<nav aria-label="انتخاب چرخه گزارش"><p>';
        $cycleLinks=['01'=>'مقالات','02'=>'کتاب‌ها','03'=>'فروشگاه و کارخانه','04'=>'بازی‌ها','05'=>'فرماندهی کسب‌وکار'];
        foreach($cycleLinks as $code=>$label){
            echo '<a href="?page=chatgpt_reports&amp;cycle='.esc($code).'">'.esc($code.' · '.$label).'</a>　';
        }
        echo '</p></nav>';

        $cycleNames=['01'=>'مقالات علمی','02'=>'کتاب‌ها','03'=>'کارخانه و فروشگاه‌ها','04'=>'بازی‌ها','05'=>'فرماندهی کسب‌وکار'];
        $coverage=[];
        foreach($cycleNames as $key=>$name)$coverage[$key]=['count'=>0,'latest'=>'—'];
        $counts=$db->query('SELECT substr(report_code,1,2) AS cycle,COUNT(*) AS n,MAX(seq) AS last_seq FROM reports GROUP BY substr(report_code,1,2)');
        if($counts===false)throw new RuntimeException('report count query failure');
        while($c=$counts->fetchArray(SQLITE3_ASSOC)){
            $key=(string)$c['cycle'];
            if(isset($coverage[$key])){
                $latest=$db->querySingle('SELECT report_code || " · " || occurred_at FROM reports WHERE seq='.(int)$c['last_seq']);
                $coverage[$key]=['count'=>(int)$c['n'],'latest'=>(string)$latest];
            }
        }
        if($publicDb!==null){
            $publicCounts=$publicDb->query('SELECT substr(report_code,1,2) AS cycle,COUNT(*) AS n,MAX(seq) AS last_seq FROM reports GROUP BY substr(report_code,1,2)');
            if($publicCounts===false)throw new RuntimeException('public cycle count query failed');
            while($c=$publicCounts->fetchArray(SQLITE3_ASSOC)){
                $key=(string)$c['cycle'];
                if(in_array($key,['01','02','04'],true)){
                    $latest=$publicDb->querySingle('SELECT report_code || " · " || occurred_at FROM reports WHERE seq='.(int)$c['last_seq']);
                    $coverage[$key]=['count'=>(int)$c['n'],'latest'=>(string)$latest];
                }
            }
        }
        echo '<section><h3>پایش پنج چرخهٔ ساعتی</h3><p class="muted">شمار گزارش‌ها از تعداد اقدامات واقعی متمایز است؛ هدف چرخه پنجم ۲۰ اقدام در هر اجراست، اما تحقق آن احراز نشده است.</p><div class="scroll"><table><tr><th>چرخه</th><th>تعداد گزارش</th><th>آخرین رسید</th><th>هدف</th><th>منبع چرخه</th></tr>';
        foreach($cycleNames as $key=>$name){
            $c=$coverage[$key];
            echo '<tr><td>'.esc($key.' · '.$name).'</td><td>'.(int)$c['count'].'</td><td>'.esc($c['latest']).'</td><td>'.($key==='05'?'۲۰ اقدام / تحقق احرازنشده':'—').'</td><td>'.($key==='05'?'متصل به دفتر مدیریت ۰۵':($publicDb!==null&&in_array($key,['01','02','04'],true)&&$c['count']>0?'دفتر عمومی ۱۵۱۴ · متصل':'فاقد اتصال خودکار و خصوصی')).'</td></tr>';
        }
        echo '</table></div></section>';
        zmBusinessCommandCenter($db,$private);
        if($total===0)echo '<p>برای این چرخه هنوز گزارش شماره‌دار از منبع معتبر دریافت نشده است.</p>';
        $limit=25;
        $offset=($page-1)*$limit;
        $stmt=$activeDb!==null?$activeDb->prepare('SELECT report_code,comment_id,occurred_at,body,evidence_url FROM reports WHERE substr(report_code,1,2)=:cycle ORDER BY seq DESC LIMIT :limit OFFSET :offset'):null;
        if($activeDb!==null && $stmt===false)throw new RuntimeException('report page preparation failure');
        if($stmt!==null){
            $stmt->bindValue(':cycle',$cycle,SQLITE3_TEXT);
            $stmt->bindValue(':limit',$limit,SQLITE3_INTEGER);
            $stmt->bindValue(':offset',$offset,SQLITE3_INTEGER);
        }
        $result=$stmt!==null?$stmt->execute():null;
        if($stmt!==null && $result===false)throw new RuntimeException('report page query failure');
        while($result!==null && ($r=$result->fetchArray(SQLITE3_ASSOC))){
            $code=$r['report_code'];$id=(int)$r['comment_id'];$body=$r['body'];
            if(!is_string($code)||!preg_match('/^[0-9]{2}-[0-9]{4,8}$/D',$code)||$id<1||
               !is_string($body)||strlen($body)<20||strlen($body)>32000||
               $r['evidence_url']!=='https://github.com/mojtabarozegar11-ship-it/Saeit/issues/'.($cycle==='05'?'1725':'1514').'#issuecomment-'.$id){
                throw new RuntimeException('invalid archived report');
            }
            $displayBody=zmBusinessReportVisibleFa($body,$code);
            $visible=$displayBody;
            $translations=$cycle==='05'?$faRows:$publicFaRows;
            $hasPersianSummary=$cycle!=='05'&&isset($translations[$code]);
            if(isset($translations[$code])){
                $fa=$translations[$code];
                if(!is_array($fa)||($fa['comment_id']??null)!==$id||!is_string($fa['text_fa']??null)||strlen($fa['text_fa'])<20||strlen($fa['text_fa'])>8000)throw new RuntimeException('invalid translation association');
                $visible=$fa['text_fa'];
            }else{
                preg_match_all('/[\x{0600}-\x{06FF}]/u',$displayBody,$faChars);
                preg_match_all('/[A-Za-z]/',$displayBody,$latinChars);
                if(count($latinChars[0])>count($faChars[0]))$visible='ترجمه فارسی این گزارش هنوز تأیید نشده است. متن اولیه در پیوند مدرک قابل مشاهده است.';
            }
            echo '<article class="card"><h3>'.esc($code).'</h3><p class="muted">زمان ثبت: '.esc($r['occurred_at']).'</p><details open><summary>'.($hasPersianSummary?'خلاصهٔ فارسی مستند از گزارش':'متن فارسی گزارش').'</summary><p lang="fa" dir="rtl" style="white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.9">'.esc($visible).'</p></details><p><a href="'.esc($r['evidence_url']).'" target="_blank" rel="noopener noreferrer">مشاهده مدرک اولیه در GitHub</a></p></article>';
        }
        if($pageCount>1){
            echo '<nav aria-label="صفحه‌بندی گزارش‌ها"><p>';
            if($page>1)echo '<a href="?page=chatgpt_reports&amp;cycle='.esc($cycle).'&amp;p='.($page-1).'">صفحه جدیدتر</a> ';
            if($page<$pageCount)echo '<a href="?page=chatgpt_reports&amp;cycle='.esc($cycle).'&amp;p='.($page+1).'">صفحه قدیمی‌تر</a>';
            echo '</p></nav>';
        }
        if($publicDb!==null)$publicDb->close();
        $db->close();
    }catch(Throwable $e){
        error_log('ZM REPORT ARCHIVE REJECTED ['.get_class($e).']');
        echo '<div class="notice danger">اعتبارسنجی آرشیو ناموفق بود؛ گزارش نامعتبر نمایش داده نشد.</div>';
    }
    echo '</section>';
    return true;
}
