(function (global) {
  'use strict';

  const modules = global.IVAixmModules || {};
  let loadPromise = null;

  function requireModules() {
    const required = ['core', 'aerodromes', 'vor', 'dme', 'ndb', 'papi', 'ils'];
    const missing = required.filter(name => !modules[name]);
    if (missing.length) throw new Error(`Módulos AIXM ausentes: ${missing.join(', ')}.`);
  }

  function buildAidIndexes(aids) {
    const aidsByAirport = new Map();
    aids.forEach(item => {
      const icao = modules.core.normalized(item.airport && item.airport.designator);
      if (!icao) return;
      const list = aidsByAirport.get(icao) || [];
      list.push(item);
      aidsByAirport.set(icao, list);
    });
    aidsByAirport.forEach(list => list.sort((a, b) => a.type.localeCompare(b.type) || a.designator.localeCompare(b.designator, 'pt-BR', { numeric: true })));
    return { aidsByAirport };
  }

  async function load() {
    if (loadPromise) return loadPromise;
    loadPromise = Promise.resolve().then(async () => {
      requireModules();
      const data = await modules.core.loadRaw();
      const context = modules.aerodromes.build(data);
      const vor = modules.vor.build(data, context);
      const dme = modules.dme.build(data, context);
      const ndb = modules.ndb.build(data, context);
      const papi = modules.papi.build(data, context);
      const ils = modules.ils.build(data, context);
      const aids = [...vor.aids, ...dme.aids, ...ndb.aids, ...ils.aids, ...papi.aids];
      const indexes = buildAidIndexes(aids);
      return {
        version: data.version || '',
        effectiveDate: data.effectiveDate || '',
        navaids: vor.navaids,
        aids,
        aidsByAirport: indexes.aidsByAirport,
        visualAids: papi.visualAids,
        runwayThresholds: papi.runwayThresholds,
        thresholdsByAirport: papi.thresholdsByAirport,
        runwayAirports: papi.runwayAirports,
      };
    }).catch(error => {
      loadPromise = null;
      throw error;
    });
    return loadPromise;
  }

  function rankedSearch(items, query, limit) {
    const term = modules.core.normalized(query);
    if (term.length < 2) return [];
    const tokens = term.split(' ').filter(Boolean);
    return items
      .filter(item => tokens.every(token => item.searchText.includes(token)))
      .map(item => {
        const ident = modules.core.normalized(item.designator);
        const name = modules.core.normalized(item.name);
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

  function search(database, query, limit) {
    return rankedSearch(database.navaids, query, limit);
  }

  function searchAids(database, query, limit) {
    const term = modules.core.normalized(query);
    if (!term) return database.aids.slice(0, limit || database.aids.length);
    return rankedSearch(database.aids, query, limit || database.aids.length);
  }

  function searchRunwayAirports(database, query, limit) {
    return rankedSearch(database.runwayAirports, query, limit || 12);
  }

  function thresholdsForAirport(database, icao) {
    return database.thresholdsByAirport && database.thresholdsByAirport.get(modules.core.normalized(icao)) || [];
  }

  function thresholdForRunway(database, icao, runway) {
    const designator = modules.core.normalized(runway).replace(/ /g, '');
    return thresholdsForAirport(database, icao).find(item => modules.core.normalized(item.designator).replace(/ /g, '') === designator) || null;
  }

  function aidsForAirport(database, icao) {
    return database.aidsByAirport && database.aidsByAirport.get(modules.core.normalized(icao)) || [];
  }

  global.IVAixm = {
    load,
    search,
    searchAids,
    searchRunwayAirports,
    thresholdsForAirport,
    thresholdForRunway,
    aidsForAirport,
    coreUrl: modules.core && modules.core.coreUrl || '',
  };
})(window);
