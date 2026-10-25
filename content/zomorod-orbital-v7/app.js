/* Zomorod Melal | offline design prototype: no server writes, no payments, no route changes. */
(() => {
  'use strict';
  const config=window.ZOMOROD_ORBIT_DATA;
  if(!config || config.rows?.length!==17 || config.rows.some(r=>r.cards?.length!==20))throw Error('17 × 20 content manifest required');
  const $=id=>document.getElementById(id);
  const stage=$('solar-stage'),svg=$('orbit-lines'),satellites=$('orbital-cards'),jumpList=$('orbit-jump-list'),shelves=$('orbit-shelves'),toggle=$('motion-toggle');
  const reducedMotion=window.matchMedia('(prefers-reduced-motion: reduce)');
  const SVG_NS='http://www.w3.org/2000/svg', TWO_PI=Math.PI*2;
  let userPaused=reducedMotion.matches,pausedOnCard=false,pausedOnFocus=false,inDetail=false;
  let elapsed=0,lastStamp=0,lastPaint=0,raf=0;
  let stageWidth=0,stageHeight=0,stageVisible=true,geometries=[];
  const stageObserver=new IntersectionObserver(([entry])=>{stageVisible=entry.isIntersecting;if(stageVisible)startLoop();else stopLoop();},{rootMargin:'100px'});
  stageObserver.observe(stage);
  const satellitesList=[], carousels=[];
  const pictos=['❧','✿','⌂','♘','♣','≈','♧','⌘','◈','⚙','▥','⚗','✺','✎','✦','◉','▤'];
  function el(tag,attrs={},label){
    const node=document.createElement(tag);
    for(const [k,v] of Object.entries(attrs)){
      if(k==='className')node.className=v;
      else if(k==='style')node.style.cssText=v;
      else node.setAttribute(k,String(v));
    }
    if(label!==undefined)node.textContent=label;
    return node;
  }
  function drawSatellites(){
    config.rows.forEach((row,index)=>{
      const a=el('a',{className:'orbital-link',href:'#'+row.target,'data-orbit':index});
      a.append(el('span',{className:'orbital-picto','aria-hidden':'true'},pictos[index]),el('span',{className:'orbital-title'},row.title));
      satellites.append(a);
      const path=document.createElementNS(SVG_NS,'ellipse');
      path.setAttribute('class','orbital-path');path.setAttribute('data-orbit',index);svg.append(path);
      satellitesList.push({a,path,index});
      if(jumpList)jumpList.append(el('a',{className:'jump-chip',href:'#'+row.target},row.title));
      a.addEventListener('mouseenter',()=>{pausedOnCard=true;path.classList.add('active')});
      a.addEventListener('mouseleave',()=>{pausedOnCard=false;path.classList.remove('active');startLoop()});
      a.addEventListener('focus',()=>{pausedOnFocus=true;path.classList.add('active')});
      a.addEventListener('blur',()=>{pausedOnFocus=false;path.classList.remove('active');startLoop()});
    });
  }
  // Geometry is recalculated only on viewport changes, not on every animation frame.
  function updateGeometry(){
    stageWidth=stage.clientWidth;stageHeight=stage.clientHeight;
    svg.setAttribute('viewBox',`0 0 ${stageWidth} ${stageHeight}`);
    geometries=satellitesList.map(({path,index})=>{
      const mobile=stageWidth<550;
      const ring=index%2===0?0:1;
      const rx=stageWidth*(mobile?(ring===0?.425:.315):(ring===0?.425:.355));
      const ry=stageHeight*(mobile?(ring===0?.412:.310):(ring===0?.385:.325));
      const angle0=-Math.PI/2+(ring===0?Math.floor(index/2)*TWO_PI/9:Math.floor(index/2)*TWO_PI/8+Math.PI/8);
      const tilt=mobile?0:(ring===0?-3:4);
      path.setAttribute('cx',stageWidth/2);path.setAttribute('cy',stageHeight/2);
      path.setAttribute('rx',rx);path.setAttribute('ry',ry);
      path.setAttribute('transform',`rotate(${tilt} ${stageWidth/2} ${stageHeight/2})`);
      path.style.opacity=index<2?'.42':'0';
      return {rx,ry,angle0,tilt};
    });
    paint();
  }
  function paint(){
    const w=stageWidth,h=stageHeight,mobile=w<550;
    if(!w||!h)return;
    satellitesList.forEach(({a,index})=>{
      const {rx,ry,angle0}=geometries[index];
      const direction=index%2===0?1:-1;
      const angle=angle0+direction*elapsed*.000036;
      const x=w/2+rx*Math.cos(angle),y=h/2+ry*Math.sin(angle);
      const depth=(1+Math.sin(angle))/2;
      const scale=(mobile?.90:.88)+depth*(mobile?.07:.14);
      a.style.transform=`translate3d(${x.toFixed(1)}px,${y.toFixed(1)}px,0) translate(-50%,-50%) scale(${scale.toFixed(3)})`;
      a.style.zIndex=String(depth>.4?12:5);
      a.style.opacity=String(.89+.11*depth);
    });
  }
  function canAnimate(){
    return !userPaused&&!pausedOnCard&&!pausedOnFocus&&!inDetail&&!document.hidden&&stageVisible;
  }
  function stopLoop(){
    if(raf)cancelAnimationFrame(raf);
    raf=0;lastStamp=0;
  }
  function startLoop(){
    if(!raf&&canAnimate()){
      lastStamp=0;
      raf=requestAnimationFrame(loop);
    }
  }
  function loop(stamp){
    raf=0;
    if(!canAnimate()){lastStamp=0;return}
    const dt=lastStamp?Math.min(55,stamp-lastStamp):0;
    lastStamp=stamp;
    elapsed+=dt;
    if(stamp-lastPaint>(stageWidth<600?48:34)){paint();lastPaint=stamp}
    raf=requestAnimationFrame(loop);
  }
  function goToCard(carousel,next,behavior='smooth'){
    carousel.index=(next+carousel.cards.length)%carousel.cards.length;
    const target=carousel.cards[carousel.index],track=carousel.track;
    const delta=target.getBoundingClientRect().left-track.getBoundingClientRect().left-(track.clientWidth-target.clientWidth)/2;
    track.scrollBy({left:delta,behavior:reducedMotion.matches?'instant':behavior});
    carousel.cards.forEach((card,i)=>card.classList.toggle('is-featured',i===carousel.index));
    carousel.due=performance.now()+5600+carousel.index*16;
  }
  function buildShelf(row,i){
    const section=el('section',{className:'orbit-shelf',id:row.target,tabindex:'-1','aria-labelledby':'heading-'+row.target});
    const description=el('div',{className:'shelf-explanation'});
    const label=el('div',{className:'shelf-heading-line'});
    label.append(el('h3',{id:'heading-'+row.target},row.title));
    description.append(label,el('p',{},row.description));
    const band=el('div',{className:'shelf-band'});
    band.append(el('span',{className:'band-satellite','aria-hidden':'true'}),el('span',{className:'band-satellite band-satellite-right','aria-hidden':'true'}));
    const prev=el('button',{className:'arrow-btn',type:'button','aria-label':`کارت پیشین از سطر ${row.title}`},'❯');
    const next=el('button',{className:'arrow-btn',type:'button','aria-label':`کارت بعدی از سطر ${row.title}`},'❮');
    const track=el('div',{className:'card-track',role:'group','aria-label':`موضوعات مرتبط با ${row.title}`});
    const items=[];
    band.append(prev,track,next);section.append(description,band);shelves.append(section);
    // Defer 20 images and 20 card nodes until this carousel approaches the viewport.
    // All topic definitions and their URLs remain available in the full content manifest.
    const state={track,cards:items,index:0,visible:false,interacting:false,due:performance.now()+5400+i*470,ensureCards:null};
    state.ensureCards=()=>{
      if(items.length||state.pending)return;
      state.pending=true;
      // Fetch only the 20 image assets for the carousel approaching the viewport.
      const filename=`./images-${String(i+1).padStart(2,'0')}.json`;
      fetch(filename,{cache:'force-cache'})
        .then(response=>{if(!response.ok)throw Error('Image gallery not found');return response.json()})
        .then(images=>{
          if(!Array.isArray(images)||images.length!==row.cards.length)throw Error('Gallery length mismatch');
          const fragment=document.createDocumentFragment();
          row.cards.forEach((topic,j)=>{
            const dest=i===16?`#news/${encodeURIComponent(topic.slug)}`:`#topic/${encodeURIComponent(row.slug)}/${encodeURIComponent(topic.slug)}`;
            const a=el('a',{className:'topic-card',href:dest});
            const visual=el('img',{className:'topic-image',src:images[j],alt:`تصویرسازی اختصاصی ${topic.title}`,loading:i===0&&j<3?'eager':'lazy',decoding:'async',width:560,height:320});
            a.append(visual,el('span',{className:'topic-name'},topic.title));
            if(i===16)a.setAttribute('title','موضوع خبری؛ خبر منتشرشده هنوز متصل نیست');
            fragment.append(a);items.push(a);
          });
          track.append(fragment);items[0]?.classList.add('is-featured');
        })
        .catch(error=>{
          console.warn('Gallery loading failed:',row.title,error);
          track.append(el('p',{className:'gallery-unavailable'},'نمایش تصاویر این بخش موقتاً در دسترس نیست. برای تلاش مجدد صفحه را بارگذاری کنید.'));
        })
        .finally(()=>{state.pending=false});
    };
    carousels.push(state);
    prev.addEventListener('click',()=>goToCard(state,state.index-1));
    next.addEventListener('click',()=>goToCard(state,state.index+1));
    track.addEventListener('pointerenter',()=>state.interacting=true);
    track.addEventListener('pointerleave',()=>{state.interacting=false;state.due=performance.now()+4500});
    track.addEventListener('focusin',()=>state.interacting=true);
    track.addEventListener('focusout',event=>{if(!track.contains(event.relatedTarget)){state.interacting=false;state.due=performance.now()+4500}});
    track.addEventListener('scroll',()=>{
      // a user's swipe interrupts auto-step temporarily
      if(!track.matches(':hover')&&!track.contains(document.activeElement))return;
      state.due=performance.now()+5600;
    },{passive:true});
    return section;
  }
  function showHome(){
    inDetail=false;$('main-view').hidden=false;$('detail-view').hidden=true;startLoop();
  }
  function showDetail(row,topic){
    inDetail=true;stopLoop();$('main-view').hidden=true;$('detail-view').hidden=false;
    $('detail-family').textContent=row.title;
    $('detail-title').textContent=topic.title;
    $('detail-intro').textContent=row.index===17
      ? `اخبار و اطلاعیه‌های رسمی مرتبط با «${topic.title}» در بخش اخبار شرکت منتشر می‌شوند.`
      : `«${topic.title}» از موضوعات حوزه «${row.title}» است. ${row.description}`;
    $('back-orbit').href='#'+row.target;
    const related=$('detail-related');related.replaceChildren();
    row.cards.filter(t=>t.slug!==topic.slug).slice(0,8).forEach(t=>{
      related.append(el('a',{href:row.index===17?`#news/${encodeURIComponent(t.slug)}`:`#topic/${encodeURIComponent(row.slug)}/${encodeURIComponent(t.slug)}`},t.title));
    });
    window.scrollTo({top:0,behavior:'instant'});$('detail-title').focus({preventScroll:true});
  }
  function handleHash(){
    let hash;
    try{hash=decodeURIComponent(location.hash.slice(1))}catch{return showHome()}
    const parts=hash.split('/');
    if(parts[0]==='topic'&&parts.length===3){
      const row=config.rows.find(r=>r.slug===parts[1]&&r.index<17),topic=row?.cards.find(c=>c.slug===parts[2]);
      if(topic)return showDetail(row,topic);
    }
    if(parts[0]==='news'&&parts.length===2){
      const row=config.rows[16],topic=row.cards.find(c=>c.slug===parts[1]);
      if(topic)return showDetail(row,topic);
    }
    showHome();
    if(/^orbit-\d{2}$/.test(hash)&&$(hash)){
      document.querySelectorAll('.orbit-shelf.is-highlighted').forEach(s=>s.classList.remove('is-highlighted'));
      const dest=$(hash);dest.classList.add('is-highlighted');
      requestAnimationFrame(()=>{dest.scrollIntoView({block:'start',behavior:reducedMotion.matches?'instant':'smooth'});dest.focus({preventScroll:true})});
    }else if(hash==='home')requestAnimationFrame(()=>window.scrollTo({top:0,behavior:'smooth'}));
  }
  function updateMotion(){
    toggle.setAttribute('aria-pressed',String(userPaused));
    toggle.setAttribute('aria-label',userPaused?'ادامه حرکت کارت‌ها و سطرها':'توقف حرکت کارت‌ها و سطرها');
    toggle.textContent=userPaused?'▶':'Ⅱ';
    if(userPaused){document.documentElement.classList.add('motion-paused');stopLoop();}
    else {document.documentElement.classList.remove('motion-paused');startLoop();}
  }
  drawSatellites();
  const nodes=[];
  const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{
    const i=nodes.indexOf(entry.target);
    if(i<0)return;
    const carousel=carousels[i];
    carousel.visible=entry.isIntersecting;
    if(entry.isIntersecting)carousel.ensureCards();
  }),{rootMargin:'320px 0px'});
  // Build the 17 semantic sections first. Render individual card images only as needed.
  function mountNextShelf(){
    const i=nodes.length;
    if(i>=config.rows.length)return;
    const node=buildShelf(config.rows[i],i);
    nodes.push(node);
    observer.observe(node);
    if(i+1<config.rows.length)setTimeout(mountNextShelf,12);
    if(i+1===config.rows.length&&location.hash)handleHash();
  }
  mountNextShelf();
  const carouselTicker=setInterval(()=>{
    if(userPaused||inDetail||document.hidden||reducedMotion.matches)return;
    const now=performance.now();
    carousels.forEach(c=>{if(c.visible&&c.cards.length&&!c.interacting&&c.due<now)goToCard(c,c.index+1)});
  },450);
  toggle.addEventListener('click',()=>{userPaused=!userPaused;updateMotion();paint()});
  reducedMotion.addEventListener('change',e=>{userPaused=e.matches;updateMotion();paint()});
  addEventListener('hashchange',handleHash);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stopLoop();else startLoop()});
  const geometryObserver=new ResizeObserver(()=>updateGeometry());geometryObserver.observe(stage);
  addEventListener('pagehide',()=>{cancelAnimationFrame(raf);clearInterval(carouselTicker);observer.disconnect();stageObserver.disconnect();geometryObserver.disconnect()});
  updateMotion();updateGeometry();handleHash();startLoop();
})();