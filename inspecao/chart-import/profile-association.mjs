import {resolveEntity} from './aeronautical.mjs';
import {inverse,normalize,angleDifference} from './geodesy.mjs';
const difference=(a,b)=>{const places=Math.max((a.raw?.split('.')[1]||'').length,(b.raw?.split('.')[1]||'').length),scale=10**places;return (Math.round(a.valueNM*scale)-Math.round(b.valueNM*scale))/scale;};
const problem=(id,message,entities=[],evidenceIds=[])=>({id,category:'ambiguity',critical:true,message,entities,evidenceIds});
export function associateProfileStations(model,database){
  const all=database.airports.filter(a=>a.icao===model.source.chart.icao?.value),official=all.filter(a=>a.source?.kind==='local-database'),candidates=official.length?official:all,airport=candidates.length===1?candidates[0]:null;
  for(const s of model.publishedProfile?.stations||[]){
    let p=model.points.find(p=>p.name===s.name);
    const runway=/^(?:RWY?|THR)\d{2}[LRC]?$/.test(s.name),nonzero=s.distances.some(d=>d.reference.kind==='threshold'&&d.valueNM!==0);
    if(!p){
      const resolution=runway||!airport?{status:'missing',candidates:[]}:resolveEntity(s.name,database,{airport});
      const row=resolution.status==='resolved'?resolution.candidates[0]:null;
      p={id:'p-'+s.name,name:s.name,kind:runway?'profile-reference':row?.type||'fix',roles:[],position:row?{...row.position}:null,coordinateState:resolution.status,coordinateSource:row?{...row.source,originalPosition:{...row.position}}:null,evidenceIds:[],candidates:resolution.status==='resolved'?[]:resolution.candidates,origin:'published-profile'};model.points.push(p);
      if(!p.position)model.issues.push(problem('coordinate-'+p.id,'Ponto do perfil sem coordenada verificável; nenhum pixel foi convertido em posição.',[p.id],s.evidenceIds));
      const date=model.source.chart.publishedDate?.value;
      if(row&&date&&((row.source.validFrom&&row.source.validFrom.slice(0,10)>date)||(row.source.validTo&&row.source.validTo.slice(0,10)<date))){p.coordinateState='temporal-review';model.issues.push(problem('date-'+p.id,'Conferir edição da coordenada do ponto do perfil em relação à carta.',[p.id],s.evidenceIds));}
    }
    p.roles=[...new Set([...p.roles,...s.roles])];p.evidenceIds=[...new Set([...p.evidenceIds,...s.evidenceIds])];
    if(runway&&nonzero)model.issues.push(problem('profile-runway-reference-'+p.id,'Rótulo de pista em posição não nula no perfil. Não foi equiparado à cabeceira; conferir referência e MAPt.',[p.id],s.evidenceIds));
    if(s.altitude){const prior=model.verticalConstraints.find(r=>r.entity===p.id);
      if(prior&&prior.value!==s.altitude.value)model.issues.push(problem('profile-altitude-'+p.id,'Altitudes publicadas do plano e do perfil divergem.',[p.id],s.altitude.evidenceIds));
      else if(!prior)model.verticalConstraints.push({id:'profile-'+p.id,entity:p.id,...s.altitude,source:'chart-profile',status:'review'});
    }
  }
}
export function splitProfileLegs(model){
  const data=model.publishedProfile;if(!data)return;
  const points=new Map(model.points.map(p=>[p.id,p]));
  for(const parent of [...model.legs]){
    if(parent.type!=='line'||parent.flightRules||typeof parent.published?.id!=='string'||!parent.published.evidenceIds?.length||parent.source?.kind==='profile-station-split')continue;
    const from=points.get(parent.from),to=points.get(parent.to);if(!from?.position||!to?.position)continue;
    const candidates=[];
    for(const axis of data.axes.filter(a=>a.reference.distanceKind==='published-profile-along-track'&&(a.reference.kind!=='threshold'||a.reference.runway===model.source.chart.runway?.value))){
      const station=name=>data.stations.filter(s=>s.name===name).flatMap(s=>s.distances.filter(d=>d.axisId===axis.id));
      const aa=station(from.name),bb=station(to.name);if(aa.length!==1||bb.length!==1)continue;
      const a=aa[0],b=bb[0],delta=difference(a,b);
      if(delta<=0||Math.abs(delta-parent.published.distanceNM)>(a.resolutionNM+b.resolutionNM+parent.published.distanceResolution)/2+1e-6)continue;
      const middle=data.stations.flatMap(s=>s.distances.filter(d=>d.axisId===axis.id&&d.valueNM<a.valueNM&&d.valueNM>b.valueNM).map(d=>({s,d,p:model.points.find(p=>p.name===s.name)}))).filter(v=>v.p?.position);
      if(!middle.length)continue;
      candidates.push({axis,chain:[{p:from,d:a},...middle.sort((a,b)=>b.d.valueNM-a.d.valueNM),{p:to,d:b}]});
    }
    if(!candidates.length)continue;
    // Duplicate axes are not additional independent support for a split.
    const signatures=new Map(candidates.map(c=>[c.chain.map(x=>x.p.id+':'+x.d.valueNM).join('|'),c]));
    if(signatures.size!==1){model.issues.push(problem('profile-split-'+parent.id,'Eixos do perfil propõem sequências diferentes; nenhuma subdivisão foi escolhida.',[parent.id]));continue;}
    const {chain,axis}=[...signatures.values()][0],children=[];let valid=true;
    for(let i=1;i<chain.length;i++){
      const a=chain[i-1],b=chain[i],distanceNM=difference(a.d,b.d),resolution=a.d.resolutionNM+b.d.resolutionNM,measured=inverse(a.p.position,b.p.position);
      const course=parent.published.reference==='magnetic'?normalize(measured.trueCourse-(model.reference.variation?.value||0)):measured.trueCourse;
      const angular=(parent.published.courseResolution+(parent.published.reference==='magnetic'?model.reference.variation?.resolution||0:0))/2;
      if(distanceNM<=0||Math.abs(distanceNM-measured.distanceNM)>resolution/2+1e-6||angleDifference(course,parent.published.course)>angular+1e-6){valid=false;break;}
      const evidenceIds=[...new Set([...a.d.evidenceIds,...b.d.evidenceIds,...parent.published.evidenceIds])];
      children.push({...structuredClone(parent),id:'l-'+a.p.id+'-'+b.p.id,from:a.p.id,to:b.p.id,published:{...parent.published,id:parent.published.id+':profile:'+i,distanceNM,distanceResolution:resolution,profileAxis:axis.id,evidenceIds},source:{kind:'profile-station-split',parent:parent.id,evidenceIds},calculated:measured,status:'candidate'});
    }
    if(!valid){model.issues.push(problem('profile-split-'+parent.id,'Ponto do perfil incompatível com o curso, distância ou coordenadas da perna. Subdivisão não aplicada.',[parent.id,...chain.map(v=>v.p.id)]));continue;}
    if(children.some(c=>model.legs.some(l=>l.id===c.id&&l!==parent))){model.issues.push(problem('profile-split-duplicate-'+parent.id,'Subdivisão do perfil conflita com pernas já existentes.',[parent.id]));continue;}
    (model.profileGeometry??={parents:[]}).parents.push(structuredClone(parent));
    model.legs.splice(model.legs.indexOf(parent),1,...children);
  }
  for(const p of model.points.filter(p=>p.origin==='published-profile'&&p.position&&!model.legs.some(l=>l.from===p.id||l.to===p.id)))model.issues.push(problem('profile-route-'+p.id,'Ponto do perfil associado à base, mas sem sequência geométrica confirmada.',[p.id],p.evidenceIds));
}
