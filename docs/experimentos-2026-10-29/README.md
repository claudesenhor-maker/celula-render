# Três comparações visuais

Base: produção `358566fd814ec05d12194670aa5c5008ef23196a`. Candidato: branch `experimento-comparacoes-20261029`.

## Mudanças

- **Mecanismo:** câmera `perto` usa os limites reais da geometria alvo, em vez do pivô e de uma redução fixa da distância do objeto inteiro. Casca cortada mostra faces internas; materiais restauram o lado original fora da seção. Rótulos usam medição/quebra e preservam nomes longos.
- **Pixel:** gesto de consumo para café, pizza e sorvete com braço, mão e objeto vinculados. Repouso, aproximação à boca e retorno dependem só do tempo da cena. Objetos explícitos, regras literais e perfil legado preservados. Não se desenham consumos/efeitos novos para outros objetos.
- **2D/ENEM:** `acao: esquema`, `esquema: escala`, `itens: [nomes]`, `valores: [medidas]`, `unidade: cm`. Duas a quatro medidas positivas na mesma unidade; comprimentos proporcionais no mesmo eixo. Preflight recusa dados inválidos, e o desenho defensivo não inventa medidas. Os prompts canônicos explicam o contrato.

## Reprodução

Os fixtures de seis segundos ficam em `motor_web/tests/comparacoes.fixtures.mjs`. O renderizador de ensaio mantém os mesmos specs e instantes para base/candidato:

```bash
node motor_web/tests/comparar_referencias.mjs CAMINHO_BASE/motor_web docs/experimentos-2026-10-29/antes
node motor_web/tests/comparar_referencias.mjs motor_web docs/experimentos-2026-10-29/depois
python3 motor_web/tests/galeria_comparacoes.py
```

`CHROME` aceita o caminho do navegador. Requer dependências npm, fontes carregáveis e FFmpeg. Os vídeos são prévias silenciosas de 12 fps, codificadas em 540×960; os PNGs de inspeção têm 1080×1920. Nos clipes, o 3D é renderizado internamente a 50% e composto na grade original, igualmente em base/candidato. Os PNGs permanecem em resolução integral. O fps de produção não muda.

`index.html` incorpora as seis prévias e três pares de quadros; pode ser transportado sozinho. Resultados técnicos e specs ficam junto dos renders, em `antes/` e `depois/`.

## Critério visual e limites

Quadros locais do usuário em 12 s e 10 s mostraram contexto ambiental e interior do objeto. A pesquisa dos canais está em `/home/azureuser/tarefas-videos-auto/CANAIS_REFERENCIA_MOTORES_2026-10-29.md`; os vídeos externos não foram integralmente assistidos neste experimento.

A cena 3D continua com geometria esquemática de lâmpada, sem simulação térmica ou material fisicamente exato. Aproximação não corrige modelo inadequado. Na cena 2D, a base desconhece `escala` e apresenta a cadeia existente: a comparação demonstra uma capacidade nova, não uma medição de realismo. As medidas 1, 2 e 4 cm são de blocos didáticos sintéticos.

O padrão de aceitação é inspeção comparativa e preservação de sentido; passar testes não prova equivalência visual aos canais. Tempos locais foram registrados com tarefas concorrentes, sem alegar ganho de velocidade. Nada foi publicado nos canais nem promovido para produção nesta rodada.
