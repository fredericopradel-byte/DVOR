(function () {
  'use strict';

  const STATUS_KEY = 'ivplanner-database-status-v1';
  const CUSTOM_LOCALITIES_KEY = 'ivplanner-custom-localities-v1';

  function isFiniteNumber(value) {
    return typeof value === 'number' && Number.isFinite(value);
  }

  function analyzeLegacy(data) {
    const issues = [];
    if (!data || typeof data !== 'object') {
      return { ok: false, version: 'Indisponível', aerodromes: 0, runwayAerodromes: 0, runways: 0, runwayHeadings: 0, sourceCounts: {}, issues: ['Arquivo legacy-data.js não carregado.'] };
    }

    const aerodromes = Array.isArray(data.aerodromes) ? data.aerodromes : [];
    const runwayMap = data.runwayDatabase && data.runwayDatabase.runways;
    const runwayEntries = runwayMap && typeof runwayMap === 'object' ? Object.entries(runwayMap) : [];
    if (!Array.isArray(data.aerodromes)) issues.push('Lista de aeródromos ausente ou inválida.');
    if (!runwayMap || typeof runwayMap !== 'object') issues.push('Base de pistas ausente ou inválida.');

    let invalidAerodromes = 0;
    aerodromes.forEach(item => {
      if (!Array.isArray(item) || typeof item[0] !== 'string' || item[0].length !== 4 || !isFiniteNumber(item[2]) || !isFiniteNumber(item[3]) || Math.abs(item[2]) > 90 || Math.abs(item[3]) > 180) invalidAerodromes += 1;
    });

    let runways = 0;
    let invalidRunways = 0;
    let runwayHeadings = 0;
    const sourceCounts = {};
    runwayEntries.forEach(([, records]) => {
      if (!Array.isArray(records)) {
        invalidRunways += 1;
        return;
      }
      records.forEach(record => {
        runways += 1;
        const headingsPresent = Array.isArray(record) && record[1] !== null && record[3] !== null;
        if (headingsPresent) runwayHeadings += 2;
        const headingsValid = !headingsPresent || (isFiniteNumber(record[1]) && isFiniteNumber(record[3]) && record[1] >= 0 && record[1] < 360 && record[3] >= 0 && record[3] < 360);
        if (!Array.isArray(record) || typeof record[0] !== 'string' || typeof record[2] !== 'string' || !headingsValid) invalidRunways += 1;
        const source = Array.isArray(record) && typeof record[5] === 'string' ? record[5] : 'não informada';
        sourceCounts[source] = (sourceCounts[source] || 0) + 1;
      });
    });

    if (invalidAerodromes) issues.push(`${invalidAerodromes} registro(s) de aeródromo com estrutura ou coordenadas inválidas.`);
    if (invalidRunways) issues.push(`${invalidRunways} registro(s) de pista com estrutura ou rumo inválidos.`);
    return {
      ok: issues.length === 0,
      version: typeof data.version === 'string' ? data.version : 'Não informada',
      aerodromes: aerodromes.length,
      runwayAerodromes: runwayEntries.length,
      runways,
      runwayHeadings,
      sourceCounts,
      issues
    };
  }

  function analyzeAdc(data) {
    const issues = [];
    if (!data || typeof data !== 'object') {
      return { ok: false, version: 'Indisponível', retrieved: 'Não informada', aerodromes: 0, headings: 0, overrides: 0, issues: ['Arquivo adc-runway-data.js não carregado.'] };
    }

    const aerodromes = data.aerodromes && typeof data.aerodromes === 'object' ? data.aerodromes : {};
    const overrides = data.overrides && typeof data.overrides === 'object' ? data.overrides : {};
    if (!data.aerodromes || typeof data.aerodromes !== 'object') issues.push('Relação de cartas ADC ausente ou inválida.');
    if (isFiniteNumber(data.aerodromeCount) && data.aerodromeCount !== Object.keys(aerodromes).length) issues.push('Contagem declarada de ADC diverge dos registros carregados.');

    let headings = 0;
    let invalidHeadings = 0;
    Object.values(aerodromes).forEach(entry => {
      const values = entry && entry.headings && typeof entry.headings === 'object' ? Object.values(entry.headings) : [];
      headings += values.length;
      values.forEach(value => {
        if (!isFiniteNumber(value) || value < 0 || value >= 360) invalidHeadings += 1;
      });
    });
    if (invalidHeadings) issues.push(`${invalidHeadings} rumo(s) ADC fora do intervalo de 000° a 359°.`);
    return {
      ok: issues.length === 0,
      version: typeof data.version === 'string' ? data.version : 'Não informada',
      source: typeof data.source === 'string' ? data.source : 'Não informada',
      retrieved: typeof data.retrieved === 'string' ? data.retrieved : 'Não informada',
      aerodromes: Object.keys(aerodromes).length,
      headings,
      overrides: Object.keys(overrides).length,
      issues
    };
  }

  function countCustomLocalities(storage) {
    try {
      const parsed = JSON.parse(storage.getItem(CUSTOM_LOCALITIES_KEY) || '[]');
      return Array.isArray(parsed) ? parsed.length : 0;
    } catch (_) {
      return 0;
    }
  }

  function formatDate(isoDate) {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoDate || '');
    return match ? `${match[3]}/${match[2]}/${match[1]}` : (isoDate || 'Não informada');
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character]);
  }

  function cardHtml(card) {
    const facts = card.facts.map(([label, value]) => `<div class="fact"><span>${escapeHtml(label)}</span><span>${escapeHtml(value)}</span></div>`).join('');
    const details = card.details && card.details.length ? `<ul class="details">${card.details.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : '';
    return `<article class="db-card"><div class="db-top"><div class="db-copy"><h3>${escapeHtml(card.title)}</h3><p>${escapeHtml(card.description)}</p></div><span class="badge ${card.badgeClass}">${escapeHtml(card.badge)}</span></div><div class="facts">${facts}</div>${details}${card.note ? `<p class="integrity-note">${escapeHtml(card.note)}</p>` : ''}</article>`;
  }

  function verify() {
    const legacy = analyzeLegacy(window.LEGACY_DATA);
    const adc = analyzeAdc(window.ADC_RUNWAY_DATA);
    const customCount = countCustomLocalities(window.localStorage);
    const checkedAt = new Date().toISOString();
    const allOk = legacy.ok && adc.ok;

    const installedCards = [
      {
        title: 'ROTAER / aeródromos e pistas',
        description: 'Base incorporada usada por Localidades e pelos cálculos locais de pista.',
        badge: legacy.ok ? 'Íntegra' : 'Atenção',
        badgeClass: legacy.ok ? 'ok' : 'bad',
        facts: [['Versão local', legacy.version], ['Aeródromos', legacy.aerodromes.toLocaleString('pt-BR')], ['Aeródromos com pista', legacy.runwayAerodromes.toLocaleString('pt-BR')], ['Pistas', legacy.runways.toLocaleString('pt-BR')], ['Rumos incorporados', legacy.runwayHeadings.toLocaleString('pt-BR')], ['Cadastros manuais', customCount.toLocaleString('pt-BR')]],
        details: legacy.issues,
        note: 'A integridade estrutural não confirma a vigência do ROTAER oficial.'
      },
      {
        title: 'ADC / rumos magnéticos publicados',
        description: 'Dados locais derivados das Cartas de Aeródromo do DECEA, incluindo BRG MAG e correções incorporadas.',
        badge: adc.ok ? 'Íntegra' : 'Atenção',
        badgeClass: adc.ok ? 'ok' : 'bad',
        facts: [['Versão local', adc.version], ['Coleta registrada', formatDate(adc.retrieved)], ['Aeródromos ADC', adc.aerodromes.toLocaleString('pt-BR')], ['Rumos publicados', adc.headings.toLocaleString('pt-BR')], ['Correções locais', adc.overrides.toLocaleString('pt-BR')]],
        details: adc.issues,
        note: 'A data de coleta não substitui a conferência de emendas e vigência na fonte oficial.'
      }
    ];

    document.getElementById('installed-bases').innerHTML = installedCards.map(cardHtml).join('');
    document.getElementById('integrity-dot').className = `dot ${allOk ? 'ok' : 'warn'}`;
    document.getElementById('integrity-status').textContent = allOk ? 'Arquivos locais íntegros' : 'Verificação encontrou alertas';

    try {
      window.localStorage.setItem(STATUS_KEY, JSON.stringify({ checkedAt, legacy: { ok: legacy.ok, version: legacy.version }, adc: { ok: adc.ok, version: adc.version } }));
    } catch (_) {
      // A verificação continua válida quando o armazenamento está indisponível.
    }
    return { checkedAt, allOk, legacy, adc, customCount };
  }

  function updateConnectionStatus() {
    const online = navigator.onLine;
    document.getElementById('connection-dot').className = `dot ${online ? 'ok' : 'warn'}`;
    document.getElementById('connection-status').textContent = online ? 'Rede disponível' : 'Modo offline';
  }

  window.IV_DATABASE_REGISTRY = { analyzeLegacy, analyzeAdc, countCustomLocalities, verify };

  if (typeof document !== 'undefined') {
    updateConnectionStatus();
    window.addEventListener('online', updateConnectionStatus);
    window.addEventListener('offline', updateConnectionStatus);
    document.getElementById('verify-button').addEventListener('click', verify);
    ['gesturestart', 'gesturechange', 'gestureend'].forEach(type => document.addEventListener(type, event => event.preventDefault(), { passive: false }));
    verify();
  }
})();
