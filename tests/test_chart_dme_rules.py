"""DME arcs: generalized evidence, geography and topology without chart-name rules."""
import unittest
from test_chart_semantics import node

SETUP=r"""
const {reconstructDmeArcs,arcSubject}=await import('./inspecao/chart-import/dme-arcs.mjs');
const {curvedPaths,circularPath}=await import('./inspecao/chart-import/vector-paths.mjs');
const {destination}=await import('./inspecao/chart-import/geodesy.mjs');
const {validateModel,finishModel}=await import('./inspecao/chart-import/reconstruct.mjs');
function sample({aid='ZYX',radius=7.25,turn='right',scale=1,offset=0,split=false,loops=false}={}){
 const center={lat:45,lon:-40},sign=turn==='right'?1:-1,start=sign===1?180:300,end=start+sign*120,c={x:200,y:200},R=80;
 const at=deg=>({x:c.x+R*Math.cos((deg-90)*Math.PI/180),y:c.y+R*Math.sin((deg-90)*Math.PI/180)}),a=at(start),b=at(end);
 const run=(s,p)=>label(s,(p.x-15)*scale+offset,(p.y-3)*scale+offset,6*scale,30*scale);
 const raw=radius.toFixed(2),plan=[run('QAVEP',a),run('ZORIL',b),run('D'+raw+' '+aid,{x:a.x,y:a.y+16}),run('D'+raw+' '+aid,{x:b.x,y:b.y+16}),run('114.30 '+aid,c)];
 const m={schema:'ivplanner-chart-geometry-v1',module:'procedimentos',source:{chart:{},page:1,sha256:'test'},reference:{course:'true'},points:[{id:'c',name:aid,kind:'DME',position:center,roles:[],coordinateSource:{kind:'local-database'}},{id:'a',name:'QAVEP',roles:['IAF'],position:destination(center,start,radius),coordinateSource:{kind:'local-database'}},{id:'b',name:'ZORIL',roles:['IF'],position:destination(center,end,radius),coordinateSource:{kind:'local-database'}}],legs:[],issues:[],structures:[{type:'dme-arc'}],verticalConstraints:[],review:{validated:false},paths:[]};
 const vectors=[];let index=0;
 function curve(s,e){const ops=[13],coords=[],p=at(s);coords.push(p.x,p.y);const parts=Math.ceil(Math.abs(e-s)/90);for(let j=0;j<parts;j++){const aa=(s+(e-s)*j/parts-90)*Math.PI/180,bb=(s+(e-s)*(j+1)/parts-90)*Math.PI/180,k=4/3*Math.tan((bb-aa)/4),x=c.x+R*Math.cos(aa),y=c.y+R*Math.sin(aa),xx=c.x+R*Math.cos(bb),yy=c.y+R*Math.sin(bb);ops.push(15);coords.push(x-k*R*Math.sin(aa),y+k*R*Math.cos(aa),xx+k*R*Math.sin(bb),yy-k*R*Math.cos(bb),xx,yy);}vectors.push({operator:'constructPath',index:index++,args:[ops,coords]},{operator:'stroke',index:index++,args:[]});}
 if(loops){curve(start,start+sign*300);curve(start+sign*300,end+sign*360);}else if(split){curve(start,start+sign*58);curve(start+sign*62,end);}else curve(start,end);
 const x={width:450*scale+offset,height:450*scale+offset,pageTransform:[scale,0,0,scale,offset,offset],vectors,text:[],truncated:false},p={provider:'decea-digital-v1',plan,frame:{bbox:[offset,offset,450*scale,450*scale]},aids:[{name:aid,evidenceIds:plan.at(-1).evidenceIds}]};return {m,p,x};
}
"""


