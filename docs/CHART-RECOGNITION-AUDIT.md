# Reconhecimento de cartas — referência e diagnóstico SBGL

Diagnóstico anterior às correções. Evolução e resultados posteriores: [classificação por estrutura e contexto](CHART-IMPORT-SEMANTICS.md).

A auditoria encontrou reconhecimento parcial útil de segmentos retos em três cartas, mas nenhum desenho na VOR Y RWY 15. TVD, curvas RF, esperas e a aproximação perdida completa continuam sem reconstrução fiel. Esses resultados justificam corrigir a interpretação local antes de escolher ou treinar um serviço avançado.

## Escopo e reprodutibilidade

Código auditado: árvore `9d9e43acd9c838489f2c7e56a00b02d53f31788f`, idêntica à `main` consultada, commit `cb1f04ce8d984d3f3b836bc70944d19141485226` (merge da PR29). Branch local de trabalho: `analysis/chart-recognition-reference`. Sem alteração dos arquivos operacionais, service worker, bases ou missões. Nenhum processamento externo, treinamento de ML, publicação ou merge nesta entrega.

Quatro PDFs fornecidos pelo responsável foram copiados sem alteração para `tests/fixtures/charts/`. São amostras históricas; suas datas não comprovam vigência. Os SHA-256, páginas, recortes normalizados, valores publicados e limites do conjunto estão em `recognition-reference.json`. O resultado medido está em `recognition-baseline.json`.

As cinco páginas foram renderizadas e examinadas visualmente. A referência contém **subconjuntos** de identificadores, pernas retas e valores de altitude, não uma codificação aeronáutica integral. Não há verdade de referência independente para todas as coordenadas, parâmetros RF, esperas ou trechos condicionais. Nenhuma coordenada geográfica foi obtida de pixels. Os recortes são posições na página, destinados à rastreabilidade visual.

Execução com Chromium 154.0.8037.57, PDF.js incorporado e base `packages/aixm/AIXM-BR-2026-09-03/aixm-core.json`. Cada página foi processada separadamente, como no seletor atual. O teste não agrega a segunda página ao modelo da primeira e não usa o nome do arquivo para reconhecer a carta (o arquivo entregue ao extrator chama-se `neutral.pdf`). O teste bloqueia toda rede fora da origem local e usa perfil temporário, sem dados reais.

```sh
IV_TEST_CHROMIUM=/usr/bin/chromium \
IV_CHART_AUDIT_OUTPUT=/tmp/chart-reference-audit.json \
python -B -m unittest discover -s tests -p test_chart_reference.py -v
```

`IV_TEST_CHROMIUM` pode ser omitido quando o Chromium do Playwright estiver instalado. A variável de saída é opcional; exporta o resultado detalhado sem escrever em armazenamento operacional.

## Resultado medido

Os valores abaixo consideram a página principal de cada carta. A segunda página da RNP A foi extraída e reconstruída separadamente, sem pernas geradas. “Altitude” significa somente associação numérica com ponto, unidade e referência MSL; não comprova qualificador, condição ou perfil completo.

| Carta | Pernas retas de referência reconhecidas | Valores de altitude associados | Pontos no modelo / segmentos nativos | Pendências críticas |
| --- | --- | --- | --- | --- |
| RNP A RWY 33, 13 JUN 2024 | 5 de 5 | 4 de 4 | 9 / 6 | 5 |
| RNP Z RWY 33 (AR), 02 NOV 2023 | 6 de 7 | 5 de 5 | 13 / 7 | 17 |
| VOR Y RWY 15, 03 OCT 2024 | 0 de 1 | 0 de 5 | 0 / 0 | 4 |
| ILS T OR LOC T RWY 10, 10 JUL 2025 | 2 de 2 | 4 de 5 | 7 / 3 | 8 |

