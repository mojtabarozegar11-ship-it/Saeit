// G-01 R32: tactical navigation is read-only; it never changes campaign state.
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
export function paintTacticalMap(canvas,state,isWall,target){
 if(!canvas||!state||typeof isWall!=='function')return false;
 const ctx=canvas.getContext('2d');if(!ctx)return false;
 const side=canvas.width,cell=side/MAP_CELLS;
 ctx.clearRect(0,0,side,side);ctx.fillStyle='#0c272d';ctx.fillRect(0,0,side,side);
 for(let y=0;y<MAP_CELLS;y++)for(let x=0;x<MAP_CELLS;x++)
  if(isWall(x,y)){ctx.fillStyle='#56717a';ctx.fillRect(x*cell,y*cell,cell,cell)}
 if(Array.isArray(target)&&target.length===2&&target.every(Number.isFinite)&&target.every(v=>v>=0&&v<MAP_CELLS)){
  ctx.fillStyle='#ffda7e';ctx.beginPath();ctx.arc(target[0]*cell,target[1]*cell,Math.max(3,cell*.45),0,2*Math.PI);ctx.fill();
 }
 for(const enemy of (Array.isArray(state.enemies)?state.enemies.slice(0,30):[])){
  if(!enemy||!(enemy.hp>0)||!Number.isFinite(enemy.x)||!Number.isFinite(enemy.y))continue;
  if(enemy.x<0||enemy.y<0||enemy.x>=MAP_CELLS||enemy.y>=MAP_CELLS)continue;
  ctx.fillStyle='#ff8475';ctx.beginPath();ctx.arc(enemy.x*cell,enemy.y*cell,Math.max(2,cell*.3),0,2*Math.PI);ctx.fill();
 }
 if(![state.x,state.y,state.angle].every(Number.isFinite))return true;
 ctx.save();ctx.translate(state.x*cell,state.y*cell);ctx.rotate(state.angle);
 ctx.fillStyle='#79ffd3';ctx.beginPath();ctx.moveTo(cell*.85,0);ctx.lineTo(-cell*.6,-cell*.5);ctx.lineTo(-cell*.6,cell*.5);ctx.closePath();ctx.fill();ctx.restore();
 return true;
}
