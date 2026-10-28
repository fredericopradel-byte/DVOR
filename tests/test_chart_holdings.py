"""Real published holding patterns: source evidence, native editing and isolated persistence."""
import unittest
from playwright.sync_api import expect
import test_e2e
import test_chart_import as previous
import test_chart_geometry as geometry
import test_chart_review as review

W='sbnt_vor-w-rwy-16l_iac_20250515.pdf'
Y='sbnt_vor-y-rwy-12_iac_20240321.pdf'
GL='sbgl_vor-y-rwy-15_iac_20241003.pdf'
NDB='sbls_ndb-rwy-13_iac_20250220.pdf'
KEY='ivplanner-procedure-editor-procedimentos-v1'

class ChartHoldingsTests(unittest.TestCase):
    setUpClass=classmethod(test_e2e.PlannerTests.setUpClass.__func__)
    setUp=test_e2e.PlannerTests.setUp
    assert_loaded=test_e2e.PlannerTests.assert_loaded
    dismiss_database_prompt=test_e2e.PlannerTests.dismiss_database_prompt
    open=previous.ChartImportTests.open
    choose=previous.ChartImportTests.choose
    records=previous.ChartImportTests.records
    mission_snapshot=previous.ChartImportTests.mission_snapshot
    install_local_fixture=geometry.ChartGeometryTests.install_local_fixture
    fixture=review.ChartReviewTests.fixture
    decide=review.ChartReviewTests.decide
    step=review.ChartReviewTests.step
    ui_issue=review.ChartReviewTests.ui_issue

    def dimensions(self,name=W,anchor='EGEGI'):
        self.choose(name);self.ui_issue('Hipódromo associado a '+anchor)
        self.page.get_by_label('Extensão da perna no desenho (NM)',exact=True).fill('2.3456789')
        self.page.get_by_label('Raio das curvas no desenho (NM)',exact=True).fill('0.7501234')
        self.page.get_by_role('button',name='Gerar hipódromo editável',exact=True).click()
        self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")

    def test_three_real_patterns_include_schematic_inset_without_pixel_georeferencing(self):
        self.open();before=self.mission_snapshot()
        for name,anchor,course,turn in [(W,'p-EGEGI',59,'right'),(Y,'p-DAKOK',358,'right'),(GL,'p-SISER',295,'left'),(NDB,'p-ESIGO',300,'right')]:
            with self.subTest(chart=name):
                m=self.fixture(name);h=next(h for h in m['holdings'] if h['anchor']==anchor)
                self.assertEqual(h['inbound']['value'],course);self.assertEqual(h['turn'],turn);self.assertEqual(h['purpose'],'holding')
                self.assertIsNone(h['published']['legDefinition']);self.assertNotIn('drawing',h)
                self.assertEqual(m['nativeMapping']['holdings'],{})
                self.assertTrue(h['evidenceIds']);self.assertFalse(m['review']['validated'])
                self.assertIn('holding-geometry-'+h['id'],[i['id'] for i in m['issues']])
                self.assertIn('structure-holding',[i['id'] for i in m['issues']])
        self.assertEqual(before,self.mission_snapshot());self.assertEqual(self.errors,[])

    def test_drawing_decision_undo_redo_and_anchor_change_keep_original_and_main_route(self):
        self.open();base=self.fixture(W);h=base['holdings'][0];issue='holding-geometry-'+h['id']
        m=self.decide(issue,'holding',{'mode':'time','timeSeconds':90,'groundSpeedKT':120,'radiusNM':.750123456})
        mapping=m['nativeMapping']['holdings'][h['id']]
        self.assertEqual(mapping['legLengthNM'],3);self.assertEqual(mapping['radiusNM'],.750123456)
        self.assertEqual(m['points'],base['points']);self.assertEqual(m['legs'],base['legs']);self.assertEqual(m['native']['flight'],base['native']['flight'])
        self.assertEqual(len(m['native']['segments']),len(base['native']['segments'])+4)
        self.assertNotIn(issue,[i['id'] for i in m['issues']]);self.assertIn('holding-route-'+h['id'],[i['id'] for i in m['issues']])
        self.assertTrue(all('timeSeconds' not in r for r in m['native']['restrictions'].values()))
        self.assertEqual(self.step('undo')['native'],base['native']);self.assertEqual(self.step('redo')['native'],m['native'])
        self.page.evaluate("""issue=>{const m=window.reviewFixture.m,h=m.holdings[0];m.issues.push({id:issue,holdingId:h.id,entities:[h.anchor],critical:true,category:'missing',message:'Rever espera'});}""",issue)
        p=next(p for p in m['points'] if p['id']==h['anchor'])
        changed=self.decide(issue,'position',{'entity':p['id'],'lat':p['position']['lat']+.000001,'lon':p['position']['lon'],'origin':'Coordenada do fixo conferida no teste'})
        self.assertEqual(changed['nativeMapping']['holdings'],{});self.assertIn(issue,[i['id'] for i in changed['issues']]);self.assertTrue(any(not o['applied'] for o in changed['reviewWork']['outcomes']))
        self.assertEqual(self.step('undo')['native'],m['native'])

    def test_contextual_touch_ui_saved_decisions_resume_offline_without_mission_change(self):
        self.open();self.install_local_fixture();before=self.mission_snapshot();self.choose(W);self.ui_issue('Hipódromo associado a')
        expect(self.page.locator('#chart-issue-source')).to_be_visible()
        for width,height in [(390,844),(844,390),(768,1024),(1024,768)]:
            self.page.set_viewport_size({'width':width,'height':height});self.assertFalse(self.page.locator('#chart-import-dialog').evaluate('d=>d.scrollWidth>d.clientWidth+1'))
        self.page.get_by_label('Extensão da perna no desenho (NM)',exact=True).fill('2.3456789')
        self.page.get_by_label('Raio das curvas no desenho (NM)',exact=True).fill('0.7501234')
        self.page.get_by_role('button',name='Gerar hipódromo editável',exact=True).click()
        self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        record=self.records()[0];m=record['reconstruction'];self.assertEqual(m['holdings'][0]['drawing']['legLengthNM'],2.3456789)
        self.context.set_offline(True);self.page.reload();self.dismiss_database_prompt();self.page.locator('[data-page=drawing]').click();self.page.locator('#import-chart').click()
        self.page.locator('#chart-library').select_option(record['id']);self.page.get_by_role('button',name='Retomar',exact=True).click();expect(self.page.locator('#chart-result')).to_be_visible();self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        self.assertEqual(self.records()[0]['reconstruction'],m);self.assertEqual(before,self.mission_snapshot());self.assertEqual(self.errors,[])

    def test_native_pattern_selection_source_edit_undo_and_offline_profile_preserve_provenance(self):
        self.open();self.install_local_fixture();self.dimensions();self.page.get_by_role('button',name='Conferência final',exact=True).click()
        expect(self.page.locator('.ci-final')).to_contain_text('Hipódromos reconhecidos')
        self.page.locator('#chart-final-apply').click();expect(self.page.locator('#chart-import-dialog')).not_to_be_visible()
        before=self.page.evaluate('(k)=>JSON.parse(localStorage.getItem(k))',KEY)
        h=before['chartImport']['provenance']['holdings'][0];mapping=before['chartImport']['provenance']['mapping']['holdings'][h['id']]
        self.assertEqual(len(mapping['segments']),4);self.assertTrue(all(s not in before['flight']['segments'] for s in mapping['segments']))
        path=self.page.locator('#drawing path[data-segment="'+mapping['segments'][0]+'"]');path.scroll_into_view_if_needed()
        at=path.evaluate('p=>{const q=p.getPointAtLength(p.getTotalLength()/2),m=p.getScreenCTM();return {x:m.a*q.x+m.c*q.y+m.e,y:m.b*q.x+m.d*q.y+m.f};}')
        self.page.mouse.click(at['x'],at['y']);self.page.locator('#properties details').first.evaluate('d=>d.open=true')
        expect(self.page.locator('#properties pre').first).to_contain_text('hipodromo');self.assertNotIn('Elemento criado após a importação',self.page.locator('#properties pre').first.inner_text())
        self.page.locator('#prop-radius').fill('0.9');self.page.get_by_role('button',name='Aplicar medidas',exact=True).click()
        edited=self.page.evaluate('(k)=>JSON.parse(localStorage.getItem(k))',KEY);self.assertTrue(edited['chartImport']['modifications']);self.assertEqual(edited['chartImport']['provenance'],before['chartImport']['provenance'])
        self.page.keyboard.press('Control+z');self.context.set_offline(True);self.page.reload();self.dismiss_database_prompt();after=self.page.evaluate('(k)=>JSON.parse(localStorage.getItem(k))',KEY)
        self.assertEqual(after['segments'],before['segments']);self.assertEqual(after['chartImport']['provenance'],before['chartImport']['provenance'])
        self.page.locator('[data-page=drawing]').click();self.page.locator('#view-vertical').click();expect(self.page.locator('#vertical-view')).to_be_visible();self.assertEqual(self.errors,[])

    def test_ndb_published_holding_keeps_destination_data_and_module_independence(self):
        self.open('ndb');self.install_local_fixture();self.dimensions(NDB,'ESIGO');self.page.get_by_role('button',name='Conferência final',exact=True).click()
        expect(self.page.locator('.ci-final')).not_to_contain_text('não cobre a inspeção específica');self.page.locator('#chart-final-apply').click()
        expect(self.page.locator('#chart-import-dialog')).not_to_be_visible()
        data=self.page.evaluate("()=>({ndb:JSON.parse(localStorage.getItem('ivplanner-procedure-editor-ndb-v1')),procedimentos:localStorage.getItem('ivplanner-procedure-editor-procedimentos-v1')})")
        self.assertIsNone(data['procedimentos']);self.assertEqual(data['ndb']['module'],'ndb');self.assertTrue(any(h['anchor']=='p-ESIGO' and h.get('drawing') for h in data['ndb']['chartImport']['provenance']['holdings']));self.assertFalse(data['ndb']['chartImport']['review']['validated'])

if __name__=='__main__':unittest.main()
