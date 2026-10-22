# Importador — classificação por estrutura e contexto

A correção trata classes de erro, sem regras por aeródromo, nome de fixo, palavra de terreno ou valor de altitude. Não há listas de palavras como “ponte” ou “after” no processamento. Os exemplos negativos nos testes são evidências conhecidas; um identificador com a mesma grafia continua admissível se tiver suporte aeronáutico adequado.

## Comportamento implementado

- Delimitação da planta por bordas vetoriais, referências cartográficas e rótulos de função. Os lados podem estar separados em vários caminhos PDF; não se exige um retângulo único nem uma posição vertical fixa. A combinação de evidências escolhe a região mais restrita que as contém, evitando incluir prosa da aproximação perdida. Sem evidência suficiente, o reconhecimento continua parcial.
- Classificação de rótulos em candidatos a identificador, função, curso, distância, altitude, referência cartográfica e texto não classificado. Letras maiúsculas isoladas são um indício de identificador, não prova de um ponto geográfico. Associação local, função, frequência e verificações geométricas continuam necessárias; nenhum pixel se transforma em coordenada.
- Identificadores desconhecidos da base exigem associação espacial com um rótulo de função. Palavras em frases não são extraídas como fixos pela simples coincidência com um nome da base. Evidências dos rótulos aceitos são conservadas em `point.labelEvidence`.
- Altitudes próximas exigem compatibilidade de tipografia, orientação, alinhamento e separação. Em auxílios, proximidade sozinha não basta: exige-se função associada ou barra de restrição. Linhas longas de diagrama não são aceitas como barras. Barras codificadas como retângulos finos preenchidos também são consideradas. Não existe filtro numérico que rejeite 600 ft, 170 ft ou qualquer outro valor isoladamente.
- Associação no perfil usa separação proporcional ao tamanho do rótulo, evitando alcançar valores de outra faixa do perfil. Restrições adicionais do mesmo ponto recebem IDs distintos. Qualificadores não determinados continuam pendentes.
- A extensão dos rótulos rotacionados é considerada como incerteza na associação visual de uma anotação; curso e distância ainda precisam conferir com coordenadas e referência magnética. Isso preserva a SID cujos identificadores estão rotacionados, sem usar frases como apoio geométrico.
- `(AR)`, `RNP AR APCH`, `RF REQ` e autorização especial são conservados com origem textual. RF gera pendência específica e não é equiparado a arco DME nem convertido em reta.
- Abertura de rascunhos mantém a reconstrução existente. A ação explícita **Atualizar prévia**, em rascunhos sem respostas, atualiza também o reconhecimento a partir da extração preservada e guarda a reconstrução anterior. Rascunhos com respostas mantêm a proteção existente do histórico; a missão não é alterada pela atualização.

A infraestrutura é compartilhada entre NDB e Procedimentos, mantendo seus destinos e dados separados. Não houve alteração de regras de clearance, bases, precisão geodésica ou editor nativo. O único service worker continua sendo o principal: cache `v119`, com `semantics.mjs` no `APP_SHELL`, sem nova dependência.

## Resultados de referência

Comparação com a árvore `9d9e43acd9c838489f2c7e56a00b02d53f31788f`, conteúdo da main consultada após a PR29:

| Carta | Pernas retas selecionadas: antes → depois | Altitudes numéricas de referência: antes → depois |
| --- | --- | --- |
| RNP A RWY 33 | 5/5 → 5/5 | 4/4 → 4/4 |
| RNP Z RWY 33 (AR) | 6/7 → 7/7 | 5/5 → 5/5 |
| VOR Y RWY 15 | 0/1 → 1/1 | 0/5 → 4/5 |
| ILS T OR LOC T RWY 10 | 2/2 → 2/2 | 4/5 → 4/5 |

A VOR agora gera uma perna nativa SOTNU–UMGTI, 155°/6.5 NM. A referência visual continua sendo um subconjunto, não a geometria completa. Na RNP A, a TVD permanece sem reconstrução; na AR, RF é identificado, mas a curva ainda não é reconstruída. A segunda página continua exigindo trabalho de integração.

Os falsos candidatos de prosa e terreno identificados na auditoria foram retirados; CXI não recebe a falsa restrição de 170 ft e os pontos da RNP AR não recebem os rótulos de 600 ft próximos. **Correção da descrição anterior:** esses rótulos de 600 ft estão associados a curvas de nível/terreno na carta, não são todos rótulos da grade geográfica. A implementação evita essa confusão por tipografia e associação de evidências; ainda não interpreta integralmente a topografia.

Foi feita ainda uma comparação local com **33 PDFs/36 páginas**, usando a mesma extração em ambas as versões: **85 pernas anteriores preservadas, 91 após a mudança; nenhuma perna anterior perdida**. Duas plantas antes ausentes passaram a ser delimitadas (VOR Y15 e ILS R/LOC R15). Nenhum modelo foi marcado como validado. A contagem adicional é diagnóstico de comportamento, não certificação das pernas ou das cartas.

