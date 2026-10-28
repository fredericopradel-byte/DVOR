import {normalize,toNative} from './geodesy.mjs';
const length=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
export function triangleSymbols(primitives,size){
  const edges=primitives.lines.filter(l=>length(l.a,l.b)>=size*.6&&length(l.a,l.b)<=size*2),nodes=[],grid=new Map(),step=size*.01;
  if(edges.length>30000)return [];
  function vertex(p){const x=Math.floor(p.x/step),y=Math.floor(p.y/step);for(let i=x-1;i<=x+1;i++)for(let j=y-1;j<=y+1;j++)for(const n of grid.get(i+':'+j)||[])if(length(p,n.p)<step)return n;const n={p,edges:[],id:nodes.length};nodes.push(n);const key=x+':'+y;grid.set(key,[...(grid.get(key)||[]),n]);return n;}
  for(const edge of edges){const a=vertex(edge.a),b=vertex(edge.b);if(a!==b){a.edges.push({to:b,edge});b.edges.push({to:a,edge});}}
  const out=primitives.symbols.filter(s=>!s.filled);
  for(const a of nodes)if(a.edges.length<=4)for(const ab of a.edges)if(ab.to.id>a.id&&ab.to.edges.length<=4)for(const bc of ab.to.edges)if(bc.to.id>ab.to.id&&bc.to.edges.length<=4){const ca=bc.to.edges.find(e=>e.to===a);if(!ca)continue;const sizes=[length(a.p,ab.to.p),length(ab.to.p,bc.to.p),length(bc.to.p,a.p)];if(Math.max(...sizes)/Math.min(...sizes)>1.15)continue;out.push({position:{x:(a.p.x+ab.to.p.x+bc.to.p.x)/3,y:(a.p.y+ab.to.p.y+bc.to.p.y)/3},size:Math.max(...sizes),evidenceIds:[...new Set([...ab.edge.evidenceIds,...bc.edge.evidenceIds,...ca.edge.evidenceIds])]});}
  return [...new Map(out.map(s=>[Math.round(s.position.x/step)+':'+Math.round(s.position.y/step),s])).values()];
}
export function capPair(a,b,lines){
  const r=(a.radius+b.radius)/2,L=length(a.center,b.center);if(L<r*.8||L>r*12||Math.abs(a.radius-b.radius)>r*.03)return null;
  const u={x:(b.center.x-a.center.x)/L,y:(b.center.y-a.center.y)/L},n={x:-u.y,y:u.x},at=(c,side)=>({x:c.x+side*n.x*r,y:c.y+side*n.y*r});
  const corners=[at(a.center,1),at(a.center,-1),at(b.center,1),at(b.center,-1)];
  for(const [cap,base,sign] of [[a,0,-1],[b,2,1]]){
    if(![cap.points[0],cap.points.at(-1)].every(p=>corners.slice(base,base+2).some(q=>length(p,q)<r*.6)))return null;
    const mid=cap.points[Math.floor(cap.points.length/2)];if(((mid.x-cap.center.x)*u.x+(mid.y-cap.center.y)*u.y)*sign<r*.7)return null;
  }
  const evidenceIds=[...a.evidenceIds,...b.evidenceIds];
  for(const side of [1,-1]){
    const start=at(a.center,side),intervals=[];
    for(const line of lines){const dx=line.b.x-line.a.x,dy=line.b.y-line.a.y,d=Math.hypot(dx,dy);if(d<r*.1||Math.abs((dx*u.x+dy*u.y)/d)<.98)continue;
      const cross=p=>Math.abs((p.x-start.x)*n.x+(p.y-start.y)*n.y);if(cross(line.a)>r*.2||cross(line.b)>r*.2)continue;
      const along=p=>(p.x-start.x)*u.x+(p.y-start.y)*u.y,lo=Math.max(0,Math.min(along(line.a),along(line.b))),hi=Math.min(L,Math.max(along(line.a),along(line.b)));if(hi>lo){intervals.push([lo,hi]);evidenceIds.push(...line.evidenceIds);}
    }
    intervals.sort((a,b)=>a[0]-b[0]);let covered=0,end=0;for(const [lo,hi] of intervals){covered+=Math.max(0,hi-Math.max(end,lo));end=Math.max(end,hi);}if(covered<L*.12)return null;
  }
  return {centers:[a.center,b.center],corners,u,n,r,L,evidenceIds:[...new Set(evidenceIds)]};
}
// Dimensions below are explicit drawing inputs, never measurements of the PDF.
export function holdingDrawing(holding,model,origin){
  const p=model.points.find(p=>p.id===holding.anchor),g=holding.drawing;
  if(!p?.position||!g||!['time','distance'].includes(g.mode)||!['holding','course-reversal'].includes(holding.purpose)||!['left','right'].includes(holding.turn)||!Number.isFinite(holding.inbound?.value)||holding.inbound.value<0||holding.inbound.value>360||!['true','magnetic'].includes(holding.inbound.reference))return null;
  if(holding.inbound.reference==='magnetic'&&!Number.isFinite(model.reference.variation?.value))return null;
  if(g.mode==='time'&&(!Number.isFinite(g.timeSeconds)||g.timeSeconds<=0||g.timeSeconds>3600||!Number.isFinite(g.groundSpeedKT)||g.groundSpeedKT<=0||g.groundSpeedKT>1000))return null;
  const legLengthNM=g.mode==='time'?g.timeSeconds*g.groundSpeedKT/3600:g.legLengthNM,radiusNM=g.radiusNM;
  if(!Number.isFinite(legLengthNM)||!Number.isFinite(radiusNM)||legLengthNM<.1||legLengthNM>500||radiusNM<.1||radiusNM>100)return null;
  const trueCourse=normalize(holding.inbound.value+(holding.inbound.reference==='magnetic'?model.reference.variation.value:0)),variation=origin.dir==='W'?-origin.mag:origin.mag,theta=(trueCourse-variation)*Math.PI/180,u={x:Math.sin(theta),y:Math.cos(theta)},sign=holding.turn==='right'?1:-1,n={x:u.y*sign,y:-u.x*sign},a=toNative(p.position,origin),id=holding.id;
  const b={x:a.x+2*radiusNM*n.x,y:a.y+2*radiusNM*n.y},c={x:b.x-legLengthNM*u.x,y:b.y-legLengthNM*u.y},d={x:a.x-legLengthNM*u.x,y:a.y-legLengthNM*u.y};
  const label=holding.purpose==='holding'?'ESPERA':'REVERSÃO';
  const points=[b,c,d].map((p,i)=>({id:id+'-p'+(i+1),name:label+' '+(i+1),...p,locked:false}));
  if(points.some(p=>Math.abs(p.x)>1000||Math.abs(p.y)>1000))return null;
  const ids=[holding.anchor,...points.map(p=>p.id),holding.anchor],segments=[];
  for(let i=0;i<4;i++)segments.push({id:id+'-s'+i,type:i%2===0?'curve':'line',from:ids[i],to:ids[i+1],...(i%2===0?{radius:radiusNM,side:sign}:{}),name:label+' '+(i+1),locked:false,lockBearing:false,lockLength:false,lockRadius:false});
  return {points,segments,legLengthNM,radiusNM,trueCourse,kind:'explicit-local-plane-racetrack',operationalRouteIncluded:false};
}
