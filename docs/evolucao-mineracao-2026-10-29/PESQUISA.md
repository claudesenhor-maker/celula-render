# Pesquisa primária e protocolo

Consulta em 29/10/2026. Não foi identificada a ferramenta usada pelos autores dos vídeos. A escolha de Three.js é uma implementação nossa de técnicas geométricas compatíveis com a versão r128 instalada.

| Fonte | Evidência e aplicação | Limite |
|---|---|---|
| [Three.js LatheGeometry](https://threejs.org/docs/pages/LatheGeometry.html) | Superfície axial em torno de Y a partir de um perfil. Aplicada ao pescoço/ombro/bulbo da lâmpada. | Documentação atual; construção conferida no código r128 local. Não gera modelo científico automaticamente. |
| [Three.js TubeGeometry](https://threejs.org/docs/pages/TubeGeometry.html) | Tubo ao longo de curva, segmentos controláveis. Aplicado a serpentina e caminho do fluxo compartilhado na fixture. | Curva estática; sem dobra animada, tampas físicas nem simulação termodinâmica. |
| [Three.js sombras](https://threejs.org/manual/pages/shadows.html) | Shadow maps repetem desenho da cena por luz; custo deve ser medido por passe. | Mantida a luz de sombra existente; adicionar luzes não foi usado como substituto de modelagem. |
| [Three.js cor](https://threejs.org/manual/pages/color-management.html) | Cálculo em espaço linear e saída de cor devem ser coerentes. | Preservada a conversão sRGB da versão instalada, sem transplantar API moderna. |
| [MDN Canvas: suavização](https://developer.mozilla.org/en-US/docs/Web/API/CanvasRenderingContext2D/imageSmoothingEnabled) | Ampliação sem suavização preserva bordas do pixel art. | Borda nítida não prova pose, contato ou coerência narrativa. |
| [MDN Canvas: otimização](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API/Tutorial/Optimizing_canvas) | Camadas e pré-render de conteúdo estático reduzem trabalho repetido. | Cache já existente deve preservar estado temporal. Melhor desempenho não é qualidade estética. |
| [Gemini: vídeo](https://ai.google.dev/gemini-api/docs/video-understanding) | Timestamps permitem perguntas localizadas; amostragem padrão pode perder movimento rápido. | Nenhuma chamada ao serviço realizada. Integração existente recebe imagens temporais, não comprova visão contínua. |
| [VBench, autores, 2023](https://arxiv.org/abs/2311.17982) | Avaliação separa dimensões como identidade, suavidade, cintilação e relações espaciais. | Usado para estruturar perguntas; VBench não foi instalado/executado e seus scores não são alegados. |
| [FFmpeg: filtros](https://ffmpeg.org/ffmpeg-filters.html) | Seleção temporal e decodificação permitem conferir artefatos exportados. | Decodificação correta é teste técnico, não aprovação visual. |
| [Releases oficiais Three.js](https://api.github.com/repos/mrdoob/three.js/releases?per_page=5) | Descoberta primária de versões, com links rastreáveis. | Títulos/metadados somente; release nova não implica que atualizar seja útil ou seguro. |

## Referências observáveis do usuário

As duas gravações locais foram verificadas por hash. A inspeção utilizou folhas de contato de 12 instantes de cada captura, fornecidas no workspace; os timecodes são da gravação de tela, não IDs/timestamps de um arquivo original do Instagram.

- `195402.mp4`: aos 17,5s observa-se o bulbo; aos 36,9s o close mostra filamento com rótulo e contexto espacial reduzido. Aos 1,9s há personagem/mesa. Técnicas transferíveis: silhueta axial reconhecível, passagem contexto→detalhe, rótulo ligado à peça. Não foi validada a física ou a fala.
- `195512.mp4`: aos 6,6s vê-se serpentina no ambiente; aos 14,5s/17,2s há close e percurso. Técnicas transferíveis: geometria contínua, conexão, percurso localizado. Assets e composição não foram copiados.
- `instagram.com/desmontandoomundo`: consulta web devolveu 429. `instagram.com/nocodeartur`: consulta falhou por cache miss. Não há análise visual nova desses perfis; o material local visível é de `desmontandoomundo`. Não atribuímos os exemplos a `nocodeartur`.

A lacuna mais relevante do mecanismo é funcional: uma esfera/cilindro genérico não descreve pescoço/ombro ou cano curvo conectado. O primeiro incremento trata dessa capacidade, sem prometer alcançar iluminação, direção de câmera, atuação ou acabamento das referências.

## Avaliação por experimento

1. Manter spec, semente, resolução, fps, navegador, dependências e sequência temporal iguais. O baseline deve ser o HEAD auditado, nunca uma versão escolhida por parecer pior. Os novos campos `perfil`/`caminho` ficam presentes nos dois specs: o motor antigo os ignora e usa `forma`; isso mede capacidade do motor, não melhoria de roteirização espontânea.
2. Conferir abertura, antecipação/contato/consequência ou revelação e os dois lados de cada corte. Até 16 amostras na revisão de produção; eventos explícitos têm prioridade dentro do limite. Na comparação de pesquisa há também clipes próprios de seis segundos a 12fps. Eles não validam movimento em 30fps nem narração.
3. Inspecionar silhueta, conexão, oclusão, legibilidade, articulação, área segura, continuidade espacial e correspondência ao texto. Registrar defeitos, sem substituí-los por contagem de peças. Para personagens e pixel, contato e semântica são critérios obrigatórios.
4. Medir tempo de preparação, média/p95 por quadro (inclui captura PNG), heap JS, recursos WebGL, erros e repetição temporal. Heap não inclui toda a memória do Chrome/GPU. A máquina tem outras cargas; o teste não é benchmark estatístico isolado.
5. Reprovar regressões semânticas e visuais relevantes. Priorizar análise de clipe com áudio real antes de promover. Sem serviço multimodal configurado e prova de resposta, declarar `técnico-local`; não gerar score fictício de qualidade nem aprovação por IA.
6. Registrar experimento/decisão no catálogo com links dos artefatos e limitações. Mudanças ficam para revisão. A promoção futura precisa de revisão humana/serviço autorizado, testes semânticos, comparação temporal e orçamento de recursos; qualquer regressão permite rollback restrito ao incremento.

O ciclo automatiza coleta, atualização idempotente, triagem por evidência revisada, prioridade e exportação de propostas. Novas fontes ainda exigem inspeção para produzir observações; experimentos e alterações de código exigem trabalho de engenharia. Não existe um agente autônomo alterando motores com sugestões de páginas.
