#!/usr/bin/env python3
"""
palito_v4 — motor de animação determinístico, estilo desenhado à mão.

Corrige o erro de proporção do v3: os braços estavam em 200deg/-20deg, que
no sistema de coordenadas da tela (y cresce para baixo) aponta para CIMA
e para os lados. Por isso pareciam curtos e grudados no ombro.
Em repouso, braço caído = ~100deg e ~80deg.

Novidades do v4:
  - braços com ângulos corretos e alcance até o quadril
  - camisa cobrindo o tronco inteiro, com gola
  - DOIS personagens (protagonista + secundário) para diálogo
  - cenário simples desenhado à mão (mesa, parede, chão)
  - duração alvo 15-25s

Este arquivo e a BIBLIOTECA do rig: geometria, poses, expressoes, traco a
mao e boil. Ele NAO renderiza video -- ver a nota no fim do arquivo.

Ponto de entrada:
    from palito_v5 import render_spec
    render_spec(spec, "saida.mp4", modo="real")
"""
import math, os, random, subprocess, tempfile, time
import cairosvg

# W,H = espaço de PROJETO (viewBox do SVG). Toda a geometria do rig usa isto.
# OUT_W,OUT_H = resolução de SAÍDA. Como o desenho é vetorial, subir a saída
# NÃO exige mexer em nenhuma coordenada — é só rasterizar maior.
# Medido: 1080x1920 = 97ms/frame · 2160x3840 = 289ms/frame. O vídeo de
# referência é 2160x3840, e o YouTube dá bitrate melhor a upload em 4K.
W, H, FPS = 1080, 1920, 24
OUT_W = int(os.environ.get("OUT_W", 2160))
OUT_H = int(os.environ.get("OUT_H", 3840))

# Paleta medida do video de referencia (quantize 8 cores)
BG        = "#A5A893"
BG_SOMBRA = "#6B6957"
TINTA     = "#1A1814"
PELE      = "#D8CDB4"
CAMISA_A  = "#5A6B7A"
CAMISA_B  = "#8C5F52"
CALCA     = "#3E3B33"
MADEIRA   = "#8A7355"

# ---------------------------------------------------------------------
# ANGULOS: 0 = direita, 90 = BAIXO (y cresce para baixo na tela).
# Braco caido em repouso fica perto de 90, nao de 200. Esse foi o bug do v3.
# ---------------------------------------------------------------------
REST = {
    "quadril": [540, 1210], "cabeca_r": 128, "tronco": -90,
    "braco_e": [103, 12], "braco_d": [77, -12],     # caidos ao lado do corpo
    "perna_e": [97, 5],   "perna_d": [83, -5],
    "boca": 0.2, "sobrancelha": 0.0, "olho": 1.0, "dx": 0.0,
}

POSES = {
    "parado_falando":  {},
    "bracos_abertos":  {"braco_e": [148, 22], "braco_d": [32, -22]},
    "apontando":       {"braco_d": [8, -4],   "braco_e": [106, 14]},
    "maos_na_cabeca":  {"braco_e": [196, 62], "braco_d": [-16, -62]},
    "encolher_ombros": {"braco_e": [158, 58], "braco_d": [22, -58], "tronco": -93},
    "pensando":        {"braco_d": [44, -96], "braco_e": [101, 10]},
    "maos_na_cintura": {"braco_e": [128, 74], "braco_d": [52, -74]},
    "acenando":        {"braco_d": [-4, -30], "braco_e": [101, 10]},
}

EXPRESSOES = {
    "neutro":   {"sobrancelha": 0.0},
    "surpreso": {"sobrancelha": 1.0, "boca": 1.0, "olho": 1.5},
    "bravo":    {"sobrancelha": -1.0, "olho": 0.72},
    "sorrindo": {"sobrancelha": 0.35, "boca": 0.55},
    "duvida":   {"sobrancelha": 0.55, "olho": 0.9},
}


def merge(b, *ds):
    o = dict(b)
    for d in ds:
        o.update(d)
    return o


def lerp(a, b, t):
    return [lerp(x, y, t) for x, y in zip(a, b)] if isinstance(a, list) else a + (b - a) * t


