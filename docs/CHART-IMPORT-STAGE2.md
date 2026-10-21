# Importador de cartas — Etapa 2

Base de implementação: `main` em `304f3e2e64a34731581256a4bbba3605b036faf4`.
Branch: `feat/chart-import-stage2`. Sem alteração de regras de inspeção.

## Comportamento entregue

Na aba Desenhar de NDB ou Procedimentos, **Importar carta** abre um assistente
temporário. Aceita PDF/PNG/JPEG, verifica a assinatura e a extensão, limita arquivos
a 25 MB, imagens a 24 MP e PDFs a 100 páginas. PDFs protegidos ou ilegíveis são
recusados. Em documentos com várias páginas, o usuário escolhe a página antes de
extrair. O processamento e a persistência são locais; não há serviço externo,
chaves de API ou envio automático de dados.

PDF.js local extrai textos posicionados, transformações e operadores gráficos.
A prévia renderiza somente a página selecionada. Dados espaciais da página nunca
são considerados coordenadas geográficas. Limites de 25.000 itens textuais e
100.000 operadores produzem aviso explícito de extração incompleta.

A identificação inicial usa evidências textuais da página: IAC/SID, ICAO,
procedimento, cabeceira, aeródromo, AIRAC e data publicada quando disponíveis.
Cada campo mantém IDs de evidência. Texto original e números extraídos permanecem
no resultado sem snap ou arredondamento do editor. Não se usa o nome do arquivo
para fingir identificação.

Navegação do título, requisitos GNSS/DME e indícios textuais de arco/espera/radial
são estruturas diferentes. Por exemplo, ILS Y com requisito GNSS continua ILS;
não se transforma em aproximação RNP. Identificadores e frequências de auxílios
são candidatos textuais, ainda sem associação AIXM. Leituras conflitantes geram
pendências, não uma escolha silenciosa.

## Isolamento e persistência

`ivplanner-chart-import-v1` é uma base IndexedDB independente, store `sessions`.
O registro inclui `Blob` original, hash SHA-256, contexto de módulo, página,
extração, identificação e estado de rascunho. Arquivo e checkpoint são gravados
na mesma transação. O progresso inicial e a seleção de página são guardados antes da extração pesada.

O assistente não lê ou escreve documentos de missão. Chaves existentes,
modelos manuais, bibliotecas e bases aeronáuticas permanecem intactos. Os acessos
de leitura verificam o módulo de destino; a lista mostra somente aquele módulo.

Falhas de armazenamento são visíveis e permitem exportação do rascunho em memória.
Não se apagam rascunhos para recuperar espaço. A exclusão/gestão de quotas poderá
ser adicionada com confirmação explícita. No iOS, IndexedDB continua sujeito a
quotas e políticas de remoção do sistema; o arquivo exportado é a cópia portátil.

O arquivo `.ivchart` inclui original em base64, hash, módulo e página. Na restauração,
o hash é conferido e o conteúdo é novamente extraído, sem confiar em reconhecimento
forjado. Arquivos de outro módulo são recusados. A restauração cria um novo rascunho,
preservando os anteriores.

**O backup geral atual não inclui a nova base IndexedDB.** A interface informa isso
e oferece exportação/restauração própria. A integração com backup geral permanece
na Etapa 5; nenhum PDF grande é introduzido no backup JSON existente/localStorage.

## Offline

O service worker principal inclui os módulos do importador e ambos os bundles
PDF.js no APP_SHELL. Não há segundo service worker. Depois da instalação completa,
é possível abrir o assistente, retomar rascunhos e extrair PDFs locais em modo avião.
O editor operacional não depende de abrir o assistente ou instalar AIXM.

## Limites desta etapa

- Não há OCR ou interpretação visual automática. A carta NDB rasterizada fornecida
  demonstra essa limitação e produz uma pendência crítica.
- Não há reconhecimento de símbolos/topologia, classificação visual de hipódromo
  ou reconstrução do “pé de galinha”. Indícios textuais não são trajetórias.
- Não há associação de fixos, cálculo geodésico, geração de desenho ou integração
  de restrições no perfil vertical. Esses itens pertencem às Etapas 3–5.
- Não existe botão de aplicar à missão ou validar. Todos os registros têm
  `review.validated=false` e aviso de reconstrução pendente.
- Não há determinação automática de vigência, nem declaração de cobertura completa.
- Revisões históricas das amostras não são promovidas a publicação vigente.
- Não foi incorporada nova base oficial nem alterada a precedência ADC/WMM.
- Validação Safari/PWA em aparelhos reais segue necessária.

## Arquivos e testes

Integração localizada em `inspecao/desenhar.html` e `sw.js`; novos módulos em
`inspecao/chart-import/`; testes em `tests/test_chart_import.py`, com oito PDFs
históricos e manifesto rastreável em `tests/fixtures/charts/`.

Comando da suíte específica:

```sh
IV_TEST_CHROMIUM=/usr/bin/chromium python -B -m unittest discover -s tests -p test_chart_import.py -v
```

O executável pode ser omitido onde o Chromium do Playwright estiver instalado.
Os testes usam servidor loopback e contextos temporários, sem dados de usuário.
Cobrem PDFs reais, metadados, vetores, imagens, entradas inválidas/protegidas,
seleção de página, retomada, exportação/integridade, isolamento, preservação da
missão, offline, falhas de armazenamento, ambiguidades, precisão estrutural e
viewports de iPhone/iPad. A suíte específica contém 15 testes. Inclui cancelamento durante leitura, retomada antes da primeira extração, JPEG com metadados longos e preservação de missões anteriores com geometria manual. Não são testes de reconhecimento geométrico completo.

Para a Etapa 3, revisar modelos esperados independentes por carta e uma matriz de
capacidades antes de converter qualquer estrutura para retas/arcos nativos.

## Resultados desta entrega

- Chromium 154.0.8037.57 em contextos isolados.
- Suíte específica: **15 testes aprovados**, incluindo as oito cartas reais.
- Suíte geral: 128 testes executados; 127 passaram na primeira execução. O único
  erro era a expectativa fixa do cache `v112` em um teste de atualização, enquanto
  a nova instalação corretamente ativou `v113`.
- Expectativa corrigida em `tests/test_offline_map_visual.py`; os dois testes de
  atualização completa/interrompida foram reexecutados e passaram, incluindo
  preservação das missões, IndexedDB de pacotes e cache de pacotes.
- Casos acrescentados e ajustes finais do importador foram verificados também
  em execuções específicas: retomada da página antes da extração, aviso de
  rascunho não validado, alternância visual e JPEG com metadados longos.
- Sintaxe dos quatro módulos JavaScript conferida com `node --check`; recursos
  do APP_SHELL conferidos e diff próprio sem erros de whitespace. Os bundles
  PDF.js mantêm os 12 espaços finais do upstream para preservar os bytes originais.
- Conferência visual em viewports de iPhone/iPad executada. Safari/iOS em aparelho
  físico ainda não validado.

A entrega é destinada à revisão em branch separada e PR em rascunho. A autorização
para enviar a branch não inclui integração à main nem implantação do aplicativo.
