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
