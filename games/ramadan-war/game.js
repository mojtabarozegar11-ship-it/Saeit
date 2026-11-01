import {createEngine} from './engine3d.js';
import {canApplyEarnedUpgrade,applyEarnedUpgrade} from './upgrade-policy.mjs';
import {MOJ1_COMMERCE} from './moj1-commerce-policy.mjs';
import {isInteractiveTarget, keyboardAction, isKeyboardOrAssistiveClick, isPrimaryGameplayPress, isModifiedOrComposingKey, shouldReleaseHeldKeysOnFocus, isFireHeld, joystickAxes, normalizeMovementAxes, resolveMovementAxes, canCaptureGameplayPointer, isOwnedGameplayPointer, recordPointerGestureMovement, shouldFireCanvasClick} from './input-guard.mjs';
import {removeEnemyAndRetargetMissiles,missilePathBlocked,missileMotionValid} from './missile-targets.mjs';
import {canEnemyAct,restoreEnemyRuntime,advanceHostileProjectile,shouldCleanupEnemy,activateTimeStop,advanceTimeStop} from './enemy-action-policy.mjs';
import {validateCampaignSave, boundedCampaignPickups, restoreRecoveryPickups, reconcileBossEncounter, restorePlayerPosition, restoreEnemyPositions, parseCampaignSave, resumeCampaignScreen, readHeroChoice, campaignSaveDisposition, storageRead, storageWrite, storageRemove} from './save-validation.mjs';
import {makeCampaignBackup,readCampaignBackup,MAX_CAMPAIGN_BACKUP_BYTES} from './campaign-backup.mjs';
import {objectiveWaypoint,objectiveApproachWaypoint,closestReachableObjective,INTERACT_RANGE,canInteractAt} from './objective-navigation.mjs';
(()=>{'use strict';
const NAMES=['سید علی خامنه‌ای','حاج قاسم — قاسم سلیمانی','عباس بابایی','علی صیاد شیرازی','مصطفی چمران','محمدابراهیم همت','مهدی باکری','حمید باکری','حسین خرازی','حسن باقری','احمد کاظمی','محمد جهان‌آرا','محمود کاوه','مهدی زین‌الدین','عباس دوران','حسین لشکری','مسعود منفرد نیاکی','ولی‌الله فلاحی','یوسف کلاهدوز','جواد فکوری','موسی نامجو','محمد بروجردی','احمد متوسلیان','عبدالحسین برونسی','ناصر کاظمی','علی هاشمی','منصور ستاری','ایرج رستمی','مصطفی اردستانی','حسین خلعتبری'];
const SKILLS=['سپر انرژی','موج الکترومغناطیس','ترمیم زره','طوفان پالس','توقف زمان','پشتیبانی مداری'];
const MISSIONS=['تهران • دفاع از پایتخت','تنگهٔ کوهستان • رهگیری پهپادها','جزیرهٔ خارک • پایگاه رباتیک','بندرعباس • عملیات شبانه','کالیفرنیا • پایگاه ساحلی','واشنگتن • تصرف قرارگاه فرماندهی'];
const $=s=>document.querySelector(s), canvas=$('#view'),hud=$('#hud'),gameRoot=$('#game');let W=1,H=1,dpr=1;const engine=createEngine(canvas);
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)), rnd=(a,b)=>a+Math.random()*(b-a), fa=n=>String(Math.max(0,Math.floor(n))).replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
const saveKey='rwNativeCampaign',stageNames=NAMES;
const survivalWave=mission=>Math.max(1,Math.floor(mission)-5);
function readSurvivalBest(){const raw=storageRead('rwSurvivalBest');return typeof raw==='string'&&/^[1-9]\d{0,3}$/.test(raw)?Math.min(9999,Number(raw)):0}
function recordSurvivalBest(){if(!world?.endless)return;const wave=survivalWave(world.mission);if(wave>readSurvivalBest())storageWrite('rwSurvivalBest',String(wave))}

let soundEnabled=storageRead('rwSound')!=='0';
function syncSoundControls(){for(const id of ['soundHome','soundPause']){const button=$('#'+id);if(!button)continue;button.setAttribute('aria-pressed',String(soundEnabled));button.textContent=soundEnabled?'🔊 صدا روشن':'🔇 بی‌صدا'}}
function toggleSound(){soundEnabled=!soundEnabled;storageWrite('rwSound',soundEnabled?'1':'0');syncSoundControls()}
const sceneFiles=['./scene-sniper-desert-v2.webp','./scene-night.webp','./scene-airbase.webp'];function setMissionScene(m){const el=$('#missionBackdrop'),file=sceneFiles[m%sceneFiles.length];if(el.dataset.scene!==file){el.style.backgroundImage=`url("${file}")`;el.dataset.scene=file}el.style.setProperty('--pan-x','0px');el.style.setProperty('--pan-y','0px')}

let sessionWinUnlocked=false;let hero=readHeroChoice(storageRead('rwHero')),world=null,screen='home',last=0,toastTimer=0,hitTimer=0,fireHeld=false,fireId=null,joyId=null,aimId=null,joyX=0,joyY=0,joyF=0,joyS=0,aimLast=0,keys={},effects=[],audioCtx=null;
const MAPSIZE=16,FOV=1.02;

