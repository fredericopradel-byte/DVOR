(function (global) {
  'use strict';

  const scriptUrl = document.currentScript && document.currentScript.src
    ? document.currentScript.src
    : location.href;
  const coreUrl = new URL('../publicacoes-offline/aixm/AIXM-BR-2026-09-03/aixm-core.json', scriptUrl).href;
  let loadPromise = null;

  function normalized(value) {
    return String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toUpperCase()
      .replace(/[^A-Z0-9]+/g, ' ')
      .trim();
  }

  function equipmentDetails(navaid, equipmentById) {
    const linked = (navaid.equipmentIds || []).map(id => equipmentById.get(id)).filter(Boolean);
    const vor = linked.find(item => item.equipmentType === 'VOR');
    const dme = linked.find(item => item.equipmentType === 'DME');
    return {
      frequency: vor && vor.frequency || null,
      channel: dme && dme.channel || null,
      operationalStatus: vor && vor.operationalStatus || dme && dme.operationalStatus || null,
    };
  }

  async function load() {
    if (loadPromise) return loadPromise;
    loadPromise = fetch(coreUrl, { cache: 'default' }).then(async response => {
      if (!response.ok) {
        const error = new Error('Pacote AIXM não instalado ou indisponível.');
        error.code = 'AIXM_UNAVAILABLE';
        throw error;
      }
      const data = await response.json();
      if (data.schema !== 'ivplanner-aixm-core-v1' || !Array.isArray(data.navaids)) {
        throw new Error('Formato da base AIXM não reconhecido.');
      }
      const equipmentById = new Map((data.navaidEquipment || []).map(item => [item.id, item]));
      const navaids = data.navaids
        .filter(item => /(^|_)VOR($|_)/.test(item.type || '') && item.position && Number.isFinite(item.position.lat) && Number.isFinite(item.position.lon))
        .map(item => {
          const details = equipmentDetails(item, equipmentById);
          const airport = item.airport || null;
          const searchText = normalized([
            item.designator,
            item.name,
            item.type,
            airport && airport.designator,
            airport && airport.name,
          ].filter(Boolean).join(' '));
          return {
            id: item.id,
            designator: item.designator || '',
            name: item.name || '',
            type: item.type || 'VOR',
            position: { lat: Number(item.position.lat), lon: Number(item.position.lon) },
            airport,
            frequency: details.frequency,
            channel: details.channel,
            operationalStatus: details.operationalStatus,
            validFrom: item.validFrom || '',
            searchText,
          };
        });
      return { version: data.version || '', effectiveDate: data.effectiveDate || '', navaids };
    }).catch(error => {
      loadPromise = null;
      throw error;
    });
    return loadPromise;
  }

  function search(database, query, limit) {
    const term = normalized(query);
    if (term.length < 2) return [];
    const tokens = term.split(' ').filter(Boolean);
    return database.navaids
      .filter(item => tokens.every(token => item.searchText.includes(token)))
      .map(item => {
        const ident = normalized(item.designator);
        const name = normalized(item.name);
        let score = 10;
        if (ident === term) score = 0;
        else if (ident.startsWith(term)) score = 1;
        else if (name === term) score = 2;
        else if (name.startsWith(term)) score = 3;
        else if (ident.includes(term)) score = 4;
        else if (name.includes(term)) score = 5;
        return { item, score };
      })
      .sort((a, b) => a.score - b.score || a.item.name.localeCompare(b.item.name, 'pt-BR'))
      .slice(0, limit || 8)
      .map(entry => entry.item);
  }

  global.IVAixm = { load, search, coreUrl };
})(window);
