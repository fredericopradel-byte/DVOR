import {recognize, newSession} from './model.mjs';
import {identify, openDocument, exportArchive, restoreArchive} from './extract.mjs';
import * as storage from './storage.mjs';

const trigger = document.getElementById('import-chart');
const module = new URLSearchParams(location.search).get('modulo') === 'ndb' ? 'ndb' : 'procedimentos';
const labels = {kind: 'Carta', icao: 'ICAO', airport: 'Aeródromo', procedure: 'Procedimento', runway: 'Cabeceira', revision: 'Emenda / revisão', publishedDate: 'Data publicada'};
function node(tag, parent, text, attrs = {}) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, value);
  parent.append(element);return element;
}
const dialog = node('dialog', document.body, undefined, {id: 'chart-import-dialog', 'aria-labelledby': 'chart-import-title'});
const header = node('header', dialog, undefined, {class: 'ci-header'});
node('h2', header, 'Importar carta · ' + (module === 'ndb' ? 'NDB' : 'Procedimentos'), {id: 'chart-import-title'});
const close = node('button', header, 'Fechar', {type: 'button', 'aria-label': 'Fechar importação'});
const scroll = node('div', dialog, undefined, {class: 'ci-scroll'});
node('p', scroll, 'Processamento local · missão preservada.', {class: 'ci-muted'});
const help = node('details', scroll);node('summary', help, 'Armazenamento e privacidade');
node('p', help, 'Nenhum arquivo será enviado para serviços externos. Rascunhos de cartas têm exportação própria; ainda não entram no backup geral.', {class: 'ci-muted'});
const actions = node('div', scroll, undefined, {class: 'ci-actions'});
const pick = node('button', actions, 'Selecionar PDF ou imagem', {type: 'button'});
const fileInput = node('input', actions, undefined, {id: 'chart-file', type: 'file', accept: '.pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg', hidden: ''});
const restore = node('button', actions, 'Restaurar rascunho', {type: 'button'});
const toggleLibrary = node('button', actions, 'Rascunhos', {type: 'button', 'aria-expanded': 'true', 'aria-controls': 'chart-library-row'});
const archiveInput = node('input', actions, undefined, {id: 'chart-archive', type: 'file', accept: '.ivchart,application/json', hidden: ''});
const libraryLabel = node('label', scroll, 'Rascunhos deste módulo', {id: 'chart-library-row', class: 'ci-library'});
const library = node('select', libraryLabel, undefined, {id: 'chart-library'});
const reopen = node('button', libraryLabel, 'Retomar', {type: 'button'});
const status = node('p', scroll, 'Selecione uma carta em PDF, PNG ou JPEG (até 25 MB).', {id: 'chart-status', role: 'status', 'aria-live': 'polite'});
const pageRow = node('div', scroll, undefined, {class: 'ci-actions', hidden: ''});
const pageLabel = node('label', pageRow, 'Página da carta ');
const pages = node('select', pageLabel, undefined, {id: 'chart-page'});
const process = node('button', pageRow, 'Extrair página', {type: 'button'});
const result = node('section', scroll, undefined, {id: 'chart-result', hidden: ''});
const tabs = node('div', result, undefined, {class: 'ci-mobile-tabs', role: 'group', 'aria-label': 'Conferir carta importada'});
const dataTab = node('button', tabs, 'Dados identificados', {type: 'button', 'aria-pressed': 'true'});
const originalTab = node('button', tabs, 'Carta original', {type: 'button', 'aria-pressed': 'false'});
function mobileView(view) {result.dataset.mobileView = view;dataTab.setAttribute('aria-pressed', String(view === 'data'));originalTab.setAttribute('aria-pressed', String(view === 'original'));}
dataTab.onclick = () => mobileView('data');originalTab.onclick = () => mobileView('original');mobileView('data');
const summary = node('div', result, undefined, {class: 'ci-summary'});
const preview = node('div', result, undefined, {class: 'ci-preview'});
const canvas = node('canvas', preview, undefined, {id: 'chart-original', role: 'img', 'aria-label': 'Página original da carta. Não é um desenho georreferenciado.'});
const footer = node('footer', dialog, undefined, {class: 'ci-actions'});
const save = node('button', footer, 'Salvar rascunho', {type: 'button', disabled: ''});
const exportButton = node('button', footer, 'Exportar rascunho', {type: 'button', disabled: ''});
let session = null, file = null, documentHandle = null, generation = 0, busy = false, persisted = true;

