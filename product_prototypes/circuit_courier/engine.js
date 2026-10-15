/* Circuit Courier: original deterministic offline route-and-collect puzzle.
 * No external services; all paths are solved by exact BFS over player position
 * and collected beacon bitmask. Browser + Node-compatible pure core.
 */
(function(root,factory){
  "use strict";
  const engine=factory();
  if(typeof module==="object"&&module.exports)module.exports=engine;
  else root.CircuitCourier=engine;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
  "use strict";
  const SIZE=6,COUNT=36;
  const START=30,EXIT=5;
  const DIRECTIONS=Object.freeze([
    ["up",0,-1],["right",1,0],["down",0,1],["left",-1,0]
  ]);
  function rng(seed){
    let state=(seed>>>0)||1;
    return function(){
      state^=state<<13;state^=state>>>17;state^=state<<5;
      return(state>>>0)/4294967296;
    };
  }
  function advance(cell,direction,walls){
    const step=DIRECTIONS.find(x=>x[0]===direction);
    if(!step)throw Error("unknown direction");
    const x=(cell%SIZE)+step[1],y=Math.floor(cell/SIZE)+step[2];
    if(x<0||x>=SIZE||y<0||y>=SIZE)return null;
    const next=y*SIZE+x;
    return walls.includes(next)?null:next;
  }
  function shortestRoute(level,cell=START,mask=0){
    const all=(1<<level.beacons.length)-1;
    const visitMask=(p,m)=>{
      const i=level.beacons.indexOf(p);
      return i===-1?m:m|(1<<i);
    };
    mask=visitMask(cell,mask);
    const startKey=cell+":"+mask;
    const queue=[[cell,mask,""]];
    const seen=new Set([startKey]);
    for(let head=0;head<queue.length;head++){
      const [at,bits,route]=queue[head];
      if(at===EXIT&&bits===all)return route;
      for(const [name] of DIRECTIONS){
        const next=advance(at,name,level.walls);
        if(next===null)continue;
        const nextBits=visitMask(next,bits);
        const key=next+":"+nextBits;
        if(seen.has(key))continue;
        seen.add(key);
        queue.push([next,nextBits,route+name[0]]);
      }
    }
    return null;
  }
  function decode(move){
    return {u:"up",r:"right",d:"down",l:"left"}[move]||null;
  }
  function generateLevel(number){
    if(!Number.isInteger(number)||number<1||number>COUNT)
      throw Error("stage outside 1..36");
    const random=rng((number*0x9e3779b1)>>>0);
    let candidate=null;
    for(let tries=0;tries<300;tries++){
      const walls=[],available=[];
      for(let cell=0;cell<SIZE*SIZE;cell++){
        if(cell!==START&&cell!==EXIT)available.push(cell);
      }
      // Fisher–Yates, from a stable seeded PRNG.
      for(let i=available.length-1;i>0;i--){
        const j=Math.floor(random()*(i+1));
        [available[i],available[j]]=[available[j],available[i]];
      }
      const wallCount=3+(number%7);
      for(let i=0;i<wallCount;i++)walls.push(available[i]);
      const beacons=available.slice(wallCount,wallCount+3);
      candidate={number,size:SIZE,start:START,exit:EXIT,
        walls:walls.slice().sort((a,b)=>a-b),
        beacons:beacons.slice().sort((a,b)=>a-b)};
      const route=shortestRoute(candidate);
      if(route!==null&&route.length>=11&&route.length<=34){
        candidate.optimalMoves=route.length;
        candidate.energyBudget=route.length+2+(number%4);
        return candidate;
      }
    }
    // Only for pathological seeds: deterministic known-solvable empty board.
    candidate={number,size:SIZE,start:START,exit:EXIT,walls:[],
      beacons:[7,16,24]};
    candidate.optimalMoves=shortestRoute(candidate).length;
    candidate.energyBudget=candidate.optimalMoves+2+(number%4);
    return candidate;
  }
  function fresh(number){
    const level=generateLevel(number);
    return {level,at:START,mask:0,moves:0,status:"playing",
      assisted:false,lastMove:null};
  }
  function apply(game,direction){
    if(!game||game.status!=="playing")return game;
    const next=advance(game.at,direction,game.level.walls);
    if(next===null)return game;
    const i=game.level.beacons.indexOf(next);
    const mask=i<0?game.mask:game.mask|(1<<i);
    const count=game.moves+1;
    const won=next===EXIT&&mask===(1<<game.level.beacons.length)-1;
    return {...game,at:next,mask,moves:count,lastMove:direction,
      status:won?"won":count>=game.level.energyBudget?"out_of_energy":"playing"};
  }
  function hint(game){
    if(!game||game.status!=="playing")return null;
    const route=shortestRoute(game.level,game.at,game.mask);
    return route?decode(route[0]):null;
  }
  function award(game){
    if(!game||game.status!=="won")return 0;
    if(game.assisted)return 1;
    const gap=game.moves-game.level.optimalMoves;
    return gap===0?3:gap<=2?2:1;
  }
  return Object.freeze({SIZE,COUNT,DIRECTIONS,START,EXIT,
    generateLevel,shortestRoute,decode,fresh,apply,hint,award});
});
