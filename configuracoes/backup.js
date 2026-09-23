(()=>{'use strict';
const FORMAT='ivplanner-backup',VERSION=1,MAX_BYTES=20*1024*1024;
const GROUPS={
 'iv-planner-saved-missions-v1':{type:'list',id:'savedMissionId',label:'missões DVOR/VOR'},
 'ivplanner-papi-missions-v1':{type:'list',id:'savedMissionId',label:'missões PAPI'},
 'ivplanner-custom-localities-v1':{type:'list',id:'icao',label:'localidades manuais'},
 'ivplanner-custom-aids-v1':{type:'list',id:'id',label:'auxílios manuais'},
 'geiv-dvor-manual-offline-v1':{type:'record',label:'rascunho DVOR/VOR'},
 'ivplanner-papi-current-v1':{type:'record',label:'rascunho PAPI'},
 'ivplanner-legacy-v1':{type:'record',label:'planejamento Legacy'},
 'ivplanner-legacy-defaults-v1':{type:'record',label:'Defaults Legacy'},
 'ivplanner-hawker-v1':{type:'record',label:'planejamento Hawker'},
 'ivplanner-hawker-defaults-v1':{type:'record',label:'Defaults Hawker'},
 'iv-weather-last':{type:'record',label:'última meteorologia'},
 'ivplanner-global-nav-v1':{type:'record',label:'memória da navegação'}
};
const $=id=>document.getElementById(id),status=$('backup-status'),preview=$('backup-preview');
let pending=null;
function validRecord(x){return x!==null&&typeof x==='object'&&!Array.isArray(x)}
function identity(item,spec){const raw=item[spec.id];return typeof raw==='string'&&raw.trim()?raw.trim().toUpperCase():JSON.stringify(item)}
function validateValue(key,value){const spec=GROUPS[key];if(!spec)throw Error('O arquivo contém uma categoria desconhecida.');if(spec.type==='record'){if(!validRecord(value))throw Error(`Dados inválidos em ${spec.label}.`);
 if(key==='geiv-dvor-manual-offline-v1'&&(!validRecord(value.metadata)||!Array.isArray(value.activities)))throw Error('Rascunho DVOR/VOR inválido.');
 if(key==='ivplanner-papi-current-v1'&&(!validRecord(value.metadata)||!Array.isArray(value.passes)))throw Error('Rascunho PAPI inválido.');
 if(key==='ivplanner-legacy-v1'&&!Array.isArray(value.legs))throw Error('Planejamento Legacy inválido.');
 if(key==='ivplanner-hawker-v1'&&!Array.isArray(value.legs))throw Error('Planejamento Hawker inválido.');
 return}
 if(!Array.isArray(value)||value.some(x=>!validRecord(x)))throw Error(`Lista inválida em ${spec.label}.`);
 const seen=new Set();for(const item of value){if(key.includes('missions')&&(!validRecord(item.metadata)||!Array.isArray(key.startsWith('ivplanner-papi')?item.passes:item.activities)))throw Error(`Missão inválida em ${spec.label}.`);if(key==='ivplanner-custom-localities-v1'&&typeof item.icao!=='string')throw Error('Localidade sem ICAO.');if(key==='ivplanner-custom-aids-v1'&&typeof item.id!=='string')throw Error('Auxílio sem identificação.');const id=identity(item,spec);if(seen.has(id))throw Error(`Identificação duplicada em ${spec.label}.`);seen.add(id)}
}
function snapshot(){const data={};for(const key of Object.keys(GROUPS)){const raw=localStorage.getItem(key);if(raw!==null){let value;try{value=JSON.parse(raw)}catch{throw Error(`Não foi possível ler ${GROUPS[key].label} neste aparelho.`)}validateValue(key,value);data[key]=value}}return data}
function archive(data){return{format:FORMAT,version:VERSION,createdAt:new Date().toISOString(),data}}
function download(doc,prefix='IV-PLANNER-backup'){const blob=new Blob([JSON.stringify(doc,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a'),stamp=new Date().toISOString().replace(/[:.]/g,'-');a.href=url;a.download=`${prefix}-${stamp}.json`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000)}
function readArchive(text){let doc;try{doc=JSON.parse(text)}catch{throw Error('O arquivo não contém JSON válido.')}if(!validRecord(doc)||doc.format!==FORMAT||doc.version!==VERSION||!validRecord(doc.data)||!Object.keys(doc.data).length)throw Error('Backup não reconhecido ou versão incompatível.');for(const [key,value] of Object.entries(doc.data))validateValue(key,value);return doc}
function mergeList(local,incoming,spec,choice){const result=local.slice(),slots=new Map(result.map((x,i)=>[identity(x,spec),i]));let added=0,conflicts=0;for(const item of incoming){const id=identity(item,spec),pos=slots.get(id);if(pos===undefined){slots.set(id,result.length);result.push(item);added++}else if(JSON.stringify(result[pos])!==JSON.stringify(item)){conflicts++;if(choice==='import')result[pos]=item}}return{value:result,added,conflicts}}
function plan(incoming,local,choice='local'){const result={},stats={added:0,conflicts:0,categories:0};for(const [key,value] of Object.entries(incoming)){const spec=GROUPS[key],existing=local[key];stats.categories++;if(existing===undefined){result[key]=value;if(spec.type==='list')stats.added+=value.length;continue}if(spec.type==='list'){const merged=mergeList(existing,value,spec,choice);result[key]=merged.value;stats.added+=merged.added;stats.conflicts+=merged.conflicts}else{const differs=JSON.stringify(existing)!==JSON.stringify(value);if(differs)stats.conflicts++;result[key]=differs&&choice==='import'?value:existing}}return{result,stats}}
function describe(doc,stats){const counts=Object.entries(doc.data).filter(([k])=>GROUPS[k].type==='list').map(([k,v])=>`${v.length} ${GROUPS[k].label}`);const when=new Date(doc.createdAt);const date=Number.isNaN(when.getTime())?'data não informada':when.toLocaleString('pt-BR');return`Backup de ${date}. ${counts.join(' · ')||'Sem listas de missões ou cadastros'}. ${stats.added} registro(s) novo(s); ${stats.conflicts} conflito(s). Dados existentes sem correspondência no arquivo serão preservados.`}
function apply(doc,choice){const before={};for(const key of Object.keys(GROUPS))before[key]=localStorage.getItem(key);
 const local=snapshot(),merged=plan(doc.data,local,choice),written=[];
 try{for(const [key,value] of Object.entries(merged.result)){const text=JSON.stringify(value);if(before[key]===text)continue;localStorage.setItem(key,text);written.push(key)}}catch(error){let rollbackOk=true;for(const key of written.reverse()){try{if(before[key]===null)localStorage.removeItem(key);else localStorage.setItem(key,before[key])}catch{rollbackOk=false}}throw Error(rollbackOk?'Falha ao gravar. Os dados anteriores foram restaurados.':'Falha ao gravar e restaurar todos os dados. Não feche o aplicativo; preserve o backup anterior.')}return merged.stats}
$('backup-export').addEventListener('click',()=>{try{download(archive(snapshot()));status.textContent='Backup gerado. Guarde o arquivo no app Arquivos ou em outro local seguro.'}catch(e){status.textContent=e.message}});
$('backup-choose').addEventListener('click',()=>$('backup-file').click());
$('backup-file').addEventListener('change',async e=>{preview.hidden=true;pending=null;const file=e.target.files?.[0];e.target.value='';if(!file)return;try{if(file.size>MAX_BYTES)throw Error('O arquivo é grande demais para um backup de registros (limite: 20 MB).');const doc=readArchive(await file.text()),local=snapshot(),assessment=plan(doc.data,local);pending=doc;$('backup-details').textContent=describe(doc,assessment.stats);$('backup-conflict').hidden=!assessment.stats.conflicts;$('backup-conflict').querySelector('[value="local"]').checked=true;preview.hidden=false;status.textContent='Confira a prévia antes de confirmar.'}catch(err){status.textContent=err.message}});
$('backup-cancel').addEventListener('click',()=>{preview.hidden=true;pending=null;status.textContent='Importação cancelada.'});
$('backup-apply').addEventListener('click',()=>{if(!pending)return;try{const current=snapshot(),choice=document.querySelector('input[name="backup-conflict"]:checked')?.value||'local';const assessment=plan(pending.data,current,choice);if(!confirm(`Importar ${assessment.stats.added} registro(s) novo(s) e resolver ${assessment.stats.conflicts} conflito(s) conforme a opção selecionada?`))return;
 if(Object.keys(current).length){download(archive(current),'IV-PLANNER-antes-da-importacao');if(!confirm('Foi iniciado o download de um backup dos dados atuais. Confirme que conseguiu salvá-lo antes de continuar.')){status.textContent='Importação cancelada. Nenhum dado foi alterado.';return}}
 const done=apply(pending,choice);pending=null;preview.hidden=true;status.textContent=`Importação concluída: ${done.added} registro(s) novo(s). Abra novamente as páginas do aplicativo para carregar os dados restaurados.`}catch(err){status.textContent=err.message}});
})();
