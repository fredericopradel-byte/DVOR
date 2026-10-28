"""General holding topology and explicit drawing dimensions: no geographic pixels/defaults."""
import unittest
import math
from test_chart_semantics import node

SETUP=r"""
const {reconstructHoldings,holdingAnswer,applyHoldingAnswer}=await import('./inspecao/chart-import/holdings.mjs');
const {holdingDrawing}=await import('./inspecao/chart-import/holding-geometry.mjs');
const {toNativeDocument}=await import('./inspecao/chart-import/native.mjs');
function sample({name='QAVEP',course=59,scale=1,offset=0,left=false,definition='',roles=['IAF','MAHF']}={}){
 const tx=(x,y)=>({x:(left?400-x:x)*scale+offset,y:y*scale+offset}),run=(s,x,y)=>{const p=tx(x,y);return label(s,p.x-15*scale,p.y-3*scale,6*scale,30*scale);};
 let index=0;const vectors=[],path=(ops,coords,paint='stroke')=>{vectors.push({operator:'constructPath',index:index++,args:[ops,coords]},{operator:paint,index:index++,args:[]});};
 const r=12,k=4/3*Math.tan(Math.PI/8)*r;
 // Two exact circular semicircles plus parallel straight strokes.
 path([13,15,15],[150,150,150,150-k,162-k,138,162,138,162+k,138,174,150-k,174,150]);
 path([13,15,15],[174,200,174,200+k,162+k,212,162,212,162-k,212,150,200+k,150,200]);
 path([13,14],[150,150,150,200]);path([13,14],[174,150,174,200]);
 path([13,14,14,18],[147.5,151.443,152.5,151.443,150,147.113]);
 const source={width:400*scale+offset,height:400*scale+offset,pageTransform:[left?-scale:scale,0,0,scale,(left?400*scale:0)+offset,offset],vectors,truncated:false};
 const plan=[run(name,132,145),run(String(course).padStart(3,'0'),144,177),run(String((course+180)%360).padStart(3,'0'),180,177)];if(definition)plan.push(run(definition,180,190));
 const p={provider:'decea-digital-v1',plan,runs:plan,frame:{bbox:[offset,offset,400*scale,400*scale]},reference:'true'},m={schema:'ivplanner-chart-geometry-v1',module:'procedimentos',reference:{course:'true'},source:{sha256:'test',page:1,chart:{kind:{value:'IAC'}}},points:[{id:'a',name,roles,position:{lat:-12.123456789,lon:-40.987654321},coordinateSource:{kind:'local-database'}}],legs:[],issues:[],verticalConstraints:[],checks:[],paths:[],review:{validated:false}};return {m,p,source};
}
"""

