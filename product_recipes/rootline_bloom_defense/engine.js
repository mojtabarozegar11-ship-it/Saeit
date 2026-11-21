/* ROOTLINE Bloom Defense — deterministic offline game engine, no network or assets. */
(function (global) {
  'use strict';
  const ROWS=5, COLS=8, WATER_CAP=100;
  const PLANTS=Object.freeze({
    thorn:{cost:12,range:440,damage:19,rate:.9},
    mist:{cost:16,range:350,damage:5,rate:1.3},
    well:{cost:19,range:0,damage:0,rate:0}
  });
  function newGame(){
    return {started:false,paused:false,over:false,health:12,maxHealth:12,
      water:38,score:0,wave:0,elapsed:0,waveRemaining:0,spawnTimer:0,
      spawnSequence:0,intermission:0,selected:'thorn',
      plants:[],enemies:[],effects:[],cooldown:0,notice:'Ready to defend the roots.',events:[]};
  }
  function announce(g,text){g.notice=text;g.events.push(text);if(g.events.length>10)g.events.shift();}
  function choose(g,kind){if(!Object.prototype.hasOwnProperty.call(PLANTS,kind))return false;g.selected=kind;return true;}
  function plant(g,row,col,kind=g.selected){
    if(!g.started||g.over||g.paused)return {ok:false,reason:'Start or resume defense before planting.'};
    if(!Number.isInteger(row)||row<0||row>=ROWS||!Number.isInteger(col)||col<0||col>=COLS)return {ok:false,reason:'Select a garden tile.'};
    if(!Object.prototype.hasOwnProperty.call(PLANTS,kind))return {ok:false,reason:'Unknown plant type.'};
    if(g.plants.some(p=>p.row===row&&p.col===col))return {ok:false,reason:'This tile is occupied.'};
    if(g.water<PLANTS[kind].cost)return {ok:false,reason:'Not enough water.'};
    g.water-=PLANTS[kind].cost;
    g.plants.push({row,col,kind,level:1,timer:.25,bob:0});
    announce(g,kind[0].toUpperCase()+kind.slice(1)+' planted in lane '+(row+1)+'.');
    return {ok:true};
  }
  function startWave(g){
    if(!g.started||g.over)return false;
    g.wave+=1;g.waveRemaining=3+g.wave*2;g.spawnTimer=1;
    g.spawnSequence=0;g.intermission=0;
    announce(g,'Wave '+g.wave+' approaching. Protect the roots!');
    return true;
  }
  function start(g){
    if(g.started||g.over)return false;
    g.started=true;startWave(g);return true;
  }
  function rainburst(g){
    if(!g.started||g.paused||g.over)return {ok:false,reason:'Start or resume defense.'};
    if(g.cooldown>0)return {ok:false,reason:'Rainburst is recharging.'};
    if(g.water<25)return {ok:false,reason:'Rainburst requires 25 water.'};
    if(g.enemies.length===0)return {ok:false,reason:'No pests in the field.'};
    g.water-=25;g.cooldown=12;
    for(const e of g.enemies){e.hp-=15;e.slow=Math.max(e.slow,4);}
    for(const e of g.enemies.filter(e=>e.hp<=0)){g.score+=e.points;}
    g.enemies=g.enemies.filter(e=>e.hp>0);
    g.effects.push({type:'rain',time:1,max:1});
    announce(g,'Rainburst! Pests weakened and slowed.');
    return {ok:true};
  }
  function spawnEnemy(g){
    const index=g.spawnSequence++;
    const row=(index*3+g.wave*2)%ROWS;
    const type=g.wave>=4&&index%5===0?'armored':g.wave>=2&&index%3===0?'swift':'beetle';
    const stats=type==='armored'?{hp:80,speed:20,points:30,hurt:2}:
      type==='swift'?{hp:24,speed:42,points:17,hurt:1}:{hp:36,speed:27,points:12,hurt:1};
    g.enemies.push({id:g.wave*1000+index,row,x:862,type,hp:stats.hp,maxHp:stats.hp,
      speed:stats.speed,points:stats.points,hurt:stats.hurt,slow:0,phase:index});
    g.waveRemaining--;
  }
  function hit(g,enemy,plant,damage){
    enemy.hp-=damage;
    if(plant.kind==='mist')enemy.slow=Math.max(enemy.slow,2.7);
    g.effects.push({type:plant.kind,time:.25,max:.25,row:plant.row,col:plant.col,targetX:enemy.x});
  }
  function advance(g,rawDt){
    if(!g.started||g.paused||g.over)return;
    const dt=Math.min(.1,Math.max(0,Number(rawDt)||0));
    if(dt===0)return;
    g.elapsed+=dt;g.cooldown=Math.max(0,g.cooldown-dt);
    g.water=Math.min(WATER_CAP,g.water+dt*(1.35+g.plants.filter(p=>p.kind==='well').length*1.1));
    for(const e of g.enemies){
      e.slow=Math.max(0,e.slow-dt);
      e.x-=e.speed*dt*(e.slow>0?.42:1);
      e.phase+=dt*7;
    }
    const survivors=[];
    for(const e of g.enemies){
      if(e.x<68){g.health-=e.hurt;announce(g,'A pest reached the root!');}
      else survivors.push(e);
    }
    g.enemies=survivors;
    for(const p of g.plants){
      p.bob+=dt;p.timer-=dt;
      if(p.kind==='well'||p.timer>0)continue;
      const px=97+p.col*92;
      const target=g.enemies.filter(e=>e.row===p.row&&e.x>px&&e.x-px<PLANTS[p.kind].range)
        .sort((a,b)=>a.x-b.x)[0];
      if(target){hit(g,target,p,PLANTS[p.kind].damage);p.timer=PLANTS[p.kind].rate;}
    }
    const living=[];
    for(const e of g.enemies){
      if(e.hp<=0)g.score+=e.points;else living.push(e);
    }
    g.enemies=living;
    g.effects=g.effects.filter(e=>(e.time-=dt)>0);
    if(g.health<=0){
      g.health=0;g.over=true;announce(g,'The roots are lost. Review your strategy and restart.');
      return;
    }
    if(g.waveRemaining>0){
      g.spawnTimer-=dt;
      if(g.spawnTimer<=0){
        spawnEnemy(g);
        g.spawnTimer=1.15+Math.max(.35,1.15-g.wave*.07);
      }
    }else if(g.enemies.length===0){
      if(g.intermission===0){
        g.intermission=4;g.water=Math.min(WATER_CAP,g.water+8);
        announce(g,'Wave '+g.wave+' cleared! +8 water, next wave in four seconds.');
      }else{
        g.intermission-=dt;
        if(g.intermission<=0)startWave(g);
      }
    }
  }
  const API={ROWS,COLS,PLANTS,newGame,choose,plant,start,startWave,rainburst,advance};
  if(typeof module!=='undefined'&&module.exports)module.exports=API;
  else global.RootlineEngine=API;
})(typeof globalThis!=='undefined'?globalThis:this);
