# Revisão dos motores 3D e pixel art — videos-auto

Data: 26/10/2026. Base local: `celula-render-retomada`, commit `c1c461f`.
Escopo: revisão técnica e direção de melhoria. Este documento não representa implementação nem atualização da produção.

## Referências e limites da comparação

Referências indicadas pelo dono:
- https://www.instagram.com/desmontandoomundo/
- https://www.instagram.com/nocodeartur/

A leitura direta de ambos os perfis foi bloqueada pelo Instagram nesta sessão. Não foi possível assistir aos vídeos; portanto, nenhuma característica visual específica é atribuída a esses criadores. Links de perfis também não identificam quais cenas o dono pretende usar como exemplo. A comparação de enquadramentos, animação e acabamento com as referências fica pendente de Reels acessíveis ou dos arquivos dos vídeos. Não usar estimativas externas de audiência ou receita como evidência de qualidade visual.

A direção proposta abaixo traduz o pedido de mais detalhes em requisitos verificáveis para o código existente. Os exemplos são propostas próprias, não descrições dos vídeos dos perfis.

## Diagnóstico principal

Aumentar segmentos e adicionar cenário já foi parcialmente feito em 23–24/10. O próximo salto deve ser tornar cada imagem específica para o assunto: silhueta reconhecível, peças com função, movimento que mostra a causa e a consequência, câmera no detalhe certo e informação legível no celular. Repetir a mesma órbita com mais polígonos não resolve essas lacunas.

Existem seis motores Three.js: `lowpoly`, `mecanismo`, `escala`, `animal`, `orbita` e `micro`. `pixel` usa Canvas 2D e buffer 180×320. `fisica` também é Canvas 2D: convém incluí-lo nas verificações de legibilidade e tempo, mas ele não é um motor 3D. Os outros estilos carregados no palco não instanciam WebGLRenderer.

## Achados e prioridades

| Prioridade | Evidência local | Consequência | Intervenção proposta |
|---|---|---|---|
| P1 | `comum.js`, `quadroComRitmo`: zoom raster de 1,08 sobre o canvas final; o destino não desativa suavização | Em pixel art, a ampliação deixa de respeitar a grade; também amplia HUD e texto em todos os motores | Separar mundo e interface; no pixel, câmera em coordenadas inteiras do buffer e ampliação inteira. Validar nitidez antes e depois do export |
| P1 | `mecanismo.js`, `corteEm`/`pose`: a casca vai a 0,14 de opacidade | É transparência, não seção geométrica; superfícies sobrepostas podem esconder a relação entre peças | Suportar corte real como opção, com acabamento da seção; manter transparência para visualização de raio X |
| P1 | `mecanismo.js`: peças na raiz, rotação no centro da própria geometria | Dobras e articulações não têm pivôs de montagem; movimentos de peças não são vinculados mecanicamente | Hierarquia de grupos, pivôs explícitos e relações de transmissão, com compatibilidade para specs antigas |
| P1 | `animal.js`: savana fixa, formas próprias, movimento inferido pelo nome da peça | Mesmo ambiente para espécies distintas e articulação pouco controlável | Habitat por espécie, pivôs e rig explícito; formas e materiais adequados à anatomia |
| P1 | `pixel.js`: cinco sprites-base, passos alterando texto das pernas, sem poses específicas por ação | Digitar, comer e dormir reutilizam a postura frontal; interação depende de objetos flutuando | Sprites de ação/direção, pontos de contato e estados de objeto; sombra de contato e camadas de cenário |
| P2 | `orbita.js`: `Date.now()` na inicialização do sistema | O mesmo spec pode mudar entre execuções em datas diferentes | Gravar data de referência no spec; mesma entrada deve reproduzir a mesma posição |
| P2 | `mecanismo.js`: modelo vazio apenas escreve aviso; animal sem partes recebe forma genérica; escala tem fallback de forma | Um render pode terminar tecnicamente e ainda entregar uma imagem pouco relacionada à fala | Validar identidade e peças essenciais antes do render; distinguir prévia de diagnóstico de vídeo apto a publicar |
| P2 | `U3.estudio`/`U3.material` usados em mecanismo, escala e micro; os demais possuem bases próprias | Regras de cor, material e iluminação divergem entre motores | Compartilhar infraestrutura com perfis por estilo; preservar o facetado intencional do low-poly e a iluminação espacial da órbita |
| P2 | `pixel.js`, `dialogo`: escreve todas as linhas resultantes sem limitar altura | Textos fora do orçamento visual podem ultrapassar a caixa | Medir linhas, reservar espaço do nome e paginar ou reprovar antes de exportar |
| P2 | `comum3d.js`: parede cilíndrica texturizada; texturas de material não aplicadas pela função `material` | Ambiente existe, mas profundidade e diferenciação de superfícies ainda são limitadas | Poucos elementos de cenário em volume e mapas procedurais discretos por material, sujeitos a orçamento de render |

