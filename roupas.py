# -*- coding: utf-8 -*-
"""roupas.py -- figurino: acessorio colado no socket, e roupa recolorida.

    PLANO-ENCAIXE.md §6. Tres niveis; aqui estao os dois baratos:

    NIVEL 1 -- ACESSORIO COLADO. Um PNG com alfa e um `encaixe` (o ponto do
    acessorio que vai no socket do corpo), escalado por uma MEDIDA do corpo
    (largura da cabeca, interocular, largura dos ombros -- lei 13: nada em
    fracao de constante). Desenhado por cima do ator, girado pelo angulo da
    peca do socket: o quepe inclina com a cabeca de graca. Os acessorios
    desta primeira leva sao vetoriais (PIL), no traco do canal; arte gerada
    entra depois com o mesmo contrato (`<nome>.png` + `<nome>.ancoras.json`
    em `lab/acessorios/`).

    NIVEL 2 -- RECOLORIR O TECIDO. A peca de roupa (peito, abdomen, mangas,
    pernas) tem uma cor dominante que nao e' pele nem traco; os pixels dessa
    familia de matiz trocam de matiz e saturacao pela cor pedida, mantendo o
    VALOR (as sombras da arte ficam). Camisa azul vira jaleco branco, colete
    verde, terno preto -- sem gerar imagem e sem re-segmentar.

    PAPEIS (`PAPEIS`): delegado = quepe + uniforme azul; rh = cracha + colete
    verde... O roteiro escreve `papel: "delegado"` e o resto sai daqui.
"""
import colorsys
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw

TRACO = (24, 20, 18, 255)
NOMINAL_CABECA = 240.0          # largura de cabeca em que os acessorios foram desenhados
NOMINAL_INTEROCULAR = 80.0
NOMINAL_OMBROS = 210.0


SS = 3      # os acessorios sao desenhados em 3x e reduzidos: sem serrilha


