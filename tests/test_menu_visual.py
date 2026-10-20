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
                        tile=card.locator('.icon')
                        tile_box=tile.bounding_box()
                        self.assertEqual(tile_box['width'],54)
                        self.assertEqual(tile_box['height'],54)
                        tile_style=tile.evaluate("e=>{const s=getComputedStyle(e);return {background:s.backgroundColor,radius:s.borderRadius,border:s.borderTopWidth,color:s.borderTopColor}}")
                        self.assertEqual(tile_style,{'background':'rgb(28, 31, 33)','radius':'16px','border':'1px','color':'rgba(255, 255, 255, 0.12)'})
                        for glyph in tile.locator('svg, img').all():
                            box=glyph.bounding_box()
                            self.assertGreaterEqual(box['x'],tile_box['x']+1)
                            self.assertGreaterEqual(box['y'],tile_box['y']+1)
                            self.assertLessEqual(box['x']+box['width'],tile_box['x']+53)
                            self.assertLessEqual(box['y']+box['height'],tile_box['y']+53)
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

    def test_menu_tiles_with_legacy_shared_css_cached_offline(self):
        self.open('index.html')
        self.page.evaluate('async()=>{await navigator.serviceWorker.ready}')
        self.page.wait_for_function('navigator.serviceWorker.controller!==null')
        self.context.set_offline(True)
        # Reproduce an installed PWA keeping the former transparent icon rule.
        # Only this temporary browser context's application caches are changed.
        legacy=test_e2e.ROOT.joinpath('page-ui.css').read_text().split('/* Page links share')[0]+'''
.iv-page-menu .icon:has([data-silhouette]){width:64px;height:54px;border:0;background:transparent;border-radius:0}
.iv-page-menu .icon svg[data-silhouette]{display:block;width:64px;height:48px}
'''
        self.page.evaluate('''async css=>{
            for(const name of await caches.keys()){
                if(!name.startsWith('iv-planner-'))continue;
                const cache=await caches.open(name);
                for(const request of await cache.keys()){
                    if(new URL(request.url).pathname.endsWith('/page-ui.css'))
                        await cache.put(request,new Response(css,{headers:{'Content-Type':'text/css'}}));
                }
            }
        }''',legacy)
        response=self.page.goto(self.base+'inspecao/index.html')
        self.assertTrue(response.from_service_worker)
        self.assert_loaded(response)
        self.assertTrue(self.page.evaluate('''()=>[...document.styleSheets].some(sheet=>
            sheet.href?.includes('/page-ui.css')&&[...sheet.cssRules].some(rule=>
                rule.selectorText==='.iv-page-menu .icon:has([data-silhouette])'))'''))
        for tile in self.page.locator('a.card .icon').all():
            self.assertEqual(tile.bounding_box()['width'],54)
            self.assertEqual(tile.bounding_box()['height'],54)
            self.assertEqual(tile.evaluate('e=>getComputedStyle(e).backgroundColor'),'rgb(28, 31, 33)')
            self.assertEqual(tile.locator('svg').bounding_box()['width'],38)
        self.assertFalse(self.errors)