P1 = primeira rodada de qualidade. P2 = consolidação. Esta prioridade representa impacto visual/técnico, não falha confirmada em todos os vídeos publicados.

## Melhorias por motor

### Mecanismo: tornar o funcionamento compreensível

Já existem peças nomeadas, materiais, sombra, vista explodida, fluxo e rótulos. O limite atual é 40 partes por modelo. Não elevar esse limite indiscriminadamente: instâncias, cache e nível de detalhe devem vir antes de modelos grandes.

Propor:
- Modelos de referência aprovados por assunto, com dimensões relativas, componentes obrigatórios e montagem plausível; o roteirista seleciona e parametriza o modelo.
- Grupos e pivôs para eixos, tampas, dobradiças, pistões e válvulas. Relações como duas engrenagens acopladas precisam compartilhar uma fase e respeitar sentido/razão de giro.
- Vista explodida com trajetórias e linhas-guia; a peça essencial permanece no campo de visão. Close calcula enquadramento pela peça, não apenas aproximação geral de 30%.
- Fluxo de entrada/saída, setas e legenda de cores. Os pontos atuais usam `depthTest: false`; oferecer modo raio X explícito e modo com oclusão para evitar leitura de fluxo atravessando paredes.
- Parafusos, juntas, espessura de parede, bordas e pequenas diferenças de acabamento apenas onde o plano mostra esses detalhes.

Piloto proposto: fechadura com corpo, cilindro, pinos, molas e lingueta. Sequência: objeto reconhecível → seção → chave alinhando pinos → giro → lingueta liberada → retorno ao objeto montado. Critério: compreender o desbloqueio no mudo, sem depender de uma frase sobreposta.

### Low-poly: cenários com função e animação com contato

Já há terreno procedural, construções, personagens, efeitos e sombras de contato. A escolha de Lambert e normais facetadas é uma otimização intencional para SwiftShader; não migrar tudo para material físico.

Propor silhuetas diferentes por personagem, cabeça/mãos mais expressivas, poses de antecipação e reação e contato dos pés com o terreno. Distribuir detalhe por planos: protagonista, objetos que participam da ação, contexto ao fundo. Empregar enquadramento aberto para contexto e close para consequência, evitando órbita contínua que esconde a ação.

Piloto: vento atingindo uma rua. Roupas, folhas e objetos leves respondem na mesma direção, pessoas se apoiam, um elemento fixo mantém a referência. Aprovar se a direção e o efeito do vento forem legíveis sem HUD.

### Escala: reconhecimento e proporção no mesmo plano

Já oferece modelos prontos, dimensões em metros, céu, chão e sombras. Há até 12 itens e 24 partes por item customizado. A resolução de profundidade e a legibilidade exigem cuidado ao misturar centímetros e milhares de quilômetros.

Propor detalhes distintivos por objeto, régua e silhueta humana persistentes quando úteis. Usar níveis de detalhe ligados ao tamanho projetado e transições com um objeto de referência comum. Cotas devem nomear a dimensão efetivamente normalizada: altura, comprimento ou maior dimensão. Não confundir o comentário inicial de altura com o comportamento aceito por `tamanho_m`.

Piloto: pessoa → ônibus → edifício. Aprovar com proporções preservadas durante a transição e rótulos visíveis, sem obrigar objetos pequenos a continuar legíveis numa vista geral de objetos gigantes.

### Animal: anatomia, habitat e locomoção

Atualmente normaliza o tamanho e compara com uma pessoa de 1,75 m. Usa até 30 partes, materiais facetados e classificações por nomes de patas/cauda/asas/boca; a rotação ocorre no centro das peças.

Propor modelos aprovados por família anatômica, com crânio, focinho/bico, olhos, orelhas, patas e cauda que tornem a espécie reconhecível. Criar pivôs em ombro/quadril/mandíbula, fases de passada por membro e contato dos pés. Habitat selecionado por espécie: terrestre, aquático, floresta, gelo etc. Diferenciar pele, pelo, escama, pena e olho com recursos compatíveis com o perfil de custo.