class _Tela:
    """Tela + desenho em `SS`x com as coordenadas nominais: quem desenha
    escreve em px da folha (cabeca de 240), e o resultado sai reduzido com
    antisserrilhado. `fim()` devolve a imagem no tamanho nominal."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def _p(self, xy):
        return [(float(x) * SS) for x in xy] if not isinstance(xy[0], (tuple, list)) \
            else [(float(x) * SS, float(y) * SS) for x, y in xy]

    def rounded_rectangle(self, xy, radius=0, **k):
        self.d.rounded_rectangle(self._p(xy), radius=radius * SS, **self._k(k))

    def rectangle(self, xy, **k):
        self.d.rectangle(self._p(xy), **self._k(k))

    def ellipse(self, xy, **k):
        self.d.ellipse(self._p(xy), **self._k(k))

    def polygon(self, xy, **k):
        self.d.polygon(self._p(xy), **self._k(k))

    def line(self, xy, **k):
        self.d.line(self._p(xy), **self._k(k))

    def pieslice(self, xy, a, b, **k):
        self.d.pieslice(self._p(xy), a, b, **self._k(k))

    def chord(self, xy, a, b, **k):
        self.d.chord(self._p(xy), a, b, **self._k(k))

    def arc(self, xy, a, b, **k):
        self.d.arc(self._p(xy), a, b, **self._k(k))

    def text(self, xy, s, font=None, **k):
        self.d.text((xy[0] * SS, xy[1] * SS), s, font=font, **k)

    @staticmethod
    def _k(k):
        k = dict(k)
        if "width" in k:
            k["width"] = int(round(k["width"] * SS))
        return k

    def fim(self):
        return self.img.resize((self.w, self.h), Image.LANCZOS)


def _tela(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def _escura(cor, f=0.72):
    return tuple(int(c * f) for c in cor[:3]) + (255,)


def _clara(cor, f=1.25):
    return tuple(min(255, int(c * f)) for c in cor[:3]) + (255,)


# ---------------------------------------------------------------------
# acessorios vetoriais (desenhados para uma cabeca de 240 px de largura).
# REDESENHADOS em 16/09 ("trajes mal feitos"): volume, sombra de baixo, luz
# de cima, aba curva -- no lugar da meia-lua com retangulo. Ancoras iguais.
# ---------------------------------------------------------------------
def quepe(cor=(40, 60, 120, 255)):
    w, h = 300, 160
    t = _Tela(w, h)
    # copa alta e abaulada
    t.chord([28, 6, 272, 150], 180, 360, fill=cor, outline=TRACO, width=7)
    t.chord([44, 14, 256, 120], 200, 340, fill=_clara(cor, 1.18))          # luz
    # faixa escura
    t.rounded_rectangle([24, 84, 276, 122], radius=10, fill=_escura(cor, 0.62), outline=TRACO, width=7)
    # aba curva (chord virado para baixo) com brilho
    t.chord([70, 86, 250, 160], 10, 170, fill=(30, 30, 34, 255), outline=TRACO, width=6)
    t.chord([96, 100, 224, 134], 20, 160, fill=(70, 70, 78, 255))
    # cordao e distintivo
    t.line([56, 118, 244, 118], fill=(247, 196, 48, 255), width=5)
    t.ellipse([128, 40, 172, 84], fill=(247, 196, 48, 255), outline=TRACO, width=4)
    t.ellipse([140, 52, 160, 72], fill=(230, 160, 30, 255))
    return t.fim(), {"encaixe": [150, 118], "socket": "topo_cabeca", "ref": "largura_cabeca",
                     "nominal": NOMINAL_CABECA, "z": "frente", "afunda": 0.10}


def chapeu(cor=(50, 44, 40, 255)):
    w, h = 340, 160
    t = _Tela(w, h)
    # aba: elipse com espessura (duas elipses) e sombra por baixo
    t.ellipse([6, 96, 334, 152], fill=_escura(cor, 0.6), outline=TRACO, width=7)
    t.ellipse([6, 88, 334, 140], fill=cor, outline=TRACO, width=7)
    # copa: retangulo arredondado, com a luz de um lado e a cova no alto
    t.rounded_rectangle([86, 14, 254, 118], radius=24, fill=cor, outline=TRACO, width=7)
    t.rounded_rectangle([98, 26, 128, 100], radius=10, fill=_clara(cor, 1.6))   # luz
    t.chord([116, 8, 224, 38], 0, 180, fill=_escura(cor, 0.6), outline=TRACO, width=5)   # a cova
    # fita
    t.rectangle([86, 82, 254, 106], fill=(120, 100, 60, 255), outline=TRACO, width=4)
    t.rounded_rectangle([90, 104, 250, 122], radius=6, fill=cor)
    return t.fim(), {"encaixe": [170, 112], "socket": "topo_cabeca", "ref": "largura_cabeca",
                     "nominal": NOMINAL_CABECA, "z": "frente", "afunda": 0.12}


def bone(cor=(200, 60, 50, 255)):
    w, h = 330, 150
    t = _Tela(w, h)
    # copa: cupula com sombra na base e luz no alto
    t.chord([34, 8, 286, 210], 180, 360, fill=cor, outline=TRACO, width=7)
    t.chord([58, 30, 262, 190], 200, 340, fill=_clara(cor, 1.18))
    t.rectangle([34, 96, 286, 112], fill=_escura(cor, 0.72))
    t.chord([34, 8, 286, 210], 180, 360, fill=None, outline=TRACO, width=7)
    # gomos e botao
    t.arc([70, 8, 250, 210], 200, 340, fill=_escura(cor, 0.8), width=4)
    t.line([160, 14, 160, 106], fill=_escura(cor, 0.8), width=4)
    t.ellipse([150, 4, 170, 24], fill=_escura(cor, 0.8), outline=TRACO, width=4)
    # aba curva, com a borda de baixo mais escura
    t.chord([150, 84, 326, 148], 340, 200, fill=_escura(cor, 0.8), outline=TRACO, width=6)
    t.chord([150, 78, 326, 136], 340, 200, fill=cor, outline=TRACO, width=6)
    t.chord([180, 86, 300, 120], 350, 190, fill=_clara(cor, 1.15))
    # a base da copa cobre a raiz da aba
    t.rounded_rectangle([40, 96, 282, 116], radius=8, fill=_escura(cor, 0.72), outline=TRACO, width=6)
    return t.fim(), {"encaixe": [160, 108], "socket": "topo_cabeca", "ref": "largura_cabeca",
                     "nominal": NOMINAL_CABECA, "z": "frente", "afunda": 0.10}


def oculos_escuros():
    w, h = 300, 100
    d = _Tela(w, h)
    for x0 in (20, 160):
        d.rounded_rectangle([x0, 20, x0 + 120, 90], radius=26, fill=(30, 30, 34, 255), outline=TRACO, width=7)
        d.rounded_rectangle([x0 + 18, 30, x0 + 60, 48], radius=8, fill=(90, 90, 100, 255))
    d.line([140, 45, 160, 45], fill=TRACO, width=8)
    d.line([20, 40, 0, 30], fill=TRACO, width=7)
    d.line([280, 40, 300, 30], fill=TRACO, width=7)
    return d.fim(), {"encaixe": [150, 52], "socket": "olhos", "ref": "interocular",
                     "nominal": NOMINAL_INTEROCULAR * 1.75, "z": "frente"}


def oculos():
    w, h = 300, 100
    d = _Tela(w, h)
    for x0 in (20, 160):
        d.ellipse([x0, 18, x0 + 120, 92], fill=(180, 210, 240, 70), outline=TRACO, width=8)
    d.line([140, 50, 160, 50], fill=TRACO, width=8)
    d.line([20, 45, 0, 34], fill=TRACO, width=7)
    d.line([280, 45, 300, 34], fill=TRACO, width=7)
    return d.fim(), {"encaixe": [150, 55], "socket": "olhos", "ref": "interocular",
                     "nominal": NOMINAL_INTEROCULAR * 1.75, "z": "frente"}


def gravata(cor=(200, 60, 50, 255)):
    w, h = 90, 260
    d = _Tela(w, h)
    # no' com volume, corpo com listra de luz
    d.polygon([(28, 34), (62, 34), (80, 200), (45, 250), (10, 200)], fill=cor, outline=TRACO)
    d.polygon([(34, 40), (46, 40), (58, 200), (45, 230), (32, 200)], fill=_clara(cor, 1.2))
    d.rounded_rectangle([24, 0, 66, 36], radius=10, fill=_escura(cor, 0.8), outline=TRACO, width=6)
    d.line([(28, 34), (62, 34), (80, 200), (45, 250), (10, 200), (28, 34)], fill=TRACO, width=6)
    return d.fim(), {"encaixe": [45, 6], "socket": "pescoco", "ref": "largura_ombros",
                     "nominal": NOMINAL_OMBROS, "z": "frente", "gira_com": "tronco"}


def cracha(texto="RH"):
    w, h = 120, 150
    d = _Tela(w, h)
    d.line([60, 0, 60, 30], fill=TRACO, width=6)
    d.rounded_rectangle([10, 28, 110, 140], radius=10, fill=(250, 250, 248, 255), outline=TRACO, width=6)
    d.rectangle([10, 28, 110, 56], fill=(62, 96, 160, 255), outline=TRACO, width=6)
    d.ellipse([28, 66, 60, 98], fill=(230, 190, 150, 255), outline=TRACO, width=4)
    d.line([70, 74, 98, 74], fill=(90, 90, 90, 255), width=5)
    d.line([70, 90, 98, 90], fill=(90, 90, 90, 255), width=5)
    from legendas import _fonte_titulo
    f = _fonte_titulo(22 * SS)
    wt = f.getlength(texto) / SS
    d.text((60 - wt / 2, 108), texto, font=f, fill=TRACO)
    return d.fim(), {"encaixe": [60, 4], "socket": "peito", "ref": "largura_ombros",
                     "nominal": NOMINAL_OMBROS * 1.6, "z": "frente", "gira_com": "tronco",
                     "desloca": [0.22, -0.10]}


def capacete(cor=(247, 196, 48, 255)):
    w, h = 320, 170
    d = _Tela(w, h)
    d.pieslice([30, 10, 290, 250], 180, 360, fill=cor, outline=TRACO, width=8)
    d.chord([54, 30, 266, 230], 200, 340, fill=_clara(cor, 1.12))
    d.rectangle([30, 100, 290, 128], fill=_escura(cor, 0.8))
    d.pieslice([30, 10, 290, 250], 180, 360, fill=None, outline=TRACO, width=8)
    d.rounded_rectangle([140, 20, 180, 118], radius=12, fill=(255, 235, 150, 255), outline=TRACO, width=4)
    d.rounded_rectangle([10, 118, 310, 150], radius=14, fill=cor, outline=TRACO, width=7)
    d.rounded_rectangle([24, 130, 296, 142], radius=6, fill=_escura(cor, 0.8))
    return d.fim(), {"encaixe": [160, 134], "socket": "topo_cabeca", "ref": "largura_cabeca",
                     "nominal": NOMINAL_CABECA, "z": "frente", "afunda": 0.16}


def coroa():
    w, h = 260, 150
    d = _Tela(w, h)
    pts = [(20, 140), (20, 50), (70, 95), (130, 15), (190, 95), (240, 50), (240, 140)]
    d.polygon(pts, fill=(247, 196, 48, 255), outline=TRACO)
    d.rectangle([20, 112, 240, 140], fill=(230, 160, 30, 255))
    d.line(pts + [pts[0]], fill=TRACO, width=7)
    for x, y in ((70, 95), (130, 15), (190, 95)):
        d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=(200, 60, 50, 255), outline=TRACO, width=4)
    return d.fim(), {"encaixe": [130, 130], "socket": "topo_cabeca", "ref": "largura_cabeca",
                     "nominal": NOMINAL_CABECA, "z": "frente", "afunda": 0.06}


def mascara():
    w, h = 250, 120
    d = _Tela(w, h)
    d.rounded_rectangle([35, 20, 215, 110], radius=24, fill=(150, 200, 235, 255), outline=TRACO, width=7)
    for y in (45, 65, 85):
        d.line([50, y, 200, y], fill=(110, 160, 200, 255), width=4)
    d.line([35, 40, 0, 20], fill=TRACO, width=6)
    d.line([215, 40, 250, 20], fill=TRACO, width=6)
    return d.fim(), {"encaixe": [125, 0], "socket": "olhos", "ref": "largura_cabeca",
                     "nominal": NOMINAL_CABECA * 1.05, "z": "frente", "desloca": [0.0, 0.18]}


def bandana(cor=(200, 60, 50, 255)):
    w, h = 300, 90
    d = _Tela(w, h)
    d.rounded_rectangle([20, 20, 280, 70], radius=20, fill=cor, outline=TRACO, width=7)
    d.rounded_rectangle([34, 28, 266, 42], radius=6, fill=_clara(cor, 1.18))
    d.polygon([(275, 40), (300, 20), (298, 70)], fill=cor, outline=TRACO)
    return d.fim(), {"encaixe": [150, 60], "socket": "topo_cabeca", "ref": "largura_cabeca",
                     "nominal": NOMINAL_CABECA, "z": "frente", "afunda": 0.30}


def fone():
    w, h = 300, 190
    d = _Tela(w, h)
    d.arc([20, 20, 280, 300], 180, 360, fill=TRACO, width=22)
    d.arc([20, 20, 280, 300], 180, 360, fill=(60, 60, 66, 255), width=12)
    for x0 in (0, 240):
        d.rounded_rectangle([x0, 120, x0 + 60, 190], radius=20, fill=(60, 60, 66, 255), outline=TRACO, width=7)
        d.rounded_rectangle([x0 + 14, 134, x0 + 30, 176], radius=6, fill=(96, 96, 104, 255))
    return d.fim(), {"encaixe": [150, 40], "socket": "topo_cabeca", "ref": "largura_cabeca",
                     "nominal": NOMINAL_CABECA * 0.95, "z": "frente", "afunda": 0.02}


CATALOGO = {
    "quepe": quepe, "chapeu": chapeu, "bone": bone, "oculos_escuros": oculos_escuros,
    "oculos": oculos, "gravata": gravata, "cracha": cracha, "capacete": capacete,
    "coroa": coroa, "mascara": mascara, "bandana": bandana, "fone": fone,
}

_CACHE_ACESSORIO = {}


def acessorio(nome, pastas=()):
    """(imagem, ancoras) do acessorio: arquivo em `pastas` primeiro, senao o
    vetorial do catalogo. Nome com parametro: 'cracha:RH', 'gravata:#c83c32'."""
    chave = str(nome)
    if chave in _CACHE_ACESSORIO:
        return _CACHE_ACESSORIO[chave]
    base, _, arg = chave.partition(":")
    achado = None
    for p in pastas:
        cand = os.path.join(p, base + ".png")
        if os.path.exists(cand):
            import ancoras as ANC
            img, anc = ANC.ler(cand)
            anc.setdefault("socket", "topo_cabeca")
            anc.setdefault("encaixe", anc.get("base", [img.width / 2.0, float(img.height)]))
            anc.setdefault("ref", "largura_cabeca")
            anc.setdefault("nominal", float(img.width))
            achado = (img, anc)
            break
    if achado is None and base in CATALOGO:
        f = CATALOGO[base]
        if arg:
            if arg.startswith("#") and len(arg) == 7:
                cor = tuple(int(arg[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
                achado = f(cor)
            else:
                achado = f(arg)
        else:
            achado = f()
    if achado is None:
        print(f"[roupas] acessorio '{nome}' nao existe; ignorando")
        return None
    _CACHE_ACESSORIO[chave] = achado
    return achado


def colar_acessorios(camada, pers, S, nomes, pastas=()):
    """Cola cada acessorio no socket, escalado pela medida e girado pela peca.

    `S` e' o dict de `ancoras.sockets`. Devolve a camada (mesmo objeto)."""
    from palito_cutout import colar
    for nome in nomes or []:
        a = acessorio(nome, pastas)
        if a is None:
            continue
        img, anc = a
        sock = anc.get("socket", "topo_cabeca")
        p = S.get(sock)
        if p is None:
            continue
        ref = anc.get("ref", "largura_cabeca")
        medida = float(S.get(ref) or S.get("largura_cabeca") or 200.0)
        k = medida / float(anc.get("nominal") or medida)
        ang = S.get("ang_cabeca", 0.0) if anc.get("gira_com", "cabeca") == "cabeca" else S.get("ang_tronco", 0.0)
        # deslocamentos no referencial da peca: `afunda` desce o chapeu para
        # dentro da cabeca (fracao da altura do cranio); `desloca` e' [dx, dy]
        # em fracao da medida de referencia
        dx = dy = 0.0
        if anc.get("afunda"):
            dy += float(anc["afunda"]) * float(S.get("altura_cranio", 200.0))
        if anc.get("desloca"):
            dx += float(anc["desloca"][0]) * medida
            dy += float(anc["desloca"][1]) * medida
        r = math.radians(ang)
        ddx = dx * math.cos(r) - dy * math.sin(r)
        ddy = dx * math.sin(r) + dy * math.cos(r)
        destino = (p[0] + ddx, p[1] + ddy)
        colar(camada, img, tuple(anc["encaixe"]), destino, ang, escala=k)
    return camada


