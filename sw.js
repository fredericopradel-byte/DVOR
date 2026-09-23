const CACHE = 'iv-planner-v53-legacy-floating-nav-20260923';
const OWNED_CACHE_PREFIXES = ['iv-planner-', 'geiv-dvor-vor-'];
const PACKAGE_DB = 'ivplanner-package-manager-v1';
const PACKAGE_DB_VERSION = 1;
const PACKAGE_STORE = 'packages';
const PACKAGE_CACHE_PREFIX = 'ivdata-package-';
const packageControllers = new Map();

// Todas as telas e dados locais necessários às funções primárias do app.
// As duas formas de cada rota (diretório e index.html) são mantidas para
// garantir a abertura offline tanto pelos menus quanto pela tela inicial.
const APP_SHELL = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './global-nav.css',
  './global-nav.js',
  './page-ui.css',
  './page-ui.js',

  './prevoo/',
  './prevoo/index.html',
  './prevoo/legacy.html',
  './prevoo/legacy-data.js',
  './prevoo/legacy-afm-performance.js',
  './prevoo/hawker.html',
  './prevoo/hawker-data.js',

  './inspecao/',
  './inspecao/index.html',
  './inspecao/dvor-vor/',
  './inspecao/dvor-vor/index.html',
  './inspecao/dvor-vor/manifest.webmanifest',
  './inspecao/dvor-vor/icon-192.png',
  './inspecao/dvor-vor/icon-512.png',
  './inspecao/dvor-vor/icon-source.svg',
  './inspecao/papi.html',
  './inspecao/legacy-map.png',
  './inspecao/ils.html',
  './inspecao/radar.html',
  './inspecao/par.html',

  './localidades/',
  './localidades/index.html',
  './localidades/aerodromos.html',
  './localidades/auxilios.html',
  './meteorologia/',
  './meteorologia/index.html',
  './configuracoes/',
  './configuracoes/index.html',
  './configuracoes/backup.js',
  './configuracoes/bases.html',
  './configuracoes/database-registry.js',
  './configuracoes/package-manager.js',
  './data/package-catalog.json',
  './data/aixm/core.js',
  './data/aixm/aerodromes.js',
  './data/aixm/vor.js',
  './data/aixm/dme.js',
  './data/aixm/ndb.js',
  './data/aixm/papi.js',
  './data/aixm/ils.js',
  './data/aixm-client.js',
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

function openPackageDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(PACKAGE_DB, PACKAGE_DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(PACKAGE_STORE)) db.createObjectStore(PACKAGE_STORE, { keyPath: 'id' });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error('Falha ao abrir a base de pacotes.'));
  });
}

async function readPackage(id) {
  const db = await openPackageDb();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(PACKAGE_STORE, 'readonly');
    const request = transaction.objectStore(PACKAGE_STORE).get(id);
    request.onsuccess = () => resolve(request.result || null);
    request.onerror = () => reject(request.error);
    transaction.oncomplete = () => db.close();
  });
}

async function readPackages() {
  const db = await openPackageDb();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(PACKAGE_STORE, 'readonly');
    const request = transaction.objectStore(PACKAGE_STORE).getAll();
    request.onsuccess = () => resolve(request.result || []);
    request.onerror = () => reject(request.error);
    transaction.oncomplete = () => db.close();
  });
}

async function writePackage(record) {
  const db = await openPackageDb();
  await new Promise((resolve, reject) => {
    const transaction = db.transaction(PACKAGE_STORE, 'readwrite');
    transaction.objectStore(PACKAGE_STORE).put(record);
    transaction.oncomplete = resolve;
    transaction.onerror = () => reject(transaction.error);
  });
  db.close();
  return record;
}

async function broadcastPackage(record) {
  const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
  clients.forEach(client => client.postMessage({ type: 'PACKAGE_STATUS', record }));
}

async function broadcastPackageStates() {
  const records = await readPackages().catch(() => []);
  for (const record of records) {
    if (record.status === 'downloading' && !packageControllers.has(record.id)) {
      record.status = 'paused';
      record.downloadedBytes = Number(record.completedBytes) || 0;
      record.updatedAt = new Date().toISOString();
      await writePackage(record);
    }
    await broadcastPackage(record);
  }
}

