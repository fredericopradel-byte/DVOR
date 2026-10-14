# AGENTS.md — Manual de desenvolvimento do IV-PLANNER

Este manual aplica-se a todo o repositório DVOR. Define as regras permanentes para desenvolvimento, manutenção e validação do IV-PLANNER. Instruções explícitas do responsável pelo projeto delimitam o escopo de cada tarefa e as autorizações concedidas.

## 1. Objetivo do projeto

O IV-PLANNER é um PWA de apoio ao planejamento de voo e à inspeção em voo, utilizado principalmente em iPhone e iPad, frequentemente em ambiente operacional.

Suas principais áreas são:

- Pré-voo Legacy e Hawker;
- Inspeção PAPI;
- Inspeção DVOR/VOR;
- Inspeção ILS;
- Inspeção Radar;
- Procedimentos e NDB;
- Meteorologia;
- Localidades;
- Configurações.

O aplicativo deve funcionar prioritariamente offline. A disponibilidade de internet nunca deve ser condição para acessar as funções operacionais principais após a instalação dos recursos necessários.

## 2. Preservação e controle de alterações

- O repositório atual é a única fonte de verdade para a implementação.
- Não utilizar versões antigas nem reconstruir arquivos a partir de implementações anteriores.
- Priorizar alterações cirúrgicas e modulares. Não reescrever páginas inteiras quando uma correção localizada for suficiente.
- Não remover funcionalidades existentes sem autorização explícita.
- Não realizar refatorações extensas sem justificativa técnica e aprovação.
- Preservar a compatibilidade com os dados e configurações existentes.
- Não modificar arquivos fora do escopo sem necessidade técnica demonstrada.
- Trabalhar preferencialmente em branches separadas, permitindo revisão das diferenças antes da incorporação.
- Não fazer commit, merge ou publicação quando a tarefa os proibir. Não integrar na branch principal nem publicar no GitHub Pages sem autorização explícita.

## 3. Funcionamento offline

O funcionamento offline é um requisito crítico.

- Preservar o service worker principal `sw.js`, situado na raiz do aplicativo. Não criar novos service workers sem autorização.
- Respeitar o mecanismo de transição em `inspecao/dvor-vor/sw.js`: ele aposenta instalações antigas do DVOR, remove seus caches antigos e desregistra o worker antigo, preservando o cache principal.
- Manter páginas e recursos operacionais essenciais disponíveis após instalação e atualização do PWA.
- Não introduzir dependências externas obrigatórias para as funções principais.
- Consultas meteorológicas, mapas externos e atualizações de bases podem depender de internet. Sua indisponibilidade não deve impedir o acesso às páginas e às funções locais.
- Ao alterar recursos essenciais, conferir o `APP_SHELL`, os caminhos relativos, a versão do cache e as estratégias de atualização em `sw.js`.
- Preservar a resolução das rotas por diretório e por `index.html`, inclusive recursos versionados por parâmetros de consulta.
- Respeitar as estratégias existentes: rede primeiro para navegação e catálogo; cache prioritário com atualização pela rede para outros recursos locais; prioridade dos pacotes instalados para seus arquivos gerenciados.
- Não limpar indiscriminadamente Cache Storage, localStorage ou IndexedDB.
- Não excluir caches válidos nem dados do usuário durante atualizações. A remoção de caches antigos deve seguir o mecanismo controlado existente, após disponibilizar a versão substituta.
- Preservar a versão ativa dos pacotes enquanto uma atualização estiver incompleta, pausada ou com erro.

## 4. Persistência de dados

- Preservar missões, planejamentos, rascunhos, configurações, preferências, bases instaladas e cadastros manuais.
- Não renomear chaves de armazenamento sem migração compatível.
- Não alterar schemas persistidos sem considerar dados de versões anteriores, leitura, validação e migração.
- Não substituir dados incompatíveis ou ilegíveis por valores vazios de forma silenciosa.
- Preservar os mecanismos existentes de backup e restauração, validação, combinação de registros, tratamento de conflitos e recuperação em caso de falha.
- Verificar a compatibilidade de novas modalidades e dados com o backup geral. Não presumir que novas chaves são incluídas automaticamente.
- Nunca executar testes destrutivos sobre dados reais do usuário. Utilizar perfis de navegador temporários ou armazenamento isolado.

### Organização atual do armazenamento

- **localStorage:** planejamentos, defaults, rascunhos, bibliotecas de missões, cadastros manuais, preferências, memória de navegação e última consulta meteorológica.
- **IndexedDB:** estado e metadados dos pacotes na base `ivplanner-package-manager-v1`, store `packages`.
- **Cache Storage:** recursos do aplicativo e arquivos de pacotes instalados.
- **Backup geral:** lista explícita de categorias em `configuracoes/backup.js`. Conferir essa lista em tarefas de persistência; as chaves de missão e rascunho Radar não estavam incluídas no diagnóstico inicial.

## 5. Arquitetura

