import {SCHEMA} from './model.mjs';
const DB = 'ivplanner-chart-import-v1', STORE = 'sessions';
function open() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE, {keyPath: 'id'});
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(Error('Feche outras abas para abrir o armazenamento de cartas.'));
  });
}
function checked(record, module) {
  if (!record || record.schema !== SCHEMA || record.module !== module || !['ndb', 'procedimentos'].includes(module) || typeof record.id !== 'string' || !(record.file instanceof Blob)) throw Error('Rascunho de carta incompatível. Os dados foram preservados.');
  if (!Number.isInteger(record.page) || record.page < 1 || record.review?.validated !== false || record.status !== 'draft') throw Error('Estado de importação não reconhecido.');
  return record;
}
async function run(mode, operation) {
  const db = await open();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      const request = operation(tx.objectStore(STORE));
      tx.oncomplete = () => resolve(request.result);
      tx.onabort = tx.onerror = () => reject(tx.error || Error('Não foi possível guardar a carta.'));
    });
  } finally {db.close();}
}
export async function save(record, file) {
  const next = checked({...record, file, updatedAt: new Date().toISOString()}, record.module);
  try {await run('readwrite', store => store.put(next));}
  catch (error) {throw Error('Rascunho não salvo. O armazenamento pode estar cheio ou indisponível. Exporte este rascunho antes de fechar. ' + (error.name || ''));}
  return next;
}
export async function list(module) {
  // Do not read large document blobs merely to render the library.
  const db = await open();
  try {return await new Promise((resolve, reject) => {
    const rows = [], tx = db.transaction(STORE, 'readonly'), request = tx.objectStore(STORE).openCursor();
    request.onsuccess = () => {const cursor = request.result;if (!cursor) return;const r = cursor.value;if (r.module === module) rows.push({id: r.id, name: r.source?.name || 'Carta', updatedAt: r.updatedAt});cursor.continue();};
    tx.oncomplete = () => resolve(rows.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)));
    tx.onabort = tx.onerror = () => reject(tx.error);
  });} finally {db.close();}
}
export async function load(id, module) {return checked(await run('readonly', store => store.get(id)), module);}