Piloto: felino correndo, primeiro em silhueta e depois com material. Aprovar identificação do animal e locomoção coerente antes de acrescentar cartões de estatísticas.

### Órbita: superfícies, iluminação e escala explicitada

Já há esferas de 64×32 segmentos, texturas procedurais, inclinação, anéis e comparação entre corpos. O ganho principal deve vir de superfícies e apresentação; não é falta de subdivisões.

Propor relevo visual e crateras legíveis em close; nuvens e atmosfera em camadas leves; terminador dia/noite coerente e anéis com iluminação apropriada. Identificar claramente diagramas com distâncias comprimidas ou tamanhos mínimos ampliados: `rSis`, `tamSis` e `palcoOrbita` usam representações ajustadas para leitura. Fixar a data no spec e registrar a fonte/versão dos dados para reprodução. Não aplicar ambiente de estúdio a planetas.

Piloto: Terra/Lua com alternância entre comparação de diâmetro e distância. Aprovar identificação da mudança de escala; não apresentar posição orbital aproximada como efeméride precisa.

### Micro: estrutura em camadas com linguagem visual própria

Já usa a base comum, células/camadas, folículo, gota e partículas. Há três rótulos principais de camadas. O material padrão deriva de plástico, cerâmica, tecido e vidro; a cena ainda pode transmitir aparência de maquete.

Propor perfis de tecido/fluido próprios, variação sutil de rugosidade e cor, bordas da seção bem definidas e caminho do ativo com alvo claro. Contraste entre estrutura e efeito deve sobreviver à redução para celular. Diferenciar representação esquemática de escala anatômica. Mudanças em penetração/efeito precisam de revisão de conteúdo e fontes do roteiro; acabamento visual não valida a explicação científica.

Piloto: gota na superfície → aproximação das camadas → destino indicado → efeito visual localizado, mantendo a continuidade espacial.

### Pixel art: riqueza na grade, atuação e interação

Manter a grade-base 180×320 e verificar ampliação inteira de 6× na saída 1080×1920. Mais detalhe deve resultar de desenho e animação na grade, com paleta organizada e silhuetas legíveis. O HUD pode continuar em resolução final, desde que preserve a linguagem visual e não seja ampliado junto do mundo.

Propor:
- Sprites de frente/lado/costas e poses próprias de digitar, comer, dormir, receber, atacar e reagir. Ciclos de 4–6 quadros quando melhorarem a leitura.
- Mão com ponto de encaixe para objeto; cadeira, cama, mesa e chão com contato coerente. Som e queda de HP/ouro no instante da ação.
- Tiles com rodapé, batentes, móveis, objetos de uso e sombra seletiva. Parallax de camadas com deslocamento inteiro, sem desfocar.
- Pequenas animações ambientais: vapor de café, monitor, relógio, luz e NPCs. Limitar a competição visual com a piada principal.
- Caixas medidas por texto e nome do falante; orçamento de leitura compatível com duração e CPS_LEITURA já usado na montagem.
- Efeito CRT opcional e discreto; avaliar a imagem após H.264, pois scanlines e detalhes de um pixel podem perder contraste.

Piloto: herói digitando → chega cobrança → pega o café → energia reage → chefe chama reunião. Aprovar mãos/objetos conectados, texto integral dentro da caixa, grade nítida e mudança do HUD sincronizada.

## Contrato de dados a evoluir

A alteração não pode ficar apenas no renderer: vocabulário/configuração, geração do roteiro, validação, montagem do spec e prévia precisam aceitar o mesmo contrato. `config_gerado.py` é artefato gerado: localizar a fonte canônica antes de alterar regras. A cópia local de `roteiros.json` contém apenas os quatro estilos iniciais; a origem dos prompts dos motores mais novos precisa ser rastreada antes da implementação.

Campos propostos, ainda não implementados: versão do spec, perfil de qualidade, data de referência, `parent`/`pivo`/relação mecânica nas peças, plano com alvo e margem segura, habitat/rig e pose/direção do sprite. Dados antigos devem continuar funcionando. Não adicionar campos ao prompt enquanto renderer e validador não os suportarem.

## Ordem de execução recomendada

