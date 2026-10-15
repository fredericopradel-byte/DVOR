"""PR 5: bases fictícias em pacote/cache e perfis temporários, sem dados reais."""
import json
import unittest
from urllib.parse import urlparse

from playwright.sync_api import expect
import test_horizontal_editor as horizontal


class MissionDatabaseTests(unittest.TestCase):
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
    tap_position = horizontal.HorizontalEditorTests.tap_position

    def dataset(self):
        airport = {'id': 'airport1', 'designator': 'TST1', 'name': 'Aeródromo Fictício AIXM'}
        raw = {'schema': 'ivplanner-aixm-core-v1', 'version': 'AIXM-FICTICIO', 'effectiveDate': '2000-01-01',
               'aerodromes': [{**airport, 'position': {'lat': -21, 'lon': -41}, 'fieldElevation': {'value': 100, 'uom': 'M'}}],
               'runwayDirections': [{'id': 'direction1', 'designator': '09', 'runwayDesignator': '09/27', 'airport': airport}],
               'runwayPoints': [{'id': 'threshold1', 'runwayId': 'direction1', 'designator': '09', 'role': 'THR', 'position': {'lat': -21.1, 'lon': -41.1}}],
               'navaids': [{'id': 'ndb1', 'type': 'NDB', 'designator': 'TST', 'name': 'NDB Fictício AIXM', 'airport': airport,
                            'position': {'lat': -21.2, 'lon': -41.2}, 'equipmentIds': ['equipment1'], 'elevation': {'value': 100, 'uom': 'M'}}],
               'navaidEquipment': [{'id': 'equipment1', 'frequency': {'value': 320, 'uom': 'KHZ'}}],
               'procedures': [{'id': 'iac1', 'name': 'RNP FICT RWY 09', 'procedureType': 'InstrumentApproachProcedure', 'airport': airport, 'validFrom': '1999-01-01'},
                              {'id': 'sid1', 'name': 'SAIDA FICT', 'procedureType': 'StandardInstrumentDeparture', 'airport': airport},
                              {'id': 'star1', 'name': 'CHEGADA FICT', 'procedureType': 'StandardInstrumentArrival', 'airport': airport}],
               'visualGlideSlopeIndicators': []}
        legacy = {'version': 'ROTAER-FICTICIO', 'aerodromes': [['TST1', 'Fictício ROTAER', -20, -40, 100, 1000, 'XX']],
                  'runwayDatabase': {'runways': {'TST1': [['09', 12, '27', 192, 1000, 'model']]}}}
        adc = {'version': 'ADC-FICTICIO', 'aerodromes': {'TST1': {'effective': '1998-01-01', 'headings': {'09': 89, '27': 269}}}, 'overrides': {}}
        manual = [{'icao': 'TST1', 'name': 'Localidade Manual Fictícia', 'lat': '', 'lon': '', 'elev': '', 'runways': [{'end1': '18', 'end2': '36', 'heading1': 123, 'heading2': 303}]}]
        aids = [{'id': 'manual-aid', 'type': 'NDB', 'designator': 'MTST', 'name': 'NDB Manual Fictício', 'airportIcao': 'TST1',
                 'lat': '', 'lon': '', 'frequencyValue': '', 'frequencyUom': '', 'elevationValue': '', 'elevationUom': ''}]
        return {'raw': raw, 'legacy': legacy, 'adc': adc, 'manual': manual, 'aids': aids}

    def open_databases(self, module='procedimentos', aixm=True):
        self.open_editor(module, timed=True)
        self.data = self.dataset()
        self.page.evaluate('''async()=>{await navigator.serviceWorker.ready;
          if(!navigator.serviceWorker.controller)await new Promise(r=>navigator.serviceWorker.addEventListener('controllerchange',r,{once:true}));}''')
        self.install_package(aixm)
        self.page.evaluate('''data=>{
          localStorage.setItem('ivplanner-custom-localities-v1',JSON.stringify(data.manual));
          localStorage.setItem('ivplanner-custom-aids-v1',JSON.stringify(data.aids));
        }''', self.data)
        self.assert_loaded(self.page.reload())
        self.tab('mission')

    def install_package(self, aixm=True):
        self.page.evaluate('''async({data,aixm})=>{
          const prefix='publicacoes-offline/aixm/AIXM-BR-2026-09-03/aixm-core.json';
          const files={'prevoo/legacy-data.js':'window.LEGACY_DATA='+JSON.stringify(data.legacy)+';',
            'adc-runway-data.js':'window.ADC_RUNWAY_DATA='+JSON.stringify(data.adc)+';'};
          if(aixm)files[prefix]=JSON.stringify(data.raw);
          const cache=await caches.open('ivdata-package-test-mission');
          for(const [path,content] of Object.entries(files))await cache.put(new URL(path,new URL('/DVOR/',location.origin)),new Response(content,{headers:{'Content-Type':path.endsWith('.js')?'text/javascript':'application/json'}}));
          await new Promise((resolve,reject)=>{const req=indexedDB.open('ivplanner-package-manager-v1',1);
            req.onupgradeneeded=()=>{if(!req.result.objectStoreNames.contains('packages'))req.result.createObjectStore('packages',{keyPath:'id'})};
            req.onerror=()=>reject(req.error);req.onsuccess=()=>{const db=req.result,tx=db.transaction('packages','readwrite');
              tx.objectStore('packages').put({id:'test-mission-databases',status:'installed',installedVersion:'fixture',activeCache:'ivdata-package-test-mission',targets:Object.keys(files)});
              tx.oncomplete=()=>{db.close();resolve()};tx.onerror=()=>reject(tx.error)};
          });
        }''', {'data': self.data, 'aixm': aixm})

    def search(self, term='TST1'):
        if not self.page.locator('#page-mission').is_visible(): self.tab('mission')
        self.page.locator('#mission-database-query').fill(term)
        self.page.locator('#mission-database-search').click()
        expect(self.page.locator('#mission-database-search')).to_be_enabled()

    def card(self, title):
        return self.page.locator('.database-card').filter(has=self.page.get_by_role('heading', name=title, exact=True))

    def use(self, title, button, accept=True):
        self.page.once('dialog', lambda d: d.accept() if accept else d.dismiss())
        self.card(title).get_by_role('button', name=button, exact=True).click()

    def test_localities_sources_adc_and_manual_data_are_not_assumed(self):
        self.open_databases()
        before = self.draft()
        self.search()
        expect(self.card('TST1 · Fictício ROTAER')).to_contain_text('ROTAER-FICTICIO')
        expect(self.card('TST1 · Aeródromo Fictício AIXM')).to_contain_text('AIXM-FICTICIO')
        manual = self.card('TST1 · Localidade Manual Fictícia')
        expect(manual.get_by_role('button', name='Usar coordenadas como origem')).to_have_count(0)
        runway = self.card('TST1 · RWY 09').filter(has_text='Rumo MAG publicado')
        expect(runway).to_contain_text('89°')
        expect(self.card('TST1 · RWY 18')).to_contain_text('Nenhum rumo é deduzido')
        self.assertEqual(self.draft(), before)
        self.use('TST1 · Fictício ROTAER', 'Usar localidade', accept=False)
        self.assertEqual(self.draft(), before)
        self.use('TST1 · Fictício ROTAER', 'Usar localidade')
        after = self.draft()
        self.assertEqual((after['mission']['icao'], after['mission']['local']), ('TST1', 'Fictício ROTAER'))
        self.assertEqual(after['origin'], before['origin'])
        self.assertEqual(after['points'], before['points'])
        self.assertEqual(self.errors, [])

    def test_published_metadata_preserves_geometry_restrictions_and_chart_revision(self):
        self.open_databases()
        self.page.locator('#mission-chart').fill('CARTA MANUAL')
        self.page.locator('#mission-revision').fill('REVISAO MANUAL')
        self.page.locator('#mission-name').click()
        before = self.draft()
        self.search()
        expect(self.card('TST1 · CHEGADA FICT').get_by_role('button')).to_have_count(0)
        self.use('TST1 · RNP FICT RWY 09', 'Usar identificação do procedimento')
        after = self.draft()
        self.assertEqual(after['title'], 'RNP FICT RWY 09')
        for key in ('points', 'segments', 'flight', 'restrictions', 'origin'):
            self.assertEqual(before[key], after[key])
        self.assertEqual((after['mission']['chart'], after['mission']['revision']), ('CARTA MANUAL', 'REVISAO MANUAL'))
        self.search()
        self.use('TST1 · SAIDA FICT', 'Usar identificação do procedimento')
        self.assertEqual(self.draft()['kind'], 'SID')
        self.assertEqual(self.draft()['restrictions'], before['restrictions'])
        self.assertEqual(self.errors, [])

    def test_ndb_units_missing_values_and_other_module_independence(self):
        self.open_databases('procedimentos')
        other = self.draft()
        self.open_databases('ndb')
        self.search()
        self.use('NDB · TST · NDB Fictício AIXM', 'Usar dados do NDB')
        after = self.draft()
        self.assertEqual(after['mission']['ndbFrequency'], '320')
        self.assertAlmostEqual(float(after['mission']['ndbAltitude']), 100 / .3048)
        self.assertEqual(after['origin']['lat'], '')
        self.search()
        expect(self.card('NDB · MTST · NDB Manual Fictício')).to_contain_text('não será preenchida')
        self.use('NDB · MTST · NDB Manual Fictício', 'Usar dados do NDB')
        manual = self.draft()
        self.assertEqual(manual['mission']['ndbIdent'], 'MTST')
        self.assertEqual(manual['mission']['ndbFrequency'], after['mission']['ndbFrequency'])
        self.assertEqual(manual['mission']['ndbAltitude'], after['mission']['ndbAltitude'])
        self.data['aids'][0].update({'frequencyValue': '.32', 'frequencyUom': 'MHZ', 'elevationValue': 0, 'elevationUom': 'FT', 'lat': 0, 'lon': 0})
        self.page.evaluate('rows=>localStorage.setItem("ivplanner-custom-aids-v1",JSON.stringify(rows))', self.data['aids'])
        self.search()
        self.use('NDB · MTST · NDB Manual Fictício', 'Usar dados do NDB')
        self.assertEqual(self.draft()['mission']['ndbFrequency'], '320')
        self.assertEqual(self.draft()['mission']['ndbAltitude'], '0')
        self.search()
        expect(self.card('NDB · MTST · NDB Manual Fictício').get_by_role('button', name='Usar coordenadas como origem')).to_have_count(1)
        self.assertEqual(self.page.evaluate('()=>JSON.parse(localStorage.getItem("ivplanner-procedure-editor-procedimentos-v1"))'), other)
        self.assertEqual(self.errors, [])

    def test_reference_is_explicit_respects_locks_and_keeps_pending_declination(self):
        self.open_databases()
        self.tab('drawing')
        self.select_segment('ab')
        self.button('Bloquear').click()
        self.tab('mission')
        before = self.draft()
        self.search()
        threshold = self.card('TST1 · RWY 09').filter(has_text='Coordenada THR')
        threshold.get_by_role('button', name='Usar coordenadas como origem').click()
        expect(self.page.locator('#toast')).to_contain_text('bloqueada')
        self.assertEqual(self.draft(), before)
        self.use('TST1 · Fictício ROTAER', 'Usar localidade')
        self.assertTrue(self.draft()['segments'][0]['locked'])
        self.tab('drawing')
        self.select_segment('ab'); self.button('Desbloquear').click()
        self.tab('mission'); self.search()
        self.page.locator('#mission-origin-mag').fill('12')
        self.page.locator('#mission-origin-dir').select_option('E')
        self.page.once('dialog', lambda d: d.accept())
        threshold.get_by_role('button', name='Usar coordenadas como origem').click()
        self.assertEqual(self.draft()['origin'], {'lat': -21.1, 'lon': -41.1, 'mag': 0, 'dir': 'W'})
        expect(self.page.locator('#mission-origin-mag')).to_have_value('12')
        expect(self.page.locator('#mission-origin-dir')).to_have_value('E')
        self.assertEqual(self.errors, [])

    def test_storage_failure_and_metadata_preserve_pending_origin(self):
        self.open_databases()
        before = self.draft()
        self.page.locator('#mission-origin-lat').fill('-25')
        self.page.locator('#mission-origin-lon').fill('-45')
        self.search()
        self.use('TST1 · Fictício ROTAER', 'Usar localidade')
        expect(self.page.locator('#mission-origin-lat')).to_have_value('-25')
        self.assertEqual(self.draft()['origin'], before['origin'])
        before = self.draft()
        self.search()
        self.page.evaluate('''()=>{const old=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k==='ivplanner-procedure-editor-procedimentos-v1')throw Error('Fictitious quota');return old.call(this,k,v)}}''')
        self.use('TST1 · Aeródromo Fictício AIXM', 'Usar localidade')
        expect(self.page.locator('#toast')).to_contain_text('Não foi possível salvar')
        self.assertEqual(self.draft(), before)
        expect(self.page.locator('#mission-origin-lat')).to_have_value('-25')
        self.assertEqual(self.errors, [])

    def test_local_catalog_is_module_specific_and_recovers_current_draft(self):
        self.open_databases()
        before = self.draft()
        catalog = []
        for module in ('procedimentos', 'ndb'):
            doc = self.fixture(); doc['module'] = module; doc['title'] = 'DESENHO ' + module
            catalog.append({'id': 'cat-' + module, 'module': module, 'icao': 'TST1', 'title': doc['title'], 'document': doc})
        self.page.evaluate('rows=>localStorage.setItem("ivplanner-custom-procedures-v1",JSON.stringify(rows))', catalog)
        self.search()
        expect(self.card('DESENHO ndb')).to_have_count(0)
        expect(self.card('DESENHO procedimentos')).to_contain_text('não comprova publicação')
        self.use('DESENHO procedimentos', 'Abrir desenho cadastrado', accept=False)
        self.assertEqual(self.draft(), before)
        self.use('DESENHO procedimentos', 'Abrir desenho cadastrado')
        self.assertEqual(self.draft()['catalogId'], 'cat-procedimentos')
        saved = self.page.evaluate('JSON.parse(localStorage.getItem("ivplanner-procedure-missions-procedimentos-v1"))')
        self.assertTrue(any(r.get('recovery') and r['document'] == before for r in saved))
        self.assertEqual(self.errors, [])

    def test_unavailable_aixm_retry_and_manual_editing_continue(self):
        self.open_databases(aixm=False)
        self.search()
        expect(self.page.locator('#mission-database-status')).to_contain_text('indisponível')
        expect(self.card('TST1 · Fictício ROTAER')).to_have_count(1)
        self.page.locator('#mission-local').fill('LOCAL MANUAL LIVRE')
        self.page.locator('#mission-name').click()
        self.assertEqual(self.draft()['mission']['local'], 'LOCAL MANUAL LIVRE')
        self.install_package(True)
        self.search()
        expect(self.card('TST1 · Aeródromo Fictício AIXM')).to_have_count(1)
        self.assertEqual(self.draft()['mission']['local'], 'LOCAL MANUAL LIVRE')
        self.assertEqual(self.errors, [])

    def test_corrupt_sources_empty_coordinates_unknown_units_are_preserved(self):
        self.open_databases('ndb')
        raw = '{invalid fictitious data'
        self.page.evaluate('raw=>localStorage.setItem("ivplanner-custom-localities-v1",raw)', raw)
        self.data['aids'][0].update({'lat': 0, 'lon': '', 'frequencyValue': '320', 'frequencyUom': 'UNKNOWN'})
        self.page.evaluate('rows=>localStorage.setItem("ivplanner-custom-aids-v1",JSON.stringify(rows))', self.data['aids'])
        before = self.draft()
        self.search()
        expect(self.page.locator('#mission-database-status')).to_contain_text('cadastro de localidades')
        manual = self.card('NDB · MTST · NDB Manual Fictício')
        expect(manual.get_by_role('button', name='Usar coordenadas como origem')).to_have_count(0)
        self.use('NDB · MTST · NDB Manual Fictício', 'Usar dados do NDB')
        self.assertEqual(self.draft()['mission']['ndbFrequency'], '')
        self.assertEqual(self.draft()['origin'], before['origin'])
        self.assertEqual(self.page.evaluate('localStorage.getItem("ivplanner-custom-localities-v1")'), raw)
        self.assertEqual(self.errors, [])

    def test_stale_async_result_never_overwrites_new_query_or_mission(self):
        self.open_databases(aixm=False)
        before = self.draft()
        # Delay only the optional AIXM request; other local requests continue normally.
        self.page.evaluate('''()=>{const realFetch=window.fetch;window.fetch=(...args)=>String(args[0]).includes('aixm-core.json')?new Promise(resolve=>{window.releaseTestFetch=()=>resolve(realFetch(...args));}):realFetch(...args);}''')
        self.page.locator('#mission-database-query').fill('TST1')
        self.page.locator('#mission-database-search').click()
        expect(self.page.locator('#mission-database-search')).to_be_disabled()
        self.page.locator('#mission-database-query').fill('INEXISTENTE')
        self.page.evaluate('window.releaseTestFetch()')
        self.page.wait_for_timeout(200)
        expect(self.page.locator('.database-card')).to_have_count(0)
        expect(self.page.locator('#mission-database-status')).to_contain_text('Busca alterada')
        self.assertEqual(self.draft(), before)
        self.assertEqual(self.errors, [])

    def test_offline_package_search_apply_reload_and_sources_unchanged(self):
        self.open_databases('ndb')
        key = 'ivplanner-custom-localities-v1'
        raw = self.page.evaluate('(k)=>localStorage.getItem(k)', key)
        cached = self.page.evaluate('''async()=>{const c=await caches.open('ivdata-package-test-mission');return (await c.match(IVAixm.coreUrl)).text()}''')
        self.context.set_offline(True)
        self.search()
        self.use('NDB · TST · NDB Fictício AIXM', 'Usar dados do NDB')
        expected = self.draft()
        self.assert_loaded(self.page.reload())
        self.assertEqual(self.draft(), expected)
        self.search()
        expect(self.card('TST1 · Aeródromo Fictício AIXM')).to_have_count(1)
        self.assertEqual(self.page.evaluate('(k)=>localStorage.getItem(k)', key), raw)
        self.assertEqual(self.page.evaluate('''async()=>{const c=await caches.open('ivdata-package-test-mission');return (await c.match(IVAixm.coreUrl)).text()}'''), cached)
        self.assertEqual(self.errors, [])

    def test_prefill_saved_mission_and_general_backup_restore(self):
        self.open_databases('ndb')
        self.search(); self.use('NDB · TST · NDB Fictício AIXM', 'Usar dados do NDB')
        self.search()
        runway = self.card('TST1 · RWY 09').filter(has_text='Coordenada THR')
        self.page.once('dialog', lambda d: d.accept())
        runway.get_by_role('button', name='Usar cabeceira', exact=True).click()
        self.button('Salvar missão').click()
        expected = self.draft()
        self.assert_loaded(self.page.goto(self.base + 'configuracoes/index.html'))
        self.dismiss_database_prompt()
        with self.page.expect_download() as download: self.page.locator('#backup-export').click()
        with open(download.value.path(), encoding='utf-8') as f: backup = json.load(f)
        with self.browser.new_context(service_workers='allow') as context:
            context.route('**/*', lambda route: route.continue_() if urlparse(route.request.url).netloc == urlparse(self.base).netloc else route.abort())
            page = context.new_page(); page.on('dialog', lambda d: d.accept())
            page.goto(self.base + 'configuracoes/index.html')
            if page.locator('#db-update-overlay').is_visible(): page.locator('#db-update-no').click()
            page.locator('#backup-file').set_input_files({'name': 'backup.json', 'mimeType': 'application/json', 'buffer': json.dumps(backup).encode()})
            expect(page.locator('#backup-preview')).to_be_visible(); page.locator('#backup-apply').click()
            expect(page.locator('#backup-status')).to_contain_text('Importação concluída')
            page.goto(self.base + 'inspecao/desenhar.html?modulo=ndb')
            restored = page.evaluate('JSON.parse(localStorage.getItem("ivplanner-procedure-editor-ndb-v1"))')
            self.assertEqual(restored, expected)
        self.assertEqual(self.errors, [])

    def test_viewports_safe_areas_touch_selection_and_no_horizontal_overflow(self):
        self.open_databases()
        self.search()
        session = self.context.new_cdp_session(self.page)
        session.send('Emulation.setSafeAreaInsetsOverride', {'insets': {'left': 44, 'right': 44, 'bottom': 34}})
        for width, height in ((390, 844), (844, 390), (820, 1180), (1180, 820)):
            self.page.set_viewport_size({'width': width, 'height': height})
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width + 1)
            for el in self.page.locator('#mission-database-results button').all():
                box = el.bounding_box()
                self.assertGreaterEqual(box['height'], 44)
                self.assertGreaterEqual(box['x'], 0)
                self.assertLessEqual(box['x'] + box['width'], width + 1)
        self.page.set_viewport_size({'width': 390, 'height': 844})
        session.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
        button = self.card('TST1 · Fictício ROTAER').get_by_role('button', name='Usar localidade', exact=True)
        button.scroll_into_view_if_needed(); box = button.bounding_box()
        self.page.once('dialog', lambda d: d.accept())
        session.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'id': 1, 'x': box['x'] + box['width']/2, 'y': box['y'] + box['height']/2}]})
        session.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        expect(self.page.locator('#mission-icao')).to_have_value('TST1')
        session.detach()
        self.assertEqual(self.errors, [])
