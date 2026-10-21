// Recognition is evidence based. Graphic coordinates are page coordinates, never geography.
export const SCHEMA = 'ivplanner-chart-import-v1';
const clean = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase().replace(/RW\s+Y/g, 'RWY').replace(/OR\s*LOC\b/g, ' OR LOC').replace(/\s+/g, ' ').trim();

export function recognize(extraction) {
  const items = extraction.text || [];
  const lines = extraction.lines || items.map(item => ({text: item.text, evidenceIds: [item.id]}));
  const joined = clean(lines.map(line => line.text).join(' '));
  const metadata = {}, issues = [];
  const matches = (regex) => lines.filter(line => {regex.lastIndex = 0; return regex.test(clean(line.text));});
  function field(key, candidates) {
    const distinct = [...new Map(candidates.filter(c => c.value).map(c => [c.value, c])).values()];
    if (distinct.length === 1) metadata[key] = {...distinct[0], status: 'extracted'};
    else if (distinct.length > 1) issues.push({id: 'ambiguous-' + key, category: 'ambiguity', critical: true, field: key, message: 'Mais de uma leitura para ' + key + '.', options: distinct});
  }
  const chartIds = matches(/\b[A-Z]{4}_(?:IAC|SID)_/).map(line => ({line, match: clean(line.text).match(/\b([A-Z]{4})_(IAC|SID)_([A-Z0-9]+)/)}));
  field('icao', chartIds.map(({line, match}) => ({value: match[1], evidenceIds: line.evidenceIds})));
  field('kind', chartIds.map(({line, match}) => ({value: match[2], evidenceIds: line.evidenceIds})));
  if (!metadata.kind) field('kind', matches(/\b(?:CHART\s*\(IAC\)|\(SID\)|STANDARD DEPARTURE)\b|CHART\s*\(IAC\)/).map(line => ({value: /IAC/.test(clean(line.text)) ? 'IAC' : 'SID', evidenceIds: line.evidenceIds})));
  const titlePattern = /\b(?:IAC\s+|SID\s+)?((?:ILS|LOC|VOR|NDB|RNP|RNAV|[A-Z]{5}\s+\d[A-Z])[A-Z0-9 /()-]*?\bRWY\s*\d{2}[LRC]?)\b/;
  const titles = matches(titlePattern).map(line => ({value: clean(line.text).match(titlePattern)[1].replace(/\s+/g, ' '), evidenceIds: line.evidenceIds}));
  field('procedure', titles);
  if (metadata.procedure) field('runway', [{value: metadata.procedure.value.match(/RWY\s*(\d{2}[LRC]?)/)?.[1], evidenceIds: metadata.procedure.evidenceIds}]);
  const airports = matches(/\([A-Z]{4}\)/).filter(line => !metadata.icao || clean(line.text).includes('(' + metadata.icao.value + ')'));
  field('airport', airports.filter(line => /\//.test(line.text)).map(line => ({value: line.text.replace(/^(?:INSTRUMENT APPROACH|STANDARD DEPARTURE CHART)\s*/i, '').trim(), evidenceIds: line.evidenceIds})));
  if (!metadata.icao) field('icao', airports.map(line => ({value: clean(line.text).match(/\(([A-Z]{4})\)/)[1], evidenceIds: line.evidenceIds})));
  field('revision', matches(/AIRAC\s*AMDT\s*[A-Z0-9]+/).map(line => {
    const match = clean(line.text).match(/AIRAC\s*AMDT\s*([A-Z0-9]+)(?:\s+(\d{2})\s*(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s*(\d{4}|\d{2}))?/);
    return {value: 'AIRAC AMDT ' + match[1] + (match[2] ? ' ' + match.slice(2).join(' ') : ''), evidenceIds: line.evidenceIds};
  }));
  const months = {JAN: 1, FEB: 2, MAR: 3, APR: 4, MAY: 5, JUN: 6, JUL: 7, AUG: 8, SEP: 9, OCT: 10, NOV: 11, DEC: 12};
  if (metadata.revision) {
    const date = clean(metadata.revision.value).match(/\b(\d{2})\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{2}|\d{4})\b/);
    if (date) {
      const year = date[3].length === 2 ? 2000 + Number(date[3]) : Number(date[3]);
      const iso = year + '-' + String(months[date[2]]).padStart(2, '0') + '-' + date[1];
      const parsed = new Date(iso + 'T00:00:00Z');
      if (Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === iso) metadata.publishedDate = {value: iso, evidenceIds: metadata.revision.evidenceIds, status: 'extracted'};
    }
  }
  const navigation = [], requirements = [], structures = [];
  const title = metadata.procedure?.value || '';
  for (const type of ['ILS', 'LOC', 'VOR', 'NDB', 'RNP', 'RNAV']) if (new RegExp('\\b' + type + '\\b').test(title)) navigation.push(type);
  for (const [label, pattern] of [['GNSS', /GNSS\s+REQ/], ['DME', /DME\s+REQ/], ['RNP APCH', /RNP\s+APCH/], ['RNAV1 / RNP1', /RNAV\s*1.*RNP\s*1/]]) {
    const evidence = matches(pattern);
    if (evidence.length) requirements.push({value: label, evidenceIds: evidence.flatMap(l => l.evidenceIds)});
  }
  for (const [type, pattern] of [['dme-arc', /(?:ARCO\s+DME|DME\s+ARC)/], ['holding', /\b(?:ESPERA|HOLDING)\b/], ['radial', /\bR\s*\d{3}\s+[A-Z]{2,3}\b|\bRDL\b/]]) {
    const evidence = matches(pattern);
    if (evidence.length) structures.push({type, status: 'text-evidence-only', evidenceIds: evidence.flatMap(l => l.evidenceIds)});
  }
  if (items.filter(item => /[A-Za-z0-9]/.test(item.text)).length < 8) issues.push({id: 'visual-required', category: 'missing', critical: true, message: 'Página sem texto extraível suficiente. É necessário OCR ou interpretação visual, ainda não disponível. Nenhum procedimento foi inferido do nome do arquivo.'});
  for (const key of ['kind', 'icao', 'procedure']) if (!metadata[key] && !issues.some(i => i.field === key)) issues.push({id: 'missing-' + key, category: 'missing', critical: true, field: key, message: ({kind: 'Tipo de carta', icao: 'ICAO', procedure: 'Procedimento'})[key] + ' não identificado com segurança.'});
  issues.push({id: 'geometry-pending', category: 'missing', critical: true, message: 'Reconstrução georreferenciada e conferência do desenho pertencem às próximas etapas. Esta extração ainda não pode ser aplicada à missão.'});
  const aids = [];
  for (const line of lines) {
    for (const match of clean(line.text).matchAll(/\b(1[01]\d\.\d{1,3})\s*([A-Z]{2,3})\b/g)) {
      if (Number(match[1]) < 108 || Number(match[1]) > 117.975 || match[2] === 'MHZ') continue;
      if (!aids.some(aid => aid.ident === match[2] && aid.frequency === Number(match[1]))) aids.push({ident: match[2], frequency: Number(match[1]), unit: 'MHz', evidenceIds: line.evidenceIds, status: 'text-candidate'});
    }
  }
  return {metadata, navigation, requirements, structures, aids, issues, coverage: 'structural-extraction-only', validity: 'not-verified', textAvailable: joined.length > 0};
}

export function newSession(module, source) {
  if (!['ndb', 'procedimentos'].includes(module)) throw Error('Módulo de destino inválido.');
  return {schema: SCHEMA, id: crypto.randomUUID(), module, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), status: 'draft', review: {validated: false}, page: 1, source, extraction: null, recognition: null};
}
