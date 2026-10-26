'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const html=fs.readFileSync(path.join(__dirname,'../../games/air-supremacy-fa/index.html'),'utf8');
assert.match(html,/<link rel="canonical" href="https:\/\/zomorodmelal\.ir\/games\/air-supremacy\/">/);
assert.match(html,/<meta property="og:url" content="https:\/\/zomorodmelal\.ir\/games\/air-supremacy\/">/);
assert.match(html,/hreflang="en" href="https:\/\/mojplaywin\.com\/air-supremacy\/"/);
const raw=html.split('<script>')[1].split('</script>')[0];
const vm=require('node:vm');
new vm.Script(raw);
const start=raw.indexOf('if(!run)return; // Fatal collision');
const end=raw.indexOf('for(let i=sparks.length-1;',start);
assert.ok(start>0&&end>start,'fatal-frame and missile loop must exist');
const update=new Function('run','missiles','enemies','dt','blast','kill','len',raw.slice(start,end));
function caseRun(life,z,active=true){
 const target={x:0,y:0,z,hp:5},enemies=[target],missiles=[{x:0,y:0,z:-4,life,speed:190,kind:'guided',target}];
 update(active,missiles,enemies,.1,()=>{},e=>{enemies.splice(enemies.indexOf(e),1)},Math.hypot);
 return {target,enemies,missiles};
}
let hit=caseRun(1,-25);
assert.equal(hit.enemies.length,0,'swept impact should kill target in the current frame');
assert.equal(hit.missiles.length,0);
let expired=caseRun(0,-14);
assert.equal(expired.target.hp,5,'expired missile cannot inflict damage');
assert.equal(expired.missiles.length,0);
let fatal=caseRun(1,-14,false);
assert.equal(fatal.target.hp,5,'no post-sortie missile damage');
console.log('ZOMOROD_FA_GUIDED_MISSILE_REGRESSION_PASS');
