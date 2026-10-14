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
