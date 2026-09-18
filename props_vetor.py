# -*- coding: utf-8 -*-
"""props_vetor.py -- props de cenario desenhados por codigo, com ancoras.

    PLANO-ENCAIXE.md §3. Sao os moveis e fachadas com os quais o boneco
    interage: balcao, porta, lixeira, cadeira, mesa, fachada, caixa
    eletronico, sofa, cama, computador. Desenhados em PIL no estilo do
    canal (traco preto grosso, cor chapada, sombra curta) para o laboratorio
    poder testar ENCAIXE hoje; a arte gerada por IA entra depois no mesmo
    contrato (`<nome>.png` + `<nome>.ancoras.json`) sem mudar uma linha do
    motor.

    Cada prop devolve (imagem RGBA, ancoras):
        base       onde encosta no chao                       [x, y]
        escala     altura do prop como fracao da altura do ator
        z          "tras" | "frente" | "entre"
        corte_z    (so' `entre`, opcional) a linha y acima da qual o prop
                   fica na FRENTE do ator `atras_de` ele; o resto vai para
                   tras. SEM corte_z o prop inteiro fica na frente de quem
                   esta' atras (balcao, mesa): a folha de 15/09 mostrou as
                   pernas do atendente por cima do painel do balcao
        sockets    apoio (segmento), sentar, macaneta, texto (rect), entrada,
                   tampa, tela...
    Coordenadas em pixels da imagem gerada.

    `python props_vetor.py <pasta>` grava todos em <pasta>.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

TRACO = (24, 20, 18, 255)
SOMBRA = (0, 0, 0, 90)
MADEIRA = (196, 140, 84, 255)
MADEIRA_ESC = (160, 108, 60, 255)
CINZA = (176, 178, 182, 255)
CINZA_ESC = (120, 122, 126, 255)
AZUL = (62, 96, 160, 255)
AZUL_ESC = (44, 70, 122, 255)
VERDE = (78, 150, 96, 255)
VERMELHO = (200, 60, 50, 255)
AMARELO = (247, 196, 48, 255)
CREME = (245, 238, 220, 255)
BRANCO = (250, 250, 248, 255)
VERDE_TELA = (120, 200, 150, 255)


def _tela(w, h, m=24):
    return Image.new("RGBA", (w + 2 * m, h + 2 * m), (0, 0, 0, 0)), m


def _sombra_chao(tela, x0, x1, y, alt=26):
    s = Image.new("RGBA", tela.size, (0, 0, 0, 0))
    ImageDraw.Draw(s).ellipse([x0 - 10, y - alt // 2, x1 + 10, y + alt // 2], fill=SOMBRA)
    s = s.filter(ImageFilter.GaussianBlur(8))
    tela.alpha_composite(s)


def _ret(d, caixa, cor, e=7, raio=0):
    if raio:
        d.rounded_rectangle(caixa, radius=raio, fill=cor, outline=TRACO, width=e)
    else:
        d.rectangle(caixa, fill=cor, outline=TRACO, width=e)


# ---------------------------------------------------------------------
def balcao(tam=900):
    """Balcao de atendimento visto de frente. `entre` sem corte: o balcao
    INTEIRO fica na frente de quem esta' atras (esconde as pernas) e atras
    de quem esta' na frente."""
    w, h = tam, int(tam * 0.62)
    tela, m = _tela(w, h)
    d = ImageDraw.Draw(tela)
    _sombra_chao(tela, m, m + w, m + h)
    d = ImageDraw.Draw(tela)
    # frente do balcao
    _ret(d, [m, m + int(h * 0.16), m + w, m + h], AZUL, e=8)
    # paineis
    for i in range(3):
        x0 = m + int(w * (0.06 + i * 0.30))
        _ret(d, [x0, m + int(h * 0.28), x0 + int(w * 0.26), m + int(h * 0.88)], AZUL_ESC, e=5)
    # tampo
    _ret(d, [m - 10, m, m + w + 10, m + int(h * 0.18)], MADEIRA, e=8)
    d.line([m - 10, m + int(h * 0.09), m + w + 10, m + int(h * 0.09)], fill=MADEIRA_ESC, width=4)
    anc = {"base": [m + w / 2.0, m + h], "escala": 0.58, "z": "entre",
           "sockets": {"apoio": [[m + w * 0.08, m + h * 0.02], [m + w * 0.92, m + h * 0.02]],
                       "tampo": [[m + w * 0.08, m - h * 0.02], [m + w * 0.92, m - h * 0.02]],
                       "texto": {"rect": [[m + w * 0.30, m + h * 0.40], [m + w * 0.70, m + h * 0.72]]},
                       "atras": [m + w / 2.0, m + h * 0.98]}}
    return tela, anc


