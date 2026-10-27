const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const html=fs.readFileSync('templates/taniya_studio/index.html','utf8');
const start=html.indexOf('    let cakeState='),end=html.indexOf('    function mountPet(){',start);
assert(start>=0&&end>start,'Cake Maker code must be present in the actual studio template');
const cakeSource=html.slice(start,end);
const nodes={
  cakepreview:{textContent:'',style:{},attributes:{},setAttribute(name,value){this.attributes[name]=value}},
  icing:{value:'#ff79b8',oninput:null}
};
const tops=['🍓','🌼','🍬'].map(top=>({dataset:{top},onclick:null}));
const downloads=[],messages=[];
const context={
  gamebody:{querySelectorAll(sel){assert.equal(sel,'[data-top]');return tops}},
  $(selector){return nodes[selector.slice(1)]},
  stage(markup){assert.match(markup,/Download your cake card/);nodes.cakepreview.textContent='🎂'},
  btn(label,action){return '<button data-action="'+action+'">'+label+'</button>'},
  say(message){messages.push(message)},
  downloadSvg(name,body){downloads.push({name,body})}
};
vm.createContext(context);
vm.runInContext(cakeSource,context);
const run=expression=>vm.runInContext(expression,context);
run('mountCake()');
assert.equal(run('cakeState.candles'),0);
assert.match(nodes.cakepreview.textContent,/🍓/);
assert.match(nodes.cakepreview.attributes['aria-label'],/berries, 0 candles/);
tops[2].onclick();
assert.equal(run('cakeState.topping'),'🍬');
run("handleCakeAction('candle')");
run("handleCakeAction('candle')");
assert.equal(run('cakeState.candles'),2);
assert.equal((nodes.cakepreview.textContent.match(/🕯️/g)||[]).length,2);
assert.match(nodes.cakepreview.attributes['aria-label'],/sweets, 2 candles/);
nodes.icing.oninput({target:{value:'#11aa22'}});
assert.equal(run('cakeState.icing'),'#11aa22');
assert.match(nodes.cakepreview.attributes['aria-label'],/frosting #11aa22/);
run("handleCakeAction('cake-download')");
assert.equal(downloads.length,1);
assert.equal(downloads[0].name,'taniya-cake-card');
assert.match(downloads[0].body,/fill="#11aa22"/);
assert.match(downloads[0].body,/🍬/);
assert.equal((downloads[0].body.match(/🕯️/g)||[]).length,2,'export must preserve exactly the visible candle count');
nodes.icing.oninput({target:{value:'"><script>'}});
assert.equal(run('cakeState.icing'),'#11aa22','untrusted color must not enter exported SVG');
tops[0].dataset.top='<script>';tops[0].onclick();
assert.equal(run('cakeState.topping'),'🍬','untrusted topping must not enter exported SVG');
for(let i=0;i<20;i++)run("handleCakeAction('candle')");
assert.equal(run('cakeState.candles'),12,'candle count must be bounded');
run("handleCakeAction('cake-download')");
assert.equal((downloads[1].body.match(/🕯️/g)||[]).length,12);
run('mountCake()');
assert.equal(run('cakeState.candles'),0,'Start over must clear all candles');
assert.equal(run('cakeState.topping'),'🍓','Start over must restore default topping');
assert.equal(run('cakeState.icing'),'#ff79b8','Start over must restore default icing');
assert.equal((nodes.cakepreview.textContent.match(/🕯️/g)||[]).length,0);
assert(messages.some(m=>m==='Cake topping updated.'),'topping changes must be announced');
assert(messages.some(m=>m==='Frosting color updated.'),'frosting changes must be announced');
assert.match(nodes.cakepreview.attributes['aria-label'],/berries, 0 candles/);
console.log('TANIYA_CAKE_MAKER_QA=PASS topping+icing+candles+SVG+input_guard+reset');
