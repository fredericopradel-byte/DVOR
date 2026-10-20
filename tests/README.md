# Testes funcionais do IV-PLANNER

Suíte mínima com `unittest` e Playwright. Não requer build, alteração do
aplicativo, instalação de pacotes aeronáuticos ou acesso ao aplicativo publicado.
A dependência Python pertence exclusivamente aos testes.

## Executar

Na raiz do repositório, com Python 3.10 ou superior:

```sh
python3 -m venv /tmp/iv-planner-tests-venv
. /tmp/iv-planner-tests-venv/bin/activate
python -m pip install -r tests/requirements.txt
python -m playwright install chromium
python -B -m unittest discover -s tests -v
```

Se o ambiente já tiver Chromium e Playwright, o download do navegador é
dispensável. Exemplo usado nesta implementação:

```sh
IV_TEST_CHROMIUM=/usr/bin/chromium python -B -m unittest discover -s tests -v
```

O comando termina com código diferente de zero se houver falha. Instalação de
dependências exige rede; a execução bloqueia serviços externos. O ambiente deve
permitir processos de navegador e sockets no loopback. Nenhum servidor público
é iniciado: a porta local é escolhida automaticamente.

## Cobertura

- Carregamento de 25 rotas: entrada, menus, Legacy, Hawker, DVOR/VOR, PAPI,
  ILS, Radar, editor NDB/Procedimentos, Localidades, Meteorologia e Configurações.
  Inclui rotas de diretório e `index.html`, resposta HTTP 200, interface de
  navegação, título e ausência de exceções JavaScript durante inicialização.
- Missão DVOR com nome, auxílio, data, coordenadas e declinação fictícios:
  salvar pela interface, verificar biblioteca, recarregar e reabrir o registro
  salvo após iniciar uma nova missão. Compara os metadados armazenados.
- Navegação com cliques reais na navegação compartilhada entre as seis áreas,
  conferindo URL e área ativa. Recusa pela interface o aviso de instalação de
  bases quando presente; não força cliques nem injeta estado para escondê-lo.
- Offline em uma origem nova: instala o service worker real, aguarda estado
  `activated` e controle pelo `sw.js` da raiz, desliga a rede do contexto e
  encerra o servidor local antes de visitar as outras páginas. Abre e recarrega
  as 25 rotas, exige respostas do service worker e interface inicializada sem
  exceções, e verifica ausência de novas requisições ao servidor encerrado.
  As páginas não são visitadas antecipadamente para preencher seus caches.

## Isolamento e limites

Cada teste usa um contexto de navegador novo, sem perfil pessoal nem estado
importado. localStorage, IndexedDB e Cache Storage pertencem exclusivamente ao
contexto temporário. Os testes não limpam nem abrem armazenamento real. O
servidor apenas lê arquivos; não modifica HTML, CSS, scripts, workers ou bases.
O aplicativo roda sob `/DVOR/`, como em uma hospedagem em subdiretório.

Os quatro testes usam subtestes para rotas e áreas. Uma falha de rota deixa a
suíte reprovada mesmo que as demais passem. A janela de observação de erros é
de 300 ms após cada carregamento, além das interações e esperas explícitas.
Não se afirma ausência de erros em todos os fluxos ou após uso prolongado.

Meteorologia, mapas e serviços remotos são deliberadamente indisponíveis;
valida-se a abertura da interface nessa condição, sem validar boletins ou mapas
online. A missão mínima não contém passagens. Cálculos aeronáuticos,
backup/restauração, migração de dados antigos, atualização de workers e
instalação de bases não são cobertos. Os caches usados são os do aplicativo
real; não há worker substituto ou respostas HTML simuladas.

Chromium automatizado não substitui validação em Safari/iOS, instalação na tela
inicial nem ensaio em iPhone/iPad reais. A viewport usada é 1024 × 768; esta
suíte não verifica layout, gestos, GNSS ou uso operacional.

## GitHub Actions

