"""Stage 3: georeferenced partial reconstruction, actual chart evidence, native preview isolation."""
import json
import math
from pathlib import Path
import unittest
from playwright.sync_api import expect
import test_e2e
import test_chart_import as previous

ROOT=Path(__file__).resolve().parents[1]
GOLDENS=json.loads((ROOT/'tests/fixtures/charts/geometry-goldens.json').read_text())['cases']


class ChartGeometryTests(unittest.TestCase):
    setUpClass=classmethod(test_e2e.PlannerTests.setUpClass.__func__)
    setUp=test_e2e.PlannerTests.setUp
    assert_loaded=test_e2e.PlannerTests.assert_loaded
    dismiss_database_prompt=test_e2e.PlannerTests.dismiss_database_prompt
    open=previous.ChartImportTests.open
    choose=previous.ChartImportTests.choose
    records=previous.ChartImportTests.records
    mission_snapshot=previous.ChartImportTests.mission_snapshot

    def build(self,name,module='procedimentos'):
        return self.page.evaluate("""async ({name,module})=>{
          const {identify,openDocument}=await import('./chart-import/extract.mjs');const {recognize}=await import('./chart-import/model.mjs');
          const {indexDatabase}=await import('./chart-import/aeronautical.mjs');const {reconstruct}=await import('./chart-import/reconstruct.mjs');
          const raw=window.chartRaw??=await(await fetch('../packages/aixm/AIXM-BR-2026-09-03/aixm-core.json')).json();
          const file=new File([await(await fetch('../tests/fixtures/charts/'+name)).blob()],'renamed.pdf');const source=await identify(file),doc=await openDocument(file,source);
          try{const extraction=await doc.extract(1,document.createElement('canvas'));return reconstruct({source,page:1,module,extraction,recognition:recognize(extraction)},indexDatabase(raw));}finally{await doc.destroy();}
        }""",dict(name=name,module=module))

    def install_local_fixture(self):
        self.page.evaluate("async()=>{await navigator.serviceWorker.ready;}")
        self.page.wait_for_function('navigator.serviceWorker.controller!==null')
        self.page.evaluate("""async()=>{
          const target='publicacoes-offline/aixm/AIXM-BR-2026-09-03/aixm-core.json',cache=await caches.open('ivdata-package-chart-geometry-fixture');
          await cache.put(new URL('../'+target,location.href),await fetch('../packages/aixm/AIXM-BR-2026-09-03/aixm-core.json'));
          await new Promise((resolve,reject)=>{const r=indexedDB.open('ivplanner-package-manager-v1',1);r.onupgradeneeded=()=>{if(!r.result.objectStoreNames.contains('packages'))r.result.createObjectStore('packages',{keyPath:'id'});};r.onsuccess=()=>{const db=r.result,tx=db.transaction('packages','readwrite');tx.objectStore('packages').put({id:'chart-test-aixm',status:'installed',activeCache:'ivdata-package-chart-geometry-fixture',targets:[target],installedVersion:'AIXM-BR-2026-09-03-r2'});tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>reject(tx.error);};});
        }""")

    def test_real_chart_partial_goldens_and_coordinate_precision(self):
        self.open()
        for case in GOLDENS:
            with self.subTest(chart=case['file']):
                m=self.build(case['file']);byid={p['id']:p for p in m['points']}
                actual={(byid[l['from']]['name'],byid[l['to']]['name']):(l['published']['course'],l['published']['distanceNM']) for l in m['legs']}
                for start,end,course,distance in case['legs']:
                    self.assertIn((start,end),actual);self.assertEqual(actual[start,end],(course,distance))
                for name,position in case.get('coordinateSnapshots',{}).items():
                    p=next(p for p in m['points'] if p['name']==name)
                    self.assertEqual(p['position'],position);self.assertEqual(p['coordinateSource']['originalPosition'],position)
                for name,altitude in case.get('altitudes',{}).items():
                    self.assertIn(altitude,[r.get('value') for r in m['verticalConstraints'] if r.get('entity')=='p-'+name])
                self.assertFalse(m['review']['validated']);self.assertEqual(m['status'],'partial')
                self.assertTrue(all(c['passed'] for c in m['checks']))
                self.assertEqual(m['source']['extractionMethod'],'pdfjs-4.10.38')
                self.assertEqual(len(m['native']['segments']),len(m['legs']))
                if case.get('blockedLeg'):
                    a,b,_,distance=case['blockedLeg'];self.assertNotIn((a,b),actual)
                    conflicts=[i for i in m['issues'] if i['id'].startswith('conflict-')]
                    self.assertTrue(any(i['annotation']['distanceNM']==distance for i in conflicts))
                if case.get('convergence'):
                    self.assertEqual(len(m['topology']['convergences'][0]['incoming']),3)
                    self.assertEqual(m['topology']['convergences'][0]['point'],'p-'+case['convergence'])
                    self.assertEqual(len(m['paths']),3);self.assertEqual(m['native']['flight']['segments'],[])

    def test_sid_uses_actual_definitions_without_filling_missing_branches(self):
        self.open();m=self.build('sbrj_evsob-1d-rwy-20l_sid_20210520.pdf')
        pairs={(l['from'],l['to']) for l in m['legs']}
        for pair in [('LOKOD','EVSOB'),('EVSOB','VAMIX'),('VAMIX','TIVRO'),('TIVRO','BITAK')]:self.assertIn(('p-'+pair[0],'p-'+pair[1]),pairs)
        self.assertTrue(any(i['id'].startswith('unassociated-') for i in m['issues']))
        self.assertEqual(m['reference']['variation']['value'],-23)
        self.assertFalse(m['review']['validated'])

    def test_raster_ndb_charts_have_no_fabricated_points(self):
        self.open('ndb')
        for name in ['sbbq_ndb-rwy-18_iac_20230518.pdf','sbjp_ndb-y-rwy-16_iac_20221201.pdf']:
            m=self.build(name,'ndb');self.assertEqual(m['points'],[]);self.assertEqual(m['legs'],[])
            self.assertIn('visual-required',[i['id'] for i in m['issues']])
            self.assertEqual(m['native']['module'],'ndb')

    def test_date_mismatch_and_unresolved_runway_waypoint_remain_critical(self):
        self.open();m=self.build('sbnt_rnp-rwy-16l_iac_20231005-1.pdf')
        self.assertIn('date-p-NT364',[i['id'] for i in m['issues']])
        self.assertTrue(any(i['id'] in ['runway-waypoint','coordinate-p-RW16L'] for i in m['issues']))
        self.assertFalse(any(l['to']=='p-RW16L' for l in m['legs']))
        self.assertEqual(next(p for p in m['points'] if p['name']=='NT364')['coordinateState'],'temporal-review')

    def test_arc_and_holding_limitations_are_not_replaced_by_straight_lines(self):
        self.open();m=self.build('sbnt_vor-w-rwy-16l_iac_20250515.pdf')
        self.assertIn('structure-dme-arc',[i['id'] for i in m['issues']])
        self.assertIn('structure-holding',[i['id'] for i in m['issues']])
        self.assertEqual(m['structures'][0]['status'],'unresolved')
        self.assertFalse(any(l['from']=='p-EGEGI' and l['to']=='p-SALBA' for l in m['legs']))

    def test_wgs84_reference_values_and_no_silent_antipodal_fallback(self):
        self.open()
        r=self.page.evaluate("""async()=>{const g=await import('./chart-import/geodesy.mjs');let rejected=false;try{g.inverse({lat:0,lon:0},{lat:0,lon:180});}catch{rejected=true;}return {equator:g.inverse({lat:0,lon:0},{lat:0,lon:1}),meridian:g.inverse({lat:0,lon:0},{lat:1,lon:0}),east:g.destination({lat:0,lon:0},90,100),rejected};}""")
        self.assertAlmostEqual(r['equator']['distanceNM']*1852,111319.49079327357,places=5)
        self.assertAlmostEqual(r['meridian']['distanceNM']*1852,110574.38855779878,places=5)
        self.assertAlmostEqual(r['east']['lon'],185200*180/(math.pi*6378137),places=10)
        self.assertAlmostEqual(r['east']['lat'],0,places=10);self.assertTrue(r['rejected'])

    def test_magnetic_true_distinction_and_required_variation(self):
        self.open()
        r=self.page.evaluate("""async()=>{const {derivePoint}=await import('./chart-import/reconstruct.mjs');const anchor={lat:-20,lon:-44};let rejected=false;try{derivePoint({anchor,course:120,distanceNM:5,reference:'magnetic'});}catch{rejected=true;}return {a:derivePoint({anchor,course:120,distanceNM:5,reference:'magnetic',variation:-23}),b:derivePoint({anchor,course:97,distanceNM:5,reference:'true'}),rejected};}""")
        self.assertEqual(r['a'],r['b']);self.assertTrue(r['rejected'])

    def test_fix_ambiguity_and_missing_database_are_not_resolved_by_guessing(self):
        self.open()
        r=self.page.evaluate("""async()=>{const {indexDatabase,resolveEntity}=await import('./chart-import/aeronautical.mjs');const db=indexDatabase({schema:'ivplanner-aixm-core-v1',designatedPoints:[{id:'a',designator:'ABCDE',position:{lat:-20,lon:-44}},{id:'b',designator:'ABCDE',position:{lat:-20.2,lon:-44}}]});return {ambiguous:resolveEntity('ABCDE',db),missing:resolveEntity('XXXXX',db)};}""")
        self.assertEqual(r['ambiguous']['status'],'ambiguous');self.assertEqual(len(r['ambiguous']['candidates']),2)
        self.assertEqual(r['missing']['status'],'missing')
        self.choose('sbls_ndb-rwy-13_iac_20250220.pdf');m=self.records()[0]['reconstruction']
        self.assertIn('database-unavailable',[i['id'] for i in m['issues']]);self.assertEqual(m['native']['segments'],[])

    def test_native_preview_and_modal_keyboard_preserve_editor_state(self):
        self.open();m=self.build('sbls_ndb-rwy-13_iac_20250220.pdf')
        before=self.mission_snapshot()
        r=self.page.evaluate("""model=>{const svg=document.querySelector('#drawing'),before=svg.outerHTML,options=document.querySelector('#rotation-center').outerHTML,view=window.IVProcedurePreview.render(model.native);return {restored:before===svg.outerHTML,optionsPreserved:options===document.querySelector('#rotation-center').outerHTML,segments:view.querySelectorAll('g[data-segment]').length,readOnly:view.getAttribute('data-readonly'),nativePoint:model.native.points.find(p=>p.id==='p-KUDGU')};}""",m)
        self.assertTrue(r['restored']);self.assertTrue(r['optionsPreserved']);self.assertEqual(r['segments'],3);self.assertEqual(r['readOnly'],'true')
        self.page.keyboard.press('Control+z');self.assertEqual(self.mission_snapshot(),before)
        self.page.keyboard.press('Escape');self.assertEqual(self.mission_snapshot(),before)

    def test_ui_reconstruction_persists_and_reopens_offline_without_installed_base(self):
        self.open('ndb');self.install_local_fixture();before=self.mission_snapshot();self.choose('sbls_ndb-rwy-13_iac_20250220.pdf')
        expect(self.page.locator('#chart-geometry-summary')).to_contain_text('3 pernas nativas')
        self.page.get_by_role('button',name='Prévia do desenho',exact=True).click();expect(self.page.locator('#chart-native')).to_be_visible()
        prior=self.records('ndb')[0];self.assertEqual(len(prior['reconstruction']['native']['segments']),3)
        self.page.evaluate("""async()=>{await caches.delete('ivdata-package-chart-geometry-fixture');await new Promise(resolve=>{const r=indexedDB.open('ivplanner-package-manager-v1',1);r.onsuccess=()=>{const db=r.result,tx=db.transaction('packages','readwrite');tx.objectStore('packages').delete('chart-test-aixm');tx.oncomplete=()=>{db.close();resolve();};};});}""")
        self.context.set_offline(True);self.page.reload();self.dismiss_database_prompt();self.page.locator('[data-page=drawing]').click();self.page.locator('#import-chart').click()
        expect(self.page.locator('#chart-library option')).to_have_count(2);self.page.locator('#chart-library').select_option(prior['id']);self.page.get_by_role('button',name='Retomar',exact=True).click()
        expect(self.page.locator('#chart-geometry-summary')).to_contain_text('3 pernas nativas')
        self.assertEqual(self.records('ndb')[0]['reconstruction']['points'],prior['reconstruction']['points'])
        self.assertEqual(self.mission_snapshot(),before)
        self.page.get_by_role('button',name='Atualizar prévia',exact=True).click();expect(self.page.locator('#chart-status')).to_contain_text('prévia salva foi preservada')
        self.assertEqual(self.errors,[])

    def test_native_conversion_keeps_published_altitudes_separate_from_clearance(self):
        self.open();m=self.build('sbls_ndb-rwy-13_iac_20250220.pdf')
        for point,value in [('ULVUK','5000'),('KUDGU','4500'),('KOVMO','3930'),('ESIGO','7000')]:
            r=m['native']['restrictions']['p-'+point];self.assertEqual(r['altitude'],value);self.assertEqual(r['qualifier'],'above');self.assertEqual(r['phase'],'');self.assertEqual(r['plannedAltitude'],'');self.assertEqual(r['inspectionAltitude'],'')
        self.assertEqual(m['native']['mission'],{})

    def test_geometry_archive_keeps_snapshot_but_never_restores_approval(self):
        self.open();self.install_local_fixture();self.choose('sbls_ndb-rwy-13_iac_20250220.pdf')
        prior=self.records()[0]
        with self.page.expect_download() as download:self.page.get_by_role('button',name='Exportar rascunho',exact=True).click()
        data=Path(download.value.path()).read_bytes();archive=json.loads(data);self.assertEqual(archive['version'],2)
        self.page.locator('#chart-archive').set_input_files({'name':'snapshot.ivchart','mimeType':'application/json','buffer':data})
        self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        rows=self.records();self.assertEqual(len(rows),2)
        restored=next(r for r in rows if r['id']!=prior['id'])['reconstruction']
        self.assertEqual(restored['native']['points'],prior['reconstruction']['native']['points'])
        self.assertIn('archive-review',[i['id'] for i in restored['issues']]);self.assertFalse(restored['review']['validated'])

    def test_context_never_changes_for_iac_sid_or_native_preview(self):
        self.open('ndb');m=self.build('sbnt_rnp-rwy-16l_iac_20231005-1.pdf','ndb')
        self.assertEqual(m['module'],'ndb');self.assertEqual(m['native']['module'],'ndb')
        m['native']['module']='procedimentos'
        rejected=self.page.evaluate("doc=>{try{window.IVProcedurePreview.render(doc);return false;}catch{return true;}}",m['native'])
        self.assertTrue(rejected)

    def test_defined_major_arc_becomes_curves_and_invalid_arc_is_rejected(self):
        self.open()
        r=self.page.evaluate("""async()=>{
          const {destination}=await import('./chart-import/geodesy.mjs'),{validateModel,MODEL_SCHEMA}=await import('./chart-import/reconstruct.mjs'),{toNativeDocument}=await import('./chart-import/native.mjs');
          const c={lat:0,lon:0},m={schema:MODEL_SCHEMA,module:'procedimentos',source:{chart:{}},reference:{course:'true',variation:null},points:[{id:'c',name:'CENTER',position:c,roles:[]},{id:'a',name:'START',position:destination(c,0,10),roles:[]},{id:'b',name:'END',position:destination(c,270,10),roles:[]}],legs:[{id:'arc',type:'arc',from:'a',to:'b',center:'c',turn:'right',radiusNM:10,radiusResolution:.1}],verticalConstraints:[],paths:[],issues:[]};
          const original=JSON.stringify(m.points);m.checks=validateModel(m).results;const valid=toNativeDocument(m);m.legs[0].radiusNM=8;m.checks=validateModel(m).results;const invalid=toNativeDocument(m);return {valid,invalid,unchanged:JSON.stringify(m.points)===original};
        }""")
        self.assertTrue(r['unchanged']);self.assertEqual(len(r['valid']['document']['segments']),3)
        self.assertTrue(all(e['type']=='curve' for e in r['valid']['document']['segments']))
        self.assertEqual(len(r['valid']['mapping']['legs']['arc']),3);self.assertEqual(r['invalid']['document']['segments'],[])

    def test_missing_magnetic_reference_and_unknown_leg_types_cannot_convert(self):
        self.open()
        r=self.page.evaluate("""async()=>{const {MODEL_SCHEMA,validateModel}=await import('./chart-import/reconstruct.mjs'),{toNativeDocument}=await import('./chart-import/native.mjs');const m={schema:MODEL_SCHEMA,module:'ndb',source:{chart:{}},reference:{course:'magnetic',variation:null},points:[{id:'a',name:'A',roles:[],position:{lat:0,lon:0}},{id:'b',name:'B',roles:[],position:{lat:0,lon:1}}],legs:[{id:'ab',type:'line',from:'a',to:'b',published:{reference:'magnetic',course:90,distanceNM:60.1,distanceResolution:.1,courseResolution:1}},{id:'hold',type:'holding',from:'a',to:'a'}],verticalConstraints:[],paths:[],issues:[]};m.checks=validateModel(m).results;return {checks:m.checks,native:toNativeDocument(m).document};}""")
        self.assertTrue(all(not c['passed'] for c in r['checks']));self.assertEqual(r['native']['segments'],[])

    def test_explicit_published_coordinates_preserve_precision_and_require_datum(self):
        self.open()
        r=self.page.evaluate("""async()=>{const {publishedPositions,interpret}=await import('./chart-import/decea.mjs');const line={text:'ALPHA 19° 38’ 30.1234” S 044° 03’ 17.9876” W',evidenceIds:['text-1']};const ex={text:[],lines:[line,{text:'WGS-84'}],vectors:[],pageTransform:[1,0,0,-1,0,800],width:600,height:800};const yes=publishedPositions(ex);ex.lines.pop();const unknown=publishedPositions(ex);ex.lines=[{text:'ALPHA 19° 60’ 30” S 044° 03’ 17” W'}];return {yes,unknown,invalid:publishedPositions(ex),provider:interpret(ex,{metadata:{},kind:'IAC'}).provider};}""")
        point=r['yes'][0];self.assertEqual(point['datum'],'WGS84');self.assertEqual(point['evidenceIds'],['text-1'])
        self.assertAlmostEqual(point['position']['lat'],-(19+38/60+30.1234/3600),12)
        self.assertAlmostEqual(point['position']['lon'],-(44+3/60+17.9876/3600),12)
        self.assertEqual(r['unknown'][0]['datum'],'unspecified');self.assertEqual(r['invalid'],[])
        self.assertEqual(r['provider'],'unsupported-local')

    def test_unconfirmed_full_circle_and_invalid_vertical_window_are_not_converted(self):
        self.open()
        r=self.page.evaluate("""async()=>{const {destination}=await import('./chart-import/geodesy.mjs'),{validateModel,MODEL_SCHEMA}=await import('./chart-import/reconstruct.mjs'),{toNativeDocument}=await import('./chart-import/native.mjs');const c={lat:0,lon:0},a=destination(c,0,10),m={schema:MODEL_SCHEMA,module:'ndb',source:{chart:{}},reference:{course:'true'},points:[{id:'c',name:'C',position:c},{id:'a',name:'A',position:a},{id:'b',name:'B',position:a}],legs:[{id:'arc',type:'arc',from:'a',to:'b',center:'c',turn:'right',radiusNM:10,radiusResolution:.1}],verticalConstraints:[{id:'v',entity:'a',unit:'FT',reference:'MSL',qualifier:'between',lower:5000,upper:4000}],paths:[]};m.checks=validateModel(m).results;const unconfirmed=toNativeDocument(m);m.legs[0].sweepDegrees=360;m.checks=validateModel(m).results;return {unconfirmed,confirmed:toNativeDocument(m)};}""")
        self.assertEqual(r['unconfirmed']['document']['segments'],[])
        self.assertEqual(len(r['confirmed']['document']['segments']),4)
        self.assertNotIn('altitude',r['confirmed']['document']['restrictions'].get('a',{}))

    def test_native_preview_responsive_iphone_ipad_and_comparison(self):
        self.open();self.install_local_fixture();self.choose('sbls_ndb-rwy-13_iac_20250220.pdf')
        before=self.mission_snapshot()
        for width,height in [(390,844),(844,390),(768,1024),(1024,768)]:
            with self.subTest(viewport=(width,height)):
                self.page.set_viewport_size({'width':width,'height':height})
                self.page.get_by_role('button',name='Prévia do desenho',exact=True).click()
                expect(self.page.locator('#chart-native')).to_be_visible()
                self.assertEqual(self.page.locator('#chart-native g[data-segment]').count(),3)
                bounds=self.page.locator('#chart-import-dialog').evaluate("d=>({right:d.getBoundingClientRect().right,bottom:d.getBoundingClientRect().bottom,overflow:d.scrollWidth>d.clientWidth+1})")
                self.assertLessEqual(bounds['right'],width);self.assertLessEqual(bounds['bottom'],height);self.assertFalse(bounds['overflow'])
                if width>=760:
                    self.page.get_by_role('button',name='Comparar',exact=True).click()
                    expect(self.page.locator('#chart-native')).to_be_visible();expect(self.page.locator('#chart-original')).to_be_visible()
                    left=self.page.locator('.ci-preview').bounding_box();right=self.page.locator('.ci-native').bounding_box()
                    self.assertGreater(right['x'],left['x']+left['width']-1)
        self.assertEqual(self.mission_snapshot(),before);self.assertEqual(self.errors,[])

    def test_published_coordinate_priority_reports_base_conflict_without_moving_source(self):
        self.open()
        r=self.page.evaluate("""async()=>{const {identify,openDocument}=await import('./chart-import/extract.mjs'),{recognize}=await import('./chart-import/model.mjs'),{indexDatabase}=await import('./chart-import/aeronautical.mjs'),{reconstruct}=await import('./chart-import/reconstruct.mjs');const raw=await(await fetch('../packages/aixm/AIXM-BR-2026-09-03/aixm-core.json')).json(),db=indexDatabase(raw),file=new File([await(await fetch('../tests/fixtures/charts/sbls_ndb-rwy-13_iac_20250220.pdf')).blob()],'test.pdf'),source=await identify(file),doc=await openDocument(file,source);try{const extraction=await doc.extract(1,document.createElement('canvas')),before=JSON.stringify(db),line={text:'KUDGU 19° 38’ 30.1234” S 044° 03’ 17.9876” W',evidenceIds:['synthetic-coordinate']};extraction.lines.push(line,{text:'WGS84'});const m=reconstruct({source,page:1,module:'ndb',extraction,recognition:recognize(extraction)},db);return {point:m.points.find(p=>p.name==='KUDGU'),issues:m.issues,unchanged:before===JSON.stringify(db)};}finally{await doc.destroy();}}""")
        self.assertTrue(r['unchanged']);p=r['point'];self.assertEqual(p['coordinateState'],'published')
        self.assertEqual(p['coordinateSource']['kind'],'chart-published-coordinate')
        self.assertAlmostEqual(p['position']['lat'],-(19+38/60+30.1234/3600),12)
        self.assertEqual(p['position'],p['coordinateSource']['originalPosition'])
        self.assertTrue(any(i['id']=='chart-base-coordinate-p-KUDGU' for i in r['issues']))


if __name__=='__main__':unittest.main()
