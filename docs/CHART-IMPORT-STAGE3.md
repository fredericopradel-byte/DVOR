# Importador de cartas — Etapa 3

Base: main `5178696a725cfa6b6b8432e8f4665514e6709c75` (Etapa 2 integrada).
Branch: `feat/chart-import-stage3`. A entrega é uma reconstrução **parcial e não validada**.
Não aplica modelos à missão nem modifica regras de inspeção.

## Comportamento

Após extrair a página, o assistente associa identificadores às bases locais disponíveis,
reconstrói pernas verificáveis e apresenta uma prévia com o renderizador nativo existente.
As abas Carta original, Prévia do desenho e Comparar permitem conferir o resultado;
a comparação lado a lado aparece em telas largas. A prévia não escreve o documento,
a seleção, o histórico ou as configurações do editor. Teclas do editor ficam suspensas
com o assistente aberto.

A representação intermediária `ivplanner-chart-geometry-v1` contém pontos, coordenadas,
origens e versões, evidências textuais, definições publicadas das pernas, restrições
verticais, estruturas não resolvidas, caminhos dirigidos, verificações e pendências.
Convergências são preservadas sem selecionar silenciosamente uma transição.

A associação consulta o AIXM **já instalado**, localidades e auxílios manuais existentes,
sem instalar, atualizar ou modificar bases. A ausência do pacote é explícita. Homônimos
não são resolvidos escolhendo simplesmente o mais próximo. Datas incompatíveis com a
carta geram pendência crítica; a base atual não comprova uma coordenada histórica.
Coordenadas textuais explícitas, com hemisférios e datum WGS84, têm prioridade sobre a
base, conservando publicação e eventual conflito. Esse formato estrito tem teste
sintético; não constitui cobertura de todas as tabelas de coordenadas reais.

Cursos e distâncias são confrontados por geodésia WGS84 (Vincenty). Os intervalos de
comparação derivam da resolução publicada, incluindo a resolução da VAR usada; não
são critérios de aprovação operacional. Referências magnética e verdadeira permanecem
distintas. A VAR publicada e sua época são conservadas; não se aplica WMM a todo rumo.
Pixels servem apenas como evidência complementar de associação, nunca como coordenada.

Coordenadas oficiais e valores publicados mantêm a precisão original. A conversão
para o plano local usa a projeção já adotada pelo editor, sem snap destrutivo. Curvas
com centro, raio, sentido e extensão conhecidos são subdivididas em curvas nativas,
com erro de projeção registrado; geometria incompatível é recusada. Arcos incompletos,
órbitas e hipódromos não são convertidos em retas. Janelas verticais inválidas não são
transferidas. Altitudes publicadas não preenchem altitude planejada, de inspeção ou
clearance. A integração operacional com o perfil vertical fica para a Etapa 5.

## Evidências nas dez cartas fornecidas

| Carta | Resultado local comprovado / limite |
| --- | --- |
| SBNT RNP 16L | Quatro pernas; três IAF convergem para NT364, depois NT366. RW16L ambíguo e datas exigem revisão. |
| SBNT ILS Y 16L | Quatro pernas dos ramos iniciais; não equivale ao procedimento ILS completo. |
| SBNT ILS W / LOC W 16L | OPNAG–BUXUP; arco e demais segmentos pendentes. |
| SBNT VOR W 16L | SALBA–EVNOP; arco/espera e conflitos permanecem pendentes. |
| SBNT VOR Y 12 | ETINA–ISIRI; arco e demais segmentos pendentes. |
| SBNT VOR Z 12 | Auxílio/fixo associados; afastamento/espera sem reconstrução automática suficiente. |
| SBRJ EVSOB 1D 20L | Cadeia LOKOD–EVSOB–VAMIX–TIVRO–BITAK e trecho PAI–ESORU; demais conexões pendentes. |
| SBLS NDB 13 | ULVUK–KUDGU, KUDGU–KOVMO e LST–ESIGO; altitudes mínimas associadas. Distância 3,5 não sustenta KOVMO–LST nas coordenadas disponíveis: ligação bloqueada. |
| SBBQ NDB 18 | Raster sem texto: requer OCR; nenhum desenho inventado. |
| SBJP NDB Y 16 | Raster sem texto: requer OCR; nenhum desenho inventado. |