O workflow `.github/workflows/tests.yml` executa os quatro testes em Pull
Requests direcionadas à `main`, com Python 3.12, Playwright e Chromium no
Ubuntu 24.04. Instala somente `tests/requirements.txt` e o Chromium com suas
dependências de sistema (`python -m playwright install --with-deps chromium`).
O comando de execução é o mesmo usado localmente:
`python -B -m unittest discover -s tests -v`.

O job tem limite de 20 minutos, permissão `contents: read` e não persiste
credenciais no checkout. Não requer segredos configurados, build ou deploy.
A execução local descrita acima continua independente do GitHub Actions.
Validar o YAML não comprova o funcionamento do job: conferir a execução e os
logs na aba Checks da Pull Request, incluindo o resultado dos quatro testes.


## Interface de Procedimentos e NDB

`test_procedure_ui.py` inclui quatro testes na descoberta automática (oito
no total), usando o mesmo servidor somente de leitura e contextos temporários:

- As quatro abas de cada módulo, barra única com ícones e seleção, ausência
  dos campos equipe/aeronave, preservação da GS e ausência de overflow ou
  sobreposição do último controle ao chegar ao fim da página. Viewports:
  390 × 844, 844 × 390, 820 × 1180 e 1180 × 820.
- Recuos de safe area por `Emulation.setSafeAreaInsetsOverride` no Chromium
  (44 px nas laterais e 34 px embaixo); isto não substitui Safari/iOS real.
- Dados antigos fictícios com equipe/aeronave: editar, salvar, iniciar uma
  missão vazia, reabrir e recarregar; verificar que os valores antigos e o
  rascunho do outro módulo permanecem intactos.
- Desenhar ponto, reta e curva, desfazer/refazer, zoom/enquadramento, gesto
  com dois toques, seleção/arraste, navegação de ida e volta, exportação,
  importação e reabertura. Os fluxos verificam exceções JavaScript.

A quarta regressão compara os estilos efetivos da cápsula com DVOR e ILS
(bordas, cor, sombra, altura, padding, gap e blur), verifica a seleção em todas
as abas e testa datas vazias/preenchidas sem ultrapassar o cartão. Larguras:
320, 375, 390, 430, 768, 820, 844 e 1180 px. O valor persistido continua ISO
(`YYYY-MM-DD`). WebKit/Safari real não é coberto por esta execução Chromium.

Executar somente estas regressões:

```sh
IV_TEST_CHROMIUM=/usr/bin/chromium python -B -m unittest discover -s tests -p test_procedure_ui.py -v
```

O workflow existente usa descoberta automática e também executa estes testes.
As verificações novas não exercitam cadastros aeronáuticos, backup/restauração
ou atualização de uma instalação PWA antiga; esses mecanismos não foram
alterados. O teste offline original continua cobrindo as duas rotas do editor.


## Mapa offline e correções visuais gerais

`test_offline_map_visual.py` acrescenta oito testes (16 no total na suíte):

- SHA-256, 241 países, rings fechados, limites WGS84 e corte no antimeridiano;
- Cartografia desenhada em Canvas, projeção independente do marcador SBGL,
  arraste/zoom e reabertura da última consulta sem regravar seu formato;
- Instalação do APP_SHELL real, desligamento da rede e do servidor antes de
  visitar Meteorologia: base/Leaflet/markers funcionais, recarga e distinção
  entre fundo local e imagens meteorológicas online;
- Transporte offline com interface de rede conectada: o indicador não afirma
  conectividade, a consulta falha sem gravar dados e o mapa local permanece.
  O sinal `navigator.onLine` é simulado separadamente do bloqueio real de rede
  porque a emulação CDP não o altera consistentemente entre versões Chromium;
- Nomes completos das abas selecionadas no iPhone de 320 px;
- Dock sem interseção entre cápsula e botão global, fontes de toque de 16 px,
  safe areas, modais locais sem sobreposição e ajuda correta do Mapa Radar;
