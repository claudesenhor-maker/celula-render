# Plano do motor `escala` — T503 (13/11/2026)

Canais: QUÉ TAN GRANDE (es, mediana 1.068), HOW BIG (en, 939), DESK UPGRADE (en, 430).

## Evidência (folhas: `/var/lib/videos-auto/motores-plano/escala/{antes,depois}/`, specs reais de 12–13/11)
1. **Comparação com ordens de grandeza some** (howbig: "Is Your Bus Safe Beside This Iceberg?" — ônibus de 12 m × pegada
   de iceberg de 170 km): o item pequeno é invisível em TODOS os quadros; o vídeo inteiro é uma faixa branca (a pegada)
   sobre grama com etiquetas. O cartão "12 M BUS" aparece sem ônibus nenhum. É o defeito que mais derruba o canal:
   o espectador não vê a comparação que o título promete.
2. Item chato e largo (pegada, pista) visto quase do chão vira uma linha (a elevação v2 sobe até 43°).
3. Metade de baixo do quadro é grama vazia; a textura de grama é ruidosa e achata a cena.
4. DESK (430): objetos de mesa (teclado) aparecem bem, mas sem referência humana/mesa a escala "cm" não impressiona.

## Tentativa desta sessão (DESFEITA)
Elevação até 66° para itens chatos + cena 6% mais alta depois do cartaz. As folhas `depois/` mostram ganho quase nulo:
a pegada continua uma faixa e o ônibus continua invisível. Não foi publicado (regra: não mexer sem ganho visível).

## O que fazer (próxima rodada, por ordem)
| # | Mudança | Por que dá views | Validação |
|---|---|---|---|
| S1 | **Lupa/encarte de escala**: quando a razão entre o item da vez e o maior visível passa de ~50×, desenhar um círculo
  (≈30% da largura) ancorado no ponto do item pequeno, com uma segunda passada de render (`U3.render` com câmera própria)
  mostrando o item pequeno na escala dele + rótulo e uma barra "= 1 px aqui"; o encarte encolhe até virar o ponto real
  durante o zoom out | A comparação prometida no título passa a ser vista | folha howbig: ônibus visível em todos os quadros |
| S2 | Item chato visto de cima (≥ 70°) com sombra/contorno forte e a pegada colorida (não branca sobre grama clara) | A área vira forma legível | folha howbig cenas |
| S3 | Chão neutro e menos ruidoso (grama de baixa frequência ou asfalto/mar conforme o tema) | Contraste do objeto | folhas dos 3 canais |
| S4 | DESK: referência fixa de mão/mesa/monitor ao lado dos objetos de mesa | A diferença em cm fica física | folha desk |

Contrato do spec intacto (`itens[]`, `alvo`, `hud`). Medir por versão do motor nos 3 canais quando o dono religar.
