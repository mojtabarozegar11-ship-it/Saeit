<?php
declare(strict_types=1);
/* MojPlayWin first-party commercial inquiry. Isolated from checkout and customer accounts. */
umask(0077);
header('Content-Type: text/html; charset=UTF-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: no-referrer');
header("Content-Security-Policy: default-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; form-action 'self'; base-uri 'self'");
$allowed = [
  'general'=>'General MojPlayWin Business Inquiry',
  'website-doctor'=>'Website Doctor — Audit & Fix',
  'landing-page-studio'=>'Landing Page Studio',
  'ai-automation'=>'AI Workflow Automation',
  'business-spreadsheets'=>'Business Spreadsheet Kits',
  'website-templates'=>'Website Template Collection',
  'social-media-kits'=>'Social Media Design Kits',
  'resume-builder'=>'International Resume Builder',
  'logo-studio'=>'AI Logo & Brand Studio',
  'browser-games'=>'Original Browser Games & Add-ons',
  'marketing-ai'=>'Marketing AI Content Workspace',
  'business-calculators'=>'Interactive Business Calculators',
  'website-care'=>'Website Care & Maintenance'
];
function h(string $v): string {return htmlspecialchars($v, ENT_QUOTES|ENT_SUBSTITUTE, 'UTF-8');}
function clean($v, int $max): string {
  if (!is_string($v)) return '';
  $v = preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/u', '', trim($v));
  return mb_substr($v ?? '', 0, $max, 'UTF-8');
}
function safe_private_dir(): string {
  $parent='/home/zomorod2/.private_mojplaywin_main_agents';
  $root=$parent.'/revenue-inquiries';
  if (!is_dir($parent) || is_link($parent)) throw new RuntimeException('Private owner storage is unavailable.');
  if (!is_dir($root) && !@mkdir($root,0700)) throw new RuntimeException('Private request storage is unavailable.');
  if (!is_dir($root) || is_link($root)) throw new RuntimeException('Unsafe request storage.');
  @chmod($root,0700);
  return $root;
}
function key_bytes(string $root): string {
  $file=$root.'/.inquiry-key';
  if (is_link($file)) throw new RuntimeException('Unsafe encryption key.');
  if (!file_exists($file)) {
    $fh=@fopen($file,'x');
    if ($fh!==false) {
      @chmod($file,0600);
      $raw=random_bytes(32);
      if (fwrite($fh,$raw)!==32) {fclose($fh);throw new RuntimeException('Key initialization failed.');}
      fflush($fh);fclose($fh);
    }
  }
  $bytes=@file_get_contents($file);
  if ($bytes===false || strlen($bytes)!==32) throw new RuntimeException('Encryption key unavailable.');
  return $bytes;
}
function store_inquiry(array $record): string {
  if (!function_exists('openssl_encrypt') || !function_exists('random_bytes')) throw new RuntimeException('Encryption unavailable.');
  $root=safe_private_dir();
  $key=key_bytes($root);
  $id=strtoupper(bin2hex(random_bytes(9)));
  $iv=random_bytes(12);$tag='';
  $plain=json_encode($record,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR);
  $cipher=openssl_encrypt($plain,'aes-256-gcm',$key,OPENSSL_RAW_DATA,$iv,$tag);
  if ($cipher===false || strlen($tag)!==16) throw new RuntimeException('Encryption failed.');
  $body=json_encode(['v'=>1,'iv'=>base64_encode($iv),'tag'=>base64_encode($tag),'cipher'=>base64_encode($cipher)],JSON_THROW_ON_ERROR);
  $file=$root.'/'.gmdate('Ymd').'-'.$id.'.json';
  $tmp=$root.'/.new-'.$id;
  $fh=@fopen($tmp,'x');
  if ($fh===false) throw new RuntimeException('Could not reserve private record.');
  @chmod($tmp,0600);
  try {
    if (fwrite($fh,$body)!==strlen($body)) throw new RuntimeException('Record write failed.');
    fflush($fh);fclose($fh);$fh=false;
    if (!@rename($tmp,$file)) throw new RuntimeException('Record commit failed.');
  } finally {if (is_resource($fh)) fclose($fh);if (file_exists($tmp)) @unlink($tmp);}
  return $id;
}
if (!extension_loaded('mbstring') || !extension_loaded('openssl')) {
  http_response_code(503);echo '<h1>Inquiry temporarily unavailable</h1><p>Please email support@mojplaywin.com.</p>';exit;
}
ini_set('session.use_strict_mode','1');
session_set_cookie_params(['lifetime'=>0,'path'=>'/mpw-editorial/revenue' . '/','secure'=>true,'httponly'=>true,'samesite'=>'Lax']);
if (!@session_start()) {http_response_code(503);echo '<h1>Secure session unavailable</h1>';exit;}
$slug=(string)($_POST['service']??$_GET['service']??'');
if (!array_key_exists($slug,$allowed)) {http_response_code(404);echo '<h1>Unknown service</h1>';exit;}
$title=$allowed[$slug];
$token=$_SESSION['mpw_inquiry_token']??bin2hex(random_bytes(24));
$_SESSION['mpw_inquiry_token']=$token;
$errors=[];$sent=false;$reference='';
$data=['name'=>'','email'=>'','company'=>'','website'=>'','details'=>'','timeline'=>''];
if ($_SERVER['REQUEST_METHOD']==='POST') {
  if (strlen((string)($_SERVER['CONTENT_LENGTH']??''))>6 && (int)($_SERVER['CONTENT_LENGTH']??0)>12000) $errors[]='Request is too large.';
  if (!hash_equals($token,(string)($_POST['csrf']??''))) $errors[]='The form expired. Refresh and try again.';
  if (!empty($_POST['fax_number'])) $errors[]='Submission rejected.';
  foreach ($data as $field=>$unused) $data[$field]=clean($_POST[$field]??'', $field==='details'?2000:($field==='email'?254:($field==='website'?300:120)));
  if (mb_strlen($data['name'])<2) $errors[]='Enter your name.';
  if (!filter_var($data['email'],FILTER_VALIDATE_EMAIL)) $errors[]='Enter a valid email address.';
  if (mb_strlen($data['details'])<40) $errors[]='Describe your request in at least 40 characters.';
  if ($data['website']!=='' && (!filter_var($data['website'],FILTER_VALIDATE_URL) || !preg_match('~^https?://~i',$data['website']))) $errors[]='Enter an http/https URL or leave the website field empty.';
  if (($_POST['consent']??'')!=='yes') $errors[]='Please acknowledge the data-use notice.';
  if (time()-(int)($_SESSION['last_mpw_inquiry']??0)<90) $errors[]='Please wait before sending another request.';
  if (!$errors) {
    try {
      $record=['created_at'=>gmdate('c'),'service'=>$slug,'name'=>$data['name'],'email'=>$data['email'],'company'=>$data['company'],'website'=>$data['website'],'details'=>$data['details'],'timeline'=>$data['timeline'],'consent'=>true,'source'=>'first_party_mpw_revenue'];
      $reference=store_inquiry($record);
      $_SESSION['last_mpw_inquiry']=time();
      $_SESSION['mpw_inquiry_token']=bin2hex(random_bytes(24));
      $token=$_SESSION['mpw_inquiry_token'];
      $sent=true;
      $body="MojPlayWin commercial inquiry received and stored privately.\nService: ".$title."\nReference: ".$reference."\n\nReview the private cPanel revenue-inquiries record. No customer data is logged to CI.\n";
      @mail('support@mojplaywin.com','New MojPlayWin web inquiry '.$reference,$body,"From: support@mojplaywin.com\r\nContent-Type: text/plain; charset=UTF-8");
    } catch (Throwable $e) {$errors[]='We could not securely save the request. Please use the email fallback.';error_log('MPW_INQUIRY_STORAGE_FAILURE');}
  }
}
$subject=rawurlencode($slug==='general' ? 'MojPlayWin business quote' : 'MojPlayWin '.$slug.' service enquiry');
$fallback='mailto:support@mojplaywin.com?subject='.$subject;
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,follow"><title>Secure Inquiry — <?=h($title)?> | MojPlayWin</title><link rel="stylesheet" href="/mpw-editorial/revenue/assets/style.css"><style>
.inquiry-wrap{max-width:790px;margin:40px auto;padding:clamp(20px,4vw,46px);background:#131d2e;border:1px solid #cda969;border-radius:22px}
.inquiry-wrap h1{font-size:clamp(2rem,5vw,3rem)}
.inquiry-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.inquiry-form label{display:flex;flex-direction:column;gap:8px;font-weight:700}
.inquiry-form input,.inquiry-form textarea{width:100%;padding:13px;border:1px solid #8c9aad;border-radius:10px;background:#f8f8fb;color:#152033;font:inherit}
.inquiry-form .span-2{grid-column:1/-1}.inquiry-form button{background:#e5bb70;color:#10151d;border:0;border-radius:10px;padding:15px;font-weight:900;font-size:1rem;min-height:48px;cursor:pointer}
.inquiry-form :focus-visible{outline:3px solid #fff1ad;outline-offset:3px}
.inquiry-note{color:#d7e0ea;font-size:.94rem}.inquiry-status{border:1px solid #9ed4a1;background:#172d22;padding:16px;border-radius:12px}.inquiry-error{border:1px solid #f0a7a7;background:#391e22;padding:16px;border-radius:12px}
.honey{position:absolute;left:-10000px;height:0;overflow:hidden}@media(max-width:680px){.inquiry-form{grid-template-columns:1fr}}
</style></head><body><header><a class="brand" href="/">MojPlayWin</a><nav aria-label="Service navigation"><a href="/mpw-editorial/revenue/index.html">All offers</a><a href="/privacy/">Privacy</a></nav></header><main id="main"><div class="inquiry-wrap"><p class="eyebrow">Commercial inquiry · No payment</p><h1><?=h($title)?></h1><p>Describe the result you need. This first-party form records your inquiry securely and provides a reference even if email delivery is delayed. No payment, binding order or contract is created.</p>
<?php if($sent): ?>
<section class="inquiry-status" role="status"><h2>Inquiry received</h2><p>Private record reference: <strong><?=h($reference)?></strong></p><p>Keep this reference for follow-up. A response time or availability is not guaranteed.</p></section>
<img width="1" height="1" alt="" src="/mpw-editorial/revenue/metrics.php?slug=<?=h($slug)?>&amp;event=inquiry_submitted">
<?php else: ?>
<?php if($errors): ?><div class="inquiry-error" role="alert"><h2>Please correct the request</h2><ul><?php foreach($errors as $msg): ?><li><?=h($msg)?></li><?php endforeach;?></ul></div><?php endif;?>
<form class="inquiry-form" method="post" action="/mpw-editorial/revenue/inquiry.php" accept-charset="UTF-8">
<input type="hidden" name="csrf" value="<?=h($token)?>"><input type="hidden" name="service" value="<?=h($slug)?>">
<label>Name <input name="name" required maxlength="120" autocomplete="name" value="<?=h($data['name'])?>"></label>
<label>Email for reply <input type="email" name="email" required maxlength="254" autocomplete="email" value="<?=h($data['email'])?>"></label>
<label>Organization (optional) <input name="company" maxlength="120" autocomplete="organization" value="<?=h($data['company'])?>"></label>
<label>Website (optional) <input type="url" name="website" maxlength="300" placeholder="https://example.com" value="<?=h($data['website'])?>"></label>
<label class="span-2">Project details (40–2000 characters) <textarea name="details" required minlength="40" maxlength="2000" rows="6" placeholder="Describe the deliverable, target audience and acceptance criteria. Do not send passwords, recovery phrases, identity documents or payment information."><?=h($data['details'])?></textarea></label>
<label class="span-2">Preferred timeframe (optional) <input name="timeline" maxlength="120" value="<?=h($data['timeline'])?>"></label>
<div class="honey" aria-hidden="true"><label>Fax number <input name="fax_number" tabindex="-1" autocomplete="off"></label></div>
<label class="span-2"><span><input type="checkbox" name="consent" value="yes" required> I agree to MojPlayWin privately storing these contact details to evaluate and respond to this specific inquiry.</span></label>
<p class="inquiry-note span-2">Information is stored encrypted in private hosting storage for inquiry handling. It is not sold or published. Request access or deletion using the support address. See the <a href="/privacy/">privacy policy</a>.</p>
<button class="span-2" type="submit">Send secure inquiry</button>
</form>
<?php endif; ?>
<p class="inquiry-note">Email fallback: <a href="<?=h($fallback)?>">support@mojplaywin.com — <?=h($title)?></a>. If you cannot receive a confirmation, retain your reference or contact support separately.</p>
</div></main><footer>© 2026 MojPlayWin · <a href="/terms/">Terms</a> · <a href="/mpw-editorial/revenue/index.html">All 12 offers</a></footer></body></html>