# PR 8 — Ícone aprovado e inicialização APU vinculada ao aplicativo

Base remota: `main` em `acd4b23`. Esta revisão preserva os ícones preparados e
substitui a reprodução temporizada do GIF por indicadores HTML/CSS controlados
por verificações reais. O GIF original fornecido (referido como
`apu-animacao-diagonais.gif` na especificação) está preservado em
`assets/branding/approved-apu.gif`; os hashes estão em `sources.json`.

## Ícones e referência visual

A imagem original, 1448 × 1086, gera ícones PWA de 192/512 px, iOS de 180 px e
máscara de 512 px. O recorte central `[181, 0, 1267, 1086]` preserva o botão e o
símbolo sem distorção. As cópias do DVOR e os dois manifests conservam os nomes e
URLs de entrada. `tools/build-branding.py` reproduz esses recursos com Pillow,
utilizado apenas na preparação/testes, sem dependência no aplicativo.

O painel mantém fundo escuro, três molduras metálicas, ON/OFF à esquerda,
STATUS com áreas âmbar/verde separadas ao centro e FIRE EXT à direita. Cada luz
usa `repeating-linear-gradient`, com faixas diagonais e intervalos transparentes:
a área não vira um retângulo de cor sólida. As cores apagadas são discretas;
o vermelho luminoso só é aplicado em FAULT. Mensagens textuais acompanham as
cores. Os GIFs e o quadro estático preparados anteriormente permanecem como
referência; não são reproduzidos durante a inicialização nem pré-carregados.

## Estados e verificações reais

`startup.js` usa os estados:

| Estado | ON/OFF | STATUS âmbar | STATUS verde | FIRE EXT | Mensagem |
| --- | --- | --- | --- | --- | --- |
| Energizando | Branco | Aceso | Apagado | Apagado | ENERGIZANDO — Acionamento do sistema |
| Self Test | Branco | Aceso | Apagado | Apagado | SELF TEST — Verificando os recursos locais |
| Pronto | Branco | Apagado | Aceso | Apagado | READY — IV-PLANNER pronto para operação |
| Falha | Branco | Apagado | Apagado | Vermelho | FAULT — descrição curta do recurso ou condição que falhou |

Não há duração mínima de carregamento. Um frame permite desenhar o estado
inicial; as verificações iniciam ao terminar o parser e os scripts defer da página.
READY só ocorre após:

1. Disponibilidade local, resposta válida e conteúdo não vazio de `global-nav.js`,
   `global-nav.css`, `page-ui.js` e `page-ui.css`.
2. Confirmação da inclusão/aplicação das duas folhas de estilo no documento.
3. Existência dos cartões do menu, controle de navegação e botão de ajuda,
   confirmando que os componentes essenciais montaram a interface.
4. Leitura do armazenamento local disponível ao planejamento.

A leitura não grava sondas nem interpreta/normaliza missões. Dados antigos ou
corrompidos continuam sob os mecanismos de recuperação dos módulos. Esta
verificação não certifica quota livre de escrita, integridade de todas as bases
ou prontidão operacional de uma aeronave; verifica a interface principal local.

METAR, TAF, radar meteorológico, satélite, rede externa, pacotes opcionais e GNSS
não são consultados. Não se usa `navigator.onLine` para decidir FAULT. Sem internet,
a inicialização funciona pelos recursos instalados no worker central.

Após READY, uma transição curta de 350 ms abre o menu; com movimento reduzido,
a transição é imediata e as verificações continuam iguais. A ausência de um
recurso essencial, interface incompleta ou armazenamento inacessível mostra
FAULT. Uma espera acima de 3,5 s aborta a verificação e oferece ações, sem ficar
indefinidamente em SELF TEST. Falhas não são sorteadas nem simuladas em produção.

## Recuperação, navegação e acessibilidade

FAULT oferece **Tentar novamente**, que recarrega de fato os recursos e executa
as verificações novamente. Um parâmetro de navegação transitório autoriza essa
reverificação mesmo com a proteção contra repetição; é removido da URL ao iniciar.
Não há parâmetro de URL para fabricar falhas. **Abrir menu** e Escape permitem
sair da apresentação sem declarar READY. Os dados não são apagados ou migrados.

Somente o sucesso marca `ivplanner-startup-verified-v2` em `sessionStorage`.
A marca antiga da demonstração não substitui uma verificação real. Navegação
interna e retorno pelo histórico não repetem a apresentação; uma recuperação
explícita pode refazer o teste. Foco e `inert` são restaurados ao sair. Sem
JavaScript ou sem o script de apresentação, o HTML mantém o menu disponível.
A oferta existente de bases aguarda o fechamento do painel.

A interface é interna à página. Não se anuncia uma splash screen nativa animada
de PWA no iOS. O sistema continua responsável pela abertura nativa estática e
pelo cache de ícones instalados. Não apagar dados do site para atualizar um ícone.

## Validação e limites

`tests/test_branding_startup.py` contém dez testes: dois de procedência/ícones e
oito de comportamento. Cobrem sequência normal, âmbar enquanto um recurso está
pendente, verde somente após sucesso, vermelho em falta controlada de script,
recuperação real com preservação do rascunho, timeout, armazenamento indisponível,
JavaScript desativado, ausência de internet com recursos instalados, serviços
opcionais bloqueados, movimento reduzido e coordenação com a oferta de bases.

Há verificações de geometria e diagonais em 320 × 568, 390 × 844, 844 × 390,
568 × 320, 820 × 1180 e 1180 × 820, com recuos de safe area emulados.
Os demais testes continuam conferindo mapas, GNSS simulado, missões, backup,
PDFs e offline. A suíte geral usa a ação real de abrir o menu quando o painel
está presente; a suíte específica verifica os estados automáticos.

O worker central recebe somente a revisão v104 e os recursos de execução no
APP_SHELL. A estratégia de atualização, prioridade dos pacotes e worker de
transição DVOR permanecem intactos. Os originais gráficos não são pré-carregados.
Nenhum cálculo aeronáutico, base oficial, chave de missão ou configuração foi
alterado.

```sh
python -m pip install -r tests/requirements.txt
IV_TEST_CHROMIUM=/usr/bin/chromium python -B -m unittest discover -s tests -v
```

Safari/iOS real, instalação na Tela de Início e retorno após suspensão pelo
sistema ainda exigem validação em aparelho. Nenhuma integração em main ou deploy
é feita como parte desta entrega.
