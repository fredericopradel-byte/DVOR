"""Stage 5: native application, isolation, final acceptance and offline persistence."""
import json
import unittest
from pathlib import Path
from playwright.sync_api import expect
import test_e2e
import test_chart_import as previous
import test_chart_geometry as geometry
import test_chart_review as review

KEY='ivplanner-procedure-editor-procedimentos-v1'
MISSIONS='ivplanner-procedure-missions-procedimentos-v1'

class ChartApplicationTests(unittest.TestCase):
    setUpClass=classmethod(test_e2e.PlannerTests.setUpClass.__func__)
    setUp=test_e2e.PlannerTests.setUp
    assert_loaded=test_e2e.PlannerTests.assert_loaded
    dismiss_database_prompt=test_e2e.PlannerTests.dismiss_database_prompt
    open=previous.ChartImportTests.open
    choose=previous.ChartImportTests.choose
    records=previous.ChartImportTests.records
    mission_snapshot=previous.ChartImportTests.mission_snapshot
    install_local_fixture=geometry.ChartGeometryTests.install_local_fixture

    def ready(self,module='procedimentos'):
        self.open(module);self.install_local_fixture();self.choose(review.CHART)
        self.page.get_by_role('button',name='Conferência final',exact=True).click()
        expect(self.page.locator('#chart-final-apply')).to_be_enabled()

    def apply_draft(self):
        self.page.locator('#chart-final-apply').click()
        expect(self.page.locator('#chart-import-dialog')).not_to_be_visible()
        expect(self.page.locator('#chart-origin-status')).to_contain_text('Rascunho importado não validado')

    def drawing(self,key=KEY):return self.page.evaluate('(k)=>JSON.parse(localStorage.getItem(k))',key)

    def test_real_chart_critical_issues_block_approval_but_draft_applies_native(self):
        self.ready();expect(self.page.locator('#chart-final-apply')).to_have_text('Abrir rascunho não validado no editor')
        before=self.records()[0]['reconstruction'];self.apply_draft();d=self.drawing()
        self.assertEqual(len(d['points']),len(before['native']['points']));self.assertEqual(len(d['segments']),len(before['native']['segments']))
        self.assertFalse(d['chartImport']['review']['validated']);self.assertEqual(d['chartImport']['modifications'],[])
        self.assertEqual(d['chartImport']['provenance']['points'],before['points']);self.assertEqual(self.errors,[])

    def seed_old(self):
        self.open();self.page.get_by_role('button',name='Fechar importação',exact=True).click()
        self.page.evaluate("""({key,missions})=>{const d=JSON.parse(localStorage.getItem(key));d.title='Manual anterior';d.mission={...d.mission,name:'Missão anterior',icao:'SBXX',runway:'01',crew:'Tripulação preservada',notes:'Não apagar'};d.points=[{id:'old-a',name:'ANTIGO',x:0,y:0,locked:false},{id:'old-b',name:'FIM',x:0,y:2,locked:false}];d.segments=[{id:'old-leg',type:'line',from:'old-a',to:'old-b',name:''}];localStorage.setItem(key,JSON.stringify(d));localStorage.setItem(missions,JSON.stringify([{id:'previous-saved',document:{...d,missionId:'previous-saved'},updatedAt:'2026-01-01'}]));localStorage.setItem('ivplanner-procedure-editor-ndb-v1',JSON.stringify({...d,module:'ndb'}));}""",dict(key=KEY,missions=MISSIONS))
        self.page.reload();self.dismiss_database_prompt();self.page.locator('[data-page=drawing]').click();self.page.locator('#import-chart').click();self.install_local_fixture();self.choose(review.CHART)
        return self.mission_snapshot()

    def test_cancel_and_final_preview_preserve_existing_missions(self):
        before=self.seed_old();self.page.get_by_role('button',name='Conferência final',exact=True).click()
        self.page.get_by_label('Destino da importação',exact=True).select_option('current')
        expect(self.page.locator('#chart-final-conflicts')).to_contain_text('SBXX');self.page.get_by_role('button',name='Fechar importação',exact=True).click()
        self.assertEqual(self.mission_snapshot(),before)

    def test_new_mission_preserves_manual_and_saved_records_and_other_module(self):
        before=self.seed_old();saved=json.loads(before[MISSIONS]);other=before['ivplanner-procedure-editor-ndb-v1']
        self.page.get_by_role('button',name='Conferência final',exact=True).click();self.apply_draft();after=self.mission_snapshot();rows=json.loads(after[MISSIONS]);d=self.drawing()
        self.assertEqual(rows[0],saved[0]);self.assertTrue(any(r.get('recovery') and r['document']['title']=='Manual anterior' for r in rows))
        self.assertEqual(len(rows),3);self.assertTrue(d['missionId']);self.assertEqual(after['ivplanner-procedure-editor-ndb-v1'],other)
        self.assertEqual(d['mission']['icao'],'SBGM');self.assertNotEqual(d['mission']['name'],'Missão anterior')

    def test_apply_current_keeps_fields_unless_conflicts_explicitly_replaced(self):
        self.seed_old();self.page.get_by_role('button',name='Conferência final',exact=True).click();self.page.get_by_label('Destino da importação',exact=True).select_option('current')
        expect(self.page.locator('#chart-final-conflicts')).to_contain_text('manter valor atual');self.apply_draft();d=self.drawing()
        self.assertEqual(d['mission']['icao'],'SBXX');self.assertEqual(d['mission']['crew'],'Tripulação preservada');self.assertEqual(d['mission']['notes'],'Não apagar')
        self.assertEqual(d['mission']['chart'],'RNP Y RWY 35');self.assertEqual(d['missionId'],'')

    def test_replace_identified_fields_is_explicit_and_does_not_overwrite_other_data(self):
        self.seed_old();self.page.get_by_role('button',name='Conferência final',exact=True).click();self.page.get_by_label('Destino da importação',exact=True).select_option('current');self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'");self.page.get_by_label('Preenchimento da missão',exact=True).select_option('chart')
        expect(self.page.locator('#chart-final-conflicts')).to_contain_text('substituir pelo valor da carta');self.apply_draft();d=self.drawing()
        self.assertEqual(d['mission']['icao'],'SBGM');self.assertEqual(d['mission']['runway'],'35');self.assertEqual(d['mission']['crew'],'Tripulação preservada')

    def test_quota_during_application_keeps_current_and_saved_records(self):
        before=self.seed_old();self.page.get_by_role('button',name='Conferência final',exact=True).click()
        self.page.evaluate("""key=>{const put=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k===key)throw new DOMException('test quota','QuotaExceededError');return put.call(this,k,v);};}""",KEY)
        self.page.locator('#chart-final-apply').click();expect(self.page.locator('#chart-status')).to_contain_text('Planejamento atual mantido');after=self.mission_snapshot()
        self.assertEqual(after[KEY],before[KEY]);self.assertEqual(json.loads(after[MISSIONS])[0],json.loads(before[MISSIONS])[0]);self.assertEqual(len(json.loads(after[MISSIONS])),2)
        self.assertEqual(self.page.evaluate('window.IVProcedureChart.snapshot().document.title'),'Manual anterior')
        expect(self.page.locator('#chart-import-dialog')).to_be_visible()

    def test_idb_failure_blocks_application_and_allows_export(self):
        self.ready();before=self.mission_snapshot()
        self.page.evaluate("""()=>{const put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(...args){if(this.name==='sessions')throw new DOMException('test quota','QuotaExceededError');return put.apply(this,args);};}""")
        self.page.locator('#chart-final-apply').click();expect(self.page.locator('#chart-status')).to_contain_text('Conferência não salva');self.assertEqual(self.mission_snapshot(),before)
        with self.page.expect_download() as download:self.page.get_by_role('button',name='Exportar rascunho',exact=True).click()
        data=json.loads(Path(download.value.path()).read_bytes());self.assertTrue(data['reconstruction']['issues'])

    def test_reload_offline_native_profile_and_published_precision_preserved(self):
        self.ready();m=self.records()[0]['reconstruction'];self.apply_draft();before=self.drawing();self.context.set_offline(True);self.page.reload();self.dismiss_database_prompt();after=self.drawing()
        self.assertEqual(after,before);self.assertEqual(after['chartImport']['provenance']['points'],m['points'])
        self.page.locator('[data-page=drawing]').click();self.page.locator('#view-vertical').click();expect(self.page.locator('#vertical-view')).to_be_visible()
        self.assertEqual(self.errors,[])

    def test_native_edit_undo_redo_export_and_reload_keep_original_provenance(self):
        self.ready();self.apply_draft();before=self.drawing()
        # Exercise the actual editor mutation and undo infrastructure, not a parallel importer model.
        self.page.locator('#drawing [data-point]').first.click()
        self.page.locator('#prop-name').fill('EDITADO');self.page.get_by_role('button',name='Aplicar medidas',exact=True).click();after=self.drawing()
        self.assertTrue(after['chartImport']['modifications']);self.assertEqual(after['chartImport']['provenance'],before['chartImport']['provenance'])
        self.page.keyboard.press('Control+z');self.assertEqual(self.drawing()['chartImport']['modifications'],[])
        self.page.keyboard.press('Control+Shift+z');self.assertTrue(self.drawing()['chartImport']['modifications'])
        self.page.reload();self.dismiss_database_prompt();self.assertEqual(self.drawing()['chartImport']['provenance'],before['chartImport']['provenance'])

    def test_ndb_incompatible_chart_warns_and_never_changes_destination(self):
        self.ready('ndb');expect(self.page.locator('.ci-final')).to_contain_text('não cobre a inspeção específica');self.apply_draft()
        d=self.drawing('ivplanner-procedure-editor-ndb-v1');self.assertEqual(d['module'],'ndb');self.assertEqual(d['chartImport']['module'],'ndb');self.assertFalse(d['chartImport']['review']['validated']);self.assertIsNone(self.drawing())

    def test_final_responsive_phone_and_tablet(self):
        self.ready()
        for width,height in [(390,844),(844,390),(768,1024),(1024,768)]:
            self.page.set_viewport_size({'width':width,'height':height})
            self.assertFalse(self.page.locator('#chart-import-dialog').evaluate('d=>d.scrollWidth>d.clientWidth+1'))
            expect(self.page.locator('#chart-final-apply')).to_be_enabled()
        self.assertEqual(self.errors,[])

    def test_selected_path_persists_and_never_discards_other_branches(self):
        self.ready();before=self.records()[0]['reconstruction'];route=self.page.get_by_label('Sequência para o perfil vertical',exact=True)
        options=route.locator('option').all();self.assertGreater(len(options),1);route.select_option(options[1].get_attribute('value'))
        self.apply_draft();d=self.drawing();self.assertTrue(d['flight']['segments']);self.assertEqual(len(d['segments']),len(before['native']['segments']))

    def test_concurrent_draft_change_rejects_stale_final_confirmation(self):
        self.ready();before=self.drawing();before['title']='Alterado em outra aba';self.page.evaluate('({k,d})=>localStorage.setItem(k,JSON.stringify(d))',dict(k=KEY,d=before))
        self.page.locator('#chart-final-apply').click();expect(self.page.locator('#chart-status')).to_contain_text('planejamento mudou');self.assertEqual(self.drawing()['title'],'Alterado em outra aba')

    def test_synthetic_complete_geometry_final_approval_and_inconsistent_rejection(self):
        self.open();result=self.page.evaluate("""async()=>{const {destination,inverse}=await import('./chart-import/geodesy.mjs'),{assess,prepareApplication}=await import('./chart-import/finalize.mjs');const a={lat:-10.123456789,lon:-40.123456789},b=destination(a,90,5),m={schema:'ivplanner-chart-geometry-v1',module:'procedimentos',source:{sha256:'a'.repeat(64),page:1,chart:{kind:{value:'IAC'},procedure:{value:'TESTE'}}},reference:{course:'true'},database:{},points:[{id:'a',name:'A',position:a,roles:[]},{id:'b',name:'B',position:b,roles:[]}],legs:[{id:'l',type:'line',from:'a',to:'b',published:{course:90,reference:'true',distanceNM:5,distanceResolution:.1,courseResolution:1}}],paths:[{legs:['l'],cycle:false}],checks:[],issues:[],verticalConstraints:[{id:'v',entity:'b',value:1234.56789,unit:'FT',reference:'MSL',qualifier:'above'}]},s={id:'synthetic',module:'procedimentos',page:1,source:{sha256:'a'.repeat(64),name:'Teste geométrico'},reconstruction:m};const app=await prepareApplication(s,{approve:true}),report=assess(s);window.completeFixture={s,app};m.legs[0].published.distanceNM=50;let rejected=false;try{await prepareApplication(s,{approve:true});}catch{rejected=true;}return {approved:app.document.chartImport.approval.validated,report:report.canApprove,altitude:app.document.restrictions.b.altitude,rejected};}""")
        self.assertTrue(result['approved']);self.assertTrue(result['report']);self.assertTrue(result['rejected']);self.assertEqual(result['altitude'],'1234.56789')
        self.page.get_by_role('button',name='Fechar importação',exact=True).click()
        self.page.evaluate('()=>window.IVProcedureChart.apply(window.completeFixture.app,window.IVProcedureChart.snapshot())')
        self.assertTrue(self.drawing()['chartImport']['review']['validated']);self.page.reload();self.dismiss_database_prompt();self.assertTrue(self.drawing()['chartImport']['review']['validated'])
        self.page.locator('[data-page=drawing]').click();self.page.locator('#drawing [data-point]').first.click();self.page.locator('#prop-name').fill('ALTERADO');self.page.get_by_role('button',name='Aplicar medidas',exact=True).click();changed=self.drawing();self.assertTrue(changed['chartImport']['approval']['validated']);self.assertFalse(changed['chartImport']['review']['validated']);self.page.keyboard.press('Control+z');self.assertTrue(self.drawing()['chartImport']['review']['validated'])

    def test_cancel_while_final_preparation_is_pending_does_not_apply(self):
        self.ready();before=self.mission_snapshot()
        self.page.evaluate("""()=>{const original=SubtleCrypto.prototype.digest;SubtleCrypto.prototype.digest=async function(...args){await new Promise(resolve=>window.resumeFinalDigest=resolve);return original.apply(this,args);};}""")
        self.page.locator('#chart-final-apply').click();self.page.get_by_role('button',name='Fechar importação',exact=True).click()
        self.page.evaluate('window.resumeFinalDigest()');expect(self.page.locator('#chart-status')).to_contain_text('fechada ou alterada')
        self.assertEqual(self.mission_snapshot(),before)

    def test_native_json_and_general_backup_preserve_chart_metadata(self):
        self.ready();self.apply_draft();expected=self.drawing()
        self.page.locator('#editor-more').click()
        self.page.locator('summary').filter(has_text='Rascunho e arquivos').click()
        with self.page.expect_download() as download:self.page.locator('#export').click()
        exported=json.loads(Path(download.value.path()).read_bytes());self.assertEqual(exported,expected)
        self.page.goto(self.base+'configuracoes/index.html');self.dismiss_database_prompt()
        with self.page.expect_download() as download:self.page.locator('#backup-export').click()
        backup=json.loads(Path(download.value.path()).read_bytes());self.assertEqual(backup['data'][KEY],expected)
        # Restore through the real backup UI into a separate empty browser profile.
        with self.browser.new_context(service_workers='allow') as context:
            from urllib.parse import urlparse
            context.route('**/*',lambda route:route.continue_() if urlparse(route.request.url).netloc==urlparse(self.base).netloc else route.abort())
            page=context.new_page();page.on('dialog',lambda d:d.accept());page.goto(self.base+'configuracoes/index.html')
            if page.locator('#db-update-overlay').is_visible():page.locator('#db-update-no').click()
            page.locator('#backup-file').set_input_files({'name':'backup.json','mimeType':'application/json','buffer':json.dumps(backup).encode()})
            expect(page.locator('#backup-preview')).to_be_visible();page.locator('#backup-apply').click();expect(page.locator('#backup-status')).to_contain_text('Importação concluída')
            page.goto(self.base+'inspecao/desenhar.html?modulo=procedimentos')
            restored=page.evaluate('(k)=>JSON.parse(localStorage.getItem(k))',KEY);self.assertEqual(restored,expected)
            self.assertIn('PDF original',page.locator('#chart-origin-status').text_content())

    def test_vertical_edit_keeps_published_origin_and_clears_no_inspection_rules(self):
        self.ready();route=self.page.get_by_label('Sequência para o perfil vertical',exact=True);route.select_option(route.locator('option').nth(1).get_attribute('value'));self.apply_draft();before=self.drawing()
        self.page.locator('#view-vertical').click();select=self.page.locator('#profile-element');self.assertGreater(select.locator('option').count(),0)
        target=select.locator('option').first.get_attribute('value');select.select_option(target)
        self.page.locator('#profile-altitude').fill('2345.6789');self.page.locator('#profile-qualifier').select_option('above');self.page.locator('#profile-apply').click()
        after=self.drawing();self.assertEqual(after['restrictions'][target[2:]]['altitude'],'2345.6789');self.assertEqual(after['restrictions'][target[2:]]['inspectionAltitude'],'')
        self.assertEqual(after['restrictions'][target[2:]]['phase'],'');self.assertEqual(after['chartImport']['provenance'],before['chartImport']['provenance']);self.assertIn(target[2:],after['chartImport']['modifications'])

    def test_invalid_selected_sequence_can_be_rechosen_after_correction(self):
        self.ready();self.page.get_by_role('button',name='Fechar importação',exact=True).click();record=self.records()[0]
        self.page.evaluate("""async id=>{const storage=await import('./chart-import/storage.mjs'),s=await storage.load(id,'procedimentos');s.finalization={selection:['obsolete-leg']};await storage.save(s,s.file);}""",record['id'])
        self.page.locator('#import-chart').click();self.page.locator('#chart-library').select_option(record['id']);self.page.get_by_role('button',name='Retomar',exact=True).click();expect(self.page.locator('#chart-result')).to_be_visible(timeout=25000)
        self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        self.page.get_by_role('button',name='Conferência final',exact=True).click();self.page.get_by_role('button',name='Rever sequência após correção',exact=True).click()
        expect(self.page.locator('#chart-final-apply')).to_be_enabled();self.assertEqual(self.records()[0]['finalization']['selection'],[])

    def test_final_choices_resume_after_reload_without_changing_mission(self):
        self.ready();before=self.mission_snapshot();self.page.get_by_label('Destino da importação',exact=True).select_option('current');self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'");self.page.get_by_label('Preenchimento da missão',exact=True).select_option('chart')
        self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'");record=self.records()[0];self.page.reload();self.dismiss_database_prompt();self.page.locator('[data-page=drawing]').click();self.page.locator('#import-chart').click();self.page.locator('#chart-library').select_option(record['id']);self.page.get_by_role('button',name='Retomar',exact=True).click();expect(self.page.locator('#chart-result')).to_be_visible(timeout=25000);self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        self.page.get_by_role('button',name='Conferência final',exact=True).click();expect(self.page.get_by_label('Destino da importação',exact=True)).to_have_value('current');expect(self.page.get_by_label('Preenchimento da missão',exact=True)).to_have_value('chart');self.assertEqual(self.mission_snapshot(),before)

    def test_single_final_confirmation_ui_with_known_synthetic_geometry(self):
        import fitz
        self.open();pdf=fitz.open();page=pdf.new_page();page.insert_text((50,50),'SYNTHETIC IAC RWY 01 - 5 NM TRUE 090');data=pdf.tobytes();pdf.close()
        self.page.locator('#chart-file').set_input_files({'name':'synthetic.pdf','mimeType':'application/pdf','buffer':data});expect(self.page.locator('#chart-result')).to_be_visible(timeout=25000);self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        record=self.records()[0];self.page.get_by_role('button',name='Fechar importação',exact=True).click()
        self.page.evaluate("""async id=>{const storage=await import('./chart-import/storage.mjs'),{destination}=await import('./chart-import/geodesy.mjs'),s=await storage.load(id,'procedimentos'),a={lat:-10.123456789,lon:-40.123456789},b=destination(a,90,5),chart={kind:{value:'IAC'},icao:{value:'TEST'},procedure:{value:'SYNTHETIC IAC RWY 01'}};s.recognition={...s.recognition,metadata:chart,navigation:[],issues:[]};s.reconstruction={schema:'ivplanner-chart-geometry-v1',module:s.module,source:{sha256:s.source.sha256,page:1,chart},reference:{course:'true'},database:{version:'synthetic-verifiable-geometry'},points:[{id:'a',name:'A',position:a,roles:[],coordinateSource:{kind:'synthetic-fixture'},coordinateState:'published'},{id:'b',name:'B',position:b,roles:[],coordinateSource:{kind:'synthetic-fixture'},coordinateState:'published'}],legs:[{id:'l',type:'line',from:'a',to:'b',published:{course:90,reference:'true',distanceNM:5,distanceResolution:.1,courseResolution:1}}],paths:[{legs:['l'],cycle:false}],checks:[],issues:[],verticalConstraints:[]};await storage.save(s,s.file);}""",record['id'])
        self.page.locator('#import-chart').click();self.page.locator('#chart-library').select_option(record['id']);self.page.get_by_role('button',name='Retomar',exact=True).click();expect(self.page.locator('#chart-result')).to_be_visible(timeout=25000);self.page.wait_for_function("document.querySelector('#chart-import-dialog').getAttribute('aria-busy')==='false'")
        self.page.get_by_role('button',name='Conferência final',exact=True).click();expect(self.page.locator('#chart-final-apply')).to_have_text('Confirmar conjunto e aplicar');self.page.locator('#chart-final-apply').click();expect(self.page.locator('#chart-import-dialog')).not_to_be_visible()
        self.assertTrue(self.drawing()['chartImport']['review']['validated']);self.assertTrue(self.records()[0]['finalization']['accepted']['validated']);self.assertEqual(self.errors,[])

    def test_missing_chart_type_cannot_apply_and_unsupported_vertical_cannot_approve(self):
        self.ready();record=self.records()[0]
        result=self.page.evaluate("""async s=>{const {assess}=await import('./chart-import/finalize.mjs');delete s.reconstruction.source.chart.kind;const unknown=assess(s);s.reconstruction.source.chart.kind={value:'IAC'};s.reconstruction.issues=[];s.reconstruction.verticalConstraints=[{id:'gradient-test',scope:'missed',value:3.3,unit:'%',reference:'MSL',qualifier:'above'}];const vertical=assess(s);return {unknown:unknown.canApply,kind:unknown.critical.some(i=>i.id==='final-kind'),vertical:vertical.critical.some(i=>i.id==='final-vertical-gradient-test'),approve:vertical.canApprove};}""",record)
        self.assertFalse(result['unknown']);self.assertTrue(result['kind']);self.assertTrue(result['vertical']);self.assertFalse(result['approve'])

    def test_native_rotation_lock_and_undo_preserve_published_origin(self):
        self.ready();self.apply_draft();before=self.drawing();self.page.locator('#editor-more').click();self.page.locator('summary').filter(has_text='Ancoragem e rotação geométrica').click()
        self.page.locator('#rotation-leg').select_option(before['segments'][0]['id']);self.page.locator('#rotation-center').select_option(before['segments'][0]['from']);self.page.locator('#rotation-azimuth').fill('45');self.page.once('dialog',lambda d:d.accept());self.page.locator('#apply-rotation').click()
        rotated=self.drawing();self.assertNotEqual(rotated['points'],before['points']);self.assertTrue(rotated['chartImport']['modifications']);self.assertIn(rotated['segments'][0]['id'],rotated['chartImport']['modifications']);self.assertEqual(rotated['chartImport']['provenance'],before['chartImport']['provenance'])
        self.page.locator('#undo').click();self.assertEqual(self.drawing()['chartImport']['modifications'],[])
        if self.page.locator('#inspector-panel').is_visible():self.page.locator('#close-inspector').click()
        self.page.locator('#drawing [data-point]').first.click();self.page.locator('#selection-lock').click();locked=self.drawing();self.assertTrue(locked['points'][0]['locked']);self.assertEqual(locked['chartImport']['modifications'],[])
        self.page.locator('#undo').click();self.assertFalse(self.drawing()['points'][0]['locked']);self.assertEqual(self.errors,[])
        self.assertTrue(self.page.evaluate("d=>{d.chartImport.provenance.mapping=null;try{window.IVProcedurePreview.render(d);return false;}catch{return true;}}",self.drawing()))

if __name__=='__main__':unittest.main()
