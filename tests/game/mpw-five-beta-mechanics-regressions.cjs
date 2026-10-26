const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
function gameSource(name){return fs.readFileSync('site_releases/mojplaywin/games-20261021/'+name+'/index.html','utf8')}
const beacon=gameSource('beacon-labyrinth');
const moveCode=beacon.slice(beacon.indexOf('function move(dx,dy){'),beacon.indexOf('function stepDrone',beacon.indexOf('function move(dx,dy){')));
assert(moveCode.startsWith('function move(dx,dy)'),'Beacon movement missing');
let score=0,finished=false;
const maze=Array.from({length:3},()=>[0,0,0]);
const bc={player:{x:1,y:1},maze,exit:{x:2,y:1},beacons:[{found:true},{found:true},{found:true}],drones:[{x:2,y:1}],turns:0,level:5,
 a:{running:true,tone(){},notice(){},score(n){score+=n},finish(){finished=true}},
 Math:Object.assign(Object.create(Math),{random:()=>1}),
 stepDrone(){},hit(){this.player={x:1,y:1}},makeMaze(){}};
vm.createContext(bc);vm.runInContext(moveCode,bc);
bc.move(1,0);
assert.equal(score,0,'sentinel contact cannot grant exit bonus');
assert.equal(finished,false,'sentinel contact cannot complete the sector');
bc.drones=[];bc.player={x:1,y:1};bc.move(1,0);
assert.equal(finished,true,'clear portal must still complete the final sector');
assert(score>0,'successful portal grants bonus');

const nebula=gameSource('nebula-salvage');
const updateCode=nebula.slice(nebula.indexOf('function update(dt){'),nebula.indexOf('function draw(){',nebula.indexOf('function update(dt){')));
assert(updateCode.startsWith('function update(dt)'),'Nebula simulation missing');
const nc={tick:0,time:65,regen:1.6,ammo:7,orbs:[],balls:[],shards:[],goal:5,progress:0,
 a:{finish(){}},addOrbs(){},Math};
vm.createContext(nc);vm.runInContext(updateCode,nc);
nc.update(.1);
assert.equal(nc.ammo,8,'one probe recharged');
assert(Math.abs(nc.regen-.05)<1e-9,'fractional recharge time must survive');
nc.regen=1.6;nc.update(.1);
assert.equal(nc.regen,0,'full magazine cannot precharge a free probe');
nc.ammo=7;nc.update(.1);
assert.equal(nc.ammo,7,'firing after a full magazine starts a fresh cooldown');
console.log('PASS: Beacon collision cannot fake portal victory; Nebula probe recharge preserves fractions and prevents precharge');
