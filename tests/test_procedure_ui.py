"""Regressões de interface de Procedimentos e NDB, em armazenamento isolado."""

import json
import unittest

from playwright.sync_api import expect
import test_e2e


class ProcedureUITests(unittest.TestCase):
    setUpClass = classmethod(test_e2e.PlannerTests.setUpClass.__func__)
    setUp = test_e2e.PlannerTests.setUp
    assert_loaded = test_e2e.PlannerTests.assert_loaded

    def open_module(self, module):
        self.assert_loaded(self.page.goto(
            self.base + 'inspecao/desenhar.html?modulo=' + module
        ))
        expect(self.page.locator('#module-title')).to_have_text(
            'NDB' if module == 'ndb' else 'Procedimentos'
        )

    def draft(self, module):
        return self.page.evaluate(
            '(key) => JSON.parse(localStorage.getItem(key))',
            f'ivplanner-procedure-editor-{module}-v1',
        )

    def tab(self, name):
        self.page.locator(f'.section-nav [data-page="{name}"]').click()
        expect(self.page.locator('#page-' + name)).to_be_visible()
        expect(self.page.locator('.section-nav .active')).to_have_attribute(
            'data-page', name
        )
        expect(self.page.locator('.section-nav [aria-pressed="true"]')).to_have_count(1)

    def test_tabs_layout_and_safe_areas(self):
        for module in ('procedimentos', 'ndb'):
            for width, height in ((390, 844), (844, 390), (820, 1180), (1180, 820)):
                with self.subTest(module=module, viewport=(width, height)):
                    self.page.set_viewport_size({'width': width, 'height': height})
                    self.open_module(module)
                    expect(self.page.locator('.section-nav')).to_have_count(1)
                    expect(self.page.locator('.section-nav button svg')).to_have_count(4)
                    expect(self.page.locator('#mission-aircraft, #mission-crew')).to_have_count(0)
                    expect(self.page.locator('#mission-flightGS')).to_be_attached()
                    for name in ('drawing', 'restrictions', 'inspection', 'mission'):
                        self.tab(name)
                        nav = self.page.locator('.section-nav').bounding_box()
                        self.assertGreater(nav['y'], height / 2)
                        self.assertLessEqual(nav['y'] + nav['height'], height - (14 if width >= 700 else 12))
                        self.assertGreaterEqual(nav['x'], 10)
                        self.assertLessEqual(nav['x'] + nav['width'], width - 10)
                        self.assertTrue(self.page.evaluate(
                            'document.documentElement.scrollWidth <= innerWidth'
                        ))
                        # No fim de cada aba, o último controle fica acima da barra.
                        self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        controls = self.page.locator(
                            '#page-' + name + ' button, #page-' + name + ' input, '
                            '#page-' + name + ' textarea, #page-' + name + ' summary'
                        )
                        visible = [c for c in controls.all() if c.is_visible()]
                        if visible:
                            last = visible[-1].bounding_box()
                            self.assertLessEqual(last['y'] + last['height'], nav['y'])
                    # Chromium oferece emulação de env(safe-area-inset-*).
                    session = self.context.new_cdp_session(self.page)
                    session.send('Emulation.setSafeAreaInsetsOverride', {'insets': {
                        'top': 0, 'left': 44, 'right': 44, 'bottom': 34,
                    }})
                    self.page.wait_for_timeout(50)
                    nav = self.page.locator('.section-nav').bounding_box()
                    self.assertGreaterEqual(nav['x'], 44)
                    self.assertLessEqual(nav['x'] + nav['width'], width - 44)
                    self.assertAlmostEqual(nav['y'] + nav['height'], height - (48 if width >= 700 else 46), delta=1)
                    session.send('Emulation.setSafeAreaInsetsOverride', {'insets': {
                        'top': 0, 'left': 0, 'right': 0, 'bottom': 0,
                    }})
                    session.detach()
        self.assertEqual(self.errors, [])

    def test_capsule_matches_dvor_ils_and_date_stays_inside_card(self):
        # Compare effective styles, including page-ui.css, rather than old local rules.
        properties = ['borderRadius', 'borderColor', 'borderWidth', 'backgroundColor',
                      'boxShadow', 'padding', 'height', 'backdropFilter', 'gap']
        style_js = """(el, properties) => {
            const css = getComputedStyle(el);
            return Object.fromEntries(properties.map(p => [p, css[p]]));
        }"""
        for width, height in ((320, 568), (375, 812), (390, 844), (430, 932),
                              (844, 390), (768, 1024), (820, 1180), (1180, 820)):
            with self.subTest(viewport=(width, height)):
                self.page.set_viewport_size({'width': width, 'height': height})
                reference = None
                for path in ('inspecao/dvor-vor/index.html', 'inspecao/ils.html'):
                    self.page.goto(self.base + path)
                    expect(self.page.locator('.iv-bottom-nav.iv-ready')).to_be_visible()
                    measured = self.page.locator('.iv-bottom-nav').evaluate(style_js, properties)
                    if reference is None:
                        reference = measured
                    self.assertEqual(measured, reference)
                for module in ('procedimentos', 'ndb'):
                    self.open_module(module)
                    expect(self.page.locator('.iv-bottom-nav.iv-ready')).to_be_visible()
                    self.assertEqual(self.page.locator('.section-nav').evaluate(
                        style_js, properties), reference)
                    self.assertEqual(self.page.locator('.section-nav').bounding_box()['height'], 62)
                    for name in ('drawing', 'restrictions', 'inspection', 'mission'):
                        self.tab(name)
                        expect(self.page.locator('.section-nav [aria-current="page"]')).to_have_attribute('data-page', name)
                    for value in ('', '2026-10-14'):
                        date = self.page.locator('#mission-date')
                        date.fill(value)
                        self.page.locator('#mission-name').click()
                        expect(date).to_have_value(value)
                        date_box = date.bounding_box()
                        label_box = date.locator('..').bounding_box()
                        self.assertLessEqual(date_box['width'], label_box['width'] + 1)
                        self.assertEqual(self.draft(module)['mission']['date'], value)
                    violations = self.page.locator('#page-mission').evaluate("""el =>
                        [...el.querySelectorAll('input:not([type=checkbox]),select,textarea')]
                        .filter(input => {
                            const a=input.getBoundingClientRect(), b=input.parentElement.getBoundingClientRect();
                            return a.left < b.left-1 || a.right > b.right+1;
                        }).map(el=>el.id)
                    """)
                    self.assertEqual(violations, [])
                    self.assert_loaded(self.page.reload())
                    expect(self.page.locator('#mission-date')).to_have_value('2026-10-14')
        self.assertEqual(self.errors, [])

    def test_legacy_values_and_independent_missions(self):
        self.page.on('dialog', lambda dialog: dialog.accept())
        for module in ('procedimentos', 'ndb'):
            self.open_module(module)
            self.page.evaluate('''(module) => {
                const key = 'ivplanner-procedure-editor-' + module + '-v1';
                const doc = JSON.parse(localStorage.getItem(key));
                doc.mission.name = 'Missão antiga ' + module;
                doc.mission.crew = 'EQUIPE FICTICIA ' + module;
                doc.mission.aircraft = 'AERONAVE FICTICIA ' + module;
                doc.missionId = 'antiga-' + module;
                localStorage.setItem(key, JSON.stringify(doc));
                localStorage.setItem('ivplanner-procedure-missions-' + module + '-v1',
                    JSON.stringify([{id: doc.missionId, document: doc}]));
            }''', module)
        snapshots = {m: self.draft(m) for m in ('procedimentos', 'ndb')}
        for module in ('procedimentos', 'ndb'):
            self.open_module(module)
            expect(self.page.locator('#mission-aircraft, #mission-crew')).to_have_count(0)
            self.page.locator('#mission-notes').fill('Observação fictícia ' + module)
            self.page.get_by_role('button', name='Salvar missão', exact=True).click()
            stored = self.draft(module)
            for field in ('crew', 'aircraft'):
                self.assertEqual(stored['mission'][field], snapshots[module]['mission'][field])
            other = 'ndb' if module == 'procedimentos' else 'procedimentos'
            self.assertEqual(self.draft(other), snapshots[other])
            self.page.get_by_role('button', name='Nova missão', exact=True).click()
            self.page.locator('#saved-mission').select_option('antiga-' + module)
            self.page.get_by_role('button', name='Reabrir', exact=True).click()
            expect(self.page.locator('#mission-notes')).to_have_value('Observação fictícia ' + module)
            self.assertEqual(self.draft(module), stored)
            self.assert_loaded(self.page.reload())
            self.assertEqual(self.draft(module), stored)
            snapshots[module] = stored
        self.assertEqual(self.errors, [])

    def test_drawing_tools_export_import_and_reopen(self):
        self.page.on('dialog', lambda dialog: dialog.accept())
        self.page.set_viewport_size({'width': 390, 'height': 844})
        for module in ('procedimentos', 'ndb'):
            with self.subTest(module=module):
                self.open_module(module)
                self.tab('drawing')
                svg = self.page.locator('#drawing')
                self.page.locator('[data-tool="point"]').click()
                svg.click(position={'x': 80, 'y': 120})
                self.assertEqual(len(self.draft(module)['points']), 1)
                self.page.locator('[data-tool="line"]').click()
                svg.click(position={'x': 80, 'y': 120})
                svg.click(position={'x': 180, 'y': 180})
                self.page.locator('[data-tool="curve"]').click()
                svg.click(position={'x': 180, 'y': 180})
                svg.click(position={'x': 280, 'y': 120})
                drawn = self.draft(module)
                self.assertEqual([s['type'] for s in drawn['segments']], ['line', 'curve'])
                self.page.locator('#undo').click()
                self.assertEqual(len(self.draft(module)['segments']), 1)
                self.page.locator('#redo').click()
                self.assertEqual(self.draft(module), drawn)
                self.page.locator('#zoom-in').click()
                self.page.locator('#zoom-out').click()
                self.page.locator('#fit').click()
                self.assertEqual(self.draft(module), drawn)
                # Dois toques reais no Chromium: zoom/rotação mudam a vista,
                # sem alterar a geometria persistida.
                svg.scroll_into_view_if_needed()
                box = svg.bounding_box()
                session = self.context.new_cdp_session(self.page)
                session.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
                north = self.page.locator('#north-arrow').get_attribute('style')
                coords = [(100, 150, 230, 150), (90, 130, 245, 180)]
                for event, (ax, ay, bx, by) in zip(('touchStart', 'touchMove'), coords):
                    session.send('Input.dispatchTouchEvent', {
                        'type': event, 'touchPoints': [
                            {'id': 1, 'x': box['x'] + ax, 'y': box['y'] + ay},
                            {'id': 2, 'x': box['x'] + bx, 'y': box['y'] + by},
                        ],
                    })
                session.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                self.page.wait_for_timeout(100)
                self.assertNotEqual(self.page.locator('#north-arrow').get_attribute('style'), north)
                self.assertEqual(self.draft(module), drawn)
                session.send('Emulation.setTouchEmulationEnabled', {'enabled': False})
                session.detach()
                self.page.locator('#fit').click()
                # Seleção e arraste pela interface, sem acesso às funções internas.
                self.page.locator('[data-tool="select"]').click()
                point = svg.locator('circle[data-point]').first
                box = point.bounding_box()
                self.assertIsNotNone(box)
                x, y = box['x'] + box['width']/2, box['y'] + box['height']/2
                self.page.mouse.move(x, y)
                self.page.mouse.down()
                self.page.mouse.move(x + 15, y + 15, steps=5)
                self.page.mouse.up()
                self.assertNotEqual(self.draft(module)['points'], drawn['points'])
                drawn = self.draft(module)
                self.tab('restrictions')
                self.tab('inspection')
                self.tab('drawing')
                self.assertEqual(self.draft(module), drawn)
                self.page.locator('summary').filter(has_text='Rascunho e arquivos').click()
                with self.page.expect_download() as download:
                    self.page.locator('#export').click()
                with open(download.value.path(), encoding='utf-8') as file:
                    exported = json.load(file)
                self.assertEqual(exported, drawn)
                self.page.locator('#clear').click()
                self.assertEqual(self.draft(module)['points'], [])
                self.page.locator('#import-file').set_input_files({
                    'name': 'desenho-ficticio.json', 'mimeType': 'application/json',
                    'buffer': json.dumps(exported).encode(),
                })
                expect(self.page.locator('#toast')).to_have_text('Desenho importado.')
                self.assertEqual(self.draft(module), drawn)
                self.assert_loaded(self.page.reload())
                self.tab('drawing')
                self.assertEqual(self.draft(module), drawn)
        self.assertEqual(self.errors, [])
