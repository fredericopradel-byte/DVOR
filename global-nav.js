(()=>{
  'use strict';

  const STORAGE_KEY='ivplanner-global-nav-v1';
  const script=document.currentScript||Array.from(document.scripts).find(item=>/\/global-nav\.js(?:\?|$)/.test(item.src));
  if(!script||document.querySelector('.ivg-shell'))return;

  const rootUrl=new URL('./',script.src);
  const scopePath=rootUrl.pathname.endsWith('/')?rootUrl.pathname:`${rootUrl.pathname}/`;
  const icons={
    home:'<path d="M4 10.5 12 4l8 6.5v8.25a1.25 1.25 0 0 1-1.25 1.25H5.25A1.25 1.25 0 0 1 4 18.75Z"/><path d="M9 20v-6h6v6"/>',
    preflight:'<path d="m3 13 7.2-2.1 4.3-7.1 2.1.7-2.5 6.1 5.8 1.5 2.1-1.4.9 1.4-2.7 2.1-5.8-1.5 2.5 6.1-2.1.7-4.3-7.1L3 14.7Z"/>',
    inspection:'<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3"/><path d="M12 1.5v4M12 18.5v4M1.5 12h4M18.5 12h4"/>',
    weather:'<path d="M6.5 17.5h11a4 4 0 0 0 .3-8 6.3 6.3 0 0 0-12-1.2 4.7 4.7 0 0 0 .7 9.2Z"/><path d="M7 21h10"/>',
    localities:'<path d="M12 22s7-6.5 7-13a7 7 0 1 0-14 0c0 6.5 7 13 7 13Z"/><circle cx="12" cy="9" r="2.3"/>',
    settings:'<circle cx="12" cy="12" r="3"/><path d="m12 2.5 1.6 2.4 2.9-.2.2 2.9 2.4 1.6-1.4 2.6 1.4 2.6-2.4 1.6-.2 2.9-2.9-.2-1.6 2.4-1.6-2.4-2.9.2-.2-2.9-2.4-1.6 1.4-2.6-1.4-2.6 2.4-1.6.2-2.9 2.9.2Z"/>'
  };
  const areas=[
    {id:'home',label:'Menu',short:'Menu',path:'index.html',icon:icons.home},
    {id:'preflight',label:'Pré-voo',short:'Pré-voo',path:'prevoo/index.html',icon:icons.preflight},
    {id:'inspection',label:'Inspeção em Voo',short:'Inspeção',path:'inspecao/index.html',icon:icons.inspection},
    {id:'weather',label:'Meteorologia',short:'Meteo',path:'meteorologia/index.html',icon:icons.weather},
    {id:'localities',label:'Localidades e Auxílios',short:'Locais',path:'localidades/index.html',icon:icons.localities},
    {id:'settings',label:'Configurações',short:'Ajustes',path:'configuracoes/index.html',icon:icons.settings}
  ];

  function relativeLocation(url=location){
    if(url.origin!==rootUrl.origin||!url.pathname.startsWith(scopePath))return null;
    const pathname=url.pathname.slice(scopePath.length)||'index.html';
    return `${pathname}${url.search}${url.hash}`;
  }
  function areaFromPath(value){
    const clean=String(value||'').split(/[?#]/,1)[0].replace(/^\.\//,'');
    if(clean===''||clean==='index.html')return'home';
    if(clean==='prevoo'||clean.startsWith('prevoo/'))return'preflight';
    if(clean==='inspecao'||clean.startsWith('inspecao/'))return'inspection';
    if(clean==='meteorologia'||clean.startsWith('meteorologia/'))return'weather';
    if(clean==='localidades'||clean.startsWith('localidades/'))return'localities';
    if(clean==='configuracoes'||clean.startsWith('configuracoes/'))return'settings';
    return null;
  }
  function readMemory(){
    try{
      const parsed=JSON.parse(localStorage.getItem(STORAGE_KEY)||'{}');
      return parsed&&typeof parsed==='object'&&parsed.areas&&typeof parsed.areas==='object'?parsed:{version:1,areas:{}};
    }catch{return{version:1,areas:{}}}
  }
  function writeMemory(memory){
    try{localStorage.setItem(STORAGE_KEY,JSON.stringify(memory))}catch{}
  }
  function validRemembered(area){
    const entry=memory.areas[area.id];
    if(!entry||typeof entry.href!=='string'||areaFromPath(entry.href)!==area.id)return null;
    try{
      const url=new URL(entry.href,rootUrl);
      if(url.origin!==rootUrl.origin||!url.pathname.startsWith(scopePath))return null;
      return{href:url.href,scrollY:Math.max(0,Number(entry.scrollY)||0)};
    }catch{return null}
  }

  const memory=readMemory();
  const currentHref=relativeLocation();
  const currentArea=areaFromPath(currentHref);
  const prior=currentArea&&memory.areas[currentArea]?.href===currentHref?memory.areas[currentArea]:null;

  function rememberCurrent(){
    if(!currentArea||!currentHref)return;
    const activeView=Array.from(document.querySelectorAll('button[data-page].active')).find(button=>!button.closest('.ivg-shell'))?.dataset.page||'';
    memory.version=1;
    memory.areas[currentArea]={href:currentHref,scrollY:Math.max(0,Math.round(window.scrollY||0)),view:activeView,updatedAt:Date.now()};
    writeMemory(memory);
  }

  const styleHref=new URL('global-nav.css?v=20260922-1',rootUrl).href;
  if(!Array.from(document.styleSheets).some(sheet=>sheet.href===styleHref)){
    const link=document.createElement('link');
    link.rel='stylesheet';
    link.href=styleHref;
    document.head.appendChild(link);
  }

  const shell=document.createElement('aside');
  shell.className='ivg-shell';
  shell.setAttribute('aria-label','Acesso rápido às áreas do IV-PLANNER');
  shell.innerHTML=`<nav class="ivg-panel" aria-label="Navegação rápida">
    <ul class="ivg-list">${areas.map(area=>`<li><a class="ivg-link" data-ivg-area="${area.id}" href="${new URL(area.path,rootUrl).href}" aria-label="${area.label}" title="${area.label}"><svg viewBox="0 0 24 24" aria-hidden="true">${area.icon}</svg><span>${area.short}</span></a></li>`).join('')}</ul>
    <button class="ivg-close" type="button" aria-label="Recolher navegação"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 5-7 7 7 7"/></svg></button>
  </nav>
  <button class="ivg-toggle" type="button" aria-label="Abrir navegação rápida" aria-expanded="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 5-7 7 7 7"/></svg></button>`;
  document.body.appendChild(shell);

  const panel=shell.querySelector('.ivg-panel');
  const toggle=shell.querySelector('.ivg-toggle');
  const close=shell.querySelector('.ivg-close');
  const links=Array.from(shell.querySelectorAll('.ivg-link'));

  links.forEach(link=>{
    const area=areas.find(item=>item.id===link.dataset.ivgArea);
    const remembered=area&&validRemembered(area);
    if(area?.id===currentArea&&currentHref){link.href=new URL(currentHref,rootUrl).href;link.setAttribute('aria-current','page')}
    else if(remembered)link.href=remembered.href;
    link.tabIndex=-1;
    link.addEventListener('click',event=>{
      rememberCurrent();
      if(relativeLocation(new URL(link.href))===currentHref){
        event.preventDefault();
        setOpen(false,true);
      }
    });
  });

  function setOpen(open,restoreFocus=false){
    shell.classList.toggle('ivg-open',open);
    toggle.setAttribute('aria-expanded',String(open));
    panel.setAttribute('aria-hidden',String(!open));
    links.forEach(link=>{link.tabIndex=open?0:-1});
    close.tabIndex=open?0:-1;
    if(open)requestAnimationFrame(()=>links.find(link=>link.getAttribute('aria-current')==='page')?.focus({preventScroll:true}));
    else if(restoreFocus)toggle.focus({preventScroll:true});
  }
  setOpen(false);
  toggle.addEventListener('click',()=>setOpen(true));
  close.addEventListener('click',()=>setOpen(false,true));
  document.addEventListener('pointerdown',event=>{
    if(shell.classList.contains('ivg-open')&&!shell.contains(event.target))setOpen(false);
  },{passive:true});
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'&&shell.classList.contains('ivg-open'))setOpen(false,true);
  });

  let scrollTimer=0;
  window.addEventListener('scroll',()=>{
    clearTimeout(scrollTimer);
    scrollTimer=setTimeout(rememberCurrent,500);
  },{passive:true});
  window.addEventListener('pagehide',rememberCurrent);
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')rememberCurrent()});

  if(prior){
    const restore=()=>{
      if(prior.view){
        const viewButton=Array.from(document.querySelectorAll('button[data-page]')).find(button=>button.dataset.page===prior.view&&!button.closest('.ivg-shell'));
        if(viewButton&&!viewButton.classList.contains('active')&&!viewButton.disabled)viewButton.click();
      }
      requestAnimationFrame(()=>{
        window.scrollTo({top:Math.min(Number(prior.scrollY)||0,Math.max(0,document.documentElement.scrollHeight-innerHeight)),left:0,behavior:'auto'});
        rememberCurrent();
      });
    };
    if(document.readyState==='complete')requestAnimationFrame(restore);
    else window.addEventListener('load',()=>requestAnimationFrame(restore),{once:true});
  }
  rememberCurrent();
})();
