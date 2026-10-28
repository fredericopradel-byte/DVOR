import {curvedPaths,circularPath,planPrimitives} from './vector-paths.mjs';
import {triangleSymbols,capPair,holdingDrawing} from './holding-geometry.mjs';
const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().toUpperCase();
const center=r=>({x:r.bbox[0]+r.bbox[2]/2,y:r.bbox[1]+r.bbox[3]/2});
const gap=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
const boxGap=(p,r)=>{const [x,y,w,h]=r.bbox;return Math.hypot(Math.max(x-p.x,0,p.x-x-w),Math.max(y-p.y,0,p.y-y-h));};
const problem=(id,category,message,entities=[],extra={})=>({id,category,critical:true,message,entities,...extra});
export function holdingSubject(h,model){const p=model.points.find(p=>p.id===h.anchor);return {anchor:{id:p?.id,position:p?.position,source:p?.coordinateSource},reference:model.reference,published:h.published,inbound:h.inbound,turn:h.turn,purpose:h.purpose,evidenceIds:h.evidenceIds};}
export function reconstructHoldings(model,interpreted,extraction){
  model.holdings=[];model.issues.splice(0,model.issues.length,...model.issues.filter(i=>!i.id.startsWith('holding-')));
  if(extraction.truncated||interpreted.provider!=='decea-digital-v1'||!interpreted.frame)return;
  const size=interpreted.plan.map(r=>r.height).sort((a,b)=>a-b)[Math.floor(interpreted.plan.length/2)]||5,frame=interpreted.frame.bbox;
  const inside=p=>p.x>=frame[0]&&p.x<=frame[0]+frame[2]&&p.y>=frame[1]&&p.y<=frame[1]+frame[3];
  const primitives=planPrimitives(extraction),paths=curvedPaths(extraction);
  if(primitives.limited||paths.limited){model.issues.push(problem('holding-limit','missing','Extração vetorial excede o limite local de reconhecimento de esperas.'));return;}
  const caps=paths.filter(p=>!p.dashed&&p.points.every(inside)).map(circularPath).filter(p=>p&&p.radius>size&&Math.abs(p.sweepDegrees)>140&&Math.abs(p.sweepDegrees)<200);
  if(caps.length>80){model.issues.push(problem('holding-limit','ambiguity','Muitos arcos candidatos; nenhuma espera foi escolhida automaticamente.'));return;}
  const text=norm((extraction.lines||[]).map(l=>l.text).join(' ')+' '+interpreted.runs.map(r=>r.text).join(' '));
  const symbols=triangleSymbols(primitives,size),seen=new Set(),ambiguousAnchors=new Set();
  for(let i=0;i<caps.length;i++)for(let j=i+1;j<caps.length;j++){
    const pair=capPair(caps[i],caps[j],primitives.lines);if(!pair)continue;
    const anchors=symbols.flatMap(s=>pair.corners.map((corner,k)=>({s,k,d:gap(s.position,corner)}))).filter(a=>a.d<pair.r*.6).sort((a,b)=>a.d-b.d);
    const unique=[...new Map(anchors.map(a=>[a.s.evidenceIds.join(':'),a])).values()];if(unique.length!==1)continue;
    const anchor=unique[0],labels=model.points.flatMap(p=>interpreted.plan.filter(r=>norm(r.text)===p.name&&boxGap(anchor.s.position,r)<=r.height*7).map(r=>({p,r})));
    const ids=[...new Set(labels.map(l=>l.p.id))];if(ids.length!==1)continue;
    const point=labels[0].p;if(ambiguousAnchors.has(point.id))continue;const id='holding-'+point.id,key=point.id+':'+caps[i].evidenceIds[0]+':'+caps[j].evidenceIds[0];if(seen.has(key))continue;seen.add(key);
    if(model.holdings.some(h=>h.anchor===point.id)){model.issues.push(problem('holding-anchor-'+point.id,'ambiguity','Mais de um hipódromo associado ao mesmo fixo. Nenhum modelo foi escolhido.',[point.id]));model.holdings=model.holdings.filter(h=>h.anchor!==point.id);model.issues=model.issues.filter(i=>i.holdingId!==id);ambiguousAnchors.add(point.id);continue;}
    const capIndex=anchor.k<2?0:1,side=anchor.k%2===0?1:-1,near=pair.centers[capIndex],far=pair.centers[1-capIndex],u={x:(near.x-far.x)/pair.L,y:(near.y-far.y)/pair.L},fix=pair.corners[anchor.k],right={x:-u.y,y:u.x};
    const turn=(near.x-fix.x)*right.x+(near.y-fix.y)*right.y>0?'right':'left';
    const lane=(r,s)=>{const q=center(r),a=pair.corners[s===1?0:1],along=(q.x-a.x)*pair.u.x+(q.y-a.y)*pair.u.y,cross=Math.abs((q.x-a.x)*pair.n.x+(q.y-a.y)*pair.n.y);return along>=-pair.r&&along<=pair.L+pair.r&&cross<pair.r*.9;};
    const courses=interpreted.plan.filter(r=>/^\d{3}[º°]?$/.test(r.text)&&Number(r.text.replace(/[º°]/g,''))<=360),inc=courses.filter(r=>lane(r,side)),out=courses.filter(r=>lane(r,-side));
    const matches=inc.flatMap(a=>out.filter(b=>Math.abs(((Number(a.text.replace(/[º°]/g,''))-Number(b.text.replace(/[º°]/g,''))+540)%360)-180)===180).map(b=>({a,b})));
    const values=[...new Set(matches.map(m=>Number(m.a.text.replace(/[º°]/g,''))))],inbound=values.length===1?{value:values[0],raw:matches.find(m=>Number(m.a.text.replace(/[º°]/g,''))===values[0]).a.text,reference:interpreted.reference,resolution:1,evidenceIds:matches.filter(m=>Number(m.a.text.replace(/[º°]/g,''))===values[0]).flatMap(m=>m.a.evidenceIds)}:null;
    const scoped=interpreted.plan.filter(r=>lane(r,1)||lane(r,-1)),definitions=[];
    for(const r of scoped){const m=norm(r.text).match(/^(\d+(?:[.,]\d+)?)\s*(MIN|SEC|S|NM)$/);if(m&&Number(m[1].replace(',','.'))>0)definitions.push({kind:m[2]==='NM'?'distance':'time',value:Number(m[1].replace(',','.'))*(m[2]==='MIN'?60:1),unit:m[2]==='NM'?'NM':'S',raw:r.text,evidenceIds:r.evidenceIds});}
    const defs=[...new Map(definitions.map(d=>[d.kind+':'+d.value,d])).values()],escaped=point.name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),namedHolding=new RegExp('(?:ESPERA\\s+(?:EM|SOBRE)|HOLDING\\s+(?:AT|OVER))\\s+'+escaped+'\\b|\\b'+escaped+'\\s+(?:PARA\\s+(?:A\\s+)?ESPERA|FOR\\s+HOLDING)\\b').test(text),purpose=point.roles?.includes('MAHF')||namedHolding?'holding':'unresolved-racetrack';
    const evidenceIds=[...new Set([...pair.evidenceIds,...anchor.s.evidenceIds,...labels.flatMap(l=>l.r.evidenceIds),...matches.flatMap(m=>[...m.a.evidenceIds,...m.b.evidenceIds]),...definitions.flatMap(d=>d.evidenceIds)])];
    const h={id,anchor:point.id,purpose,turn,inbound,published:{inboundCourse:inbound?structuredClone(inbound):null,outboundCourse:inbound?{value:(inbound.value+180)%360,reference:inbound.reference,evidenceIds:matches.flatMap(m=>m.b.evidenceIds)}:null,legDefinition:defs.length===1?defs[0]:null,definitionCandidates:defs,constraintIds:model.verticalConstraints.filter(r=>r.entity===point.id).map(r=>r.id)},evidenceIds,source:{kind:'paired-circular-caps-parallel-strokes-and-fix-symbol',layoutUsedFor:'topology-only'},status:'dimensions-required'};
    if(model.holdings.length>=64){model.issues.push(problem('holding-limit','missing','Limite local de hipódromos atingido. Cobertura restante permanece pendente.'));return;}
    model.holdings.push(h);if(defs.length>1)model.issues.push(problem('holding-definition-'+id,'ambiguity','Definições de extensão conflitantes permanecem preservadas. Dimensionar o desenho não resolve essa divergência publicada.',[point.id],{holdingId:id,evidenceIds}));model.issues.push(problem('holding-geometry-'+id,defs.length>1||!inbound||purpose==='unresolved-racetrack'?'ambiguity':'missing','Hipódromo associado a '+point.name+'. Confira a função publicada e forneça somente as dimensões não determinadas para o desenho.',[point.id],{holdingId:id,evidenceIds}));
    model.issues.push(problem('holding-route-'+id,'missing','O hipódromo permanece separado da sequência principal. Entrada, saída e número de circuitos não foram presumidos.',[point.id],{holdingId:id,evidenceIds}));
  }
  const coverage=model.issues.find(i=>i.id==='structure-holding');if(coverage&&model.holdings.length)coverage.message=model.holdings.length+' hipódromo(s) associado(s). Cobertura de outras esperas/reversões, entradas e saídas ainda parcial; confira as pendências específicas.';
}
const finite=(value,min,max,label)=>{if((typeof value!=='number'&&typeof value!=='string')||String(value).trim()==='')throw Error('Preencha '+label+'.');const n=Number(value);if(!Number.isFinite(n)||n<min||n>max)throw Error(label+' fora dos limites do desenho.');return n;};
export function holdingAnswer(h,answer){
  const a={purpose:h.purpose==='unresolved-racetrack'?answer.purpose:h.purpose};
  if(!['holding','course-reversal'].includes(a.purpose))throw Error('Confirme se o hipódromo é espera ou reversão publicada.');
  a.inbound=h.inbound?structuredClone(h.inbound):{value:finite(answer.course,0,360,'Curso publicado'),reference:answer.reference,source:'manual-confirmed'};
  if(!['magnetic','true'].includes(a.inbound.reference))throw Error('Referência do curso não determinada.');
  const definition=h.published.legDefinition;a.mode=definition?.kind||answer.mode;if(!['time','distance'].includes(a.mode))throw Error('Escolha como dimensionar a perna do desenho.');
  a.radiusNM=finite(answer.radiusNM,.1,100,'Raio das curvas (NM)');
  if(a.mode==='time'){a.timeSeconds=finite(definition?.value??answer.timeSeconds,.1,3600,'Tempo da perna (s)');a.groundSpeedKT=finite(answer.groundSpeedKT,1,1000,'GS para o desenho (kt)');const d=a.timeSeconds*a.groundSpeedKT/3600;if(d<.1||d>500)throw Error('Distância calculada do desenho fora de 0,1 a 500 NM.');}
  else a.legLengthNM=finite(definition?.value??answer.legLengthNM,.1,500,'Extensão da perna (NM)');
  a.source='manual-drawing-dimensions';return a;
}
export function applyHoldingAnswer(model,h,a,decision){
  const candidate={...h,purpose:a.purpose,inbound:structuredClone(a.inbound),drawing:structuredClone(a),decision,status:'drawing-confirmed'};
  const origin=model.native?.origin||{...model.points.find(p=>p.position)?.position,mag:Math.abs(model.reference.variation?.value||0),dir:(model.reference.variation?.value||0)<0?'W':'E'};
  if(!holdingDrawing(candidate,model,origin))throw Error('Espera sem coordenadas/referência suficientes ou acima dos limites do editor.');
  Object.assign(h,candidate);model.issues=model.issues.filter(i=>i.id!=='holding-geometry-'+h.id);
}
export function appendHoldings(model,document,mapping,issues){
  mapping.holdings={};
  for(const h of model.holdings||[]){if(!h.drawing)continue;const result=holdingDrawing(h,model,document.origin);
    if(!result||!mapping.points[h.anchor]){issues.push(problem('holding-native-'+h.id,'inconsistency','A espera não pode ser representada com as coordenadas e dimensões atuais.',[h.anchor],{holdingId:h.id}));continue;}
    document.points.push(...result.points);document.segments.push(...result.segments);mapping.holdings[h.id]={points:[h.anchor,...result.points.map(p=>p.id)],segments:result.segments.map(s=>s.id),legLengthNM:result.legLengthNM,radiusNM:result.radiusNM,kind:result.kind,operationalRouteIncluded:false};
    for(const p of result.points)mapping.derived.push({id:p.id,holding:h.id,source:'explicit-holding-drawing-dimensions',anchor:h.anchor});
  }
}

