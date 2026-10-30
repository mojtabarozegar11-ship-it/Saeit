// G-01 R34: accessible, wall-aware route guidance. No campaign or storage writes.
export const MAP_CELLS=16;
export function relativeDirection(px,py,angle,tx,ty){
 if(![px,py,angle,tx,ty].every(Number.isFinite))return 'نامشخص';
 const dx=tx-px,dy=ty-py;
 if(Math.hypot(dx,dy)<.15)return 'همین‌جا';
 const d=Math.atan2(Math.sin(Math.atan2(dy,dx)-angle),Math.cos(Math.atan2(dy,dx)-angle));
 if(Math.abs(d)<=Math.PI/4)return 'روبه‌رو';
 if(Math.abs(d)>=3*Math.PI/4)return 'پشت سر';
 return d>0?'سمت راست':'سمت چپ';
}
// Return a shortest four-neighbour route; never draw a misleading straight line through walls.
// For a target embedded in a solid tile, find a reachable interaction cell within 1.35 tiles.
export function findTacticalRoute(px,py,tx,ty,isWall,size=MAP_CELLS){
 if(typeof isWall!=='function'||![px,py,tx,ty].every(Number.isFinite)||!Number.isInteger(size)||size<2||size>64)return null;
 if([px,py,tx,ty].some(v=>v<0||v>=size))return null;
 const sx=Math.floor(px),sy=Math.floor(py),gx=Math.floor(tx),gy=Math.floor(ty);
 if(isWall(sx,sy))return null;
 const solidGoal=!!isWall(gx,gy),n=size*size,start=sy*size+sx,prev=new Int32Array(n).fill(-1);
 const queue=new Int32Array(n);let head=0,tail=0;queue[tail++]=start;prev[start]=start;
 let end=-1;
 while(head<tail){
  const current=queue[head++],x=current%size,y=Math.floor(current/size);
  if((!solidGoal&&x===gx&&y===gy)||(solidGoal&&Math.hypot(x+.5-tx,y+.5-ty)<=1.35)){end=current;break;}
  for(const [dx,dy] of [[0,-1],[-1,0],[1,0],[0,1]]){
   const nx=x+dx,ny=y+dy;if(nx<0||ny<0||nx>=size||ny>=size)continue;
   const next=ny*size+nx;if(prev[next]!==-1||isWall(nx,ny))continue;
   prev[next]=current;queue[tail++]=next;
  }
 }
 if(end<0)return null;
 const path=[];for(let current=end;;current=prev[current]){
  path.push({x:current%size+.5,y:Math.floor(current/size)+.5});
  if(current===start)break;
  if(path.length>n)return null;
 }
 path.reverse();return {path,steps:path.length-1,approach:solidGoal};
}
// Guidance follows the same walkable route as the radar, never a bearing through a wall.
export function routeGuidance(px,py,angle,tx,ty,isWall,size=MAP_CELLS){
 if(![px,py,angle,tx,ty].every(Number.isFinite))return {status:'invalid',message:'مسیر هدف: نامشخص'};
 const route=findTacticalRoute(px,py,tx,ty,isWall,size);
 if(!route)return {status:'blocked',message:'مسیر هدف: مسدود؛ از سمت دیگری نزدیک شوید'};
 if(route.steps===0)return {status:'arrived',steps:0,message:route.approach?'در محدودهٔ تعامل هدف':'در محل هدف'};
 const next=route.path[1];
 return {status:'reachable',steps:route.steps,message:'مسیر هدف: '+relativeDirection(px,py,angle,next.x,next.y)+' · '+route.steps+' خانه'};
}
export function paintTacticalMap(canvas,state,isWall,target){
 if(!canvas||!state||typeof isWall!=='function')return false;
 const ctx=canvas.getContext?.('2d');if(!ctx||!Number.isFinite(canvas.width)||canvas.width<=0)return false;
 const side=canvas.width,cell=side/MAP_CELLS;
 ctx.clearRect(0,0,side,side);ctx.fillStyle='#0c272d';ctx.fillRect(0,0,side,side);
 for(let y=0;y<MAP_CELLS;y++)for(let x=0;x<MAP_CELLS;x++)
  if(isWall(x,y)){ctx.fillStyle='#56717a';ctx.fillRect(x*cell,y*cell,cell,cell)}
 const targetValid=Array.isArray(target)&&target.length===2&&target.every(Number.isFinite)&&target.every(v=>v>=0&&v<MAP_CELLS);
 const playerValid=[state.x,state.y,state.angle].every(Number.isFinite)&&state.x>=0&&state.y>=0&&state.x<MAP_CELLS&&state.y<MAP_CELLS;
 if(typeof canvas.setAttribute==='function'){
  const hint=targetValid&&playerValid?routeGuidance(state.x,state.y,state.angle,target[0],target[1],isWall):null;
  const label=hint?'نقشه تاکتیکی؛ '+hint.message:targetValid?'نقشه تاکتیکی؛ موقعیت بازیکن نامعتبر است':'نقشه تاکتیکی؛ هدف فعالی وجود ندارد';
  if(canvas.getAttribute?.('aria-label')!==label)canvas.setAttribute('aria-label',label);
 }
 if(targetValid&&playerValid){
  const route=findTacticalRoute(state.x,state.y,target[0],target[1],isWall);
  if(route&&route.path.length>1&&typeof ctx.stroke==='function'){
   ctx.save();ctx.beginPath();ctx.moveTo(state.x*cell,state.y*cell);
   for(const point of route.path.slice(1))ctx.lineTo(point.x*cell,point.y*cell);
   ctx.strokeStyle='#79ffd3';ctx.lineWidth=Math.max(2,cell*.2);ctx.stroke();ctx.restore();
  }
 }
 if(targetValid){
  ctx.fillStyle='#ffda7e';ctx.beginPath();ctx.arc(target[0]*cell,target[1]*cell,Math.max(3,cell*.45),0,2*Math.PI);ctx.fill();
 }
 for(const enemy of (Array.isArray(state.enemies)?state.enemies.slice(0,30):[])){
  if(!enemy||!(enemy.hp>0)||!Number.isFinite(enemy.x)||!Number.isFinite(enemy.y))continue;
  if(enemy.x<0||enemy.y<0||enemy.x>=MAP_CELLS||enemy.y>=MAP_CELLS)continue;
  ctx.fillStyle='#ff8475';ctx.beginPath();ctx.arc(enemy.x*cell,enemy.y*cell,Math.max(2,cell*.3),0,2*Math.PI);ctx.fill();
 }
 if(!playerValid)return true;
 ctx.save();ctx.translate(state.x*cell,state.y*cell);ctx.rotate(state.angle);
 ctx.fillStyle='#79ffd3';ctx.beginPath();ctx.moveTo(cell*.85,0);ctx.lineTo(-cell*.6,-cell*.5);ctx.lineTo(-cell*.6,cell*.5);ctx.closePath();ctx.fill();ctx.restore();
 return true;
}
