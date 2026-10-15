"use strict";
const core=window.CircuitCourier;
const el=id=>document.getElementById(id);
let stage=1,game=core.fresh(stage),progress={};
try{
  const saved=JSON.parse(localStorage.getItem("circuit_courier_progress_v1")||"{}");
  if(saved&&typeof saved==="object"&&!Array.isArray(saved))
    for(const [key,val] of Object.entries(saved)){
      if(/^([1-9]|[12][0-9]|3[0-6])$/.test(key)&&Number.isInteger(val)&&val>=1&&val<=3)
        progress[key]=val;
    }
}catch(_){}
function persist(){try{localStorage.setItem("circuit_courier_progress_v1",JSON.stringify(progress));}catch(_){}}
function draw(){
  const board=el("board");board.replaceChildren();
  const data=game.level;
  for(let at=0;at<36;at++){
    const tile=document.createElement("div");
    let cls="cell",label="empty";let symbol="";
    const beaconIndex=data.beacons.indexOf(at);
    if(data.walls.includes(at)){cls+=" wall";symbol="▣";label="wall";}
    if(at===data.exit){cls+=" exit";symbol="⬡";label="exit";}
    if(beaconIndex>=0&&!(game.mask&(1<<beaconIndex))){
      cls+=" beacon";symbol="◆";label="uncollected beacon";
    }
    if(at===game.at){cls+=" hero-tile";symbol="◈";label="courier";}
    tile.className=cls;tile.textContent=symbol;
    tile.setAttribute("role","gridcell");
    tile.setAttribute("aria-label","row "+(Math.floor(at/6)+1)+
      " column "+(at%6+1)+": "+label);
    board.append(tile);
  }
  el("level-label").textContent=String(stage).padStart(2,"0")+" / 36";
  el("energy").textContent=String(Math.max(0,data.energyBudget-game.moves));
  el("beacons").textContent=String(popcount(game.mask))+" / 3";
  el("optimal").textContent=String(data.optimalMoves);
  const text=game.status==="won"?
    "Circuit restored! "+core.award(game)+" ★ earned. Next stage unlocked.":
    game.status==="out_of_energy"?"Energy exhausted. Restart and try another route.":
    game.assisted?"Hint used: one-star award maximum. Complete the route!":
    "Collect all three beacons, then reach the exit.";
  el("status").textContent=text;
  el("next").disabled=game.status!=="won"||stage===core.COUNT;
  const finished=Object.keys(progress).length;
  el("progress").textContent=finished+" / 36";
  el("progress-bar").style.width=(100*finished/core.COUNT).toFixed(1)+"%";
  drawStages();
}
function popcount(n){let x=0;for(;n;n&=n-1)x++;return x;}
function drawStages(){
  const root=el("level-list");root.replaceChildren();
  const unlocked=Math.min(core.COUNT,Math.max(0,...Object.keys(progress).map(Number))+1);
  // Any completed higher stage implies previous stages had been visited.
  for(let n=1;n<=core.COUNT;n++){
    const btn=document.createElement("button");
    btn.type="button";btn.textContent=String(n);
    btn.title=progress[n]?progress[n]+" star(s) earned":"Stage "+n;
    btn.disabled=n>unlocked&&!progress[n];
    if(progress[n])btn.classList.add("complete");
    if(n===stage)btn.setAttribute("aria-current","true");
    btn.setAttribute("aria-label","Stage "+n+
      (progress[n]?", "+progress[n]+" stars":""));
    btn.addEventListener("click",()=>changeStage(n));root.append(btn);
  }
}
function changeStage(n){stage=n;game=core.fresh(n);draw();}
function move(direction){
  if(game.status!=="playing")return;
  game=core.apply(game,direction);
  if(game.status==="won"){
    progress[stage]=Math.max(progress[stage]||0,core.award(game));persist();
  }
  draw();
}
for(const btn of document.querySelectorAll("[data-move]")){
  btn.addEventListener("click",()=>move(btn.dataset.move));
}
document.addEventListener("keydown",e=>{
  const key={ArrowUp:"up",ArrowRight:"right",ArrowDown:"down",ArrowLeft:"left"}[e.key];
  if(!key||e.altKey||e.ctrlKey||e.metaKey||
      ["INPUT","TEXTAREA","SELECT"].includes(document.activeElement?.tagName))return;
  e.preventDefault();move(key);
});
el("hint").addEventListener("click",()=>{
  if(game.status!=="playing")return;
  const suggested=core.hint(game);
  game={...game,assisted:true};
  draw();
  el("status").textContent=suggested?
    "Shortest-route hint: move "+suggested.toUpperCase()+". Award limited to 1 star.":
    "No route remains. Restart the level.";
});
el("reset").addEventListener("click",()=>changeStage(stage));
el("next").addEventListener("click",()=>{if(game.status==="won"&&stage<core.COUNT)changeStage(stage+1);});
draw();
