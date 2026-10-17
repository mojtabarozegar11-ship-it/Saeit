// Tala-only offline shell. Never cache business, admin, or API responses.
const CACHE='tala-shell-v3';
const CORE=['/tala/','/tala/manifest.webmanifest','/tala/assets/tala-mark.svg'];
const SAFE_PATHS=new Set(CORE);
self.addEventListener('install',event=>{
  event.waitUntil((async()=>{
    const cache=await caches.open(CACHE);
    await cache.addAll(CORE);
    await self.skipWaiting();
  })());
});
self.addEventListener('activate',event=>{
  event.waitUntil((async()=>{
    const keys=await caches.keys();
    // Older Tala cache versions might contain private API responses.
    // Purge only Tala-owned caches: never delete caches from other sites.
    await Promise.all(keys.filter(key=>key.startsWith('tala-shell-')&&key!==CACHE).map(key=>caches.delete(key)));
    await self.clients.claim();
  })());
});
self.addEventListener('fetch',event=>{
  const request=event.request;
  if(request.method!=='GET')return;
  const url=new URL(request.url);
  if(url.origin!==self.location.origin || url.search || !SAFE_PATHS.has(url.pathname))return;
  if(request.headers.has('Authorization')||request.headers.has('X-Tala-Request'))return;
  event.respondWith((async()=>{
    try{
      const response=await fetch(request);
      if(response.ok && response.type==='basic'){
        const cache=await caches.open(CACHE);
        await cache.put(request,response.clone());
      }
      return response;
    }catch(error){
      const cached=await caches.match(request);
      if(cached)return cached;
      throw error;
    }
  })());
});
