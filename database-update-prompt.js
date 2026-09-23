(function () {
  'use strict';

  const overlay = document.getElementById('db-update-overlay');
  const dialog = document.getElementById('db-update-dialog');
  const yes = document.getElementById('db-update-yes');
  const no = document.getElementById('db-update-no');
  const download = document.getElementById('db-update-download');
  const progress = document.getElementById('db-update-progress');
  const fill = document.getElementById('db-update-fill');
  const status = document.getElementById('db-update-status');
  const current = document.getElementById('db-update-current');
  const menu = document.querySelector('main');
  const DB_NAME = 'ivplanner-package-manager-v1';
  let pending = [];
  let registration = null;
  let running = false;
  let previousFocus = null;

  function records() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, 1);
      request.onupgradeneeded = () => {
        if (!request.result.objectStoreNames.contains('packages')) request.result.createObjectStore('packages', { keyPath: 'id' });
      };
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        const db = request.result;
        const transaction = db.transaction('packages', 'readonly');
        const all = transaction.objectStore('packages').getAll();
        all.onsuccess = () => resolve(all.result || []);
        all.onerror = () => reject(all.error);
        transaction.oncomplete = () => db.close();
      };
    });
  }

  function close() {
    overlay.hidden = true;
    menu.inert = false;
    previousFocus?.focus();
  }

  function open(packages) {
    pending = packages;
    document.getElementById('db-update-list').replaceChildren(...packages.map(pkg => {
      const item = document.createElement('li');
      item.textContent = pkg.title;
      return item;
    }));
    previousFocus = document.activeElement;
    overlay.hidden = false;
    menu.inert = true;
    yes.focus();
  }

  function showProgress(record) {
    const total = Number(record.totalBytes) || Number(pending[0]?.size) || 0;
    const amount = Math.max(0, Math.min(total, Number(record.downloadedBytes) || 0));
    const percent = total ? Math.round(amount / total * 100) : 0;
    fill.style.width = `${percent}%`;
    progress.setAttribute('aria-valuenow', String(percent));
    status.textContent = `${percent}%${total ? ` · ${(amount / 1048576).toFixed(1)} de ${(total / 1048576).toFixed(1)} MB` : ''}`;
  }

  async function next() {
    if (!pending.length) {
      running = false;
      close();
      return;
    }
    const pkg = pending[0];
    current.textContent = `Baixando ${pkg.title}`;
    fill.style.width = '0%';
    progress.setAttribute('aria-valuenow', '0');
    status.textContent = 'Iniciando download…';
    try {
      if (navigator.storage?.persist) await navigator.storage.persist().catch(() => false);
      const worker = registration.active || registration.waiting || registration.installing;
      if (!worker) throw new Error('Gerenciador de downloads indisponível.');
      worker.postMessage({ type: 'PACKAGE_DOWNLOAD', package: pkg });
    } catch (error) {
      fail(error.message || 'Não foi possível iniciar o download.');
    }
  }

  function fail(message) {
    running = false;
    current.textContent = 'Download interrompido';
    status.textContent = `${message} Você pode tentar novamente ou acessar Configurações > Base de dados.`;
    no.disabled = false;
    no.textContent = 'Fechar';
    yes.hidden = false;
    yes.disabled = false;
    yes.textContent = 'Tentar novamente';
    yes.focus();
  }

  yes.addEventListener('click', async () => {
    if (running || !pending.length) return;
    running = true;
    yes.hidden = true;
    no.disabled = true;
    download.hidden = false;
    dialog.focus();
    try {
      registration = await navigator.serviceWorker.register('./sw.js', { scope: './', updateViaCache: 'none' });
      await navigator.serviceWorker.ready;
      await next();
    } catch (error) {
      fail(error.message || 'Não foi possível iniciar o download.');
    }
  });

  no.addEventListener('click', () => { if (!running) close(); });
  document.addEventListener('keydown', event => {
    if (overlay.hidden) return;
    if (event.key !== 'Tab') return;
    const buttons = [no, yes].filter(button => !button.hidden && !button.disabled);
    if (!buttons.length) { event.preventDefault(); dialog.focus(); return; }
    const index = buttons.indexOf(document.activeElement);
    if (event.shiftKey && index <= 0) { event.preventDefault(); buttons[buttons.length - 1].focus(); }
    else if (!event.shiftKey && index === buttons.length - 1) { event.preventDefault(); buttons[0].focus(); }
  });

  navigator.serviceWorker?.addEventListener('message', event => {
    if (!running || event.data?.type !== 'PACKAGE_STATUS' || event.data.record?.id !== pending[0]?.id) return;
    const record = event.data.record;
    showProgress(record);
    if (record.status === 'installed' && record.installedVersion === pending[0].version) {
      pending.shift();
      next();
    } else if (record.status === 'error' || record.status === 'paused') {
      fail(record.error || 'Download pausado.');
    }
  });

  async function check() {
    if (!navigator.onLine || !('serviceWorker' in navigator) || !('indexedDB' in window)) return;
    try {
      const response = await fetch(`./data/package-catalog.json?t=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) return;
      const catalog = await response.json();
      if (catalog.schemaVersion !== 1 || !Array.isArray(catalog.packages)) return;
      const installed = new Map((await records()).map(record => [record.id, record]));
      const cachedPackages = new Set(await caches.keys());
      const updates = catalog.packages.filter(pkg => {
        if (!pkg.connected || !pkg.version || !Array.isArray(pkg.files) || !pkg.files.length) return false;
        const record = installed.get(pkg.id);
        const version = record?.installedVersion || pkg.bundledVersion || null;
        return version !== pkg.version || Boolean(record?.activeCache && !cachedPackages.has(record.activeCache));
      });
      if (updates.length) open(updates);
    } catch (_) {
      // Sem rede ou armazenamento, o menu continua utilizável.
    }
  }

  window.addEventListener('load', check, { once: true });
})();