- Preservar a arquitetura HTML/CSS/JavaScript existente, salvo autorização para mudanças estruturais.
- Não introduzir frameworks, sistemas de build ou dependências desnecessárias.
- Respeitar a ordem de carregamento dos scripts e os objetos globais compartilhados.
- Priorizar o reaproveitamento dos componentes existentes.
- Evitar duplicação de lógica quando houver componentes compartilháveis, sem realizar refatorações não solicitadas.
- Identificar qual arquivo é efetivamente utilizado antes de modificar páginas ou scripts duplicados.
- Preservar a navegação global e os mecanismos compartilhados de interface.

### Mapa da implementação

| Caminho | Responsabilidade |
| --- | --- |
| `index.html`, `manifest.webmanifest` | Entrada do aplicativo e configuração do PWA. |
| `global-nav.js`, `global-nav.css` | Navegação compartilhada e memória de contexto. |
| `page-ui.js`, `page-ui.css` | Interface compartilhada, ajuda e acompanhamento de atualizações. |
| `prevoo/` | Planejamento Legacy/Hawker, dados de aeronaves, tabelas de performance e relatórios. |
| `inspecao/` | PAPI, ILS, Radar, DVOR/VOR e editor de Procedimentos/NDB. PAR encaminha para o módulo em desenvolvimento. |
| `localidades/` | Consulta e cadastro de aeródromos, pistas, auxílios e procedimentos. |
| `meteorologia/` | Consulta de METAR/TAF e mapas externos. |
| `configuracoes/` | Preferências, backup/restauração, verificação de bases e gerência de pacotes. |
| `data/aixm/`, `data/aixm-client.js` | Adaptadores AIXM e cliente compartilhado de consultas. |
| `data/package-catalog.json`, `packages/` | Catálogo e pacotes aeronáuticos versionados. |
| `sw.js`, `database-update-prompt.js` | Disponibilidade offline e fluxo de atualização de bases. |
| `wmm2025.js`, `adc-runway-data.js` | Declinação magnética e rumos/correções ADC. |
| `tools/build-aixm-package.py` | Geração de pacotes AIXM a partir do XML oficial; requer Python e `lxml`. |

Grande parte da lógica está dentro dos arquivos HTML. Scripts compartilham objetos globais, incluindo `LEGACY_DATA`, `HAWKER_DATA`, `LEGACY_AFM_PERFORMANCE`, `ADC_RUNWAY_DATA`, `WMM2025`, `IVAixmModules` e `IVAixm`.

Há arquivos PAPI, ILS e `report-pdf.js` tanto na raiz quanto em `inspecao/`. Não presumir equivalência entre essas cópias. Conferir as rotas usadas pelos menus, referências de scripts e caminhos relativos antes de editar.

## 6. Interface e experiência do usuário

- Preservar a identidade visual do IV-PLANNER e os padrões consolidados nas páginas de inspeção.
- Manter a interface adequada para iPhone e iPad, respeitando safe areas, barras flutuantes, navegação e orientação da tela.
- Evitar zoom global indesejado e manter campos e controles adequados para interação por toque.
- Preservar os gestos de mapas: um dedo para arrastar; dois dedos para zoom ou rotação, conforme o módulo.
- Não bloquear os gestos próprios dos mapas ao ajustar o comportamento de zoom da página.
- Utilizar DVOR/VOR como referência visual e de interação quando solicitado para novas modalidades.
- Não alterar cores, ícones, dimensões ou disposição de elementos fora do escopo da tarefa.

## 7. Lógica aeronáutica

As regras operacionais devem seguir as especificações fornecidas pelo responsável pelo projeto e as publicações aplicáveis.

- MANINV-BRASIL é a referência operacional principal para inspeção em voo, complementada pelo MOp IV quando aplicável.
- Não inventar limites, tolerâncias, procedimentos ou critérios de aprovação.
- Quando uma regra operacional estiver indefinida, solicitar esclarecimento antes de implementá-la.
- Preservar unidades aeronáuticas, conversões, referências geográficas e cálculos existentes. Conferir diferenças entre modalidades, incluindo kg/lb, m/ft, NM, kt e graus.
- Distinguir corretamente referências magnéticas e verdadeiras.
- Preservar a precedência das fontes de rumos de pista, conforme a implementação e `ADC-RUNWAY-AUDIT.md`:
  1. Rumo magnético publicado na ADC.
  2. Rumo verdadeiro obtido de geometria verificada, convertido pelo WMM2025.
  3. Rumo magnético nominal derivado do designador da cabeceira.
- O WMM2025 não deve sobrescrever um rumo magnético publicado. Preservar a conversão interna para verdadeiro quando necessária ao cálculo com vento em referência verdadeira.
- Não alterar fórmulas operacionais sem autorização e testes específicos.
- Utilizar dados aeronáuticos vigentes e rastreáveis quando a tarefa exigir atualização de informações.

## 8. Bases de dados aeronáuticas