/* Each operation has a different win condition: objectives, not a recycled kill arena. */
const OPERATIONS=[
 {kind:'activate',title:'فعال‌سازی دو مرکز دفاعی',quota:4,sites:[[8.5,3.5],[11.5,11.5]]},
 {kind:'defend',title:'پایداری در منطقهٔ دفاع',quota:5,sites:[[8.5,7.5]],seconds:22},
 {kind:'recover',title:'بازیابی سه بستهٔ اطلاعاتی',quota:5,sites:[[4.5,2.5],[12.5,4.5],[8.5,12.5]]},
 {kind:'activate',title:'قطع دو رلهٔ راداری',quota:6,sites:[[3.5,5.5],[11.5,11.5]]},
 {kind:'extract',title:'پاکسازی و رسیدن به نقطهٔ خروج',quota:7,sites:[[13.5,13.5]]},
 {kind:'boss',title:'شکست فرماندهٔ زرهی',quota:8,sites:[[8.5,7.5]]}
];
function plan(){return OPERATIONS[Math.min(world.mission,OPERATIONS.length-1)]}
function objectiveTarget(){if(!world||world.endless)return null;const p=plan(),o=world.objective||{done:0};
 if(p.kind==='boss'){const boss=world.enemies.find(e=>e.boss&&e.hp>0);return boss?[boss.x,boss.y]:null}
 if(p.kind==='defend')return o.hold>=p.seconds?null:p.sites[0];
 if(p.kind==='recover'){const intel=world.pickups.filter(item=>item.type==='mission-intel').map(item=>[item.x,item.y]);return closestReachableObjective(world.x,world.y,intel,(x,y)=>tile(x,y,world.mission)===0)}
 return o.done>=p.sites.length?null:p.sites[o.done];
}
function prepareObjective(){if(world.endless)return;const p=plan();
 world.objective={done:0,hold:0,bossDefeated:false,...(p.kind==='recover'?{collectedSites:[]}:{})};world.bossSpawned=false;
 if(p.kind==='recover')for(let i=0;i<p.sites.length;i++)world.pickups.push({x:p.sites[i][0],y:p.sites[i][1],type:'mission-intel',spotIndex:i,life:3600});
}
function objectiveInfo(){if(world.endless)return['بقا • پاکسازی موج','موج '+fa(survivalWave(world.mission))];
 const p=plan(),o=world.objective||{done:0,hold:0};
 const progress=p.kind==='defend'?fa(Math.ceil(o.hold))+' / '+fa(p.seconds)+' ثانیه · '+(Math.hypot(world.x-p.sites[0][0],world.y-p.sites[0][1])<2.5?'در منطقه دفاع':'بیرون از منطقه؛ زمان متوقف است'):
 p.kind==='boss'?(o.bossDefeated?'فرمانده شکست خورد':(()=>{const boss=world.enemies.find(e=>e.boss&&e.hp>0);return boss?'زره فرمانده: '+fa(Math.ceil(100*boss.hp/Math.max(1,boss.max)))+'٪':'فرماندهٔ زرهی را پیدا کن'})()):
 fa(o.done)+' / '+fa(p.sites.length);
 return[p.title,progress+' · دشمن '+fa(world.missionKills)+' / '+fa(p.quota)];
}
function interactObjective(){if(screen!=='game'||!world||world.endless||world.missionPassed)return false;
 const p=plan(),o=world.objective,target=objectiveTarget();
 if(!target||!['activate','extract'].includes(p.kind)||o.done>=p.sites.length)return false;
 if(!canInteractAt(world.x,world.y,target[0],target[1])){toast('برای تعامل به علامت نورانی نزدیک شو');return false}
 if(p.kind==='extract'&&world.missionKills<p.quota){toast('ابتدا محدوده را امن کن');return false}
 o.done++;world.score+=250;world.points++;toast(p.kind==='extract'?'استخراج موفق':'سامانه فعال شد • +۲۵۰');playTone(740,.13);sync();save();return true;
}
function updateObjective(dt){if(!world||world.endless)return;const p=plan(),o=world.objective;
 if(p.kind==='defend'&&Math.hypot(world.x-p.sites[0][0],world.y-p.sites[0][1])<2.5){
   o.hold=Math.min(p.seconds,o.hold+dt);if(o.hold>=p.seconds&&!o.done){o.done=1;toast('دفاع موفق • موقعیت تثبیت شد');save()}
 }
 const site=objectiveTarget();world.marker=site?{x:site[0],y:site[1],kind:p.kind}:null;
 if(site){const inInteractRange=['activate','extract'].includes(p.kind)&&canInteractAt(world.x,world.y,site[0],site[1]);const inDefenseZone=p.kind==='defend'&&Math.hypot(world.x-site[0],world.y-site[1])<2.5;const nearIntel=p.kind==='recover'&&Math.hypot(world.x-site[0],world.y-site[1])<.78;const waypoint=(inInteractRange||inDefenseZone||nearIntel)?null:objectiveWaypoint(world.x,world.y,site[0],site[1],(x,y)=>tile(x,y,world.mission)===0)||objectiveApproachWaypoint(world.x,world.y,site[0],site[1],(x,y)=>tile(x,y,world.mission)===0,p.kind==='boss'||p.kind==='defend'?2.5:p.kind==='recover'?.78:INTERACT_RANGE);const arrow=$('#objectiveArrow');arrow.style.visibility=waypoint?'visible':'hidden';arrow.setAttribute('aria-hidden',String(!waypoint));if(waypoint){const bearing=Math.atan2(waypoint.y-world.y,waypoint.x-world.x)-world.angle;arrow.style.transform='rotate('+(-bearing*180/Math.PI+90)+'deg)'}$('#objectiveRange').textContent=inInteractRange?(p.kind==='extract'&&world.missionKills<p.quota?'ابتدا دشمنان باقی‌مانده را پاکسازی کن':'تعامل آماده است · دکمه تعامل را بزن'):inDefenseZone?'در منطقه دفاع · موقعیت را حفظ کن':nearIntel?'بستهٔ اطلاعاتی در حال جمع‌آوری است':waypoint?(waypoint.steps>0?fa(waypoint.steps)+' خانه مسیر':fa(Math.hypot(site[0]-world.x,site[1]-world.y).toFixed(1))+' متر'):'مسیر بسته است';}else{$('#objectiveArrow').style.visibility='hidden';$('#objectiveArrow').setAttribute('aria-hidden','true');$('#objectiveRange').textContent=p.kind==='boss'&&!o.bossDefeated?'فرمانده هنوز ظاهر نشده است':p.kind==='recover'&&o.done<p.sites.length?(world.pickups.some(item=>item.type==='mission-intel')?'مسیر بسته است؛ از مسیر دیگری نزدیک شوید':'بستهٔ اطلاعاتی پیدا نشد؛ مرحله را دوباره بررسی کن'):world.missionKills<p.quota?'هدف موضعی انجام شد · پاکسازی دشمنان باقی مانده':'هدف انجام شد';}
 const hint=$('#interact');if(hint){const near=site&&canInteractAt(world.x,world.y,site[0],site[1]);
 hint.classList.toggle('hidden',!near||!['activate','extract'].includes(p.kind)||p.kind==='extract'&&world.missionKills<p.quota)}
}
function missionObjectiveComplete(){if(world.endless)return world.missionKills>=required();const p=plan(),o=world.objective;
 if(world.missionKills<p.quota)return false;
 if(p.kind==='boss')return o.bossDefeated;
 if(p.kind==='defend')return o.hold>=p.seconds;
 return o.done>=p.sites.length;
}

