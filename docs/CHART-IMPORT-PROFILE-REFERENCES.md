# Importador — referências explícitas do perfil vertical

A mudança distingue escalas da cabeceira, do MAPt e de cada auxílio DME, antes de associar pontos ou calcular geometria. Não há regras por aeroporto, identificação de fixo, altitude ou distância específica. O código foi desenvolvido sobre a árvore `e5d0fb474562a13bed42a6ac7e2e37733c7a47ce`, idêntica à main `9f67e05bb28e0d01656b8b6aab8bba9ffb0e571f` após a PR30. Branch: `feat/chart-profile-references`.

## Representação intermediária

`model.publishedProfile`, opcional e compatível com modelos anteriores, usa o schema interno `ivplanner-published-profile-v1`:

- `axes`: referência explícita (`threshold`, `mapt`, `dme`), identificação, rótulo e unidade publicados, natureza da distância, marcas numéricas com resolução, texto original e evidências da página.
- `stations`: nomes/funções publicados, associações a marcas de cada eixo e altitudes da coluna. Posições na página servem apenas para associar informações; não são coordenadas geográficas.
- `minima`: pares explícitos DA/MDA e OCH encontrados no cabeçalho, variante quando determinável e evidências. Não viram restrições de ponto, altitudes planejadas ou mínimos de inspeção.
- `gradients`: valores publicados, origem e contexto. Aproximação perdida e perfil de aproximação são classificados separadamente; aplicação e condições continuam sujeitas a conferência.
- `conditions`: trechos publicados da aproximação perdida, com origem e `unresolved-sequencing`. Não são transformados em uma sequência operacional presumida.
- `finalCourse`: curso final explicitamente publicado, com referência e evidências; ausências/contradições impedem a derivação que dele dependeria.

Números contíguos só são separados quando o PDF contém itens de texto numéricos completos verificáveis. Não se adivinha como dividir uma sequência como `1.30.3`. Valores e strings publicados são preservados; coordenadas não são arredondadas para incrementos editáveis.

## Associação e geometria nativa

Pontos identificados apenas no perfil, como GL008 na amostra ILS, podem ser associados à base aeronáutica local, respeitando o contexto de localidade, ambiguidades e edição dos dados. A altitude publicada continua distinta da altitude utilizada no editor e dos cálculos de clearance. Sem qualificador seguro, fica uma pendência; somente a confirmação pelo mecanismo de revisão existente permite converter essa restrição ao formato nativo.

Uma perna reta publicada pode ser subdividida por um ponto do perfil quando:

1. Os extremos e o ponto intermediário têm coordenadas verificáveis.
2. As marcas pertencem ao mesmo eixo de distância ao longo da trajetória, compatível com a carta.
3. Distâncias e cursos de todas as partes conferem com as coordenadas, dentro dos intervalos de arredondamento das informações publicadas.
4. Não há ambiguidade de sequência ou conflito com pernas existentes.

A perna publicada original é conservada em `profileGeometry.parents`; as novas pernas registram sua origem, eixo e evidências. A resolução da diferença de distâncias soma as resoluções dos dois valores publicados; não se finge que uma diferença possui a mesma precisão de um único valor. Dados brutos ficam preservados.

Arcos não são achatados, trechos visuais não são subdivididos por essa rotina e distâncias DME oblíquas não são usadas como distâncias horizontais. Correções de pontos refazem as verificações; uma correção incompatível mantém a perna original e apresenta pendência, sem manter uma subdivisão inválida. Desfazer restaura o resultado correspondente às coordenadas anteriores.

## Derivação conservadora da cabeceira

A derivação anterior por definição explícita do plano e perfil foi preservada (incluindo o caso SBGM já testado).

A alternativa para final de localizador requer conjuntamente:

- Carta IAC ILS/LOC, sem indicação de AR ou trecho visual na final interpretada.
- Eixo explícito de distância em NM à cabeceira correta e coluna nomeada de valor zero.
- Um único FAF/FAP identificado na escala e com coordenada disponível.
- Curso final no cabeçalho e curso consistente publicado no trecho do perfil entre esse fixo e a cabeceira.
- Referência verdadeira/magnética determinada e declinação publicada disponível quando necessária.
- Coerência com as demais referências verificáveis existentes no plano/perfil.

Sem essas evidências, o aplicativo não determina a cabeceira automaticamente. A posição calculada é marcada `chart-derived`/`derived-review`, com método, definições utilizadas, coordenada do fixo de referência, limites de arredondamento e conferências. **Não é coordenada oficial**. O limite informado continua sem incluir a incerteza da coordenada da referência. Coordenadas oficiais existentes não são deslocadas para concordar com o cálculo.

## Exemplos reais verificados

### VOR Y RWY 15 — SBGL, 03 OCT 2024

O documento traz literalmente `TO THR 15 (DME)` e `TO CXI (DME)`. O importador conserva esses textos e sinaliza que a natureza da escala da cabeceira precisa ser conferida; não interpreta silenciosamente o primeiro rótulo como distância horizontal em NM.

- SOTNU: 11.5 na escala da cabeceira / D11.8 CXI.
- UMGTI: 5.0 / D5.3 CXI.
- Rótulo RWY15/MAPt: 1.0 / D1.3 CXI.
- Zero da escala da cabeceira: corresponde a D0.3 CXI; esse deslocamento publicado não é convertido em uma regra geométrica de alcance horizontal.

O rótulo de pista em posição não nula não foi equiparado à cabeceira. MDA 500 ft MSL / OCH 490 ft fica registrada como publicação VOR/DME, separada das restrições dos fixos.

### ILS T OR LOC T RWY 10 — SBGL, 10 JUL 2025

- GAVUG: 10.7 NM à cabeceira / D13.0 ITB; altitude publicada 3500 ft.
- GL008, identificado apenas no perfil: 8.7 NM / D11.0 ITB; altitude publicada 2800 ft, com qualificador pendente até confirmação.
- GL167/FAF: 5.0 NM / D7.3 ITB; altitude publicada 1670 ft.
- Cabeceira: 0.0 NM / D2.3 ITB.

A perna GAVUG–GL167 de 5.7 NM é preservada como origem e subdividida em GAVUG–GL008 (2.0 NM) e GL008–GL167 (3.7 NM), com coordenadas oficiais mantidas. A derivação da cabeceira utiliza GL167, 5.0 NM, curso magnético 097°, VAR publicada 23°W e conferência por GAVUG. A amostra produz posição derivada aproximada `-22.8009281095157, -43.2554705780293`, não uma nova coordenada oficial cadastrada na base.

DA 216 ft / OCH 200 ft (CAT I) e MDA 450 ft / OCH 440 ft (LOC) são alternativas distintas. O texto de subida para 7000 ft e curva após 2000 ft fica preservado com sequenciamento ainda não confirmado; não se calcula uma posição de curva pela imagem.

### RNP A RWY 33 — SBGL, 13 JUN 2024

A escala `TO MAPT (NM)` conserva MAPt GL053 no zero, GL027 em 4.3 NM e LIXUG em 9.3 NM. Zero do MAPt não é convertido em zero de cabeceira. A TVD permanece fora da reconstrução integral.

## Interface, persistência e integridade

As informações aparecem em detalhes de origem do importador e na conferência final, com descrições de distância em português. Também são conservadas na origem do documento nativo, no JSON, no backup das missões e no rascunho `.ivchart`, para consulta offline. O PDF continua sendo armazenado separadamente no IndexedDB e na exportação específica de cartas.

Não se alteram automaticamente rascunhos com decisões, missões existentes ou desenhos manuais. Para reprocessar um rascunho sem respostas, usar a ação explícita Atualizar prévia. As verificações de compatibilidade entre módulos e confirmação antes da aplicação permanecem.

Não foram alteradas fórmulas, critérios de clearance, valores de altitude de inspeção/planejamento ou bases oficiais. Não há chave/API, OCR fictício, serviço externo ou dependência remota nova. O service worker principal passa a v120 e inclui os dois novos módulos locais.

