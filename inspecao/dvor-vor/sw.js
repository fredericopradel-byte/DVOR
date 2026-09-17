// Worker de transição: aposenta instalações antigas do DVOR sem apagar o
// cache principal do IV-PLANNER. Novas instalações usam somente /sw.js.
self.addEventListener('install', event => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys
          .filter(key => key.startsWith('geiv-dvor-vor-'))
          .map(key => caches.delete(key))
      ))
      .then(() => self.registration.unregister())
  );
});
