(()=>{
  'use strict';

  const STORAGE_KEY='ivplanner-global-nav-v1';
  const script=document.currentScript||Array.from(document.scripts).find(item=>/\/global-nav\.js(?:\?|$)/.test(item.src));
  if(!script||document.querySelector('.ivg-shell'))return;

  const rootUrl=new URL('./',script.src);
  const scopePath=rootUrl.pathname.endsWith('/')?rootUrl.pathname:`${rootUrl.pathname}/`;
  const icons={
    home:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 10.5 12 4l8 6.5v8.25a1.25 1.25 0 0 1-1.25 1.25H5.25A1.25 1.25 0 0 1 4 18.75Z" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/><path d="M9 20v-6h6v6" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/></svg>',
    preflight:'<i class="ivg-plane" aria-hidden="true">✈</i>',
    inspection:'<svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="25" cy="27" r="18" fill="none" stroke="currentColor" stroke-width="3"/><path d="M25 9v7M7 27h7M25 38v7M36 27h7" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/><circle cx="25" cy="27" r="3.5" fill="currentColor"/><path d="M25 27l12-11" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/><path d="M12 46l18-9 18-15 3 2-10 14 13 6-2 4-15-4-12 10-4-1 5-11-12 7z" fill="currentColor" stroke="currentColor" stroke-linejoin="round"/></svg>',
    weather:'<svg viewBox="0 0 64 64" aria-hidden="true"><path d="M19 43h29a10 10 0 0 0 1-20 17 17 0 0 0-32-3A12 12 0 0 0 19 43Z" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M16 51h32M23 58h18" stroke="currentColor" stroke-width="3.2" stroke-linecap="round"/></svg>',
    localities:'<svg viewBox="0 0 64 64" aria-hidden="true"><path d="M32 57s18-16.4 18-33A18 18 0 1 0 14 24c0 16.6 18 33 18 33Z" fill="none" stroke="currentColor" stroke-width="3"/><circle cx="32" cy="24" r="6" fill="none" stroke="currentColor" stroke-width="3"/><path d="M8 56h48" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>',
    settings:'<svg viewBox="0 0 64 64" aria-hidden="true"><path d="M26.5 8h11l2 7a20 20 0 0 1 4.5 2.6l7-1.8 5.5 9.5-5 5.1a20 20 0 0 1 0 5.2l5 5.1-5.5 9.5-7-1.8a20 20 0 0 1-4.5 2.6l-2 7h-11l-2-7a20 20 0 0 1-4.5-2.6l-7 1.8-5.5-9.5 5-5.1a20 20 0 0 1 0-5.2l-5-5.1 5.5-9.5 7 1.8a20 20 0 0 1 4.5-2.6z" fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/><circle cx="32" cy="33" r="8" fill="none" stroke="currentColor" stroke-width="3"/></svg>'
  };
  const areas=[
    {id:'home',label:'Menu',short:'Menu',path:'index.html',icon:icons.home},
    {id:'preflight',label:'Pré-voo',short:'Pré-voo',path:'prevoo/index.html',icon:icons.preflight},
    {id:'inspection',label:'Inspeção em Voo',short:'Inspeção',path:'inspecao/index.html',icon:icons.inspection},
    {id:'weather',label:'Meteorologia',short:'Meteoro',path:'meteorologia/index.html',icon:icons.weather},
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
    <ul class="ivg-list">${areas.map(area=>`<li><a class="ivg-link" data-ivg-area="${area.id}" href="${new URL(area.path,rootUrl).href}" aria-label="${area.label}" title="${area.label}">${area.icon}<span>${area.short}</span></a></li>`).join('')}</ul>
    <button class="ivg-close" type="button" aria-label="Recolher navegação"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 5 7 7-7 7"/></svg></button>
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