def porta(tam=900, aberta=False):
    """Porta com batente; `entrada` e' onde alguem fica ao passar por ela."""
    w, h = int(tam * 0.55), tam
    tela, m = _tela(w, h)
    d = ImageDraw.Draw(tela)
    _sombra_chao(tela, m, m + w, m + h)
    d = ImageDraw.Draw(tela)
    # batente
    _ret(d, [m, m, m + w, m + h], CINZA, e=8)
    # folha
    if aberta:
        # folha girada para dentro: um paralelogramo estreito a esquerda
        pts = [(m + 14, m + 14), (m + int(w * 0.30), m + 40), (m + int(w * 0.30), m + h - 40), (m + 14, m + h - 8)]
        d.polygon(pts, fill=MADEIRA, outline=TRACO)
        d.line(pts + [pts[0]], fill=TRACO, width=7)
        # o vao escuro atras
        d.rectangle([m + int(w * 0.30), m + 14, m + w - 14, m + h - 8], fill=(60, 56, 54, 255))
        macaneta = [m + int(w * 0.27), m + int(h * 0.52)]
    else:
        _ret(d, [m + 14, m + 14, m + w - 14, m + h - 8], MADEIRA, e=7)
        _ret(d, [m + int(w * 0.22), m + int(h * 0.10), m + w - int(w * 0.22), m + int(h * 0.44)], MADEIRA_ESC, e=5)
        _ret(d, [m + int(w * 0.22), m + int(h * 0.54), m + w - int(w * 0.22), m + int(h * 0.90)], MADEIRA_ESC, e=5)
        macaneta = [m + int(w * 0.80), m + int(h * 0.52)]
    d.ellipse([macaneta[0] - 16, macaneta[1] - 16, macaneta[0] + 16, macaneta[1] + 16],
              fill=AMARELO, outline=TRACO, width=5)
    anc = {"base": [m + w / 2.0, m + h], "escala": 1.18, "z": "tras",
           "sockets": {"macaneta": macaneta,
                       "texto": {"rect": [[m + w * 0.25, m + h * 0.12], [m + w * 0.75, m + h * 0.30]]},
                       "entrada": [m + w / 2.0, m + h]}}
    return tela, anc


def lixeira(tam=520):
    w, h = int(tam * 0.62), tam
    tela, m = _tela(w, h)
    d = ImageDraw.Draw(tela)
    _sombra_chao(tela, m, m + w, m + h)
    d = ImageDraw.Draw(tela)
    # corpo afunilado
    pts = [(m + int(w * 0.06), m + int(h * 0.16)), (m + w - int(w * 0.06), m + int(h * 0.16)),
           (m + w - int(w * 0.14), m + h), (m + int(w * 0.14), m + h)]
    d.polygon(pts, fill=CINZA_ESC)
    d.line(pts + [pts[0]], fill=TRACO, width=8)
    for i in range(3):
        x = m + int(w * (0.30 + i * 0.20))
        d.line([x, m + int(h * 0.22), x, m + h - 14], fill=(96, 98, 102, 255), width=6)
    # tampa
    _ret(d, [m, m + int(h * 0.06), m + w, m + int(h * 0.18)], CINZA, e=8, raio=10)
    _ret(d, [m + int(w * 0.35), m, m + int(w * 0.65), m + int(h * 0.07)], CINZA, e=6, raio=8)
    anc = {"base": [m + w / 2.0, m + h], "escala": 0.46, "z": "frente",
           "sockets": {"tampa": [m + w / 2.0, m + h * 0.02],
                       "apoio": [[m + w * 0.2, m + h * 0.10], [m + w * 0.8, m + h * 0.10]]}}
    return tela, anc