function resize(){dpr=Math.min(devicePixelRatio||1,1.35);W=gameRoot.clientWidth;H=gameRoot.clientHeight;engine.setSize(W,H,dpr)}addEventListener('resize',resize);resize();
function tile(col,row,m=world?.mission||0){if(col<0||row<0||col>=16||row>=16||col===0||row===0||col===15||row===15)return 1;if(m%3===1&&col===7&&row>=3&&row<=10&&row!==6)return 1;if(m%3===2&&row===8&&col>=3&&col<=11&&col!==8)return 1;if([[3,3],[12,3],[3,11],[5,7],[10,6],[5,4],[12,5],[4,10],[12,10]].some(([x,y])=>col===x&&row===y))return 1;if(col===4&&row===6||col===11&&row===7)return 1;if(m%2===1&&(col===10&&row===4||col===5&&row===11))return 1;return 0}
function newWorld(endless=false){world={hero,mission:0,lives:100,kills:0,missionKills:0,shots:0,ammo:8,magazine:8,reloadTimer:0,combo:0,comboTimer:0,score:0,rocketHits:0,drones:3,rockets:12,points:0,power:0,armor:0,best:0,x:2.5,y:7.5,angle:0,hp:100+(hero%5)*3,maxHp:100+(hero%5)*3,time:0,shotTimer:0,rocketTimer:0,droneTimer:0,enemyTimer:.8,skillTimer:0,shield:3,strikeTimer:0,strikeX:0,strikeY:0,muzzle:0,hitFlash:0,explosionTimer:0,victory:false,gameOver:false,endless,missionPassed:false,hit:false,skillFired:false,freeze:0,enemies:[],hostile:[],missiles:[],pickups:[]};prepareObjective();if(endless){world.mission=6;world.endless=true;world.objective=null;world.best=readSurvivalBest()}screen='play';scoped=false;$('#game').classList.remove('scope-mode');$('#scope').classList.remove('active');$('#scope').setAttribute('aria-pressed','false');engine.scope(false);engine.build(world,tile);save();showScreen('game');last=performance.now();scheduleFrame()}
let saveWarningShown=false,saveStatus='not-saved',foreignSaveDetected=false,lastSavedSnapshot=undefined;function save(){// Never let an idle menu autosave overwrite an invalid or imported campaign.
if(screen==='home'||screen==='heroes')return false;
// Suspended mobile tabs may miss the storage event; compare durable baseline before writes/removals.
if(world&&!world.endless&&lastSavedSnapshot!==undefined&&storageRead(saveKey)!==lastSavedSnapshot){foreignSaveDetected=true;saveStatus='failed';if(!saveWarningShown){saveWarningShown=true;toast('ذخیره در برگهٔ دیگری تغییر کرده است؛ پشتیبان بگیرید و صفحه را بازخوانی کنید')}return false}
if(foreignSaveDetected&&world&&!world.endless){saveStatus='failed';return false}const action=campaignSaveDisposition(world);if(action==='keep'){saveStatus=world?.endless?'survival':'not-saved';return false}if(action==='remove'){try{const removed=storageRemove(saveKey)&&storageRead(saveKey)===null;if(!removed){saveStatus='failed';toast('پاکسازی ذخیرهٔ پایان‌یافته تأیید نشد؛ دوباره تلاش کنید');return false}lastSavedSnapshot=null;foreignSaveDetected=false;saveWarningShown=false;saveStatus='not-saved';return true}catch(_){saveStatus='failed';toast('پاکسازی ذخیرهٔ پایان‌یافته ناموفق بود');return false}}try{const snapshot=JSON.stringify({...world,pickups:boundedCampaignPickups(world.pickups)});const ok=storageWrite(saveKey,snapshot)&&storageRead(saveKey)===snapshot;saveStatus=ok?'saved':'failed';if(ok){saveWarningShown=false;lastSavedSnapshot=snapshot}else if(!saveWarningShown){saveWarningShown=true;toast('ذخیرهٔ مرورگر غیرفعال است؛ از پیشرفت پشتیبان بگیرید')}return ok}catch(_){saveStatus='failed';if(!saveWarningShown){saveWarningShown=true;toast('ذخیرهٔ مرورگر ناموفق بود؛ از پیشرفت پشتیبان بگیرید')}return false}}
function observeExternalCampaignSave(event){
// Clearing the browser storage emits key=null; invalidate the previous campaign snapshot.
if(event.key!==saveKey&&!(event.key===null&&lastSavedSnapshot!==undefined))return false;
if(event.key===saveKey&&event.newValue===lastSavedSnapshot)return false;
foreignSaveDetected=true;if(world&&!world.endless){saveStatus='failed';toast('ذخیرهٔ کارزار در برگهٔ دیگری تغییر کرده است؛ از این برگه پشتیبان بگیرید و سپس صفحه را بازخوانی کنید')}return true}
function warnUnsavedCampaignBeforeExit(event){
 // Flush the latest live campaign before a desktop tab closes; the periodic autosave
 // may still be five seconds behind. A blocked/conflicting save must warn the player.
 if(!world||world.endless||world.victory||world.gameOver)return;
 if(saveStatus!=='failed')save();
 if(saveStatus==='failed'){event.preventDefault();event.returnValue=''}
}
function saveCampaignOnHidden(){
 // Mobile browsers often suspend a hidden tab without pagehide/beforeunload.
 if(document.visibilityState==='hidden'&&world&&!world.endless)save();
}
function updatePauseSaveStatus(){const status=$('#pauseSaveStatus'),retry=$('#retrySave');if(!status||!retry)return;const survival=world?.endless===true;retry.hidden=survival||saveStatus==='saved';status.textContent=foreignSaveDetected?'ذخیره در برگهٔ دیگری تغییر کرده است؛ ابتدا پشتیبان بگیرید، سپس صفحه را بازخوانی کنید.':survival?'حالت بقا ذخیرهٔ کارزار را تغییر نمی‌دهد؛ رکورد موج‌های تکمیل‌شده فقط با اجازهٔ مرورگر نگه‌داری می‌شود.':saveStatus==='saved'?'پیشرفت کارزار در این مرورگر ذخیره شد. برای انتقال به دستگاه دیگر پشتیبان بگیرید.':'ذخیرهٔ خودکار انجام نشد؛ «تلاش دوباره» یا «پشتیبان پیشرفت» را انتخاب کنید.'}
function restore(){// A corrupt disk save must never discard a newer in-memory campaign.
const previousWorld=hasResumableCampaignInMemory()?world:null,previousHero=hero;
world=null;try{const s=parseCampaignSave(storageRead(saveKey));if(!validateCampaignSave(s)){world=previousWorld;saveStatus='failed';return false;}world={ammo:8,magazine:8,reloadTimer:0,combo:0,comboTimer:0,score:0,rocketHits:0,pickups:[],...s};world.power=Math.min(12,world.power??0);world.armor=Math.min(5,world.armor??0);// Keep recovery mission intel at the tail when limiting restored transient drops.
world.pickups=boundedCampaignPickups(world.pickups).slice(-30);if(!world.endless&&!world.objective){prepareObjective()}if(!world.endless&&world.mission===2)restoreRecoveryPickups(world,OPERATIONS[2].sites);if(!world.endless&&world.mission===5)reconcileBossEncounter(world);if(world.x===2.5&&world.y===2.5&&world.missionKills===0)world.y=7.5;restorePlayerPosition(world,(x,y)=>tile(x,y)!==0);if(restoreEnemyPositions(world,(x,y)=>tile(x,y,world.mission)!==0)<0){world=previousWorld;hero=previousHero;saveStatus='failed';return false;}hero=world.hero;world.enemies=world.enemies.slice(0,20);world.enemies.forEach((e,i)=>restoreEnemyRuntime(e,i));world.hostile=(world.hostile||[]).slice(0,100);world.missiles=(world.missiles||[]).slice(0,50);screen='play';engine.build(world,tile);lastSavedSnapshot=storageRead(saveKey);foreignSaveDetected=false;saveStatus='saved';if(resumeCampaignScreen(world)==='success'){showResult('منطقه پاکسازی شد','پیشرفت ذخیره شد؛ موشک و پهپاد در مرحلهٔ بعد شارژ می‌شوند.','success');return true}showScreen('game');last=performance.now();scheduleFrame();toast('بازی ذخیره‌شده ادامه پیدا می‌کند');return true}catch(_){world=previousWorld;hero=previousHero;saveStatus='failed';return false}}
function showScreen(name){if(name!=='game')releaseGameInputs();else if(document.activeElement?.closest?.('.panel'))document.activeElement.blur();screen=name;gameRoot.classList.toggle('playing',name==='game');if(name==='game'&&world)setMissionScene(world.mission);hud.classList.toggle('hidden',name!=='game');for(const id of ['home','heroes','pausePanel','upgradePanel','result'])$('#'+id).classList.toggle('hidden',id!==name&&!(id==='result'&&['success','victory','over'].includes(name)));if(name==='home'){updateHome();updateHomeSaveStatus();$('#survival').classList.toggle('hidden',!sessionWinUnlocked&&storageRead('rwWin')!=='1');$('#start').textContent=hasResumableCampaignInMemory()||storageRead(saveKey)?'ادامهٔ نبرد':'شروع نبرد'}if(name==='game'){hud.classList.remove('hidden');sync()}if(name==='pausePanel')updatePauseSaveStatus()}
function toast(text){const el=$('#toast');el.textContent=text;el.classList.add('on');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('on'),1700)}
function hasResumableCampaignInMemory(){return !!(world&&!world.endless&&!world.victory&&!world.gameOver)}
function resumeInMemoryCampaign(){if(!hasResumableCampaignInMemory())return false;if(world.missionPassed){showResult('منطقه پاکسازی شد','پیشرفت کارزار در حافظهٔ همین صفحه محفوظ است؛ برای نگهداری دائمی پشتیبان بگیرید.','success');return true}showScreen('game');last=performance.now();scheduleFrame();if(saveStatus==='failed')toast('ذخیرهٔ مرورگر ناموفق بود؛ برای جلوگیری از حذف پیشرفت پشتیبان بگیرید');return true}
// An in-memory campaign can be the only surviving copy when storage is blocked.
// Keep this warning visible on Home, not just in the Pause overlay.
function updateHomeSaveStatus(){
 const banner=$('#homeSaveStatus');if(!banner)return;
 const atRisk=hasResumableCampaignInMemory()&&(saveStatus==='failed'||foreignSaveDetected);
 banner.hidden=!atRisk;
 banner.textContent=foreignSaveDetected?'هشدار: ذخیرهٔ کارزار در برگهٔ دیگری تغییر کرده است. پیش از خروج از این صفحه، پشتیبان پیشرفت را دریافت کنید.':'هشدار: پیشرفت فعلی فقط در حافظهٔ این صفحه است و ذخیرهٔ مرورگر تأیید نشده است. اکنون پشتیبان پیشرفت را دریافت کنید.';
}
// Never silently discard the only copy by entering Survival or restarting.
function confirmCampaignReplacement(kind){
 const atRisk=hasResumableCampaignInMemory()&&(saveStatus!=='saved'||foreignSaveDetected);
 const stored=storageRead(saveKey)!==null;
 if(!atRisk&&kind==='survival')return true; // Survival does not alter the stored campaign.
 if(!atRisk&&!stored&&!hasResumableCampaignInMemory())return true;
 const message=atRisk?'پیشرفت فعلی ذخیرهٔ تأییدشده ندارد و با این کار از بین می‌رود. ابتدا پشتیبان پیشرفت را دریافت کنید. آیا ادامه می‌دهید؟':'شروع کارزار تازه، پیشرفت فعلی ذخیره‌شده را جایگزین می‌کند. آیا ادامه می‌دهید؟';
 return confirm(message);
}
function updateHome(){$('#heroName').textContent=NAMES[hero];$('#skillName').textContent=SKILLS[hero%6];$('#portrait').textContent=fa(hero+1);const record=$('#survivalRecord');if(record){const best=readSurvivalBest();record.hidden=(!sessionWinUnlocked&&storageRead('rwWin')!=='1')||best===0;record.textContent=best?'بیشترین موج تکمیل‌شده: '+fa(best):''}}
function sync(){if(!world)return;$('#missionName').textContent=world.endless?'بقای بی‌پایان • موج '+fa(survivalWave(world.mission)):MISSIONS[Math.min(world.mission,5)];$('#hpText').textContent=fa(world.hp);$('#lifeText').textContent=fa(world.lives);$('#hpBar').style.width=(100*world.hp/world.maxHp)+'%';$('#stageText').textContent=fa(world.endless?survivalWave(world.mission):Math.min(world.mission+1,6));$('#progress').textContent=fa(world.missionKills)+' / '+fa(required());const objectiveText=objectiveInfo();$('#objectiveTitle').textContent=objectiveText[0];$('#objectiveDetail').textContent=objectiveText[1];$('#rocketText').textContent=fa(world.rockets);$('#droneText').textContent=fa(world.drones);$('#pointText').textContent=fa(world.points);$('#scoreText').textContent=fa(world.score);$('#ammoText').textContent=world.reloadTimer>0?'تعویض…':fa(world.ammo)+' / '+fa(world.magazine);const reloadButton=$('#reload');if(reloadButton){reloadButton.disabled=world.reloadTimer>0||world.ammo>=world.magazine;reloadButton.textContent=world.reloadTimer>0?'⏳':'↻';reloadButton.setAttribute('aria-label',world.reloadTimer>0?'خشاب در حال تعویض است':'تعویض خشاب (R)')}$('#comboText').textContent=fa(world.combo)+'×';$('#special').disabled=world.skillTimer>0;$('#special').style.opacity=world.skillTimer>0?'.5':'1'}
function required(){return world.endless?8+Math.min(10,world.mission):plan().quota}
function blocked(ax,ay,bx,by){let n=Math.hypot(bx-ax,by-ay)*14;for(let i=1;i<n;i++){let t=i/n;if(tile(ax+(bx-ax)*t|0,ay+(by-ay)*t|0)!==0)return true}return false}
function routeToPlayer(e){const sx=e.x|0,sy=e.y|0,gx=world.x|0,gy=world.y|0,start=sy*16+sx,goal=gy*16+gx;if(start===goal)return null;const prev=new Int16Array(256);prev.fill(-2);prev[start]=-1;const q=new Int16Array(256);let head=0,tail=0;q[tail++]=start;const dirs=[[1,0],[-1,0],[0,1],[0,-1]];while(head<tail&&prev[goal]===-2){const n=q[head++],x=n%16,y=n>>4;for(const [dx,dy]of dirs){const nx=x+dx,ny=y+dy,k=ny*16+nx;if(nx<0||ny<0||nx>=16||ny>=16||prev[k]!==-2||tile(nx,ny)!==0)continue;prev[k]=n;q[tail++]=k}}if(prev[goal]===-2)return null;const path=[];for(let n=goal;n!==start&&n>=0;n=prev[n])path.push([n%16+.5,(n>>4)+.5]);path.reverse();let waypoint=path[0];for(const p of path){if(blocked(e.x,e.y,p[0],p[1]))break;waypoint=p}return waypoint}
function ray(a){let c=Math.cos(a),s=Math.sin(a);for(let d=.035;d<18;d+=.035)if(tile(world.x+c*d|0,world.y+s*d|0)!==0)return d;return 18}
function body(x,y,type,hp){return{x,y,vx:0,vy:0,type,hp,max:hp,life:1.5,targetId:-1,dead:false}}
function spawn(){const pts=[[5.5,2.5],[10.5,2.5],[12.5,5.5],[10.5,10.5],[5.5,10.5],[3.5,12.5],[12.5,12.5],[9.5,6.5],[3.5,8.5]];let [x,y]=world.missionKills===0&&world.enemies.length===0?[8.5,7.5]:pts[Math.floor(Math.random()*pts.length)];if(tile(x|0,y|0)!==0){x=12.5;y=11.5}const n=world.missionKills+world.enemies.length;let bossMission=!world.endless&&world.mission===5&&!world.bossSpawned;let type=bossMission?3:world.mission>=1&&n%7===6?3:world.mission>=2&&Math.random()<.35?2:Math.random()<.2?1:0;let hp=type===3?130+world.mission*18:type===2?88+world.mission*15:type===1?50:39+world.mission*4;let e=body(x,y,bossMission?3:type,bossMission?410:hp);if(bossMission){e.boss=true;world.bossSpawned=true;e.x=8.5;e.y=7.5}e.life=1.5;e.strafe=Math.random()<.5?-1:1;world.enemies.push(e)}
function move(dx,dy){let nx=world.x+dx,ny=world.y+dy;if(tile(nx+Math.sign(dx)*.21|0,world.y|0)===0)world.x=nx;if(tile(world.x|0,ny+Math.sign(dy)*.21|0)===0)world.y=ny}
function targetAim(range,cone=.32){let best=null,bd=Infinity;for(const e of world.enemies){if(!(e.hp>0))continue;let dx=e.x-world.x,dy=e.y-world.y,d=Math.hypot(dx,dy),a=Math.atan2(dy,dx)-world.angle;a=Math.atan2(Math.sin(a),Math.cos(a));if(d<range&&Math.abs(a)<cone&&d<bd&&!blocked(world.x,world.y,e.x,e.y)){best=e;bd=d}}return best}
function nearest(range=Infinity){let best=null,bd=range;for(const e of world.enemies){if(!(e.hp>0))continue;let d=Math.hypot(e.x-world.x,e.y-world.y);if(d<bd){best=e;bd=d}}return best}
function visibleAttack(range=24){let target=null,best=Infinity;const aimPitch=engine.pitch();for(const e of world.enemies){if(!(e.hp>0))continue;let dx=e.x-world.x,dy=e.y-world.y,d=Math.hypot(dx,dy),yaw=Math.atan2(Math.sin(Math.atan2(dy,dx)-world.angle),Math.cos(Math.atan2(dy,dx)-world.angle)),bodyPitch=Math.atan2(1.08-1.62,d),yawTol=Math.atan2(.34,d),pitchTol=Math.atan2(.58,d);if(d<range&&Math.abs(yaw)<=yawTol&&Math.abs(aimPitch-bodyPitch)<=pitchTol&&!blocked(world.x,world.y,e.x,e.y)){const error=Math.hypot(yaw/yawTol,(aimPitch-bodyPitch)/pitchTol);if(error<best){target=e;best=error}}}return target}
function reload(manual=false){if(screen!=='game'||!world||world.reloadTimer>0||world.ammo>=world.magazine)return false;world.reloadTimer=manual?1.05:.95;world.reloading=true;playTone(72,.08);sync();save();return true}
function fire(){if(screen!=='game'||!world||world.missionPassed)return;if(world.reloadTimer>0)return;if(world.ammo<=0){reload();toast('خشاب خالی • تعویض خشاب');return}if(world.shotTimer>0)return;world.shots++;world.ammo--;world.shotTimer=Math.max(.34,.42-(world.hero%5)*.018);world.muzzle=.11;world.recoil=.16;let target=visibleAttack();if(target){const dx=target.x-world.x,dy=target.y-world.y,d=Math.hypot(dx,dy),headPitch=Math.atan2(1.78-1.62,d),headshot=Math.abs(engine.pitch()-headPitch)<Math.atan2(.17,d),damage=(headshot?82:38)+world.power*9+world.hero%6*2;target.hp-=damage;target.hit=.24;target.flash=.18;target.headshot=headshot;target.lastHit=headshot?'سر':'بدن';world.impacts=world.impacts||[];world.impacts.push({x:target.x,y:target.y,height:headshot?1.78:1.08,life:.24,type:headshot?'head':'body'});const reticle=document.querySelector('#reticle');reticle?.classList.remove('hit','headshot');reticle?.classList.add(headshot?'headshot':'hit');clearTimeout(hitTimer);hitTimer=setTimeout(()=>reticle?.classList.remove('hit','headshot'),150);world.comboTimer=4.2;world.score+=headshot?250:100;world.points+=headshot?2:1;toast(headshot?'اصابت سر • +۲۵۰':'اصابت دقیق • +۱۰۰');playTone(headshot?880:560,.055)}else{world.combo=0;world.comboTimer=0;document.querySelector('#reticle')?.classList.remove('hit','headshot');toast('خطا • نشانه‌گیری را دقیق‌تر کن');playTone(130,.035)}sync();if(world.ammo===0)reload();save();}
function launchRocket(){if(screen!=='game'||!world||world.rockets<=0||world.rocketTimer>0||world.missionPassed){toast('موشک آماده نیست');return}let target=targetAim(13)||nearest(13);if(!target){toast('هدف در برد موشک نیست');return}world.rockets--;world.rocketTimer=1.05;let dx=target.x-world.x,dy=target.y-world.y,d=Math.max(.01,Math.hypot(dx,dy));world.missiles.push({x:world.x,y:world.y,vx:dx/d*7.5,vy:dy/d*7.5,life:Math.max(.4,d/7.5+1.2),targetId:world.enemies.indexOf(target)});toast('موشک رهگیر شلیک شد');playTone(160,.12);sync();save()}
function droneStrike(persist=true){if(screen!=='game'||!world||world.drones<=0||world.droneTimer>0||world.missionPassed){toast('پشتیبانی پهپادی آماده نیست');return false}let target=targetAim(12)||nearest(10);if(!target){toast('برای پهپاد دشمنی در برد نیست');return false}world.drones--;world.droneTimer=7;world.strikeX=target.x;world.strikeY=target.y;world.strikeTimer=1.15;toast('پهپاد در راه است');sync();if(persist)save();return true}
function explode(x,y,dmg){world.explosionTimer=.65;world.strikeX=x;world.strikeY=y;world.impacts=world.impacts||[];world.impacts.push({x,y,height:.45,life:.7,type:'blast'});effects.push({type:'blast',life:.7,x:W/2,y:H*.49});for(const e of world.enemies){let d=Math.hypot(e.x-x,e.y-y);if(d<2.3){e.hp-=dmg*(1-d/3);e.hit=.3}}}
function hurt(amount){if(world.gameOver||world.victory||screen!=='game'||world.shield>0||world.hitFlash>0)return;world.hp-=Math.max(1,amount-world.armor*2);world.hitFlash=.38;world.hit=true;if(world.hp<=0){world.lives--;if(world.lives<=0){world.gameOver=true;world.hp=0;showResult('نبرد دشوار بود','۱۰۰ جان مصرف شد. می‌توانی کارزار را از نو آغاز کنی.','over');return}world.hp=world.maxHp;world.x=2.5;world.y=7.5;world.shield=4;world.hostile=[];toast('بازگشت به میدان • جان ذخیره شد')}sync();save()}
function special(){if(screen!=='game'||!world||world.skillTimer>0||world.missionPassed)return;if([1,3,5].includes(world.hero%6)&&!droneStrike(false))return;world.skillTimer=13+world.hero/10;world.skillFired=true;switch(world.hero%6){case 0:world.shield=12;toast('سپر انرژی فعال شد');break;case 1:case 3:case 5:toast('پشتیبانی ویژه');break;case 2:world.hp=Math.min(world.maxHp,world.hp+55);world.shield=4;toast('ترمیم زره');break;case 4:activateTimeStop(world,5);world.hostile=[];toast('توقف زمان • پنج ثانیه');break}sync();save()}
function tick(dt){if(!world||screen!=='game'||world.gameOver||world.victory||world.missionPassed)return;dt=Math.min(.04,Math.max(0,dt));world.time+=dt;const enemyFrozen=advanceTimeStop(world,dt);world.shotTimer=Math.max(0,world.shotTimer-dt);world.reloadTimer=Math.max(0,world.reloadTimer-dt);if(world.reloadTimer===0&&world.ammo<world.magazine&&world.reloading){world.ammo=world.magazine;world.reloading=false;toast('خشاب آماده است');sync();save()}world.comboTimer=Math.max(0,world.comboTimer-dt);if(world.comboTimer===0)world.combo=0;world.explosionTimer=Math.max(0,world.explosionTimer-dt);world.rocketTimer=Math.max(0,world.rocketTimer-dt);world.droneTimer=Math.max(0,world.droneTimer-dt);world.skillTimer=Math.max(0,world.skillTimer-dt);world.shield=Math.max(0,world.shield-dt);world.muzzle=Math.max(0,world.muzzle-dt);world.recoil=Math.max(0,(world.recoil||0)-dt);world.impacts=(world.impacts||[]).filter(x=>(x.life-=dt)>0);world.hitFlash=Math.max(0,world.hitFlash-dt);world.angle+=0;
 if(fireHeld)fire();let pace=(keys.ShiftLeft||keys.ShiftRight?3.85:2.9)+(world.hero%4)*.12;const movement=resolveMovementAxes(joyF,joyS,keys);const forward=movement.forward,side=movement.side;move(Math.cos(world.angle)*forward*pace*dt-Math.sin(world.angle)*side*pace*dt,Math.sin(world.angle)*forward*pace*dt+Math.cos(world.angle)*side*pace*dt);
 updateObjective(dt);if(!enemyFrozen)world.enemyTimer-=dt;if(!enemyFrozen&&world.enemyTimer<=0&&world.enemies.length<6&&(world.missionKills+world.enemies.length<required()||
   (world.mission===5&&!world.endless&&!world.bossSpawned&&!world.objective?.bossDefeated))){spawn();world.enemyTimer=Math.max(.42,1.14-world.mission*.07)}
 for(const e of world.enemies){if(enemyFrozen||!canEnemyAct(e))continue;let dx=world.x-e.x,dy=world.y-e.y,d=Math.hypot(dx,dy);e.moving=false;e.hit=Math.max(0,(e.hit||0)-dt);if(d>1.05){let sp=e.type===3?.74:e.type===1?1.28:e.type===2?1.02:.92,tx=world.x,ty=world.y;if(d>2.7){e.pathTimer=(e.pathTimer||0)-dt;if(e.pathTimer<=0){e.route=routeToPlayer(e);e.pathTimer=.38}if(e.route){tx=e.route[0];ty=e.route[1]}}else{tx=e.x-dy/d*1.15*e.strafe;ty=e.y+dx/d*1.15*e.strafe}const td=Math.max(.01,Math.hypot(tx-e.x,ty-e.y)),ux=(tx-e.x)/td,uy=(ty-e.y)/td,wiggle=(e.type===0?.05:.12)*e.strafe*Math.sin(world.time*1.8+e.x),nx=e.x+(ux-wiggle*uy)*sp*dt,ny=e.y+(uy+wiggle*ux)*sp*dt,ox=e.x,oy=e.y;if(tile(nx|0,oy|0)===0)e.x=nx;if(tile(e.x|0,ny|0)===0)e.y=ny;e.moving=Math.abs(e.x-ox)+Math.abs(e.y-oy)>.0005}e.life-=dt;const hasLOS=!blocked(e.x,e.y,world.x,world.y);if(e.life<=0&&d<8.5&&hasLOS){e.life=e.type===3?1.65:e.type===1?1.28:e.type===2?1.85:2.2;let b=body(e.x,e.y,0,e.type===3?14:8);b.vx=dx/Math.max(d,.01)*(e.type===1?5.3:4.2);b.vy=dy/Math.max(d,.01)*(e.type===1?5.3:4.2);b.life=5;world.hostile.push(b)}if(d<.82)hurt(e.type===3?18:11);if(world.gameOver)return}
 for(const b of world.hostile){if(!enemyFrozen&&advanceHostileProjectile(b,dt,world,(x,y)=>tile(x,y)!==0))hurt(b.hp);if(world.gameOver)return}
 for(const m of world.missiles){if(!missileMotionValid(m,dt)){m.life=-1;continue}let target=world.enemies[m.targetId];if(target&&target.hp>0){let dx=target.x-m.x,dy=target.y-m.y,d=Math.max(.01,Math.hypot(dx,dy));m.vx=dx/d*8;m.vy=dy/d*8;if(d<.55){explode(m.x,m.y,145);m.life=-1;continue}}if(!missileMotionValid(m,dt)){m.life=-1;continue}if(missilePathBlocked(m,dt,(x,y)=>tile(x,y)!==0)){explode(m.x,m.y,145);m.life=-1;continue}m.x+=m.vx*dt;m.y+=m.vy*dt;m.life-=dt;if(m.life<0)explode(m.x,m.y,100)}
 let earnedProgressThisTick=false;for(let i=world.enemies.length-1;i>=0;i--){const e=world.enemies[i];if(shouldCleanupEnemy(e)){earnedProgressThisTick=true;removeEnemyAndRetargetMissiles(world.enemies,world.missiles,i);if(e.boss&&world.objective)world.objective.bossDefeated=true;world.missionKills++;world.kills++;world.combo++;world.comboTimer=4.2;world.score+=100*world.combo;if(world.combo>1)toast('ترکیب '+fa(world.combo)+'× • امتیاز افزایشی');if(world.missionKills%4===0)world.rockets=Math.min(24,world.rockets+1);if(world.missionKills%6===0)world.drones=Math.min(7,world.drones+1);if(world.missionKills%3===0)world.points++;if(world.kills%3===0){const type=world.hp<72?'health':world.ammo<=4?'ammo':['ammo','health','intel'][Math.floor(Math.random()*3)];world.pickups.push({x:e.x,y:e.y,type,life:22})}}}world.hostile=world.hostile.filter(x=>x.life>=0);world.missiles=world.missiles.filter(x=>x.life>=0);
 for(let i=world.pickups.length-1;i>=0;i--){const p=world.pickups[i];if(p.type!=='mission-intel')p.life-=dt;if(Math.hypot(world.x-p.x,world.y-p.y)<.78){if(p.type==='mission-intel'){const o=world.objective;const index=p.spotIndex;if(!o||!Number.isInteger(index)||index<0||index>2){world.pickups.splice(i,1);continue}if(o.done>=3||Array.isArray(o.collectedSites)&&o.collectedSites.includes(index)){world.pickups.splice(i,1);continue}if(Array.isArray(o.collectedSites)){o.collectedSites.push(index);o.collectedSites.sort((a,b)=>a-b);o.done=o.collectedSites.length}else{o.done++}world.score+=300;world.points++;world.pickups.splice(i,1);toast('اطلاعات حیاتی بازیابی شد');sync();save();continue}if(p.type==='health'){world.hp=Math.min(world.maxHp,world.hp+28);if(world.hp===world.maxHp)world.points++}else if(p.type==='ammo'){const before=world.ammo;world.ammo=Math.min(world.magazine,world.ammo+4);if(before===world.ammo)world.points++}else{world.points+=2;world.score+=200}world.pickups.splice(i,1);earnedProgressThisTick=true;toast(p.type==='health'?'جعبهٔ امداد • زره ترمیم شد':p.type==='ammo'?'مهمات بازیابی شد':'اطلاعات بازیابی شد • +۲ اعتبار');sync()}else if(p.type!=='mission-intel'&&p.life<=0)world.pickups.splice(i,1)}
 if(earnedProgressThisTick)save();
 if(world.strikeTimer>0){world.strikeTimer-=dt;if(world.strikeTimer<=0){explode(world.strikeX,world.strikeY,235);for(const e of world.enemies)if(Math.hypot(e.x-world.strikeX,e.y-world.strikeY)<2.4)e.hp=0}}
 if(missionObjectiveComplete()&&world.enemies.length===0){if(world.endless){recordSurvivalBest();world.mission++;world.best=Math.max(world.best,survivalWave(world.mission)-1);world.missionKills=0;prepareMission()}else{world.missionPassed=true;world.points++;save();showResult('منطقه پاکسازی شد','پیشرفت ذخیره شد؛ موشک و پهپاد در مرحلهٔ بعد شارژ می‌شوند.','success')}}if(world.time%1<dt)sync();if(world.hit)world.hit=false
}
function prepareMission(){world.x=2.5;world.y=7.5;world.angle=0;world.hp=Math.min(world.maxHp,world.hp+40);world.rockets=Math.min(12,world.rockets+3);world.drones=Math.min(3,world.drones+1);world.missionKills=0;world.missionPassed=false;world.victory=false;world.gameOver=false;world.enemyTimer=.8;world.shotTimer=world.rocketTimer=world.droneTimer=world.skillTimer=0;world.shield=3;world.enemies=[];world.hostile=[];world.missiles=[];world.pickups=[];world.bossSpawned=false;prepareObjective();engine.build(world,tile);save()}
function showResult(title,text,type){screen=type;showScreen(type);$('#resultTitle').textContent=title;$('#continue').classList.toggle('hidden',type==='victory'||type==='over');$('#retry').classList.toggle('hidden',type!=='victory'&&type!=='over');$('#continue').textContent=world?.mission>=5?'پایان کارزار':'مرحلهٔ بعد';$('#resultMark').textContent=type==='victory'?'🏁':type==='over'?'↻':'✦';if(type==='victory'){sessionWinUnlocked=true;storageWrite('rwWin','1');}const saved=save();const verified=type==='success'&&saved&&saveStatus==='saved';$('#resultText').textContent=type==='success'&&!verified?'مرحله کامل شد، اما ذخیرهٔ مرورگر تأیید نشد. پیش از خروج فایل پشتیبان پیشرفت را دریافت کنید.':text;$('#resultSaveStatus').textContent=type==='success'?(verified?'ذخیرهٔ مرحله در این مرورگر تأیید شد.':'هشدار: ذخیرهٔ مرحله انجام نشد؛ پشتیبان پیشرفت را دریافت کنید.'):(type==='victory'||type==='over')&&saveStatus==='failed'?'هشدار: پاکسازی ذخیرهٔ پایان‌یافته ناموفق بود. دوباره تلاش کنید.':'';$('#resultRetryClear').hidden=!(type==='victory'||type==='over')||saveStatus!=='failed';$('#resultExport').hidden=type!=='success'}
function nextMission(){if(!world)return;if(world.mission>=5){world.victory=true;showResult('کارزار با پیروزی پایان یافت','در پایان داستان خیالی، قرارگاه فرماندهی واشنگتن تصرف شد.','victory');return}world.mission++;prepareMission();screen='game';showScreen('game');last=performance.now();scheduleFrame()}
function updateUpgradeButtons(){if(!world)return;document.querySelectorAll('[data-up]').forEach(button=>{const result=canApplyEarnedUpgrade(world,Number(button.dataset.up));button.disabled=!result.ok;button.setAttribute('aria-disabled',String(!result.ok));button.title=result.reason==='cap'?'به سقف ارتقا رسیده است':result.reason==='points'?'امتیاز کافی نیست':''})}
function upgrade(k){if(screen!=='upgradePanel'||!world)return;const result=applyEarnedUpgrade(world,k);if(!result.ok){toast(result.reason==='cap'?'این ارتقا به سقف رسیده است':result.reason==='points'?'امتیاز ارتقا کافی نیست':'ارتقا نامعتبر است');updateUpgradeButtons();return}save();sync();$('#upgradePoints').textContent=fa(world.points);$('#upgradePoints2').textContent=fa(world.points);updateUpgradeButtons();toast('ارتقا با امتیاز بازی انجام شد')}

