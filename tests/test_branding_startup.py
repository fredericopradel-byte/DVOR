"""Recursos originais, instalação PWA e inicialização sem dependência de rede."""
import hashlib
import json
from pathlib import Path
import unittest
from functools import partial
from http.server import ThreadingHTTPServer
from threading import Thread

from PIL import Image
import test_e2e

ROOT=Path(__file__).resolve().parents[1]


class BrandingAssetTests(unittest.TestCase):
    def test_approved_originals_and_animation_timing_are_preserved(self):
        folder=ROOT/'assets/branding';meta=json.loads((folder/'sources.json').read_text())
        for name,digest in meta['sha256'].items():
            self.assertEqual(hashlib.sha256((folder/name).read_bytes()).hexdigest(),digest)
        with Image.open(folder/'approved-icon.png') as im:self.assertEqual(im.size,(1448,1086))
        with Image.open(folder/'approved-apu.gif') as im:
            self.assertEqual(im.n_frames,24);durations=[]
            for i in range(im.n_frames):im.seek(i);durations.append(im.info['duration'])
            self.assertEqual(sum(durations),8100)
            self.assertEqual(durations,meta['animation']['frameDurationsMs'])

    def test_manifest_and_ios_icons_have_correct_dimensions_and_safe_symbol(self):
        for path in [ROOT/'manifest.webmanifest',ROOT/'inspecao/dvor-vor/manifest.webmanifest']:
            data=json.loads(path.read_text());self.assertEqual(data['start_url'],'./')
            self.assertEqual({icon['purpose'] for icon in data['icons']},{'any','maskable'})
            for icon in data['icons']:
                with Image.open(path.parent/icon['src']) as im:
                    self.assertEqual(f'{im.width}x{im.height}',icon['sizes']);self.assertEqual(im.mode,'RGB')
                    if icon['purpose']=='maskable':
                        luminous=[(x,y) for y in range(im.height) for x in range(im.width) if (lambda c:c[2]>150 and c[2]>c[0]*1.5)(im.getpixel((x,y)))]
                        self.assertTrue(luminous)
                        self.assertTrue(all((x-256)**2+(y-256)**2<(.4*512)**2 for x,y in luminous))
        with Image.open(ROOT/'apple-touch-icon.png') as im:self.assertEqual(im.size,(180,180))
        for size in [192,512]:
            self.assertEqual((ROOT/f'icon-{size}.png').read_bytes(),(ROOT/f'inspecao/dvor-vor/icon-{size}.png').read_bytes())


