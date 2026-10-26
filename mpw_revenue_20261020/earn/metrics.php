<?php
declare(strict_types=1);
/* Anonymous, allowlisted aggregate events. No IP, user agent, email, cookies or PII saved. */
umask(0077);
header('Content-Type: image/gif');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
header('X-Robots-Tag: noindex, nofollow');
$pixel=base64_decode('R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=');
$slugs=['website-doctor','landing-page-studio','ai-automation','business-spreadsheets','website-templates','social-media-kits','resume-builder','logo-studio','browser-games','marketing-ai','business-calculators','website-care'];
$events=['quote_click','tool_generated','game_interacted','inquiry_submitted'];
$s=(string)($_GET['slug']??'');$e=(string)($_GET['event']??'');
if ($_SERVER['REQUEST_METHOD']==='GET' && in_array($s,$slugs,true) && in_array($e,$events,true)) {
 try {
  $parent='/home/zomorod2/.private_mojplaywin_main_agents';
  $dir=$parent.'/revenue-metrics';
  if (!is_dir($parent)||is_link($parent)) throw new RuntimeException('private-root');
  if (!is_dir($dir) && !@mkdir($dir,0700)) throw new RuntimeException('private-metrics');
  if (is_link($dir)) throw new RuntimeException('symlink');
  $file=$dir.'/'.gmdate('Y-m').'.json';
  if (is_link($file)) throw new RuntimeException('metrics-symlink');
  $h=@fopen($file,'c+');
  if (!$h) throw new RuntimeException('metrics-write');
  @chmod($file,0600);
  if (flock($h,LOCK_EX)) {
   $current=stream_get_contents($h);
   $counts=($current!==false && $current!=='')?json_decode($current,true):[];
   if (!is_array($counts))$counts=[];
   $key=$s.':'.$e;
   $counts[$key]=min(2147483647,max(0,(int)($counts[$key]??0))+1);
   rewind($h);ftruncate($h,0);
   fwrite($h,json_encode($counts,JSON_THROW_ON_ERROR));fflush($h);flock($h,LOCK_UN);
  }
  fclose($h);
 } catch (Throwable $ignored) {error_log('MPW_ANONYMOUS_METRIC_UNAVAILABLE');}
}
echo $pixel;