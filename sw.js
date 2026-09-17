const CACHE = 'iv-planner-v16-papi-tabs-fix-20260917';
const OWNED_CACHE_PREFIXES = ['iv-planner-', 'geiv-dvor-vor-'];

// Todas as telas e dados locais necessários às funções primárias do app.
// As duas formas de cada rota (diretório e index.html) são mantidas para
// garantir a abertura offline tanto pelos menus quanto pela tela inicial.
const APP_SHELL = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',

  './prevoo/',
  './prevoo/index.html',
  './prevoo/legacy.html',
  './prevoo/legacy-data.js',
  './prevoo/hawker.html',

  './inspecao/',
  './inspecao/index.html',
  './inspecao/dvor-vor/',
  './inspecao/dvor-vor/index.html',
  './inspecao/dvor-vor/manifest.webmanifest',
  './inspecao/dvor-vor/icon-192.png',
  './inspecao/dvor-vor/icon-512.png',
  './inspecao/dvor-vor/icon-source.svg',
  './inspecao/papi.html',
  './inspecao/ils.html',
  './inspecao/radar.html',
  './inspecao/par.html',

  './localidades/',
  './localidades/index.html',
  './meteorologia/',
  './meteorologia/index.html',
  './modulo-em-breve.html',

  './wmm2025.js',
  './adc-runway-data.js',
  './WMM2025-LICENSE.txt'
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
          .filter(key =>
            key !== CACHE &&
            OWNED_CACHE_PREFIXES.some(prefix => key.startsWith(prefix))
          )
          .map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

function cachedNavigation(request) {
  const url = new URL(request.url);
  const scope = new URL(self.registration.scope);
  const relative = url.pathname.startsWith(scope.pathname)
    ? url.pathname.slice(scope.pathname.length)
    : '';
  const canonical = relative.endsWith('/')
    ? new URL(`${relative}index.html`, scope)
    : new URL(relative || 'index.html', scope);

  return caches.match(request, { ignoreSearch: true })
    .then(hit => hit || caches.match(canonical.href, { ignoreSearch: true }))
    .then(hit => hit || caches.match('./index.html'));
}

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const request = event.request;
  const url = new URL(request.url);

  // Não interfere em METAR, radar, mapas ou qualquer outro serviço externo.
  if (url.origin !== self.location.origin) return;

  // HTML: tenta atualizar quando há rede e usa a cópia local quando não há.
  if (request.mode === 'navigate' || url.pathname.endsWith('/index.html')) {
    const network = fetch(request, { cache: 'no-store' })
      .then(async response => {
        if (response && response.ok) {
          const cache = await caches.open(CACHE);
          await cache.put(request, response.clone());
        }
        return response;
      });

    event.respondWith(
      network.catch(() => cachedNavigation(request))
    );
    return;
  }

  // Arquivos locais: cache primeiro. ignoreSearch permite que os arquivos
  // versionados por ?v= continuem disponíveis no modo avião.
  const network = fetch(request)
    .then(async response => {
      if (response && response.ok) {
        const cache = await caches.open(CACHE);
        await cache.put(request, response.clone());
      }
      return response;
    });
  event.waitUntil(network.catch(() => undefined));

  event.respondWith(
    caches.match(request, { ignoreSearch: true }).then(cached => {
      return cached || network.catch(() => cached);
    })
  );
});

self.addEventListener('message', event => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});
