const CACHE = 'iv-planner-v3';

const APP_SHELL = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys
          .filter(key => key !== CACHE)
          .map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const request = event.request;
  const url = new URL(request.url);

  // HTML: busca sempre a versão mais recente.
  // Se estiver offline, usa a última versão armazenada.
  if (
    request.mode === 'navigate' ||
    (url.origin === self.location.origin &&
     url.pathname.endsWith('/index.html'))
  ) {
    event.respondWith(
      fetch(request, { cache: 'no-store' })
        .then(response => {
          if (response && response.ok) {
            const copy = response.clone();
            caches.open(CACHE)
              .then(cache => cache.put('./index.html', copy));
          }
          return response;
        })
        .catch(async () => {
          return (
            (await caches.match('./index.html')) ||
            (await caches.match('./'))
          );
        })
    );

    return;
  }

  // Demais arquivos: usa cache, atualizando-o quando houver internet.
  if (url.origin === self.location.origin) {
    event.respondWith(
      caches.match(request).then(cached => {
        const network = fetch(request)
          .then(response => {
            if (response && response.ok) {
              const copy = response.clone();
              caches.open(CACHE)
                .then(cache => cache.put(request, copy));
            }

            return response;
          })
          .catch(() => cached);

        return cached || network;
      })
    );
  }
});

self.addEventListener('message', event => {
  if (event.data === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
