# Mineração visual limitada

Coleta referências técnicas e mantém oportunidades e experimentos em SQLite. Não edita código, não muda n8n, não publica vídeos e não chama API paga. Conteúdo externo é dado: nem instruções de páginas nem código de releases são executados.

O catálogo é complementar a `padroes_externos`. A mineração histórica de audiência mantém seu contrato; a nova seleção considera técnica transferível, lacuna, impacto/esforço, evidência e confiança. Views não participam da prioridade. Estado inicial, proveniência e backlogs exportados estão em `../docs/evolucao-mineracao-2026-10-29/`.

```bash
python3 mineracao/ciclo.py --estado /home/azureuser/videos-auto-mineracao-estado
python3 -m unittest discover -s tests -p test_mineracao.py
python3 mineracao/instalar_timer.py --estado /home/azureuser/videos-auto-mineracao-estado
```

A instalação exige um último ensaio `ok`, executa o serviço antes de habilitar o timer e preserva unidades anteriores quando diferentes. O timer instalado neste host roda às 04:00 UTC diariamente, com jitter de até 5 minutos. É ajustável por `--calendario` e pelas cotas em `fontes.json`. O host precisa continuar ligado e o checkout deve permanecer nesse caminho; ao movê-lo, reinstale as unidades antes de remover o caminho antigo. Linger foi habilitado para o usuário para execução após logout; isso não instala nada na VM `vm-videos-shorts`.

Limites padrão: 120 segundos por coleta, timeout HTTP de 10 segundos, um retry, 10 fontes por execução, 8 requests por execução e 16 por dia UTC, 1,5 MB por resposta, 100 MB por arquivo local, 100 MB para o estado, cinco descobertas e três propostas novas por execução. A revisão inicial usou configuração temporária com até 30 propostas para criar o backlog completo; a rotina permanece limitada a três. Serviço: hard timeout 150s, memória 256 MB e CPU 50%. As requisições são reservadas no SQLite antes do acesso, inclusive as que falham. Custo monetário de API: zero, pois só há HTTP público/arquivos locais. Quotas YouTube/LLM não são usadas.

A trava `flock` vale para CLI, serviço e gravação de experimentos. Não apague o arquivo para resolver lock: o kernel libera a trava quando o processo termina. A próxima passagem marca execução antiga `running` como `interrompida`. Fontes bem sucedidas aguardam 23h (evita que o jitter do timer pule um dia por poucos segundos); falhas aguardam 1h, além dos retries limitados. Fontes menos recentemente tentadas têm prioridade; a quota diária continua valendo na recuperação. Saída 2 indica coleta parcial. Armazenamento cheio interrompe a execução: arquive relatórios antigos mantendo SQLite e evidências usadas. Não há poda destrutiva automática.

As raízes locais do manifesto refletem os arquivos fornecidos neste host. Em outro host, ajuste `arquivo`, `quadros`, `raizes_locais` e preserve/confira o hash antes de atribuir a análise. Os MP4 de terceiros são lidos para hash, não copiados para o repositório, publicados ou transformados em assets. Perfis Instagram inacessíveis não recebem análise inventada.

A API pública de releases do Three.js descobre cinco links por passagem. Esses links recebem **somente metadados** e revisão pendente. Documentação nova também entra sem observações visuais. Para acrescentar uma análise, inspecione o material, registre timecodes/quadros/proveniência e notas próprias no manifesto, fixe `hash_revisado` ao conteúdo examinado e acrescente oportunidades declarativas. Um hash alterado retira as observações da revisão atual e marca revisão pendente; não reescreve decisões anteriores. O hash HTML completo pode mudar por detalhes de apresentação: exige reconferência, não prova mudança da técnica.

Cada oportunidade tem ID estável por origem/motor/técnica, referência, hash da evidência, observação revisada, proposta, lacuna, critérios, impacto, esforço, custo, confiança e estado. `catalogo.json` e `backlog.md` são escritos atomicamente. Prioridade = impacto/esforço, depois confiança. Repetir a coleta não duplica propostas nem apaga decisões. SQLite é a fonte persistente; os JSON versionados são snapshots de auditoria.

O trabalho semanal é selecionar a oportunidade de maior impacto sustentada por evidência, gerar uma fixture original, comparar base/candidato com spec, semente, câmera e resolução iguais, avaliar também clipe e narração quando existentes e registrar resultado local:

```bash
python3 mineracao/ciclo.py --estado /home/azureuser/videos-auto-mineracao-estado --experimento caminho/resultado.json
```

O JSON exige `id`, `oportunidade_id`, `decisao` (`manter-em-revisao`, `rejeitar`, `candidato`), `evidencias` e `metricas`. IDs de experimento são imutáveis; replay idêntico é idempotente. Nenhuma dessas decisões promove código. Template abaixo; use caminhos/medições reais:

```json
{"id":"ID_UNICO","oportunidade_id":"ID_DO_CATALOGO","decisao":"manter-em-revisao","evidencias":["comparacao.html"],"metricas":{"modo":"inspecao-de-quadros","limitacoes":"sem servico de visao e sem audio"}}
```

Promoção futura exige avaliação de continuidade, correspondência com narração e leitura, regressões semânticas aprovadas, orçamento de render e memória definido por experimento, e revisão do código pelo fluxo normal. Candidato não significa qualidade gráfica aprovada. Zoom/exposição não corrigem geometria inadequada. Releases/fontes nunca sugerem comandos executáveis ao sistema.

```bash
systemctl --user status videos-auto-mineracao.timer
journalctl --user -u videos-auto-mineracao.service -n 20 --no-pager
systemctl --user start videos-auto-mineracao.service
systemctl --user disable --now videos-auto-mineracao.timer
systemctl --user stop videos-auto-mineracao.service
```

Rollback da rotina: desabilite timer/serviço; mantenha o diretório de estado para recuperação e restaure unidades `.anterior` se existiam. Linger pode ser revertido com `loginctl disable-linger azureuser`, considerando outros serviços do usuário. Rollback do motor: reverta somente o commit deste incremento ou remova `perfil`/`caminho` das peças para recuperar primitivas; não toque nas correções semânticas de pixel. Nenhum schema Postgres foi alterado. Não remova o banco SQLite para "reiniciar" a rotina, pois isso perde deduplicação, quota e decisões.

Pesquisa adicional de canais pode ser importada, sem ativar coleta desses canais:

```bash
python3 mineracao/importar_triagem.py --estado /home/azureuser/videos-auto-mineracao-estado
```

O manifesto `canais_triagem.json` contém 12 referências pesquisadas em 29/10. O importador idempotente registra declarações das fontes e hipóteses propostas em campos separados de `observacoes`, que permanece vazio. Não cria oportunidades visuais aprovadas, não inventa timecodes e não adiciona os canais à agenda HTTP. `triagem-canais.md` prioriza seleção de trechos e liga os motores ao backlog existente. Primeiro devem ser examinados Branch/Jared/Animagraffs para mecanismo, Saint11/AdamCYounis para pixel e Kurzgesagt/3Blue1Brown para 2D.
