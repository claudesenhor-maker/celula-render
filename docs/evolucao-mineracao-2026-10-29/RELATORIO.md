# Mineração visual — encerramento local em 03/11/2026

O ciclo local foi implementado, ativado e conferido por execuções reais. A primeira passagem referência → oportunidade → experimento → comparação → decisão foi concluída, incluindo duas revisões motivadas por defeitos vistos nos quadros. O código e os artefatos ficam para revisão; não houve promoção para produção nem publicação de vídeos nos canais. O acesso à VM/n8n/banco canônicos continua fora desta entrega: as recusas documentadas em 29/10 não foram contornadas nem reensaiadas em 03/11.

Abra [a comparação da lâmpada, serpentina e controle pixel](comparacao.html). As fontes, contratos e pendências estão em [pesquisa](PESQUISA.md), [auditoria](AUDITORIA.md), [contrato](COMPARACAO_CONTRATO.md) e [operação/rollback](../../mineracao/README.md).

## O que está ativo

- Timer **local deste host** `videos-auto-mineracao.timer`, diário às 04:00 UTC, jitter até cinco minutos e linger do usuário habilitado. Não é o Minerador antigo do n8n nem uma instalação na VM.
- SQLite persistente em `/home/azureuser/videos-auto-mineracao-estado/catalogo.sqlite`; exportações idempotentes em `catalogo.json`, `backlog.md` e `triagem-canais.md`.
- Oito fontes configuradas: duas gravações fornecidas, cinco documentos primários e uma API pública de releases do Three.js. Limites: 120s, 8 tentativas por execução, 16 por dia, um retry, dois redirects por tentativa somente em hosts permitidos, 1,5 MB por resposta, cinco descobertas e três propostas novas por passagem. Até 48 transações HTTP/dia incluindo redirects; o campo histórico `requests` conta tentativas de coleta. Nenhuma API paga é chamada.
- Trava contra sobreposição, quota reservada antes do acesso, erros rastreáveis, recuperação de execução interrompida e preservação de decisões. O agendador coleta/triageia; não executa código de fontes externas nem altera motores automaticamente.

### Execuções reais e recuperação

| Dia UTC | Resultado automático | Coleta |
|---|---|---|
| 30/10 | ok | Oito fontes recentes respeitaram a janela de cache |
| 31/10 | ok | Oito fontes, seis tentativas HTTP, uma descoberta nova |
| 01/11 | ok | Oito fontes, seis tentativas HTTP |
| 02/11 | ok | Oito fontes, seis tentativas HTTP |
| 03/11 04:05 | parcial / saída 2 | Sete fontes; falha no redirect da documentação Google |
| 03/11 recuperação manual | ok | Fonte Google coletada após correção restrita; serviço normal reexecutado com sucesso |

O destino real era `https://aistudio.google.com/docs/video-understanding`. O diagnóstico interrompeu o primeiro redirect sem seguir host desconhecido e reservou uma tentativa na quota. Foi acrescentado **somente** esse host oficial; o ensaio coletou 86.313 bytes e manteve custo de API paga zero. A lista de hosts não foi aberta genericamente, e mudanças de hash não receberam aprovação visual. O motivo seguro `redirect_nao_permitido` agora aparece no erro, sem persistir texto de transporte ou credenciais. O feed Atom antigo, grande demais, permanece como registro histórico de falha; a rotina usa a API limitada de releases.

[Execuções exportadas](coletas-reais.json), [estado do timer/serviço](timer-verificado.txt) e [diagnóstico do redirect](redirect-google-20261103.json) sustentam esses resultados. O sucesso da última execução normal também respeitou o cache: não significa que oito fontes foram baixadas novamente nesse instante.

## Catálogo e backlog

O catálogo contém 20 oportunidades para 17 motores e o rig auxiliar `palito_v4`. A análise das gravações locais usa quadros/timecodes explicitamente registrados; não houve reprodução integral nem validação da narração. O backlog cobre os seis estilos Three.js, oito Canvas e três motores Python, sem contar auxiliares como motores independentes.

