"""Explicit profile axes, verified profile-only stations and published vertical data."""
import json
from pathlib import Path
import unittest
from playwright.sync_api import expect
import test_e2e
import test_chart_import as previous
import test_chart_geometry as geometry

ILS='sbgl_ils-t-or-loc-t-rwy-10_iac_20250710.pdf'
VOR='sbgl_vor-y-rwy-15_iac_20241003.pdf'
RNP='sbgl_rnp-a-rwy-33_iac_20240613.pdf'


class ChartProfileAxesTests(unittest.TestCase):
    setUpClass=classmethod(test_e2e.PlannerTests.setUpClass.__func__)
    setUp=test_e2e.PlannerTests.setUp
    assert_loaded=test_e2e.PlannerTests.assert_loaded
    dismiss_database_prompt=test_e2e.PlannerTests.dismiss_database_prompt
    open=previous.ChartImportTests.open
    choose=previous.ChartImportTests.choose
    records=previous.ChartImportTests.records
    mission_snapshot=previous.ChartImportTests.mission_snapshot
    install_local_fixture=geometry.ChartGeometryTests.install_local_fixture

    def build(self,name=ILS,edit='normal'):
        return self.page.evaluate("""async({name,edit})=>{
          const {identify,openDocument}=await import('./chart-import/extract.mjs'),{recognize}=await import('./chart-import/model.mjs'),{indexDatabase}=await import('./chart-import/aeronautical.mjs'),{reconstruct}=await import('./chart-import/reconstruct.mjs'),{interpret}=await import('./chart-import/decea.mjs');
          const raw=await(await fetch('../packages/aixm/AIXM-BR-2026-09-03/aixm-core.json')).json(),before=JSON.stringify(raw),db=indexDatabase(raw);
          const file=new File([await(await fetch('../tests/fixtures/charts/'+name)).blob()],'neutral.pdf'),source=await identify(file),doc=await openDocument(file,source);
          try{const extraction=await doc.extract(1,document.createElement('canvas'));
            if(edit==='dme')for(const t of extraction.text)if(t.text.includes('TO THR'))t.text=t.text.replace('(NM)','(DME)');
            if(edit==='no-header')for(const t of extraction.text)if(t.text==='FINAL CRS')t.text='';
            if(edit==='course-conflict'){
              const p=interpret(extraction,recognize(extraction)),r=p.runs.find(r=>r.text==='097'&&r.bbox[1]>440&&r.bbox[1]<470),ids=r.evidenceIds;let first=true;
              for(const t of extraction.text)if(ids.includes(t.id)){t.text=first?'182':'';first=false;}
            }
            if(edit==='ambiguous-anchor')db.entities.push({...db.entities.find(r=>r.name==='GL167'),id:'conflicting-anchor',position:{lat:-22.9,lon:-43.4}});
            if(edit==='bad-crosscheck')db.entities.find(r=>r.name==='GAVUG').position.lat+=.02;
            if(edit==='bad-station')db.entities.find(r=>r.name==='GL008').position.lat+=.02;
            if(edit==='scale'){extraction.width*=1.5;extraction.height*=1.5;extraction.pageTransform=extraction.pageTransform.map(v=>v*1.5);for(const t of extraction.text){t.pageMatrix=t.pageMatrix.map(v=>v*1.5);t.width*=1.5;}}
            const recognition=recognize(extraction),session={id:'profile-test',module:'procedimentos',page:1,source,extraction,recognition},model=reconstruct(session,db);
            window.profileTestSession=session;window.profileTestModel=model;
            return {model,baseUnchanged:before===JSON.stringify(raw)};
          }finally{await doc.destroy();}
        }""",dict(name=name,edit=edit))

    def test_real_dual_axes_preserve_dme_nature_and_nonzero_mapt(self):
        self.open();m=self.build(VOR)['model'];pub=m['publishedProfile']
        by={a['reference']['name']:a for a in pub['axes']}
        self.assertEqual([v['raw'] for v in by['CXI']['marks']],['11.8','5.3','2.4','1.7','1.3','0.3'])
        self.assertEqual([v['raw'] for v in by['THR15']['marks']],['11.5','5.0','2.1','1.4','1.0','0.0'])
        self.assertEqual(by['CXI']['reference']['distanceKind'],'slant-range')
        self.assertEqual(by['THR15']['reference']['distanceKind'],'threshold-reference-dme-labelled')
        station=next(s for s in pub['stations'] if s['name']=='RWY15')
        self.assertEqual({d['reference']['name']:d['valueNM'] for d in station['distances']},{'CXI':1.3,'THR15':1})
        self.assertIsNone(next(p for p in m['points'] if p['name']=='RWY15')['position'])
        self.assertTrue(any(i['id'].startswith('profile-distance-kind-') for i in m['issues']))
        self.assertIn('profile-runway-reference-p-RWY15',{i['id'] for i in m['issues']})

    def test_profile_only_fix_is_georeferenced_and_splits_only_verified_parent(self):
        self.open();r=self.build();m=r['model'];self.assertTrue(r['baseUnchanged'])
        point=next(p for p in m['points'] if p['name']=='GL008')
        self.assertEqual(point['origin'],'published-profile');self.assertEqual(point['coordinateSource']['kind'],'local-database')
        self.assertEqual(point['position'],point['coordinateSource']['originalPosition'])
        station=next(s for s in m['publishedProfile']['stations'] if s['name']=='GL008')
        self.assertEqual({d['reference']['name']:d['raw'] for d in station['distances']},{'THR10':'8.7','ITB':'11.0'})
        legs={(l['from'],l['to']):l for l in m['legs']}
        self.assertEqual(legs['p-GAVUG','p-GL008']['published']['distanceNM'],2)
        self.assertEqual(legs['p-GL008','p-GL167']['published']['distanceNM'],3.7)
        self.assertEqual(legs['p-GL008','p-GL167']['published']['distanceResolution'],.2)
        self.assertNotIn(('p-GAVUG','p-GL167'),legs)
        self.assertEqual(m['profileGeometry']['parents'][0]['published']['distanceNM'],5.7)
        self.assertTrue(all(c['passed'] for c in m['checks']))
        self.assertNotIn('p-GL008',m['native']['restrictions'])  # qualifier was not published unambiguously
        confirmed=self.page.evaluate("""async()=>{const {decide}=await import('./chart-import/review.mjs');return decide(window.profileTestModel,window.profileTestSession,'qualifier-profile-p-GL008','altitude',{entity:'p-GL008',value:2800,qualifier:'at'});}""")
        native=confirmed['native']['restrictions']['p-GL008'];self.assertEqual(native['altitude'],'2800')
        self.assertEqual(native['plannedAltitude'],'');self.assertEqual(native['inspectionAltitude'],'')

    def test_localizer_threshold_is_derived_only_from_explicit_consistent_publications(self):
        self.open();m=self.build()['model'];p=next(p for p in m['points'] if p['name']=='RWY10')
        self.assertEqual(p['coordinateState'],'derived-review')
        self.assertEqual(p['coordinateSource']['definition'],'published-localizer-final-and-profile')
        self.assertEqual(p['coordinateSource']['anchor'],'p-GL167')
        self.assertEqual(p['coordinateSource']['distanceNM'],5);self.assertEqual(p['coordinateSource']['course'],97)
        self.assertEqual(p['coordinateSource']['variation']['value'],-23)
        self.assertTrue(p['coordinateSource']['crossChecks'][0]['passed'])
        self.assertFalse(p['coordinateSource']['roundingBound']['includesAnchorUncertainty'])
        self.assertAlmostEqual(p['position']['lat'],-22.8009281095157,11)
        self.assertAlmostEqual(p['position']['lon'],-43.2554705780293,11)
        scaled=self.build(edit='scale')['model'];other=next(p for p in scaled['points'] if p['name']=='RWY10')
        self.assertEqual(other['position'],p['position'])
        for edit in ['dme','no-header','course-conflict','ambiguous-anchor','bad-crosscheck']:
            with self.subTest(edit=edit):
                bad=self.build(edit=edit)['model'];target=next((p for p in bad['points'] if p['name']=='RWY10'),None)
                self.assertTrue(target is None or target['position'] is None)

    def test_mapt_axis_cannot_be_relabelled_as_threshold_and_minima_are_separate(self):
        self.open();m=self.build(RNP)['model']
        self.assertEqual(m['publishedProfile']['axes'][0]['reference']['kind'],'mapt')
        self.assertEqual(next(s for s in m['publishedProfile']['stations'] if s['name']=='GL053')['distances'][0]['valueNM'],0)
        self.assertFalse(any(p['coordinateSource'] and p['coordinateSource']['kind']=='chart-derived' for p in m['points']))
        m=self.build()['model'];minimum=m['publishedProfile']['minima']
        self.assertEqual([(r['type'],r['value'],r['ochFT'],r['variant']) for r in minimum],[('DA',216,200,'CAT I'),('MDA',450,440,'LOC')])
        self.assertFalse(any(r.get('value') in [216,450] for r in m['verticalConstraints']))
        self.assertTrue(m['publishedProfile']['conditions'])
        self.assertTrue(all(r['status']=='unresolved-sequencing' for r in m['publishedProfile']['conditions']))
        vor=self.build(VOR)['model']['publishedProfile']
        self.assertTrue(any(g['value']==5 and g['scope']=='missed-approach' for g in vor['gradients']))
        self.assertTrue(any(g['value']==5.2 and g['scope']=='approach-profile' for g in vor['gradients']))

    def test_coordinate_correction_recomputes_split_and_undo_restores_it(self):
        self.open();self.build()
        r=self.page.evaluate("""async()=>{
          const {decide,historyStep}=await import('./chart-import/review.mjs');const m=window.profileTestModel,s=window.profileTestSession,p=m.points.find(p=>p.name==='GL008');
          const changed=decide(m,s,'qualifier-profile-p-GL008','position',{entity:p.id,lat:p.position.lat+.02,lon:p.position.lon,origin:'isolated test correction'});
          const undone=historyStep(changed,s,'undo');return {changed,undone};
        }""")
        self.assertTrue(any(i['id'].startswith('profile-split-') for i in r['changed']['issues']))
        self.assertFalse(any(l['source'].get('kind')=='profile-station-split' for l in r['changed']['legs']))
        self.assertTrue(any(l['from']=='p-GAVUG' and l['to']=='p-GL008' for l in r['undone']['legs']))
        self.assertFalse(any(i['id'].startswith('profile-split-') for i in r['undone']['issues']))
        bad=self.build(edit='bad-station')['model']
        self.assertTrue(any(l['from']=='p-GAVUG' and l['to']=='p-GL167' for l in bad['legs']))

    def test_profile_publications_survive_archive_offline_and_native_application(self):
        self.open();self.install_local_fixture();before=self.mission_snapshot();self.choose(ILS)
        original=self.records()[0]
        expect(self.page.locator('#chart-geometry-summary')).to_contain_text('5 pernas nativas')
        with self.page.expect_download() as download:self.page.get_by_role('button',name='Exportar rascunho',exact=True).click()
        archive=json.loads(Path(download.value.path()).read_bytes())
        self.assertEqual(archive['reconstruction']['publishedProfile'],original['reconstruction']['publishedProfile'])
        self.context.set_offline(True);self.page.reload();self.dismiss_database_prompt();self.page.locator('[data-page=drawing]').click();self.page.locator('#import-chart').click()
        expect(self.page.locator('#chart-library option')).to_have_count(2);self.page.locator('#chart-library').select_option(original['id']);self.page.get_by_role('button',name='Retomar',exact=True).click()
        expect(self.page.locator('#chart-geometry-summary')).to_contain_text('5 pernas nativas')
        self.assertEqual(self.records()[0]['reconstruction']['publishedProfile'],original['reconstruction']['publishedProfile'])
        self.assertEqual(self.mission_snapshot(),before)
        r=self.page.evaluate("""async()=>{
          const {list,load}=await import('./chart-import/storage.mjs'),{prepareApplication}=await import('./chart-import/finalize.mjs');
          const s=await load((await list('procedimentos'))[0].id,'procedimentos'),snapshot=window.IVProcedureChart.snapshot(),app=await prepareApplication(s,{mode:'new',approve:false});
          window.IVProcedureChart.apply(app,snapshot);return app.document.chartImport.provenance;
        }""")
        self.assertEqual(r['publishedProfile'],original['reconstruction']['publishedProfile'])
        self.assertEqual(r['profileGeometry'],original['reconstruction']['profileGeometry'])
        self.page.reload();self.dismiss_database_prompt()
        data=self.page.evaluate("JSON.parse(localStorage.getItem('ivplanner-procedure-editor-procedimentos-v1')).chartImport.provenance")
        self.assertEqual(data['publishedProfile'],r['publishedProfile'])
        self.assertEqual(self.records('ndb'),[])
        self.assertEqual(self.errors,[])

    def test_publication_details_fit_phone_tablet_and_keep_mission_untouched(self):
        self.open();self.install_local_fixture();self.choose(ILS);before=self.mission_snapshot()
        self.page.get_by_text('Coordenadas, restrições e verificações',exact=True).click()
        summary=self.page.get_by_text('Perfil publicado · referências e mínimos',exact=True)
        summary.click();details=summary.locator('..')
        expect(details).to_contain_text('distância DME oblíqua')
        expect(details).to_contain_text('DA 216 ft MSL')
        expect(details).to_contain_text('MDA 450 ft MSL')
        for width,height in [(390,844),(844,390),(820,1180)]:
            with self.subTest(viewport=(width,height)):
                self.page.set_viewport_size({'width':width,'height':height})
                bounds=self.page.locator('#chart-import-dialog').evaluate('d=>({width:d.scrollWidth,client:d.clientWidth,right:d.getBoundingClientRect().right,bottom:d.getBoundingClientRect().bottom})')
                self.assertLessEqual(bounds['width'],bounds['client']+1)
                self.assertLessEqual(bounds['right'],width);self.assertLessEqual(bounds['bottom'],height)
                self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        self.page.get_by_role('button',name='Conferência final',exact=True).click()
        expect(self.page.locator('.ci-final')).to_contain_text('DA 216 ft MSL')
        self.assertEqual(self.mission_snapshot(),before)
        self.assertEqual(self.errors,[])
