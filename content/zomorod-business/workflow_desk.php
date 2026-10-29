<?php
declare(strict_types=1);
/** Zomorod Melal private approval desk v1.
 * This isolated workflow register does NOT make payments, sign contracts,
 * change employee salaries, alter the accounting ledger, or send messages.
 */
function zmFlowDb(string $private): PDO {
    if (!is_dir($private) || is_link($private)) throw new RuntimeException('Private workflow directory unavailable');
    $path=$private.'/company-workflow.sqlite3';
    if (is_link($path)) throw new RuntimeException('Unsafe workflow database');
    $umask=umask(0077);
    try {
        $db=new PDO('sqlite:'.$path,null,null,[
            PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,
            PDO::ATTR_TIMEOUT=>12,
        ]);
        if (!chmod($path,0600)) throw new RuntimeException('Could not secure company workflow DB');
    } finally {umask($umask);}
    $db->exec('PRAGMA busy_timeout=12000; PRAGMA foreign_keys=ON;');
    $db->exec("CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY,
        request_key TEXT NOT NULL UNIQUE,
        fingerprint TEXT NOT NULL,
        category TEXT NOT NULL CHECK(category IN ('procurement','contract','leave','administration','maintenance','project','research')),
        title TEXT NOT NULL,
        details TEXT NOT NULL,
        amount INTEGER NOT NULL DEFAULT 0 CHECK(amount>=0),
        currency TEXT NOT NULL DEFAULT 'IRR' CHECK(currency IN ('IRR','USD','EUR','AED')),
        risk TEXT NOT NULL CHECK(risk IN ('normal','high_impact')),
        state TEXT NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','submitted','approved','rejected','cancelled')),
        requested_by INTEGER NOT NULL,
        reviewed_by INTEGER,
        review_note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )");
    $db->exec("CREATE TABLE IF NOT EXISTS request_events (
        id INTEGER PRIMARY KEY,
        request_id INTEGER NOT NULL REFERENCES requests(id),
        actor_id INTEGER NOT NULL,
        event TEXT NOT NULL,
        note TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )");
    $db->exec('CREATE INDEX IF NOT EXISTS flow_requests_queue ON requests(state,category,id)');
    $db->exec('CREATE INDEX IF NOT EXISTS flow_events_request ON request_events(request_id,id)');
    return $db;
}
function zmFlowAdminOrManager(): void {
    if (!function_exists('actor') || actor()<=0 || !in_array(role(),['admin','manager','accountant'],true)) {
        bail('برای این عملیات دسترسی مدیر یا حسابدار لازم است.',403);
    }
}
function zmFlowInput(string $s,int $limit): string {
    $s=trim($s);
    if($s==='' || mbSafeLen($s)>$limit || preg_match('/[\x00-\x08\x0b\x0c\x0e-\x1f]/u',$s)===1) {
        bail('اطلاعات درخواست نامعتبر است.',422);
    }
    return $s;
}
function zmFlowCreate(PDO $db,string $key,string $category,string $title,string $details,
                      int $amount,string $currency,string $risk,int $actor): array {
    $categories=['procurement','contract','leave','administration','maintenance','project','research'];
    if (!preg_match('/^[0-9a-f]{32}$/D',$key) || !in_array($category,$categories,true) ||
        !in_array($risk,['normal','high_impact'],true) ||
        !in_array($currency,['IRR','USD','EUR','AED'],true) || $amount<0 || $amount>99999999999999 ||
        $actor<1) bail('دسته‌بندی، شناسه یا مبلغ نامعتبر است.',422);
    $title=zmFlowInput($title,160);$details=zmFlowInput($details,2500);
    if (($category==='procurement'||$category==='contract') && $amount>0) $risk='high_impact';
    $fingerprint=hash('sha256',json_encode([$category,$title,$details,$amount,$currency,$risk,$actor],JSON_UNESCAPED_UNICODE));
    $db->beginTransaction();
    try {
        $existing=$db->prepare('SELECT id,fingerprint FROM requests WHERE request_key=?');
        $existing->execute([$key]);$old=$existing->fetch();
        if($old){
            if(!hash_equals((string)$old['fingerprint'],$fingerprint))bail('شناسه قبلاً برای دستور متفاوت استفاده شده است.',409);
            $db->commit();return [(int)$old['id'],false];
        }
        $db->prepare('INSERT INTO requests(request_key,fingerprint,category,title,details,amount,currency,risk,requested_by) VALUES(?,?,?,?,?,?,?,?,?)')
            ->execute([$key,$fingerprint,$category,$title,$details,$amount,$currency,$risk,$actor]);
        $id=(int)$db->lastInsertId();
        $db->prepare('INSERT INTO request_events(request_id,actor_id,event,note) VALUES(?,?,?,?)')
            ->execute([$id,$actor,'created','درخواست ثبت شد؛ هیچ اقدام حقوقی یا مالی انجام نشده است.']);
        $db->commit();return [$id,true];
    }catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
}
function zmFlowTransition(PDO $db,int $id,string $action,string $note,int $actor,string $role): void {
    if($id<1||$actor<1||!in_array($action,['submit','approve','reject','revise','cancel'],true)) {
        bail('عملیات درخواست معتبر نیست.',422);
    }
    if(!in_array($role,['admin','manager','accountant'],true))bail('دسترسی کافی نیست.',403);
    $note=zmFlowInput($note,900);
    $db->beginTransaction();
    try {
        $get=$db->prepare('SELECT * FROM requests WHERE id=?');$get->execute([$id]);$item=$get->fetch();
        if(!$item)bail('درخواست پیدا نشد.',404);
        $state=(string)$item['state'];$owner=(int)$item['requested_by'];
        $isAdmin=$role==='admin';
        $allowed=[
            'draft'=>['submit'=>'submitted','cancel'=>'cancelled'],
            'submitted'=>['approve'=>'approved','reject'=>'rejected','cancel'=>'cancelled'],
            'rejected'=>['revise'=>'draft','cancel'=>'cancelled'],
            'approved'=>[], 'cancelled'=>[],
        ];
        if(!isset($allowed[$state][$action]))bail('این تغییر وضعیت مجاز نیست.',409);
        if(in_array($action,['submit','revise','cancel'],true) && $actor!==$owner && !$isAdmin) {
            bail('فقط درخواست‌کننده یا مدیر اصلی مجاز است.',403);
        }
        if(in_array($action,['approve','reject'],true)){
            if(!$isAdmin)bail('تأیید و رد نهایی فقط با مدیر اصلی است.',403);
            if($item['risk']==='high_impact' && $actor===$owner) {
                bail('درخواست حساس به تأیید شخص مجاز مستقل نیاز دارد.',403);
            }
        }
        $next=$allowed[$state][$action];
        $reviewer=in_array($action,['approve','reject'],true)?$actor:null;
        $db->prepare('UPDATE requests SET state=?,reviewed_by=?,review_note=?,updated_at=CURRENT_TIMESTAMP WHERE id=?')
            ->execute([$next,$reviewer,$note,$id]);
        $db->prepare('INSERT INTO request_events(request_id,actor_id,event,note) VALUES(?,?,?,?)')
            ->execute([$id,$actor,$action,$note]);
        $db->commit();
    }catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
}
function zmFlowHandle(PDO $db,string $action): void {
    zmFlowAdminOrManager();
    if($action==='flow_create'){
        $amount=cents(req('amount','0'));
        zmFlowCreate($db,req('request_key'),req('category'),req('title'),req('details'),
            $amount,req('currency','IRR'),req('risk','normal'),actor());
        return;
    }
    if($action==='flow_transition'){
        zmFlowTransition($db,(int)req('request_id'),req('decision'),req('note'),actor(),role());
        return;
    }
    bail('عملیات اتوماسیون مجاز نیست.',403);
}
function zmFlowRender(PDO $db): void {
    authorize('view');
    $categories=['procurement'=>'درخواست خرید','contract'=>'قرارداد','leave'=>'مرخصی','administration'=>'امور اداری','maintenance'=>'تعمیر و نگهداری','project'=>'پروژه','research'=>'پژوهش'];
    $states=['draft'=>'پیش‌نویس','submitted'=>'در انتظار تصمیم','approved'=>'تأیید مدیریتی','rejected'=>'برگشت برای اصلاح','cancelled'=>'لغوشده'];
    echo '<section><h2>کارتابل یکپارچه و گردش‌کار شرکت</h2><p class="muted">تأیید در این بخش صرفاً تصمیم داخلی است؛ انتقال وجه، انعقاد حقوقی قرارداد، امضای سند یا تغییر دفاتر مالی انجام نمی‌دهد.</p>';
    $counts=q($db,'SELECT state,COUNT(*) total FROM requests GROUP BY state');
    echo '<div class="grid">';
    foreach($counts as $r)echo '<div class="card"><div class="metric">'.(int)$r['total'].'</div>'.esc($states[$r['state']]??$r['state']).'</div>';
    echo '</div></section>';
    if(in_array(role(),['admin','manager','accountant'],true)){
        echo '<section><h2>ثبت درخواست سازمانی</h2>';formBegin('flow_create');
        echo '<input type="hidden" name="request_key" value="'.bin2hex(random_bytes(16)).'"><div class="form">';
        echo '<div><label>نوع درخواست</label><select name="category">';
        foreach($categories as $k=>$v)echo '<option value="'.esc($k).'">'.esc($v).'</option>';
        echo '</select></div><div><label>ریسک</label><select name="risk"><option value="normal">عادی</option><option value="high_impact">حساس</option></select></div>';
        echo '<div><label>مبلغ صرفاً پیشنهادی (بدون پرداخت)</label><input name="amount" value="0"></div>';
        echo '<div><label>ارز</label><select name="currency"><option>IRR</option><option>USD</option><option>EUR</option><option>AED</option></select></div>';
        echo '<div class="full"><label>عنوان</label><input name="title" maxlength="160" required></div>';
        echo '<div class="full"><label>شرح و مستندات موردنیاز</label><textarea name="details" maxlength="2500" required></textarea></div></div>';
        echo '<button>ثبت پیش‌نویس</button></form></section>';
    }
    echo '<section><h2>درخواست‌ها و وضعیت پیگیری</h2><div class="scroll"><table><thead><tr><th>شناسه</th><th>درخواست</th><th>شرح</th><th>وضعیت</th><th>مبلغ پیشنهادی</th><th>اقدام</th></tr></thead><tbody>';
    foreach(q($db,'SELECT * FROM requests ORDER BY id DESC LIMIT 100') as $r){
        $id=(int)$r['id'];
        echo '<tr><td>'.$id.'</td><td>'.esc($categories[$r['category']]??$r['category']).'<p>'.esc($r['title']).'</p></td><td>'.esc($r['details']).'</td><td>'.esc($states[$r['state']]??$r['state']).'</td><td>'.money((int)$r['amount']).' '.esc($r['currency']).'</td><td>';
        if(in_array(role(),['admin','manager','accountant'],true)){
            $choices=[];
            $owner=(int)$r['requested_by']===actor();
            if($r['state']==='draft' && ($owner||role()==='admin'))$choices=['submit'=>'ارسال به بررسی','cancel'=>'لغو'];
            elseif($r['state']==='rejected' && ($owner||role()==='admin'))$choices=['revise'=>'بازگشت به پیش‌نویس','cancel'=>'لغو'];
            elseif($r['state']==='submitted' && role()==='admin'){
                $choices=['approve'=>'تأیید مدیریتی','reject'=>'رد با توضیح','cancel'=>'لغو'];
                if($r['risk']==='high_impact' && $owner)unset($choices['approve'],$choices['reject']);
            }elseif($r['state']==='submitted'&&$owner)$choices=['cancel'=>'لغو'];
            if($choices){
                formBegin('flow_transition');
                echo '<input type="hidden" name="request_id" value="'.$id.'"><select name="decision">';
                foreach($choices as $k=>$label)echo '<option value="'.esc($k).'">'.esc($label).'</option>';
                echo '</select><input name="note" required maxlength="900" placeholder="دلیل یا نتیجه قابل پیگیری"><button>ثبت تصمیم</button></form>';
            }
        }
        echo '</td></tr>';
    }
    echo '</tbody></table></div></section>';
    echo '<section><h2>آخرین تغییرات کارتابل</h2><div class="scroll"><table><tr><th>درخواست</th><th>اقدام</th><th>شناسه کاربر</th><th>توضیح</th><th>تاریخ</th></tr>';
    foreach(q($db,'SELECT * FROM request_events ORDER BY id DESC LIMIT 80') as $e)echo '<tr><td>'.(int)$e['request_id'].'</td><td>'.esc($e['event']).'</td><td>'.(int)$e['actor_id'].'</td><td>'.esc($e['note']).'</td><td>'.esc($e['created_at']).'</td></tr>';
    echo '</table></div></section>';
}