- Atualização de v94 para o worker atual preservando missão NDB fictícia,
  IndexedDB e cache de pacote fictício; depois, mapa funcional offline;
- Falha intencional 503 de um recurso novo: o worker candidato não ativa,
  a versão anterior e os dados permanecem disponíveis.

O fixture contém bytes do worker real anterior, identificado em
`fixtures/README.md`; as páginas e assets servidos são os do checkout atual.
Não reconstrói todas as versões históricas de HTML. Não há testes com dados
pessoais. O cenário 503 pode cancelar requisições ao servidor local; isso é
esperado e não substitui as verificações explícitas de preservação.

A base Natural Earth não inclui ruas, rios, relevo ou limites estaduais. Os
produtos meteorológicos permanecem externos. Validar ainda Safari/iOS real,
teclado, PWA em dispositivo e desempenho/memória em hardware operacional.

## Segurança da Missão e acessos neutros — PR 1

`test_mission_safety.py` acrescenta oito regressões à descoberta automática
(24 testes no total):

- Cancelamento de Nova missão, recuperação persistente após recarga, dados
  históricos de equipe/aeronave e independência entre NDB e Procedimentos.
- Reabertura que preserva alterações não salvas sem sobrescrever a missão
  original; documentos já guardados não produzem cópias idênticas de recuperação.
- Importação e abertura pelo catálogo protegidas mesmo com missão sem pontos.
- Falha de gravação na biblioteca ou no rascunho impede substituição; rascunho
  ilegível permanece intacto.
- Salvamento captura referências geográficas ainda não aplicadas e restaura a
  biblioteca anterior se a gravação do rascunho falhar.
- Exclusão exige duas confirmações identificando o registro, preserva o
  rascunho aberto e os campos pendentes; ações sem seleção ficam desabilitadas.
- Exportação e restauração do backup geral em outro contexto temporário,
  incluindo a reabertura de uma recuperação restaurada.
- Cartões com estilos e dimensões iguais, URLs preservadas e hierarquia de
  Salvar/Nova missão em viewports de iPhone/iPad, retrato e paisagem.

As recuperações usam as bibliotecas de missões já incluídas no backup geral,
sem nova chave nem alteração do formato de desenho. Permanecem na lista até
exclusão explícita; não há limpeza automática. O worker central mantém suas
estratégias e passa a usar o cache v96 para distribuir as páginas atualizadas.
O teste de atualização bem-sucedida foi ajustado para essa versão; o fixture
v94 e o cenário de atualização incompleta continuam preservados.

```sh
IV_TEST_CHROMIUM=/usr/bin/chromium python -B -m unittest discover -s tests -p test_mission_safety.py -v
```

Todos os registros são fictícios e os perfis são temporários. Estas regressões
Chromium não validam Safari/iOS real, GNSS ou critérios aeronáuticos.

## Editor horizontal — PR 2

`test_horizontal_editor.py` acrescenta dez testes (34 no total) com documentos
e dados publicados fictícios:

- Leitura de desenhos v1 antigos, cadeado persistente de perna e extremos
  compartilhados, bloqueio de exclusão e reposicionamento por referência.
- Seleção múltipla por toques CDP, bloqueio/desbloqueio conjunto e pan sem
  deslocar a geometria.
- Divisão de reta com conectividade, sequência explícita e desfazer/refazer.
- Divisão de arco com ponto no círculo original, raio e sentido preservados.
- Inversão de curva preservando geometria e escolha manual de ramificações.
- Dados originais de pernas divididas preservados; cálculos ficam pendentes
  até revisão explícita, sem redistribuição automática de tempos ou limites.
- Edição numérica e aplicação de tempos não movem pontos de pernas bloqueadas.
- Backup/restauração em outro contexto preserva cadeados, sequência, fontes
  originais, origem geográfica e revisão pendente.
- Gesto de dois dedos sobre geometria bloqueada continua mudando somente a vista.
- Importações com cadeados inválidos, sequência desconectada ou fonte ausente
  são rejeitadas sem substituir o documento atual.

