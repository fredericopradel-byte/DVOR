# Importador de cartas — Etapa 4: pendências contextuais

Base analisada: main `747d76c5e7aa72db0d126473d6ac0a7661348cbe`, árvore
`4135f959404864b3078e2e2c4034a5bf908c45f6`, correspondente à reconstrução por perfil
incorporada na PR #27. Branch: `feat/chart-import-stage4`.

## Fluxo entregue

A aba **Resolver pendências** integra o assistente existente em Procedimentos e NDB.
Também se pode tocar numa pendência na lista de dados. As abas permanecem visíveis
na rolagem da área de resultados. Não há nova página nem editor paralelo.

As dúvidas são agrupadas por elemento/categoria e ordenadas por dependência:
coordenadas e referência de cursos, associação/geometria, altitude, limite visual,
conferência de origem/edição e limitações de cobertura. O usuário vê a mensagem,
o recorte correspondente da página e uma prévia do mesmo renderizador nativo,
com destaque e enquadramento do elemento. Sem evidência localizada, a interface
informa que está mostrando a carta inteira; sem coordenada não inventa destaque.
Recortes são exclusivamente visuais, não uma fonte de georreferenciamento.

Há respostas contextuais para:

- Coordenada ausente/ambígua ou conflitante: opção de fonte conhecida ou coordenada
  WGS84 com origem informada; preservação integral dos valores anteriores. Selecionar uma
  fonte não confirma automaticamente sua edição em relação à carta.
- Associação de pernas: escolha de extremidades candidatas ou correção explícita
  de início, fim, curso, referência e distância publicados.
- Referência dos cursos: magnética com VAR assinada ou verdadeira, por confirmação
  explícita da publicação; não há aplicação indiscriminada de WMM.
- Altitudes publicadas: exatamente, mínima, máxima ou janela, com validação de valores.
- Edição ou posição derivada: aceitação da posição e origem **para o rascunho**,
  sem declaração de vigência ou promoção da coordenada a oficial.
- Trecho visual: extensão confirmada a partir do fim da perna, com opções extraídas
  dos números do eixo do perfil quando disponíveis ou entrada do dado indispensável.

A cada resposta, a aplicação recalcula as associações e a geometria, reconstrói
posições derivadas dependentes, revalida as pernas e atualiza a prévia. Uma definição
inconsistente continua crítica e fica fora da conversão nativa; não se desloca um
fixo para encaixá-la. As questões relacionadas que ficaram determinadas deixam de
ser apresentadas, sem dispensar limitações independentes.

## SBGM e limite visual

Na carta SBGM RNP Y RWY 35 de 14 MAY 26, o usuário pode conferir a altitude de ANSAG,
a origem da cabeceira derivada e o limite visual. A opção **Visual nos últimos 3 NM**
provém do número explícito 3,0 no eixo TO THR; ela **exige escolha humana** e não é
aplicada automaticamente por interpretar o pontilhado como distância.

Ao confirmar essa opção, a ligação ANSAG–RWY35 é dividida em duas pernas nativas,
com ponto intermediário geodésico e rastreabilidade da decisão. O segmento visual
recebe rótulo VISUAL e traço descontínuo. O anterior permanece **sem classificação
automática**. Coordenadas de ANSAG e RWY35 são preservadas. Ainda não há seleção de
variante operacional LNAV/LNAV-VNAV ou aplicação do resultado à missão.

## Histórico e integridade

O modelo guarda `reviewWork.version=1`, vinculado ao hash do original, página e
módulo. Contém uma cópia imutável da interpretação inicial, respostas com data e
origem, estado atual e resultados de aplicação. Não duplica PDFs a cada resposta.
O histórico admite até 1000 decisões por rascunho e mantém ramificações: desfazer
uma resposta e substituí-la não apaga a resposta anterior.

**Desfazer resposta**, **Refazer resposta**, **Rever resposta** e **Restaurar até aqui**
reproduzem o estado a partir da interpretação inicial. Uma aceitação de coordenada
ou limite visual perde a aplicação se a coordenada, origem ou geometria de que
depende mudou; aparece nova pendência de conferência. Não se reutiliza uma aceitação
antiga silenciosamente depois de corrigir uma âncora.

As respostas e o modelo atualizado são salvos juntos no rascunho IndexedDB, separados
por módulo. Permanecem no arquivo `.ivchart` versão 2 e reabrem offline. Versões
anteriores sem histórico continuam legíveis e podem iniciar o fluxo. Históricos com
hash, módulo, página ou encadeamento incompatíveis são recusados. Restauração portátil
continua não validada e mantém o aviso de fontes não verificadas.

