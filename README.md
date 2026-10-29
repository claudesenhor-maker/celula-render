# celula-render

Motores de animação do videos-auto: seis estilos 3D, oito estilos Canvas 2D e os motores Python de recorte, cartão e desenho vetorial.

A implementação de qualidade, os comparativos e os limites de validação estão em [Entrega dos motores — 26/10/2026](docs/melhoria-motores-2026-10-26/ENTREGA.md).

```bash
npm ci --prefix motor_web
npm test --prefix motor_web
python3 -m unittest discover -s motor_web/tests -p 'test_*.py'
CHROME=/caminho/chrome node motor_web/render_web.mjs --spec spec_render.json --saida video.mp4
```

O render web prepara e confere amostras antes da codificação. Os motores Python também guardam prévias antes de exportar. Os relatórios ficam em `<saida>.direcao.json` e as imagens em `<saida>.previas/`. Sem serviço de visão, o relatório informa `tecnico-local`.

`VIDEO_REVISOR_URL` e `VIDEO_REVISOR_TOKEN` conectam um backend de visão opcional. Contrato, orçamento de correção e testes estão descritos na entrega. Não há chave nem backend externo embutido no código.