function safeSegment(value) {
  return String(value || '').replace(/[^a-zA-Z0-9._-]/g, '-').slice(0, 100);
}

function validatePackage(pkg) {
  if (!pkg || typeof pkg !== 'object' || !pkg.connected) throw new Error('Pacote não conectado.');
  if (!/^[a-z0-9-]+$/.test(pkg.id || '') || typeof pkg.version !== 'string' || !Array.isArray(pkg.files) || !pkg.files.length) throw new Error('Manifesto do pacote inválido.');
  const scope = new URL(self.registration.scope);
  pkg.files.forEach(file => {
    const source = new URL(file.url, scope);
    const target = new URL(file.target, scope);
    if (source.origin !== scope.origin || target.origin !== scope.origin || !target.pathname.startsWith(scope.pathname)) throw new Error('O pacote contém caminho fora do aplicativo.');
    if (!/^[a-f0-9]{64}$/.test(file.sha256 || '') || !Number.isFinite(file.size) || file.size < 1) throw new Error('Arquivo sem tamanho ou hash válido.');
  });
}

function bytesToHex(buffer) {
  return Array.from(new Uint8Array(buffer), byte => byte.toString(16).padStart(2, '0')).join('');
}

async function downloadResponse(url, controller, onProgress) {
  const response = await fetch(url, { cache: 'no-store', signal: controller.signal });
  if (!response.ok) throw new Error(`Falha HTTP ${response.status} em ${url.pathname}.`);
  if (!response.body || !response.body.getReader) {
    const buffer = await response.arrayBuffer();
    onProgress(buffer.byteLength);
    return { buffer, type: response.headers.get('content-type') || 'application/octet-stream' };
  }
  const reader = response.body.getReader();
  const chunks = [];
  let length = 0;
  while (true) {
    const part = await reader.read();
    if (part.done) break;
    chunks.push(part.value);
    length += part.value.byteLength;
    onProgress(length);
  }
  const combined = new Uint8Array(length);
  let offset = 0;
  chunks.forEach(chunk => {
    combined.set(chunk, offset);
    offset += chunk.byteLength;
  });
  return { buffer: combined.buffer, type: response.headers.get('content-type') || 'application/octet-stream' };
}

async function startPackageDownload(pkg) {
  validatePackage(pkg);
  if (packageControllers.has(pkg.id)) return;
  const controller = new AbortController();
  packageControllers.set(pkg.id, controller);
  const scope = new URL(self.registration.scope);
  const cacheName = `${PACKAGE_CACHE_PREFIX}${safeSegment(pkg.id)}-${safeSegment(pkg.version)}`;
  const previous = await readPackage(pkg.id).catch(() => null);
  const canResume = previous && previous.pendingVersion === pkg.version && previous.pendingCache === cacheName;
  const completedTargets = canResume && Array.isArray(previous.completedTargets) ? previous.completedTargets : [];
  let completedBytes = canResume ? Number(previous.completedBytes) || 0 : 0;
  if (!canResume) await caches.delete(cacheName);
  const cache = await caches.open(cacheName);
  let lastBroadcast = 0;
  let record = {
    id: pkg.id,
    title: pkg.title,
    installedVersion: previous && previous.installedVersion || pkg.bundledVersion || null,
    activeCache: previous && previous.activeCache || null,
    targets: previous && Array.isArray(previous.targets) ? previous.targets : [],
    status: 'downloading',
    pendingVersion: pkg.version,
    pendingCache: cacheName,
    totalBytes: Number(pkg.size) || pkg.files.reduce((sum, file) => sum + file.size, 0),
    downloadedBytes: completedBytes,
    completedBytes,
    completedTargets: [...completedTargets],
    error: '',
    updatedAt: new Date().toISOString()
  };
  await writePackage(record);
  await broadcastPackage(record);

  try {
    for (const file of pkg.files) {
      if (record.completedTargets.includes(file.target)) continue;
      const sourceUrl = new URL(file.url, scope);
      const targetUrl = new URL(file.target, scope);
      const downloaded = await downloadResponse(sourceUrl, controller, length => {
        record.downloadedBytes = completedBytes + length;
        const now = Date.now();
        if (now - lastBroadcast > 250) {
          lastBroadcast = now;
          broadcastPackage({ ...record });
        }
      });
      if (downloaded.buffer.byteLength !== file.size) throw new Error(`Tamanho divergente em ${file.target}.`);
      const hash = bytesToHex(await crypto.subtle.digest('SHA-256', downloaded.buffer));
      if (hash !== file.sha256) throw new Error(`Falha de integridade em ${file.target}.`);
      await cache.put(targetUrl.href, new Response(downloaded.buffer, { headers: { 'Content-Type': downloaded.type, 'X-IV-Planner-Package': pkg.id, 'X-IV-Planner-Version': pkg.version } }));
      completedBytes += downloaded.buffer.byteLength;
      record.completedBytes = completedBytes;
      record.downloadedBytes = completedBytes;
      record.completedTargets.push(file.target);
      record.updatedAt = new Date().toISOString();
      await writePackage(record);
      await broadcastPackage(record);
    }

    record = {
      id: pkg.id,
      title: pkg.title,
      installedVersion: pkg.version,
      status: 'installed',
      activeCache: cacheName,
      targets: pkg.files.map(file => file.target),
      totalBytes: record.totalBytes,
      downloadedBytes: record.totalBytes,
      installedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      error: ''
    };
    await writePackage(record);
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key.startsWith(`${PACKAGE_CACHE_PREFIX}${safeSegment(pkg.id)}-`) && key !== cacheName).map(key => caches.delete(key)));
    await broadcastPackage(record);
  } catch (error) {
    const paused = error && error.name === 'AbortError';
    record.status = paused ? 'paused' : 'error';
    record.downloadedBytes = completedBytes;
    record.error = paused ? '' : (error.message || 'Falha ao baixar o pacote.');
    record.updatedAt = new Date().toISOString();
    await writePackage(record);
    await broadcastPackage(record);
  } finally {
    packageControllers.delete(pkg.id);
  }
}

