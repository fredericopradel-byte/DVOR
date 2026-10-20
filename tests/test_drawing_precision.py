"""Editable geometry precision and the actual usable drawing viewport; fictitious data."""
import json
import math
import unittest
from playwright.sync_api import expect
import test_horizontal_editor as horizontal
import test_procedure_models as models


class DrawingPrecisionTests(unittest.TestCase):
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
    details = models.ProcedureModelTests.details
    rotation = models.ProcedureModelTests.rotation
    model = models.ProcedureModelTests.model

    def geometry(self, ident='ab'):
        data = self.draft()
        edge = next(e for e in data['segments'] if e['id'] == ident)
        a = next(p for p in data['points'] if p['id'] == edge['from'])
        b = next(p for p in data['points'] if p['id'] == edge['to'])
        length = math.hypot(b['x'] - a['x'], b['y'] - a['y'])
        bearing = math.degrees(math.atan2(b['x'] - a['x'], b['y'] - a['y'])) % 360
        return edge, length, bearing

    def assert_grid(self, value, step):
        self.assertAlmostEqual(value / step, round(value / step), places=7)

    def assert_arc_grid(self, ident):
        edge, chord, _ = self.geometry(ident)
        sweep = math.degrees(2 * math.asin(min(1, chord / (2 * edge['radius']))))
        self.assert_grid(edge['radius'], .1)
        self.assert_grid(sweep, 1)
        self.assertGreaterEqual(sweep, 1)
        self.assertLessEqual(sweep, 180)

    def load(self, data):
        self.page.once('dialog', lambda d: d.accept())
        self.page.locator('#import-file').set_input_files({
            'name': 'precision-fixture.json', 'mimeType': 'application/json',
            'buffer': json.dumps(data).encode()})
        expect(self.page.locator('#toast')).to_have_text('Desenho importado.')
        self.page.locator('#fit').click()

    def test_numeric_rounding_changes_geometry_history_reload_and_modules(self):
        for module in ('procedimentos', 'ndb'):
            self.open_editor(module)
            before = self.draft()
            self.select_segment('ab')
            expect(self.page.locator('#prop-bearing')).to_have_attribute('step', '1')
            expect(self.page.locator('#prop-length')).to_have_attribute('step', '0.1')
            self.page.locator('#prop-bearing').fill('120.5')
            self.page.locator('#prop-length').fill('2.15')
            self.button('Aplicar medidas').click()
            _, length, heading = self.geometry()
            self.assertAlmostEqual(length, 2.2)
            self.assertAlmostEqual(heading, 121)
            after = self.draft()
            self.assertEqual(after['points'][2], before['points'][2])
            expect(self.page.locator('#toast')).to_contain_text('121° · 2,2 NM')
            self.page.locator('#undo').click()
            self.assertEqual(self.draft(), before)
            self.page.locator('#redo').click()
            self.assertEqual(self.draft(), after)
            self.assert_loaded(self.page.reload())
            self.tab('drawing')
            self.assertEqual(self.draft(), after)
        self.assertEqual(self.errors, [])

    def test_wrap_decimal_ties_and_minimum_distance(self):
        self.open_editor()
        self.select_segment('ab')
        self.page.locator('#prop-bearing').fill('359.6')
        self.page.locator('#prop-length').fill('5.047')
        self.button('Aplicar medidas').click()
        _, length, heading = self.geometry()
        self.assertAlmostEqual(length, 5)
        self.assertAlmostEqual(heading % 360, 0)
        # Enter submits before blur on several browsers: it must use the same rounding rule.
        self.page.locator('#prop-length').fill('2.13')
        self.page.locator('#prop-length').press('Enter')
        self.assertAlmostEqual(self.geometry()[1], 2.1)
        self.page.locator('#prop-bearing').fill('360.4')
        self.page.locator('#prop-bearing').press('Enter')
        self.assertAlmostEqual(self.geometry()[2] % 360, 0)
        valid = self.draft()
        self.page.locator('#prop-length').fill('0.04')
        self.button('Aplicar medidas').click()
        self.assertEqual(self.draft(), valid)
        self.assertEqual(self.page.evaluate('''()=>[-2.15,-.05,.05,2.15,12.76].map(IVDrawingPrecision.nm)'''),
                         [-2.2, -.1, .1, 2.2, 12.8])
        self.assertEqual(self.errors, [])

    def test_legacy_inspection_and_rename_do_not_normalize_coordinates(self):
        self.open_editor()
        data = self.fixture()
        data['segments'] = data['segments'][:1]
        data['points'] = data['points'][:2]
        data['points'][1].update(x=math.sin(math.radians(197.9))*4.94,
                                 y=math.cos(math.radians(197.9))*4.94)
        data['origin'] = {'lat': '-23.123456789', 'lon': '-43.987654321', 'mag': 10.25, 'dir': 'W'}
        self.load(data)
        before = self.draft()
        self.select_segment('ab')
        expect(self.page.locator('#prop-bearing')).to_have_value('198')
        expect(self.page.locator('#prop-length')).to_have_value('4.9')
        self.page.locator('#prop-name').fill('SÓ IDENTIFICAÇÃO')
        self.button('Aplicar medidas').click()
        after = self.draft()
        self.assertEqual(after['points'], before['points'])
        self.assertEqual(after['origin'], before['origin'])
        self.assert_loaded(self.page.reload())
        self.assertEqual(self.draft()['points'], before['points'])
        # A geographic edit must not round the coordinate the user did not edit.
        def geographic(document):
            point = document['points'][1]
            origin = document['origin']
            lat, lon = math.radians(origin['lat']), math.radians(origin['lon'])
            angular = math.hypot(point['x'], point['y']) / 3440.065
            bearing = math.atan2(point['x'], point['y']) - math.radians(origin['mag'])
            result_lat = math.asin(math.sin(lat)*math.cos(angular) + math.cos(lat)*math.sin(angular)*math.cos(bearing))
            result_lon = lon + math.atan2(math.sin(bearing)*math.sin(angular)*math.cos(lat), math.cos(angular)-math.sin(lat)*math.sin(result_lat))
            return math.degrees(result_lat), (math.degrees(result_lon)+540)%360-180
        original_lat, original_lon = geographic(self.draft())
        self.tab('drawing')
        self.select_point('b')
        self.page.get_by_text('Editar por coordenadas', exact=True).click()
        self.page.locator('#prop-lat').fill(str(original_lat + .001234567))
        self.button('Aplicar medidas').click()
        applied_lat, applied_lon = geographic(self.draft())
        self.assertAlmostEqual(applied_lat, original_lat + .001234567, places=10)
        self.assertAlmostEqual(applied_lon, original_lon, places=10)
        self.assertEqual(self.errors, [])

    def test_curve_numeric_and_handle_keep_radius_and_sweep_steps(self):
        self.open_editor()
        self.select_segment('bc')
        self.page.locator('#prop-radius').fill('2.15')
        self.page.locator('#prop-sweep').fill('45.5')
        self.button('Aplicar medidas').click()
        self.assert_arc_grid('bc')
        self.assertEqual(self.draft()['segments'][1]['radius'], 2.2)
        # Use the actual SVG handle and pointer events rather than the private editor functions.
        self.page.locator('#close-inspector').click()
        handle = self.page.locator('rect[data-curve=bc]').bounding_box()
        self.page.mouse.move(handle['x']+handle['width']/2, handle['y']+handle['height']/2)
        self.page.mouse.down()
        self.page.mouse.move(handle['x']+35, handle['y']+25, steps=6)
        self.page.mouse.up()
        self.assert_arc_grid('bc')
        self.assertEqual(self.errors, [])

    def test_touch_drag_snaps_connected_leg_commits_once_and_cancel_restores(self):
        self.open_editor()
        self.select_point('b')
        before = self.draft()
        p = self.point_position('b')
        session = self.context.new_cdp_session(self.page)
        session.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
        session.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'id': 1, **p}]})
        session.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'id': 1, 'x': p['x']+37, 'y': p['y']+18}]})
        self.assertEqual(self.draft(), before)
        session.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        after = self.draft()
        self.assertNotEqual(after['points'], before['points'])
        _, length, heading = self.geometry()
        self.assert_grid(length, .1)
        self.assert_grid(heading, 1)
        self.assertEqual(after['points'][0], before['points'][0])
        self.assertEqual(after['points'][2], before['points'][2])
        self.assertEqual(after['segments'][0]['to'], after['segments'][1]['from'])
        self.page.locator('#undo').click()
        self.assertEqual(self.draft(), before)
        self.page.locator('#redo').click()
        self.assertEqual(self.draft(), after)
        p = self.point_position('b')
        session.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'id': 1, **p}]})
        session.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'id': 1, 'x': p['x']+15, 'y': p['y']+15}]})
        session.send('Input.dispatchTouchEvent', {'type': 'touchCancel', 'touchPoints': []})
        self.assertEqual(self.draft(), after)
        session.detach()
        self.assertEqual(self.errors, [])

    def test_creation_and_templates_use_quantized_editable_geometry(self):
        self.open_editor()
        self.load({**self.fixture(), 'points': [], 'segments': []})
        svg = self.page.locator('#drawing')
        self.page.locator('#add-element').click()
        self.page.locator('[data-tool=line]').click()
        svg.click(position={'x': 90, 'y': 220})
        svg.click(position={'x': 280, 'y': 340})
        ident = self.draft()['segments'][0]['id']
        _, length, heading = self.geometry(ident)
        self.assert_grid(length, .1)
        self.assert_grid(heading, 1)
        self.page.locator('#add-element').click()
        self.page.locator('[data-tool=curve]').click()
        p = self.point_position(self.draft()['points'][-1]['id'])
        self.tap_position(p)
        svg.click(position={'x': 450, 'y': 240})
        self.assert_arc_grid(self.draft()['segments'][-1]['id'])
        for template in ('rnp', 'conventional'):
            self.model(template)
            for e in self.draft()['segments']:
                if e['type'] == 'curve':
                    self.assert_arc_grid(e['id'])
                else:
                    _, length, heading = self.geometry(e['id'])
                    self.assert_grid(length, .1)
                    self.assert_grid(heading, 1)
        self.assertEqual(self.errors, [])

    def test_incompatible_existing_endpoint_does_not_move_or_leave_orphans(self):
        self.open_editor()
        data = self.fixture()
        data['segments'] = []
        data['points'] = data['points'][:2]
        data['points'][1].update(x=math.sin(math.radians(12.3))*2.13,
                                 y=math.cos(math.radians(12.3))*2.13, locked=True)
        self.load(data)
        before = self.draft()
        undo = self.page.locator('#undo').is_enabled()
        self.page.locator('#add-element').click()
        self.page.locator('[data-tool=line]').click()
        self.tap_position(self.point_position('a'))
        self.tap_position(self.point_position('b'))
        expect(self.page.locator('#toast')).to_contain_text('encaixe exige medidas')
        self.assertEqual(self.draft(), before)
        self.assertEqual(self.page.locator('#undo').is_enabled(), undo)
        self.assertEqual(self.errors, [])

    def test_locked_connected_endpoint_rejects_rounding_atomically(self):
        self.open_editor()
        data = self.fixture()
        data['points'][2]['locked'] = True
        self.load(data)
        before = self.draft()
        self.select_segment('bc')
        self.page.locator('#prop-radius').fill('2.15')
        self.page.locator('#prop-sweep').fill('45.3')
        self.button('Aplicar medidas').click()
        expect(self.page.locator('#toast')).to_contain_text('conflita')
        self.assertEqual(self.draft(), before)
        self.assertEqual(self.errors, [])

    def test_rotation_quantizes_input_without_rounding_declination(self):
        self.open_editor()
        self.rotation(45.3)
        self.assertAlmostEqual(self.geometry()[2], 45)
        data = self.draft()
        data['origin'] = {'lat': '-23.123456789', 'lon': '-43.987654321', 'mag': 10.25, 'dir': 'W'}
        self.load(data)
        self.details('Ancoragem e rotação geométrica')
        self.page.locator('#rotation-declination-confirmed').check()
        self.rotation(90.4, reference='true')
        self.assertAlmostEqual(self.geometry()[2]-10.25, 90)
        self.assertEqual(self.draft()['origin']['mag'], 10.25)
        self.assertEqual(self.errors, [])

    def test_timed_ndb_drawing_rounds_without_changing_operational_calculation(self):
        self.open_editor('ndb', timed=True)
        before = self.draft()
        self.tab('inspection')
        expect(self.page.locator('#page-inspection')).to_contain_text('3,333 NM')
        self.page.once('dialog', lambda d: d.accept())
        self.button('Aplicar pernas ao desenho').click()
        self.assertAlmostEqual(self.geometry()[1], 3.3)
        self.assertEqual(self.draft()['restrictions'], before['restrictions'])
        expect(self.page.locator('#page-inspection')).to_contain_text('3,333 NM')
        self.assertEqual(self.errors, [])

    def test_viewport_fills_available_space_and_reacts_to_safe_areas(self):
        for width, height in ((390, 844), (393, 852), (430, 932), (844, 390), (820, 1180), (1180, 820)):
            self.page.set_viewport_size({'width': width, 'height': height})
            self.open_editor()
            session = self.context.new_cdp_session(self.page)
            for insets in ({'top': 0, 'bottom': 0, 'left': 0, 'right': 0},
                           {'top': 47 if width<height else 0, 'bottom': 34, 'left': 0 if width<height else 44, 'right': 0 if width<height else 44}):
                session.send('Emulation.setSafeAreaInsetsOverride', {'insets': insets})
                self.page.wait_for_timeout(100)
                layout = self.page.evaluate('''()=>{const a=document.querySelector('#stage').getBoundingClientRect(),b=document.querySelector('.section-nav').getBoundingClientRect();return {gap:b.top-a.bottom,overflow:document.documentElement.scrollWidth-innerWidth,scroll:document.documentElement.scrollHeight-innerHeight}}''')
                self.assertGreaterEqual(layout['gap'], 10)
                self.assertLessEqual(layout['gap'], 14)
                self.assertLessEqual(layout['scroll'], 1)
                self.assertLessEqual(layout['overflow'], 0)
            session.send('Emulation.setSafeAreaInsetsOverride', {'insets': {'top': 0, 'bottom': 0, 'left': 0, 'right': 0}})
            session.detach()
            self.page.locator('#view-vertical').click()
            visible = [b for b in self.page.locator('#vertical-view button').all() if b.is_visible()]
            self.assertTrue(visible)
            self.page.evaluate('scrollTo(0,document.documentElement.scrollHeight)')
            button = visible[-1].bounding_box()
            dock = self.page.locator('.section-nav').bounding_box()
            self.assertLessEqual(button['y'] + button['height'], dock['y'] - 6)
        self.assertEqual(self.errors, [])
