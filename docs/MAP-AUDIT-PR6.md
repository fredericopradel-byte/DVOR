# Auditoria dos mapas — PR 6

Auditoria do checkout equivalente à `main` em `4c066c5`, seguida de correções
localizadas. Não foram substituídos motores de mapa nem alterados cálculos,
bases, formatos de missão ou mecanismos de GNSS.

## Rotas inspecionadas

| Mapa | Rota | Achado inicial | Correção |
| --- | --- | --- | --- |
| Radar | `inspecao/radar.html` | Perfil girava com dois dedos; controles de 40 px no iPhone; leitura de zoom/giro sobreposta ao GNSS | Perfil com eixos fixos; rotação em planta mantida; controles de 44 px; leitura e botão PERFIL na segunda linha superior |
| DVOR/VOR | `inspecao/dvor-vor/index.html` | Controles de 40 px; leitura de zoom/giro sobreposta ao GNSS em telas estreitas | Controles de 44 px; leitura e botão COR separados do quadro GNSS |
| ILS | `inspecao/ils.html` | Controles de 40 px e pequeno desalinhamento do botão GNSS | Alvos de 44 px e margens alinhadas; painel externo de GNSS/COR preservado |
| PAPI | `inspecao/papi.html` | Botão GNSS com 40 px de altura | Altura mínima de 44 px; Canvas e gestos preservados |
| Procedimentos | `inspecao/desenhar.html?modulo=procedimentos` | Controles de zoom/enquadramento de 42 px | Alvos de 44 px; modelo, câmera, cadeados e perfil vertical preservados |
| NDB | `inspecao/desenhar.html?modulo=ndb` | Mesmos alvos de 42 px do editor compartilhado | Mesma correção visual, mantendo dados independentes |
| Meteorologia | `meteorologia/index.html` | Links de zoom Leaflet com 30 px e aparência clara isolada | Alvos de 44 px com aparência neutra escura; cartografia, atribuição e marcadores preservados |
| PAPI legado | `papi.html` | Caminho do CSS compartilhado escapava da raiz do aplicativo | Caminho do CSS corrigido; alvos de toque recebem a correção compartilhada |
| ILS legado | `ils.html` | Mesmo problema no caminho do CSS e controles de 40 px no iPhone | Caminho do CSS corrigido; alvos de toque recebem a correção compartilhada |

As alterações de estilo usam seletores de controles de mapa em `page-ui.css`.
As cores operacionais, como TX1/TX2, passagens e GNSS ativo, permanecem no
controle de cada módulo. A leitura GNSS fica logo abaixo do gráfico SVG,
sem disputar espaço com os eixos ou o indicador de zoom/giro. O contêiner deixa
de reservar espaço vazio que podia empurrar a leitura para a barra inferior.
Não há mudanças nos
recursos de navegação, zoom ou rolagem da Meteorologia.
Os controles de avanço, conclusão e desfazer de passagens acima dos mapas SVG
também passam de aproximadamente 43 × 42 px para alvos de pelo menos 44 px.

## Comportamento específico do Radar

Somente o perfil vertical deixa de aplicar o delta angular do gesto de dois
dedos. O zoom e o deslocamento continuam usando os mecanismos anteriores.
O grupo SVG recebe rotação zero no perfil; a aeronave usa o símbolo de perfil
sem compensação angular. A vista em planta mantém sua rotação normal.
Escalas, projeção do perfil, distâncias, altitudes, passagens, centralização e
os cálculos da posição GNSS permanecem inalterados.

## Evidências e limites

- Nove rotas em cinco viewports: 320 × 568, 390 × 844, 844 × 390,
  820 × 1180 e 1180 × 820. Conferência de alvos, alinhamento, interseções,
  limites do mapa e overflow horizontal da página.
- Safe areas emuladas nas sete rotas operacionais: retrato com topo/rodapé
  e paisagem com recuos laterais e rodapé.
- Gestos CDP de dois dedos e mouse no Radar; zoom, pan, reset e alternância
  de vistas. Rotação mantida em DVOR/VOR e nos editores de Procedimentos/NDB.
- Geolocalização do Chromium simulada por CDP, com atualizações de posição,
  altitude, velocidade e rumo no Radar. Não corresponde a GNSS de hardware.
- Comparação do rascunho Radar antes/depois dos gestos e uso offline após
  instalação do worker central pela entrada real do aplicativo.
- Capturas visuais locais de iPhone/iPad para revisão; não constituem
  certificação de Safari/iOS nem de operação aeronáutica.

As cópias antigas de PAPI/ILS na raiz não são as rotas usadas pelo menu atual.
Nesta PR, a validação dessas cópias cobre apresentação e controles; não afirma
equivalência funcional com as versões de `inspecao/`. Outros caminhos antigos
de scripts e imagens dessas cópias devem ser revisados separadamente antes de
ampliar seu uso. A auditoria não substitui testes em iPhone/iPad reais, PWA
instalado, teclado, avisos de permissão e GNSS de hardware.

O service worker central recebe somente a versão de cache v101. Os recursos
compartilhados modificados já pertencem ao APP_SHELL; não há novos serviços
externos ou bibliotecas. As cópias legadas na raiz mantêm sua cobertura offline
anterior, sem inclusão de novas rotas legadas no APP_SHELL.
