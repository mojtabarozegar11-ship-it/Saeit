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
    echo '<section><h2>گزارش‌های متنی اقدامات ChatGPT</h2>';
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
        echo '<p class="notice">گزارش شماره‌دار قابل مشاهده: '.count($rows).' · بررسی مستقل محتوای ادعاها انجام نشده است.</p>';
        if(!$rows)echo '<p>گزارش قابل نمایش وجود ندارد.</p>';
        foreach(array_reverse($rows) as $row){
            echo '<article class="card"><h3>'.esc($row['report_code']).'</h3><p class="muted">زمان ثبت‌شده: '.esc($row['occurred_at']).'</p>';
            echo '<details><summary>متن کامل گزارش</summary><p style="white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.9">'.esc($row['body']).'</p></details>';
            echo '<p><a href="'.esc($row['evidence_url']).'" target="_blank" rel="noopener noreferrer">مشاهده مدرک اولیه در GitHub</a></p></article>';
        }
    }catch(Throwable $e){
        error_log('ZM REPORT SNAPSHOT REJECTED ['.get_class($e).']');
        echo '<div class="notice danger">اعتبارسنجی پرونده گزارش ناموفق بود؛ نمایش داده‌ها متوقف شد.</div>';
    }
    echo '</section>';
}
