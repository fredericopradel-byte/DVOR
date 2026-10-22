import {validateModel} from './reconstruct.mjs';
import {toNativeDocument} from './native.mjs';
const clone=x=>structuredClone(x);
export function missionSuggestions(session){const m=session.recognition?.metadata||session.reconstruction?.source.chart||{},value=k=>m[k]?.value||'';return Object.fromEntries(Object.entries({icao:value('icao'),local:value('airport'),runway:value('runway'),chart:value('procedure'),revision:value('revision')}).filter(([,v])=>v));}
export function assess(session,selection=[]){
 const m=session.reconstruction;if(!m||m.module!==session.module||m.source.sha256!==session.source.sha256||m.source.page!==session.page)throw Error('Modelo incompatível com a importação.');
 const validation=validateModel(m),copy=clone(m);copy.checks=validation.results;const envelope=toNativeDocument(copy);
 const issues=[...new Map([...(m.issues||[]),...validation.issues,...envelope.issues].map(i=>[i.id,i])).values()];
 const route=selection.length?selection:envelope.document.flight.segments;
 let cursor='',start='';const seen=new Set();for(const id of route){const leg=envelope.document.segments.find(l=>l.id===id);if(!leg||seen.has(id)||cursor&&leg.from!==cursor)throw Error('Sequência selecionada desconectada ou duplicada.');if(!start)start=leg.from;cursor=leg.to;seen.add(id);}
 if(route.length)envelope.document.flight={start,end:cursor,segments:[...route]};
 if(!route.length)issues.push({id:'final-route',critical:true,message:'Selecione uma sequência contínua para o perfil vertical.'});
 // A selection is an operational route; it does not prove that omitted branches were reconstructed.
 if(!envelope.document.segments.length)issues.push({id:'final-empty',critical:true,message:'Nenhuma perna nativa disponível para aplicar.'});
 const classified=['IAC','SID'].includes(m.source.chart.kind?.value);if(!classified)issues.push({id:'final-kind',critical:true,message:'Tipo de carta ausente ou não suportado. Confirme IAC/SID antes de aplicar; nenhum tipo foi presumido.'});
 const nav=session.recognition?.navigation||[];
 if(session.module==='ndb'&&(!nav.includes('NDB')||m.source.chart.kind?.value!=='IAC'))issues.push({id:'module-compatibility',critical:true,message:'O módulo NDB não cobre a inspeção específica desta carta. A geometria pode ser aberta somente como rascunho, preservando sua identificação original.'});
 for(const r of m.verticalConstraints||[])if(!envelope.document.restrictions[r.entity]||!['at','above','below','between'].includes(r.qualifier)||r.unit!=='FT'||r.reference!=='MSL'||envelope.document.restrictions[r.entity]?.altitude!==String(r.lower??r.value)||(r.qualifier==='between'&&envelope.document.restrictions[r.entity]?.upperAltitude!==String(r.upper)))issues.push({id:'final-vertical-'+r.id,critical:true,message:'Restrição vertical '+r.id+' sem representação nativa confirmada; dado original preservado na origem da carta.'});
 const critical=issues.filter(i=>i.critical);return {document:envelope.document,mapping:envelope.mapping,issues,critical,canApprove:critical.length===0,canApply:classified&&envelope.document.segments.length>0,checks:validation.results,resolved:m.reviewWork?.outcomes?.filter(o=>o.applied).length||0,route};
}
export async function fingerprint(session,selection=[]){const data={source:session.source.sha256,page:session.page,module:session.module,model:session.reconstruction,selection};const bytes=new TextEncoder().encode(JSON.stringify(data));return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(b=>b.toString(16).padStart(2,'0')).join('');}
export async function prepareApplication(session,{mode='new',fieldPolicy='empty',selection=[],approve=false}={}){
 if(!['new','current'].includes(mode)||!['empty','chart'].includes(fieldPolicy))throw Error('Destino inválido.');
 const report=assess(session,selection);if(!report.canApply)throw Error('Ainda não há geometria aplicável.');if(approve&&!report.canApprove)throw Error('Pendências críticas impedem a aprovação. Salve ou abra como rascunho não validado.');
 const d=report.document,m=session.reconstruction;
 d.chartImport={version:1,module:session.module,sessionId:session.id,source:{...clone(session.source),page:session.page,chart:clone(m.source.chart)},provenance:{points:clone(m.points),legs:clone(m.legs),verticalConstraints:clone(m.verticalConstraints),publishedProfile:clone(m.publishedProfile||null),profileGeometry:clone(m.profileGeometry||null),dmeArcs:clone(m.dmeArcs||null),reference:clone(m.reference),database:clone(m.database),mapping:clone(report.mapping),decisions:clone(m.reviewWork?.nodes||[]),decisionHead:m.reviewWork?.head??null,decisionOutcomes:clone(m.reviewWork?.outcomes||[])},pending:clone(report.issues),checks:clone(report.checks),approval:{validated:approve,at:new Date().toISOString(),fingerprint:await fingerprint(session,selection),meaning:'Aceitação do modelo pelo usuário; não certifica a carta nem sua vigência.'},baseline:null,modifications:[],review:{validated:approve}};
 return {document:d,suggestions:missionSuggestions(session),mode,fieldPolicy,report:{critical:report.critical.length,resolved:report.resolved}};
}
