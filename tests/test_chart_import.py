"""Stage 2: real PDF extraction and isolated import drafts, no operational reconstruction."""
import hashlib
import io
import json
from pathlib import Path
import unittest

import fitz
from PIL import Image
from playwright.sync_api import expect
import test_e2e

ROOT = Path(__file__).resolve().parents[1]
CHARTS = ROOT / 'tests/fixtures/charts'
CASES = json.loads((CHARTS / 'manifest.json').read_text())['cases']


class ChartImportTests(unittest.TestCase):
    setUpClass = classmethod(test_e2e.PlannerTests.setUpClass.__func__)
    setUp = test_e2e.PlannerTests.setUp
    assert_loaded = test_e2e.PlannerTests.assert_loaded
    dismiss_database_prompt = test_e2e.PlannerTests.dismiss_database_prompt

    def open(self, module='procedimentos'):
        self.assert_loaded(self.page.goto(self.base + 'inspecao/desenhar.html?modulo=' + module))
        self.dismiss_database_prompt()
        self.page.locator('[data-page=drawing]').click()
        self.page.locator('#import-chart').click()
        expect(self.page.locator('#chart-import-dialog')).to_be_visible()

    def choose(self, name='sbnt_ils-y-rwy-16l_iac_20231228.pdf'):
        self.page.locator('#chart-file').set_input_files(CHARTS / name)
        expect(self.page.locator('#chart-result')).to_be_visible(timeout=25000)
        expect(self.page.locator('#chart-status')).to_contain_text('Rascunho salvo', timeout=25000)
        self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy') === 'false'")

    def records(self, module='procedimentos'):
        return self.page.evaluate("""async module => {
          const s = await import('./chart-import/storage.mjs');const rows = await s.list(module);
          return await Promise.all(rows.map(async row => {const r = await s.load(row.id,module);delete r.file;return r;}));
        }""", module)

    def mission_snapshot(self):
        return self.page.evaluate("""()=>Object.fromEntries(Object.entries(localStorage).filter(([k])=>k.startsWith('ivplanner-procedure-')||k.startsWith('ivplanner-custom-')))""")

    def test_eight_real_charts_text_vectors_metadata_and_distinct_navigation(self):
        self.open()
        for case in CASES:
            with self.subTest(chart=case['file']):
                self.assertEqual(hashlib.sha256((CHARTS / case['file']).read_bytes()).hexdigest(), case['sha256'])
                result = self.page.evaluate("""async name => {
                  const {identify,openDocument} = await import('./chart-import/extract.mjs');
                  const {recognize} = await import('./chart-import/model.mjs');
                  const blob = await (await fetch('../tests/fixtures/charts/'+name)).blob();
                  const file = new File([blob], 'renamed.pdf', {type:'application/pdf'});
                  const source = await identify(file), doc = await openDocument(file,source);
                  try {const ex = await doc.extract(1,document.createElement('canvas'));
                    return {recognition:recognize(ex),text:ex.text,vectors:ex.vectors,truncated:ex.truncated};
                  } finally {await doc.destroy();}
                }""", case['file'])
                recognition = result['recognition']
                for key in ['icao', 'kind', 'procedure', 'publishedDate']:
                    self.assertEqual(recognition['metadata'].get(key, {}).get('value'), case[key])
                self.assertEqual(recognition['navigation'], case['navigation'])
                self.assertTrue(set(case['requirements']).issubset({x['value'] for x in recognition['requirements']}))
                self.assertTrue(set(case['structures']).issubset({x['type'] for x in recognition['structures']}))
                self.assertEqual(recognition['validity'], 'not-verified')
                self.assertIn('geometry-pending', [issue['id'] for issue in recognition['issues']])
                self.assertFalse(result['truncated'])
                if case['rasterOnly']:
                    self.assertEqual(result['text'], [])
                    self.assertIn('visual-required', [issue['id'] for issue in recognition['issues']])
                else:
                    self.assertGreater(len(result['text']), 50)
                    self.assertTrue(any(op['operator'] == 'constructPath' for op in result['vectors']))
                    self.assertTrue(all(len(item['transform']) == 6 and len(item['bbox']) == 4 for item in result['text']))
                    self.assertTrue(all(field['evidenceIds'] for field in recognition['metadata'].values()))
                if case['kind'] == 'SID':
                    self.assertIn('CXI', {a['ident'] for a in recognition['aids']})
                if case['navigation'] == ['ILS']:
                    self.assertNotIn('RNP', recognition['navigation'])
        self.assertEqual(self.errors, [])

    def test_ui_original_preview_and_no_mission_mutation_on_select_or_cancel(self):
        self.open()
        before = self.mission_snapshot()
        self.choose()
        expect(self.page.locator('#chart-result')).to_contain_text('ILS Y RWY 16L')
        expect(self.page.locator('#chart-result')).to_contain_text('Rascunho não validado')
        expect(self.page.locator('#chart-result')).to_contain_text('Vigência não verificada')
        self.assertEqual(self.mission_snapshot(), before)
        self.assertGreater(self.page.locator('#chart-original').evaluate('c=>c.width'), 100)
        self.assertEqual(self.records()[0]['review'], {'validated': False})
        self.page.get_by_role('button', name='Fechar importação').click()
        self.assertEqual(self.mission_snapshot(), before)
        self.assertEqual(self.errors, [])

    def test_existing_missions_manual_geometry_and_catalog_survive_import_reload(self):
        self.open()
        self.page.get_by_role('button', name='Fechar importação').click()
        self.page.evaluate("""()=>{
          const key='ivplanner-procedure-editor-procedimentos-v1',doc=JSON.parse(localStorage.getItem(key));
          doc.title='DESENHO MANUAL';doc.mission.name='MISSÃO ANTERIOR';
          doc.points=[{id:'official',name:'FIXO MANUAL',x:1.234567891,y:2.987654321,locked:false}];
          localStorage.setItem(key,JSON.stringify(doc));
          localStorage.setItem('ivplanner-procedure-missions-procedimentos-v1',JSON.stringify([{id:'prior',document:{...doc,version:1}}]));
          localStorage.setItem('ivplanner-procedure-missions-ndb-v1',JSON.stringify([{id:'prior-ndb',document:{...doc,module:'ndb'}}]));
          localStorage.setItem('ivplanner-procedure-editor-ndb-v1',JSON.stringify({...doc,module:'ndb'}));
          localStorage.setItem('ivplanner-custom-procedures-v1',JSON.stringify([{id:'catalog',module:'procedimentos',document:doc}]));
        }""")
        self.open();before = self.mission_snapshot()
        self.choose(CASES[7]['file'])
        self.page.get_by_role('button', name='Fechar importação').click()
        self.assertEqual(self.mission_snapshot(), before)
        self.page.reload()
        self.assertEqual(self.mission_snapshot(), before)
        self.assertEqual(self.errors, [])

    def test_resume_interrupted_import_before_any_page_was_extracted(self):
        self.open()
        pdf = fitz.open()
        for text in ['SBNT_IAC_00J\nIAC ILS Y RWY 16L', 'SBRJ_SID_02O\nSID EVSOB 1D RWY 20L']:
            pdf.new_page().insert_text((40,40),text)
        self.page.locator('#chart-file').set_input_files({'name':'interrupted.pdf','mimeType':'application/pdf','buffer':pdf.tobytes()})
        expect(self.page.locator('#chart-status')).to_contain_text('Selecione a página')
        self.page.locator('#chart-page').select_option('2')
        expect(self.page.locator('#chart-status')).to_contain_text('Página selecionada e salva')
        record = self.records()[0]
        self.assertIsNone(record['extraction'])
        self.assertEqual(record['page'],2)
        self.page.reload();self.dismiss_database_prompt();self.page.locator('[data-page=drawing]').click();self.page.locator('#import-chart').click()
        expect(self.page.locator('#chart-library option')).to_have_count(2)
        self.page.locator('#chart-library').select_option(record['id']);self.page.get_by_role('button', name='Retomar', exact=True).click()
        expect(self.page.locator('#chart-result')).to_contain_text('EVSOB 1D RWY 20L')
        expect(self.page.locator('#chart-status')).to_contain_text('Rascunho salvo')
        self.assertEqual(self.records()[0]['id'],record['id'])

    def test_close_during_file_verification_cannot_reopen_stale_import(self):
        self.open()
        self.page.evaluate("""()=>{const digest=crypto.subtle.digest.bind(crypto.subtle);crypto.subtle.digest=async(...args)=>{await new Promise(resolve=>setTimeout(resolve,500));return digest(...args);};}""")
        self.page.locator('#chart-file').set_input_files(CHARTS / CASES[1]['file'])
        self.page.get_by_role('button', name='Fechar importação').click()
        self.page.wait_for_timeout(1000)
        self.page.locator('#import-chart').click()
        expect(self.page.locator('#chart-result')).to_be_hidden()
        expect(self.page.locator('#chart-page').locator('..').locator('..')).to_be_hidden()
        self.assertEqual(self.records(),[])
        self.assertEqual(self.errors,[])

    def test_png_and_jpeg_are_real_images_without_fabricated_ocr(self):
        self.open('ndb')
        before = self.mission_snapshot()
        for fmt, suffix, extended in [('PNG', 'png', False), ('JPEG', 'jpg', False), ('JPEG', 'jpeg', True)]:
            buffer = io.BytesIO();Image.new('RGB', (640, 900), 'white').save(buffer, format=fmt)
            data = buffer.getvalue()
            if extended:
                data = data[:2] + b'\xff\xe1\xff\xff' + b'\x00' * 65533 + data[2:]
            self.page.locator('#chart-file').set_input_files({'name': 'sbbq_ndb-rwy-18.' + suffix, 'mimeType': 'image/' + suffix, 'buffer': data})
            expect(self.page.locator('#chart-result')).to_be_visible()
            expect(self.page.locator('#chart-status')).to_contain_text('Rascunho salvo')
            self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy') === 'false'")
            record = self.records('ndb')[0]
            self.assertEqual(record['recognition']['metadata'], {})
            self.assertIn('visual-required', [issue['id'] for issue in record['recognition']['issues']])
            self.assertEqual(record['extraction']['method'], 'image-decode')
        self.assertEqual(self.mission_snapshot(), before)
        self.assertEqual(self.errors, [])

    def test_invalid_misnamed_corrupt_and_password_files_preserve_draft(self):
        self.open();self.choose()
        original = self.records()[0]['id'];before = self.mission_snapshot()
        payloads = [('bad.pdf', b'not a PDF'), ('bad.jpg', (CHARTS / CASES[1]['file']).read_bytes()), ('broken.pdf', b'%PDF-1.7\ninvalid')]
        pdf = fitz.open();pdf.new_page().insert_text((40, 40), 'SECRET')
        payloads.append(('locked.pdf', pdf.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw='owner', user_pw='user')))
        for name, data in payloads:
            with self.subTest(file=name):
                self.page.locator('#chart-file').set_input_files({'name': name, 'mimeType': 'application/pdf', 'buffer': data})
                expect(self.page.locator('#chart-status')).to_have_class('ci-error', timeout=15000)
                self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy') === 'false'")
                self.assertEqual([r['id'] for r in self.records()], [original])
                self.assertEqual(self.mission_snapshot(), before)
        self.assertEqual(self.errors, [])

    def test_multipage_selection_extracts_only_selected_page_and_resumes(self):
        self.open()
        pdf = fitz.open()
        for text in ['SBNT_IAC_00J\nIAC ILS Y RWY 16L', 'SBRJ_SID_02O\nSID EVSOB 1D RWY 20L']:
            pdf.new_page().insert_text((40, 40), text)
        self.page.locator('#chart-file').set_input_files({'name': 'two-pages.pdf', 'mimeType': 'application/pdf', 'buffer': pdf.tobytes()})
        expect(self.page.locator('#chart-page option')).to_have_count(2)
        self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy') === 'false'")
        expect(self.page.locator('#chart-result')).to_be_hidden()
        self.assertIsNone(self.records()[0]['extraction'])
        self.page.locator('#chart-page').select_option('2')
        self.page.get_by_role('button', name='Extrair página').click()
        expect(self.page.locator('#chart-result')).to_contain_text('EVSOB 1D RWY 20L')
        expect(self.page.locator('#chart-status')).to_contain_text('Rascunho salvo')
        self.assertEqual(self.records()[0]['page'], 2)
        self.page.reload();self.dismiss_database_prompt();self.page.locator('[data-page=drawing]').click();self.page.locator('#import-chart').click()
        expect(self.page.locator('#chart-library option')).to_have_count(2)
        self.page.locator('#chart-library').select_option(index=1)
        self.page.get_by_role('button', name='Retomar', exact=True).click()
        expect(self.page.locator('#chart-result')).to_contain_text('EVSOB 1D RWY 20L')
        self.assertEqual(self.errors, [])

    def test_drafts_and_library_are_isolated_between_modules(self):
        self.open('ndb');self.choose(CASES[3]['file']);ndb_id = self.records('ndb')[0]['id']
        self.open('procedimentos')
        expect(self.page.locator('#chart-library option')).to_have_count(1)
        self.assertEqual(self.records(), [])
        self.choose(CASES[6]['file'])
        self.assertEqual(self.records('ndb')[0]['id'], ndb_id)
        self.assertNotEqual(self.records()[0]['id'], ndb_id)
        denied = self.page.evaluate("""async id=>{try {await (await import('./chart-import/storage.mjs')).load(id,'procedimentos');return false;}catch{return true;}}""", ndb_id)
        self.assertTrue(denied)

    def test_archive_exports_original_and_restores_only_matching_module(self):
        self.open();self.choose();record = self.records()[0]
        with self.page.expect_download() as download:
            self.page.get_by_role('button', name='Exportar rascunho', exact=True).click()
        data = Path(download.value.path()).read_bytes();archive = json.loads(data)
        self.assertEqual(archive['source']['sha256'], record['source']['sha256'])
        self.page.locator('#chart-archive').set_input_files({'name': 'backup.ivchart', 'mimeType': 'application/json', 'buffer': data})
        expect(self.page.locator('#chart-status')).to_contain_text('Rascunho salvo')
        self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy') === 'false'")
        self.assertEqual(len(self.records()), 2)
        self.open('ndb')
        self.page.locator('#chart-archive').set_input_files({'name': 'wrong-module.ivchart', 'mimeType': 'application/json', 'buffer': data})
        expect(self.page.locator('#chart-status')).to_contain_text('outro módulo')
        self.assertEqual(self.records('ndb'), [])
        archive['module'] = 'ndb';archive['source']['sha256'] = '0' * 64
        self.page.locator('#chart-archive').set_input_files({'name': 'tampered.ivchart', 'mimeType': 'application/json', 'buffer': json.dumps(archive).encode()})
        expect(self.page.locator('#chart-status')).to_contain_text('Integridade')
        self.assertEqual(self.records('ndb'), [])

    def test_offline_reopen_reload_and_pdf_worker_are_cached(self):
        self.open();self.choose()
        self.page.evaluate("async()=>{await navigator.serviceWorker.ready;}")
        self.page.wait_for_function('navigator.serviceWorker.controller !== null')
        self.context.set_offline(True)
        self.page.reload();self.dismiss_database_prompt();self.page.locator('[data-page=drawing]').click();self.page.locator('#import-chart').click()
        expect(self.page.locator('#chart-library option')).to_have_count(2)
        self.page.locator('#chart-library').select_option(index=1);self.page.get_by_role('button', name='Retomar', exact=True).click()
        expect(self.page.locator('#chart-result')).to_contain_text('ILS Y RWY 16L', timeout=25000)
        expect(self.page.locator('#chart-status')).to_contain_text('Rascunho salvo')
        self.assertEqual(self.errors, [])

    def test_storage_failure_keeps_existing_records_and_allows_export(self):
        self.open();self.choose();original = self.records()[0]['id']
        self.page.evaluate("""()=>{const original=IDBDatabase.prototype.transaction;IDBDatabase.prototype.transaction=function(names,mode,...args){const tx=original.call(this,names,mode,...args);if(this.name==='ivplanner-chart-import-v1'&&mode==='readwrite')queueMicrotask(()=>tx.abort());return tx;};}""")
        self.page.locator('#chart-file').set_input_files(CHARTS / CASES[6]['file'])
        expect(self.page.locator('#chart-result')).to_contain_text('RNP RWY 16L')
        expect(self.page.locator('#chart-status')).to_contain_text('Rascunho não salvo')
        self.assertEqual([r['id'] for r in self.records()], [original])
        expect(self.page.get_by_role('button', name='Exportar rascunho', exact=True)).to_be_enabled()
        self.page.once('dialog', lambda dialog: dialog.dismiss())
        self.page.get_by_role('button', name='Fechar importação').click()
        expect(self.page.locator('#chart-import-dialog')).to_be_visible()

    def test_ambiguity_and_incomplete_text_are_never_silently_accepted(self):
        self.open()
        result = self.page.evaluate("""async()=>{const {recognize}=await import('./chart-import/model.mjs');return recognize({text:[],lines:[{text:'SBNT_IAC_01 IAC VOR Z RWY 12',evidenceIds:['a']},{text:'SBRJ_SID_02 SID EVSOB 1D RWY 20L',evidenceIds:['b']}]});}""")
        self.assertNotIn('icao', result['metadata'])
        self.assertIn('ambiguous-icao', [i['id'] for i in result['issues']])
        self.assertTrue(all(i['critical'] for i in result['issues']))

    def test_no_destructive_rounding_of_structural_coordinates(self):
        self.open();self.choose()
        record = self.records()[0]
        self.assertTrue(any(any(abs(n-round(n, 1)) > 1e-7 for n in item['transform']) for item in record['extraction']['text']))
        original = record['extraction']['text'][0]['transform']
        stored = self.page.evaluate("""async id=>{const {load}=await import('./chart-import/storage.mjs');return (await load(id,'procedimentos')).extraction.text[0].transform;}""", record['id'])
        self.assertEqual(stored, original)

    def test_responsive_dialog_touch_layout_and_keyboard_focus(self):
        for width, height in [(390, 844), (844, 390), (768, 1024), (1024, 768)]:
            with self.subTest(viewport=(width, height)):
                self.page.set_viewport_size({'width': width, 'height': height})
                self.open();self.choose()
                bounds = self.page.locator('#chart-import-dialog').evaluate("d=>({x:d.getBoundingClientRect().x,y:d.getBoundingClientRect().y,w:d.getBoundingClientRect().width,h:d.getBoundingClientRect().height,overflow:d.scrollWidth>d.clientWidth+1})")
                self.assertGreaterEqual(bounds['x'], 0);self.assertGreaterEqual(bounds['y'], 0)
                self.assertLessEqual(bounds['x']+bounds['w'], width)
                self.assertLessEqual(bounds['y']+bounds['h'], height)
                self.assertFalse(bounds['overflow'])
                if width < 760:
                    self.page.get_by_role('button', name='Carta original', exact=True).click()
                    expect(self.page.locator('#chart-original')).to_be_visible()
                    expect(self.page.locator('.ci-summary')).to_be_hidden()
                    self.page.get_by_role('button', name='Dados identificados', exact=True).click()
                    expect(self.page.locator('.ci-summary')).to_be_visible()
                self.page.keyboard.press('Escape')
                expect(self.page.locator('#chart-import-dialog')).to_be_hidden()
                expect(self.page.locator('#import-chart')).to_be_focused()
        self.assertEqual(self.errors, [])


if __name__ == '__main__':
    unittest.main()
