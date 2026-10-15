/* Relatório A4 local para os planejamentos das aeronaves. */
(function(){
'use strict';
const W=1240,H=1754,M=76,R=W-M,B=1625,enc=new TextEncoder();
async function exportReport(data){
 const pages=[];let canvas,ctx,y;
 const font=(s=23,b=false)=>ctx.font=`${b?'700':'400'} ${s}px Arial,sans-serif`;
 const text=(v,x,yy,s=23,c='#172126',b=false)=>{font(s,b);ctx.fillStyle=c;ctx.fillText(String(v??'—'),x,yy)};
 function start(subtitle='PLANEJAMENTO DE VOO'){canvas=document.createElement('canvas');canvas.width=W;canvas.height=H;ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,W,H);ctx.fillStyle='#172126';ctx.fillRect(0,0,W,145);ctx.fillStyle='#078dd1';ctx.fillRect(0,140,W,5);text('IV-PLANNER',M,64,26,'#55caff',true);text(`Plano de voo • ${data.aircraft}`,M,112,38,'#fff',true);text(subtitle,M,169,17,'#58646c',true);text(new Date().toLocaleString('pt-BR'),R-245,169,17,'#58646c');y=207}
 async function finish(){ctx.strokeStyle='#d5dce0';ctx.beginPath();ctx.moveTo(M,1685);ctx.lineTo(R,1685);ctx.stroke();text('IV-PLANNER  •  Planejamento de voo',M,1715,18,'#58646c');text(`Página ${pages.length+1}`,R-110,1715,18,'#58646c');const blob=await new Promise((ok,no)=>canvas.toBlob(v=>v?ok(v):no(Error('Falha ao montar página')),'image/jpeg',.87));pages.push(new Uint8Array(await blob.arrayBuffer()));canvas.width=0}
 function wrap(value,width,size=22,bold=false){
  font(size,bold);const out=[];
  for(const paragraph of String(value??'—').split(/\r?\n/)){
   let row='';
   for(let word of paragraph.split(/\s+/).filter(Boolean)){
    if(row&&ctx.measureText(row+' '+word).width>width){out.push(row);row=''}
    while(ctx.measureText(word).width>width){let n=1;while(n<word.length&&ctx.measureText(word.slice(0,n+1)).width<=width)n++;out.push(word.slice(0,n));word=word.slice(n)}
    row=row?row+' '+word:word;
   }
   out.push(row);
  }
  return out;
 }
 function heading(label,sub=''){y+=28;text(label,M,y,33,'#172126',true);if(sub)text(sub,M,y+29,18,'#58646c');y+=sub?68:42}
 function rounded(x,yy,w,h,fill='#f0f3f5',stroke=null,r=18){const radius=Math.min(r,w/2,h/2);ctx.beginPath();ctx.moveTo(x+radius,yy);ctx.lineTo(x+w-radius,yy);ctx.arcTo(x+w,yy,x+w,yy+radius,radius);ctx.lineTo(x+w,yy+h-radius);ctx.arcTo(x+w,yy+h,x+w-radius,yy+h,radius);ctx.lineTo(x+radius,yy+h);ctx.arcTo(x,yy+h,x,yy+h-radius,radius);ctx.lineTo(x,yy+radius);ctx.arcTo(x,yy,x+radius,yy,radius);ctx.closePath();ctx.fillStyle=fill;ctx.fill();if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=2;ctx.stroke()}}
 // Cada bloco é medido antes de desenhar; blocos maiores que uma página têm continuação explícita.
 async function room(height){if(y+height>B){await finish();start('PLANEJAMENTO • CONTINUAÇÃO')}}
 async function section(label){await room(180);heading(label)}
 async function rows(items){
  for(const [label,value] of items){
   const labels=wrap(String(label).toUpperCase(),R-M-36,16,true),lines=wrap(value,R-M-36,22);
   let offset=0;
   while(offset<lines.length){
    const header=labels.length*23+18;
    const whole=header+lines.length*31+14;
    await room(Math.min(whole,B-207));
    const count=Math.min(lines.length-offset,Math.max(1,Math.floor((B-y-header-14)/31)));
    const h=header+count*31+14;rounded(M,y,R-M,h);
    labels.forEach((v,i)=>text(v,M+18,y+23+i*23,16,'#58646c',true));
    if(offset)text('CONTINUAÇÃO',R-150,y+23,14,'#58646c');
    lines.slice(offset,offset+count).forEach((v,i)=>text(v,M+18,y+header+23+i*31,22));
    y+=h+9;offset+=count;
   }
  }
 }
 async function metrics(items,columns=3){
  const gap=12,w=(R-M-gap*(columns-1))/columns;
  for(let i=0;i<items.length;i+=columns){
   const chunk=items.slice(i,i+columns).map(([label,value])=>({labels:wrap(String(label).toUpperCase(),w-28,15,true),values:wrap(value,w-28,26,true)}));
   const labelH=Math.max(...chunk.map(c=>c.labels.length))*21+12;
   let offset=0,total=Math.max(...chunk.map(c=>c.values.length));
   while(offset<total){
    await room(Math.min(labelH+(total-offset)*34+22,B-207));
    const count=Math.min(total-offset,Math.max(1,Math.floor((B-y-labelH-22)/34))),h=labelH+count*34+22;
    chunk.forEach((c,j)=>{const x=M+j*(w+gap);rounded(x,y,w,h);c.labels.forEach((v,k)=>text(v,x+14,y+24+k*21,15,'#58646c',true));c.values.slice(offset,offset+count).forEach((v,k)=>text(v,x+14,y+labelH+27+k*34,26,'#172126',true))});
    y+=h+12;offset+=count;
   }
  }
 }
 async function totalsPage(){
  start('RESUMO GERAL');await section('Números totais do voo');await metrics(data.totals.metrics);
  await section('Rota planejada');await rows([['Rota',data.totals.route]]);
  await section('Pesos e carga');await rows(data.totals.weights);
  await section('Verificações');await rows(data.checks);await finish();
 }
 async function legPage(leg,isAlternate=false){
  start(isAlternate?'ALTERNATIVA':'ETAPA DE VOO');heading(isAlternate?'Alternativa':'Etapa '+leg.number,leg.type);
  await rows([['Trecho',leg.route],['Aeródromos',leg.airports]]);
  await section('Dados do trecho');await metrics([['Distância',leg.distance],['TEV',leg.time],['Nível',leg.level],['Consumo',leg.burn],['Fuel início',leg.fuelStart],['Fuel fim',leg.fuelEnd]]);
  await section('Pesos estimados');await metrics([['TOW início',leg.weightStart],['Peso fim',leg.weightEnd],['ZFW',leg.zfw]]);
  if(leg.note){await section('Observação');await rows([['Informação',leg.note]])}await finish();
 }
 async function weatherPages(){
  start('METEOROLOGIA');heading('Meteorologia do planejamento','Boletins e condições usadas nos cálculos');
  if(!data.weather.length)await rows([['Boletins','Não há aeródromos definidos no planejamento.']]);
  for(const wx of data.weather){
   await section(`${wx.label} • ${wx.icao}`);
   await rows([['Aeródromo',wx.airport],['Condições usadas',wx.conditions],['Cabeceira / componente',wx.runway],['Performance',wx.performance],['METAR completo',wx.metar],['TAF completo',wx.taf]]);y+=10;
  }
  await finish();
 }
 await totalsPage();for(const leg of data.legs)await legPage(leg);await legPage(data.alternate,true);await weatherPages();
 const objects=['<< /Type /Catalog /Pages 2 0 R >>',`<< /Type /Pages /Kids [${pages.map((_,i)=>`${4+i*3} 0 R`).join(' ')}] /Count ${pages.length} >>`,'<< /Producer (IV-PLANNER) >>'];pages.forEach((jpeg,i)=>{const page=4+i*3,image=page+1,content=page+2,cmd=`q 595 0 0 842 0 0 cm /Im${i} Do Q`;objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /XObject << /Im${i} ${image} 0 R >> >> /Contents ${content} 0 R >>`,{head:`<< /Type /XObject /Subtype /Image /Width ${W} /Height ${H} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpeg.length} >>\nstream\n`,body:jpeg},`<< /Length ${enc.encode(cmd).length} >>\nstream\n${cmd}\nendstream`)});
 const parts=[enc.encode('%PDF-1.4\n')],offsets=[0];let at=parts[0].length;objects.forEach((o,i)=>{offsets.push(at);const h=enc.encode(`${i+1} 0 obj\n`);parts.push(h);at+=h.length;if(typeof o==='string'){const b=enc.encode(`${o}\nendobj\n`);parts.push(b);at+=b.length}else{const before=enc.encode(o.head),after=enc.encode('\nendstream\nendobj\n');parts.push(before,o.body,after);at+=before.length+o.body.length+after.length}});const trailer=`xref\n0 ${objects.length+1}\n0000000000 65535 f \n${offsets.slice(1).map(n=>`${String(n).padStart(10,'0')} 00000 n \n`).join('')}trailer\n<< /Size ${objects.length+1} /Root 1 0 R /Info 3 0 R >>\nstartxref\n${at}\n%%EOF`;const blob=new Blob([...parts,enc.encode(trailer)],{type:'application/pdf'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`IV-PLANNER-PLANO-${data.aircraft.replace(/[^a-zA-Z0-9-]/g,'-')}.pdf`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000)
}
window.IVFlightReport={exportReport};
})();
