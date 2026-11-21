(()=>{'use strict';
const canvas=document.querySelector('#stage'),slug=canvas?.dataset.game;if(!canvas||!slug)return;
const ctx=canvas.getContext('2d'),W=920,H=520,keys=new Set(),$=id=>document.getElementById(id);
let active=false,paused=false,done=false,last=0,clock=0,score=0,level=1,scene=null,frame=0;
const rand=(a,b)=>Math.random()*(b-a)+a,clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const colors=['#82eaf7','#ffc787','#a893f5','#96e7a2','#f48d9c'];
const storageKey='mpw-tenlab-'+slug+'-best-v1';
let best=0;try{const stored=Number(localStorage.getItem(storageKey));best=Number.isSafeInteger(stored)&&stored>=0?Math.min(stored,1000000000):0}catch{}
function text(t,x,y,size=20,color='#e7f8ff',align='left'){ctx.fillStyle=color;ctx.font='700 '+size+'px system-ui,sans-serif';ctx.textAlign=align;ctx.fillText(String(t),x,y)}
function bg(a='#08182a',b='#12304a'){let g=ctx.createLinearGradient(0,0,0,H);g.addColorStop(0,a);g.addColorStop(1,b);ctx.fillStyle=g;ctx.fillRect(0,0,W,H)}
function circle(x,y,r,c){ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fillStyle=c;ctx.fill()}
function rect(x,y,w,h,c,r=0){ctx.fillStyle=c;if(r){ctx.beginPath();ctx.roundRect(x,y,w,h,r);ctx.fill()}else ctx.fillRect(x,y,w,h)}
function line(x,y,X,Y,c,w=2){ctx.strokeStyle=c;ctx.lineWidth=w;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(X,Y);ctx.stroke()}
function save(){if(score>best){best=score;try{localStorage.setItem(storageKey,String(best))}catch{}}}
function hud(){ $('score').textContent='SCORE '+Math.round(score);$('level').textContent='LEVEL '+level;$('best').textContent='BEST '+Math.round(best)}
function note(t){$('instructions').textContent=t}
function finish(won,msg){active=false;done=true;save();hud();$('overlay-title').textContent=won?'MISSION COMPLETE':'ROUND COMPLETE';$('overlay-text').textContent=msg+' · SCORE '+Math.round(score);$('start').textContent='PLAY AGAIN';$('overlay').classList.remove('hidden')}
function start(){active=true;paused=false;done=false;clock=0;frame=0;score=0;level=1;$('overlay').classList.add('hidden');$('pause').textContent='PAUSE';keys.clear();scene=builders[slug]();hud();note(scene.info)}
function pause(force){if(!active)return;paused=force===undefined?!paused:force;$('pause').textContent=paused?'RESUME':'PAUSE';if(paused)keys.clear();note(paused?'Paused. Resume when ready.':scene.info)}
function action(which){if(!active||paused)return;if(scene.press)scene.press(which)}
function inputKey(k){if(k==='Escape'||k==='KeyP'){pause();return}if(!active||paused)return; if(['Space','Enter'].includes(k)||k==='ArrowUp'&&slug==='metro-vault')action('action');if(k==='Digit1')action('left');if(k==='Digit2')action('action');if(k==='Digit3')action('right');if(scene.key)scene.key(k)}
$('start').addEventListener('click',start);$('pause').addEventListener('click',()=>pause());
for(const id of ['left','right','up','down','action']){
 const el=$(id);el.addEventListener('pointerdown',e=>{keys.add(id);action(id);try{el.setPointerCapture(e.pointerId)}catch{}e.preventDefault()});
 for(const ev of ['pointerup','pointercancel','lostpointercapture'])el.addEventListener(ev,()=>keys.delete(id));
}
addEventListener('keydown',e=>{if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Space'].includes(e.code))e.preventDefault();if(!e.repeat)inputKey(e.code);keys.add(e.code)});
addEventListener('keyup',e=>keys.delete(e.code));
document.addEventListener('visibilitychange',()=>{if(document.hidden&&active&&!paused)pause(true)});
addEventListener('blur',()=>{if(active&&!paused)pause(true)});
function down(id){return keys.has(id)||({left:'ArrowLeft',right:'ArrowRight',up:'ArrowUp',down:'ArrowDown',action:'Space'}[id]&&keys.has({left:'ArrowLeft',right:'ArrowRight',up:'ArrowUp',down:'ArrowDown',action:'Space'}[id]))||keys.has({left:'KeyA',right:'KeyD',up:'KeyW',down:'KeyS',action:'Space'}[id])}
function pointer(e){const p=canvas.getBoundingClientRect();return{x:(e.clientX-p.left)/p.width*W,y:(e.clientY-p.top)/p.height*H}}
canvas.addEventListener('pointerdown',e=>{if(active&&!paused&&scene.click)scene.click(pointer(e));e.preventDefault()});
function windward(){
 let boat={x:85,y:260,a:0,v:0},wind=1.3,t=100,ix=0,reefHit=0;
 const buoys=[{x:180,y:135},{x:335,y:375},{x:495,y:150},{x:655,y:365},{x:825,y:230}];
 const reefs=[{x:270,y:235,r:34},{x:557,y:255,r:38},{x:747,y:125,r:30}];
 note('Steer: ◀ ▶ / A D. Trim sails: ▲ / W. Slow: ▼. Sail near every buoy in order.');
 return{info:'Round all five buoys in sequence. Trim upwind and avoid reefs. 100-second race.',
 update(dt){clock+=dt;t-=dt;wind+=Math.sin(clock*.30)*dt*.10;const control=(down('right')?1:0)-(down('left')?1:0);
 boat.a+=control*dt*(1.4+boat.v/125);
 const lift=(.27+.73*Math.abs(Math.sin(boat.a-wind)))*(down('up')?1.35:1);
 boat.v+=(lift*108-boat.v*(down('down')?2.4:1.0))*dt*1.25;
 boat.v=clamp(boat.v,0,143);
 boat.x+=Math.cos(boat.a)*boat.v*dt;boat.y+=Math.sin(boat.a)*boat.v*dt;
 boat.x=clamp(boat.x,25,900);boat.y=clamp(boat.y,28,490);
 const mark=buoys[ix];if(mark&&Math.hypot(mark.x-boat.x,mark.y-boat.y)<37){ix++;level=ix+1;score+=200+Math.round(t);if(ix===buoys.length){finish(true,'All five buoys rounded');return} }
 for(const reef of reefs)if(Math.hypot(boat.x-reef.x,boat.y-reef.y)<reef.r+10&&clock-reefHit>1.6){reefHit=clock;t-=8;boat.v*=.3;note('Reef collision: 8-second penalty')}
 if(t<=0)finish(false,'Race time expired');
 },draw(){
 bg('#0c324b','#085269');for(let i=0;i<19;i++){let x=(i*87+clock*15)%W;line(x,0,x-50,H,'#7cd8e629',1)}
 for(const r of reefs){circle(r.x,r.y,r.r+11,'#136076');circle(r.x,r.y,r.r,'#39575c');circle(r.x-8,r.y-8,r.r*.52,'#8a9b85')}
 buoys.forEach((b,i)=>{circle(b.x,b.y,18,i===ix?'#ffd48b':'#36849a');circle(b.x,b.y,9,i<ix?'#8cf4b7':'#10354b');text(String(i+1),b.x,b.y-24,14,i<ix?'#8be9be':'#effcff','center');if(i===ix){ctx.strokeStyle='#ffe1a0';ctx.lineWidth=2;ctx.beginPath();ctx.arc(b.x,b.y,31+Math.sin(clock*5)*3,0,7);ctx.stroke()}});
 ctx.save();ctx.translate(boat.x,boat.y);ctx.rotate(boat.a);rect(-27,-9,54,18,'#dce6db',9);ctx.beginPath();ctx.moveTo(-8,0);ctx.lineTo(-8,-33);ctx.lineTo(29,0);ctx.closePath();ctx.fillStyle='#f7cb85';ctx.fill();circle(0,0,5,'#184961');ctx.restore();
 line(720,60,720+Math.cos(wind)*50,60+Math.sin(wind)*50,'#8df2de',5);text('WIND',704,39,14);
 text('TIME '+Math.ceil(t)+'s',26,45,24,'#f9dca5');text('BUOY '+Math.min(ix+1,5)+' / 5',26,75,18);text('SPEED '+Math.round(boat.v)+' kn',26,103,15);
 }};
}
function lexicon(){
 const words=['ORBIT','FROST','SOLAR','RIVER','MANGO','PILOT','QUEST','BRAVE','WAVES','PIXEL','JELLY','NORTH','DELTA','SCALE','TIGER','STONE','CLOUD','SHIFT','ROUTE','BERRY'];
 let board=[],found=new Set(),chosen=null,startTime=90,list=[],hint=0,cursor=0;
 function make(){
  cursor=0;board=Array.from({length:64},()=>String.fromCharCode(65+Math.floor(rand(0,26))));
  list=words.slice((level-1)*5,(level-1)*5+5);found.clear();
  const occupied=new Set();
  for(const w of list){let placed=false;
   for(let tryN=0;tryN<600&&!placed;tryN++){
    const x=Math.floor(rand(0,8)),y=Math.floor(rand(0,8)),dir=[[1,0],[0,1],[-1,0],[0,-1],[1,1],[-1,1]][Math.floor(rand(0,6))];let coords=[];
    for(let j=0;j<w.length;j++){let X=x+dir[0]*j,Y=y+dir[1]*j;if(X<0||X>7||Y<0||Y>7){coords=[];break}coords.push(Y*8+X)}
    if(coords.length===w.length&&coords.every(k=>!occupied.has(k))){coords.forEach((k,i)=>{board[k]=w[i];occupied.add(k)});placed=true}
   }
   if(!placed)throw Error('Word grid generator failed');
  }
 }
 make();
 function select(k){
   if(k<0||k>=64)return;
   if(chosen===null){chosen=k;return}
   const a=chosen,bb=k;chosen=null;
   const dx=Math.sign(bb%8-a%8),dy=Math.sign(Math.floor(bb/8)-Math.floor(a/8));
   if(!(dx===0||dy===0||Math.abs(bb%8-a%8)===Math.abs(Math.floor(bb/8)-Math.floor(a/8))))return;
   const n=Math.max(Math.abs(bb%8-a%8),Math.abs(Math.floor(bb/8)-Math.floor(a/8)))+1;
   let w='';for(let i=0;i<n;i++){let x=a%8+i*dx,y=Math.floor(a/8)+i*dy;if(x<0||x>7||y<0||y>7)return;w+=board[y*8+x]}
   if(list.includes(w)&&!found.has(w)){found.add(w);score+=150+Math.floor(startTime);hint=0;note('FOUND '+w+' — '+found.size+'/5. Select the first and last letter of each word.');if(found.size===5){level++;if(level>4)finish(true,'All four word grids solved');else {startTime+=38;make()}}}
   else{hint=.45;note('Not in target list: '+w+'. Try a straight word in any direction.')}
 }
 return{info:'Find five hidden words in each grid. Tap the first and last letter, or use a mouse. Four rounds.',press(which){if(which==='action')select(cursor)},
 key(k){if(k==='ArrowLeft')cursor=Math.max(0,cursor-1);else if(k==='ArrowRight')cursor=Math.min(63,cursor+1);else if(k==='ArrowUp')cursor=Math.max(0,cursor-8);else if(k==='ArrowDown')cursor=Math.min(63,cursor+8)},
 click(p){const x=Math.floor((p.x-68)/57),y=Math.floor((p.y-35)/57);if(x>=0&&x<8&&y>=0&&y<8){cursor=y*8+x;select(cursor)}},
 update(dt){startTime-=dt;hint=Math.max(0,hint-dt);if(startTime<=0)finish(false,'Out of time')},
 draw(){bg('#112541','#162942');for(let y=0;y<8;y++)for(let x=0;x<8;x++){const k=y*8+x,X=68+x*57,Y=35+y*57;rect(X+2,Y+2,50,50,k===chosen?'#547e9d':'#204158',7);if(k===chosen)rect(X+2,Y+2,50,50,'#467785a8',7);if(k===cursor){ctx.strokeStyle='#f5d995';ctx.lineWidth=3;ctx.strokeRect(X+4,Y+4,46,46)}text(board[k],X+27,Y+37,25,k===chosen?'#ffe3b3':'#e5f5ff','center')}
 text('TARGET WORDS',568,74,20,'#f2c988');list.forEach((w,i)=>{rect(555,94+i*65,290,50,found.has(w)?'#245949':'#18384c',9);text((found.has(w)?'✓ ':'○ ')+w,576,128+i*65,21,found.has(w)?'#9af2bd':'#f0f8f9')});
 text('TIME '+Math.ceil(startTime)+'s',574,466,23);text('ROUND '+level+' / 4',574,500,14,'#a9c9d1');if(hint>0)rect(60,488,420,6,'#ff9569')}}
}
function dominion(){
 const cols=9,rows=7,cells=Array(cols*rows).fill(0);let energy=7,aiEnergy=7,turn=0,cursor=3*cols+1;
 cells[3*cols+0]=1;cells[3*cols+8]=2;const terrain=Array.from({length:cells.length},(_,i)=>(i*17+Math.floor(i/9)*11)%13===0?2:1);
 function adj(i,owner){let x=i%9,y=Math.floor(i/9);return [[x-1,y],[x+1,y],[x,y-1],[x,y+1]].some(([a,b])=>a>=0&&a<cols&&b>=0&&b<rows&&cells[b*cols+a]===owner)}
 function options(owner){return cells.map((v,i)=>v?null:i).filter(v=>v!==null&&adj(v,owner))}
 function choose(i,owner){if(cells[i]!==0||!adj(i,owner))return false;const cost=terrain[i];if((owner===1?energy:aiEnergy)<cost)return false;cells[i]=owner;if(owner===1)energy-=cost;else aiEnergy-=cost;return true}
 function outcome(){const you=cells.filter(x=>x===1).length,ai=cells.filter(x=>x===2).length;score=you*90+(turn*3);if(you+ai===cells.length||turn>88||(!options(1).length&&!options(2).length)){finish(you>ai,'Territory '+you+' : '+ai);return true}return false}
 function player(i){if(!active||paused)return;if(!choose(i,1)){note('Select an unclaimed square NEXT TO your blue territory. Spend 1–2 energy.');return}turn++;energy=Math.min(10,energy+3);aiEnergy=Math.min(10,aiEnergy+3);let optionsAI=options(2).filter(j=>terrain[j]<=aiEnergy);optionsAI.sort((a,b)=>((adj(a,1)?-4:0)+terrain[a])-((adj(b,1)?-4:0)+terrain[b]));if(optionsAI.length)choose(optionsAI[0],2);level=Math.floor(turn/7)+1;outcome()}
 return{info:'Claim adjacent blue territory for 1–2 energy. The orange AI responds each turn. Tap a cell; energy regenerates.',
 key(k){const dx=k==='ArrowLeft'?-1:k==='ArrowRight'?1:0,dy=k==='ArrowUp'?-1:k==='ArrowDown'?1:0;cursor=clamp(cursor%9+dx,0,8)+9*clamp(Math.floor(cursor/9)+dy,0,6)},
 press(which){if(which==='action')player(cursor)},
 click(p){const x=Math.floor((p.x-49)/90),y=Math.floor((p.y-56)/58);if(x>=0&&x<9&&y>=0&&y<7){cursor=y*9+x;player(cursor)}},
 update(){},draw(){bg('#0b2232','#102538');for(let i=0;i<cells.length;i++){const x=i%9,y=Math.floor(i/9),px=49+x*90,py=56+y*58;rect(px,py,81,51,cells[i]===1?'#247b99':cells[i]===2?'#ae664c':terrain[i]===2?'#30415c':'#1c4050',6);if(cells[i]===0&&adj(i,1)&&terrain[i]<=energy){ctx.strokeStyle='#8ef1bd';ctx.lineWidth=1.5;ctx.strokeRect(px+5,py+5,71,41)}if(terrain[i]===2)text('◆',px+40,py+32,13,'#f1d59e','center');if(i===cursor){ctx.strokeStyle='#fcdf9f';ctx.lineWidth=3;ctx.strokeRect(px+2,py+2,77,47)}}
 text('YOUR ENERGY '+energy+'    AI ENERGY '+aiEnergy,43,32,18,'#f9d69f');text('BLUE '+cells.filter(x=>x===1).length+'  /  ORANGE '+cells.filter(x=>x===2).length,42,503,15)}};
}
function metro(){
 let y=387,vy=0,distance=0,bonus=0,hp=3,spawn=.8,obstacles=[],inv=0,dash=0,ground=418,space=0;
 function jump(){if(y>=ground-31){vy=-480}}
 return{info:'Arrow Up / Space / ACTION to jump. Right to dash. Clear rooftop vents, holes and drones. Grab gold tokens.',
 press(which){if(['action','up'].includes(which))jump();if(which==='right')dash=.75},
 update(dt){clock+=dt;distance+=dt*(205+(level-1)*16);score=Math.floor(distance/9)+bonus;level=1+Math.floor(distance/750);spawn-=dt;
 if(down('right'))dash=.20;
 if(spawn<=0){const type=['vent','drone','pit','coin'][Math.floor(rand(0,4))];obstacles.push({type,x:970,y:type==='drone'?rand(310,370):418});spawn=rand(.8,1.45)*Math.max(.65,1-level*.025)}
 vy+=1060*dt;y+=vy*dt;if(y>ground-31){y=ground-31;vy=0}
 for(const o of obstacles){o.x-=dt*(205+(level-1)*16+(dash>0?100:0));
 if(o.x<125&&o.x>60){const bodyBottom=y+31;if(o.type==='coin'){if(Math.abs(o.y-25-y)<45){bonus+=80;score+=80;o.x=-200}}else if(!inv&&(o.type==='pit'&&bodyBottom>=ground-2||o.type==='vent'&&bodyBottom>ground-65||o.type==='drone'&&Math.abs(o.y-y)<32)){hp--;inv=1.2;o.x=-150;note('Collision! '+hp+' shields remain. Jump earlier or dash through the gap.');if(hp<=0)finish(false,'The skyline claimed your last shield')}}
 }
 obstacles=obstacles.filter(o=>o.x>-220);
 if(distance>3500)finish(true,'Skyline cleared with '+hp+' shields left');
 dash=Math.max(0,dash-dt);inv=Math.max(0,inv-dt);
 },draw(){bg('#182a44','#28344a');let shift=(distance*.4)%85;for(let i=-1;i<14;i++){const x=i*85-shift;rect(x,160+((i*29)%90),71,270,'#172739');for(let j=0;j<4;j++)rect(x+12,220+j*44,8,12,'#597381')}
 rect(0,418,920,102,'#182d3b');for(let i=0;i<16;i++)rect(i*70-(distance%70),422,36,5,'#6ea0a5');
 for(const o of obstacles){if(o.type==='vent')rect(o.x,385,35,33,'#fa966e',4);else if(o.type==='drone'){circle(o.x,o.y,19,'#f2a9aa');line(o.x-28,o.y,o.x+28,o.y,'#ffe0ae',4)}else if(o.type==='pit')rect(o.x,418,68,102,'#081321');else{circle(o.x,o.y-25,12,'#f3d181');text('◆',o.x,o.y-19,15,'#55401e','center')}}
 if(inv<=0||Math.floor(clock*18)%2){rect(81,y,40,60,dash>0?'#a1f5e9':'#81d7fa',9);rect(102,y-12,14,20,'#f5d29a',5);rect(79,y+53,17,8,'#f6c490',3)}
 text('SHIELDS '+hp,20,48,22,'#f4d6a3');text('DISTANCE '+Math.floor(distance)+'m',20,76,15);text('JUMP / DASH',745,47,17)}};
}
function cargo(){
 let seq=0,lives=5,streak=0,spawn=1.4,train=[],choice=1,settled=0;
 const bays=['#74dbed','#eeb980','#b69afa'];
 function set(i){choice=i;note('Switch set to '+['BLUE','GOLD','VIOLET'][i]+' dock. Press 1, 2 or 3 to reroute each arriving car.')}
 return{info:'Switch 1 / 2 / 3 (or ◀ / ACTION / ▶) to match each freight car with its colored loading bay. Five mistakes end the shift.',
 key(k){if(k==='Digit1')set(0);if(k==='Digit2')set(1);if(k==='Digit3')set(2)},
 press(which){set(which==='left'?0:which==='right'?2:1)},
 update(dt){clock+=dt;spawn-=dt;if(spawn<=0){train.push({x:980,color:Math.floor(rand(0,3)),assigned:null,id:++seq});spawn=Math.max(.6,1.8-level*.09)*rand(.8,1.15)}
 const v=(160+level*22)*dt;for(const car of train){car.x-=v;if(car.x<465&&car.assigned===null){car.assigned=choice;note(car.assigned===car.color?'Nice routing! Next shipment inbound.':'Wrong dock — adjust the switch earlier next time.')}
 if(car.x<52&&!car.done){car.done=true;settled++;if(car.assigned===car.color){streak++;score+=100+Math.min(10,streak)*15}else{lives--;streak=0}level=1+Math.floor(settled/7);if(lives<=0)finish(false,'Shift ended: '+settled+' shipments sorted');else if(settled>=35)finish(true,'All 35 shipments dispatched')}}train=train.filter(x=>!x.done);
 },draw(){bg('#0e1e2d','#163a45');text('ROUTE THE COLORED FREIGHT',24,42,24,'#f3d7ac');for(let j=0;j<3;j++){const y=185+j*111;line(42,y,875,y,'#527d83',11);line(42,y,875,y,'#193446',5);rect(35,y-36,117,70,'#234052',9);rect(40,y-33,110,65,bays[j]+'44',8);text(['BAY 1','BAY 2','BAY 3'][j],63,y+7,19,bays[j]);}
 line(460,67,460,450,'#f1d392aa',5);for(let j=0;j<3;j++)line(460,300,575,185+j*111,bays[j],4);circle(460,302,16,bays[choice]);for(const c of train){let y=c.assigned===null?300:185+c.assigned*111;rect(c.x,y-24,76,48,bays[c.color],9);rect(c.x+7,y-13,62,24,'#0c2a3b',4);text(String(c.id),c.x+38,y+5,16,bays[c.color],'center')}
 text('SWITCH: '+['BLUE','GOLD','VIOLET'][choice],700,66,21,bays[choice]);text('LIVES '+lives+'   COMBO '+streak,620,480,18);text('DISPATCHED '+settled+' / 35',24,480,18)}}
}
const builders={'windward-regatta':windward,'lexicon-sprint':lexicon,'grid-dominion':dominion,'metro-vault':metro,'cargo-switchyard':cargo};
if(!builders[slug])throw Error('Unknown arcade game '+slug);
function loop(ts){requestAnimationFrame(loop);let dt=Math.min(.045,Math.max(0,(ts-last)/1000||.016));last=ts;
 if(active&&!paused)scene.update(dt);
 if(scene&&scene.draw)scene.draw();else{bg();text('PRESS START',W/2,H/2,35,'#e6d1ad','center')}
 hud();frame++;}
$('overlay-title').textContent='READY FOR '+slug.replaceAll('-',' ').toUpperCase()+'?';
note('Five original skill games. Press START GAME. Use keyboard or on-screen buttons.');
requestAnimationFrame(loop);
window.__MPW_TEN_GAME_QA__={snapshot:()=>({slug,active,paused,done,score,level,best,frame}),start,pause,action};
})();