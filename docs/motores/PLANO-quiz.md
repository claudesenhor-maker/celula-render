# Plano do motor `quiz` — T503 (13/11/2026)

Canal: ODD ONE OUT (en, mediana 1.170 — o melhor canal; "fica" 0,40). Regra do dono: **não piorar o que está bom**.
Formato: grade de itens iguais com um diferente, cronômetro, resposta circulada. Sem voz. 28,7 s de 32 s com quadro
congelado (T487) — e mesmo assim é o melhor canal: a retenção vem da TAREFA dada ao espectador, não de animação.

## Evidência (folhas: `/var/lib/videos-auto/motores-plano/quiz/{antes,depois}/`, specs reais `odd1`, `odd2` de 12/11)
1. A grade começava em y=540 e terminava em y=1380: entre o cartão e a área coberta pelo app (y>1440) sobravam
   60 px, e no topo o rótulo do nível (y=300) e o cronômetro (y=430) gastavam 240 px em duas linhas.
2. Símbolos pequenos: grade 6×9 em 840 px de altura → célula de 93 px; no celular (360 px de largura) vira ~31 px.
3. Nível 1: o cartaz do título (2,2 s) fica sobre o rótulo/cronômetro — coerente, não muda.

## Mudanças (motor_web/estilos/quiz.js; contrato do spec intacto)
| # | O quê | Por que dá views | Como validar | Reverter |
|---|---|---|---|---|
| Q1 | Rótulo do nível e cronômetro na MESMA linha (y=330; cronômetro à direita, "FOUND IT?" no lugar do cronômetro) | Libera 110 px no topo | folha depois (gancho) | `git revert` |
| Q2 | Grade de y=430 a y=1440 (era 540–1380) e x até 895 (era 890) | Grade 20% mais alta → símbolos ~15–20% maiores, mais legíveis no celular; a tarefa ("ache o diferente") fica mais fácil de aceitar no 1º segundo | folha depois (cenas); célula de 93 → 112 px na 6×9 | idem |

O que NÃO muda: regras de dificuldade (piso 6×9 → 10×16), camuflagem, cores, cartaz, tempo de revelação, variação por vídeo
(política de conteúdo repetitivo).

## Validação
- `npm test` (quiz/depois/npm-test.log); folhas antes/depois conferidas em tamanho real (odd1, odd2).
- Push no main → `validar-motores` (disparo manual, se o push pela API não acionar) → 1º render real.

## Pendente / próxima rodada
- Hipótese T487 não aplicada: entrada animada da grade no 1º meio segundo (hoje `entra` em 0,35 s a partir de −0,25 s: já é rápida).
- Medir ao vivo: mediana e "fica" por versão do motor em ODD ONE OUT, 7 dias após o push.
