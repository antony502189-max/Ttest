self.addEventListener('push', (event) => {
  let message = { title: '112233.es', body: '', url: '/#/publicidad/nueva' }
  try { if (event.data) message = { ...message, ...event.data.json() } } catch { /* Display the fallback. */ }
  event.waitUntil(self.registration.showNotification(message.title, {
    body: message.body, tag: 'advertising-slot-available', data: { url: message.url },
  }))
})
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const target = new URL(event.notification.data?.url || '/#/publicidad/nueva', self.location.origin)
  if (target.origin !== self.location.origin) return
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(async (windows) => {
    const window = windows.find((client) => new URL(client.url).origin === target.origin)
    if (window) { await window.navigate(target.href); return window.focus() }
    return self.clients.openWindow(target.href)
  }))
})
