"""PR 4: perfil esquemático, dados fictícios e armazenamento isolado."""
import json
import math
import unittest
from urllib.parse import urlparse

from playwright.sync_api import expect
import test_horizontal_editor as horizontal


class VerticalProfileTests(unittest.TestCase):
    setUpClass = classmethod(horizontal.HorizontalEditorTests.setUpClass.__func__)
    setUp = horizontal.HorizontalEditorTests.setUp
    assert_loaded = horizontal.HorizontalEditorTests.assert_loaded
    dismiss_database_prompt = horizontal.HorizontalEditorTests.dismiss_database_prompt
    fixture = horizontal.HorizontalEditorTests.fixture
    open_editor = horizontal.HorizontalEditorTests.open_editor
    tab = horizontal.HorizontalEditorTests.tab
    draft = horizontal.HorizontalEditorTests.draft
    button = horizontal.HorizontalEditorTests.button
    sequence = horizontal.HorizontalEditorTests.sequence
    select_segment = horizontal.HorizontalEditorTests.select_segment
    select_point = horizontal.HorizontalEditorTests.select_point
    point_position = horizontal.HorizontalEditorTests.point_position
    tap_position = horizontal.HorizontalEditorTests.tap_position

    def vertical(self):
        self.page.locator('#view-vertical').click()
        expect(self.page.locator('#vertical-view')).to_be_visible()
        expect(self.page.locator('#horizontal-view')).to_be_hidden()

    def edit(self, key='p:a', altitude='3000', qualifier='at', upper='', planned=''):
        self.page.locator('#profile-element').select_option(key)
        self.page.locator('#profile-qualifier').select_option(qualifier)
        self.page.locator('#profile-altitude').fill(altitude)
        if qualifier == 'between':
            self.page.locator('#profile-upper').fill(upper)
        if key.startswith('p:'):
            self.page.locator('#profile-planned').fill(planned)
        self.page.locator('#profile-apply').click()

    def geometry(self, doc):
        return {key: doc[key] for key in ('points', 'segments', 'flight', 'origin', 'mission', 'splitSources')}

    def test_no_sequence_no_inferred_branch_partial_sequence_and_toggle(self):
        self.open_editor(branch=True)
        original = self.draft()
        self.vertical()
        expect(self.page.locator('#profile-status')).to_contain_text('Defina o início')
        expect(self.page.locator('[data-profile-point]')).to_have_count(0)
        expect(self.page.locator('#profile-editor')).to_be_hidden()
        self.assertEqual(self.draft(), original)
        self.page.locator('#profile-sequence').click()
        expect(self.page.locator('#horizontal-view')).to_be_visible()
        self.page.locator('#flight-start').select_option('a')
        self.page.locator('#flight-end').select_option('c')
        self.page.locator('#flight-next').select_option('ab')
        self.button('Adicionar à sequência').click()
        before = self.draft()
        camera = self.page.locator('#north-arrow').get_attribute('style')
        self.vertical()
        expect(self.page.locator('#profile-status')).to_contain_text('Sequência parcial')
        self.assertEqual(self.page.locator('[data-profile-point]').evaluate_all('els=>els.map(e=>e.dataset.profilePoint)'), ['a', 'b'])
        expect(self.page.locator('[data-profile-leg="bd"]')).to_have_count(0)
        self.page.locator('#view-horizontal').click()
        self.assertEqual(self.page.locator('#north-arrow').get_attribute('style'), camera)
        self.assertEqual(self.draft(), before)
        self.assertEqual(self.errors, [])

    def test_order_curve_distance_missing_altitudes_and_no_interpolation(self):
        self.open_editor(branch=True)
        self.sequence()
        self.vertical()
        expect(self.page.locator('#profile-status')).to_contain_text('conectada')
        self.assertEqual(self.page.locator('[data-profile-point]').evaluate_all('els=>els.map(e=>e.dataset.profilePoint)'), ['a', 'b', 'c'])
        distances = self.page.locator('[data-profile-leg]').evaluate_all('els=>els.map(e=>Number(e.dataset.distance))')
        self.assertAlmostEqual(distances[0], 10)
        self.assertAlmostEqual(distances[1], 10 * math.asin(.8))
        totals = self.page.locator('[data-cumulative-distance]').evaluate_all('els=>els.map(e=>Number(e.dataset.cumulativeDistance))')
        self.assertAlmostEqual(totals[-1], 10 + 10 * math.asin(.8))
        expect(self.page.locator('[data-published-altitude]')).to_have_count(0)
        self.edit('p:a', planned='4000')
        self.edit('p:c', planned='1000')
        expect(self.page.locator('[data-planned-altitude]')).to_have_count(2)
        expect(self.page.locator('[data-planned-leg]')).to_have_count(0)
        self.edit('p:b', planned='2500')
        expect(self.page.locator('[data-planned-leg]')).to_have_count(2)
        self.edit('p:a', altitude='0', planned='4000')
        expect(self.page.locator('[data-published-altitude="0"]')).to_have_count(1)
        self.assertEqual(self.errors, [])

    def test_all_constraint_boxes_hatches_and_atomic_window_validation(self):
        self.open_editor()
        self.sequence()
        self.vertical()
        for kind in ('above', 'below', 'at', 'between'):
            self.edit(qualifier=kind, upper='4500', planned='3200')
            box = self.page.locator('[data-profile-constraint="p:a"]')
            expect(box).to_have_attribute('data-type', kind)
            expected = 2 if kind in ('at', 'between') else 1
            expect(box.locator('rect[fill="url(#profile-hatch)"]')).to_have_count(expected)
            self.assertEqual(self.draft()['restrictions']['a']['qualifier'], kind)
        original = self.draft()
        self.edit(altitude='5000', qualifier='between', upper='4000', planned='3200')
        expect(self.page.locator('#toast')).to_contain_text('altitude superior é menor')
        self.assertEqual(self.draft(), original)
        self.edit('s:ab', altitude='3500', qualifier='above')
        expect(self.page.locator('[data-profile-constraint="s:ab"]')).to_have_attribute('data-type', 'above')
        expect(self.page.locator('#profile-planned')).to_be_hidden()
        self.assertEqual(self.errors, [])

    def test_shared_restrictions_editor_and_no_new_operational_calculations(self):
        self.open_editor()
        self.sequence()
        self.tab('restrictions')
        card = self.page.locator('[data-restriction="a"]')
        card.locator('summary').click()
        self.page.locator('#restriction-a-phase').select_option('initial')
        self.page.locator('#restriction-a-altitude').fill('3000')
        self.tab('inspection')
        original = self.page.locator('#page-inspection').inner_text()
        self.tab('drawing')
        self.vertical()
        expect(self.page.locator('#profile-altitude')).to_have_value('3000')
        self.edit(planned='9000')
        self.assertEqual(self.draft()['restrictions']['a']['inspectionAltitude'], '')
        self.tab('inspection')
        self.assertEqual(self.page.locator('#page-inspection').inner_text(), original)
        self.tab('restrictions')
        card.locator('summary').click()
        expect(self.page.locator('#restriction-a-plannedAltitude')).to_have_value('9000')
        self.page.locator('#restriction-a-altitude').fill('3200')
        self.tab('drawing')
        expect(self.page.locator('#profile-altitude')).to_have_value('3200')
        self.assertEqual(self.errors, [])

    def test_geometry_locks_and_history_stay_independent_of_altitude_edit(self):
        self.open_editor(timed=True)
        self.sequence()
        self.select_segment('ab')
        self.page.once('dialog', lambda d: d.accept())
        self.button('Inserir ponto no meio').click()
        self.select_segment('ab')
        self.button('Bloquear').click()
        before = self.draft()
        self.vertical()
        self.edit(planned='2700')
        edited = self.draft()
        self.assertEqual(self.geometry(before), self.geometry(edited))
        self.page.locator('#profile-undo').click()
        self.assertEqual(self.draft(), before)
        self.page.locator('#profile-redo').click()
        self.assertEqual(self.draft(), edited)
        self.edit('s:ab', altitude='3100', qualifier='above')
        expect(self.page.locator('#profile-review')).to_contain_text('Revisão pendente')
        self.assertTrue(self.draft()['restrictions']['ab']['reviewRequired'])
        self.assertEqual(self.draft()['splitSources'], before['splitSources'])
        self.page.locator('#view-horizontal').click()
        expect(self.page.locator('[data-locked-point]')).to_have_count(2)
        self.assertEqual(self.errors, [])

    def test_pending_edits_require_confirmation_on_selection_and_navigation(self):
        self.open_editor()
        self.sequence()
        self.vertical()
        before = self.draft()
        self.page.locator('#profile-planned').fill('3500')
        self.page.locator('#view-vertical').click()
        self.tab('drawing')
        expect(self.page.locator('#profile-planned')).to_have_value('3500')
        self.page.once('dialog', lambda d: d.dismiss())
        self.page.locator('#profile-element').select_option('p:b')
        expect(self.page.locator('#profile-element')).to_have_value('p:a')
        expect(self.page.locator('#profile-planned')).to_have_value('3500')
        self.page.once('dialog', lambda d: d.dismiss())
        self.page.locator('#view-horizontal').click()
        expect(self.page.locator('#vertical-view')).to_be_visible()
        self.page.once('dialog', lambda d: d.dismiss())
        self.page.locator('.section-nav [data-page=mission]').click()
        expect(self.page.locator('#page-drawing')).to_be_visible()
        self.assertEqual(self.draft(), before)
        self.page.locator('#profile-apply').focus()
        self.page.keyboard.press('Escape')
        expect(self.page.locator('#profile-planned')).to_have_value('3500')
        self.page.once('dialog', lambda d: d.dismiss())
        self.page.keyboard.press('Control+z')
        expect(self.page.locator('#profile-planned')).to_have_value('3500')
        self.assertEqual(self.draft(), before)
        self.page.locator('#profile-apply').click()
        self.assertEqual(self.draft()['restrictions']['a']['plannedAltitude'], '3500')
        self.page.locator('#profile-planned').fill('4000')
        self.page.once('dialog', lambda d: d.accept())
        self.page.locator('#view-horizontal').click()
        self.vertical()
        expect(self.page.locator('#profile-planned')).to_have_value('3500')
        self.assertEqual(self.errors, [])

    def test_migration_v1_v2_export_import_reload_and_module_isolation(self):
        self.open_editor('ndb')
        ndb = self.draft()
        self.open_editor('procedimentos')
        previous = self.draft()
        old = self.fixture()
        old['version'] = 2
        old['flight'] = {'start': 'a', 'end': 'c', 'segments': ['ab', 'bc']}
        self.page.once('dialog', lambda d: d.accept())
        self.page.locator('#import-file').set_input_files({'name': 'v2.json', 'mimeType': 'application/json', 'buffer': json.dumps(old).encode()})
        expect(self.page.locator('#toast')).to_have_text('Desenho importado.')
        self.assertEqual(self.draft()['version'], 3)
        self.assertEqual(self.draft()['points'], previous['points'])
        self.vertical()
        self.edit(altitude='2000', qualifier='between', upper='4000', planned='3000')
        edited = self.draft()
        self.assert_loaded(self.page.reload())
        self.assertEqual(self.draft(), edited)
        self.tab('drawing')
        self.page.locator('#editor-more').click()
        self.page.locator('summary').filter(has_text='Rascunho e arquivos').click()
        with self.page.expect_download() as download:
            self.page.locator('#export').click()
        with open(download.value.path(), encoding='utf-8') as f:
            exported = json.load(f)
        self.assertEqual(exported, edited)
        self.page.once('dialog', lambda d: d.accept())
        self.page.locator('#import-file').set_input_files({'name': 'v3.json', 'mimeType': 'application/json', 'buffer': json.dumps(exported).encode()})
        expect(self.page.locator('#toast')).to_have_text('Desenho importado.')
        self.assertEqual(self.draft(), edited)
        self.assertEqual(self.page.evaluate('()=>JSON.parse(localStorage.getItem("ivplanner-procedure-editor-ndb-v1"))'), ndb)
        self.assertEqual(self.errors, [])

    def test_general_backup_restore_schema3_mission_and_historical_versions(self):
        self.open_editor('ndb', timed=True)
        self.sequence()
        self.vertical()
        self.edit(altitude='2300', qualifier='above', planned='2500')
        self.tab('mission')
        self.button('Salvar missão').click()
        expected = self.draft()
        self.assert_loaded(self.page.goto(self.base + 'configuracoes/index.html'))
        self.dismiss_database_prompt()
        with self.page.expect_download() as download:
            self.page.locator('#backup-export').click()
        with open(download.value.path(), encoding='utf-8') as f:
            backup = json.load(f)
        library = 'ivplanner-procedure-missions-ndb-v1'
        for version in (1, 2):
            old = self.fixture(); old['version'] = version
            backup['data'][library].append({'id': 'old-v' + str(version), 'document': old})
        with self.browser.new_context(service_workers='allow') as context:
            context.route('**/*', lambda route: route.continue_() if urlparse(route.request.url).netloc == urlparse(self.base).netloc else route.abort())
            page = context.new_page()
            page.on('dialog', lambda d: d.accept())
            page.goto(self.base + 'configuracoes/index.html')
            if page.locator('#db-update-overlay').is_visible(): page.locator('#db-update-no').click()
            page.locator('#backup-file').set_input_files({'name': 'backup.json', 'mimeType': 'application/json', 'buffer': json.dumps(backup).encode()})
            expect(page.locator('#backup-preview')).to_be_visible()
            page.locator('#backup-apply').click()
            expect(page.locator('#backup-status')).to_contain_text('Importação concluída')
            page.goto(self.base + 'inspecao/desenhar.html?modulo=ndb')
            restored = page.evaluate('()=>JSON.parse(localStorage.getItem("ivplanner-procedure-editor-ndb-v1"))')
            self.assertEqual(restored, expected)
            for version in (1, 2):
                page.locator('#saved-mission').select_option('old-v' + str(version))
                page.get_by_role('button', name='Reabrir', exact=True).click()
                expect(page.locator('#mission-name')).to_have_value('MISSÃO FICTÍCIA')
        self.assertEqual(self.errors, [])

    def test_invalid_planned_altitudes_preserve_document_and_raw_storage(self):
        self.open_editor()
        original = self.draft()
        for key, value in (('a', 'NaN'), ('a', '60001'), ('ab', '3000')):
            invalid = self.fixture(); invalid['version'] = 3
            invalid['restrictions'] = {key: {'plannedAltitude': value}}
            self.page.locator('#import-file').set_input_files({'name': 'invalid.json', 'mimeType': 'application/json', 'buffer': json.dumps(invalid).encode()})
            expect(self.page.locator('#toast')).to_contain_text('inválid' if key == 'a' else 'somente nos pontos')
            self.assertEqual(self.draft(), original)
        raw = json.dumps(invalid)
        self.page.evaluate('(raw)=>localStorage.setItem("ivplanner-procedure-editor-procedimentos-v1",raw)', raw)
        self.assert_loaded(self.page.reload())
        expect(self.page.locator('#storage-warning')).to_contain_text('preservado')
        self.assertEqual(self.page.evaluate('localStorage.getItem("ivplanner-procedure-editor-procedimentos-v1")'), raw)
        self.assertEqual(self.errors, [])

    def test_profile_edit_offline_and_reload(self):
        self.open_editor('ndb')
        self.sequence()
        self.page.evaluate('''async()=>{await navigator.serviceWorker.ready;
          if(!navigator.serviceWorker.controller)await new Promise(r=>navigator.serviceWorker.addEventListener('controllerchange',r,{once:true}));}''')
        self.context.set_offline(True)
        self.vertical()
        self.edit(altitude='2800', qualifier='above', planned='2900')
        expected = self.draft()
        self.assert_loaded(self.page.reload())
        self.tab('drawing')
        self.vertical()
        expect(self.page.locator('#profile-planned')).to_have_value('2900')
        self.assertEqual(self.draft(), expected)
        self.assertEqual(self.errors, [])

    def test_touch_scroll_safe_areas_viewports_and_repeated_point(self):
        self.open_editor()
        data = self.draft()
        data['segments'].append({'id': 'ca', 'type': 'line', 'from': 'c', 'to': 'a'})
        data['flight'] = {'start': 'a', 'end': 'a', 'segments': ['ab', 'bc', 'ca']}
        self.page.once('dialog', lambda d: d.accept())
        self.page.locator('#import-file').set_input_files({'name': 'loop.json', 'mimeType': 'application/json', 'buffer': json.dumps(data).encode()})
        expect(self.page.locator('#toast')).to_have_text('Desenho importado.')
        self.vertical()
        self.edit(planned='3000')
        expect(self.page.locator('[data-profile-point="a"]')).to_have_count(2)
        before = self.draft()
        session = self.context.new_cdp_session(self.page)
        session.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
        session.send('Emulation.setSafeAreaInsetsOverride', {'insets': {'left': 44, 'right': 44, 'bottom': 34}})
        for width, height in ((390, 844), (844, 390), (820, 1180), (1180, 820)):
            self.page.set_viewport_size({'width': width, 'height': height})
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width + 1)
            for ident in ('profile-element', 'profile-altitude', 'profile-planned', 'profile-apply'):
                box = self.page.locator('#' + ident).bounding_box()
                self.assertGreaterEqual(box['x'], 0)
                self.assertLessEqual(box['x'] + box['width'], width + 1)
                self.assertGreaterEqual(box['height'], 44)
        self.page.set_viewport_size({'width': 390, 'height': 844})
        scroll = self.page.locator('#vertical-profile').locator('..')
        scroll.scroll_into_view_if_needed()
        box = scroll.bounding_box()
        for event, x in (('touchStart', 280), ('touchMove', 100)):
            session.send('Input.dispatchTouchEvent', {'type': event, 'touchPoints': [{'id': 1, 'x': box['x'] + x, 'y': box['y'] + 150}]})
        session.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        self.page.wait_for_timeout(200)
        self.assertGreater(scroll.evaluate('el=>el.scrollLeft'), 0)
        self.assertEqual(self.draft(), before)
        session.detach()
        self.assertEqual(self.errors, [])