`geometry-goldens.json` contém expectativas parciais transcritas das cartas e snapshots
identificados das coordenadas da base. Não certifica o procedimento completo nem
substitui revisão independente dos modelos. Identificação visual de símbolos de
espera, radiais, DME e aproximação perdida ainda não está automatizada integralmente.
O provedor inicial é limitado a PDFs digitais DECEA identificados como IAC/SID;
layouts não suportados ficam explicitamente pendentes.

## Persistência e offline

O modelo intermediário e o envelope nativo ficam no mesmo rascunho IndexedDB da Etapa 2,
separados por módulo. Ao reabrir, o snapshot é validado e a prévia regenerada sem depender
de rede ou da permanência da base instalada. Atualizar prévia é uma ação explícita;
sem base disponível, o snapshot anterior é preservado. Atualizações guardam o snapshot
anterior no rascunho. Não há alteração de chaves de missão ou de documentos manuais.

`.ivchart` versão 2 conserva o snapshot e o original com hash; versão 1 continua legível.
A restauração confere módulo, hash, página e estrutura e força revisão não validada.
O backup geral ainda não inclui a base de importações: permanece a exportação própria.
Os cinco módulos novos entram no APP_SHELL do service worker principal (v114).
Não há OCR, serviços externos, transmissão de arquivos ou novas dependências.

## Arquivos

- `aeronautical.mjs`: índice e associação às fontes locais, somente leitura.
- `decea.mjs`: agrupamento textual orientado, evidências de layout e interpretações explícitas.
- `geodesy.mjs`: operações WGS84 e projeção do editor.
- `reconstruct.mjs`: modelo intermediário, validação e sequenciamento.
- `native.mjs`: conversão para schema 3 e rastreabilidade da projeção.
- `extract.mjs`, `ui.mjs`, `ui.css`: snapshot portátil, retomada e conferência.
- `inspecao/desenhar.html`: chamada isolada ao renderizador existente.
- `sw.js`: cache dos recursos locais; teste de atualização ajustado à versão.
- `tests/test_chart_geometry.py`, fixtures e manifesto: dez PDFs e expectativas parciais.

## Verificação

```sh
IV_TEST_CHROMIUM=/usr/bin/chromium python -B -m unittest discover -s tests
```

Testes em perfis temporários verificam cartas reais, geodésia independente, precisão,
associação ambígua/ausente, distinção magnética, conflitos, curvas, altitude, isolamento,
persistência, reabertura sem base e offline, restauração sem aprovação e preservação do
editor. A suíte de importação também cobre PDF/imagem inválidos, múltiplas páginas,
iPhone/iPad e falhas de armazenamento. Resultado: **148 testes aprovados na suíte completa**, em 749,639 segundos,
Chromium 154.0.8037.57. Dois testes acrescentados após o início dessa execução
passaram separadamente: prévia/comparação nas quatro dimensões de iPhone/iPad e
precedência de coordenada publicada com conflito de base. São **150 casos distintos
aprovados**, dos quais 19 pertencem à nova suíte geométrica. Os 15 casos de importação
incluem agora as dez cartas. Sintaxe de todos os módulos conferida com `node --check`,
hashes das dez amostras conferidos e `git diff --cached --check` sem erros.

Validação manual ainda necessária no Safari de iPhone e iPad: toque, rotação da tela,
comparação, retomada após suspensão do PWA e comportamento sob pressão de armazenamento.

## Próximas etapas

Etapa 4: resolução contextual das pendências, histórico de decisões, recortes e atualização
após respostas. Etapa 5: aprovação única, aplicação à missão, integração do perfil e
backup. Reconhecimento visual avançado permanece opcional, sujeito à aprovação específica
da Etapa 6. Esta etapa não anuncia importação automática integral de IAC/SID.
