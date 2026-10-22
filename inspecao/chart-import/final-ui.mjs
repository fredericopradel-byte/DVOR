import {distanceDescription,gradientDescription} from './profile-data.mjs';
import {assess,missionSuggestions,prepareApplication} from './finalize.mjs';
export function createFinalReview({container,node,getSession,setBusy,persist,onApplied,message}){
 let snapshot=null,applying=false;
 function render(){
  container.replaceChildren();snapshot=null;const s=getSession();if(!s?.reconstruction)return;const isCurrent=()=>{const active=getSession();return active?.id===s.id&&active.reconstruction===s.reconstruction;};
  try{
   snapshot=window.IVProcedureChart.snapshot();const state=s.finalization||{},selection=state.selection||[],report=assess(s,selection),m=s.reconstruction;
   node('h3',container,'Conferência final');node('p',container,(m.source.chart.procedure?.value||'Procedimento não identificado')+' · '+(m.source.chart.icao?.value||'ICAO pendente')+' · '+(m.source.chart.revision?.value||'Revisão não identificada'));
   node('p',container,report.document.points.length+' pontos · '+report.document.segments.length+' pernas nativas · '+report.resolved+' respostas aplicadas · '+report.critical.length+' pendências críticas.',{id:'chart-final-summary'});
   node('p',container,report.checks.filter(c=>c.passed).length+' verificações geométricas aprovadas / '+report.checks.filter(c=>!c.passed).length+' reprovadas. Não são cálculos de clearance.');
   const restrictions=node('details',container);node('summary',restrictions,'Restrições verticais publicadas · '+m.verticalConstraints.length);
   if(m.publishedProfile){
    for(const a of m.publishedProfile.axes)node('p',restrictions,a.raw+' · '+distanceDescription(a.reference));
    for(const minimum of m.publishedProfile.minima)node('p',restrictions,minimum.type+' '+minimum.value+' ft MSL / OCH '+minimum.ochFT+' ft · '+(minimum.variant||'variante pendente')+' · publicação, não clearance');
    for(const g of m.publishedProfile.gradients)node('p',restrictions,g.value+'% · '+gradientDescription(g.scope)+' · condições a conferir');
    if(m.publishedProfile.conditions.length)node('p',restrictions,m.publishedProfile.conditions.length+' trechos publicados de aproximação perdida com sequenciamento ainda não confirmado.');
   }
   for(const r of m.verticalConstraints)node('p',restrictions,(m.points.find(p=>p.id===r.entity)?.name||r.entity||r.scope||'Gradiente')+': '+(r.lower??r.value??'pendente')+(r.upper!==undefined?' a '+r.upper:'')+' '+r.unit+' · '+(r.qualifier||'qualificador pendente'));
   node('p',restrictions,'Altitudes planejadas e de inspeção permanecem em branco. Fases operacionais não são inferidas. Restrições sem representação nativa ficam na origem da carta e nas pendências.');
   const pending=node('details',container);node('summary',pending,'Pendências e limitações · '+report.issues.length);const list=node('ul',pending);for(const i of report.issues)node('li',list,(i.critical?'Crítica: ':'')+i.message);
   const paths=node('label',container,'Sequência para o perfil vertical');const route=node('select',paths,undefined,{'aria-label':'Sequência para o perfil vertical'});route.add(new Option('Sem sequência escolhida / sequência única automática',''));
   for(const [i,path] of m.paths.entries()){if(path.cycle||!path.legs.every(id=>report.mapping.legs[id]))continue;route.add(new Option(path.legs.map(id=>{const l=m.legs.find(l=>l.id===id);return m.points.find(p=>p.id===l.from)?.name;}).concat(m.points.find(p=>p.id===m.legs.find(l=>l.id===path.legs.at(-1))?.to)?.name||'').join(' → '),String(i)));}
   route.value=selection.length?String(m.paths.findIndex(p=>JSON.stringify(p.legs.flatMap(id=>report.mapping.legs[id]||[]))===JSON.stringify(selection))):'';
   const target=node('label',container,'Destino');const mode=node('select',target,undefined,{'aria-label':'Destino da importação'});mode.add(new Option('Criar nova missão','new'));mode.add(new Option('Aplicar à missão atual','current'));mode.value=state.mode||'new';
   const policyLabel=node('label',container,'Dados identificados na carta');const policy=node('select',policyLabel,undefined,{'aria-label':'Preenchimento da missão'});policy.add(new Option('Preencher somente campos vazios','empty'));policy.add(new Option('Usar os dados da carta nos campos identificados','chart'));policy.value=state.fieldPolicy||'empty';
   const changes=node('div',container,undefined,{id:'chart-final-conflicts'});const suggestions=missionSuggestions(s);
   function describe(){changes.replaceChildren();if(mode.value==='current'){node('p',changes,'O desenho atual será substituído. Uma cópia do planejamento anterior ficará na lista de missões. Os demais dados da missão serão mantidos. Confira os mínimos e parâmetros de inspeção existentes: eles não foram atualizados pela importação.',{class:'ci-warning'});for(const [label,old,value] of [['Título do desenho',snapshot.document.title,report.document.title],['Tipo da carta',snapshot.document.kind,report.document.kind]])if(old!==value)node('p',changes,label+': atual “'+old+'”; carta “'+value+'” → usar identificação da carta no desenho.');for(const [key,value] of Object.entries(suggestions)){const old=snapshot.document.mission[key];if(old&&old!==value)node('p',changes,({icao:'ICAO',local:'Local',runway:'Cabeceira',chart:'Carta',revision:'Revisão'})[key]+': atual “'+old+'”; carta “'+value+'” → '+(policy.value==='chart'?'substituir pelo valor da carta':'manter valor atual'));}}else node('p',changes,'Nova missão com identidade própria. O planejamento anterior ficará preservado na lista de missões.');}
   async function change(redraw=false){if(applying)return;setBusy(true);try{const active=getSession();if(active?.id!==s.id||active.reconstruction!==s.reconstruction)throw Error('Importação alterada. Confira novamente.');active.finalization={mode:mode.value,fieldPolicy:policy.value,selection:route.value===''?[]:m.paths[Number(route.value)].legs.flatMap(id=>report.mapping.legs[id])};describe();await persist();if(redraw)render();}finally{if(isCurrent())setBusy(false);}}
   mode.onchange=policy.onchange=()=>void change().catch(e=>{if(isCurrent())message(e.message,true);});route.onchange=()=>void change(true).catch(e=>{if(isCurrent())message(e.message,true);});describe();
   node('p',container,'Esta confirmação aceita o modelo reconstruído. Não certifica a carta nem comprova vigência. Nenhum arquivo será enviado para serviços externos.',{class:'ci-muted'});
   if(report.critical.length)node('p',container,'Há pendências críticas: somente rascunho não validado. Os elementos não reconstruídos continuarão ausentes e suas pendências permanecerão visíveis no editor.',{class:'ci-warning'});
   const apply=node('button',container,report.canApprove?'Confirmar conjunto e aplicar':'Abrir rascunho não validado no editor',{type:'button',id:'chart-final-apply'});apply.disabled=!report.canApply;
   apply.onclick=async()=>{if(applying)return;applying=true;const reviewedSnapshot=snapshot;setBusy(true);try{
    const current=getSession();if(current?.id!==s.id||current.reconstruction!==s.reconstruction)throw Error('Importação alterada. Confira novamente.');
    const selection=current.finalization?.selection||[];
    const application=await prepareApplication(s,{mode:mode.value,fieldPolicy:policy.value,selection,approve:report.canApprove});
    // Persist the complete review before changing the operational draft. Failed writes block application.
    current.finalization={...(current.finalization||{}),mode:mode.value,fieldPolicy:policy.value,selection,accepted:{at:new Date().toISOString(),fingerprint:application.document.chartImport.approval.fingerprint,validated:report.canApprove}};
    if(getSession()?.id!==s.id||getSession().reconstruction!==s.reconstruction)throw Error('Importação fechada ou alterada. Nenhuma missão foi modificada.');await persist();if(getSession()?.id!==s.id||getSession().reconstruction!==s.reconstruction)throw Error('Importação fechada ou alterada. Nenhuma missão foi modificada.');const result=window.IVProcedureChart.apply(application,reviewedSnapshot);onApplied(result);
   }catch(e){if(isCurrent())message(e.message,true);}finally{applying=false;if(isCurrent())setBusy(false);}};
  }catch(e){node('p',container,e.message,{class:'ci-error'});if(s.finalization?.selection?.length){const reset=node('button',container,'Rever sequência após correção',{type:'button'});reset.onclick=async()=>{setBusy(true);try{s.finalization={...s.finalization,selection:[]};await persist();render();}catch(error){if(isCurrent())message(error.message,true);}finally{if(isCurrent())setBusy(false);}};}}
 }
 return {render};
}
