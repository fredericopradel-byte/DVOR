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

  function finitePosition(item) {
    return item && item.position && Number.isFinite(item.position.lat) && Number.isFinite(item.position.lon);
  }

  function buildRunwayData(data) {
    const directionById = new Map((data.runwayDirections || []).map(item => [item.id, item]));
    const pointsByDirection = new Map();
    (data.runwayPoints || []).forEach(point => {
      if (!finitePosition(point) || !['THR', 'DISTHR'].includes(point.role)) return;
      const list = pointsByDirection.get(point.runwayId) || [];
      list.push(point);
      pointsByDirection.set(point.runwayId, list);
    });

    const papiByDirection = new Map();
    (data.visualGlideSlopeIndicators || [])
      .filter(item => item.type === 'PAPI' && item.runwayDirectionId)
      .forEach(item => {
        const list = papiByDirection.get(item.runwayDirectionId) || [];
        list.push({
          id: item.id,
          type: item.type,
          side: item.side || '',
          slopeAngle: Number.isFinite(item.slopeAngle) ? Number(item.slopeAngle) : null,
          minimumEyeHeightOverThreshold: item.minimumEyeHeightOverThreshold || null,
          numberOfBoxes: Number.isFinite(item.numberOfBoxes) ? Number(item.numberOfBoxes) : null,
          validFrom: item.validFrom || '',
        });
        papiByDirection.set(item.runwayDirectionId, list);
      });

    const runwayThresholds = [];
    directionById.forEach(direction => {
      const candidates = (pointsByDirection.get(direction.id) || [])
        .filter(point => !point.designator || point.designator === direction.designator)
        .sort((a, b) => {
          const role = { DISTHR: 0, THR: 1 };
          return (role[a.role] ?? 9) - (role[b.role] ?? 9) || String(b.validFrom || '').localeCompare(String(a.validFrom || ''));
        });
      const point = candidates[0];
      if (!point || !direction.airport || !direction.airport.designator) return;
      const airport = {
        id: direction.airport.id || '',
        designator: direction.airport.designator || '',
        name: direction.airport.name || '',
      };
      runwayThresholds.push({
        directionId: direction.id,
        designator: direction.designator || point.designator || '',
        runwayDesignator: direction.runwayDesignator || '',
        airport,
        threshold: {
          id: point.id,
          role: point.role,
          position: { lat: Number(point.position.lat), lon: Number(point.position.lon) },
          validFrom: point.validFrom || '',
        },
        papiSystems: papiByDirection.get(direction.id) || [],
        validFrom: direction.validFrom || '',
      });
    });

    const thresholdsByAirport = new Map();
    runwayThresholds.forEach(item => {
      const icao = normalized(item.airport.designator);
      const list = thresholdsByAirport.get(icao) || [];
      list.push(item);
      thresholdsByAirport.set(icao, list);
    });
    thresholdsByAirport.forEach(list => list.sort((a, b) => a.designator.localeCompare(b.designator, 'pt-BR', { numeric: true })));

    const runwayAirports = [...thresholdsByAirport.entries()].map(([designator, thresholds]) => ({
      designator,
      name: thresholds[0] && thresholds[0].airport.name || '',
      searchText: normalized(`${designator} ${thresholds[0] && thresholds[0].airport.name || ''}`),
    })).sort((a, b) => a.designator.localeCompare(b.designator));

    return { runwayThresholds, thresholdsByAirport, runwayAirports };
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
      const runwayData = buildRunwayData(data);
      return { version: data.version || '', effectiveDate: data.effectiveDate || '', navaids, ...runwayData };
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

  function searchRunwayAirports(database, query, limit) {
    const term = normalized(query);
    if (term.length < 2) return [];
    const tokens = term.split(' ').filter(Boolean);
    return (database.runwayAirports || [])
      .filter(item => tokens.every(token => item.searchText.includes(token)))
      .map(item => {
        const ident = normalized(item.designator);
        const name = normalized(item.name);
        let score = 10;
        if (ident === term) score = 0;
        else if (ident.startsWith(term)) score = 1;
        else if (name === term) score = 2;
        else if (name.startsWith(term)) score = 3;
        return { item, score };
      })
      .sort((a, b) => a.score - b.score || a.item.designator.localeCompare(b.item.designator))
      .slice(0, limit || 12)
      .map(entry => entry.item);
  }

  function thresholdsForAirport(database, icao) {
    return database.thresholdsByAirport && database.thresholdsByAirport.get(normalized(icao)) || [];
  }

  function thresholdForRunway(database, icao, runway) {
    const designator = normalized(runway).replace(/ /g, '');
    return thresholdsForAirport(database, icao).find(item => normalized(item.designator).replace(/ /g, '') === designator) || null;
  }

  global.IVAixm = { load, search, searchRunwayAirports, thresholdsForAirport, thresholdForRunway, coreUrl };
})(window);
