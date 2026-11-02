<?php
declare(strict_types=1);
/**
 * Private text report viewer for the existing authenticated PHP business desk.
 * No direct entrypoint: this script is only called from app.php *after* the
 * currently active role is re-read from the existing company user database.
 */
function zmBusinessChatgptReports(string $private):void {
    if(role()!=='admin')bail('دسترسی فقط برای مدیرکل مجاز است.',403);
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
            echo '<tr><td>'.esc($key.' · '.$name).'</td><td>'.(int)$data['count'].'</td><td>'.esc($data['latest']).'</td><td>'.($key==='05'?'۲۰ اقدام / تحقق احرازنشده':'—').'</td></tr>';
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