class ChartDmeRulesTests(unittest.TestCase):
    def run_case(self,body):
        return node(SETUP+body)

    def test_arbitrary_aids_radii_scales_and_both_turns_preserve_coordinates(self):
        rows=self.run_case("""const out=[];for(const aid of ['ABC','ZYX','DV01'])for(const radius of [4.75,9.25,16.75])for(const turn of ['left','right'])for(const scale of [.6,1,1.7]){const {m,p,x}=sample({aid,radius,turn,scale,offset:35}),before=JSON.stringify(m.points);reconstructDmeArcs(m,p,x);finishModel(m);out.push({radius,turn,leg:m.legs[0],unchanged:before===JSON.stringify(m.points),checks:m.checks,segments:m.native.segments});}console.log(JSON.stringify(out));""")
        self.assertEqual(len(rows),54)
        for row in rows:
            self.assertTrue(row['unchanged']);leg=row['leg'];self.assertEqual(leg['type'],'arc')
            self.assertEqual(leg['turn'],row['turn']);self.assertEqual(leg['publishedDME']['radiusNM'],row['radius'])
            self.assertEqual(leg['publishedDME']['distanceKind'],'slant-range')
            self.assertAlmostEqual(leg['radiusNM'],row['radius'],7)
            self.assertTrue(all(c['passed'] for c in row['checks']))
            self.assertTrue(row['segments']);self.assertTrue(all(s['type']=='curve' for s in row['segments']))

    def test_shared_dme_reading_alone_never_creates_a_route(self):
        rows=self.run_case("""const out=[];for(const mode of ['no-vector','no-arc','rf','no-roles','dashed','filled','truncated','wrong-aid','wrong-center-label']){const {m,p,x}=sample();if(mode==='no-vector')x.vectors=[];if(mode==='no-arc')m.structures=[];if(mode==='rf')m.structures.push({type:'rf-leg'});if(mode==='no-roles')m.points[1].roles=[];if(mode==='dashed')x.vectors.unshift({operator:'setDash',args:[[3,3],0]});if(mode==='filled')x.vectors.at(-1).operator='fillStroke';if(mode==='truncated')x.truncated=true;if(mode==='wrong-aid')p.aids=[];if(mode==='wrong-center-label')p.plan.at(-1).bbox=[400,400,30,6];reconstructDmeArcs(m,p,x);out.push({mode,legs:m.legs});}console.log(JSON.stringify(out));""")
        for row in rows:
            self.assertEqual(row['legs'],[],row['mode'])

    def test_inconsistent_or_missing_coordinates_remain_critical(self):
        rows=self.run_case("""const out=[];for(const mode of ['missing-center','missing-end','bad-radius','vor-is-not-dme']){const {m,p,x}=sample();if(mode==='missing-center')m.points[0].position=null;if(mode==='missing-end')m.points[2].position=null;if(mode==='bad-radius')m.points[2].position=destination(m.points[0].position,300,9);if(mode==='vor-is-not-dme')m.points[0].kind='VOR';reconstructDmeArcs(m,p,x);out.push({mode,legs:m.legs,issues:m.issues});}console.log(JSON.stringify(out));""")
        for row in rows:
            self.assertEqual(row['legs'],[]);self.assertTrue(row['issues']);self.assertTrue(all(i['critical'] for i in row['issues']))

    def test_short_vector_gaps_are_association_only_and_large_gaps_are_rejected(self):
        rows=self.run_case("""const {m,p,x}=sample({split:true});reconstructDmeArcs(m,p,x);const good=m.legs;const other=sample({split:true});other.x.vectors[2].args[1]=other.x.vectors[2].args[1].map(v=>v+70);reconstructDmeArcs(other.m,other.p,other.x);console.log(JSON.stringify({good,bad:other.m.legs}));""")
        self.assertEqual(len(rows['good']),1);self.assertEqual(rows['bad'],[])

    def test_reversed_or_off_radius_intermediate_fix_is_not_converted(self):
        r=self.run_case("""const out=[];for(const mode of ['ordered','off-radius','reversed','missing']){const {m}=sample();m.points.push({id:'v',name:'MID',position:destination(m.points[0].position,240,mode==='off-radius'?9:7.25)});const leg={id:'arc',type:'arc',from:'a',to:'b',center:'c',turn:'right',radiusNM:7.25,radiusResolution:.01,via:[mode==='missing'?'unknown':'v']};if(mode==='reversed')leg.via=['b','v'];m.legs=[leg];m.checks=validateModel(m).results;const {toNativeDocument}=await import('./inspecao/chart-import/native.mjs');out.push({mode,checks:m.checks,segments:toNativeDocument(m).document.segments});}console.log(JSON.stringify(out));""")
        self.assertTrue(r[0]['checks'][0]['passed']);self.assertTrue(r[0]['segments'])
        for row in r[1:]:self.assertFalse(row['checks'][0]['passed']);self.assertEqual(row['segments'],[])

    def test_duplicate_readings_merge_evidence_but_conflicting_definitions_stay_pending(self):
        r=self.run_case("""const out=[];for(const mode of ['duplicate','conflict','limit','line-conflict']){const {m,p,x}=sample(),copy=structuredClone(p.plan[2]);copy.evidenceIds=['independent-label'];if(mode==='line-conflict')m.legs.push({id:'prior-published-line',type:'line',from:'a',to:'b',published:{id:'published-definition'}});if(mode==='conflict')copy.text='D8.25 ZYX';p.plan.push(...Array.from({length:mode==='limit'?1001:1},()=>copy));reconstructDmeArcs(m,p,x);out.push({mode,m});}console.log(JSON.stringify(out));""")
        self.assertEqual(len(r[0]['m']['legs']),1)
        self.assertIn('independent-label',r[0]['m']['legs'][0]['source']['evidenceIds'])
        for row in r[1:3]:self.assertEqual(row['m']['legs'],[]);self.assertTrue(row['m']['issues'])
        self.assertEqual([l['id'] for l in r[3]['m']['legs']],['prior-published-line']);self.assertTrue(r[3]['m']['issues'])
        self.assertIn('dme-definition-a',[i['id'] for i in r[1]['m']['issues']])
        self.assertIn('dme-station-limit',[i['id'] for i in r[2]['m']['issues']])

    def test_analysis_limits_and_non_circular_beziers_never_create_arcs(self):
        r=self.run_case("""const a=sample();a.x.vectors[0].args[1][2]+=50;reconstructDmeArcs(a.m,a.p,a.x);const b=sample();b.x.vectors[0].args[1]=Array(50001).fill(1);reconstructDmeArcs(b.m,b.p,b.x);const c=sample({loops:true});reconstructDmeArcs(c.m,c.p,c.x);const d=sample();d.x.vectors=Array.from({length:50},()=>structuredClone(d.x.vectors)).flat();reconstructDmeArcs(d.m,d.p,d.x);console.log(JSON.stringify({noncircle:a.m.legs,limited:b.m,winding:c.m.legs,complex:d.m}));""")
        self.assertEqual(r['noncircle'],[]);self.assertEqual(r['limited']['legs'],[]);self.assertEqual(r['winding'],[]);self.assertEqual(r['complex']['legs'],[])
        self.assertTrue(any(i['id'].startswith('dme-topology-limit-') for i in r['complex']['issues']))
        self.assertIn('dme-vector-limit',[i['id'] for i in r['limited']['issues']])


if __name__=='__main__':unittest.main()
