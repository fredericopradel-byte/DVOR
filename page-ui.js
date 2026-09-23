(()=>{'use strict';
const rootPath=new URL('.',document.currentScript.src).pathname;
const H={
'/index.html':['Menu','Escolha uma área para abrir suas ferramentas. A barra lateral permite passar diretamente entre as áreas e voltar à última tela usada.'],
'/prevoo/index.html':['Pré-voo','Escolha a aeronave para iniciar o planejamento. As informações já instaladas continuam acessíveis sem internet.'],
'/prevoo/legacy.html':{
 route:['Rota','Informe os aeródromos e adicione trechos de rota ou inspeção. O último aeródromo da sequência é usado como origem da alternativa.'],
 weight:['Peso/Fuel','Informe ocupantes, carga e combustível. Confira os limites e os avisos calculados antes de usar o plano.'],
 performance:['Performance','Confira as pistas, o vento e a cabeceira escolhida. Você pode alternar entre a seleção automática e uma cabeceira manual.'],
 summary:['Resumo','Confira o plano consolidado, os pesos e as margens. Revise os dados informados nas outras abas antes da utilização.'],
 defaults:['Defaults','Ajuste consumos, tempos, reservas, níveis e PBO por matrícula. Restaurar padrões devolve os parâmetros originais.']},
 '/prevoo/hawker.html':{
 route:['Rota Hawker','Informe até cinco trechos de rota ou inspeção e, se necessário, uma alternativa. O último aeródromo alimenta a origem da alternativa.'],
 weight:['Peso/Fuel Hawker','Escolha a matrícula, informe de zero a cinco passageiros, carga e combustível em libras. Confira os limites de peso.'],
 performance:['Performance Hawker','Informe altitude pressão e temperatura manualmente ou atualize pelo METAR. Selecione flapes de decolagem e condição da pista de pouso. Confira as faixas da tabela e a cabeceira.'],
 summary:['Resumo Hawker','Confira percurso, combustível, pesos e avisos antes de utilizar o planejamento.'],
 defaults:['Defaults Hawker','Ajuste os consumos, os tempos, a reserva, os níveis sugeridos e o PBO das matrículas. Restaurar padrões recupera os valores iniciais.']},
 '/inspecao/index.html':['Inspeção em Voo','Selecione o sistema a planejar ou acompanhar. As missões de PAPI e DVOR/VOR podem ser mantidas neste aparelho.'],
 '/inspecao/dvor-vor/index.html':{
 mission:['Missão DVOR/VOR','Identifique a missão, informe o auxílio e sua declinação planejada, salve ou abra uma missão anterior. Também é possível importar e exportar.'],
 plan:['Planejar DVOR/VOR','Adicione as passagens radiais ou arcos e escolha transmissor, sentido e observações conforme seu planejamento.'],
 rose:['Mapa DVOR/VOR','Veja a posição auxiliar em relação ao auxílio. Use os controles de centralização, aproximação e GNSS; o mapa não substitui o resultado de inspeção.'],
 execution:['Execução DVOR/VOR','Ordene as passagens, acompanhe Atual e Próxima, conclua ou refaça registros. Os cartões podem ser agrupados para organização.']},
 '/inspecao/ils.html':{
 mission:['Missão ILS','Informe o auxílio, o TX inicial e os alarmes solicitados. Salve, importe ou exporte a missão.'],
 plan:['Planejar ILS','Confira o pacote P3, P2 e P4 e ajuste as passagens conforme o planejamento da inspeção.'],
 rose:['Mapa ILS','Veja as trajetórias planejadas e a posição auxiliar do GNSS quando houver coordenadas e declinação.'],
 execution:['Execução ILS','Ordene os cartões, acompanhe Atual e Próxima, conclua, refaça e agrupe passagens.']},
 '/inspecao/papi.html':{
 plan:['Planejamento PAPI','Identifique a missão, selecione cabeceira, lado e conjunto, confira as coordenadas e os valores planejados antes da execução.'],
 execute:['Execução PAPI','Registre os quatro ângulos encontrados. Confirmar cria uma nova passagem sem substituir as anteriores.'],
 map:['Mapa PAPI','Use um dedo para deslocar e dois para aproximar ou girar. A posição GNSS é apenas um apoio visual.'],
 passes:['Passagens PAPI','Confira as medidas, a interpretação e a situação de cada passagem registrada. Cada cartão pode ser excluído separadamente.']},
 '/meteorologia/index.html':['Meteorologia','Busque pelo código ICAO para consultar produtos disponíveis online. Sem conexão, a página abre e mantém os recursos locais e a última consulta disponível.'],
 '/localidades/index.html':['Localidades e Auxílios','Escolha aeródromos ou auxílios para consultar os dados instalados e os registros cadastrados neste aparelho.'],
 '/localidades/aerodromos.html':['Aeródromos','Busque por ICAO, nome ou UF. Abra um registro para consultar pistas e cabeceiras ou adicione uma localidade manualmente.'],
 '/localidades/auxilios.html':['Auxílios','Busque por nome ou identificação. Consulte a base instalada e adicione ou edite registros manuais.'],
 '/configuracoes/index.html':['Configurações','Use Backup para exportar seus registros em JSON ou importar um arquivo salvo. Em Base de dados, verifique arquivos instalados e atualizações.'],
 '/configuracoes/bases.html':['Base de dados','Verifique integridade e atualizações quando houver internet. A base instalada continua disponível offline.'],
 '/modulo-em-breve.html':['Módulo em breve','Este módulo ainda não está disponível. Use o botão Voltar para escolher outra ferramenta.']
};
const icons={mission:'M12 2 7 4v4a5 5 0 0 0 10 0V4l-5-2Zm-7 9v10h14V11M8 15h8m-8 3h5',plan:'M8 4H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-3M8 4c0-1.1.9-2 2-2h4c1.1 0 2 .9 2 2v2H8V4Zm0 8h8m-8 4h6',route:'M3 18h5l4-12 4 12h5M8 14h8',weight:'M12 3v4m-7 2h14M7 9l-4 7h8L7 9Zm10 0-4 7h8l-4-7ZM5 21h14m-7-14v14',performance:'M4 19 12 4l8 15M7 16h10',summary:'M5 4h14v16H5V4Zm3 4h8m-8 4h8m-8 4h5',defaults:'M4 7h16M4 17h16M9 4v6m6 4v6',execute:'M12 3a9 9 0 1 0 9 9 9 9 0 0 0-9-9Zm-4 9 2.7 2.7L16 9.5',execution:'M12 3a9 9 0 1 0 9 9 9 9 0 0 0-9-9Zm-4 9 2.7 2.7L16 9.5',map:'M12 22s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12Zm0-9a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z',rose:'M12 22s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12Zm0-9a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z',passes:'M9 5h12M9 12h12M9 19h12M3 5h2m-2 7h2m-2 7h2'};
function path(){let p=location.pathname.slice(rootPath.length);return '/'+(p.endsWith('/')?p+'index.html':p)}
function initUpdates(){
 if(!('serviceWorker' in navigator)||!location.protocol.startsWith('http'))return;
 const wasControlled=!!navigator.serviceWorker.controller;
 navigator.serviceWorker.addEventListener('controllerchange',()=>{
  if(!wasControlled||document.querySelector('.iv-update-notice'))return;
  const notice=document.createElement('div');notice.className='iv-update-notice';notice.setAttribute('role','status');
  const label=document.createElement('span');label.textContent='Atualização pronta para usar.';
  const reload=document.createElement('button');reload.type='button';reload.textContent='Recarregar';reload.addEventListener('click',()=>location.reload());
  notice.append(label,reload);document.body.append(notice);
 });
 let lastCheck=0;
 function check(){if(Date.now()-lastCheck<60000)return;lastCheck=Date.now();navigator.serviceWorker.getRegistration(rootPath).then(reg=>reg?.update()).catch(()=>{})}
 window.addEventListener('load',check,{once:true});window.addEventListener('online',check);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)check()});
}
initUpdates();
function init(){
 const entry=H[path()];
 if(!entry)return;
 const anchor=document.querySelector('.topbar,header .bar,main > header,.hero');
 const button=document.createElement('button');button.type='button';button.className='iv-help-button'+(anchor?'':' iv-help-floating');button.textContent='?';button.setAttribute('aria-label','Ajuda desta página');button.setAttribute('aria-haspopup','dialog');
 if(anchor){const spacer=anchor.querySelector(':scope > .spacer');if(spacer)spacer.replaceWith(button);else anchor.append(button)}else document.body.append(button);
 const overlay=document.createElement('div');overlay.className='iv-help-overlay';overlay.hidden=true;overlay.innerHTML='<div class="iv-help-panel" role="dialog" aria-modal="true" aria-labelledby="iv-help-title"><button type="button" class="iv-help-close" aria-label="Fechar ajuda">×</button><h2 id="iv-help-title"></h2><div class="iv-help-text"></div></div>';document.body.append(overlay);
 const close=()=>{overlay.hidden=true;document.body.classList.remove('iv-help-open');button.focus()};
 button.addEventListener('click',()=>{const active=document.querySelector('.bottom-nav button.active,.page-nav button.active,.tabs .tab.active');const item=Array.isArray(entry)?entry:entry[active?.dataset.page]||Object.values(entry)[0];overlay.querySelector('h2').textContent=item[0];const target=overlay.querySelector('.iv-help-text');target.replaceChildren(...item.slice(1).map(t=>{const p=document.createElement('p');p.textContent=t;return p}));overlay.hidden=false;document.body.classList.add('iv-help-open');overlay.querySelector('.iv-help-close').focus()});
 overlay.querySelector('.iv-help-close').addEventListener('click',close);overlay.addEventListener('click',e=>{if(e.target===overlay)close()});document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!overlay.hidden)close()});
 const nav=document.querySelector('.page-nav,.tabs nav'),papiNav=document.querySelector('.bottom-nav');
 if(!nav&&!papiNav){document.body.classList.add('iv-no-bottom-nav');return}
 document.body.classList.add('iv-has-bottom-nav');
 if(papiNav){papiNav.classList.add('iv-fixed-nav');return}
 nav.classList.add('iv-bottom-nav','iv-fixed-nav');
 if(nav.parentElement.classList.contains('tabs')){const footer=nav.parentElement;document.body.append(nav);footer.hidden=true;document.body.classList.add('iv-legacy-nav')}
 else document.body.append(nav);
 const buttons=[...nav.querySelectorAll('button[data-page]')],factor=buttons.length===5?2.12:1.95;nav.style.setProperty('--iv-active-grow',factor);
 const pill=document.createElement('span');pill.className='iv-nav-pill';pill.setAttribute('aria-hidden','true');nav.prepend(pill);
 buttons.forEach(b=>{const label=b.textContent.trim();b.setAttribute('aria-label',label);b.querySelector('i')?.remove();b.textContent='';const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');const shape=document.createElementNS('http://www.w3.org/2000/svg','path');shape.setAttribute('d',icons[b.dataset.page]||icons.plan);svg.append(shape);const span=document.createElement('span');span.className='iv-nav-label';span.textContent=label;b.append(svg,span)});
 function update(){const active=buttons.findIndex(b=>b.classList.contains('active'));if(active<0)return;const css=getComputedStyle(nav),left=parseFloat(css.paddingLeft)||0,right=parseFloat(css.paddingRight)||0,unit=(nav.clientWidth-left-right)/(buttons.length+factor-1);nav.style.setProperty('--iv-pill-x',`${left+active*unit}px`);nav.style.setProperty('--iv-pill-width',`${unit*factor}px`);buttons.forEach((b,i)=>{if(i===active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')});nav.classList.add('iv-ready')}
 const observer=new MutationObserver(records=>{if(records.some(r=>r.attributeName==='class'))update()});buttons.forEach(b=>observer.observe(b,{attributes:true,attributeFilter:['class']}));window.addEventListener('resize',update,{passive:true});update();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
