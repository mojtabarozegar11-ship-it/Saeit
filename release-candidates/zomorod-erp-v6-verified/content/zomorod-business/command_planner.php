<?php
declare(strict_types=1);
/**
 * Deterministic, read-only operations planner for Zomorod company tasks.
 * A proposed next action is not evidence of execution.
 * This module cannot schedule, pay, execute, or change a task.
 */
function zmCcOpsSnapshot(PDO $control, string $today): array {
    if (!preg_match('/^\d{4}-\d{2}-\d{2}$/D', $today)) {
        throw new InvalidArgumentException('Invalid reporting date');
    }
    $counts = [
        'queued'=>0,'in_progress'=>0,'blocked'=>0,
        'awaiting_review'=>0,'missing_plan'=>0,'needs_evidence'=>0,
        'high_impact'=>0,'stale'=>0
    ];
    $query = "SELECT t.id,t.title,t.workstream,t.priority,t.state,t.created_at,t.updated_at,
                     q.risk,q.review_state
              FROM tasks t LEFT JOIN task_quality q ON q.task_id=t.id
              WHERE t.state IN ('queued','in_progress','blocked')
              ORDER BY CASE t.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END,
                       CASE t.state WHEN 'blocked' THEN 0 WHEN 'in_progress' THEN 1 ELSE 2 END,
                       t.id ASC LIMIT 200";
    $rows = q($control,$query);
    $items=[];
    foreach ($rows as $row) {
        $state=(string)$row['state'];
        $counts[$state]++;
        $review=$row['review_state'];
        $risk=$row['risk'];
        $action='';
        $label='';
        if($review===null){
            $counts['missing_plan']++;
            $action='ثبت خروجی مورد انتظار، طبقه ریسک و معیار پذیرش';
            $label='فاقد برنامهٔ کنترل کیفیت';
        } elseif ($state==='blocked') {
            $action='بررسی مانع و ثبت نتیجهٔ قابل پیگیری';
            $label='نیازمند رفع مانع';
        } elseif ($review==='submitted') {
            $counts['awaiting_review']++;
            $action='بررسی دستی مستندات و ثبت تأیید یا رد';
            $label='در انتظار داوری';
        } elseif ($review==='rejected') {
            $action='اصلاح خروجی و ارسال مدرک جدید';
            $label='بازکاری';
        } elseif ($review==='planned') {
            $counts['needs_evidence']++;
            $action=$state==='queued'?'آغاز پیگیری طبق برنامهٔ ثبت‌شده':'تحویل شواهد قابل راستی‌آزمایی';
            $label='در انتظار اجرا یا شواهد';
        } elseif ($review==='approved') {
            $action='بررسی نهایی و بستن وظیفه با ثبت نتیجه';
            $label='تأییدشده، آمادهٔ جمع‌بندی';
        }
        if($risk==='high_impact')$counts['high_impact']++;
        $last=substr((string)$row['updated_at'],0,10);
        $age=($last!=='' && preg_match('/^\d{4}-\d{2}-\d{2}$/D',$last))?
            (int)((strtotime($today.' 00:00:00 UTC')-strtotime($last.' 00:00:00 UTC'))/86400):0;
        if($age>=7){$counts['stale']++;}
        $score=($row['priority']==='critical'?60:($row['priority']==='high'?40:20));
        if($state==='blocked')$score+=10;
        if($review==='submitted')$score+=20;
        if($review===null)$score+=8;
        if($age>=7)$score+=8;
        $items[]=[
            'id'=>(int)$row['id'],
            'title'=>(string)$row['title'],
            'workstream'=>(string)$row['workstream'],
            'priority'=>(string)$row['priority'],
            'state'=>$state,
            'review'=>(string)($review??'missing'),
            'risk'=>(string)($risk??'unclassified'),
            'action'=>$action,
            'label'=>$label,
            'age'=>max(0,$age),
            'score'=>$score,
        ];
    }
    usort($items,static fn($a,$b) => ($b['score'] <=> $a['score']) ?: ($a['id'] <=> $b['id']));
    return ['counts'=>$counts,'items'=>array_slice($items,0,15),'examined'=>count($rows),'capped'=>count($rows)===200];
}
function zmCcOpsRender(PDO $control): void {
    zmCcRequireAdmin();
    $snapshot=zmCcOpsSnapshot($control,gmdate('Y-m-d'));
    $c=$snapshot['counts'];
    echo '<section><h2>برنامه‌ریز عملیاتی مدیرعامل</h2>';
    echo '<p class="muted">این اولویت‌بندی بر اساس وضعیت و قواعد شفاف انجام می‌شود و جایگزین تشخیص مدیر یا بررسی شواهد نیست. پیشنهاد به‌معنای اجرای عملیات نیست.</p>';
    echo '<div class="grid">';
    $metrics=[
        'در صف'=>$c['queued'],
        'در حال پیگیری'=>$c['in_progress'],
        'متوقف'=>$c['blocked'],
        'منتظر داوری'=>$c['awaiting_review'],
        'بدون برنامهٔ کیفیت'=>$c['missing_plan'],
        'بدون مدرک کامل'=>$c['needs_evidence'],
        'دارای ریسک بالا'=>$c['high_impact'],
        'بدون تغییر طی ۷ روز'=>$c['stale'],
    ];
    foreach($metrics as $name=>$value){
        echo '<div class="card"><div class="metric">'.(int)$value.'</div><h3>'.esc($name).'</h3></div>';
    }
    echo '</div><h3>اقدام‌های پیشنهادی اولویت‌دار</h3>';
    echo '<div class="scroll"><table><thead><tr><th>شناسه</th><th>کار</th><th>اولویت</th><th>وضعیت کنترل</th><th>اقدام پیشنهادی</th></tr></thead><tbody>';
    foreach($snapshot['items'] as $row) {
        echo '<tr><td>'.(int)$row['id'].'</td><td>'.esc($row['title']).'</td><td>'.esc($row['priority']).'</td><td>'.esc($row['label']).'</td><td>'.esc($row['action']).'</td></tr>';
    }
    if(!$snapshot['items'])echo '<tr><td colspan="5">فعلاً وظیفهٔ باز برای اولویت‌بندی وجود ندارد.</td></tr>';
    echo '</tbody></table></div>';
    if($snapshot['capped'])echo '<p class="muted">بررسی به ۲۰۰ وظیفهٔ فعال محدود است؛ برای گزارش کامل به صفحهٔ وظایف مراجعه کنید.</p>';
    echo '<p class="muted">ثبت و به‌روزرسانی وظایف فقط در فرم‌های خصوصی پایین صفحه انجام می‌شود. هیچ زمان‌بندی دوره‌ای فعال نیست.</p></section>';
}
