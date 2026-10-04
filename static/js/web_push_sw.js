'use strict';

function internalPath(value) {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) return '/notifications/';
  try {
    let decoded = value;
    for (let count = 0; count < 3; count += 1) decoded = decodeURIComponent(decoded);
    if (decoded.startsWith('//') || /[\\\u0000-\u001f]/.test(decoded)) return '/notifications/';
    const url = new URL(value, self.location.origin);
    return url.origin === self.location.origin && !url.search && !url.hash ? url.pathname : '/notifications/';
  } catch (_) {
    return '/notifications/';
  }
}

self.addEventListener('push', function (event) {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (_) { /* แสดงข้อความทั่วไปแทน */ }
  if (!data || typeof data !== 'object') data = {};
  const title = typeof data.title === 'string' ? data.title.slice(0, 100) : 'SIGROOM';
  const body = typeof data.body === 'string' ? data.body.slice(0, 300) : 'มีการแจ้งเตือนใหม่ใน SIGROOM';
  event.waitUntil(self.registration.showNotification(title, {body: body, data: {url: internalPath(data.url)}}));
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  const path = internalPath(event.notification.data && event.notification.data.url);
  const target = new URL(path, self.location.origin).href;
  event.waitUntil(self.clients.matchAll({type: 'window', includeUncontrolled: true}).then(async function (windows) {
    const existing = windows.find(function (client) { return client.url === target; });
    if (existing) return existing.focus();
    return self.clients.openWindow(target);
  }));
});
