/**
 * River Pulse: deterministic turn-based ecosystem and kingdom strategy.
 * Standalone logic, independently testable; no timers, real-money or streak hooks.
 */
export const GENES = Object.freeze({
  bounty: {label:'پربار',desc:'۵۰٪ محصول بیشتر',icon:'🌻'},
  swift: {label:'زودرس',desc:'یک روز رشد سریع‌تر',icon:'⚡'},
  hardy: {label:'مقاوم',desc:'مقاومت در خشکسالی و بذر جایزه',icon:'🛡️'}
});
export const FLOW = Object.freeze({
  grow:{label:'آبیاری هوشمند',icon:'💧',detail:'دو روز رشد بیشتر و تقویت برداشت',color:0x6ee4e1},
  guard:{label:'خندق دفاعی',icon:'🛡️',detail:'کاهش آسیب حمله‌های بعدی دشمن',color:0x77d6ad},
  siege:{label:'سیل محاصره',icon:'🌊',detail:'ضربه تقویتی به قلعه انتخابی',color:0xffd38c}
});
export const SEASONS=['بهار','تابستان','پاییز','زمستان'];
export const WEATHER=['آفتابی','نسیم بارانی','گرما','باران آرام','خشکسالی','مه'];
export function climate(day){
 const seasonIndex=Math.floor((day-1)/5)%4;
 let weather=WEATHER[(Math.floor((day-1)/2)+seasonIndex*2)%WEATHER.length];
 return {seasonIndex,season:SEASONS[seasonIndex],weather,
   recharge:seasonIndex===1?12:seasonIndex===3?14:24,
   isDrought:weather==='خشکسالی'||(seasonIndex===1&&weather==='گرما'),
   rain:weather==='نسیم بارانی'||weather==='باران آرام'};
}
export function makeContract(day=1){
 const type=['wheat','corn','pumpkin'][Math.floor((day-1)/4)%3];
 const quota=type==='wheat'?2:1;
 return {type,quota,delivered:0,rewardGold:type==='pumpkin'?160:120,
   rewardWood:24,rewardWater:18,issuedAt:day};
}
export function makeMeta(day=1){
 return {
  v:1,water:85,flow:'grow',pulseDay:0,irrigationUntil:0,
  guardCharges:0,siegeCharges:0,siegeTarget:0,
  gene:'bounty',renown:0,cargo:{wheat:0,corn:0,pumpkin:0},
  contract:makeContract(day),contractsDone:0,weatherEvents:0
 };
}
export function validMeta(m,day){
 const bounded=(v,max=1000000)=>Number.isSafeInteger(v)&&v>=0&&v<=max;
 const cropKinds=['wheat','corn','pumpkin'];
 return !!(m&&m.v===1&&bounded(m.water,100)&&bounded(m.pulseDay,day)&&
 bounded(m.irrigationUntil,day+8)&&bounded(m.guardCharges,3)&&
 bounded(m.siegeCharges,2)&&bounded(m.siegeTarget,2)&&
 Object.hasOwn(FLOW,m.flow)&&Object.hasOwn(GENES,m.gene)&&
 bounded(m.renown)&&bounded(m.contractsDone)&&bounded(m.weatherEvents)&&
 m.cargo&&cropKinds.every(k=>bounded(m.cargo[k],10000))&&
 m.contract&&cropKinds.includes(m.contract.type)&&
 ['quota','delivered','rewardGold','rewardWood','rewardWater','issuedAt'].every(k=>bounded(m.contract[k]))&&
 m.contract.quota>=1&&m.contract.delivered<=m.contract.quota);
}
export function ensureMeta(s){
 if(!validMeta(s.meta,s.day))s.meta=makeMeta(s.day);
 return s.meta;
}
export function seedDetails(s){
 const m=ensureMeta(s),info=GENES[m.gene],c=climate(s.day);
 return {name:info.label,trait:m.gene,climate:c,icon:info.icon};
}
export function requiredDays(s,p,days){
 const m=ensureMeta(s);
 return Math.max(1,days-(p.gene==='swift'?1:0));
}
export function pulse(s,mode,enemyIndex=0){
 const m=ensureMeta(s);
 if(!Object.hasOwn(FLOW,mode))return {ok:false,reason:'دستور ناشناخته'};
 if(m.pulseDay===s.day)return {ok:false,reason:'این روز یک‌بار می‌توانید شبکه آب را تغییر دهید؛ با روز بعد فرصت تازه‌ای می‌گیرید.'};
 if(m.water<25)return {ok:false,reason:'برای فعال‌سازی دست‌کم ۲۵ واحد آب لازم است.'};
 if(mode==='siege'&&(enemyIndex<0||enemyIndex>2||s.enemies?.[enemyIndex]===0))return {ok:false,reason:'ابتدا یک قلعه فعال برای محاصره انتخاب کنید.'};
 m.water-=25;
 m.pulseDay=s.day;m.flow=mode;
 if(mode==='grow'){m.irrigationUntil=s.day+2;
  for(const plot of Object.values(s.plots||{}))if(['wheat','corn','pumpkin'].includes(plot.type))plot.age+=1;
 }else if(mode==='guard')m.guardCharges=Math.min(3,m.guardCharges+2);
 else {m.siegeCharges=1;m.siegeTarget=enemyIndex;}
 return {ok:true,mode,water:m.water,color:FLOW[mode].color};
}
export function cycleGene(s){
 const m=ensureMeta(s);const keys=Object.keys(GENES);
 m.gene=keys[(keys.indexOf(m.gene)+1)%keys.length];
 return GENES[m.gene];
}
export function harvest(s,plot,base){
 const m=ensureMeta(s),c=climate(s.day),gene=plot.gene||'bounty';
 let modifier=gene==='bounty'?1.5:gene==='hardy'?1.15:1;
 if(c.isDrought&&m.irrigationUntil<s.day&&gene!=='hardy')modifier*=.8;
 if(m.irrigationUntil>=s.day)modifier*=1.18;
 const food=Math.max(1,Math.floor(base.food*modifier));
 const gold=Math.max(1,Math.floor(base.gold*(gene==='bounty'?1.08:1)));
 m.cargo[plot.type]=(m.cargo[plot.type]||0)+1;
 if(gene==='hardy')m.water=Math.min(100,m.water+4);
 return {food,gold,stock:m.cargo[plot.type]};
}
export function attackModifier(s,targetIndex){
 const m=ensureMeta(s);
 if(m.siegeCharges>0&&m.siegeTarget===targetIndex){
  m.siegeCharges-=1;
  return {damage:39,explain:'موج آبِ محاصره راه دفاعی رقیب را شکست'};
 }
 return {damage:0,explain:''};
}
export function mitigateRaid(s,baseDamage){
 const m=ensureMeta(s);
 if(m.guardCharges>0){
   m.guardCharges-=1;
   return {damage:Math.max(1,Math.round(baseDamage*.33)),shielded:true};
 }
 return {damage:baseDamage,shielded:false};
}
export function advance(s){
 const m=ensureMeta(s),forecast=climate(s.day);
 const boost=m.irrigationUntil>=s.day?1:0;
 const drought=forecast.isDrought&&boost===0;
 for(const plot of Object.values(s.plots||{})){
  if(['wheat','corn','pumpkin'].includes(plot.type))plot.age+=drought&&plot.gene!=='hardy'?.65:1+boost;
 }
 const replenishment=forecast.recharge+(forecast.rain?9:0);
 m.water=Math.min(100,m.water+replenishment);
 if(s.day%5===1)m.weatherEvents++;
 return {forecast,boost,replenishment,newWater:m.water};
}
export function deliver(s){
 const m=ensureMeta(s),offer=m.contract;
 const available=m.cargo[offer.type]||0;
 const remaining=offer.quota-offer.delivered;
 if(available<remaining)return {ok:false,reason:'برای سفارش فعلی هنوز '+remaining+' محموله '+offer.type+' لازم است.'};
 m.cargo[offer.type]-=remaining;
 offer.delivered+=remaining;
 s.gold+=offer.rewardGold;
 s.wood+=offer.rewardWood;
 m.water=Math.min(100,m.water+offer.rewardWater);
 m.renown+=25;m.contractsDone++;
 const result={ok:true,type:offer.type,gold:offer.rewardGold,wood:offer.rewardWood,water:offer.rewardWater};
 m.contract=makeContract(s.day+4);
 return result;
}
export function rivalsTurn(s,rivalIndex,random=0.5){
 const m=ensureMeta(s),hp=s.enemies?.[rivalIndex]||0;
 if(!hp)return {kind:'gone',damage:0};
 // Each faction has an independent personality; the player can counter them.
 if(rivalIndex===0){
   const initial=39+Math.floor(random*13),r=mitigateRaid(s,initial);
   s.health=Math.max(0,s.health-r.damage);
   return {kind:'blitz',damage:r.damage,shielded:r.shielded};
 }
 if(rivalIndex===1){
  const initial=30+Math.floor(random*10),r=mitigateRaid(s,initial);
  s.health=Math.max(0,s.health-r.damage);
  const restored=s.day%4===0?Math.min(16,260-hp):0;
  s.enemies[rivalIndex]+=restored;
  return {kind:'armored',damage:r.damage,shielded:r.shielded,healed:restored};
 }
 const initial=21+Math.floor(random*9),r=mitigateRaid(s,initial);
 s.health=Math.max(0,s.health-r.damage);
 const stolen=Math.min(s.food,9+Math.floor(random*8));
 s.food-=stolen;
 return {kind:'raider',damage:r.damage,shielded:r.shielded,stolen};
}
