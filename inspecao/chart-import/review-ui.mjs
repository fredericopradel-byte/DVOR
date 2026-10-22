import {pendingGroups, question, decide, historyStep, checkout, evidenceFor, activeNodes} from './review.mjs';
const labels={'confirm-arc':'Representação horizontal do arco DME',position:'Coordenada',altitude:'Altitude',reference:'Referência dos cursos',leg:'Associação da perna',visual:'Limite visual','confirm-coordinate':'Conferência da coordenada'};
const raw=(n,r=1)=>Number(n).toFixed(Math.max(0,Math.min(9,Math.round(-Math.log10(r)))));
export function createReview({container,node,original,getSession,onModel,isBusy}){
  let selected=null;
  function button(parent,label,fn){const b=node('button',parent,label,{type:'button'});b.onclick=fn;b.disabled=isBusy();return b;}
  function input(parent,label,value='',attributes={}){const l=node('label',parent,label),i=node('input',l,undefined,{...attributes,value:String(value),'aria-label':label});return i;}
  function select(parent,label,options,value=''){const l=node('label',parent,label),s=node('select',l,undefined,{'aria-label':label});for(const [v,text]of options)s.add(new Option(text,v));s.value=value;return s;}
  function focusCurrent(){const h=container.querySelector('h3');if(h&&container.getBoundingClientRect().height){h.style.scrollMarginTop=((container.parentElement.querySelector('.ci-mobile-tabs')?.getBoundingClientRect().height||100)+16)+'px';h.focus({preventScroll:true});h.scrollIntoView({block:'start'});}}
  async function update(make,nextIssue=selected){if(isBusy())return;try{const s=getSession();const m=make(s);selected=nextIssue;await onModel(m);focusCurrent();}
    catch(e){const note=container.querySelector('[data-review-message]');if(note){note.textContent=e.message;note.className='ci-error';}}
  }
  function answer(kind,payload){return update(s=>decide(s.reconstruction,s,selected,kind,payload));}
  function comparison(issue,model,session,parent){
    const compare=node('div',parent,undefined,{class:'ci-review-comparison'}),source=node('figure',compare),target=node('figure',compare);
    node('figcaption',source,'Trecho da carta · página '+session.page);const crop=node('canvas',source,undefined,{id:'chart-issue-source','aria-label':'Recorte da carta referente à pendência'});
    const evidence=evidenceFor(issue,model,session.extraction),W=session.extraction.width,H=session.extraction.height;
    if(original.width&&original.height){
      const boxes=evidence.map(t=>t.bbox).filter(b=>b?.length===4&&b.every(Number.isFinite));let x=0,y=0,w=W,h=H;
      if(boxes.length){x=Math.max(0,Math.min(...boxes.map(b=>b[0]))-12);y=Math.max(0,Math.min(...boxes.map(b=>b[1]))-12);w=Math.min(W-x,Math.max(40,Math.max(...boxes.map(b=>b[0]+b[2]))-x+12));h=Math.min(H-y,Math.max(30,Math.max(...boxes.map(b=>b[1]+b[3]))-y+12));}
      const scale=Math.min(2,600/w,450/h);crop.width=Math.max(1,Math.ceil(w*scale));crop.height=Math.max(1,Math.ceil(h*scale));
      const ctx=crop.getContext('2d');ctx.drawImage(original,x*original.width/W,y*original.height/H,w*original.width/W,h*original.height/H,0,0,crop.width,crop.height);
      ctx.strokeStyle='#b65d00';ctx.lineWidth=1.5;for(const b of boxes)ctx.strokeRect((b[0]-x)*scale,(b[1]-y)*scale,b[2]*scale,b[3]*scale);
      if(!boxes.length)node('p',source,'Sem recorte específico identificado; carta inteira para conferência.',{class:'ci-muted'});
    }else node('p',source,'Reabra a carta para exibir sua imagem.');
    if(evidence.length){const d=node('details',source);node('summary',d,'Texto de origem');node('p',d,evidence.map(t=>t.text).join(' '));}
    node('figcaption',target,'Elemento no desenho · prévia não validada');
    if(!model.native.points.length){node('p',target,'Sem coordenadas para destacar este elemento.');return;}
    const svg=window.IVProcedurePreview.render(model.native);svg.id='chart-issue-drawing';target.append(svg);
    const ids=new Set(issue.entities||[]);for(const option of issue.options||[]){if(option.from)ids.add(option.from);if(option.to)ids.add(option.to);}
    for(const leg of model.legs.filter(l=>ids.has(l.id))){ids.add(leg.from);ids.add(leg.to);ids.add(leg.center);for(const id of leg.via||[])ids.add(id);for(const id of model.nativeMapping?.legs?.[leg.id]||[])ids.add(id);}
    const focus=[];
    for(const g of svg.querySelectorAll('g[data-point]'))if(ids.has(g.dataset.point)){
      const c=g.querySelector('circle'),x=Number(c.getAttribute('cx')),y=Number(c.getAttribute('cy'));focus.push({x,y});
      const halo=document.createElementNS('http://www.w3.org/2000/svg','circle');for(const [k,v]of Object.entries({cx:x,cy:y,r:15,fill:'none',stroke:'#ffd49a','stroke-width':3,'data-issue-highlight':g.dataset.point}))halo.setAttribute(k,v);g.append(halo);
    }
    for(const g of svg.querySelectorAll('g[data-segment]'))if(ids.has(g.dataset.segment))for(const path of g.querySelectorAll('path'))if(path.getAttribute('stroke')!=='transparent'){path.setAttribute('stroke','#ffd49a');path.setAttribute('stroke-width','4');g.dataset.issueHighlight=g.dataset.segment;}
    if(focus.length){const xs=focus.map(p=>p.x),ys=focus.map(p=>p.y),x=Math.min(...xs)-60,y=Math.min(...ys)-60,w=Math.max(160,Math.max(...xs)-x+60),h=Math.max(140,Math.max(...ys)-y+60);svg.setAttribute('viewBox',[x,y,w,h].join(' '));svg.dataset.focused='true';}
    else node('p',target,'Sem posição específica disponível para esta pendência.',{class:'ci-muted'});
  }
  function form(q,issue,m,parent){
    const actions=node('div',parent,undefined,{class:'ci-review-form'});
    if(q.kind==='position'){
      if(/^dme-(radius|via)-/.test(issue.id))for(const id of issue.entities||[])if(id!==q.entity&&m.points.some(p=>p.id===id))button(actions,'Conferir coordenada de '+m.points.find(p=>p.id===id).name,()=>{actions.replaceChildren();form({kind:'position',entity:id,options:[]},issue,m,actions);});
      node('p',actions,'Coordenadas WGS84 em graus decimais. Não use pixels da carta. A fonte anterior ficará preservada no histórico.');
      for(const [index,row]of(q.options||[]).entries())button(actions,(row.name||row.designator||'Coordenada publicada')+' · '+row.position.lat+', '+row.position.lon+' · '+(row.source?.version||row.datum||'fonte local')+(row.source?.validFrom?' · edição '+row.source.validFrom.slice(0,10):''),()=>answer('position',{entity:q.entity,lat:row.position.lat,lon:row.position.lon,origin:row.source?'Base local · '+(row.source.version||'cadastro')+' · registro '+(row.source.recordId||row.id||'selecionado'):'Coordenada WGS84 publicada · '+(row.raw||'conferida na carta'),choice:index}));
      const point=m.points.find(p=>p.id===q.entity),lat=input(actions,'Latitude',point?.position?.lat??'',{type:'text',inputmode:'text',maxlength:'32'}),lon=input(actions,'Longitude',point?.position?.lon??'',{type:'text',inputmode:'text',maxlength:'32'}),origin=input(actions,'Origem da coordenada','',{type:'text',maxlength:'500'});
      button(actions,'Usar coordenada conferida',()=>answer('position',{entity:q.entity,lat:lat.value,lon:lon.value,origin:origin.value}));
    }else if(q.kind==='confirm-arc'){
      const leg=m.legs.find(l=>l.id===q.entity),name=id=>m.points.find(p=>p.id===id)?.name||id;
      node('p',actions,[leg.from,...(leg.via||[]),leg.to].map(name).join(' → ')+' · '+(leg.turn==='right'?'direita':'esquerda')+' · auxílio '+name(leg.center));
      node('p',actions,'DME publicado: '+leg.publishedDME.raw.join(' / ')+'. Raio horizontal calculado das coordenadas: '+leg.radiusNM.toFixed(4)+' NM. Os valores e coordenadas de origem permanecem preservados.');
      node('p',actions,'A curva é uma representação horizontal para edição. Não calcula a distância inclinada em cada altitude nem certifica o seguimento do arco DME. Confira também as conexões e eventuais fixos intermediários.',{class:'ci-warning'});
      button(actions,'Aceitar representação horizontal neste rascunho',()=>answer('confirm-arc',{}));
      for(const id of [...new Set([leg.center,leg.from,...(leg.via||[]),leg.to])])button(actions,'Corrigir coordenada de '+name(id),()=>{actions.replaceChildren();form({kind:'position',entity:id,options:[]},issue,m,actions);});
    }else if(q.kind==='confirm-coordinate'){
      node('p',actions,'Confira a origem e a posição no conjunto. Aceitar para este rascunho não comprova vigência nem transforma uma coordenada derivada em oficial.');
      button(actions,'Aceitar coordenada neste rascunho',()=>answer(q.kind,{}));
    }else if(q.kind==='altitude'){
      const qualifier=select(actions,'Restrição publicada',[['at','Exatamente'],['above','Mínima'],['below','Máxima'],['between','Janela']],q.constraint?.qualifier==='unspecified'?'':q.constraint?.qualifier||'');qualifier.insertBefore(new Option('Selecionar',''),qualifier.firstChild);if(!q.constraint||q.constraint.qualifier==='unspecified')qualifier.value='';
      const value=input(actions,'Altitude publicada (FT MSL)',q.constraint?.value??q.constraint?.lower??'',{type:'number',step:'any',inputmode:'decimal'}),upper=input(actions,'Limite superior (FT MSL)',q.constraint?.upper??'',{type:'number',step:'any',inputmode:'decimal'});
      const visible=()=>{upper.parentElement.hidden=qualifier.value!=='between';};qualifier.onchange=visible;visible();
      button(actions,'Confirmar restrição',()=>answer('altitude',{qualifier:qualifier.value,value:value.value,upper:upper.value}));
      node('p',actions,'Não altera altitude planejada, de inspeção ou clearance.',{class:'ci-muted'});
    }else if(q.kind==='reference'){
      const reference=select(actions,'Referência publicada',[['','Selecionar'],['magnetic','Magnética'],['true','Verdadeira']],m.reference.course);
      const variation=input(actions,'VAR publicada (graus; oeste negativo)',m.reference.variation?.value??'',{type:'text',inputmode:'text',maxlength:'32'});
      reference.onchange=()=>{variation.parentElement.hidden=reference.value!=='magnetic';};reference.onchange();
      button(actions,'Confirmar referência dos cursos',()=>answer('reference',{reference:reference.value,variation:variation.value}));
    }else if(q.kind==='leg'){
      const a=q.annotation,choose=(option,course=raw(a.course,a.courseResolution),distance=raw(a.distanceNM,a.distanceResolution),reference=a.reference)=>answer('leg',{from:option.from,to:option.to,course,distance,reference});
      node('p',actions,'Carta: '+raw(a.course,a.courseResolution)+'° '+a.reference+' · '+raw(a.distanceNM,a.distanceResolution)+' NM.');
      for(const option of q.options||[])if(option.measured)node('p',actions,'Coordenadas candidatas: '+option.measured.distanceNM.toFixed(3)+' NM · curso verdadeiro '+option.measured.trueCourse.toFixed(3)+'°. Confira a origem antes de corrigir.');
      for(const option of q.options||[])button(actions,(m.points.find(p=>p.id===option.from)?.name||option.from)+' → '+(m.points.find(p=>p.id===option.to)?.name||option.to)+(issue.category==='inconsistency'?' · conferir valores abaixo':''),()=>choose(option));
      const options=[['','Selecionar'],...m.points.map(p=>[p.id,p.name])],from=select(actions,'Início',options,q.options?.[0]?.from||''),to=select(actions,'Fim',options,q.options?.[0]?.to||''),course=input(actions,'Curso publicado (graus)',raw(a.course,a.courseResolution),{type:'number',step:'any',inputmode:'decimal'}),distance=input(actions,'Distância publicada (NM)',raw(a.distanceNM,a.distanceResolution),{type:'number',step:'any',inputmode:'decimal'}),reference=select(actions,'Referência',[['magnetic','Magnética'],['true','Verdadeira'],['unknown','Não determinada']],a.reference);
      button(actions,'Usar definição conferida',()=>choose({from:from.value,to:to.value},course.value,distance.value,reference.value));
      node('p',actions,'Os valores originais são preservados. Uma resposta geometricamente inconsistente continuará pendente.');
      for(const id of issue.entities||[]){const point=m.points.find(p=>p.id===id);if(point)button(actions,'Corrigir coordenada de '+point.name,()=>{actions.replaceChildren();form({kind:'position',entity:id,options:point.candidates||[]},issue,m,actions);});}
    }else if(q.kind==='visual'){
      node('p',actions,'Confirme a extensão do trecho visual a partir do fim desta perna. O trecho anterior ficará sem classificação automática.');
      for(const option of q.options)button(actions,'Visual nos últimos '+option.distanceNM+' NM',()=>answer('visual',{distanceNM:option.distanceNM}));
      const value=input(actions,'Extensão visual até o fim da perna (NM)','',{type:'number',step:'any',inputmode:'decimal'});
      button(actions,'Confirmar limite visual',()=>answer('visual',{distanceNM:value.value}));
    }else node('p',actions,'Esta limitação ainda não tem resolução automática/contextual disponível. Permanecerá visível no rascunho; não pode ser dispensada por uma confirmação genérica.',{class:'ci-warning'});
  }
  function render(){
    const session=getSession(),m=session?.reconstruction;container.replaceChildren();if(!m)return;
    const groups=pendingGroups(m),all=groups.flatMap(g=>g.issues),issue=all.find(i=>i.id===selected)||all[0];selected=issue?.id||null;
    node('p',container,m.issues.filter(i=>i.critical).length+' pendências críticas · respostas salvas no rascunho, sem alterar a missão.',{class:'ci-warning'});
    const nav=node('div',container,undefined,{class:'ci-actions'}),work=m.reviewWork;
    const undo=button(nav,'Desfazer resposta',()=>update(s=>historyStep(s.reconstruction,s,'undo')));undo.disabled=isBusy()||!work?.head;
    const redo=button(nav,'Refazer resposta',()=>update(s=>historyStep(s.reconstruction,s,'redo')));redo.disabled=isBusy()||!work?.nodes.some(n=>n.parent===work.head);
    const message=node('p',container,'Selecione somente as dúvidas que precisam de conferência.',{'data-review-message':'',role:'status','aria-live':'polite'});
    if(issue){
      const group=groups.find(g=>g.issues.includes(issue));
      const chooseGroup=select(container,'Grupo de pendências',groups.map(g=>[g.id,g.label+' · '+g.issues.length+' · '+g.issues[0].message]),group.id);chooseGroup.onchange=()=>{selected=groups.find(g=>g.id===chooseGroup.value).issues[0].id;render();focusCurrent();};
      if(group.issues.length>1){const chooseIssue=select(container,'Pendência relacionada',group.issues.map(i=>[i.id,i.message]),issue.id);chooseIssue.onchange=()=>{selected=chooseIssue.value;render();focusCurrent();};}
      node('h3',container,group.label,{tabindex:'-1'});node('p',container,issue.message,{id:'chart-current-issue'});
      comparison(issue,m,session,container);form(question(m,issue),issue,m,container);
    }else message.textContent='Nenhuma pendência listada. A aprovação do conjunto ainda não está disponível nesta etapa.';
    const history=node('details',container,undefined,{class:'ci-review-history'});node('summary',history,'Histórico de decisões · '+(work?.nodes.length||0));
    const active=new Set(work?activeNodes(work).map(n=>n.id):[]);
    for(const n of [...(work?.nodes||[])].reverse()){
      const row=node('div',history,undefined,{class:'ci-review-history-row'}),outcome=work.outcomes.find(o=>o.id===n.id);
      node('p',row,new Date(n.at).toLocaleString('pt-BR')+' · '+labels[n.kind]+' · '+(active.has(n.id)?outcome?.applied?'aplicada':'precisa de nova conferência':'fora da sequência atual'));
      const a=n.answer,description=n.kind==='position'?'Coordenada: '+a.lat+', '+a.lon+' · '+a.origin:n.kind==='altitude'?'Restrição: '+({at:'exatamente',above:'mínima',below:'máxima',between:'janela'}[a.qualifier])+' '+a.value+(a.upper!==undefined?' a '+a.upper:'')+' FT MSL':n.kind==='leg'?(work.base.points.find(p=>p.id===a.from)?.name||a.from)+' → '+(work.base.points.find(p=>p.id===a.to)?.name||a.to)+' · '+a.course.raw+'° '+a.reference+' · '+a.distance.raw+' NM':n.kind==='confirm-arc'?'Representação horizontal e origens do arco conferidas para este rascunho.':n.kind==='visual'?'Visual nos últimos '+a.distanceNM+' NM':n.kind==='reference'?a.reference+(a.variation?' · VAR '+a.variation.raw:''):'Posição e origem conferidas para este rascunho.';
      node('p',row,description,{class:'ci-muted'});if(outcome?.reason)node('p',row,outcome.reason,{class:'ci-warning'});
      button(row,'Rever resposta',()=>update(s=>checkout(s.reconstruction,s,n.parent),n.issueId));button(row,'Restaurar até aqui',()=>update(s=>checkout(s.reconstruction,s,n.id),n.issueId));
    }
  }
  return {render,open(id){if(id!==undefined)selected=id;render();focusCurrent();},reset(){selected=null;container.replaceChildren();}};
}
