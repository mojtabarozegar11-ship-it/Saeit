import {createEngine} from './engine3d.js';
(()=>{'use strict';
const NAMES=['سید علی خامنه‌ای','حاج قاسم — قاسم سلیمانی','عباس بابایی','علی صیاد شیرازی','مصطفی چمران','محمدابراهیم همت','مهدی باکری','حمید باکری','حسین خرازی','حسن باقری','احمد کاظمی','محمد جهان‌آرا','محمود کاوه','مهدی زین‌الدین','عباس دوران','حسین لشکری','مسعود منفرد نیاکی','ولی‌الله فلاحی','یوسف کلاهدوز','جواد فکوری','موسی نامجو','محمد بروجردی','احمد متوسلیان','عبدالحسین برونسی','ناصر کاظمی','علی هاشمی','منصور ستاری','ایرج رستمی','مصطفی اردستانی','حسین خلعتبری'];
const SKILLS=['سپر انرژی','موج الکترومغناطیس','ترمیم زره','طوفان پالس','توقف زمان','پشتیبانی مداری'];
const MISSIONS=['تهران • دفاع از پایتخت','تنگهٔ کوهستان • رهگیری پهپادها','جزیرهٔ خارک • پایگاه رباتیک','بندرعباس • عملیات شبانه','کالیفرنیا • پایگاه ساحلی','واشنگتن • تصرف قرارگاه فرماندهی'];
const $=s=>document.querySelector(s), canvas=$('#view'),hud=$('#hud'),gameRoot=$('#game');let W=1,H=1,dpr=1;const engine=createEngine(canvas);
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)), rnd=(a,b)=>a+Math.random()*(b-a), fa=n=>String(Math.max(0,Math.floor(n))).replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
const saveKey='rwNativeCampaign',stageNames=NAMES;
const sceneFiles=['./scene-sniper-desert-v2.webp','./scene-night.webp','./scene-airbase.webp'];function setMissionScene(m){const el=$('#missionBackdrop'),file=sceneFiles[m%sceneFiles.length];if(el.dataset.scene!==file){el.style.backgroundImage=`url("${file}")`;el.dataset.scene=file}el.style.setProperty('--pan-x','0px');el.style.setProperty('--pan-y','0px')}

