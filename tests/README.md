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

O job tem limite de 10 minutos, permissão `contents: read` e não persiste
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
