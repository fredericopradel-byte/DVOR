import {roleNames} from './semantics.mjs';
// Layout is evidence for association/topology only. No page coordinate becomes a position.
const multiply=(a,b)=>[a[0]*b[0]+a[2]*b[1],a[1]*b[0]+a[3]*b[1],a[0]*b[2]+a[2]*b[3],a[1]*b[2]+a[3]*b[3],a[0]*b[4]+a[2]*b[5]+a[4],a[1]*b[4]+a[3]*b[5]+a[5]];
const point=(m,x,y)=>({x:m[0]*x+m[2]*y+m[4],y:m[1]*x+m[3]*y+m[5]});
const norm=s=>String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase();
const box=points=>[Math.min(...points.map(p=>p.x)),Math.min(...points.map(p=>p.y)),Math.max(...points.map(p=>p.x))-Math.min(...points.map(p=>p.x)),Math.max(...points.map(p=>p.y))-Math.min(...points.map(p=>p.y))];
export const center=b=>({x:b[0]+b[2]/2,y:b[1]+b[3]/2});
export function textRuns(extraction) {
  const viewport=extraction.pageTransform||[1,0,0,-1,0,extraction.height],groups=[];
  for(const item of extraction.text||[]) {
    const m=item.pageMatrix||multiply(viewport,item.transform),h=Math.hypot(m[2],m[3]),angle=Math.atan2(m[1],m[0]);
    const u={x:Math.cos(angle),y:Math.sin(angle)},along=m[4]*u.x+m[5]*u.y,baseline=-m[4]*u.y+m[5]*u.x;
    const glyph={...item,m,h,angle,u,along,baseline};
    const group=groups.find(g=>Math.abs(g.angle-angle)<.015 && Math.abs(g.baseline-baseline)<Math.max(.7,h*.18) && Math.abs(g.h-h)<Math.max(1,h*.22));
    if(group)group.items.push(glyph);else groups.push({angle,baseline,h,items:[glyph]});
  }
  const runs=[];
  for(const group of groups) {
    group.items.sort((a,b)=>a.along-b.along);let current=[];
    function flush(){if(!current.length)return;const first=current[0],corners=current.flatMap(i=>[point(i.m,0,0),{x:i.m[4]+i.u.x*i.width,y:i.m[5]+i.u.y*i.width},point(i.m,0,1),{x:i.m[4]+i.u.x*i.width+i.m[2],y:i.m[5]+i.u.y*i.width+i.m[3]}]);
      let text='';for(let i=0;i<current.length;i++){const a=current[i],prior=current[i-1],gap=prior?a.along-prior.along-prior.width:0;text+=(prior&&gap>Math.min(prior.h,a.h)*.18?' ':'')+a.text;}
      runs.push({text:text.trim(),bbox:box(corners),angle:first.angle,height:first.h,evidenceIds:current.map(i=>i.id)});current=[];}
    for(const item of group.items){const prior=current.at(-1);if(prior && item.along-prior.along-prior.width>Math.max(2,item.h*.7))flush();current.push(item);}flush();
  }
  return runs;
}
export function graphics(extraction, runs=textRuns(extraction)) {
  let matrix=[1,0,0,1,0,0],path=[],stack=[];const frames=[],lines=[];
  const viewport=extraction.pageTransform||[1,0,0,-1,0,extraction.height];
  for(const op of extraction.vectors||[]) {
    if(op.operator==='save')stack.push([...matrix]);
    else if(op.operator==='restore')matrix=stack.pop()||[1,0,0,1,0,0];
    else if(op.operator==='transform')matrix=multiply(matrix,op.args);
    else if(op.operator==='constructPath') {
      path=[];const [ops,coords]=op.args,m=multiply(viewport,matrix);let i=0,previous=null,start=null,straight=true;
      for(const code of ops) {
        if(code===13){previous=point(m,coords[i++],coords[i++]);start=previous;}
        else if(code===14){const next=point(m,coords[i++],coords[i++]);if(previous)path.push({a:previous,b:next,evidenceId:'vector-'+op.index});previous=next;}
        else if(code===18){if(previous&&start)path.push({a:previous,b:start,evidenceId:'vector-'+op.index});previous=start;}
        else if(code===19){const [x,y,w,h]=coords.slice(i,i+4);i+=4;const p=[point(m,x,y),point(m,x+w,y),point(m,x+w,y+h),point(m,x,y+h)];path.push(...p.map((a,j)=>({a,b:p[(j+1)%4],evidenceId:'vector-'+op.index})));}
        else {straight=false;break;}
      }
      if(straight && path.length>=4 && path.length<=5) {
        const b=box(path.flatMap(l=>[l.a,l.b]));
        if(b[2]>extraction.width*.8 && b[3]>extraction.height*.25 && b[3]<extraction.height*.9 && b[1]>extraction.height*.06 && b[1]+b[3]<extraction.height*.96) frames.push({bbox:b,evidenceId:'vector-'+op.index});
      }
    } else if(['stroke','closeStroke','fillStroke','eoFillStroke','closeFillStroke','closeEOFillStroke'].includes(op.operator)) lines.push(...path.filter(l=>Math.abs(l.a.y-l.b.y)<.2));
    else if(['fill','eoFill'].includes(op.operator)&&path.length>=4&&path.length<=5){
      const bounds=box(path.flatMap(l=>[l.a,l.b]));
      // Under/overlines may be thin filled rectangles rather than stroked paths.
      if(bounds[3]>0&&bounds[3]<1.2&&bounds[2]>bounds[3]*4)lines.push({a:{x:bounds[0],y:bounds[1]+bounds[3]/2},b:{x:bounds[0]+bounds[2],y:bounds[1]+bounds[3]/2},evidenceId:path[0].evidenceId});
    }
  }
  let frame=frames.sort((a,b)=>b.bbox[2]*b.bbox[3]-a.bbox[2]*a.bbox[3])[0]||null;
  if(!frame){
    const wide=lines.filter(l=>Math.abs(l.a.x-l.b.x)>extraction.width*.8),pairs=[];
    for(const top of wide)for(const bottom of wide)if(top.a.y>extraction.height*.18&&top.a.y<extraction.height*.3&&bottom.a.y>extraction.height*.55&&bottom.a.y<extraction.height*.7&&Math.abs(Math.min(top.a.x,top.b.x)-Math.min(bottom.a.x,bottom.b.x))<2)pairs.push({bbox:[Math.min(top.a.x,top.b.x),top.a.y,Math.abs(top.a.x-top.b.x),bottom.a.y-top.a.y],evidenceIds:[top.evidenceId,bottom.evidenceId],rule:'decea-horizontal-plan-borders'});
    const unique=[...new Map(pairs.map(p=>[p.bbox.map(v=>v.toFixed(1)).join(':'),p])).values()];if(unique.length===1)frame=unique[0];
  }
  // Reassemble plan borders even when the PDF encodes each side in a separate path.
  // Select the tightest border pair enclosing map reference labels AND point-function labels.
  // This avoids treating a larger rectangle containing missed-approach prose as the plan.
  const references=runs.filter(r=>/\b(?:BRG|DIST)\s*:|\bVAR\s*\d/i.test(r.text)),roles=runs.filter(r=>/^\(/.test(r.text)&&roleNames(r).length);
  if(references.length>=2&&roles.length){
    const anchors=[...references,...roles],wide=lines.filter(l=>Math.abs(l.a.x-l.b.x)>extraction.width*.8),candidates=[];
    for(const top of wide)for(const bottom of wide){
      const x=Math.min(top.a.x,top.b.x),w=Math.abs(top.a.x-top.b.x),y=top.a.y,h=bottom.a.y-y;
      if(h<extraction.height*.2||h>extraction.height*.8||Math.abs(x-Math.min(bottom.a.x,bottom.b.x))>2||Math.abs(w-Math.abs(bottom.a.x-bottom.b.x))>2)continue;
      const bbox=[x,y,w,h];
      if(anchors.every(r=>inBox(r,{bbox})))candidates.push({bbox,evidenceIds:[top.evidenceId,bottom.evidenceId,...anchors.flatMap(r=>r.evidenceIds)],rule:'map-references-and-function-labels'});
    }
    const unique=[...new Map(candidates.map(c=>[c.bbox.map(v=>v.toFixed(1)).join(':'),c])).values()].sort((a,b)=>a.bbox[2]*a.bbox[3]-b.bbox[2]*b.bbox[3]);
    if(unique.length&&(!unique[1]||unique[1].bbox[2]*unique[1].bbox[3]-unique[0].bbox[2]*unique[0].bbox[3]>1))frame=unique[0];
  }
  return {frame,lines};
}
export function inBox(run, area) {const c=center(run.bbox),b=area.bbox;return c.x>=b[0]&&c.x<=b[0]+b[2]&&c.y>=b[1]&&c.y<=b[1]+b[3];}
export function interpret(extraction, recognition) {
  const runs=textRuns(extraction), graphic=graphics(extraction,runs), issues=[];
  const providerText=[...(extraction.lines||[]).map(l=>l.text),...runs.map(r=>r.text)].join(' ');
  const compatible=norm(providerText).replace(/[^A-Z]/g,'').includes('DEPARTAMENTODECONTROLE')&&['IAC','SID'].includes(recognition.metadata.kind?.value);
  if(!compatible&&runs.length)issues.push({id:'provider-unsupported',category:'missing',critical:true,message:'Formato sem interpretador local compatível. A extração foi preservada; nenhuma trajetória foi presumida.'});
  if(!graphic.frame && runs.length)issues.push({id:'layout-missing',category:'missing',critical:true,message:'Limites do plano horizontal não reconhecidos. Associação geométrica automática suspensa.'});
  const plan=graphic.frame&&compatible?runs.filter(r=>inBox(r,graphic.frame)):[];
  const allText=[...(extraction.lines||[]).map(l=>l.text),...runs.map(r=>r.text)].join(' ');
  const reference=/\bBRG\s*:\s*MAG\b/i.test(allText)?'magnetic':/\bBRG\s*:\s*(?:TRUE|VERD)\b/i.test(allText)?'true':'unknown';
  const variations=[];
  for(const run of runs) {
    const m=norm(run.text).match(/VAR\s*(\d{1,2}(?:\.\d+)?)(?:\D{0,8}([WE])\b)?/);
    if(m){let direction=m[2],evidenceIds=[...run.evidenceIds];
      if(!direction){const c=center(run.bbox),neighbors=runs.filter(r=>/^[WE](?:\s*-)?$/.test(norm(r.text))&&Math.abs(r.angle-run.angle)<.02&&Math.hypot(center(r.bbox).x-c.x,center(r.bbox).y-c.y)<run.height*10);if(neighbors.length===1){direction=norm(neighbors[0].text)[0];evidenceIds.push(...neighbors[0].evidenceIds);}}
      if(direction)variations.push({value:Number(m[1])*(direction==='W'?-1:1),resolution:m[1].includes('.')?10**(-m[1].split('.')[1].length):1,evidenceIds,origin:'chart-published',epoch:'as-published-in-chart',chartDate:recognition.metadata.publishedDate?.value||''});
    }
  }
  const distinct=[...new Map(variations.map(v=>[v.value,v])).values()],variation=distinct.length===1?distinct[0]:null;
  if(reference==='unknown'||(reference==='magnetic'&&!variation))issues.push({id:'magnetic-reference',category:distinct.length>1?'ambiguity':'missing',critical:true,message:'Referência dos cursos ou declinação publicada não determinada com segurança. Cursos não serão convertidos por suposição.'});
  const courses=plan.filter(r=>/^\d{3}[º°]?$/.test(r.text)&&Number(r.text.replace(/[º°]/g,''))<=360);
  const distances=plan.filter(r=>/^\d{1,3}\.\d{1,2}$/.test(r.text)&&Number(r.text)>0&&Number(r.text)<=500);
  const annotations=[];
  for(const distance of distances) {
    const dc=center(distance.bbox);
    const near=courses.filter(c=>Math.abs(c.angle-distance.angle)<.06).map(course=>({course,gap:Math.hypot(center(course.bbox).x-dc.x,center(course.bbox).y-dc.y)})).filter(c=>c.gap<Math.max(distance.height,c.height||distance.height)*4).sort((a,b)=>a.gap-b.gap);
    if(!near.length)continue;
    if(near[1]&&Math.abs(near[0].gap-near[1].gap)<.5)continue;
    const course=near[0].course;
    annotations.push({id:'annotation-'+annotations.length,course:Number(course.text.replace(/[º°]/g,'')),distanceNM:Number(distance.text),courseResolution:1,distanceResolution:10**(-distance.text.split('.')[1].length),reference,bbox:box([center(course.bbox),dc]),evidenceIds:[...course.evidenceIds,...distance.evidenceIds]});
  }
  const aids=[];
  for(const run of runs) {
    const text=norm(run.text);
    for(const match of text.matchAll(/\b(\d{3}(?:\.\d+)?)\s*([A-Z]{2,3})\b/g)) {
      const frequency=Number(match[1]);if(match[2]==='MHZ'||match[2]==='KHZ')continue;
      if(frequency>=108&&frequency<=117.975)aids.push({name:match[2],frequency:{value:frequency,unit:'MHZ'},type:null,evidenceIds:run.evidenceIds});
      else if(recognition.navigation.includes('NDB')&&frequency>=190&&frequency<=1750&&inBox(run,graphic.frame||{bbox:[0,0,0,0]})&&plan.some(r=>/^NDB$/.test(norm(r.text))&&Math.hypot(center(r.bbox).x-center(run.bbox).x,center(r.bbox).y-center(run.bbox).y)<40))aids.push({name:match[2],frequency:{value:frequency,unit:'KHZ'},type:'NDB',evidenceIds:run.evidenceIds});
    }
  }
  const gradients=[];
  for(const run of runs) for(const match of run.text.matchAll(/\b(\d+(?:[.,]\d+)?)\s*%/g))gradients.push({value:Number(match[1].replace(',','.')),unit:'percent',scope:'unresolved',evidenceIds:run.evidenceIds});
  return {provider:compatible?'decea-digital-v1':'unsupported-local',runs,plan,frame:compatible?graphic.frame:null,lines:graphic.lines,reference,variation,annotations,aids,gradients,positions:compatible?publishedPositions(extraction):[],issues};
}
export function publishedPositions(extraction){
  const rows=[],datum=/WGS\s*[- ]?84/i.test((extraction.lines||[]).map(l=>l.text).join(' '));
  const pattern=/\b([A-Z][A-Z0-9]{2,5})\s+(\d{1,2})[°º]\s*(\d{1,2})['’′]\s*(\d{1,2}(?:[.,]\d+)?)["”″]?\s*([NS])\s*[,;/]?\s*(\d{1,3})[°º]\s*(\d{1,2})['’′]\s*(\d{1,2}(?:[.,]\d+)?)["”″]?\s*([EW])\b/g;
  for(const line of extraction.lines||[])for(const m of norm(line.text).matchAll(pattern)){
    const [latDeg,latMin,latSec,lonDeg,lonMin,lonSec]=[m[2],m[3],m[4],m[6],m[7],m[8]].map(v=>Number(v.replace(',','.')));
    if(latMin>=60||latSec>=60||lonMin>=60||lonSec>=60)continue;
    const lat=(latDeg+latMin/60+latSec/3600)*(m[5]==='S'?-1:1),lon=(lonDeg+lonMin/60+lonSec/3600)*(m[9]==='W'?-1:1);
    if(Math.abs(lat)>=89||Math.abs(lon)>180)continue;
    const resolution=value=>value.includes('.')||value.includes(',')?10**(-value.split(/[.,]/)[1].length):1;
    rows.push({name:m[1],position:{lat,lon},datum:datum?'WGS84':'unspecified',raw:m[0],resolutionNM:Math.hypot(resolution(m[4]),resolution(m[8]))/120,evidenceIds:line.evidenceIds});
  }return rows;
}
export function supportedLayout(annotation, from, to) {
  const p=center(annotation.bbox);
  return from.some(a=>to.some(b=>{
    const aa=center(a.bbox),bb=center(b.bbox),dx=bb.x-aa.x,dy=bb.y-aa.y,L=Math.hypot(dx,dy);if(L<8)return false;
    const t=((p.x-aa.x)*dx+(p.y-aa.y)*dy)/(L*L),cross=Math.abs((p.x-aa.x)*dy-(p.y-aa.y)*dx)/L;
    // Identifier labels can be rotated and offset from the symbol. Account for the
    // extent perpendicular to the candidate leg, not unrelated prose occurrences.
    const extent=run=>(Math.abs(dy)*run.bbox[2]+Math.abs(dx)*run.bbox[3])/(2*L);
    const labelAllowance=Math.min(Math.max(extent(a),extent(b)),Math.max(a.height,b.height)*3);
    return t>=-.25&&t<=1.25&&cross<=Math.max(24,a.height*6,b.height*6,L*.3)+labelAllowance;
  }));
}
