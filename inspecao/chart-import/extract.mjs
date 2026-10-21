import {validateModel, MODEL_SCHEMA} from './reconstruct.mjs';
const MAX_BYTES = 25 * 1024 * 1024, MAX_PIXELS = 24_000_000, MAX_ITEMS = 25000, MAX_OPS = 100000;
let pdfLibrary;
export async function pdfjs() {
  if (!pdfLibrary) pdfLibrary = import('./vendor/pdfjs/pdf.mjs').then(lib => {
    lib.GlobalWorkerOptions.workerSrc = new URL('./vendor/pdfjs/pdf.worker.mjs', import.meta.url).href;
    return lib;
  }).catch(error => {pdfLibrary = null;throw error;});
  return pdfLibrary;
}
export async function sha256(file) {
  const hash = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
  return [...new Uint8Array(hash)].map(n => n.toString(16).padStart(2, '0')).join('');
}
export async function identify(file) {
  if (!(file instanceof Blob) || !file.size || file.size > MAX_BYTES) throw Error('Selecione um PDF, PNG ou JPEG de até 25 MB.');
  const bytes = new Uint8Array(await file.slice(0, 65536).arrayBuffer());
  let mediaType = '';
  if (new TextDecoder().decode(bytes.slice(0, 5)) === '%PDF-') mediaType = 'application/pdf';
  else if ([137,80,78,71,13,10,26,10].every((v, i) => bytes[i] === v)) mediaType = 'image/png';
  else if (bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255) mediaType = 'image/jpeg';
  if (!mediaType) throw Error('Arquivo inválido. O conteúdo não é PDF, PNG ou JPEG.');
  const expected = {'application/pdf': /\.pdf$/i, 'image/png': /\.png$/i, 'image/jpeg': /\.jpe?g$/i};
  if (file.name && !expected[mediaType].test(file.name)) throw Error('A extensão do arquivo não corresponde ao conteúdo.');
  let width, height;
  if (mediaType === 'image/png' && bytes.length >= 24) {
    const view = new DataView(bytes.buffer);width = view.getUint32(16);height = view.getUint32(20);
  } else if (mediaType === 'image/jpeg') {
    let offset = 2;
    // Skip EXIF/ICC segments without assuming the SOF marker is in the first 64 KiB.
    for (let segment=0;segment<1024 && offset + 9 < file.size;segment++) {
      const header = new Uint8Array(await file.slice(offset, offset + 12).arrayBuffer());
      if (header[0] !== 255) break;
      const marker = header[1];
      if (marker === 255) {offset++;continue;}
      if (marker === 218 || marker === 217) break;
      const size = (header[2] << 8) + header[3];
      if (size < 2) break;
      if ([192,193,194,195,197,198,199,201,202,203,205,206,207].includes(marker)) {height = (header[5] << 8) + header[6];width = (header[7] << 8) + header[8];break;}
      offset += size + 2;
    }
  }
  if (mediaType.startsWith('image/') && (!width || !height || width * height > MAX_PIXELS)) throw Error('Imagem sem dimensões válidas ou acima de 24 megapixels. Reduza a imagem antes de importar.');
  const name = String(file.name || 'carta');
  return {name: name.length > 200 ? name.slice(0, 180) + name.slice(-10) : name, size: file.size, mediaType, sha256: await sha256(file)};
}
function groupLines(items) {
  const rows = [];
  for (const item of [...items].sort((a,b) => a.bbox[1] - b.bbox[1] || a.bbox[0] - b.bbox[0])) {
    const row = rows.find(row => Math.abs(row.y - item.bbox[1]) < Math.min(3, item.bbox[3] * .35));
    if (row) row.items.push(item);else rows.push({y: item.bbox[1], items: [item]});
  }
  return rows.map(row => {
    row.items.sort((a,b) => a.bbox[0]-b.bbox[0]);let text = '', previous;
    for (const item of row.items) {
      const gap = previous ? item.bbox[0] - previous.bbox[0] - previous.bbox[2] : 0;
      // Some official PDFs encode each letter separately. Do not manufacture word spaces.
      text += (previous && gap > Math.min(previous.bbox[3], item.bbox[3]) * .18 ? ' ' : '') + item.text;
      previous = item;
    }
    return {text, evidenceIds: row.items.map(i => i.id)};
  });
}
export async function openDocument(file, source) {
  if (source.mediaType === 'application/pdf') {
    const lib = await pdfjs();
    const task = lib.getDocument({data: new Uint8Array(await file.arrayBuffer()), isEvalSupported: false, useSystemFonts: true, stopAtErrors: true});
    // Password protected files must never leave an unresolved password prompt.
    task.onPassword = () => {void task.destroy();};
    let pdf;
    try {pdf = await task.promise;} catch {throw Error('PDF ilegível, protegido por senha ou incompatível. A missão foi preservada.');}
    if (pdf.numPages > 100) {await pdf.destroy();throw Error('PDF acima de 100 páginas. Separe a página da carta antes de importar.');}
    return {
      pages: pdf.numPages,
      async extract(number, canvas) {
        const page = await pdf.getPage(number), viewport = page.getViewport({scale: 1});
        const content = await page.getTextContent();
        const usable = content.items.filter(i => typeof i.str === 'string' && i.str.trim());
        const text = usable.slice(0, MAX_ITEMS).map((item, index) => {
          const m = lib.Util.transform(viewport.transform, item.transform), angle = Math.atan2(m[1], m[0]), width = item.width, height = Math.hypot(m[2], m[3]);
          const xs = [m[4], m[4] + Math.cos(angle)*width, m[4] + Math.sin(angle)*height, m[4] + Math.cos(angle)*width + Math.sin(angle)*height];
          const ys = [m[5], m[5] + Math.sin(angle)*width, m[5] - Math.cos(angle)*height, m[5] + Math.sin(angle)*width - Math.cos(angle)*height];
          return {id: 'page-' + number + '-text-' + index, text: item.str, bbox: [Math.min(...xs), Math.min(...ys), Math.max(...xs)-Math.min(...xs), Math.max(...ys)-Math.min(...ys)], transform: [...item.transform], pageMatrix: [...m], width: item.width, height: item.height, fontName: item.fontName};
        });
        const operators = await page.getOperatorList(), names = new Map(Object.entries(lib.OPS).map(([name, code]) => [code, name]));
        const allowed = new Set(['save','restore','transform','constructPath','stroke','closeStroke','fill','eoFill','fillStroke','eoFillStroke','closeFillStroke','closeEOFillStroke','endPath','clip','eoClip','setLineWidth','setDash']);
        const vectors = [], counts = {};
        const serializable = value => ArrayBuffer.isView(value) ? Array.from(value) : Array.isArray(value) ? value.map(serializable) : value;
        for (let i=0;i<Math.min(operators.fnArray.length, MAX_OPS);i++) {
          const name = names.get(operators.fnArray[i]) || 'unknown';counts[name] = (counts[name] || 0) + 1;
          if (allowed.has(name)) vectors.push({index: i, operator: name, args: serializable(operators.argsArray[i])});
        }
        const result = {method: 'pdfjs-4.10.38', page: number, width: viewport.width, height: viewport.height, rotation: viewport.rotation, pageTransform: [...viewport.transform], coordinateSpace: 'page-points-top-left', text, lines: groupLines(text), vectors, operatorCounts: counts, truncated: usable.length > MAX_ITEMS || operators.fnArray.length > MAX_OPS};
        const scale = Math.min(2, 1500 / Math.max(viewport.width, viewport.height));
        const renderViewport = page.getViewport({scale});canvas.width = Math.ceil(renderViewport.width);canvas.height = Math.ceil(renderViewport.height);
        try {await page.render({canvasContext: canvas.getContext('2d'), viewport: renderViewport}).promise;} finally {page.cleanup();}
        return result;
      },
      destroy: () => pdf.destroy()
    };
  }
  const url = URL.createObjectURL(new Blob([file], {type: source.mediaType})), image = new Image();
  image.src = url;
  try {await image.decode();} catch {URL.revokeObjectURL(url);throw Error('Não foi possível decodificar a imagem.');}
  return {
    pages: 1,
    async extract(number, canvas) {
      const scale = Math.min(1, 1500 / Math.max(image.naturalWidth, image.naturalHeight));
      canvas.width = Math.ceil(image.naturalWidth * scale);canvas.height = Math.ceil(image.naturalHeight * scale);canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
      return {method: 'image-decode', page: 1, width: image.naturalWidth, height: image.naturalHeight, rotation: 0, coordinateSpace: 'image-pixels', text: [], lines: [], vectors: [], operatorCounts: {}, truncated: false};
    },
    destroy: () => URL.revokeObjectURL(url)
  };
}

