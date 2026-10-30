<?php
declare(strict_types=1);
/**
 * Private industry operations register: crop cycles, land, laboratory samples,
 * production batches, and equipment. Internal records only. No devices, bank,
 * public sales, or autonomous agent execute from this module.
 */
function zmIndustryDb(string $private): PDO {
    if (!is_dir($private) || is_link($private)) throw new RuntimeException('Industry private storage missing');
    $path=$private.'/industry-operations.sqlite3';
    if (is_link($path)) throw new RuntimeException('Unsafe industry database path');
    $umask=umask(0077);
    try {
        $db=new PDO('sqlite:'.$path, null,null,[
            PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,
            PDO::ATTR_TIMEOUT=>12
        ]);
        if (!chmod($path,0600)) throw new RuntimeException('Cannot protect industry database');
    } finally {umask($umask);}
    $db->exec('PRAGMA busy_timeout=12000; PRAGMA foreign_keys=ON;');
    $db->exec("CREATE TABLE IF NOT EXISTS industry_items (
        id INTEGER PRIMARY KEY,
        request_key TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL CHECK(kind IN ('plot','crop','lab','batch','asset')),
        reference TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        detail TEXT NOT NULL,
        status TEXT NOT NULL,
        parent_id INTEGER REFERENCES industry_items(id),
        quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity>=0),
        unit TEXT NOT NULL DEFAULT 'unit',
        created_by INTEGER NOT NULL,
        reviewed_by INTEGER,
        evidence_url TEXT NOT NULL DEFAULT '',
        review_note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CHECK (
            (kind='plot' AND status IN ('planned','active','resting','retired')) OR
            (kind='crop' AND status IN ('planned','growing','harvested','cancelled')) OR
            (kind='lab' AND status IN ('received','testing','review_required','verified','rejected')) OR
            (kind='batch' AND status IN ('planned','producing','quality_hold','released','rejected','cancelled')) OR
            (kind='asset' AND status IN ('in_service','maintenance','retired'))
        )
    )");
    $db->exec("CREATE TABLE IF NOT EXISTS industry_events (
        id INTEGER PRIMARY KEY,
        item_id INTEGER NOT NULL REFERENCES industry_items(id),
        user_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        note TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )");
    $db->exec('CREATE INDEX IF NOT EXISTS industry_kind_status ON industry_items(kind,status,id)');
    $db->exec('CREATE INDEX IF NOT EXISTS industry_item_events ON industry_events(item_id,id)');
    $db->exec("CREATE TRIGGER IF NOT EXISTS industry_events_no_update BEFORE UPDATE ON industry_events
        BEGIN SELECT RAISE(ABORT,'Append-only industry audit history'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS industry_events_no_delete BEFORE DELETE ON industry_events
        BEGIN SELECT RAISE(ABORT,'Append-only industry audit history'); END");
    return $db;
}
function zmIndustryStates(): array {
    return [
        'plot'=>['planned'=>['active','retired'],'active'=>['resting','retired'],'resting'=>['active','retired'],'retired'=>[]],
        'crop'=>['planned'=>['growing','cancelled'],'growing'=>['harvested','cancelled'],'harvested'=>[],'cancelled'=>[]],
        'lab'=>['received'=>['testing','rejected'],'testing'=>['review_required','rejected'],'review_required'=>['verified','rejected'],'verified'=>[],'rejected'=>[]],
        'batch'=>['planned'=>['producing','cancelled'],'producing'=>['quality_hold','rejected'],'quality_hold'=>['released','rejected'],'released'=>[],'rejected'=>[],'cancelled'=>[]],
        'asset'=>['in_service'=>['maintenance','retired'],'maintenance'=>['in_service','retired'],'retired'=>[]],
    ];
}
function zmIndustryAdmin(): void {
    if (!function_exists('actor') || actor()<=0 || role()!=='admin') bail('فقط مدیر مجاز است.',403);
}
function zmIndustryOperator(): void {
    if (!function_exists('actor') || actor()<=0 || !in_array(role(),['admin','manager'],true)) bail('فقط واحد مدیریتی مجاز است.',403);
}
function zmIndustryText(string $value,int $limit): string {
    $value=trim($value);
    if($value==='' || mbSafeLen($value)>$limit || preg_match('/[\x00-\x08\x0b\x0c\x0e-\x1f]/u',$value))bail('اطلاعات ثبت نامعتبر است.',422);
    return $value;
}
function zmIndustryCreate(PDO $db,string $key,string $kind,string $reference,string $title,string $detail,
                          int $quantity,string $unit,?int $parent,int $actorId): array {
    $states=zmIndustryStates();
    if(!preg_match('/^[a-f0-9]{32}$/D',$key) || !isset($states[$kind]) || $actorId<=0 ||
       $quantity<0 || $quantity>1000000000000) bail('پارامترهای ثبت نامعتبر است.',422);
    $reference=zmIndustryText($reference,60);$title=zmIndustryText($title,180);
    $detail=zmIndustryText($detail,1800);$unit=zmIndustryText($unit,24);
    $first=(string)array_key_first($states[$kind]);
    $db->beginTransaction();
    try {
        $old=$db->prepare('SELECT * FROM industry_items WHERE request_key=?');$old->execute([$key]);$prior=$old->fetch();
        if($prior){
            $same=$prior['kind']===$kind && $prior['reference']===$reference &&
                  $prior['title']===$title && $prior['detail']===$detail &&
                  (int)$prior['created_by']===$actorId &&
                  (int)$prior['quantity']===$quantity && $prior['unit']===$unit &&
                  ($prior['parent_id']===null?null:(int)$prior['parent_id'])===$parent;
            if(!$same)bail('شناسه ثبت تکراری با اطلاعات متفاوت.',409);
            $db->commit();return [(int)$prior['id'],false];
        }
        if($kind==='crop'){
            if(!$parent || $parent<=0)bail('دوره کشت باید به یک قطعه زمین متصل باشد.',422);
            $q=$db->prepare("SELECT id FROM industry_items WHERE id=? AND kind='plot' AND status!='retired'");
            $q->execute([$parent]);if(!$q->fetchColumn())bail('قطعه زمین معتبر پیدا نشد.',422);
        } elseif($parent!==null) bail('رابط والد برای این نوع مجاز نیست.',422);
        $db->prepare('INSERT INTO industry_items(request_key,kind,reference,title,detail,status,parent_id,quantity,unit,created_by) VALUES(?,?,?,?,?,?,?,?,?,?)')
            ->execute([$key,$kind,$reference,$title,$detail,$first,$parent,$quantity,$unit,$actorId]);
        $id=(int)$db->lastInsertId();
        $db->prepare('INSERT INTO industry_events(item_id,user_id,action,note) VALUES(?,?,?,?)')
            ->execute([$id,$actorId,'created','ثبت داخلی اولیه؛ هیچ عملیات فیزیکی اجرا نشده است.']);
        $db->commit();return [$id,true];
    } catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
}
function zmIndustryAdvance(PDO $db,int $id,string $target,string $note,int $actorId,string $actorRole,string $evidence=''): void {
    $note=zmIndustryText($note,1000);
    if($id<=0 || $actorId<=0 || !in_array($actorRole,['admin','manager'],true))bail('دسترسی یا شناسه نامعتبر است.',403);
    $db->beginTransaction();
    try {
        $q=$db->prepare('SELECT * FROM industry_items WHERE id=?');$q->execute([$id]);$item=$q->fetch();
        if(!$item)bail('رکورد عملیاتی یافت نشد.',404);
        $states=zmIndustryStates();
        if(!in_array($target,$states[$item['kind']][$item['status']]??[],true))bail('انتقال وضعیت مجاز نیست.',409);
        $qualityDecision=($item['kind']==='lab' && $target==='verified') || ($item['kind']==='batch' && $target==='released');
        if($qualityDecision){
            if($actorRole!=='admin' || $actorId===(int)$item['created_by'])bail('تأیید مستقل مدیر برای نتیجه حساس لازم است.',403);
            $evidence=trim($evidence);
            if(strlen($evidence)>500 || !filter_var($evidence,FILTER_VALIDATE_URL) ||
               strtolower((string)parse_url($evidence,PHP_URL_SCHEME))!=='https' ||
               parse_url($evidence,PHP_URL_USER)!==null || parse_url($evidence,PHP_URL_PASS)!==null)
                bail('پیوند امن شواهد برای تأیید کیفیت الزامی است.',422);
        } else {
            if($evidence!=='')bail('شواهد رسمی فقط در مرحله بررسی کیفیت قابل ثبت است.',422);
        }
        $db->prepare('UPDATE industry_items SET status=?, reviewed_by=?, evidence_url=?,review_note=?,updated_at=CURRENT_TIMESTAMP WHERE id=?')
            ->execute([$target,$qualityDecision?$actorId:null,$qualityDecision?$evidence:'',$note,$id]);
        $db->prepare('INSERT INTO industry_events(item_id,user_id,action,note) VALUES(?,?,?,?)')
            ->execute([$id,$actorId,'status:'.$target,$note]);
        $db->commit();
    } catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
}
function zmIndustryHandle(PDO $db,string $action): void {
    zmIndustryOperator();
    if($action==='industry_create'){
        $rawParent=req('parent_id');
        if($rawParent!=='' && !preg_match('/^[1-9][0-9]{0,9}$/D',$rawParent))bail('شناسه قطعه زمین نامعتبر است.',422);
        $parent=$rawParent===''?null:(int)$rawParent;
        $rawQuantity=req('quantity','0');
        if(!preg_match('/^(?:0|[1-9][0-9]{0,11})$/D',$rawQuantity))bail('مقدار ثبت نامعتبر است.',422);
        zmIndustryCreate($db,req('request_key'),req('kind'),req('reference'),req('title'),req('detail'),
            (int)$rawQuantity,req('unit','unit'),$parent,actor());
    } elseif($action==='industry_advance'){
        zmIndustryAdvance($db,(int)req('item_id'),req('target'),req('note'),actor(),role(),req('evidence_url'));
    } else bail('عملیات ناشناخته است.',403);
}
function zmIndustryRender(PDO $db): void {
    authorize('view');
    $labels=['plot'=>'قطعات زمین','crop'=>'دوره کشت','lab'=>'نمونه آزمایشگاه','batch'=>'بچ تولید','asset'=>'دارایی و ماشین‌آلات'];
    echo '<section><h2>عملیات کشاورزی، آزمایشگاه، تولید و دارایی‌ها</h2><p class="muted">داده‌های این بخش پرونده‌های مدیریتی هستند، نه کنترل مستقیم ماشین‌آلات یا گواهی کیفی محصول. هیچ پرداخت یا اقدام بیرونی انجام نمی‌شود.</p>';
    $totals=q($db,'SELECT kind,COUNT(*) cnt FROM industry_items GROUP BY kind');echo '<div class="grid">';
    foreach($totals as $r)echo '<div class="card"><div class="metric">'.(int)$r['cnt'].'</div>'.esc($labels[$r['kind']]??$r['kind']).'</div>';
    echo '</div></section>';
    if(in_array(role(),['admin','manager'],true)){
        echo '<section><h2>ثبت پرونده عملیاتی جدید</h2>';formBegin('industry_create');
        echo '<input type="hidden" name="request_key" value="'.bin2hex(random_bytes(16)).'"><div class="form">';
        echo '<div><label>حوزه</label><select name="kind">';foreach($labels as $k=>$v)echo '<option value="'.esc($k).'">'.esc($v).'</option>';echo '</select></div>';
        echo '<div><label>شناسه یکتا</label><input maxlength="60" required name="reference"></div>';
        echo '<div><label>مقدار غیرمالی</label><input name="quantity" type="number" value="0" min="0"></div>';
        echo '<div><label>واحد سنجش</label><input name="unit" value="unit" maxlength="24"></div>';
        echo '<div><label>شناسه قطعه زمین (فقط دوره کشت)</label><input name="parent_id" type="number" min="1"></div>';
        echo '<div class="full"><label>عنوان</label><input name="title" maxlength="180" required></div>';
        echo '<div class="full"><label>شرح، منبع داده و هدف ثبت</label><textarea name="detail" maxlength="1800" required></textarea></div></div>';
        echo '<button>ثبت پرونده داخلی</button></form></section>';
    }
    echo '<section><h2>رکوردهای عملیاتی</h2><div class="scroll"><table><tr><th>شناسه</th><th>نوع</th><th>نام</th><th>وضعیت</th><th>مقدار</th><th>اقدام</th></tr>';
    $states=zmIndustryStates();
    foreach(q($db,'SELECT * FROM industry_items ORDER BY id DESC LIMIT 100') as $r){
        $id=(int)$r['id'];echo '<tr><td>'.esc($r['reference']).'</td><td>'.esc($labels[$r['kind']]??$r['kind']).'</td><td>'.esc($r['title']).'</td><td>'.esc($r['status']).'</td><td>'.(int)$r['quantity'].' '.esc($r['unit']).'</td><td>';
        if(in_array(role(),['admin','manager'],true)){
            $choices=$states[$r['kind']][$r['status']]??[];
            if($choices){formBegin('industry_advance');echo '<input type="hidden" name="item_id" value="'.$id.'"><select name="target">';
                foreach($choices as $target){
                    $sensitive=($r['kind']==='lab'&&$target==='verified')||($r['kind']==='batch'&&$target==='released');
                    if($sensitive && (role()!=='admin'||actor()===(int)$r['created_by']))continue;
                    echo '<option value="'.esc($target).'">'.esc($target).'</option>';
                }
                echo '</select><input name="note" maxlength="1000" placeholder="شرح و شواهد اقدام" required>';
                echo '<input type="url" maxlength="500" name="evidence_url" placeholder="HTTPS: فقط برای تأیید کیفیت"><button>ثبت تغییر وضعیت</button></form>';
            }
        }
        echo '</td></tr>';
    }
    echo '</table></div></section><section><h2>رویدادهای ثبت‌شده</h2><div class="scroll"><table><tr><th>ردیف</th><th>اقدام</th><th>کاربر</th><th>شرح</th></tr>';
    foreach(q($db,'SELECT * FROM industry_events ORDER BY id DESC LIMIT 80') as $e)echo '<tr><td>'.(int)$e['item_id'].'</td><td>'.esc($e['action']).'</td><td>'.(int)$e['user_id'].'</td><td>'.esc($e['note']).'</td></tr>';
    echo '</table></div></section>';
}