class ChartHoldingRulesTests(unittest.TestCase):
    def run_case(self,body):return node(SETUP+body)

    def test_topology_arbitrary_fix_names_courses_scales_offsets_and_both_turns(self):
        r=self.run_case("""const out=[];for(const name of ['QAVEP','PONTE','ZX123'])for(const course of [0,137,271])for(const scale of [.6,1,1.8])for(const left of [false,true]){const {m,p,source}=sample({name,course,scale,left,offset:23}),before=JSON.stringify(m.points);reconstructHoldings(m,p,source);out.push({name,course,left,unchanged:JSON.stringify(m.points)===before,holdings:m.holdings});}console.log(JSON.stringify(out));""")
        self.assertEqual(len(r),54)
        for c in r:
            self.assertTrue(c['unchanged']);self.assertEqual(len(c['holdings']),1,c)
            h=c['holdings'][0];self.assertEqual(h['inbound']['value'],c['course']);self.assertEqual(h['turn'],'left' if c['left'] else 'right')
            self.assertIsNone(h['published']['legDefinition']);self.assertNotIn('drawing',h)

    def test_published_360_is_preserved_while_drawing_uses_zero_direction(self):
        r=self.run_case("""const {m,p,source}=sample({course:360});reconstructHoldings(m,p,source);const h=m.holdings[0],a=holdingAnswer(h,{mode:'distance',legLengthNM:2,radiusNM:1});applyHoldingAnswer(m,h,a,'north');const result=holdingDrawing(h,m,{...m.points[0].position,mag:0,dir:'E'});console.log(JSON.stringify({h,result}));""")
        self.assertEqual(r['h']['published']['inboundCourse']['value'],360)
        self.assertEqual(r['h']['published']['inboundCourse']['raw'],'360')
        self.assertEqual(r['result']['trueCourse'],0)
        self.assertAlmostEqual(r['result']['points'][-1]['x'],0,10);self.assertAlmostEqual(r['result']['points'][-1]['y'],-2,10)

    def test_no_default_time_distance_speed_radius_or_magnetic_variation(self):
        r=self.run_case("""const {m,p,source}=sample();reconstructHoldings(m,p,source);const h=m.holdings[0],rejected=[];for(const a of [{},{mode:'time',timeSeconds:60,radiusNM:1},{mode:'distance',legLengthNM:2},{mode:'distance',legLengthNM:0,radiusNM:1},{mode:'time',timeSeconds:-60,groundSpeedKT:-120,radiusNM:1}]){try{holdingAnswer(h,a);rejected.push(false);}catch{rejected.push(true);}}h.inbound.reference='magnetic';h.drawing={mode:'distance',legLengthNM:2,radiusNM:1};console.log(JSON.stringify({rejected,drawing:holdingDrawing(h,m,{lat:m.points[0].position.lat,lon:m.points[0].position.lon,mag:0,dir:'E'})}));""")
        self.assertTrue(all(r['rejected']));self.assertIsNone(r['drawing'])

    def test_time_is_preserved_and_explicit_gs_only_dimensions_straight_leg(self):
        r=self.run_case("""const {m,p,source}=sample({definition:'1.5 MIN'});reconstructHoldings(m,p,source);const h=m.holdings[0],a=holdingAnswer(h,{groundSpeedKT:120,radiusNM:.750123456});applyHoldingAnswer(m,h,a,'decision');const d=toNativeDocument(m);console.log(JSON.stringify({h,d,source:m.points[0]}));""")
        self.assertEqual(r['h']['published']['legDefinition']['raw'],'1.5 MIN');self.assertEqual(r['h']['published']['legDefinition']['value'],90)
        self.assertEqual(r['d']['mapping']['holdings']['holding-a']['legLengthNM'],3)
        self.assertEqual(r['d']['mapping']['holdings']['holding-a']['radiusNM'],.750123456)
        self.assertEqual([s['type'] for s in r['d']['document']['segments']],['curve','line','curve','line'])
        self.assertEqual(r['d']['document']['flight']['segments'],[])
        self.assertEqual(r['source']['position']['lat'],-12.123456789)
        points={p['id']:p for p in r['d']['document']['points']}
        for segment in r['d']['document']['segments']:
            a,b=points[segment['from']],points[segment['to']]
            chord=math.hypot(b['x']-a['x'],b['y']-a['y'])
            self.assertAlmostEqual(chord,2*.750123456 if segment['type']=='curve' else 3,places=10)
        inbound=r['d']['document']['segments'][-1];a,b=points[inbound['from']],points[inbound['to']]
        self.assertAlmostEqual(math.degrees(math.atan2(b['x']-a['x'],b['y']-a['y']))%360,59,places=10)

        self.assertFalse(any('timeSeconds' in v for v in r['d']['document']['restrictions'].values()))

    def test_missing_nonreciprocal_courses_unknown_purpose_and_conflicting_definitions_stay_explicit(self):
        r=self.run_case("""const out=[];for(const mode of ['course','purpose','conflict']){const {m,p,source}=sample({roles:mode==='purpose'?['IAF']:['MAHF'],definition:mode==='conflict'?'1 MIN':''});if(mode==='course')p.plan[2].text='201';if(mode==='conflict')p.plan.push(label('2 MIN',165,192,6,30));reconstructHoldings(m,p,source);const h=m.holdings[0];let rejected=false;try{holdingAnswer(h,{mode:'distance',legLengthNM:2,radiusNM:1});}catch{rejected=true;}out.push({mode,h,issues:m.issues,rejected});}console.log(JSON.stringify(out));""")
        self.assertIsNone(r[0]['h']['inbound']);self.assertTrue(r[0]['rejected'])
        self.assertEqual(r[1]['h']['purpose'],'unresolved-racetrack');self.assertTrue(r[1]['rejected'])
        self.assertEqual(len(r[2]['h']['published']['definitionCandidates']),2)
        self.assertTrue(any(i['id'].startswith('holding-definition-') for i in r[2]['issues']))

    def test_without_fix_symbol_parallel_strokes_or_compatible_provider_no_racetrack_is_invented(self):
        r=self.run_case("""const out=[];for(const mode of ['symbol','parallel','provider','truncated','distorted']){const {m,p,source}=sample();if(mode==='symbol')source.vectors=source.vectors.slice(0,-2);if(mode==='parallel')source.vectors=source.vectors.filter((v,i)=>![4,5,6,7].includes(i));if(mode==='provider')p.provider='unsupported-local';if(mode==='truncated')source.truncated=true;if(mode==='distorted')source.vectors[0].args[1][3]+=30;reconstructHoldings(m,p,source);out.push({mode,holdings:m.holdings});}console.log(JSON.stringify(out));""")
        for c in r:self.assertEqual(c['holdings'],[],c['mode'])

    def test_invalid_drawing_data_cannot_mutate_candidate_or_override_published_distance(self):
        r=self.run_case("""const {m,p,source}=sample({definition:'4.25 NM'});reconstructHoldings(m,p,source);const h=m.holdings[0],a=holdingAnswer(h,{legLengthNM:99,radiusNM:1});m.points[0].position=null;const before=JSON.stringify(h);let rejected=false;try{applyHoldingAnswer(m,h,a,'bad');}catch{rejected=true;}console.log(JSON.stringify({a,rejected,unchanged:before===JSON.stringify(h)}));""")
        self.assertEqual(r['a']['legLengthNM'],4.25);self.assertTrue(r['rejected']);self.assertTrue(r['unchanged'])

if __name__=='__main__':unittest.main()
