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
    t = int(tam_fonte)
    while t > 10:
        fonte = _fonte_titulo(t) if negrito else _fonte(t)
        linhas = _quebrar(texto, fonte, larg * 0.94)
        alt_l = int(t * 1.12)
        if len(linhas) <= max_linhas and alt_l * len(linhas) <= alt * 0.96 \
                and all(fonte.getlength(l) <= larg * 0.94 for l in linhas):
            break
        t = int(t * 0.9)
    y = y0 + (alt - alt_l * len(linhas)) / 2.0
    esp = fonte.getlength(" ")
    for l in linhas:
        w = fonte.getlength(l)
        x = x0 + (larg - w) / 2.0
        for pal in l.split(" "):
            c = cor
            if destaque_numeros and any(ch.isdigit() for ch in pal):
                c = TITULO_DESTAQUE
            d.text((x, y), pal, font=fonte, fill=c)
            x += fonte.getlength(pal) + esp
        y += alt_l
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
    fonte = _fonte_titulo(int(H_ * 0.16))
    s = texto.upper()
    w = fonte.getlength(s)
    for (fx, fy) in ((0.18, 0.20), (0.82, 0.20), (0.18, 0.80), (0.82, 0.80)):
        d.text((m + W_ * fx - w / 2, m + H_ * fy - H_ * 0.09), s, font=fonte, fill=(30, 60, 35, 255))
    _texto_centrado(d, (m + int(W_ * 0.30), m + int(H_ * 0.30), m + int(W_ * 0.70), m + int(H_ * 0.70)),
                    texto.upper(), int(H_ * 0.34), cor=(30, 60, 35, 255), max_linhas=1,
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
        fonte = _fonte_titulo(int(tam * 0.16))
        w = fonte.getlength(texto.upper())
        d.text((cx - w / 2, m + tam * 0.72), texto.upper(), font=fonte, fill=BRANCO)
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


GERADORES = {
    "documento": documento, "carimbo": carimbo, "letreiro": letreiro,
    "calendario": calendario, "relogio": relogio, "nota": nota,
    "etiqueta": etiqueta, "balao": balao, "x": x, "interrogacao": interrogacao,
    "exclamacao": exclamacao, "check": check, "seta": seta, "cartaz": cartaz,
    "tela": tela, "painel": painel,
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
