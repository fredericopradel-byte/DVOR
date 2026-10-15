"""PR 6: gestos reais CDP, GNSS simulado e auditoria de controles de mapa."""
import json
import re
import unittest
from urllib.parse import urlparse

from playwright.sync_api import expect
import test_e2e


ROUTES = [
    ('inspecao/radar.html', '.page-nav [data-page=rose]', '.rose-stage', '.map-corner-controls button,.map-color-toggle,.map-readout,.gnss-hud'),
    ('inspecao/dvor-vor/index.html', '.page-nav [data-page=rose]', '.rose-stage', '.map-corner-controls button,.map-color-toggle,.map-readout,.gnss-hud'),
    ('inspecao/ils.html', '.page-nav [data-page=rose]', '.rose-stage', '.map-corner-controls button,.ils-map-extras button,.gnss-hud'),
    ('inspecao/papi.html', '.bottom-nav [data-page=map]', '.canvas-wrap', '.map-gnss,.map-readout,.map-overlay'),
    ('inspecao/desenhar.html?modulo=procedimentos', '.section-nav [data-page=drawing]', '#stage', '.map-controls button,.north,.stage-hint'),
    ('inspecao/desenhar.html?modulo=ndb', '.section-nav [data-page=drawing]', '#stage', '.map-controls button,.north,.stage-hint'),
    ('meteorologia/index.html', None, '.mapwrap', '.leaflet-control-zoom a,.leaflet-control-attribution,.legend'),
    ('papi.html', '.bottom-nav [data-page=map]', '.canvas-wrap', '.map-gnss,.map-readout,.map-overlay'),
    ('ils.html', '.page-nav [data-page=rose]', '.rose-stage', '.map-corner-controls button,.map-color-toggle,.gnss-hud'),
]