function message(text, error = false) {status.textContent = text;status.classList.toggle('ci-error', error);}
function setBusy(value) {
  busy = value;dialog.setAttribute('aria-busy', String(value));
  for (const button of [pick, restore, reopen, process]) button.disabled = value;
  pages.disabled = value;
  save.disabled = exportButton.disabled = value || !session;
}
async function refreshLibrary() {
  try {
    const rows = await storage.list(module);library.replaceChildren();
    library.add(new Option(rows.length ? 'Selecionar rascunho' : 'Nenhum rascunho salvo', ''));
    for (const row of rows) library.add(new Option(row.name + ' · ' + new Date(row.updatedAt).toLocaleString('pt-BR'), row.id));
  } catch {library.replaceChildren(new Option('Armazenamento indisponível', ''));}
}
function showSummary() {
  summary.replaceChildren();
  const recognition = session.recognition;
  node('p', summary, session.source.name + ' · página ' + session.page + ' de ' + documentHandle.pages, {class: 'ci-muted'});
  if (!recognition) return;
  node('p', summary, 'Rascunho não validado · ' + recognition.issues.filter(issue => issue.critical).length + ' pendência(s) crítica(s). Desenho georreferenciado ainda não disponível.', {class: 'ci-warning'});
  const dl = node('dl', summary);
  for (const [key, label] of Object.entries(labels)) {
    node('dt', dl, label);node('dd', dl, recognition.metadata[key]?.value || 'Não identificado');
  }
  node('p', summary, 'Navegação identificada no título: ' + (recognition.navigation.join(' / ') || 'Não determinada'));
  if (recognition.aids.length) node('p', summary, 'Auxílios candidatos no texto: ' + recognition.aids.map(a => a.ident + ' · ' + a.frequency + ' ' + a.unit).join('; ') + '. Associação às bases ainda pendente.');
  node('p', summary, 'Requisitos publicados identificados: ' + (recognition.requirements.map(r => r.value).join(' · ') || 'Nenhum identificado no texto'));
  if (recognition.structures.length) node('p', summary, 'Indícios textuais: ' + recognition.structures.map(s => ({'dme-arc': 'arco DME', holding: 'espera', radial: 'radiais'})[s.type]).join(', ') + '. Topologia e geometria ainda não interpretadas.');
  node('p', summary, 'Vigência não verificada. A data publicada não comprova que esta carta esteja vigente.', {class: 'ci-warning'});
  const pending = node('details', summary);node('summary', pending, 'Pendências · ' + recognition.issues.length);
  const list = node('ul', pending);
  recognition.issues.forEach(issue => node('li', list, issue.message));
  const evidence = node('details', summary);node('summary', evidence, 'Dados extraídos e origem');
  node('p', evidence, session.extraction.text.length + ' trechos de texto · ' + session.extraction.vectors.length + ' operadores gráficos preservados. Posições referem-se à página, não a latitude/longitude.');
  const pre = node('pre', evidence, session.extraction.lines.map(line => line.text).join('\n') || 'Sem camada textual. OCR/interpretação visual ainda não disponível.');
  pre.tabIndex = 0;
  node('p', evidence, 'SHA-256: ' + session.source.sha256, {class: 'ci-hash'});
  node('p', summary, 'Extração inicial. O desenho georreferenciado ainda não está disponível; a missão permanece intacta.', {class: 'ci-warning'});
}
async function persist(token) {
  try {
    const saved = await storage.save(session, file);
    if (token !== generation) return;
    session = saved;persisted = true;
    message('Rascunho salvo neste aparelho. Missão preservada.');await refreshLibrary();
  } catch (error) {if (token === generation) {persisted = false;message(error.message, true);}}
}
async function extractPage() {
  if (!documentHandle || busy) return;
  const token = generation;setBusy(true);message('Extraindo textos e estrutura da página no aparelho…');
  try {
    session.page = Number(pages.value);session.extraction = null;session.recognition = null;persisted = false;
    // Persist page selection before the expensive extraction so interrupted work can resume.
    await persist(token);
    if (token !== generation) return;
    const extraction = await documentHandle.extract(session.page, canvas);
    if (token !== generation) return;
    session.extraction = extraction;session.recognition = recognize(extraction);
    if (extraction.truncated) session.recognition.issues.unshift({id: 'extraction-limit', category: 'missing', critical: true, message: 'Página acima do limite de extração local. Parte dos dados não foi processada.'});
    persisted = false;result.hidden = false;mobileView('data');showSummary();await persist(token);
  } catch (error) {if (token === generation) {persisted = false;message(error.message || 'Falha na extração. Rascunho preservado.', true);}}
  finally {if (token === generation) setBusy(false);}
}
async function acceptFile(original, existing = null, selectedPage = 1) {
  if (busy) return;
  const token = ++generation;setBusy(true);message('Verificando arquivo local…');
  let opened;
  try {
    const source = await identify(original);
    if (existing && source.sha256 !== existing.source.sha256) throw Error('Arquivo salvo com integridade divergente. Rascunho preservado.');
    opened = await openDocument(original, source);
    if (token !== generation) {await opened.destroy();return;}
    if (selectedPage > opened.pages) throw Error('Página inexistente no arquivo.');
    if (documentHandle) await documentHandle.destroy();
    if (token !== generation) {await opened.destroy();return;}
    documentHandle = opened;opened = null;file = original;session = existing || newSession(module, source);session.page = selectedPage;persisted = false;
    pages.replaceChildren();for (let n=1;n<=documentHandle.pages;n++) pages.add(new Option('Página ' + n + ' de ' + documentHandle.pages, String(n)));
    pages.value = String(selectedPage);pageRow.hidden = documentHandle.pages === 1;result.hidden = true;
    libraryLabel.hidden = true;toggleLibrary.setAttribute('aria-expanded', 'false');
    await persist(token);
    if (documentHandle.pages > 1 && !existing) {message('Selecione a página e toque em Extrair página. Rascunho ' + (persisted ? 'salvo.' : 'ainda não salvo.'), !persisted);return;}
    setBusy(false);await extractPage();
  } catch (error) {if (opened) await opened.destroy();if (token === generation) message(error.message || 'Não foi possível abrir o arquivo.', true);}
  finally {if (token === generation) setBusy(false);}
}