O editor lê desenhos v1 e v2 e salva os novos documentos como v2, com campos
validados (`locked`, `flight`, `splitSources` e `reviewRequired`). O backup geral
continua no formato v1 e aceita documentos de desenho nas duas versões. Isso
evita que o editor anterior aceite os novos arquivos e descarte os cadeados
silenciosamente; versões anteriores precisam ser atualizadas para abri-los. A sequência não altera fórmulas
operacionais nem passa a escolher ramificações nos cálculos existentes. As
fontes originais de divisões ficam preservadas no documento, mesmo após revisar
os valores das novas pernas. O backup usa as mesmas categorias de missão e
rascunho. O worker central recebe somente a versão de cache v97.

```sh
IV_TEST_CHROMIUM=/usr/bin/chromium python -B -m unittest discover -s tests -p test_horizontal_editor.py -v
```

Os testes de viewport e safe areas do editor continuam na suíte existente.
Chromium e toques CDP não substituem validação em Safari/iOS e dispositivos reais.

## Modelos, ancoragem e azimute — PR 3

`test_procedure_models.py` acrescenta nove testes (43 no total):

- Modelos RNP com três ramos e convencional com bloqueio, afastamento e
  aproximação, além de desenho em branco: geometrias ilustrativas editáveis,
  sem inferir restrições, fases publicadas ou sequência de voo.
- Confirmação e recuperação do desenho anterior, preservação dos metadados
  da missão, falha de gravação e independência dos rascunhos dos dois módulos.
- Rotação por azimute absoluto da reta escolhida, centro fixo, cancelamento,
  rigidez das distâncias/curvas, sequência, desfazer/refazer e recarga.
- Conversão verdadeira/magnética com declinação manual E/W e confirmação
  renovada quando a referência muda; entradas vazias e fora dos limites.
- Ancoragem exata do ponto escolhido nas coordenadas informadas, tornando-o
  origem local sem modificar as medidas relativas, restrições ou sequência.
- Proteção de cadeados, travas de rumo e referências ainda não aplicadas;
  rejeição de coordenadas inválidas sem modificar o documento.
- Backup/restauração das geometrias transformadas em contexto novo.
- Modelos e rotação offline em viewports de iPhone/iPad, retrato/paisagem,
  sem overflow horizontal e com controles de pelo menos 44 px.
- Acionamento da rotação por toque CDP com safe areas e ponto central
  bloqueado: o centro mantém suas coordenadas locais e geográficas.

As transformações usam o plano local existente. O azimute verdadeiro resulta
da declinação informada, sem WMM automático nem novo cálculo aeronáutico ou
rumo geodésico. A ancoragem redefine a origem; os outros pontos são
reposicionados. Travas de azimute precisam ser desativadas para rotação;
cadeados impedem mudanças na geometria que protegem. Os dados persistidos
continuam no schema de desenho v2 e nas mesmas chaves de armazenamento.
Fontes originais de divisões continuam preservadas e não são transformadas.
O service worker central recebe somente a versão de cache v98; os novos
controles são locais à página já incluída no APP_SHELL.

```sh
IV_TEST_CHROMIUM=/usr/bin/chromium python -B -m unittest discover -s tests -p test_procedure_models.py -v
```

Chromium, viewports e safe areas emulados não substituem Safari/iOS real.

## Perfil vertical vinculado — PR 4

`test_vertical_profile.py` acrescenta onze testes (54 no total):

- Alternância horizontal/vertical sem modificar geometria ou câmera;
  sequência parcial identificada e ramificações nunca escolhidas automaticamente.
- Pontos e pernas na ordem explícita, inclusive retorno ao mesmo ponto;
  distâncias locais acumuladas e comprimento dos arcos, em NM.
- Altitudes publicadas e planejadas manuais distintas, sem preencher valores
  ausentes nem ligar a trajetória através de um ponto sem altitude planejada.
