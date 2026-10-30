# Contrato do incremento

O mecanismo oferece agora dois campos opcionais por peça, mantendo `forma` como fallback:

```json
{"nome":"bulbo","forma":"esfera","perfil":[[0.17,-0.5],[0.17,-0.3],[0.5,0.15],[0,0.5]],"pos":[0,2,0],"tam":[1.65,1.9,1.65],"material":"vidro","cor":"#B8DCEB"}
```

`perfil` contém de 3 a 32 pares `[raio,y]`, com raio entre 0 e 2, pelo menos um raio positivo e Y crescente no intervalo -2..2, com passo mínimo .0001 para estabilidade numérica. O raio é interpolado por cúbica monótona em Y, com quatro amostras por intervalo, sem ultrapassar os raios dos controles; a superfície gira em Y com 48 segmentos. Há no máximo 125 amostras axiais por peça. `pos/tam/giro/pivo`, material, cortes, alvos e rótulos continuam aplicados à peça resultante.

```json
{"nome":"cano","forma":"tubo","caminho":[[-0.5,-0.5,0],[-0.5,0.5,0],[0.5,0.5,0]],"raio":0.05,"pos":[0,1,0],"tam":[1,1,1],"material":"metal","cor":"#C88752"}
```

`caminho` contém de 2 a 32 pontos `[x,y,z]` locais, componentes entre -2 e 2, sem pontos consecutivos iguais. `raio` entre .005 e .25. O rótulo de uma peça com caminho ancora no ponto de controle central da curva (com transformação de pivô/pose), evitando apontar para o vazio da origem do modelo. A curva Catmull-Rom centrípeta recebe 24..256 segmentos longitudinais e 12 radiais. Perfil e caminho são mutuamente exclusivos. Limites são verificados pelo diretor antes da preparação e pelo construtor de geometria no navegador. Não há execução de código, download de modelo nem crescimento de geometria por frame.

As geometrias pertencem à preparação e usam o descarte de cena existente. Geometria paramétrica com pivô não é clonada desnecessariamente. Peças antigas sem os novos campos continuam usando exatamente as formas existentes. A biblioteca Three.js permanece em r128.

Marcos opcionais por cena:

```json
{"ini":0,"fim":3,"acao":"mostra","marcos_visuais":[{"local_s":1.5,"evento":"revelacao"}]}
```

Até quatro marcos por cena; eventos: `antecipacao`, `contato`, `consequencia`, `revelacao`. O tempo local deve estar dentro da cena. A revisão coleta o marco e quadros vizinhos, priorizando também bordas de cortes, até o limite global. Muitos eventos exigem subamostragem: não há garantia de cobrir todos. Sem endpoint real, continua apenas revisão técnica de amostras. A exportação dos clipes da comparação não usa essa API de revisão.

Limites geométricos: não há tampas de seção, refração física, deformação animada de tubo, colisão termodinâmica nem garantia de ausência de autointerseção para qualquer caminho arbitrário. Modelos ainda precisam ser planejados e revisados; o contrato novo amplia a capacidade, não garante que a IA a utilize corretamente. O prompt local foi atualizado, mas não sincronizado automaticamente com o n8n inacessível.
