"""Generalized structural classification: variations are synthetic, never geographic pixels."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


def node(body):
    program = """
      import {labelType,roleNames,roleSupports,altitudeSupports,altitudeBar} from './inspecao/chart-import/semantics.mjs';
      import {graphics,supportedLayout} from './inspecao/chart-import/decea.mjs';
      import {recognize} from './inspecao/chart-import/model.mjs';
      const label=(text,x,y,h=6,w=text.length*h*.55,angle=0)=>({text,bbox:[x,y,w,h],height:h,angle,evidenceIds:[text+'-'+x+'-'+y]});
    """ + body
    result = subprocess.run(['node', '--input-type=module', '-e', program],cwd=ROOT,capture_output=True,text=True,check=True)
    return json.loads(result.stdout)


class ChartSemanticTests(unittest.TestCase):
    def test_arbitrary_labels_and_prose_are_classified_by_form_not_word_blacklists(self):
        result = node("""
          const samples=['QAVEP','ZORIL','PONTE','AFTER','RIVER','AB123'];
          console.log(JSON.stringify(samples.map(name=>({name,identifier:labelType(label(name,10,10)),prose:labelType(label('TURN DIRECT '+name,10,10)),terrain:labelType(label(name[0]+name.slice(1).toLowerCase(),10,10))}))));
        """)
        for row in result:
            self.assertEqual(row['identifier'],'identifier-candidate')
            self.assertNotEqual(row['prose'],'identifier-candidate')
            self.assertNotEqual(row['terrain'],'identifier-candidate')

    def test_roles_require_alignment_and_separation_instead_of_nearest_word(self):
        result = node("""
          const rows=[];for(const scale of [.6,1,1.7])for(const name of ['QAVEP','PONTE','ZORIL']){
            const role=label('(IF)',100*scale,100*scale,5*scale,20*scale),fix=label(name,96*scale,108*scale,6*scale,29*scale);
            rows.push({valid:roleSupports(role,fix),prose:roleSupports(role,label('DIRECT '+name,96*scale,108*scale,6*scale)),wrongSide:roleSupports(role,label(name,96*scale,50*scale,6*scale)),remote:roleSupports(role,label(name,190*scale,108*scale,6*scale))});
          }console.log(JSON.stringify(rows));
        """)
        for row in result:
            self.assertTrue(row['valid'])
            self.assertFalse(row['prose'] or row['wrongSide'] or row['remote'])

    def test_altitude_numeric_value_is_not_a_blacklist_and_map_type_size_is_evidence(self):
        result = node("""
          const rows=[];for(const value of [482,600,1700,3500,12000])for(const scale of [.6,1,1.8]){
            const fix=label('QAVEP',100*scale,100*scale,6*scale,30*scale);
            const altitude=label(value+"'",101*scale,108*scale,6*scale,28*scale);
            const contour={...altitude,height:4.25*scale};
            rows.push({valid:altitudeSupports(fix,altitude),contour:altitudeSupports(fix,contour),rotated:altitudeSupports(fix,{...altitude,angle:.4}),remote:altitudeSupports(fix,{...altitude,bbox:[101*scale,170*scale,28*scale,6*scale]})});
          }console.log(JSON.stringify(rows));
        """)
        for row in result:
            self.assertTrue(row['valid'])
            self.assertFalse(row['contour'] or row['rotated'] or row['remote'])

    def test_aid_proximity_and_long_diagram_lines_do_not_establish_restriction(self):
        result = node("""
          const aid=label('ABC',100,100,6,28),alt=label("600'",100,108,6,28);
          const long={a:{x:0,y:115},b:{x:400,y:115}},bar={a:{x:100,y:115},b:{x:128,y:115}};
          console.log(JSON.stringify({alone:altitudeSupports(aid,alt,{aid:true}),border:altitudeSupports(aid,alt,{aid:true,lines:[long]}),publishedBar:altitudeSupports(aid,alt,{aid:true,lines:[bar]}),barType:altitudeBar(bar,alt)}));
        """)
        self.assertFalse(result['alone']);self.assertFalse(result['border'])
        self.assertTrue(result['publishedBar']);self.assertEqual(result['barType'],'below')

    def test_fragmented_frames_translate_and_scale_without_using_fixed_page_bands(self):
        result = node("""
          const rows=[];for(const scale of [.7,1,1.4])for(const offset of [0,45]){
            const x=20*scale,w=360*scale,top=(180+offset)*scale,bottom=(400+offset)*scale;
            const lines=[100+offset,180+offset,400+offset,550+offset];let index=0;
            const vectors=lines.flatMap(y=>[{operator:'constructPath',index:index++,args:[[13,14],[x,y*scale,x+w,y*scale]]},{operator:'stroke',index:index++,args:[]}]);
            const runs=[label('BRG: MAG',50*scale,(200+offset)*scale,6*scale),label('DIST: NM',50*scale,(215+offset)*scale,6*scale),label('(IF)',220*scale,(300+offset)*scale,6*scale),label('UNRELATED PROSE',40*scale,(140+offset)*scale,6*scale)];
            const g=graphics({width:400*scale,height:(600+offset)*scale,pageTransform:[1,0,0,1,0,0],vectors},runs);
            rows.push({actual:g.frame.bbox,expected:[x,top,w,bottom-top],rule:g.frame.rule});
          }console.log(JSON.stringify(rows));
        """)
        for row in result:
            self.assertEqual(row['rule'],'map-references-and-function-labels')
            for actual,expected in zip(row['actual'],row['expected']):self.assertAlmostEqual(actual,expected)

    def test_filled_altitude_bars_are_preserved_without_interpreting_filled_map_areas(self):
        result = node("""
          const vectors=[{operator:'constructPath',index:1,args:[[19],[100,115,28,.5]]},{operator:'fill',index:2,args:[]},{operator:'constructPath',index:3,args:[[19],[100,150,28,30]]},{operator:'fill',index:4,args:[]}];
          const g=graphics({width:400,height:600,pageTransform:[1,0,0,1,0,0],vectors},[]);
          console.log(JSON.stringify(g.lines));
        """)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['a'],{'x':100,'y':115.25})

    def test_rf_and_dme_arc_are_distinct_and_ar_qualifier_keeps_its_evidence(self):
        result=node("""
          const extraction={text:[{text:'digital'}],lines:[{text:'SBXX_IAC_001',evidenceIds:['id']},{text:'IAC RNP Z RWY 12 (AR)',evidenceIds:['title']},{text:'RNP AR APCH. RF REQ.',evidenceIds:['req']},{text:'SPECIAL AUTHORIZATION FOR AIRCRAFT AND CREW REQUIRED',evidenceIds:['authorization']},{text:'DME ARC',evidenceIds:['arc']}]};
          const a=recognize(extraction);extraction.lines=extraction.lines.filter(l=>l.evidenceIds[0]!=='req');const b=recognize(extraction);
          console.log(JSON.stringify({a,b}));
        """)
        a=result['a'];self.assertEqual(a['metadata']['procedure']['value'],'RNP Z RWY 12 (AR)')
        self.assertEqual(a['metadata']['procedure']['evidenceIds'],['title'])
        self.assertTrue({'RF','RNP AR APCH','AUTORIZAÇÃO ESPECIAL'}.issubset({r['value'] for r in a['requirements']}))
        self.assertTrue({'rf-leg','dme-arc'}.issubset({r['type'] for r in a['structures']}))
        self.assertNotIn('rf-leg',{r['type'] for r in result['b']['structures']})

    def test_rotated_identifier_extents_do_not_need_prose_to_associate_a_leg(self):
        result=node("""
          const a=label('ABCDE',190,440,6,6,Math.PI/2),b=label('FGHIJ',154,469,6,6,Math.PI/2);a.bbox[3]=28;b.bbox[3]=28;
          console.log(JSON.stringify({near:supportedLayout({bbox:[162,429,4,5]},[a],[b]),far:supportedLayout({bbox:[350,100,4,5]},[a],[b])}));
        """)
        self.assertTrue(result['near']);self.assertFalse(result['far'])