def cadeira(tam=760):
    w, h = int(tam * 0.62), tam
    tela, m = _tela(w, h)
    d = ImageDraw.Draw(tela)
    _sombra_chao(tela, m, m + w, m + h)
    d = ImageDraw.Draw(tela)
    # encosto
    _ret(d, [m + int(w * 0.08), m, m + w - int(w * 0.08), m + int(h * 0.48)], MADEIRA, e=8, raio=18)
    _ret(d, [m + int(w * 0.20), m + int(h * 0.08), m + w - int(w * 0.20), m + int(h * 0.40)], MADEIRA_ESC, e=5, raio=12)
    # pernas
    for fx in (0.10, 0.90):
        x = m + int(w * fx)
        d.line([x, m + int(h * 0.55), x, m + h], fill=TRACO, width=22)
        d.line([x, m + int(h * 0.55), x, m + h], fill=MADEIRA_ESC, width=10)
    # assento
    _ret(d, [m, m + int(h * 0.46), m + w, m + int(h * 0.60)], MADEIRA, e=8, raio=10)
    anc = {"base": [m + w / 2.0, m + h], "escala": 0.66, "z": "tras",
           "sockets": {"sentar": [m + w / 2.0, m + h * 0.47],
                       "apoio": [[m + w * 0.1, m + h * 0.46], [m + w * 0.9, m + h * 0.46]]}}
    return tela, anc


def mesa(tam=900):
    w, h = tam, int(tam * 0.50)
    tela, m = _tela(w, h)
    d = ImageDraw.Draw(tela)
    _sombra_chao(tela, m, m + w, m + h)
    d = ImageDraw.Draw(tela)
    for fx in (0.08, 0.92):
        x = m + int(w * fx)
        d.line([x, m + int(h * 0.16), x, m + h], fill=TRACO, width=26)
        d.line([x, m + int(h * 0.16), x, m + h], fill=MADEIRA_ESC, width=12)
    _ret(d, [m, m, m + w, m + int(h * 0.18)], MADEIRA, e=8, raio=8)
    anc = {"base": [m + w / 2.0, m + h], "escala": 0.46, "z": "entre",
           "sockets": {"apoio": [[m + w * 0.08, m], [m + w * 0.92, m]],
                       "tampo": [[m + w * 0.10, m - 4], [m + w * 0.90, m - 4]],
                       "atras": [m + w / 2.0, m + h * 0.98]}}
    return tela, anc


def fachada(tam=1100, cor=CREME, letreiro_cor=AZUL):
    """Frente de predio: parede, porta, duas janelas e a faixa do letreiro
    (socket `texto`, onde a placa com o nome e' colada)."""
    w, h = tam, int(tam * 0.95)
    tela, m = _tela(w, h)
    d = ImageDraw.Draw(tela)
    _ret(d, [m, m + int(h * 0.18), m + w, m + h], cor, e=9)
    # telhado / platibanda
    _ret(d, [m - 16, m, m + w + 16, m + int(h * 0.20)], letreiro_cor, e=9)
    # janelas
    for fx in (0.10, 0.66):
        _ret(d, [m + int(w * fx), m + int(h * 0.32), m + int(w * (fx + 0.24)), m + int(h * 0.58)], (170, 210, 235, 255), e=7)
        d.line([m + int(w * (fx + 0.12)), m + int(h * 0.32), m + int(w * (fx + 0.12)), m + int(h * 0.58)], fill=TRACO, width=5)
        d.line([m + int(w * fx), m + int(h * 0.45), m + int(w * (fx + 0.24)), m + int(h * 0.45)], fill=TRACO, width=5)
    # porta
    _ret(d, [m + int(w * 0.40), m + int(h * 0.50), m + int(w * 0.60), m + h], MADEIRA, e=8)
    d.ellipse([m + int(w * 0.565) - 9, m + int(h * 0.76) - 9, m + int(w * 0.565) + 9, m + int(h * 0.76) + 9],
              fill=AMARELO, outline=TRACO, width=4)
    # degrau
    _ret(d, [m + int(w * 0.36), m + h - 22, m + int(w * 0.64), m + h], CINZA, e=6)
    anc = {"base": [m + w / 2.0, m + h], "escala": 1.55, "z": "tras",
           "sockets": {"texto": {"rect": [[m + w * 0.12, m + h * 0.03], [m + w * 0.88, m + h * 0.17]]},
                       "entrada": [m + w * 0.5, m + h],
                       "macaneta": [m + w * 0.565, m + h * 0.76]}}
    return tela, anc


