const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const html=fs.readFileSync(path.join(__dirname,'../../games/echoform/signal-lattice.html'),'utf8');
const start=html.indexOf('function choose(i){'),end=html.indexOf('function manualPause()',start);
assert.ok(start>0&&end>start,'ECHOFORM choose implementation found');
const source=html.slice(start,end);
function scenario(storage){
 const nodes={storageNote:{textContent:''}},ctx={
  phase:'input',sequence:[3],cursor:0,round:1,best:0,session:1,KEY:'test-key',
  localStorage:storage,$:id=>nodes[id]||(nodes[id]={textContent:''}),
  light:()=>{},finish:()=>{},update:()=>{},setStatus:()=>{},setTimeout:()=>{}
 };
 vm.createContext(ctx);vm.runInContext(source+';this.chooseNow=choose;',ctx);
 ctx.chooseNow(3);return {ctx,nodes};
}
test('failed best-round storage readback visibly reports session-only progress',()=>{
 const {ctx,nodes}=scenario({setItem(){},getItem(){return null}});
 assert.equal(ctx.best,1);assert.match(nodes.storageNote.textContent,/session-only/);
});
test('successful best-round storage has no false warning',()=>{
 let value=null;const {ctx,nodes}=scenario({setItem(k,v){value=v},getItem(){return value}});
 assert.equal(ctx.best,1);assert.equal(nodes.storageNote.textContent,'');
});
test('storage exception cannot interrupt round completion',()=>{
 const {ctx,nodes}=scenario({setItem(){throw Error('quota')},getItem(){throw Error('quota')}});
 assert.equal(ctx.phase,'show');assert.match(nodes.storageNote.textContent,/session-only/);
});