# ---------------------------------------------------------------------
# NIVEL 2 -- recolorir o tecido
# ---------------------------------------------------------------------
PECAS_DE_ROUPA = {
    "peito": ("peito",), "abdomen": ("abdomen",),
    "mangas": ("braco_sup_e", "braco_sup_d", "braco_inf_e", "braco_inf_d"),
    "pernas": ("perna_sup_e", "perna_sup_d", "perna_inf_e", "perna_inf_d"),
    "pes": ("pe_e", "pe_d"),
}


def _hex(cor):
    if isinstance(cor, (tuple, list)):
        return tuple(int(c) for c in cor[:3])
    s = str(cor).lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def _cor_dominante(arr, alfa):
    """A cor mais comum entre os pixels opacos que nao sao traco nem pele."""
    rgb = arr[..., :3].astype(np.int32)
    lum = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2])
    ok = alfa & (lum > 60)
    if ok.sum() < 20:
        return None
    q = (rgb[ok] // 24)
    chaves = q[:, 0] * 10000 + q[:, 1] * 100 + q[:, 2]
    vals, cont = np.unique(chaves, return_counts=True)
    k = vals[cont.argmax()]
    sel = chaves == k
    return rgb[ok][sel].mean(axis=0)


def _mascara_da_familia(arr, alfa, dom, tol_h=0.09, tol_s=0.45):
    rgb = arr[..., :3].astype(np.float32) / 255.0
    mx, mn = rgb.max(axis=2), rgb.min(axis=2)
    v = mx
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    # matiz
    d = np.maximum(mx - mn, 1e-6)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6.0
    hd, sd, vd = colorsys.rgb_to_hsv(*(dom / 255.0))
    dh = np.abs(h - hd)
    dh = np.minimum(dh, 1.0 - dh)
    if sd < 0.12:
        # roupa cinza/preta/branca: a familia e' por VALOR e pouca saturacao
        m = alfa & (s < 0.25) & (np.abs(v - vd) < 0.35)
    else:
        m = alfa & (dh < tol_h) & (s > 0.12) & (np.abs(s - sd) < tol_s)
    lum = (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2])
    m = m & (lum > 45)
    # A FAMILIA TEM BURACOS (16/09). A arte gerada tem ruido de matiz dentro
    # do tecido; o terno do Zeca saiu PONTILHADO na folha de 15/09 porque
    # cada pixel fora da tolerancia ficava verde no meio do preto. O tecido
    # e' uma mancha continua (lei 21): fecha-se a mascara (dilata e erode) e
    # o que ficou dentro dela entra, desde que nao seja traco nem pele.
    if m.sum() < 10:
        return m
    from PIL import ImageFilter
    mi = Image.fromarray((m * 255).astype(np.uint8), "L")
    fechada = np.asarray(mi.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(9))) > 127
    pele = _mascara_pele(rgb)
    if 0.0 <= hd <= 0.12 and sd > 0.15:
        pele = np.zeros_like(pele)          # a roupa E' cor de pele: nao ha como separar
    livre = alfa & (lum > 45) & ~pele
    m = m | (fechada & livre)
    # e a faixa anti-serrilhada entre o tecido e o contorno preto (ficava
    # verde-claro em volta do terno): dois pixels alem da familia, se nao
    # forem traco nem pele
    mi = Image.fromarray((m * 255).astype(np.uint8), "L")
    borda = np.asarray(mi.filter(ImageFilter.MaxFilter(5))) > 127
    return m | (borda & livre)