def caixa_eletronico(tam=900):
    w, h = int(tam * 0.5), tam
    tela, m = _tela(w, h)
    d = ImageDraw.Draw(tela)
    _sombra_chao(tela, m, m + w, m + h)
    d = ImageDraw.Draw(tela)
    _ret(d, [m, m, m + w, m + h], CINZA, e=8, raio=14)
    _ret(d, [m + int(w * 0.10), m + int(h * 0.08), m + w - int(w * 0.10), m + int(h * 0.34)], (40, 44, 52, 255), e=7, raio=8)
    d.rectangle([m + int(w * 0.14), m + int(h * 0.11), m + w - int(w * 0.14), m + int(h * 0.31)], fill=VERDE_TELA)
    # teclado
    for r in range(3):
        for c in range(3):
            x = m + int(w * (0.18 + c * 0.22))
            y = m + int(h * (0.42 + r * 0.07))
            _ret(d, [x, y, x + int(w * 0.16), y + int(h * 0.05)], BRANCO, e=3, raio=4)
    # boca de dinheiro
    _ret(d, [m + int(w * 0.16), m + int(h * 0.70), m + w - int(w * 0.16), m + int(h * 0.76)], (40, 44, 52, 255), e=5)
    anc = {"base": [m + w / 2.0, m + h], "escala": 1.05, "z": "tras",
           "sockets": {"tela": {"rect": [[m + w * 0.14, m + h * 0.11], [m + w * 0.86, m + h * 0.31]]},
                       "apoio": [[m + w * 0.2, m + h * 0.45], [m + w * 0.8, m + h * 0.45]],
                       "alvo": [m + w * 0.5, m + h * 0.50]}}
    return tela, anc


def sofa(tam=1100):
    w, h = tam, int(tam * 0.42)
    tela, m = _tela(w, h)
    d = ImageDraw.Draw(tela)
    _sombra_chao(tela, m, m + w, m + h)
    d = ImageDraw.Draw(tela)
    _ret(d, [m + int(w * 0.06), m, m + w - int(w * 0.06), m + int(h * 0.62)], VERMELHO, e=8, raio=22)
    for fx in (0.0, 0.86):
        _ret(d, [m + int(w * fx), m + int(h * 0.20), m + int(w * (fx + 0.14)), m + int(h * 0.92)], VERMELHO, e=8, raio=22)
    _ret(d, [m + int(w * 0.12), m + int(h * 0.50), m + w - int(w * 0.12), m + int(h * 0.90)], (222, 84, 72, 255), e=8, raio=14)
    d.line([m + int(w * 0.5), m + int(h * 0.52), m + int(w * 0.5), m + int(h * 0.88)], fill=TRACO, width=5)
    for fx in (0.16, 0.82):
        x = m + int(w * fx)
        d.line([x, m + int(h * 0.90), x, m + h], fill=TRACO, width=16)
    anc = {"base": [m + w / 2.0, m + h], "escala": 0.55, "z": "tras",
           "sockets": {"sentar": [m + w * 0.5, m + h * 0.52],
                       "sentar_e": [m + w * 0.32, m + h * 0.52],
                       "sentar_d": [m + w * 0.68, m + h * 0.52]}}
    return tela, anc


