<?php
declare(strict_types=1);
/**
 * Private read-only project portfolio analytics; no project, finance, or task writes.
 * All input is prevalidated and all output is escaped.
 */
function zmPortfolioRender(PDO $db):void {
    authorize('view');
    $today=today();
    $byState=['planned'=>0,'active'=>0,'paused'=>0,'done'=>0];
    $forecast=[];
    foreach(q($db,'SELECT state,COUNT(*) AS n,COALESCE(SUM(budget),0) AS budget FROM projects GROUP BY state') as $row){
        if(array_key_exists($row['state'],$byState)){
            $byState[$row['state']]=(int)$row['n'];
            $forecast[$row['state']]=(int)$row['budget'];
        }
    }
    $total=array_sum($byState);
    $rejected=(int)one($db,"SELECT COUNT(*) FROM projects WHERE title LIKE '%| ردشده -%'");
    $approved=(int)one($db,"SELECT COUNT(*) FROM projects WHERE title LIKE '%| مصوب |%'");
    $uncategorized=max(0,$total-$rejected-$approved);
    $linkedProjects=(int)one($db,'SELECT COUNT(DISTINCT project_id) FROM zm_project_links');
    $allLinks=(int)one($db,'SELECT COUNT(*) FROM zm_project_links');
    $withMilestones=(int)one($db,'SELECT COUNT(DISTINCT project_id) FROM zm_project_milestones');
    $openMilestones=(int)one($db,"SELECT COUNT(*) FROM zm_project_milestones WHERE state NOT IN ('done','cancelled')");
    $overdue=(int)one($db,"SELECT COUNT(*) FROM zm_project_milestones WHERE state NOT IN ('done','cancelled') AND due_date<?",[$today]);
    $blocked=(int)one($db,"SELECT COUNT(*) FROM zm_project_milestones WHERE state='blocked'");
    $assignedOpen=(int)one($db,"SELECT COUNT(*) FROM zm_project_milestones m JOIN zm_project_milestone_assignments a ON a.milestone_id=m.id WHERE m.state NOT IN ('done','cancelled')");
    $unassignedOpen=max(0,$openMilestones-$assignedOpen);
    $updateCount=(int)one($db,'SELECT COUNT(*) FROM zm_project_updates');
    $pendingApprovals=(int)one($db,"SELECT COUNT(*) FROM zm_project_approval_cases WHERE status='submitted'");
    $recordedExecutionDecisions=(int)one($db,"SELECT COUNT(DISTINCT project_id) FROM zm_project_approval_cases WHERE kind='execution' AND status='approved'");
    $statusChanges=(int)one($db,'SELECT COUNT(*) FROM zm_project_events');
    $sourceCounts=q($db,'SELECT source,COUNT(*) AS total,COUNT(DISTINCT project_id) AS projects FROM zm_project_links GROUP BY source ORDER BY total DESC,source');
    $withLinksAndDue=q($db,"SELECT p.id,p.title,p.state,p.owner,
        (SELECT COUNT(*) FROM zm_project_links l WHERE l.project_id=p.id) AS linked,
        (SELECT COUNT(*) FROM zm_project_milestones m WHERE m.project_id=p.id AND m.state NOT IN ('done','cancelled')) AS open_count,
        (SELECT COUNT(*) FROM zm_project_milestones m WHERE m.project_id=p.id AND m.state NOT IN ('done','cancelled') AND m.due_date<?) AS overdue,
        (SELECT MAX(progress_pct) FROM zm_project_updates u WHERE u.project_id=p.id AND u.category='progress') AS claimed_max
        FROM projects p WHERE EXISTS(SELECT 1 FROM zm_project_links l WHERE l.project_id=p.id)
        OR EXISTS(SELECT 1 FROM zm_project_milestones m WHERE m.project_id=p.id)
        ORDER BY overdue DESC,open_count DESC,p.id DESC LIMIT 100",[$today]);
    $unresolved=q($db,"SELECT m.id,m.project_id,p.title AS project_title,m.title,m.due_date,m.state
        FROM zm_project_milestones m JOIN projects p ON p.id=m.project_id
        WHERE m.state NOT IN ('done','cancelled') AND m.due_date<?
        ORDER BY m.due_date,m.id LIMIT 60",[$today]);
    $labels=['planned'=>'برنامه‌ریزی‌شده','active'=>'فعال ثبت‌شده','paused'=>'متوقف','done'=>'خاتمه اداری ثبت‌شده'];
    $sources=function_exists('zmPiSources')?zmPiSources():[];
    echo '<section><h2>گزارش جامع سبد پروژه‌های زمرد ملل</h2>';
    echo '<p class="muted">آخرین بازخوانی: '.esc($today).'، ساعت ایران. گزارش از داده‌های واقعی دفتر پروژه استخراج می‌شود. بودجه صرفاً پیشنهادی است و هیچ هزینه یا اشتغالی از آن استنباط نمی‌شود.</p>';
    echo '<div class="grid">';
    foreach(['کل پرونده‌ها'=>$total,'مصوب در متن مصوبه'=>$approved,'ردشده؛ فقط بایگانی'=>$rejected,'بدون برچسب قطعی مصوبه'=>$uncategorized,'دارای ارتباط مستند'=>$linkedProjects,'فاقد ارتباط ثبت‌شده'=>max(0,$total-$linkedProjects),'دارای زمان‌بندی'=>$withMilestones,'اقدامات باز'=>$openMilestones,'اقدامات معوق'=>$overdue,'اقدامات مسدود'=>$blocked,'اقدامات باز دارای مسئول'=>$assignedOpen,'اقدامات باز فاقد مسئول'=>$unassignedOpen,'درخواست تصویب در انتظار'=>$pendingApprovals,'پروژه دارای تصمیم اجرای ثبت‌شده'=>$recordedExecutionDecisions,'گزارش‌های پیشرفت و موانع'=>$updateCount] as $label=>$count)
        echo '<div class="card"><div class="metric">'.(int)$count.'</div><h3>'.esc($label).'</h3></div>';
    echo '</div><p><a href="?page=projects">جست‌وجو و مدیریت پروژه‌ها</a> · <a href="?page=project_links">پرونده یکپارچه</a> · <a href="?page=project_calendar">تقویم پروژه‌ها</a> · <a href="?page=project_assignments">کارتابل مسئولان</a> · <a href="?page=project_governance">مصوبات و مستندات پروژه‌ها</a>';
    if(in_array(role(),['admin','accountant'],true))echo ' · <a href="?page=project_finance">گزارش مالی پروژه‌ها</a>';
    echo '</p></section>';
    echo '<p class="muted">مصوب و ردشده از برچسب صریح پرونده استخراج می‌شوند؛ وضعیت برنامه‌ریزی یا توقف به تنهایی ملاک مصوبه نیست.</p>';
    // Read-only provenance crosswalk. A matched plan code is not a subsystem link
    // and cannot authorize execution, expense, hiring, or milestone completion.
    $crosswalkError='';
    $crosswalk=null;
    $snapshotPath=__DIR__.'/approvals_snapshot.json';
    if(!is_file($snapshotPath)||is_link($snapshotPath)||!is_readable($snapshotPath)){
        $crosswalkError='فایل منبع خصوصی دفتر مصوبات در دسترس نیست.';
    }else{
        $snapshotSize=filesize($snapshotPath);
        $snapshotRaw=$snapshotSize!==false&&$snapshotSize>0&&$snapshotSize<=2000000?file_get_contents($snapshotPath):false;
        $snapshot=$snapshotRaw!==false?json_decode($snapshotRaw,true,16):null;
        if(!is_array($snapshot)||($snapshot['version']??null)!==1||!isset($snapshot['items'])
            ||!is_array($snapshot['items'])||count($snapshot['items'])<1||count($snapshot['items'])>1000){
            $crosswalkError='نسخه یا ساختار دفتر مصوبات معتبر نیست؛ تطبیق نمایش داده نمی‌شود.';
        }else{
            $plans=[];
            $allowedDecisions=['approved'=>true,'rejected'=>true,'undetermined'=>true];
            foreach($snapshot['items'] as $item){
                $key=is_array($item)?($item['external_key']??null):null;
                $decision=is_array($item)?($item['decision']??null):null;
                if(!is_string($key)||!preg_match('/^ZM-[A-Z0-9-]{2,40}$/D',$key)
                    ||!is_string($decision)||!isset($allowedDecisions[$decision])||isset($plans[$key])){
                    $crosswalkError='شناسه تکراری یا ردیف نامعتبر در دفتر مصوبات؛ تطبیق متوقف شد.';
                    break;
                }
                $plans[$key]=$decision;
            }
            if($crosswalkError===''){
                $planProjects=[];
                $unregisteredProjects=[];
                foreach(q($db,'SELECT id,title FROM projects ORDER BY id') as $projectRow){
                    $title=(string)$projectRow['title'];
                    $prefix=trim(explode('|',$title,2)[0]);
                    if(preg_match('/^ZM-[A-Z0-9-]{2,40}$/D',$prefix)){
                        if(!isset($planProjects[$prefix]))$planProjects[$prefix]=[];
                        $planProjects[$prefix][]=['id'=>(int)$projectRow['id'],'title'=>$title];
                    }else{
                        $unregisteredProjects[]=['id'=>(int)$projectRow['id'],'title'=>$title];
                    }
                }
                $matched=[];
                $missing=[];
                $contradictions=[];
                $duplicateProjects=[];
                $undetermined=0;
                foreach($plans as $key=>$decision){
                    if($decision==='undetermined')$undetermined++;
                    if(!isset($planProjects[$key])){
                        $missing[]=$key;
                        continue;
                    }
                    if(count($planProjects[$key])!==1){
                        $duplicateProjects[]=$key;
                        continue;
                    }
                    $projectRow=$planProjects[$key][0];
                    $title=$projectRow['title'];
                    $approvedLabel=(bool)preg_match('/\|\s*مصوب\s*\|/u',$title);
                    $rejectedLabel=(bool)preg_match('/\|\s*ردشده(?:\s*[-|]|$)/u',$title);
                    if(($decision==='approved'&&!$approvedLabel)
                        ||($decision==='rejected'&&!$rejectedLabel)
                        ||($decision==='undetermined'&&($approvedLabel||$rejectedLabel))
                        ||($approvedLabel&&$rejectedLabel)){
                        $contradictions[]=$key;
                    }else{
                        $matched[]=$key;
                    }
                }
                $orphanCodes=array_values(array_diff(array_keys($planProjects),array_keys($plans)));
                $crosswalk=[
                    'plans'=>count($plans),'matched'=>count($matched),'missing'=>$missing,
                    'independent'=>$unregisteredProjects,'orphan'=>$orphanCodes,
                    'duplicate'=>$duplicateProjects,'conflict'=>$contradictions,
                    'undetermined'=>$undetermined
                ];
            }
        }
    }
    echo '<section><h2>تطبیق مستند مصوبات با پرونده‌های پروژه</h2>';
    echo '<p class="muted">مبنای تطبیق: شناسه یکتای طرح در دفتر مصوبات خصوصی و پیشوند عنوان پرونده. این تطبیق فقط شناسنامه طرح است، نه «ارتباط مستند» با زیرسامانه‌های عملیاتی، تأیید اجرا، استخدام یا پرداخت.</p>';
    if($crosswalk===null){
        echo '<p class="warn">'.esc($crosswalkError).'</p>';
    }else{
        echo '<div class="grid">';
        foreach([
            'ردیف‌های معتبر دفتر مصوبات'=>$crosswalk['plans'],
            'پرونده با برچسب و تصمیم منطبق'=>$crosswalk['matched'],
            'طرح فاقد پرونده'=>$crosswalk['missing']?count($crosswalk['missing']):0,
            'پرونده مستقل از دفتر شماره‌دار'=>count($crosswalk['independent']),
            'کد پرونده بدون سند متناظر'=>count($crosswalk['orphan']),
            'کد تکراری در پرونده‌ها'=>count($crosswalk['duplicate']),
            'تعارض برچسب و تصمیم رسمی'=>count($crosswalk['conflict']),
            'تصمیم رسمی هنوز نامشخص'=>$crosswalk['undetermined']
        ] as $label=>$count)
            echo '<div class="card"><div class="metric">'.(int)$count.'</div><h3>'.esc($label).'</h3></div>';
        echo '</div>';
        $anomalies=array_merge($crosswalk['missing'],$crosswalk['orphan'],$crosswalk['duplicate'],$crosswalk['conflict']);
        if($anomalies){
            echo '<p>شناسه‌های نیازمند بررسی: '.esc(implode('، ',array_unique($anomalies))).'</p>';
        }else{
            echo '<p class="muted">برای شناسه‌های دفتر مصوبات مغایرتی در تعداد پرونده‌ها یا برچسب تصمیم شناسایی نشد.</p>';
        }
        if($crosswalk['independent']){
            echo '<p class="muted">پرونده‌های مستقل بدون کد مصوبه شماره‌دار (بدون تغییر تصمیم یا وضعیت):</p><ul>';
            foreach(array_slice($crosswalk['independent'],0,20) as $independent)
                echo '<li><a href="?page=project_links&amp;project_id='.(int)$independent['id'].'">'.esc($independent['title']).'</a></li>';
            echo '</ul>';
        }
    }
    echo '</section>';
    echo '<section><h2>وضعیت‌های اداری و بودجه برنامه‌ای</h2><div class="scroll"><table><tr><th>وضعیت</th><th>پروژه</th><th>جمع بودجه پیشنهادی ریالی</th></tr>';
    foreach($byState as $key=>$n)
        echo '<tr><td>'.esc($labels[$key]).'</td><td>'.(int)$n.'</td><td>'.money($forecast[$key]??0).'</td></tr>';
    echo '</table></div><p class="muted">وضعیت «فعال» در سیستم فقط وضعیت اداری است؛ اثبات شروع واقعی عملیات نیست. تعداد رویدادهای تغییر وضعیت ثبت‌شده: '.$statusChanges.'.</p></section>';
    echo '<section><h2>پوشش ارتباطات با زیرسامانه‌ها</h2><div class="scroll"><table><tr><th>سامانه</th><th>تعداد ارتباطات واقعی</th><th>پروژه متصل</th></tr>';
    foreach($sourceCounts as $row){
        $name=$sources[$row['source']][0]??$row['source'];
        echo '<tr><td>'.esc($name).'</td><td>'.(int)$row['total'].'</td><td>'.(int)$row['projects'].'</td></tr>';
    }
    if(!$sourceCounts)echo '<tr><td colspan="3">هیچ ارتباطی ثبت نشده؛ ارتباط حدسی یا انتساب خودکار انجام نمی‌شود.</td></tr>';
    echo '</table></div><p>تعداد کل ارتباطات مستند: '.$allLinks.'</p></section>';
    echo '<section><h2>پروژه‌های دارای فعالیت ثبت‌شده</h2><p class="muted">تا ۱۰۰ پروژه دارای پیوند یا نقطه عطف. عدم نمایش پروژه‌های دیگر به معنی حذف آن‌ها نیست.</p>';
    echo '<div class="scroll"><table><tr><th>پروژه</th><th>وضعیت</th><th>پیوند</th><th>اقدام باز</th><th>معوق</th></tr>';
    foreach($withLinksAndDue as $r)
        echo '<tr><td><a href="?page=project_links&amp;project_id='.(int)$r['id'].'">'.esc($r['title']).'</a></td><td>'.esc($labels[$r['state']]??$r['state']).'</td><td>'.(int)$r['linked'].'</td><td>'.(int)$r['open_count'].'</td><td>'.(int)$r['overdue'].'</td></tr>';
    if(!$withLinksAndDue)echo '<tr><td colspan="5">هنوز ارتباط یا نقطه عطف ثبت‌شده‌ای وجود ندارد.</td></tr>';
    echo '</table></div></section>';
    echo '<section><h2>اقدامات معوق جهت رسیدگی</h2><div class="scroll"><table><tr><th>پروژه</th><th>اقدام</th><th>تاریخ سررسید</th><th>وضعیت</th></tr>';
    foreach($unresolved as $item)
        echo '<tr><td><a href="?page=project_links&amp;project_id='.(int)$item['project_id'].'">'.esc($item['project_title']).'</a></td><td>'.esc($item['title']).'</td><td>'.esc($item['due_date']).'</td><td>'.esc($item['state']).'</td></tr>';
    if(!$unresolved)echo '<tr><td colspan="4">در حال حاضر اقدام معوقی در دفتر پروژه ثبت نشده است.</td></tr>';
    echo '</table></div><p class="muted">مرکز فرمان صرفاً وظیفه پیگیری می‌سازد؛ این گزارش خودکار وضعیت پروژه یا مانده مالی را تغییر نمی‌دهد.</p></section>';
}
