# Importador — arcos DME da aproximação inicial

O importador passa a reconstruir arcos DME iniciais como curvas nativas editáveis quando a carta digital fornece evidências suficientes. O reconhecimento cruza etiquetas de distância, funções IAF/IF, identificação do auxílio, coordenadas verificáveis e conectividade de vetores curvos. Não há regras por nome de aeroporto, fixo, auxílio ou valor de raio.

Branch local: `feat/chart-dme-arcs`. Base: árvore `5f9b41dcc3c785beb404eb9f9f60e850a5a0d341`, correspondente à main `4b24841898205671be5db5e0a69a930f17ebe782`, após a PR31. Não há merge, implantação ou publicação automática.

## Reconhecimento e representação intermediária

`vector-paths.mjs` lê caminhos Bézier abertos e efetivamente traçados, com transformações e estado de tracejado do PDF. Testa circularidade e orientação no espaço da página, preservando referências aos operadores originais. Caminhos preenchidos/fechados, tracejados de aproximação perdida, curvaturas não circulares, grandes lacunas e desenhos excessivamente complexos não são usados para completar os arcos iniciais. O processamento possui limites locais explícitos. A busca de conectividade também é limitada, sem escolher o primeiro resultado quando o limite é excedido. Voltas adicionais não são encurtadas silenciosamente para o arco entre extremos.

`dme-arcs.mjs` associa etiquetas completas como `D10.4 NTL` ao ponto identificado no plano. Etiquetas repetidas são consolidadas com suas evidências; definições conflitantes permanecem pendentes. Uma definição publicada de reta concorrente também impede escolher o arco automaticamente. Sua aplicação exige conjuntamente:

1. Interpretador DECEA digital com plano delimitado, extração não truncada e evidência textual de arco DME; cartas RF permanecem fora deste caminho.
2. Etiquetas DME compatíveis nos extremos e sequência IAF → IF publicada, apoiada por conectividade de vetores curvos próximos dos rótulos.
3. Auxílio identificado na carta e coordenada própria do equipamento **DME**, sem emprestar automaticamente a posição de um VOR de mesmo identificador.
4. Coordenadas verificáveis dos extremos, coerência das distâncias geodésicas com o intervalo de arredondamento publicado e sentido único apoiado pelos vetores.
5. Associação dos fixos intermediários verificáveis às junções dos vetores, com ordenação geográfica e verificação radial. Conflitos impedem a conexão; nenhum ponto é deslocado para caber no círculo.

Pequenas interrupções gráficas podem ser associadas somente entre caminhos concêntricos, com raio gráfico compatível e lacuna curta. Os limites em unidades da página são heurísticas de reconhecimento, **não tolerâncias operacionais**. A imagem e os vetores não fornecem latitude, longitude ou distância em NM. O sentido é obtido da topologia dos vetores, orientada pela sequência de funções publicada; não é escolhido simplesmente o arco mais curto entre dois fixos.

O campo opcional `model.dmeArcs` conserva estações, associações, etiquetas brutas, valores publicados, raio horizontal calculado e evidências. Cada perna `arc` registra centro, extremos, sentido, `via`, `publishedDME`, método e estado de revisão. O sequenciamento nativo atravessa os fixos intermediários e as subdivisões necessárias às curvas do editor.

## DME inclinado e representação horizontal

A publicação DME permanece classificada como `slant-range`. Seu valor não vira silenciosamente uma distância horizontal nem uma coordenada.

O raio horizontal utilizado na representação é a média das distâncias geodésicas do equipamento DME aos extremos, preservando integralmente as coordenadas dos fixos e o DME publicado. Esse círculo é uma representação do desenho, não uma solução certificada da trajetória de distância inclinada em todas as altitudes. A discrepância radial é verificada e a projeção local registra seu erro de centro. O limite de representação do conversor nativo existente, 0,05 NM, não foi alterado; curvas incompatíveis continuam bloqueadas, sem reta substituta.

Cada arco reconstruído apresenta pendência contextual para conferir essa representação, incluindo centro, extremos, fixos intermediários e raio publicado/calculado. A aceitação:

- Conserva a evidência de origem, o erro de projeção e a decisão no histórico.
- Não elimina pendências de cobertura, espera ou aproximação perdida.
- Não certifica a publicação, sua vigência ou o seguimento operacional do DME.
- É invalidada quando mudam coordenadas, fontes, referência ou geometria usadas na decisão.

A interface permite corrigir as coordenadas envolvidas, com origem explícita, além de desfazer/refazer as respostas. O desenho continua no editor existente, com edição de raio, sentido, pontos e demais ferramentas nativas. Alterações posteriores conservam o modelo de origem e indicam modificação.

## Exemplos reais conferidos

Foram reutilizados dois PDFs já presentes nos testes e inspecionadas suas representações gráficas.

| Carta | Reconstrução inicial | DME publicado | Representação nativa |
| --- | --- | --- | --- |
| SBNT VOR Y RWY 12 — 21 MAR 2024 | EDROS → ETINA, esquerda; DAKOK → ETINA, direita | D10.4 NTL | 3 curvas, além da reta ETINA → ISIRI já existente |
| SBNT VOR W RWY 16L — 15 MAY 2025 | EGEGI → IRUNU → SALBA, direita | D8.0 NTL | 2 curvas conectadas a IRUNU, além da reta SALBA → EVNOP já existente |

Na base local, NTL VOR (`-5.908333333, -35.248666667`) e NTL DME (`-5.908355556, -35.248586111`) são registros distintos. A mudança utiliza o segundo como centro e conserva ambos; não atualiza ou sobrescreve a base.