function project(a){let d=Math.hypot(a.x-world.x,a.y-world.y),bearing=Math.atan2(a.y-world.y,a.x-world.x)-world.angle;bearing=Math.atan2(Math.sin(bearing),Math.cos(bearing));return{x:W/2+Math.tan(bearing)/Math.tan(FOV/2)*W/2,d,bearing}}
function drawEnemy(e,t,depths){let p=project(e),sx=p.x,d=p.d;if(Math.abs(p.bearing)>FOV*.66||d<.15||sx<-100||sx>W+100)return;let c=Math.max(0,Math.min(depths.length-1,Math.floor(sx/W*depths.length)));if(d>depths[c]+.22)return;let size=Math.min(H*.66,H*.51/d),cy=H*.49+size*.05+Math.sin(t/270+(e.seed||0))*1.5;ctx.save();ctx.translate(sx,cy);ctx.fillStyle='#0008';ctx.beginPath();ctx.ellipse(0,size*.43,size*.24,size*.06,0,0,Math.PI*2);ctx.fill();if(e.type===2){ctx.fillStyle='#303e42';ctx.fillRect(-size*.27,-size*.15,size*.54,size*.19);ctx.strokeStyle='#c9a34e';ctx.lineWidth=Math.max(2,size*.02);ctx.beginPath();ctx.moveTo(-size*.46,-size*.07);ctx.lineTo(size*.46,-size*.07);ctx.moveTo(-size*.38,-size*.2);ctx.lineTo(size*.38,-size*.2);ctx.stroke();ctx.fillStyle='#ed604a';ctx.beginPath();ctx.arc(0,0,size*.04,0,7);ctx.fill()}else{let scale=e.type===3?1.55:e.type===1?1.06:1;let w=size*.2*scale;ctx.fillStyle=e.type===3?'#677579':e.type===1?'#716549':'#40594b';ctx.fillRect(-w,-size*.04,w*2,size*.44);ctx.fillStyle='#17282a';ctx.fillRect(-w*.65,size*.32,w*.42,size*.22);ctx.fillRect(w*.23,size*.32,w*.42,size*.22);ctx.strokeStyle='#27322e';ctx.lineWidth=Math.max(3,w*.36);ctx.beginPath();ctx.moveTo(-w*.8,size*.05);ctx.lineTo(-w*1.2,size*.28);ctx.moveTo(w*.8,size*.05);ctx.lineTo(w*1.4,size*.01);ctx.stroke();ctx.strokeStyle='#111918';ctx.lineWidth=Math.max(3,w*.18);ctx.beginPath();ctx.moveTo(w*.8,size*.01);ctx.lineTo(w*2.35,size*.1);ctx.stroke();ctx.fillStyle='#d2af8c';ctx.beginPath();ctx.arc(0,-size*.18,w*.52,0,Math.PI*2);ctx.fill();ctx.fillStyle=e.type===3?'#656b68':'#353b36';ctx.fillRect(-w*.62,-size*.22,w*1.24,size*.09);ctx.fillStyle='#1b2929';ctx.fillRect(-w*.8,-size*.03,w*1.6,size*.055)}let bw=size*.42;ctx.fillStyle='#172927';ctx.fillRect(-bw/2,-size*.34,bw,Math.max(3,size*.018));ctx.fillStyle=e.type===2?'#e4aa53':'#ee7563';ctx.fillRect(-bw/2,-size*.34,bw*clamp(e.hp/e.max,0,1),Math.max(3,size*.018));ctx.restore()}
function render(ts){engine.render(world,ts);if(world){gameRoot.classList.toggle('firing',world.muzzle>0);const el=$('#missionBackdrop'),panX=Math.max(-38,Math.min(38,-world.angle*92-(world.x-2.5)*7)),panY=Math.max(-28,Math.min(28,(world.y-7.5)*5));el.style.setProperty('--pan-x',panX.toFixed(1)+'px');el.style.setProperty('--pan-y',panY.toFixed(1)+'px')}}
// One RAF owner across pause/resume, mission transitions and rapid taps.
// A pending callback is reused when play resumes before the browser delivers it.
let frameQueued=false;
function scheduleFrame(){if(screen!=='game'||frameQueued)return;frameQueued=true;requestAnimationFrame(frame)}
function frame(ts){frameQueued=false;if(screen!=='game')return;const elapsed=Math.min(.32,Math.max(0,(ts-last)/1000||.016));last=ts;const steps=Math.max(1,Math.ceil(elapsed/.04));for(let i=0;i<steps&&screen==='game';i++)tick(elapsed/steps);render(ts);if(screen==='game')scheduleFrame()}
function playTone(freq,dur){if(!soundEnabled)return;try{audioCtx=audioCtx||new(window.AudioContext||window.webkitAudioContext)();const o=audioCtx.createOscillator(),g=audioCtx.createGain();o.type='square';o.frequency.value=freq;g.gain.value=.025;o.connect(g);g.connect(audioCtx.destination);o.start();o.stop(audioCtx.currentTime+dur)}catch(_){}}
function modalResultHome(){const keepUnsaved=!!(world&&!world.endless&&world.missionPassed&&saveStatus!=='saved');if(!keepUnsaved)world=null;showScreen('home');if(keepUnsaved)toast('پیشرفت ذخیره نشده است؛ «ادامهٔ نبرد» یا پشتیبان پیشرفت را انتخاب کنید')}
syncSoundControls();$('#soundHome').onclick=toggleSound;$('#soundPause').onclick=toggleSound;
let scoped=false;$('#scope').onclick=()=>{scoped=!scoped;$('#game').classList.toggle('scope-mode',scoped);$('#scope').classList.toggle('active',scoped);$('#scope').setAttribute('aria-pressed',String(scoped));engine.scope(scoped)};$('#reload').onclick=()=>reload(true);$('#fullscreen').onclick=async()=>{try{if(!document.fullscreenElement){if(!gameRoot.requestFullscreen){toast('تمام‌صفحه در این مرورگر پشتیبانی نمی‌شود');return}await gameRoot.requestFullscreen()}else if(document.exitFullscreen)await document.exitFullscreen()}catch(_){toast('تمام‌صفحه در این مرورگر پشتیبانی نمی‌شود')}};$('#prevHero').onclick=()=>{hero=(hero+29)%30;storageWrite('rwHero',hero);updateHome()};$('#nextHero').onclick=()=>{hero=(hero+1)%30;storageWrite('rwHero',hero);updateHome()};$('#chooseHero').onclick=()=>{const grid=$('#heroGrid');grid.innerHTML='';NAMES.forEach((n,i)=>{const b=document.createElement('button');b.className='hero-card'+(i===hero?' selected':'');b.innerHTML=n+'<small>'+SKILLS[i%6]+'</small>';b.onclick=()=>{hero=i;storageWrite('rwHero',hero);updateHome();showScreen('home')};grid.appendChild(b)});showScreen('heroes')};$('#heroBack').onclick=()=>showScreen('home');$('#start').onclick=()=>{if(hasResumableCampaignInMemory()&&(saveStatus==='failed'||storageRead(saveKey)===null)&&resumeInMemoryCampaign())return;if(storageRead(saveKey)){if(!restore()){if(hasResumableCampaignInMemory()&&resumeInMemoryCampaign()){toast('فایل ذخیرهٔ مرورگر نامعتبر است؛ پیشرفت محفوظ در این صفحه ادامه یافت. پشتیبان بگیرید.');return}toast('ذخیرهٔ قبلی نامعتبر است؛ برای شروع مجدد «بازی تازه» را انتخاب کنید');return}}else newWorld(false)};$('#newGame').onclick=()=>{if(!confirmCampaignReplacement('new'))return;newWorld(false)};
function exportCampaignBackup(){
 if(world&&!world.endless)save();
 // Export the current paused campaign even if browser storage is unavailable or stale.
 const current=world&&!world.endless?JSON.stringify({...world,pickups:boundedCampaignPickups(world.pickups)}):storageRead(saveKey);
 const backup=makeCampaignBackup(current);
 if(!backup){toast('پیشرفت معتبر برای پشتیبان‌گیری پیدا نشد');return}
 let url=null;
 try{
  url=URL.createObjectURL(new Blob([backup],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download='ramadan-war-campaign-backup.json';
  document.body.appendChild(a);
  try{a.click()}finally{a.remove()}
  // Keep the object URL alive for slow mobile download hand-off.
  const pendingUrl=url;setTimeout(()=>URL.revokeObjectURL(pendingUrl),60000);
  url=null;
  toast('درخواست دانلود پشتیبان ارسال شد؛ ذخیرهٔ فایل را در دانلودها بررسی کنید');
 }catch(_){
  if(url)URL.revokeObjectURL(url);
  toast('دانلود پشتیبان ممکن نشد؛ پیشرفت فعلی را حفظ کنید و دوباره تلاش کنید');
 }
}
$('#exportSave').onclick=exportCampaignBackup;$('#exportPauseSave').onclick=exportCampaignBackup;$('#resultExport').onclick=exportCampaignBackup;$('#resultRetryClear').onclick=()=>{const ok=save();if(ok){$('#resultRetryClear').hidden=true;$('#resultSaveStatus').textContent='ذخیرهٔ پایان‌یافته پاکسازی و تأیید شد.'}else $('#resultSaveStatus').textContent='پاکسازی ذخیره ناموفق بود؛ ذخیرهٔ قدیمی هنوز ممکن است موجود باشد.'};$('#retrySave').onclick=()=>{save();updatePauseSaveStatus();if(saveStatus==='saved')toast('پیشرفت کارزار اکنون ذخیره شد')};
$('#importSave').onclick=()=>$('#importSaveFile').click();
$('#importSaveFile').onchange=async e=>{
 const input=e.currentTarget,file=input.files?.[0];input.value='';
 if(!file)return;
 if(file.size>MAX_CAMPAIGN_BACKUP_BYTES){toast('حجم فایل پشتیبان بیش از حد مجاز است');return}
 let imported=null;try{imported=readCampaignBackup(await file.text())}catch(_){imported=null}
 if(!imported){toast('فایل پشتیبان معتبر نیست؛ پیشرفت فعلی محفوظ ماند');return}
 if((hasResumableCampaignInMemory()||storageRead(saveKey)!==null)&&!confirm('بازیابی، پیشرفت فعلی (از جمله پیشرفت ذخیره‌نشده در همین صفحه) را جایگزین می‌کند. ادامه می‌دهید؟'))return;
 const priorSave=storageRead(saveKey);
// Import is a destructive replacement: refuse a stale-tab overwrite.
if(foreignSaveDetected||(lastSavedSnapshot!==undefined&&priorSave!==lastSavedSnapshot)){
 toast('ذخیره در برگهٔ دیگری تغییر کرده است؛ از این برگه پشتیبان بگیرید و سپس صفحه را بازخوانی کنید');return;
}
 if(!storageWrite(saveKey,imported)||storageRead(saveKey)!==imported){toast('مرورگر ذخیرهٔ فایل را تأیید نکرد؛ پیشرفت فعلی محفوظ ماند');return}
 // Activate the imported campaign before committing to it. A backup can be
 // structurally valid but still fail runtime geometry or graphics recovery.
 if(!restore()){
  const rolledBack=priorSave===null?storageRemove(saveKey):storageWrite(saveKey,priorSave);
  toast(rolledBack?'بازیابی این فایل ممکن نشد؛ ذخیرهٔ قبلی محفوظ ماند':'بازیابی ناموفق بود و بازگردانی ذخیرهٔ قبلی نیز ناموفق شد؛ از صفحه خارج نشوید و پشتیبان بگیرید');
  return;
 }
 saveStatus='saved';lastSavedSnapshot=imported;foreignSaveDetected=false;storageWrite('rwHero',hero);updateHome();toast('پشتیبان بازیابی شد و نبرد آمادهٔ ادامه است');
};$('#survival').onclick=()=>{if(!confirmCampaignReplacement('survival'))return;newWorld(true)};$('#pause').onclick=()=>{save();showScreen('pausePanel')};$('#resume').onclick=()=>{showScreen('game');last=performance.now();scheduleFrame()};$('#openUpgrades').onclick=()=>{if(world){$('#upgradePoints').textContent=fa(world.points);$('#upgradePoints2').textContent=fa(world.points);showScreen('upgradePanel');updateUpgradeButtons();$('#moj1Status').textContent='خرید با '+MOJ1_COMMERCE.asset+' فعلاً غیرفعال است؛ امتیازهای ارتقا فقط در بازی به‌دست می‌آیند.'}};$('#upgradeBack').onclick=()=>{showScreen('game');last=performance.now();scheduleFrame()};document.querySelectorAll('[data-up]').forEach(b=>b.onclick=()=>upgrade(+b.dataset.up));$('#goHome').onclick=()=>{save();showScreen('home')};$('#continue').onclick=nextMission;$('#retry').onclick=()=>{if(!confirmCampaignReplacement('retry'))return;newWorld(false)};$('#resultHome').onclick=modalResultHome;$('#rocket').onpointerdown=e=>{if(!isPrimaryGameplayPress(e))return;e.preventDefault();launchRocket()};$('#rocket').onclick=e=>{if(isKeyboardOrAssistiveClick(e))launchRocket()};$('#drone').onpointerdown=e=>{if(!isPrimaryGameplayPress(e))return;e.preventDefault();droneStrike()};$('#drone').onclick=e=>{if(isKeyboardOrAssistiveClick(e))droneStrike()};$('#special').onpointerdown=e=>{if(!isPrimaryGameplayPress(e))return;e.preventDefault();special()};$('#special').onclick=e=>{if(isKeyboardOrAssistiveClick(e))special()};$('#fire').onpointerdown=e=>{if(!isPrimaryGameplayPress(e)||!canCaptureGameplayPointer(fireId,e.pointerId,screen))return;e.preventDefault();fireId=e.pointerId;try{$('#fire').setPointerCapture(e.pointerId)}catch(_){fireId=null;return}updateHeldFire();fire()};function endFire(e){if(!isOwnedGameplayPointer(fireId,e.pointerId))return;fireId=null;updateHeldFire()}$('#fire').onpointerup=$('#fire').onpointercancel=$('#fire').onlostpointercapture=endFire;$('#fire').onclick=e=>{if(isKeyboardOrAssistiveClick(e))fire()};$('#interact').onpointerdown=e=>{if(!isPrimaryGameplayPress(e))return;e.preventDefault();interactObjective()};$('#interact').onclick=e=>{if(isKeyboardOrAssistiveClick(e))interactObjective()};
const stick=$('#stick'),knob=$('#knob');function stickMove(e){let r=stick.getBoundingClientRect(),dx=e.clientX-(r.left+r.width/2),dy=e.clientY-(r.top+r.height/2),lim=r.width*.36,len=Math.hypot(dx,dy)||1,x=dx/len*Math.min(len,lim),y=dy/len*Math.min(len,lim);knob.style.transform=`translate(${x}px,${y}px)`;const axes=joystickAxes(x,y,lim);joyF=axes.forward;joyS=axes.side}stick.onpointerdown=e=>{if(!isPrimaryGameplayPress(e)||!canCaptureGameplayPointer(joyId,e.pointerId,screen))return;e.preventDefault();joyId=e.pointerId;try{stick.setPointerCapture(e.pointerId)}catch(_){joyId=null;return}stickMove(e)};stick.onpointermove=e=>{if(e.pointerId===joyId)stickMove(e)};function endStick(e){if(e.pointerId!==joyId)return;joyId=null;joyF=joyS=0;knob.style.transform=''}stick.onpointerup=endStick;stick.onpointercancel=endStick;stick.onlostpointercapture=endStick;
// Aiming with a finger (including landscape tablets) must never fire a shot.
// A desktop mouse drag is also an aim gesture, not a click-to-fire action.
let aimY=0,aimGesture=null;
canvas.addEventListener('pointerdown',e=>{
 if(!isPrimaryGameplayPress(e)||!canCaptureGameplayPointer(aimId,e.pointerId,screen))return;
 aimId=e.pointerId;aimLast=e.clientX;aimY=e.clientY;
 aimGesture={pointerId:e.pointerId,pointerType:e.pointerType,startX:e.clientX,startY:e.clientY,moved:0,finished:false,cancelled:false};
 try{canvas.setPointerCapture(e.pointerId)}catch(_){aimId=null;aimGesture=null}
});
canvas.addEventListener('pointermove',e=>{
 if(aimId!==e.pointerId||!world)return;
 recordPointerGestureMovement(aimGesture,e);
 let dx=e.clientX-aimLast,dy=e.clientY-aimY;world.angle-=dx*(W<700?.008:.0045);engine.look(0,dy,W);aimLast=e.clientX;aimY=e.clientY
});
canvas.addEventListener('pointerup',e=>{if(e.pointerId!==aimId)return;recordPointerGestureMovement(aimGesture,e);aimId=null;if(aimGesture)aimGesture.finished=true});
canvas.addEventListener('pointercancel',e=>{if(e.pointerId!==aimId)return;aimId=null;if(aimGesture)aimGesture.cancelled=true});
canvas.addEventListener('lostpointercapture',e=>{if(e.pointerId!==aimId)return;aimId=null;if(aimGesture&&!aimGesture.finished)aimGesture.cancelled=true});
canvas.addEventListener('click',e=>{const eligible=shouldFireCanvasClick(e,screen,innerWidth,aimGesture);aimGesture=null;if(eligible)fire()});
function updateHeldFire(){fireHeld=isFireHeld(keys.Space,fireId)}
function safeReleaseCapture(element,pointerId){if(pointerId===null||pointerId===undefined)return;try{if(element?.hasPointerCapture?.(pointerId))element.releasePointerCapture(pointerId)}catch(_){}}
function releaseGameInputs(){const oldFire=fireId,oldJoy=joyId,oldAim=aimId;keys={};fireHeld=false;fireId=null;joyId=null;aimId=null;joyF=joyS=0;aimGesture=null;knob.style.transform='';safeReleaseCapture($('#fire'),oldFire);safeReleaseCapture(stick,oldJoy);safeReleaseCapture(canvas,oldAim)}
addEventListener('keydown',e=>{
 if(screen!=='game'||isInteractiveTarget(e.target))return;
 // Release keyboard-held movement/fire on browser shortcuts or IME input.
 // The browser may swallow keyup while a Ctrl/Alt/Meta shortcut is active.
 if(isModifiedOrComposingKey(e)){keys={};updateHeldFire();return;}
 const action=keyboardAction(e.code,screen,e.target,e.repeat);
 if(['Space','ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.code))e.preventDefault();
 if(action==='pause'){e.preventDefault();$('#pause').click();return}
 keys[e.code]=true;
 if(action==='rocket')launchRocket();
 else if(action==='drone')droneStrike();
 else if(action==='special')special();
 else if(action==='reload')reload(true);
 else if(action==='interact')interactObjective();
 else if(action==='fire')updateHeldFire();
});
addEventListener('keyup',e=>{keys[e.code]=false;if(e.code==='Space')updateHeldFire()});
addEventListener('compositionstart',()=>{keys={};updateHeldFire()});
// Keyboard focus may move to a HUD control without a window blur or keyup.
// Preserve a genuinely held touch fire pointer while releasing keyboard input.
document.addEventListener('focusin',e=>{if(shouldReleaseHeldKeysOnFocus(screen,e.target)){keys={};updateHeldFire()}});
addEventListener('blur',()=>{releaseGameInputs();if(screen==='game')$('#pause').click()});
document.addEventListener('visibilitychange',()=>{if(document.hidden){releaseGameInputs();if(screen==='game')$('#pause').click()}});
addEventListener('pagehide',save);addEventListener('storage',observeExternalCampaignSave);addEventListener('beforeunload',warnUnsavedCampaignBeforeExit);addEventListener('visibilitychange',saveCampaignOnHidden);setInterval(save,5000);
const qaIsLocal=['localhost','127.0.0.1'].includes(location.hostname);
const debugApi={
 heroes:Object.freeze([...NAMES]),skills:Object.freeze([...SKILLS]),
 getState:()=>world&&({mode:screen,hero:world.hero,stage:world.mission,hp:world.hp,maxHp:world.maxHp,lives:world.lives,rockets:world.rockets,drones:world.drones,kills:world.kills,missionKills:world.missionKills,enemies:world.enemies.length,shots:world.shots||0,points:world.points,objective:world.objective?JSON.parse(JSON.stringify(world.objective)):null,objectiveKind:world.endless?'survival':plan().kind,objectiveTarget:objectiveTarget(),...engine.stats(),score:world.score,ammo:world.ammo,combo:world.combo})
};
if(qaIsLocal)Object.assign(debugApi,{
 selectHero:n=>{hero=(n+30)%30;storageWrite('rwHero',hero);updateHome()},
 start:()=>newWorld(false),fire,rocket:launchRocket,drone:droneStrike,tick,reload:()=>reload(true),
 spawnTestEnemy:()=>{if(world){const e=body(6.5,7.5,0,39);e.strafe=1;world.enemies.push(e)}},
 interact:interactObjective,
 qaPosition:()=>world?{x:world.x,y:world.y}:null,
 qaMove:(x,y)=>{if(!world||tile(x|0,y|0)!==0)return false;world.x=x;world.y=y;updateObjective(0);return true},
 qaMission:n=>{if(!world||n<0||n>5)return false;world.mission=n;prepareMission();return true},
 spawnTestPickup:(type='ammo')=>{if(world)world.pickups.push({x:world.x,y:world.y,type:['ammo','health','intel'].includes(type)?type:'ammo',life:10})}
});
window.RamadanWarDebug=Object.freeze(debugApi);if(hasResumableCampaignInMemory()||storageRead(saveKey))$('#start').textContent='ادامهٔ نبرد';showScreen('home');engine.build({hero:0,mission:0,x:2.5,y:7.5,angle:.08,muzzle:0,enemies:[],missiles:[]},tile);engine.render(null,0)
})();
