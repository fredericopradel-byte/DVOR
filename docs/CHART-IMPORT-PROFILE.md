# Reconstrução por perfil e plano — cabeceira sem coordenada na base

Base analisada: main `6c20519ce4beab4cc62eaf1cdd08a7394a722f36`, com árvore
`254fc6f594b88cb19b7724079a1ba8f649c6b98f` idêntica à Etapa 3 testada.
Branch: `feat/chart-profile-reconstruction`. Sem aplicação à missão ou mudança de clearance.

## Resultado na carta fornecida

A IAC **SBGM RNP Y RWY 35**, AIRAC AMDT 2605A1, 14 MAY 26, não possui coordenada
RWY35 no índice local. O plano publica ANSAG–RWY35, 360° magnéticos, 5,0 NM.
O perfil publica o eixo **TO THR 35 (NM)**, com RWY35 em 0,0, ANSAG em 5,0 e
GM001 em 10,0. A VAR publicada é 13° W, referência 2026.

A reconstrução usa a coordenada AIXM de ANSAG e a solução geodésica direta WGS84,
curso verdadeiro 347°, distância 5,0 NM. Resultado preservado sem snap:

- Latitude: **−10.794088451275934°**.
- Longitude: **−65.28210268920293°**.

São valores **derivados de publicação arredondada**, não coordenadas oficiais de
cabeceira. O modelo continua não validado, com pendência crítica para conferência.
GM001 fornece uma verificação adicional da mesma final: a solução a partir de
10,0 NM fica a aproximadamente **0,05039 NM** da primeira, coerente com os
intervalos de arredondamento explicitados. As duas soluções compartilham evidência
de curso/VAR; não constituem certificação independente nem medição de precisão.

O ponto fica em `coordinateState=derived-review`, com origem `chart-derived`;
a evidência conserva coordenada e fonte da âncora, versão, curso, referência,
VAR, distância publicada, IDs textuais, cálculos e verificações adicionais.
A prévia passa de quatro pontos associados/três pernas para **cinco pontos/quatro
pernas**, incluindo ANSAG–RWY35. A associação da anotação GM001–ANSAG também é
corrigida pelo perfil, eliminando aquela ambiguidade quando as evidências são únicas.

## Condições para o cálculo

O interpretador local exige PDF digital DECEA IAC, eixo textual explícito
`TO THR xx (NM)` correspondente à pista identificada, referência zero associada
inequivocamente a RWY/THR, fixo com coordenada conhecida e uma anotação explícita de
curso/distância no plano compatível com a distância à cabeceira. Posições de textos
servem somente para associar colunas/anotações. Não medem NM nem latitude/longitude.

A distância deste caso é **ao longo do perfil até a cabeceira**, não DME inclinado.
Não há conversão automática de distância DME, nem estimativa pela posição do ARP e
metade do comprimento de pista. Metros, DME, eixos sem identificação, associação
ambígua, referência magnética ausente e extração truncada não autorizam o cálculo.

A âncora mais próxima reduz a propagação do arredondamento. Referências adicionais
só são confrontadas quando há uma definição publicada de ligação colinear; curso,
distância e coordenadas precisam ser coerentes. Conflitos bloqueiam a derivação.
A posição existente nunca é deslocada para encaixar a publicação. Uma cabeceira
local única pode ser associada quando o próprio perfil comprova a correspondência
com a referência zero; isso mantém uma pendência para edição/correspondência.

O limite registrado de arredondamento combina intervalos dos valores impressos
de distância, curso e VAR. Usa `erroDistância + 2d·sin(erroAngular/2)` como envelope
geométrico dos dados arredondados. **Não inclui a incerteza da coordenada da âncora,
não é precisão oficial e não é tolerância operacional.** A origem permanece
consultável em Coordenadas, restrições e verificações, sem arredondar os dados salvos.

## Trecho visual

A indicação textual **PROSSIGA VMC / PROCEED VMC** é conservada e associada à final.
O modelo/nativo recebe `flightRules=visual-transition-review` e referência à evidência;
a prévia mostra **VMC\*** e explicação. A ligação inteira não é classificada como
instrumental nem como visual. O limite exato do trecho visual continua uma pendência
crítica: esta entrega não interpreta automaticamente toda a simbologia pontilhada,
nem inventa uma divisão operacional em 3,0 NM somente pela posição gráfica.
Isso não altera regras de inspeção, altitudes planejadas, altitude de inspeção ou clearance.

## Arquivos, persistência e offline

- Novo `inspecao/chart-import/profile.mjs`: leitura do eixo e reconstrução verificável.
- `reconstruct.mjs`: integração após associação inicial e antes da validação final.
- `native.mjs` e `inspecao/desenhar.html`: conservação da referência visual e rótulo VMC*.
- `ui.mjs`: aviso de coordenada derivada, origem e limite de arredondamento.
- `sw.js`: recurso no APP_SHELL, cache v115; teste de atualização ajustado.
- `tests/test_chart_profile.py`, manifesto e PDF SBGM: testes rastreáveis.

Os campos são aditivos no modelo intermediário e no arquivo `.ivchart` versão 2;
a leitura da versão 1 e dos modelos anteriores continua disponível. Reabertura
regenera a prévia do snapshot salvo. **Rascunhos antigos não são recalculados
silenciosamente:** para usar esta reconstrução, retomar e tocar em Atualizar prévia,
ou importar a carta novamente. Bases e missões não são modificadas. Sem transmissão
externa, novas dependências, migrações ou armazenamento de PDFs em localStorage.

## Validação

Testes novos cobrem a carta real e coordenada esperada, referências do perfil,
coerência de GM001, precisão sem snap, independência da escala da página, ausência
de definições, ambiguidade, conflito, preservação de coordenada existente, VMC,
retomada offline, arquivo portátil e independência NDB/Procedimentos. Casos negativos
alteram somente cópias de dados em memória, em perfis temporários.

Comando:

```sh
IV_TEST_CHROMIUM=/usr/bin/chromium python -B -m unittest discover -s tests
```

Resultado: **159 casos distintos aprovados**, sem falhas de teste observadas:

- Execução geral interrompida por desconexão do ambiente após **135 aprovações**;
  os **23 casos restantes** foram enumerados e executados separadamente, todos
  aprovados em 118,375 segundos. O registro inicial preserva 135 resultados de sucesso,
  mas não tem encerramento normal; não é apresentado como execução única concluída.
- O teste novo de prévia responsiva de SBGM foi acrescentado após o início da execução
  geral e passou separadamente nos quatro viewports de iPhone/iPad.
- Os oito testes específicos do cálculo, na versão final, também foram reexecutados
  e passaram em 58,799 segundos, incluindo conflitos de rumo e distância e a preferência
  por cabeceira existente. Junto ao responsivo, são nove testes específicos novos.
- Sintaxe dos módulos com `node --check`, hashes das onze cartas, recurso no APP_SHELL
  e `git diff --cached --check` conferidos sem erros.

A regressão inclui as outras dez cartas e as ferramentas do editor, perfil vertical
e atualização PWA. Chromium 154.0.8037.57, em contextos temporários.
Validação manual ainda necessária em Safari/PWA de iPhone e iPad: atualizar o app,
retomar um rascunho anterior, Atualizar prévia, conferir VMC* e origens, suspender e
reabrir em modo avião. O reconhecimento completo de hipódromos, arcos e aproximação
perdida, resolução contextual de pendências e aplicação à missão continuam fora
desta alteração.
