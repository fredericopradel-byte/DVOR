"""PR 1: compact editor, tap selection and contextual locks; isolated Chromium."""
import unittest
from playwright.sync_api import expect
import test_horizontal_editor as horizontal


class ContextualEditorTests(unittest.TestCase):
    setUpClass = classmethod(horizontal.HorizontalEditorTests.setUpClass.__func__)
    setUp = horizontal.HorizontalEditorTests.setUp
    assert_loaded = horizontal.HorizontalEditorTests.assert_loaded
    dismiss_database_prompt = horizontal.HorizontalEditorTests.dismiss_database_prompt
    fixture = horizontal.HorizontalEditorTests.fixture
    open_editor = horizontal.HorizontalEditorTests.open_editor
    tab = horizontal.HorizontalEditorTests.tab
    draft = horizontal.HorizontalEditorTests.draft
    button = horizontal.HorizontalEditorTests.button
    point_position = horizontal.HorizontalEditorTests.point_position
    select_point = horizontal.HorizontalEditorTests.select_point
    select_segment = horizontal.HorizontalEditorTests.select_segment
    tap_position = horizontal.HorizontalEditorTests.tap_position

    def empty_tap(self):
        if self.page.locator('#inspector-panel').is_visible():
            self.page.locator('#close-inspector').click()
        self.page.locator('#drawing').click(position={'x': 280, 'y': 70})

    def test_single_taps_replace_selection_without_geometry_or_history(self):
        for module in ('procedimentos', 'ndb'):
            self.open_editor(module)
            original = self.draft()
            undo = self.page.locator('#undo').is_enabled()
            self.select_point('a')
            expect(self.page.locator('#selection-title')).to_have_text('A')
            self.select_segment('ab')
            expect(self.page.locator('#selection-title')).to_have_text('Trecho reto')
            self.select_point('b')
            expect(self.page.locator('#selection-title')).to_have_text('B')
            expect(self.page.locator('g[data-point=a] circle[stroke="#48d9ff"]')).to_have_count(0)
            expect(self.page.locator('g[data-point=b] circle[stroke="#48d9ff"]')).to_have_count(2)
            expect(self.page.locator('#selection-lock')).to_be_enabled()
            self.empty_tap()
            expect(self.page.locator('#selection-lock')).to_be_disabled()
            expect(self.page.locator('#inspector-panel')).to_be_hidden()
            self.assertEqual(self.draft(), original)
            self.assertEqual(self.page.locator('#undo').is_enabled(), undo)
        self.assertEqual(self.errors, [])

    def test_multiple_touch_toggle_mixed_locks_and_shared_endpoints(self):
        self.open_editor()
        before = self.draft()
        self.touch_session = self.context.new_cdp_session(self.page)
        self.touch_session.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
        self.select_point('a')
        self.page.locator('#selection-lock').click()
        self.page.locator('#multi-select').click()
        self.select_segment('bc')
        expect(self.page.locator('#selection-title')).to_have_text('2 elementos selecionados')
        expect(self.page.locator('#selection-lock')).to_have_attribute('aria-pressed', 'mixed')
        expect(self.page.locator('g[data-segment=bc] path[stroke="#48d9ff"]')).to_have_count(1)
        for ident in ('a', 'b', 'c'):
            expect(self.page.locator('g[data-point=' + ident + '] circle[stroke="#48d9ff"]')).to_have_count(2)
        self.select_point('b')
        expect(self.page.locator('#selection-title')).to_have_text('3 elementos selecionados')
        self.select_point('a')
        expect(self.page.locator('#selection-title')).to_have_text('2 elementos selecionados')
        self.page.locator('#selection-lock').click()
        locked = self.draft()
        self.assertTrue(locked['points'][1]['locked'])
        self.assertTrue(locked['segments'][1]['locked'])
        self.assertEqual([(p['x'], p['y']) for p in locked['points']],
                         [(p['x'], p['y']) for p in before['points']])
        expect(self.page.locator('#multi-select')).to_have_attribute('aria-pressed', 'true')
        self.page.locator('#selection-lock').click()
        self.assertFalse(self.draft()['points'][1]['locked'])
        self.assertFalse(self.draft()['segments'][1]['locked'])
        self.page.locator('#multi-select').click()
        self.select_point('c')
        expect(self.page.locator('#selection-title')).to_have_text('C')
        self.touch_session.detach()
        self.assertEqual(self.errors, [])

    def test_lock_undo_redo_reload_and_module_independence(self):
        self.open_editor('ndb')
        before = self.draft()
        self.select_segment('ab')
        self.page.locator('#selection-lock').click()
        locked = self.draft()
        self.page.locator('#undo').click()
        self.assertEqual(self.draft(), before)
        self.page.locator('#redo').click()
        self.assertEqual(self.draft(), locked)
        self.assert_loaded(self.page.reload())
        self.tab('drawing')
        self.select_segment('ab')
        expect(self.page.locator('#selection-lock')).to_have_attribute('aria-pressed', 'true')
        self.open_editor('procedimentos')
        self.assertFalse(any(e['locked'] for e in self.draft()['segments']))
        self.assertEqual(self.page.evaluate("JSON.parse(localStorage.getItem('ivplanner-procedure-editor-ndb-v1'))"), locked)
        self.assertEqual(self.errors, [])

    def test_shared_point_cannot_unlock_unselected_locked_leg(self):
        self.open_editor()
        self.select_segment('ab')
        self.page.locator('#selection-lock').click()
        locked = self.draft()
        self.select_point('b')
        expect(self.page.locator('#selection-lock')).to_have_attribute('aria-pressed', 'true')
        self.page.locator('#selection-lock').click()
        expect(self.page.locator('#toast')).to_contain_text('perna bloqueada')
        self.assertEqual(self.draft(), locked)
        self.assertEqual(self.errors, [])

    def test_empty_tap_and_collapse_preserve_unapplied_properties(self):
        self.open_editor()
        self.select_point('a')
        before = self.draft()
        self.page.locator('#prop-name').fill('AINDA EDITANDO')
        self.empty_tap()
        self.page.locator('#selection-peek').click()
        expect(self.page.locator('#prop-name')).to_have_value('AINDA EDITANDO')
        expect(self.page.locator('#selection-title')).to_have_text('A')
        self.assertEqual(self.draft(), before)
        self.button('Aplicar medidas').click()
        self.assertEqual(self.draft()['points'][0]['name'], 'AINDA EDITANDO')
        self.assertEqual(self.errors, [])

    def test_compact_controls_panels_safe_areas_and_no_dock_overlap(self):
        for module in ('ndb', 'procedimentos'):
            for width, height in ((320, 568), (390, 844), (844, 390), (820, 1180), (1180, 820)):
                with self.subTest(module=module, viewport=(width, height)):
                    self.page.set_viewport_size({'width': width, 'height': height})
                    self.open_editor(module)
                    session = self.context.new_cdp_session(self.page)
                    for insets in ({'top': 0, 'left': 0, 'right': 0, 'bottom': 0},
                                   {'top': 0, 'left': 44, 'right': 44, 'bottom': 34}):
                        session.send('Emulation.setSafeAreaInsetsOverride', {'insets': insets})
                        self.page.wait_for_timeout(50)
                        self.page.evaluate('scrollTo(0,0)')
                        self.page.locator('#fit').click()
                        layout = self.page.evaluate('''()=>{
                            const r=s=>document.querySelector(s).getBoundingClientRect();
                            return {overflow:document.documentElement.scrollWidth>innerWidth,
                                scroll:document.documentElement.scrollHeight-innerHeight,
                                stageBottom:r('#stage').bottom,dockTop:r('.section-nav').top,
                                tools:[...document.querySelectorAll('.toolbar button')].map(e=>{
                                    const b=e.getBoundingClientRect();return {w:b.width,h:b.height,left:b.left,right:b.right};})};}''')
                        self.assertFalse(layout['overflow'])
                        self.assertLessEqual(layout['scroll'], 1)
                        self.assertLessEqual(layout['stageBottom'], layout['dockTop'] - 6)
                        self.assertEqual(len(layout['tools']), 7)
                        for tool in layout['tools']:
                            self.assertGreaterEqual(tool['w'], 44)
                            self.assertGreaterEqual(tool['h'], 44)
                            self.assertGreaterEqual(tool['left'], insets['left'])
                            self.assertLessEqual(tool['right'], width-insets['right'])
                        self.select_point('a')
                        expect(self.page.locator('#inspector-panel')).to_be_visible()
                        self.assertLessEqual(self.page.locator('#inspector-panel').bounding_box()['y'] +
                                             self.page.locator('#inspector-panel').bounding_box()['height'],
                                             self.page.locator('#stage').bounding_box()['y'] +
                                             self.page.locator('#stage').bounding_box()['height'])
                        self.page.locator('#close-inspector').click()
                    session.send('Emulation.setSafeAreaInsetsOverride', {'insets': {'top': 0, 'left': 0, 'right': 0, 'bottom': 0}})
                    session.detach()
        self.assertEqual(self.errors, [])

    def test_secondary_tools_and_vertical_view_remain_available(self):
        self.open_editor()
        original = self.draft()
        self.page.locator('#add-element').click()
        expect(self.page.locator('#creation-tools')).to_be_visible()
        self.page.locator('[data-tool=curve]').click()
        expect(self.page.locator('#creation-tools')).to_be_hidden()
        self.page.locator('[data-tool=select]').click()
        self.page.locator('#editor-more').click()
        for title in ('Sequência de voo', 'Modelos iniciais editáveis',
                      'Ancoragem e rotação geométrica', 'Procedimento e referência', 'Rascunho e arquivos'):
            expect(self.page.get_by_text(title, exact=True)).to_be_visible()
        self.page.locator('#view-vertical').click()
        expect(self.page.locator('#vertical-view')).to_be_visible()
        self.page.locator('#view-horizontal').click()
        self.assertEqual(self.draft(), original)
        self.assertEqual(self.errors, [])
