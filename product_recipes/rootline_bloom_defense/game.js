/* ROOTLINE Bloom Defense v0.1 — original Canvas renderer/controller, offline only */
'use strict';
(function(){
  const E=window.RootlineEngine;
  if(!E){document.getElementById('notice').textContent='Game engine missing. Reload the local files together.';return;}
  const canvas=document.getElementById('field'),ctx=canvas.getContext('2d',{alpha:false});
  if(!ctx){document.getElementById('notice').textContent='A Canvas 2D compatible browser is required.';return;}
  const $=id=>document.getElementById(id);
  const overlay=$('overlay'),title=$('overlayTitle'),intro=$('overlayText');
  let g=E.newGame(),best=0,muted=true,audio=null,last=0,hover=null,ended=false;
  try{best=Math.max(0,Number(localStorage.getItem('rootline_best_v1'))||0)}catch(_){}
  const X=70,Y=74,CW=92,RH=81;
  function shade(a,b,t){return a+(b-a)*t;}
  function circle(x,y,r,color){
    ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();
  }
  function line(x1,y1,x2,y2,color,width=2){
    ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke();
  }
  function note(message){$('notice').textContent=message;}
  function tone(hz=300,duration=.07){
    if(muted)return;
    try{
      const C=window.AudioContext||window.webkitAudioContext;
      if(!C)return;
      audio=audio||new C();if(audio.state==='suspended')audio.resume().catch(()=>{});
      const os=audio.createOscillator(),gain=audio.createGain(),t=audio.currentTime;
      os.type='sine';os.frequency.setValueAtTime(hz,t);
      os.frequency.exponentialRampToValueAtTime(Math.max(70,hz*.72),t+duration);
      gain.gain.setValueAtTime(.045,t);gain.gain.exponentialRampToValueAtTime(.0001,t+duration);
      os.connect(gain);gain.connect(audio.destination);os.start(t);os.stop(t+duration);
    }catch(_){}
  }
  function hud(){
    $('wave').textContent=String(Math.max(1,g.wave));
    $('health').textContent=g.health+' / '+g.maxHealth;
    $('water').textContent=String(Math.floor(g.water));
    $('score').textContent=String(g.score);
    $('best').textContent=String(best);
    $('rain').disabled=!g.started||g.over||g.paused||g.water<25||g.cooldown>0||g.enemies.length===0;
    $('rain').firstChild.textContent=g.cooldown>0?'Rainburst ('+Math.ceil(g.cooldown)+'s) ':'Rainburst ';
    $('pause').disabled=!g.started||g.over;
    $('pause').firstChild.textContent=g.paused?'Resume ':'Pause ';
    document.querySelectorAll('.tool').forEach(b=>{
      const active=b.dataset.kind===g.selected;
      b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));
    });
  }
  function showOverlay(heading,message,button){
    title.textContent=heading;intro.textContent=message;$('launch').textContent=button;overlay.hidden=false;
  }
  function reset(){
    g=E.newGame();ended=false;hover=null;
    showOverlay('Your orchard is under threat','Plant defenders, manage irrigation, and protect five root lanes.','Start defense');
    note('Ready for a new run.');hud();draw();
  }
  function begin(){
    if(g.over)g=E.newGame();
    if(E.start(g)){overlay.hidden=true;note(g.notice);tone(475,.12);}
    hud();
  }
  function select(kind){if(E.choose(g,kind)){hud();note(kind+' selected. Tap a garden tile.');tone(350,.04);}}
  function pointerCell(event){
    const rect=canvas.getBoundingClientRect();
    if(!rect.width||!rect.height)return null;
    const x=(event.clientX-rect.left)*canvas.width/rect.width;
    const y=(event.clientY-rect.top)*canvas.height/rect.height;
    const row=Math.floor((y-Y)/RH),col=Math.floor((x-X)/CW);
    if(x<X||x>=X+CW*8||y<Y||y>=Y+RH*5)return null;
    return {row,col};
  }
  canvas.addEventListener('pointermove',e=>{hover=pointerCell(e);});
  canvas.addEventListener('pointerleave',()=>{hover=null;});
  canvas.addEventListener('pointerdown',e=>{
    if(e.pointerType==='touch')e.preventDefault();
    const cell=pointerCell(e);
    if(!cell){note('Select one of the highlighted garden tiles.');return;}
    const result=E.plant(g,cell.row,cell.col);
    note(result.ok?g.notice:result.reason);if(result.ok)tone(570,.09);hud();
  },{passive:false});
  document.querySelectorAll('.tool').forEach(b=>b.addEventListener('click',()=>select(b.dataset.kind)));
  $('launch').addEventListener('click',begin);
  $('restart').addEventListener('click',reset);
  $('pause').addEventListener('click',()=>{
    if(!g.started||g.over)return;g.paused=!g.paused;
    note(g.paused?'Defense paused.':'Defense resumed.');hud();
  });
  $('rain').addEventListener('click',()=>{
    const result=E.rainburst(g);note(result.ok?g.notice:result.reason);
    if(result.ok)tone(190,.29);hud();
  });
  $('help').addEventListener('click',()=>{
    const panel=$('instructions');panel.hidden=!panel.hidden;
    $('help').setAttribute('aria-expanded',String(!panel.hidden));
  });
  $('mute').addEventListener('click',()=>{
    muted=!muted;
    $('mute').textContent=muted?'Sound: off':'Sound: on';
    $('mute').setAttribute('aria-pressed',String(muted));
    if(!muted)tone(570,.11);
  });
  document.addEventListener('keydown',e=>{
    if(e.repeat)return;
    if(e.key==='1'||e.key==='2'||e.key==='3'){select({1:'thorn',2:'mist',3:'well'}[e.key]);}
    if(e.key===' '){e.preventDefault();const r=E.rainburst(g);note(r.ok?g.notice:r.reason);if(r.ok)tone(200,.25);hud();}
    if(e.key.toLowerCase()==='p'&&g.started&&!g.over){g.paused=!g.paused;note(g.paused?'Paused':'Resumed');hud();}
  });
  function backdrop(time){
    const sky=ctx.createLinearGradient(0,0,0,540);
    sky.addColorStop(0,'#102e3a');sky.addColorStop(.48,'#245048');sky.addColorStop(1,'#153b33');
    ctx.fillStyle=sky;ctx.fillRect(0,0,900,540);
    circle(767,47,22,'#dae3bc');circle(778,43,20,'#183a43');
    for(let i=0;i<23;i++){
      const xx=30+(i*127)%820,yy=11+(i*41)%55;
      circle(xx,yy,(i%3+1)*.65,'rgba(235,248,194,.4)');
    }
    for(let row=0;row<5;row++){
      const y=Y+row*RH;
      ctx.fillStyle=row%2?'rgba(55,103,66,.68)':'rgba(47,92,59,.74)';
      ctx.fillRect(X,y,8*CW,RH-2);
      for(let col=0;col<8;col++){
        const x=X+col*CW;
        ctx.fillStyle=(row+col)%2?'rgba(50,110,70,.23)':'rgba(18,56,42,.17)';
        ctx.fillRect(x+1,y+1,CW-2,RH-4);
        ctx.strokeStyle='rgba(187,216,147,.17)';ctx.lineWidth=1;
        ctx.strokeRect(x+.5,y+.5,CW-1,RH-3);
        circle(x+15+(row*7+col*5)%20,y+58,2,'rgba(143,195,117,.34)');
      }
      ctx.fillStyle='#0c272a';ctx.fillRect(0,y,67,RH-2);
      ctx.fillStyle='#668f7b';ctx.fillRect(55,y+6,8,RH-15);
      ctx.fillStyle='rgba(143,210,166,.65)';ctx.font='13px system-ui';ctx.textAlign='center';
      ctx.fillText(String(row+1),34,y+44);
      circle(840,y+RH*.5,5,'rgba(236,192,105,.6)');
    }
    const glow=.23+.1*Math.sin(time/1150);
    ctx.fillStyle='rgba(31,73,55,'+glow+')';ctx.fillRect(817,73,70,406);
    ctx.strokeStyle='#6b9d80';ctx.strokeRect(X,Y,8*CW,5*RH-2);
    ctx.textAlign='left';ctx.fillStyle='#e8efc9';ctx.font='bold 15px system-ui';
    ctx.fillText('THE ROOTLINE',15,64);
    ctx.textAlign='right';ctx.fillText('PEST FRONT',872,64);
    line(57,84,57,461,'#b4db9a',4);
    for(let i=0;i<5;i++){
      const y=Y+i*RH+RH/2;
      circle(55,y,9,'#86bd8c');circle(55,y,4,'#e1e7a2');
    }
    if(hover&&!g.over&&g.started&&!g.paused){
      const x=X+hover.col*CW,y=Y+hover.row*RH;
      ctx.fillStyle='rgba(232,220,128,.20)';ctx.fillRect(x+2,y+2,CW-4,RH-6);
      ctx.strokeStyle='#e5d47b';ctx.lineWidth=2;ctx.strokeRect(x+3,y+3,CW-6,RH-8);
    }
    ctx.fillStyle='#d3e7c9';ctx.textAlign='left';ctx.font='12px system-ui';
    ctx.fillText('Waves intensify • Guard the vulnerable lanes',72,518);
    if(g.intermission>0){ctx.textAlign='right';ctx.fillText('Next wave in '+Math.ceil(g.intermission)+'s',824,518);}
  }
  function drawPlant(p,time){
    const x=X+p.col*CW+CW/2,y=Y+p.row*RH+RH*.55;
    ctx.save();ctx.translate(x,y);
    const sway=Math.sin(time/520+p.bob*1.8+p.col*.2)*3;
    ctx.shadowBlur=13;ctx.shadowColor=p.kind==='mist'?'#82ceea':'#6cd889';
    ctx.fillStyle='#172c22';ctx.beginPath();ctx.ellipse(0,20,27,8,0,0,Math.PI*2);ctx.fill();
    line(0,13,sway,-20,'#70a779',7);
    if(p.kind==='thorn'){
      ctx.fillStyle='#a9d884';
      for(let i=0;i<7;i++){const a=i*Math.PI*2/7;
        ctx.beginPath();ctx.moveTo(sway+Math.cos(a)*7,-18+Math.sin(a)*7);
        ctx.lineTo(sway+Math.cos(a)*24,-18+Math.sin(a)*24);
        ctx.lineTo(sway+Math.cos(a+.27)*8,-18+Math.sin(a+.27)*8);ctx.fill();}
      circle(sway,-18,12,'#e1c96f');circle(sway,-18,5,'#54783f');
    }else if(p.kind==='mist'){
      circle(sway,-17,19,'#6db4b7');circle(sway,-17,14,'#b3dad2');
      for(let i=0;i<4;i++)circle(sway-14+i*9,-28+Math.sin(time/330+i+p.col)*5,3,'#d6efec');
    }else{
      ctx.fillStyle='#9cbe87';ctx.fillRect(-18,-15,36,30);
      ctx.fillStyle='#b7d1ae';ctx.fillRect(-23,-22,46,9);
      circle(sway,-23,12,'#e8bb64');circle(sway,-23,6,'#765f3c');
      line(-10,8,10,8,'#6b966b',3);
    }
    ctx.restore();
  }
  function drawEnemy(e){
    const x=e.x,y=Y+e.row*RH+RH*.55;
    ctx.save();ctx.translate(x,y+Math.sin(e.phase)*2);
    ctx.shadowBlur=9;ctx.shadowColor='#170f1e';
    ctx.fillStyle='#1d2021';ctx.beginPath();ctx.ellipse(0,20,23,7,0,0,Math.PI*2);ctx.fill();
    const armored=e.type==='armored',swift=e.type==='swift';
    ctx.fillStyle=armored?'#a98f61':swift?'#c79c81':'#945c56';
    ctx.beginPath();ctx.ellipse(0,0,armored?23:swift?14:19,armored?22:15,0,0,Math.PI*2);ctx.fill();
    ctx.fillStyle=armored?'#776d58':swift?'#ede0ae':'#7a3e40';
    ctx.beginPath();ctx.ellipse(-4,-4,armored?13:9,armored?17:11,-.1,0,Math.PI*2);ctx.fill();
    circle(9,-5,2.7,'#f7e7bd');circle(10,-5,1.2,'#171616');
    for(let leg=0;leg<3;leg++){const dy=(leg-1)*9;line(-12,dy, -24,dy+Math.sin(e.phase+leg)*5,'#c38d7f',2);}
    if(e.slow>0){ctx.strokeStyle='#91dceb';ctx.lineWidth=3;ctx.strokeRect(-24,-26,48,51);}
    ctx.fillStyle='#351f23';ctx.fillRect(-22,-31,44,5);
    ctx.fillStyle=e.hp/e.maxHp>.45?'#8cde8c':'#efbd73';ctx.fillRect(-22,-31,44*Math.max(0,e.hp/e.maxHp),5);
    ctx.restore();
  }
  function drawEffect(effect){
    if(effect.type==='rain'){
      ctx.fillStyle='rgba(100,185,214,'+(effect.time*.21)+')';ctx.fillRect(X,Y,8*CW,5*RH);
      for(let i=0;i<35;i++){const xx=X+(i*73)%730,yy=Y+(i*47)%393;
        line(xx,yy,xx-10,yy+25,'rgba(188,237,242,'+(effect.time*.65)+')',2);}
    }else{
      const x=X+effect.col*CW+CW/2,y=Y+effect.row*RH+RH*.55;
      line(x,y,effect.targetX,y,effect.type==='mist'?'#a5e6ec':'#e4da81',effect.type==='mist'?5:3);
      circle(effect.targetX,y,5,'#edf8d3');
    }
  }
  function draw(){
    const now=performance.now();
    backdrop(now);
    for(const p of g.plants)drawPlant(p,now);
    for(const e of g.enemies)drawEnemy(e);
    for(const f of g.effects)drawEffect(f);
    if(g.paused){
      ctx.fillStyle='rgba(7,18,19,.58)';ctx.fillRect(0,0,900,540);
      ctx.textAlign='center';ctx.fillStyle='#fff';ctx.font='bold 36px system-ui';
      ctx.fillText('PAUSED',450,275);
    }
  }
  function frame(now){
    const dt=last?Math.min(.1,(now-last)/1000):0;last=now;
    E.advance(g,dt);
    if(g.events.length){const current=g.events[g.events.length-1];if($('notice').textContent!==current)note(current);}
    if(g.score>best){best=g.score;try{localStorage.setItem('rootline_best_v1',String(best));}catch(_){}}
    if(g.over&&!ended){
      ended=true;tone(130,.3);
      showOverlay('The rootline has fallen','You survived '+g.wave+' waves and earned '+g.score+' points. Try a different balance of thorns, mist and wells.','Try again');
    }
    draw();hud();requestAnimationFrame(frame);
  }
  hud();requestAnimationFrame(frame);
})();
