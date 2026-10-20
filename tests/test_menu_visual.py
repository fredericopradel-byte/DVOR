"""Menu palette, local silhouettes and navigation in isolated Chromium contexts."""
import unittest
from playwright.sync_api import expect
import test_e2e


class MenuVisualTests(unittest.TestCase):
    setUpClass = classmethod(test_e2e.PlannerTests.setUpClass.__func__)
    setUp = test_e2e.PlannerTests.setUp
    assert_loaded = test_e2e.PlannerTests.assert_loaded
    dismiss_database_prompt = test_e2e.PlannerTests.dismiss_database_prompt

    def open(self, path):
        self.assert_loaded(self.page.goto(self.base + path))
        self.dismiss_database_prompt()

    def assert_brand_resolution(self, page):
        # Decode the actual SVG image source; cover retina iPhone/iPad density.
        size=page.evaluate("""async()=>{const source=document.querySelector('.mark image');const image=new Image();image.src=source.href.baseVal;await image.decode();return [image.naturalWidth,image.naturalHeight]}""")
        self.assertEqual(size,[1448,1086])
        self.assertEqual(page.locator('.mark svg').get_attribute('viewBox'),'441 260 566 566')

    def test_menu_palette_and_bounds_on_phone_tablet_and_landscape(self):
        for width,height in [(320,568),(390,844),(844,390),(820,1180),(1180,820)]:
            self.page.set_viewport_size({'width':width,'height':height})
            for path in ['index.html','prevoo/index.html','inspecao/index.html','localidades/index.html','configuracoes/index.html']:
                with self.subTest(viewport=(width,height),path=path):
                    self.open(path)
                    self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width)
                    for card in self.page.locator('a.card').all():
                        styles=card.evaluate('''e=>({background:getComputedStyle(e).backgroundImage,border:getComputedStyle(e).borderColor,icon:getComputedStyle(e.querySelector('.icon')).color,arrow:getComputedStyle(e.querySelector('.arrow')).color})''')
                        self.assertNotIn('7, 141, 209',styles['background'])
                        self.assertEqual(styles['border'],'rgb(77, 83, 89)')
                        self.assertEqual(styles['icon'],'rgb(10, 164, 239)')
                        self.assertEqual(styles['arrow'],'rgb(10, 164, 239)')
                        b=card.bounding_box();self.assertGreaterEqual(b['height'],44)
                        pieces=[card.locator(s).bounding_box() for s in ['.icon','.copy','.arrow']]
                        for a,b in zip(pieces,pieces[1:]):
                            if min(a['y']+a['height'],b['y']+b['height'])>max(a['y'],b['y']):
                                self.assertLessEqual(a['x']+a['width'],b['x']+1)
        self.assertFalse(self.errors)

    def test_silhouettes_links_and_brand_without_javascript(self):
        context=self.browser.new_context(java_script_enabled=False,viewport={'width':390,'height':844})
        self.addCleanup(context.close)
        page=context.new_page();page.goto(self.base+'index.html')
        self.assert_brand_resolution(page)
        self.assertEqual(page.locator('.wordmark').inner_text(),'IV-PLANNER')
        page.locator('a.card[href="inspecao/"]').click()
        cards=page.locator('a.card');self.assertEqual(cards.count(),7)
        routes=[c.get_attribute('href') for c in cards.all()]
        self.assertEqual(len(set(page.locator('[data-silhouette]').evaluate_all('els=>els.map(e=>e.dataset.silhouette)'))),7)
        for route in routes:
            page.goto(self.base+'inspecao/index.html')
            page.locator('a.card[href="'+route+'"]').click()
            self.assertNotIn('404',page.title())
            self.assertTrue(page.locator('body').inner_text().strip())

    def test_brand_and_inspection_navigation_offline(self):
        self.open('index.html')
        self.page.evaluate('async()=>{await navigator.serviceWorker.ready}')
        self.page.wait_for_function('navigator.serviceWorker.controller!==null')
        self.context.set_offline(True)
        # CDP blocks transport independently of navigator.onLine. A cached
        # catalog may still offer optional databases when the OS reports online.
        self.page.add_init_script("Object.defineProperty(navigator,'onLine',{get:()=>new URL(location.href).searchParams.get('offline-interface')==='online'})")
        for signal in ['offline','online']:
            with self.subTest(interface=signal):
                response=self.page.goto(self.base+'index.html?offline-interface='+signal)
                self.assertTrue(response.from_service_worker)
                self.assert_loaded(response)
                self.assertEqual(self.page.evaluate('navigator.onLine'),signal=='online')
                if signal=='online':
                    expect(self.page.locator('#db-update-overlay')).to_be_visible()
                self.dismiss_database_prompt()
                expect(self.page.locator('#db-update-overlay')).to_be_hidden()
                self.assertFalse(self.page.locator('main').evaluate('e=>e.inert'))
                self.assertFalse(self.page.evaluate("async()=>{try{await fetch('./menu-probe-not-cached.txt',{cache:'no-store'});return true}catch{return false}}"))
                self.assert_brand_resolution(self.page)
                self.page.locator('a.card[href="inspecao/"]').click()
                self.assertEqual(self.page.locator('[data-silhouette]').count(),7)
                self.assertTrue(self.page.evaluate("async()=>{const r=await fetch('../assets/branding/approved-icon.png');const b=new Uint8Array(await r.arrayBuffer());return r.ok&&b[0]===137&&b[1]===80&&b[2]===78&&b[3]===71}"))
                self.page.locator('a.card[href="papi.html"]').click()
                self.assertIn('papi.html',self.page.url)
        self.assertFalse(self.errors)
