# Auditoria dos relatórios PDF — PR 7

Base: `main` em `028b53e` (árvore `a013f0c`, incluindo a PR 6).
Escopo: apresentação dos relatórios, sem alterar fórmulas, unidades, dados de missão,
formatos persistidos ou bibliotecas aeronáuticas.

## Inventário

| Consumidores | Gerador efetivo | Achados e correções |
| --- | --- | --- |
| `prevoo/legacy.html`, `prevoo/hawker.html` | `prevoo/flight-report.js` | Resumo sem paginação de pesos/avisos; rota repetida e sem quebra; valores de métricas abreviados; nomes de aeródromos em linha única; boletins maiores que uma página transbordavam. Blocos agora medidos, valores completos, rota exibida uma vez, títulos espaçados e continuação para textos extensos. |
| `inspecao/ils.html`, `inspecao/papi.html` | `inspecao/report-pdf.js` | Metadados abreviados; cartões estimados por caracteres e limitados a 400 px; observações PAPI sem paginação. Medição real de linhas e fontes, metadados completos, cartões que cabem mantidos inteiros e continuação explícita para os maiores que a página. |
| `inspecao/dvor-vor/index.html` | Gerador incorporado no próprio HTML | Mesmos problemas de metadados e cartões. Correções localizadas no gerador incorporado, preservando a captura do mapa e as cores TX/grupo. |
| `inspecao/radar.html` | Gerador incorporado no próprio HTML | Mesmos problemas; observações não quebravam palavras sem espaços. Mantidos mapas superior/vertical, cores das modalidades e restauração da câmera após exportação. |
| `ils.html`, `papi.html` na raiz, legados | `report-pdf.js` da raiz | Correções equivalentes de texto e paginação. A cópia permanece independente; não foi substituída pela versão de `inspecao/`. |

Não foram encontrados outros geradores de PDF ou fluxos de impressão no código do
aplicativo. Procedimentos/NDB, Meteorologia e Localidades não recebem um novo
exportador nesta etapa. As referências de script e os menus foram conferidos para
distinguir os arquivos incorporados das duas cópias de `report-pdf.js`.

## Evidências do problema anterior

Reprodução com dados fictícios e instrumentação Canvas, carregando os geradores
anteriores sem modificar os arquivos do aplicativo:

- Mesmo no exemplo curto de pré-voo, o título `Verificações` interceptava os glifos
  da linha anterior (`Extra fixo`).
- No exemplo extenso de pré-voo, sete registros de texto ultrapassavam a área útil;
  a rota repetida chegava a mais de 2.200 px em uma folha Canvas de 1.240 px.
- No ILS extenso, a descrição alcançava o rodapé e uma sequência sem espaços era
  desenhada com mais de 32.000 px de largura.
- A revisão visual também identificou títulos sobre o fundo do cartão anterior,
  mesmo sem colisão entre os glifos. Há teste de pixels do fundo antes do título.

## Comportamento resultante

- A medição usa a mesma fonte, tamanho e peso do desenho; há quebra também de
  tokens sem espaços e preservação de quebras explícitas de parágrafo.
- Um cartão comum é deslocado inteiro para a próxima página quando necessário.
  Conteúdo maior que a área útil é continuado sem corte, com identificação.
- Métricas, pesos, limites, avisos, combustível, desempenho, METAR/TAF e resultados
  permanecem com os valores fornecidos pelo modelo existente. A rota redundante
  no subtítulo do resumo foi removida; a rota completa continua no cartão de rota.
- Valores de metadados não são mais abreviados. O cabeçalho compacto de inspeção
  pode abreviar títulos extensos; o nome completo é garantido nos metadados.
- Resultados PAPI usam linhas medidas com seus estados SAT/DEF, valores e cores;
  os cinco indicadores de setor mantêm suas amostras de cor. Observações extensas
  têm continuação junto da identificação da passagem.
- ILS conserva os mapas LOC e GLIDE, sem forçar uma página vazia após o perfil.
- Mantidos os encoders PDF incorporados, A4 e rasterização local. Não há chamada
  a serviço externo, biblioteca nova no aplicativo ou alteração de captura/projeção.

## Validação reproduzível

`tests/test_report_pdf.py` contém oito testes com Chromium e perfis temporários.
Eles geram downloads reais, abrem o resultado em um leitor independente (PyMuPDF),
conferem páginas A4, imagens decodificáveis, margens, colisões de glifos e fundo dos
títulos. Valores são comparados com a entrada entregue ao gerador; a entrada e o
armazenamento são conferidos antes/depois. A exportação real do Radar também
confere a restauração da câmera. Os campos importados são confirmados antes do
snapshot, respeitando a normalização já existente da página.

Cobertura: quatro variantes dos geradores de inspeção, Legacy/Hawker, PAPI atual e
legado, relatório vazio, textos longos, métricas extensas, estados e notas PAPI,
exportações pelos formulários reais e geração offline nas seis rotas operacionais.
Há exemplos visuais locais de Legacy/Hawker com cinco trechos, inspeção, alternativa
e boletins extensos, além de ILS, Radar, DVOR e PAPI sintéticos.

```sh
python -m pip install -r tests/requirements.txt
IV_TEST_CHROMIUM=/usr/bin/chromium python -B -m unittest discover -s tests -v
# Opcional: salvar os PDFs fictícios e a renderização de cada página para revisão.
IV_TEST_CHROMIUM=/usr/bin/chromium IV_TEST_PDF_DIR=work/pdf-review python -B -m unittest discover -s tests -p test_report_pdf.py -v
```

PyMuPDF é uma dependência somente dos testes. Os arquivos de evidência são locais
e não devem ser versionados como relatórios operacionais.

## Offline e limites

O worker central passa ao cache v102; sua estratégia, controle de substituição e
prioridade dos pacotes permanecem intactos. Os recursos operacionais modificados
já estão no APP_SHELL. A cobertura offline das rotas legadas não é ampliada.

Os testes cobrem geração e leitura em Chromium; compartilhamento, visualização,
impressão e download em Safari/iOS real continuam exigindo validação no aparelho.
PDFs permanecem rasterizados, como antes: texto pesquisável/selecionável e novos
formatos de relatório não fazem parte desta PR. Não foram alterados critérios
operacionais, dados faltantes de performance nem cálculos aeronáuticos.
