"""Convert the pinned world-atlas 2.0.2 countries topology without network access."""
import json, hashlib, gzip, sys
from pathlib import Path
source=Path(sys.argv[1])
if hashlib.sha256(source.read_bytes()).hexdigest()!='04342cdc1e3016bcd7db1630de95684d67b79fe3c8c460321e87aef469502394':raise ValueError('Unexpected source: use world-atlas 2.0.2 countries-50m.json')
top=json.loads(source.read_text()); scale=top['transform']['scale'];translate=top['transform']['translate'];arcs=[]
for arc in top['arcs']:
 x=y=0;points=[]
 for dx,dy in arc:
  x+=dx;y+=dy;points.append([round(x*scale[0]+translate[0],5),round(y*scale[1]+translate[1],5)])
 arcs.append(points)
def ring(indices):
 points=[]
 for index in indices:
  part=arcs[index if index>=0 else ~index]
  if index<0:part=list(reversed(part))
  points.extend(part if not points else part[1:])
 if len(points)<4:raise ValueError('Short polygon ring')
 if points[0]!=points[-1]:points.append(points[0])
 return points
def unwrap(points):
 result=[points[0][:]]
 for lon,lat in points[1:]:
  lon+=360*round((result[-1][0]-lon)/360)
  result.append([lon,lat])
 return result

def planar_ring(points):
 result=unwrap(points)
 if result[-1]!=result[0] and abs(result[-1][0]-result[0][0])>=359.99:
  # A spherical ring encircling a pole must close there, not across the world
  # at the latitude of its first coastal point in the planar renderer.
  pole=-90 if result[0][1]<0 else 90
  result.extend([[result[-1][0],pole],[result[0][0],pole]])
 if result[0]==result[-1]:result.pop()
 return result

def clip(points,bound,keep_greater):
 # Clip at the meridian in geographic coordinates; no estimated coast geometry.
 result=[]
 for previous,current in zip(points[-1:]+points[:-1],points):
  pin=previous[0]>=bound if keep_greater else previous[0]<=bound
  cin=current[0]>=bound if keep_greater else current[0]<=bound
  if pin!=cin:
   ratio=(bound-previous[0])/(current[0]-previous[0])
   result.append([bound,round(previous[1]+ratio*(current[1]-previous[1]),5)])
  if cin:result.append(current)
 return result

def split_antimeridian(coords):
 polygons=[]
 for polygon in coords:
  outer=planar_ring(polygon[0])
  center=sum(p[0] for p in outer)/len(outer)
  unwrapped=[outer]
  for hole in polygon[1:]:
   h=planar_ring(hole)
   shift=360*round((center-sum(p[0] for p in h)/len(h))/360)
   unwrapped.append([[x+shift,y] for x,y in h])
  for shift in (-360,0,360):
   rings=[]
   for index,ring_points in enumerate(unwrapped):
    part=clip([[x+shift,y] for x,y in ring_points],-180,True)
    if part:part=clip(part,180,False)
    if len(part)>=3:
     if part[0]!=part[-1]:part.append(part[0][:])
     area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(part,part[1:]))
     if len(part)>=4 and abs(area)>1e-12:rings.append(part)
     elif index==0:break
    elif index==0:break
   if rings:polygons.append(rings)
 return polygons

features=[]
for g in top['objects']['countries']['geometries']:
 if g['type']=='Polygon':coords=[ring(r) for r in g['arcs']]
 elif g['type']=='MultiPolygon':coords=[[ring(r) for r in p] for p in g['arcs']]
 else:raise ValueError(g['type'])
 polygons=split_antimeridian([coords] if g['type']=='Polygon' else coords)
 if not polygons:raise ValueError('Empty country after clipping')
 kind='Polygon' if len(polygons)==1 else 'MultiPolygon'
 coords=polygons[0] if len(polygons)==1 else polygons
 features.append({'type':'Feature','id':g.get('id'),'properties':g.get('properties',{}),'geometry':{'type':kind,'coordinates':coords}})
result={'type':'FeatureCollection','features':features}
out=Path(__file__).resolve().parents[1]/'meteorologia/basemap';out.mkdir(exist_ok=True)
data=json.dumps(result,separators=(',',':'),ensure_ascii=False).encode()
(out/'countries-50m.geojson').write_bytes(data)
manifest={'source':'Natural Earth 4.1.0, admin-0 countries 1:50m','distribution':'world-atlas 2.0.2','url':'https://unpkg.com/world-atlas@2.0.2/countries-50m.json','inputSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'outputSha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'gzipBytes':len(gzip.compress(data)),'features':len(features),'coordinates':'WGS84 longitude, latitude (RFC 7946)','conversion':'Delta decode TopoJSON arcs, apply quantization transform, reverse negative arcs, stitch rings; coordinates rounded to 5 decimals; split rings at the antimeridian and close pole-encircling spherical rings at the geographic poles for planar Leaflet rendering. No guessed geometry.'}
(out/'source.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')

print(json.dumps(manifest,ensure_ascii=False))
