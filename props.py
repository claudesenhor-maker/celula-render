# -*- coding: utf-8 -*-
"""props.py -- carrega um prop de cenario (PNG + ancoras) na escala da cena.

    O prop e' medido contra a ALTURA DO ATOR (lei 38): `ancoras.escala` diz
    que fracao dela o prop ocupa. Depois de escalado, ele sabe onde fica a
    base (pousa no chao desenhado, lei 27), onde estao os sockets na tela e,
    se for `entre`, como se parte em duas camadas (tras/frente) na linha
    `corte_z`.
"""
import os

from PIL import Image

import ancoras as ANC


class Prop:
    def __init__(self, nome, img, anc):
        self.nome = nome
        self.img = img
        self.anc = anc
        self.x = 0.0            # onde a base foi posta na tela (x)
        self.y = 0.0            # (y da base = linha do chao)

    @property
    def z(self):
        return self.anc.get("z", "frente")

    def colocar(self, x_base, y_base):
        self.x, self.y = float(x_base), float(y_base)
        return self

    def canto(self):
        """O canto superior esquerdo da imagem na tela, dado onde a base esta."""
        bx, by = self.anc["base"]
        return (int(round(self.x - bx)), int(round(self.y - by)))

    def para_tela(self, p):
        cx, cy = self.canto()
        return (cx + float(p[0]), cy + float(p[1]))

    def socket(self, nome, perto_de=None):
        s = (self.anc.get("sockets") or {}).get(nome)
        if s is None:
            if nome == "base":
                return (self.x, self.y)
            if nome == "centro":
                return self.para_tela((self.img.width / 2.0, self.img.height / 2.0))
            if nome == "topo":
                return self.para_tela((self.img.width / 2.0, 0.0))
            return None
        # segmentos e retangulos sao resolvidos em coordenadas de TELA
        if isinstance(s, dict) and s.get("rect"):
            (x0, y0), (x1, y1) = s["rect"]
            a, b = self.para_tela((x0, y0)), self.para_tela((x1, y1))
            return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        if isinstance(s, (list, tuple)) and s and isinstance(s[0], (list, tuple)):
            seg = [self.para_tela(s[0]), self.para_tela(s[1])]
            return ANC.ponto_do_socket(seg, perto_de)
        return self.para_tela(s)

    def rect_socket(self, nome):
        s = (self.anc.get("sockets") or {}).get(nome)
        if isinstance(s, dict) and s.get("rect"):
            (x0, y0), (x1, y1) = s["rect"]
            return (x0, y0, x1, y1)          # em px da imagem do prop
        return None

    def bbox(self):
        cx, cy = self.canto()
        return (cx, cy, cx + self.img.width, cy + self.img.height)

    def camadas(self):
        """[(z_nome, imagem, canto)] -- `entre` sem `corte_z` e' o prop INTEIRO
        entre quem esta' atras e quem esta' na frente (balcao, mesa: o painel
        esconde as pernas de quem esta' atras). Com `corte_z`, so' o que esta'
        acima da linha fica na frente; o resto vai para tras (encosto de sofa,
        parede de guiche)."""
        cx, cy = self.canto()
        if self.z != "entre":
            return [(self.z, self.img, (cx, cy))]
        if self.anc.get("corte_z") is None:
            return [("entre", self.img, (cx, cy))]
        corte = int(round(float(self.anc["corte_z"])))
        corte = max(1, min(self.img.height - 1, corte))
        frente = self.img.crop((0, 0, self.img.width, corte))
        tras = self.img.crop((0, corte, self.img.width, self.img.height))
        return [("tras", tras, (cx, cy + corte)), ("entre", frente, (cx, cy))]

    def com_placa(self, placa_img, socket="texto"):
        """Uma copia do prop com a placa colada dentro do retangulo do socket."""
        r = self.rect_socket(socket)
        novo = self.img.copy()
        if r is None:
            return Prop(self.nome, novo, self.anc).colocar(self.x, self.y)
        x0, y0, x1, y1 = r
        larg, alt = max(1.0, x1 - x0), max(1.0, y1 - y0)
        k = min(larg / placa_img.width, alt / placa_img.height)
        p = placa_img.resize((max(1, int(placa_img.width * k)), max(1, int(placa_img.height * k))),
                             Image.LANCZOS)
        novo.alpha_composite(p, (int(x0 + (larg - p.width) / 2), int(y0 + (alt - p.height) / 2)))
        return Prop(self.nome, novo, self.anc).colocar(self.x, self.y)


def _achar(pastas, nome):
    for p in pastas:
        for ext in (".png", ".webp", ".jpg"):
            c = os.path.join(p, nome + ext)
            if os.path.exists(c):
                return c
    return None


_CACHE = {}


def carregar(nome, pastas, altura_ator, escala_extra=1.0, destacar=False):
    """Prop `nome` escalado para `escala * altura_ator` de altura."""
    chave = (nome, round(altura_ator), round(escala_extra, 3))
    if chave in _CACHE:
        p = _CACHE[chave]
        return Prop(p.nome, p.img, p.anc)
    caminho = _achar(pastas, nome)
    if caminho is None:
        print(f"[prop] '{nome}' nao existe em {[os.path.normpath(x) for x in pastas]}")
        return None
    img, anc = ANC.ler(caminho)
    frac = float(anc.get("escala", 0.6)) * float(escala_extra)
    alvo = altura_ator * frac
    k = alvo / max(1.0, float(img.height))
    from palito_cutout import _reamostrar, _destacar_objeto
    img = _reamostrar(img, (max(1, int(img.width * k)), max(1, int(img.height * k))))
    anc = ANC.escalar(anc, k)
    if destacar or not anc.get("sem_contorno"):
        pass   # os props vetoriais ja tem contorno; arte de IA passa por _destacar_objeto se pedir
    if destacar:
        img = _destacar_objeto(img)
    p = Prop(nome, img, anc)
    _CACHE[chave] = p
    return Prop(p.nome, p.img, p.anc)
