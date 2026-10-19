"""Testes funcionais isolados; executar: python -m unittest discover -s tests -v."""

import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import unittest
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PAGES = (
    "", "index.html", "prevoo/", "prevoo/index.html",
    "prevoo/legacy.html", "prevoo/hawker.html",
    "inspecao/", "inspecao/index.html", "inspecao/dvor-vor/",
    "inspecao/dvor-vor/index.html", "inspecao/papi.html",
    "inspecao/ils.html", "inspecao/radar.html",
    "inspecao/desenhar.html?modulo=ndb",
    "inspecao/desenhar.html?modulo=procedimentos",
    "localidades/", "localidades/index.html", "localidades/aerodromos.html",
    "localidades/auxilios.html", "localidades/procedimentos.html",
    "meteorologia/", "meteorologia/index.html",
    "configuracoes/", "configuracoes/index.html", "configuracoes/bases.html",
)
AREAS = (
    ("preflight", "prevoo/index.html"),
    ("inspection", "inspecao/index.html"),
    ("weather", "meteorologia/index.html"),
    ("localities", "localidades/index.html"),
    ("settings", "configuracoes/index.html"),
    ("home", "index.html"),
)


class Handler(SimpleHTTPRequestHandler):
    """Servidor somente de leitura, no loopback e sob o prefixo do Pages."""

    def do_GET(self):
        self.server.requests.append(self.path)
        if not self.path.startswith("/DVOR/"):
            self.send_error(404)
            return
        self.path = self.path[len("/DVOR"):]
        super().do_GET()

    def log_message(self, *_args):
        pass


class PlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(Handler, directory=str(ROOT))
        )
        cls.server.requests = []
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls.server.server_close)
        cls.addClassCleanup(cls.server.shutdown)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}/DVOR/"
        cls.pw = sync_playwright().start()
        cls.addClassCleanup(cls.pw.stop)
        # O caminho pode ser omitido para usar o Chromium instalado pelo Playwright.
        executable = os.environ.get("IV_TEST_CHROMIUM")
        cls.browser = cls.pw.chromium.launch(
            executable_path=executable, headless=True
        )
        cls.addClassCleanup(cls.browser.close)
        print(f"\nChromium {cls.browser.version}; origem temporária {cls.base}")

    def setUp(self):
        self.context = self.browser.new_context(
            viewport={"width": 1024, "height": 768}, service_workers="allow"
        )
        self.addCleanup(self.context.close)
        self.errors = []
        # Serviços externos indisponíveis: nenhuma consulta usa dados reais ou rede externa.
        self.context.route(
            "**/*",
            lambda route: route.continue_()
            if urlparse(route.request.url).netloc == urlparse(self.base).netloc
            else route.abort(),
        )
        self.page = self.context.new_page()
        self.page.set_default_timeout(10000)
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.context.on("weberror", lambda error: self.errors.append(str(error.error)))

    def assert_loaded(self, response):
        self.assertIsNotNone(response)
        self.assertEqual(response.status, 200)
        expect(self.page.locator(".ivg-toggle")).to_be_visible()
        expect(self.page.locator(".ivg-link[aria-current='page']")).to_have_count(1)
        self.assertTrue(self.page.title().strip())
        startup = self.page.locator('#iv-startup')
        if startup.is_visible():
            startup.locator('.iv-startup-skip').click()
        # Janela explícita para callbacks de inicialização; não afirma ausência futura de erros.
        self.page.wait_for_timeout(300)
        self.assertEqual(self.errors, [], "Exceções JavaScript")

    def dismiss_database_prompt(self):
        startup = self.page.locator('#iv-startup')
        if startup.is_visible():
            startup.locator('.iv-startup-skip').click()
            self.page.wait_for_timeout(200)
        # Interação normal: recusa a instalação de bases no perfil fictício.
        prompt = self.page.locator("#db-update-overlay")
        if prompt.is_visible():
            self.page.locator("#db-update-no").click()
            expect(prompt).to_be_hidden()

    def test_carregamento_paginas_principais(self):
        for path in PAGES:
            with self.subTest(pagina=path or "/"):
                self.assert_loaded(self.page.goto(self.base + path, wait_until="load"))

    def test_persistencia_missao_dvor(self):
        self.assert_loaded(self.page.goto(self.base + "inspecao/dvor-vor/index.html"))
        fields = {
            "mission-title": "TESTE FICTICIO DVOR 001",
            "mission-name": "AUXILIO FICTICIO",
            "mission-date": "2026-01-15",
            "station-lat-deg": "10", "station-lat-min": "30.00",
            "station-lon-deg": "050", "station-lon-min": "15.00",
            "station-magvar": "12.5",
        }
        for identifier, value in fields.items():
            self.page.locator("#" + identifier).fill(value)
        self.page.locator("#save-mission").click()
        button = self.page.locator(".saved-mission-open").filter(
            has_text=fields["mission-title"]
        )
        expect(button).to_have_count(1)
        saved = self.page.evaluate(
            "JSON.parse(localStorage.getItem('iv-planner-saved-missions-v1'))"
        )
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["metadata"]["missionTitle"], fields["mission-title"])
        self.assert_loaded(self.page.reload(wait_until="load"))
        for identifier, value in fields.items():
            # Coordenadas são normalizadas pelo aplicativo ao reabrir.
            if identifier not in ("station-lat-min", "station-lon-deg", "station-lon-min"):
                expect(self.page.locator("#" + identifier)).to_have_value(value)
        self.assertEqual(self.page.evaluate(
            "JSON.parse(localStorage.getItem('iv-planner-saved-missions-v1'))"
        ), saved)
        # Prova que a biblioteca reabre a missão, sem depender apenas do rascunho automático.
        self.page.on("dialog", lambda dialog: dialog.accept())
        self.page.locator("#new-mission").click()
        expect(self.page.locator("#mission-title")).to_have_value("")
        button.click()
        expect(self.page.locator("#mission-title")).to_have_value(fields["mission-title"])
        expect(self.page.locator("#mission-name")).to_have_value(fields["mission-name"])
        metadata = self.page.evaluate(
            "JSON.parse(localStorage.getItem('geiv-dvor-manual-offline-v1')).metadata"
        )
        self.assertEqual(metadata, saved[0]["metadata"])
        self.assertEqual(self.errors, [])

    def test_navegacao_entre_areas(self):
        self.assert_loaded(self.page.goto(self.base + "index.html"))
        for area, path in AREAS:
            with self.subTest(area=area):
                self.dismiss_database_prompt()
                self.page.locator(".ivg-toggle").click()
                with self.page.expect_navigation(wait_until="load") as navigation:
                    self.page.locator(f".ivg-link[data-ivg-area='{area}']").click()
                self.assertEqual(self.page.url, self.base + path)
                self.assert_loaded(navigation.value)
                expect(self.page.locator(
                    f".ivg-link[data-ivg-area='{area}']"
                )).to_have_attribute("aria-current", "page")

    def test_offline_apos_ativacao_service_worker(self):
        # Origem exclusiva: desligar o servidor comprova também a ausência de rede
        # no worker, que nem todo Chromium submete a context.set_offline().
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(Handler, directory=str(ROOT))
        )
        server.requests = []
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.base = f"http://127.0.0.1:{server.server_port}/DVOR/"
        self.assert_loaded(self.page.goto(self.base + "index.html"))
        self.page.wait_for_function(
            "navigator.serviceWorker.controller !== null", timeout=30000
        )
        worker = self.page.evaluate("""async () => {
            const registration = await navigator.serviceWorker.ready;
            return {state: registration.active.state, scope: registration.scope,
                script: navigator.serviceWorker.controller.scriptURL};
        }""")
        self.assertEqual(worker, {
            "state": "activated", "scope": self.base, "script": self.base + "sw.js"
        })
        # Não visita/preaquece as páginas essenciais: elas devem vir do APP_SHELL real.
        self.context.set_offline(True)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        before = len(server.requests)
        for path in PAGES:
            with self.subTest(pagina_offline=path or "/"):
                response = self.page.goto(self.base + path, wait_until="load")
                self.assert_loaded(response)
                self.assertTrue(response.from_service_worker)
                response = self.page.reload(wait_until="load")
                self.assert_loaded(response)
                self.assertTrue(response.from_service_worker)
        self.assertEqual(len(server.requests), before,
                         "O servidor recebeu requisições durante o teste offline")


if __name__ == "__main__":
    unittest.main(verbosity=2)
