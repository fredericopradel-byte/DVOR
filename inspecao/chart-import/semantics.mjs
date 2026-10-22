// Page-space semantics only: these classifications never establish geographic positions.
const normalized=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().toUpperCase();
export function roleNames(run) {
  const text=normalized(run.text);
  return /^\(?(?:IAF|IF|FAF|FAP|MAPT|MAHF|DER)(?:\/(?:IAF|IF|FAF|FAP|MAPT|MAHF|DER))*\)?$/.test(text)?text.replace(/[()]/g,'').split('/'):[];
}
export function labelType(run) {
  const text=String(run.text||'').trim(),upper=normalized(text);
  if(roleNames(run).length)return 'role';
  if(/(?:\b(?:VAR|BRG|DIST)\b\s*:?|[°º].*['′’]|\b\d{1,3}\s+[0-5]\d\s*[NSEW]\b)/.test(upper))return 'cartographic-reference';
  if(/^\d{3,5}['’]$/.test(text))return 'altitude-candidate';
  if(/^\d{3}[°º]?$/.test(text))return 'course-candidate';
  if(/^\d{1,3}\.\d{1,2}$/.test(text))return 'distance-candidate';
  // Case and isolation are evidence, not a dictionary of terrain/prose words.
  if(text===upper&&/^[A-Z][A-Z0-9]{1,7}$/.test(text))return 'identifier-candidate';
  return 'unclassified-text';
}
export function roleSupports(role,label) {
  if(!roleNames(role).length||labelType(label)!=='identifier-candidate')return false;
  const [x,y,w,h]=label.bbox,[rx,ry,rw,rh]=role.bbox,size=Math.max(label.height,role.height);
  // Function labels sit immediately above/beside their identifier, not arbitrary prose nearby.
  return Math.abs(label.angle-role.angle)<.04&&label.height>=role.height*.8&&label.height<=role.height*1.8&&
    Math.abs(x+w/2-rx-rw/2)<=Math.max(w,rw)*.55+size*.3&&y>=ry-rh*.4&&y-(ry+rh)<=size*2;
}
export function altitudeBar(line,altitude) {
  const [x,y,w,h]=altitude.bbox,left=Math.min(line.a.x,line.b.x),right=Math.max(line.a.x,line.b.x),length=right-left;
  if(Math.abs(line.a.y-line.b.y)>.2||length<w*.7||length>w*1.6||left>x+w*.2||right<x+w*.8||left<x-w*.35||right>x+w*1.35)return null;
  if(line.a.y>=y+h-1&&line.a.y<=y+h+2.5)return 'below';
  if(line.a.y>=y-2.5&&line.a.y<=y+1)return 'above';
  return null;
}
export function altitudeSupports(label,altitude,{roles=[],lines=[],aid=false}={}) {
  if(labelType(altitude)!=='altitude-candidate'||Math.abs(label.angle-altitude.angle)>.04)return false;
  const [x,y,w,h]=label.bbox,[ax,ay,aw]=altitude.bbox,size=label.height;
  if(altitude.height<size*.92||altitude.height>size*1.3||ay<y+h-1||ay>y+h+size*2.3||Math.abs(ax+aw/2-x-w/2)>Math.max(size,w*.35))return false;
  // Aid boxes also contain terrain/frequency annotations. Proximity alone is insufficient.
  return !aid||roles.some(role=>roleSupports(role,label))||lines.some(line=>altitudeBar(line,altitude));
}