Não converter esses números em taxa de reconhecimento integral: o subconjunto favorece pernas retas verificáveis, as curvas não foram quantificadas, há elementos extras incorretos e as quatro cartas são do mesmo aeródromo. O total de segmentos nativos também não mede completude. Todos os modelos permaneceram não validados.

Asserções automatizadas preservam os acertos mínimos desse subconjunto e permitem melhorias. As lacunas são registradas, sem exigir que o programa continue falhando nelas. Aprovação do teste significa que a auditoria executou e os acertos de referência foram preservados; não significa que as cartas foram convertidas integralmente.

## Falhas e evidências

### 1. Limites da planta na VOR: bloqueio anterior à geometria

O título, ICAO, data e referência magnética foram reconhecidos. Entretanto, `layout-missing` suspendeu toda a associação, deixando a planta vazia. A base AIXM foi fornecida ao processamento; o resultado não demonstra ausência dos fixos na base.

`decea.mjs:graphics()` depende de contornos vetoriais específicos ou de um único par de linhas horizontais em faixas proporcionais estreitas da página. Essa carta tem apresentação distinta. Próxima correção: reconhecer candidatos de regiões por evidência estrutural e rótulos, mantendo a suspensão quando limites forem ambíguos. Proibir qualquer uso desse enquadramento gráfico como coordenada geográfica.

### 2. Falsos pontos e falsas restrições

A RNP A ganhou um candidato `PONTE`; a RNP AR ganhou `PONTE` e `AFTER`. São texto de referência terrestre/prosa, não fixos publicados. Na RNP AR aparecem restrições de 600 ft associadas a vários pontos; a inspeção visual da região correspondente mostra rótulos de terreno/curvas de nível próximos, não essas altitudes operacionais. Há ainda IDs de restrição duplicados para um mesmo ponto com valores diferentes. Na ILS, CXI recebeu um candidato de 170 ft próximo de rotulagem do mapa que não comprova restrição naquele auxílio.

`reconstruct.mjs` usa proximidade de rótulos e funções para acrescentar identificadores e altitudes. Próxima correção: classificar zonas e tipos de texto (grade, terreno, prosa, ponto, auxílio, perfil), exigir evidência de associação e gerar IDs únicos. Ausência de qualificador precisa continuar pendente. Não resolver removendo palavras isoladas específicas dessas cartas.

### 3. RNP AR: identidade incompleta e RF sem representação semântica

O título reconhecido é `RNP Z RWY 33`, perdendo `(AR)`. O texto `RNP AR APCH`, `RF REQ.` e a exigência de autorização especial estão presentes na carta, mas não há um requisito RF estruturado nem geometria RF reconstruída. O identificador RWY33 não é um ponto do modelo.

A perna GL086–GL087, 097°/5.5 NM, ficou ambígua; as outras seis pernas retas selecionadas coincidem com a referência. GL032–GL086 é **091°/12.9 NM**, conferido na planta e no texto de aproximação perdida. A curva GL043–GL042 não pode ser completada ligando os extremos por uma reta. O perfil apresenta GL043 a 3.3 NM da THR, GL042/FROP a 1.5 NM e alinhamento final 329°; isso não fornece, por si só, todos os parâmetros para reconstruir qualquer RF.

Próxima correção: conservar qualificadores do título, requisitos AR/RF e restrições de autorização como entidades rastreáveis. Depois, criar uma representação de RF distinta de arco DME e solicitar apenas os parâmetros que não forem determináveis com evidência suficiente. A pendência genérica de cobertura atual impede validação, mas não informa adequadamente essa limitação específica.

### 4. TVD e páginas complementares

A primeira página da RNP A fornece cinco pernas retas de referência reconhecidas. A trajetória visual e suas curvas não foram reconstruídas. A segunda página contém TVD, IAS máxima 160 KT, referências visuais e condições de arremetida, incluindo gradiente de 10% em situações descritas. O extrator encontra texto e gradiente, mas não integra essas condições ao procedimento da primeira página.

