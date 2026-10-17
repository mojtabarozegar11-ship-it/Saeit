/* Three accessible rotating carousels and independently moving navigation/globe. */
(function(){"use strict";
var scene=document.querySelector(".orbital-scene");if(!scene)return;
var reduced=window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches;
var isPaused=Boolean(reduced);
var toggle=document.querySelector("[data-orb-motion]");
function updatePause(){
 document.body.classList.toggle("orb-motion-paused",isPaused);
 if(toggle){toggle.setAttribute("aria-pressed",String(isPaused));toggle.textContent=isPaused?"فعال‌کردن حرکت":"توقف حرکت";}
}
if(toggle)toggle.addEventListener("click",function(){isPaused=!isPaused;updatePause();});
updatePause();
var track=document.querySelector("[data-orb-nav-track]");
if(track&&!reduced){
 var items=track.querySelector(".orb-nav-items");
 if(items){
  var clone=items.cloneNode(true);
  clone.setAttribute("aria-hidden","true");clone.setAttribute("inert","");
  Array.prototype.forEach.call(clone.querySelectorAll("a"),function(a){a.tabIndex=-1;});
  track.appendChild(clone);track.classList.add("is-looping");
 }
}
var states=[];
function mod(n,max){return (n%max+max)%max;}
Array.prototype.forEach.call(document.querySelectorAll("[data-orbital-carousel]"),function(row){
 var deck=row.querySelector(".orb-deck"),cards=Array.prototype.slice.call(row.querySelectorAll(".orb-card"));
 if(!deck||cards.length<3)return;
 var selected=Math.floor(cards.length/2),hovered=false,focused=false,touchStart=null,ignoreClick=false;
 var status=row.querySelector("[data-orb-status]");
 function render(){
  cards.forEach(function(a,n){
   var d=mod(n-selected,cards.length);
   if(d>Math.floor(cards.length/2))d-=cards.length;
   a.dataset.position=String(d);
   a.setAttribute("aria-current",d===0?"true":"false");
   a.tabIndex=d===0?0:-1;
  });
  if(status)status.textContent=String(selected+1)+" از "+String(cards.length)+" — "+(cards[selected].dataset.label||"");
 }
 function rotate(dx){selected=mod(selected+dx,cards.length);render();}
 deck.classList.add("is-ready");render();
 var prev=row.querySelector("[data-orb-prev]"),next=row.querySelector("[data-orb-next]");
 if(prev)prev.addEventListener("click",function(){rotate(-1);});
 if(next)next.addEventListener("click",function(){rotate(1);});
 cards.forEach(function(card){
  card.addEventListener("click",function(e){
   if(ignoreClick){e.preventDefault();ignoreClick=false;return;}
   var shift=Number(card.dataset.position);
   if(shift!==0){e.preventDefault();rotate(shift);}
  });
 });
 row.addEventListener("keydown",function(e){
  if(e.key==="ArrowRight"){e.preventDefault();rotate(-1);}
  if(e.key==="ArrowLeft"){e.preventDefault();rotate(1);}
 });
 row.addEventListener("mouseenter",function(){hovered=true;});
 row.addEventListener("mouseleave",function(){hovered=false;});
 row.addEventListener("focusin",function(){focused=true;});
 row.addEventListener("focusout",function(e){if(!row.contains(e.relatedTarget))focused=false;});
 deck.addEventListener("touchstart",function(e){if(e.touches.length===1)touchStart=e.touches[0].clientX;},{passive:true});
 deck.addEventListener("touchend",function(e){
  if(touchStart===null||!e.changedTouches.length)return;
  var dx=e.changedTouches[0].clientX-touchStart;touchStart=null;
  if(Math.abs(dx)>50){ignoreClick=true;rotate(dx>0?-1:1);window.setTimeout(function(){ignoreClick=false;},250);}
 },{passive:true});
 states.push({move:rotate,ready:function(){return !isPaused&&!reduced&&!hovered&&!focused&&!document.hidden;}});
});
var timer=window.setInterval(function(){states.forEach(function(s){if(s.ready())s.move(1);});},6500);
window.addEventListener("pagehide",function(){window.clearInterval(timer);},{once:true});
})();