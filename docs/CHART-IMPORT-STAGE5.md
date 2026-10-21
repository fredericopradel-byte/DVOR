# Importador de cartas — Etapa 5: conferência e aplicação ao editor

Branch: `feat/chart-import-stage5`. Base de entrega: main
`2fb602f65f1f966db26a2579eea9f53e8c21c870`, árvore
`df3ec1cf28d794f84c87edacd8031c864dc97d97`, que já contém a Etapa 4 (PR #28).
Não há merge, implantação nem alteração de bases nesta entrega.

## Fluxo

A aba **Conferência final**, no assistente já existente em Procedimentos/NDB, mostra
identificação/revisão da carta, contagem de pontos/pernas, respostas aplicadas,
pendências, restrições verticais e verificações geométricas. Não exige abrir cada
elemento. A data da publicação continua sem comprovar vigência.

É possível escolher uma sequência candidata contínua para o perfil vertical. Isso
não elimina os demais ramos do desenho nem confirma a cobertura integral da carta.
Uma escolha que ficou inválida depois de corrigir a geometria pode ser revista.
As escolhas de destino, sequência e preenchimento são persistidas no rascunho
IndexedDB e podem ser retomadas após recarregamento.

O destino é **Criar nova missão** ou **Aplicar à missão atual**. Na missão atual,
os conflitos de ICAO, local, cabeceira, carta e revisão são apresentados com os
valores atual/publicado e a política selecionada: preencher apenas vazios (padrão)
ou utilizar os valores identificados da carta. Campos sem sugestão, tripulação,
notas, velocidades, critérios e demais dados de inspeção não são sobrescritos.
Não há inferência de mínimos, fases operacionais ou regras de clearance.

A confirmação final é o próprio botão na conferência, sem confirmações individuais
por elemento. Com dados completos e sem pendências críticas, é possível **Confirmar
conjunto e aplicar**. Com pendências críticas, o botão é **Abrir rascunho não validado
no editor**: os elementos ausentes continuam ausentes, os avisos ficam conservados,
e o modelo não é promovido a validado. Sem tipo IAC/SID reconhecido ou sem perna convertível, a aplicação fica
indisponível; o salvamento/exportação da importação continua disponível.

Cartas incompatíveis com inspeção NDB, como RNP ou SID, recebem aviso explícito e
só podem abrir sua geometria como rascunho, sem mudar o módulo, título ou tipo
para simular um NDB. O módulo é sempre o local em que a importação começou.

## Preservação e gravação

Antes de substituir o desenho, é gravada uma cópia de recuperação do planejamento
anterior na biblioteca do mesmo módulo, reutilizando `preservePlanning`. Registros
já salvos não são atualizados pela aplicação. Nova missão recebe identidade própria
e um novo registro; aplicar à atual mantém sua identidade no rascunho aberto.
Atualizar posteriormente uma missão salva continua sendo uma ação explícita do
editor existente.

A conferência e o histórico são salvos em IndexedDB antes de tocar no planejamento.
Falha nessa gravação impede a aplicação e permite exportar o rascunho em memória.
Na etapa localStorage, o editor em memória só muda depois de preservar o anterior
e gravar o candidato. Se a gravação do novo rascunho falhar, o novo registro de
missão é revertido, mantendo a recuperação do planejamento anterior. Uma falha
adicional de rollback é informada, sem apagar dados para liberar espaço.

Um snapshot da missão e do conteúdo persistido é comparado no momento da aplicação.
Mudanças em outra aba exigem nova conferência, sem sobrescrever o rascunho daquela
aba. Fechar ou trocar a importação durante o preparo assíncrono cancela a aplicação.
Selecionar arquivo, conferir, alterar opções ou cancelar não modifica missões.

## Editor nativo e origem

Não há editor paralelo. Pontos, retas e curvas são inseridos no documento nativo
schema 3 e usam as ferramentas existentes, incluindo seleção, movimentação, medidas,
travas, rotação, exclusão, desfazer/refazer e perfil vertical. A aplicação inteira
constitui uma operação no histórico do editor.

A extensão opcional `chartImport.version=1` conserva:

- ID do rascunho, módulo, hash, página, arquivo e identificação/revisão da carta;
- coordenadas e fontes originais, definições publicadas das pernas e restrições;
- referência dos cursos, base utilizada, mapeamento de elementos e decisões humanas;
- pendências e verificações da conferência, data e hash da aceitação;
- snapshot geométrico nativo normalizado anterior a edições e lista de modificações.

Não há PDF nem texto/vetores completos da extração no localStorage. O original,
extração e IR completos continuam em IndexedDB, com exportação própria `.ivchart`.
A extensão do desenho limita-se a 2 milhões de caracteres; se ultrapassada, a
aplicação falha explicitamente, mantendo a importação, sem truncar a origem.

O editor preserva essa extensão na validação, gravação, JSON, missões e cadastros.
Um aviso compacto acompanha o documento em todas as abas; os detalhes mostram a
revisão, aceitação original, alterações e pendências. O inspetor oferece a origem
do ponto/perna selecionado, incluindo pontos calculados na subdivisão de arcos.

Alterar posição/nome, trajetória, referência geográfica, sequência ou restrições
registra diferença em relação ao snapshot. A aceitação original continua como
histórico, mas a revisão efetiva fica não validada enquanto houver diferenças.
Desfazer até a geometria original restaura a correspondência ao snapshot. Travas
e alterações de visualização não adulteram os dados publicados de origem.
Não são aplicados snaps destrutivos às coordenadas ou definições publicadas.

As altitudes suportadas entram nas restrições nativas, associadas aos pontos.
Altitudes planejadas/inspeção e fases operacionais ficam em branco. Restrições sem
representação fiel são preservadas como origem e geram pendência crítica na
conferência, em vez de desaparecerem ou serem promovidas a um cálculo de clearance.

## Offline e backup

O service worker principal permanece o único do aplicativo, com cache v117 e os
três recursos novos no APP_SHELL. Os modelos aplicados usam a persistência normal
do editor e abrem/editam offline, sem serviço de reconhecimento ou base AIXM ativa.
Os formatos anteriores de desenho e rascunhos de importação continuam legíveis.

O backup geral já inclui os rascunhos e bibliotecas de Procedimentos e NDB; portanto,
a geometria aplicada e a extensão de origem acompanham essas categorias, sem nova
migração ou chave. PDFs e importações IndexedDB não entram nesse backup: é preciso
exportar também `.ivchart` para guardar a publicação original em outro aparelho.
O desenho restaurado é utilizável sem esse PDF; o aviso explica onde o original
normalmente fica e a necessidade da exportação específica. Nenhuma nova dependência,
serviço externo, transmissão de arquivos ou chave de API foi introduzida.

## Limitações

Esta etapa conclui a integração da geometria disponível com missão/editor. Não
amplia o reconhecimento de símbolos, esperas, arcos, aproximação perdida ou OCR.
As cartas reais atuais ainda carregam `coverage-review` e outras pendências críticas;
a conferência não possui uma dispensa genérica para obter aprovação artificial.
Consequentemente, elas entram como rascunhos parciais. O caminho de aprovação sem
pendências é testado com geometria sintética conhecida, sem declarar reconhecimento
integral de IAC/SID. A automação avançada permanece na Etapa 6, sujeita à aprovação
específica antes de integrar qualquer processamento externo.

A escolha de uma sequência não classifica fases operacionais nem resolve por si
só a aproximação perdida. Gradientes ou restrições verticais fora da representação
nativa de ponto são preservados e bloqueiam aprovação.

O arquivo `.ivchart` continua sendo um rascunho de interpretação, reaberto sem
aprovação automática. As edições feitas depois da aplicação ficam no JSON/backup
do editor, não são propagadas ao IR de importação nem ao arquivo original.

## Arquivos

- `inspecao/chart-import/finalize.mjs`: avaliação final, sugestões, fingerprint e envelope.
- `inspecao/chart-import/final-ui.mjs`: conferência, escolhas e confirmação única.
- `inspecao/chart-provenance.js`: preservação da origem e comparação após edições.
- `inspecao/chart-import/ui.mjs`, `ui.css`: aba final e aviso do documento.
- `inspecao/desenhar.html`: ponte de aplicação, recuperação e persistência da extensão.
- `sw.js`: APP_SHELL e cache; teste correspondente de atualização.
- `tests/test_chart_application.py`: casos de integração e preservação.

## Validação

Comandos principais:

```sh
IV_TEST_CHROMIUM=/usr/bin/chromium python -B -m unittest discover -s tests -v
IV_TEST_CHROMIUM=/usr/bin/chromium python -B -m unittest discover -s tests -p test_chart_application.py -v
```

Chromium 154.0.8037.57, servidores loopback sob `/DVOR/` e perfis temporários.

- Os **20 testes de aplicação** passaram em 148,303 s. Incluem carta SBGM real,
  rascunho/aplicação, missão nova/atual, conflitos, cancelamento, concorrência,
  quota localStorage/IndexedDB, reabertura offline, precisão, perfil vertical,
  JSON, backup/restauração, retomada das escolhas e quatro viewports.
- Os três testes finais de tipo ausente, vertical não representável, rascunho real
  e confirmação única sintética passaram em 31,657 s (dois repetem casos do grupo
  acima; o caso de bloqueio de tipo/vertical é adicional).
- Rotação, cadeados e desfazer sobre o modelo importado passaram em 7,118 s:
  **22 casos novos distintos aprovados** no conjunto dessas execuções.
- Após os ajustes finais de rastreabilidade das pernas e validação de origem,
  rotação/undo, edição nativa e backup foram reexecutados: 3 casos passaram em
  22,250 s. Os detalhes conservam o estado aberto durante redesenhos e permitem
  consultar também as restrições publicadas, inclusive as não convertidas.
  Após essa consulta, rotação, edição vertical e backup passaram novamente
  em 19,128 s (3 casos).
- O caminho de aceitação usa geometria sintética conhecida (5 NM, curso verdadeiro
  090°), com confirmação única pela interface. O teste também verifica que uma
  edição nativa invalida a revisão efetiva, preserva a aceitação original e pode
  ser desfeita. Isso não representa reconhecimento integral de uma carta real.
- Conferidas capturas em 390×844 e 1024×768, incluindo o desenho aplicado no iPhone;
  sem erros de página. Os testes de responsividade incluem também 844×390 e 768×1024.
- Sintaxe de todos os módulos de importação, origem e script inline do editor,
  existência dos caminhos APP_SHELL e `git diff --check`: sem erros.

A suíte geral executou **188 casos em 1149,712 s**: 186 passaram, houve
uma falha no novo seletor de preenchimento e um timeout de 10 s aguardando o
controle do service worker no preparo de um teste novo. A persistência dos seletores
foi corrigida e os dois casos passaram nas reexecuções, inclusive no grupo de
20 casos aprovado acima. Os **174 casos anteriores** passaram na execução geral;
o conjunto entregue tem **196 casos distintos aprovados nas execuções combinadas**
(174 anteriores + 22 novos). Não se declara uma única execução integral sem falhas.

A conferência final adicional de origem, edição vertical e backup passou em 19,128 s.
Os logs e capturas ficam em `work/` como artefatos locais, sem PDFs adicionais no
repositório.

## Situação da entrega

Implementação preparada em branch separada, com envio e abertura de PR em rascunho
autorizados pelo responsável. Sem merge nem implantação.

Safari/PWA em iPhone e iPad físicos exige validação manual: instalar/atualizar,
importar e abrir um rascunho, editar e desfazer, suspender/reabrir em modo avião,
exportar JSON/ivchart, restaurar backup, testar rotação/safe areas e pressão de quota.
