"""PR 2: geometria, cadeados, sequência e dados publicados fictícios."""
import json
import math
import unittest
from urllib.parse import urlparse

from playwright.sync_api import expect
import test_e2e


class HorizontalEditorTests(unittest.TestCase):
    setUpClass = classmethod(test_e2e.PlannerTests.setUpClass.__func__)
    setUp = test_e2e.PlannerTests.setUp
    assert_loaded = test_e2e.PlannerTests.assert_loaded
    dismiss_database_prompt = test_e2e.PlannerTests.dismiss_database_prompt

    def fixture(self, timed=False, branch=False):
        points = [{'id': 'a', 'name': 'A', 'x': 0, 'y': 0},
                  {'id': 'b', 'name': 'B', 'x': 0, 'y': 10},
                  {'id': 'c', 'name': 'C', 'x': 8, 'y': 10}]
        segments = [{'id': 'ab', 'type': 'line', 'from': 'a', 'to': 'b'},
                    {'id': 'bc', 'type': 'curve', 'from': 'b', 'to': 'c', 'radius': 5, 'side': 1}]
        if branch:
            points.append({'id': 'd', 'name': 'D', 'x': 8, 'y': 0})
            segments.append({'id': 'bd', 'type': 'line', 'from': 'b', 'to': 'd'})
        return {'format': 'ivplanner-procedure-drawing', 'version': 1,
                'module': self.module, 'points': points, 'segments': segments,
                'mission': {'name': 'MISSÃO FICTÍCIA', 'flightGS': '180'},
                'restrictions': {'ab': {'phase': 'initial', 'altitude': '3000',
                                       'speed': '140', 'timeSeconds': '60',
                                       'notes': 'PUBLICADO FICTÍCIO'}} if timed else {}}

    def open_editor(self, module='procedimentos', timed=False, branch=False):
        self.module = module
        self.assert_loaded(self.page.goto(self.base + 'inspecao/desenhar.html?modulo=' + module))
        self.page.once('dialog', lambda dialog: dialog.accept())
        self.page.locator('#import-file').set_input_files({
            'name': 'ficticio-v1.json', 'mimeType': 'application/json',
            'buffer': json.dumps(self.fixture(timed, branch)).encode()})
        expect(self.page.locator('#toast')).to_have_text('Desenho importado.')
        self.tab('drawing')
        self.page.locator('#fit').click()

    def tab(self, name):
        self.page.locator('.section-nav [data-page=' + name + ']').click()
        expect(self.page.locator('#page-' + name)).to_be_visible()

    def draft(self):
        return self.page.evaluate('(key)=>JSON.parse(localStorage.getItem(key))',
                                  'ivplanner-procedure-editor-' + self.module + '-v1')

    def button(self, name):
        return self.page.get_by_role('button', name=name, exact=True)

    def point_position(self, ident):
        self.page.locator('#drawing').scroll_into_view_if_needed()
        return self.page.locator('g[data-point="' + ident + '"] circle').first.evaluate('''el=>{
            const r=el.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};
        }''')

    def select_point(self, ident):
        p = self.point_position(ident)
        self.tap_position(p)

    def tap_position(self, p):
        if getattr(self, 'touch_session', None):
            self.touch_session.send('Input.dispatchTouchEvent', {'type': 'touchStart',
                                    'touchPoints': [{'id': 1, 'x': p['x'], 'y': p['y']}]})
            self.touch_session.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        else:
            self.page.mouse.click(p['x'], p['y'])

    def select_segment(self, ident):
        self.page.locator('#drawing').scroll_into_view_if_needed()
        p = self.page.locator('g[data-segment="' + ident + '"] path').first.evaluate('''el=>{
            const p=el.getPointAtLength(el.getTotalLength()*.3),m=el.getScreenCTM();
            return {x:p.x*m.a+p.y*m.c+m.e,y:p.x*m.b+p.y*m.d+m.f};
        }''')
        self.tap_position(p)

    def drag_point(self, ident, dx=16, dy=12):
        p = self.point_position(ident)
        self.page.mouse.move(p['x'], p['y'])
        self.page.mouse.down()
        self.page.mouse.move(p['x'] + dx, p['y'] + dy, steps=5)
        self.page.mouse.up()

    def sequence(self, last='c', ids=('ab', 'bc')):
        self.page.locator('summary').filter(has_text='Sequência de voo').click()
        self.page.locator('#flight-start').select_option('a')
        self.page.locator('#flight-end').select_option(last)
        for ident in ids:
            self.page.locator('#flight-next').select_option(ident)
            self.button('Adicionar à sequência').click()

    def test_old_drawing_defaults_and_persistent_segment_lock(self):
        for module in ('ndb', 'procedimentos'):
            self.open_editor(module)
            initial = self.draft()
            self.assertTrue(all(not p['locked'] for p in initial['points']))
            self.assertEqual(initial['version'], 2)
            self.assertEqual(initial['flight'], {'start': '', 'end': '', 'segments': []})
            self.select_segment('ab')
            self.button('Bloquear').click()
            locked = self.draft()
            self.assertTrue(locked['segments'][0]['locked'])
            expect(self.page.locator('[data-locked-point]')).to_have_count(2)
            expect(self.page.locator('#prop-length')).to_be_disabled()
            expect(self.page.locator('#hint')).to_contain_text('Elemento bloqueado')
            expect(self.button('Excluir')).to_be_disabled()
            expect(self.button('Inserir ponto no meio')).to_be_disabled()
            expect(self.button('Desconectar fim')).to_be_disabled()
            self.tab('mission')
            self.page.locator('#mission-origin-lat').fill('-23')
            self.page.locator('#mission-origin-lon').fill('-43')
            self.button('Aplicar coordenadas e declinação').click()
            expect(self.page.locator('#toast')).to_contain_text('Referência geográfica bloqueada')
            self.assertEqual(self.draft(), locked)
            self.page.locator('#mission-origin-lat').fill('')
            self.page.locator('#mission-origin-lon').fill('')
            self.tab('drawing')
            self.drag_point('b')
            self.assertEqual(self.draft(), locked)
            self.assert_loaded(self.page.reload())
            self.tab('drawing')
            self.select_segment('ab')
            self.button('Desbloquear').click()
            self.drag_point('b')
            self.assertNotEqual(self.draft()['points'], locked['points'])
        self.assertEqual(self.errors, [])

    def test_multiple_touch_selection_bulk_lock_and_navigation(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.open_editor()
        self.page.locator('[data-tool=curve]').click()
        self.page.locator('#multi-select').click()
        expect(self.page.locator('[data-tool=select]')).to_have_attribute('aria-pressed', 'true')
        expect(self.page.locator('#hint')).to_contain_text('Seleção múltipla')
        self.touch_session = self.context.new_cdp_session(self.page)
        self.touch_session.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
        self.select_point('b')
        self.select_segment('bc')
        expect(self.page.locator('#selection-title')).to_have_text('2 elementos selecionados')
        self.button('Bloquear selecionados').click()
        locked = self.draft()
        self.assertTrue(locked['points'][1]['locked'])
        self.assertTrue(locked['segments'][1]['locked'])
        self.drag_point('b')
        self.assertEqual(self.draft(), locked)
        expect(self.page.locator('#selection-title')).to_have_text('2 elementos selecionados')
        self.button('Desbloquear selecionados').click()
        self.assertTrue(all(not p['locked'] for p in self.draft()['points']))
        self.assertTrue(all(not e['locked'] for e in self.draft()['segments']))
        self.touch_session.detach()
        self.assertEqual(self.errors, [])

    def test_split_straight_preserves_path_and_undo_redo(self):
        self.open_editor()
        self.sequence()
        self.select_segment('ab')
        before = self.draft()
        self.button('Inserir ponto no meio').click()
        divided = self.draft()
        middle = divided['points'][-1]
        first, second, curve = divided['segments']
        self.assertEqual((middle['x'], middle['y']), (0, 5))
        self.assertEqual((first['from'], first['to'], second['from'], second['to']),
                         ('a', middle['id'], middle['id'], 'b'))
        self.assertEqual(first['id'], 'ab')
        self.assertEqual(divided['flight']['segments'], ['ab', second['id'], 'bc'])
        self.assertEqual(curve, before['segments'][1])
        self.page.locator('#undo').click()
        self.assertEqual(self.draft(), before)
        self.page.locator('#redo').click()
        self.assertEqual(self.draft(), divided)
        self.assert_loaded(self.page.reload())
        self.assertEqual(self.draft(), divided)
        self.assertEqual(self.errors, [])

    def test_split_curve_retains_circle_and_direction(self):
        self.open_editor()
        self.select_segment('bc')
        self.button('Inserir ponto no meio').click()
        divided = self.draft()
        p = divided['points'][-1]
        self.assertAlmostEqual(p['x'], 4, places=6)
        self.assertAlmostEqual(p['y'], 12, places=6)
        self.assertAlmostEqual(math.hypot(p['x'] - 4, p['y'] - 7), 5)
        halves = divided['segments'][1:]
        self.assertEqual([e['radius'] for e in halves], [5, 5])
        self.assertEqual([e['side'] for e in halves], [1, 1])
        self.assertEqual((halves[0]['from'], halves[0]['to'], halves[1]['from'], halves[1]['to']),
                         ('b', p['id'], p['id'], 'c'))
        expect(self.page.locator('[data-flight-arrow]')).to_have_count(3)
        self.assertEqual(self.errors, [])

    def test_reversal_keeps_arc_geometry_and_requires_explicit_branch(self):
        self.open_editor(branch=True)
        self.select_segment('bc')
        before = self.draft()
        self.button('Inverter sentido de voo').click()
        curve = self.draft()['segments'][1]
        self.assertEqual((curve['from'], curve['to'], curve['side'], curve['radius']), ('c', 'b', -1, 5))
        self.assertEqual(self.draft()['points'], before['points'])
        self.button('Inverter sentido de voo').click()
        self.sequence()
        self.assertEqual(self.draft()['flight']['segments'], ['ab', 'bc'])
        self.assertNotIn('bd', self.draft()['flight']['segments'])
        self.select_segment('bc')
        self.button('Inverter sentido de voo').click()
        expect(self.page.locator('#toast')).to_contain_text('Reordene a sequência')
        self.page.once('dialog', lambda dialog: dialog.accept())
        self.button('Reordenar a partir de 2').click()
        self.page.locator('#flight-end').select_option('d')
        self.page.locator('#flight-next').select_option('bd')
        self.button('Adicionar à sequência').click()
        self.assertEqual(self.draft()['flight'], {'start': 'a', 'end': 'd', 'segments': ['ab', 'bd']})
        self.assertEqual(self.errors, [])

    def test_published_values_preserved_and_gated_until_review(self):
        self.open_editor('ndb', timed=True)
        self.select_segment('ab')
        original = self.draft()
        self.page.once('dialog', lambda dialog: dialog.accept())
        self.button('Inserir ponto no meio').click()
        divided = self.draft()
        ids = [e['id'] for e in divided['segments'][:2]]
        source = next(iter(divided['splitSources'].values()))
        self.assertEqual(source['segment'], original['segments'][0])
        self.assertEqual(source['restriction'], original['restrictions']['ab'])
        for ident in ids:
            self.assertTrue(divided['restrictions'][ident]['reviewRequired'])
            self.assertEqual(divided['restrictions'][ident]['timeSeconds'], '60')
        self.tab('inspection')
        self.button('Aplicar pernas ao desenho').click()
        expect(self.page.locator('#toast')).to_contain_text('Revise as restrições')
        self.assertEqual(self.draft(), divided)
        self.tab('restrictions')
        for ident in ids:
            card = self.page.locator('[data-restriction="' + ident + '"]')
            card.locator('summary').first.click()
            card.locator('#restriction-' + ident + '-timeSeconds').fill('30')
            card.locator('summary').first.click()
            card.locator('summary').first.click()
            self.page.once('dialog', lambda dialog: dialog.accept())
            card.get_by_role('button', name='Confirmar revisão', exact=True).click()
        self.assertTrue(all(not self.draft()['restrictions'][ident].get('reviewRequired') for ident in ids))
        self.assertEqual(next(iter(self.draft()['splitSources'].values()))['restriction'], original['restrictions']['ab'])
        self.tab('inspection')
        self.page.once('dialog', lambda dialog: dialog.accept())
        self.button('Aplicar pernas ao desenho').click()
        expect(self.page.locator('#toast')).to_contain_text('Pernas aplicadas')
        self.assertEqual(self.errors, [])

    def test_timed_application_cannot_move_locked_shared_point(self):
        self.open_editor('ndb', timed=True)
        self.select_segment('bc')
        self.button('Bloquear').click()
        before = self.draft()
        self.select_segment('ab')
        self.page.locator('#prop-length').fill('4')
        self.button('Aplicar medidas').click()
        expect(self.page.locator('#toast')).to_contain_text('conflita')
        self.assertEqual(self.draft(), before)
        self.tab('inspection')
        self.button('Aplicar pernas ao desenho').click()
        expect(self.page.locator('#toast')).to_contain_text('bloqueado')
        self.assertEqual(self.draft(), before)
        self.assertEqual(self.errors, [])

    def test_invalid_additive_fields_preserve_existing_document(self):
        self.open_editor()
        previous = self.draft()
        cases = []
        wrong_lock = self.fixture()
        wrong_lock['points'][0]['locked'] = 'false'
        cases.append(wrong_lock)
        disconnected = self.fixture()
        disconnected['flight'] = {'start': 'a', 'end': 'c', 'segments': ['bc', 'ab']}
        cases.append(disconnected)
        missing_source = self.fixture()
        missing_source['segments'][0]['splitSource'] = 'fonte-inexistente'
        cases.append(missing_source)
        for index, data in enumerate(cases):
            with self.subTest(case=index):
                self.page.locator('#import-file').set_input_files({
                    'name': 'invalido.json', 'mimeType': 'application/json',
                    'buffer': json.dumps(data).encode()})
                expect(self.page.locator('#toast')).to_be_visible()
                self.assertEqual(self.draft(), previous)
        self.assertEqual(self.errors, [])

    def test_backup_restore_retains_locks_sequence_sources_and_review(self):
        self.open_editor('ndb', timed=True)
        self.tab('mission')
        self.page.locator('#mission-origin-lat').fill('-23')
        self.page.locator('#mission-origin-lon').fill('-43')
        self.button('Aplicar coordenadas e declinação').click()
        self.tab('drawing')
        self.sequence()
        self.select_segment('ab')
        self.page.once('dialog', lambda dialog: dialog.accept())
        self.button('Inserir ponto no meio').click()
        self.select_segment('bc')
        self.button('Bloquear').click()
        expected = self.draft()
        self.assertEqual(next(iter(expected['splitSources'].values()))['origin'],
                         {'lat': -23, 'lon': -43, 'mag': 0, 'dir': 'W'})
        self.tab('mission')
        self.button('Salvar missão').click()
        saved = self.draft()
        self.assert_loaded(self.page.goto(self.base + 'configuracoes/index.html'))
        self.dismiss_database_prompt()
        with self.page.expect_download() as download:
            self.page.locator('#backup-export').click()
        with open(download.value.path(), encoding='utf-8') as file:
            backup = json.load(file)
        key = 'ivplanner-procedure-editor-ndb-v1'
        self.assertEqual(backup['data'][key], saved)
        # A historical v1 mission can coexist with v2 documents in the same backup.
        historical = self.fixture()
        historical['mission']['name'] = 'MISSÃO ANTIGA V1'
        historical['missionId'] = 'historical-v1'
        library_key = 'ivplanner-procedure-missions-ndb-v1'
        backup['data'][library_key].append({'id': 'historical-v1', 'document': historical})
        with self.browser.new_context(service_workers='allow') as context:
            context.route('**/*', lambda route: route.continue_()
                          if urlparse(route.request.url).netloc == urlparse(self.base).netloc
                          else route.abort())
            page = context.new_page()
            page.on('dialog', lambda dialog: dialog.accept())
            page.goto(self.base + 'configuracoes/index.html')
            if page.locator('#db-update-overlay').is_visible():
                page.locator('#db-update-no').click()
            page.locator('#backup-file').set_input_files({'name': 'backup.json', 'mimeType': 'application/json',
                                                        'buffer': json.dumps(backup).encode()})
            expect(page.locator('#backup-preview')).to_be_visible()
            page.locator('#backup-apply').click()
            expect(page.locator('#backup-status')).to_contain_text('Importação concluída')
            page.goto(self.base + 'inspecao/desenhar.html?modulo=ndb')
            restored = page.evaluate('(key)=>JSON.parse(localStorage.getItem(key))', key)
            self.assertEqual(restored, saved)
            self.assertEqual(restored['splitSources'], expected['splitSources'])
            self.assertEqual(restored['flight'], expected['flight'])
            page.locator('#saved-mission').select_option('historical-v1')
            page.get_by_role('button', name='Reabrir', exact=True).click()
            expect(page.locator('#mission-name')).to_have_value('MISSÃO ANTIGA V1')
            migrated = page.evaluate('(key)=>JSON.parse(localStorage.getItem(key))', key)
            self.assertEqual(migrated['version'], 2)
            self.assertEqual([(p['id'], p['x'], p['y']) for p in migrated['points']],
                             [(p['id'], p['x'], p['y']) for p in historical['points']])
        self.assertEqual(self.errors, [])

    def test_two_finger_gesture_on_locked_geometry_keeps_document(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.open_editor()
        self.select_segment('ab')
        self.button('Bloquear').click()
        before = self.draft()
        self.page.locator('#drawing').scroll_into_view_if_needed()
        box = self.page.locator('#drawing').bounding_box()
        session = self.context.new_cdp_session(self.page)
        session.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
        north = self.page.locator('#north-arrow').get_attribute('style')
        for event, points in [('touchStart', [(100, 150), (230, 150)]),
                              ('touchMove', [(90, 130), (245, 180)])]:
            session.send('Input.dispatchTouchEvent', {'type': event, 'touchPoints':
                         [{'id': i+1, 'x': box['x']+x, 'y': box['y']+y} for i, (x, y) in enumerate(points)]})
        session.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        self.page.wait_for_timeout(100)
        self.assertNotEqual(self.page.locator('#north-arrow').get_attribute('style'), north)
        self.assertEqual(self.draft(), before)
        session.detach()
        self.assertEqual(self.errors, [])
