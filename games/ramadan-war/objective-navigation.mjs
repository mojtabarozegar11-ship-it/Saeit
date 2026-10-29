// Deterministic grid routing for campaign objective guidance; no network or storage.
// Returns the first traversable waypoint. Never invents a route through walls.
export function objectiveWaypoint(px, py, tx, ty, passable, size=16) {
  if (![px,py,tx,ty].every(Number.isFinite) || !Number.isInteger(size) || size<2 || size>64 || typeof passable!=='function') return null;
  const sx=Math.floor(px), sy=Math.floor(py), gx=Math.floor(tx), gy=Math.floor(ty);
  if ([sx,sy,gx,gy].some(v=>v<0||v>=size) || !passable(sx,sy) || !passable(gx,gy)) return null;
  if (sx===gx && sy===gy) return {x:tx,y:ty,steps:0};
  const count=size*size, prev=new Int32Array(count);prev.fill(-2);
  const start=sy*size+sx, goal=gy*size+gx, queue=new Int32Array(count);
  let head=0,tail=0;prev[start]=-1;queue[tail++]=start;
  while(head<tail && prev[goal]===-2){
    const current=queue[head++],x=current%size,y=Math.floor(current/size);
    for(const [dx,dy] of [[1,0],[0,1],[-1,0],[0,-1]]){
      const nx=x+dx,ny=y+dy;
      if(nx<0||ny<0||nx>=size||ny>=size)continue;
      const next=ny*size+nx;
      if(prev[next]!==-2||!passable(nx,ny))continue;
      prev[next]=current;queue[tail++]=next;
    }
  }
  if(prev[goal]===-2)return null;
  let current=goal,steps=0;
  while(prev[current]!==start){current=prev[current];steps++;if(current<0||steps>=count)return null}
  return {x:current%size+.5,y:Math.floor(current/size)+.5,steps:steps+1};
}
export const INTERACT_RANGE=1.35;
export function canInteractAt(px,py,tx,ty,range=INTERACT_RANGE){
  return [px,py,tx,ty,range].every(Number.isFinite)&&range>=0&&Math.hypot(px-tx,py-ty)<=range;
}

 // When a goal is blocked, guide only to a traversable position near it.
export function objectiveApproachWaypoint(px,py,tx,ty,passable,radius=INTERACT_RANGE,size=16){
  if (![px,py,tx,ty,radius].every(Number.isFinite)||radius<=0||radius>4||!Number.isInteger(size)||size<2||size>64||typeof passable!=='function')return null;
  let best=null;
  for(let y=Math.max(0,Math.floor(ty-radius-1));y<=Math.min(size-1,Math.ceil(ty+radius));y++){
    for(let x=Math.max(0,Math.floor(tx-radius-1));x<=Math.min(size-1,Math.ceil(tx+radius));x++){
      if(!passable(x,y))continue;
      const cx=x+.5,cy=y+.5;
      if(Math.hypot(cx-tx,cy-ty)>radius)continue;
      const route=objectiveWaypoint(px,py,cx,cy,passable,size);
      if(route&&(best===null||route.steps<best.steps))best=route;
    }
  }
  return best;
}
// Recovery intel is order-independent: use the closest reachable package.
export function closestReachableObjective(px,py,targets,passable,size=16){
  if(!Array.isArray(targets)||targets.length>64||typeof passable!=='function')return null;
  let best=null,steps=Infinity;
  for(const target of targets){
    if(!Array.isArray(target)||target.length<2||!target.slice(0,2).every(Number.isFinite))continue;
    const route=objectiveWaypoint(px,py,target[0],target[1],passable,size);
    if(route&&route.steps<steps){best=[target[0],target[1]];steps=route.steps}
  }
  return best;
}
