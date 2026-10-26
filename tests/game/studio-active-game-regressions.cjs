const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');

const raha=fs.readFileSync('templates/studio_raha/index.html','utf8');
const jungle=raha.slice(raha.indexOf('function jungleGame(stage){'),raha.indexOf('function runnerGame(stage)'));
assert(jungle.startsWith('function jungleGame('),'Super Jungle Run must have its own active-game logic');
let keyListener=null;
const documentMock={
 addEventListener(type,fn){if(type==='keydown')keyListener=fn},
 removeEventListener(type,fn){if(type==='keydown'&&keyListener===fn)keyListener=null},
 getElementById(){return {classList:{contains:()=>true}}}
};
const jungleContext={document:documentMock,jungleCleanup:()=>{},button:(label,fn)=>({textContent:label,onclick:fn,id:''})};
vm.createContext(jungleContext);vm.runInContext(jungle,jungleContext);
function makeStage(){
 const nodes={};for(const id of ['jungleStatus','jungleObstacle','jungleHint','jungleFeedback'])nodes[id]={textContent:''};
 const buttons=[0,1,2].map(i=>({dataset:{jungleAction:String(i)},disabled:false,handlers:{},addEventListener(k,f){this.handlers[k]=f}}));
 return {nodes,buttons,retry:null,innerHTML:'',querySelector(s){return s==='#jungleRetry'?this.retry:nodes[s.slice(1)]},querySelectorAll(s){assert.equal(s,'[data-jungle-action]');return buttons},append(b){this.retry=b}};
}
let stage=makeStage();jungleContext.jungleGame(stage);assert(keyListener,'keyboard listener installed');
const course=[0,1,2,0,1,2,1,0,2,0,2,1];
for(const action of course)stage.buttons[action].handlers.click();
assert.match(stage.nodes.jungleObstacle.textContent,/completed/);
assert.equal(stage.buttons.every(b=>b.disabled),true);
assert(stage.retry,'replay must be offered after finishing');
jungleContext.jungleCleanup();assert.equal(keyListener,null,'closing game must release keyboard listener');
stage=makeStage();jungleContext.jungleGame(stage);
for(let i=0;i<3;i++)stage.buttons[1].handlers.click();
assert.match(stage.nodes.jungleObstacle.textContent,/Rest and try again/);
assert.equal(stage.buttons.every(b=>b.disabled),true);
jungleContext.jungleCleanup();

const taniya=fs.readFileSync('templates/taniya_studio/index.html','utf8');
const cake=taniya.slice(taniya.indexOf('function mountCake(){'),taniya.indexOf('    function mountPet()'));
assert(cake.startsWith('function mountCake('),'Cake Maker source missing');
const preview={textContent:'',style:{}},icing={value:'#ff79b8'},tops=['🍓','🌼','🍬'].map(top=>({dataset:{top},onclick:null}));
const candle={onclick:null},download={onclick:null},reset={onclick:null},cakeBody={
 querySelector(s){return s==='[data-action="candle"]'?candle:s==='[data-action="cake-download"]'?download:s==='[data-action="cake-reset"]'?reset:null},
 querySelectorAll(s){assert.equal(s,'[data-top]');return tops}
};
let svg=null,lastMessage='';
const cakeContext={
 gamebody:cakeBody,stage(){},btn:(label,action)=>'<button data-action="'+action+'">'+label+'</button>',
 $:(s)=>s==='#cakepreview'?preview:s==='#icing'?icing:null,
 say:s=>{lastMessage=s},downloadSvg:(name,body)=>{svg={name,body}}
};
vm.createContext(cakeContext);vm.runInContext(cake,cakeContext);cakeContext.mountCake();
tops[1].onclick();candle.onclick({stopPropagation(){}});
candle.onclick({stopPropagation(){}});
tops[2].onclick();
assert.equal((preview.textContent.match(/🕯️/g)||[]).length,2,'changing toppings must preserve candles');
icing.value='#123abc';icing.oninput({target:icing});
download.onclick({stopPropagation(){}});
assert.equal(svg.name,'taniya-cake-card');
assert(svg.body.includes('#123abc'),'download must reflect frosting color');
assert(svg.body.includes('2 candles'),'download must reflect candle count');
assert(svg.body.includes('🍬'),'download must reflect topping');
reset.onclick({stopPropagation(){}});
assert.equal(icing.value,'#ff79b8','start over restores default frosting');
assert.equal(preview.textContent,'🎂 🍓 ','start over clears toppings and candles');
download.onclick({stopPropagation(){}});
assert(svg.body.includes('#ff79b8'),'reset cake export uses default frosting');
assert(svg.body.includes('0 candles'),'reset cake export clears candles');
assert(svg.body.includes('🍓'),'reset cake export restores berries');
for(let i=0;i<30;i++)candle.onclick({stopPropagation(){}});
assert.equal((preview.textContent.match(/🕯️/g)||[]).length,12,'cap candles at 12');
assert.match(lastMessage,/twelve/);
console.log('PASS: Super Jungle Run twelve-obstacle progression, loss/retry, listener cleanup; Cake Maker persistent decorations, personalized SVG, capped candles');
