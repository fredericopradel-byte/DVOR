// WGS-84 geodesics. NM and degrees are retained at full floating-point precision.
const A = 6378137, F = 1 / 298.257223563, B = A * (1-F), D = Math.PI / 180;
export const normalize = value => (value % 360 + 360) % 360;
export const angleDifference = (a,b) => Math.abs(((a-b+540)%360)-180);
export function position(value) {
  return !!value && Number.isFinite(value.lat) && Number.isFinite(value.lon) && Math.abs(value.lat) < 89 && Math.abs(value.lon) <= 180;
}
export function inverse(from, to) {
  if (!position(from) || !position(to)) throw Error('Coordenadas geográficas inválidas.');
  if (from.lat === to.lat && from.lon === to.lon) return {distanceNM: 0, trueCourse: 0};
  const u1 = Math.atan((1-F)*Math.tan(from.lat*D)), u2 = Math.atan((1-F)*Math.tan(to.lat*D));
  const s1 = Math.sin(u1), c1 = Math.cos(u1), s2 = Math.sin(u2), c2 = Math.cos(u2), L = (((to.lon-from.lon+540)%360)-180)*D;
  let lambda=L, sigma, sinSigma, cosSigma, sinAlpha, cosSqAlpha, cos2SigmaM, converged=false;
  for (let i=0;i<200;i++) {
    const sl=Math.sin(lambda), cl=Math.cos(lambda);
    sinSigma=Math.hypot(c2*sl,c1*s2-s1*c2*cl);
    if (sinSigma===0) throw Error('Geodésia singular.');
    cosSigma=s1*s2+c1*c2*cl;sigma=Math.atan2(sinSigma,cosSigma);
    sinAlpha=c1*c2*sl/sinSigma;cosSqAlpha=1-sinAlpha*sinAlpha;
    cos2SigmaM=cosSqAlpha>1e-15?cosSigma-2*s1*s2/cosSqAlpha:0;
    const C=F/16*cosSqAlpha*(4+F*(4-3*cosSqAlpha)), previous=lambda;
    lambda=L+(1-C)*F*sinAlpha*(sigma+C*sinSigma*(cos2SigmaM+C*cosSigma*(-1+2*cos2SigmaM*cos2SigmaM)));
    if (Math.abs(lambda-previous)<1e-12) {converged=true;break;}
  }
  if (!converged) throw Error('Geodésia não convergiu; não foi utilizada aproximação silenciosa.');
  const uSq=cosSqAlpha*(A*A-B*B)/(B*B), k1=1+uSq/16384*(4096+uSq*(-768+uSq*(320-175*uSq))), k2=uSq/1024*(256+uSq*(-128+uSq*(74-47*uSq)));
  const delta=k2*sinSigma*(cos2SigmaM+k2/4*(cosSigma*(-1+2*cos2SigmaM**2)-k2/6*cos2SigmaM*(-3+4*sinSigma**2)*(-3+4*cos2SigmaM**2)));
  return {distanceNM:B*k1*(sigma-delta)/1852,trueCourse:normalize(Math.atan2(c2*Math.sin(lambda),c1*s2-s1*c2*Math.cos(lambda))/D)};
}
export function destination(from, trueCourse, distanceNM) {
  if (!position(from) || !Number.isFinite(trueCourse) || !Number.isFinite(distanceNM) || distanceNM<0 || distanceNM>1000) throw Error('Definição geodésica inválida.');
  const alpha=trueCourse*D, sa=Math.sin(alpha), ca=Math.cos(alpha), tu=(1-F)*Math.tan(from.lat*D), cu=1/Math.sqrt(1+tu*tu), su=tu*cu;
  const sigma1=Math.atan2(tu,ca), sinAlpha=cu*sa, cosSq=1-sinAlpha*sinAlpha, uSq=cosSq*(A*A-B*B)/(B*B);
  const k1=1+uSq/16384*(4096+uSq*(-768+uSq*(320-175*uSq))), k2=uSq/1024*(256+uSq*(-128+uSq*(74-47*uSq)));
  const base=distanceNM*1852/(B*k1);let sigma=base;
  for(let i=0;i<100;i++) {
    const c2=Math.cos(2*sigma1+sigma), ss=Math.sin(sigma), cs=Math.cos(sigma), previous=sigma;
    sigma=base+k2*ss*(c2+k2/4*(cs*(-1+2*c2*c2)-k2/6*c2*(-3+4*ss*ss)*(-3+4*c2*c2)));
    if(Math.abs(sigma-previous)<1e-12) break;
    if(i===99) throw Error('Destino geodésico não convergiu.');
  }
  const ss=Math.sin(sigma),cs=Math.cos(sigma),tmp=su*ss-cu*cs*ca, lat=Math.atan2(su*cs+cu*ss*ca,(1-F)*Math.hypot(sinAlpha,tmp));
  const lambda=Math.atan2(ss*sa,cu*cs-su*ss*ca), C=F/16*cosSq*(4+F*(4-3*cosSq));
  const L=lambda-(1-C)*F*sinAlpha*(sigma+C*ss*(Math.cos(2*sigma1+sigma)+C*cs*(-1+2*Math.cos(2*sigma1+sigma)**2)));
  return {lat:lat/D,lon:((from.lon+L/D+540)%360)-180};
}
// Exactly the existing editor's spherical local projection; not used as a geodesic oracle.
export function toNative(point, origin) {
  if(!position(point)||!position(origin)) throw Error('Referência nativa inválida.');
  const p1=origin.lat*D,p2=point.lat*D,dp=p2-p1,dl=(point.lon-origin.lon)*D;
  const a=Math.sin(dp/2)**2+Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)**2;
  const distance=2*Math.atan2(Math.sqrt(a),Math.sqrt(1-a))*3440.065;
  const bearing=Math.atan2(Math.sin(dl)*Math.cos(p2),Math.cos(p1)*Math.sin(p2)-Math.sin(p1)*Math.cos(p2)*Math.cos(dl))-(origin.dir==='W'?-origin.mag:origin.mag)*D;
  return {x:Math.sin(bearing)*distance,y:Math.cos(bearing)*distance};
}
