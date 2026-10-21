"""Published profile distances, geodesic derivation and visual-final provenance."""
import unittest
from playwright.sync_api import expect
import test_e2e
import test_chart_import as previous
import test_chart_geometry as geometry

CHART='sbgm_rnp-y-rwy-35_iac_20260514.pdf'


class ChartProfileTests(unittest.TestCase):
    setUpClass=classmethod(test_e2e.PlannerTests.setUpClass.__func__)
    setUp=test_e2e.PlannerTests.setUp
    assert_loaded=test_e2e.PlannerTests.assert_loaded
    dismiss_database_prompt=test_e2e.PlannerTests.dismiss_database_prompt
    open=previous.ChartImportTests.open
    choose=previous.ChartImportTests.choose
    records=previous.ChartImportTests.records
    mission_snapshot=previous.ChartImportTests.mission_snapshot
    install_local_fixture=geometry.ChartGeometryTests.install_local_fixture

    def build(self,edit='normal',module='procedimentos'):
        return self.page.evaluate("""async ({edit,module})=>{
          const {identify,openDocument}=await import('./chart-import/extract.mjs'),{recognize}=await import('./chart-import/model.mjs'),{indexDatabase}=await import('./chart-import/aeronautical.mjs'),{reconstruct}=await import('./chart-import/reconstruct.mjs'),{interpret}=await import('./chart-import/decea.mjs'),{reconstructThreshold}=await import('./chart-import/profile.mjs');
          const raw=window.chartRaw??=await(await fetch('../packages/aixm/AIXM-BR-2026-09-03/aixm-core.json')).json(),db=indexDatabase(raw),before=JSON.stringify(raw);
          const file=new File([await(await fetch('../tests/fixtures/charts/sbgm_rnp-y-rwy-35_iac_20260514.pdf')).blob()],'renamed.pdf'),source=await identify(file),doc=await openDocument(file,source);
          try{const extraction=await doc.extract(1,document.createElement('canvas'));let recognition=recognize(extraction);
            if(edit==='dme')for(const t of extraction.text)if(t.text.includes('TO THR'))t.text=t.text.replace('TO THR','DME');
            if(edit==='wrong-runway')recognition.metadata.runway.value='17';
            if(edit==='truncated')extraction.truncated=true;
            if(edit==='no-course'){const p=interpret(extraction,recognition),ids=new Set(p.annotations[0].evidenceIds);extraction.text=extraction.text.filter(t=>!ids.has(t.id));}
            if(edit==='no-var')for(const t of extraction.text)if(t.id.match(/text-(?:1[0-9]|2[0-2])$/))t.text='';
            if(edit==='conflict')db.entities.find(p=>p.name==='GM001').position.lat+=.02;
            if(edit==='conflict-course')db.entities.find(p=>p.name==='GM001').position.lon+=.005;
            if(edit==='threshold'||edit==='threshold-duplicate'){const row={icao:'SBGM',runway:'35',position:{lat:-10.794088451275934,lon:-65.28210268920293},source:{kind:'local-database',collection:'runwayPoints'}};db.thresholds=[row];if(edit==='threshold-duplicate')db.thresholds.push({...row,id:'other'});}

            if(edit==='official')db.entities.push({id:'official-rwy',name:'RWY35',type:'fix',position:{lat:-10.79,lon:-65.25},source:{kind:'local-database'}});
            if(edit==='no-base')db.entities=[];
            if(edit==='scale'){extraction.width*=2;extraction.height*=2;extraction.pageTransform=extraction.pageTransform.map(n=>n*2);for(const t of extraction.text){t.pageMatrix=t.pageMatrix.map(n=>n*2);t.width*=2;}}

            const m=reconstruct({source,page:1,module,extraction,recognition},db);
            if(edit==='ambiguous'){const p=interpret(extraction,recognition),target=m.points.find(p=>p.name==='RWY35');target.position=null;target.coordinateState='missing';m.legs=m.legs.filter(l=>l.to!==target.id);p.annotations.push({...p.annotations[0],id:'duplicate-final'});reconstructThreshold(m,p,db);}
            return {m,sourceUnchanged:before===JSON.stringify(raw)};
          }finally{await doc.destroy();}
        }""",dict(edit=edit,module=module))

    def test_actual_profile_reconstructs_missing_threshold_with_traceable_precision(self):
        self.open();r=self.build();m=r['m'];p=next(p for p in m['points'] if p['name']=='RWY35')
        self.assertTrue(r['sourceUnchanged']);self.assertEqual(p['coordinateState'],'derived-review')
        self.assertAlmostEqual(p['position']['lat'],-10.794088451275934,11)
        self.assertAlmostEqual(p['position']['lon'],-65.28210268920293,11)
        source=p['coordinateSource'];self.assertEqual(source['originalPosition'],p['position'])
        self.assertEqual(source['anchor'],'p-ANSAG');self.assertEqual(source['distanceNM'],5)
        self.assertEqual(source['course'],360);self.assertEqual(source['variation']['value'],-13)
        self.assertFalse(source['roundingBound']['includesAnchorUncertainty'])
        self.assertEqual(source['crossChecks'][0]['anchor'],'p-GM001');self.assertTrue(source['crossChecks'][0]['passed'])
        self.assertAlmostEqual(source['crossChecks'][0]['separationNM'],.05038854549369888,8)
        self.assertEqual([(s['name'],s['distanceNM']) for s in m['profileReferences'][0]['stations']],[('RWY35',0),('ANSAG',5),('GM001',10)])
        self.assertEqual(len(m['native']['segments']),4);self.assertTrue(all(c['passed'] for c in m['checks']))
        self.assertNotIn('coordinate-p-RWY35',[i['id'] for i in m['issues']]);self.assertIn('derived-p-RWY35',[i['id'] for i in m['issues']])
        self.assertNotIn('association-annotation-1',[i['id'] for i in m['issues']])
        self.assertEqual(next(l for l in m['legs'] if l['from']=='p-GM001' and l['to']=='p-ANSAG')['published']['id'],'annotation-1')
        self.assertFalse(m['review']['validated'])

    def test_page_scale_does_not_change_geographic_reconstruction(self):
        self.open();first=self.build()['m'];scaled=self.build('scale')['m']
        p=lambda m:next(p for p in m['points'] if p['name']=='RWY35')
        self.assertEqual(p(first)['position'],p(scaled)['position'])
        self.assertEqual(p(first)['coordinateSource']['distanceNM'],p(scaled)['coordinateSource']['distanceNM'])

    def test_vmc_is_preserved_without_classifying_whole_final_or_guessing_boundary(self):
        self.open();m=self.build()['m'];leg=next(l for l in m['legs'] if l['to']=='p-RWY35')
        self.assertEqual(leg['flightRules'],'visual-transition-review');self.assertEqual(leg['visualReference']['bounds'],'unresolved')
        native=next(l for l in m['native']['segments'] if l['to']=='p-RWY35')
        self.assertEqual(native['visualReference'],leg['visualReference'])
        label=self.page.evaluate("m=>window.IVProcedurePreview.render(m.native).textContent",m)
        self.assertIn('VMC*',label);self.assertTrue(any(i['id'].startswith('visual-boundary-') and i['critical'] for i in m['issues']))
        self.assertIn('structure-holding',[i['id'] for i in m['issues']]);self.assertIn('coverage-review',[i['id'] for i in m['issues']])
        self.assertEqual(m['native']['mission'],{})

    def test_missing_or_incompatible_definitions_do_not_generate_threshold(self):
        self.open()
        for edit in ['dme','wrong-runway','truncated','no-course','no-var','no-base']:
            with self.subTest(edit=edit):
                m=self.build(edit)['m'];p=next((p for p in m['points'] if p['name']=='RWY35'),None)
                self.assertTrue(p is None or p['position'] is None)
                self.assertFalse(any(l['to']=='p-RWY35' for l in m['native']['segments']))

    def test_inconsistent_secondary_anchor_blocks_derivation(self):
        self.open()
        for edit in ['conflict','conflict-course']:
            with self.subTest(edit=edit):
                m=self.build(edit)['m']
                self.assertIsNone(next(p for p in m['points'] if p['name']=='RWY35')['position'])
                self.assertIn('threshold-conflict',[i['id'] for i in m['issues']])

    def test_existing_coordinate_is_not_overwritten_by_derivation(self):
        self.open();m=self.build('official')['m'];p=next(p for p in m['points'] if p['name']=='RWY35')
        self.assertEqual(p['position'],dict(lat=-10.79,lon=-65.25));self.assertEqual(p['coordinateSource']['kind'],'local-database')
        self.assertIn('threshold-source-conflict',[i['id'] for i in m['issues']])
        known=self.build('threshold')['m'];p=next(p for p in known['points'] if p['name']=='RWY35')
        self.assertEqual(p['coordinateState'],'threshold-database-review');self.assertEqual(p['coordinateSource']['collection'],'runwayPoints')
        ambiguous=self.build('threshold-duplicate')['m'];p=next(p for p in ambiguous['points'] if p['name']=='RWY35')
        self.assertIsNone(p['position']);self.assertIn('threshold-database-ambiguity',[i['id'] for i in ambiguous['issues']])

    def test_ambiguous_published_definition_is_not_chosen(self):
        self.open();m=self.build('ambiguous')['m']
        self.assertIsNone(next(p for p in m['points'] if p['name']=='RWY35')['position'])
        self.assertIn('threshold-ambiguity',[i['id'] for i in m['issues']])

    def test_derived_model_offline_reopen_archive_and_module_isolation(self):
        self.open('ndb');self.install_local_fixture();before=self.mission_snapshot();self.choose(CHART)
        expect(self.page.locator('#chart-geometry-summary')).to_contain_text('4 pernas nativas')
        self.page.get_by_role('button',name='Prévia do desenho',exact=True).click()
        expect(self.page.locator('#chart-native')).to_be_visible();expect(self.page.locator('.ci-native')).to_contain_text('VMC*')
        prior=self.records('ndb')[0];self.assertEqual(self.records('procedimentos'),[])
        with self.page.expect_download() as download:self.page.get_by_role('button',name='Exportar rascunho',exact=True).click()
        from pathlib import Path
        data=Path(download.value.path()).read_bytes()
        self.context.set_offline(True);self.page.reload();self.dismiss_database_prompt();self.page.locator('[data-page=drawing]').click();self.page.locator('#import-chart').click()
        self.page.locator('#chart-library').select_option(prior['id']);self.page.get_by_role('button',name='Retomar',exact=True).click()
        expect(self.page.locator('#chart-geometry-summary')).to_contain_text('4 pernas nativas')
        self.assertEqual(self.records('ndb')[0]['reconstruction']['points'],prior['reconstruction']['points'])
        self.page.locator('#chart-archive').set_input_files({'name':'sbgm.ivchart','mimeType':'application/json','buffer':data})
        self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        self.assertEqual(len(self.records('ndb')),2);self.assertEqual(self.records('procedimentos'),[])
        self.assertEqual(self.mission_snapshot(),before);self.assertEqual(self.errors,[])

    def test_derived_preview_and_vmc_warning_fit_iphone_ipad(self):
        self.open();self.install_local_fixture();before=self.mission_snapshot();self.choose(CHART)
        for width,height in [(390,844),(844,390),(768,1024),(1024,768)]:
            with self.subTest(viewport=(width,height)):
                self.page.set_viewport_size({'width':width,'height':height})
                self.page.get_by_role('button',name='Prévia do desenho',exact=True).click()
                expect(self.page.locator('#chart-native')).to_be_visible()
                self.assertEqual(self.page.locator('#chart-native g[data-segment]').count(),4)
                expect(self.page.locator('.ci-native')).to_contain_text('não é coordenada oficial')
                expect(self.page.locator('.ci-native')).to_contain_text('VMC*')
                box=self.page.locator('#chart-import-dialog').evaluate("d=>({right:d.getBoundingClientRect().right,bottom:d.getBoundingClientRect().bottom,overflow:d.scrollWidth>d.clientWidth+1})")
                self.assertLessEqual(box['right'],width);self.assertLessEqual(box['bottom'],height);self.assertFalse(box['overflow'])
        self.assertEqual(self.mission_snapshot(),before);self.assertEqual(self.errors,[])


if __name__=='__main__':unittest.main()