export async function exportArchive(session, file) {
  const bytes = new Uint8Array(await file.arrayBuffer());let binary = '';
  for (let offset=0;offset<bytes.length;offset+=32768) binary += String.fromCharCode(...bytes.subarray(offset,offset+32768));
  const archive=new Blob([JSON.stringify({format: 'ivplanner-chart-archive', version: 2, module: session.module, page: session.page, source: session.source, reconstruction:session.reconstruction||null, fileBase64: btoa(binary)})], {type: 'application/json'});
  if(archive.size>36*1024*1024)throw Error('Rascunho acima de 36 MB. O arquivo original e o modelo permanecem no aparelho.');return archive;
}
export async function restoreArchive(file, module) {
  if (file.size > 36 * 1024 * 1024) throw Error('Arquivo de rascunho muito grande.');
  const data = JSON.parse(await file.text());
  if (data.format !== 'ivplanner-chart-archive' || ![1,2].includes(data.version) || data.module !== module || !Number.isInteger(data.page) || data.page < 1 || typeof data.fileBase64 !== 'string' || typeof data.source?.name !== 'string') throw Error('Rascunho inválido ou pertencente a outro módulo.');
  const binary = atob(data.fileBase64), bytes = Uint8Array.from(binary, c => c.charCodeAt(0));
  const original = new File([bytes], data.source.name, {type: data.source.mediaType});
  const source = await identify(original);
  if (source.sha256 !== data.source.sha256) throw Error('Integridade do arquivo original divergente.');
  let reconstruction=null;
  if(data.version===2&&data.reconstruction){
    const m=data.reconstruction;
    if(m.schema!==MODEL_SCHEMA||m.module!==module||m.source?.sha256!==source.sha256||m.source.page!==data.page||!Array.isArray(m.issues))throw Error('Modelo de rascunho incompatível com o arquivo original.');
    validateModel(m);m.review={validated:false};m.status='partial';
    m.issues.push({id:'archive-review',category:'missing',critical:true,message:'Modelo restaurado de arquivo. As origens declaradas ainda precisam de conferência com as bases locais.'});
    for(const p of m.points)if(p.position)p.coordinateState='archive-review';reconstruction=m;
  }
  // The original is always re-read. Restored geometry is explicitly unverified, never trusted as approval.
  return {file: original, source, page: data.page,reconstruction};
}
