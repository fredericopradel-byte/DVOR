"""PR 1: recuperação, substituição e exclusão em armazenamento temporário."""
import json
import unittest
from urllib.parse import urlparse

from playwright.sync_api import expect
import test_e2e


class MissionSafetyTests(unittest.TestCase):
    setUpClass = classmethod(test_e2e.PlannerTests.setUpClass.__func__)
    assert_loaded = test_e2e.PlannerTests.assert_loaded
    dismiss_database_prompt = test_e2e.PlannerTests.dismiss_database_prompt

    def setUp(self):
        test_e2e.PlannerTests.setUp(self)
        self.answers = []
        self.dialogs = []
        self.page.on('dialog', self.dialog)

    def dialog(self, dialog):
        self.dialogs.append(dialog.message)
        if self.answers and self.answers.pop(0):
            dialog.accept()
        else:
            dialog.dismiss()

    def open_module(self, module='procedimentos', suffix=''):
        self.module = module
        self.assert_loaded(self.page.goto(
            self.base + 'inspecao/desenhar.html?modulo=' + module + suffix))

    def stored(self, key):
        return self.page.evaluate('(key)=>JSON.parse(localStorage.getItem(key))', key)

    def draft(self):
        return self.stored('ivplanner-procedure-editor-' + self.module + '-v1')

    def missions(self):
        return self.stored('ivplanner-procedure-missions-' + self.module + '-v1') or []

    def button(self, name):
        return self.page.get_by_role('button', name=name, exact=True)

    def fill_mission(self, name='PLANEJAMENTO FICTÍCIO', notes='Dados não salvos'):
        self.page.locator('#mission-name').fill(name)
        self.page.locator('#mission-notes').fill(notes)
        self.page.locator('#page-mission h1').click()

    def confirm_click(self, name, *answers):
        self.answers.extend(answers)
        self.button(name).click()
        self.assertEqual(self.answers, [])

    def recoveries(self):
        return [r for r in self.missions() if r.get('recovery')]

    def fail_writes(self, key):
        self.page.evaluate('''key=>{
            window.originalSetItem=Storage.prototype.setItem;
            Storage.prototype.setItem=function(k,v){
                if(k===key)throw new DOMException('Falha fictícia','QuotaExceededError');
                return window.originalSetItem.call(this,k,v);
            };
        }''', key)

    def restore_writes(self):
        self.page.evaluate('()=>{Storage.prototype.setItem=window.originalSetItem}')

    def test_new_mission_cancel_recovery_reload_and_module_isolation(self):
        for module in ('ndb', 'procedimentos'):
            self.open_module(module)
            # Historical fields are still supported even though absent from the UI.
            self.page.evaluate('''module=>{
                const key='ivplanner-procedure-editor-'+module+'-v1';
                const doc=JSON.parse(localStorage.getItem(key));
                doc.mission.crew='EQUIPE FICTÍCIA';doc.mission.aircraft='ANV FICTÍCIA';
                localStorage.setItem(key,JSON.stringify(doc));
            }''', module)
            self.assert_loaded(self.page.reload())
            self.fill_mission(notes='Rascunho '+module)
            stored_before = self.draft()
            self.page.locator('#mission-origin-lat').fill('-23')
            self.page.locator('#mission-origin-lon').fill('-43')
            self.page.locator('#mission-origin-mag').fill('7')
            previous = dict(stored_before, origin={'lat': -23, 'lon': -43, 'mag': 7, 'dir': 'W'})
            other = 'procedimentos' if module == 'ndb' else 'ndb'
            other_key = 'ivplanner-procedure-editor-' + other + '-v1'
            other_before = self.stored(other_key)
            self.confirm_click('Nova missão', False)
            self.assertEqual(self.draft(), stored_before)
            expect(self.page.locator('#mission-origin-lat')).to_have_value('-23')
            self.assertEqual(self.recoveries(), [])
            self.confirm_click('Nova missão', True)
            self.assertEqual(self.draft()['mission']['name'], '')
            recovery = self.recoveries()[0]
            self.assertEqual(recovery['document'], previous)
            self.assertEqual(self.stored(other_key), other_before)
            self.assert_loaded(self.page.reload())
            self.page.locator('#saved-mission').select_option(recovery['id'])
            self.confirm_click('Reabrir', True)
            expected = dict(previous, missionId=recovery['id'])
            self.assertEqual(self.draft(), expected)
            self.assert_loaded(self.page.reload())
            self.assertEqual(self.draft(), expected)
            self.assertEqual(self.stored(other_key), other_before)
            expect(self.page.locator('#mission-aircraft, #mission-crew')).to_have_count(0)
        self.assertEqual(self.errors, [])

    def test_reopen_preserves_unsaved_changes_and_never_overwrites_saved_mission(self):
        self.open_module()
        self.fill_mission(notes='Versão salva')
        self.button('Salvar missão').click()
        saved = self.missions()[0]
        self.page.locator('#mission-notes').fill('Alteração ainda não salva')
        self.page.locator('#page-mission h1').click()
        current = self.draft()
        self.page.locator('#saved-mission').select_option(saved['id'])
        self.confirm_click('Reabrir', False)
        self.assertEqual(self.draft(), current)
        self.assertEqual(self.missions(), [saved])
        self.confirm_click('Reabrir', True)
        self.assertEqual(self.draft(), saved['document'])
        self.assertEqual(self.missions()[0], saved)
        self.assertEqual(self.recoveries()[0]['document'], current)
        # An already saved plan need not create another recovery copy.
        before = self.missions()
        self.confirm_click('Nova missão', True)
        self.assertEqual(self.missions(), before)
        self.assertEqual(self.errors, [])

    def test_import_and_catalog_protect_mission_without_points(self):
        self.open_module()
        blank = self.draft()
        imported = json.loads(json.dumps(blank))
        imported['title'] = 'PROCEDIMENTO FICTÍCIO'
        imported['mission']['name'] = 'IMPORTADO'
        self.fill_mission(notes='Sem geometria, mas com planejamento')
        previous = self.draft()
        file = {'name': 'ficticio.json', 'mimeType': 'application/json',
                'buffer': json.dumps(imported).encode()}
        self.page.locator('#import-file').set_input_files(file)
        self.assertEqual(self.draft(), previous)
        self.assertEqual(self.recoveries(), [])
        self.answers.append(True)
        self.page.locator('#import-file').set_input_files(file)
        expect(self.page.locator('#toast')).to_have_text('Desenho importado.')
        self.assertEqual(self.draft(), imported)
        self.assertEqual(self.recoveries()[0]['document'], previous)
        self.page.evaluate('''document=>localStorage.setItem('ivplanner-custom-procedures-v1',
            JSON.stringify([{id:'catalogo-ficticio',module:'procedimentos',document}]))''', blank)
        self.open_module(suffix='&procedimento=catalogo-ficticio')
        self.assertEqual(self.draft(), imported)
        self.assertIn('substituir', self.dialogs[-1])
        self.answers.append(True)
        self.open_module(suffix='&procedimento=catalogo-ficticio')
        self.assertEqual(self.draft()['catalogId'], 'catalogo-ficticio')
        self.assertTrue(any(r['document'] == imported for r in self.recoveries()))
        self.assertEqual(self.errors, [])

    def test_storage_failure_and_corrupt_data_block_replacement(self):
        self.open_module()
        self.fill_mission()
        previous = self.draft()
        for key in ('ivplanner-procedure-missions-procedimentos-v1',
                    'ivplanner-procedure-editor-procedimentos-v1'):
            with self.subTest(key=key):
                self.fail_writes(key)
                self.confirm_click('Nova missão', True)
                expect(self.page.locator('#toast')).to_contain_text('planejamento atual foi mantido')
                self.assertEqual(self.draft(), previous)
                expect(self.page.locator('#mission-name')).to_have_value(previous['mission']['name'])
                self.restore_writes()
        self.page.evaluate("localStorage.setItem('ivplanner-procedure-editor-procedimentos-v1','{ilegível')")
        self.assert_loaded(self.page.reload())
        self.button('Nova missão').click()
        expect(self.page.locator('#toast')).to_contain_text('não pôde ser lido')
        self.assertEqual(self.page.evaluate("localStorage.getItem('ivplanner-procedure-editor-procedimentos-v1')"), '{ilegível')
        self.assertEqual(self.errors, [])

    def test_save_failure_rolls_back_library_and_captures_reference_fields(self):
        self.open_module('ndb')
        self.fill_mission()
        self.page.locator('#mission-origin-lat').fill('-23')
        self.page.locator('#mission-origin-lon').fill('-43')
        self.page.locator('#mission-origin-mag').fill('12')
        self.page.locator('#page-mission h1').click()
        self.page.locator('#mission-kind').select_option('SID')
        expect(self.page.locator('#mission-origin-lat')).to_have_value('-23')
        expect(self.page.locator('#mission-origin-lon')).to_have_value('-43')
        self.page.locator('#mission-origin-lat').fill('-23.5')
        self.page.locator('#page-mission h1').click()
        self.button('Salvar missão').click()
        expect(self.page.locator('#toast')).to_have_text('Missão salva.')
        self.assertEqual(self.draft()['origin'], {'lat': -23.5, 'lon': -43, 'mag': 12, 'dir': 'W'})
        saved = self.missions()
        self.page.locator('#mission-notes').fill('Mudança fictícia')
        self.page.locator('#page-mission h1').click()
        previous = self.draft()
        self.fail_writes('ivplanner-procedure-editor-ndb-v1')
        self.button('Salvar missão').click()
        expect(self.page.locator('#toast')).to_contain_text('Não foi possível salvar a missão')
        self.assertEqual(self.draft(), previous)
        self.assertEqual(self.missions(), saved)
        self.restore_writes()
        self.assertEqual(self.errors, [])

    def test_delete_requires_two_confirmations_and_preserves_open_draft(self):
        self.open_module()
        expect(self.button('Reabrir')).to_be_disabled()
        expect(self.button('Excluir')).to_be_disabled()
        self.fill_mission()
        self.button('Salvar missão').click()
        record = self.missions()[0]
        previous = self.draft()
        self.page.locator('#mission-origin-lat').fill('-22')
        self.page.locator('#mission-origin-lon').fill('-42')
        for answers in ((False,), (True, False)):
            self.page.locator('#saved-mission').select_option(record['id'])
            self.confirm_click('Excluir', *answers)
            self.assertEqual(self.missions(), [record])
            self.assertIn(previous['mission']['name'], self.dialogs[-1])
            self.assertEqual(self.draft(), previous)
        self.confirm_click('Excluir', True, True)
        self.assertEqual(self.missions(), [])
        self.assertEqual(self.draft(), previous)
        expect(self.page.locator('#mission-origin-lat')).to_have_value('-22')
        expect(self.page.locator('#mission-origin-lon')).to_have_value('-42')
        expect(self.button('Excluir')).to_be_disabled()
        self.button('Salvar missão').click()
        self.assertEqual(len(self.missions()), 1)
        self.assertNotEqual(self.missions()[0]['id'], record['id'])
        self.assertEqual(self.errors, [])

    def test_recovery_survives_general_backup_restore(self):
        self.open_module()
        self.fill_mission()
        self.confirm_click('Nova missão', True)
        recovery = self.recoveries()[0]
        self.assert_loaded(self.page.goto(self.base + 'configuracoes/index.html'))
        self.dismiss_database_prompt()
        with self.page.expect_download() as downloaded:
            self.page.locator('#backup-export').click()
        with open(downloaded.value.path(), encoding='utf-8') as source:
            backup = json.load(source)
        key = 'ivplanner-procedure-missions-procedimentos-v1'
        self.assertEqual(backup['data'][key], [recovery])
        with self.browser.new_context(service_workers='allow') as isolated:
            isolated.route('**/*', lambda route: route.continue_()
                           if urlparse(route.request.url).netloc == urlparse(self.base).netloc
                           else route.abort())
            target = isolated.new_page()
            target.on('dialog', lambda dialog: dialog.accept())
            target.goto(self.base + 'configuracoes/index.html')
            prompt = target.locator('#db-update-overlay')
            if prompt.is_visible():
                target.locator('#db-update-no').click()
            target.locator('#backup-file').set_input_files({
                'name': 'backup-ficticio.json', 'mimeType': 'application/json',
                'buffer': json.dumps(backup).encode()})
            expect(target.locator('#backup-preview')).to_be_visible()
            target.locator('#backup-apply').click()
            expect(target.locator('#backup-status')).to_contain_text('Importação concluída')
            self.assertEqual(target.evaluate('(key)=>JSON.parse(localStorage.getItem(key))', key), [recovery])
            target.goto(self.base + 'inspecao/desenhar.html?modulo=procedimentos')
            target.locator('#saved-mission').select_option(recovery['id'])
            target.get_by_role('button', name='Reabrir', exact=True).click()
            expect(target.locator('#mission-name')).to_have_value('PLANEJAMENTO FICTÍCIO')
        self.assertEqual(self.errors, [])

    def test_neutral_access_cards_and_mission_action_hierarchy(self):
        links = ['papi.html', 'dvor-vor/index.html', 'ils.html', 'radar.html',
                 'par.html', 'desenhar.html?modulo=ndb', 'desenhar.html?modulo=procedimentos']
        for width, height in ((320, 568), (390, 844), (844, 390), (820, 1180), (1180, 820)):
            self.page.set_viewport_size({'width': width, 'height': height})
            self.assert_loaded(self.page.goto(self.base + 'inspecao/index.html'))
            self.dismiss_database_prompt()
            values = self.page.locator('.card').evaluate_all('''cards=>cards.map(el=>{
                const c=getComputedStyle(el),r=el.getBoundingClientRect();
                return {href:el.getAttribute('href'),width:r.width,height:r.height,
                    border:c.borderColor,background:c.backgroundImage,font:c.fontFamily,
                    radius:c.borderRadius,status:getComputedStyle(el.querySelector('.status')).color};
            })''')
            self.assertEqual([v.pop('href') for v in values], links)
            self.assertTrue(all(v == values[0] for v in values))
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            self.open_module()
            self.assertEqual(self.button('Salvar missão').get_attribute('class'), 'primary')
            self.assertEqual(self.button('Nova missão').get_attribute('class'), '')
            expect(self.page.locator('#page-mission button.primary')).to_have_count(1)
            expect(self.page.locator('#mission-flightGS')).to_be_visible()
        self.assertEqual(self.errors, [])
