# -*- coding: utf-8 -*-
"""placas.py -- texto DENTRO da cena: documento, carimbo, letreiro,
calendario, relogio, nota de dinheiro, etiqueta, balao, X, ?, seta.

    PLANO-ENCAIXE.md §3.5. E' o cartaz do titulo (`legendas.Titulo`) virando
    familia: o mesmo papel creme, o mesmo contorno preto dos bonecos, a mesma
    fonte -- e o TEXTO que o roteiro pediu, gerado na hora, sem IA e sem
    rembg. Cada placa sai com ancoras (`pega` para a mao, `base` para o chao,
    `gravidade` para ficar em pe') e entra no mesmo caminho de qualquer
    objeto.

    O tamanho e' em pixels da MAIOR dimensao; quem chama decide a escala
    contra a altura do ator (lei 38) ou do quadro.
"""
import math

from PIL import Image, ImageDraw, ImageFilter

from legendas import (_fonte_titulo, _fonte, TITULO_PAPEL, TITULO_TINTA,
                      TITULO_CONTORNO, TITULO_DESTAQUE, TITULO_SOMBRA)

VERMELHO = (214, 48, 40, 255)
AMARELO = (247, 196, 48, 255)
AZUL = (40, 80, 160, 255)
VERDE = (60, 150, 80, 255)
VERDE_NOTA = (98, 160, 92, 255)
CINZA = (120, 120, 120, 255)
BRANCO = (252, 252, 250, 255)

# texto que nao coube na caixa da placa (lido por `ferramentas/regua_cartao.py`)
ESTOUROS = []


def _estourou(onde, texto, larg_texto, larg_caixa):
    if larg_texto > larg_caixa + 1:
        ESTOUROS.append(f"{onde} '{texto}' {larg_texto:.0f}px em {larg_caixa:.0f}px")

# A LISTA DE TIPOS VIVE NO FIM DO ARQUIVO, derivada de `GERADORES` (18/09).
#
# Ela era escrita a mao aqui e ja estava desatualizada: `tela` e `painel`
# entraram em `GERADORES` em 16/09 (a serie do Madrazzo -- metade das
# historias passa por um app ou um visor) e ninguem as acrescentou nesta
# tupla. Quem lesse `TIPOS` para saber o que o motor desenha -- foi o que o
# `ferramentas/ideia.py` fez -- ofereceria ao roteiro 14 placas quando o
# motor sabe 16. Duas listas da mesma coisa e' um lugar para apodrecer, e
# esta apodreceu em nove dias.


def _cont(tam):
    return max(4, int(tam * 0.028))


def _quebrar(texto, fonte, larg_max):
    linhas, atual = [], ""
    for p in str(texto).split():
        tenta = (atual + " " + p).strip()
        if fonte.getlength(tenta) <= larg_max or not atual:
            atual = tenta
        else:
            linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    return linhas


def _texto_centrado(d, caixa, texto, tam_fonte, cor=TITULO_TINTA, negrito=True,
                    destaque_numeros=True, max_linhas=3):
    """Escreve `texto` centrado na caixa (x0,y0,x1,y1), encolhendo a fonte
    ate' caber em `max_linhas`. Numeros saem na cor de destaque."""
    x0, y0, x1, y1 = caixa
    larg, alt = x1 - x0, y1 - y0

    def _tentar(n_max):
        t = int(tam_fonte)
        while True:
            fonte = _fonte_titulo(t) if negrito else _fonte(t)
            linhas = _quebrar(texto, fonte, larg * 0.94)
            alt_l = int(t * 1.12)
            if len(linhas) <= n_max and alt_l * len(linhas) <= alt * 0.96 \
                    and all(fonte.getlength(l) <= larg * 0.94 for l in linhas):
                return t, fonte, linhas, alt_l, True
            if t <= 10:
                return t, fonte, linhas, alt_l, False
            t = max(10, int(t * 0.9))

    # O TEXTO CABE NA CAIXA, SEMPRE (25/09, dono: *"muitas caixas com texto
    # estourado"*). O laco parava na fonte 10 e desenhava o que tivesse --
    # palavra comprida numa caixa estreita saia pela borda da placa. Agora:
    # 1) as linhas pedidas; 2) mais duas linhas; 3) o texto e' desenhado a
    # parte e REDUZIDO ate' caber. Estouro nunca chega a tela.
    t, fonte, linhas, alt_l, ok = _tentar(max_linhas)
    if not ok:
        t, fonte, linhas, alt_l, ok = _tentar(max_linhas + 2)
    alvo = d
    ox, oy = x0, y0
    tela_txt = None
    if not ok:
        lw = max(fonte.getlength(l) for l in linhas) if linhas else 1
        tela_txt = Image.new("RGBA", (int(lw) + 4, alt_l * len(linhas) + 4), (0, 0, 0, 0))
        alvo = ImageDraw.Draw(tela_txt)
        ox, oy = 2, 2
        larg_d, alt_d = lw, alt_l * len(linhas)
    else:
        larg_d, alt_d = larg, alt
    y = oy + (alt_d - alt_l * len(linhas)) / 2.0
    esp = fonte.getlength(" ")
    for l in linhas:
        w = fonte.getlength(l)
        x = ox + (larg_d - w) / 2.0
        for pal in l.split(" "):
            c = cor
            if destaque_numeros and any(ch.isdigit() for ch in pal):
                c = TITULO_DESTAQUE
            alvo.text((x, y), pal, font=fonte, fill=c)
            x += fonte.getlength(pal) + esp
        y += alt_l
    if tela_txt is not None:
        k = min(larg * 0.94 / tela_txt.width, alt * 0.94 / tela_txt.height)
        pq = tela_txt.resize((max(1, int(tela_txt.width * k)), max(1, int(tela_txt.height * k))), Image.LANCZOS)
        base = getattr(d, "_image", None)
        if base is not None:
            base.alpha_composite(pq, (int(x0 + (larg - pq.width) / 2.0), int(y0 + (alt - pq.height) / 2.0)))
        else:
            ESTOUROS.append(f"texto '{texto}' sem tela para reduzir")
        t = int(t * k)
    return t


