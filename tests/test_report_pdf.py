"""Geração real de PDFs rasterizados, com métricas Canvas e leitura independente."""
import json
import os
import unittest
from pathlib import Path

import fitz
import test_e2e

SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="500" height="500"><rect width="500" height="500" fill="#111619"/><path d="M50 400L400 50" stroke="#078dd1" stroke-width="4"/></svg>'
INSTRUMENT = '''() => {
 window.pdfDraws=[];let number=0;const ids=new WeakMap();
 const proto=CanvasRenderingContext2D.prototype,original=proto.fillText;
 proto.fillText=function(value,x,y,...rest){
  if(this.canvas.width===1240&&this.canvas.height===1754){
   if(!ids.has(this.canvas))ids.set(this.canvas,++number);
   const m=this.measureText(String(value));
   window.pdfDraws.push({text:String(value),x,y,w:m.width,top:y-m.actualBoundingBoxAscent,bottom:y+m.actualBoundingBoxDescent,page:ids.get(this.canvas),color:this.fillStyle,font:this.font,background:[...this.getImageData(x+8,y-18,1,1).data]});
  }
  return original.call(this,value,x,y,...rest);
 };
}'''


def flight_fixture(stress=False):
    long = ('Observação fictícia para verificar quebra de linha e integridade dos valores. ' * (95 if stress else 1)) + 'MARCADOR-FINAL'
    leg = dict(number=1,type='Rota',route='SBXX → SBYY',airports='Aeródromo de teste → Destino de teste',distance='125 NM',time='0h35',level='FL180',burn='543 kg',fuelStart='4.321 kg',fuelEnd='3.778 kg',weightStart='19.876 kg',weightEnd='19.333 kg',zfw='15.555 kg',note=long if stress else '')
    return dict(aircraft='Legacy 3601',totals=dict(route='SBXX → SBYY • INSPEÇÃO SBYY • SBYY → SBZZ' * (4 if stress else 1),metrics=[['Distância total','1.234 NM'],['Tempo total','9h45'],['Consumo total','3.456 kg'],['Fuel mínimo','4.567 kg'],['Fuel planejado','5.678 kg'],['Fuel máximo','8.765 kg'],['ZFW','15.555 kg'],['TOW','21.233 kg'],['LW final','17.777 kg']],weights=[['PBO','12.345 kg'],['Payload total','3.210 kg'],['ZFW','15.555 kg / limite 18.500 kg'],['TOW','21.233 kg / MTOW 22.500 kg'],['LW no destino','18.765 kg / MLW 19.500 kg'],['Reserva','1.111 kg'],['Extra fixo','222 kg']]),legs=[leg],alternate={**leg,'number':'ALT','note':''},weather=[dict(label='ADEP',icao='SBXX',airport='Aeródromo fictício',conditions='Temperatura 25 °C · vento 090° / 12 kt',runway='09 · 090° M · 2.345 m · 12.0 kt PROA',performance='1.234 m requeridos · V1 100 / VR 110 / V2 120 kt',metar='METAR SBXX 151200Z 09012KT 9999 SCT020 25/19 Q1013',taf=('TAF SBXX 151100Z 1512/1612 09012KT 9999 SCT020 ' * (150 if stress else 1))+'FIM-TAF')],checks=[['Verificação '+str(i+1),long if stress else 'Dados fictícios — conferir limites.'] for i in range(3 if stress else 1)])


def inspection_fixture(kind='ILS',stress=False):
    long = ('Conferir passagem fictícia, sentido e altitude publicada. ' * (100 if stress else 1))+'FIM-DESCRIÇÃO'
    detail = ('SEMESPACO' * 250 if stress else '090° M · 10 NM · 3.000 ft')+' FIM-DETALHE'
    return dict(kind=kind,name='MISSÃO FICTÍCIA',meta=[['Missão','MISSÃO FICTÍCIA'],['Data','15/10/2026'],['Observação',long if stress else 'Teste sem dados reais'],['Identificação','AUX-TESTE']],notes=detail if kind=='RADAR' else '',maps=[SVG,SVG],profileMap=SVG,cards=[dict(tx='TX1',type='P2',description=long,detail=detail,group='GRUPO AZUL',groupColor='#078dd1',done=False,current=True),dict(tx='TX2',type='P3',description='ÚLTIMA PASSAGEM',detail='FIM-DAS-PASSAGENS',done=True)])