- Preservar ROTAER, ADC, WMM2025, AIXM e os mecanismos existentes de atualização.
- Não sobrescrever bases incorporadas durante configuração ou testes.
- Não regenerar pacotes aeronáuticos sem solicitação explícita.
- Preservar integridade, versões, tamanhos, hashes, metadados de origem e datas dos pacotes.
- Priorizar fontes oficiais para dados aeronáuticos.
- Não substituir dados publicados por estimativas sem respeitar a precedência definida.
- Manter o aplicativo funcional quando uma base opcional estiver indisponível, informando a limitação correspondente.
- Não confundir integridade estrutural ou data de coleta com vigência oficial.
- Preservar as verificações de tamanho e SHA-256 antes de ativar pacotes e a correspondência entre catálogo, arquivos e destinos gerenciados.

### Bases existentes

- **ROTAER:** `prevoo/legacy-data.js` e pacote versionado em `packages/rotaer/`.
- **ADC:** `adc-runway-data.js`, pacote em `packages/adc/` e auditoria em `ADC-RUNWAY-AUDIT.md`.
- **WMM2025:** `wmm2025.js` e `WMM2025-LICENSE.txt`.
- **AIXM:** índice JSON e arquivo oficial compactado em partes em `packages/aixm/`. O cliente carrega o índice pelo destino gerenciado em `publicacoes-offline/`, servido pelo pacote instalado.
- **Fontes ainda não conectadas:** consultar o catálogo atual; a presença de uma entrada não significa que cartas, AIP/eAIP, obstáculos, suplementos ou NOTAM estejam disponíveis.

## 9. Testes e validação

Antes de apresentar uma alteração como concluída, executar as verificações aplicáveis ao escopo e ao risco:

- Verificar erros de sintaxe e exceções JavaScript.
- Testar a página modificada e seus fluxos principais. Uma página não é funcional apenas porque carregou sem erros JavaScript.
- Verificar regressões nas funcionalidades relacionadas e nos componentes compartilhados.
- Testar persistência, reabertura e compatibilidade com dados anteriores quando houver alteração de dados ou missões. Conferir backup/restauração quando aplicável.
- Verificar o comportamento offline quando houver alteração de recursos, navegação ou service worker, incluindo instalação, atualização e acesso aos recursos essenciais.
- Validar cálculos com exemplos conhecidos e casos-limite quando houver mudanças operacionais.
- Verificar diferentes dimensões de tela quando houver alterações visuais, incluindo iPhone e iPad.
- Distinguir testes automatizados, verificações estáticas e testes que ainda exigem validação real no Safari/iOS.
- Não declarar uma funcionalidade validada se os testes correspondentes não tiverem sido executados. Informar impedimentos e testes pendentes.
- Usar dados fictícios e armazenamento isolado; não modificar dados reais nem bases incorporadas para preparar testes.

O diagnóstico inicial não identificou suíte automatizada, runner de testes ou CI versionada. Há verificações estruturais de bases e validações durante o uso, que não substituem testes funcionais e operacionais. Conferir a infraestrutura disponível no repositório atual antes de escolher comandos de validação.

Para alterações exclusivamente documentais, verificar conteúdo, caminhos mencionados, escopo e diff; testes funcionais são necessários quando houver mudanças no aplicativo.

## 10. Procedimento de desenvolvimento

Para cada tarefa:

1. Inspecionar os arquivos relevantes e compreender a implementação atual.
2. Identificar o escopo exato e os possíveis impactos, incluindo dependências compartilhadas, dados persistidos e disponibilidade offline.
3. Preservar os comportamentos existentes.
4. Implementar somente as alterações necessárias.
5. Executar testes proporcionais ao risco da modificação.
6. Revisar o diff e o estado do repositório para detectar mudanças acidentais e respeitar alterações preexistentes.
7. Apresentar um resumo dos arquivos alterados, das mudanças realizadas e dos testes executados.
8. Informar limitações, riscos e testes pendentes.
9. Aguardar aprovação antes de integrar ou publicar alterações na versão principal.

## 11. Segurança operacional

O IV-PLANNER é uma ferramenta de apoio. Não substitui publicações oficiais, instrumentos certificados ou procedimentos operacionais aplicáveis.

- Priorizar correção, previsibilidade e integridade dos dados sobre alterações estéticas ou otimizações.
- Não ocultar falhas de cálculos ou indisponibilidade de dados.
- Não apresentar dados desatualizados como atuais.
- Não introduzir valores operacionais presumidos sem identificação.
- Em caso de dúvida sobre uma mudança com impacto operacional, solicitar esclarecimento.

## 12. Regras de autonomia

O agente está autorizado a analisar código, executar testes não destrutivos e implementar alterações explicitamente solicitadas, dentro do escopo autorizado.

Solicitar autorização antes de:

- Publicar ou integrar alterações na branch principal;
- Excluir dados ou funcionalidades;
- Realizar migrações destrutivas;
- Modificar a arquitetura global;
- Alterar fórmulas ou critérios operacionais não abrangidos pela tarefa;
- Atualizar ou substituir bases aeronáuticas oficiais;
- Introduzir dependências estruturais.

Uma solicitação explícita que abranja a ação constitui autorização para esse escopo; não ampliá-la para outras ações. Quando faltar autorização, concluir as etapas independentes já autorizadas e apresentar o resultado concreto para revisão antes de executar a ação dependente.
