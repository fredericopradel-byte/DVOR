"""Offline cartography and regressions found in the visual audit."""
import hashlib
import json
import unittest
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer
from threading import Thread

from playwright.sync_api import expect
import test_e2e


class OfflineMapVisualTests(unittest.TestCase):
    setUpClass = classmethod(test_e2e.PlannerTests.setUpClass.__func__)
    setUp = test_e2e.PlannerTests.setUp
    assert_loaded = test_e2e.PlannerTests.assert_loaded
    dismiss_database_prompt = test_e2e.PlannerTests.dismiss_database_prompt

    def open(self, path):
        self.assert_loaded(self.page.goto(self.base + path))
        self.dismiss_database_prompt()

    def assert_map(self):
        expect(self.page.locator('#map')).to_have_attribute('data-basemap', 'ready')
        expect(self.page.locator('.leaflet-control-attribution')).to_contain_text('Natural Earth')
        canvas = self.page.locator('.leaflet-offlineBase-pane canvas')
        expect(canvas).to_have_count(1)
        pixels = canvas.evaluate('''el => {
            const rgba=el.getContext('2d').getImageData(0,0,el.width,el.height).data;
            let drawn=0; for(let i=3;i<rgba.length;i+=4) if(rgba[i]>0) drawn++;
            return drawn;
        }''')
        self.assertGreater(pixels, 1000, 'Cartography must actually render, not only load JSON')
        expect(self.page.locator('#map .leaflet-marker-icon')).to_have_count(12)

    def test_cartographic_source_integrity_and_coordinates(self):
        folder=test_e2e.ROOT/'meteorologia/basemap'
        raw=(folder/'countries-50m.geojson').read_bytes()
        metadata=json.loads((folder/'source.json').read_text())
        self.assertEqual(hashlib.sha256(raw).hexdigest(),metadata['outputSha256'])
        self.assertEqual(len(raw),metadata['bytes'])
        features=json.loads(raw)['features']
        self.assertEqual(len(features),241)
        brazil=next(f for f in features if f['id']=='076')
        self.assertEqual(brazil['properties']['name'],'Brazil')
        for f in features:
            g=f['geometry']
            polygons=[g['coordinates']] if g['type']=='Polygon' else g['coordinates']
            for polygon in polygons:
                for ring in polygon:
                    self.assertGreaterEqual(len(ring),4)
                    self.assertEqual(ring[0],ring[-1])
                    for a,b in zip(ring,ring[1:]):
                        if abs(a[1])<85 and abs(b[1])<85:
                            self.assertLessEqual(abs(a[0]-b[0]),180, 'Do not draw cross-world dateline edges')
                    for lon,lat in ring:
                        self.assertLessEqual(abs(lon),180)
                        self.assertLessEqual(abs(lat),90)

    def test_map_alignment_pan_zoom_and_saved_weather(self):
        self.page.set_viewport_size({'width':390,'height':844})
        self.open('meteorologia/index.html')
        self.assert_map()
        # Independent Web Mercator projection of the existing SBGL coordinate.
        error=self.page.evaluate('''() => {
            const host=document.getElementById('map'),r=host.getBoundingClientRect();
            const marker=[...host.querySelectorAll('.leaflet-marker-icon')].find(el=>el.textContent==='GL');
            const m=marker.getBoundingClientRect(),center=L.CRS.EPSG3857.latLngToPoint(L.latLng(-14.5,-52.5),4),station=L.CRS.EPSG3857.latLngToPoint(L.latLng(-22.81,-43.25),4);
            const origin=center.subtract(L.point(host.clientWidth/2,host.clientHeight/2)).round();
            return Math.hypot(m.x-r.x+9-(station.x-origin.x),m.y-r.y+32-(station.y-origin.y));
        }''')
        self.assertLess(error,2,'Airport position must match geographic projection')
        mapbox=self.page.locator('#map').bounding_box()
        pane=self.page.locator('.leaflet-map-pane')
        before=pane.get_attribute('style')
        self.page.mouse.move(mapbox['x']+120,mapbox['y']+200)
        self.page.mouse.down();self.page.mouse.move(mapbox['x']+180,mapbox['y']+240,steps=6);self.page.mouse.up()
        self.assertNotEqual(pane.get_attribute('style'),before)
        self.page.locator('.leaflet-control-zoom-in').click()
        self.page.wait_for_timeout(400)
        self.assert_map()
        saved={'code':'SBGL','saved':1760000000000,'metar':{'rawOb':'TESTE FICTICIO METAR','visib':10},'taf':{'rawTAF':'TESTE FICTICIO TAF'}}
        self.page.evaluate('(data)=>localStorage.setItem("iv-weather-last",JSON.stringify(data))',saved)
        self.page.reload()
        expect(self.page.locator('#metarRaw')).to_have_text(saved['metar']['rawOb'])
        expect(self.page.locator('#connection-status')).to_have_attribute('data-state','cached')
        self.assertEqual(self.page.evaluate('JSON.parse(localStorage.getItem("iv-weather-last"))'),saved)
        self.assertEqual(self.errors,[])

    def test_active_tab_labels_fit_small_iphone(self):
        self.page.set_viewport_size({'width':320,'height':568})
        for path in ('prevoo/legacy.html','prevoo/hawker.html','inspecao/papi.html','inspecao/desenhar.html?modulo=ndb'):
            self.open(path)
            for button in self.page.locator('button[data-page]').all():
                button.click();self.page.wait_for_timeout(600)
                self.assertTrue(self.page.locator('.iv-fixed-nav button.active').evaluate("el=>[...el.querySelectorAll('span')].every(e=>e.scrollWidth<=e.clientWidth+1)"),'Selected tab name must not be clipped')
        self.assertEqual(self.errors,[])

    def open_weather_without_network(self, interface_online):
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(test_e2e.Handler,directory=str(test_e2e.ROOT)))
        server.requests=[]
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        self.base=f'http://127.0.0.1:{server.server_port}/DVOR/'
        self.open('index.html')
        self.page.wait_for_function('navigator.serviceWorker.controller!==null',timeout=30000)
        self.context.set_offline(True)
        # CDP transport-offline does not consistently change navigator.onLine
        # across Chromium versions. Model the OS interface signal separately;
        # the real transport AND origin server remain unavailable below.
        self.context.add_init_script("Object.defineProperty(navigator, 'onLine', {get: () => " + ('true' if interface_online else 'false') + "})")
        server.shutdown();server.server_close();thread.join(timeout=5)
        before=len(server.requests)
        response=self.page.goto(self.base+'meteorologia/index.html')
        self.assertTrue(response.from_service_worker)
        self.assert_map()
        self.assertEqual(self.page.evaluate('navigator.onLine'),interface_online)
        return server,before

    def test_map_offline_without_previsiting_weather(self):
        server,before=self.open_weather_without_network(interface_online=False)
        expect(self.page.locator('#connection-status')).to_have_attribute('data-state','offline')
        self.page.locator('#radarBtn').click()
        expect(self.page.locator('#status')).to_contain_text('requer conexão')
        self.page.locator('#satelliteBtn').click()
        expect(self.page.locator('#status')).to_contain_text('requer conexão')
        self.page.reload();self.assert_map()
        self.assertEqual(len(server.requests),before)
        self.assertEqual(self.errors,[])

    def test_interface_online_does_not_claim_weather_connectivity(self):
        server,before=self.open_weather_without_network(interface_online=True)
        expect(self.page.locator('#connection-status')).to_have_attribute('data-state','unknown')
        self.page.locator('#icao').fill('SBGL')
        self.page.locator('#searchBtn').click()
        expect(self.page.locator('#connection-status')).to_have_attribute('data-state','unavailable')
        expect(self.page.locator('#status')).to_contain_text('Não foi possível obter dados')
        self.assertIsNone(self.page.evaluate('localStorage.getItem("iv-weather-last")'))
        self.page.evaluate("window.dispatchEvent(new Event('offline'))")
        expect(self.page.locator('#connection-status')).to_have_attribute('data-state','offline')
        self.page.evaluate("window.dispatchEvent(new Event('online'))")
        expect(self.page.locator('#connection-status')).to_have_attribute('data-state','unknown')
        self.page.reload();self.assert_map()
        expect(self.page.locator('#connection-status')).to_have_attribute('data-state','unknown')
        self.assertEqual(len(server.requests),before)
        self.assertEqual(self.errors,[])

    def upgrade_fixture(self, fail=False):
        old_worker=(test_e2e.ROOT/'tests/fixtures/sw-before-offline-map.js').read_bytes()
        class UpgradeHandler(test_e2e.Handler):
            def do_GET(handler):
                if handler.path=='/DVOR/sw.js' and handler.server.legacy:
                    handler.server.requests.append(handler.path)
                    handler.send_response(200);handler.send_header('Content-Type','text/javascript');handler.send_header('Cache-Control','no-store');handler.end_headers();handler.wfile.write(old_worker);return
                if handler.server.fail_new and handler.path.endswith('/vendor/leaflet/leaflet.css'):
                    handler.send_error(503);return
                try:super().do_GET()
                except (BrokenPipeError,ConnectionResetError):pass  # Worker aborts remaining requests after a deliberate 503.
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(UpgradeHandler,directory=str(test_e2e.ROOT)))
        server.requests=[];server.legacy=True;server.fail_new=False
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        self.base=f'http://127.0.0.1:{server.server_port}/DVOR/'
        self.open('index.html')
        self.page.wait_for_function('navigator.serviceWorker.controller!==null',timeout=30000)
        self.open('inspecao/desenhar.html?modulo=ndb')
        self.page.locator('#mission-name').fill('MISSAO FICTICIA ANTERIOR')
        self.page.get_by_role('button',name='Salvar missão',exact=True).click()
        saved=self.page.evaluate('localStorage.getItem("ivplanner-procedure-missions-ndb-v1")')
        # An isolated package store/cache sentinel proves activation preserves these too.
        self.page.evaluate("""async()=>{
            await new Promise((resolve,reject)=>{
                const req=indexedDB.open('ivplanner-package-manager-v1',1);
                req.onupgradeneeded=()=>{if(!req.result.objectStoreNames.contains('packages'))req.result.createObjectStore('packages',{keyPath:'id'})};
                req.onerror=()=>reject(req.error);req.onsuccess=()=>{const db=req.result,tx=db.transaction('packages','readwrite');tx.objectStore('packages').put({id:'test-package',version:'fixture',targets:[],activeCache:'ivdata-package-test-fixture'});tx.oncomplete=()=>{db.close();resolve()};tx.onerror=()=>reject(tx.error)};
            });
            const cache=await caches.open('ivdata-package-test-fixture');await cache.put(new URL('/DVOR/fixture.txt',location.origin).href,new Response('fictitious package'));
        }""")
        self.open('index.html')
        server.legacy=False;server.fail_new=fail
        state=self.page.evaluate("""async()=>{
            const reg=await navigator.serviceWorker.getRegistration();
            await reg.update();const worker=reg.installing||reg.waiting||reg.active;
            if(!worker)return 'no-worker';
            return await new Promise(resolve=>{
                function check(){if(['activated','redundant'].includes(worker.state))resolve(worker.state)}
                worker.addEventListener('statechange',check);check();
            });
        }""")
        self.assertEqual(state,'redundant' if fail else 'activated')
        self.assertEqual(self.page.evaluate('localStorage.getItem("ivplanner-procedure-missions-ndb-v1")'),saved)
        self.assertEqual(self.page.evaluate("""async()=>{
            return await new Promise(resolve=>{const req=indexedDB.open('ivplanner-package-manager-v1',1);req.onsuccess=()=>{const db=req.result,tx=db.transaction('packages','readonly'),get=tx.objectStore('packages').get('test-package');get.onsuccess=()=>{resolve(get.result.version);db.close()}}});
        }"""),'fixture')
        self.assertEqual(self.page.evaluate("async()=>{const c=await caches.open('ivdata-package-test-fixture');return (await c.match(new URL('/DVOR/fixture.txt',location.origin).href)).text()}"),'fictitious package')
        keys=self.page.evaluate('caches.keys()')
        self.assertIn('iv-planner-v94-procedure-missions-20261007' if fail else 'iv-planner-v107-apu-light-states-20261019',keys)
        if fail:
            # An incomplete candidate must not remove the old, activated shell.
            self.assertGreater(self.page.evaluate("async()=>{const c=await caches.open('iv-planner-v94-procedure-missions-20261007');return (await c.keys()).length}"),20)
        else:
            server.shutdown();server.server_close();thread.join(timeout=5)
            self.context.set_offline(True)
            response=self.page.goto(self.base+'meteorologia/index.html')
            self.assertTrue(response.from_service_worker);self.assert_map()
        self.assertEqual(self.errors,[])

    def test_successful_update_preserves_missions_and_package_storage(self):
        self.upgrade_fixture()

    def test_incomplete_update_preserves_previous_active_cache_and_data(self):
        self.upgrade_fixture(fail=True)

    def test_dock_fonts_and_modals_in_touch_viewports(self):
        paths=('inspecao/dvor-vor/index.html','inspecao/ils.html','inspecao/papi.html','inspecao/radar.html','prevoo/legacy.html','prevoo/hawker.html','inspecao/desenhar.html?modulo=ndb')
        for width,height in ((320,568),(390,844),(844,390),(820,1180)):
            self.page.set_viewport_size({'width':width,'height':height})
            for path in paths:
                with self.subTest(path=path,viewport=(width,height)):
                    self.open(path)
                    self.page.wait_for_timeout(200)
                    a=self.page.locator('.iv-fixed-nav').bounding_box();b=self.page.locator('.ivg-toggle').bounding_box()
                    self.assertLessEqual(a['x']+a['width'],b['x'])
                    self.assertEqual(a['height'],62)
                    self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                    if '/prevoo/' not in '/'+path and 'desenhar' not in path:
                        small=self.page.evaluate('''()=>[...document.querySelectorAll('input:not([type=checkbox]):not([type=radio]):not([type=hidden]),select,textarea')].filter(el=>el.getClientRects().length&&parseFloat(getComputedStyle(el).fontSize)<16).map(el=>el.id)''')
                        self.assertEqual(small,[])
            session=self.context.new_cdp_session(self.page)
            session.send('Emulation.setSafeAreaInsetsOverride',{'insets':{'left':44,'right':44,'bottom':34,'top':0}})
            for path in paths:
                self.open(path)
                a=self.page.locator('.iv-fixed-nav').bounding_box()
                self.assertGreaterEqual(a['x'],44)
                self.assertLessEqual(a['y']+a['height'],height-34)
            session.send('Emulation.setSafeAreaInsetsOverride',{'insets':{'left':0,'right':0,'bottom':0,'top':0}});session.detach()
        self.page.set_viewport_size({'width':390,'height':844})
        for path in ('localidades/aerodromos.html','localidades/auxilios.html'):
            self.open(path)
            self.page.locator('#new').click()
            expect(self.page.locator('.modal.open')).to_be_visible()
            expect(self.page.locator('.ivg-toggle')).to_be_hidden()
            self.assertEqual(self.page.evaluate('getComputedStyle(document.body,"::after").content'),'none')
            self.page.locator('.modal.open .close').click()
            expect(self.page.locator('.ivg-toggle')).to_be_visible()
        self.open('inspecao/radar.html')
        self.page.locator('[data-page=rose]').click()
        self.page.locator('.iv-help-button').click()
        expect(self.page.locator('#iv-help-title')).to_have_text('Mapa Radar')
        self.assertEqual(self.errors,[])