A aproximação perdida publicada nas duas cartas envolve interceptação condicional do arco e espera. Esses trechos continuam pendentes. Não são equiparados aos arcos iniciais reconhecidos, nem completados por linhas ou por extensões presumidas dos vetores.

## Persistência, módulos e offline

A informação permanece no modelo intermediário, no histórico existente, na proveniência do documento nativo e nas exportações existentes. Não há nova chave de localStorage nem alteração destrutiva de schema. O PDF continua separado no IndexedDB e na exportação `.ivchart`; o backup geral de missões não passa a incorporar documentos PDF.

Procedimentos e NDB usam a mesma rotina técnica, mas o contexto de destino, as missões e a compatibilidade de inspeção permanecem independentes. Uma carta VOR aberta em NDB continua gerando o aviso de incompatibilidade existente, sem troca automática do módulo.

O service worker principal passa a `v121-chart-dme-arcs-20261022` e inclui os dois módulos locais. Não há nova dependência remota, OCR, chave privada, serviço externo, transmissão de cartas ou alteração de clearance.

Modelos anteriores não são reprocessados silenciosamente. Rascunhos sem decisões podem usar Atualizar prévia; rascunhos com histórico preservam suas respostas e limitações anteriores. Missões e desenhos existentes não são substituídos até a aplicação explícita pelo usuário.

## Arquivos alterados

- Novos módulos: `inspecao/chart-import/vector-paths.mjs` e `dme-arcs.mjs`.
- Integração: `reconstruct.mjs`, `native.mjs`, `review.mjs`, `review-ui.mjs` e `finalize.mjs`, no mesmo diretório.
- Offline: `sw.js` e a expectativa de atualização em `tests/test_offline_map_visual.py`.
- Novos testes: `tests/test_chart_dme_rules.py` e `tests/test_chart_dme_arcs.py`.
- Regressão geométrica: `tests/test_chart_geometry.py`, distinguindo as retas anteriores das novas curvas; as expectativas das retas publicadas continuam verificadas.
- Auditoria: `tests/fixtures/charts/dme-reference-results.json` e este relatório. Nenhum PDF novo incluído.

## Verificações

Os sete testes gerais exercitam 54 combinações de identificadores de auxílio, raios, escalas, deslocamento e sentidos, além de informações ausentes, coordenadas conflitantes, ausência de função/vetor, RF, tracejado, caminhos preenchidos, lacunas, fixos intermediários fora de ordem/raio, etiquetas repetidas/conflitantes, voltas adicionais e limites de processamento. As variações não alteram coordenadas a partir de pixels.

Os cinco fluxos de cartas reais verificam as três associações acima, coordenadas próprias do DME, edição nativa do raio, desfazer, histórico e invalidação da aceitação, respostas e rascunhos retomados offline, aplicação à missão e preservação da origem. A conferência contextual foi exercitada em dimensões de iPhone, paisagem e iPad, sem excesso de largura.

Comparação diagnóstica das **33 cartas / 36 páginas** com a versão anterior: **94 pernas anteriores preservadas, 97 pernas intermediárias e 99 segmentos nativos resultantes**. Apenas as duas cartas acima receberam arcos novos. Não houve exceções nem modelo real marcado como validado. Os resultados por página e hashes estão no JSON de auditoria. Contagens não medem reconhecimento completo nem precisão oficial.

Resultados locais, Chromium 154.0.8037.57:

- Suíte geral: **232 testes aprovados em 1246.508 s**, sem falhas na execução final.
- Depois dos reforços finais de reconhecimento, repetição focalizada da versão final: **12 testes de arcos aprovados em 36.913 s**, abrangendo as sete regras gerais e os cinco fluxos reais. Inclui um teste novo acrescentado após a descoberta da suíte geral.
- Consolidado: **233 testes distintos aprovados nas execuções**; não houve execução única de 233 casos. Uma repetição intermediária de geometria e revisão também passou em 45 testes.
- A primeira tentativa geral foi interrompida para atualizar uma expectativa antiga que proibia qualquer arco na carta VOR W. A expectativa atual mantém a proibição de retas substitutas e verifica as curvas reconhecidas; a suíte geral foi reiniciada e passou.
- Comparação final das 33 cartas/36 páginas, sintaxe JavaScript/Python, JSON, preservação dos hashes de origem e whitespace do diff verificados.
- Inspeção visual automatizada adicional em dimensões de iPhone/iPad, sem erros de página. A validação física no Safari/iOS continua pendente.
- Nenhum CI remoto foi iniciado nesta entrega local.

## Limitações e validação manual

- Esta entrega cobre um subconjunto verificável de **arcos DME iniciais em PDFs digitais DECEA**. Não representa reconhecimento integral de arcos DME, IAC ou SID.
- Arcos sem extremos identificados, sem funções IAF/IF, sem textos DME completos, sem coordenadas do equipamento, sem vetores utilizáveis ou com ambiguidade permanecem pendentes. Rótulos muito deslocados, fragmentados ou rotacionados podem não ser associados.
- RF, esperas, reversões e interceptações condicionais da aproximação perdida continuam fora desta reconstrução. Nenhum desses casos é substituído por reta.
- A representação horizontal não executa compensação tridimensional de DME ao longo de um perfil variável de altitude. Divergências que não caibam no intervalo verificado ficam pendentes; não se deslocam fixos.
- Os testes usam cartas históricas e uma edição local da base, sem atestar vigência nem correspondência temporal completa.
- Falta validação física em Safari/iPhone/iPad: atualização do PWA, leitura das cartas, conferência do arco, seleção por toque, alteração de raio/sentido, desfazer e reabertura offline. Os testes automatizados usam Chromium e dimensões equivalentes de tela.

Publicação em PR depende de autorização do responsável. Sem merge nem implantação automática.