- Caixas com hachuras diagonais para mínima, máxima, exata e janela;
  validação atômica de intervalos e edição das restrições das pernas.
- Os mesmos dados na aba Restrições e no perfil. A altitude planejada nova
  não altera as altitudes calculadas na aba Inspeção.
- Edição vertical preserva cadeados da geometria, sequência, fontes originais
  de pernas divididas e a indicação de revisão pendente; desfazer/refazer.
- Edições ainda não aplicadas exigem confirmação antes de descarte ao trocar
  de elemento, vista ou aba. Repetir o toque na vista ativa mantém os campos.
- Leitura de desenhos v1/v2, exportação/importação v3, recarga e independência
  dos rascunhos NDB e Procedimentos.
- Backup/restauração do rascunho e missão v3 em outro contexto, com missões
  históricas v1/v2 na mesma biblioteca; dados inválidos permanecem preservados.
- Instalação do worker real, edição e recarga offline do perfil.
- Rolagem horizontal por toque CDP, safe areas e controles de pelo menos
  44 px em viewports iPhone/iPad, retrato e paisagem, sem overflow da página.

A representação é esquemática, inspirada no perfil IAC, e não constitui uma
carta. A escala vertical acompanha os valores informados; o espaçamento
horizontal prioriza a leitura e **não está em escala**. As distâncias locais
de cada perna e as acumuladas são mostradas numericamente. Não há avaliação
de cumprimento de restrições, gradientes, descidas ou interpolação automática.
Os cálculos operacionais preexistentes permanecem na aba Inspeção.

O campo `plannedAltitude` pertence às mesmas restrições dos pontos e é
independente de `inspectionAltitude`. Altitudes publicadas, limites e tipos
reutilizam `altitude`, `upperAltitude` e `qualifier`. Os cadeados continuam
protegendo a geometria horizontal; eles não impedem editar altitudes.

O editor lê desenhos v1, v2 e v3 e passa a gravar v3, evitando que versões
anteriores aceitem o arquivo e descartem a altitude planejada silenciosamente.
As chaves existentes são preservadas. O backup geral mantém formato v1 e
aceita as três versões de desenho em rascunhos, missões e catálogo. Atualizar
o aplicativo em todos os dispositivos antes de compartilhar desenhos v3.

O único novo recurso é `inspecao/vertical-profile.js`, incluído no APP_SHELL
do worker central (cache v99). Não há novas dependências ou serviços externos.

```sh
IV_TEST_CHROMIUM=/usr/bin/chromium python -B -m unittest discover -s tests -p test_vertical_profile.py -v
```

Os testes usam valores fictícios e perfis temporários. Validar ainda Safari/iOS,
PWA instalado e dispositivos reais; a emulação Chromium não os substitui.

## Bases aeronáuticas na Missão — PR 5

`test_mission_databases.py` acrescenta doze testes (66 no total). As bases de
teste são inteiramente fictícias, servidas pelo worker real a partir de um
pacote em Cache Storage e IndexedDB temporários. Arquivos incorporados e
pacotes reais não são alterados.

- Fontes ROTAER, ADC, AIXM e cadastros manuais apresentadas separadamente;
  seleção de localidade, ICAO e cabeceira com confirmação das mudanças.
- Rumo magnético publicado da ADC tem precedência; rumos legados sem fonte
  verificada não são apresentados como publicados nem estimados pelo designador.
- Metadados de procedimentos AIXM preenchem identificação e tipo IAC/SID,
  sem inventar pernas, restrições, carta, revisão ou vínculo com cabeceira
  deduzido do nome. STAR aparece somente para consulta.
- NDB: frequência kHz/MHz, elevação M/FT, elevação zero, coordenadas zero
  válidas e rejeição de pares incompletos. Unidade desconhecida ou valor ausente
  não substitui o campo manual existente.
