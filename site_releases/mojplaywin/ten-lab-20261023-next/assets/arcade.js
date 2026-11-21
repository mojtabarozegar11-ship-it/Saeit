(()=>{'use strict';
const canvas=document.querySelector('#stage'),slug=canvas?.dataset.game;if(!canvas)return;
const C=canvas.getContext('2d'),W=920,H=520,$=id=>document.getElementById(id),keys=new Set();
let playing=false,paused=false,finished=false,score=0,level=1,frame=0,last=0,scene=null;
const col=['#7ee8ef','#ffd28e','#ae97f7','#a7e5ae','#fa9b9e'],rnd=(n)=>Math.floor(Math.random()*n),clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
let best=0;try{const stored=Number(localStorage.getItem('mpw-next-'+slug+'-best'));best=Number.isSafeInteger(stored)&&stored>=0?Math.min(stored,1000000000):0}catch{}
function bg(a='#09233a',b='#101b31'){const g=C.createLinearGradient(0,0,W,H);g.addColorStop(0,a);g.addColorStop(1,b);C.fillStyle=g;C.fillRect(0,0,W,H);}
function rectangle(x,y,w,h,color,r=0){C.fillStyle=color;C.beginPath();C.roundRect(x,y,w,h,r);C.fill();}
function circle(x,y,r,color){C.beginPath();C.arc(x,y,r,0,Math.PI*2);C.fillStyle=color;C.fill();}
function label(s,x,y,size=18,color='#edf9ff',align='left'){C.fillStyle=color;C.textAlign=align;C.font='700 '+size+'px system-ui';C.fillText(String(s),x,y)}
function stroke(x,y,xx,yy,color,w=3){C.strokeStyle=color;C.lineWidth=w;C.beginPath();C.moveTo(x,y);C.lineTo(xx,yy);C.stroke()}
function notify(msg){$('instructions').textContent=msg}
function hud(){$('score').textContent='SCORE '+Math.floor(score);$('level').textContent='LEVEL '+level;$('best').textContent='BEST '+best}
function reward(v){if(!Number.isFinite(v)||v<0)return;score=Math.min(1000000000,score+Math.floor(v));if(score>best){best=score;try{localStorage.setItem('mpw-next-'+slug+'-best',String(best))}catch{}}hud()}
function finish(won,msg){playing=false;finished=true;$('overlay-title').textContent=won?'MISSION COMPLETE':'ROUND OVER';$('overlay-text').textContent=msg+' · SCORE '+Math.floor(score);$('overlay').classList.remove('hidden');$('start').textContent='PLAY AGAIN';hud()}
function mountInput(id,placeholder,max){let d=document.createElement('div');d.className='field';d.style.margin='8px 0';d.innerHTML='<label for="'+id+'">TYPE YOUR '+(id==='typeInput'?'WORD':'GUESS')+'</label><input id="'+id+'" type="text" maxlength="'+max+'" autocomplete="off" spellcheck="false" autocapitalize="characters" placeholder="'+placeholder+'">';$('instructions').before(d);return d.querySelector('input')}
function focusInput(){const x=$('typeInput')||$('codeInput');if(x)x.focus({preventScroll:true})}
function start(){keys.clear();playing=true;paused=false;finished=false;score=0;level=1;$('overlay').classList.add('hidden');$('pause').textContent='PAUSE';if(scene?.dispose)scene.dispose();scene=builders[slug]();hud();notify(scene.help);focusInput()}
function pause(){if(!playing)return;paused=!paused;$('pause').textContent=paused?'RESUME':'PAUSE';keys.clear();notify(paused?'Paused. Resume when ready.':scene.help);if(!paused)focusInput()}
function act(key){if(!playing||paused||!scene)return;scene.act?.(key)}
$('start').addEventListener('click',start);$('pause').addEventListener('click',pause);
for(const key of ['left','up','right','down','action']){const e=$(key);e.addEventListener('pointerdown',ev=>{keys.add(key);act(key);ev.preventDefault();try{e.setPointerCapture(ev.pointerId)}catch{}});for(const name of ['pointerup','pointercancel','lostpointercapture'])e.addEventListener(name,()=>keys.delete(key));}
addEventListener('keydown',e=>{if(e.code==='Escape'){pause();return}const input=document.activeElement?.tagName==='INPUT';if(input){if(e.code==='Enter'){e.preventDefault();act('action')}return}if(['Space','ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.code))e.preventDefault();if(e.repeat)return;if(e.code==='KeyP'){pause();return}const dir=({'ArrowLeft':'left','KeyA':'left','ArrowRight':'right','KeyD':'right','ArrowUp':'up','KeyW':'up','ArrowDown':'down','KeyS':'down','Space':'action','Enter':'action'})[e.code];if(dir)act(dir)});
addEventListener('visibilitychange',()=>{if(document.hidden&&playing&&!paused)pause()});addEventListener('blur',()=>{if(playing&&!paused)pause()});
function pointer(e){const b=canvas.getBoundingClientRect();return{x:(e.clientX-b.left)/b.width*W,y:(e.clientY-b.top)/b.height*H}}
canvas.addEventListener('pointerdown',e=>{if(playing&&!paused)scene.click?.(pointer(e));e.preventDefault()});
function hexBloom(){
 const N=5,a=Array(N*N).fill(0),movesMax=38;let moves=0,selected=null;
 for(let i=0;i<11;i++){const empty=a.map((v,k)=>v===0?k:-1).filter(x=>x>=0);a[empty[rnd(empty.length)]]=rnd(5)===0?4:2}
 function neigh(i){let x=i%N,y=Math.floor(i/N);return [[x-1,y],[x+1,y],[x,y-1],[x,y+1]].filter(([xx,yy])=>xx>=0&&xx<N&&yy>=0&&yy<N).map(([xx,yy])=>yy*N+xx)}
 // A fresh board must always have at least one legal merge, even with unlucky random placement.
 if(!a.some((v,k)=>v&&neigh(k).some(j=>a[j]===v))){a[0]=2;a[1]=2}
 function play(i){if(!playing||paused)return;if(i<0||i>=a.length)return;if(selected===null){if(a[i])selected=i;return}const prior=selected;selected=null;if(i===prior){return}if(!neigh(prior).includes(i)||a[prior]!==a[i]||!a[i]){selected=a[i]?i:null;notify('Merge adjacent matching crystals. Select one bloom and then its identical neighbor.');return}
 a[i]*=2;a[prior]=0;moves++;reward(a[i]*2);level=Math.max(1,Math.floor(Math.log2(Math.max(...a)))-1);
 if(a[i]>=128){finish(true,'You grew the legendary 128 crystal!');return}
 let empties=a.map((v,k)=>v===0?k:-1).filter(x=>x>=0);if(empties.length)a[empties[rnd(empties.length)]]=rnd(7)===0?4:2;
 if(!a.some((x,k)=>x&&neigh(k).some(j=>a[j]===x))||moves>=movesMax){finish(false,'No more useful merges. Try a new strategy.');return}
 notify('Successful merge! '+moves+' moves used. Target: 128 bloom.');
 }
 return{help:'Tap one energy crystal, then an adjacent matching crystal to merge. Build a 128-point bloom.',act(k){const delta={left:-1,right:1,up:-5,down:5}[k];if(delta&&selected!==null)selected=clamp(selected+delta,0,24);else if(k==='action'&&selected!==null){const opts=neigh(selected).filter(j=>a[j]===a[selected]);if(opts.length)play(opts[0])}},click(p){const x=Math.floor((p.x-230)/93),y=Math.floor((p.y-28)/91);if(x>=0&&x<N&&y>=0&&y<N)play(y*N+x)},update(){},draw(){
 bg('#171a38','#172f46');label('HEX BLOOM',48,66,28,'#ffd99b');label('Merge equals. Reach 128.',48,97,16);label('MOVES '+moves+' / '+movesMax,48,152,18);label('MAX '+Math.max(...a),48,192,20,'#85ebc7');
 for(let i=0;i<a.length;i++){let x=230+i%N*93,y=28+Math.floor(i/N)*91,v=a[i];rectangle(x+3,y+3,85,83,v?col[Math.log2(v)%col.length]+'4f':'#1b3345',15);if(selected===i){C.strokeStyle='#fff1a9';C.lineWidth=4;C.strokeRect(x+5,y+5,80,77)}
 if(v){circle(x+45,y+44,27+Math.log2(v)*1.7,col[Math.log2(v)%col.length]);label(v,x+45,y+52,23,'#0e2332','center')}
 }label('SELECT → MERGE → GROW',46,474,14,'#9cd2df')}}}
function prismRelay(){
 const levels=[[[2,2,1],[2,0,1]],[[1,2,1],[1,4,0],[6,4,0]],[[3,2,1],[3,0,1]],[[4,2,1],[4,4,0],[7,4,0]],[[2,2,1],[2,0,1],[6,0,0]],[[1,2,1],[1,4,0],[5,4,0]]];
 // A preset's final receiver follows the trace of its solved mirror states.
 const solved=[{x:7,y:0},{x:6,y:0},{x:7,y:0},{x:7,y:4},{x:6,y:4},{x:5,y:0}];
 let grid={},target=solved[0],path=[],solvedNow=false,pause=0,cursor=0;
 function stage(){grid={};for(const [x,y,v] of levels[level-1])grid[y*8+x]=1-v;cursor=Number(Object.keys(grid)[0])||0;target=solved[level-1];path=[];solvedNow=false;pause=0}
 stage();
 function trace(){let x=0,y=2,dx=1,dy=0,vis=new Set();path=[];for(let n=0;n<55;n++){const state=x+','+y+','+dx+','+dy;if(vis.has(state))break;vis.add(state);path.push({x,y});if(x===target.x&&y===target.y)return true;let typ=grid[y*8+x];if(typ!==undefined){if(typ===1){const a=-dy,b=-dx;dx=a;dy=b}else{const a=dy,b=dx;dx=a;dy=b}}x+=dx;y+=dy;if(x<0||x>7||y<0||y>4)break}return false}
 function rotate(x,y){if(solvedNow)return;const k=y*8+x;if(grid[k]===undefined)return;grid[k]=1-grid[k];if(trace()){reward(400+level*100);solvedNow=true;pause=.65;notify('Receiver illuminated! Next optical challenge unlocked.')}else notify('Rotate mirrors until the beam reaches the glowing receiver.')}
 return{help:'Click mirror tiles to rotate the laser. Light the receiver on each of six optical circuits.',click(p){const x=Math.floor((p.x-104)/89),y=Math.floor((p.y-36)/90);if(x>=0&&x<8&&y>=0&&y<5)rotate(x,y)},act(k){if(solvedNow)return;const mirrors=Object.keys(grid).map(Number);if(!mirrors.length)return;
 if(['left','right','up','down'].includes(k)){const idx=Math.max(0,mirrors.indexOf(cursor)),step=['left','up'].includes(k)?-1:1;cursor=mirrors[(idx+step+mirrors.length)%mirrors.length]}
 else if(k==='action')rotate(cursor%8,Math.floor(cursor/8))},update(dt){if(solvedNow){pause-=dt;if(pause<=0){if(level>=6){finish(true,'Six mirror circuits solved');return}level++;stage()}}},draw(){
 bg('#0a1d31','#152444');for(let y=0;y<5;y++)for(let x=0;x<8;x++){const xx=104+x*89,yy=36+y*90;rectangle(xx+3,yy+3,82,83,'#1a324e',10);let typ=grid[y*8+x];if(typ!==undefined){rectangle(xx+10,yy+9,68,71,'#274c67',10);label(typ===1?'/':'\\',xx+44,yy+57,51,'#fcd692','center');if(y*8+x===cursor){C.strokeStyle='#fff3aa';C.lineWidth=3;C.strokeRect(xx+6,yy+6,76,77)}}}
 trace();for(let i=1;i<path.length;i++){const a=path[i-1],bb=path[i];stroke(148+a.x*89,81+a.y*90,148+bb.x*89,81+bb.y*90,'#7cecf5',6)}
 circle(148,81+2*90,15,'#fcad73');circle(148+target.x*89,81+target.y*90,19,'#a1f6bd');label('TARGET',150+target.x*89,66+target.y*90,10,'#aaf7d8','center');label('CIRCUIT '+level+' / 6',25,498,21,'#f7d6a0');label('CLICK MIRRORS TO ROTATE',500,499,13)}}
}
function kitchenRush(){
 const dishes=[{name:'TACOS',need:[0,2]},{name:'RAMEN',need:[1,2]},{name:'SALAD',need:[0,1]}],colors=['#b8f5ae','#f1b17b','#ebda88'];
 let remaining=94,served=0,hearts=4,order=dishes[rnd(3)],selected=[],queueClock=0;
 function choose(i){if(selected.length<2)selected.push(i);notify('Ingredients: '+selected.map(k=>['GREENS','PROTEIN','SPICE'][k]).join(' + ')+'. Tap SERVE when ready.')}
 function serve(){if(!playing||paused)return;let sorted=a=>a.slice().sort().join(',');if(sorted(selected)===sorted(order.need)){reward(140+Math.floor(remaining));served++;level=1+Math.floor(served/4);notify('Perfect plate! Order '+served+' served.')}else{hearts--;notify('Wrong order. Watch the customer recipe!');if(hearts<=0){finish(false,'Kitchen closed after four mistakes');return}}selected=[];order=dishes[rnd(dishes.length)];queueClock=0;if(served>=15)finish(true,'Fifteen orders served — chef victory!')}
 return{help:'Serve 15 orders. GREENS = ◀, PROTEIN = ▲, SPICE = ▶. Tap ACTION to serve your chosen two ingredients.',act(k){if(k==='left')choose(0);if(k==='up')choose(1);if(k==='right')choose(2);if(k==='action')serve();if(k==='down'){selected=[];notify('Plate cleared. Choose two ingredients.')}},click(p){if(p.y>344){const i=Math.floor((p.x-100)/225);if(i>=0&&i<3)choose(i)}else if(p.x>650&&p.y<210)serve()},update(dt){remaining-=dt;if(remaining<=0){finish(false,'Service timer expired');return}queueClock+=dt;if(queueClock>18){hearts--;queueClock=0;selected=[];order=dishes[rnd(3)];notify('Customer waited too long!');if(hearts<=0){finish(false,'Too many missed orders');return}}},draw(){
 bg('#202d3f','#112c33');label('KITCHEN RUSH',36,57,31,'#ffdb9b');label('TIME '+Math.ceil(remaining)+'s',690,56,24);label('HEARTS '+hearts+'    SERVED '+served+' / 15',37,95,19);
 rectangle(34,122,848,186,'#244a53',20);label('CUSTOMER ORDER',67,162,18,'#a9e5e2');label(order.name,67,230,44,'#ffe4b7');label('RECIPE',480,160,16);order.need.forEach((x,i)=>{rectangle(480+i*168,188,150,74,colors[x],14);label(['GREENS','PROTEIN','SPICE'][x],555+i*168,234,16,'#173345','center')});
 for(let i=0;i<3;i++){rectangle(90+i*225,342,198,94,colors[i]+'b5',16);label(['1 • GREENS','2 • PROTEIN','3 • SPICE'][i],189+i*225,396,19,'#103044','center')}
 label('CURRENT PLATE: '+selected.map(x=>['GREENS','PROTEIN','SPICE'][x]).join(' + '),36,478,16,'#e7d7bb');label('ACTION → SERVE',715,495,15,'#fbd9a8');}}
}
function typeDefender(){
 const wordlist=['ORBIT','SOLAR','METRIC','CANVAS','PYTHON','CIPHER','ROCKET','COMET','OCEAN','CLOUD','LOGIC','SQUAD','VECTOR','MATRIX','SECURE','PUZZLE','NEBULA','GALAXY','NIMBLE','BRIGHT','QUARTZ','STREAM'];
 const input=mountInput('typeInput','Type the falling word',15);let enemies=[],clock=0,spawn=1.8,miss=0,kills=0;
 function type(){if(!playing||paused)return;const t=input.value.trim().toUpperCase();if(!t)return;const i=enemies.findIndex(x=>x.word===t);if(i>=0){reward(110+Math.round((1-enemies[i].y/505)*70));enemies.splice(i,1);kills++;level=1+Math.floor(kills/5);notify('Intercept confirmed! '+kills+' of 20 targets cleared.');input.value='';if(kills>=20)finish(true,'Cyber perimeter protected against twenty threats')}else{input.value='';notify('No matching threat. Type any visible falling word.')}}input.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();e.stopPropagation();type()}});const form=input.parentElement;
 return{help:'Type an entire falling word and press Enter / ACTION. Defeat 20 words before four reach the shield.',act(k){if(k==='action')type();else{input.focus()}},update(dt){clock+=dt;spawn-=dt;if(spawn<=0){let w=wordlist[rnd(wordlist.length)];enemies.push({word:w,y:-12,x:125+rnd(645)});spawn=Math.max(.8,2.6-level*.19)}for(const e of enemies)e.y+=(40+level*7)*dt;const lost=enemies.filter(x=>x.y>=445);miss+=lost.length;enemies=enemies.filter(x=>x.y<445);if(lost.length){notify(lost.length+' threats reached the shield; '+Math.max(0,4-miss)+' shields remain.');if(miss>=4)finish(false,'Four threats breached the firewall')}},draw(){bg('#131332','#0b3547');for(let i=0;i<27;i++){let x=(i*71)%W;stroke(x,0,x,H,'#6c9de818',1)}rectangle(0,467,W,53,'#176572',0);label('FIREWALL',24,499,20,'#b3f4e6');for(const e of enemies){rectangle(e.x-62,e.y-26,124,48,'#244c69',11);label(e.word,e.x,e.y+5,21,'#f0dbad','center')}label('INTERCEPTED '+kills+'/20',27,49,19,'#b5f4e6');label('SHIELDS '+Math.max(0,4-miss),765,49,18,'#ffdab4')},dispose(){form.remove()}}
}
function codebreaker(){
 const input=mountInput('codeInput','Four unique digits 1–6',4),secret=[];while(secret.length<4){const x=1+rnd(6);if(!secret.includes(x))secret.push(x)}
 let history=[],guesses=0;
 function guess(){if(!playing||paused)return;const s=input.value.trim();if(!/^[1-6]{4}$/.test(s)||new Set(s).size!==4){notify('Enter 4 DIFFERENT digits, each from 1 through 6.');return}
 const digits=s.split('').map(Number),exact=digits.filter((v,i)=>v===secret[i]).length,common=digits.filter(v=>secret.includes(v)).length,misplaced=common-exact;
 history.push({s,exact,misplaced});guesses++;reward(exact*65+misplaced*25);
 input.value='';
 if(exact===4){finish(true,'Security vault unlocked in '+guesses+' guesses!');return}
 if(guesses>=8){finish(false,'Vault locked after eight guesses.');return}
 level=guesses+1;notify('Exact position: '+exact+'. Correct digit, wrong slot: '+misplaced+'. '+(8-guesses)+' tries left.')}
 input.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();e.stopPropagation();guess()}});
 return{help:'Deduce four UNIQUE digits between 1 and 6. After each guess see exact matches and misplaced matches. Eight attempts.',act(k){if(k==='action')guess();else input.focus()},update(){},draw(){bg('#121c2f','#122f42');label('CODEBREAKER VAULT',32,50,31,'#ffd5a1');label('4 unique digits from 1–6  •  8 attempts',34,77,17);
 for(let i=0;i<8;i++){const y=106+i*47;rectangle(35,y,849,41,i===history.length?'#24465b':'#142c41',7);if(history[i]){const h=history[i];for(let j=0;j<4;j++){circle(70+j*56,y+20,17,col[Number(h.s[j])-1]);label(h.s[j],70+j*56,y+26,17,'#0a2936','center')}
 label(h.exact+' EXACT',355,y+27,17,'#a5edcc');label(h.misplaced+' MISPLACED',568,y+27,17,'#efd196')}else{label('ATTEMPT '+(i+1),57,y+26,14,'#819daa')}}
 label('Submit using Enter or ACTION',33,505,17,'#f2d5a4')},dispose(){input.parentElement.remove()}}
}
const builders={'hex-bloom':hexBloom,'prism-relay':prismRelay,'kitchen-rush':kitchenRush,'type-defender':typeDefender,'codebreaker-vault':codebreaker};
if(!builders[slug])throw Error('Unknown game '+slug);
function loop(t){requestAnimationFrame(loop);const dt=Math.min(.05,Math.max(0,(t-last)/1000||.016));last=t;if(playing&&!paused)scene.update(dt);if(scene)scene.draw();else{bg();label('CHOOSE START GAME',W/2,H/2,32,'#eddfb2','center')}hud();frame++}
$('overlay-title').textContent='READY FOR '+slug.replaceAll('-',' ').toUpperCase()+'?';notify('Start a completely different original game. Use mouse, touch or keyboard controls.');requestAnimationFrame(loop);
window.__MPW_NEXT_GAME_QA__={snapshot:()=>({slug,playing,paused,finished,score,level,frame}),start,act,pause};
})();