async function matchManagedPackage(request, url) {
  const relative = url.pathname.slice(new URL(self.registration.scope).pathname.length);
  const managed = relative === 'prevoo/legacy-data.js' || relative === 'adc-runway-data.js' || relative.startsWith('publicacoes-offline/');
  if (!managed) return null;
  const packages = await readPackages().catch(() => []);
  const scope = new URL(self.registration.scope);
  for (const record of packages) {
    if (!record.activeCache || !Array.isArray(record.targets)) continue;
    const target = record.targets.find(item => new URL(item, scope).pathname === url.pathname);
    if (!target) continue;
    const hit = await caches.open(record.activeCache).then(cache => cache.match(new URL(target, scope).href, { ignoreSearch: true }));
    if (hit) return hit;
  }
  return null;
}

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const request = event.request;
  const url = new URL(request.url);

  // Não interfere em METAR, radar, mapas ou qualquer outro serviço externo.
  if (url.origin !== self.location.origin) return;

  // O catálogo é rede-primeiro para detectar versões novas, com fallback
  // para a cópia local quando o aparelho estiver offline.
  if (url.pathname.endsWith('/data/package-catalog.json')) {
    const network = fetch(request, { cache: 'no-store' }).then(async response => {
      if (response && response.ok) {
        const cache = await caches.open(CACHE);
        await cache.put(request, response.clone());
      }
      return response;
    });
    event.respondWith(network.catch(() => caches.match(request, { ignoreSearch: true })));
    return;
  }

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
    matchManagedPackage(request, url).then(packageHit => {
      if (packageHit) return packageHit;
      return caches.match(request, { ignoreSearch: true }).then(cached => cached || network.catch(() => cached));
    })
  );
});

self.addEventListener('message', event => {
  if (event.data === 'SKIP_WAITING') {
    self.skipWaiting();
    return;
  }
  if (!event.data || typeof event.data !== 'object') return;
  if (event.data.type === 'PACKAGE_DOWNLOAD') event.waitUntil(startPackageDownload(event.data.package));
  if (event.data.type === 'PACKAGE_STATUS_REQUEST') event.waitUntil(broadcastPackageStates());
  if (event.data.type === 'PACKAGE_PAUSE') {
    const controller = packageControllers.get(event.data.packageId);
    if (controller) controller.abort();
  }
});