class StartupTests(unittest.TestCase):
    setUpClass=classmethod(test_e2e.PlannerTests.setUpClass.__func__)

    def setUp(self):
        test_e2e.PlannerTests.setUp(self)
        self.context.route('**/data/package-catalog.json*',lambda route:route.fulfill(json={'schemaVersion':1,'packages':[]}))
        self.page.add_init_script("window.startupStates=[];document.addEventListener('iv-startup-state',e=>startupStates.push(e.detail.state));")

    def open(self):self.page.goto(self.base+'index.html')

    def settled(self):
        self.page.wait_for_function('document.querySelector("#iv-startup").hidden||document.querySelector("#iv-startup").dataset.state==="fault"')

    def test_normal_checks_reach_ready_and_do_not_repeat_on_internal_navigation(self):
        self.open();self.settled()
        self.assertEqual(self.page.evaluate('startupStates'),['energizing','self-test','ready'])
        self.assertFalse(self.page.locator('main').evaluate('e=>e.inert'))
        self.assertFalse(self.errors)
        self.page.locator('a.card[href="inspecao/"]').click();self.page.go_back()
        self.assertTrue(self.page.locator('#iv-startup').is_hidden())

    def test_installed_start_url_directory_reaches_ready(self):
        self.page.goto(self.base)
        self.settled()
        self.assertEqual(self.page.evaluate('startupStates'),['energizing','self-test','ready'])
        self.assertEqual(self.page.locator('.iv-help-button').count(),1)
        self.assertFalse(self.page.locator('main').evaluate('e=>e.inert'))
        self.assertFalse(self.errors)

    def test_three_cycles_branding_and_square_switches(self):
        self.open()
        self.page.wait_for_function('document.querySelector("#iv-startup").dataset.state==="self-test"')
        self.assertEqual(self.page.locator('.apu-heading').inner_text(),'IV-PLANNER')
        self.assertEqual(self.page.locator('.apu-brand').get_attribute('src'),'icon-192.png')
        self.assertEqual(self.page.locator('.apu-indicator>span').count(),0)
        self.assertEqual(self.page.locator('.apu-green').evaluate('e=>getComputedStyle(e).animationDuration'),'0.75s')
        for width,height in [(320,568),(390,844),(844,390),(820,1180),(1440,900)]:
            self.page.set_viewport_size({'width':width,'height':height})
            for button in self.page.locator('.apu-switch').all():
                b=button.bounding_box()
                self.assertAlmostEqual(b['width'],b['height'],delta=1)
        self.settled()
        self.assertGreaterEqual(self.page.evaluate('performance.now()'),2250)
        self.assertIn('ready',self.page.evaluate('startupStates'))

    def test_green_cycles_with_white_fixed_and_amber_red_off(self):
        self.page.add_init_script("(()=>{const original=fetch;window.fetch=async (...a)=>{if(String(a[0]).endsWith('page-ui.css'))await new Promise(r=>setTimeout(r,350));return original(...a)}})()")
        self.open();self.page.wait_for_function('document.querySelector("#iv-startup").dataset.state==="self-test"')
        self.assertEqual(self.page.locator('.apu-amber').evaluate('e=>getComputedStyle(e).getPropertyValue("--light").trim()'),'#60421e')
        self.assertEqual(self.page.locator('.apu-green').evaluate('e=>getComputedStyle(e).getPropertyValue("--light").trim()'),'#43df70')
        self.assertEqual(self.page.locator('.apu-red').evaluate('e=>getComputedStyle(e).getPropertyValue("--light").trim()'),'#68272d')
        self.settled();self.assertIn('ready',self.page.evaluate('startupStates'))
        self.assertNotIn('fault',self.page.evaluate('startupStates'))

    def test_warning_appears_only_after_green_cycles_and_lamps_are_exclusive(self):
        self.open()
        self.page.evaluate("document.dispatchEvent(new CustomEvent('iv-startup-warning',{detail:{message:'Atualização disponível'}}))")
        self.assertEqual(self.page.locator('#iv-startup').get_attribute('data-state'),'self-test')
        self.assertEqual(self.page.locator('.apu-white').evaluate('e=>getComputedStyle(e).animationName'),'none')
        self.assertEqual(self.page.locator('.apu-amber').evaluate('e=>getComputedStyle(e).getPropertyValue("--light").trim()'),'#60421e')
        self.page.wait_for_function('document.querySelector("#iv-startup").dataset.state==="caution"')
        self.assertEqual(self.page.locator('.apu-green').evaluate('e=>getComputedStyle(e).getPropertyValue("--light").trim()'),'#18452c')
        self.assertEqual(self.page.locator('.apu-amber').evaluate('e=>getComputedStyle(e).getPropertyValue("--light").trim()'),'#ffc267')
        self.assertEqual(self.page.locator('.apu-amber').evaluate('e=>getComputedStyle(e).animationName'),'none')
        self.assertEqual(self.page.locator('.apu-red').evaluate('e=>getComputedStyle(e).getPropertyValue("--light").trim()'),'#68272d')
        self.settled()
        self.assertNotIn('ready',self.page.evaluate('startupStates'))

    def test_missing_essential_resource_fault_and_retry_recover_without_data_loss(self):
        self.context.route('**/page-ui.js*',lambda route:route.abort())
        self.open();self.settled()
        self.assertEqual(self.page.locator('#iv-startup').get_attribute('data-state'),'fault')
        self.assertIn('page-ui.js',self.page.locator('#iv-startup-description').inner_text())
        self.assertEqual(self.page.locator('.apu-red').evaluate('e=>getComputedStyle(e).getPropertyValue("--light").trim()'),'#ff666d')
        for width,height in [(320,568),(568,320)]:
            self.page.set_viewport_size({'width':width,'height':height})
            self.page.add_style_tag(content='#iv-startup{padding:'+('0 44px 21px' if width>height else '44px 16px 34px')+'}')
            for selector in ['.apu-brand','.apu-panel','.apu-actions']:
                b=self.page.locator(selector).bounding_box();self.assertIsNotNone(b)
                self.assertGreaterEqual(b['y'],0);self.assertLessEqual(b['y']+b['height'],height+1)
        self.page.evaluate('localStorage.setItem("ivplanner-legacy-v1","rascunho histórico preservado")')
        self.context.unroute('**/page-ui.js*')
        with self.page.expect_navigation():self.page.locator('.iv-startup-retry').click()
        self.settled();self.assertIn('ready',self.page.evaluate('startupStates'))
        self.assertEqual(self.page.evaluate('localStorage.getItem("ivplanner-legacy-v1")'),'rascunho histórico preservado')

    def test_pending_resource_times_out_with_actions_and_no_false_ready(self):
        self.page.add_init_script("(()=>{const original=fetch;window.fetch=(...a)=>String(a[0]).endsWith('page-ui.css')?new Promise(()=>{}):original(...a)})()")
        self.open();self.page.wait_for_function('document.querySelector("#iv-startup").dataset.state==="fault"',timeout=4200)
        self.assertNotIn('ready',self.page.evaluate('startupStates'))
        self.assertTrue(self.page.locator('.iv-startup-retry').is_visible())
        self.page.locator('.iv-startup-skip').click()
        self.assertFalse(self.page.locator('main').evaluate('e=>e.inert'))

    def test_offline_and_unavailable_optional_services_are_not_critical(self):
        # Isolar a origem para desligá-la sem afetar os outros testes da classe.
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(test_e2e.Handler,directory=str(ROOT)))
        server.requests=[]
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        self.base=f'http://127.0.0.1:{server.server_port}/DVOR/'
        self.open();self.settled()
        self.page.evaluate('async()=>{await navigator.serviceWorker.ready}')
        self.page.wait_for_function('navigator.serviceWorker.controller!==null')
        self.context.set_offline(True)
        # O transporte CDP e o sinal de interface do SO são independentes:
        # Chromium 151 pode manter onLine=true com o transporte já bloqueado.
        self.page.add_init_script("Object.defineProperty(navigator,'onLine',{get:()=>new URL(location.href).searchParams.get('interface')==='online'})")
        server.shutdown();server.server_close();thread.join(timeout=5)
        before=len(server.requests)
        for reported_online in [False,True]:
            with self.subTest(reported_online=reported_online):
                self.page.evaluate('sessionStorage.removeItem("ivplanner-startup-verified-v2")')
                signal='online' if reported_online else 'offline'
                response=self.page.goto(self.base+f'index.html?interface={signal}',referer='https://example.invalid/')
                self.assertTrue(response.from_service_worker)
                self.settled()
                self.assertEqual(self.page.evaluate('navigator.onLine'),reported_online)
                # Uma URL não instalada não pode ser alcançada com a origem desligada.
                self.assertFalse(self.page.evaluate("async()=>{try{await fetch('./offline-probe-not-cached.txt',{cache:'no-store'});return true}catch{return false}}"))
                self.assertIn('ready',self.page.evaluate('startupStates'))
                self.assertNotIn('fault',self.page.evaluate('startupStates'))
                for icon in ['icon-192.png','icon-512.png','icon-maskable-512.png','apple-touch-icon.png']:
                    self.assertTrue(self.page.evaluate('async p=>(await fetch(p)).ok',icon))
                self.assertEqual(len(server.requests),before)
        self.assertFalse(self.errors)

    def test_storage_failure_is_diagnosed_and_javascript_disabled_has_menu(self):
        self.page.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw Error('blocked')}})")
        self.open();self.settled()
        self.assertEqual(self.page.locator('#iv-startup').get_attribute('data-state'),'fault')
        self.assertIn('armazenamento',self.page.locator('#iv-startup-description').inner_text())
        self.page.keyboard.press('Escape');self.assertTrue(self.page.locator('#iv-startup').is_hidden())
        context=self.browser.new_context(java_script_enabled=False)
        try:
            page=context.new_page();page.goto(self.base+'index.html');self.assertTrue(page.locator('#iv-startup').is_hidden())
            page.locator('a.card[href="inspecao/"]').click();self.assertTrue(page.url.endswith('/inspecao/'))
        finally:context.close()

    def test_reduced_motion_safe_areas_and_diagonal_lights(self):
        self.page.emulate_media(reduced_motion='reduce')
        self.page.add_init_script("(()=>{const original=fetch;const gate=new Promise(r=>window.releaseStartupVisualCheck=r);window.fetch=async (...a)=>{if(String(a[0]).endsWith('page-ui.css'))await gate;return original(...a)}})()")
        for width,height in [(320,568),(390,844),(844,390),(568,320),(820,1180),(1180,820)]:
            self.page.goto(self.base+'inspecao/index.html')
            self.page.evaluate('sessionStorage.removeItem("ivplanner-startup-verified-v2")')
            self.page.set_viewport_size({'width':width,'height':height})
            self.page.goto(self.base+'index.html',referer='https://example.invalid/')
            self.page.add_style_tag(content='#iv-startup{padding:'+('0 44px 21px' if width>height else '44px 16px 34px')+'}')
            for selector in ['.apu-panel','.apu-actions']:
                b=self.page.locator(selector).bounding_box();self.assertIsNotNone(b)
                self.assertGreaterEqual(b['x'],0);self.assertGreaterEqual(b['y'],0)
                self.assertLessEqual(b['x']+b['width'],width+1);self.assertLessEqual(b['y']+b['height'],height+1)
            for lamp in self.page.locator('.apu-lamp').all():
                self.assertIn('repeating-linear-gradient',lamp.evaluate('e=>getComputedStyle(e).backgroundImage'))
            self.page.evaluate('releaseStartupVisualCheck()')
            self.settled();self.assertIn('ready',self.page.evaluate('startupStates'))

    def test_database_offer_waits_for_self_test_and_normal_actions_remain(self):
        self.context.unroute('**/data/package-catalog.json*')
        self.page.add_init_script("(()=>{const original=fetch;window.fetch=async (...a)=>{if(String(a[0]).endsWith('page-ui.css'))await new Promise(r=>setTimeout(r,250));return original(...a)}})()")
        self.open();self.assertTrue(self.page.locator('#db-update-overlay').is_hidden())
        self.settled();self.page.wait_for_function('!document.querySelector("#db-update-overlay").hidden')
        self.assertIn('caution',self.page.evaluate('startupStates'))
        self.page.locator('#db-update-no').click();self.assertFalse(self.page.locator('main').evaluate('e=>e.inert'))