class ReportPDFTests(unittest.TestCase):
    setUpClass = classmethod(test_e2e.PlannerTests.setUpClass.__func__)
    setUp = test_e2e.PlannerTests.setUp
    assert_loaded = test_e2e.PlannerTests.assert_loaded

    def storage_snapshot(self):
        # A memória de rolagem da navegação pode atualizar-se durante o download.
        return self.page.evaluate('Object.fromEntries(Object.entries(localStorage).filter(([key])=>key!=="ivplanner-global-nav-v1"))')

    def install_probe(self):
        self.page.evaluate(INSTRUMENT)

    def save_review(self,download):
        # Opcional: evidências locais para revisão, nunca adicionadas ao repositório.
        destination=os.environ.get('IV_TEST_PDF_DIR')
        if not destination:return
        folder=Path(destination);folder.mkdir(parents=True,exist_ok=True)
        path=folder/(str(len(list(folder.glob('*.pdf')))+1)+'-'+download.suggested_filename)
        download.save_as(path)
        with fitz.open(path) as doc:
            for i,page in enumerate(doc):
                page.get_pixmap().save(str(path.with_suffix(''))+f'-pagina-{i+1}.png')

    def generate(self, data, flight=False):
        before=json.dumps(data,ensure_ascii=False,sort_keys=True)
        self.page.evaluate('(data)=>window.pdfInput=data',data)
        with self.page.expect_download(timeout=30000) as event:
            self.page.evaluate('async flight=>{await (flight?IVFlightReport:IVReport).exportReport(window.pdfInput)}',flight)
        self.assertEqual(json.dumps(self.page.evaluate('pdfInput'),ensure_ascii=False,sort_keys=True),before)
        download=event.value
        self.save_review(download)
        self.assertIsNone(download.failure())
        raw=Path(download.path()).read_bytes()
        self.assertTrue(raw.startswith(b'%PDF-1.4'))
        doc=fitz.open(stream=raw,filetype='pdf')
        self.addCleanup(doc.close)
        self.assertFalse(doc.is_repaired)
        draws=self.page.evaluate('pdfDraws')
        self.assertEqual(len(doc),max(d['page'] for d in draws))
        self.assertGreater(len(raw),20000)
        for page in doc:
            self.assertEqual(tuple(page.rect),(0.0,0.0,595.0,842.0))
            self.assertEqual(len(page.get_images()),1)
            self.assertTrue(page.get_pixmap(matrix=fitz.Matrix(.25,.25)).samples)
        self.assert_layout(draws)
        return draws,doc

    def assert_layout(self,draws):
        body=[d for d in draws if 206<=d['y']<1680]
        for d in draws:
            self.assertGreaterEqual(d['x'],-.5,d)
            self.assertLessEqual(d['x']+d['w'],1240+.5,d)
        for d in body:
            if '33px' in d['font']:
                self.assertTrue(all(c>=248 for c in d['background'][:3]),d)
            self.assertGreaterEqual(d['x'],76-.5,d)
            self.assertLessEqual(d['x']+d['w'],1164+.5,d)
            self.assertLessEqual(d['bottom'],1630+.5,d)
        # Teste de colisão de glifos: não confunde linhas próximas com sobreposição.
        for i,a in enumerate(body):
            if not a['text'].strip():continue
            for b in body[i+1:]:
                if b['page']!=a['page'] or not b['text'].strip():continue
                dx=min(a['x']+a['w'],b['x']+b['w'])-max(a['x'],b['x'])
                dy=min(a['bottom'],b['bottom'])-max(a['top'],b['top'])
                self.assertFalse(dx>1 and dy>1,(a,b))

    def test_preflight_summary_and_long_weather_preserve_all_values(self):
        self.page.goto(self.base+'prevoo/legacy.html');self.install_probe()
        data=flight_fixture(True);draws,doc=self.generate(data,True)
        self.assertGreater(len(doc),6)
        texts=[d['text'] for d in draws]
        for _,value in data['totals']['metrics']+data['totals']['weights']:
            self.assertIn(value,texts)
        self.assertEqual(texts.count(data['totals']['route']),0)  # Rota longa efetivamente quebrada.
        combined=''.join(texts)
        self.assertIn('MARCADOR-FINAL',combined);self.assertIn('FIM-TAF',combined)
        self.assertFalse(any('…' in t for t in texts))

    def test_preflight_metrics_do_not_truncate_long_formatted_values(self):
        self.page.goto(self.base+'prevoo/hawker.html');self.install_probe()
        data=flight_fixture();data['aircraft']='Hawker FAB 6050'
        data['totals']['metrics'][0][1]='123.456.789.012.345 lb'
        draws,_=self.generate(data,True)
        self.assertIn('123.456.789.012.345lb',''.join(d['text'].replace(' ','') for d in draws))
        self.assertEqual(sum(d['text']==data['totals']['route'] for d in draws),1)

    def test_all_inspection_generators_long_cards_metadata_and_tokens(self):
        routes=[('inspecao/ils.html','ILS'),('inspecao/radar.html','RADAR'),('inspecao/dvor-vor/index.html','DVOR-VOR'),('ils.html','ILS')]
        for route,kind in routes:
            with self.subTest(route=route):
                self.page.goto(self.base+route);self.install_probe()
                draws,doc=self.generate(inspection_fixture(kind,True))
                text=''.join(d['text'] for d in draws)
                self.assertGreater(len(doc),3)
                for end in ['FIM-DESCRIÇÃO','FIM-DETALHE','FIM-DAS-PASSAGENS','GRUPO AZUL']:
                    self.assertIn(end,text)
                self.assertIn('CONTINUAÇÃO',text)
                self.assertNotIn('undefined',text)

    def test_papi_passages_and_long_notes_paginate_without_losing_results(self):
        for route in ['inspecao/papi.html','papi.html']:
            with self.subTest(route=route):
                self.page.goto(self.base+route);self.install_probe()
                data=inspection_fixture('PAPI');data['passes']=[dict(number=1,createdAt='2026-10-15T12:00:00Z',svg=SVG,boxNumbers=[1,2,3,4],values=['3.20','3.10','3.00','2.90'],results=dict(lower='2.80',lowerSat=True,center='3.00',centerSat=True,upper='3.20',upperSat=False,ramp='3.00',rampSat=True),clearance=dict(angle='2.00',source='Fonte fictícia'),sectors=['Setor fictício '+str(i) for i in range(5)],note=('Nota fictícia. '*600)+'FIM-OBSERVAÇÃO')]
                draws,doc=self.generate(data)
                text=''.join(d['text'] for d in draws)
                for expected in ['Caixa 1: 3.20°','Inferior 2.80° SAT','Superior 3.20° DEF','Clearance 2.00°','FIM-OBSERVAÇÃO']:
                    self.assertIn(expected,text)
                self.assertGreater(len(doc),2)
                # Uma passagem comum cabe inteira: desenho e resultados ficam juntos.
                self.page.goto(self.base+route);self.install_probe();data['passes'][0]['note']='Nota curta.'
                draws,_=self.generate(data)
                title=next(d for d in draws if d['text'].startswith('PASSAGEM 1  •'))
                result=next(d for d in draws if d['text'].startswith('Inferior 2.80'))
                self.assertEqual(title['page'],result['page'])

    def test_empty_reports_generate_no_blank_content_pages(self):
        for route,flight in [('prevoo/legacy.html',True),('inspecao/ils.html',False)]:
            self.page.goto(self.base+route);self.install_probe()
            data=flight_fixture() if flight else inspection_fixture()
            if flight:data['legs']=[];data['weather']=[];data['checks']=[]
            else:data['cards']=[];data['meta']=[]
            draws,doc=self.generate(data,flight)
            for i in range(1,len(doc)+1):
                self.assertTrue(any(d['page']==i and 206<=d['y']<=1630 for d in draws))

    def test_real_aircraft_export_matches_report_input_and_preserves_storage(self):
        for aircraft in ['legacy','hawker']:
            with self.subTest(aircraft=aircraft):
                self.page.goto(self.base+f'prevoo/{aircraft}.html')
                # O formulário real calcula e entrega os mesmos valores ao gerador.
                self.page.locator('[data-leg="0"][data-side="from"]').fill('SBBR');self.page.locator('[data-leg="0"][data-side="from"]').dispatch_event('change')
                self.page.locator('[data-leg="0"][data-side="to"]').fill('SBGL');self.page.locator('[data-leg="0"][data-side="to"]').dispatch_event('change')
                self.page.locator('#alternate').fill('SBSP');self.page.locator('#alternate').dispatch_event('change')
                self.page.locator('[data-page="summary"]').click();self.install_probe()
                self.page.evaluate('''()=>{const original=IVFlightReport.exportReport;IVFlightReport.exportReport=async data=>{window.exportInput=JSON.parse(JSON.stringify(data));return original(data)}}''')
                stored=self.storage_snapshot()
                with self.page.expect_download(timeout=30000) as event:self.page.locator('#export-flight-pdf').click()
                self.save_review(event.value)
                self.assertEqual(self.storage_snapshot(),stored)
                data=self.page.evaluate('exportInput');draws=self.page.evaluate('pdfDraws');self.assert_layout(draws)
                texts=[d['text'] for d in draws]
                for _,value in data['totals']['metrics']+data['totals']['weights']:self.assertIn(value,texts)
                self.assertTrue(any('kg' in x for x in texts) if aircraft=='legacy' else any('lb' in x for x in texts))
                self.assertFalse(self.errors)

    def test_offline_pdf_generation_from_cached_operational_pages(self):
        self.page.goto(self.base+'index.html')
        self.page.evaluate('async()=>{await Promise.race([navigator.serviceWorker.ready,new Promise((_,r)=>setTimeout(()=>r(Error("Worker não pronto")),10000))])}')
        self.page.reload();self.page.wait_for_function('navigator.serviceWorker.controller!==null')
        self.context.set_offline(True)
        for route,flight in [('prevoo/legacy.html',True),('prevoo/hawker.html',True),('inspecao/ils.html',False),('inspecao/papi.html',False),('inspecao/radar.html',False),('inspecao/dvor-vor/index.html',False)]:
            with self.subTest(route=route):
                self.page.goto(self.base+route);self.install_probe()
                data=flight_fixture() if flight else inspection_fixture('RADAR' if 'radar' in route else 'DVOR-VOR' if 'dvor' in route else 'PAPI' if 'papi' in route else 'ILS')
                if data.get('kind')=='PAPI':data['passes']=[]
                stored=self.storage_snapshot()
                self.generate(data,flight)
                self.assertEqual(self.storage_snapshot(),stored)
        self.assertFalse(self.errors)

    def test_real_radar_export_restores_camera_and_mission(self):
        import test_map_controls
        test_map_controls.MapControlTests.radar(self,vertical=False)
        # Confirmar os campos importados pelo mesmo fluxo usado na edição da missão.
        self.page.locator('#mission-title').dispatch_event('input')
        self.page.locator('#rose').dispatch_event('wheel',{'deltaY':-200})
        test_map_controls.MapControlTests.drag(self)
        before=self.page.locator('#map-world').get_attribute('transform')
        self.page.locator('.page-nav [data-page=plan]').click()
        stored=self.storage_snapshot()
        self.install_probe()
        self.page.evaluate('()=>{const original=IVReport.exportReport;IVReport.exportReport=async data=>{window.exportInput=JSON.parse(JSON.stringify(data));return original(data)}}')
        with self.page.expect_download(timeout=30000) as event:self.page.locator('#export-pdf').click()
        self.save_review(event.value)
        self.assertEqual(self.page.locator('#map-world').get_attribute('transform'),before)
        self.assertEqual(self.storage_snapshot(),stored)
        draws=self.page.evaluate('pdfDraws');self.assert_layout(draws)
        data=self.page.evaluate('exportInput');text=''.join(d['text'] for d in draws)
        for card in data['cards']:
            self.assertIn(card['description'],text)
            self.assertIn(card['detail'],text)
        self.assertNotIn('undefined',text)
        self.assertFalse(self.errors)
