<?php
declare(strict_types=1);
/**
 * Private text report viewer for the existing authenticated PHP business desk.
 * No direct entrypoint: this script is only called from app.php *after* the
 * currently active role is re-read from the existing company user database.
 */
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
               !is_string($body)||strlen($body)<20||strlen($body)>8000||
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
               !is_string($body)||strlen($body)<20||strlen($body)>8000||
               $r['evidence_url']!=='https://github.com/mojtabarozegar11-ship-it/Saeit/issues/'.($cycle==='05'?'1725':'1514').'#issuecomment-'.$id){
                throw new RuntimeException('invalid archived report');
            }
            $visible=$body;
            if(isset($faRows[$code])){
                $fa=$faRows[$code];
                if(!is_array($fa)||($fa['comment_id']??null)!==$id||!is_string($fa['text_fa']??null)||strlen($fa['text_fa'])<20||strlen($fa['text_fa'])>8000)throw new RuntimeException('invalid translation association');
                $visible=$fa['text_fa'];
            }else{
                preg_match_all('/[\x{0600}-\x{06FF}]/u',$body,$faChars);
                preg_match_all('/[A-Za-z]/',$body,$latinChars);
                if(count($latinChars[0])>count($faChars[0]))$visible='ترجمه فارسی این گزارش هنوز تأیید نشده است. متن اولیه در پیوند مدرک قابل مشاهده است.';
            }
            echo '<article class="card"><h3>'.esc($code).'</h3><p class="muted">زمان ثبت: '.esc($r['occurred_at']).'</p><details open><summary>متن فارسی گزارش</summary><p lang="fa" dir="rtl" style="white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.9">'.esc($visible).'</p></details><p><a href="'.esc($r['evidence_url']).'" target="_blank" rel="noopener noreferrer">مشاهده مدرک اولیه در GitHub</a></p></article>';
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
