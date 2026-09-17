(function () {
  'use strict';

  const DB_NAME = 'ivplanner-package-manager-v1';
  const DB_VERSION = 1;
  const PACKAGE_STORE = 'packages';
  const CATALOG_URL = '../data/package-catalog.json';
  const state = { catalog: [], records: new Map(), registration: null, loading: false };

  function openDb() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(PACKAGE_STORE)) db.createObjectStore(PACKAGE_STORE, { keyPath: 'id' });
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error('Não foi possível abrir o armazenamento de pacotes.'));
    });
  }

  async function readRecords() {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(PACKAGE_STORE, 'readonly');
      const request = transaction.objectStore(PACKAGE_STORE).getAll();
      request.onsuccess = () => resolve(request.result || []);
      request.onerror = () => reject(request.error);
      transaction.oncomplete = () => db.close();
    });
  }

  async function loadCatalog() {
    const response = await fetch(`${CATALOG_URL}?t=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`Catálogo indisponível (${response.status}).`);
    const catalog = await response.json();
    if (catalog.schemaVersion !== 1 || !Array.isArray(catalog.packages)) throw new Error('Formato do catálogo não reconhecido.');
    state.catalog = catalog.packages;
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character]);
  }

  function formatBytes(value) {
    const bytes = Number(value) || 0;
    if (!bytes) return 'Tamanho não informado';
    if (bytes < 1024) return `${bytes} B`;
    const units = ['KB', 'MB', 'GB'];
    let amount = bytes / 1024;
    let unit = units[0];
    for (let index = 1; index < units.length && amount >= 1024; index += 1) {
      amount /= 1024;
      unit = units[index];
    }
    return `${amount >= 100 ? amount.toFixed(0) : amount.toFixed(1)} ${unit}`;
  }

  function formatDate(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value || '');
    return match ? `${match[3]}/${match[2]}/${match[1]}` : (value || 'Não informada');
  }

  function packageView(pkg) {
    const record = state.records.get(pkg.id) || {};
    const installedVersion = record.installedVersion || pkg.bundledVersion || null;
    const status = record.status || (installedVersion ? 'installed' : 'not-installed');
    const updateAvailable = Boolean(pkg.connected && pkg.version && installedVersion && pkg.version !== installedVersion);
    const downloaded = Number(record.downloadedBytes) || 0;
    const total = Number(record.totalBytes) || Number(pkg.size) || 0;
    const progress = total ? Math.max(0, Math.min(100, Math.round((downloaded / total) * 100))) : 0;

    let badge = 'Não conectada';
    let badgeClass = 'pending';
    let button = '<button class="package-button" type="button" disabled>Fonte não conectada</button>';
    if (pkg.connected) {
      if (status === 'downloading') {
        badge = 'Baixando'; badgeClass = 'working';
        button = `<button class="package-button secondary" type="button" data-action="pause" data-package-id="${escapeHtml(pkg.id)}">Pausar</button>`;
      } else if (status === 'paused') {
        badge = 'Pausada'; badgeClass = 'pending';
        button = `<button class="package-button" type="button" data-action="download" data-package-id="${escapeHtml(pkg.id)}">Continuar</button>`;
      } else if (status === 'error') {
        badge = 'Erro'; badgeClass = 'bad';
        button = `<button class="package-button" type="button" data-action="download" data-package-id="${escapeHtml(pkg.id)}">Tentar novamente</button>`;
      } else if (updateAvailable) {
        badge = 'Atualização disponível'; badgeClass = 'pending';
        button = `<button class="package-button" type="button" data-action="download" data-package-id="${escapeHtml(pkg.id)}">Atualizar</button>`;
      } else if (installedVersion) {
        badge = 'Atualizada'; badgeClass = 'ok';
        button = '<button class="package-button secondary" type="button" disabled>Versão atual</button>';
      } else {
        badge = 'Disponível'; badgeClass = 'pending';
        button = `<button class="package-button" type="button" data-action="download" data-package-id="${escapeHtml(pkg.id)}">Baixar</button>`;
      }
    }

    const showProgress = ['downloading', 'paused', 'error'].includes(status);
    const progressHtml = showProgress ? `<div class="progress-block"><div class="progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress}"><span style="width:${progress}%"></span></div><div class="progress-copy"><span>${progress}%</span><span>${formatBytes(downloaded)} de ${formatBytes(total)}</span></div></div>` : '';
    const errorHtml = record.error ? `<p class="package-error">${escapeHtml(record.error)}</p>` : '';
    return `<article class="db-card package-card" data-package="${escapeHtml(pkg.id)}"><div class="db-top"><div class="db-copy"><h3>${escapeHtml(pkg.title)}</h3><p>${escapeHtml(pkg.description)}</p></div><span class="badge ${badgeClass}">${escapeHtml(badge)}</span></div><div class="facts"><div class="fact"><span>Instalada</span><span>${escapeHtml(installedVersion || 'Não instalada')}</span></div><div class="fact"><span>Disponível</span><span>${escapeHtml(pkg.version || 'Fonte não conectada')}</span></div><div class="fact"><span>Vigência/coleta</span><span>${escapeHtml(formatDate(pkg.effectiveDate))}</span></div><div class="fact"><span>Tamanho</span><span>${escapeHtml(formatBytes(pkg.size))}</span></div><div class="fact"><span>Fonte</span><span>${escapeHtml(pkg.source || 'Não informada')}</span></div></div>${progressHtml}${errorHtml}<div class="package-actions">${button}</div></article>`;
  }

  function render() {
    const connected = state.catalog.filter(pkg => pkg.connected);
    const planned = state.catalog.filter(pkg => !pkg.connected);
    document.getElementById('package-list').innerHTML = connected.map(packageView).join('');
    document.getElementById('planned-bases').innerHTML = planned.map(packageView).join('');
    document.querySelectorAll('[data-action]').forEach(button => button.addEventListener('click', handleAction));
  }

  async function updateStorageEstimate() {
    const label = document.getElementById('storage-status');
    if (!navigator.storage || !navigator.storage.estimate) {
      label.textContent = 'Espaço não informado';
      return;
    }
    try {
      const estimate = await navigator.storage.estimate();
      label.textContent = `${formatBytes(estimate.usage)} usados de ${formatBytes(estimate.quota)}`;
    } catch (_) {
      label.textContent = 'Espaço não informado';
    }
  }

  async function ensureRegistration() {
    if (!('serviceWorker' in navigator)) throw new Error('Service worker indisponível neste navegador.');
    state.registration = await navigator.serviceWorker.register('../sw.js', { scope: '../', updateViaCache: 'none' });
    await navigator.serviceWorker.ready;
    const worker = state.registration.active || state.registration.waiting || state.registration.installing;
    if (worker) worker.postMessage({ type: 'PACKAGE_STATUS_REQUEST' });
    return state.registration;
  }

  async function sendMessage(message) {
    const registration = state.registration || await ensureRegistration();
    const worker = registration.active || registration.waiting || registration.installing;
    if (!worker) throw new Error('Gerenciador de downloads ainda não está ativo. Reabra o aplicativo.');
    worker.postMessage(message);
  }

  async function handleAction(event) {
    const button = event.currentTarget;
    const pkg = state.catalog.find(item => item.id === button.dataset.packageId);
    if (!pkg) return;
    button.disabled = true;
    try {
      if (button.dataset.action === 'pause') {
        await sendMessage({ type: 'PACKAGE_PAUSE', packageId: pkg.id });
      } else {
        if (navigator.storage && navigator.storage.persist) await navigator.storage.persist().catch(() => false);
        await sendMessage({ type: 'PACKAGE_DOWNLOAD', package: pkg });
      }
    } catch (error) {
      window.alert(error.message || 'Não foi possível iniciar a operação.');
      button.disabled = false;
    }
  }

  async function refresh(options) {
    const button = document.getElementById('updates-button');
    const announce = options && options.announce;
    if (state.loading) return;
    state.loading = true;
    button.disabled = true;
    try {
      await Promise.all([loadCatalog(), readRecords().then(records => { state.records = new Map(records.map(record => [record.id, record])); })]);
      render();
      await updateStorageEstimate();
      if (announce) document.getElementById('catalog-status').textContent = 'Catálogo verificado agora';
    } catch (error) {
      document.getElementById('catalog-status').textContent = error.message || 'Não foi possível verificar o catálogo';
    } finally {
      state.loading = false;
      button.disabled = false;
    }
  }

  window.IV_PACKAGE_MANAGER = { refresh, formatBytes };

  document.getElementById('updates-button').addEventListener('click', () => refresh({ announce: true }));
  navigator.serviceWorker?.addEventListener('message', event => {
    if (!event.data || event.data.type !== 'PACKAGE_STATUS') return;
    const record = event.data.record;
    if (record && record.id) state.records.set(record.id, record);
    render();
    updateStorageEstimate();
  });
  ensureRegistration().catch(() => null);
  refresh();
})();