- Coordenadas de ARP, cabeceira e auxílio são referências distintas. A aplicação
  como origem é explícita e respeita cadeados; não gira o desenho nem preenche
  declinação automaticamente. Edições pendentes de referência são preservadas.
- Falha de gravação mantém documento e rascunho anteriores; cadastros corrompidos
  não são apagados nem regravados pela consulta.
- O catálogo de desenhos locais mantém a separação dos módulos e usa a
  confirmação e recuperação existentes ao abrir um desenho.
- AIXM indisponível mantém ROTAER, cadastros locais e edição manual funcionais;
  nova tentativa encontra o pacote depois de disponibilizado.
- Resposta atrasada não atualiza uma busca alterada nem preenche a missão.
- Busca e preenchimento offline, recarga, fontes/cache preservados, missão
  salva e backup/restauração em outro contexto temporário.
- Controles em viewports iPhone/iPad, retrato/paisagem, safe areas e seleção
  por toque CDP, sem overflow horizontal da página.

A consulta reutiliza `IVAixm.load()` e seus adaptadores. O cliente passa a
expor também os aeródromos e metadados de procedimentos já presentes no índice
instalado; não baixa nem interpreta o XML integral. Nenhuma base foi atualizada.
O AIXM permanece opcional: seus registros só estão disponíveis quando o pacote
está instalado e acessível. Datas dos registros e da base não comprovam vigência
operacional nem correspondem automaticamente à revisão da carta.

O preenchimento usa os campos existentes de missão e referência. Campos não
fornecidos são mantidos; ao trocar localidade ou auxílio, o usuário deve
conferir os demais campos que continuaram no planejamento. Não há novos campos
persistidos, chaves ou versão de desenho: continuam válidos os desenhos v1/v2/v3,
com gravação v3 e backup geral v1. Informações de fonte aparecem na consulta;
os valores preenchidos continuam sujeitos à edição manual.

O recurso local `inspecao/mission-databases.js` entra no APP_SHELL do worker
central (cache v100). Scripts ROTAER, ADC e AIXM reutilizam os caminhos e as
estratégias de pacote/offline existentes, sem novas dependências externas.

```sh
IV_TEST_CHROMIUM=/usr/bin/chromium python -B -m unittest discover -s tests -p test_mission_databases.py -v
```

Pendente: Safari/iOS real, PWA instalado e conferência operacional com as
publicações aplicáveis. Chromium e dados fictícios não substituem essa validação.

## Mapas e perfil Radar — PR 6

`test_map_controls.py` acrescenta oito testes (74 no total):

- O perfil Radar mantém a rotação zero em um gesto real de dois dedos CDP,
  com zoom e pan funcionais, passagens e rascunho preservados.
- A rotação em planta continua funcionando antes e depois da troca de vista.
- GNSS simulado por CDP atualiza posição, altitude, velocidade e rumo;
  aeronave e centralização funcionam no perfil sem girar os eixos.
- Nove rotas de mapa em cinco viewports, incluindo as cópias antigas PAPI/ILS
  na raiz, sem alvos menores que 44 px, corte de controles, interseções entre
  os elementos auditados ou overflow horizontal da página.
- Safe areas emuladas em retrato e paisagem nas sete rotas operacionais.
- DVOR/VOR, Procedimentos e NDB mantêm rotação por gesto; o zoom Leaflet
  continua reposicionando os marcadores de Meteorologia.
- Roda do mouse, deslocamento e reset por duplo clique no perfil Radar.
- Radar offline após instalação do worker central pela entrada real do app,
  recarga e gestos, mantendo as passagens fictícias e os dados persistidos.

Os controles de mapa e de passagens acima dos mapas SVG passam a ter alvos de
pelo menos 44 px. Zoom/giro e COR/PERFIL ficam na segunda linha superior de
DVOR/Radar, separados do quadro GNSS logo abaixo do gráfico. O contêiner segue
o tamanho do desenho, sem espaço vazio empurrando a leitura para o dock.
As regras são visuais e
localizadas em `page-ui.css`; não substituem os motores SVG, Canvas ou Leaflet.
As cores operacionais continuam nos módulos, e a atribuição do mapa é mantida.

