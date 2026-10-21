(()=>{'use strict';
const clone=x=>JSON.parse(JSON.stringify(x));
const geometry=d=>({origin:d.origin,points:d.points.map(p=>({id:p.id,name:p.name,x:p.x,y:p.y})),segments:d.segments.map(s=>({id:s.id,type:s.type,from:s.from,to:s.to,radius:s.type==='curve'?s.radius:null,side:s.type==='curve'?s.side:null,flightRules:s.flightRules||''})),restrictions:d.restrictions,flight:d.flight});
function reconcile(d,module){
 const m=d.chartImport;if(m===undefined)return;
 if(!m||m.version!==1||m.module!==module||typeof m.sessionId!=='string'||!/^[a-f0-9]{64}$/i.test(m.source?.sha256)||!Number.isInteger(m.source.page)||m.source.page<1||!m.baseline||!Array.isArray(m.baseline.points)||!Array.isArray(m.baseline.segments)||!Array.isArray(m.pending)||!Array.isArray(m.provenance?.points)||!Array.isArray(m.provenance?.legs)||!Array.isArray(m.provenance?.verticalConstraints)||!m.provenance.mapping?.points||!m.provenance.mapping?.legs||!Array.isArray(m.provenance.mapping?.derived)||!m.baseline.origin||!m.baseline.restrictions||!m.baseline.flight||typeof m.approval?.validated!=='boolean'||JSON.stringify(m).length>2000000)throw Error('Origem da carta incompatível. Dados preservados.');
 const current=geometry(d),base=m.baseline,changed=[];
 for(const key of ['points','segments']){const slots=new Map((base[key]||[]).map(p=>[p.id,p]));for(const item of current[key]){if(JSON.stringify(item)!==JSON.stringify(slots.get(item.id)))changed.push(item.id);slots.delete(item.id);}changed.push(...slots.keys());}
 for(const id of new Set([...Object.keys(current.restrictions||{}),...Object.keys(base.restrictions||{})]))if(JSON.stringify(current.restrictions[id])!==JSON.stringify(base.restrictions[id]))changed.push(id);
 if(JSON.stringify(current.origin)!==JSON.stringify(base.origin))changed.push('origin');if(JSON.stringify(current.flight)!==JSON.stringify(base.flight))changed.push('flight');
 for(const leg of d.segments)if(changed.includes('origin')||changed.includes(leg.from)||changed.includes(leg.to))changed.push(leg.id);
 d.chartImport=clone(m);d.chartImport.modifications=[...new Set(changed)];d.chartImport.review={validated:m.approval.validated&&!m.pending.some(i=>i.critical)&&!changed.length};
}
window.IVChartProvenance=Object.freeze({geometry,reconcile});
})();