class MapControlTests(unittest.TestCase):
    setUpClass = classmethod(test_e2e.PlannerTests.setUpClass.__func__)
    setUp = test_e2e.PlannerTests.setUp
    assert_loaded = test_e2e.PlannerTests.assert_loaded
    dismiss_database_prompt = test_e2e.PlannerTests.dismiss_database_prompt

    def open_map(self, route):
        path, nav, stage, selectors = route
        self.page.goto(self.base + path)
        self.page.wait_for_timeout(200)
        if nav: self.page.locator(nav).click()
        self.page.locator(stage).first.wait_for(state='visible')
        self.page.locator(stage).first.scroll_into_view_if_needed()
        return stage, selectors

    def radar(self, vertical=True):
        self.assert_loaded(self.page.goto(self.base + 'inspecao/radar.html'))
        fixture = {'schema': 'ivplanner-radar-v2', 'metadata': {'missionTitle': 'RADAR FICTÍCIO', 'radar': 'TST', 'name': 'SÍTIO FICTÍCIO',
                   'stationLat': -23, 'stationLon': -43, 'magVar': '10', 'magVarDir': 'W', 'alt': '100'},
                   'activities': [
                       {'id': 'ori', 'kind': 'ORI', 'description': 'Orientação fictícia', 'azimuth': 90, 'start': 0, 'end': 10, 'alt': 1000},
                       {'id': 'p1', 'kind': 'P1', 'description': 'Horizontal fictícia', 'start': 10, 'end': 20, 'radius': 15, 'alt': 2000},
                       {'id': 'p2', 'kind': 'P2', 'description': 'Vertical fictícia', 'azimuth': 90, 'start': 0, 'end': 25, 'alt': 5000}], 'activeId': 'ori'}
        self.page.locator('#import-file').set_input_files({'name': 'radar-ficticio.json', 'mimeType': 'application/json', 'buffer': json.dumps(fixture).encode()})
        expect(self.page.locator('#mission-title')).to_have_value('RADAR FICTÍCIO')
        self.page.locator('.page-nav [data-page=rose]').click()
        if vertical: self.page.locator('#map-profile').click()
        return self.page.evaluate('localStorage.getItem("ivplanner-radar-current-v1")')

    def touch_session(self):
        session = self.context.new_cdp_session(self.page)
        session.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
        self.addCleanup(session.detach)
        return session

    def pinch(self, selector='#rose'):
        svg = self.page.locator(selector)
        svg.scroll_into_view_if_needed(); box = svg.bounding_box()
        session = self.touch_session()
        for kind, points in [('touchStart', [(.35, .45), (.60, .45)]),
                             ('touchMove', [(.30, .35), (.70, .55)])]:
            session.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': [
                {'id': i + 1, 'x': box['x'] + x * box['width'], 'y': box['y'] + y * box['height']}
                for i, (x, y) in enumerate(points)]})
        session.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        self.page.wait_for_timeout(100)

    def drag(self):
        svg = self.page.locator('#rose'); svg.scroll_into_view_if_needed(); b = svg.bounding_box()
        self.page.mouse.move(b['x'] + b['width'] * .55, b['y'] + b['height'] * .55)
        self.page.mouse.down()
        self.page.mouse.move(b['x'] + b['width'] * .65, b['y'] + b['height'] * .60, steps=5)
        self.page.mouse.up()

    def assert_controls(self, stage, selector):
        result = self.page.evaluate('''({stage,selector})=>{
            const host=document.querySelector(stage),r=host.getBoundingClientRect();
            const controls=[...document.querySelectorAll(selector)].filter(e=>e.getClientRects().length).map(e=>{
                const b=e.getBoundingClientRect();return {id:e.id||e.className,button:e.matches('button,a'),inside:host.contains(e),x:b.x-r.x,y:b.y-r.y,w:b.width,h:b.height};});
            return {w:r.width,h:r.height,controls,overflow:document.documentElement.scrollWidth>innerWidth+1};
        }''', {'stage': stage, 'selector': selector})
        self.assertFalse(result['overflow'])
        for c in result['controls']:
            if c['button']:
                self.assertGreaterEqual(c['w'], 44, c['id']); self.assertGreaterEqual(c['h'], 44, c['id'])
            if c['inside']:
                self.assertGreaterEqual(c['x'], 0, c['id']); self.assertGreaterEqual(c['y'], 0, c['id'])
                self.assertLessEqual(c['x'] + c['w'], result['w'] + 1, c['id'])
                self.assertLessEqual(c['y'] + c['h'], result['h'] + 1, c['id'])
        inside = [c for c in result['controls'] if c['inside']]
        for i, a in enumerate(inside):
            for b in inside[i + 1:]:
                overlap_x = min(a['x'] + a['w'], b['x'] + b['w']) - max(a['x'], b['x'])
                overlap_y = min(a['y'] + a['h'], b['y'] + b['h']) - max(a['y'], b['y'])
                self.assertFalse(overlap_x > 1 and overlap_y > 1, (a['id'], b['id']))
        for button in self.page.locator('.rose-page .step-controls button').all():
            box = button.bounding_box()
            self.assertGreaterEqual(box['width'], 44)
            self.assertGreaterEqual(box['height'], 44)

    def test_radar_vertical_pinch_keeps_axes_zoom_pan_and_mission(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        original = self.radar()
        paths = self.page.locator('#rose-lines').inner_html()
        before = self.page.locator('#rose').get_attribute('viewBox')
        self.pinch()
        expect(self.page.locator('#map-world')).to_have_attribute('transform', 'rotate(0 250 250)')
        expect(self.page.locator('#map-readout')).to_contain_text('Perfil vertical')
        self.assertNotEqual(self.page.locator('#rose').get_attribute('viewBox'), before)
        before = self.page.locator('#rose').get_attribute('viewBox')
        self.drag()
        self.assertNotEqual(self.page.locator('#rose').get_attribute('viewBox'), before)
        self.assertEqual(self.page.locator('#rose-lines').inner_html(), paths)
        expect(self.page.locator('#rose-lines>line')).to_have_count(2)
        self.assertEqual(self.page.evaluate('localStorage.getItem("ivplanner-radar-current-v1")'), original)
        self.assertEqual(self.errors, [])

    def test_radar_horizontal_rotation_remains_after_profile_switch(self):
        original = self.radar(vertical=False)
        self.pinch()
        self.assertNotEqual(self.page.locator('#map-world').get_attribute('transform'), 'rotate(0 250 250)')
        self.page.locator('#map-profile').click()
        self.pinch()
        expect(self.page.locator('#map-world')).to_have_attribute('transform', 'rotate(0 250 250)')
        self.page.locator('#map-profile').click()
        self.pinch()
        self.assertNotEqual(self.page.locator('#map-world').get_attribute('transform'), 'rotate(0 250 250)')
        self.assertEqual(self.page.evaluate('localStorage.getItem("ivplanner-radar-current-v1")'), original)
        self.assertEqual(self.errors, [])

    def test_radar_gnss_updates_profile_and_centers_without_rotation(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        original = self.radar()
        url = urlparse(self.base)
        self.context.grant_permissions(['geolocation'], origin=url.scheme + '://' + url.netloc)
        session = self.context.new_cdp_session(self.page); self.addCleanup(session.detach)
        session.send('Emulation.setGeolocationOverride', {'latitude': -22.97, 'longitude': -42.97, 'accuracy': 5, 'altitude': 500, 'altitudeAccuracy': 1, 'heading': 60, 'speed': 90})
        self.page.locator('#gnss-toggle').click()
        expect(self.page.locator('#gnss-readout')).to_contain_text('RDL')
        expect(self.page.locator('#aircraft-layer image')).to_have_attribute('href', 'legacy-profile.png')
        first = self.page.locator('#aircraft-layer>g').get_attribute('transform')
        text = self.page.locator('#gnss-readout').inner_text()
        session.send('Emulation.setGeolocationOverride', {'latitude': -22.95, 'longitude': -42.95, 'accuracy': 8, 'altitude': 1500, 'altitudeAccuracy': 1, 'heading': 120, 'speed': 70})
        expect(self.page.locator('#gnss-readout')).not_to_have_text(text)
        self.assertNotEqual(self.page.locator('#aircraft-layer>g').get_attribute('transform'), first)
        self.page.locator('#center-aircraft').click(); self.pinch()
        expect(self.page.locator('#map-world')).to_have_attribute('transform', 'rotate(0 250 250)')
        expect(self.page.locator('#aircraft-layer>g')).to_have_attribute('transform', re.compile(r'.*rotate\(0\)'))
        self.assert_controls(*ROUTES[0][2:])
        self.page.locator('#gnss-toggle').click()
        expect(self.page.locator('#aircraft-layer image')).to_have_count(0)
        self.assertEqual(self.page.evaluate('localStorage.getItem("ivplanner-radar-current-v1")'), original)
        self.assertEqual(self.errors, [])

    def test_all_map_controls_nine_routes_five_viewports(self):
        for route in ROUTES:
            for width, height in ((320, 568), (390, 844), (844, 390), (820, 1180), (1180, 820)):
                with self.subTest(path=route[0], width=width):
                    self.page.set_viewport_size({'width': width, 'height': height})
                    self.assert_controls(*self.open_map(route))
        self.assertEqual(self.errors, [])

    def test_operational_controls_safe_areas_and_landscape(self):
        session = self.context.new_cdp_session(self.page); self.addCleanup(session.detach)
        for width, height, insets in ((390, 844, {'top': 44, 'bottom': 34}),
                                      (844, 390, {'left': 44, 'right': 44, 'bottom': 21})):
            self.page.set_viewport_size({'width': width, 'height': height})
            session.send('Emulation.setSafeAreaInsetsOverride', {'insets': insets})
            for route in ROUTES[:7]:
                with self.subTest(path=route[0], width=width):
                    self.assert_controls(*self.open_map(route))
        self.assertEqual(self.errors, [])

    def test_other_maps_keep_rotation_and_weather_zoom(self):
        self.open_map(ROUTES[1]); self.pinch()
        self.assertNotEqual(self.page.locator('#map-world').get_attribute('transform'), 'rotate(0 250 250)')
        for route in ROUTES[4:6]:
            self.open_map(route)
            previous = self.page.locator('#north-arrow').get_attribute('style')
            self.pinch('#drawing')
            self.assertNotEqual(self.page.locator('#north-arrow').get_attribute('style'), previous)
        self.open_map(ROUTES[6])
        marker = self.page.locator('#map .leaflet-marker-icon').first
        previous = marker.get_attribute('style')
        self.page.locator('.leaflet-control-zoom-in').click(); self.page.wait_for_timeout(400)
        self.assertNotEqual(marker.get_attribute('style'), previous)
        self.assertEqual(self.errors, [])

    def test_radar_profile_wheel_zoom_and_reset_still_work(self):
        self.radar()
        self.page.locator('#rose').scroll_into_view_if_needed()
        box = self.page.locator('#rose').bounding_box()
        self.page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        self.page.mouse.wheel(0, -100)
        self.page.wait_for_timeout(100)
        self.assertNotEqual(self.page.locator('#rose').get_attribute('viewBox'), '0 0 500 500')
        self.page.locator('#rose').dblclick(position={'x': box['width'] / 2, 'y': box['height'] / 2})
        expect(self.page.locator('#rose')).to_have_attribute('viewBox', '0 0 500 500')
        expect(self.page.locator('#map-world')).to_have_attribute('transform', 'rotate(0 250 250)')
        self.assertEqual(self.errors, [])

    def test_radar_profile_offline_reload_preserves_passages(self):
        self.page.goto(self.base + 'index.html')
        self.page.evaluate('''async()=>{await Promise.race([navigator.serviceWorker.ready,new Promise((_,reject)=>setTimeout(()=>reject(Error('Worker não ativou')),10000))]);}''')
        original = self.radar()
        self.page.evaluate('''async()=>{await navigator.serviceWorker.ready;if(!navigator.serviceWorker.controller)await new Promise(r=>navigator.serviceWorker.addEventListener('controllerchange',r,{once:true}));}''')
        self.context.set_offline(True)
        self.assert_loaded(self.page.reload())
        self.page.locator('.page-nav [data-page=rose]').click()
        self.page.locator('#map-profile').click()
        self.pinch()
        expect(self.page.locator('#map-world')).to_have_attribute('transform', 'rotate(0 250 250)')
        expect(self.page.locator('#rose-lines>line')).to_have_count(2)
        self.assertEqual(self.page.evaluate('localStorage.getItem("ivplanner-radar-current-v1")'), original)
        self.assertEqual(self.errors, [])
