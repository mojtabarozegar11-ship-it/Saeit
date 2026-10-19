import assert from 'node:assert/strict';
import test from 'node:test';
import {
  GENES,FLOW,climate,makeMeta,ensureMeta,validMeta,makeContract,requiredDays,
  pulse,cycleGene,harvest,attackModifier,advance,deliver,rivalsTurn
} from '../src/strategy.mjs';
function kingdom(){
 return {day:1,meta:makeMeta(1),plots:{'6,9':{type:'wheat',age:1,gene:'bounty'}},
 gold:420,wood:220,food:190,army:12,health:450,
 enemies:[220,260,310],enemySelected:0};
}
test('new player has valid finite turn-based ecosystem',()=>{
 const s=kingdom(),m=ensureMeta(s);
 assert(validMeta(m,s.day));assert.equal(m.water,85);assert.equal(m.gene,'bounty');
 assert(Object.keys(FLOW).length===3);assert(Object.keys(GENES).length===3);
 assert(climate(1).season==='بهار');
 assert(climate(11).season==='پاییز');
 assert.equal(climate(20).season,'زمستان');
});
test('same-day water action can run exactly once; prevents free infinite pulse',()=>{
 const s=kingdom();
 const result=pulse(s,'grow',0);
 assert.equal(result.ok,true);assert.equal(s.meta.water,60);
 assert.equal(s.plots['6,9'].age,2);
 assert.equal(pulse(s,'guard',0).ok,false);
 assert.equal(pulse(s,'siege',0).ok,false);
 s.day++;advance(s);
 assert.equal(pulse(s,'guard',0).ok,true);assert.equal(s.meta.guardCharges,2);
 assert.equal(pulse(s,'grow',0).ok,false);
 assert(validMeta(s.meta,s.day));
});
test('irrigation and genes change food, readiness and drought behavior',()=>{
 const s=kingdom();
 assert.equal(requiredDays(s,{gene:'swift'},3),2);
 assert.equal(requiredDays(s,{gene:'bounty'},3),3);
 const base={food:34,gold:15};
 const p={type:'wheat',gene:'bounty',age:2};
 let out=harvest(s,p,base);
 assert(out.food>=51,'bounty must exceed base yield');assert.equal(s.meta.cargo.wheat,1);
 assert.equal(cycleGene(s).label,'زودرس');
 assert.equal(cycleGene(s).label,'مقاوم');
 const water=s.meta.water;
 out=harvest(s,{type:'wheat',gene:'hardy',age:2},base);
 assert(s.meta.water>water,'hardy seed returns water');
 assert(out.food>=34);
});
test('flooded siege boosts only next attack on selected live enemy',()=>{
 const s=kingdom();
 assert.equal(pulse(s,'siege',1).ok,true);
 assert.equal(attackModifier(s,0).damage,0,'Cannot raid wrong rival');
 assert.equal(attackModifier(s,1).damage,39);
 assert.equal(attackModifier(s,1).damage,0,'Siege bonus consumed');
 assert.equal(pulse(s,'grow',0).ok,false,'Cannot double use');
});
test('river defense is meaningful against each rival and has finite charges',()=>{
 const s=kingdom();
 s.day=2;
 assert.equal(pulse(s,'guard',0).ok,true);
 const h=s.health;
 const a=rivalsTurn(s,0,.5,0);
 assert.equal(a.kind,'blitz');assert(a.shielded);assert(h-s.health<20);
 assert.equal(s.meta.guardCharges,1);
 const b=rivalsTurn(s,2,.5,0);
 assert(b.shielded);assert.equal(s.meta.guardCharges,0);
 const c=rivalsTurn(s,0,.5,0);
 assert(!c.shielded&&c.damage>a.damage);
});
test('each rival has distinct economy: iron heals, shadow steals food',()=>{
 const s=kingdom();s.day=4;
 s.enemies[1]=130;
 const iron=rivalsTurn(s,1,.5,0);
 assert(iron.healed>0);assert.equal(s.enemies[1],130+iron.healed);
 const previousFood=s.food;
 const shadow=rivalsTurn(s,2,.5,0);
 assert(shadow.stolen>0);assert.equal(s.food,previousFood-shadow.stolen);
});
test('contracts remove cargo and award actual gold, wood, water and renown',()=>{
 const s=kingdom();
 const before=s.gold;
 assert.equal(deliver(s).ok,false,'No phantom delivery');
 s.meta.cargo.wheat=2;
 const result=deliver(s);
 assert.equal(result.ok,true);
 assert.equal(s.meta.cargo.wheat,0);
 assert.equal(s.gold,before+result.gold);
 assert.equal(s.meta.renown,25);
 assert.equal(s.meta.contractsDone,1);
 assert.equal(s.meta.contract.type,'corn');
 assert.equal(deliver(s).ok,false,'Cannot exploit already-delivered order');
});
test('climate progression cannot create negative or unbounded water',()=>{
 const s=kingdom();
 s.meta.water=99;
 for(let day=2;day<150;day++){
  s.day=day;advance(s);
  assert(s.meta.water>=0&&s.meta.water<=100);
  assert(Number.isInteger(s.plots['6,9'].age));
  assert(validMeta(s.meta,s.day));
 }
});
test('invalid pulse cannot spend water',()=>{
 const s=kingdom(),old=s.meta.water;
 assert.equal(pulse(s,'impossible').ok,false);assert.equal(s.meta.water,old);
 s.meta.water=10;assert.equal(pulse(s,'grow').ok,false);assert.equal(s.meta.water,10);
 s.meta.water=50;s.enemies[0]=0;assert.equal(pulse(s,'siege',0).ok,false);
 assert.equal(s.meta.water,50);
});
console.log('FARM_RIVER_PULSE_STRATEGY_TESTS_REGISTERED=9');