def blend(p1, p2, t):
    return {k: lerp(p1[k], p2[k], t) for k in p1}


def pt(o, ang, ln):
    r = math.radians(ang)
    return [o[0] + math.cos(r) * ln, o[1] + math.sin(r) * ln]


# =====================================================================
# TRAÇO À MÃO + BOIL
# A semente inclui o número do frame: mesma semente = mesma ondulação,
# frame novo = ondulação nova. É isso que produz o "boil" do desenho.
# =====================================================================
def _wobble(pts, seed, amp, segs):
    rnd = random.Random(seed)
    out = []
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        for s in range(segs + 1):
            t = s / segs
            k = math.sin(t * math.pi)          # desvio zero nas pontas
            out.append((a[0] + (b[0] - a[0]) * t + rnd.uniform(-amp, amp) * k,
                        a[1] + (b[1] - a[1]) * t + rnd.uniform(-amp, amp) * k))
    d = f"M{out[0][0]:.1f},{out[0][1]:.1f}"
    for p in out[1:]:
        d += f" L{p[0]:.1f},{p[1]:.1f}"
    return d


def traco(pts, seed, w=14, amp=3.0, segs=6, cor=None):
    """Duas passadas levemente diferentes = espessura irregular de caneta."""
    rnd = random.Random(seed * 7919)
    c = cor or TINTA
    return (f'<path d="{_wobble(pts, seed, amp, segs)}" fill="none" stroke="{c}" '
            f'stroke-width="{w:.1f}" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="{_wobble(pts, seed + 977, amp * 0.5, segs)}" fill="none" stroke="{c}" '
            f'stroke-width="{w * rnd.uniform(0.7, 0.9):.1f}" stroke-linecap="round" stroke-linejoin="round"/>')


def forma(pts, seed, fill, w=13, amp=2.6, segs=5):
    return (f'<path d="{_wobble(list(pts) + [pts[0]], seed, amp, segs)} Z" fill="{fill}" '
            f'stroke="{TINTA}" stroke-width="{w}" stroke-linejoin="round"/>')


def circ(cx, cy, r, seed, fill, w=13, amp=3.0, n=20):
    return forma([(cx + math.cos(a) * r, cy + math.sin(a) * r)
                  for a in [i * math.tau / n for i in range(n)]], seed, fill, w, amp, 3)



def _lado(a, b, w0, w1, seed, amp, segs):
    """Um lado do osso: caminha de a para b com largura variavel, e ondula."""
    rnd = random.Random(seed)
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / L, dx / L
    pts = []
    for i in range(segs + 1):
        t = i / segs
        w = (w0 + (w1 - w0) * t) / 2
        k = math.sin(t * math.pi)                 # ondula no meio, nao nas pontas
        pts.append((a[0] + dx * t + nx * w + rnd.uniform(-amp, amp) * k,
                    a[1] + dy * t + ny * w + rnd.uniform(-amp, amp) * k))
    return pts


def osso(a, b, w0, w1, seed, cor=None, amp=2.2, segs=6):
    """Traco com ESPESSURA VARIAVEL, como caneta de verdade.

    O v4 antigo usava stroke-width fixo: largura uniforme do comeco ao fim.
    Isso e a assinatura visual de clip art -- nenhum instrumento real
    desenha assim. Aqui o osso e um poligono preenchido que afina, com o
    contorno ondulado dos DOIS lados."""
    up = _lado(a, b, w0, w1, seed, amp, segs)
    dn = _lado(a, b, -w0, -w1, seed + 4441, amp, segs)[::-1]
    pts = up + dn
    d = "M%.1f,%.1f " % pts[0] + " ".join("L%.1f,%.1f" % q for q in pts[1:]) + " Z"
    # calotas arredondadas nas pontas evitam corte reto
    c = cor or TINTA
    return (f'<path d="{d}" fill="{c}"/>'
            f'<circle cx="{a[0]:.1f}" cy="{a[1]:.1f}" r="{w0/2:.1f}" fill="{c}"/>'
            f'<circle cx="{b[0]:.1f}" cy="{b[1]:.1f}" r="{w1/2:.1f}" fill="{c}"/>')


