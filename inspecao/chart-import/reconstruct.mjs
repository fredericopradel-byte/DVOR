import {labelType, roleNames, roleSupports, altitudeSupports, altitudeBar} from './semantics.mjs';
import {interpret, center, supportedLayout} from './decea.mjs';
import {resolveEntity} from './aeronautical.mjs';
import {inverse, destination, position, normalize, angleDifference} from './geodesy.mjs';
import {reconstructThreshold} from './profile.mjs';
import {toNativeDocument} from './native.mjs';

export const MODEL_SCHEMA='ivplanner-chart-geometry-v1';
const norm=value=>String(value||'').trim().toUpperCase();
const id=value=>norm(value).replace(/[^A-Z0-9_-]/g,'_');
const issue=(id,category,message,entities=[],extra={})=>({id,category,message,entities,critical:true,...extra});
function temporal(source,date){return !!date && ((source.validFrom&&source.validFrom.slice(0,10)>date)||(source.validTo&&source.validTo.slice(0,10)<date));}
export function validateModel(model) {
  if(!model||model.schema!==MODEL_SCHEMA||!['ndb','procedimentos'].includes(model.module)||!Array.isArray(model.points)||!Array.isArray(model.legs)||model.points.length>500||model.legs.length>700)throw Error('Modelo intermediário incompatível.');
  const results=[],issues=[],points=new Map();
  for(const p of model.points){if(typeof p.id!=='string'||points.has(p.id))throw Error('Identificação de ponto duplicada.');if(p.position&&!position(p.position))throw Error('Coordenada intermediária inválida.');points.set(p.id,p);}
  const ids=new Set();
  for(const leg of model.legs){
    if(typeof leg.id!=='string'||ids.has(leg.id))throw Error('Identificação de perna duplicada.');ids.add(leg.id);
    const a=points.get(leg.from),b=points.get(leg.to);
    if(!a?.position||!b?.position){results.push({entity:leg.id,passed:false,reason:'missing-endpoints'});issues.push(issue('endpoints-'+leg.id,'missing','Perna sem coordenadas verificáveis.',[leg.id]));continue;}
    const measured=inverse(a.position,b.position);
    if(leg.type==='line'){
      if(!leg.published||![leg.published.distanceNM,leg.published.course,leg.published.distanceResolution,leg.published.courseResolution].every(Number.isFinite)||leg.published.distanceNM<=0||leg.published.distanceResolution<=0||leg.published.courseResolution<=0||!['true','magnetic'].includes(leg.published.reference)||(leg.published.reference==='magnetic'&&!Number.isFinite(model.reference.variation?.value))){results.push({entity:leg.id,passed:false,reason:'missing-published-definition'});issues.push(issue('definition-'+leg.id,'missing','Definição publicada ou referência magnética incompleta.',[leg.id]));continue;}
      const distanceError=Math.abs(measured.distanceNM-leg.published.distanceNM),course=leg.published.reference==='magnetic'?normalize(measured.trueCourse-(model.reference.variation?.value||0)):measured.trueCourse;
      const courseError=angleDifference(course,leg.published.course),distanceTolerance=leg.published.distanceResolution/2+1e-6,courseTolerance=leg.published.courseResolution/2+(leg.published.reference==='magnetic'?(model.reference.variation?.resolution||0)/2:0)+1e-6;
      const passed=distanceError<=distanceTolerance&&courseError<=courseTolerance;
      results.push({id:'geometry-'+leg.id,entity:leg.id,passed,measured,distanceError,courseError,distanceTolerance,courseTolerance,reason:'published-rounding-intervals'});
      if(!passed)issues.push(issue('geometry-'+leg.id,'inconsistency','Curso/distância publicados divergem das coordenadas; a perna não será convertida.',[leg.id],{published:leg.published,measured}));
    }else if(leg.type==='arc'){
      const c=points.get(leg.center);if(!c?.position||!['left','right'].includes(leg.turn)||!Number.isFinite(leg.radiusNM)||leg.radiusNM<=0||!Number.isFinite(leg.radiusResolution)||leg.radiusResolution<=0){results.push({entity:leg.id,passed:false,reason:'incomplete-arc'});issues.push(issue('arc-'+leg.id,'missing','Arco sem centro, raio ou sentido confirmado.',[leg.id]));continue;}
      const ra=inverse(c.position,a.position),rb=inverse(c.position,b.position),tolerance=(leg.radiusResolution||.1)/2+1e-6;
      const sweep=normalize((leg.turn==='right'?1:-1)*(rb.trueCourse-ra.trueCourse));
      if(sweep<1e-8&&leg.sweepDegrees!==360){results.push({entity:leg.id,passed:false,reason:'missing-sweep'});issues.push(issue('sweep-'+leg.id,'missing','Extensão angular do arco não confirmada.',[leg.id]));continue;}
      const passed=Math.abs(ra.distanceNM-leg.radiusNM)<=tolerance&&Math.abs(rb.distanceNM-leg.radiusNM)<=tolerance;
      results.push({id:'geometry-'+leg.id,entity:leg.id,passed,radialStart:ra.distanceNM,radialEnd:rb.distanceNM,radiusTolerance:tolerance});
      if(!passed)issues.push(issue('geometry-'+leg.id,'inconsistency','Extremidades incompatíveis com o raio publicado do arco.',[leg.id]));
    }else {results.push({entity:leg.id,passed:false,reason:'unsupported-type'});issues.push(issue('unsupported-'+leg.id,'missing','Tipo de trajetória não suportado pelo conversor: '+leg.type+'.',[leg.id]));}
  }
  for(const r of model.verticalConstraints||[]) if(r.upper!==undefined&&r.lower!==undefined&&r.upper<r.lower)issues.push(issue('vertical-'+r.id,'inconsistency','Janela vertical invertida.',[r.entity]));
  return {results,issues};
}
export function tracePaths(points,legs) {
  const outgoing=new Map(),incoming=new Map();for(const leg of legs){outgoing.set(leg.from,[...(outgoing.get(leg.from)||[]),leg]);incoming.set(leg.to,(incoming.get(leg.to)||0)+1);}
  const paths=[];
  function walk(at,route,visited){if(paths.length>=128)return;if(visited.has(at)){paths.push({legs:route,cycle:true});return;}const next=outgoing.get(at)||[];if(!next.length){paths.push({legs:route,cycle:false});return;}for(const leg of next)walk(leg.to,[...route,leg.id],new Set([...visited,at]));}
  const roots=points.filter(p=>outgoing.has(p.id)&&!incoming.has(p.id));for(const root of roots)walk(root.id,[],new Set());
  if(!roots.length&&legs.length)walk(legs[0].from,[],new Set());
  return paths;
}
export function derivePoint({anchor,course,distanceNM,reference,variation}) {
  if(reference!=='true'&&reference!=='magnetic')throw Error('Referência do curso não confirmada.');
  if(reference==='magnetic'&&!Number.isFinite(variation))throw Error('Declinação não confirmada.');
  return destination(anchor,reference==='magnetic'?normalize(course+variation):course,distanceNM);
}
export function reconstruct(session,database) {
  const {extraction,recognition,module,source}=session;
  if(!extraction||!recognition||!['ndb','procedimentos'].includes(module))throw Error('Extração/contexto indisponível.');
  const interpreted=interpret(extraction,recognition),issues=[...recognition.issues.filter(i=>i.id!=='geometry-pending'),...interpreted.issues];
  const model={schema:MODEL_SCHEMA,module,source:{sha256:source.sha256,page:session.page,chart:recognition.metadata,extractionMethod:extraction.method},provider:interpreted.provider,reference:{course:interpreted.reference,variation:interpreted.variation},database:{version:database.version,effectiveDate:database.effectiveDate},points:[],legs:[],verticalConstraints:[],structures:[],paths:[],checks:[],issues,status:'partial',review:{validated:false}};
  if(!database.available)issues.push(issue('database-unavailable','missing','Base estruturada AIXM indisponível. Fixos ausentes não serão estimados.'));
  for(const [i,message] of database.warnings.entries())issues.push(issue('database-warning-'+i,'missing',message));
  if(extraction.truncated)issues.push(issue('truncated-geometry','missing','Extração incompleta: associação automática de pernas suspensa.'));
  if(!extraction.text.length){issues.push(issue('no-geometry','missing','Sem texto reconhecido: nenhum ponto ou percurso foi inferido da imagem ou do nome do arquivo.'));return finishModel(model);}
  const icao=recognition.metadata.icao?.value,officialAirports=database.airports.filter(a=>a.icao===icao&&a.source.kind==='local-database'),fallback=database.airports.filter(a=>a.icao===icao);
  const airports=officialAirports.length?officialAirports:fallback,airport=airports.length===1?airports[0]:null;
  if(!airport)issues.push(issue('airport-context','ambiguity','Localidade de referência ausente ou ambígua; a associação espacial automática foi suspensa.'));
  const knownNames=new Set(database.entities.map(p=>p.name)),names=new Set(),aidNames=new Map();
  for(const aid of interpreted.aids)if(interpreted.plan.some(r=>r.evidenceIds.some(e=>aid.evidenceIds.includes(e)))){aidNames.set(aid.name,aid);names.add(aid.name);}
  for(const publication of interpreted.positions)names.add(publication.name);
  for(const run of interpreted.plan)if(labelType(run)==='identifier-candidate'&&(knownNames.has(norm(run.text))||aidNames.has(norm(run.text))))names.add(norm(run.text));
  const roles=interpreted.plan.filter(r=>roleNames(r).length);
  // Missing database entries need a function-label association, not merely a nearby word.
  for(const role of roles){const near=interpreted.plan.filter(r=>roleSupports(role,r)).map(r=>({r,d:Math.hypot(center(r.bbox).x-center(role.bbox).x,center(r.bbox).y-center(role.bbox).y)})).sort((a,b)=>a.d-b.d);if(near[0]&&(!near[1]||near[1].d-near[0].d>role.height*.25))names.add(norm(near[0].r.text));}
  const layout=new Map();
  for(const name of names){
    const aid=aidNames.get(name),seen=interpreted.plan.filter(r=>(labelType(r)==='identifier-candidate'&&norm(r.text)===name)||(aid&&r.evidenceIds.some(e=>aid.evidenceIds.includes(e)))),resolution=airport?resolveEntity(name,database,{type:aid?.type,frequency:aid?.frequency,airport}):{status:'missing',candidates:[]};
    const pointId='p-'+id(name),point={id:pointId,name,kind:aid?'aid':'fix',roles:[],position:null,coordinateState:resolution.status,coordinateSource:null,evidenceIds:seen.flatMap(r=>r.evidenceIds),candidates:resolution.candidates};
    if(resolution.status==='resolved'){
      const row=resolution.candidates[0];point.position={...row.position};point.coordinateSource={...row.source,originalPosition:{...row.position}};point.kind=row.type;point.candidates=[];
      if(temporal(row.source,recognition.metadata.publishedDate?.value)){point.coordinateState='temporal-review';issues.push(issue('date-'+pointId,'inconsistency','A edição da coordenada de '+name+' não comprova correspondência com a data desta carta.',[pointId],{source:row.source,chartDate:recognition.metadata.publishedDate?.value}));}
    }else issues.push(issue('coordinate-'+pointId,resolution.status==='ambiguous'?'ambiguity':'missing','Coordenada de '+name+(resolution.status==='ambiguous'?' possui mais de uma associação possível.':' não disponível com segurança.'),[pointId],{options:resolution.candidates}));
    const publications=interpreted.positions.filter(p=>p.name===name);point.coordinatePublications=publications;
    if(publications.length){const unique=[...new Map(publications.map(p=>[p.position.lat+':'+p.position.lon,p])).values()];
      if(unique.length===1&&unique[0].datum==='WGS84'){
        const publication=unique[0];if(point.position&&inverse(point.position,publication.position).distanceNM>publication.resolutionNM+1e-6)issues.push(issue('chart-base-coordinate-'+pointId,'inconsistency','Coordenada publicada de '+name+' diverge da base local. O valor publicado foi preservado.',[pointId],{published:publication.position,database:point.position}));
        point.databaseCandidates=resolution.candidates;point.position={...publication.position};point.coordinateState='published';point.coordinateSource={kind:'chart-published-coordinate',datum:'WGS84',originalPosition:{...publication.position},raw:publication.raw,evidenceIds:publication.evidenceIds};
        const missing=issues.findIndex(i=>i.id==='coordinate-'+pointId);if(missing>=0)issues.splice(missing,1);
      }else issues.push(issue('published-coordinate-'+pointId,unique.length>1?'ambiguity':'missing',unique.length>1?'Coordenadas publicadas conflitantes para '+name+'.':'Datum da coordenada publicada não identificado para '+name+'.',[pointId]));
    }
    point.labelEvidence=seen.map(r=>({type:labelType(r),evidenceIds:r.evidenceIds}));
    const maxHeight=Math.max(...seen.map(r=>r.height),0),main=seen.filter(r=>r.height>=maxHeight*.85);
    for(const occurrence of main.filter(r=>norm(r.text)===name))for(const role of roles)if(roleSupports(role,occurrence))point.roles.push(...roleNames(role));
    point.roles=[...new Set(point.roles)];
    // Under/overlines carry published altitude semantics; absence is not silently 'at'.
    for(const occurrence of main){const nearby=interpreted.plan.filter(r=>altitudeSupports(occurrence,r,{roles,lines:interpreted.lines,aid:!!aid}));
      if(nearby.length===1){const alt=nearby[0],bars=interpreted.lines.map(l=>altitudeBar(l,alt)),below=bars.includes('below'),above=bars.includes('above');
        const qualifier=below&&above?'at':below?'above':above?'below':'unspecified';
        if(!model.verticalConstraints.some(r=>r.entity===pointId&&r.value===parseInt(alt.text)))model.verticalConstraints.push({id:'vertical-'+pointId+(model.verticalConstraints.some(r=>r.entity===pointId)?'-'+parseInt(alt.text):''),entity:pointId,value:parseInt(alt.text),unit:'FT',reference:'MSL',qualifier,evidenceIds:alt.evidenceIds,source:'chart-label',status:qualifier==='unspecified'?'review':'extracted'});
      }else if(nearby.length>1)issues.push(issue('altitude-'+pointId,'ambiguity','Mais de uma altitude próxima de '+name+'. Associação vertical pendente.',[pointId]));
    }
    layout.set(pointId,seen);model.points.push(point);
  }
  associateLegs(model,interpreted,layout,{truncated:extraction.truncated,airportKnown:!!airport});
  reconstructThreshold(model,interpreted,database,{truncated:extraction.truncated});
  if(interpreted.frame){
    const bottom=interpreted.frame.bbox[1]+interpreted.frame.bbox[3],profile=interpreted.runs.filter(r=>r.bbox[1]>bottom&&r.bbox[1]<bottom+extraction.height*.13);
    for(const p of model.points)for(const label of profile.filter(r=>norm(r.text)===p.name)){
      const c=center(label.bbox),near=profile.filter(r=>/^\d{3,5}['’]$/.test(r.text)&&r.bbox[1]>label.bbox[1]&&r.bbox[1]<label.bbox[1]+label.height*4&&Math.abs(center(r.bbox).x-c.x)<Math.max(18,label.bbox[2]*.7));
      const values=[...new Map(near.map(r=>[parseInt(r.text),r])).entries()];
      if(values.length===1){const [value,alt]=values[0],prior=model.verticalConstraints.find(r=>r.entity===p.id);
        if(prior&&prior.value!==value)issues.push(issue('profile-altitude-'+p.id,'inconsistency','Altitudes do plano e do perfil divergem em '+p.name+'.',[p.id]));
        else if(!prior)model.verticalConstraints.push({id:'profile-'+p.id,entity:p.id,value,unit:'FT',reference:'MSL',qualifier:'unspecified',evidenceIds:[...label.evidenceIds,...alt.evidenceIds],source:'chart-profile',status:'review'});
      }else if(values.length>1)issues.push(issue('profile-altitude-'+p.id,'ambiguity','Mais de uma altitude no perfil próxima de '+p.name+'.',[p.id]));
    }
  }
  for(const r of model.verticalConstraints)if(r.qualifier==='unspecified')issues.push(issue('qualifier-'+r.id,'ambiguity','Qualificador da altitude de '+model.points.find(p=>p.id===r.entity)?.name+' ainda não confirmado.',[r.entity]));
  for(const structure of recognition.structures.filter(s=>s.type!=='radial')){model.structures.push({...structure,status:'unresolved'});issues.push(issue('structure-'+structure.type,'missing',structure.type==='dme-arc'?'Arco DME identificado: centro, extremidades, varredura e sentido precisam de associação confirmada. Não foi substituído por reta.':structure.type==='rf-leg'?'Curva RF identificada: parâmetros e associação ainda não determinados. Não foi equiparada a arco DME nem substituída por reta.':'Espera identificada: parâmetros e sequência ainda não determinados. Não foi substituída por polilinha.',[],{evidenceIds:structure.evidenceIds}));}
  for(const gradient of interpreted.gradients)model.verticalConstraints.push({id:'gradient-'+model.verticalConstraints.length,...gradient,type:'climb-or-descent-gradient',status:'review'});
  // A runway-named waypoint is not automatically the runway threshold (MAPt may differ).
  if(!model.profileReferences?.some(p=>model.points.some(point=>point.name===p.target&&point.position))&&/\bRW(?:Y)?\s?\d{2}[LRC]?\b/.test(interpreted.plan.map(r=>r.text).join(' ')))issues.push(issue('runway-waypoint','missing','Referência de pista identificada. Não foi equiparada automaticamente a um MAPt ou waypoint sem coordenada publicada.'));
  issues.push(issue('coverage-review','missing','Prévia parcial: símbolos, transições, aproximação perdida e cobertura integral ainda exigem conferência. Nenhuma missão foi alterada.'));
  return finishModel(model);
}
export function finishModel(model){
  const validation=validateModel(model);model.checks=validation.results;model.issues.push(...validation.issues);
  model.paths=tracePaths(model.points,model.legs.filter(l=>!validation.issues.some(i=>i.entities.includes(l.id))));
  model.topology={convergences:model.points.filter(p=>model.legs.filter(l=>l.to===p.id).length>1).map(p=>({point:p.id,incoming:model.legs.filter(l=>l.to===p.id).map(l=>l.id)})),divergences:model.points.filter(p=>model.legs.filter(l=>l.from===p.id).length>1).map(p=>({point:p.id,outgoing:model.legs.filter(l=>l.from===p.id).map(l=>l.id)}))};
  if(model.paths.length!==1||model.paths.some(p=>p.cycle))model.issues.push(issue('sequence-review','ambiguity','Sequências múltiplas, incompletas ou cíclicas: nenhum ramo foi escolhido automaticamente.'));
  const envelope=toNativeDocument(model);model.native=envelope.document;model.nativeMapping=envelope.mapping;model.issues.push(...envelope.issues);
  model.issues=[...new Map(model.issues.map(i=>[i.id,i])).values()];return model;
}

export function associateLegs(model,interpreted,layout,{truncated=false,airportKnown=true,bindings={}}={}){
  const issues=model.issues;
  const usable=model.points.filter(p=>p.position);
  for(const annotation of interpreted.annotations){
    if(truncated||!airportKnown||(annotation.reference==='magnetic'&&!interpreted.variation)||annotation.reference==='unknown')continue;
    const binding=bindings[annotation.id];
    if(binding){
      const a=model.points.find(p=>p.id===binding.from),b=model.points.find(p=>p.id===binding.to);
      const legId='l-'+binding.from+'-'+binding.to;
      if(!a||!b||a===b)throw Error('Extremidades da perna não reconhecidas.');
      model.legs=model.legs.filter(l=>l.published?.id!==annotation.id&&l.id!==legId);
      model.legs.push({id:legId,type:'line',from:a.id,to:b.id,published:{...annotation},source:{kind:'manual-confirmed-association',decision:binding.decision,evidenceIds:annotation.evidenceIds},status:'manual-confirmed'});
      continue;
    }
    const matches=[],conflicts=[];
    for(const a of usable)for(const b of usable){if(a===b||!supportedLayout(annotation,layout.get(a.id),layout.get(b.id)))continue;
      const measured=inverse(a.position,b.position),course=annotation.reference==='magnetic'?normalize(measured.trueCourse-interpreted.variation.value):measured.trueCourse;
      const courseTolerance=.5+(annotation.reference==='magnetic'?interpreted.variation.resolution/2:0)+1e-6;
      const distanceError=Math.abs(measured.distanceNM-annotation.distanceNM),courseError=angleDifference(course,annotation.course);
      if(courseError<=courseTolerance&&distanceError<=annotation.distanceResolution/2+1e-6)matches.push({a,b,measured});
      else if(courseError<=courseTolerance&&distanceError<Math.max(1,annotation.distanceNM*.1))conflicts.push({a,b,measured});
    }
    if(matches.length===1){const {a,b,measured}=matches[0],legId='l-'+a.id+'-'+b.id;if(!model.legs.some(l=>l.id===legId))model.legs.push({id:legId,type:'line',from:a.id,to:b.id,published:{...annotation},calculated:measured,source:{kind:'coordinates-and-published-course-distance',evidenceIds:annotation.evidenceIds,layoutUsedFor:'association-only'},status:'candidate'});}
    else if(matches.length>1)issues.push(issue('association-'+annotation.id,'ambiguity','A anotação publicada pode ligar mais de um par de pontos.',[],{annotation,options:matches.map(m=>({from:m.a.id,to:m.b.id}))}));
    else if(conflicts.length)issues.push(issue('conflict-'+annotation.id,'inconsistency','Distância publicada incompatível com as coordenadas candidatas. Nenhum fixo foi deslocado.',conflicts.flatMap(m=>[m.a.id,m.b.id]),{annotation,options:conflicts.map(m=>({from:m.a.id,to:m.b.id,measured:m.measured}))}));
    else issues.push(issue('unassociated-'+annotation.id,'missing','Curso/distância reconhecidos sem extremidades determinadas com segurança.',[],{annotation}));
  }
}
