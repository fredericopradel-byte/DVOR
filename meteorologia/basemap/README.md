# Fundo meteorológico local

Base de países e costas Natural Earth 1:50m, versão 4.1.0, distribuída em
world-atlas 2.0.2. Dados de domínio público:
https://www.naturalearthdata.com/about/terms-of-use/

Origem: https://unpkg.com/world-atlas@2.0.2/countries-50m.json
Documentação: https://github.com/topojson/world-atlas/tree/v2.0.2
A licença ISC da distribuição está em LICENSE-world-atlas. Leaflet 1.9.4,
já usado no aplicativo, foi incluído localmente com licença BSD-2-Clause
em ../vendor/leaflet/LICENSE. Não há dependência de CDN em tempo de execução.

O arquivo GeoJSON contém 241 países/territórios e suas costas em longitude,
latitude WGS84 (RFC 7946). Leaflet projeta para EPSG:3857, alinhando a base
às coordenadas dos aeródromos e tiles das camadas meteorológicas existentes.
Não contém ruas, relevo, rios ou limites estaduais. É uma base geral de
contexto meteorológico, não uma carta aeronáutica ou mapa de navegação.
Zoom maior amplia a mesma geometria 1:50m, sem acrescentar precisão.

Conversão: decodificar deltas/transformação TopoJSON, inverter arcs negativos,
unir rings, arredondar a cinco casas e cortar no antimeridiano para evitar
segmentos que cruzem o mundo no Leaflet. Rings que circundam os polos
fecham no polo geográfico para projeção plana, sem estimar costas.
source.json registra procedência, SHA-256 de entrada/saída e tamanho.
Para reproduzir, forneça o arquivo fonte ao comando:

    python tools/build-weather-basemap.py countries-50m.topo.json

O arquivo ocupa 2.090.750 bytes; gzip de referência: 740.688 bytes. O download
real depende da compressão HTTP da hospedagem. O cache offline inclui também
Leaflet, CSS, imagens e licenças. Todos os recursos são locais no APP_SHELL;
a instalação só ativa o novo cache depois de concluída. As missões e as bases
aeronáuticas não são alteradas. Este cache utiliza a quota da mesma origem.

Radar e satélite continuam externos e requerem conexão. METAR/TAF salvos
continuam na chave existente iv-weather-last, com indicação de dados salvos.
A disponibilidade do fundo local não significa produtos meteorológicos atuais.
