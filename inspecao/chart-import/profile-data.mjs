import {center, textRuns} from './decea.mjs';
import {roleNames, labelType} from './semantics.mjs';
const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().toUpperCase();
const number=/^\d{1,3}(?:\.\d{1,12})?$/;
const precision=s=>s.includes('.')?10**(-s.split('.')[1].length):1;
const issue=(id,message,evidenceIds=[],entities=[])=>({id,category:'ambiguity',critical:true,message,evidenceIds,entities});
const unique=a=>[...new Set(a)];
function reference(text){
  let m=norm(text).match(/^TO\s+THR\s*(\d{2}[LRC]?)\s*\((NM|DME)\)$/);
  if(m)return {kind:'threshold',runway:m[1],name:'THR'+m[1],publishedUnit:m[2],distanceKind:m[2]==='NM'?'published-profile-along-track':'threshold-reference-dme-labelled'};
  if(/^TO\s+MAPT\s*\(NM\)$/.test(norm(text)))return {kind:'mapt',name:'MAPt',publishedUnit:'NM',distanceKind:'published-profile-along-track'};
  m=norm(text).match(/^TO\s+([A-Z][A-Z0-9]{1,7})\s*\(DME\)$/);
  return m?{kind:'dme',name:m[1],publishedUnit:'DME',distanceKind:'slant-range'}:null;
}
function tokens(runs,extraction){
  return runs.flatMap(run=>{
    if(number.test(run.text))return [run];
    // Some PDFs place complete adjacent numbers without whitespace. Recover only
    // explicit source items, never split an ambiguous string by guessing decimals.
    if(!/^[\d.]+$/.test(run.text)||!extraction?.text)return [];
    const items=extraction.text.filter(i=>run.evidenceIds.includes(i.id)).sort((a,b)=>a.bbox[0]-b.bbox[0]);
    if(items.length<2||items.some(i=>!number.test(i.text)||!i.text.includes('.'))||items.map(i=>i.text).join('')!==run.text)return [];
    return items.flatMap(i=>textRuns({...extraction,text:[i]}));
  });
}
export function profileData(interpreted,metadata,extraction={}){
  const empty={schema:'ivplanner-published-profile-v1',axes:[],stations:[],minima:[],gradients:[],conditions:[],issues:[],finalCourse:null};
  if(interpreted.provider!=='decea-digital-v1'||!interpreted.frame||metadata.kind?.value!=='IAC')return empty;
  const out=empty,runs=interpreted.runs,bottom=interpreted.frame.bbox[1]+interpreted.frame.bbox[3];
  for(const label of runs.filter(r=>r.bbox[1]>bottom&&reference(r.text))){
    const ref=reference(label.text),id='profile-axis-'+label.evidenceIds[0],y=center(label.bbox).y;
    const row=runs.filter(r=>Math.abs(center(r.bbox).y-y)<label.height*.45&&Math.abs(r.angle)<.03&&r!==label);
    const marks=tokens(row,extraction).filter(r=>number.test(r.text)).map(r=>({valueNM:Number(r.text),raw:r.text,resolutionNM:precision(r.text),bbox:r.bbox,evidenceIds:r.evidenceIds}));
    const axis={id,reference:ref,unit:'NM',raw:label.text,bbox:label.bbox,marks,evidenceIds:label.evidenceIds,status:'extracted'};out.axes.push(axis);
    if(ref.kind==='threshold'&&ref.runway!==metadata.runway?.value)out.issues.push(issue('profile-runway-'+id,'Cabeceira do eixo de distâncias diverge da identificação da carta.',label.evidenceIds));
    if(ref.distanceKind==='threshold-reference-dme-labelled')out.issues.push(issue('profile-distance-kind-'+id,'Escala da cabeceira publicada com rótulo DME. Natureza da distância a confirmar; não foi usada como distância horizontal.',label.evidenceIds));
    if(marks.length<2)out.issues.push(issue('profile-axis-incomplete-'+id,'Escala de distância incompleta ou sem números separáveis com segurança.',row.flatMap(r=>r.evidenceIds)));
    if(row.some(r=>/^[\d.]+$/.test(r.text)&&!number.test(r.text)&&!tokens([r],extraction).length))out.issues.push(issue('profile-axis-numbers-'+id,'Números contíguos do perfil sem separação verificável na origem.',row.flatMap(r=>r.evidenceIds)));
  }
  const firstAxis=out.axes.length?Math.min(...out.axes.map(a=>a.bbox[1])):bottom+120;
  const labels=runs.filter(r=>r.bbox[1]>bottom&&r.bbox[1]<firstAxis&&Math.abs(r.angle)<.03&&labelType(r)==='identifier-candidate'&&!/^(?:DA|MDA|MSL|LNAV|VNAV|FROP|RDH|TCH|TA|ALT)$/.test(norm(r.text)));
  const functions=runs.filter(r=>roleNames(r).length||/^MAPT\s+LOC$|^FROP$/.test(norm(r.text)));
  for(const label of labels){
    const x=center(label.bbox).x,distances=[];
    for(const axis of out.axes){const near=axis.marks.filter(m=>Math.abs(center(m.bbox).x-x)<=label.height*.8+1e-7);
      if(near.length===1)distances.push({axisId:axis.id,reference:axis.reference,valueNM:near[0].valueNM,resolutionNM:near[0].resolutionNM,raw:near[0].raw,evidenceIds:[...axis.evidenceIds,...near[0].evidenceIds]});
      else if(near.length>1)out.issues.push(issue('profile-column-'+axis.id+'-'+label.evidenceIds[0],'Mais de uma marca de distância corresponde à coluna do ponto.',[...label.evidenceIds,...near.flatMap(m=>m.evidenceIds)]));
    }
    if(!distances.length)continue;
    const nearby=functions.filter(r=>r.bbox[1]<=label.bbox[1]&&label.bbox[1]-r.bbox[1]<label.height*4&&Math.abs(center(r.bbox).x-x)<label.height*1.2);
    const roles=unique(nearby.flatMap(r=>roleNames(r).length?roleNames(r):[norm(r.text).startsWith('MAPT')?'MAPT':'FROP']));
    const alts=runs.filter(r=>/^\d{2,5}['’′]$/.test(r.text)&&r.bbox[1]>=label.bbox[1]+label.bbox[3]-.5&&r.bbox[1]<label.bbox[1]+label.height*3.5&&Math.abs(center(r.bbox).x-x)<label.height*.85);
    const values=unique(alts.map(r=>parseInt(r.text)));
    out.stations.push({id:'profile-station-'+label.evidenceIds[0],name:norm(label.text),roles,bbox:label.bbox,evidenceIds:[...label.evidenceIds,...nearby.flatMap(r=>r.evidenceIds)],distances,altitude:values.length===1?{value:values[0],unit:'FT',reference:'MSL',qualifier:'unspecified',evidenceIds:alts.flatMap(r=>r.evidenceIds)}:null});
    if(values.length>1)out.issues.push(issue('profile-altitudes-'+label.evidenceIds[0],'Mais de uma altitude publicada na coluna do ponto.',alts.flatMap(r=>r.evidenceIds)));
  }
  // Explicit DA/MDA pairs remain publications, never mission clearances/minima inputs.
  for(const r of runs){
    const match=norm(r.text).match(/\b(MDA|DA)\s*\/\s*\(OCH\)\s*:\s*(\d{2,5})['’′]\s*\/\s*\((\d{1,5})['’′]\)/);
    if(!match)continue;
    const above=runs.filter(t=>t.bbox[1]<r.bbox[1]&&r.bbox[1]-t.bbox[1]<r.height*2&&Math.abs(center(t.bbox).x-center(r.bbox).x)<r.height*2&&/^(?:LOC|ILS|CAT\s*(?:I|II|III)|LNAV(?:\/VNAV)?|VOR(?:\/DME)?)$/.test(norm(t.text)));
    out.minima.push({id:'published-minimum-'+r.evidenceIds[0],type:match[1],value:Number(match[2]),unit:'FT',reference:'MSL',ochFT:Number(match[3]),variant:above.length===1?norm(above[0].text):null,scope:'header-publication',status:'review',evidenceIds:[...r.evidenceIds,...above.flatMap(a=>a.evidenceIds)],raw:r.text});
  }
  const crs=runs.filter(r=>norm(r.text)==='FINAL CRS');
  if(crs.length===1){const label=crs[0],near=runs.filter(r=>/^\d{3}[°º]$/.test(r.text)&&r.bbox[1]>label.bbox[1]&&r.bbox[1]-label.bbox[1]<label.height*3&&Math.abs(center(r.bbox).x-center(label.bbox).x)<label.height*2);
    if(near.length===1)out.finalCourse={value:Number(near[0].text.replace(/[°º]/g,'')),resolution:1,reference:interpreted.reference,evidenceIds:[...label.evidenceIds,...near[0].evidenceIds]};
  }
  for(const g of interpreted.gradients||[]){const contexts=(extraction.lines||[]).filter(l=>l.evidenceIds?.some(id=>g.evidenceIds.includes(id))),text=contexts.map(l=>l.text).join(' '),source=runs.find(r=>r.evidenceIds.some(id=>g.evidenceIds.includes(id)));
    const scope=/APCH\s+PERDIDA|MISSED\s+APCH/i.test(norm(text))?'missed-approach':source?.bbox[1]>bottom&&source.bbox[1]<firstAxis?'approach-profile':'unresolved';
    out.gradients.push({...g,id:'published-gradient-'+out.gradients.length,scope,status:'review',context:text,evidenceIds:unique([...g.evidenceIds,...contexts.flatMap(l=>l.evidenceIds||[])])});
  }
  for(const l of extraction.lines||[])if(/APCH\s+PERDIDA|MISSED\s+APCH/i.test(norm(l.text)))out.conditions.push({id:'published-condition-'+out.conditions.length,scope:'missed-approach',raw:l.text,status:'unresolved-sequencing',evidenceIds:l.evidenceIds||[]});
  return out;
}

export const distanceDescription=ref=>({'published-profile-along-track':'distância publicada no perfil em NM','slant-range':'distância DME oblíqua','threshold-reference-dme-labelled':'referência da cabeceira rotulada DME; natureza a conferir'})[ref.distanceKind]||'natureza a conferir';
export const gradientDescription=scope=>({'missed-approach':'aproximação perdida','approach-profile':'perfil de aproximação',unresolved:'trecho a conferir'})[scope]||'trecho a conferir';