def _sombra(tela, caixa, raio, dy):
    s = Image.new("RGBA", tela.size, (0, 0, 0, 0))
    x0, y0, x1, y1 = caixa
    ImageDraw.Draw(s).rounded_rectangle([x0 + dy // 2, y0 + dy, x1 + dy // 2, y1 + dy],
                                        radius=raio, fill=TITULO_SOMBRA)
    return s.filter(ImageFilter.GaussianBlur(max(2, dy // 2)))


# ---------------------------------------------------------------------
def documento(texto, tam=520, titulo=None, carimbo=None):
    """Folha de papel com titulo, linhas rabiscadas e um carimbo opcional.
    `texto` vira o titulo se `titulo` nao for dado."""
    W_, H_ = int(tam * 0.78), int(tam)
    m = int(tam * 0.06)
    tela = Image.new("RGBA", (W_ + 2 * m, H_ + 2 * m), (0, 0, 0, 0))
    caixa = (m, m, m + W_, m + H_)
    tela.alpha_composite(_sombra(tela, caixa, int(tam * 0.02), int(tam * 0.03)))
    d = ImageDraw.Draw(tela)
    d.rounded_rectangle(caixa, radius=int(tam * 0.02), fill=BRANCO,
                        outline=TITULO_CONTORNO, width=_cont(tam))
    # cabecalho
    cab = (m + int(W_ * 0.08), m + int(H_ * 0.06), m + int(W_ * 0.92), m + int(H_ * 0.26))
    _texto_centrado(d, cab, (titulo or texto).upper(), int(tam * 0.10), max_linhas=2)
    d.line([cab[0], cab[3] + 4, cab[2], cab[3] + 4], fill=TITULO_TINTA, width=max(3, _cont(tam) - 1))
    # linhas de texto rabiscado
    y = cab[3] + int(H_ * 0.08)
    esp = int(H_ * 0.075)
    n = 0
    while y < m + H_ * 0.80 and n < 7:
        larg = W_ * (0.74 if n % 3 else 0.60)
        xa = m + int(W_ * 0.10)
        pts = []
        for i in range(0, int(larg), max(6, int(tam * 0.02))):
            pts.append((xa + i, y + (2.5 if (i // 12) % 2 else -2.5)))
        if len(pts) > 1:
            d.line(pts, fill=(90, 90, 90, 255), width=max(2, _cont(tam) - 2))
        y += esp
        n += 1
    if texto and titulo:
        corpo = (m + int(W_ * 0.08), m + int(H_ * 0.30), m + int(W_ * 0.92), m + int(H_ * 0.58))
        d.rectangle(corpo, fill=BRANCO)
        _texto_centrado(d, corpo, texto.upper(), int(tam * 0.085), max_linhas=3)
    if carimbo:
        c, _ = globals()["carimbo"](carimbo, tam=int(tam * 0.62))
        tela.alpha_composite(c, (m + int(W_ * 0.5) - c.width // 2,
                                 m + int(H_ * 0.72) - c.height // 2))
    anc = {"pega": [m + W_ * 0.5, m + H_ * 0.92], "base": [m + W_ * 0.5, m + H_],
           "gravidade": True, "z": "frente"}
    return tela, anc


def carimbo(texto, tam=420, cor=VERMELHO, rot=-12.0):
    """Retangulo vermelho inclinado, texto vazado, moldura dupla."""
    fonte_tam = int(tam * 0.24)
    fonte = _fonte_titulo(fonte_tam)
    larg_t = fonte.getlength(texto.upper())
    while larg_t > tam * 0.86 and fonte_tam > 12:
        fonte_tam = int(fonte_tam * 0.9)
        fonte = _fonte_titulo(fonte_tam)
        larg_t = fonte.getlength(texto.upper())
    W_ = int(larg_t + tam * 0.18)
    H_ = int(fonte_tam * 1.75)
    m = int(tam * 0.18)
    tela = Image.new("RGBA", (W_ + 2 * m, H_ + 2 * m), (0, 0, 0, 0))
    d = ImageDraw.Draw(tela)
    e = max(4, int(tam * 0.022))
    d.rounded_rectangle([m, m, m + W_, m + H_], radius=int(H_ * 0.18),
                        outline=cor, width=e)
    d.rounded_rectangle([m + e * 2, m + e * 2, m + W_ - e * 2, m + H_ - e * 2],
                        radius=int(H_ * 0.14), outline=cor, width=max(2, e // 2))
    d.text(((tela.width - larg_t) / 2.0, m + (H_ - fonte_tam * 1.05) / 2.0),
           texto.upper(), font=fonte, fill=cor)
    # textura de tinta: pontinhos claros apagando o carimbo por cima
    import random
    from PIL import ImageChops
    rnd = random.Random(len(texto) * 7 + 3)
    furos = Image.new("L", tela.size, 255)
    dt = ImageDraw.Draw(furos)
    for _ in range(int(tam * 0.9)):
        px_, py_ = rnd.randint(0, tela.width - 1), rnd.randint(0, tela.height - 1)
        r = rnd.randint(1, max(2, tam // 140))
        dt.ellipse([px_ - r, py_ - r, px_ + r, py_ + r], fill=90)
    tela.putalpha(ImageChops.multiply(tela.getchannel("A"), furos))
    tela = tela.rotate(rot, resample=Image.BICUBIC, expand=True)
    anc = {"pega": [tela.width / 2.0, tela.height * 0.85],
           "base": [tela.width / 2.0, float(tela.height)], "gravidade": True,
           "z": "frente", "sem_contorno": True}
    return tela, anc


def letreiro(texto, tam=600, cor=AMARELO, cor_texto=TITULO_TINTA, poste=False):
    """Placa retangular com contorno grosso (a placa da loja, o aviso)."""
    W_ = int(tam)
    H_ = int(tam * 0.36)
    m = int(tam * 0.05)
    alt_poste = int(tam * 0.35) if poste else 0
    tela = Image.new("RGBA", (W_ + 2 * m, H_ + 2 * m + alt_poste), (0, 0, 0, 0))
    d = ImageDraw.Draw(tela)
    if poste:
        d.rectangle([tela.width // 2 - int(tam * 0.03), m + H_,
                     tela.width // 2 + int(tam * 0.03), m + H_ + alt_poste],
                    fill=(110, 110, 110, 255), outline=TITULO_CONTORNO, width=_cont(tam) - 1)
    tela.alpha_composite(_sombra(tela, (m, m, m + W_, m + H_), int(tam * 0.02), int(tam * 0.025)))
    d = ImageDraw.Draw(tela)
    d.rounded_rectangle([m, m, m + W_, m + H_], radius=int(tam * 0.03), fill=cor,
                        outline=TITULO_CONTORNO, width=_cont(tam))
    _texto_centrado(d, (m + int(W_ * 0.05), m + int(H_ * 0.08), m + int(W_ * 0.95), m + int(H_ * 0.92)),
                    texto.upper(), int(H_ * 0.52), cor=cor_texto, max_linhas=2,
                    destaque_numeros=(cor_texto == TITULO_TINTA))
    anc = {"pega": [tela.width / 2.0, m + H_ * 0.9], "base": [tela.width / 2.0, float(tela.height)],
           "gravidade": True, "z": "frente",
           "sockets": {"texto": {"rect": [[m, m], [m + W_, m + H_]]}}}
    return tela, anc


def calendario(texto, tam=520, numero=None):
    """Folha de calendario: faixa vermelha em cima, o texto grande, e um
    numero circulado quando `numero` vier."""
    W_ = H_ = int(tam)
    m = int(tam * 0.06)
    tela = Image.new("RGBA", (W_ + 2 * m, H_ + 2 * m), (0, 0, 0, 0))
    tela.alpha_composite(_sombra(tela, (m, m, m + W_, m + H_), int(tam * 0.03), int(tam * 0.03)))
    d = ImageDraw.Draw(tela)
    d.rounded_rectangle([m, m, m + W_, m + H_], radius=int(tam * 0.04), fill=BRANCO,
                        outline=TITULO_CONTORNO, width=_cont(tam))
    d.rounded_rectangle([m, m, m + W_, m + int(H_ * 0.22)], radius=int(tam * 0.04), fill=VERMELHO)
    d.rectangle([m, m + int(H_ * 0.12), m + W_, m + int(H_ * 0.22)], fill=VERMELHO)
    d.line([m, m + int(H_ * 0.22), m + W_, m + int(H_ * 0.22)], fill=TITULO_CONTORNO, width=_cont(tam))
    # argolas
    for fx in (0.28, 0.72):
        x = m + int(W_ * fx)
        d.rounded_rectangle([x - int(tam * 0.03), m - int(tam * 0.04), x + int(tam * 0.03), m + int(tam * 0.08)],
                            radius=int(tam * 0.02), fill=(200, 200, 200, 255), outline=TITULO_CONTORNO, width=3)
    _texto_centrado(d, (m + int(W_ * 0.06), m + int(H_ * 0.26), m + int(W_ * 0.94), m + int(H_ * 0.62)),
                    texto.upper(), int(tam * 0.16), max_linhas=2)
    # grade de dias
    gx0, gy0 = m + int(W_ * 0.10), m + int(H_ * 0.66)
    cel = int(W_ * 0.115)
    for r in range(2):
        for c in range(7):
            x, y = gx0 + c * cel, gy0 + r * cel
            d.rectangle([x, y, x + cel - 4, y + cel - 4], outline=(150, 150, 150, 255), width=2)
    if numero is not None:
        try:
            k = int(numero) % 14
        except Exception:                                    # noqa: BLE001
            k = 3
        x, y = gx0 + (k % 7) * cel, gy0 + (k // 7) * cel
        d.ellipse([x - 6, y - 6, x + cel + 2, y + cel + 2], outline=VERMELHO, width=max(4, _cont(tam)))
    anc = {"pega": [tela.width / 2.0, m + H_ * 0.9], "base": [tela.width / 2.0, float(tela.height)],
           "gravidade": True, "z": "frente"}
    return tela, anc


def relogio(texto="", tam=460, hora=10.0, minutos=10.0):
    W_ = H_ = int(tam)
    m = int(tam * 0.05)
    tela = Image.new("RGBA", (W_ + 2 * m, H_ + 2 * m), (0, 0, 0, 0))
    d = ImageDraw.Draw(tela)
    cx = cy = m + W_ / 2.0
    R = W_ / 2.0
    d.ellipse([m, m, m + W_, m + H_], fill=VERMELHO if not texto else AZUL,
              outline=TITULO_CONTORNO, width=_cont(tam))
    d.ellipse([m + int(R * 0.14), m + int(R * 0.14), m + W_ - int(R * 0.14), m + H_ - int(R * 0.14)],
              fill=BRANCO, outline=TITULO_CONTORNO, width=max(3, _cont(tam) - 2))
    fonte = _fonte_titulo(int(tam * 0.09))
    for h in range(1, 13):
        a = math.radians(h * 30 - 90)
        x, y = cx + math.cos(a) * R * 0.70, cy + math.sin(a) * R * 0.70
        s = str(h)
        w = fonte.getlength(s)
        d.text((x - w / 2, y - tam * 0.05), s, font=fonte, fill=TITULO_TINTA)
    for ang_, comp, esp in ((hora % 12 * 30 + minutos * 0.5 - 90, R * 0.45, _cont(tam) + 2),
                            (minutos * 6 - 90, R * 0.62, _cont(tam))):
        a = math.radians(ang_)
        d.line([cx, cy, cx + math.cos(a) * comp, cy + math.sin(a) * comp],
               fill=TITULO_TINTA, width=esp)
    d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=TITULO_TINTA)
    if texto:
        _texto_centrado(d, (m + int(W_ * 0.25), m + int(H_ * 0.60), m + int(W_ * 0.75), m + int(H_ * 0.78)),
                        texto.upper(), int(tam * 0.08), max_linhas=1)
    anc = {"pega": [cx, cy + R * 0.9], "base": [cx, float(tela.height)], "gravidade": True, "z": "frente"}
    return tela, anc


def nota(texto, tam=560):
    """Nota de dinheiro com o valor nos cantos e no centro."""
    W_ = int(tam)
    H_ = int(tam * 0.45)
    m = int(tam * 0.05)
    tela = Image.new("RGBA", (W_ + 2 * m, H_ + 2 * m), (0, 0, 0, 0))
    tela.alpha_composite(_sombra(tela, (m, m, m + W_, m + H_), int(tam * 0.02), int(tam * 0.02)))
    d = ImageDraw.Draw(tela)
    d.rounded_rectangle([m, m, m + W_, m + H_], radius=int(tam * 0.02), fill=VERDE_NOTA,
                        outline=TITULO_CONTORNO, width=_cont(tam))
    d.rounded_rectangle([m + int(W_ * 0.05), m + int(H_ * 0.10), m + W_ - int(W_ * 0.05), m + H_ - int(H_ * 0.10)],
                        radius=int(tam * 0.015), outline=(40, 90, 50, 255), width=max(2, _cont(tam) - 2))
    # o medalhao do meio
    r = int(H_ * 0.30)
    d.ellipse([m + W_ // 2 - r, m + H_ // 2 - r, m + W_ // 2 + r, m + H_ // 2 + r],
              fill=(150, 200, 150, 255), outline=(40, 90, 50, 255), width=3)
    # NOS CANTOS SO' O VALOR (25/09): a frase inteira nos quatro cantos saia
    # pela borda da nota ("MUITO DINHEIRO" com 240 px numa faixa de 127).
    # Nota de verdade traz o numero no canto; sem numero, o canto fica liso.
    import re as _re
    num = _re.findall(r"\d[\d.,]*", texto)
    s = num[0] if num else ""
    if s:
        tf = int(H_ * 0.16)
        fonte = _fonte_titulo(tf)
        while fonte.getlength(s) > W_ * 0.26 and tf > 8:
            tf = int(tf * 0.9)
            fonte = _fonte_titulo(tf)
        w = fonte.getlength(s)
        _estourou("nota.canto", s, w, W_ * 0.30)
        for (fx, fy) in ((0.18, 0.20), (0.82, 0.20), (0.18, 0.80), (0.82, 0.80)):
            d.text((m + W_ * fx - w / 2, m + H_ * fy - tf * 0.56), s, font=fonte, fill=(30, 60, 35, 255))
    # sem numero o TEXTO e' o dado: ocupa a nota inteira, com fundo claro
    # ("MUITO DINHEIRO" no medalhao de 40% saia em letra de rodape)
    caixa_c = (m + int(W_ * 0.30), m + int(H_ * 0.30), m + int(W_ * 0.70), m + int(H_ * 0.70))
    if not s:
        caixa_c = (m + int(W_ * 0.10), m + int(H_ * 0.18), m + int(W_ * 0.90), m + int(H_ * 0.82))
        d.rounded_rectangle(caixa_c, radius=int(H_ * 0.12), fill=(150, 200, 150, 255), outline=(40, 90, 50, 255), width=3)
    _texto_centrado(d, caixa_c,
                    texto.upper(), int(H_ * 0.34), cor=(30, 60, 35, 255), max_linhas=2,
                    destaque_numeros=False)
    anc = {"pega": [m + W_ * 0.5, m + H_ * 0.8], "base": [m + W_ * 0.5, float(tela.height)],
           "gravidade": False, "z": "frente"}
    return tela, anc


def etiqueta(texto, tam=420):
    """Etiqueta de preco pendurada."""
    W_ = int(tam)
    H_ = int(tam * 0.5)
    m = int(tam * 0.06)
    tela = Image.new("RGBA", (W_ + 2 * m, H_ + 2 * m + int(tam * 0.18)), (0, 0, 0, 0))
    d = ImageDraw.Draw(tela)
    y0 = m + int(tam * 0.18)
    pts = [(m, y0 + H_ * 0.5), (m + W_ * 0.22, y0), (m + W_, y0), (m + W_, y0 + H_),
           (m + W_ * 0.22, y0 + H_)]
    d.polygon(pts, fill=AMARELO, outline=TITULO_CONTORNO)
    d.line(pts + [pts[0]], fill=TITULO_CONTORNO, width=_cont(tam))
    d.ellipse([m + W_ * 0.14 - 10, y0 + H_ * 0.5 - 10, m + W_ * 0.14 + 10, y0 + H_ * 0.5 + 10],
              fill=BRANCO, outline=TITULO_CONTORNO, width=3)
    d.line([m + W_ * 0.14, y0 + H_ * 0.5, m + W_ * 0.14, m], fill=TITULO_CONTORNO, width=3)
    _texto_centrado(d, (m + int(W_ * 0.30), y0 + int(H_ * 0.10), m + int(W_ * 0.95), y0 + int(H_ * 0.90)),
                    texto.upper(), int(H_ * 0.5), max_linhas=2)
    anc = {"pega": [m + W_ * 0.14, m], "base": [m + W_ * 0.5, float(tela.height)],
           "gravidade": True, "z": "frente"}
    return tela, anc


def balao(texto, tam=520, rabo="baixo_esq"):
    """Balao de fala com uma ou duas palavras -- o "AMEACA!" do Madrazzo."""
    fonte_tam = int(tam * 0.22)
    fonte = _fonte_titulo(fonte_tam)
    linhas = _quebrar(texto.upper(), fonte, tam * 0.9)
    larg = max(fonte.getlength(l) for l in linhas) + tam * 0.22
    alt = fonte_tam * 1.2 * len(linhas) + tam * 0.18
    m = int(tam * 0.06)
    rabo_h = int(tam * 0.16)
    tela = Image.new("RGBA", (int(larg) + 2 * m, int(alt) + 2 * m + rabo_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(tela)
    caixa = [m, m, m + larg, m + alt]
    d.rounded_rectangle(caixa, radius=int(alt * 0.35), fill=BRANCO, outline=TITULO_CONTORNO, width=_cont(tam))
    # o rabo
    if rabo.endswith("esq"):
        bx = m + larg * 0.25
        pts = [(bx - tam * 0.05, m + alt - 4), (bx + tam * 0.08, m + alt - 4), (bx - tam * 0.09, m + alt + rabo_h)]
    else:
        bx = m + larg * 0.75
        pts = [(bx - tam * 0.08, m + alt - 4), (bx + tam * 0.05, m + alt - 4), (bx + tam * 0.09, m + alt + rabo_h)]
    d.polygon(pts, fill=BRANCO)
    d.line([pts[0], pts[2], pts[1]], fill=TITULO_CONTORNO, width=_cont(tam))
    d.line([pts[0], pts[1]], fill=BRANCO, width=_cont(tam) + 2)
    y = m + (alt - fonte_tam * 1.2 * len(linhas)) / 2.0
    for l in linhas:
        w = fonte.getlength(l)
        d.text((m + (larg - w) / 2.0, y), l, font=fonte, fill=TITULO_TINTA)
        y += fonte_tam * 1.2
    anc = {"pega": [pts[2][0], pts[2][1]], "base": [pts[2][0], float(pts[2][1])],
           "gravidade": True, "z": "frente", "sem_contorno": True}
    return tela, anc


def x(texto="", tam=420):
    m = int(tam * 0.08)
    tela = Image.new("RGBA", (int(tam) + 2 * m, int(tam) + 2 * m), (0, 0, 0, 0))
    d = ImageDraw.Draw(tela)
    e = max(10, int(tam * 0.13))
    for (a, b) in (((m, m), (m + tam, m + tam)), ((m + tam, m), (m, m + tam))):
        d.line([a, b], fill=TITULO_CONTORNO, width=e + _cont(tam) * 2)
    for (a, b) in (((m, m), (m + tam, m + tam)), ((m + tam, m), (m, m + tam))):
        d.line([a, b], fill=VERMELHO, width=e)
    anc = {"pega": [tela.width / 2.0, tela.height * 0.9], "base": [tela.width / 2.0, float(tela.height)],
           "gravidade": True, "z": "frente", "sem_contorno": True}
    return tela, anc


def _simbolo(ch, tam, cor):
    fonte = _fonte_titulo(int(tam * 1.0))
    w = fonte.getlength(ch)
    m = int(tam * 0.10)
    tela = Image.new("RGBA", (int(w) + 2 * m, int(tam * 1.15) + 2 * m), (0, 0, 0, 0))
    d = ImageDraw.Draw(tela)
    e = _cont(tam) + 2
    for dx in range(-e, e + 1, 2):
        for dy in range(-e, e + 1, 2):
            if dx * dx + dy * dy <= e * e:
                d.text((m + dx, m + dy - tam * 0.08), ch, font=fonte, fill=TITULO_CONTORNO)
    d.text((m, m - tam * 0.08), ch, font=fonte, fill=cor)
    anc = {"pega": [tela.width / 2.0, tela.height * 0.9], "base": [tela.width / 2.0, float(tela.height)],
           "gravidade": True, "z": "frente", "sem_contorno": True}
    return tela, anc


def interrogacao(texto="", tam=460):
    return _simbolo("?", tam, AMARELO)


def exclamacao(texto="", tam=460):
    return _simbolo("!", tam, VERMELHO)


def check(texto="", tam=420):
    m = int(tam * 0.1)
    tela = Image.new("RGBA", (int(tam) + 2 * m, int(tam) + 2 * m), (0, 0, 0, 0))
    d = ImageDraw.Draw(tela)
    cx = cy = m + tam / 2.0
    d.ellipse([m, m, m + tam, m + tam], fill=VERDE, outline=TITULO_CONTORNO, width=_cont(tam))
    pts = [(cx - tam * 0.25, cy), (cx - tam * 0.07, cy + tam * 0.18), (cx + tam * 0.27, cy - tam * 0.2)]
    d.line(pts, fill=BRANCO, width=max(8, int(tam * 0.09)), joint="curve")
    if texto:
        # dentro do circulo, medido (25/09: "TUDO CERTO" com 369 px num
        # circulo de 262 -- o texto saia pelos lados do selo)
        _texto_centrado(d, (m + tam * 0.20, m + tam * 0.66, m + tam * 0.80, m + tam * 0.88),
                        texto.upper(), int(tam * 0.16), cor=BRANCO, destaque_numeros=False, max_linhas=1)
    anc = {"pega": [cx, tela.height * 0.9], "base": [cx, float(tela.height)], "gravidade": True, "z": "frente"}
    return tela, anc


def seta(texto="", tam=460, sentido="direita"):
    m = int(tam * 0.08)
    W_, H_ = int(tam), int(tam * 0.5)
    tela = Image.new("RGBA", (W_ + 2 * m, H_ + 2 * m), (0, 0, 0, 0))
    d = ImageDraw.Draw(tela)
    h = H_ / 2.0
    pts = [(m, m + h * 0.6), (m + W_ * 0.6, m + h * 0.6), (m + W_ * 0.6, m), (m + W_, m + h),
           (m + W_ * 0.6, m + H_), (m + W_ * 0.6, m + h * 1.4), (m, m + h * 1.4)]
    d.polygon(pts, fill=AMARELO)
    d.line(pts + [pts[0]], fill=TITULO_CONTORNO, width=_cont(tam), joint="curve")
    if sentido == "esquerda":
        tela = tela.transpose(Image.FLIP_LEFT_RIGHT)
    anc = {"pega": [tela.width / 2.0, tela.height * 0.9], "base": [tela.width / 2.0, float(tela.height)],
           "gravidade": True, "z": "frente", "sem_contorno": True}
    return tela, anc


def cartaz(texto, tam=640):
    """O mesmo papel do titulo, solto na cena (uma frase curta)."""
    W_ = int(tam)
    fonte_tam = int(tam * 0.11)
    fonte = _fonte_titulo(fonte_tam)
    linhas = _quebrar(texto.upper(), fonte, W_ * 0.86)
    H_ = int(fonte_tam * 1.25 * len(linhas) + tam * 0.12)
    m = int(tam * 0.06)
    tela = Image.new("RGBA", (W_ + 2 * m, H_ + 2 * m), (0, 0, 0, 0))
    tela.alpha_composite(_sombra(tela, (m, m, m + W_, m + H_), int(tam * 0.02), int(tam * 0.025)))
    d = ImageDraw.Draw(tela)
    d.rounded_rectangle([m, m, m + W_, m + H_], radius=int(tam * 0.025), fill=TITULO_PAPEL,
                        outline=TITULO_CONTORNO, width=_cont(tam))
    _texto_centrado(d, (m + int(W_ * 0.05), m + int(H_ * 0.06), m + int(W_ * 0.95), m + int(H_ * 0.94)),
                    texto.upper(), fonte_tam, max_linhas=3)
    anc = {"pega": [tela.width / 2.0, m + H_ * 0.9], "base": [tela.width / 2.0, float(tela.height)],
           "gravidade": True, "z": "frente"}
    return tela, anc


def tela(texto, tam=560, titulo=None, cor=(62, 96, 160, 255)):
    """CELULAR com uma tela: o app de aposta, a mensagem, o resultado.
    (16/09, serie minerada: metade das historias do canal passa por um
    aplicativo.) `titulo` e' a faixa de cima (nome do app/remetente); o
    texto vai no meio, grande, numeros em destaque."""
    H_ = int(tam)
    W_ = int(tam * 0.52)
    m = int(tam * 0.05)
    t = Image.new("RGBA", (W_ + 2 * m, H_ + 2 * m), (0, 0, 0, 0))
    t.alpha_composite(_sombra(t, (m, m, m + W_, m + H_), int(tam * 0.07), int(tam * 0.02)))
    d = ImageDraw.Draw(t)
    r = int(tam * 0.07)
    d.rounded_rectangle([m, m, m + W_, m + H_], radius=r, fill=(36, 36, 42, 255),
                        outline=TITULO_CONTORNO, width=_cont(tam))
    b = int(tam * 0.035)
    d.rounded_rectangle([m + b, m + b * 2, m + W_ - b, m + H_ - b * 2], radius=int(r * 0.6), fill=BRANCO)
    # o entalhe e o botao
    d.rounded_rectangle([m + W_ * 0.35, m + b, m + W_ * 0.65, m + b * 2.2], radius=b, fill=(36, 36, 42, 255))
    y_faixa = m + b * 2
    if titulo:
        d.rectangle([m + b, y_faixa, m + W_ - b, y_faixa + int(tam * 0.11)], fill=cor)
        _texto_centrado(d, (m + b, y_faixa, m + W_ - b, y_faixa + int(tam * 0.11)),
                        str(titulo).upper(), int(tam * 0.055), cor=BRANCO, destaque_numeros=False, max_linhas=1)
        y_faixa += int(tam * 0.11)
    _texto_centrado(d, (m + b * 2, y_faixa + b, m + W_ - b * 2, m + H_ - b * 3),
                    str(texto).upper(), int(tam * 0.085), max_linhas=4)
    anc = {"pega": [t.width / 2.0, m + H_ * 0.8], "base": [t.width / 2.0, float(t.height)],
           "gravidade": True, "z": "frente"}
    return t, anc


def painel(texto, tam=520, cor_fundo=(30, 30, 34, 255), cor_texto=(240, 60, 50, 255)):
    """VISOR de numeros (bomba de gasolina, caixa, placar): fundo escuro,
    digitos vermelhos, moldura clara."""
    W_ = int(tam)
    H_ = int(tam * 0.46)
    m = int(tam * 0.05)
    t = Image.new("RGBA", (W_ + 2 * m, H_ + 2 * m), (0, 0, 0, 0))
    t.alpha_composite(_sombra(t, (m, m, m + W_, m + H_), int(tam * 0.03), int(tam * 0.02)))
    d = ImageDraw.Draw(t)
    d.rounded_rectangle([m, m, m + W_, m + H_], radius=int(tam * 0.03), fill=(200, 200, 196, 255),
                        outline=TITULO_CONTORNO, width=_cont(tam))
    b = int(tam * 0.045)
    d.rounded_rectangle([m + b, m + b, m + W_ - b, m + H_ - b], radius=int(tam * 0.02), fill=cor_fundo,
                        outline=TITULO_CONTORNO, width=max(3, _cont(tam) // 2))
    _texto_centrado(d, (m + b * 2, m + b, m + W_ - b * 2, m + H_ - b), str(texto),
                    int(tam * 0.22), cor=cor_texto, destaque_numeros=False, max_linhas=1)
    anc = {"pega": [t.width / 2.0, m + H_ * 0.8], "base": [t.width / 2.0, float(t.height)],
           "gravidade": True, "z": "frente"}
    return t, anc


# ---------------------------------------------------------------------
# PECAS NOVAS (25/09, dono: *"pouca variacao de pecas"*). A copia de 43
# cartoes usava 12 pecas e o calendario 7 vezes. Estas sao as ALTERNATIVAS
# que `cartao._variar_pecas` troca quando um tipo se repete -- e o roteiro
# pode pedir direto: ampulheta (espera), recibo (conta, compra), envelope
# (carta, intimacao), grafico (subiu/caiu), post_it (lembrete, bilhete),
# alerta (perigo, aviso).
def ampulheta(texto="", tam=460):
    """Ampulheta com areia caindo; `texto` numa faixa embaixo (o prazo)."""
    W_, H_ = int(tam * 0.62), int(tam)
    m = int(tam * 0.06)
    # a faixa do prazo e' LARGA e alta: "TRES MESES DEPOIS" numa faixa da
    # largura do vidro saia em letra de rodape (folha da regua, 25/09)
    faixa = int(tam * 0.36) if texto else 0
    larg_f = int(tam * 1.0)
    m_x = max(m, (larg_f - W_) // 2 + m // 2) if texto else m
    tela_ = Image.new("RGBA", (W_ + 2 * m_x, H_ + 2 * m + faixa), (0, 0, 0, 0))
    m0 = m
    m = m_x
    m_y = m0
    d = ImageDraw.Draw(tela_)
    c = _cont(tam)
    madeira = (150, 96, 52, 255)
    tampa = int(H_ * 0.09)
    for y in (m_y, m_y + H_ - tampa):
        d.rounded_rectangle([m, y, m + W_, y + tampa], radius=int(tampa * 0.3), fill=madeira,
                            outline=TITULO_CONTORNO, width=c)
    cx = m + W_ / 2.0
    ya, yb = m_y + tampa, m_y + H_ - tampa
    ym = (ya + yb) / 2.0
    lv = W_ * 0.40
    vidro = [(cx - lv, ya), (cx + lv, ya), (cx + W_ * 0.05, ym), (cx + lv, yb), (cx - lv, yb), (cx - W_ * 0.05, ym)]
    d.polygon(vidro, fill=(226, 240, 246, 255))
    areia = (236, 190, 90, 255)
    d.polygon([(cx - lv * 0.55, ya + (ym - ya) * 0.45), (cx + lv * 0.55, ya + (ym - ya) * 0.45),
               (cx + W_ * 0.04, ym - 2), (cx - W_ * 0.04, ym - 2)], fill=areia)
    d.polygon([(cx - lv * 0.92, yb - 2), (cx + lv * 0.92, yb - 2), (cx, yb - (yb - ym) * 0.55)], fill=areia)
    d.line([(cx, ym), (cx, yb - (yb - ym) * 0.5)], fill=areia, width=max(3, c // 2))
    d.line(vidro + [vidro[0]], fill=TITULO_CONTORNO, width=c, joint="curve")
    for sx in (-1, 1):
        d.rectangle([cx + sx * W_ * 0.46 - c, ya, cx + sx * W_ * 0.46 + c, yb], fill=madeira,
                    outline=TITULO_CONTORNO, width=max(2, c // 2))
    if texto:
        yf = m_y + H_ + int(tam * 0.02)
        fx0, fx1 = 4, tela_.width - 4
        d.rounded_rectangle([fx0, yf, fx1, yf + faixa - 4], radius=int(faixa * 0.2),
                            fill=TITULO_PAPEL, outline=TITULO_CONTORNO, width=c)
        _texto_centrado(d, (fx0 + 10, yf + 6, fx1 - 10, yf + faixa - 10), texto.upper(), int(faixa * 0.40), max_linhas=2)
    anc = {"pega": [tela_.width / 2.0, tela_.height * 0.9], "base": [tela_.width / 2.0, float(tela_.height)],
           "gravidade": True, "z": "frente"}
    return tela_, anc


def recibo(texto, tam=520):
    """Cupom fiscal comprido, borda serrilhada, TOTAL no pe'."""
    W_, H_ = int(tam * 0.56), int(tam)
    m = int(tam * 0.06)
    tela_ = Image.new("RGBA", (W_ + 2 * m, H_ + 2 * m), (0, 0, 0, 0))
    tela_.alpha_composite(_sombra(tela_, (m, m, m + W_, m + H_), 4, int(tam * 0.02)))
    d = ImageDraw.Draw(tela_)
    dente = max(6, int(W_ / 12))
    pts = [(m, m)]
    for k in range(12):
        pts += [(m + dente * k + dente / 2.0, m + dente * 0.5), (m + dente * (k + 1), m)]
    pts += [(m + W_, m + H_)]
    for k in range(12):
        pts += [(m + W_ - dente * k - dente / 2.0, m + H_ - dente * 0.5), (m + W_ - dente * (k + 1), m + H_)]
    d.polygon(pts, fill=BRANCO)
    d.line(pts + [pts[0]], fill=TITULO_CONTORNO, width=_cont(tam), joint="curve")
    y = m + H_ * 0.10
    for k in range(6):
        larg = W_ * (0.70 if k % 2 else 0.50)
        d.line([(m + W_ * 0.12, y), (m + W_ * 0.12 + larg, y)], fill=(120, 120, 120, 255), width=max(3, _cont(tam) - 2))
        d.line([(m + W_ * 0.80, y), (m + W_ * 0.88, y)], fill=(120, 120, 120, 255), width=max(3, _cont(tam) - 2))
        y += H_ * 0.075
    d.line([(m + W_ * 0.08, m + H_ * 0.60), (m + W_ * 0.92, m + H_ * 0.60)], fill=TITULO_TINTA, width=3)
    _texto_centrado(d, (m + W_ * 0.08, m + H_ * 0.62, m + W_ * 0.92, m + H_ * 0.90), texto.upper(),
                    int(tam * 0.10), max_linhas=2)
    anc = {"pega": [tela_.width / 2.0, m + H_ * 0.9], "base": [tela_.width / 2.0, float(tela_.height)],
           "gravidade": True, "z": "frente"}
    return tela_, anc


def envelope(texto, tam=520):
    """Envelope fechado com selo; `texto` e' o remetente/assunto."""
    W_, H_ = int(tam), int(tam * 0.62)
    m = int(tam * 0.06)
    tela_ = Image.new("RGBA", (W_ + 2 * m, H_ + 2 * m), (0, 0, 0, 0))
    tela_.alpha_composite(_sombra(tela_, (m, m, m + W_, m + H_), int(tam * 0.02), int(tam * 0.025)))
    d = ImageDraw.Draw(tela_)
    papel = (244, 232, 206, 255)
    c = _cont(tam)
    d.rounded_rectangle([m, m, m + W_, m + H_], radius=int(tam * 0.02), fill=papel, outline=TITULO_CONTORNO, width=c)
    d.line([(m, m), (m + W_ / 2.0, m + H_ * 0.52), (m + W_, m)], fill=TITULO_CONTORNO, width=c, joint="curve")
    r = int(H_ * 0.10)
    d.ellipse([m + W_ / 2.0 - r, m + H_ * 0.52 - r, m + W_ / 2.0 + r, m + H_ * 0.52 + r],
              fill=VERMELHO, outline=TITULO_CONTORNO, width=max(3, c - 2))
    _texto_centrado(d, (m + W_ * 0.10, m + H_ * 0.66, m + W_ * 0.90, m + H_ * 0.94), texto.upper(),
                    int(H_ * 0.18), max_linhas=1)
    anc = {"pega": [tela_.width / 2.0, m + H_ * 0.9], "base": [tela_.width / 2.0, float(tela_.height)],
           "gravidade": True, "z": "frente"}
    return tela_, anc


def grafico(texto="", tam=520, sentido=None):
    """Quadro com barras e a linha: sobe (verde) ou cai (vermelho). O
    sentido sai do texto (cai/caiu/perde/down) quando nao vem."""
    if sentido is None:
        t_ = str(texto).lower()
        sentido = "cai" if any(p in t_ for p in ("cai", "caiu", "desc", "perd", "queda", "down", "drop", "fall", "lost")) \
            else "sobe"
    W_, H_ = int(tam), int(tam * 0.78)
    m = int(tam * 0.06)
    tela_ = Image.new("RGBA", (W_ + 2 * m, H_ + 2 * m), (0, 0, 0, 0))
    tela_.alpha_composite(_sombra(tela_, (m, m, m + W_, m + H_), int(tam * 0.02), int(tam * 0.025)))
    d = ImageDraw.Draw(tela_)
    c = _cont(tam)
    d.rounded_rectangle([m, m, m + W_, m + H_], radius=int(tam * 0.03), fill=BRANCO, outline=TITULO_CONTORNO, width=c)
    cor = VERDE if sentido == "sobe" else VERMELHO
    alt_t = int(H_ * 0.24) if texto else 0
    base_y = m + H_ * 0.90
    topo = m + H_ * 0.08 + alt_t
    alturas = (0.30, 0.48, 0.62, 0.88) if sentido == "sobe" else (0.88, 0.62, 0.42, 0.20)
    lb = W_ * 0.13
    pts = []
    for k, h in enumerate(alturas):
        x = m + W_ * (0.16 + 0.21 * k)
        y = base_y - (base_y - topo) * h
        d.rectangle([x, y, x + lb, base_y], fill=cor, outline=TITULO_CONTORNO, width=max(3, c - 2))
        pts.append((x + lb / 2.0, y - H_ * 0.04))
    d.line(pts, fill=TITULO_CONTORNO, width=c + 2, joint="curve")
    d.line([(m + W_ * 0.08, base_y), (m + W_ * 0.94, base_y)], fill=TITULO_CONTORNO, width=c)
    if texto:
        _texto_centrado(d, (m + W_ * 0.06, m + H_ * 0.04, m + W_ * 0.94, m + H_ * 0.04 + alt_t), texto.upper(),
                        int(alt_t * 0.7), max_linhas=1)
    anc = {"pega": [tela_.width / 2.0, m + H_ * 0.9], "base": [tela_.width / 2.0, float(tela_.height)],
           "gravidade": True, "z": "frente"}
    return tela_, anc


def post_it(texto, tam=460, cor=(252, 226, 90, 255)):
    """Bilhete adesivo meio torto, escrito a mao (fonte comum)."""
    L = int(tam)
    m = int(tam * 0.08)
    tela_ = Image.new("RGBA", (L + 2 * m, L + 2 * m), (0, 0, 0, 0))
    tela_.alpha_composite(_sombra(tela_, (m, m, m + L, m + L), 4, int(tam * 0.03)))
    d = ImageDraw.Draw(tela_)
    dobra = int(L * 0.16)
    pts = [(m, m), (m + L, m), (m + L, m + L - dobra), (m + L - dobra, m + L), (m, m + L)]
    d.polygon(pts, fill=cor)
    d.polygon([(m + L, m + L - dobra), (m + L - dobra, m + L - dobra), (m + L - dobra, m + L)],
              fill=tuple(int(v * 0.8) for v in cor[:3]) + (255,))
    d.line(pts + [pts[0]], fill=TITULO_CONTORNO, width=_cont(tam), joint="curve")
    _texto_centrado(d, (m + L * 0.08, m + L * 0.10, m + L * 0.92, m + L * 0.82), texto.upper(),
                    int(L * 0.18), negrito=False, max_linhas=3)
    tela_ = tela_.rotate(4.0, resample=Image.BICUBIC, expand=True)
    anc = {"pega": [tela_.width / 2.0, tela_.height * 0.9], "base": [tela_.width / 2.0, float(tela_.height)],
           "gravidade": True, "z": "frente"}
    return tela_, anc


def alerta(texto="", tam=460):
    """Triangulo de perigo amarelo com '!'; `texto` numa faixa embaixo."""
    L = int(tam)
    m = int(tam * 0.08)
    faixa = int(tam * 0.22) if texto else 0
    tela_ = Image.new("RGBA", (L + 2 * m, int(L * 0.88) + 2 * m + faixa), (0, 0, 0, 0))
    d = ImageDraw.Draw(tela_)
    c = _cont(tam)
    tri = [(m + L / 2.0, m), (m + L, m + L * 0.88), (m, m + L * 0.88)]
    d.polygon(tri, fill=AMARELO)
    d.line(tri + [tri[0]], fill=TITULO_CONTORNO, width=c + 3, joint="curve")
    cx = m + L / 2.0
    d.rounded_rectangle([cx - L * 0.05, m + L * 0.30, cx + L * 0.05, m + L * 0.62], radius=int(L * 0.04),
                        fill=TITULO_CONTORNO)
    d.ellipse([cx - L * 0.055, m + L * 0.68, cx + L * 0.055, m + L * 0.79], fill=TITULO_CONTORNO)
    if texto:
        yf = m + int(L * 0.88) + int(tam * 0.03)
        d.rounded_rectangle([m, yf, m + L, yf + faixa - 6], radius=int(faixa * 0.25), fill=TITULO_PAPEL,
                            outline=TITULO_CONTORNO, width=c)
        _texto_centrado(d, (m + L * 0.05, yf + 4, m + L * 0.95, yf + faixa - 10), texto.upper(),
                        int(faixa * 0.6), max_linhas=1)
    anc = {"pega": [tela_.width / 2.0, tela_.height * 0.9], "base": [tela_.width / 2.0, float(tela_.height)],
           "gravidade": True, "z": "frente", "sem_contorno": True}
    return tela_, anc


GERADORES = {
    "documento": documento, "carimbo": carimbo, "letreiro": letreiro,
    "calendario": calendario, "relogio": relogio, "nota": nota,
    "etiqueta": etiqueta, "balao": balao, "x": x, "interrogacao": interrogacao,
    "exclamacao": exclamacao, "check": check, "seta": seta, "cartaz": cartaz,
    "tela": tela, "painel": painel,
    "ampulheta": ampulheta, "recibo": recibo, "envelope": envelope,
    "grafico": grafico, "post_it": post_it, "alerta": alerta,
}

# quando um tipo se repete no video, a peca que entra no lugar dele e diz a
# mesma coisa (`cartao._variar_pecas`)
ALTERNATIVAS = {
    "calendario": ("ampulheta", "post_it"),     # relogio nao: "4 MESES" num relogio nao le
    "relogio": ("ampulheta",),
    "etiqueta": ("recibo", "nota", "letreiro"),
    "nota": ("recibo", "etiqueta"),
    "carimbo": ("documento", "envelope", "alerta"),
    "documento": ("envelope", "recibo"),
    "seta": ("grafico",),
    "exclamacao": ("alerta",),
    "interrogacao": ("balao", "post_it"),
    "cartaz": ("post_it", "letreiro"),
    "x": ("carimbo", "alerta"),
    "check": ("carimbo",),
    "balao": ("post_it", "cartaz"),
}

# o que o motor SABE desenhar -- ver o comentario no lugar em que esta tupla
# era escrita a mao
TIPOS = tuple(GERADORES)


def gerar(tipo, texto="", tam=None, **kw):
    """(imagem RGBA, ancoras) da placa pedida. Tipo desconhecido vira cartaz."""
    f = GERADORES.get(str(tipo or "").strip().lower(), cartaz)
    if tam is not None:
        kw["tam"] = int(tam)
    return f(texto, **kw)
