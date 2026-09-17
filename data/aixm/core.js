(function (global) {
  'use strict';

  const modules = global.IVAixmModules = global.IVAixmModules || {};
  const scriptUrl = document.currentScript && document.currentScript.src
    ? document.currentScript.src
    : location.href;
  const coreUrl = new URL('../../publicacoes-offline/aixm/AIXM-BR-2026-09-03/aixm-core.json', scriptUrl).href;
  let rawPromise = null;

  function normalized(value) {
    return String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toUpperCase()
      .replace(/[^A-Z0-9]+/g, ' ')
      .trim();
  }

  function finitePosition(item) {
    return !!(item && item.position && Number.isFinite(item.position.lat) && Number.isFinite(item.position.lon));
  }

  function airportSummary(airport) {
    if (!airport || !airport.designator) return null;
    return {
      id: airport.id || '',
      designator: airport.designator || '',
      name: airport.name || '',
    };
  }

  async function loadRaw() {
    if (rawPromise) return rawPromise;
    rawPromise = fetch(coreUrl, { cache: 'default' }).then(async response => {
      if (!response.ok) {
        const error = new Error('Pacote AIXM não instalado ou indisponível.');
        error.code = 'AIXM_UNAVAILABLE';
        throw error;
      }
      const data = await response.json();
      if (data.schema !== 'ivplanner-aixm-core-v1' || !Array.isArray(data.navaids)) {
        throw new Error('Formato da base AIXM não reconhecido.');
      }
      return data;
    }).catch(error => {
      rawPromise = null;
      throw error;
    });
    return rawPromise;
  }

  modules.core = { loadRaw, normalized, finitePosition, airportSummary, coreUrl };
})(window);
