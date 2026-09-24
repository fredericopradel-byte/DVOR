/* Relatório A4 local, com o mesmo cabeçalho e codificação PDF dos relatórios de inspeção. */
(function(){
'use strict';
const W=1240,H=1754,M=76,R=W-M,B=1625,enc=new TextEncoder();
async function exportReport(data){
  const pages=[];let canvas,ctx,y;
  const font=(size=23,bold=false)=>{ctx.font=`${bold?'700':'400'} ${size}px Arial, sans-serif`};
  function line(s,x,at,size=23,color='#172126',bold=false){font(size,bold);ctx.fillStyle=color;ctx.fillText(String(s),x,at)}
  function start(){canvas=document.createElement('canvas');canvas.width=W;canvas.height=H;ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,W,H);ctx.fillStyle='#172126';ctx.fillRect(0,0,W,145);ctx.fillStyle='#078dd1';ctx.fillRect(0,140,W,5);line('IV-PLANNER',M,64,26,'#55caff',true);line(`Plano de voo • ${data.aircraft}`,M,112,38,'#fff',true);line('RELATÓRIO DE APOIO OPERACIONAL',M,169,17,'#58646c',true);line(new Date().toLocaleString('pt-BR'),R-245,169,17,'#58646c');y=207}
  async function finish(){ctx.strokeStyle='#d5dce0';ctx.beginPath();ctx.moveTo(M,1685);ctx.lineTo(R,1685);ctx.stroke();line('IV-PLANNER  •  Planejamento de voo',M,1715,18,'#58646c');line(`Página ${pages.length+1}`,R-110,1715,18,'#58646c');const blob=await new Promise((ok,fail)=>canvas.toBlob(b=>b?ok(b):fail(Error('Falha ao montar página')),'image/jpeg',.86));pages.push(new Uint8Array(await blob.arrayBuffer()));canvas.width=0}
  async function room(h){if(y+h>B){await finish();start()}}
  function wrapped(s,x,width,size=22){font(size);const result=[];let row='';for(const word of String(s??'—').split(/\s+/)){let fragment=word;while(ctx.measureText(fragment).width>width){let n=1;while(n<fragment.length&&ctx.measureText(fragment.slice(0,n+1)).width<=width)n++;if(row){result.push(row);row=''}result.push(fragment.slice(0,n));fragment=fragment.slice(n)}if(!fragment)continue;const candidate=row?row+' '+fragment:fragment;if(row&&ctx.measureText(candidate).width>width){result.push(row);row=fragment}else row=candidate}if(row)result.push(row);return result.length?result:['—']}
  start();
  for(const section of data.sections){await room(80);ctx.fillStyle='#172126';ctx.fillRect(M,y,R-M,46);line(section.title.toUpperCase(),M+16,y+32,21,'#fff',true);y+=62;
    for(const [label,value] of section.rows){const lines=wrapped(value,M+18,R-M-36,22),height=34+lines.length*31;await room(height+8);ctx.fillStyle='#f0f3f5';ctx.fillRect(M,y,R-M,height);line(label.toUpperCase(),M+17,y+23,16,'#58646c',true);lines.forEach((part,i)=>line(part,M+18,y+52+i*31,22));y+=height+8}y+=17;
  }
  await finish();
  const objects=['<< /Type /Catalog /Pages 2 0 R >>',`<< /Type /Pages /Kids [${pages.map((_,i)=>`${4+i*3} 0 R`).join(' ')}] /Count ${pages.length} >>`,'<< /Producer (IV-PLANNER) >>'];
  pages.forEach((jpeg,i)=>{const page=4+i*3,image=page+1,content=page+2,command=`q 595 0 0 842 0 0 cm /Im${i} Do Q`;objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /XObject << /Im${i} ${image} 0 R >> >> /Contents ${content} 0 R >>`,{head:`<< /Type /XObject /Subtype /Image /Width ${W} /Height ${H} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpeg.length} >>\nstream\n`,body:jpeg},`<< /Length ${enc.encode(command).length} >>\nstream\n${command}\nendstream`)});
  const parts=[enc.encode('%PDF-1.4\n')],offsets=[0];let offset=parts[0].length;objects.forEach((obj,i)=>{offsets.push(offset);const head=enc.encode(`${i+1} 0 obj\n`);parts.push(head);offset+=head.length;if(typeof obj==='string'){const body=enc.encode(`${obj}\nendobj\n`);parts.push(body);offset+=body.length}else{const before=enc.encode(obj.head),after=enc.encode('\nendstream\nendobj\n');parts.push(before,obj.body,after);offset+=before.length+obj.body.length+after.length}});
  const trailer=`xref\n0 ${objects.length+1}\n0000000000 65535 f \n${offsets.slice(1).map(n=>`${String(n).padStart(10,'0')} 00000 n \n`).join('')}trailer\n<< /Size ${objects.length+1} /Root 1 0 R /Info 3 0 R >>\nstartxref\n${offset}\n%%EOF`;
  const blob=new Blob([...parts,enc.encode(trailer)],{type:'application/pdf'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`IV-PLANNER-PLANO-${data.aircraft.replace(/[^a-zA-Z0-9-]/g,'-')}.pdf`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
}
window.IVFlightReport={exportReport};
})();