Se a gravação falhar, o modelo/respondido permanece em memória e pode ser exportado;
a interface avisa para salvar/exportar antes de fechar. Não se apagam importações
para liberar espaço. A atualização/reextração de um rascunho com respostas não apaga
nem reaplica o histórico a uma interpretação diferente. Para uma nova interpretação,
importar novamente cria outro rascunho; o anterior permanece salvo. A troca de página
com respostas também é bloqueada com explicação para preservar o trabalho.

Missões, bibliotecas, documentos manuais, cadastros e bases oficiais não são alterados.
Altitudes publicadas permanecem distintas das planejadas, de inspeção e clearance.
O estado continua `review.validated=false`; a Etapa 5 fará a conferência final única
e a aplicação à missão. Não há botão de aprovar o conjunto nesta entrega.

## Limites conhecidos

- Não há resolução genérica para fingir que uma estrutura não representada foi
  reconstruída. Esperas/hipódromos, certos arcos DME, OCR, cobertura integral e
  outros casos ainda não suportados continuam críticos, com explicação.
- A interface não oferece um botão para dispensar qualquer aviso. Algumas pendências
  permanecem informativas/bloqueantes até ampliar o reconhecimento/conversor.
- A escolha operacional de uma sequência/transição completa ainda fica para a
  integração com a missão. Múltiplos ramos permanecem desenhados e a pendência de
  sequenciamento não é dispensada por uma confirmação genérica.
- A revisão não determina vigência nem certifica correspondência histórica da base.
- O recorte usa evidências textuais disponíveis. Pode abranger regiões distantes da
  mesma página quando uma pendência reúne evidências do plano e do perfil.
- Não há rebase automático das respostas em uma extração/base diferente. O snapshot
  é preservado; uma nova importação inicia outro histórico.
- Backup geral ainda não inclui importações; mantém-se exportação própria.
- O processamento é local. Não há serviço externo, OCR, envio de cartas ou novas
  dependências estruturais. O service worker principal inclui os dois módulos novos
  no APP_SHELL e usa o cache v116.
- Safari/PWA em iPhone e iPad físicos ainda exige validação de toque, foco, suspensão,
  rotação da tela, recortes e persistência sob pressão de armazenamento.

## Arquivos e testes

- `review.mjs`: tipos de resposta, agrupamento, validação, replay e histórico.
- `review-ui.mjs`: seleção contextual, recorte, destaque, formulários e histórico.
- `reconstruct.mjs`: associação/validação reutilizada, sem duplicar fórmulas geodésicas.
- `profile.mjs`: evidências numéricas do eixo e respeito à associação confirmada.
- `native.mjs`, `inspecao/desenhar.html`: metadados e simbologia de segmento visual.
- `ui.mjs`, `ui.css`: integração temporária no assistente e preservação do progresso.
- `extract.mjs`: validação do histórico na restauração portátil.
- `sw.js`, teste de atualização: recursos locais e transição de cache.
- `tests/test_chart_review.py`: fluxo com SBGM e RNP SBNT, negativos e isolamento.

```sh
IV_TEST_CHROMIUM=/usr/bin/chromium python -B -m unittest discover -s tests -v
```

Resultado: **174 casos distintos aprovados após correções**, Chromium 154.0.8037.57.

- A suíte geral executou **173 casos** em 969,623 segundos: 171 passaram e dois
  falharam pela mesma regressão no novo painel, que acessava extremidades inexistentes
  de uma perna sem candidatos (carta sem AIXM). Não houve mistura de dados entre módulos.
- Corrigida a seleção contextual para esse caso, os testes de isolamento e de falha de
  armazenamento/exportação foram reexecutados e passaram, respectivamente em
  20,366 e 15,998 segundos. Não se declara uma execução única integral sem falhas.
- Os **15 testes específicos novos** passaram em 103,608 segundos, incluindo o caso
  de edição da fonte acrescentado após o início da suíte geral. Somado aos casos
  corrigidos, o conjunto atual tem 174 testes distintos aprovados.
- Reexecutados também a retomada/undo/restauração sem AIXM em modo avião (25,657 s)
  e a navegação compacta nos quatro viewports (8,016 s), ambos aprovados.
- Sintaxe de todos os módulos conferida com `node --check`, recursos no APP_SHELL
  verificados e `git diff --cached --check` sem erros.

Os testes específicos cobrem ambiguidades, correções, recálculo, restrições, conflitos, divisão visual,
histórico/ramificações, invalidação de aceitações dependentes, recorte/destaque,
restauração offline, isolamento, quota, integridade, preservação e quatro viewports.
Os testes usam somente dados e contextos temporários.
