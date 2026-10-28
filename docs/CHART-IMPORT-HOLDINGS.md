# Importador — esperas e hipódromos reconhecidos por evidência vetorial

Esta entrega reconhece um subconjunto de hipódromos em cartas digitais DECEA, associa o fixo e os cursos publicados e permite gerar seus componentes no editor nativo após resolver os parâmetros que faltam. Não presume tempo padrão, velocidade, raio de curva nem distância a partir da imagem.

Branch: `feat/chart-holdings`. Base: árvore `30d54b20e8645b8a10a2207216f0df42692b6f31`, correspondente à main `6e29fd2b3c0a33bed414c3e21d4cd66a4fb85d76`, após a PR32. Trabalho local, sem publicação, merge ou implantação automática.

## Reconhecimento e dados intermediários

A rotina combina duas extremidades circulares compatíveis, trechos paralelos visíveis, símbolo triangular de fixo e identificação textual. Fragmentos de triângulos podem ser reconstituídos quando o PDF codifica cada lado como caminho separado. Formas preenchidas, fechadas ou tracejadas não são utilizadas como arcos circulares de espera. Cursos recíprocos são associados às duas retas; o símbolo do fixo identifica a reta de aproximação e o sentido das curvas.

As tolerâncias de associação são relativas ao tamanho dos textos e figuras na página. Permitem interrupções de traçado por números, símbolos e setas; não representam tolerâncias operacionais. **Nenhuma posição ou dimensão da página é convertida em latitude, longitude ou NM.**

O reconhecimento distingue:

- **Espera:** função MAHF publicada ou texto explícito que associa o fixo à espera, como “holding at [fixo]” ou “[fixo] para espera”. Não há lista de nomes de pontos, aeródromos ou auxílios.
- **Hipódromo com função não determinada:** a forma foi reconhecida, mas ainda é necessário confirmar se corresponde a espera ou reversão. Um IAF, isoladamente, não resolve essa classificação.

O campo opcional `model.holdings` conserva:

- Fixo de referência, curso de aproximação, sentido e natureza da referência magnética/verdadeira.
- Valores e evidências dos cursos e da definição publicada de extensão, quando reconhecida.
- Restrições verticais associadas ao fixo por seus identificadores originais.
- Evidências dos textos e vetores; método de associação.
- Dimensões do desenho, origem da decisão e estado de revisão, separados da publicação.

A extensão publicada pode ser reconhecida em rótulos explícitos com `MIN`, `SEC`, `S` ou `NM` próximos das retas do hipódromo. DME, radiais e pixels não são tratados como comprimento da perna. Definições conflitantes permanecem preservadas e pendentes, mesmo após dimensionar o desenho.

## Perguntas somente para os dados não determinados

O painel de pendências apresenta o recorte da carta e o fixo correspondente. Curso e sentido identificados são apresentados sem exigir redigitação. Quando a função da figura é incerta, o usuário confirma espera ou reversão em hipódromo.

As dimensões do desenho exigem:

- **Extensão em NM**, quando publicada ou fornecida explicitamente para o desenho; ou
- **Tempo e GS explícita para o desenho**, usando distância = GS × tempo / 3600, em NM.
- **Raio das curvas em NM**, fornecido explicitamente nesta entrega.

Não se assume espera de um minuto, GS a partir da categoria da aeronave, velocidade indicada como velocidade no solo, inclinação ou razão de curva. A forma não utiliza compensação de vento. Quando a carta não traz extensão reconhecida, os valores informados permanecem classificados como dimensões do desenho, sem serem promovidos a dados publicados.

A operação gera duas retas e duas curvas semicirculares, ancoradas no fixo georreferenciado, com precisão interna preservada. A edição continua usando os incrementos e ferramentas existentes do editor. Não é criado um editor paralelo nem um novo tipo de perna operacional.

## Sequenciamento e perfil vertical

