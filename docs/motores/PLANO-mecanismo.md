# Plano do motor `mecanismo` — T503 (11–12/11/2026)

Canais: HOW IT WORKS (en, mediana 1.033), ASÍ FUNCIONA 3D (es, 1.051), GADGET GUTS (en, 894), CAR HACKS 3D (en, 825),
TIMELINE DROP (en, trocado de `linha_tempo` em 10/11) e CAI NO ENEM (pt, trocado de `enem` em 05/11: 82 → 918).
É o motor com mais canais (6) e "fica" 0,43–0,49: cada ponto de retenção nos 3 primeiros segundos vale em seis canais.

## Evidência (folhas em tamanho real, bancada na VM: `/var/lib/videos-auto/motores-plano/mecanismo/`)
Specs reais publicados em 11/11: `hiw` (airbag), `asi` (plancha), `gadget`, `car`. Folhas `antes/` (main `cbe51fe`),
`depois/` e `depois2/` (sessões T503 de 11/11), `depois3/` (12/11, sessão interativa). Cópias na branch `folhas/2026-11-12`
do celula-render (`*.jpg.b64`).

Defeitos vistos no ANTES (hiw-gancho.jpg, hiw-cenas-1.jpg):
1. **Rótulo escondido atrás do cartaz do título** nos 3 primeiros segundos (a linha amarela sobe para debaixo do cartão):
   o espectador não lê o rótulo da peça exatamente no gancho. (Régua: "elemento coberto".)
2. **Objeto pequeno**: ~25% da altura útil; 40% do quadro é chão vazio entre o objeto e a legenda. (Régua: "< 30% da altura".)
3. Rótulo de 42 px: no celular (quadro a 360 px de largura) vira ~14 px — ilegível.
4. Corte "por dentro" lento na 1ª cena: o interior só aparece perto de 1 s.
5. (ASI) modelo da plancha é uma placa cinza com dois tubos; o cartão "OBJETO COMPLETO" (piloto T454) ocupa o canto e
   mostra o objeto inteiro em miniatura. O problema aqui é a GEOMETRIA que o planejador gera (`planejar_web.js`/spec
   `modelo.partes`), não o motor; fica registrado para a rodada de "modelos" (abaixo).

## Mudanças (motor_web/estilos/mecanismo.js; contrato do spec intacto)
| # | O quê | Por que dá views | Como validar | Reverter |
|---|---|---|---|---|
| M1 | Rótulo desce para baixo do cartaz enquanto o cartaz está na tela (3 s) e volta ao topo depois (`baseCartaz`, `topo0`) | O gancho mostra a peça + o nome dela legível no 1º segundo (tarefa/pergunta na tela, o que diferencia os canais fortes) | teste `tests/mecanismo_t503.test.mjs`: rótulo y ≥ 470 em t=1,5 s e < 470 em t=5 s | `git revert` do commit T503 |
| M2 | Fonte do rótulo 42→56 px (mínimo 38), caixa/linha/ponto maiores | Legível no celular | teste: fonte ≥ 50 px | idem |
| M3 | Câmera 20% mais perto (`ZOOM503 = 0.80`) e folga horizontal 1,35→1,15; `setViewOffset` sobe o objeto 7% para a faixa livre entre cartaz e legenda | Objeto ≥ 30% da altura; menos chão vazio | teste: distância < 17,5; folha depois3 | idem |
| M4 | Corte "por dentro" 1,6× mais rápido só na 1ª cena (`k * 3.2`) | O "por dentro" aparece antes de 1 s | folha gancho t=0,3/1 s | idem |

O que NÃO muda: paleta, cartaz, legenda (posição 70%, área segura), lógica das ações (corte/monta/mostra/destaque),
piloto T454 (referência "OBJETO COMPLETO") e o contrato do spec.

## Validação
- `npm test` (30 testes + 4 cjs) verde na VM — ver `depois3/npm-test.log`.
- Render completo `render_web.mjs` do spec real `hiw` (preflight) — ver `depois3/render.log` (duração, 1080×1920).
- Folhas antes/depois conferidas em tamanho real (gancho, cenas, fim, t=1 s) para hiw/asi/gadget/car.
- Push no main pela API (`ferramentas/push_main.py`) → `validar-motores` = success → próximo render real de produção do motor.

## Pendente / próxima rodada deste motor (fora desta entrega)
- **Modelos**: a biblioteca de `partes` (caixa/esfera/cilindro) gera objetos pouco reconhecíveis (plancha = placa). Candidato
  a maior ganho visual do motor: formas compostas por tipo de objeto (eletrodoméstico, peça de carro, gadget) com 3–5
  primitivas pré-montadas, escolhidas por palavra-chave do título. Exige mudança no planejador (`planejar_web.js`) ou
  no `comum3d.js`; medir por folha antes/depois.
- **Chão vazio**: avaliar legenda a 62% e objeto a 48% da altura (hoje 70%/~40%); depende de conferir área segura do app.
- Medir ao vivo: mediana de views e "fica" por versão do motor (commit sha no `video_atributos`) nos 6 canais, 7 dias após o push.