def _mascara_pele(rgb):
    """Pixels na faixa de pele (laranja claro, pouco saturado)."""
    mx, mn = rgb.max(axis=2), rgb.min(axis=2)
    d = np.maximum(mx - mn, 1e-6)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6.0
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    return (h >= 0.0) & (h <= 0.12) & (s > 0.12) & (s < 0.75) & (mx > 0.45)


def recolorir_peca(img, cor, dom=None):
    """Devolve a peca com a familia de cor dominante trocada por `cor`."""
    arr = np.asarray(img.convert("RGBA")).copy()
    alfa = arr[..., 3] > 96
    if dom is None:
        dom = _cor_dominante(arr, alfa)
    if dom is None:
        return img
    m = _mascara_da_familia(arr, alfa, dom)
    if m.sum() < 10:
        return img
    tr, tg, tb = _hex(cor)
    th, ts, tv = colorsys.rgb_to_hsv(tr / 255.0, tg / 255.0, tb / 255.0)
    rgb = arr[..., :3].astype(np.float32) / 255.0
    mx = rgb.max(axis=2)
    _, _, vd = colorsys.rgb_to_hsv(*(dom / 255.0))
    # o valor do pixel em relacao ao valor da cor dominante = a sombra da arte
    rel = np.clip(mx / max(vd, 1e-3), 0.0, 1.35)
    v_novo = np.clip(tv * rel, 0.0, 1.0)
    # saturacao: a da cor alvo, um pouco menor onde a arte e' mais escura
    s_novo = np.clip(ts * (0.85 + 0.15 * rel), 0.0, 1.0)
    # hsv -> rgb vetorizado (so' nos pixels da mascara)
    s_m, v_m = s_novo[m], v_novo[m]
    i = int(math.floor(th * 6.0)) % 6
    f = th * 6.0 - math.floor(th * 6.0)
    p = v_m * (1.0 - s_m)
    q = v_m * (1.0 - s_m * f)
    t = v_m * (1.0 - s_m * (1.0 - f))
    tabela = {0: (v_m, t, p), 1: (q, v_m, p), 2: (p, v_m, t),
              3: (p, q, v_m), 4: (t, p, v_m), 5: (v_m, p, q)}
    r_, g_, b_ = tabela[i]
    arr[..., 0][m] = (r_ * 255).astype(np.uint8)
    arr[..., 1][m] = (g_ * 255).astype(np.uint8)
    arr[..., 2][m] = (b_ * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def recolorir(pers, mapa):
    """Aplica `mapa` ({"peito": "#hex", "pernas": ..., "mangas": ...}) no
    Personagem JA CARREGADO (troca `pers.img`). Devolve os nomes trocados."""
    trocadas = []
    for grupo, cor in (mapa or {}).items():
        pecas = PECAS_DE_ROUPA.get(grupo, (grupo,))
        for nome in pecas:
            if not pers.tem(nome):
                continue
            pers.img[nome] = recolorir_peca(pers.img[nome], cor)
            trocadas.append(nome)
    # o cache de caras e de escala e' por objeto de imagem; trocou, zera
    if trocadas:
        pers._cache_var = {}
        pers._cache_cara = {}
    return trocadas


# ---------------------------------------------------------------------
PALETAS = {
    "uniforme_policial": {"peito": "#2e4a86", "mangas": "#2e4a86", "pernas": "#1e2a44"},
    "jaleco": {"peito": "#f4f2ec", "mangas": "#f4f2ec", "pernas": "#e8e6df"},
    "terno": {"peito": "#26262c", "mangas": "#26262c", "pernas": "#1e1e24"},
    "colete_verde": {"peito": "#3f8a4a", "mangas": "#e9e4d6"},
    "macacao": {"peito": "#e8731f", "mangas": "#e8731f", "pernas": "#e8731f"},
    "camisa_vermelha": {"peito": "#c83c32", "mangas": "#c83c32"},
    "camisa_branca": {"peito": "#f2efe6", "mangas": "#f2efe6"},
    "roupa_de_banco": {"peito": "#8a8fa8", "mangas": "#8a8fa8", "pernas": "#2f3140"},
    "avental": {"peito": "#efe7d2", "pernas": "#3a3a44"},
}

PAPEIS = {
    "delegado": {"acessorios": ["quepe"], "roupa": "uniforme_policial"},
    "policial": {"acessorios": ["quepe", "oculos_escuros"], "roupa": "uniforme_policial"},
    "rh": {"acessorios": ["cracha:RH"], "roupa": "colete_verde"},
    "advogado": {"acessorios": ["chapeu", "oculos_escuros", "gravata"], "roupa": "terno"},
    "chefe": {"acessorios": ["gravata"], "roupa": "terno"},
    "medico": {"acessorios": ["mascara"], "roupa": "jaleco"},
    "gerente": {"acessorios": ["cracha:GERENTE", "gravata:#2e4a86"], "roupa": "roupa_de_banco"},
    "atendente": {"acessorios": ["fone", "cracha:SAC"], "roupa": "camisa_branca"},
    "pedreiro": {"acessorios": ["capacete"], "roupa": "macacao"},
    "rei": {"acessorios": ["coroa"], "roupa": "camisa_vermelha"},
    "cozinheiro": {"acessorios": ["bandana"], "roupa": "avental"},
}


def expandir_papel(papel, acessorios=None, roupa=None):
    """Junta o que o papel manda com o que o cartao pediu por cima."""
    p = PAPEIS.get(str(papel or "").strip().lower(), {})
    acs = list(p.get("acessorios", [])) + list(acessorios or [])
    rp = roupa or p.get("roupa")
    if isinstance(rp, str):
        rp = PALETAS.get(rp, None) if rp in PALETAS else (json.loads(rp) if rp.startswith("{") else None)
    return acs, rp
