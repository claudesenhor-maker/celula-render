# Motor `quiz` — v3 (redesenho, T503, 13/11/2026)

Canal: **ODD ONE OUT** (en) — o melhor canal da casa nos últimos 30 dias: mediana 1.188 views, retenção média 0,77,
"fica" 0,40 (61 vídeos). Ordem do dono (13/11): "pegue o nosso melhor canal e redesenhe completamente o motor; ache
todos os erros; mais retentivo; mais detalhes; melhore a legenda". Contrato do spec intacto; som intacto (REVELA = 1,3 s).

Folhas antes/depois na VM: `/var/lib/videos-auto/motores-plano/quiz/{antes,depois2,v3c}/` (5 specs reais do canal:
odd1–odd5) e na branch `folhas/2026-11-13` (`quiz/v3b`, `quiz/v3c`). Teste: `motor_web/tests/quiz_v3_t503.test.mjs`.

## Erros achados (v2) e o que a v3 faz
| # | Erro na v2 | Efeito | v3 |
|---|---|---|---|
| E1 | `sem_pedaco` e os furos dos ícones (chave, peixe, casa, olho, gato) usavam `destination-out`: o furo atravessava o cartão e mostrava o fundo colorido | O diferente virava um ponto amarelo/rosa no meio da grade — nível sem desafio (31 de 61 vídeos tinham `sem_pedaco`; com ele no nível 1 a mediana é 1.125 contra 1.228 sem) | Furo pintado com a cor do cartão (opaco) |
| E2 | As frases que o roteiro escreve na premissa ("If you blink, your streak ends", "But now, look closer", "How many did you catch?") nunca apareciam | O roteiro prometia escalada e pedido de comentário que o vídeo não mostrava | Legenda no alto (faixa livre depois do cartaz do título): `cena.legenda` > `spec.legendas` > frases entre aspas da premissa > frases padrão do idioma (en/es/pt), sem repetir o rótulo nem outro nível |
| E3 | "FOUND IT?" na mesma linha do rótulo ("MYTHIC FOUND IT?") | Texto encavalado | Virou legenda |
| E4 | Resposta = círculo fino de ~40 px numa grade 12×16 | Invisível no celular: o payoff do vídeo não era visto | Holofote (o resto do cartão escurece), anel vermelho/branco que pulsa, o diferente **ampliado** (≥ 150 px) no lugar |
| E5 | Nível 1 curto (4 s): só 0,2 s entre o cartaz e a revelação | A frase de abertura só piscaria | A abertura passa para o nível 2 |

## Retenção e detalhe
- Placar de progresso "2/4" + barrinhas dos níveis (feitos / atual enchendo / futuros): quem está no 3 fica para o 4.
- Cronômetro com anel que esvazia; vermelho e tremendo nos 2 últimos segundos.
- Troca de nível com lampejo branco e cartão que sobe com mola (o nível 1 já está no quadro 0).
- Fim: "How many did you get? _/4" (ou a pergunta final da premissa + "_/4") — pede o placar nos comentários.
- Fundo com listras e vinheta, cartão com sombra e borda, itens com sombra curta; letras com respiro na legenda.

## Não mudou
Regras de dificuldade (piso 6×9 → 10×16, camuflagem por tremor, sutileza por nível), cores por nível, cartaz do título,
tempo de revelação (1,3 s), eventos de som do `montar_web.py`, `window.QUIZ_ITENS`.

## Medir (quando o dono religar os canais)
Mediana de views, retenção e "fica" de ODD ONE OUT nos 7 dias após o 1º vídeo com a v3 contra os 30 dias anteriores
(1.188 / 0,77 / 0,40). Reverter: `git revert` do commit da v3.

## v3.1 — encerramento de conversão (13/11, ordem do dono)
O canal tem a maior retenção da casa; o problema é **likes, comentários e inscritos**. `montar_web.py` dá à última cena
mais `CTA_QUIZ_S` = 2,6 s (`spec.cta_s`); o cronômetro e o "plim" do último nível recuam o mesmo tanto e entram três "pop".
Nesses 2,6 s o motor desenha: "COMMENT YOUR SCORE" com botões 0..N (responder = digitar um número), "♥ LIKE IF YOU GOT N/N"
e o botão SUBSCRIBE com sino, que é "apertado" e vira SUBSCRIBED ("NEW LEVELS EVERY DAY"). Idiomas en/es/pt.
A descrição do SEO do canal passa a pedir o placar nos comentários e a inscrição. Testes: `quiz_v3_t503.test.mjs`
(encerramento) e `test_quiz_cta_t503.py` (tempo e som). Medir: likes, comentários e inscritos por 1.000 views.
