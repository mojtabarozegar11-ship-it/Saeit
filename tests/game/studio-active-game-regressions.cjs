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
const jungleBestStore=new Map();
const jungleContext={document:documentMock,jungleCleanup:()=>{},localStorage:{getItem:key=>jungleBestStore.get(key)||null,setItem:(key,value)=>jungleBestStore.set(key,value)},button:(label,fn)=>({textContent:label,onclick:fn,id:''})};
vm.createContext(jungleContext);vm.runInContext(jungle,jungleContext);
function makeStage(){
 const nodes={};for(const id of ['jungleStatus','jungleObstacle','jungleHint','jungleFeedback'])nodes[id]={textContent:''};
 const buttons=[0,1,2].map(i=>({dataset:{jungleAction:String(i)},disabled:false,handlers:{},addEventListener(k,f){this.handlers[k]=f}}));
 return {nodes,buttons,retry:null,innerHTML:'',querySelector(s){return s==='#jungleRetry'?this.retry:nodes[s.slice(1)]},querySelectorAll(s){assert.equal(s,'[data-jungle-action]');return buttons},append(b){this.retry=b}};
}
let stage=makeStage();jungleContext.jungleGame(stage);assert(keyListener,'keyboard listener installed');
for(const modifier of ['ctrlKey','altKey','metaKey','isComposing']){
 let prevented=false;
 keyListener({code:'Digit1',repeat:false,target:{tagName:'DIV'},[modifier]:true,preventDefault(){prevented=true}});
 assert.equal(prevented,false,modifier+' must remain available to browser/IME');
 assert.match(stage.nodes.jungleStatus.textContent,/Obstacle 1 \/ 12/,modifier+' must not advance gameplay');
}
const course=[0,1,2,0,1,2,1,0,2,0,2,1];
for(const action of course)stage.buttons[action].handlers.click();
assert.match(stage.nodes.jungleObstacle.textContent,/completed/);
assert.equal(jungleBestStore.get('studioRahamJungleBestV1'),'12','only bounded best progress is saved');
assert.equal(stage.buttons.every(b=>b.disabled),true);
assert(stage.retry,'replay must be offered after finishing');
let completedKeyPrevented=false;
keyListener({code:'Digit1',repeat:false,target:{tagName:'DIV'},preventDefault(){completedKeyPrevented=true}});
assert.equal(completedKeyPrevented,false,'finished jungle game must not swallow digit keys');
assert.match(stage.nodes.jungleObstacle.textContent,/completed/,'finished run stays complete after a keypress');
jungleContext.jungleCleanup();assert.equal(keyListener,null,'closing game must release keyboard listener');
stage=makeStage();jungleContext.jungleGame(stage);
assert.match(stage.nodes.jungleStatus.textContent,/Best 12 \/ 12/,'replay shows persisted best');
for(let i=0;i<3;i++)stage.buttons[1].handlers.click();
assert.match(stage.nodes.jungleObstacle.textContent,/Rest and try again/);
assert.equal(stage.buttons.every(b=>b.disabled),true);
jungleContext.jungleCleanup();
jungleContext.localStorage={getItem(){throw Error('blocked storage')},setItem(){throw Error('blocked storage')}};
stage=makeStage();assert.doesNotThrow(()=>jungleContext.jungleGame(stage),'private mode cannot prevent starting the game');
stage.buttons[0].handlers.click();assert.match(stage.nodes.jungleStatus.textContent,/Best 1 \/ 12/);
jungleContext.jungleCleanup();

const taniya=fs.readFileSync('templates/taniya_studio/index.html','utf8');
const cake=taniya.slice(taniya.indexOf('function mountCake(){'),taniya.indexOf('    function mountPet()'));
assert(cake.startsWith('function mountCake('),'Cake Maker source missing');
const preview={textContent:'',style:{}},icing={value:'#ff79b8'},tops=['🍓','🌼','🍬'].map(top=>({dataset:{top},onclick:null}));
const candle={onclick:null},download={onclick:null},cakeBody={
 querySelector(s){return s==='[data-action="candle"]'?candle:s==='[data-action="cake-download"]'?download:null},
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
for(let i=0;i<30;i++)candle.onclick({stopPropagation(){}});
assert.equal((preview.textContent.match(/🕯️/g)||[]).length,12,'cap candles at 12');
assert.match(lastMessage,/twelve/);
console.log('PASS: Super Jungle Run twelve-obstacle progression, loss/retry, listener cleanup; Cake Maker persistent decorations, personalized SVG, capped candles');

const cartFn=raha.slice(raha.indexOf('function loadCart(){'),raha.indexOf('function showToast('));
assert(cartFn.startsWith('function loadCart('),'cart sanitization helper must exist');
const catalog=[{name:'Creative Play Starter Bundle',price:9.99,emoji:'🎁',desc:'catalog-only'}];
function runCart(storage){
 const context={products:catalog,localStorage:storage,JSON,Number,Array,Math};
 vm.createContext(context);
 return vm.runInContext(cartFn+';loadCart()',context);
}
assert.equal(runCart({getItem(){throw Error('SecurityError')}}).length,0,'blocked storage must not crash studio');
assert.equal(runCart({getItem:()=>'{broken'}).length,0,'invalid JSON must not crash games');
assert.equal(runCart({getItem:()=>JSON.stringify({name:'not an array'})}).length,0);
const tampered=runCart({getItem:()=>JSON.stringify([
 {name:'Creative Play Starter Bundle',price:0.01,emoji:'<img src=x onerror=alert(1)>',qty:19},
 {name:'Creative Play Starter Bundle',price:0.01,qty:19},
 {name:'Injected Product',price:0,qty:5}
])});
assert.equal(tampered.length,1,'unrecognized products must be discarded');
assert.equal(tampered[0].price,9.99,'local cart cannot override catalog price');
assert.equal(tampered[0].emoji,'🎁','local cart cannot inject HTML');
assert.equal(tampered[0].qty,20,'duplicate quantity is bounded');
assert.match(raha,/function saveCart\(\)\{try\{localStorage\.setItem/,'saving must tolerate blocked storage');
console.log('PASS: Raham cart sanitization, blocked-storage fallback, price integrity, injection rejection, quantity cap');