const safeHero=v=>{const n=Number(v);return Number.isInteger(n)&&n>=0&&n<NAMES.length?n:0};
let enemySerial=0;
// Private browsing and embedded browsers may block all persistent storage.
// Keep the game playable in memory when access is denied.
const storage={
 get(key){try{return localStorage.getItem(key)}catch(_){return null}},
 set(key,value){try{localStorage.setItem(key,String(value))}catch(_){}},
 remove(key){try{localStorage.removeItem(key)}catch(_){}},
};
let hero=safeHero(storage.get('rwHero')),world=null,screen='home',last=0,toastTimer=0,hitTimer=0,fireHeld=false,joyId=null,aimId=null,joyX=0,joyY=0,joyF=0,joyS=0,aimLast=0,keys={},effects=[],audioCtx=null;
const MAPSIZE=16,FOV=1.02;
// Periodic checkpointing preserves long missions even if the tab closes without pausing.
let nextCheckpointAt=12;

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
 if(p.kind==='recover'){const item=world.pickups.find(p=>p.type==='mission-intel');return item?[item.x,item.y]:null}
 return o.done>=p.sites.length?null:p.sites[o.done];
}
function prepareObjective(){if(world.endless)return;const p=plan();
 world.objective={done:0,hold:0,bossDefeated:false};world.bossSpawned=false;
 if(p.kind==='recover')for(let i=0;i<p.sites.length;i++)world.pickups.push({x:p.sites[i][0],y:p.sites[i][1],type:'mission-intel',spotIndex:i,life:3600});
}
function objectiveInfo(){if(world.endless)return['بقا • پاکسازی موج','موج '+fa(world.mission+1)];
 const p=plan(),o=world.objective||{done:0,hold:0};
 const progress=p.kind==='defend'?fa(Math.ceil(o.hold))+' / '+fa(p.seconds)+' ثانیه':
 p.kind==='boss'?(o.bossDefeated?'فرمانده شکست خورد':'فرماندهٔ زرهی را پیدا کن'):
 fa(o.done)+' / '+fa(p.sites.length);
 return[p.title,progress+' · دشمن '+fa(world.missionKills)+' / '+fa(p.quota)];
}
function interactObjective(){if(screen!=='game'||!world||world.endless||world.missionPassed)return false;
 const p=plan(),o=world.objective,target=objectiveTarget();
 if(!target||!['activate','extract'].includes(p.kind)||o.done>=p.sites.length)return false;
 if(Math.hypot(world.x-target[0],world.y-target[1])>1.35){toast('برای تعامل به علامت نورانی نزدیک شو');return false}
 if(p.kind==='extract'&&world.missionKills<p.quota){toast('ابتدا محدوده را امن کن');return false}
 o.done++;world.score+=250;world.points++;toast(p.kind==='extract'?'استخراج موفق':'سامانه فعال شد • +۲۵۰');playTone(740,.13);sync();return true;
}
function updateObjective(dt){if(!world||world.endless)return;const p=plan(),o=world.objective;
 if(p.kind==='defend'&&Math.hypot(world.x-p.sites[0][0],world.y-p.sites[0][1])<2.5){
   o.hold=Math.min(p.seconds,o.hold+dt);if(o.hold>=p.seconds&&!o.done){o.done=1;toast('دفاع موفق • موقعیت تثبیت شد')}
 }
 const site=objectiveTarget();world.marker=site?{x:site[0],y:site[1],kind:p.kind}:null;
 if(site){const bearing=Math.atan2(site[1]-world.y,site[0]-world.x)-world.angle;$('#objectiveArrow').style.transform='rotate('+(-bearing*180/Math.PI+90)+'deg)';$('#objectiveRange').textContent=fa(Math.hypot(site[0]-world.x,site[1]-world.y).toFixed(0))+' متر';}else{$('#objectiveRange').textContent='هدف انجام شد';}
 const hint=$('#interact');if(hint){const near=site&&Math.hypot(world.x-site[0],world.y-site[1])<1.55;
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
function newWorld(endless=false){enemySerial=0;world={hero,mission:0,lives:100,kills:0,missionKills:0,shots:0,ammo:8,magazine:8,reloadTimer:0,combo:0,comboTimer:0,score:0,rocketHits:0,drones:3,rockets:12,points:0,power:0,armor:0,best:1,x:2.5,y:7.5,angle:0,hp:100+(hero%5)*3,maxHp:100+(hero%5)*3,time:0,shotTimer:0,rocketTimer:0,droneTimer:0,enemyTimer:.8,skillTimer:0,shield:3,strikeTimer:0,strikeX:0,strikeY:0,muzzle:0,hitFlash:0,explosionTimer:0,victory:false,gameOver:false,endless,missionPassed:false,hit:false,skillFired:false,freeze:0,enemies:[],hostile:[],missiles:[],pickups:[]};nextCheckpointAt=12;prepareObjective();if(endless){world.mission=6;world.endless=true;world.objective=null}screen='play';scoped=false;$('#game').classList.remove('scope-mode');$('#scope').classList.remove('active');engine.scope(false);engine.build(world,tile);save();showScreen('game');last=performance.now();requestAnimationFrame(frame)}
function save(){if(!world)return;try{if(world.mission<6&&!world.victory&&!world.gameOver)storage.set(saveKey,JSON.stringify(world));else storage.remove(saveKey)}catch(_){}}
function validSavedWorld(s){
 if(!s||typeof s!=='object'||Array.isArray(s)||!Array.isArray(s.enemies)||s.endless||s.victory||s.gameOver)return false;
 const within=(v,lo,hi)=>Number.isFinite(v)&&v>=lo&&v<=hi;
 if(!Number.isInteger(s.mission)||!within(s.mission,0,5)||!Number.isInteger(s.hero)||safeHero(s.hero)!==s.hero)return false;
 if(!within(s.x,1,14)||!within(s.y,1,14)||tile(s.x|0,s.y|0,s.mission)!==0||!within(s.angle,-1e6,1e6)||!within(s.hp,1,10000)||!within(s.maxHp,1,10000)||s.hp>s.maxHp)return false;
 if(!within(s.lives,1,100)||!within(s.ammo,0,8)||!within(s.rockets,0,24)||!within(s.drones,0,7)||!within(s.score,0,1e9))return false;
 // Persisted progress must never poison wave spawning, timers, or mission completion.
 for(const k of ['missionKills','kills','shots','points','combo','rocketHits','time']){
   if(s[k]!==undefined&&(!within(s[k],0,k==='time'?31536000:1e9)||(k!=='time'&&!Number.isSafeInteger(s[k]))))return false;
 }
 if(s.missionPassed!==undefined&&typeof s.missionPassed!=='boolean')return false;
 if(s.objective!=null){
   const o=s.objective;
   if(typeof o!=='object'||Array.isArray(o)||!Number.isInteger(o.done)||!within(o.done,0,10)||!within(o.hold,0,3600)||typeof o.bossDefeated!=='boolean')return false;
   // A restored objective cannot claim more activated sites or defense time than this mission permits.
   const missionPlan=OPERATIONS[s.mission];
   if(o.done>missionPlan.sites.length||o.hold>(missionPlan.seconds||0))return false;
 }
 if(s.enemies.length>20||!s.enemies.every(e=>e&&within(e.x,1,14)&&within(e.y,1,14)&&within(e.hp,-1000,10000)))return false;
 return [['pickups',200],['hostile',300],['missiles',200]].every(([k,cap])=>s[k]===undefined||(Array.isArray(s[k])&&s[k].length<=cap));
}
// Saved browser state is untrusted. Preserve legitimate projectiles and mission items,
// but drop off-map, over-speed or malformed objects before they enter the render/physics loop.
function cleanSavedProjectiles(items,cap,kind){
 if(!Array.isArray(items))return [];
 return items.slice(0,200).filter(p=>p&&typeof p==='object'&&!Array.isArray(p)&&
  [p.x,p.y,p.vx,p.vy,p.life].every(Number.isFinite)&&
  p.x>=0&&p.x<=16&&p.y>=0&&p.y<=16&&p.life>0&&p.life<=12&&
  Math.hypot(p.vx,p.vy)<=25&&
  (kind!=='hostile'||Number.isFinite(p.hp)&&p.hp>=0&&p.hp<=1000)).slice(0,cap);
}
function cleanSavedPickups(items){
 if(!Array.isArray(items))return [];
 return items.slice(0,200).filter(p=>p&&typeof p==='object'&&!Array.isArray(p)&&
  [p.x,p.y,p.life].every(Number.isFinite)&&p.x>=0&&p.x<=16&&
  p.y>=0&&p.y<=16&&p.life>0&&p.life<=3600&&
  ['ammo','health','intel','mission-intel'].includes(p.type)).slice(0,30);
}
function restore(){try{const s=JSON.parse(storage.get(saveKey)||'null');if(!validSavedWorld(s))return false;world={ammo:8,magazine:8,reloadTimer:0,combo:0,comboTimer:0,score:0,rocketHits:0,missionKills:0,kills:0,points:0,time:0,pickups:[],...s};nextCheckpointAt=world.time+12;
 // Old or tampered saves must not turn cooldowns into NaN and soft-lock combat.
 for(const k of ['shotTimer','rocketTimer','droneTimer','skillTimer','reloadTimer','comboTimer','shield','strikeTimer','muzzle','hitFlash','explosionTimer','freeze'])world[k]=Number.isFinite(world[k])?clamp(world[k],0,60):0;
 world.enemyTimer=Number.isFinite(world.enemyTimer)?clamp(world.enemyTimer,0,60):.8;
 world.reloading=world.reloading===true;
 world.pickups=cleanSavedPickups(world.pickups);if(!world.endless&&!world.objective){prepareObjective()}if(world.x===2.5&&world.y===2.5&&world.missionKills===0)world.y=7.5;hero=world.hero;world.enemies=world.enemies.slice(0,20);const seenEnemyIds=new Set();world.enemies.forEach((e,i)=>{if(!Number.isFinite(e.strafe))e.strafe=i%2?1:-1;e.stun=Number.isFinite(e.stun)?clamp(e.stun,0,3.5):0;
 // Imported or legacy saves may omit enemy max HP, attack timers, or type; never feed NaN into combat/rendering.
 e.max=Math.max(1,e.hp,Number.isFinite(e.max)&&e.max>=1&&e.max<=10000?e.max:0);
 e.life=Number.isFinite(e.life)?clamp(e.life,0,30):1.5;
 e.type=Number.isInteger(e.type)&&e.type>=0&&e.type<=3?e.type:0;
 e.hit=Number.isFinite(e.hit)?clamp(e.hit,0,3):0;
 e.flash=Number.isFinite(e.flash)?clamp(e.flash,0,3):0;if(!Number.isSafeInteger(e.uid)||e.uid<=0||e.uid>1000000||seenEnemyIds.has(e.uid)){let next=1;while(seenEnemyIds.has(next))next++;e.uid=next}seenEnemyIds.add(e.uid)});enemySerial=Math.max(0,...seenEnemyIds);world.hostile=cleanSavedProjectiles(world.hostile,100,'hostile');world.missiles=cleanSavedProjectiles(world.missiles,50,'missile');screen='play';engine.build(world,tile);if(world.missionPassed){showResult('منطقه پاکسازی شد','پیشرفت ذخیره شده است؛ برای ادامه مرحلهٔ بعد را انتخاب کنید.','success');toast('مرحلهٔ پایان‌یافته بازیابی شد');return true}showScreen('game');last=performance.now();requestAnimationFrame(frame);toast('بازی ذخیره‌شده ادامه پیدا می‌کند');return true}catch(_){return false}}
function showScreen(name){screen=name;gameRoot.classList.toggle('playing',name==='game');if(name==='game'&&world)setMissionScene(world.mission);hud.classList.toggle('hidden',name!=='game');for(const id of ['home','heroes','pausePanel','upgradePanel','result'])$('#'+id).classList.toggle('hidden',id!==name&&!(id==='result'&&['success','victory','over'].includes(name)));if(name==='home'){updateHome();$('#survival').classList.toggle('hidden',storage.get('rwWin')!=='1');$('#start').textContent=storage.get(saveKey)?'ادامهٔ نبرد':'شروع نبرد'}if(name==='game'){hud.classList.remove('hidden');sync()}}
function toast(text){const el=$('#toast');el.textContent=text;el.classList.add('on');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('on'),1700)}
function updateHome(){$('#heroName').textContent=NAMES[hero];$('#skillName').textContent=SKILLS[hero%6];$('#portrait').textContent=fa(hero+1)}
function sync(){if(!world)return;$('#missionName').textContent=world.endless?'بقای بی‌پایان • موج '+fa(world.mission+1):MISSIONS[Math.min(world.mission,5)];$('#hpText').textContent=fa(world.hp);$('#lifeText').textContent=fa(world.lives);$('#hpBar').style.width=(100*world.hp/world.maxHp)+'%';$('#stageText').textContent=fa(Math.min(world.mission+1,6));$('#progress').textContent=fa(world.missionKills)+' / '+fa(required());const objectiveText=objectiveInfo();$('#objectiveTitle').textContent=objectiveText[0];$('#objectiveDetail').textContent=objectiveText[1];$('#rocketText').textContent=fa(world.rockets);$('#droneText').textContent=fa(world.drones);$('#pointText').textContent=fa(world.points);$('#scoreText').textContent=fa(world.score);$('#ammoText').textContent=world.reloadTimer>0?'تعویض…':fa(world.ammo)+' / '+fa(world.magazine);$('#comboText').textContent=fa(world.combo)+'×';$('#special').disabled=world.skillTimer>0;$('#special').style.opacity=world.skillTimer>0?'.5':'1'}
function required(){return world.endless?8+Math.min(10,world.mission):plan().quota}
// Swept projectile contact prevents fast bullets passing through the player between frames.
function segmentHitsCircle(ax,ay,bx,by,cx,cy,r){const dx=bx-ax,dy=by-ay,den=dx*dx+dy*dy;const t=den>0?clamp(((cx-ax)*dx+(cy-ay)*dy)/den,0,1):0;return Math.hypot(ax+t*dx-cx,ay+t*dy-cy)<=r}
function blocked(ax,ay,bx,by){let n=Math.hypot(bx-ax,by-ay)*14;for(let i=1;i<n;i++){let t=i/n;if(tile(ax+(bx-ax)*t|0,ay+(by-ay)*t|0)!==0)return true}return false}
function routeToPlayer(e){const sx=e.x|0,sy=e.y|0,gx=world.x|0,gy=world.y|0,start=sy*16+sx,goal=gy*16+gx;if(start===goal)return null;const prev=new Int16Array(256);prev.fill(-2);prev[start]=-1;const q=new Int16Array(256);let head=0,tail=0;q[tail++]=start;const dirs=[[1,0],[-1,0],[0,1],[0,-1]];while(head<tail&&prev[goal]===-2){const n=q[head++],x=n%16,y=n>>4;for(const [dx,dy]of dirs){const nx=x+dx,ny=y+dy,k=ny*16+nx;if(nx<0||ny<0||nx>=16||ny>=16||prev[k]!==-2||tile(nx,ny)!==0)continue;prev[k]=n;q[tail++]=k}}if(prev[goal]===-2)return null;const path=[];for(let n=goal;n!==start&&n>=0;n=prev[n])path.push([n%16+.5,(n>>4)+.5]);path.reverse();let waypoint=path[0];for(const p of path){if(blocked(e.x,e.y,p[0],p[1]))break;waypoint=p}return waypoint}
function ray(a){let c=Math.cos(a),s=Math.sin(a);for(let d=.035;d<18;d+=.035)if(tile(world.x+c*d|0,world.y+s*d|0)!==0)return d;return 18}
function body(x,y,type,hp){return{x,y,vx:0,vy:0,type,hp,max:hp,life:1.5,targetId:-1,dead:false}}
function spawn(){const pts=[[5.5,2.5],[10.5,2.5],[12.5,5.5],[10.5,10.5],[5.5,10.5],[3.5,12.5],[12.5,12.5],[9.5,6.5],[3.5,8.5]];let [x,y]=world.missionKills===0&&world.enemies.length===0?[8.5,7.5]:pts[Math.floor(Math.random()*pts.length)];if(tile(x|0,y|0)!==0){x=12.5;y=11.5}const n=world.missionKills+world.enemies.length;let bossMission=!world.endless&&world.mission===5&&!world.bossSpawned;let type=bossMission?3:world.mission>=1&&n%7===6?3:world.mission>=2&&Math.random()<.35?2:Math.random()<.2?1:0;let hp=type===3?130+world.mission*18:type===2?88+world.mission*15:type===1?50:39+world.mission*4;let e=body(x,y,bossMission?3:type,bossMission?410:hp);if(bossMission){e.boss=true;world.bossSpawned=true;e.x=8.5;e.y=7.5}e.life=1.5;e.strafe=Math.random()<.5?-1:1;e.uid=++enemySerial;world.enemies.push(e)}
function move(dx,dy){let nx=world.x+dx,ny=world.y+dy;if(tile(nx+Math.sign(dx)*.21|0,world.y|0)===0)world.x=nx;if(tile(world.x|0,ny+Math.sign(dy)*.21|0)===0)world.y=ny}
function targetAim(range,cone=.32){let best=null,bd=Infinity;for(const e of world.enemies){let dx=e.x-world.x,dy=e.y-world.y,d=Math.hypot(dx,dy),a=Math.atan2(dy,dx)-world.angle;a=Math.atan2(Math.sin(a),Math.cos(a));if(d<range&&Math.abs(a)<cone&&d<bd&&!blocked(world.x,world.y,e.x,e.y)){best=e;bd=d}}return best}
function nearest(range=Infinity){let best=null,bd=range;for(const e of world.enemies){let d=Math.hypot(e.x-world.x,e.y-world.y);if(d<bd){best=e;bd=d}}return best}
function visibleAttack(range=24){let target=null,best=Infinity;const aimPitch=engine.pitch();for(const e of world.enemies){let dx=e.x-world.x,dy=e.y-world.y,d=Math.hypot(dx,dy),yaw=Math.atan2(Math.sin(Math.atan2(dy,dx)-world.angle),Math.cos(Math.atan2(dy,dx)-world.angle)),bodyPitch=Math.atan2(1.08-1.62,d),yawTol=Math.atan2(.34,d),pitchTol=Math.atan2(.58,d);if(d<range&&Math.abs(yaw)<=yawTol&&Math.abs(aimPitch-bodyPitch)<=pitchTol&&!blocked(world.x,world.y,e.x,e.y)){const error=Math.hypot(yaw/yawTol,(aimPitch-bodyPitch)/pitchTol);if(error<best){target=e;best=error}}}return target}
function reload(manual=false){if(!world||world.reloadTimer>0||world.ammo>=world.magazine)return false;world.reloadTimer=manual?1.05:.95;world.reloading=true;fireHeld=false;playTone(72,.08);sync();return true}
function fire(){if(screen!=='game'||!world||world.missionPassed)return;if(world.reloadTimer>0)return;if(world.ammo<=0){reload();toast('خشاب خالی • تعویض خشاب');return}if(world.shotTimer>0)return;world.shots++;world.ammo--;world.shotTimer=Math.max(.34,.42-(world.hero%5)*.018);world.muzzle=.11;world.recoil=.16;let target=visibleAttack();if(target){const dx=target.x-world.x,dy=target.y-world.y,d=Math.hypot(dx,dy),headPitch=Math.atan2(1.78-1.62,d),headshot=Math.abs(engine.pitch()-headPitch)<Math.atan2(.17,d),damage=(headshot?82:38)+world.power*9+world.hero%6*2;target.hp-=damage;target.hit=.24;target.flash=.18;target.headshot=headshot;target.lastHit=headshot?'سر':'بدن';world.impacts=world.impacts||[];world.impacts.push({x:target.x,y:target.y,height:headshot?1.78:1.08,life:.24,type:headshot?'head':'body'});const reticle=document.querySelector('#reticle');reticle?.classList.remove('hit','headshot');reticle?.classList.add(headshot?'headshot':'hit');clearTimeout(hitTimer);hitTimer=setTimeout(()=>reticle?.classList.remove('hit','headshot'),150);world.comboTimer=4.2;world.score+=headshot?250:100;world.points+=headshot?2:1;toast(headshot?'اصابت سر • +۲۵۰':'اصابت دقیق • +۱۰۰');playTone(headshot?880:560,.055)}else{world.combo=0;world.comboTimer=0;document.querySelector('#reticle')?.classList.remove('hit','headshot');toast('خطا • نشانه‌گیری را دقیق‌تر کن');playTone(130,.035)}sync();if(world.ammo===0)reload();}
function launchRocket(){if(screen!=='game'||!world||world.rockets<=0||world.rocketTimer>0||world.missionPassed){toast('موشک آماده نیست');return}let target=targetAim(13)||nearest(13);if(!target){toast('هدف در برد موشک نیست');return}world.rockets--;world.rocketTimer=1.05;let dx=target.x-world.x,dy=target.y-world.y,d=Math.max(.01,Math.hypot(dx,dy));world.missiles.push({x:world.x,y:world.y,vx:dx/d*7.5,vy:dy/d*7.5,life:Math.max(.4,d/7.5+1.2),targetUid:target.uid});toast('موشک رهگیر شلیک شد');playTone(160,.12);sync();save()}
function droneStrike(){if(screen!=='game'||!world||world.drones<=0||world.droneTimer>0||world.missionPassed){toast('پشتیبانی پهپادی آماده نیست');return}let target=targetAim(12)||nearest(10);if(!target){toast('برای پهپاد دشمنی در برد نیست');return}world.drones--;world.droneTimer=7;world.strikeX=target.x;world.strikeY=target.y;world.strikeTimer=1.15;toast('پهپاد در راه است');sync();save()}
function explode(x,y,dmg){world.explosionTimer=.65;world.strikeX=x;world.strikeY=y;world.impacts=world.impacts||[];world.impacts.push({x,y,height:.45,life:.7,type:'blast'});effects.push({type:'blast',life:.7,x:W/2,y:H*.49});for(const e of world.enemies){let d=Math.hypot(e.x-x,e.y-y);if(d<2.3){e.hp-=dmg*(1-d/3);e.hit=.3}}}
function hurt(amount){if(world.shield>0||world.hitFlash>0)return;world.hp-=Math.max(1,amount-world.armor*2);world.hitFlash=.38;world.hit=true;if(world.hp<=0){world.lives--;if(world.lives<=0){world.gameOver=true;world.hp=0;showResult('نبرد دشوار بود','۱۰۰ جان مصرف شد. می‌توانی کارزار را از نو آغاز کنی.','over');return}world.hp=world.maxHp;world.x=2.5;world.y=7.5;world.shield=4;world.hostile=[];toast('بازگشت به میدان • جان ذخیره شد')}sync()}
function special(){
 if(screen!=='game'||!world||world.skillTimer>0||world.missionPassed)return;
 const skill=world.hero%6;
 // Orbital support needs a real target. Do not consume a cooldown on a failed lock.
 const target=skill===5?(targetAim(14)||nearest(12)):null;
 if(skill===5&&!target){toast('هدف برای پشتیبانی مداری پیدا نشد');return}
 world.skillTimer=13+world.hero/10;world.skillFired=true;
 switch(skill){
  case 0:world.shield=12;toast('سپر انرژی فعال شد');break;
  case 1:
   world.hostile=[];
   for(const e of world.enemies)e.stun=Math.max(e.stun||0,3.5);
   toast('موج الکترومغناطیس • دشمنان موقتاً از کار افتادند');break;
  case 2:world.hp=Math.min(world.maxHp,world.hp+55);world.shield=4;toast('ترمیم زره');break;
  case 3:
   for(const e of world.enemies){const d=Math.hypot(e.x-world.x,e.y-world.y);if(d<4.5){e.hp-=Math.round(85*(1-d/4.5));e.hit=.3}}
   world.hostile=world.hostile.filter(b=>Math.hypot(b.x-world.x,b.y-world.y)>4.5);
   toast('طوفان پالس • ضربه منطقه‌ای');break;
  case 4:world.freeze=5;toast('توقف زمان • پنج ثانیه');break;
  case 5:
   world.strikeX=target.x;world.strikeY=target.y;world.strikeTimer=1.15;
   toast('پشتیبانی مداری • هدف قفل شد');break;
 }
 sync();save();
}
function tick(dt){if(!world||screen!=='game'||world.gameOver||world.victory||world.missionPassed)return;dt=Math.min(.04,Math.max(0,dt));world.time+=dt;if(world.time>=nextCheckpointAt){nextCheckpointAt=world.time+12;save()}world.shotTimer=Math.max(0,world.shotTimer-dt);world.reloadTimer=Math.max(0,world.reloadTimer-dt);if(world.reloadTimer===0&&world.ammo<world.magazine&&world.reloading){world.ammo=world.magazine;world.reloading=false;toast('خشاب آماده است')}world.comboTimer=Math.max(0,world.comboTimer-dt);if(world.comboTimer===0)world.combo=0;world.explosionTimer=Math.max(0,world.explosionTimer-dt);world.rocketTimer=Math.max(0,world.rocketTimer-dt);world.droneTimer=Math.max(0,world.droneTimer-dt);world.skillTimer=Math.max(0,world.skillTimer-dt);world.shield=Math.max(0,world.shield-dt);world.freeze=Math.max(0,world.freeze-dt);world.muzzle=Math.max(0,world.muzzle-dt);world.recoil=Math.max(0,(world.recoil||0)-dt);world.impacts=(world.impacts||[]).filter(x=>(x.life-=dt)>0);world.hitFlash=Math.max(0,world.hitFlash-dt);world.angle+=0;
 if(fireHeld)fire();let pace=(keys.ShiftLeft||keys.ShiftRight?3.85:2.9)+(world.hero%4)*.12;let forward=joyF,side=joyS;if(keys.KeyW||keys.ArrowUp)forward=1;if(keys.KeyS||keys.ArrowDown)forward=-1;if(keys.KeyA)side=-1;if(keys.KeyD)side=1;const length=Math.hypot(forward,side);if(length>1){forward/=length;side/=length}move(Math.cos(world.angle)*forward*pace*dt-Math.sin(world.angle)*side*pace*dt,Math.sin(world.angle)*forward*pace*dt+Math.cos(world.angle)*side*pace*dt);
 updateObjective(dt);if(world.freeze<=0)world.enemyTimer-=dt;if(world.freeze<=0&&world.enemyTimer<=0&&world.enemies.length<6&&world.missionKills+world.enemies.length<required()){spawn();world.enemyTimer=Math.max(.42,1.14-world.mission*.07)}
 for(const e of world.enemies){let dx=world.x-e.x,dy=world.y-e.y,d=Math.hypot(dx,dy);e.moving=false;e.hit=Math.max(0,(e.hit||0)-dt);if(world.freeze>0||(e.stun||0)>0){e.stun=Math.max(0,(e.stun||0)-dt);continue}if(d>1.05){let sp=e.type===3?.74:e.type===1?1.28:e.type===2?1.02:.92,tx=world.x,ty=world.y;if(d>2.7){e.pathTimer=(e.pathTimer||0)-dt;if(e.pathTimer<=0){e.route=routeToPlayer(e);e.pathTimer=.38}if(e.route){tx=e.route[0];ty=e.route[1]}}else{tx=e.x-dy/d*1.15*e.strafe;ty=e.y+dx/d*1.15*e.strafe}const td=Math.max(.01,Math.hypot(tx-e.x,ty-e.y)),ux=(tx-e.x)/td,uy=(ty-e.y)/td,wiggle=(e.type===0?.05:.12)*e.strafe*Math.sin(world.time*1.8+e.x),nx=e.x+(ux-wiggle*uy)*sp*dt,ny=e.y+(uy+wiggle*ux)*sp*dt,ox=e.x,oy=e.y;if(tile(nx|0,oy|0)===0)e.x=nx;if(tile(e.x|0,ny|0)===0)e.y=ny;e.moving=Math.abs(e.x-ox)+Math.abs(e.y-oy)>.0005}e.life-=dt;const hasLOS=!blocked(e.x,e.y,world.x,world.y);if(e.life<=0&&d<8.5&&hasLOS){e.life=e.type===3?1.65:e.type===1?1.28:e.type===2?1.85:2.2;let b=body(e.x,e.y,0,e.type===3?14:8);b.vx=dx/Math.max(d,.01)*(e.type===1?5.3:4.2);b.vy=dy/Math.max(d,.01)*(e.type===1?5.3:4.2);b.life=5;world.hostile.push(b)}if(d<.82)hurt(e.type===3?18:11)}
 for(const b of world.hostile){if(world.freeze>0)continue;const nx=b.x+b.vx*dt,ny=b.y+b.vy*dt;b.life-=dt;if(blocked(b.x,b.y,nx,ny)||tile(nx|0,ny|0)!==0){b.life=-1;continue}if(segmentHitsCircle(b.x,b.y,nx,ny,world.x,world.y,.31)){hurt(b.hp);b.life=-1;continue}b.x=nx;b.y=ny}
 for(const m of world.missiles){let target=m.targetUid?world.enemies.find(e=>e.uid===m.targetUid):world.enemies[m.targetId];if(target&&target.hp>0){let dx=target.x-m.x,dy=target.y-m.y,d=Math.max(.01,Math.hypot(dx,dy));m.vx=dx/d*8;m.vy=dy/d*8;if(d<.55){explode(m.x,m.y,145);m.life=-1;continue}}else if(tile((m.x+m.vx*dt)|0,(m.y+m.vy*dt)|0)!==0){explode(m.x,m.y,145);m.life=-1;continue}m.x+=m.vx*dt;m.y+=m.vy*dt;m.life-=dt;if(m.life<0)explode(m.x,m.y,100)}
 for(let i=world.enemies.length-1;i>=0;i--){const e=world.enemies[i];if(e.hp<=0||e.life< -4){world.enemies.splice(i,1);if(e.boss&&world.objective)world.objective.bossDefeated=true;world.missionKills++;world.kills++;world.combo++;world.comboTimer=4.2;world.score+=100*world.combo;if(world.combo>1)toast('ترکیب '+fa(world.combo)+'× • امتیاز افزایشی');if(world.missionKills%4===0)world.rockets=Math.min(24,world.rockets+1);if(world.missionKills%6===0)world.drones=Math.min(7,world.drones+1);if(world.missionKills%3===0)world.points++;if(world.kills%3===0){const type=world.hp<72?'health':world.ammo<=4?'ammo':['ammo','health','intel'][Math.floor(Math.random()*3)];world.pickups.push({x:e.x,y:e.y,type,life:22})}}}world.hostile=world.hostile.filter(x=>x.life>=0);world.missiles=world.missiles.filter(x=>x.life>=0);
 for(let i=world.pickups.length-1;i>=0;i--){const p=world.pickups[i];p.life-=dt;if(Math.hypot(world.x-p.x,world.y-p.y)<.78){if(p.type==='mission-intel'){if(world.objective)world.objective.done++;world.score+=300;world.points++;world.pickups.splice(i,1);toast('اطلاعات حیاتی بازیابی شد');sync();continue}if(p.type==='health'){world.hp=Math.min(world.maxHp,world.hp+28);if(world.hp===world.maxHp)world.points++}else if(p.type==='ammo'){const before=world.ammo;world.ammo=Math.min(world.magazine,world.ammo+4);if(before===world.ammo)world.points++}else{world.points+=2;world.score+=200}world.pickups.splice(i,1);toast(p.type==='health'?'جعبهٔ امداد • زره ترمیم شد':p.type==='ammo'?'مهمات بازیابی شد':'اطلاعات بازیابی شد • +۲ اعتبار');sync()}else if(p.life<=0)world.pickups.splice(i,1)}
 if(world.strikeTimer>0){world.strikeTimer-=dt;if(world.strikeTimer<=0){explode(world.strikeX,world.strikeY,235);for(const e of world.enemies)if(Math.hypot(e.x-world.strikeX,e.y-world.strikeY)<2.4)e.hp=0}}
 if(missionObjectiveComplete()&&world.enemies.length===0){if(world.endless){world.mission++;world.best=Math.max(world.best,world.mission+1);world.missionKills=0;prepareMission()}else{world.missionPassed=true;world.points++;save();showResult('منطقه پاکسازی شد','پیشرفت ذخیره شد؛ موشک و پهپاد در مرحلهٔ بعد شارژ می‌شوند.','success')}}if(world.time%1<dt)sync();if(world.hit)world.hit=false
}
function prepareMission(){world.x=2.5;world.y=7.5;world.angle=0;world.hp=Math.min(world.maxHp,world.hp+40);world.rockets=Math.min(12,world.rockets+3);world.drones=Math.min(3,world.drones+1);world.missionKills=0;world.missionPassed=false;world.victory=false;world.gameOver=false;world.enemyTimer=.8;world.shotTimer=world.rocketTimer=world.droneTimer=world.skillTimer=0;world.shield=3;world.enemies=[];world.hostile=[];world.missiles=[];world.pickups=[];world.bossSpawned=false;prepareObjective();engine.build(world,tile);save()}
function showResult(title,text,type){screen=type;showScreen(type);$('#resultTitle').textContent=title;$('#resultText').textContent=text;$('#continue').classList.toggle('hidden',type==='victory'||type==='over');$('#retry').classList.toggle('hidden',type!=='victory'&&type!=='over');$('#continue').textContent=world?.mission>=5?'پایان کارزار':'مرحلهٔ بعد';$('#resultMark').textContent=type==='victory'?'🏁':type==='over'?'↻':'✦';if(type==='victory')storage.set('rwWin','1');save()}
function nextMission(){if(!world)return;if(world.mission>=5){world.victory=true;storage.remove(saveKey);showResult('کارزار با پیروزی پایان یافت','در پایان داستان خیالی، قرارگاه فرماندهی واشنگتن تصرف شد.','victory');return}world.mission++;prepareMission();screen='game';showScreen('game');last=performance.now();requestAnimationFrame(frame)}
function upgrade(k){if(!world||world.points<1){toast('امتیاز ارتقا کافی نیست');return}world.points--;if(k===0)world.power++;else if(k===1){world.armor++;world.maxHp+=20;world.hp=Math.min(world.maxHp,world.hp+30)}else if(k===2)world.rockets=Math.min(24,world.rockets+6);else world.drones=Math.min(7,world.drones+2);save();sync();$('#upgradePoints').textContent=fa(world.points);$('#upgradePoints2').textContent=fa(world.points);toast('ارتقا انجام شد')}
function project(a){let d=Math.hypot(a.x-world.x,a.y-world.y),bearing=Math.atan2(a.y-world.y,a.x-world.x)-world.angle;bearing=Math.atan2(Math.sin(bearing),Math.cos(bearing));return{x:W/2+Math.tan(bearing)/Math.tan(FOV/2)*W/2,d,bearing}}
function drawEnemy(e,t,depths){let p=project(e),sx=p.x,d=p.d;if(Math.abs(p.bearing)>FOV*.66||d<.15||sx<-100||sx>W+100)return;let c=Math.max(0,Math.min(depths.length-1,Math.floor(sx/W*depths.length)));if(d>depths[c]+.22)return;let size=Math.min(H*.66,H*.51/d),cy=H*.49+size*.05+Math.sin(t/270+(e.seed||0))*1.5;ctx.save();ctx.translate(sx,cy);ctx.fillStyle='#0008';ctx.beginPath();ctx.ellipse(0,size*.43,size*.24,size*.06,0,0,Math.PI*2);ctx.fill();if(e.type===2){ctx.fillStyle='#303e42';ctx.fillRect(-size*.27,-size*.15,size*.54,size*.19);ctx.strokeStyle='#c9a34e';ctx.lineWidth=Math.max(2,size*.02);ctx.beginPath();ctx.moveTo(-size*.46,-size*.07);ctx.lineTo(size*.46,-size*.07);ctx.moveTo(-size*.38,-size*.2);ctx.lineTo(size*.38,-size*.2);ctx.stroke();ctx.fillStyle='#ed604a';ctx.beginPath();ctx.arc(0,0,size*.04,0,7);ctx.fill()}else{let scale=e.type===3?1.55:e.type===1?1.06:1;let w=size*.2*scale;ctx.fillStyle=e.type===3?'#677579':e.type===1?'#716549':'#40594b';ctx.fillRect(-w,-size*.04,w*2,size*.44);ctx.fillStyle='#17282a';ctx.fillRect(-w*.65,size*.32,w*.42,size*.22);ctx.fillRect(w*.23,size*.32,w*.42,size*.22);ctx.strokeStyle='#27322e';ctx.lineWidth=Math.max(3,w*.36);ctx.beginPath();ctx.moveTo(-w*.8,size*.05);ctx.lineTo(-w*1.2,size*.28);ctx.moveTo(w*.8,size*.05);ctx.lineTo(w*1.4,size*.01);ctx.stroke();ctx.strokeStyle='#111918';ctx.lineWidth=Math.max(3,w*.18);ctx.beginPath();ctx.moveTo(w*.8,size*.01);ctx.lineTo(w*2.35,size*.1);ctx.stroke();ctx.fillStyle='#d2af8c';ctx.beginPath();ctx.arc(0,-size*.18,w*.52,0,Math.PI*2);ctx.fill();ctx.fillStyle=e.type===3?'#656b68':'#353b36';ctx.fillRect(-w*.62,-size*.22,w*1.24,size*.09);ctx.fillStyle='#1b2929';ctx.fillRect(-w*.8,-size*.03,w*1.6,size*.055)}let bw=size*.42;ctx.fillStyle='#172927';ctx.fillRect(-bw/2,-size*.34,bw,Math.max(3,size*.018));ctx.fillStyle=e.type===2?'#e4aa53':'#ee7563';ctx.fillRect(-bw/2,-size*.34,bw*clamp(e.hp/e.max,0,1),Math.max(3,size*.018));ctx.restore()}
function render(ts){engine.render(world,ts);if(world){gameRoot.classList.toggle('firing',world.muzzle>0);const el=$('#missionBackdrop'),panX=Math.max(-38,Math.min(38,-world.angle*92-(world.x-2.5)*7)),panY=Math.max(-28,Math.min(28,(world.y-7.5)*5));el.style.setProperty('--pan-x',panX.toFixed(1)+'px');el.style.setProperty('--pan-y',panY.toFixed(1)+'px')}}
function frame(ts){if(screen!=='game')return;const dt=Math.min(.04,(ts-last)/1000||.016);last=ts;tick(dt);render(ts);if(screen==='game')requestAnimationFrame(frame)}
function playTone(freq,dur){try{audioCtx=audioCtx||new(window.AudioContext||window.webkitAudioContext)();const o=audioCtx.createOscillator(),g=audioCtx.createGain();o.type='square';o.frequency.value=freq;g.gain.value=.025;o.connect(g);g.connect(audioCtx.destination);o.start();o.stop(audioCtx.currentTime+dur)}catch(_){}}
function modalResultHome(){world=null;showScreen('home')}
let scoped=false;$('#scope').onclick=()=>{scoped=!scoped;$('#game').classList.toggle('scope-mode',scoped);$('#scope').classList.toggle('active',scoped);engine.scope(scoped)};$('#fullscreen').onclick=async()=>{try{if(!document.fullscreenElement){if(!gameRoot.requestFullscreen){toast('تمام‌صفحه در این مرورگر پشتیبانی نمی‌شود');return}await gameRoot.requestFullscreen()}else if(document.exitFullscreen)await document.exitFullscreen()}catch(_){toast('تمام‌صفحه در این مرورگر پشتیبانی نمی‌شود')}};$('#prevHero').onclick=()=>{hero=(hero+29)%30;storage.set('rwHero',hero);updateHome()};$('#nextHero').onclick=()=>{hero=(hero+1)%30;storage.set('rwHero',hero);updateHome()};$('#chooseHero').onclick=()=>{const grid=$('#heroGrid');grid.innerHTML='';NAMES.forEach((n,i)=>{const b=document.createElement('button');b.className='hero-card'+(i===hero?' selected':'');b.innerHTML=n+'<small>'+SKILLS[i%6]+'</small>';b.onclick=()=>{hero=i;storage.set('rwHero',hero);updateHome();showScreen('home')};grid.appendChild(b)});showScreen('heroes')};$('#heroBack').onclick=()=>showScreen('home');$('#start').onclick=()=>{if(storage.get(saveKey)){if(!restore())newWorld(false)}else newWorld(false)};$('#newGame').onclick=()=>newWorld(false);$('#survival').onclick=()=>newWorld(true);$('#pause').onclick=()=>pauseOnInterruption();$('#resume').onclick=()=>{showScreen('game');last=performance.now();requestAnimationFrame(frame)};$('#openUpgrades').onclick=()=>{if(world){$('#upgradePoints').textContent=fa(world.points);$('#upgradePoints2').textContent=fa(world.points);showScreen('upgradePanel')}};$('#upgradeBack').onclick=()=>{showScreen('game');last=performance.now();requestAnimationFrame(frame)};document.querySelectorAll('[data-up]').forEach(b=>b.onclick=()=>upgrade(+b.dataset.up));$('#goHome').onclick=()=>{save();showScreen('home')};$('#continue').onclick=nextMission;$('#retry').onclick=()=>newWorld(false);$('#resultHome').onclick=modalResultHome;$('#rocket').onpointerdown=e=>{e.preventDefault();launchRocket()};$('#drone').onpointerdown=e=>{e.preventDefault();droneStrike()};$('#special').onpointerdown=e=>{e.preventDefault();special()};$('#fire').onpointerdown=e=>{e.preventDefault();fireHeld=true;$('#fire').setPointerCapture(e.pointerId);fire()};$('#fire').onpointerup=$('#fire').onpointercancel=$('#fire').onlostpointercapture=()=>fireHeld=false;$('#interact').onpointerdown=e=>{e.preventDefault();interactObjective()};
const stick=$('#stick'),knob=$('#knob');function stickMove(e){let r=stick.getBoundingClientRect(),dx=e.clientX-(r.left+r.width/2),dy=e.clientY-(r.top+r.height/2),lim=r.width*.36,len=Math.hypot(dx,dy)||1,x=dx/len*Math.min(len,lim),y=dy/len*Math.min(len,lim);knob.style.transform=`translate(${x}px,${y}px)`;joyF=x/lim;joyS=y/lim}stick.onpointerdown=e=>{joyId=e.pointerId;stick.setPointerCapture(e.pointerId);stickMove(e)};stick.onpointermove=e=>{if(e.pointerId===joyId)stickMove(e)};function endStick(e){if(e.pointerId!==joyId)return;joyId=null;joyF=joyS=0;knob.style.transform=''}stick.onpointerup=endStick;stick.onpointercancel=endStick;stick.onlostpointercapture=endStick;
let aimY=0;canvas.addEventListener('pointerdown',e=>{if(screen!=='game')return;aimId=e.pointerId;aimLast=e.clientX;aimY=e.clientY;canvas.setPointerCapture(e.pointerId)});canvas.addEventListener('pointermove',e=>{if(aimId!==e.pointerId||!world)return;let dx=e.clientX-aimLast,dy=e.clientY-aimY;world.angle-=dx*(W<700?.008:.0045);engine.look(0,dy,W);aimLast=e.clientX;aimY=e.clientY});canvas.addEventListener('pointerup',e=>{if(e.pointerId===aimId)aimId=null});canvas.addEventListener('pointercancel',e=>{if(e.pointerId===aimId)aimId=null});canvas.addEventListener('click',()=>{if(screen==='game'&&innerWidth>=700)fire()});
function handleGameKeydown(e){
 const target=e.target;
 // Menu controls and text fields must keep their native keyboard behavior.
 if(target&&(target.isContentEditable||['INPUT','TEXTAREA','SELECT','BUTTON'].includes(target.tagName)))return;
 if(screen!=='game')return;
 if(['Space','ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.code))e.preventDefault();
 keys[e.code]=true;
 // Holding a key must not repeatedly consume limited rockets, drones or abilities.
 if(e.repeat)return;
 if(e.code==='Escape'){$('#pause').click();return}
 if(e.code==='KeyQ')launchRocket();
 if(e.code==='KeyE')droneStrike();
 if(e.code==='KeyF')special();
 if(e.code==='KeyR')reload(true);
 if(e.code==='KeyG')interactObjective();
 if(e.code==='Space')fireHeld=true;
}
addEventListener('keydown',handleGameKeydown);addEventListener('keyup',e=>{keys[e.code]=false;if(e.code==='Space')fireHeld=false});addEventListener('pagehide',save);setInterval(save,5000);
function pauseOnInterruption(){fireHeld=false;joyId=aimId=null;joyF=joyS=0;keys={};knob.style.transform='';if(screen==='game'){save();showScreen('pausePanel')}}
addEventListener('blur',pauseOnInterruption);document.addEventListener('visibilitychange',()=>{if(document.hidden)pauseOnInterruption()});
window.RamadanWarDebug={heroes:NAMES,skills:SKILLS,getState:()=>world&&({mode:screen,hero:world.hero,stage:world.mission,hp:world.hp,maxHp:world.maxHp,lives:world.lives,rockets:world.rockets,drones:world.drones,kills:world.kills,missionKills:world.missionKills,enemies:world.enemies.length,shots:world.shots||0,points:world.points,objective:world.objective,objectiveKind:world.endless?'survival':plan().kind,objectiveTarget:objectiveTarget(),...engine.stats(),score:world.score,ammo:world.ammo,combo:world.combo}),selectHero:n=>{hero=(n+30)%30;storage.set('rwHero',hero);updateHome()},start:()=>newWorld(false),fire,rocket:launchRocket,drone:droneStrike,tick,reload:()=>reload(true),spawnTestEnemy:()=>{if(world){const e=body(6.5,7.5,0,39);e.strafe=1;e.uid=++enemySerial;world.enemies.push(e)}},interact:interactObjective,qaMove:(x,y)=>{if(!['localhost','127.0.0.1'].includes(location.hostname)||!world||tile(x|0,y|0)!==0)return false;world.x=x;world.y=y;updateObjective(0);return true},qaMission:n=>{if(!['localhost','127.0.0.1'].includes(location.hostname)||!world||n<0||n>5)return false;world.mission=n;prepareMission();return true},spawnTestPickup:(type='ammo')=>{if(world)world.pickups.push({x:world.x,y:world.y,type:['ammo','health','intel'].includes(type)?type:'ammo',life:10})}};if(storage.get(saveKey))$('#start').textContent='ادامهٔ نبرد';updateHome();engine.build({hero:0,mission:0,x:2.5,y:7.5,angle:.08,muzzle:0,enemies:[],missiles:[]},tile);engine.render(null,0)
})();
