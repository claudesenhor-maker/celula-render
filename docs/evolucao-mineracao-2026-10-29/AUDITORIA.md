# Auditoria de mineração e produção

Base: `origin/main` conferida via fetch, commit `358566fd814ec05d12194670aa5c5008ef23196a`. Implementação em checkout isolado `/home/azureuser/celula-render-mineracao`, branch `evolucao-mineracao-20261029`. As cópias `celula-render-producao-20261029` e `celula-render-retomada` foram preservadas. Não houve upload de ensaios nem alteração de workflow/SQL remoto.

## O que foi possível comprovar

- O arquivo versionado `planejamento_nos.json` seleciona Shorts por canal, views e janela de 60 dias, e grava `padroes_externos` com conflito por `(cell_id,video_id)`. O schema documentado contém gancho, virada, falas e outlier. São sinais úteis de audiência/conteúdo, mas faltam evidências de geometria, câmera, continuidade e pixel art. A configuração de categoria Comedy está nos nós do Planejamento; não é prova de que todo o Minerador ativo use a categoria.
- O comentário de `gancho.py:184` usa estatísticas históricas de `padroes_externos` para justificar critérios de gancho. Isso não é um consumidor SQL ao vivo. Não foi encontrada neste repositório a definição integral de todos os consumidores atuais de banco.
- Snapshot local coletado às 21:43 UTC de 29/10 listava o Minerador `fMgDq0e0BX05ljlc` ativo, atualizado em 23/10 às 07:12 UTC. Ativo não prova execução recente nem utilidade. Esse snapshot impede afirmar que ele simplesmente foi desligado.
- Snapshot local da Produção (sub) mostra versão `06526505-af64-46aa-873b-b1ab32eddec7`, draft/active iguais no momento do snapshot. O briefing citava outra versão anterior. Não republicamos nem sobrescrevemos esse estado.
- A API pública do GitHub confirmou o HEAD e a validação técnica anterior `40960935130` bem sucedida. Os jobs de render `40970255754`, `40971438851` e `40971371481`, no mesmo HEAD, terminaram com falha no passo Render. Não há logs autenticados nesta auditoria que permitam atribuir a causa. Isso não deve ser relatado como produção completamente saudável. Detalhes em `ci-auditada.json`.

## Acesso negado e o que continua pendente

O helper documentado `/tmp/videos_auto_vm.py`, pelo Python do ambiente do orquestrador, recebeu `PermissionError: rota não permitida para este processo` em `/vm/token`. A emissão de uma identidade nova para o gateway MCP também recebeu a mesma recusa. Não foram reutilizadas identidades revogadas nem credenciais de outros processos.

Sem acesso autorizado ao projeto canônico não foi possível consultar DAG ativo do Minerador, schedule/timezone, últimas execuções/erros, contagens e amostras reais de `padroes_externos`, quotas/custos históricos, consumidores SQL atuais nem configuração de visão na VM. Portanto **não há diagnóstico comprovado da causa de uma eventual interrupção operacional**. A inadequação do objetivo histórico para evolução gráfica é comprovável pelo contrato local; a causa de falhas/suspensão exige consulta ao vivo.

Para fechar essa parte, o operador com acesso ao gateway deve exportar, sem credenciais: definição active e draft do Minerador/consumidores, últimas 20 execuções com erros/duração, schema/índices e contagens por origem/motor/data, duplicatas por chave e uso diário de APIs. Comparar active/draft antes de qualquer publicação. O novo catálogo não depende desse acesso e não migra/destrói dados históricos.

## Inventário e lacunas

Os 14 estilos web estão registrados em `motor_web/estilos`; primitivas/contratos e auditoria visual anterior foram examinados. O painel histórico de sete estilos foi visto como histórico, não como nova captura do HEAD. Os três motores Python (palito_v5, palito_cutout e cartao) e o rig auxiliar palito_v4 foram inventariados por entradas de render e consumidores. A nova comparação cobre mecanismo e pixel; não representa nova aprovação estética de todos.

| Motor | Lacuna prioritária | Dependência/critério para próximo experimento |
|---|---|---|
| mecanismo | Silhueta axial e percurso curvo não representáveis por primitivas | Perfil/tubo deste incremento; conferir conexão, corte, interior e legibilidade |
| lowpoly | Contexto e ação genérica em enquadramento amplo | Contexto→detalhe com UI inteira, contato no evento |
| escala | Hierarquia entre comparação e medida | Medidas preservadas e âncora legível em transição |
| animal | Anatomia e articulação ainda simplificadas | Fixture com ombro/quadril, joelho/cotovelo e pé apoiado |
| orbita | Transições e escala esquemática | Data explícita, alvo/rótulo estáveis |
| micro | Causalidade e oclusão entre camadas | Percurso explícito, sem inferir eficácia científica |
| pixel | Atuação/contacto na grade; semântica acima de decoração | Digita/consome/entrega; objetos explícitos e replay sem ouro/dano falso |
| mangueira | Antecipação/contato em gag | Fixture original legível sem fala |
| silhueta | Separação tonal da ação e fundo | Três poses legíveis sem sobreposição confusa |
| mapa | Rotas e rótulos próximos | Faixas reservadas; dados geográficos preservados |
| linha_tempo | Densidade e duração de leitura | Texto integral, cronologia preservada |
| quiz | Contraste do desafio e revelação | Mesma resposta/posição; alvo legível ao final |
| fisica | Relação contato/trajetória/som | Conferir penetração e evento no frame de contato |
| enem | Hierarquia da explicação na lousa | Um conceito por beat e correspondência à frase |
| palito_v5 | Piloto narrado de fallback | Assets/voz reais; visemas, contato e área segura |
| palito_v4 (biblioteca) | Rig SVG partilhado; não é motor de vídeo independente | Ombro/alcance/contato via piloto de palito_v5/cutout |
| palito_cutout | Contato e recorte dependentes do elenco | Assets licenciados e narração reais do canal |
| cartao | Layout, leitura e composição por partes | Assets/fontes reais e tempo de leitura |

`palito_v4.py` é biblioteca de rig SVG (o próprio arquivo declara não renderizar vídeo). `placas.py`, `props*.py`, `folha_personagem.py`, `efeitos.py` são geradores/auxiliares; `esboco.py` é diagnóstico ASCII; `longo.py`, `job.py` e `motor_web/montar_web.py` são montagem/orquestração. Não os contamos como motores independentes para inflar cobertura. Dependem do backlog do motor consumidor; os legados sem assets não receberam uma comparação visual nova.

O backlog persistente contém propostas por todos os motores inventariados, com critérios, impacto/esforço/custo/confiança. No estado inicial há 19 propostas para 17 motores e o rig partilhado. O rótulo inicial de palito_v4 como motor/CLI foi corrigido no catálogo sem remover seu ID ou decisões; não é contado como motor independente. As prioridades altas são modelagem funcional do mecanismo, anatomia de animal e atuação semântica do pixel. O primeiro incremento foca o mecanismo; pixel é controle de preservação, não uma melhoria estética alegada.

## Pesquisa adicional de canais

Foram importadas 12 referências pesquisadas no pedido adicional do usuário, a partir de `CANAIS_REFERENCIA_MOTORES_2026-10-29.json`. `triagem-canais.md` registra prioridade editorial, motores e hipóteses de experimento. São metadados/declarações das fontes: sem reprodução integral, sem quadros analisados e sem timecodes inventados. O replay da importação inseriu zero duplicatas. Nenhuma coleta desses canais foi ativada e o backlog de oportunidades visuais revisadas continua com 19 itens.
