/* Perfil esquemático: lê a sequência e edita as mesmas restrições do desenho. */
(() => {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const number = value => String(value ?? '').trim() === '' ? null : Number(String(value).replace(',', '.'));
  const types = {at: 'Exata', above: 'Mínima', below: 'Máxima', between: 'Janela'};
  const labels = r => r.altitude === '' ? 'Não informada' :
    (r.qualifier === 'above' ? '≥ ' : r.qualifier === 'below' ? '≤ ' : '') + r.altitude +
    (r.qualifier === 'between' ? ' – ' + (r.upperAltitude || '?') : '') + ' ft';
  const node = (tag, parent, text, attrs = {}) => {
    const n = document.createElement(tag);
    if (text !== undefined) n.textContent = text;
    Object.entries(attrs).forEach(([key, value]) => n.setAttribute(key, value));
    if (parent) parent.append(n);
    return n;
  };
  const svgNode = (tag, parent, attrs = {}, text) => {
    const n = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([key, value]) => n.setAttribute(key, value));
    if (text !== undefined) n.textContent = text;
    parent.append(n);
    return n;
  };

  window.IVVerticalProfile = {create(host, config) {
    const intro = node('div', host, undefined, {class: 'panel'});
    node('h2', intro, 'Perfil vertical');
    const status = node('p', intro, '', {id: 'profile-status', class: 'help'});
    node('p', intro, 'Representação esquemática inspirada no perfil IAC; não é uma carta. Altitudes em ft MSL. Horizontal sem escala: as distâncias locais são anotadas em NM, incluindo o comprimento dos arcos.', {class: 'note muted'});
    node('p', intro, 'Trajetória planejada exclusivamente manual. Não há interpolação de altitudes ausentes, verificação de limites, cálculo de descida ou aplicação de regras operacionais.', {class: 'note muted'});
    const sequence = node('button', intro, 'Definir sequência de voo', {type: 'button', id: 'profile-sequence'});
    sequence.onclick = config.sequence;
    const legend = node('div', host, undefined, {class: 'legend'});
    node('span', legend, '● Publicada', {class: 'profile-published'});
    node('span', legend, '///// Área fora da restrição informada', {class: 'profile-limit'});
    node('span', legend, '┄ Planejada manual', {class: 'profile-planned'});
    const viewport = node('div', host, undefined, {class: 'profile-scroll', tabindex: '0', role: 'region', 'aria-label': 'Gráfico vertical; deslize horizontalmente para percorrer a sequência'});
    const chart = svgNode('svg', viewport, {id: 'vertical-profile', role: 'img', 'aria-label': 'Altitudes por sequência de voo'});
    const editor = node('form', host, undefined, {class: 'panel profile-editor', id: 'profile-editor'});
    node('h3', editor, 'Editar dados do perfil');
    const field = (text, id, kind = 'input') => {
      const label = node('label', editor, text);
      const input = node(kind, label, undefined, {id});
      if (kind === 'input') Object.entries({type: 'number', step: 'any', inputmode: 'decimal'}).forEach(([k, v]) => input.setAttribute(k, v));
      return {input, label};
    };
    const element = field('Ponto ou perna', 'profile-element', 'select').input;
    const qualifier = field('Restrição de altitude', 'profile-qualifier', 'select').input;
    Object.entries(types).forEach(([value, label]) => qualifier.add(new Option(label, value)));
    const lower = field('Altitude publicada / limite (ft MSL)', 'profile-altitude').input;
    const upper = field('Altitude superior da janela (ft MSL)', 'profile-upper');
    const planned = field('Altitude planejada manual no ponto (ft MSL)', 'profile-planned');
    const review = node('p', editor, '', {class: 'note pending', id: 'profile-review'});
    node('button', editor, 'Aplicar altitudes e restrição', {type: 'submit', id: 'profile-apply'});
    const history = node('div', host, undefined, {class: 'actions'});
    const undo = node('button', history, 'Desfazer', {type: 'button', id: 'profile-undo'});
    const redo = node('button', history, 'Refazer', {type: 'button', id: 'profile-redo'});
    undo.onclick = () => config.history(false);
    redo.onclick = () => config.history(true);
    const tableDetails = node('details', host, undefined, {class: 'details'});
    node('summary', tableDetails, 'Dados do perfil em sequência');
    const tableArea = node('div', tableDetails, undefined, {class: 'profile-scroll'});
    const table = node('table', tableArea, undefined, {class: 'profile-table'});
    let current = '', data, applied = '';
    const formState = () => JSON.stringify([qualifier.value, lower.value, upper.input.value, planned.input.value]);
    const canLeave = () => editor.hidden || formState() === applied || confirm('Há alterações de altitude ainda não aplicadas. Descartar essas edições? Os dados já aplicados serão mantidos.');

    function edit(key, scroll = false) {
      current = key; element.value = key;
      const id = key.slice(2), r = config.restriction(id);
      qualifier.value = r.qualifier; lower.value = r.altitude === '' ? '' : number(r.altitude);
      upper.input.value = r.upperAltitude === '' ? '' : number(r.upperAltitude);
      upper.label.hidden = r.qualifier !== 'between';
      planned.label.hidden = !key.startsWith('p:');
      planned.input.value = r.plannedAltitude === '' || r.plannedAltitude === undefined ? '' : number(r.plannedAltitude);
      applied = formState();
      review.textContent = r.reviewRequired ? 'Revisão pendente: dados da perna original preservados. Confirme a revisão na aba Restrições.' : '';
      if (scroll) editor.scrollIntoView({block: 'center', behavior: 'smooth'});
    }
    const select = (key, scroll = false) => {if (canLeave()) edit(key, scroll); else element.value = current;};
    element.onchange = () => select(element.value);
    qualifier.onchange = () => { upper.label.hidden = qualifier.value !== 'between'; };
    editor.onsubmit = event => {
      event.preventDefault(); if (!current) return;
      config.save(current.slice(2), {...config.restriction(current.slice(2)),
        qualifier: qualifier.value, altitude: lower.value.trim(), upperAltitude: upper.input.value.trim(),
        plannedAltitude: current.startsWith('p:') ? planned.input.value.trim() : ''});
    };

    function render() {
      data = config.data();
      const points = new Map(data.points.map(p => [p.id, p]));
      const segments = new Map(data.segments.map(e => [e.id, e]));
      const legs = data.flight.segments.map(id => segments.get(id));
      const ordered = data.flight.start ? [points.get(data.flight.start), ...legs.map(e => points.get(e.to))] : [];
      const complete = ordered.length > 1 && data.flight.end && ordered[ordered.length - 1].id === data.flight.end;
      status.textContent = !ordered.length ? 'Defina o início e a sequência de voo para representar o perfil. Nenhuma ramificação é escolhida automaticamente.' : !legs.length ? 'Início definido; adicione as pernas na sequência de voo.' : complete ? 'Sequência de voo conectada do início ao fim.' : 'Sequência parcial: somente as pernas explicitamente escolhidas são exibidas. Confira o fim do procedimento.';
      undo.disabled = !config.canUndo(); redo.disabled = !config.canRedo();
      const options = new Map();
      ordered.forEach(p => options.set('p:' + p.id, p.name));
      legs.forEach(e => options.set('s:' + e.id, points.get(e.from).name + ' → ' + points.get(e.to).name));
      element.replaceChildren();
      options.forEach((label, key) => element.add(new Option((key.startsWith('p:') ? 'Ponto · ' : 'Perna · ') + label, key)));
      editor.hidden = !options.size;
      if (options.size) edit(options.has(current) ? current : options.keys().next().value);
      else current = '';
      chart.replaceChildren(); table.replaceChildren();
      chart.setAttribute('width', Math.max(650, 180 + Math.max(0, ordered.length - 1) * 170));
      chart.setAttribute('height', 510);
      const defs = svgNode('defs', chart);
      const hatch = svgNode('pattern', defs, {id: 'profile-hatch', patternUnits: 'userSpaceOnUse', width: 8, height: 8});
      svgNode('path', hatch, {d: 'M-2 2L2 -2 M0 8L8 0 M6 10L10 6', stroke: '#ffb64d', 'stroke-width': 1, opacity: .6});
      const values = [];
      [...ordered, ...legs].forEach(item => {
        const r = config.restriction(item.id);
        [r.altitude, ...(r.qualifier === 'between' ? [r.upperAltitude] : []), ...(points.has(item.id) ? [r.plannedAltitude] : [])].forEach(v => {
          const n = number(v); if (n !== null && Number.isFinite(n)) values.push(n);
        });
      });
      const low = values.length ? Math.min(...values) : 0, high = values.length ? Math.max(...values) : 1;
      const margin = Math.max(100, (high - low) * .15), min = low - margin, max = high + margin;
      const top = 50, bottom = 355, y = value => bottom - (value - min) / (max - min) * (bottom - top);
      const x = index => 110 + index * 170, width = Number(chart.getAttribute('width'));
      svgNode('text', chart, {x: 12, y: 22, fill: '#aeb5bc', 'font-size': 12}, 'ft MSL');
      if (values.length) for (let i = 0; i <= 4; i++) {
        const value = min + (max - min) * i / 4, row = y(value);
        svgNode('line', chart, {x1: 65, x2: width - 20, y1: row, y2: row, stroke: '#ffffff18'});
        svgNode('text', chart, {x: 58, y: row + 4, 'text-anchor': 'end', fill: '#aeb5bc', 'font-size': 11}, config.format(value, 0));
      } else svgNode('text', chart, {x: 85, y: 190, fill: '#aeb5bc', 'font-size': 13}, ordered.length ? 'Informe as altitudes publicadas e/ou planejadas.' : 'Sequência de voo não definida.');

      function constraint(item, key, center, boxWidth) {
        const r = config.restriction(item.id), a = number(r.altitude), b = number(r.upperAltitude);
        if (a === null || !Number.isFinite(a)) return;
        const group = svgNode('g', chart, {'data-profile-constraint': key, 'data-type': r.qualifier});
        svgNode('title', group, {}, types[r.qualifier] + ' · ' + labels(r) + (r.reviewRequired ? ' · Revisão pendente' : ''));
        const left = center - boxWidth / 2;
        const shade = (from, to) => { if (to > from) svgNode('rect', group, {x: left, y: from, width: boxWidth, height: to - from, fill: 'url(#profile-hatch)'}); };
        const boundary = altitude => svgNode('line', group, {x1: left, x2: left + boxWidth, y1: y(altitude), y2: y(altitude), stroke: '#ffb64d', 'stroke-width': 2});
        if (r.qualifier === 'above') shade(y(a), bottom);
        else if (r.qualifier === 'below') shade(top, y(a));
        else if (r.qualifier === 'between') {
          if (b !== null && Number.isFinite(b)) { shade(top, y(b)); shade(y(a), bottom); boundary(b); }
        } else { shade(top, y(a) - 3); shade(y(a) + 3, bottom); }
        svgNode('rect', group, {x: left, y: top, width: boxWidth, height: bottom - top, fill: 'none', stroke: '#ffb64d88', 'stroke-dasharray': r.reviewRequired ? '4 4' : 'none'});
        boundary(a);
        svgNode('text', group, {x: center, y: key.startsWith('s:') ? 25 : 40, fill: '#ffb64d', 'font-size': 10, 'text-anchor': 'middle'}, r.reviewRequired ? 'REVISAR' : r.qualifier === 'between' && b === null ? 'Janela incompleta' : types[r.qualifier]);
        if (key.startsWith('s:')) svgNode('text', group, {x: center, y: 40, fill: '#ffb64d', 'font-size': 10, 'text-anchor': 'middle'}, labels(r).replace(' ft', ''));
      }
      ordered.forEach((p, i) => constraint(p, 'p:' + p.id, x(i), 96));
      legs.forEach((e, i) => constraint(e, 's:' + e.id, (x(i) + x(i + 1)) / 2, 52));
      const head = node('thead', table), header = node('tr', head);
      ['Ordem / ponto', 'Distância acumulada (NM)', 'Publicada / restrição', 'Planejada manual (ft MSL)', 'Perna seguinte (NM)', 'Restrição da perna seguinte'].forEach(t => node('th', header, t, {scope: 'col'}));
      const body = node('tbody', table); let cumulative = 0;
      ordered.forEach((p, i) => {
        const r = config.restriction(p.id), altitude = number(r.altitude), plan = number(r.plannedAltitude);
        const group = svgNode('g', chart, {tabindex: 0, role: 'button', 'aria-label': 'Editar ponto ' + p.name, 'data-profile-point': p.id, 'data-order': i + 1});
        group.addEventListener('click', () => select('p:' + p.id, true));
        group.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') {e.preventDefault(); select('p:' + p.id, true);} });
        svgNode('rect', group, {x: x(i) - 45, y: top, width: 90, height: bottom - top + 48, fill: 'transparent'});
        svgNode('line', group, {x1: x(i), x2: x(i), y1: top, y2: bottom, stroke: '#ffffff28', 'stroke-dasharray': '3 5'});
        if (altitude !== null) {
          svgNode('circle', group, {cx: x(i), cy: y(altitude), r: 5, fill: '#111619', stroke: '#f5f7f9', 'stroke-width': 2, 'data-published-altitude': r.altitude});
          svgNode('text', group, {x: x(i) + 9, y: y(altitude) - 9, fill: '#f5f7f9', 'font-size': 11}, r.qualifier === 'between' ? r.altitude + '–' + (r.upperAltitude || '?') : r.altitude);
        }
        if (plan !== null) {
          svgNode('rect', group, {x: x(i) - 4, y: y(plan) - 4, width: 8, height: 8, fill: '#48d9ff', 'data-planned-altitude': r.plannedAltitude});
          svgNode('text', group, {x: x(i) + 9, y: y(plan) + 16, fill: '#48d9ff', 'font-size': 11}, 'P ' + r.plannedAltitude);
          const previous = i ? number(config.restriction(ordered[i - 1].id).plannedAltitude) : null;
          if (previous !== null) svgNode('line', chart, {x1: x(i - 1), x2: x(i), y1: y(previous), y2: y(plan), stroke: '#48d9ff', 'stroke-width': 2.5, 'stroke-dasharray': '8 5', 'pointer-events': 'none', 'data-planned-leg': legs[i - 1].id});
        }
        const name = (i + 1) + '. ' + p.name;
        const nameText = svgNode('text', group, {x: x(i), y: bottom + 25, fill: '#f5f7f9', 'font-size': 11, 'text-anchor': 'middle'});
        for (let offset = 0; offset < name.length; offset += 18) svgNode('tspan', nameText, {x: x(i), dy: offset ? 14 : 0}, name.slice(offset, offset + 18));
        svgNode('text', group, {x: x(i), y: bottom + 70, fill: '#aeb5bc', 'font-size': 10, 'text-anchor': 'middle', 'data-cumulative-distance': cumulative}, config.format(cumulative, 3) + ' NM acum.');
        const row = node('tr', body);
        [name, config.format(cumulative, 3), labels(r), r.plannedAltitude || '—', legs[i] ? config.format(config.length(legs[i]), 3) : '—', legs[i] ? labels(config.restriction(legs[i].id)) : '—'].forEach(value => node('td', row, value));
        if (legs[i]) {
          const length = config.length(legs[i]); cumulative += length;
          const legGroup = svgNode('g', chart, {tabindex: 0, role: 'button', 'aria-label': 'Editar perna ' + (i + 1), 'data-profile-leg': legs[i].id, 'data-distance': length});
          legGroup.addEventListener('click', () => select('s:' + legs[i].id, true));
          legGroup.addEventListener('keydown', e => {if (e.key === 'Enter' || e.key === ' ') {e.preventDefault(); select('s:' + legs[i].id, true);} });
          svgNode('rect', legGroup, {x: x(i) + 40, y: 440, width: 90, height: 48, fill: 'transparent'});
          svgNode('text', legGroup, {x: (x(i) + x(i + 1)) / 2, y: 462, fill: '#aeb5bc', 'font-size': 11, 'text-anchor': 'middle'}, '→ ' + config.format(length, 3) + ' NM');
        }
      });
      svgNode('text', chart, {x: 85, y: 500, fill: '#aeb5bc', 'font-size': 11}, 'Sentido de voo → · Deslize para os próximos pontos');
    }
    return {render, canLeave};
  }};
})();