1. Fixar fixtures de referência e registrar a imagem atual. Corrigir composição da interface/zoom e grade de pixel art; validar texto e modelos vazios.
2. Fazer os pilotos de mecanismo e pixel, pois expõem diretamente as limitações de peças/interação. Medir imagem e custo antes/depois.
3. Extrair infraestrutura comum comprovada pelos pilotos: composição, enquadramento, orçamento de detalhe e recursos reutilizáveis, com perfis distintos por motor.
4. Aplicar os pilotos de animal, low-poly, escala, órbita e micro, nessa ordem ajustável conforme os canais prioritários.
5. Comparar os pilotos com os Reels fornecidos; aprovar o padrão visual; só depois alterar a esteira de geração e distribuição.

## Critérios de aceitação

- Mesmo spec e instante produzem o mesmo PNG, inclusive após solicitar outros instantes. Data externa deve virar entrada explícita.
- Objeto/espécie/evento reconhecível sem legenda; detalhe principal visível no tamanho de celular.
- Nenhuma mão, pé ou peça que precise de contato flutuando na ação aprovada; corte e fluxo coerentes com a explicação.
- Título, HUD, rótulos e legendas com zonas reservadas, sem colisão entre si nem corte pela composição final.
- Pixel art sem suavização ou deslocamento fracionário do mundo; verificar PNG e vídeo exportado.
- Prévia com abertura, quadro de detalhe, transição e desfecho; render amostrado não substitui ver o vídeo e ouvir o áudio.
- Medir p50/p95 de tempo por quadro, memória e duração total em uma sequência representativa. Meta inicial proposta: não exceder 20% sobre o baseline do mesmo motor no mesmo runner, salvo ganho aprovado. Não tratar esse orçamento como medição já obtida.
- Preservar o resultado dos testes existentes e testar casos que realmente usam os recursos novos. Vídeos de produção exigem specs reais além das fixtures sintéticas.

## Evidências reproduzíveis

`capturar.mjs` cria um spec sintético por motor e captura 0, 1,5, 4,5 e 6 segundos em 1080×1920; repete 1,5 s após 6 s para detectar dependência da ordem. As peças dos exemplos são propositalmente mínimas: não representam a qualidade de um roteiro real nem uma comparação justa de complexidade entre motores. O teste não usa TTS nem publica vídeos.

Execução a partir da raiz do repositório:

```bash
CHROME=/caminho/para/chrome node docs/revisao-visual-2026-10-26/capturar.mjs
```

Os tempos de `resultados.json` incluem render, leitura e codificação PNG no navegador local com SwiftShader. São amostras de diagnóstico, não benchmark de throughput nem estimativa de custo de produção. A checagem de igualdade vale para os instantes exercitados na mesma inicialização; não comprova reprodução entre datas, máquinas ou drivers.

## Resultado da auditoria local

Foram renderizados 28 quadros de amostra (quatro por motor), além da repetição de 1,5 s em cada motor. Não houve `pageerror` nos sete exemplos. Os seis testes existentes passaram: três de ritmo/composição e três de sentido visual.

| Motor | Repetição de 1,5 s após avançar até 6 s | Diagnóstico |
|---|---|---|
| lowpoly | PNG idêntico | Sem divergência nesta fixture |
| mecanismo | PNG idêntico | Sem divergência nesta fixture |
| escala | PNG idêntico | Sem divergência nesta fixture |
| animal | PNG idêntico | Sem divergência nesta fixture |
| orbita | PNG idêntico | Esta checagem não cobre mudança de data na criação |
| micro | PNG diferente | P1: investigar estado/renderização antes de usar quadros isolados como evidência do vídeo |
| pixel | PNG idêntico | A saída final está com `imageSmoothingEnabled: true` |

A divergência de micro é um achado adicional ao exame estático: a causa ainda não está isolada. Não atribuir o resultado a uma função específica sem uma reprodução mais estreita. O verificador registra a divergência no JSON; não constitui teste de aprovação automática nem encerra o processo com falha por esse motivo.

Na amostra pixel, a captura de 1,5 s também mostra o HUD encostando na margem esquerda após o zoom e o herói em postura frontal junto à mesa durante `digita`. Isso reforça a necessidade de separar interface/mundo e desenhar poses de interação. As quatro capturas por motor e o painel `painel-atual.jpg` permitem revisar o baseline. Não houve exportação MP4/áudio nesta revisão; a verificação se restringe ao renderer e aos testes locais.
