const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../../games/air-supremacy/index.html'),'utf8');
const fn=html.match(/function persistProfile\(\)\{[^\n]*return saved\}/)?.[0];
assert(fn,'persistProfile must verify local storage readback');
for(const available of [true,false]){
 const elements={profileSaveNotice:{textContent:''},endSaveStatus:{textContent:''}};
 const data=new Map(),storage={setItem(k,v){if(!available)throw Error('quota');data.set(k,v)},getItem:k=>data.get(k)||null};
 const ctx={localStorage:storage,SAVE_KEY:'air-qa',profile:{credits:12},$:id=>elements[id]};
 vm.runInNewContext(fn+';globalThis.result=persistProfile()',ctx);
 assert.equal(ctx.result,available);
 assert.match(elements.profileSaveNotice.textContent,available?/verified/:/blocked or full/);
 assert.match(elements.endSaveStatus.textContent,/No purchases or financial transactions/);
}
console.log('Air Supremacy R26 storage success and failure messages PASS');
