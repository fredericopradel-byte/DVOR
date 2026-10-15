/* Relatórios locais A4: usa apenas Canvas e o exportador PDF incorporado. */
(function () {
  'use strict';
  const W = 1240, H = 1754, M = 76, RIGHT = W - M, BOTTOM = 1630;
  const C = { ink:'#172126', muted:'#58646c', blue:'#078dd1', red:'#df354c', green:'#188957', amber:'#b47712', pale:'#f0f3f5', line:'#d5dce0', map:'#111619' };
  const enc = new TextEncoder();
  const bytes = value => enc.encode(value);
  const human = v => v === undefined || v === null || v === '' ? '—' : String(v);
  const date = v => { const d = new Date(v); return v && !Number.isNaN(d.getTime()) ? d.toLocaleString('pt-BR') : human(v); };
  const safeName = v => String(v || 'missao').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-zA-Z0-9_-]+/g,'-').slice(0,55) || 'missao';
  let canvas, ctx, pages, y, title, stamp;

  function font(size=25, weight=400) { ctx.font = `${weight >= 600 ? 700 : 400} ${size}px Arial, sans-serif`; }
  function line(text,x,yy,size=25,color=C.ink,weight=400) { font(size,weight);ctx.fillStyle=color;ctx.fillText(human(text),x,yy); }
  function box(x,yy,w,h,fill=C.pale,r=15,stroke=null) {
    ctx.beginPath();ctx.roundRect(x,yy,w,h,r);ctx.fillStyle=fill;ctx.fill();
    if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=2;ctx.stroke();}
  }
  // Medição em pixels com a mesma fonte do desenho, inclusive palavras sem espaços.
  function textLines(value,width,size=23,weight=400){
    font(size,weight);const lines=[];
    for(const paragraph of human(value).split(/\r?\n/)){
      let row='';
      for(let word of paragraph.split(/\s+/).filter(Boolean)){
        if(row&&ctx.measureText(row+' '+word).width>width){lines.push(row);row='';}
        while(ctx.measureText(word).width>width){
          let n=1;while(n<word.length&&ctx.measureText(word.slice(0,n+1)).width<=width)n++;
          lines.push(word.slice(0,n));word=word.slice(n);
        }
        row=row?row+' '+word:word;
      }
      lines.push(row);
    }
    return lines;
  }
  function wrap(text,x,yy,maxWidth,size=23,color=C.ink,weight=400,leading=32){
    const lines=textLines(text,maxWidth,size,weight);
    lines.forEach((v,i)=>line(v,x,yy+i*leading,size,color,weight));return yy+lines.length*leading;
  }
  function contentRows(value,size=23,color=C.ink,weight=400,leading=32,width=RIGHT-M-48){
    return textLines(value,width,size,weight).map(text=>({text,size,color,weight,leading}));
  }
  async function flowCard(rows,drawHeader,fill=C.pale,accent=null){
    let offset=0;
    while(offset<rows.length){
      const remaining=rows.slice(offset).reduce((n,r)=>n+r.leading,0);
      await room(Math.min(66+remaining+12,BOTTOM-206));
      let count=0,height=66;
      while(offset+count<rows.length&&y+height+rows[offset+count].leading+12<=BOTTOM){height+=rows[offset+count].leading;count++;}
      const top=y;box(M,top,RIGHT-M,height+4,fill,14,C.line);
      if(accent){ctx.fillStyle=accent;ctx.fillRect(M,top,9,height+4);}
      drawHeader(top,offset>0,height+4);
      let at=top+66;
      for(const row of rows.slice(offset,offset+count)){if(row.swatch)box(M+23,at-17,19,19,row.swatch,3,C.line);line(row.text,M+23+(row.inset||0),at,row.size,row.color,row.weight);at+=row.leading;}
      y=top+height+16;offset+=count;
    }
  }
  function newPage(){
    canvas=document.createElement('canvas');canvas.width=W;canvas.height=H;
    ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,W,H);
    ctx.fillStyle=C.ink;ctx.fillRect(0,0,W,145);ctx.fillStyle=C.blue;ctx.fillRect(0,140,W,5);
    line('IV-PLANNER',M,64,26,'#55caff',800);
    font(40,700);let heading=title;while(heading.length>4&&ctx.measureText(heading).width>RIGHT-M)heading=heading.slice(0,-2)+'…';
    line(heading,M,112,40,'#fff',700);
    line('RELATÓRIO DE APOIO OPERACIONAL',M,168,17,C.muted,700);
    line(stamp,RIGHT-310,168,17,C.muted);y=206;
  }
  async function endPage(){
    ctx.strokeStyle=C.line;ctx.beginPath();ctx.moveTo(M,1685);ctx.lineTo(RIGHT,1685);ctx.stroke();
    line('IV-PLANNER  •  Registro da missão',M,1715,18,C.muted);
    line(`Página ${pages.length+1}`,RIGHT-110,1715,18,C.muted);
    const blob=await new Promise((resolve,reject)=>canvas.toBlob(value=>value?resolve(value):reject(Error('Falha ao montar a página PDF.')),'image/jpeg',.86));
    pages.push(new Uint8Array(await blob.arrayBuffer()));canvas.width=0;canvas.height=0;
  }
  async function room(height){if(y+height>BOTTOM){await endPage();newPage();}}
  function section(label){box(M,y,RIGHT-M,47,C.ink,10);line(label.toUpperCase(),M+18,y+33,22,'#fff',700);y+=65;}
  async function metadata(items){
    const filtered=items.filter(([key,value])=>value!==''&&value!==null&&value!==undefined),w=(RIGHT-M-14)/2;
    for(let i=0;i<filtered.length;i+=2){
      const row=filtered.slice(i,i+2).map(([key,value])=>({labels:textLines(key.toUpperCase(),w-28,16,700),values:textLines(value,w-28,24,700)}));
      const header=Math.max(...row.map(c=>c.labels.length))*22+15,total=Math.max(...row.map(c=>c.values.length));let offset=0;
      while(offset<total){
        await room(Math.min(header+(total-offset)*32+16,BOTTOM-206));
        const count=Math.min(total-offset,Math.max(1,Math.floor((BOTTOM-y-header-16)/32))),h=header+count*32+16;
        row.forEach((c,j)=>{const x=M+j*(w+14);box(x,y,w,h,C.pale,10);c.labels.forEach((v,k)=>line(v,x+14,y+23+k*22,16,C.muted,700));c.values.slice(offset,offset+count).forEach((v,k)=>line(v,x+14,y+header+24+k*32,24,C.ink,700));});
        y+=h+10;offset+=count;
      }
    }
    y+=12;
  }
  function svgImage(markup){return new Promise((resolve,reject)=>{
    const blob=new Blob([markup],{type:'image/svg+xml;charset=utf-8'}),url=URL.createObjectURL(blob),img=new Image();
    img.onload=()=>{URL.revokeObjectURL(url);resolve(img)};
    img.onerror=()=>{URL.revokeObjectURL(url);reject(Error('Não foi possível incluir um desenho no PDF.'))};
    img.src=url;
  });}
  function captureMap(svg){
    const original=svg.cloneNode(true), source=[svg,...svg.querySelectorAll('*')], targets=[original,...original.querySelectorAll('*')];
    source.forEach((node,i)=>{
      const style=getComputedStyle(node), target=targets[i];
      for(const prop of ['fill','stroke','stroke-width','stroke-dasharray','opacity','font-size','font-family','font-weight','text-anchor','paint-order']){
        const val=style.getPropertyValue(prop);if(val)target.style.setProperty(prop,val);
      }
    });
    original.querySelector('#aircraft-layer,#map-aircraft')?.remove();
    original.querySelectorAll('#rose-lines path,#rose-lines line,#map-routes path').forEach(route=>{
      route.style.opacity='.9';
      route.style.strokeWidth='3';
    });
    original.querySelector('#map-world')?.removeAttribute('transform');
    original.setAttribute('viewBox','0 0 500 500');original.setAttribute('width','500');original.setAttribute('height','500');
    original.setAttribute('xmlns','http://www.w3.org/2000/svg');
    original.style.background=C.map;
    return new XMLSerializer().serializeToString(original);
  }
  async function mapPair(maps){
    await room(665);section('Trajetórias planejadas');const w=(RIGHT-M-18)/2;
    for(let i=0;i<2;i++){
      const x=M+i*(w+18);box(x,y,w,580,C.map,14);
      line(i?'GRUPOS • COR':'TRANSMISSORES • TX',x+15,y+32,19,'#fff',700);
      const image=await svgImage(maps[i]);ctx.drawImage(image,x+6,y+42,w-12,w-12);
    }
    y+=598;
  }
  async function flightCards(cards){
    await room(cards.length?240:130);section('Passagens na ordem atual');
    if(!cards.length){line('Nenhuma passagem planejada.',M,y+30,26,C.muted);y+=55;return;}
    for(let i=0;i<cards.length;i++){
      const card=cards[i],accent=card.tx==='TX2'?C.red:C.blue;
      const rows=[...contentRows(card.description,25,card.done?'#4d585c':C.ink,700,33),...contentRows(card.detail,21,C.muted,400,29)];
      if(card.group)rows.push(...contentRows(`GRUPO  •  ${card.group}`,18,card.groupColor||C.amber,700,27));
      await flowCard(rows,(top,continued,height)=>{
        if(continued)line('CONTINUAÇÃO',RIGHT-360,top+34,16,C.muted,700);
      line(`${String(i+1).padStart(2,'0')}   ${card.tx}   ${card.type||''}`,M+23,y+34,23,accent,750);
      line(card.done?'CONCLUÍDA':card.current?'ATUAL':'A FAZER',RIGHT-195,y+34,19,card.done?C.green:C.muted,750);
      },card.done?'#e7ebec':C.pale,accent);
    }
  }
  async function papiPass(pass,index){
    const nums=(pass.boxNumbers||[]).map((n,i)=>`Caixa ${n}: ${human(pass.values?.[i])}°`).join('    •    ');
    const results=pass.results||{},clr=pass.clearance||{};
    const rows=contentRows(nums,22);
    for(const [label,key,sat] of [['Inferior','lower','lowerSat'],['Central','center','centerSat'],['Superior','upper','upperSat'],['Rampa','ramp','rampSat']]){
      rows.push(...contentRows(`${label}   ${human(results[key])}°   ${results[sat]?'SAT':'DEF'}`,22,results[sat]?C.green:C.red,700,32));
    }
    rows.push(...contentRows(clr.pending?'Clearance pendente':`Clearance ${human(clr.angle)}°`,23,C.amber,700));
    if(clr.source)rows.push(...contentRows(clr.source,20,C.muted,400,28));
    if(pass.sectors?.length){
      rows.push(...contentRows('INDICAÇÕES POR SETOR ANGULAR',18,C.muted,700,28));
      const colors=['#681f2a','#87323d','#66535a','#9b8d91','#e7e9ea'];
      pass.sectors.forEach((sector,i)=>{const parts=contentRows(sector,19,C.ink,400,27,RIGHT-M-78);parts.forEach((r,j)=>{r.inset=30;if(j===0)r.swatch=colors[i]||C.pale;});rows.push(...parts);});
    }
    if(pass.note)rows.push(...contentRows(`Observação: ${pass.note}`,20,C.ink,400,28));
    const passHeight=65+578+66+rows.reduce((n,row)=>n+row.leading,0)+16;
    await room(Math.min(passHeight,BOTTOM-206));
    section(`Passagem ${pass.number||index+1}  •  ${date(pass.createdAt)}`);
    box(M,y,RIGHT-M,560,C.map,14);
    const img=await svgImage(pass.svg),imageWidth=Math.min(RIGHT-M-40,536*365/220);
    ctx.drawImage(img,M+(RIGHT-M-imageWidth)/2,y+12,imageWidth,536);y+=578;
    await flowCard(rows,(top,continued)=>line(`PASSAGEM ${pass.number||index+1}${continued?' • CONTINUAÇÃO':''}`,M+23,top+34,21,C.ink,700));
  }
  function encodePdf(jpegs){
    const objects=[];const ref=(n)=>`${n} 0 R`;
    objects.push('<< /Type /Catalog /Pages 2 0 R >>');
    objects.push(`<< /Type /Pages /Kids [${jpegs.map((_,i)=>ref(4+i*3)).join(' ')}] /Count ${jpegs.length} >>`);
    objects.push(null);
    jpegs.forEach((jpeg,i)=>{
      const page=4+i*3,image=page+1,content=page+2;
      objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /XObject << /Im${i} ${ref(image)} >> >> /Contents ${ref(content)} >>`);
      objects.push({head:`<< /Type /XObject /Subtype /Image /Width ${W} /Height ${H} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpeg.length} >>\nstream\n`,body:jpeg});
      const command=`q 595 0 0 842 0 0 cm /Im${i} Do Q`;
      objects.push(`<< /Length ${bytes(command).length} >>\nstream\n${command}\nendstream`);
    });
    objects[2]='<< /Producer (IV-PLANNER) >>';
    const parts=[bytes('%PDF-1.4\n')],offsets=[0];let offset=parts[0].length;
    objects.forEach((object,i)=>{
      offsets.push(offset);
      const head=bytes(`${i+1} 0 obj\n`);parts.push(head);offset+=head.length;
      if(typeof object==='string'){const body=bytes(`${object}\nendobj\n`);parts.push(body);offset+=body.length;}
      else{const before=bytes(object.head),after=bytes('\nendstream\nendobj\n');parts.push(before,object.body,after);offset+=before.length+object.body.length+after.length;}
    });
    const xref=offset;const trailer=`xref\n0 ${objects.length+1}\n0000000000 65535 f \n${offsets.slice(1).map(n=>`${String(n).padStart(10,'0')} 00000 n \n`).join('')}trailer\n<< /Size ${objects.length+1} /Root 1 0 R /Info 3 0 R >>\nstartxref\n${xref}\n%%EOF`;
    parts.push(bytes(trailer));return new Blob(parts,{type:'application/pdf'});
  }
  function save(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`IV-PLANNER-${name}.pdf`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);}
  async function exportReport(data){
    title=`${data.kind}  •  ${human(data.name)}`;stamp=new Date().toLocaleString('pt-BR');pages=[];newPage();
    section('Identificação da missão e do auxílio');
    const meta=(data.meta||[]).slice();
    if(data.name&&!meta.some(([,value])=>String(value)===String(data.name)))meta.unshift(['Missão',data.name]);
    await metadata(meta);
    if(data.kind==='PAPI'){
      await room(55);section(`Resultados  •  ${data.passes.length} passagem(ns)`);
      if(!data.passes.length){line('Nenhuma passagem registrada.',M,y+30,26,C.muted);y+=65;}
      for(let i=0;i<data.passes.length;i++)await papiPass(data.passes[i],i);
    }else{
      await mapPair(data.maps);
      await flightCards(data.cards);
    }
    await endPage();save(encodePdf(pages),`${data.kind}-${safeName(data.name)}`);
  }
  window.IVReport={exportReport,captureMap};
})();