O diagnóstico, as rotas, os limites e as pendências das cópias legadas estão em
[`docs/MAP-AUDIT-PR6.md`](../docs/MAP-AUDIT-PR6.md). Os testes dessas cópias
cobrem apresentação e controles, sem afirmar equivalência funcional com as
versões atuais de `inspecao/` nem nova cobertura offline para as rotas legadas.

O worker central muda somente a versão do cache para v101. As regras de
atualização, os recursos existentes do APP_SHELL e os pacotes são preservados.
Não há alteração de schema, armazenamento, bases ou cálculos operacionais.

```sh
IV_TEST_CHROMIUM=/usr/bin/chromium python -B -m unittest discover -s tests -p test_map_controls.py -v
```

CDP, viewports e geolocalização simulada no Chromium não substituem Safari/iOS,
PWA instalado, interfaces de permissão nem GNSS em iPhone/iPad reais.

### PR 7 — Relatórios PDF

A auditoria de geradores e os limites estão em
[`docs/PDF-AUDIT-PR7.md`](../docs/PDF-AUDIT-PR7.md).
`test_report_pdf.py` adiciona oito testes (82 no total) com downloads reais,
leitura A4 por PyMuPDF, margens, colisões de glifos, fundo dos títulos,
preservação dos valores e da entrada, formulários Legacy/Hawker e restauração
da câmera Radar. Inclui PAPI, ILS, DVOR/VOR, Radar, cópias legadas e textos
maiores que uma página. A geração offline é exercitada nas seis rotas
operacionais após instalar o worker pela entrada do aplicativo.

A dependência `PyMuPDF` em `tests/requirements.txt` serve somente aos testes;
o aplicativo continua sem nova biblioteca. Para salvar os exemplos fictícios
e as imagens de todas as páginas:

```sh
IV_TEST_CHROMIUM=/usr/bin/chromium IV_TEST_PDF_DIR=work/pdf-review python -B -m unittest discover -s tests -p test_report_pdf.py -v
```

Não usar os exemplos como planejamento operacional. Compartilhamento/impressão
e download no Safari/iOS real permanecem pendentes. O worker só recebe a versão
de cache v102; cálculos, unidades, formatos de missão e dados persistidos não
foram alterados.

### PR 8 — Ícone e painel APU com verificações reais

[`docs/BRANDING-PR8.md`](../docs/BRANDING-PR8.md) documenta os originais aprovados,
os ícones, os estados e o escopo das verificações. `test_branding_startup.py`
contém dez testes (92 no total): dois de recursos e oito de inicialização real.
Inclui recurso essencial indisponível, recuperação via Tentar novamente sem
perder rascunho, timeout sem falso READY, armazenamento indisponível, ausência
de internet com recursos instalados, movimento reduzido, seis viewports,
diagonais separadas e coordenação com a oferta de bases.

O painel HTML/CSS substitui a reprodução temporizada do GIF e não depende de
serviços meteorológicos. A marca de sucesso fica apenas em sessionStorage;
missões/configurações não são alteradas. O worker central recebe a revisão v104.
A validação em Safari/iOS real continua pendente. Pillow serve somente à
preparação/testes dos ícones, sem dependência no aplicativo.

#### Independência do indicador de rede no Chromium

O teste offline da inicialização desliga uma origem HTTP isolada e bloqueia o
transporte do navegador. Comprova navegação pelo service worker, falha de uma
consulta não instalada e READY usando os recursos locais. Exercita separadamente
`navigator.onLine` verdadeiro e falso, pois o Chromium do CI pode conservar esse
sinal verdadeiro durante a emulação offline. A aplicação e seus critérios de
falha não são alterados; o teste não depende desse sinal para comprovar a rede.

## Editor contextual — primeira etapa

