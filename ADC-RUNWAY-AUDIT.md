# Auditoria de rumos de pista — ADC

Fonte: cartas ADC vigentes disponibilizadas pelo DECEA/AISWEB.

Data de obtenção: 17/09/2026.

## Resultado da importação

- 136 ADC obtidas e identificadas por ICAO, emenda e data de efetivação.
- 153 pistas físicas e 306 cabeceiras extraídas.
- 136 ADC aprovadas na validação de reciprocidade.
- Nenhum rumo publicado divergiu mais de 10 graus do designador da cabeceira.
- 133 localidades tiveram correspondência integral com as cabeceiras já existentes.
- SBME exigiu correção estrutural: inclusão da pista 05/23 e correção da pista 06/24.
- SBMT continha uma pista espúria 11/29 de 25 m, removida por não existir na ADC vigente.
- SBFS e SSGG não existiam na base anterior e foram incorporadas a partir de suas ADC.

## Prioridade aplicada pelo aplicativo

1. BRG MAG publicado na ADC vigente.
2. Rumo verdadeiro obtido de geometria verificada, convertido pelo WMM2025.
3. Rumo magnético nominal derivado do designador da cabeceira.

O WMM2025 nunca deve sobrescrever um BRG MAG publicado. Para cálculo com vento informado em graus verdadeiros, o rumo magnético publicado é convertido internamente para verdadeiro usando a declinação do aeródromo.

## Correções importantes encontradas

- SBAC: 09/27 = 092/272 graus magnéticos.
- SBNT: 16L/34R = 162/342; 16R/34L = 162/342; 12/30 = 120/300 graus magnéticos.
- SBME: 05/23 = 053/233 e 06/24 = 057/237 graus magnéticos.

Os PDFs das ADC foram usados apenas como fonte de extração e conferência; a aplicação embarca somente os dados necessários e os metadados de origem.