def osso_out(a, b, w0, w1, seed, fill, borda=9, amp=2.2):
    """Membro COLORIDO com contorno de tinta.

    A tentativa anterior desenhava a manga e depois um osso preto por
    cima, com sementes diferentes -- as duas ondulacoes nao batiam e a
    manga aparecia deslocada ao lado do braco. Aqui o contorno e o mesmo
    osso, so que maior, e com a MESMA semente: o preenchimento cai exato
    dentro dele."""
    return (osso(a, b, w0 + borda, w1 + borda, seed, TINTA, amp)
            + osso(a, b, w0, w1, seed, fill, amp))


def mao(punho, ang, larg, seed, fill=None):
    """Mao em forma de LUVA, nao bolinha.

    Bolinha nao le como mao -- le como articulacao. Uma luva com polegar
    tem silhueta de mao mesmo em traco minimo, que e como quadrinho e
    animacao 2D resolvem isso ha decadas."""
    rnd = random.Random(seed)
    L = larg * 2.3
    w = larg * 1.55
    # perfil em coordenadas locais: x avanca no sentido do antebraco
    perfil = [
        (0.00, -0.50), (0.42, -0.58), (0.78, -0.46), (1.00, -0.16),
        (1.00,  0.18), (0.80,  0.46), (0.52,  0.60),
        (0.34,  0.86), (0.16,  0.92), (0.04,  0.60),   # polegar
        (0.00,  0.50),
    ]
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    pts = []
    for fx, fy in perfil:
        x, y = fx * L + rnd.uniform(-1.2, 1.2), fy * w + rnd.uniform(-1.2, 1.2)
        pts.append((punho[0] + x * ca - y * sa, punho[1] + x * sa + y * ca))
    return forma(pts, seed, fill or PELE, 9, 1.6, 3)


# =====================================================================
def personagem(rig, fr, camisa=CAMISA_A, ident=0):
    S = lambda n: n * 131 + fr * 977 + ident * 40009
    dx = rig["dx"]
    q = [rig["quadril"][0] + dx, rig["quadril"][1]]
    r = rig["cabeca_r"]
    ombro = pt(q, rig["tronco"], 235)
    cab = pt(ombro, rig["tronco"], r + 34)
    o = []

    # ---- pernas: calça ----
    for i, c in enumerate((rig["perna_e"], rig["perna_d"])):
        jo = pt(q, c[0], 150)
        pe = pt(jo, c[0] + c[1], 145)
        # coxa mais grossa que canela: o corpo afina para baixo
        o.append(osso_out(q, jo, 36, 28, S(10 + i), CALCA))
        o.append(osso_out(jo, pe, 26, 20, S(11 + i), CALCA))
        o.append(forma([(pe[0] - 30, pe[1] - 12), (pe[0] + 26, pe[1] - 14),
                        (pe[0] + 30, pe[1] + 12), (pe[0] - 32, pe[1] + 12)],
                       S(14 + i), TINTA, 5, 2.0))

    # ---- tronco: camisa cobrindo do ombro ao quadril ----
    ox, oy = ombro
    o.append(forma([(ox - 86, oy + 6), (ox + 86, oy + 6),
                    (q[0] + 70, q[1] + 26), (q[0] - 70, q[1] + 26)], S(20), camisa, 13, 2.4))
    o.append(traco([(ox - 30, oy + 4), (ox, oy + 46), (ox + 30, oy + 4)], S(21), 9, 2.0))  # gola

    # ---- braços: alcance até o quadril ----
    for i, c in enumerate((rig["braco_e"], rig["braco_d"])):
        base = [ox + (-74 if i == 0 else 74), oy + 22]
        cot = pt(base, c[0], 132)
        mo = pt(cot, c[0] + c[1], 126)
        # manga colorida ate o cotovelo, antebraco cor de pele: le como
        # braco de personagem, nao como vareta preta
        o.append(osso_out(base, cot, 30, 24, S(30 + i), camisa))
        o.append(osso_out(cot, mo, 22, 18, S(31 + i), PELE))
        # a mao aponta na direcao do antebraco
        ang_ante = math.degrees(math.atan2(mo[1] - cot[1], mo[0] - cot[0]))
        o.append(mao(mo, ang_ante, 26, S(34 + i)))

    # ---- cabeça ----
    cx, cy = cab
    o.append(circ(cx, cy, r, S(40), PELE, 14, 3.4, 34))
    o.append(traco([(cx - r * 0.55, cy - r * 0.62), (cx, cy - r * 0.86), (cx + r * 0.55, cy - r * 0.62)],
                   S(41), 16, 3.0))                                        # linha do cabelo

    sb, ex = rig["sobrancelha"], r * 0.34
    ro = r * 0.20 * rig["olho"]
    sy = cy - r * 0.40
    for i, sx in enumerate((-ex, ex)):
        o.append(circ(cx + sx, cy - r * 0.05, ro, S(50 + i), "#FBF8F0", 8, 1.6, 22))
        o.append(f'<circle cx="{cx+sx+ro*0.2:.0f}" cy="{cy-r*0.05:.0f}" r="{ro*0.44:.0f}" fill="{TINTA}"/>')
    o.append(traco([(cx - ex - 44, sy + sb * 22), (cx - ex + 40, sy - sb * 22)], S(60), 15, 2.0))
    o.append(traco([(cx + ex - 40, sy - sb * 22), (cx + ex + 44, sy + sb * 22)], S(61), 15, 2.0))

    bw = r * 0.30
    bh = 6 + rig["boca"] * 42
    o.append(forma([(cx - bw, cy + r * 0.45), (cx + bw, cy + r * 0.45),
                    (cx + bw * 0.78, cy + r * 0.45 + bh), (cx - bw * 0.78, cy + r * 0.45 + bh)],
                   S(70), TINTA, 6, 1.8))
    return "".join(o)


