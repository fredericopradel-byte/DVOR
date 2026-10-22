"""Metamorphic reference tests: no airport, waypoint, altitude or distance whitelist."""
import unittest
from test_chart_semantics import node


class ChartProfileRulesTests(unittest.TestCase):
    def test_axes_translate_scale_and_preserve_arbitrary_reference_names(self):
        r=node("""
          const {profileData}=await import('./inspecao/chart-import/profile-data.mjs');const out=[];
          for(const scale of [.6,1,1.7])for(const offset of [0,35])for(const aid of ['ABC','ZYX','DV01']){
            const run=(s,x,y)=>label(s,x*scale,(y+offset)*scale,5*scale,s.length*2.6*scale);
            const runs=[run('TO THR 04 (NM)',20,470),run('TO '+aid+' (DME)',20,478),run('9.25',120,470),run('0.0',220,470),run('11.75',120,478),run('2.5',220,478),run('(FAF)',116,360),run('QAVEP',116,368),run("2300'",116,376)];
            const p=profileData({provider:'decea-digital-v1',frame:{bbox:[0,(100+offset)*scale,400*scale,250*scale]},runs,gradients:[]},{kind:{value:'IAC'},runway:{value:'04'}});
            out.push({axes:p.axes.map(a=>[a.reference.name,a.reference.distanceKind,a.marks.map(m=>m.valueNM)]),station:p.stations.find(s=>s.name==='QAVEP'),issues:p.issues});
          }console.log(JSON.stringify(out));
        """)
        for case in r:
            self.assertEqual(case['axes'][0],['THR04','published-profile-along-track',[9.25,0]])
            self.assertEqual(case['axes'][1][1:],[ 'slant-range',[11.75,2.5]])
            self.assertEqual(case['station']['altitude']['value'],2300)
            self.assertEqual([d['valueNM'] for d in case['station']['distances']],[9.25,11.75])
            self.assertEqual(case['issues'],[])

    def test_ambiguous_numeric_string_is_not_split_without_explicit_source_items(self):
        r=node("""
          const {profileData}=await import('./inspecao/chart-import/profile-data.mjs');
          const i={provider:'decea-digital-v1',frame:{bbox:[0,100,400,250]},gradients:[],runs:[label('TO ABC (DME)',20,470),label('1.30.3',200,470),label('5.3',100,470)]};
          const a=profileData(i,{kind:{value:'IAC'}});
          console.log(JSON.stringify(a));
        """)
        self.assertEqual([m['valueNM'] for m in r['axes'][0]['marks']],[5.3])
        self.assertTrue(any(i['id'].startswith('profile-axis-numbers-') for i in r['issues']))

    def test_threshold_dme_label_and_wrong_runway_stay_explicitly_unresolved(self):
        r=node("""
          const {profileData}=await import('./inspecao/chart-import/profile-data.mjs');
          const p=profileData({provider:'decea-digital-v1',frame:{bbox:[0,100,400,250]},gradients:[],runs:[label('TO THR 22 (DME)',20,470),label('9.0',110,470),label('0.0',220,470)]},{kind:{value:'IAC'},runway:{value:'04'}});
          console.log(JSON.stringify(p));
        """)
        self.assertEqual(r['axes'][0]['reference']['distanceKind'],'threshold-reference-dme-labelled')
        self.assertTrue(any(i['id'].startswith('profile-runway-') for i in r['issues']))
        self.assertTrue(any(i['id'].startswith('profile-distance-kind-') for i in r['issues']))

    def test_minima_values_and_variants_never_become_profile_station_altitudes(self):
        r=node("""
          const {profileData}=await import('./inspecao/chart-import/profile-data.mjs');const out=[];
          for(const [da,mda] of [[216,450],[370,620],[1234,1850]]){
            const p=profileData({provider:'decea-digital-v1',frame:{bbox:[0,150,400,200]},gradients:[],runs:[label('CAT II',100,70),label('LOC',250,70),label('DA / (OCH): '+da+"' / (100')",75,78,6,80),label('MDA / (OCH): '+mda+"' / (300')",225,78,6,80)]},{kind:{value:'IAC'}});
            out.push({minima:p.minima,stations:p.stations});
          }console.log(JSON.stringify(out));
        """)
        for row,expected in zip(r,[(216,450),(370,620),(1234,1850)]):
            self.assertEqual([m['value'] for m in row['minima']],list(expected))
            self.assertEqual(row['stations'],[])

    def test_split_uses_verified_coordinates_and_skips_slant_ranges_and_arcs(self):
        r=node("""
          const {splitProfileLegs}=await import('./inspecao/chart-import/profile-association.mjs'),{destination}=await import('./inspecao/chart-import/geodesy.mjs');
          const out=[];for(const mode of ['straight','dme','arc','inconsistent']){
            const origin={lat:0,lon:-40},points=[{id:'a',name:'ALPHA',position:origin},{id:'c',name:'CHILD',position:destination(origin,90,2.5)},{id:'b',name:'BRAVO',position:destination(origin,90,5)}];if(mode==='inconsistent')points[1].position.lat+=.1;
            const m={points,legs:[{id:'ab',from:'a',to:'b',type:mode==='arc'?'arc':'line',published:{id:'definition',course:90,courseResolution:1,reference:'true',distanceNM:5,distanceResolution:.1,evidenceIds:['course']}}],issues:[],reference:{},publishedProfile:{axes:[{id:'axis',reference:{distanceKind:mode==='dme'?'slant-range':'published-profile-along-track'}}],stations:['ALPHA','CHILD','BRAVO'].map((name,j)=>({name,distances:[{axisId:'axis',valueNM:[5,2.5,0][j],raw:['5.0','2.5','0.0'][j],resolutionNM:.1,evidenceIds:[name]}]}))}};
            splitProfileLegs(m);out.push({mode,legs:m.legs.map(l=>[l.from,l.to,l.type,l.published.distanceNM]),issues:m.issues});
          }console.log(JSON.stringify(out));
        """)
        self.assertEqual(r[0]['legs'],[['a','c','line',2.5],['c','b','line',2.5]])
        for row in r[1:]:self.assertEqual(len(row['legs']),1)
        self.assertEqual(r[2]['legs'][0][2],'arc')
        self.assertTrue(r[3]['issues'])
