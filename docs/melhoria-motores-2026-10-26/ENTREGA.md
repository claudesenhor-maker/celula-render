# Melhoria dos motores — implementação de 26/10/2026

Implementado em `/home/azureuser/celula-render-retomada`, sobre o commit `c1c461f`. Os arquivos de produção/remotos não foram publicados nesta sessão. O diagnóstico anterior está em `../revisao-visual-2026-10-26/REVISAO.md`; este documento registra a implementação posterior.

## Referências usadas

Foram examinados 12 quadros distribuídos ao longo de cada gravação enviada:

- `/home/azureuser/Gravando 2026-10-26 195402.mp4`: 46,6 segundos, exemplo de lâmpada/filamento, aproximações para revelar o interior, rótulos e partículas localizadas.
- `/home/azureuser/Gravando 2026-10-26 195512.mp4`: 31,67 segundos, exemplo de refrigeração, peças conectadas, setas de percurso, ambiente doméstico e alternância entre contexto e detalhe.

As folhas das referências estão em `/home/azureuser/retomada-videos-auto/referencias-20261026/`. As gravações são capturas de tela do Instagram; não foram reutilizadas como assets dos motores. A referência orientou a direção visual: detalhe funcional, contexto, fluxo visível e continuidade espacial. Não houve análise da narração nem validação científica do conteúdo dos vídeos.

Pesquisa aplicada a partir de fontes primárias:

- [Three.js — instâncias](https://threejs.org/docs/pages/InstancedMesh): agrupamento de objetos com geometria/material comuns, usado em janelas, vegetação e blocos da pele.
- [Three.js — otimização de objetos](https://threejs.org/manual/pages/optimize-lots-of-objects.html): redução do trabalho por objeto e reutilização de recursos.
- [Three.js — cor](https://threejs.org/manual/pages/color-management.html): separação entre texturas de cor e dados de superfície. As APIs usadas foram adaptadas à versão **r128 já instalada**, sem atualizar a biblioteca.
- [MDN — otimização de Canvas](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API/Tutorial/Optimizing_canvas): reutilização de elementos estáticos em camadas fora da tela.
- [MDN — suavização](https://developer.mozilla.org/en-US/docs/Web/API/CanvasRenderingContext2D/imageSmoothingEnabled): preservação da grade no pixel art.
- [FFmpeg — filtros](https://ffmpeg.org/ffmpeg-filters.html): conversão de matriz/faixa de cor explícita na exportação web.

## Alterações nos seis motores 3D

**Base comum:** cache de geometrias por preparação, liberação de geometrias/materiais/texturas/reflexos na troca de preparação, materiais opacos fora da fila de transparência, transparências sem escrita indevida de profundidade e métricas de chamadas/triângulos/recursos. Madeira recebe relevo procedural discreto. Microtextura adicional em tecido/pedra/pele fica disponível por `microtextura: true`, por ter custo maior. Vidro recebeu transparência dependente da borda, preservando reflexo sem exigir refração física de tela inteira.

**Mecanismo:** pivôs locais opcionais, transmissão direta entre peças, curvas de fluxo calculadas uma vez por cena e fluxo com oclusão por padrão. `fluxo.raio_x: true` permite atravessar a superfície quando isso for intencional. `corte_modo: "secao"` aplica plano de recorte à carcaça; não constrói tampas nas superfícies seccionadas. O raio X anterior continua disponível. Cenários interiores ganharam alguns elementos laterais em volume.

**Low-poly:** geometrias de caixas e normais facetadas reutilizadas, janelas agrupadas em instâncias e luz de recorte discreta. Na fixture examinada, a implementação passou de 306 chamadas antes do agrupamento para 164 depois. Mantido o desenho facetado e a base Lambert adequada ao render em software.

**Escala:** formas compartilhadas, pequenos detalhes no personagem de referência, névoa reutilizada e novo plano de câmera aplicado apenas ao mundo 3D. Proporções e medidas permanecem nos dados do spec.

**Animal:** formas suaves, materiais de superfície, articulação das patas no encaixe, pivôs/fases explícitos opcionais, sombra de contato e habitats savana/floresta/gelo/deserto. Vegetação distante agrupada em instâncias com geometria leve; chão Lambert evita gastar material físico na tela inteira. Não foi criado um catálogo anatômico completo nem um ambiente aquático.

**Órbita:** continentes derivados do conjunto Natural Earth já incluído no projeto, nuvens incorporadas à textura e configuração consistente de cor. Data de referência explícita; sem data, usa J2000 para reprodução, com indicação na cena de sistema. O halo por composição está disponível em `atmosfera_2d: true`; fica desligado por padrão após medição de custo. A camada de nuvens não é uma simulação atmosférica e as órbitas continuam esquemáticas.

**Micro:** blocos agrupados quando a cena não precisa de transparência individual de esfoliação, geometrias celulares mais econômicas, transparências corrigidas e perfil de superfície de pele. Na fixture, 202 chamadas antes do agrupamento passaram a 23. O caminho com esfoliação mantém peças individuais para preservar a animação. O modelo continua esquemático, sem comprovar penetração ou eficácia de um ativo.

## Alterações nos motores 2D

**Composição comum dos 14 motores web:** o zoom raster sobre o quadro inteiro foi retirado do padrão. A câmera pode aproximar o mundo 3D sem recortar interface. Título e legenda passaram a usar largura segura, medição e cache de quebra de texto. O comportamento raster antigo só é solicitado explicitamente com `ritmo_raster: true`, e continua proibido para pixel art.

**Pixel:** saída sem suavização, sprites/fundos estáticos em cache, desenho de digitação com contato com teclado/cadeira, vapor de café, sombras e detalhes de piso/rodapé. Diálogo paginado com linhas estáveis durante a digitação. CRT agora é opcional (`crt: true`). A grade-base permanece 180×320, ampliada 6× em 1080×1920.

**Mangueira:** grão menos agressivo no padrão e vinheta reutilizada. `pelicula_intensidade` permite recuperar a intensidade desejada sem alterar a atuação.

**Silhueta:** vinheta reutilizada e passagem menos escura entre cenas, preservando leitura da ação.

**Mapa:** caminhos geográficos pré-processados e projeções reutilizadas durante o desenho de sombra/preenchimento/contorno. Não foram inventadas fronteiras históricas.

**Linha do tempo:** texto dos eventos ajustado ao espaço disponível, usando o conteúdo completo recebido, em lugar de descartar tudo após duas linhas fixas.

**Quiz:** grade reutilizada depois da entrada, mantendo a posição do diferente e a revelação determinísticas.

**Física:** fundo estático em cache. Simulação e eventos de áudio preservados.

**ENEM:** lousa e manchas de giz renderizadas uma vez e reutilizadas; texto/ações permanecem independentes do fundo.

**Motores Python de recorte/cartão/vetorial:** perfil de codificação compartilhado em `qualidade_render.py`, com CRF 20 no padrão e bitrate calculado com reserva dentro do orçamento de 45 MB. O perfil rápido usa CRF 23. A reamostragem de ampliação do recorte foi preservada, pois o projeto já documentava que alternativas criavam halos. Esses motores receberam melhoria de exportação e conferência de amostras via `conferir_quadros`, que guarda prévias/relatório e consulta o mesmo revisor opcional. Sem endpoint há apenas diagnóstico técnico; com endpoint, reprovação ou pedido de correção interrompe, pois a ponte legada é de aprovação/reprovação. Não houve reconstrução de personagens nem render completo de cada caminho legado nesta sessão.

## Como a direção e a revisão funcionam durante o render

1. `diretor_visual.mjs` prepara uma cópia do spec, valida intervalos/dimensões/modelos/alvos, fixa a data da órbita e define câmera funcional para mecanismo quando ausente.
2. `preflight.mjs` renderiza abertura, instantes das cenas e final, até 16 amostras, antes de codificar o MP4. Registra imagens, contraste e custo/recursos. Quadros sem variação na área do assunto são reprovados.
3. Sem serviço externo configurado, o relatório declara **técnico-local**. Isso não representa aprovação semântica por IA.
4. Com `VIDEO_REVISOR_URL`, as imagens ordenadas, as cenas e as capacidades do motor são enviadas ao revisor de visão. A configuração de voz/credenciais não é incluída.
5. O revisor pode pedir mudanças limitadas de câmera, zoom e exposição quando o motor suporta esses campos. Uma mudança exige reconstrução e nova revisão. Há no máximo uma rodada de correção; reprovação persistente interrompe o render. Texto, números, geometria e fatos não podem ser alterados por essa interface.
6. O spec efetivamente renderizado e o relatório são preservados junto das prévias. A montagem com áudio conserva esses arquivos, inclusive em reprovação.

Isso é análise de **amostras temporais**, não visão contínua de todos os quadros nem um novo modelo de IA instalado. O serviço de visão permanece opcional e não foi conectado a uma API externa real nesta sessão. A ponte foi testada com servidor local simulado e navegador real.

`roteiros.json` recebeu instruções de continuidade/detalhe nos estilos existentes e contratos para mecanismo, escala, animal, órbita e micro. A esteira externa deve sincronizar esses prompts para usá-los; não houve alteração direta dos prompts persistidos no n8n/banco de produção.

## Contrato do revisor opcional

O backend indicado por `VIDEO_REVISOR_URL` deve aceitar POST JSON com `versao`, `instrucao`, `capacidades`, `spec` e `quadros`. Cada quadro inclui tempo, índice de cena, imagem JPEG em data URL e métricas. O backend deve encaminhar imagens ao modelo multimodal que a instalação utilizar e devolver JSON:

```json
{"aprovado": false, "problemas": ["Detalhe pequeno no quadro da segunda cena"], "correcoes": [{"cena": 1, "camera": "perto", "plano": {"zoom": 1.05}}]}
```

Uma resposta final aprovada deve ter `aprovado: true` e `correcoes: []`. O token opcional vem de `VIDEO_REVISOR_TOKEN`, enviado como Bearer. Timeout: 60 segundos. Erro HTTP, contrato inválido ou câmera/campo não suportado interrompe o render configurado com revisor. Não há fallback que finja aprovação de visão.

No GitHub Actions, URL usa a variável `VIDEO_REVISOR_URL` e token usa o secret `VIDEO_REVISOR_TOKEN`. Esses valores não foram criados. O workflow local também recebeu execução dos testes e guarda do relatório/prévias como artefato; a instalação do motor web funciona com specs recebidos por URL, além do payload inline.

## Evidências e limites da validação

- **13 testes Node + 7 Python passaram (20 no total).** Cobrem preparação, recusas de spec, preservação de fatos, correções permitidas, falhas HTTP, limite de revisão e orçamento de codificação, além dos testes anteriores de ritmo e sentido visual.
- **14 motores web:** quatro amostras em 1080×1920 por motor, sem `pageerror`, com as seis fontes disponíveis. Foram exercitados começo, meio e troca de cena com fixtures específicas.
- **Repetição temporal:** o teste pede 1,5 s, avança até 6 s e volta a 1,5 s. O critério admite até 0,1% dos pixels com diferença superior a quatro níveis por canal. Micro e mangueira apresentaram pequenas diferenças raster registradas no JSON; não há garantia de identidade bit a bit entre chamadas, máquinas ou drivers.
- **Dois MP4** exportados e decodificados por FFmpeg: mecanismo sem áudio e pixel via montagem completa, com SFX/trilha AAC. O pixel saiu 1080×1920, H.264/AAC e BT.709. São ensaios técnicos com fps reduzido (2 e 8), não pilotos aprovados editorialmente nem mudança do fps padrão de produção.
- **Ciclo real no navegador:** duas chamadas ao servidor local simulado, com troca de câmera, liberação/recriação do motor e aprovação na segunda rodada.
- Sintaxe dos módulos, Python, JSON e YAML verificada; `git diff --check` passou.

As fixtures não representam todos os roteiros possíveis. A validação dos motores legados Python cobriu o helper de codificação, geração de prévias, ponte HTTP com aceitação/reprovação e sintaxe dos pontos integrados; não substitui renderizar vídeos completos com os assets reais desses canais.

Comparativos: [3D](comparativos.html#3d), [2D](comparativos.html#2d), [quadro extraído do MP4 pixel](comparativos.html#pixel).

Tempos orientativos de três quadros após o primeiro, no mesmo navegador/VM com SwiftShader, incluindo leitura e PNG. Não são benchmark estatístico nem medição de vídeo inteiro. Valores negativos indicam menor tempo; pequenas diferenças podem ser ruído de carga da VM. Órbita aceita custo maior para a cor/superfície mais correta, com halo caro fora do padrão.

| Motor | Antes (ms) | Depois (ms) | Variação |
|---|---:|---:|---:|
| lowpoly | 698 | 699 | +0.2% |
| mecanismo | 1845 | 1726 | -6.4% |
| escala | 1368 | 1161 | -15.2% |
| animal | 988 | 983 | -0.6% |
| orbita | 543 | 639 | +17.7% |
| micro | 2556 | 2267 | -11.3% |
| pixel | 459 | 334 | -27.3% |
| mangueira | 1191 | 995 | -16.5% |
| silhueta | 1149 | 979 | -14.8% |
| mapa | 1459 | 1402 | -3.9% |
| linha_tempo | 553 | 530 | -4.1% |
| quiz | 339 | 324 | -4.6% |
| fisica | 1151 | 961 | -16.5% |
| enem | 745 | 426 | -42.8% |

Dados completos: `medicoes.json`, `antes/resultados.json`, `final/resultados.json`. Os JSON por motor em `final/` preservam as medições posteriores de animal/órbita. Capturas estão nas mesmas pastas. Artefatos exploratórios intermediários foram movidos para `/tmp/videos-auto-exploracao`.

Reprodução a partir da raiz:

```bash
npm test --prefix motor_web
python3 -m unittest discover -s motor_web/tests -p 'test_*.py'
CHROME=/caminho/chrome node motor_web/tests/auditar_graficos.mjs motor_web /tmp/auditoria-motores
CHROME=/caminho/chrome node motor_web/tests/revisao.browser.mjs
```

O pipeline web usa PNG intermediário no perfil detalhado, CRF 18 para pixel e 20 para os demais, com matriz/faixa de cor explícitas. `qualidade: "rapido"` usa JPEG intermediário e reduz extras de superfície/cenário; não recebeu benchmark completo separado. Os perfis e limites são determinísticos, não mudam a imagem conforme a velocidade do computador.