def cenario(fr, tipo="sala"):
    S = lambda n: n * 7717 + fr * 331
    o = [f'<rect width="{W}" height="{H}" fill="{BG}"/>']
    chao_y = 1620
    o.append(f'<path d="{_wobble([(0, chao_y - 8), (540, chao_y + 6), (1080, chao_y - 4)], S(1), 5.0, 9)} '
             f'L1080,{H} L0,{H} Z" fill="{BG_SOMBRA}" opacity="0.28"/>')
    o.append(traco([(0, chao_y - 8), (540, chao_y + 6), (1080, chao_y - 4)], S(2), 8, 5.0, 9))
    if tipo == "sala":
        o.append(forma([(120, 620), (470, 612), (476, 900), (126, 906)], S(10), "#B9BCA6", 11, 3.0))
        o.append(traco([(150, 660), (300, 700), (240, 760), (400, 730)], S(11), 7, 4.0, 8))
    elif tipo == "mesa":
        o.append(forma([(60, 1300), (1020, 1290), (1030, 1370), (50, 1380)], S(20), MADEIRA, 12, 3.0))
        o.append(traco([(150, 1370), (160, 1620)], S(21), 18, 3.0, 5))
        o.append(traco([(930, 1370), (920, 1620)], S(22), 18, 3.0, 5))
    return "".join(o)


def frame_svg(rigs, fr, cen="sala"):
    corpos = "".join(personagem(r, fr, cam, i) for i, (r, cam) in enumerate(rigs))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}">{cenario(fr, cen)}{corpos}</svg>')


# =====================================================================
# =====================================================================
# NAO existe render() aqui de proposito.
#
# Havia um, e ele era uma armadilha: montava o video a partir de
# trechos[].dur informado no spec. Isso viola a LEI DO RITMO -- a duracao
# tem que SAIR do audio, nunca entrar como estimativa. Quem chamasse este
# arquivo direto geraria video MUDO com timeline inventada, que e
# exatamente o defeito que o palito_v5 existe para corrigir.
#
# Ponto de entrada unico:
#     from palito_v5 import render_spec
#     render_spec(spec, "saida.mp4", modo="real")
#
# Este arquivo e so a BIBLIOTECA do rig: geometria, poses, expressoes,
# traco a mao, boil e frame_svg.
# =====================================================================


if __name__ == "__main__":
    import sys
    print(__doc__)
    print("Este modulo nao renderiza sozinho. Use:")
    print("    python3 palito_v5.py --modo demo -o saida.mp4")
    sys.exit(1)
