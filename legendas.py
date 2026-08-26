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

O QUE MUDOU EM 29/08
    1. TAMANHO. A legenda ocupava 3,8% da altura e no feed, num telefone,
       ela competia em tamanho com a costura da camisa do personagem.
       Passou para 4,8% -- que e a faixa em que os canais de corte de
       podcast trabalham -- e a palavra que esta soando cresce mais 12%.
    2. A ULTIMA PALAVRA. No video de 28/08 o punchline ("bloqueado") ficou
       sem legenda: o edge-tts devolveu 9 WordBoundary para uma fala de 10
       palavras, e o codigo confiava cegamente na contagem de marcas. Uma
       fala pode perder qualquer palavra pelo caminho, mas perder a ULTIMA
       e perder a piada. Agora o texto manda: `_casar` garante uma entrada
       por palavra escrita, estimando o tempo das que faltarem.
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
COR_SOMBRA = (0, 0, 0, 150)

# A palavra que esta soando e desenhada maior. O destaque so por cor
# desaparece quando o fundo do quadro e claro (a rua de 28/08 e rosa), e
# tamanho e uma diferenca que sobrevive a qualquer cenario.
ESCALA_ATIVA = 1.12

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


def _so_letras(s):
    return "".join(c for c in s.lower() if c.isalnum())


def _casar(texto, marcas, inicio, dur):
    """Uma entrada por PALAVRA ESCRITA, custe o que custar.

    O texto e a verdade sobre o que tem que aparecer na tela; as marcas sao
    a melhor informacao sobre QUANDO. Quando as duas discordam -- e elas
    discordam, o edge-tts perdeu a ultima palavra da fala de 28/08 -- quem
    ganha e o texto: legenda com tempo estimado ainda se le, legenda que
    nao existe custou o punchline.

    Casamento guloso, em ordem: cada palavra do texto procura a proxima
    marca que combine com ela (comparando so letras e numeros, porque a
    marca vem sem pontuacao). Palavra sem marca fica com tempo INTERPOLADO
    entre a marca anterior e a proxima -- ou, no fim da fala, entre a
    ultima marca e o fim do audio."""
    palavras = [p for p in texto.split() if p]
    if not palavras:
        return []
    marcas = [m for m in (marcas or []) if m.get("palavra")]
    if not marcas:
        return _reparto(texto, inicio, dur)

    fora, j = [], 0
    for p in palavras:
        alvo = _so_letras(p)
        achou = None
        # janela curta: a marca certa esta logo adiante, e procurar ate o
        # fim faria a palavra "de" casar com um "de" tres frases depois
        for k in range(j, min(j + 3, len(marcas))):
            if _so_letras(marcas[k].get("palavra", "")) == alvo and alvo:
                achou = k
                break
        if achou is None:
            fora.append({"txt": p, "inicio": None, "fim": None})
        else:
            m = marcas[achou]
            fora.append({"txt": p,
                         "inicio": inicio + float(m.get("inicio_s", 0.0)),
                         "fim": inicio + float(m.get("fim_s", 0.0))})
            j = achou + 1

    # tempo das que ficaram sem marca, por interpolacao entre as vizinhas
    fim_fala = inicio + max(dur, 0.05)
    ancoras = [(i, w) for i, w in enumerate(fora) if w["inicio"] is not None]
    if not ancoras:
        return _reparto(texto, inicio, dur)
    for i, w in enumerate(fora):
        if w["inicio"] is not None:
            continue
        antes = [a for a in ancoras if a[0] < i]
        depois = [a for a in ancoras if a[0] > i]
        t0 = antes[-1][1]["fim"] if antes else inicio
        t1 = depois[0][1]["inicio"] if depois else fim_fala
        n = (depois[0][0] if depois else len(fora)) - (antes[-1][0] + 1 if antes else 0)
        passo = max((t1 - t0) / max(n, 1), 0.12)
        k = i - (antes[-1][0] + 1 if antes else 0)
        w["inicio"] = t0 + passo * k
        w["fim"] = w["inicio"] + passo
    return fora


class Legenda:
    """Pre-monta os blocos e desenha o que estiver no ar em cada instante.

    A fonte e carregada uma vez: `truetype` por frame custa mais que o
    desenho em si num video de 400 frames."""

    def __init__(self, largura, altura, tamanho=None, por_bloco=3):
        self.W, self.H = largura, altura
        self.tam = tamanho or int(altura * 0.048)     # ~92px em 1920
        self.fonte = _fonte(self.tam)
        self.fonte_ativa = _fonte(int(self.tam * ESCALA_ATIVA))
        self.borda = max(5, self.tam // 7)
        self.por_bloco = max(1, int(por_bloco))
        self.blocos = []

    def adicionar(self, texto, marcas, inicio_s, dur_s):
        """Acrescenta a fala de UM trecho, ja deslocada para o tempo global.

        `marcas` sao as do edge-tts (inicio_s/fim_s relativos ao trecho).
        Quem manda no QUE aparece e o texto; as marcas mandam no QUANDO --
        ver `_casar`."""
        palavras = _casar(texto, marcas, inicio_s, dur_s)
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
        ativas = [p["inicio"] - 0.02 <= t <= p["fim"] + 0.12 for p in bloco["palavras"]]

        # A LARGURA E MEDIDA COM A FONTE QUE SERA USADA em cada palavra: a
        # ativa cresce 12%, e medir todas com a fonte normal faria o bloco
        # inteiro escorregar para a direita a cada troca de palavra ativa --
        # legenda que anda sozinha e mais chamativa que o destaque.
        fontes = [self.fonte_ativa if a else self.fonte for a in ativas]
        espaco = d.textlength(" ", font=self.fonte)
        larguras = [d.textlength(s, font=f) for s, f in zip(textos, fontes)]
        total = sum(larguras) + espaco * (len(textos) - 1)

        # uma palavra muito longa nao pode vazar do quadro
        margem = self.W * 0.06
        util = self.W - 2 * margem
        if total > util:
            escala = util / total
            fontes = [_fonte(max(18, int(self.tam * ESCALA_ATIVA * escala))) if a
                      else _fonte(max(18, int(self.tam * escala))) for a in ativas]
            espaco = d.textlength(" ", font=fontes[0])
            larguras = [d.textlength(s, font=f) for s, f in zip(textos, fontes)]
            total = sum(larguras) + espaco * (len(textos) - 1)

        x = (self.W - total) / 2.0
        y = self.H * Y_RELATIVO
        desl = max(3, self.tam // 16)
        for s, larg, f, ativa in zip(textos, larguras, fontes, ativas):
            # sombra deslocada: o contorno preto sozinho some quando o
            # cenario atras e escuro (o onibus), e a sombra descola o texto
            # do fundo em vez de so cerca-lo
            d.text((x + desl, y + desl), s, font=f, anchor="lm",
                   fill=COR_SOMBRA, stroke_width=self.borda, stroke_fill=COR_SOMBRA)
            d.text((x, y), s, font=f, anchor="lm",
                   fill=COR_ATIVA if ativa else COR_TEXTO,
                   stroke_width=self.borda, stroke_fill=COR_BORDA)
            x += larg + espaco
        return quadro