O hipódromo é representado como figura fechada, **separada da sequência de voo principal**. Não se presume entrada, saída, quantidade de circuitos ou uma repetição operacional da figura. Uma pendência específica mantém essa limitação visível e impede aprovação indevida do conjunto.

Altitudes publicadas no fixo permanecem vinculadas a ele e registradas na proveniência; não são propagadas silenciosamente a todas as partes da espera. O perfil vertical principal não recebe voltas ou altitudes interpoladas automaticamente.

O tempo usado para dimensionar a figura não é escrito em `restrictions.timeSeconds`, nem substitui velocidades da missão. Isso preserva a distinção em relação às regras existentes de dimensionamento e inspeção NDB. Ferramentas que exigem cadeias simples continuam com as mesmas restrições para circuitos fechados e ramificações, como em um desenho manual equivalente. Não foram alteradas fórmulas ou critérios de clearance.

## Origem, revisão e persistência

A resposta fica no histórico existente, vinculada à carta, página e módulo. Desfazer/refazer recompõe o desenho. Uma alteração da coordenada, fonte ou referência que sustentava a resposta invalida a aceitação anterior e exige nova conferência.

A aplicação preserva a definição intermediária em `chartImport.provenance.holdings`, e o mapeamento de componentes em `mapping.holdings`. Pontos derivados conservam referência à espera e às dimensões explícitas que os originaram. A origem é consultável tanto no painel geral quanto nas propriedades de cada componente nativo. A sinalização existente de alterações geométricas continua ativa após a edição.

Rascunhos e missões existentes não são reprocessados ou substituídos automaticamente. O PDF permanece separado no IndexedDB e na exportação `.ivchart`; JSON e backup de missões conservam os metadados, mas não passam a incluir o documento original. Não há nova chave de localStorage nem migração destrutiva de schema.

Procedimentos e NDB preservam seu contexto e armazenamento independentes. O mecanismo anterior de aviso de incompatibilidade de carta/módulo permanece. Não há serviço externo, OCR simulado, chave de API ou transmissão de cartas.

O service worker principal passa a `v122-chart-holdings-20261028`, incluindo os dois módulos novos e preservando o fluxo de atualização e funcionamento offline.

## Cartas reais conferidas

| Carta | Fixo | Aproximação publicada | Sentido | Observação |
| --- | --- | --- | --- | --- |
| SBNT VOR Y RWY 12, 21 MAR 2024 | DAKOK | 358° magnéticos | Direita | Função IAF/MAHF; extensão não determinada |
| SBNT VOR W RWY 16L, 15 MAY 2025 | EGEGI | 059° magnéticos | Direita | Função IAF/MAHF; extensão não determinada |
| SBGL VOR Y RWY 15, 03 OCT 2024 | SISER | 295° magnéticos | Esquerda | Quadro NOT TO SCALE; fixo associado à base, sem usar a escala da figura |
| SBLS NDB RWY 13, 20 FEB 2025 | ESIGO | 300° magnéticos | Direita | Quadro NOT TO SCALE e função MAHF; testado no módulo NDB |

Na SBLS também foi associado o hipódromo de ULVUK, mas a função não foi decidida apenas pela presença de IAF. Ele permanece pendente de classificação. Não se declara reconstrução completa dessa carta NDB.

A comparação diagnóstica das **33 cartas / 36 páginas** conservou as **97 pernas intermediárias e os 99 segmentos nativos anteriores**. Foram associados **10 hipódromos em 9 cartas**: 7 classificados como espera por evidência publicada e 3 com função pendente. Nenhum foi dimensionado automaticamente sem parâmetros suficientes; nenhum modelo real foi marcado como validado. As contagens não medem completude ou acurácia universal. O resultado por página, com hashes, está em `tests/fixtures/charts/holding-reference-results.json`.

## Arquivos alterados

