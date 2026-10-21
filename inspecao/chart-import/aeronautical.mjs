import {position, inverse} from './geodesy.mjs';
const norm = v => String(v||'').trim().toUpperCase();
const snapshot = (record, collection, database) => ({kind:'local-database',collection,recordId:record.id,version:database.version||'',effectiveDate:database.effectiveDate||'',validFrom:record.validFrom||'',validTo:record.validTo||'',datum:'WGS84'});
export function indexDatabase(raw = {}, manual = {}) {
  const database={version:raw.version||'',effectiveDate:raw.effectiveDate||'',available:raw.schema==='ivplanner-aixm-core-v1',airports:[],entities:[],thresholds:[],warnings:[]};
  const add=(record,collection,type,extra={})=>{
    if(!record.designator || !position(record.position)) return;
    database.entities.push({id:record.id||collection+':'+record.designator,name:norm(record.designator),type,position:{...record.position},source:snapshot(record,collection,raw),...extra});
  };
  for(const record of raw.aerodromes||[]) if(position(record.position)) database.airports.push({icao:norm(record.designator),position:{...record.position},source:snapshot(record,'aerodromes',raw)});
  for(const record of raw.designatedPoints||[]) add(record,'designatedPoints','fix');
  // Equipment positions/frequencies avoid conflating collocated VOR and DME systems.
  for(const record of raw.navaidEquipment||[]) add(record,'navaidEquipment',record.equipmentType,{frequency:record.frequency||null});
  const runways=new Map((raw.runways||[]).map(r=>[r.id,r]));
  for(const record of raw.runwayPoints||[]) {
    const runway=runways.get(record.runwayId), icao=norm(runway?.airport?.designator);
    if(record.role==='THR' && icao && position(record.position)) database.thresholds.push({id:record.id,name:'THR'+norm(record.designator),icao,runway:norm(record.designator),position:{...record.position},source:snapshot(record,'runwayPoints',raw)});
  }
  for(const row of manual.airports||[]) if(position(row.position)) database.airports.push(row);
  for(const row of manual.aids||[]) if(position(row.position)) database.entities.push(row);
  return database;
}
export async function loadLocalDatabase(global = window) {
  let raw={}, warning='';
  try {raw=await global.IVAixmModules.core.loadRaw();} catch {warning='Pacote AIXM não instalado ou indisponível. A prévia utilizará somente fontes locais disponíveis; coordenadas ausentes não serão estimadas.';}
  const manual={airports:[],aids:[]};
  for(const row of global.LEGACY_DATA?.aerodromes||[]) if(Array.isArray(row)&&Number.isFinite(row[2])&&Number.isFinite(row[3])) manual.airports.push({icao:norm(row[0]),position:{lat:row[2],lon:row[3]},source:{kind:'bundled-rotaer',version:global.LEGACY_DATA.version||'',recordId:row[0]}});
  function records(key) {try {const r=JSON.parse(localStorage.getItem(key)||'[]');if(!Array.isArray(r))throw Error();return r;}catch{warning+=' Cadastro local ilegível preservado: '+key+'.';return [];}}
  for(const row of records('ivplanner-custom-localities-v1')) if(position({lat:row.lat,lon:row.lon})) manual.airports.push({icao:norm(row.icao),position:{lat:row.lat,lon:row.lon},source:{kind:'manual-register',recordId:row.id||row.icao}});
  for(const row of records('ivplanner-custom-aids-v1')) if(position({lat:row.lat,lon:row.lon})) manual.aids.push({id:'manual:'+row.id,name:norm(row.designator),type:row.type||'unknown',position:{lat:row.lat,lon:row.lon},frequency:row.frequencyValue?{value:Number(row.frequencyValue),uom:row.frequencyUom||'MHZ'}:null,source:{kind:'manual-register',recordId:row.id}});
  const result=indexDatabase(raw,manual);if(warning)result.warnings.push(warning);return result;
}
export function resolveEntity(name, database, {type,frequency,airport}={}) {
  let candidates=database.entities.filter(row=>row.name===norm(name));
  if(type) candidates=candidates.filter(row=>row.type===type);
  if(frequency) candidates=candidates.filter(row=>row.frequency && row.frequency.uom?.toUpperCase()===frequency.unit.toUpperCase() && Math.abs(Number(row.frequency.value)-frequency.value)<1e-8);
  // A chart must identify its airport; distance is a search bound, never a new coordinate source.
  if(airport) candidates=candidates.filter(row=>inverse(airport.position,row.position).distanceNM<=200);
  const unique=new Map();
  for(const row of candidates) {
    const key=[row.type,row.position.lat,row.position.lon].join(':');
    const prior=unique.get(key);if(prior) prior.additionalSources=[...(prior.additionalSources||[]),row.source];else unique.set(key,{...row});
  }
  candidates=[...unique.values()];
  return {status:candidates.length===1?'resolved':candidates.length?'ambiguous':'missing',candidates};
}