Próxima correção: permitir associar páginas do mesmo documento/procedimento com conferência de identidade e revisão; preservar origem por página e agrupar informações repetidas. O gradiente condicionado da manobra visual deve permanecer separado do gradiente de descida do perfil e dos cálculos de inspeção.

### 5. Perfil: distância à cabeceira não equivale a DME

Na VOR Y, o perfil publica duas escalas: SOTNU 11.5 NM à THR/11.8 DME CXI; UMGTI 5.0/5.3; THR 0.0/0.3. MAPt D1.3 CXI não é a cabeceira. Na ILS, GAVUG 10.7 NM à THR/13.0 DME ITB; GL008 8.7/11.0; GL167 5.0/7.3; THR 0.0/2.3. GL008 está no perfil, mas não aparece no modelo atual.

Próxima correção: estruturar cada eixo de distância com referência explícita (THR, MAPt, auxílio identificado), mantendo valores publicados. DME é distância oblíqua quando aplicável; não convertê-la automaticamente em distância horizontal. A derivação da posição da THR exige alinhamento, tipo de distância, fonte de azimute, declinação apropriada e propagação das incertezas. Não arredondar nem deslocar fixos oficiais para encaixá-los no editor.

ILS e LOC compartilham desenho, mas DA 216 ft e MDA 450 ft são alternativas diferentes. A subida perdida depende da condição 2000 ft antes da curva direta PCX e tem altitude final 7000 ft: não escolher um ponto geográfico de curva pela posição dos pixels.

## Próximas mudanças propostas, em ordem

1. **Interpretação local de regiões e rótulos:** recuperar a planta VOR, bloquear grade/prosa como fixo ou altitude, garantir IDs únicos e preservar AR/RF. Critério: novos testes com regiões/evidências de referência, sem aumentar falsos pontos/restrições nos casos atuais.
2. **Perfil com referências explícitas:** eixos THR/MAPt/DME, pontos presentes apenas no perfil, mínimos por variante, condições verticais e checagem das derivações de cabeceira. Critério: reproduzir os valores publicados acima sem confundir escalas ou alterar clearances.
3. **Documento multipágina e topologia:** consolidar páginas, TVD, aproximação perdida, esperas e pernas condicionais; representar suportes/limitações sem atalhos geométricos. Critério: nenhuma página complementar operacional omitida da conferência final.
4. **RF e estruturas ainda não suportadas:** definir representação intermediária e capacidade nativa real antes de qualquer conversão. Selecionar processamento visual avançado somente para lacunas demonstradas.

A inspeção do MCA 96-3/2021 orienta a interpretação: 2.7.21 para outros segmentos, nota da página 58 para RNP a pista visual/TVD, 3.8 para arcos DME, 3.10 e 3.11 para perdida/perfil. Não aplicar “tracejado = visual”: a função, o contexto e a vista da carta também são necessários. A vigência do manual de 2021 não foi verificada nesta auditoria.

## Validação e entrega

- Novo teste de referência: uma execução automatizada cobrindo quatro arquivos/cinco páginas, extração real PDF.js, associação e reconstrução reais, acertos de referência, ausência de validação indevida e ausência de alteração do localStorage.
- Teste de referência: **1 teste passou**, cobrindo os quatro PDFs/cinco páginas e preservando os acertos de referência.
- Regressão geométrica existente: **19 testes passaram em 59.970 s**. A suíte completa da aplicação não foi repetida, pois o código operacional não foi alterado.
- Sintaxe Python e integridade dos quatro arquivos verificadas; conferência do diff sem alterações operacionais.
- Não houve mudança de interface; validação física em iPhone/iPad continua necessária para as etapas funcionais anteriores, mas não foi realizada nesta auditoria.
- Sem PR publicada nesta entrega diagnóstica. Arquivos disponíveis localmente para revisão, sem merge nem implantação.