export function validateHoldingRecords(model){
  if(model.holdings===undefined)return;
  if(!Array.isArray(model.holdings)||model.holdings.length>64)throw Error('Coleção de hipódromos inválida.');
  const ids=new Set();for(const h of model.holdings){
    if(!h||typeof h.id!=='string'||ids.has(h.id)||!model.points.some(p=>p.id===h.anchor)||!['holding','course-reversal','unresolved-racetrack'].includes(h.purpose)||!['left','right'].includes(h.turn)||!h.published||typeof h.published!=='object'||!Array.isArray(h.evidenceIds))throw Error('Definição de hipódromo incompatível.');ids.add(h.id);
    if(h.inbound&&(!Number.isFinite(h.inbound.value)||h.inbound.value<0||h.inbound.value>360||!['true','magnetic','unknown'].includes(h.inbound.reference)))throw Error('Curso de hipódromo inválido.');
    if(h.drawing){const g=h.drawing;if(!['time','distance'].includes(g.mode)||!Number.isFinite(g.radiusNM)||g.radiusNM<.1||g.radiusNM>100)throw Error('Dimensões do hipódromo inválidas.');if(g.mode==='time'&&(!Number.isFinite(g.timeSeconds)||g.timeSeconds<=0||g.timeSeconds>3600||!Number.isFinite(g.groundSpeedKT)||g.groundSpeedKT<=0||g.groundSpeedKT>1000))throw Error('Tempo/GS do hipódromo inválidos.');const d=g.mode==='time'?g.timeSeconds*g.groundSpeedKT/3600:g.legLengthNM;if(!Number.isFinite(d)||d<.1||d>500)throw Error('Extensão do hipódromo inválida.');}
  }
}
