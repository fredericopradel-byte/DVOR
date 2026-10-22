"""Real DECEA DME arcs: native curves, review lifecycle and offline persistence."""
import unittest
from playwright.sync_api import expect
import test_e2e
import test_chart_import as previous
import test_chart_geometry as geometry
import test_chart_review as review

Y='sbnt_vor-y-rwy-12_iac_20240321.pdf'
W='sbnt_vor-w-rwy-16l_iac_20250515.pdf'
KEY='ivplanner-procedure-editor-procedimentos-v1'


class ChartDmeArcsTests(unittest.TestCase):
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

    def test_real_arcs_follow_published_topology_and_specific_dme_equipment(self):
        self.open();before=self.mission_snapshot()
        for name,expected in [(Y,[('p-EDROS',[],'p-ETINA','left'),('p-DAKOK',[],'p-ETINA','right')]),(W,[('p-EGEGI',['p-IRUNU'],'p-SALBA','right')])]:
            with self.subTest(chart=name):
                m=self.fixture(name);arcs=[l for l in m['legs'] if l['type']=='arc']
                self.assertEqual([(l['from'],l['via'],l['to'],l['turn']) for l in arcs],expected)
                center=next(p for p in m['points'] if p.get('origin')=='dme-center')
                self.assertEqual(center['position'],{'lat':-5.908355556,'lon':-35.248586111})
                self.assertEqual(center['position'],center['coordinateSource']['originalPosition'])
                vor=next(p for p in m['points'] if p['name']=='NTL');self.assertNotEqual(vor['position'],center['position'])
                for leg in arcs:
                    self.assertEqual(leg['center'],center['id']);self.assertEqual(leg['publishedDME']['distanceKind'],'slant-range')
                    native=[s for s in m['native']['segments'] if s['id'] in m['nativeMapping']['legs'][leg['id']]]
                    self.assertTrue(native);self.assertTrue(all(s['type']=='curve' for s in native))
                    self.assertIn('dme-horizontal-'+leg['id'],[i['id'] for i in m['issues']])
                if name==W:
                    native=[s for s in m['native']['segments'] if s['type']=='curve']
                    self.assertEqual([(s['from'],s['to']) for s in native],[('p-EGEGI','p-IRUNU'),('p-IRUNU','p-SALBA')])
                self.assertTrue(all(c['passed'] for c in m['checks']))
                self.assertFalse(m['review']['validated'])
                self.assertIn('coverage-review',[i['id'] for i in m['issues']]);self.assertIn('structure-holding',[i['id'] for i in m['issues']])
        self.assertEqual(self.mission_snapshot(),before)

    def test_confirmation_undo_redo_and_coordinate_change_invalidate_old_acceptance(self):
        self.open();base=self.fixture(W);leg=next(l for l in base['legs'] if l['type']=='arc');issue='dme-horizontal-'+leg['id']
        m=self.decide(issue,'confirm-arc',{});self.assertNotIn(issue,[i['id'] for i in m['issues']]);self.assertEqual(m['reviewWork']['base']['points'],base['points'])
        self.assertNotIn('projection-review-'+leg['id'],[i['id'] for i in m['issues']]);self.assertEqual(len(m['native']['segments']),3)
        self.assertIn(issue,[i['id'] for i in self.step('undo')['issues']]);self.assertNotIn(issue,[i['id'] for i in self.step('redo')['issues']])
        # Reopen a geometry issue to correct the center using the same contextual form.
        self.page.evaluate("""issue=>{const m=window.reviewFixture.m,leg=m.legs.find(l=>l.type==='arc');m.issues.push({id:issue,category:'ambiguity',critical:true,entities:[leg.id,leg.center],message:'Rever centro'});}""",issue)
        p=next(p for p in m['points'] if p['id']==leg['center'])
        changed=self.decide(issue,'position',{'entity':p['id'],'lat':p['position']['lat']+.000001,'lon':p['position']['lon'],'origin':'Coordenada conferida em teste'})
        self.assertIn(issue,[i['id'] for i in changed['issues']]);self.assertTrue(any(not o['applied'] for o in changed['reviewWork']['outcomes']))
        self.assertTrue(any(i['id'].startswith('decision-') for i in changed['issues']))
        self.assertEqual(self.step('undo')['native'],m['native'])

    def test_real_dme_missing_or_conflicting_equipment_is_never_replaced_by_vor(self):
        self.open();self.fixture(W)
        r=self.page.evaluate("""async()=>{const {indexDatabase}=await import('./chart-import/aeronautical.mjs'),{reconstruct}=await import('./chart-import/reconstruct.mjs'),raw=await(await fetch('../packages/aixm/AIXM-BR-2026-09-03/aixm-core.json')).json(),out=[];for(const mode of ['missing','conflict','ambiguous','via-conflict']){const copy=structuredClone(raw),dme=copy.navaidEquipment.find(r=>r.designator==='NTL'&&r.equipmentType==='DME');if(mode==='via-conflict')copy.designatedPoints.find(r=>r.designator==='IRUNU').position.lat+=.02;if(mode==='missing')copy.navaidEquipment=copy.navaidEquipment.filter(r=>r!==dme);if(mode==='conflict')dme.position.lat+=.04;if(mode==='ambiguous')copy.navaidEquipment.push({...dme,id:'second-dme',position:{...dme.position,lat:dme.position.lat+.001}});out.push({mode,m:reconstruct(window.reviewFixture.s,indexDatabase(copy))});}return out;}""")
        for row in r:
            self.assertEqual([l for l in row['m']['legs'] if l['type']=='arc'],[])
            self.assertTrue(any(i['critical'] and ('dme-' in i['id']) for i in row['m']['issues']))
        self.assertIsNone(next(p for p in r[0]['m']['points'] if p.get('origin')=='dme-center')['position'])
        fixed=self.page.evaluate("""async m=>{const {question,decide}=await import('./chart-import/review.mjs'),i=m.issues.find(i=>i.id.startsWith('dme-radius-')),q=question(m,i),center=window.reviewFixture.m.points.find(p=>p.origin==='dme-center');return {kind:q.kind,model:decide(m,window.reviewFixture.s,i.id,'position',{entity:center.id,...center.position,origin:'Coordenada específica do DME conferida na fonte local de teste'})};}""",r[1]['m'])
        self.assertEqual(fixed['kind'],'position');self.assertEqual(sum(l['type']=='arc' for l in fixed['model']['legs']),1)
        self.assertFalse(any(i['id'].startswith('dme-radius-') for i in fixed['model']['issues']))


    def test_contextual_arc_ui_responsive_confirmation_and_saved_draft_resume_offline(self):
        self.open();self.install_local_fixture();before=self.mission_snapshot();self.choose(W)
        self.ui_issue('Arco DME reconstruído')
        expect(self.page.locator('#chart-issue-source')).to_be_visible()
        expect(self.page.locator('#chart-issue-drawing g[data-segment][data-issue-highlight]')).to_have_count(2)
        expect(self.page.locator('.ci-review')).to_contain_text('EGEGI → IRUNU → SALBA')
        for width,height in [(390,844),(844,390),(768,1024),(1024,768)]:
            self.page.set_viewport_size({'width':width,'height':height})
            self.assertFalse(self.page.locator('#chart-import-dialog').evaluate('d=>d.scrollWidth>d.clientWidth+1'))
        self.page.get_by_role('button',name='Aceitar representação horizontal neste rascunho',exact=True).click()
        self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        m=self.records()[0]['reconstruction'];self.assertTrue(any(n['kind']=='confirm-arc' for n in m['reviewWork']['nodes']))
        self.assertFalse(any(i['id'].startswith('dme-horizontal-') for i in m['issues']))
        sid=self.records()[0]['id'];self.context.set_offline(True);self.page.reload();self.dismiss_database_prompt()
        self.page.locator('[data-page=drawing]').click();self.page.locator('#import-chart').click()
        self.page.locator('#chart-library').select_option(sid);self.page.get_by_role('button',name='Retomar',exact=True).click()
        expect(self.page.locator('#chart-result')).to_be_visible();self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        self.assertEqual(self.records()[0]['reconstruction'],m);self.assertEqual(before,self.mission_snapshot());self.assertEqual(self.errors,[])

    def test_curves_apply_to_native_editor_edit_undo_and_reopen_offline(self):
        self.open();self.install_local_fixture();self.choose(W)
        self.page.get_by_role('button',name='Conferência final',exact=True).click();self.page.locator('#chart-final-apply').click()
        expect(self.page.locator('#chart-import-dialog')).not_to_be_visible()
        before=self.page.evaluate('(k)=>JSON.parse(localStorage.getItem(k))',KEY)
        self.assertEqual(sum(s['type']=='curve' for s in before['segments']),2)
        self.assertEqual(before['chartImport']['provenance']['dmeArcs']['associations'][0]['via'],['p-IRUNU'])
        self.assertFalse(before['chartImport']['review']['validated'])
        arc=next(s for s in before['segments'] if s['type']=='curve')
        path=self.page.locator('#drawing path[data-segment="'+arc['id']+'"]')
        path.scroll_into_view_if_needed()
        at=path.evaluate('p=>{const q=p.getPointAtLength(p.getTotalLength()/2),m=p.getScreenCTM();return {x:m.a*q.x+m.c*q.y+m.e,y:m.b*q.x+m.d*q.y+m.f};}')
        self.page.mouse.click(at['x'],at['y'])
        expect(self.page.locator('#prop-radius')).to_be_visible()
        self.page.locator('#prop-radius').fill('8.1');self.page.get_by_role('button',name='Aplicar medidas',exact=True).click()
        edited=self.page.evaluate('(k)=>JSON.parse(localStorage.getItem(k))',KEY)
        self.assertTrue(edited['chartImport']['modifications']);self.assertEqual(edited['chartImport']['provenance'],before['chartImport']['provenance'])
        self.page.keyboard.press('Control+z');self.assertEqual(self.page.evaluate('(k)=>JSON.parse(localStorage.getItem(k)).segments',KEY),before['segments'])
        self.context.set_offline(True);self.page.reload();self.dismiss_database_prompt()
        after=self.page.evaluate('(k)=>JSON.parse(localStorage.getItem(k))',KEY)
        self.assertEqual(after['chartImport']['provenance'],before['chartImport']['provenance']);self.assertEqual(after['segments'],before['segments']);self.assertEqual(self.errors,[])


if __name__=='__main__':unittest.main()