trigger.addEventListener('click', () => {dialog.showModal();void refreshLibrary();});
pick.onclick = () => fileInput.click();restore.onclick = () => archiveInput.click();
toggleLibrary.onclick = () => {libraryLabel.hidden = !libraryLabel.hidden;toggleLibrary.setAttribute('aria-expanded', String(!libraryLabel.hidden));};
fileInput.onchange = async () => {const selected = fileInput.files[0];fileInput.value = '';if (selected) await acceptFile(selected);};
archiveInput.onchange = async () => {
  const selected = archiveInput.files[0];archiveInput.value = '';if (!selected || busy) return;
  const token = generation;setBusy(true);
  try {const restored = await restoreArchive(selected, module);if (token !== generation) return;setBusy(false);await acceptFile(restored.file, null, restored.page);} catch (error) {if (token === generation) message(error.message, true);}
  finally {if (token === generation) setBusy(false);}
};
reopen.onclick = async () => {
  if (!library.value || busy) return;
  const token = generation;setBusy(true);
  try {const record = await storage.load(library.value, module);if (token !== generation) return;setBusy(false);await acceptFile(record.file, record, record.page);} catch (error) {if (token === generation) message(error.message, true);}
  finally {if (token === generation) setBusy(false);}
};
process.onclick = extractPage;
pages.onchange = async () => {
  if (!session || busy) return;
  const token = generation;setBusy(true);session.page = Number(pages.value);session.extraction = session.recognition = null;persisted = false;result.hidden = true;
  try {await persist(token);if (token === generation && persisted) message('Página selecionada e salva. Toque em Extrair página para reconhecê-la.');}
  finally {if (token === generation) setBusy(false);}
};
save.onclick = async () => {const token = generation;setBusy(true);try {await persist(token);} finally {if (token === generation) setBusy(false);}};
exportButton.onclick = async () => {
  const current = session, original = file, token = generation;setBusy(true);
  try {
    const blob = await exportArchive(current, original);if (token !== generation) return;
    const url = URL.createObjectURL(blob), anchor = document.createElement('a');
    anchor.href = url;anchor.download = 'IV-PLANNER-' + module + '-' + current.id + '.ivchart';anchor.click();setTimeout(() => URL.revokeObjectURL(url), 10000);
    message('Rascunho exportado com o arquivo original. O backup geral ainda não inclui cartas importadas.');
  } catch {if (token === generation) message('Não foi possível exportar o rascunho.', true);} finally {if (token === generation) setBusy(false);}
};
function canClose() {return persisted || confirm('Este rascunho ainda não está salvo. Fechar mesmo assim? A missão permanece intacta.');}
close.onclick = () => {if (canClose()) dialog.close();};
dialog.addEventListener('cancel', event => {if (!canClose()) event.preventDefault();});
dialog.addEventListener('close', () => {
  generation++;const previous = documentHandle;documentHandle = null;
  if (previous) void previous.destroy();
  session = null;file = null;result.hidden = pageRow.hidden = true;libraryLabel.hidden = false;toggleLibrary.setAttribute('aria-expanded', 'true');canvas.width = canvas.height = 0;setBusy(false);message('Selecione uma carta ou retome um rascunho.');
  trigger.focus();
});
