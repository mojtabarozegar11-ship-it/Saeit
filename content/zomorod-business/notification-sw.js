/* Zomorod Melal approval notification worker. No network mutation is performed here. */
self.addEventListener('install', event => { self.skipWaiting(); });
self.addEventListener('activate', event => { event.waitUntil(self.clients.claim()); });
self.addEventListener('notificationclick', event => {
  const action = event.action || 'open';
  const target = (event.notification && event.notification.data && event.notification.data.url) || '/staff/command-center/integrated/';
  event.notification.close();
  event.waitUntil((async () => {
    const list = await self.clients.matchAll({type:'window', includeUncontrolled:true});
    for (const client of list) {
      if ('focus' in client) {
        await client.focus();
        if (action !== 'open' && 'postMessage' in client) client.postMessage({type:'zm-approval-action', action});
        return;
      }
    }
    if (self.clients.openWindow) await self.clients.openWindow(target);
  })());
});
