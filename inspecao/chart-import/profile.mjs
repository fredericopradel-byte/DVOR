import {center, supportedLayout} from './decea.mjs';
import {destination, inverse, normalize, angleDifference} from './geodesy.mjs';

const norm=s=>String(s||'').trim().toUpperCase();
const runway=s=>norm(s).replace(/^(?:RWY?|THR)\s*/, '');
const problem=(id,category,message,entities=[],extra={})=>({id,category,critical:true,message,entities,...extra});
const resolution=s=>s.includes('.')?10**(-s.split('.')[1].length):1;

// Page positions associate explicit labels/columns only. Distances come exclusively
// from printed numbers, never from the width or scale of the profile.
export function thresholdProfile(interpreted, metadata) {
  if(interpreted.provider!=='decea-digital-v1'||!interpreted.frame||metadata.kind?.value!=='IAC')return null;
  const bottom=interpreted.frame.bbox[1]+interpreted.frame.bbox[3],runs=interpreted.runs;
  const axes=runs.filter(r=>r.bbox[1]>bottom&&/^TO\s+THR\s+\d{2}[LRC]?\s*\(NM\)$/.test(norm(r.text)));
  if(axes.length!==1)return null;
  const axis=axes[0],rwy=norm(axis.text).match(/THR\s+(\d{2}[LRC]?)/)[1];
  if(rwy!==metadata.runway?.value)return null;
  const row=runs.filter(r=>/^\d{1,3}\.\d{1,2}$/.test(r.text)&&Math.abs(center(r.bbox).y-center(axis.bbox).y)<axis.height&&r.bbox[0]<axis.bbox[0]);
  if(row.filter(r=>Number(r.text)===0).length!==1||row.length<2)return null;
  const labels=runs.filter(r=>r.bbox[1]>bottom&&r.bbox[1]+r.bbox[3]<axis.bbox[1]&&Math.abs(r.angle)<.02&&/^[A-Z][A-Z0-9]{2,7}$/.test(norm(r.text)));
  const stations=[];
  for(const number of row){const x=center(number.bbox).x,near=labels.filter(l=>Math.abs(center(l.bbox).x-x)<=Math.max(8,l.height*2));
    // Multiple named labels in one column are ambiguous, never resolved by guess.
    const names=[...new Set(near.map(l=>norm(l.text)).filter(n=>!['FAF','FAP','MAPT','LNAV','MDA','MSL'].includes(n)))];
    if(names.length===1)stations.push({name:names[0],distanceNM:Number(number.text),resolutionNM:resolution(number.text),evidenceIds:[...axis.evidenceIds,...number.evidenceIds,...near.filter(l=>norm(l.text)===names[0]).flatMap(l=>l.evidenceIds)]});
  }
  const zero=stations.filter(s=>s.distanceNM===0&&/^(?:RWY?|THR)\d{2}[LRC]?$/.test(s.name)&&runway(s.name)===rwy);
  if(zero.length!==1)return null;
  const vmc=runs.filter(r=>r.bbox[1]>bottom&&r.bbox[1]<axis.bbox[1]&&/\b(?:PROSSIGA|PROCEED)\s+VMC\b/.test(norm(r.text)));
  return {kind:'distance-to-threshold',unit:'NM',distanceKind:'published-profile-along-track',runway:rwy,target:zero[0].name,stations,distanceMarks:row.map(r=>({distanceNM:Number(r.text),resolutionNM:resolution(r.text),evidenceIds:r.evidenceIds})),visual:vmc.length?{kind:'published-vmc',bounds:'unresolved',evidenceIds:vmc.flatMap(r=>r.evidenceIds)}:null,evidenceIds:axis.evidenceIds};
}
// Only an explicitly zero-valued, named threshold column can support this fallback.
function profileFromAxes(model){
  const data=model.publishedProfile;if(!data)return null;
  const axes=data.axes.filter(a=>a.reference.kind==='threshold'&&a.reference.runway===model.source.chart.runway?.value&&a.reference.distanceKind==='published-profile-along-track');
  if(axes.length!==1)return null;
  const axis=axes[0],stations=data.stations.flatMap(s=>s.distances.filter(d=>d.axisId===axis.id).map(d=>({name:s.name,distanceNM:d.valueNM,resolutionNM:d.resolutionNM,evidenceIds:[...s.evidenceIds,...d.evidenceIds]})));
  const zero=stations.filter(s=>s.distanceNM===0&&/^(?:RWY?|THR)\d{2}[LRC]?$/.test(s.name)&&runway(s.name)===axis.reference.runway);
  if(zero.length!==1)return null;
  return {kind:'distance-to-threshold',unit:'NM',distanceKind:axis.reference.distanceKind,runway:axis.reference.runway,target:zero[0].name,stations,distanceMarks:axis.marks.map(m=>({distanceNM:m.valueNM,resolutionNM:m.resolutionNM,evidenceIds:m.evidenceIds})),visual:null,evidenceIds:axis.evidenceIds};
}
function localizerDefinition(model,interpreted,profile){
  const data=model.publishedProfile,course=data?.finalCourse,title=model.source.chart.procedure?.value||'';
  if(!/\b(?:ILS|LOC)\b/.test(title)||/\b(?:AR|RF)\b/.test(title)||model.structures?.some(s=>s.type==='rf-leg')||profile.visual||!course||course.reference!==model.reference.course)return null;
  const bottom=interpreted.frame.bbox[1]+interpreted.frame.bbox[3],axisTop=Math.min(...data.axes.map(a=>a.bbox[1]));
  const profileCourses=interpreted.runs.filter(r=>r.bbox[1]>bottom&&r.bbox[1]<axisTop&&/^\d{3}[°º]?$/.test(r.text));
  const named=data.stations.filter(s=>s.roles.some(r=>['FAF','FAP'].includes(r))&&s.distances.some(d=>d.reference.kind==='threshold'&&d.reference.runway===profile.runway&&d.valueNM>0));
  const zero=data.stations.filter(s=>s.name===profile.target&&s.distances.some(d=>d.reference.kind==='threshold'&&d.valueNM===0));
  if(named.length!==1||zero.length!==1)return null;
  const a=center(named[0].bbox).x,b=center(zero[0].bbox).x,finalCourses=profileCourses.filter(r=>center(r.bbox).x>Math.min(a,b)&&center(r.bbox).x<Math.max(a,b));
  if(!finalCourses.length||finalCourses.some(r=>Number(r.text.replace(/[°º]/g,''))!==course.value)||interpreted.runs.some(r=>r.bbox[1]>bottom&&r.bbox[1]<axisTop&&/\b(?:VMC|VISUAL|TVD)\b/.test(r.text)))return null;
  return {anchorName:named[0].name,course:course.value,courseResolution:course.resolution,reference:course.reference,evidenceIds:[...course.evidenceIds,...profileCourses.filter(r=>Number(r.text.replace(/[°º]/g,''))===course.value).flatMap(r=>r.evidenceIds)],origin:'published-localizer-final-and-profile'};
}
function betweenLabels(annotation,from,to){
  const p=center(annotation.bbox);return supportedLayout(annotation,from,to)&&from.some(a=>to.some(b=>{const x=center(a.bbox),y=center(b.bbox),dx=y.x-x.x,dy=y.y-x.y,coordinate=Math.abs(dx)>Math.abs(dy)?'x':'y';return p[coordinate]>=Math.min(x[coordinate],y[coordinate])&&p[coordinate]<=Math.max(x[coordinate],y[coordinate]);}));
}
function sameCourse(a,b){return a.reference===b.reference&&angleDifference(a.course,b.course)<1e-8;}
function roundingBound(distance,resolutionNM,annotation,variation){
  const halfAngle=(annotation.courseResolution+(annotation.reference==='magnetic'?variation?.resolution||0:0))/2;
  return {distanceNM:resolutionNM/2,angleDegrees:halfAngle,radiusNM:resolutionNM/2+2*distance*Math.sin(halfAngle*Math.PI/360),kind:'published-rounding-bound',includesAnchorUncertainty:false};
}
export function reconstructThreshold(model, interpreted, database, {truncated=false}={}) {
  const profile=thresholdProfile(interpreted,model.source.chart)||profileFromAxes(model);if(!profile)return;
  model.profileReferences=[profile];
  const target=model.points.find(p=>p.name===profile.target);
  if(!target||truncated)return;
  const planName=name=>interpreted.plan.filter(r=>norm(r.text)===name);
  const candidates=[];
  for(const station of profile.stations.filter(s=>s.distanceNM>0)){
    const anchor=model.points.find(p=>p.name===station.name);if(!anchor?.position||anchor.coordinateState==='ambiguous'||anchor.coordinateSource?.kind==='chart-derived')continue;
    for(const annotation of interpreted.annotations){
      if(!['magnetic','true'].includes(annotation.reference)||(annotation.reference==='magnetic'&&!Number.isFinite(model.reference.variation?.value)))continue;
      if(annotation.association&&(annotation.association.from!==anchor.id||annotation.association.to!==target.id))continue;
      if(Math.abs(station.distanceNM-annotation.distanceNM)>1e-8||!betweenLabels(annotation,planName(anchor.name),planName(target.name)))continue;
      // A profile station alone does not establish a direct leg: require the
      // explicit plan course/distance and a unique known anchor for that annotation.
      const course=normalize(annotation.course+(annotation.reference==='magnetic'?model.reference.variation.value:0));
      const coordinate=destination(anchor.position,course,station.distanceNM),zero=profile.stations.find(s=>s.distanceNM===0);
      const bound=roundingBound(station.distanceNM,station.resolutionNM+zero.resolutionNM,annotation,model.reference.variation);
      candidates.push({anchor,station,annotation,coordinate,bound});
    }
  }
  if(!candidates.length){
    const definition=localizerDefinition(model,interpreted,profile);
    if(definition)for(const station of profile.stations.filter(s=>s.distanceNM>0)){
      const anchor=model.points.find(p=>p.name===station.name);
      if(station.name!==definition.anchorName||!anchor?.position||!anchor.roles.some(r=>['FAF','FAP'].includes(r))||anchor.coordinateSource?.kind==='chart-derived'||anchor.coordinateState==='ambiguous')continue;
      if(definition.reference==='magnetic'&&!Number.isFinite(model.reference.variation?.value))continue;
      const annotation={...definition,id:'profile-final-'+anchor.id,distanceNM:station.distanceNM,distanceResolution:station.resolutionNM,profileEvidenceIds:station.evidenceIds};
      const coordinate=destination(anchor.position,normalize(annotation.course+(annotation.reference==='magnetic'?model.reference.variation.value:0)),station.distanceNM);
      candidates.push({anchor,station,annotation,coordinate,bound:roundingBound(station.distanceNM,station.resolutionNM+profile.stations.find(s=>s.distanceNM===0).resolutionNM,annotation,model.reference.variation)});
    }
  }
  if(!candidates.length)return;
  const closest=Math.min(...candidates.map(c=>c.station.distanceNM)),chosen=candidates.filter(c=>c.station.distanceNM===closest);
  if(chosen.length!==1){model.issues.push(problem('threshold-ambiguity','ambiguity','Mais de uma definição publicada pode localizar a cabeceira.',[target.id],{options:chosen.map(c=>({anchor:c.anchor.id,annotation:c.annotation.id}))}));return;}
  const candidate=chosen[0],{anchor,station,annotation,coordinate,bound}=candidate;
  const checks=[];
  // A second station requires an explicit collinear course/distance annotation.
  // This is a consistency check on shared evidence, not independent certification.
  for(const other of profile.stations.filter(s=>s.distanceNM>station.distanceNM)){
    const point=model.points.find(p=>p.name===other.name);
    const links=interpreted.annotations.filter(a=>(!a.association||(a.association.from===point?.id&&a.association.to===anchor.id))&&sameCourse(a,annotation)&&Math.abs(a.distanceNM-(other.distanceNM-station.distanceNM))<1e-8&&betweenLabels(a,planName(other.name),planName(anchor.name)));
    if(!point?.position||!links.length)continue;
    if(links.length!==1){model.issues.push(problem('threshold-check-ambiguity','ambiguity','Mais de uma definição para a referência de conferência da cabeceira.',[target.id,point.id]));return;}
    const link=links[0];
    const measured=inverse(point.position,anchor.position),difference=other.distanceNM-station.distanceNM;
    const interval=(other.resolutionNM+station.resolutionNM)/2+1e-6;
    const measuredCourse=normalize(measured.trueCourse-(annotation.reference==='magnetic'?model.reference.variation.value:0));
    const courseError=angleDifference(measuredCourse,annotation.course),courseInterval=(link.courseResolution+(annotation.reference==='magnetic'?model.reference.variation.resolution:0))/2+1e-6;
    const otherBound=roundingBound(other.distanceNM,other.resolutionNM+profile.stations.find(s=>s.distanceNM===0).resolutionNM,annotation,model.reference.variation);
    const otherCoordinate=destination(point.position,normalize(annotation.course+(annotation.reference==='magnetic'?model.reference.variation.value:0)),other.distanceNM),separation=inverse(coordinate,otherCoordinate).distanceNM;
    checks.push({anchor:point.id,annotation:link.id,publication:link,profileDistanceNM:other.distanceNM,coordinate:otherCoordinate,separationNM:separation,roundingBound:otherBound,courseError,courseInterval,passed:courseError<=courseInterval&&Math.abs(measured.distanceNM-difference)<=interval&&separation<=bound.radiusNM+otherBound.radiusNM+1e-6,evidenceIds:other.evidenceIds,sharedCourseEvidence:true});
  }
  if(checks.some(c=>!c.passed)){model.issues.push(problem('threshold-conflict','inconsistency','As referências do perfil e do plano divergem. A cabeceira não foi calculada automaticamente.',[target.id],{checks}));return;}
  for(const check of checks){const leg=model.legs.find(l=>l.from===check.anchor&&l.to===anchor.id);if(leg){leg.published={...check.publication};leg.source={kind:'profile-and-plan',evidenceIds:[...check.evidenceIds,...check.publication.evidenceIds]};}}
  const thresholds=database.thresholds.filter(p=>p.icao===model.source.chart.icao?.value&&p.runway===profile.runway);
  if(!target.position&&target.coordinateState!=='ambiguous'&&thresholds.length===1){const row=thresholds[0];target.position={...row.position};target.coordinateSource={...row.source,originalPosition:{...row.position}};target.coordinateState='threshold-database-review';model.issues.push(problem('threshold-database-review','inconsistency','Cabeceira associada à base local; conferir edição e correspondência com o waypoint da carta.',[target.id]));}
  if(thresholds.length>1&&!target.position){model.issues.push(problem('threshold-database-ambiguity','ambiguity','Mais de uma coordenada local para a cabeceira. Nenhuma foi escolhida.',[target.id]));return;}
  if(target.coordinateState==='ambiguous')return;
  const published={...annotation,distanceNM:station.distanceNM,profileEvidenceIds:station.evidenceIds};
  if(target.position){const separation=inverse(target.position,coordinate).distanceNM;if(separation>bound.radiusNM+1e-6){model.issues.push(problem('threshold-source-conflict','inconsistency','A coordenada existente da cabeceira diverge da reconstrução publicada; não foi deslocada.',[target.id],{existing:target.position,derived:coordinate,separationNM:separation,roundingBound:bound}));return;}}
  else{
    target.position=coordinate;target.coordinateState='derived-review';target.kind='threshold-reference';
    target.coordinateSource={kind:'chart-derived',method:annotation.origin==='published-localizer-final-and-profile'?'WGS84-direct-from-published-localizer-final-and-profile-distance':'WGS84-direct-from-published-course-and-profile-distance',definition:annotation.origin||'published-plan-course-and-distance',anchor:anchor.id,anchorPosition:{...anchor.position},anchorSource:structuredClone(anchor.coordinateSource),course:annotation.course,reference:annotation.reference,variation:structuredClone(model.reference.variation),distanceNM:station.distanceNM,roundingBound:bound,crossChecks:checks,evidenceIds:[...station.evidenceIds,...annotation.evidenceIds],originalPosition:{...coordinate}};
    model.issues.push(problem('derived-'+target.id,'missing','Cabeceira calculada de curso/distância publicados arredondados. Posição derivada, não coordenada oficial; conferir origens e precisão.',[target.id],{roundingBound:bound}));
  }
  const retained=model.issues.filter(i=>i.id!=='coordinate-'+target.id&&i.id!=='unassociated-'+annotation.id&&i.id!=='association-'+annotation.id&&!checks.some(c=>i.id==='association-'+c.annotation));model.issues.splice(0,model.issues.length,...retained);
  const legId='l-'+anchor.id+'-'+target.id,existing=model.legs.find(l=>l.id===legId);
  const leg=existing||{id:legId,type:'line',from:anchor.id,to:target.id,published,calculated:inverse(anchor.position,target.position),source:{kind:annotation.origin==='published-localizer-final-and-profile'?'published-localizer-profile':'profile-and-plan',evidenceIds:[...station.evidenceIds,...annotation.evidenceIds]},status:'candidate'};
  if(profile.visual){leg.flightRules='visual-transition-review';leg.visualReference=profile.visual;model.issues.push(problem('visual-boundary-'+leg.id,'ambiguity','PROSSIGA VMC identificado na final. Os limites do trecho visual ainda precisam de conferência; a ligação inteira não foi classificada como instrumental nem visual.',[leg.id],{evidenceIds:profile.visual.evidenceIds}));}
  if(!existing)model.legs.push(leg);
}
