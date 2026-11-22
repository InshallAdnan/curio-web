/* Curio service worker — phone reminders. The push itself is empty; we ask Curio what to show. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('push', (e) => {
  e.waitUntil((async () => {
    let items = [];
    try {
      const r = await fetch('/api/tracker/inbox', { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-Curio': '1' }, body: '{}' });
      const j = await r.json(); items = (j && j.data) || [];
    } catch (err) { /* offline or signed out */ }
    if (!items.length) items = [{ title: 'Curio', body: 'You have a reminder — open Tracker.', tag: 'curio', url: '/#/tracker' }];
    for (const it of items.slice(0, 3)) {
      await self.registration.showNotification(it.title || 'Curio', { body: it.body || '', tag: (it.tag || 'curio') + ':' + (it.id || ''), icon: '/icon.svg', badge: '/icon.svg', data: { url: it.url || '/#/tracker' } });
    }
  })());
});
self.addEventListener('notificationclick', (e) => {
  e.notification.close(); const url = (e.notification.data && e.notification.data.url) || '/#/tracker';
  e.waitUntil((async () => {
    const all = await clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const c of all) { if ('focus' in c) { c.navigate(url).catch(() => {}); return c.focus(); } }
    return clients.openWindow(url);
  })());
});
