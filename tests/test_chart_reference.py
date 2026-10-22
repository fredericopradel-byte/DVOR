"""Measured recognition audit against manually inspected chart evidence, not full coverage."""
import hashlib
import json
import os
from pathlib import Path
import unittest
import fitz
import test_e2e
import test_chart_import
import test_chart_geometry
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = json.loads((ROOT / 'tests/fixtures/charts/recognition-reference.json').read_text())


class ChartReferenceTests(unittest.TestCase):
    setUpClass = classmethod(test_e2e.PlannerTests.setUpClass.__func__)
    setUp = test_e2e.PlannerTests.setUp

    assert_loaded = test_e2e.PlannerTests.assert_loaded
    dismiss_database_prompt = test_e2e.PlannerTests.dismiss_database_prompt

    open = test_chart_import.ChartImportTests.open
    choose = test_chart_import.ChartImportTests.choose
    records = test_chart_import.ChartImportTests.records
    mission_snapshot = test_chart_import.ChartImportTests.mission_snapshot
    install_local_fixture = test_chart_geometry.ChartGeometryTests.install_local_fixture

    def test_rebuild_refreshes_recognition_without_replacing_saved_draft_silently(self):
        self.open(); self.install_local_fixture()
        self.choose('sbgl_rnp-z-rwy-33--ar-_iac_20231102.pdf')
        before = self.mission_snapshot()
        session_id = self.records()[0]['id']
        self.page.get_by_role('button', name='Fechar importação', exact=True).click()
        self.page.evaluate("""async id=>{
          const s=await import('./chart-import/storage.mjs'),r=await s.load(id,'procedimentos');
          r.recognition.metadata.procedure.value='RNP Z RWY 33';r.recognition.requirements=[];
          r.recognition.structures=r.recognition.structures.filter(v=>v.type!=='rf-leg');
          r.reconstruction.source.chart.procedure.value='RNP Z RWY 33';
          r.reconstruction.issues=r.reconstruction.issues.filter(v=>v.id!=='structure-rf-leg');
          await s.save(r,r.file);
        }""", session_id)
        self.page.locator('#import-chart').click()
        expect(self.page.locator('#chart-library option')).to_have_count(2)
        self.page.locator('#chart-library').select_option(session_id)
        self.page.get_by_role('button', name='Retomar', exact=True).click()
        expect(self.page.locator('#chart-result')).to_be_visible()
        self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        # Opening an old draft preserves its prior reconstruction until explicit rebuild.
        self.assertEqual(self.records()[0]['recognition']['metadata']['procedure']['value'],'RNP Z RWY 33')
        self.page.get_by_role('button', name='Atualizar prévia', exact=True).click()
        self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        updated = self.records()[0]
        self.assertEqual(updated['recognition']['metadata']['procedure']['value'],'RNP Z RWY 33 (AR)')
        self.assertIn('structure-rf-leg',{v['id'] for v in updated['reconstruction']['issues']})
        self.assertEqual(updated['previousReconstructions'][-1]['source']['chart']['procedure']['value'],'RNP Z RWY 33')
        self.assertFalse(updated['reconstruction']['review']['validated'])
        self.assertEqual(before,self.mission_snapshot())
        self.assertEqual(self.errors,[])

    def test_real_chart_reference_audit_and_no_false_validation(self):
        self.assert_loaded(self.page.goto(self.base + 'inspecao/desenhar.html?modulo=procedimentos'))
        self.dismiss_database_prompt()
        before = self.page.evaluate('()=>JSON.stringify({...localStorage})')
        results = []
        for case in REFERENCE['cases']:
            with self.subTest(chart=case['file']):
                path = ROOT / 'tests/fixtures/charts' / case['file']
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), case['sha256'])
                with fitz.open(path) as pdf:
                    self.assertEqual(len(pdf), case['pages'])
                    for evidence in case['evidence']:
                        self.assertTrue(1 <= evidence['page'] <= len(pdf))
                        x0, y0, x1, y1 = evidence['region']
                        self.assertTrue(0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1)
                actual = self.page.evaluate("""async name=>{
                  const {identify,openDocument}=await import('./chart-import/extract.mjs');
                  const {recognize}=await import('./chart-import/model.mjs');
                  const {indexDatabase}=await import('./chart-import/aeronautical.mjs');
                  const {reconstruct}=await import('./chart-import/reconstruct.mjs');
                  const raw=await(await fetch('../packages/aixm/AIXM-BR-2026-09-03/aixm-core.json')).json();
                  const db=indexDatabase(raw),file=new File([await(await fetch('../tests/fixtures/charts/'+name)).blob()],'neutral.pdf');
                  const source=await identify(file),doc=await openDocument(file,source),pages=[];
                  try {for(let page=1;page<=doc.pages;page++){
                    const extraction=await doc.extract(page,document.createElement('canvas')),recognition=recognize(extraction);
                    const model=reconstruct({source,page,module:'procedimentos',extraction,recognition},db);
                    pages.push({page,recognition,model,text:extraction.lines.map(r=>r.text).join(' '),textItems:extraction.text.length,vectorOps:extraction.vectors.length,truncated:extraction.truncated});
                  }return {source,pages};}finally{await doc.destroy();}
                }""", case['file'])
                self.assertEqual(len(actual['pages']), case['pages'])
                main = actual['pages'][0]['model']
                for page in actual['pages']:
                    self.assertGreater(page['textItems'], 50)
                    self.assertGreater(page['vectorOps'], 0)
                    self.assertFalse(page['truncated'])
                    # Partial recognition must never silently certify a real chart.
                    self.assertFalse(page['model']['review']['validated'])
                    self.assertTrue(any(i['critical'] for i in page['model']['issues']))
                    self.assertEqual(page['recognition']['validity'], 'not-verified')
                self.assertNotIn('layout-missing', {i['id'] for i in main['issues']})
                ids = [v['id'] for v in main['verticalConstraints']]
                self.assertEqual(len(ids), len(set(ids)), 'Duplicate vertical restriction IDs')
                if 'rf-required' in case['features']:
                    rec = actual['pages'][0]['recognition']
                    self.assertEqual(rec['metadata']['procedure']['value'], case['title'])
                    self.assertTrue({'RF','RNP AR APCH','AUTORIZAÇÃO ESPECIAL'}.issubset({r['value'] for r in rec['requirements']}))
                    self.assertIn('structure-rf-leg', {i['id'] for i in main['issues']})
                    self.assertNotIn('structure-dme-arc', {i['id'] for i in main['issues']})
                # These are known negative chart annotations, not production word/value filters.
                self.assertFalse({'PONTE','AFTER'}.intersection(p['name'] for p in main['points']))
                self.assertFalse(any(v.get('value') == 600 for v in main['verticalConstraints']))
                self.assertFalse(any(v.get('entity') == 'p-CXI' and v.get('value') == 170 for v in main['verticalConstraints']))
                by_id = {p['id']: p for p in main['points']}
                names = {p['name'] for p in main['points']}
                legs = {(by_id[l['from']]['name'], by_id[l['to']]['name']): l for l in main['legs']}
                # A retained published parent may now be faithfully subdivided by a
                # profile-only station. Require actual continuous native model children.
                for parent in main.get('profileGeometry',{}).get('parents',[]):
                    children=[l for l in main['legs'] if l.get('source',{}).get('parent')==parent['id']]
                    cursor=parent['from']; remaining=list(children); total=0
                    while remaining:
                        next_leg=next((l for l in remaining if l['from']==cursor),None)
                        if next_leg is None:break
                        total+=next_leg['published']['distanceNM'];cursor=next_leg['to'];remaining.remove(next_leg)
                    if children and not remaining and cursor==parent['to'] and abs(total-parent['published']['distanceNM'])<1e-10:
                        legs[(by_id[parent['from']]['name'],by_id[parent['to']]['name'])]=parent
                metrics = []
                for start, end, course, distance in case['legs']:
                    leg = legs.get((start, end))
                    matches = bool(leg and leg['type'] == 'line' and leg['published']['course'] == course and leg['published']['distanceNM'] == distance and leg['published']['reference'] == 'magnetic')
                    metrics.append(dict(start=start,end=end,course=course,distanceNM=distance,matched=matches,actual=leg))
                results.append(dict(file=case['file'],sha256=case['sha256'],pages=actual['pages'],namedReferenceFound=sorted(names.intersection(case['points'])),namedReferenceMissing=sorted(set(case['points'])-names),referenceLegs=metrics,referenceAltitudes=[dict(**a,matched=any(v.get('entity')=='p-'+a['point'] and v.get('value')==a['value'] and v.get('unit')==a['unit'] and v.get('reference')==a['reference'] for v in main['verticalConstraints'])) for a in case['altitudeValues']]))
        for case, row in zip(REFERENCE['cases'], results):
            self.assertGreaterEqual(sum(l['matched'] for l in row['referenceLegs']), case['regressionFloor']['matchedReferenceLegs'], case['file'])
            self.assertGreaterEqual(sum(a['matched'] for a in row['referenceAltitudes']), case['regressionFloor']['matchedAltitudeValues'], case['file'])
        after = self.page.evaluate('()=>JSON.stringify({...localStorage})')
        self.assertEqual(after, before, 'Read-only audit changed persisted user state')
        self.assertEqual(self.errors, [])
        output = os.environ.get('IV_CHART_AUDIT_OUTPUT')
        if output:
            Path(output).write_text(json.dumps(dict(reference=REFERENCE,results=results),ensure_ascii=False,indent=2)+'\n')
        print('\nReference subsets only (not full-chart recognition):')
        for row in results:
            m=row['pages'][0]['model']
            print(row['file'], 'reference legs',sum(l['matched'] for l in row['referenceLegs']),'/',len(row['referenceLegs']), 'points',len(m['points']),'native segments',len(m['native']['segments']),'critical',sum(bool(i['critical']) for i in m['issues']))
