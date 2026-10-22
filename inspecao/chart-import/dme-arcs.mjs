import {resolveEntity} from './aeronautical.mjs';
import {curvedPaths,circularPath} from './vector-paths.mjs';
import {inverse,normalize} from './geodesy.mjs';
const norm=s=>String(s||'').trim().toUpperCase();
const gap=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
const boxGap=(p,r)=>{const [x,y,w,h]=r.bbox;return Math.hypot(Math.max(x-p.x,0,p.x-x-w),Math.max(y-p.y,0,p.y-y-h));};
const issue=(id,category,message,entities=[],extra={})=>({id,category,critical:true,message,entities,...extra});
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
export function arcSubject(model,leg){return {reference:model.reference,coordinateSources:[leg.from,...(leg.via||[]),leg.to,leg.center].map(id=>({id,source:model.points.find(p=>p.id===id)?.coordinateSource})),nativeOrigin:model.points.find(p=>p.position)?.position,from:model.points.find(p=>p.id===leg.from)?.position,to:model.points.find(p=>p.id===leg.to)?.position,center:model.points.find(p=>p.id===leg.center)?.position,radiusNM:leg.radiusNM,turn:leg.turn,source:leg.source,publishedDME:leg.publishedDME,via:(leg.via||[]).map(id=>({id,position:model.points.find(p=>p.id===id)?.position}))};}
export function arcReviewed(model,leg){return !!leg.horizontalReview?.subject&&same(leg.horizontalReview.subject,arcSubject(model,leg));}
export function dmeStations(model,interpreted){
  const out=new Map(),names=new Map();
  for(const p of model.points)names.set(norm(p.name),[...(names.get(norm(p.name))||[]),p]);
  const labels=interpreted.plan.flatMap(r=>(names.get(norm(r.text))||[]).map(p=>({p,r}))),readings=interpreted.plan.filter(r=>/^D\s*\d/.test(norm(r.text)));
  if(labels.length>2000||readings.length>1000)return Object.assign([],{limited:true});
  for(const run of readings){
    const m=norm(run.text).match(/^D\s*(\d{1,3}(?:\.\d{1,3})?)\s+([A-Z][A-Z0-9]{1,4})$/);if(!m||Number(m[1])<=0)continue;
    const radiusNM=Number(m[1]),radiusResolution=m[1].includes('.')?10**(-m[1].split('.')[1].length):1;
    const candidates=labels.filter(({r})=>Math.abs(r.angle-run.angle)<.04&&r.bbox[1]<=run.bbox[1]&&run.bbox[1]-r.bbox[1]<=r.height*4.5&&Math.abs(r.bbox[0]+r.bbox[2]/2-run.bbox[0]-run.bbox[2]/2)<=Math.max(r.bbox[2],run.bbox[2])*.55);
    const ids=[...new Set(candidates.map(c=>c.p.id))];if(ids.length!==1)continue;
    const key=ids[0]+':'+m[2]+':'+radiusNM,evidenceIds=[...run.evidenceIds,...candidates.flatMap(c=>c.r.evidenceIds)],prior=out.get(key);
    if(prior){prior.radiusResolution=Math.min(prior.radiusResolution,radiusResolution);prior.raws=[...new Set([...prior.raws,run.text])];prior.evidenceIds=[...new Set([...prior.evidenceIds,...evidenceIds])];}
    else out.set(key,{point:ids[0],aid:m[2],radiusNM,radiusResolution,raw:run.text,raws:[run.text],evidenceIds,distanceKind:'slant-range'});
    if(out.size>64)return Object.assign([],{limited:true});
  }return [...out.values()];
}
// Stitched paths must share their page-space circle and have only a short gap.
// These thresholds govern recognition, never operational/geographic tolerance.
function pathGroups(paths,size){
  const groups=[];
  for(const p of paths){const group=groups.find(g=>gap(g[0].center,p.center)<=size*.5&&Math.abs(g[0].radius-p.radius)<=size*.25);if(group)group.push(p);else groups.push([p]);}
  return groups;
}
function routes(group,from,to,labels,size){
  const ends=group.flatMap((p,i)=>[0,1].map(end=>({i,end,p:p.points[end?p.points.length-1:0]})));
  const near=id=>ends.filter(e=>labels.get(id)?.some(r=>boxGap(e.p,r)<=r.height*5.5));
  const starts=near(from),targets=new Set(near(to).map(e=>e.i+':'+e.end)),out=[];
  // Limit combinatorics: a complicated/ambiguous drawing stays pending.
  if(starts.length>8||targets.size>8||ends.length>80)return Object.assign([],{limited:true});
  let visits=0,limited=false;
  function walk(entry,used,steps){if(limited)return;if(++visits>4096||out.length>8||steps.length>12){limited=true;return;}if(used.has(entry.i))return;
    const p=group[entry.i],exit=ends.find(e=>e.i===entry.i&&e.end!==entry.end),next=[...steps,{path:p,reverse:entry.end===1}],seen=new Set([...used,entry.i]);
    if(targets.has(exit.i+':'+exit.end)){out.push(next);return;}
    for(const other of ends)if(!seen.has(other.i)&&gap(other.p,exit.p)<=size*3){
      // A gap cannot bridge a large angular sector or silently jump circles.
      const a=Math.atan2(exit.p.y-p.center.y,exit.p.x-p.center.x),b=Math.atan2(other.p.y-p.center.y,other.p.x-p.center.x);
      if(Math.abs(Math.atan2(Math.sin(b-a),Math.cos(b-a)))<=Math.PI/18)walk(other,seen,next);
    }
  }
  for(const start of starts)walk(start,new Set(),[]);
  if(limited)return Object.assign([],{limited:true});
  return out.filter(route=>{
    let total=0,sign=0;
    for(let j=0;j<route.length;j++){
      const step=route[j],sweep=step.path.sweepDegrees*(step.reverse?-1:1);if(sign&&Math.sign(sweep)!==sign)return false;sign=Math.sign(sweep);
      if(j){const prior=route[j-1],a=prior.path.points[prior.reverse?0:prior.path.points.length-1],b=step.path.points[step.reverse?step.path.points.length-1:0],c=step.path.center,delta=Math.atan2(Math.sin(Math.atan2(b.y-c.y,b.x-c.x)-Math.atan2(a.y-c.y,a.x-c.x)),Math.cos(Math.atan2(b.y-c.y,b.x-c.x)-Math.atan2(a.y-c.y,a.x-c.x)))*180/Math.PI;
        if(delta*sign < -1e-6)return false;total+=delta;
      }total+=sweep;
    }
    return Math.abs(total)<350;
  });
}
export function reconstructDmeArcs(model,interpreted,extraction,database){
  // Regenerate from source after each answer; never preserve a stale automatic arc.
  model.legs=model.legs.filter(l=>l.source?.kind!=='dme-arc-association');
  model.issues.splice(0,model.issues.length,...model.issues.filter(i=>!i.id.startsWith('dme-')));
  model.dmeArcs={version:1,stations:[],associations:[]};
  if(extraction.truncated||!interpreted.frame||interpreted.provider!=='decea-digital-v1'||!model.structures.some(s=>s.type==='dme-arc')||model.structures.some(s=>s.type==='rf-leg'))return;
  const stations=dmeStations(model,interpreted);if(stations.limited){model.issues.push(issue('dme-station-limit','missing','Etiquetas DME excedem o limite de associação local. Origem preservada; nenhum arco foi presumido.'));return;}
  model.dmeArcs.stations=stations;
  const ambiguous=new Set(stations.filter(s=>stations.some(t=>s.point===t.point&&(s.aid!==t.aid||s.radiusNM!==t.radiusNM))).map(s=>s.point));
  for(const point of ambiguous)model.issues.push(issue('dme-definition-'+point,'ambiguity','Mais de uma definição DME associada ao mesmo ponto. Nenhum raio ou auxílio foi escolhido automaticamente.',[point],{evidenceIds:stations.filter(s=>s.point===point).flatMap(s=>s.evidenceIds)}));
  // VOR and DME equipment may have different surveyed positions. Never borrow
  // the VOR position merely because the identifier is shared.
  for(const aid of [...new Set(stations.map(s=>s.aid))]){
    if(!interpreted.aids.some(a=>a.name===aid)||model.points.some(p=>p.dmeIdent===aid||p.name===aid&&p.kind==='DME'))continue;
    if(!database)continue;
    const airports=database.airports.filter(a=>a.icao===model.source.chart.icao?.value),official=airports.filter(a=>a.source.kind==='local-database'),contexts=official.length?official:airports;
    const result=contexts.length===1?resolveEntity(aid,database,{type:'DME',airport:contexts[0]}):{status:'missing',candidates:[]},row=result.status==='resolved'?result.candidates[0]:null;
    const p={id:'p-dme-aid-'+aid,name:aid+' (DME)',dmeIdent:aid,origin:'dme-center',kind:'DME',roles:[],position:row?{...row.position}:null,coordinateState:result.status,coordinateSource:row?{...row.source,originalPosition:{...row.position}}:null,evidenceIds:stations.filter(s=>s.aid===aid).flatMap(s=>s.evidenceIds),candidates:row?[]:result.candidates};
    if(model.points.some(q=>q.id===p.id))continue;model.points.push(p);
    if(!row)model.issues.push(issue('coordinate-'+p.id,result.status==='ambiguous'?'ambiguity':'missing','Coordenada do equipamento DME '+aid+' não determinada; a posição do VOR não foi usada em seu lugar.',[p.id],{options:p.candidates,evidenceIds:p.evidenceIds}));
    const date=model.source.chart.publishedDate?.value;
    if(row&&date&&((row.source.validFrom&&row.source.validFrom.slice(0,10)>date)||(row.source.validTo&&row.source.validTo.slice(0,10)<date)))model.issues.push(issue('date-'+p.id,'inconsistency','Conferir edição da coordenada do DME em relação à carta.',[p.id]));
  }
  const size=interpreted.plan.map(r=>r.height).sort((a,b)=>a-b)[Math.floor(interpreted.plan.length/2)]||5;
  const frame=interpreted.frame.bbox,inside=p=>p.x>=frame[0]-size&&p.x<=frame[0]+frame[2]+size&&p.y>=frame[1]-size&&p.y<=frame[1]+frame[3]+size;
  const vectors=curvedPaths(extraction);if(vectors.limited){model.issues.push(issue('dme-vector-limit','missing','Vetores excedem o limite local de análise de arcos. Associação suspensa; origem preservada.'));return;}
  const paths=vectors.filter(p=>!p.dashed&&p.points.every(inside)&&gap(p.points[0],p.points.at(-1))>size*4).map(circularPath).filter(Boolean);
  const groups=pathGroups(paths,size),labels=new Map(model.points.map(p=>[p.id,interpreted.plan.filter(r=>norm(r.text)===p.name)]));
  for(const start of stations)for(const end of stations){
    const from=model.points.find(p=>p.id===start.point),to=model.points.find(p=>p.id===end.point);
    // Explicit function sequence plus continuous curved vectors is independent
    // evidence beyond coincident DME readings. Missed-approach prose is not a route.
    if(ambiguous.has(start.point)||ambiguous.has(end.point)||start.aid!==end.aid||start.radiusNM!==end.radiusNM||from===to||!from?.roles?.includes('IAF')||!to?.roles?.includes('IF'))continue;
    const key=from.id+'-'+to.id,center=model.points.find(p=>p.dmeIdent===start.aid||p.name===start.aid&&p.kind==='DME');
    const publication={radiusNM:start.radiusNM,radiusResolution:Math.min(start.radiusResolution,end.radiusResolution),distanceKind:'slant-range',raw:[...(start.raws||[start.raw]),...(end.raws||[end.raw])],aid:start.aid,evidenceIds:[...new Set([...start.evidenceIds,...end.evidenceIds])]};
    const aidEvidence=new Set(interpreted.aids.filter(a=>a.name===start.aid).flatMap(a=>a.evidenceIds)),aidLabels=interpreted.plan.filter(r=>r.evidenceIds.some(e=>aidEvidence.has(e)));
    const attempts=groups.filter(g=>aidLabels.some(r=>boxGap(g[0].center,r)<=r.height*12)).map(g=>routes(g,from.id,to.id,labels,size));
    if(attempts.some(a=>a.limited)){model.issues.push(issue('dme-topology-limit-'+key,'ambiguity','Conectividade dos vetores do arco excede o limite de análise local. Nenhuma sequência foi escolhida.',[from.id,to.id],{evidenceIds:publication.evidenceIds}));continue;}
    const options=attempts.flat();
    if(!options.length)continue;
    if(model.legs.some(l=>l.type==='line'&&l.from===from.id&&l.to===to.id&&l.published?.id)){
      model.issues.push(issue('dme-definition-'+key,'ambiguity','A ligação também possui uma definição publicada de reta. A alternativa de arco não foi escolhida automaticamente.',[from.id,to.id],{evidenceIds:publication.evidenceIds}));continue;
    }
    // No unsupported chord competes with a recognized DME arc.
    const evidenceIds=[...new Set([...publication.evidenceIds,...options.flatMap(o=>o.flatMap(s=>s.path.evidenceIds))])];
    const turns=[...new Set(options.map(o=>o[0].path.sweepDegrees*(o[0].reverse?-1:1)>0?'right':'left'))];
    if(turns.length!==1){model.issues.push(issue('dme-topology-'+key,'ambiguity','Vetores permitem mais de um sentido de arco; nenhum sentido foi presumido.',[from.id,to.id],{evidenceIds}));continue;}
    if(!center?.position||!from.position||!to.position){model.issues.push(issue('dme-coordinate-'+key,'missing','Arco associado à carta, mas centro ou extremidades ainda não possuem coordenadas verificáveis.',[from.id,to.id,...(center?[center.id]:[])],{evidenceIds}));continue;}
    const a=inverse(center.position,from.position),b=inverse(center.position,to.position),tolerance=publication.radiusResolution/2+1e-6;
    if(Math.abs(a.distanceNM-publication.radiusNM)>tolerance||Math.abs(b.distanceNM-publication.radiusNM)>tolerance){model.issues.push(issue('dme-radius-'+key,'inconsistency','Distâncias geodésicas dos fixos incompatíveis com o intervalo do DME publicado. Nenhum fixo foi deslocado.',[center.id,from.id,to.id],{evidenceIds,published:publication,measured:[a,b]}));continue;}
    const turn=turns[0],sweep=normalize((turn==='right'?1:-1)*(b.trueCourse-a.trueCourse));
    if(sweep<=0||sweep>=350){model.issues.push(issue('dme-sweep-'+key,'inconsistency','Topologia do arco incompatível com a extensão geográfica; conferir extremidades e sentido.',[from.id,to.id],{evidenceIds}));continue;}
    // A third explicitly DME-labelled point along this route is a branch/boundary,
    // not an invitation to bypass it. Leave the larger connection unresolved.
    const crossed=stations.some(s=>s.point!==from.id&&s.point!==to.id&&s.aid===start.aid&&s.radiusNM===start.radiusNM&&options.some(o=>o.some(step=>[step.path.points[0],step.path.points.at(-1)].some(p=>labels.get(s.point)?.some(r=>boxGap(p,r)<=r.height*4)))));
    if(crossed)continue;
    // Fixes at a vector junction cannot silently disappear when their official
    // coordinate conflicts with the arc. Do not bypass a broken intermediate fix.
    let junctionConflict=false;
    for(const route of options)for(let j=1;j<route.length;j++){
      const left=route[j-1],right=route[j],exit=left.path.points[left.reverse?0:left.path.points.length-1],entry=right.path.points[right.reverse?right.path.points.length-1:0],joint={x:(exit.x+entry.x)/2,y:(exit.y+entry.y)/2};
      const near=model.points.filter(p=>p!==from&&p!==to&&p!==center&&labels.get(p.id)?.some(r=>boxGap(joint,r)<=r.height*8));
      if(near.length>1){junctionConflict=true;model.issues.push(issue('dme-via-ambiguity-'+key,'ambiguity','Mais de um fixo possível na junção dos vetores do arco. Nenhum fixo intermediário foi escolhido.',near.map(p=>p.id),{evidenceIds}));continue;}
      if(near.length){const p=near[0],radial=p.position?inverse(center.position,p.position):null,along=radial?normalize((turn==='right'?1:-1)*(radial.trueCourse-a.trueCourse)):null;
        if(!radial||Math.abs(radial.distanceNM-publication.radiusNM)>tolerance||along<=0||along>=sweep){junctionConflict=true;model.issues.push(issue('dme-via-'+key,radial?'inconsistency':'missing','Fixo na junção gráfica sem coordenada compatível com o arco. A conexão não foi desenhada por cima desse conflito.',[p.id],{evidenceIds}));}
      }
    }
    if(junctionConflict)continue;
    const horizontalRadiusNM=(a.distanceNM+b.distanceNM)/2;
    const intermediates=model.points.filter(p=>p!==from&&p!==to&&p!==center&&p.position).map(p=>({p,radial:inverse(center.position,p.position)})).filter(({p,radial})=>{
      const along=normalize((turn==='right'?1:-1)*(radial.trueCourse-a.trueCourse));
      return along>1e-6&&along<sweep-1e-6&&Math.abs(radial.distanceNM-publication.radiusNM)<=tolerance&&options.some(o=>o.some(step=>[step.path.points[0],step.path.points.at(-1)].some(at=>labels.get(p.id)?.some(r=>boxGap(at,r)<=r.height*8))));
    }).sort((x,y)=>normalize((turn==='right'?1:-1)*(x.radial.trueCourse-a.trueCourse))-normalize((turn==='right'?1:-1)*(y.radial.trueCourse-a.trueCourse)));
    const via=intermediates.map(x=>x.p.id);for(const id of via)for(const r of labels.get(id)||[])for(const e of r.evidenceIds)if(!evidenceIds.includes(e))evidenceIds.push(e);
    const leg={id:'dme-'+key,type:'arc',from:from.id,to:to.id,center:center.id,turn,via,radiusNM:horizontalRadiusNM,radiusResolution:publication.radiusResolution,publishedDME:publication,source:{kind:'dme-arc-association',scope:'initial-approach',sequence:'published-IAF-IF-and-curved-vector-connectivity',evidenceIds,layoutUsedFor:'topology-only',horizontalRadiusSource:'mean-of-verified-endpoint-geodesic-distances',viaAssociation:'verified-coordinate-on-arc-and-vector-junction'},status:'horizontal-review'};
    model.legs.push(leg);model.dmeArcs.associations.push({leg:leg.id,center:center.id,from:from.id,to:to.id,turn,via,publishedDME:publication,horizontalRadiusNM,evidenceIds});
    model.issues.push(issue('dme-horizontal-'+leg.id,'ambiguity','Arco DME reconstruído como curva horizontal pelas coordenadas dos fixos. DME é distância inclinada: confira esta representação antes de aceitá-la.',[leg.id,center.id,from.id,...via,to.id],{evidenceIds}));
  }
  const coverage=model.issues.find(i=>i.id==='structure-dme-arc');
  if(coverage&&model.dmeArcs.associations.length)coverage.message=model.dmeArcs.associations.length+' arco(s) da aproximação inicial associado(s). Arcos de aproximação perdida, interceptações condicionais e cobertura restante ainda precisam de reconstrução; não foram presumidos.';
}
