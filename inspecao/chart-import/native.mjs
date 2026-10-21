import {toNative, inverse, destination, normalize} from './geodesy.mjs';

// Native schema 3 envelope. Provenance remains in the persisted IR/nativeMapping;
// this stage never writes the document into the mission editor.
export function toNativeDocument(model) {
  const issues=[],mapping={points:{},legs:{},derived:[],projection:[]};
  const valid=model.points.filter(p=>p.position),first=valid[0],variation=model.reference.variation?.value||0;
  const origin={lat:first?.position.lat??'',lon:first?.position.lon??'',mag:Math.abs(variation),dir:variation<0?'W':'E'};
  const document={format:'ivplanner-procedure-drawing',version:3,module:model.module,title:model.source.chart.procedure?.value||'Prévia parcial da carta',kind:model.source.chart.kind?.value==='SID'?'SID':'IAC',origin,mission:{},restrictions:{},points:[],segments:[],flight:{start:'',end:'',segments:[]},splitSources:{}};
  const points=new Map(model.points.map(p=>[p.id,p]));
  for(const p of valid){const local=toNative(p.position,origin);if(Math.abs(local.x)>1000||Math.abs(local.y)>1000){issues.push(problem('range-'+p.id,'Ponto fora dos limites do editor.',[p.id]));continue;}mapping.points[p.id]=p.id;document.points.push({id:p.id,name:p.name,x:local.x,y:local.y,locked:false});}
  for(const leg of model.legs){
    if(!mapping.points[leg.from]||!mapping.points[leg.to]||model.checks.some(c=>c.entity===leg.id&&!c.passed))continue;
    if(leg.type==='line'){
      document.segments.push({id:leg.id,type:'line',from:leg.from,to:leg.to,name:'',locked:false,lockBearing:false,lockLength:false,lockRadius:false});mapping.legs[leg.id]=[leg.id];
    }else if(leg.type==='arc'){
      const center=points.get(leg.center),a=points.get(leg.from),b=points.get(leg.to);
      if(!center?.position||!['left','right'].includes(leg.turn)||!Number.isFinite(leg.radiusNM)){issues.push(problem('native-arc-'+leg.id,'Arco incompleto não convertido.',[leg.id]));continue;}
      const start=inverse(center.position,a.position).trueCourse,end=inverse(center.position,b.position).trueCourse,sign=leg.turn==='right'?1:-1;
      const measuredSweep=normalize(sign*(end-start));
      if(measuredSweep<1e-8&&leg.sweepDegrees!==360){issues.push(problem('arc-sweep-'+leg.id,'Arco sem extensão angular confirmada.',[leg.id]));continue;}
      const sweep=measuredSweep<1e-8?360:measuredSweep,parts=Math.ceil(sweep/90),midpoints=[],segments=[],ids=[];let previous=document.points.find(p=>p.id===leg.from),failed=false,maxError=0;
      const cp=toNative(center.position,origin);
      for(let i=1;i<=parts;i++){
        let next;
        if(i===parts)next=document.points.find(p=>p.id===leg.to);
        else{const geographic=destination(center.position,start+sign*sweep*i/parts,leg.radiusNM),local=toNative(geographic,origin),nativeId=leg.id+'-split-'+i;next={id:nativeId,name:'ARCO '+i,...local,locked:false};midpoints.push(next);mapping.derived.push({id:nativeId,leg:leg.id,position:geographic,source:'geodesic-arc-subdivision'});}
        const ra=Math.hypot(previous.x-cp.x,previous.y-cp.y),rb=Math.hypot(next.x-cp.x,next.y-cp.y),radius=(ra+rb)/2,d=Math.hypot(next.x-previous.x,next.y-previous.y);
        if(d<.001||radius<d/2){failed=true;break;}
        const side=leg.turn==='right'?1:-1,h=Math.sqrt(Math.max(0,radius*radius-d*d/4)),cx=(previous.x+next.x)/2+(next.y-previous.y)/d*h*side,cy=(previous.y+next.y)/2-(next.x-previous.x)/d*h*side,error=Math.hypot(cx-cp.x,cy-cp.y);
        maxError=Math.max(maxError,error);if(error>.05){failed=true;break;}
        const nativeId=leg.id+'-arc-'+i;ids.push(nativeId);segments.push({id:nativeId,type:'curve',from:previous.id,to:next.id,radius,side,name:'',locked:false,lockBearing:false,lockLength:false,lockRadius:false});previous=next;
      }
      if(failed){mapping.derived=mapping.derived.filter(p=>p.leg!==leg.id);issues.push(problem('projection-'+leg.id,'O arco geodésico não pode ser representado fielmente no plano local do editor; não foi substituído por reta.',[leg.id]));continue;}
      document.points.push(...midpoints);document.segments.push(...segments);mapping.legs[leg.id]=ids;
      mapping.projection.push({leg:leg.id,publishedRadiusNM:leg.radiusNM,maxCenterErrorNM:maxError,kind:'local-plane-circle',displayResolutionNM:.1});
      if(maxError>1e-6)issues.push(problem('projection-review-'+leg.id,'Arco representado como curva local; erro de projeção registrado para conferência.',[leg.id],{maxCenterErrorNM:maxError}));
    }else issues.push(problem('native-type-'+leg.id,'Trajetória sem representação nativa fiel: '+leg.type+'.',[leg.id]));
  }
  const supportedRoles=['IAF','IF','FAF','FAP','MAPT','DER'];
  for(const point of valid){const roles=(point.roles||[]).filter(r=>supportedRoles.includes(r));if(roles.length===1)document.restrictions[point.id]={role:roles[0],phase:''};}
  for(const r of model.verticalConstraints||[]){
    if(!Number.isFinite(r.lower??r.value)||(r.qualifier==='between'&&(!Number.isFinite(r.upper)||r.upper<(r.lower??r.value))))continue;
    if(!mapping.points[r.entity]||r.unit!=='FT'||r.reference!=='MSL'||!['at','above','below','between'].includes(r.qualifier))continue;
    document.restrictions[r.entity]={...document.restrictions[r.entity],qualifier:r.qualifier,altitude:String(r.lower??r.value),upperAltitude:r.upper===undefined?'':String(r.upper),plannedAltitude:'',inspectionAltitude:'',phase:''};
  }
  if(model.paths.length===1&&!model.paths[0].cycle&&model.paths[0].legs.length===model.legs.length&&model.paths[0].legs.every(id=>mapping.legs[id])){
    const route=model.paths[0].legs.flatMap(id=>mapping.legs[id]);if(route.length){document.flight={start:document.segments.find(l=>l.id===route[0]).from,end:document.segments.find(l=>l.id===route.at(-1)).to,segments:route};}
  }
  if(document.points.length>500||document.segments.length>700)throw Error('Conversão acima dos limites do editor. O modelo intermediário deve ser dividido explicitamente.');
  return {document,mapping,issues};
}
function problem(id,message,entities,extra={}){return {id,category:'inconsistency',critical:true,message,entities,...extra};}
