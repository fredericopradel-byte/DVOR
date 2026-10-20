"""PR 3: modelos ilustrativos e transformações, sem regras aeronáuticas."""
import json
import math
import unittest
from urllib.parse import urlparse

from playwright.sync_api import expect
import test_horizontal_editor as horizontal


class ProcedureModelTests(unittest.TestCase):
    setUpClass = classmethod(horizontal.HorizontalEditorTests.setUpClass.__func__)
    setUp = horizontal.HorizontalEditorTests.setUp
    assert_loaded = horizontal.HorizontalEditorTests.assert_loaded
    dismiss_database_prompt = horizontal.HorizontalEditorTests.dismiss_database_prompt
    fixture = horizontal.HorizontalEditorTests.fixture
    open_editor = horizontal.HorizontalEditorTests.open_editor
    tab = horizontal.HorizontalEditorTests.tab
    draft = horizontal.HorizontalEditorTests.draft
    button = horizontal.HorizontalEditorTests.button
    select_segment = horizontal.HorizontalEditorTests.select_segment
    select_point = horizontal.HorizontalEditorTests.select_point
    point_position = horizontal.HorizontalEditorTests.point_position
    tap_position = horizontal.HorizontalEditorTests.tap_position
    drag_point = horizontal.HorizontalEditorTests.drag_point
    sequence = horizontal.HorizontalEditorTests.sequence

    def details(self, text):
        if self.page.locator('#editor-options').is_hidden() or self.page.locator('#inspector-panel').is_hidden():
            self.page.locator('#editor-more').click()
        summary = self.page.locator('summary').filter(has_text=text)
        if not summary.evaluate('el=>el.parentElement.open'):
            summary.click()

    def model(self, name, accept=True):
        self.details('Modelos iniciais editáveis')
        self.page.locator('#drawing-model').select_option(name)
        self.page.once('dialog', lambda d: d.accept() if accept else d.dismiss())
        self.page.locator('#apply-model').click()

    def rotation(self, value, center='a', reference='magnetic', accept=True):
        self.details('Ancoragem e rotação geométrica')
        self.page.locator('#rotation-leg').select_option('ab')
        self.page.locator('#rotation-center').select_option(center)
        self.page.locator('#rotation-azimuth').fill(str(value))
        self.page.locator('#rotation-reference').select_option(reference)
        if accept is not None:
            self.page.once('dialog', lambda d: d.accept() if accept else d.dismiss())
        self.page.locator('#apply-rotation').click()

    def origin(self, lat='-23', lon='-43', mag='10', direction='W'):
        self.details('Procedimento e referência')
        self.page.locator('#origin-lat').fill(lat)
        self.page.locator('#origin-lon').fill(lon)
        self.page.locator('#mag-value').fill(mag)
        self.page.locator('#mag-dir').select_option(direction)
        self.page.locator('#apply-reference').click()

    def assert_rigid(self, before, after):
        self.assertEqual([p['id'] for p in before['points']], [p['id'] for p in after['points']])
        self.assertEqual(before['segments'], after['segments'])
        self.assertEqual(before['restrictions'], after['restrictions'])
        self.assertEqual(before['flight'], after['flight'])
        for a, b in zip(before['points'], after['points']):
            for c, d in zip(before['points'], after['points']):
                self.assertAlmostEqual(math.hypot(a['x']-c['x'], a['y']-c['y']),
                                       math.hypot(b['x']-d['x'], b['y']-d['y']), places=9)

    def test_templates_confirm_recover_preserve_mission_and_are_editable(self):
        for module in ('ndb', 'procedimentos'):
            self.open_editor(module, timed=True)
            self.origin()
            original = self.draft()
            self.model('rnp', accept=False)
            self.assertEqual(original, self.draft())
            self.model('rnp')
            template = self.draft()
            self.assertEqual(template['mission'], original['mission'])
            self.assertEqual(template['origin'], original['origin'])
            self.assertEqual(template['restrictions'], {})
            self.assertEqual(template['flight'], {'start': '', 'end': '', 'segments': []})
            self.assertEqual((len(template['points']), len(template['segments'])), (6, 5))
            incoming = {}
            for e in template['segments']:
                incoming[e['to']] = incoming.get(e['to'], 0) + 1
            self.assertEqual(max(incoming.values()), 3)
            self.assertTrue(all(not e['locked'] for e in template['segments']))
            self.drag_point(template['points'][0]['id'])
            self.assertNotEqual(template['points'], self.draft()['points'])
            self.model('conventional')
            conventional = self.draft()
            self.assertEqual((len(conventional['points']), len(conventional['segments'])), (7, 6))
            self.assertEqual([e['type'] for e in conventional['segments']].count('curve'), 1)
            for prev, nxt in zip(conventional['segments'], conventional['segments'][1:]):
                self.assertEqual(prev['to'], nxt['from'])
            self.model('blank')
            self.assertEqual(self.draft()['points'], [])
            self.assertEqual(self.draft()['mission'], original['mission'])
            self.tab('mission')
            recoveries = self.page.evaluate('(k)=>JSON.parse(localStorage.getItem(k))',
                                           'ivplanner-procedure-missions-' + module + '-v1')
            record = next(r for r in recoveries if r.get('recovery') and r['document'] == original)
            self.page.locator('#saved-mission').select_option(record['id'])
            self.page.once('dialog', lambda d: d.accept())
            self.button('Reabrir').click()
            self.assertEqual(self.draft()['points'], original['points'])
            self.assertEqual(self.draft()['restrictions'], original['restrictions'])
        self.assertEqual(self.errors, [])

    def test_template_preservation_failure_and_other_module_are_safe(self):
        self.open_editor('ndb')
        ndb = self.draft()
        self.open_editor('procedimentos', timed=True)
        original = self.draft()
        self.page.evaluate('''()=>{const original=Storage.prototype.setItem;
            Storage.prototype.setItem=function(key,value){
                if(key==='ivplanner-procedure-missions-procedimentos-v1')throw new Error('Fictitious quota');
                return original.call(this,key,value);
            };}''')
        self.model('rnp')
        expect(self.page.locator('#toast')).to_contain_text('Não foi possível preservar')
        self.assertEqual(self.draft(), original)
        self.assertEqual(self.page.evaluate('()=>JSON.parse(localStorage.getItem("ivplanner-procedure-editor-ndb-v1"))'), ndb)
        self.assertEqual(self.errors, [])

    def test_rotation_absolute_center_rigidity_cancel_undo_and_reload(self):
        self.open_editor(timed=True)
        self.origin()
        self.sequence()
        original = self.draft()
        self.rotation(90, center='b', accept=False)
        self.assertEqual(self.draft(), original)
        self.rotation(90, center='b')
        rotated = self.draft()
        self.assert_rigid(original, rotated)
        self.assertEqual(rotated['points'][1], original['points'][1])
        self.assertAlmostEqual(rotated['points'][0]['x'], -10)
        self.assertAlmostEqual(rotated['points'][0]['y'], 10)
        self.assertEqual(rotated['origin'], original['origin'])
        self.rotation(90, center='b', accept=None)
        expect(self.page.locator('#toast')).to_contain_text('já está no azimute')
        self.assertEqual(self.draft(), rotated)
        self.page.locator('#undo').click()
        self.assertEqual(self.draft(), original)
        self.page.locator('#redo').click()
        self.assertEqual(self.draft(), rotated)
        self.assert_loaded(self.page.reload())
        self.assertEqual(self.draft(), rotated)
        self.assertEqual(self.errors, [])

    def test_true_rotation_manual_declination_east_west_and_limits(self):
        self.open_editor()
        self.origin()
        original = self.draft()
        self.rotation(90, reference='true', accept=None)
        expect(self.page.locator('#toast')).to_contain_text('Confira a declinação')
        self.assertEqual(self.draft(), original)
        self.page.locator('#rotation-declination-confirmed').check()
        self.rotation(90, reference='true')
        p = self.draft()['points'][1]
        self.assertAlmostEqual((math.degrees(math.atan2(p['x'], p['y']))+360)%360, 100)
        self.origin(direction='E')
        expect(self.page.locator('#rotation-declination-confirmed')).not_to_be_checked()
        self.page.locator('#rotation-declination-confirmed').check()
        self.rotation(360, reference='true')
        p = self.draft()['points'][1]
        self.assertAlmostEqual((math.degrees(math.atan2(p['x'], p['y']))+360)%360, 350)
        before = self.draft()
        for value in ('', '-1', '361'):
            self.rotation(value, accept=None)
            expect(self.page.locator('#toast')).to_contain_text('Informe um azimute')
            self.assertEqual(self.draft(), before)
        self.assertEqual(self.errors, [])

    def test_anchor_exact_point_rigidity_confirmation_and_persistence(self):
        self.open_editor(timed=True)
        self.sequence()
        original = self.draft()
        self.details('Ancoragem e rotação geométrica')
        self.page.locator('#anchor-point').select_option('b')
        self.page.locator('#anchor-lat').fill('-22.123456')
        self.page.locator('#anchor-lon').fill('179.9')
        self.page.once('dialog', lambda d: d.dismiss())
        self.page.locator('#apply-anchor').click()
        self.assertEqual(self.draft(), original)
        self.page.once('dialog', lambda d: d.accept())
        self.page.locator('#apply-anchor').click()
        anchored = self.draft()
        self.assert_rigid(original, anchored)
        self.assertEqual((anchored['points'][1]['x'], anchored['points'][1]['y']), (0, 0))
        self.assertEqual(anchored['origin'], {'lat': -22.123456, 'lon': 179.9, 'mag': 0, 'dir': 'W'})
        self.select_point('b')
        expect(self.page.locator('#prop-lat')).to_have_value('-22.123456')
        expect(self.page.locator('#prop-lon')).to_have_value('179.900000')
        self.page.locator('#undo').click()
        self.assertEqual(self.draft(), original)
        self.page.locator('#redo').click()
        self.assertEqual(self.draft(), anchored)
        self.assert_loaded(self.page.reload())
        self.assertEqual(self.draft(), anchored)
        self.assertEqual(self.errors, [])

    def test_locks_measurement_constraints_pending_reference_and_invalid_anchor(self):
        self.open_editor()
        self.select_segment('bc')
        self.button('Bloquear').click()
        original = self.draft()
        self.rotation(90, accept=None)
        expect(self.page.locator('#toast')).to_contain_text('bloqueado')
        self.page.locator('#anchor-point').select_option('b')
        self.page.locator('#anchor-lat').fill('-23')
        self.page.locator('#anchor-lon').fill('-43')
        self.page.locator('#apply-anchor').click()
        expect(self.page.locator('#toast')).to_contain_text('bloqueada')
        self.assertEqual(self.draft(), original)
        self.button('Desbloquear').click()
        self.select_segment('ab')
        self.page.get_by_label('Travar rumo', exact=True).check()
        self.button('Aplicar medidas').click()
        locked_bearing = self.draft()
        self.rotation(90, accept=None)
        expect(self.page.locator('#toast')).to_contain_text('travas de azimute')
        self.assertEqual(self.draft(), locked_bearing)
        self.page.locator('#close-inspector').click()
        self.page.locator('#selection-peek').click()
        self.page.get_by_label('Travar rumo', exact=True).uncheck()
        self.button('Aplicar medidas').click()
        original = self.draft()
        self.details('Ancoragem e rotação geométrica')
        for lat, lon in (('', '0'), ('89', '0'), ('-89', '0'), ('0', '181')):
            self.page.locator('#anchor-lat').fill(lat)
            self.page.locator('#anchor-lon').fill(lon)
            self.page.locator('#apply-anchor').click()
            expect(self.page.locator('#toast')).to_contain_text('coordenadas válidas')
            self.assertEqual(self.draft(), original)
        self.details('Procedimento e referência')
        self.page.locator('#mag-value').fill('12')
        self.rotation(90, accept=None)
        expect(self.page.locator('#toast')).to_contain_text('Aplique a referência')
        self.assertEqual(self.draft(), original)
        self.assertEqual(self.errors, [])

    def test_models_transforms_backup_and_restore_in_new_context(self):
        self.open_editor('ndb', timed=True)
        self.select_segment('ab')
        self.page.once('dialog', lambda d: d.accept())
        self.button('Inserir ponto no meio').click()
        sources = self.draft()['splitSources']
        self.model('conventional')
        model = self.draft()
        self.details('Ancoragem e rotação geométrica')
        self.page.locator('#anchor-point').select_option(model['points'][1]['id'])
        self.page.locator('#anchor-lat').fill('-23')
        self.page.locator('#anchor-lon').fill('-43')
        self.page.once('dialog', lambda d: d.accept())
        self.page.locator('#apply-anchor').click()
        self.page.locator('#rotation-leg').select_option(model['segments'][1]['id'])
        self.page.locator('#rotation-azimuth').fill('240')
        self.page.once('dialog', lambda d: d.accept())
        self.page.locator('#apply-rotation').click()
        expected = self.draft()
        self.assertEqual(expected['splitSources'], sources)
        self.assert_loaded(self.page.goto(self.base + 'configuracoes/index.html'))
        self.dismiss_database_prompt()
        with self.page.expect_download() as download:
            self.page.locator('#backup-export').click()
        with open(download.value.path(), encoding='utf-8') as file:
            backup = json.load(file)
        with self.browser.new_context(service_workers='allow') as context:
            context.route('**/*', lambda route: route.continue_()
                          if urlparse(route.request.url).netloc == urlparse(self.base).netloc else route.abort())
            page = context.new_page()
            page.on('dialog', lambda d: d.accept())
            page.goto(self.base + 'configuracoes/index.html')
            if page.locator('#db-update-overlay').is_visible():
                page.locator('#db-update-no').click()
            page.locator('#backup-file').set_input_files({'name': 'backup.json', 'mimeType': 'application/json',
                                                        'buffer': json.dumps(backup).encode()})
            expect(page.locator('#backup-preview')).to_be_visible()
            page.locator('#backup-apply').click()
            expect(page.locator('#backup-status')).to_contain_text('Importação concluída')
            page.goto(self.base + 'inspecao/desenhar.html?modulo=ndb')
            restored = page.evaluate('()=>JSON.parse(localStorage.getItem("ivplanner-procedure-editor-ndb-v1"))')
            self.assertEqual(restored, expected)
        self.assertEqual(self.errors, [])

    def test_models_and_transforms_offline_viewports(self):
        self.open_editor()
        self.page.evaluate('''async()=>{await navigator.serviceWorker.ready;
            if(!navigator.serviceWorker.controller)await new Promise(r=>navigator.serviceWorker.addEventListener('controllerchange',r,{once:true}));}''')
        self.context.set_offline(True)
        for width, height in ((390, 844), (844, 390), (820, 1180), (1180, 820)):
            self.page.set_viewport_size({'width': width, 'height': height})
            self.model('rnp')
            model = self.draft()
            self.details('Ancoragem e rotação geométrica')
            self.page.locator('#rotation-leg').select_option(model['segments'][3]['id'])
            self.page.locator('#rotation-azimuth').fill('60')
            self.page.once('dialog', lambda d: d.accept())
            self.page.locator('#apply-rotation').click()
            self.assert_rigid(model, self.draft())
            for ident in ('drawing-model', 'apply-model', 'anchor-point', 'rotation-azimuth', 'apply-rotation'):
                box = self.page.locator('#' + ident).bounding_box()
                self.assertGreaterEqual(box['x'], 0)
                self.assertLessEqual(box['x'] + box['width'], width + 1)
                self.assertGreaterEqual(box['height'], 44)
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width + 1)
        before = self.draft()
        self.assert_loaded(self.page.reload())
        self.assertEqual(self.draft(), before)
        self.assertEqual(self.errors, [])

    def test_touch_rotation_safe_area_keeps_locked_pivot_georeferenced(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.open_editor()
        self.origin()
        self.select_point('b')
        self.button('Bloquear').click()
        original = self.draft()
        lat = self.page.locator('#prop-lat').input_value()
        lon = self.page.locator('#prop-lon').input_value()
        self.details('Ancoragem e rotação geométrica')
        session = self.context.new_cdp_session(self.page)
        session.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
        session.send('Emulation.setSafeAreaInsetsOverride', {'insets': {'left': 44, 'right': 44, 'bottom': 34}})
        self.page.locator('#rotation-leg').select_option('ab')
        self.page.locator('#rotation-center').select_option('b')
        self.page.locator('#rotation-azimuth').fill('45')
        button = self.page.locator('#apply-rotation')
        button.scroll_into_view_if_needed()
        box = button.bounding_box()
        self.assertGreaterEqual(box['x'], 0)
        self.assertLessEqual(box['x'] + box['width'], 390)
        self.page.once('dialog', lambda d: d.accept())
        session.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [
            {'id': 1, 'x': box['x'] + box['width']/2, 'y': box['y'] + box['height']/2}]})
        session.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        expect(self.page.locator('#toast')).to_contain_text('Desenho rotacionado')
        self.assert_rigid(original, self.draft())
        self.assertEqual(self.draft()['points'][1], original['points'][1])
        self.select_point('b')
        expect(self.page.locator('#prop-lat')).to_have_value(lat)
        expect(self.page.locator('#prop-lon')).to_have_value(lon)
        session.detach()
        self.assertEqual(self.errors, [])
