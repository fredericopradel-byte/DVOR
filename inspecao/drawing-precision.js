/* Precision of user-editable local geometry. Never run as a data migration. */
(()=>{'use strict';
 const DEG=Math.PI/180;
 const step=(value,increment)=>{
  if(!Number.isFinite(value))return NaN;
  // Decimal half steps round away from zero, including binary representations of 2.15.
  const magnitude=Math.abs(value)/increment;
  return Math.sign(value)*Math.round(magnitude+Number.EPSILON*Math.max(1,magnitude)*4)*increment;
 };
 const nm=value=>Number(step(value,.1).toFixed(1));
 const angle=value=>((step(value,1)%360)+360)%360;
 const distance=(a,b)=>Math.hypot(b.x-a.x,b.y-a.y);
 const bearing=(a,b)=>angle(Math.atan2(b.x-a.x,b.y-a.y)/DEG);
 const point=(anchor,heading,length)=>({x:anchor.x+Math.sin(heading*DEG)*length,y:anchor.y+Math.cos(heading*DEG)*length});
 function line(anchor,target){
  const length=nm(distance(anchor,target)),heading=bearing(anchor,target);
  if(length<.1||length>500)throw Error('Comprimento entre 0,1 e 500,0 NM.');
  return {point:point(anchor,heading,length),length,bearing:heading};
 }
 function arc(anchor,target,radius,sweep){
  radius=nm(radius);
  if(!Number.isFinite(radius)||radius<.1||radius>500)throw Error('Raio entre 0,1 e 500,0 NM.');
  const chord=distance(anchor,target);
  if(sweep===undefined)sweep=2*Math.asin(Math.min(1,chord/(2*radius)))/DEG;
  if(!Number.isFinite(sweep))throw Error('Ângulo inválido.');
  sweep=Math.max(1,Math.min(180,step(sweep,1)));
  const heading=bearing(anchor,target),length=2*radius*Math.sin(sweep*DEG/2);
  return {point:point(anchor,heading,length),radius,sweep,bearing:heading};
 }
 const formatNM=value=>nm(value).toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1});
 const formatAngle=value=>String(angle(value));
 window.IVDrawingPrecision=Object.freeze({step,nm,angle,line,arc,point,formatNM,formatAngle});
})();
