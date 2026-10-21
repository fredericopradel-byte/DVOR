"""Stage 4: contextual decisions, replay, geometry, audit and offline integrity."""
import json
from pathlib import Path
import unittest
from playwright.sync_api import expect
import test_e2e
import test_chart_import as previous
import test_chart_geometry as geometry

CHART='sbgm_rnp-y-rwy-35_iac_20260514.pdf'


class ChartReviewTests(unittest.TestCase):
    setUpClass=classmethod(test_e2e.PlannerTests.setUpClass.__func__)
    setUp=test_e2e.PlannerTests.setUp
    assert_loaded=test_e2e.PlannerTests.assert_loaded
    dismiss_database_prompt=test_e2e.PlannerTests.dismiss_database_prompt
    open=previous.ChartImportTests.open
    choose=previous.ChartImportTests.choose
    records=previous.ChartImportTests.records
    mission_snapshot=previous.ChartImportTests.mission_snapshot
    install_local_fixture=geometry.ChartGeometryTests.install_local_fixture

    def fixture(self,name=CHART):
        return self.page.evaluate("""async name=>{const {identify,openDocument}=await import('./chart-import/extract.mjs'),{recognize}=await import('./chart-import/model.mjs'),{indexDatabase}=await import('./chart-import/aeronautical.mjs'),{reconstruct}=await import('./chart-import/reconstruct.mjs');const raw=await(await fetch('../packages/aixm/AIXM-BR-2026-09-03/aixm-core.json')).json(),file=new File([await(await fetch('../tests/fixtures/charts/'+name)).blob()],name),source=await identify(file),doc=await openDocument(file,source);try{const extraction=await doc.extract(1,document.createElement('canvas')),s={source,page:1,module:'procedimentos',extraction,recognition:recognize(extraction)};window.reviewFixture={s,m:reconstruct(s,indexDatabase(raw))};return window.reviewFixture.m;}finally{await doc.destroy();}}""",name)

    def decide(self,issue,kind,answer):
        return self.page.evaluate("""async a=>{const {decide}=await import('./chart-import/review.mjs');const f=window.reviewFixture;f.m=decide(f.m,f.s,a.issue,a.kind,a.answer);return f.m;}""",dict(issue=issue,kind=kind,answer=answer))

    def step(self,direction):
        return self.page.evaluate("""async direction=>{const {historyStep}=await import('./chart-import/review.mjs'),f=window.reviewFixture;f.m=historyStep(f.m,f.s,direction);return f.m;}""",direction)

    def test_qualifier_decision_undo_redo_and_fork_preserve_original(self):
        self.open();base=self.fixture();original=json.dumps(base,sort_keys=True)
        m=self.decide('qualifier-profile-p-ANSAG','altitude',{'value':2120,'qualifier':'at'})
        self.assertNotIn('qualifier-profile-p-ANSAG',[i['id'] for i in m['issues']]);self.assertEqual(m['reviewWork']['base']['verticalConstraints'],base['verticalConstraints'])
        self.assertEqual(m['native']['restrictions']['p-ANSAG']['altitude'],'2120');self.assertEqual(m['native']['restrictions']['p-ANSAG']['phase'],'')
        self.assertIn('qualifier-profile-p-ANSAG',[i['id'] for i in self.step('undo')['issues']])
        self.assertNotIn('qualifier-profile-p-ANSAG',[i['id'] for i in self.step('redo')['issues']])
        self.step('undo');m=self.decide('qualifier-profile-p-ANSAG','altitude',{'value':2120,'qualifier':'above'})
        self.assertEqual(len(m['reviewWork']['nodes']),2);self.assertIsNone(m['reviewWork']['nodes'][1]['parent'])
        self.assertEqual(json.dumps(base,sort_keys=True),original);self.assertFalse(m['review']['validated'])
        self.assertEqual(m['native']['mission'],{})

    def test_visual_boundary_splits_native_geometry_and_keeps_official_coordinates(self):
        self.open();base=self.fixture();m=self.decide('visual-boundary-l-p-ANSAG-p-RWY35','visual',{'distanceNM':3})
        self.assertEqual(len(m['native']['segments']),5);self.assertEqual(len(m['native']['points']),6)
        self.assertTrue(all(c['passed'] for c in m['checks']));self.assertFalse(any(i['id'].startswith('visual-boundary-') for i in m['issues']))
        for p in base['points']:self.assertEqual(p['position'],next(q for q in m['points'] if q['id']==p['id'])['position'])
        visual=next(l for l in m['legs'] if l.get('flightRules')=='visual');self.assertEqual(visual['published']['distanceNM'],3)
        self.assertEqual(next(l for l in m['legs'] if l['id'].endswith('-before-visual'))['flightRules'],'unclassified')
        rendered=self.page.evaluate("m=>{const svg=window.IVProcedurePreview.render(m.native);return {text:svg.textContent,dashes:svg.querySelectorAll('g[data-segment] path[stroke-dasharray]').length};}",m)
        self.assertIn('VISUAL',rendered['text']);self.assertEqual(rendered['dashes'],1)
        self.assertEqual(len(self.step('undo')['native']['segments']),4)

    def test_coordinate_correction_recomputes_derived_threshold_and_related_legs(self):
        self.open();base=self.fixture();p=next(p for p in base['points'] if p['name']=='ANSAG')
        # A constraint issue can also direct a coordinate correction on its named entity.
        m=self.decide('qualifier-profile-p-ANSAG','position',{'entity':p['id'],'lat':p['position']['lat']+.00001,'lon':p['position']['lon'],'origin':'Coordenada WGS84 conferida na publicação de teste'})
        self.assertEqual(next(q for q in m['points'] if q['id']==p['id'])['coordinateSource']['kind'],'manual-confirmed')
        old=next(p for p in base['points'] if p['name']=='RWY35');new=next(p for p in m['points'] if p['name']=='RWY35')
        self.assertNotEqual(old['position'],new['position']);self.assertTrue(all(c['passed'] for c in m['checks']))
        self.assertEqual(self.step('undo')['points'],base['points'])

    def test_prior_coordinate_acceptance_becomes_stale_when_anchor_changes(self):
        self.open();base=self.fixture();self.decide('derived-p-RWY35','confirm-coordinate',{})
        p=next(p for p in base['points'] if p['name']=='ANSAG')
        m=self.decide('qualifier-profile-p-ANSAG','position',{'entity':p['id'],'lat':p['position']['lat']+.00001,'lon':p['position']['lon'],'origin':'Referência corrigida em teste'})
        self.assertIn('derived-p-RWY35',[i['id'] for i in m['issues']]);self.assertTrue(any(not o['applied'] for o in m['reviewWork']['outcomes']))
        self.assertTrue(any(i['id'].startswith('decision-') for i in m['issues']))

    def test_ambiguous_fix_selection_keeps_source_precision_and_builds_new_associations(self):
        self.open();m=self.fixture('sbnt_rnp-rwy-16l_iac_20231005-1.pdf');issue=next(i for i in m['issues'] if i['id'].startswith('coordinate-') and i.get('options'))
        option=issue['options'][0];m=self.decide(issue['id'],'position',{'entity':issue['entities'][0],'lat':option['position']['lat'],'lon':option['position']['lon'],'origin':json.dumps(option['source'])})
        point=next(p for p in m['points'] if p['id']==issue['entities'][0]);self.assertEqual(point['position'],option['position'])
        self.assertNotIn(issue['id'],[i['id'] for i in m['issues']]);self.assertEqual(point['coordinateSource']['originalPosition'],option['position'])

    def test_inconsistent_leg_definition_stays_critical_and_outside_native(self):
        self.open();self.fixture();m=self.decide('visual-boundary-l-p-ANSAG-p-RWY35','visual',{'distanceNM':5})
        # Expose an actual published annotation conflict using a baseline with moved endpoints.
        m=self.page.evaluate("""async()=>{const f=window.reviewFixture;f.m=structuredClone(f.m.reviewWork.base);const leg=f.m.legs[0];f.m.issues.push({id:'geometry-test',category:'inconsistency',critical:true,message:'Conflito de teste',entities:[leg.id]});const {decide}=await import('./chart-import/review.mjs');return decide(f.m,f.s,'geometry-test','leg',{from:leg.from,to:leg.to,course:'360',distance:'50.0',reference:'magnetic'});}""")
        bad=[c for c in m['checks'] if not c['passed']];self.assertTrue(bad)
        self.assertTrue(all(c['entity'] not in [s['id'] for s in m['native']['segments']] for c in bad))
        self.assertTrue(any(i['id'].startswith('geometry-') and i['critical'] for i in m['issues']))

    def test_invalid_answers_and_unsupported_acknowledgement_do_not_mutate_model(self):
        self.open();base=self.fixture()
        for issue,kind,answer in [('structure-holding','confirm-coordinate',{}),('qualifier-profile-p-ANSAG','altitude',{'value':5000,'upper':4000,'qualifier':'between'}),('visual-boundary-l-p-ANSAG-p-RWY35','visual',{'distanceNM':8}),('qualifier-profile-p-ANSAG','position',{'entity':'p-ANSAG','lat':95,'lon':-65,'origin':'test'})]:
            with self.subTest(kind=kind):
                with self.assertRaises(Exception):self.decide(issue,kind,answer)
        self.assertEqual(self.page.evaluate('window.reviewFixture.m'),base)
        self.assertTrue(any(i['id']=='coverage-review' for i in base['issues']))

    def test_decisions_are_bound_to_module_page_and_file(self):
        self.open();self.fixture();self.decide('qualifier-profile-p-ANSAG','altitude',{'value':2120,'qualifier':'at'})
        for field,value in [('module','ndb'),('page',2),('sha256','other')]:
            with self.subTest(field=field):
                self.assertTrue(self.page.evaluate("""async ({field,value})=>{const {replayReview}=await import('./chart-import/review.mjs'),f=window.reviewFixture,s=structuredClone(f.s);if(field==='sha256')s.source.sha256=value;else s[field]=value;try{replayReview(f.m,s);return false;}catch{return true;}}""",dict(field=field,value=value)))

    def ui_issue(self,text):
        self.page.get_by_role('button',name='Dados identificados',exact=True).click()
        self.page.locator('.ci-summary details').filter(has=self.page.locator('.ci-pending-link')).evaluate('d=>d.open=true')
        self.page.locator('.ci-pending-link').filter(has_text=text).click()
        expect(self.page.locator('.ci-review')).to_be_visible()

    def test_contextual_ui_highlight_crop_decision_and_history(self):
        self.open();self.install_local_fixture();before=self.mission_snapshot();self.choose(CHART)
        self.ui_issue('Qualificador da altitude')
        expect(self.page.locator('#chart-issue-source')).to_be_visible();expect(self.page.locator('#chart-issue-drawing [data-issue-highlight]').first).to_be_visible()
        self.assertEqual(self.page.locator('#chart-issue-drawing').get_attribute('data-focused'),'true')
        self.page.get_by_label('Restrição publicada',exact=True).select_option('at');self.page.get_by_role('button',name='Confirmar restrição',exact=True).click()
        self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        m=self.records()[0]['reconstruction'];self.assertEqual(len(m['reviewWork']['nodes']),1)
        self.assertNotIn('qualifier-profile-p-ANSAG',[i['id'] for i in m['issues']])
        self.page.get_by_role('button',name='Desfazer resposta',exact=True).click();self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        self.assertIn('qualifier-profile-p-ANSAG',[i['id'] for i in self.records()[0]['reconstruction']['issues']])
        self.page.get_by_role('button',name='Refazer resposta',exact=True).click();self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        self.ui_issue('PROSSIGA VMC identificado')
        self.page.get_by_role('button',name='Visual nos últimos 3 NM',exact=True).click();self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        self.assertEqual(len(self.records()[0]['reconstruction']['native']['segments']),5)
        self.assertEqual(self.mission_snapshot(),before);self.assertEqual(self.errors,[])

    def test_offline_reopen_archive_restores_history_without_approval_or_cross_module(self):
        self.open('ndb');self.install_local_fixture();before=self.mission_snapshot();self.choose(CHART);self.ui_issue('Qualificador da altitude')
        self.page.get_by_label('Restrição publicada',exact=True).select_option('above');self.page.get_by_role('button',name='Confirmar restrição',exact=True).click();self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        prior=self.records('ndb')[0]
        with self.page.expect_download() as download:self.page.get_by_role('button',name='Exportar rascunho',exact=True).click()
        data=Path(download.value.path()).read_bytes()
        self.page.evaluate("""async()=>{await caches.delete('ivdata-package-chart-geometry-fixture');await new Promise(resolve=>{const r=indexedDB.open('ivplanner-package-manager-v1',1);r.onsuccess=()=>{const db=r.result,tx=db.transaction('packages','readwrite');tx.objectStore('packages').delete('chart-test-aixm');tx.oncomplete=()=>{db.close();resolve();};};});}""")
        self.context.set_offline(True);self.page.reload();self.dismiss_database_prompt();self.page.locator('[data-page=drawing]').click();self.page.locator('#import-chart').click()
        self.page.locator('#chart-library').select_option(prior['id']);self.page.get_by_role('button',name='Retomar',exact=True).click();expect(self.page.locator('#chart-geometry-summary')).to_contain_text('4 pernas nativas')
        self.assertEqual(self.records('ndb')[0]['reconstruction']['reviewWork'],prior['reconstruction']['reviewWork'])
        self.page.locator('#chart-archive').set_input_files({'name':'review.ivchart','mimeType':'application/json','buffer':data});self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        rows=self.records('ndb');self.assertEqual(len(rows),2);restored=next(r for r in rows if r['id']!=prior['id'])['reconstruction'];self.assertIn('archive-review',[i['id'] for i in restored['issues']]);self.assertFalse(restored['review']['validated'])
        self.page.get_by_role('button',name='Resolver pendências',exact=True).click();self.page.get_by_role('button',name='Desfazer resposta',exact=True).click();self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        self.assertEqual(self.records('procedimentos'),[]);self.assertEqual(self.mission_snapshot(),before);self.assertEqual(self.errors,[])

    def test_responsive_review_crop_inputs_and_sticky_navigation(self):
        self.open();self.install_local_fixture();self.choose(CHART)
        for width,height in [(390,844),(844,390),(768,1024),(1024,768)]:
            with self.subTest(viewport=(width,height)):
                self.page.set_viewport_size({'width':width,'height':height});self.ui_issue('Qualificador da altitude')
                bounds=self.page.locator('#chart-import-dialog').evaluate("d=>({right:d.getBoundingClientRect().right,bottom:d.getBoundingClientRect().bottom,overflow:d.scrollWidth>d.clientWidth+1})")
                self.assertLessEqual(bounds['right'],width);self.assertLessEqual(bounds['bottom'],height);self.assertFalse(bounds['overflow'])
                self.assertEqual(self.page.locator('.ci-review input').first.evaluate('e=>getComputedStyle(e).fontSize'),'16px')
                self.assertEqual(self.page.locator('.ci-mobile-tabs').evaluate('e=>getComputedStyle(e).position'),'sticky')
                expect(self.page.locator('#chart-issue-source')).to_be_visible();expect(self.page.locator('#chart-issue-drawing')).to_be_visible()
        self.assertEqual(self.errors,[])

    def test_quota_failure_keeps_answer_in_memory_and_portable_export(self):
        self.open();self.install_local_fixture();before=self.mission_snapshot();self.choose(CHART);self.ui_issue('Qualificador da altitude')
        self.page.evaluate("""()=>{const original=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(...args){if(this.name==='sessions'){IDBObjectStore.prototype.put=original;throw new DOMException('test quota','QuotaExceededError');}return original.apply(this,args);};}""")
        self.page.get_by_label('Restrição publicada',exact=True).select_option('at');self.page.get_by_role('button',name='Confirmar restrição',exact=True).click()
        expect(self.page.locator('[data-review-message]')).to_contain_text('não salva')
        self.assertNotIn('reviewWork',self.records()[0]['reconstruction'])
        with self.page.expect_download() as download:self.page.get_by_role('button',name='Exportar rascunho',exact=True).click()
        archive=json.loads(Path(download.value.path()).read_bytes());self.assertEqual(len(archive['reconstruction']['reviewWork']['nodes']),1)
        self.page.get_by_role('button',name='Salvar rascunho',exact=True).click();expect(self.page.locator('#chart-status')).to_contain_text('Rascunho salvo')
        self.assertEqual(len(self.records()[0]['reconstruction']['reviewWork']['nodes']),1);self.assertEqual(self.mission_snapshot(),before)

    def test_corrupt_history_is_rejected_and_explicit_refresh_preserves_answers(self):
        self.open();self.install_local_fixture();self.choose(CHART);self.ui_issue('Qualificador da altitude')
        self.page.get_by_label('Restrição publicada',exact=True).select_option('at');self.page.get_by_role('button',name='Confirmar restrição',exact=True).click();self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        prior=self.records()[0];self.page.get_by_role('button',name='Atualizar prévia',exact=True).click();expect(self.page.locator('#chart-status')).to_contain_text('Histórico preservado')
        self.assertEqual(self.records()[0]['reconstruction']['reviewWork'],prior['reconstruction']['reviewWork'])
        with self.page.expect_download() as download:self.page.get_by_role('button',name='Exportar rascunho',exact=True).click()
        archive=json.loads(Path(download.value.path()).read_bytes());archive['reconstruction']['reviewWork']['binding']['module']='ndb'
        self.page.locator('#chart-archive').set_input_files({'name':'bad.ivchart','mimeType':'application/json','buffer':json.dumps(archive).encode()})
        expect(self.page.locator('#chart-status')).to_contain_text('Histórico incompatível')
        self.assertEqual(len(self.records()),1);self.assertEqual(self.records()[0]['reconstruction']['reviewWork'],prior['reconstruction']['reviewWork'])

    def test_existing_threshold_ambiguity_is_not_erased_by_unrelated_answer(self):
        self.open();self.fixture()
        m=self.page.evaluate("""async()=>{const f=window.reviewFixture,p=f.m.points.find(p=>p.name==='RWY35');p.position=null;p.coordinateSource=null;p.coordinateState='missing';f.m.issues.push({id:'threshold-database-ambiguity',category:'ambiguity',critical:true,message:'Duas cabeceiras locais',entities:[p.id]});const {decide}=await import('./chart-import/review.mjs');return decide(f.m,f.s,'qualifier-profile-p-ANSAG','altitude',{value:2120,qualifier:'at'});}""")
        self.assertIn('threshold-database-ambiguity',[i['id'] for i in m['issues']])
        self.assertIsNone(next(p for p in m['points'] if p['name']=='RWY35')['position'])

    def test_selecting_source_does_not_silently_confirm_its_edition(self):
        self.open();base=self.fixture()
        m=self.page.evaluate("""async()=>{const f=window.reviewFixture,p=f.m.points.find(p=>p.name==='ANSAG'),row={id:'test-future',name:'ANSAG',position:structuredClone(p.position),source:{...p.coordinateSource,validFrom:'2099-01-01'}};f.m.issues.push({id:'coordinate-'+p.id,category:'ambiguity',critical:true,message:'Fonte de teste ambígua',entities:[p.id],options:[row]});const {decide}=await import('./chart-import/review.mjs');return decide(f.m,f.s,'coordinate-'+p.id,'position',{entity:p.id,lat:row.position.lat,lon:row.position.lon,origin:'Fonte candidata de teste',choice:0});}""")
        self.assertIn('date-p-ANSAG',[i['id'] for i in m['issues']])
        point=next(p for p in m['points'] if p['name']=='ANSAG')
        self.assertEqual(point['coordinateSource']['selectedSource']['validFrom'],'2099-01-01')
        self.assertNotIn('coordinate-p-ANSAG',[i['id'] for i in m['issues']])


if __name__=='__main__':unittest.main()