def cama(tam=1100):
    w, h = tam, int(tam * 0.5)
    tela, m = _tela(w, h)
    d = ImageDraw.Draw(tela)
    _sombra_chao(tela, m, m + w, m + h)
    d = ImageDraw.Draw(tela)
    _ret(d, [m, m, m + int(w * 0.14), m + int(h * 0.80)], MADEIRA, e=8, raio=12)
    _ret(d, [m + int(w * 0.08), m + int(h * 0.36), m + w, m + int(h * 0.82)], BRANCO, e=8, raio=10)
    _ret(d, [m + int(w * 0.34), m + int(h * 0.42), m + w - 8, m + int(h * 0.76)], AZUL, e=6, raio=8)
    _ret(d, [m + int(w * 0.14), m + int(h * 0.42), m + int(w * 0.32), m + int(h * 0.60)], CREME, e=6, raio=10)
    for fx in (0.10, 0.94):
        x = m + int(w * fx)
        d.line([x, m + int(h * 0.82), x, m + h], fill=TRACO, width=18)
    anc = {"base": [m + w / 2.0, m + h], "escala": 0.52, "z": "tras",
           "sockets": {"sentar": [m + w * 0.55, m + h * 0.40],
                       "deitar": [m + w * 0.55, m + h * 0.40]}}
    return tela, anc


def computador(tam=620):
    """Monitor + teclado sobre nada (para por em cima de uma mesa)."""
    w, h = tam, int(tam * 0.78)
    tela, m = _tela(w, h)
    d = ImageDraw.Draw(tela)
    _ret(d, [m + int(w * 0.08), m, m + w - int(w * 0.08), m + int(h * 0.62)], (40, 44, 52, 255), e=8, raio=10)
    d.rectangle([m + int(w * 0.12), m + int(h * 0.05), m + w - int(w * 0.12), m + int(h * 0.56)], fill=(170, 210, 235, 255))
    d.line([m + int(w * 0.5), m + int(h * 0.62), m + int(w * 0.5), m + int(h * 0.76)], fill=TRACO, width=20)
    _ret(d, [m + int(w * 0.30), m + int(h * 0.74), m + int(w * 0.70), m + int(h * 0.80)], CINZA, e=6)
    _ret(d, [m, m + int(h * 0.84), m + w, m + h], CINZA, e=7, raio=8)
    anc = {"base": [m + w / 2.0, m + h], "escala": 0.40, "z": "frente",
           "sockets": {"tela": {"rect": [[m + w * 0.12, m + h * 0.05], [m + w * 0.88, m + h * 0.56]]},
                       "alvo": [m + w * 0.5, m + h * 0.92]}}
    return tela, anc


CATALOGO = {
    "balcao": balcao, "porta": porta, "lixeira": lixeira, "cadeira": cadeira,
    "mesa": mesa, "fachada": fachada, "caixa_eletronico": caixa_eletronico,
    "sofa": sofa, "cama": cama, "computador": computador,
}


def gravar(pasta):
    os.makedirs(pasta, exist_ok=True)
    for nome, f in CATALOGO.items():
        img, anc = f()
        img.save(os.path.join(pasta, nome + ".png"))
        json.dump(anc, open(os.path.join(pasta, nome + ".ancoras.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"[props] {nome}: {img.width}x{img.height}, escala {anc['escala']}, z {anc['z']}")
    # a porta aberta e' uma variante com o mesmo contrato
    img, anc = porta(aberta=True)
    img.save(os.path.join(pasta, "porta_aberta.png"))
    json.dump(anc, open(os.path.join(pasta, "porta_aberta.ancoras.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("[props] porta_aberta")


if __name__ == "__main__":
    gravar(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "lab", "props"))
