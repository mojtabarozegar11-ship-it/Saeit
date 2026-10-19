<?php
declare(strict_types=1);
/** Isolated catalogue for the Zomorod main store. Bank Shahr is NOT an activated PSP. */
function zmStoreDb(string $private):PDO {
 if(!is_dir($private))throw new RuntimeException('Missing private catalogue directory');
 $db=new PDO('sqlite:'.$private.'/site_store.sqlite3',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_TIMEOUT=>10]);
 $db->exec('PRAGMA journal_mode=WAL; PRAGMA busy_timeout=10000');
 $db->exec('CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, sku TEXT NOT NULL UNIQUE, title TEXT NOT NULL, description TEXT NOT NULL, price_irr INTEGER NOT NULL CHECK(price_irr>0), enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN(0,1)), created_at TEXT DEFAULT CURRENT_TIMESTAMP)');
 $db->exec('CREATE TABLE IF NOT EXISTS payment_state (id INTEGER PRIMARY KEY CHECK(id=1), provider TEXT NOT NULL, state TEXT NOT NULL, note TEXT NOT NULL)');
 $db->exec("INSERT OR IGNORE INTO payment_state(id,provider,state,note) VALUES(1,'Bank Shahr','not_configured','No verified merchant agreement, test environment, signed callback or settlement evidence')");
 // Free digital releases are separate from the bank/payment-bound paid catalog.
 // Only a hash-verified, explicit release workflow can enable a free artifact.
 $db->exec("CREATE TABLE IF NOT EXISTS free_digital_products (
   id INTEGER PRIMARY KEY, sku TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
   description TEXT NOT NULL, download_path TEXT NOT NULL UNIQUE,
   artifact_sha256 TEXT NOT NULL, license_text TEXT NOT NULL,
   price_irr INTEGER NOT NULL DEFAULT 0 CHECK(price_irr=0),
   enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN(0,1)),
   created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
 return $db;
}
function zmStoreHandle(PDO $db,string $action):void{
 if($action==='product_create'){
  $sku=req('sku');$title=req('title');$body=req('description');$amount=req('price_irr');
  if(!preg_match('/^[A-Za-z0-9_-]{3,40}$/',$sku)||mbSafeLen($title)<3||mbSafeLen($title)>160||mbSafeLen($body)>2000||!preg_match('/^[1-9][0-9]{3,11}$/',$amount))bail('مشخصات محصول یا قیمت ریالی نامعتبر است.');
  $db->prepare('INSERT INTO products(sku,title,description,price_irr) VALUES(?,?,?,?)')->execute([$sku,$title,$body,(int)$amount]);
 }elseif($action==='product_toggle'){
  $id=(int)req('product_id');
  if($id<=0) bail('شناسه محصول نامعتبر است.');
  $stmt=$db->prepare('UPDATE products SET enabled=CASE enabled WHEN 1 THEN 0 ELSE 1 END WHERE id=?');$stmt->execute([$id]);
  if($stmt->rowCount()!==1)bail('محصول وجود ندارد.');
 }else bail('عملیات فروشگاه نامعتبر است.');
}
function zmFactoryDraftsPanel(PDO $db):void {
 $existing=$db->query("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='factory_drafts'")->fetchColumn();
 if(!(int)$existing){
   echo '<section><h2>ربات رابط انبار کارخانه VPS</h2><p>هنوز محصولی از انبار کارخانه در کاتالوگ خصوصی فروشگاه ثبت نشده است.</p></section>';
   return;
 }
 $n=(int)$db->query("SELECT COUNT(*) FROM factory_drafts")->fetchColumn();
 echo '<section><h2>ربات رابط انبار کارخانه VPS — پیش‌نویس‌های دریافت‌شده</h2>'.
 '<p>تعداد بسته‌های تأیید فنی و دریافت‌شده: '.number_format($n).
 '. این محصولات تا کنترل حقوق محتوا، مجوز عرضه، قیمت‌گذاری و تأیید مالک برای فروش عمومی فعال نیستند.</p>'.
 '<div class="scroll"><table><thead><tr><th>شناسه کارخانه</th><th>عنوان</th><th>خانواده</th><th>وضعیت</th><th>دریافت</th></tr></thead><tbody>';
 $stmt=$db->query("SELECT product_id,title,family_id,state,imported_at FROM factory_drafts ORDER BY id DESC LIMIT 50");
 foreach($stmt->fetchAll() as $row){
   echo '<tr><td>'.esc((string)$row['product_id']).'</td>'.
   '<td>'.esc((string)$row['title']).'</td>'.
   '<td>'.esc((string)$row['family_id']).'</td>'.
   '<td>پیش‌نویسِ منتظر تأیید تجاری</td>'.
   '<td>'.esc((string)$row['imported_at']).'</td></tr>';
 }
 echo '</tbody></table></div></section>';
}
function zmStoreRender(PDO $db):void {
 $payment=$db->query('SELECT * FROM payment_state WHERE id=1')->fetch();
 echo '<section><h2>فروشگاه زمرد ملل — پنل مدیریت</h2><p>وضعیت پرداخت: <strong>بانک شهر — '.esc($payment['state']).'</strong>. برای شروع پرداخت بانکی، قرارداد، مشخصات پایانه و مستندات رسمی تأیید پرداخت سروربه‌سرور لازم است. هیچ پرداختی در وضعیت فعلی تأیید نمی‌شود.</p><p><a href="/store/">نمایش فروشگاه عمومی</a></p></section>';
 echo '<section><h2>کاتالوگ محصولات واقعی</h2><div class="scroll"><table><tr><th>شناسه</th><th>محصول</th><th>قیمت (ریال)</th><th>نمایش عمومی</th><th>عملیات</th></tr>';
 foreach($db->query('SELECT * FROM products ORDER BY id DESC LIMIT 150')->fetchAll() as $p){
   echo '<tr><td>'.esc($p['sku']).'</td><td>'.esc($p['title']).'</td><td>'.number_format((int)$p['price_irr']).'</td><td>'.($p['enabled']?'فعال':'پیش‌نویس').'</td><td>';
   if(role()==='admin')echo '<form method="post">'.tokenInput().'<input type="hidden" name="product_id" value="'.(int)$p['id'].'"><button name="action" value="product_toggle">'.($p['enabled']?'پنهان‌کردن':'نمایش عمومی').'</button></form>';
   echo '</td></tr>';
 }
 echo '</table></div></section>';
 echo '<section><h2>محصولات دیجیتال رایگان تأییدشده</h2><p>عرضه عمومی فقط پس از آزمون فایل، کنترل SHA-256 و ثبت مجوز انتشار انجام می‌شود. این بخش به درگاه پرداخت متصل نیست.</p><div class="scroll"><table><tr><th>شناسه</th><th>محصول</th><th>هش</th><th>مجوز</th><th>نمایش</th></tr>';
 foreach($db->query("SELECT sku,title,artifact_sha256,license_text,enabled FROM free_digital_products ORDER BY id DESC LIMIT 150")->fetchAll() as $item){
  echo '<tr><td>'.esc((string)$item['sku']).'</td><td>'.esc((string)$item['title']).'</td><td><code>'.esc((string)$item['artifact_sha256']).'</code></td><td>'.esc((string)$item['license_text']).'</td><td>'.($item['enabled']?'عمومی':'تأییدنشده').'</td></tr>';
 }
 echo '</table></div></section>';
 zmFactoryDraftsPanel($db);
 if(role()==='admin'){
  echo '<section><h2>افزودن محصول</h2><p class="muted">فقط محصولاتی را ثبت کنید که فایل یا خدمت واقعی و مجوز عرضه آنها در اختیار شرکت است. قیمت باید ریالی باشد.</p><form method="post">'.tokenInput().'<div class="form"><div><label>شناسه محصول</label><input name="sku" required pattern="[A-Za-z0-9_-]{3,40}"></div><div><label>نام محصول</label><input name="title" required maxlength="160"></div><div><label>قیمت (ریال)</label><input name="price_irr" type="number" min="1000" step="1" required></div><div class="full"><label>توضیحات</label><textarea name="description" maxlength="2000"></textarea></div></div><button name="action" value="product_create">ذخیره به‌صورت پیش‌نویس</button></form></section>';
 }
}