import {splitProfileLegs} from './profile-association.mjs';
import {interpret} from './decea.mjs';
import {reconstructThreshold} from './profile.mjs';
import {validateModel, associateLegs, finishModel} from './reconstruct.mjs';
import {position, inverse, destination} from './geodesy.mjs';

const clone=value=>structuredClone(value);
const problem=(id,message,entities=[])=>({id,category:'inconsistency',critical:true,message,entities});
const binding=m=>({sha256:m.source.sha256,page:m.source.page,module:m.module});
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
export function pointSubject(p){return {position:p.position,source:p.coordinateSource};}
function legSubject(m,l){return {from:pointSubject(m.points.find(p=>p.id===l.from)),to:pointSubject(m.points.find(p=>p.id===l.to)),published:l.published};}
const category={missing:'Dado ausente',ambiguity:'Ambiguidade',inconsistency:'Inconsistência'};
function priority(i){return /^(coordinate-|published-coordinate-|magnetic-reference)/.test(i.id)?0:/^(association-|unassociated-|conflict-|geometry-)/.test(i.id)?1:/^(qualifier-|altitude-|profile-altitude-)/.test(i.id)?2:/^visual-boundary-/.test(i.id)?3:/^(date-|derived-)/.test(i.id)?4:8;}
export function pendingGroups(model){
  const groups=new Map();
  for(const issue of model.issues){const entity=issue.entities?.[0],key=issue.category+':'+(entity||issue.id),leg=model.legs.find(l=>l.id===entity),name=model.points.find(p=>p.id===entity)?.name||(leg?(model.points.find(p=>p.id===leg.from)?.name||'Início')+' → '+(model.points.find(p=>p.id===leg.to)?.name||'Fim'):'');
    if(!groups.has(key))groups.set(key,{id:key,label:(name?name+' · ':'')+(category[issue.category]||'Conferência'),issues:[],priority:priority(issue)});
    const g=groups.get(key);g.issues.push(issue);g.priority=Math.min(g.priority,priority(issue));
  }
  return [...groups.values()].sort((a,b)=>a.priority-b.priority||a.id.localeCompare(b.id));
}
export function question(model,issue){
  const entity=issue.entities?.[0],point=model.points.find(p=>p.id===entity);
  if(point&&/^(coordinate-|published-coordinate-|chart-base-coordinate-|threshold-database-ambiguity|threshold-source-conflict)/.test(issue.id))return {kind:'position',entity,options:[...(issue.options||point.candidates||[]),...(point.databaseCandidates||[]),...(point.coordinatePublications||[]).filter(p=>p.datum==='WGS84')].filter(p=>position(p.position))};
  if(point&&/^(date-|derived-|threshold-database-review)/.test(issue.id))return {kind:'confirm-coordinate',entity,subject:pointSubject(point)};
  if(point&&/^(qualifier-|altitude-|profile-altitude-)/.test(issue.id))return {kind:'altitude',entity,constraint:model.verticalConstraints.find(r=>r.entity===entity)||null};
  if(issue.id==='magnetic-reference')return {kind:'reference'};
  const leg=model.legs.find(l=>l.id===entity);
  if(issue.id.startsWith('visual-boundary-')&&leg)return {kind:'visual',entity,subject:legSubject(model,leg),distanceNM:leg.published.distanceNM,options:(model.profileReferences?.[0]?.distanceMarks||[]).filter(m=>m.distanceNM>0&&m.distanceNM<leg.published.distanceNM)};
  if(issue.annotation||leg?.published&&/^(geometry-|definition-)/.test(issue.id))return {kind:'leg',annotation:issue.annotation||leg.published,options:issue.options||(leg?[{from:leg.from,to:leg.to}]:[])};
  return {kind:'information'};
}
function ledger(model){
  if(model.reviewWork)return checkedLedger(model);
  const base=clone(model);delete base.native;delete base.nativeMapping;delete base.reviewWork;
  return {version:1,binding:binding(model),base,nodes:[],head:null,outcomes:[]};
}
export function checkedLedger(model){
  const w=model.reviewWork;
  if(!w||w.version!==1||!same(w.binding,binding(model))||!same(binding(w.base),w.binding)||!Array.isArray(w.nodes)||!Array.isArray(w.outcomes)||w.base.reviewWork||w.nodes.length>1000)throw Error('Histórico incompatível com a carta, página ou módulo. Dados preservados.');
  validateModel(w.base);const seen=new Set();
  for(const n of w.nodes){if(typeof n.id!=='string'||seen.has(n.id)||(n.parent!==null&&!seen.has(n.parent))||!['position','confirm-coordinate','altitude','reference','leg','visual'].includes(n.kind)||typeof n.issueId!=='string'||typeof n.answer!=='object'||n.answer===null||typeof n.at!=='string')throw Error('Histórico de decisões inválido.');seen.add(n.id);}
  if(w.head!==null&&!seen.has(w.head))throw Error('Posição do histórico inválida.');return w;
}
export function activeNodes(w){let at=w.head;const map=new Map(w.nodes.map(n=>[n.id,n])),out=[];while(at!==null){const n=map.get(at);if(!n)throw Error('Decisão inexistente.');out.unshift(n);at=n.parent;}return out;}
function number(raw,min,max){if(typeof raw!=='string'&&typeof raw!=='number'||String(raw).trim()==='')throw Error('Preencha o valor indispensável.');const n=Number(raw);if(!Number.isFinite(n)||n<min||n>max)throw Error('Valor fora dos limites do editor.');return n;}
function numeric(raw,min,max){const value=number(raw,min,max),s=String(raw).trim();if(!/^[+-]?\d+(?:\.\d{1,9})?$/.test(s))throw Error('Use número decimal, sem unidades, com até nove casas.');return {value,resolution:s.includes('.')?10**(-s.split('.')[1].length):1,raw:s};}
function action(model,issueId,kind,answer){
  const i=model.issues.find(i=>i.id===issueId);if(!i)throw Error('Esta pendência já mudou. Selecione a pendência atual.');
  const q=question(model,i);
  if(kind!==q.kind){if(kind!=='position'||!i.entities?.includes(answer.entity))throw Error('Resposta incompatível com esta pendência.');}
  const a=clone(answer);let subject=null;
  if(kind==='position'){
    a.entity=a.entity||q.entity;if(!model.points.some(p=>p.id===a.entity))throw Error('Ponto inexistente.');
    delete a.selectedSource;
    if(a.choice!==undefined){const row=q.options?.[a.choice];if(q.kind!=='position'||!Number.isInteger(a.choice)||!position(row?.position))throw Error('Fonte selecionada não reconhecida.');a.lat=row.position.lat;a.lon=row.position.lon;a.selectedSource=clone(row.source||{kind:'chart-published-coordinate',raw:row.raw,datum:row.datum});}
    a.lat=number(a.lat,-88.999999999,88.999999999);a.lon=number(a.lon,-180,180);if(!position({lat:a.lat,lon:a.lon}))throw Error('Coordenada WGS84 inválida.');
    if(!String(a.origin||'').trim())throw Error('Informe a origem da coordenada.');a.origin=String(a.origin).slice(0,500);
  }else if(kind==='altitude'){
    a.entity=q.entity;if(!['at','above','below','between'].includes(a.qualifier))throw Error('Escolha o qualificador publicado.');a.value=number(a.value,-60000,60000);
    if(a.qualifier==='between'){a.upper=number(a.upper,-60000,60000);if(a.upper<a.value)throw Error('Janela de altitude invertida.');}else delete a.upper;
  }else if(kind==='reference'){
    if(!['true','magnetic'].includes(a.reference))throw Error('Escolha a referência publicada.');
    if(a.reference==='magnetic')a.variation=numeric(a.variation,-180,180);
  }else if(kind==='leg'){
    a.annotation=q.annotation.id;if(!a.annotation)throw Error('Sem definição textual da perna.');
    if(!model.points.some(p=>p.id===a.from)||!model.points.some(p=>p.id===a.to)||a.from===a.to)throw Error('Selecione início e fim distintos.');
    a.course=numeric(a.course,0,360);a.distance=numeric(a.distance,.000000001,500);
    if(!['true','magnetic'].includes(a.reference))throw Error('Referência do curso ausente.');
  }else if(kind==='visual'){
    a.entity=q.entity;a.distanceNM=number(a.distanceNM,.000000001,q.distanceNM);subject=q.subject;
  }else if(kind==='confirm-coordinate'){a.entity=q.entity;subject=q.subject;}
  return {kind,issueId,answer:a,subject};
}
function scrub(model){
  // Regenerate only checks/associations whose inputs can change. Coverage and
  // unsupported structures are never cleared by a generic acknowledgement.
  const dynamic=/^(profile-split-|profile-route-|coordinate-|association-|unassociated-|conflict-|geometry-|definition-|endpoints-|native-|projection-|range-|sequence-review$|qualifier-|derived-|threshold-|visual-boundary-)/;
  model.issues=model.issues.filter(i=>i.id.startsWith('threshold-database-')||!dynamic.test(i.id));
  for(const p of model.points)if(p.coordinateSource?.kind==='chart-derived'){p.position=null;p.coordinateState='missing';p.coordinateSource=null;}
}
function setPosition(model,n){const a=n.answer,p=model.points.find(p=>p.id===a.entity);if(!p||!position({lat:a.lat,lon:a.lon})||!a.origin)throw Error('Coordenada ou origem ausente.');
  p.position={lat:a.lat,lon:a.lon};p.coordinateState='manual-confirmed';p.coordinateSource={kind:'manual-confirmed',decision:n.id,origin:a.origin,...(a.selectedSource?{selectedSource:clone(a.selectedSource)}:{}),originalPosition:clone(p.position)};p.candidates=[];
  model.issues=model.issues.filter(i=>!i.entities?.includes(p.id)||!(/^(date-|published-coordinate-|chart-base-coordinate-|threshold-database-)/.test(i.id)));
}
function setAltitude(model,n){const a=n.answer;if(!model.points.some(p=>p.id===a.entity)||!['at','above','below','between'].includes(a.qualifier)||!Number.isFinite(a.value)||Math.abs(a.value)>60000||(a.qualifier==='between'&&(!Number.isFinite(a.upper)||a.upper<a.value)))throw Error('Restrição vertical inválida.');
  const prior=model.verticalConstraints.find(r=>r.entity===a.entity),evidence=prior?.evidenceIds||[];
  model.verticalConstraints=model.verticalConstraints.filter(r=>r.entity!==a.entity);
  model.verticalConstraints.push({id:prior?.id||'manual-altitude-'+a.entity,entity:a.entity,value:a.value,...(a.upper!==undefined?{upper:a.upper}:{}),qualifier:a.qualifier,unit:'FT',reference:'MSL',source:'manual-confirmed',decision:n.id,evidenceIds:evidence});
  model.issues=model.issues.filter(i=>!i.entities?.includes(a.entity)||!(/^(altitude-|profile-altitude-)/.test(i.id)));
}
function splitVisual(model,n){const a=n.answer,leg=model.legs.find(l=>l.id===a.entity);if(!leg||!same(n.subject,legSubject(model,leg)))throw Error('A final mudou. Confirme novamente o limite visual.');
  const d=number(a.distanceNM,.000000001,leg.published.distanceNM),whole=leg.published.distanceNM,from=model.points.find(p=>p.id===leg.from),to=model.points.find(p=>p.id===leg.to);
  if(!from.position||!to.position)throw Error('Final sem coordenadas suficientes.');
  const visualReference={kind:'manual-confirmed-visual-boundary',distanceToEndNM:d,evidenceIds:leg.visualReference?.evidenceIds||[],decision:n.id};
  if(d===whole){leg.flightRules='visual';leg.visualReference=visualReference;return;}
  const measured=inverse(from.position,to.position),coordinate=destination(from.position,measured.trueCourse,measured.distanceNM*(whole-d)/whole),id=leg.id+'-visual-start';
  if(model.points.some(p=>p.id===id))throw Error('Identificação de limite visual duplicada.');
  model.points.push({id,name:'INÍCIO VISUAL',roles:[],position:coordinate,coordinateState:'manual-derived',coordinateSource:{kind:'manual-derived',decision:n.id,originalPosition:clone(coordinate)},evidenceIds:visualReference.evidenceIds});
  const before={...clone(leg),id:leg.id+'-before-visual',to:id,flightRules:'unclassified',visualReference:undefined,published:{...leg.published,distanceNM:whole-d},source:{...leg.source,decision:n.id,originalLeg:leg.id}};
  const visual={...clone(leg),id:leg.id+'-visual',from:id,flightRules:'visual',visualReference,published:{...leg.published,distanceNM:d},source:{...leg.source,decision:n.id,originalLeg:leg.id}};
  model.legs=model.legs.filter(l=>l.id!==leg.id);model.legs.push(before,visual);
}
export function replayReview(model,session,work=ledger(model)){
  if(!same(binding(model),{sha256:session.source.sha256,page:session.page,module:session.module})||!same(work.binding,binding(model)))throw Error('Decisões pertencem a outra carta, página ou módulo.');
  const m=clone(work.base),p=interpret(session.extraction,session.recognition),nodes=activeNodes(work),outcomes=[],deferred=[],bindings={};
  scrub(m);if(m.profileGeometry)m.profileGeometry={parents:[]};
  for(const n of nodes){try{
    const a=n.answer;
    if(n.kind==='position')setPosition(m,n);
    else if(n.kind==='altitude')setAltitude(m,n);
    else if(n.kind==='reference'){
      if(!['true','magnetic'].includes(a.reference))throw Error('Referência inválida.');
      m.reference.course=p.reference=a.reference;
      if(a.reference==='magnetic'){number(a.variation.value,-180,180);number(a.variation.resolution,.000000001,1);m.reference.variation=p.variation={value:a.variation.value,resolution:a.variation.resolution,origin:'manual-confirmed',decision:n.id};}
      for(const t of p.annotations)t.reference=a.reference;
      m.issues=m.issues.filter(i=>i.id!=='magnetic-reference');
    }else if(n.kind==='leg'){
      const annotation=p.annotations.find(t=>t.id===a.annotation);if(!annotation)throw Error('Anotação da carta não encontrada.');
      number(a.course.value,0,360);number(a.distance.value,.000000001,500);number(a.course.resolution,.000000001,1);number(a.distance.resolution,.000000001,1);if(!['magnetic','true'].includes(a.reference))throw Error('Referência inválida.');
      Object.assign(annotation,{course:a.course.value,courseResolution:a.course.resolution,distanceNM:a.distance.value,distanceResolution:a.distance.resolution,reference:a.reference,association:{from:a.from,to:a.to}});
      bindings[annotation.id]={from:a.from,to:a.to,decision:n.id};
    }else {deferred.push(n);continue;}
    outcomes.push({id:n.id,applied:true});
  }catch(e){outcomes.push({id:n.id,applied:false,reason:e.message});m.issues.push(problem('decision-'+n.id,e.message,n.answer.entity?[n.answer.entity]:[]));}}
  const oldLegs=m.legs;m.legs=oldLegs.filter(l=>l.type!=='line'||!l.published?.id);
  const layout=new Map(m.points.map(point=>[point.id,p.plan.filter(r=>new RegExp('(^|[^A-Z0-9])'+point.name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'([^A-Z0-9]|$)').test(r.text))]));
  associateLegs(m,p,layout,{truncated:session.extraction.truncated,bindings});
  if(!m.issues.some(i=>i.id==='threshold-database-ambiguity'))reconstructThreshold(m,p,{thresholds:[]},{truncated:session.extraction.truncated});
  splitProfileLegs(m);
  for(const point of m.points){
    if(!point.position&&!m.issues.some(i=>i.id==='coordinate-'+point.id))m.issues.push({id:'coordinate-'+point.id,category:point.candidates?.length?'ambiguity':'missing',critical:true,message:'Coordenada de '+point.name+' ainda não determinada.',entities:[point.id],options:point.candidates||[]});
    const s=point.coordinateSource?.selectedSource||point.coordinateSource,date=m.source.chart.publishedDate?.value;
    if(s?.kind==='local-database'&&date&&((s.validFrom&&s.validFrom.slice(0,10)>date)||(s.validTo&&s.validTo.slice(0,10)<date))&&!m.issues.some(i=>i.id==='date-'+point.id))m.issues.push(problem('date-'+point.id,'Conferir a edição da coordenada de '+point.name+' em relação à carta.',[point.id]));
  }
  for(const r of m.verticalConstraints)if(r.qualifier==='unspecified')m.issues.push({id:'qualifier-'+r.id,category:'ambiguity',critical:true,message:'Confirme o qualificador da altitude publicada.',entities:[r.entity]});
  for(const n of deferred){try{
    if(n.kind==='visual'){
      splitVisual(m,n);m.issues=m.issues.filter(i=>i.id!=='visual-boundary-'+n.answer.entity);
    }else{
      const point=m.points.find(p=>p.id===n.answer.entity);if(!point||!same(n.subject,pointSubject(point)))throw Error('A coordenada/origem mudou. Confira novamente esta decisão.');
      m.issues=m.issues.filter(i=>!(['date-'+point.id,'derived-'+point.id].includes(i.id)||i.id==='threshold-database-review'&&i.entities?.includes(point.id)));if(point.coordinateState==='derived-review')point.coordinateState='derived-confirmed';
    }
    outcomes.push({id:n.id,applied:true});
  }catch(e){outcomes.push({id:n.id,applied:false,reason:e.message});m.issues.push(problem('decision-'+n.id,e.message,[n.answer.entity]));}}
  // Restored archives retain the unverified-source warning even if their original
  // baseline predates that warning. Decisions never grant final approval.
  if(model.issues.some(i=>i.id==='archive-review')&&!m.issues.some(i=>i.id==='archive-review'))m.issues.push(clone(model.issues.find(i=>i.id==='archive-review')));
  m.review={validated:false};m.status='partial';m.reviewWork={...clone(work),outcomes};return finishModel(m);
}
export function decide(model,session,issueId,kind,answer){
  const w=clone(ledger(model));if(w.nodes.length>=1000)throw Error('Histórico chegou ao limite de 1000 decisões. Exporte o rascunho para preservá-lo.');
  const a=action(model,issueId,kind,answer);const n={...a,id:crypto.randomUUID(),parent:w.head,at:new Date().toISOString()};w.nodes.push(n);w.head=n.id;return replayReview(model,session,w);
}
export function checkout(model,session,head){const w=clone(ledger(model));if(head!==null&&!w.nodes.some(n=>n.id===head))throw Error('Decisão não encontrada.');w.head=head;return replayReview(model,session,w);}
export function historyStep(model,session,direction){const w=ledger(model),n=w.nodes.find(n=>n.id===w.head),head=direction==='undo'?n?.parent:w.nodes.filter(n=>n.parent===w.head).at(-1)?.id;if(head===undefined)return model;return checkout(model,session,head);}
export function evidenceFor(issue,model,extraction){
  const ids=new Set([...(issue.evidenceIds||[]),...(issue.annotation?.evidenceIds||[])]);
  for(const entity of issue.entities||[]){const point=model.points.find(p=>p.id===entity),leg=model.legs.find(l=>l.id===entity);for(const id of [...(point?.evidenceIds||[]),...(point?.coordinateSource?.evidenceIds||[]),...(leg?.published?.evidenceIds||[]),...(leg?.visualReference?.evidenceIds||[])])ids.add(id);for(const r of model.verticalConstraints.filter(r=>r.entity===entity))for(const id of r.evidenceIds||[])ids.add(id);}
  return extraction.text.filter(t=>ids.has(t.id));
}