As 12 referências adicionais de canais estão [em triagem](triagem-canais.md): Branch/Jared/Animagraffs, Saint11/AdamCYounis e Kurzgesagt/3Blue1Brown têm prioridade editorial. Declarações das páginas e hipóteses de uso ficam separadas de observações visuais. Não foram inventados timecodes, baixados assets ou ativada coleta desses canais. Releases novas também entram como metadados, sem aprovação automática.

Quando o hash de uma fonte muda, o catálogo marca reconferência pendente e não gera propostas com observações antigas. A mudança de HTML pode ser decorativa; não prova mudança técnica. Experimentos mantêm seus próprios hashes e decisões. Views não participam da prioridade gráfica. A nova oportunidade de close/rótulos nasceu para vincular o laboratório separado à lacuna de direção visual, sem misturá-la à implementação de perfil/tubo.

## Incremento e comparação visual

Base dos ensaios: `358566fd814ec05d12194670aa5c5008ef23196a`, auditada em 29/10. O mecanismo ganhou perfil axial com interpolação monótona limitada e tubo contínuo em curva centrípeta, com dados finitos, limites de geometria e pivôs preservados. Peças antigas mantêm suas primitivas. Rótulos de curvas ancoram num ponto real do caminho, transformado pela pose/pivô, em vez da origem vazia.

Os dois lados de cada par usam o mesmo spec, semente, resolução e câmeras lógicas. A base ignora os novos campos e usa a forma de fallback: é um experimento de capacidade do motor, não prova de que a IA planejará automaticamente bons modelos. O enquadramento automático responde à caixa da geometria; a projeção numérica pode mudar com o modelo.

| Experimento | Evidência observada | Decisão registrada |
|---|---|---|
| Perfil r0 | Pescoço surgiu, mas o contorno ficou angular | Rejeitado, apesar dos testes geométricos aprovados |
| Lâmpada suavizada | Contorno mais suave e distinção pescoço/ombro; interior preservado | Em revisão: custo acima do orçamento; vidro/modelo ainda esquemáticos |
| Tubo r1 | Serpentina contínua; rótulo apontava para o vazio da origem | Devolvido à revisão |
| Tubo final | Rótulo sobre um ponto do cano; teste com pivô teve erro de projeção zero | Candidato técnico para revisão, sem promoção/editorial aprovado |
| Pixel controle | 72 PNGs idênticos entre base e candidato | Preservação, sem melhoria estética alegada |

Os quadros de r0 e r1 foram preservados (`r0-bulbo-angular-rejeitado.png`, `r1-rotulo-no-vazio.png`, MP4 r1), e os JSON `experimento-*.json` registram as decisões. As imagens finais foram inspecionadas em 1,5s e 4,5s. Seis clipes de seis segundos/72 quadros a 12fps foram decodificados; isso não equivale a assistir continuamente aos clipes com narração. PNGs e MP4s integrais têm 1080×1920. O player oferece WebM de compatibilidade em 540×960.

O fluxo continua sujeito à oclusão do metal; não demonstramos uma explicação completa de fluido/termodinâmica. Não há tampas físicas de seção, refração realista, anatomia reconstruída ou garantia de ausência de autointerseção para qualquer curva. A qualidade global permanece abaixo das referências em direção, acabamento e atuação.

### Custo observado

| Cena | Média base ms/quadro | Média final ms/quadro | Heap JS base/final (MB decimais) |
|---|---:|---:|---:|
| Lâmpada | 3.623 | 9.691 | 4,32 / 3,79 |
| Serpentina | 4.535 | 1.856 | 3,64 / 3,57 |
| Pixel | 797 | 813 | 2,51 / 2,51 |

Médias incluem leitura/PNG. Cargas do host variaram; **não são ganhos/perdas estatísticos de velocidade**. A lâmpada excedeu o critério de até +20% e permanece em revisão, aguardando medição isolada. Não usamos a melhora aparente da serpentina como prova de eficiência. Heap JS exclui memória completa de Chrome/GPU. Houve timeout ao iniciar Chrome e `Target closed` durante tentativas sob pressão de memória; foram registradas falhas, retomados renders sequenciais e concluídas as exportações. Não atribuímos a causa desses incidentes à geometria sem diagnóstico adicional.

