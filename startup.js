/* Inicialização local. O painel acompanha verificações reais, sem consultar meteorologia. */
(()=>{
 'use strict';
 const overlay=document.getElementById('iv-startup');if(!overlay)return;
 const base=new URL('.',document.currentScript.src),root=document.documentElement;
 const key='ivplanner-startup-verified-v2',motion=matchMedia('(prefers-reduced-motion: reduce)');
 let shown=false,internal=false;
 const entry=new URL(location.href),requestedRetry=entry.searchParams.get('iv-startup-retry')==='1';
 if(requestedRetry){entry.searchParams.delete('iv-startup-retry');try{history.replaceState(history.state,'',entry);}catch{}}
 try{shown=sessionStorage.getItem(key)==='1';}catch{}
 try{const ref=new URL(document.referrer);internal=ref.origin===base.origin&&ref.pathname.startsWith(base.pathname);}catch{}
 if(!requestedRetry&&(shown||internal||performance.getEntriesByType('navigation')[0]?.type==='back_forward'))return;
 const skip=overlay.querySelector('.iv-startup-skip'),retry=overlay.querySelector('.iv-startup-retry');
 const label=overlay.querySelector('#iv-startup-label'),description=overlay.querySelector('#iv-startup-description');
 const inert=[],focus=document.activeElement,controller=new AbortController();
 let closed=false,timer,transition,warning="",presentationComplete=false;
 function result(){if(warning)state("caution","CAUTION",warning);else state("ready","READY","IV-PLANNER pronto para operação");}
 function warn(event){if(closed||controller.signal.aborted)return;warning=event.detail?.message||"Atualização disponível";if(presentationComplete)result();}
 document.addEventListener("iv-startup-warning",warn);
 const presentationStarted=performance.now(),minimumPresentation=2250;
 function state(name,message,detail){
  overlay.dataset.state=name;label.textContent=message;description.textContent=detail;
  retry.hidden=name!=='fault';
  document.dispatchEvent(new CustomEvent('iv-startup-state',{detail:{state:name}}));
 }
 function close(){
  if(closed)return;closed=true;clearTimeout(timer);clearTimeout(transition);controller.abort();
  overlay.hidden=true;root.removeAttribute('data-iv-startup');
  for(const [node,wasInert] of inert)node.inert=wasInert;
  document.removeEventListener('iv-startup-warning',warn);
  document.removeEventListener('keydown',keyboard,true);window.removeEventListener('pagehide',close);
  if(overlay.contains(document.activeElement)){if(focus&&focus!==document.body&&focus.isConnected)focus.focus();else document.activeElement.blur();}
  document.dispatchEvent(new Event('iv-startup-finished'));
 }
 function fault(message){
  if(closed)return;clearTimeout(timer);controller.abort();
  state('fault','FAULT',message);retry.focus({preventScroll:true});
 }
 function keyboard(event){
  if(event.key==='Escape'){event.preventDefault();close();}
  if(event.key==='Tab'){
   const buttons=[skip,retry].filter(b=>!b.hidden),index=buttons.indexOf(document.activeElement);
   event.preventDefault();buttons[(index+(event.shiftKey?-1:1)+buttons.length)%buttons.length].focus();
  }
 }
 async function resource(path){
  try{
   const response=await fetch(new URL(path,base),{signal:controller.signal});
   if(!response.ok||!(await response.text()).trim())throw Error('unavailable');
  }catch{throw Error(`Não foi possível carregar o recurso essencial ${path}.`);}
 }
 async function stylesheet(path){
  const link=[...document.querySelectorAll('link[rel=stylesheet]')].find(node=>new URL(node.href).pathname===new URL(path,base).pathname);
  if(!link)throw Error(`O estilo essencial ${path} não foi incluído.`);
  if(link.sheet)return;
  await new Promise((resolve,reject)=>{
   const stop=()=>{link.removeEventListener('load',loaded);link.removeEventListener('error',failed);controller.signal.removeEventListener('abort',failed);};
   const loaded=()=>{stop();resolve();};
   const failed=()=>{stop();reject(Error(`Não foi possível aplicar o estilo ${path}.`));};
   link.addEventListener('load',loaded,{once:true});link.addEventListener('error',failed,{once:true});controller.signal.addEventListener('abort',failed,{once:true});
   if(controller.signal.aborted)failed();
  });
 }
 async function check(){
  // Aguardar o parser e os scripts defer existentes, sem inventar trabalho.
  if(document.readyState==='loading')await new Promise(resolve=>document.addEventListener('DOMContentLoaded',resolve,{once:true}));
  if(closed)return;
  state('self-test','SELF TEST','Verificando os recursos locais');
  await Promise.all(['global-nav.js','global-nav.css','page-ui.js','page-ui.css'].map(resource));
  if(closed||controller.signal.aborted)return;
  await Promise.all(['global-nav.css','page-ui.css'].map(stylesheet));
  if(closed||controller.signal.aborted)return;
  if(!document.querySelector('main nav a.card')||!document.querySelector('.ivg-toggle')||!document.querySelector('.iv-help-button')){
   throw Error('A interface principal não concluiu a inicialização.');
  }
  // Somente leitura: não gravar, normalizar nem apagar dados de planejamento.
  try{localStorage.getItem('ivplanner-global-nav-v1');}catch{throw Error('O armazenamento local está indisponível neste navegador.');}
  clearTimeout(timer);
  // Três ciclos de 750 ms; verificações concluídas não deixam o watchdog disparar.
  await new Promise(resolve=>{transition=setTimeout(resolve,Math.max(0,minimumPresentation-(performance.now()-presentationStarted)));});
  if(closed||controller.signal.aborted)return;
  presentationComplete=true;result();
  try{sessionStorage.setItem(key,'1');}catch{}
  transition=setTimeout(close,motion.matches?0:350);
 }
 // O watchdog troca espera indefinida por diagnóstico e ações de recuperação.
 timer=setTimeout(()=>fault('A verificação dos recursos locais excedeu o tempo disponível. Tente novamente.'),3500);
 try{
  root.setAttribute('data-iv-startup','');
  for(const node of document.body.children){if(node!==overlay&&!['SCRIPT','STYLE'].includes(node.tagName)){inert.push([node,node.inert]);node.inert=true;}}
  skip.addEventListener('click',close);retry.addEventListener('click',()=>{const next=new URL(location.href);next.searchParams.set('iv-startup-retry','1');location.replace(next);});
  document.addEventListener('keydown',keyboard,true);window.addEventListener('pagehide',close,{once:true});
  overlay.hidden=false;skip.focus({preventScroll:true});state('energizing','ENERGIZANDO','Acionamento do sistema');
  // Um frame permite desenhar o estado inicial, sem duração mínima artificial.
  requestAnimationFrame(()=>check().catch(error=>{if(!controller.signal.aborted)fault(error.message||'Não foi possível iniciar a interface.');}));
 }catch(error){fault(error.message||'Não foi possível iniciar a interface.');}
})();
