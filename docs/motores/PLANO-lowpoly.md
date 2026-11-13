# Plano do motor `lowpoly` — T503 (12/11/2026)

Canais: TINY WHAT IF (en, mediana 1.027), MINI QUÉ PASARÍA (es, 1.147) e NIVEL: ADULTO (es, trocado de `pixel` em 10/11).
Melhor "fica" de todos os motores (0,49–0,56). Regra do dono: **não piorar o que está bom** — só mudanças de enquadramento,
sem tocar em cenário, personagens, ações, cores ou ritmo.

## Evidência (folhas em tamanho real: `/var/lib/videos-auto/motores-plano/lowpoly/{antes,depois,depois2}/`)
Specs reais publicados em 12/11: `tiny1` (gravidade dobrada), `tiny2` (oceanos +100 m), `mini1` (globo).
Defeitos no ANTES:
1. Cartaz do título tampa a cabeça do protagonista nos 3 primeiros segundos (tiny1 quadro 1; mini1 o balão some atrás do cartaz).
2. ~30% do quadro embaixo é grama vazia: a ação fica entre 25% e 60% da altura, a legenda a 70%, e o resto sobra.
3. Personagens ~25–35% da altura em câmera "orbita" (dist 21, alt 9,5): no celular ficam pequenos.
4. Personagem caído passa por trás da legenda (tiny1 cena 2): texto sobre o corpo. (Não mexido: é a ação `cai`; registrado.)

## Mudanças (motor_web/estilos/lowpoly.js; contrato do spec intacto)
| # | O quê | Por que dá views | Como validar | Reverter |
|---|---|---|---|---|
| L1 | `setViewOffset` por quadro: cena 2% mais baixa enquanto o cartaz está na tela (t<3 s), depois sobe 6% (transição 0,5 s) | Cabeça nunca entra no cartaz no gancho; depois a ação ocupa a faixa livre entre cartaz e legenda | folhas depois2 (gancho t=0,3/1/2/3) | `git revert` |
| L2 | Câmera 10% mais perto e mais baixa no mundo plano (`ZOOM503 = 0.9` em dist e alt); globo inalterado | Personagens ~10% maiores sem cortar cenário | folhas depois/depois2 cenas | idem |

O que NÃO muda: cenário, personagens, ações, paleta, cartaz, legenda, número/selo de tempo, globo.

## Validação
- `npm test` na VM (depois2/npm-test.log) e render completo `render_web.mjs` do spec real `tiny1` (depois2/render.log).
- Folhas antes/depois2 conferidas em tamanho real (tiny1, mini1). Push no main pela API → `validar-motores` → 1º render real.

## Pendente / próxima rodada
- Personagem caído × legenda (defeito 4): mover a pose `cai` para a frente/esquerda do foco ou subir a legenda nessa ação.
- Medir ao vivo por versão do motor nos 3 canais (mediana e "fica"), 7 dias após o push.
