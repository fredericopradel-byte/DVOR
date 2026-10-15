/* Consulta somente de leitura às bases existentes. Nenhum dado ausente é estimado. */
(() => {
  'use strict';
  const norm = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase().replace(/[^A-Z0-9]+/g, ' ').trim();
  const finite = value => value !== null && value !== undefined && String(value).trim() !== '' && Number.isFinite(Number(value));
  const position = (lat, lon) => finite(lat) && finite(lon) && Math.abs(Number(lat)) < 89 && Math.abs(Number(lon)) <= 180 ? {lat: Number(lat), lon: Number(lon)} : null;
  const text = value => typeof value === 'string' ? value.trim() : '';
  const node = (tag, parent, label, attrs = {}) => {
    const el = document.createElement(tag);
    if (label !== undefined) el.textContent = label;
    Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
    parent.append(el); return el;
  };
  const quantity = (value, units) => value && finite(value.value) && Object.hasOwn(units, String(value.uom || '').toUpperCase()) ? Number(value.value) * units[String(value.uom).toUpperCase()] : null;
  let database = null, loading = null;
  async function load() {
    if (database) return database;
    if (!loading) loading = window.IVAixm.load().then(value => {database = value; return value;}).finally(() => {loading = null;});
    return loading;
  }
  function records(key, warnings) {
    const label = {'ivplanner-custom-localities-v1': 'localidades', 'ivplanner-custom-aids-v1': 'auxílios', 'ivplanner-custom-procedures-v1': 'procedimentos'}[key];
    try {
      const raw = localStorage.getItem(key), rows = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(rows)) throw Error();
      if (rows.some(r => !r || typeof r !== 'object' || Array.isArray(r))) warnings.push('Há registros inválidos no cadastro de ' + label + '; os dados foram preservados.');
      return rows.filter(r => r && typeof r === 'object' && !Array.isArray(r));
    } catch {warnings.push('Não foi possível ler o cadastro de ' + label + '. Os dados foram preservados.'); return [];}
  }
  function airports(warnings) {
    const legacy = window.LEGACY_DATA || {}, adc = window.ADC_RUNWAY_DATA || {}, overrides = adc.overrides || {};
    const original = new Set((legacy.aerodromes || []).map(a => a[0]));
    const base = [...(legacy.aerodromes || [])];
    Object.values(overrides).forEach(row => {if (Array.isArray(row.aerodrome) && !original.has(row.aerodrome[0])) base.push(row.aerodrome);});
    const rows = base.filter(a => Array.isArray(a) && text(a[0])).map(a => ({
      icao: text(a[0]), name: text(a[1]), position: position(a[2], a[3]), elevation: finite(a[4]) ? a[4] + ' ft' : '',
      source: original.has(a[0]) ? 'ROTAER incorporado · ' + (legacy.version || 'versão não informada') : 'Complemento ADC incorporado · ' + (adc.version || 'versão não informada'),
      runwaySource: overrides[a[0]]?.runways ? 'Complemento ADC incorporado · ' + (adc.version || 'versão não informada') : '',
      runways: overrides[a[0]]?.runways || legacy.runwayDatabase?.runways?.[a[0]] || [],
      adc: adc.aerodromes?.[a[0]], manual: false
    }));
    records('ivplanner-custom-localities-v1', warnings).forEach(a => {
      if (!text(a.icao)) {warnings.push('Localidade manual sem ICAO ignorada na consulta; registro preservado.'); return;}
      rows.push({icao: text(a.icao).toUpperCase(), name: text(a.name), position: position(a.lat, a.lon),
        elevation: finite(a.elev) ? a.elev + ' ft' : '', source: 'Cadastro manual neste aparelho', runways: Array.isArray(a.runways) ? a.runways : [], manual: true});
    });
    if (database) database.aerodromes.forEach(a => {
      if (!a || typeof a !== 'object') {warnings.push('Aeródromo AIXM inválido ignorado na consulta.'); return;}
      if (!text(a.designator)) return;
      rows.push({icao: a.designator, name: text(a.name), position: position(a.position?.lat, a.position?.lon),
        elevation: a.fieldElevation && finite(a.fieldElevation.value) ? a.fieldElevation.value + ' ' + (a.fieldElevation.uom || '') : '',
        source: source(), runways: [], manual: false, aixm: true, validFrom: text(a.validFrom)});
    });
    return rows;
  }
  const source = () => 'AIXM · ' + (database?.version || '') + ' · data da base ' + (database?.effectiveDate || 'não informada');
  function matches(values, query) {const haystack = norm(values.join(' ')); return norm(query).split(' ').every(token => haystack.includes(token));}
  function aidFields(aid) {
    const mission = {};
    if (aid.type === 'NDB') {
      if (text(aid.designator)) mission.ndbIdent = aid.designator;
      if (text(aid.name)) mission.ndbName = aid.name;
      const frequency = quantity(aid.frequency, {KHZ: 1, MHZ: 1000, HZ: .001});
      const altitude = quantity(aid.elevation, {FT: 1, M: 1 / .3048});
      if (frequency !== null && frequency > 0 && frequency <= 60000) mission.ndbFrequency = String(frequency);
      if (altitude !== null && Math.abs(altitude) <= 60000) mission.ndbAltitude = String(altitude);
    }
    return mission;
  }

  window.IVMissionDatabases = {mount(host, config) {
    node('p', host, 'Busque ICAO, nome ou identificador. Selecione a fonte para preencher a missão; campos manuais continuam editáveis. Dados incompletos não são estimados.', {class: 'note muted'});
    node('p', host, 'Confira a vigência na publicação aplicável; a versão ou data da base não a comprova.', {class: 'note muted'});
    const form = node('form', host, undefined, {class: 'actions'});
    const label = node('label', form, 'Localidade, ICAO ou auxílio', {class: 'database-query'});
    const query = node('input', label, undefined, {id: 'mission-database-query', type: 'search', maxlength: '100', placeholder: 'ICAO, nome ou identificador'});
    query.value = config.icao || '';
    const search = node('button', form, 'Buscar nas bases', {id: 'mission-database-search', type: 'submit'});
    const status = node('p', host, 'ROTAER e cadastros locais disponíveis. AIXM depende do pacote instalado.', {id: 'mission-database-status', class: 'note muted', role: 'status'});
    const results = node('div', host, undefined, {id: 'mission-database-results'});
    let generation = 0;
    query.oninput = () => {generation++; results.replaceChildren(); status.textContent = 'Busca alterada. Toque em Buscar nas bases.'; search.disabled = false;};

    function card(group, title, details, sourceLabel, patch, coords, actionLabel) {
      const article = node('article', group, undefined, {class: 'database-card'});
      node('h3', article, title);
      if (details) node('p', article, details, {class: 'note'});
      node('p', article, sourceLabel, {class: 'note muted'});
      if (coords) node('p', article, 'Coordenadas do registro: ' + coords.lat + '°, ' + coords.lon + '°.', {class: 'note muted'});
      const actions = node('div', article, undefined, {class: 'actions'});
      if (patch && (Object.keys(patch.mission || {}).length || patch.title)) {
        const use = node('button', actions, actionLabel || 'Usar dados na missão', {type: 'button'});
        use.onclick = () => config.apply(patch, sourceLabel);
      }
      if (coords) {
        const reference = node('button', actions, 'Usar coordenadas como origem', {type: 'button'});
        reference.onclick = () => config.apply({origin: coords}, sourceLabel + ' · ' + title);
      }
      return article;
    }
    function group(label) {const part = node('section', results); node('h3', part, label); return part;}
    function render(term, unavailable) {
      results.replaceChildren(); const warnings = [], allAirports = airports(warnings);
      const exact = norm(term), airportRows = allAirports.filter(a => matches([a.icao, a.name], term)).sort((a, b) => Number(norm(b.icao) === exact) - Number(norm(a.icao) === exact)).slice(0, 12);
      const airportGroup = group('Localidades e aeródromos');
      airportRows.forEach(a => card(airportGroup, a.icao + ' · ' + a.name, a.elevation ? 'Elevação do aeródromo: ' + a.elevation + '.' : 'Elevação não informada.', a.source,
        {mission: {icao: a.icao, ...(a.name ? {local: a.name} : {})}}, a.position, 'Usar localidade'));
      if (!airportRows.length) node('p', airportGroup, 'Nenhuma localidade encontrada nesta consulta.', {class: 'note muted'});
      const related = new Set(allAirports.filter(a => matches([a.icao, a.name], term)).map(a => norm(a.icao)));
      if (/^[A-Z0-9]{4}$/.test(exact)) related.add(exact);
      const runwayGroup = group('Pistas e cabeceiras'); let runwayCount = 0;
      const seen = new Set();
      allAirports.filter(a => related.has(norm(a.icao)) && !a.aixm).forEach(a => {
        (a.runways || []).forEach(row => {
          if (!Array.isArray(row) && (!row || typeof row !== 'object')) return;
          const ends = Array.isArray(row) ? [row[0], row[2]] : [row.end1, row.end2];
          ends.forEach((end, index) => {
            if (!text(end)) return;
            const key = a.source + a.icao + end; if (seen.has(key) || runwayCount >= 24) return; seen.add(key); runwayCount++;
            const published = a.adc?.headings?.[end];
            const declared = Array.isArray(row) ? row[6 + index] : row['publishedMag' + (index + 1)];
            const provided = Array.isArray(row) ? row[1 + index * 2] : row['heading' + (index + 1)], origin = Array.isArray(row) ? row[5] : row.source;
            const magnetic = finite(published) ? published : finite(declared) ? declared : origin === 'published' && finite(provided) ? provided : null;
            const description = magnetic !== null ? (a.manual ? 'Rumo MAG do cadastro manual: ' : 'Rumo MAG publicado: ') + magnetic + '°.' : a.manual && row.headingRef === 'M' && finite(provided) ? 'Rumo MAG do cadastro manual: ' + provided + '°.' : ['coordinates', 'rotaer+coordinates', 'coordinates+published-mag'].includes(origin) && finite(provided) ? 'Rumo VERD da geometria registrada: ' + provided + '°.' : 'Rumo publicado não disponível nesta consulta. Nenhum rumo é deduzido do designador.';
            card(runwayGroup, a.icao + ' · RWY ' + end, description + ' Coordenadas da cabeceira não fornecidas por este registro.', (a.runwaySource || a.source) + (finite(published) ? ' · ADC ' + (a.adc.effective || '') : ''), {mission: {icao: a.icao, runway: end}}, null, 'Usar cabeceira');
          });
        });
      });
      if (database) database.runwayThresholds.filter(r => related.has(norm(r.airport?.designator))).slice(0, 24).forEach(r => {
        runwayCount++;
        card(runwayGroup, r.airport.designator + ' · RWY ' + r.designator, 'Coordenada ' + r.threshold.role + ' do registro AIXM. Não altera o azimute do desenho.', source(),
          {mission: {icao: r.airport.designator, runway: r.designator}}, position(r.threshold.position?.lat, r.threshold.position?.lon), 'Usar cabeceira');
      });
      if (!runwayCount) node('p', runwayGroup, 'Nenhuma pista ou cabeceira disponível para esta consulta.', {class: 'note muted'});
      const aidGroup = group('Auxílios à navegação');
      const manual = records('ivplanner-custom-aids-v1', warnings).map(a => ({...a, manual: true,
        position: position(a.lat, a.lon), airport: {designator: text(a.airportIcao)},
        frequency: finite(a.frequencyValue) ? {value: a.frequencyValue, uom: text(a.frequencyUom)} : null,
        elevation: finite(a.elevationValue) ? {value: a.elevationValue, uom: text(a.elevationUom)} : null}));
      const aids = [...(database?.aids || []), ...manual].filter(a => related.has(norm(a.airport?.designator)) || matches([a.designator, a.name, a.type, a.airport?.designator], term)).slice(0, 20);
      aids.forEach(a => {
        const fields = config.module === 'ndb' ? aidFields(a) : {};
        if (a.type === 'NDB' && config.module === 'ndb') {
          if (text(a.airport?.designator)) fields.icao = a.airport.designator;
          if (text(a.airport?.name)) fields.local = a.airport.name;
        }
        const frequency = a.frequency ? 'Frequência: ' + a.frequency.value + ' ' + (a.frequency.uom || '(unidade não informada)') + '. ' : 'Frequência não informada. ';
        const info = frequency + (a.type === 'NDB' && config.module === 'ndb' && fields.ndbFrequency === undefined ? 'A frequência não será preenchida sem valor e unidade reconhecidos. ' : '') + (a.elevation ? 'Elevação: ' + a.elevation.value + ' ' + (a.elevation.uom || '(unidade não informada)') + '.' : 'Elevação do auxílio não informada.');
        card(aidGroup, a.type + ' · ' + [a.designator, a.name].filter(Boolean).join(' · '), info, a.manual ? 'Cadastro manual neste aparelho' : source(),
          {mission: fields}, position(a.position?.lat, a.position?.lon), 'Usar dados do NDB');
      });
      if (!aids.length) node('p', aidGroup, 'Nenhum auxílio disponível para esta consulta.', {class: 'note muted'});
      const publishedGroup = group('Procedimentos publicados · metadados AIXM');
      const published = (database?.procedures || []).filter(p => p && typeof p === 'object' && (related.has(norm(p.airport?.designator)) || matches([p.name, p.designator, p.airport?.designator], term))).slice(0, 20);
      published.forEach(p => {
        const kind = {InstrumentApproachProcedure: 'IAC', StandardInstrumentDeparture: 'SID'}[p.procedureType];
        card(publishedGroup, (p.airport?.designator || '') + ' · ' + (p.name || p.designator || 'Sem identificação'),
          'Registro desde ' + (p.validFrom || 'data não informada') + '. Sem pernas, altitudes ou carta para importar. A revisão da carta continua manual.' + (!kind ? ' Tipo não suportado pelo editor IAC/SID: consulta apenas.' : ''), source(),
          kind && text(p.name || p.designator) ? {title: p.name || p.designator, kind, mission: {...(text(p.airport?.designator) ? {icao: p.airport.designator} : {}), ...(text(p.airport?.name) ? {local: p.airport.name} : {})}} : null, null, 'Usar identificação do procedimento');
      });
      if (!published.length) node('p', publishedGroup, 'Nenhum metadado de procedimento publicado disponível nesta consulta.', {class: 'note muted'});
      const localGroup = group('Desenhos cadastrados neste aparelho');
      const local = records('ivplanner-custom-procedures-v1', warnings).filter(p => p.module === config.module && matches([p.icao, p.local, p.title], term)).slice(0, 20);
      local.forEach(p => {
        const row = card(localGroup, p.title || 'Sem identificação', 'Cadastro local; não comprova publicação oficial. Abrir substitui o planejamento com confirmação e recuperação do atual.', 'Cadastro manual neste aparelho', null, null);
        const open = node('button', row, 'Abrir desenho cadastrado', {type: 'button'}); open.onclick = () => config.open(p);
      });
      if (!local.length) node('p', localGroup, 'Nenhum desenho deste módulo cadastrado para a consulta.', {class: 'note muted'});
      status.textContent = (unavailable ? 'AIXM não instalado ou indisponível. ROTAER e cadastros locais continuam disponíveis. ' : 'Consulta concluída. Fontes apresentadas separadamente. ') + warnings.join(' ');
      if (airportRows.length === 12 || aids.length === 20 || published.length === 20) node('p', results, 'Resultados limitados. Refine a busca pelo ICAO ou identificador.', {class: 'note muted'});
    }
    form.onsubmit = async event => {
      event.preventDefault(); const term = query.value.trim(), request = ++generation;
      if (norm(term).length < 2) {results.replaceChildren(); status.textContent = 'Informe pelo menos dois caracteres.'; return;}
      render(term, !database); status.textContent += ' Consultando o pacote AIXM…'; search.disabled = true;
      let unavailable = false; try {await load();} catch {unavailable = true;}
      if (!host.isConnected || request !== generation) return;
      search.disabled = false; render(term, unavailable);
    };
  }};
})();