[Medições completas](comparacao/medicoes.json), [specs](comparacao/specs.json) e [validação de artefatos](comparacao/validacao-artefatos.json) incluem determinismo e hashes. Contagem de triângulos/chamadas é custo técnico, nunca nota de qualidade visual.

## Três ensaios do outro laboratório

Foram importados resultados reais de mecanismo, pixel e escala **2D/ENEM**, da branch `experimento-comparacoes-20261029`, sem editar `/home/azureuser/videos-auto-comparacoes`. Os três registros finais estão em revisão, com hashes da galeria, resumo e verificação. `escala` é o nome da fixture ENEM desse laboratório; não é o motor Three.js homônimo.

A [galeria do laboratório separado](/home/azureuser/videos-auto-comparacoes/docs/experimentos-2026-10-29/index.html) contém as comparações de close/corte/rótulos, gesto de consumo e diagrama de medidas. Esses resultados não foram promovidos nem integrados a esta branch. Os primeiros snapshots de catálogo foram conservados; registros `-final` atualizam apenas a proveniência da galeria que recebeu compatibilidade WebM, sem reescrever os anteriores. A integração futura deve preservar `rotuloLocal`/`localToWorld` e repetir os testes na combinação de mudanças.

## Validação e limites de conclusão

- 22 testes Node, regressões T392 (423 cenas), T294, T302 e T337 passaram. Python: 9 testes da mineração e 7 do helper/motor. Teste de rótulo no navegador: ponto esperado e desenhado iguais, erro zero, sem pageerror.
- Seis MP4s finais, 72 quadros cada, decodificados. Repetição temporal idêntica nos três pares desta branch. As 72 imagens pixel foram comparadas byte a byte. WebM e funcionamento da galeria têm registro próprio; não são revisão semântica por IA.
- A ponte de revisão foi testada com servidor **simulado**, sem serviço externo multimodal. Não houve IA assistindo ao vídeo inteiro. A amostragem agora prioriza eventos declarados e os dois lados dos cortes, até 16 instantes; eventos em excesso exigem subamostragem.
- A recorrência real está comprovada neste host, com limites e recuperação. Novas descobertas ainda exigem inspeção; o ciclo não transforma metadados em análise visual nem executa mudanças arbitrárias.
- Continuam pendentes: DAG/execuções/banco/consumidores/quotas do Minerador antigo, saúde atual da produção, narração/fps real dos pilotos, avaliação visual autorizada e integração das duas branches. A auditoria histórica não comprova por que o Minerador antigo teria parado; ele aparecia ativo no snapshot disponível.

O trabalho local está pronto para revisão. Produção e promoção permanecem pendentes por acesso e critérios de qualidade, sem pedido de autorização implícito para publicar ensaios.

## Reprodução e rollback

```bash
npm test --prefix motor_web
python3 -m unittest discover -s tests -p test_mineracao.py
python3 -m unittest discover -s motor_web/tests -p 'test_*.py'
CHROME=/caminho/chrome node motor_web/tests/rotulo_curva.browser.mjs
python3 mineracao/validar_artefatos.py docs/evolucao-mineracao-2026-10-29/comparacao
```

As sequências completas temporárias ficam fora do Git; `validacao-sequencias-completas.json` preserva a conferência das 72 imagens pixel. O verificador padrão usa os oito quadros pixel versionados quando a sequência não está presente. Para regenerar todos os clipes/quadros, execute `motor_web/tests/comparar_evolucao.mjs` com checkout base e saída; `VARIANTE`/`CENA` permitem repetir apenas um caso. Use um Chrome por vez neste host.

Para parar a rotina: `systemctl --user disable --now videos-auto-mineracao.timer` e `systemctl --user stop videos-auto-mineracao.service`. Preserve o SQLite, a quota e os resultados. Revertendo o código, desabilite antes o serviço que aponta para o checkout. Rollback do incremento gráfico pode remover os campos novos para recuperar primitivas ou reverter os commits pertinentes, preservando correções semânticas e consumidores existentes. Nenhum schema Postgres foi alterado.
