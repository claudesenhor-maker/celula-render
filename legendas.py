#!/usr/bin/env python3
"""
legendas — legenda queimada, palavra por palavra, no ritmo real da fala.

POR QUE ISTO EXISTE
    Short se assiste no mudo. Legenda nao e acessibilidade opcional aqui,
    e o que faz o video ser entendido antes de o espectador decidir subir
    o dedo -- e o formato "uma palavra estourando por vez" e o que segura
    atencao no feed. Estava listado como F5 no HANDOFF e nunca foi feito.

DE ONDE VEM O TEMPO
    O Edge-TTS devolve WordBoundary: para cada palavra sintetizada, o
    offset e a duracao em unidades de 100ns. Ou seja, o tempo exato de
    cada palavra ja existia -- `palito_cutout.render` simplesmente jogava
    fora as marcas (`_, dur = sintetizar(...)`). Nao se estima nada aqui,
    pelo mesmo motivo pelo qual a timeline vem da duracao real do audio:
    estimativa desincroniza, e legenda fora de sincronia e pior que
    legenda nenhuma.

    O ElevenLabs nao devolve marcas, e o Edge as vezes devolve audio sem
    nenhum WordBoundary. Nesses casos cai no reparto proporcional ao
    tamanho das palavras -- pior, mas ainda legivel, e nunca deixa o
    video mudo de texto.

COMO SE LE NA TELA
    Blocos de ate 3 palavras, porque uma palavra so obriga o olho a
    resetar a cada 300ms e a linha inteira vira parede de texto. Dentro do
    bloco, a palavra que esta soando fica em destaque -- e isso que da a
    leitura de "acompanhando a fala" sem precisar animar nada.
"""
import os
from PIL import Image, ImageDraw, ImageFont

# Fica ACIMA da faixa de baixo: no app do YouTube o titulo, o @canal e os
# botoes comem os ultimos ~18% da tela, e legenda embaixo demais e legenda
# tapada.
Y_RELATIVO = 0.74

COR_TEXTO = (255, 255, 255, 255)
COR_ATIVA = (255, 211, 77, 255)      # ambar: destaca sem competir com a pele
COR_BORDA = (16, 14, 12, 255)

# Fontes na ordem em que se acha uma: runner Ubuntu primeiro (e onde a
# producao roda), depois Windows (e onde se confere antes de gastar render).
CANDIDATAS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
]


def _fonte(tamanho):
    for c in CANDIDATAS:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, tamanho)
            except Exception:
                pass
    # load_default ignora o tamanho e sai minusculo; melhor uma legenda
    # feia que nenhuma, mas o log precisa dizer que foi por aqui
    print("[legenda] nenhuma fonte TTF encontrada; usando a fonte padrao do PIL")
    return ImageFont.load_default()


def _reparto(texto, inicio, dur):
    """Sem WordBoundary: divide a janela entre as palavras na proporcao do
    numero de letras. Palavra longa demora mais que palavra curta, e isso
    sozinho ja e melhor do que dividir por igual."""
    palavras = [p for p in texto.split() if p]
    if not palavras:
        return []
    total = sum(len(p) for p in palavras) or 1
    fora, t = [], inicio
    for p in palavras:
        d = dur * len(p) / total
        fora.append({"txt": p, "inicio": t, "fim": t + d})
        t += d
    return fora


class Legenda:
    """Pre-monta os blocos e desenha o que estiver no ar em cada instante.

    A fonte e carregada uma vez: `truetype` por frame custa mais que o
    desenho em si num video de 400 frames."""

    def __init__(self, largura, altura, tamanho=None, por_bloco=3):
        self.W, self.H = largura, altura
        self.tam = tamanho or int(altura * 0.038)     # ~73px em 1920
        self.fonte = _fonte(self.tam)
        self.borda = max(4, self.tam // 8)
        self.por_bloco = max(1, int(por_bloco))
        self.blocos = []

    def adicionar(self, texto, marcas, inicio_s, dur_s):
        """Acrescenta a fala de UM trecho, ja deslocada para o tempo global.

        `marcas` sao as do edge-tts (inicio_s/fim_s relativos ao trecho).
        Lista vazia cai no reparto proporcional."""
        if marcas:
            palavras = [{"txt": m.get("palavra", ""),
                         "inicio": inicio_s + float(m.get("inicio_s", 0.0)),
                         "fim": inicio_s + float(m.get("fim_s", 0.0))}
                        for m in marcas if m.get("palavra")]
        else:
            palavras = _reparto(texto, inicio_s, dur_s)
        if not palavras:
            return
        for i in range(0, len(palavras), self.por_bloco):
            grupo = palavras[i:i + self.por_bloco]
            self.blocos.append({"inicio": grupo[0]["inicio"],
                                "fim": grupo[-1]["fim"],
                                "palavras": grupo})

    def desenhar(self, quadro, t):
        """Queima na imagem o bloco que contem o instante `t` (segundos).

        Recebe e devolve o quadro RGB ja montado -- a legenda vai por cima
        de tudo, inclusive do personagem, que e como Short faz."""
        bloco = None
        for b in self.blocos:
            # a margem para tras segura o bloco no ar durante a pausa entre
            # palavras; sem ela a legenda pisca a cada respiro do TTS
            if b["inicio"] - 0.08 <= t <= b["fim"] + 0.28:
                bloco = b
                break
        if bloco is None:
            return quadro

        d = ImageDraw.Draw(quadro)
        textos = [p["txt"].upper() for p in bloco["palavras"]]
        espaco = d.textlength(" ", font=self.fonte)
        larguras = [d.textlength(s, font=self.fonte) for s in textos]
        total = sum(larguras) + espaco * (len(textos) - 1)

        # uma palavra muito longa nao pode vazar do quadro
        margem = self.W * 0.06
        if total > self.W - 2 * margem:
            escala = (self.W - 2 * margem) / total
            fonte = _fonte(max(18, int(self.tam * escala)))
            larguras = [d.textlength(s, font=fonte) for s in textos]
            espaco = d.textlength(" ", font=fonte)
            total = sum(larguras) + espaco * (len(textos) - 1)
        else:
            fonte = self.fonte

        x = (self.W - total) / 2.0
        y = self.H * Y_RELATIVO
        for s, larg, p in zip(textos, larguras, bloco["palavras"]):
            ativa = p["inicio"] - 0.02 <= t <= p["fim"] + 0.12
            d.text((x, y), s, font=fonte, anchor="lm",
                   fill=COR_ATIVA if ativa else COR_TEXTO,
                   stroke_width=self.borda, stroke_fill=COR_BORDA)
            x += larg + espaco
        return quadro