`test_contextual_editor.py` acrescenta sete regressões funcionais, com dados
fictícios e perfis temporários. Cobrem seleção simples sem alterar geometria ou
histórico, alternância de seleção múltipla por toques CDP, cadeados mistos e
compartilhados, desfazer/refazer do bloqueio, recarga, independência dos módulos,
edição pendente preservada ao tocar o fundo, painéis retráteis, menus secundários,
alternância para o perfil vertical e layout sem rolagem/colisão com o dock.

O layout é medido em 320 × 568, 390 × 844, 844 × 390, 820 × 1180 e 1180 × 820,
com e sem safe areas emuladas. Verifica áreas de toque de pelo menos 44 × 44 px
na barra. A seleção também é exercitada quando um ponto coincide com a escala
gráfica; a escala não pode interceptar o evento do ponto.

```sh
IV_TEST_CHROMIUM=/usr/bin/chromium python -B -m unittest discover -s tests -p test_contextual_editor.py -v
```

Os testes anteriores mantêm suas verificações e passam a abrir os menus de
criação, operações e opções pela interface. O cadeado contextual substitui os
botões separados de bloquear/desbloquear. Não há novo schema ou chave de
armazenamento; desenhos antigos continuam com os valores padrão existentes.
O worker central usa v108 para distribuir o editor atualizado, mantendo as
estratégias e a lista de recursos essenciais existentes.

Esta etapa não implementa pressão prolongada, movimentação/rotação conjunta,
lixeira por gesto, seleção por retângulo ou quantização da geometria. Os
arrastes e a rotação da vista existentes permanecem; sua substituição exige a
etapa seguinte autorizada pelo responsável. A suíte Chromium não valida Safari
ou gestos em iPhone/iPad reais. Conferir nesses dispositivos o PWA offline,
notch, barra do navegador, teclado e uso dos painéis em ambas as orientações.

O limite do job de CI passa a 20 minutos para acomodar a suíte de 113 testes e
as matrizes de dispositivos. Isso não altera verificações nem critérios de aprovação.

## Área útil e precisão editável — ajuste do editor

`test_drawing_precision.py` adiciona onze cenários. Verifica valores calculados
pelas coordenadas persistidas, além dos rótulos: entradas numéricas, criação,
arraste de ponto por toque CDP, alça de curva por ponteiro, modelos novos,
rotação absoluta, histórico, cancelamento, recarga, cadeados e encaixes
incompatíveis sem pontos órfãos. A área gráfica termina a aproximadamente
12 px do dock nas dimensões de iPhone/iPad, inclusive com safe areas emuladas.

`inspecao/drawing-precision.js` concentra os passos de 1° e 0,1 NM, com empates
arredondados para longe de zero. Retas criadas/editadas são reconstruídas com
os parâmetros aplicados; curvas usam raio em 0,1 NM e abertura em 1°. No
arraste de um ponto conectado, o snap usa a perna selecionada ou a conexão de
entrada como referência; as outras conexões são recalculadas. Cálculos
derivados, comprimento de arco, conversões geográficas e declinação mantêm
precisão interna. O encaixe não desloca silenciosamente pontos existentes
para satisfazer passos incompatíveis.

Não há migração ao abrir/importar desenhos antigos. Selecionar, renomear e
bloquear não normalizam coordenadas históricas. A aplicação explícita das
medidas usa os valores apresentados no painel. Modelos/exemplos novos usam
os passos; os documentos já salvos permanecem intactos. Aplicar pernas NDB
normaliza somente o desenho: tempos, restrições e resultados operacionais
continuam com os valores completos. O novo recurso local integra o APP_SHELL
no cache v109, sem dependência externa.

```sh
IV_TEST_CHROMIUM=/usr/bin/chromium PYTHONPATH=tests python -B -m unittest test_drawing_precision -v
```

Os testes são Chromium. Safari/iOS real, barra dinâmica do navegador e teclado
em iPhone/iPad continuam exigindo validação nos dispositivos.