O resultado agregado com hashes e diferenças por página está em `tests/fixtures/charts/recognition-improvements.json`. As quatro cartas anotadas estão versionadas nos testes; os demais exemplos utilizados são fixtures anteriores ou anexos fornecidos nesta sessão. A comparação ampliada não é um conjunto independente de validação: a maioria das novas cartas é de SBGL e diversas variantes compartilham geometria.

## Testes e arquivos

- `semantics.mjs`: novo componente puro de classificação e associação de rótulos.
- `decea.mjs`: composição de bordas, evidências de região, barras preenchidas e extensão de rótulos rotacionados.
- `reconstruct.mjs`: seleção de rótulos/pontos e associações verticais por evidência.
- `model.mjs`: identificação de AR/RF e autorização especial.
- `ui.mjs`: descrição de RF e atualização explícita do reconhecimento.
- `sw.js`: atualização do cache e inclusão do novo módulo local.
- `tests/test_chart_semantics.py`: oito testes, com múltiplos nomes/valores, escalas, deslocamentos, bordas fragmentadas, desenho preenchido, prosa, auxílios e rótulos rotacionados. Testa inclusive um valor de 600 ft e identificadores de grafia idêntica aos exemplos negativos em contextos válidos.
- `tests/test_offline_map_visual.py`: expectativa do cache atualizada para v119, preservando verificações de atualização completa/incompleta e integridade de dados.
- `tests/test_chart_reference.py`: auditoria real de quatro cartas/cinco páginas, limites mínimos de acertos, ausência dos falsos positivos conhecidos, IDs únicos, requisitos RF e teste da atualização explícita de rascunho antigo.
- `recognition-reference.json`, `recognition-baseline.json`, `recognition-improvements.json` e quatro PDFs: evidências de referência, estado anterior e resultados.
- `CHART-RECOGNITION-AUDIT.md`: diagnóstico histórico que fundamentou as mudanças.

Execução reproduzível dos testes específicos:

```sh
python -B -m unittest discover -s tests -p test_chart_semantics.py -v
IV_TEST_CHROMIUM=/usr/bin/chromium python -B -m unittest discover -s tests -p test_chart_reference.py -v
```

A variável `IV_TEST_CHROMIUM` pode ser omitida com o Chromium do Playwright instalado. A suíte utiliza perfis temporários, serviços externos bloqueados e armazenamento isolado. Os testes puros de semântica exigem Node.js no ambiente de desenvolvimento/teste; não acrescentam dependência ao PWA.

Resultados locais finais, Chromium 154.0.8037.57:

- Execução completa: **208 testes em 1016.090 s**, 207 aprovados e uma falha exclusivamente na asserção que esperava o cache v118; o cache ativo observado foi v119 e os dados já haviam sido conferidos antes dessa asserção.
- Após atualizar essa expectativa para o cache efetivamente declarado, os **2 testes de atualização completa/incompleta passaram em 16.578 s**. Não se enfraqueceram nem removeram verificações de preservação.
- Referência e novo teste de retomada explícita: **2 testes passaram em 28.056 s**. O teste de retomada foi acrescentado depois da descoberta da suíte completa.
- Resultado consolidado: **209 testes distintos aprovados entre as execuções**, incluindo os oito testes de semântica e o novo fluxo de retomada. A suíte completa não foi repetida após a correção da constante do teste; não há execução única de 209 testes nesta entrega.
- Sintaxe JavaScript/Python, JSON, SHA-256 dos quatro PDFs e whitespace do diff verificados.
- Nenhuma execução de CI remoto foi iniciada nesta entrega local; não se declara CI verde.

## Limitações e validação manual

Esta é uma melhoria do reconhecimento local de PDFs digitais, não um modelo de ML treinado ou um classificador visual universal. Caixa de texto, capitalização e tamanho são evidências conservadoras: convenções gráficas diferentes, texto misturado no mesmo run, fonte irregular ou identificação sem suporte ainda podem exigir intervenção. PDFs digitalizados continuam necessitando OCR/interpretação visual. Arcos, esperas, RF e pernas condicionais não foram integralmente implementados por esta mudança.

Não se alteraram automaticamente modelos já aplicados ou rascunhos com decisões. Para conferir o novo reconhecimento, importar novamente ou usar **Atualizar prévia** em um rascunho sem respostas e com base local instalada. Manter o original para comparação. Vigência das publicações e correspondência temporal das coordenadas continuam não comprovadas pelo reconhecimento.

Validação física pendente em Safari/iPhone/iPad: atualizar o PWA, importar VOR e AR, conferir os avisos e a prévia, retomar rascunho antigo e testar reabertura offline. Não houve publicação, merge ou implantação automática.