- Novos: `inspecao/chart-import/holdings.mjs` e `holding-geometry.mjs`.
- Extração vetorial complementar: `vector-paths.mjs`, preservando a rotina anterior de arcos DME.
- Integração: `reconstruct.mjs`, `native.mjs`, `review.mjs`, `review-ui.mjs`, `finalize.mjs`, `final-ui.mjs` e `ui.mjs`.
- Consulta da origem no editor: alterações localizadas em `inspecao/desenhar.html`.
- Offline: `sw.js` e expectativa de versão em `tests/test_offline_map_visual.py`.
- Testes novos: `tests/test_chart_holding_rules.py` e `tests/test_chart_holdings.py`.
- Auditoria e documentação: JSON de referência e este relatório. Nenhum PDF novo incluído.

## Validação

Os sete testes gerais exercitam 54 combinações de nomes, cursos, escalas, deslocamento e sentidos, além de ausência de símbolo/retas, informação faltante ou conflitante, referência magnética desconhecida, dados de desenho inválidos e preservação do tempo publicado. Há também um caso específico que conserva o curso publicado 360° e o utiliza como direção equivalente a 0° no desenho. Dimensões e direção dos componentes nativos são conferidas independentemente a partir de suas coordenadas.

Os cinco fluxos reais cobrem as quatro cartas acima, correções de coordenadas, desfazer/refazer, invalidação de resposta antiga, conferência responsiva, retomada offline, edição de raio no editor, preservação da proveniência, perfil vertical e independência do módulo NDB.

Resultados locais, Chromium 154.0.8037.57:

- Suíte geral: **244 testes aprovados em 1145.578 s**, sem falhas.
- Rodada final específica: **12 testes aprovados em 45.409 s**, incluindo o caso 360° acrescentado após a descoberta da suíte geral.
- Consolidado: **245 testes distintos aprovados nas execuções**. Não houve execução única de 245 testes.
- Comparação das 33 cartas/36 páginas sem exceções e sem perda das 97 pernas anteriores; nenhum modelo real validado automaticamente.
- Sintaxe JavaScript/Python, JSON da auditoria e whitespace do diff verificados.
- Inspeção visual adicional da comparação NDB e da pendência de classificação em dimensões de iPad/iPhone, sem erros JavaScript.
- Uma expectativa inicial de teste de renomeação foi corrigida para exercitar alteração de raio: o mecanismo existente sinaliza alterações geométricas, e a renomeação da perna foi persistida normalmente. Não se alterou esse mecanismo para satisfazer o teste.
- CI remoto não iniciado: a branch ainda não foi publicada. Validação física em Safari/iPhone/iPad pendente.

## Limitações e próximo avanço

- O reconhecimento exige a família geométrica suportada e um símbolo triangular associável. Codificações vetoriais diferentes, outros símbolos, trechos muito incompletos e PDFs rasterizados continuam pendentes.
- Raio de curva, vento e desempenho não são deduzidos da carta. A forma dimensionada é uma representação local explícita para planejamento e edição, não uma previsão certificada da trajetória real.
- Entrada, saída e repetição das esperas ainda precisam de uma representação operacional própria. Não foram inferidas conexões de aproximação perdida pelo simples reconhecimento do hipódromo.
- A leitura integral de limites de velocidade e altitude da espera ainda não está implementada; conservam-se os dados já associados ao fixo pela extração existente.
- A classificação manual de reversão cobre apenas a forma em hipódromo reconhecida. Reversões de outros tipos, inclusive 45°/180° ou 80°/260°, ainda não são reconstruídas.
- OCR e interpretação avançada permanecem fora desta entrega e exigirão aprovação específica se houver serviço externo.
- As cartas históricas e a edição local da base não atestam vigência ou correspondência temporal completa.
- Falta validação física no Safari/iPhone/iPad: atualização do PWA, conferência dos recortes, dimensionamento, seleção por toque, edição, desfazer e reabertura offline. Os testes automatizados usam Chromium e dimensões equivalentes de tela.

Publicação em PR depende da autorização do responsável. Sem merge ou implantação automática.