## Arquivos e validação

- Novos: `profile-data.mjs` e `profile-association.mjs` (extração semântica, associação e subdivisão conservadora).
- Integração: `profile.mjs`, `reconstruct.mjs`, `review.mjs`, `finalize.mjs`, `final-ui.mjs`, `ui.mjs`, `inspecao/desenhar.html` e `sw.js`.
- Testes: `test_chart_profile_axes.py` (sete fluxos reais) e `test_chart_profile_rules.py` (cinco grupos de variações independentes de nomes, valores, escala e posição). A auditoria anterior foi adaptada para verificar a continuidade das subdivisões e a retenção da perna publicada original. A expectativa do cache no teste de atualização do PWA acompanha v120.
- Reutilizadas as cartas de teste já presentes no repositório; nenhum novo PDF incluído.

Testes específicos verificam escalas duplas, MAPt distinto da cabeceira, marcadores contíguos, separação dos mínimos, derivação bloqueada por informação ausente/conflitante, subdivisão bloqueada por coordenada inconsistente, atualização após correção, desfazer, armazenamento offline, exportação e aplicação nativa. A referência real de SBGM permanece como teste de regressão.

A comparação diagnóstica das 33 cartas/36 páginas passou sem exceções. Das 91 pernas anteriores, nenhuma ficou sem representação; houve uma subdivisão verificada de perna anterior e duas novas ligações, resultando em 94 pernas. Contagens não medem completude nem validam as publicações. Nenhum modelo real foi marcado como validado.

Resultados locais, Chromium 154.0.8037.57:

- Suíte completa: **220 testes passaram em 1065.262 s**, sem falhas.
- Teste adicional de detalhes publicados em dimensões de iPhone/paisagem/iPad: **1 teste passou em 7.387 s**. Foi acrescentado após a descoberta da suíte completa; não houve execução única de 221 casos nesta entrega.
- Consolidado: **221 testes distintos aprovados**, incluindo os nove testes anteriores de cabeceira/perfil, os novos casos reais e as variações de referência.
- A derivação anterior de SBGM também passou em execução focalizada de nove testes; os casos reais novos passaram em seis testes e as regras gerais em cinco grupos antes da execução completa.
- Sintaxe JavaScript/Python, JSON, integridade das métricas do conjunto de referência e whitespace do diff verificados.
- Nenhum CI remoto foi iniciado nesta entrega local. A comparação por carta/página está em `tests/fixtures/charts/profile-reference-results.json`.

 A verificação física em Safari/iPhone/iPad continua pendente: atualização do PWA, comparação da ILS com a carta, resolução do qualificador de GL008, edição das novas pernas, desfazer, reabertura offline e consulta da origem após aplicação.

## Limitações conhecidas

- O interpretador novo é de perfis IAC digitais do padrão DECEA com rótulos explícitos suportados. Não representa reconhecimento integral de IAC/SID ou de todas as convenções gráficas.
- Uma escala THR rotulada DME permanece pendente quanto à natureza da distância. A correção manual de uma coordenada não elimina essa incerteza da publicação.
- Pontos sem coordenadas, limites visuais, RF, esperas, FL, janelas de altitude não reconhecidas e ambiguidades de coluna continuam exigindo dados ou conferência. Sem correspondência geométrica segura, não se cria uma ligação para apenas fechar o desenho.
- A extração de mínimos cobre pares explícitos DA/MDA/OCH identificáveis no cabeçalho; a tabela completa de categorias, RVR/visibilidade e suas condições não foi integralmente codificada.
- Condições da aproximação perdida são preservadas e classificadas por contexto, mas ainda não se tornam um modelo completo de pernas condicionais.
- Os testes usam amostras históricas e a base local disponível; não comprovam vigência da carta, contemporaneidade de todos os fixos nem precisão oficial da posição derivada.

Sem merge ou implantação automática. Publicação em PR depende da autorização do responsável.
