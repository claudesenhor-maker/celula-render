# -*- coding: utf-8 -*-
"""ancoras.py -- os SOCKETS do corpo e as ANCORAS de objeto e prop.

    PLANO-ENCAIXE.md §1. Encaixar e' levar uma ancora ate' um socket. O corpo
    tem sockets (palma, topo da cabeca, olhos, ombro, cintura, sola...), o
    objeto tem ancoras (pega, base) e o prop tem sockets proprios (apoio,
    sentar, macaneta, texto). Tudo e' MEDIDO da arte -- nunca fracao de uma
    constante (leis 13 e 38) -- e cabe num JSON ao lado do asset, que pode
    ser corrigido a mao so' na ancora errada (PIVOS-MANUAIS.md, mesma regra).

SOCKETS DO CORPO
    Saem de `pose_na_tela` (onde cada pivo caiu na tela e com que angulo)
    mais um ponto LOCAL por peca, medido no alfa dela uma vez e guardado no
    Personagem: o topo do cranio, a sola do pe', o centro do peito. O ponto
    local e' girado pelo angulo da peca e somado ao pivo -- a mesma conta
    que poe um filho a partir do pai. Um chapeu encaixado no `topo_cabeca`
    inclina junto com a cabeca de graca.

ANCORAS DO OBJETO
    `<nome>.ancoras.json` ao lado do PNG, ou marcas de cor na arte:
        magenta  -> pega  (ja era assim, ver palito_cutout._pivo_de_pega)
        ciano    -> base  (onde encosta no chao)
        amarelo  -> alvo  (macaneta, apoio: onde a mao vai)
    Sem marca e sem JSON: `pega` pelo eixo principal do alfa (objeto
    alongado segura pela ponta de baixo; compacto, pelo centro) e `base` no
    ponto mais baixo do alfa.
"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------
# pontos locais por peca (em pixels da tela INFLADA da peca, relativos ao
# pivo -- e' o sistema em que `Personagem.img/piv` ja' estao)
# ---------------------------------------------------------------------


def _alfa(img):
    return np.asarray(img.convert("RGBA"))[..., 3] > 96


def _extremo(img, piv, eixo, sinal):
    """O ponto do alfa mais longe na direcao `eixo` ('x'|'y') e `sinal` (+-1).

    Devolve (dx, dy) relativo ao pivo. Usa o CENTRO da fatia extrema, nao um
    pixel solto: o topo de um cranio e' uma linha de varios pixels, e o meio
    dela e' o que se le como 'topo'."""
    a = _alfa(img)
    if not a.any():
        return (0.0, 0.0)
    ys, xs = np.nonzero(a)
    if eixo == "y":
        v = ys.max() if sinal > 0 else ys.min()
        sel = xs[ys == v]
        return (float(sel.mean()) - piv[0], float(v) - piv[1])
    v = xs.max() if sinal > 0 else xs.min()
    sel = ys[xs == v]
    return (float(v) - piv[0], float(sel.mean()) - piv[1])


def _centro(img, piv):
    a = _alfa(img)
    if not a.any():
        return (0.0, 0.0)
    ys, xs = np.nonzero(a)
    return (float(xs.mean()) - piv[0], float(ys.mean()) - piv[1])


def _largura_na_linha(img, y):
    a = _alfa(img)
    y = int(max(0, min(a.shape[0] - 1, round(y))))
    xs = np.nonzero(a[y])[0]
    if not len(xs):
        return 0.0, 0.0
    return float(xs.min()), float(xs.max())


def medir_locais(pers):
    """Mede uma vez os pontos locais de cada peca e guarda em `pers._locais`.

    Tudo relativo ao pivo da peca, em pixels da ARTE (antes da escala de
    cena): quem usa multiplica por `pers.escala` e gira pelo angulo."""
    cache = getattr(pers, "_locais", None)
    if cache is not None:
        return cache
    L = {}
    if pers.tem("cranio"):
        img, piv = pers.p("cranio")
        L["topo_cabeca"] = _extremo(img, piv, "y", -1)
        L["queixo"] = _extremo(img, piv, "y", +1)
        # OLHOS: se as feicoes foram recortadas do cranio, os offsets delas
        # sao relativos ao pivo e sobrevivem a fusao do cabelo; senao a arte
        # ainda tem os olhos e `_analisar_rosto` os acha de novo.
        olhos = None
        feic = getattr(pers, "feicoes", None) or {}
        if feic.get("olho_e") and feic.get("olho_d"):
            e, d = feic["olho_e"], feic["olho_d"]
            olhos = ((e["dx"] + d["dx"]) / 2.0, (e["dy"] + d["dy"]) / 2.0)
            L["interocular"] = abs(d["dx"] - e["dx"])
        else:
            try:
                from palito_cutout import _analisar_rosto
                r = _analisar_rosto(img)
            except Exception:
                r = None
            if r:
                olhos = (r["eixo"] - piv[0], r["linha_olhos"] - piv[1])
                L["interocular"] = float(r["d_olhos"])
        if olhos is None:
            # sem olhos medidos: um terco da altura do cranio abaixo do topo
            t = L["topo_cabeca"]
            q = L["queixo"]
            olhos = (t[0], t[1] + (q[1] - t[1]) * 0.42)
            L["interocular"] = (q[1] - t[1]) * 0.36
        L["olhos"] = olhos
        x0, x1 = _largura_na_linha(img, piv[1] + olhos[1])
        L["largura_cabeca"] = max(1.0, x1 - x0)
        L["orelha_e"] = (x0 - piv[0], olhos[1])
        L["orelha_d"] = (x1 - piv[0], olhos[1])
    for nome in ("peito", "abdomen"):
        if pers.tem(nome):
            img, piv = pers.p(nome)
            L["centro_" + nome] = _centro(img, piv)
            L["topo_" + nome] = _extremo(img, piv, "y", -1)
            x0, x1 = _largura_na_linha(img, piv[1] + L["centro_" + nome][1])
            L["largura_" + nome] = max(1.0, x1 - x0)
    for lado in ("e", "d"):
        pe = "pe_" + lado
        if pers.tem(pe):
            img, piv = pers.p(pe)
            L["sola_" + lado] = _extremo(img, piv, "y", +1)
        mao = "mao_" + lado
        if pers.tem(mao):
            img, piv = pers.p(mao)
            vx, vy = pers.vetor_da_palma(mao)
            L["palma_" + lado] = (vx, vy)
            # a ponta dos dedos: o ponto do alfa mais longe no sentido da palma
            a = _alfa(img)
            ys, xs = np.nonzero(a)
            if len(xs):
                n = math.hypot(vx, vy) or 1.0
                proj = ((xs - piv[0]) * vx + (ys - piv[1]) * vy) / n
                k = int(proj.argmax())
                L["dedos_" + lado] = (float(xs[k]) - piv[0], float(ys[k]) - piv[1])
            else:
                L["dedos_" + lado] = (vx * 1.6, vy * 1.6)
    pers._locais = L
    return L


def _girar(v, graus):
    r = math.radians(graus)
    return (v[0] * math.cos(r) - v[1] * math.sin(r),
            v[0] * math.sin(r) + v[1] * math.cos(r))


def sockets(pers, rig, pos=None, ang=None):
    """Os sockets do corpo NA TELA, para este rig.

    Devolve {nome: (x, y)} e tambem as escalas uteis: `interocular`,
    `largura_cabeca`, `altura_cranio`, `largura_ombros` (em px de tela)."""
    from palito_cutout import pose_na_tela
    if pos is None or ang is None:
        pos, ang = pose_na_tela(pers, rig)
    L = medir_locais(pers)
    e = pers.escala
    S = {}

    def _p(peca, local):
        if peca not in pos or local not in L:
            return None
        d = _girar((L[local][0] * e, L[local][1] * e), ang.get(peca, 0.0))
        return (pos[peca][0] + d[0], pos[peca][1] + d[1])

    for nome, peca, local in (
            ("topo_cabeca", "cranio", "topo_cabeca"),
            ("queixo", "cranio", "queixo"),
            ("olhos", "cranio", "olhos"),
            ("orelha_e", "cranio", "orelha_e"),
            ("orelha_d", "cranio", "orelha_d"),
            ("peito", "peito", "centro_peito"),
            ("topo_peito", "peito", "topo_peito"),
            ("barriga", "abdomen", "centro_abdomen"),
            ("sola_e", "pe_e", "sola_e"), ("sola_d", "pe_d", "sola_d"),
            ("palma_e", "mao_e", "palma_e"), ("palma_d", "mao_d", "palma_d"),
            ("dedos_e", "mao_e", "dedos_e"), ("dedos_d", "mao_d", "dedos_d")):
        p = _p(peca, local)
        if p is not None:
            S[nome] = p
    if "cranio" in pos:
        S["pescoco"] = pos["cranio"]
    for lado in ("e", "d"):
        if "braco_sup_" + lado in pos:
            S["ombro_" + lado] = pos["braco_sup_" + lado]
        if "mao_" + lado in pos:
            S["punho_" + lado] = pos["mao_" + lado]
        if "braco_inf_" + lado in pos:
            S["cotovelo_" + lado] = pos["braco_inf_" + lado]
        if "perna_inf_" + lado in pos:
            S["joelho_" + lado] = pos["perna_inf_" + lado]
    raiz = "abdomen" if "abdomen" in pos else next(iter(pos))
    S["cintura"] = pos[raiz]
    if "ombro_e" in S and "ombro_d" in S:
        S["largura_ombros"] = abs(S["ombro_d"][0] - S["ombro_e"][0])
    S["interocular"] = L.get("interocular", 40.0) * e
    S["largura_cabeca"] = L.get("largura_cabeca", 120.0) * e
    S["altura_cranio"] = pers.altura_cranio() * e
    S["ang_cabeca"] = ang.get("cranio", 0.0)
    S["ang_tronco"] = ang.get("peito", ang.get(raiz, 0.0))
    S["_pos"], S["_ang"] = pos, ang
    return S


# ---------------------------------------------------------------------
# ancoras de OBJETO e PROP
# ---------------------------------------------------------------------
_MARCAS = {
    # nome: (teste sobre r,g,b) -- cores que nenhuma arte de traco usa
    "pega": lambda r, g, b: (r > 180) & (b > 180) & (g < 110),      # magenta
    "base": lambda r, g, b: (g > 180) & (b > 180) & (r < 110),      # ciano
    "alvo": lambda r, g, b: (r > 200) & (g > 200) & (b < 90),       # amarelo
}


def _marcas_de_cor(img):
    a = np.asarray(img.convert("RGBA"), dtype=np.int16)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    fora, mascara_total = {}, np.zeros(al.shape, dtype=bool)
    for nome, teste in _MARCAS.items():
        m = (al > 128) & teste(r, g, b)
        if m.sum() >= 6:
            ys, xs = np.nonzero(m)
            fora[nome] = [float(xs.mean()), float(ys.mean())]
            mascara_total |= m
    return fora, mascara_total


def _apagar_marcas(img, mascara):
    """Preenche a marca com a cor vizinha, para ela nao aparecer na tela."""
    if not mascara.any():
        return img
    a = np.asarray(img.convert("RGBA")).copy()
    ys, xs = np.nonzero(mascara)
    r = 3
    for y, x in zip(ys, xs):
        y0, y1 = max(0, y - r), min(a.shape[0], y + r + 1)
        x0, x1 = max(0, x - r), min(a.shape[1], x + r + 1)
        viz = a[y0:y1, x0:x1].reshape(-1, 4)
        viz_m = mascara[y0:y1, x0:x1].reshape(-1)
        ok = viz[(~viz_m) & (viz[:, 3] > 128)]
        if len(ok):
            a[y, x] = ok.mean(axis=0).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def _pega_por_eixo(img):
    """Sem marca: objeto alongado segura pela ponta de BAIXO do eixo maior;
    compacto (razao < 1,6), pelo centro."""
    a = _alfa(img)
    if not a.any():
        return [img.width / 2.0, img.height / 2.0]
    ys, xs = np.nonzero(a)
    cx, cy = xs.mean(), ys.mean()
    cov = np.cov(np.vstack([xs - cx, ys - cy]))
    val, vec = np.linalg.eigh(cov)
    maior, menor = math.sqrt(max(val[1], 1e-6)), math.sqrt(max(val[0], 1e-6))
    if maior / menor < 1.6:
        return [float(cx), float(cy)]
    ex, ey = vec[:, 1]
    if ey < 0:
        ex, ey = -ex, -ey                 # apontar para baixo
    proj = (xs - cx) * ex + (ys - cy) * ey
    k = proj.max() * 0.72                 # a pega e' perto da ponta, nao nela
    return [float(cx + ex * k), float(cy + ey * k)]


def ler(caminho_png, img=None):
    """Le (ou deduz) as ancoras de um objeto/prop. Devolve (img_limpa, dict).

    Ordem: JSON ao lado > marcas de cor > deducao. O dict sempre traz `pega`
    e `base`; `sockets`, `escala`, `z`, `gravidade`, `corte_z` sao opcionais."""
    if img is None:
        img = Image.open(caminho_png).convert("RGBA")
    base_nome = os.path.splitext(caminho_png)[0]
    anc = {}
    for cand in (base_nome + ".ancoras.json", base_nome + ".json"):
        if os.path.exists(cand):
            try:
                anc = json.load(open(cand, encoding="utf-8-sig"))
                break
            except Exception as e:                       # noqa: BLE001
                print(f"[ancoras] {cand}: {e}; ignorando")
    marcas, mascara = _marcas_de_cor(img)
    if mascara.any():
        img = _apagar_marcas(img, mascara)
    for k, v in marcas.items():
        anc.setdefault(k, v)
    # RECORTE PELO ALFA SOLIDO (lei 32) -- e as ancoras acompanham o recorte
    a = np.asarray(img)[..., 3]
    ys, xs = np.nonzero(a > 128)
    if len(ys):
        x0, y0 = int(xs.min()), int(ys.min())
        x1, y1 = int(xs.max()) + 1, int(ys.max()) + 1
        if (x0, y0, x1, y1) != (0, 0, img.width, img.height):
            img = img.crop((x0, y0, x1, y1))
            anc = _deslocar(anc, -x0, -y0)
    anc.setdefault("pega", _pega_por_eixo(img))
    if "base" not in anc:
        a = _alfa(img)
        ys, xs = np.nonzero(a)
        if len(ys):
            v = ys.max()
            anc["base"] = [float(xs[ys == v].mean()), float(v)]
        else:
            anc["base"] = [img.width / 2.0, float(img.height)]
    # ALONGADO (chave, guarda-chuva, controle) segue a mao: continua o
    # antebraco, como um bastao. COMPACTO (marmita, caixa, xicara) fica em
    # pe' na palma (gravidade). Antes tudo girava com a mao e a chave
    # erguida ficava deitada ATRAS da mao -- invisivel no video de 16/09.
    anc.setdefault("alongado", _alongado(img))
    anc.setdefault("gravidade", not anc["alongado"])
    anc.setdefault("z", "frente")
    anc.setdefault("sockets", {})
    return img, anc


def _alongado(img):
    a = _alfa(img)
    if not a.any():
        return False
    ys, xs = np.nonzero(a)
    cov = np.cov(np.vstack([xs - xs.mean(), ys - ys.mean()]))
    val = np.linalg.eigvalsh(cov)
    return math.sqrt(max(val[1], 1e-6)) / math.sqrt(max(val[0], 1e-6)) >= 1.6


def _deslocar(anc, dx, dy):
    """Move todas as coordenadas (pontos, segmentos e retangulos) de (dx, dy)."""
    def mv(v):
        if isinstance(v, (list, tuple)) and len(v) == 2 and all(
                isinstance(c, (int, float)) for c in v):
            return [float(v[0]) + dx, float(v[1]) + dy]
        if isinstance(v, (list, tuple)):
            return [mv(c) for c in v]
        if isinstance(v, dict):
            return {k: mv(c) for k, c in v.items()}
        return v
    fora = dict(anc)
    for k in ("pega", "pega2", "base", "alvo"):
        if k in fora:
            fora[k] = mv(fora[k])
    if "sockets" in fora:
        fora["sockets"] = mv(fora["sockets"])
    return fora


def escalar(anc, k):
    """As ancoras de uma arte reamostrada por `k`."""
    def mv(v):
        if isinstance(v, (list, tuple)) and len(v) == 2 and all(
                isinstance(c, (int, float)) for c in v):
            return [float(v[0]) * k, float(v[1]) * k]
        if isinstance(v, (list, tuple)):
            return [mv(c) for c in v]
        if isinstance(v, dict):
            return {a: mv(c) for a, c in v.items()}
        return v
    fora = dict(anc)
    for chave in ("pega", "pega2", "base", "alvo", "sockets"):
        if chave in fora:
            fora[chave] = mv(fora[chave])
    if "corte_z" in fora:
        fora["corte_z"] = float(fora["corte_z"]) * k
    return fora


def ponto_do_socket(socket, perto_de=None):
    """Um socket pode ser um ponto [x,y], um segmento [[x0,y0],[x1,y1]] ou um
    retangulo [[x0,y0],[x1,y1]] marcado como `rect`. Devolve o ponto a usar:
    num segmento, o mais proximo de `perto_de`."""
    if socket is None:
        return None
    if isinstance(socket, dict):
        if socket.get("rect"):
            (x0, y0), (x1, y1) = socket["rect"]
            return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
        socket = socket.get("pontos") or socket.get("segmento")
    if isinstance(socket[0], (int, float)):
        return (float(socket[0]), float(socket[1]))
    (x0, y0), (x1, y1) = socket[0], socket[1]
    if perto_de is None:
        return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
    # projecao de `perto_de` no segmento, limitada as pontas
    vx, vy = x1 - x0, y1 - y0
    n2 = vx * vx + vy * vy
    if n2 <= 1e-6:
        return (float(x0), float(y0))
    u = ((perto_de[0] - x0) * vx + (perto_de[1] - y0) * vy) / n2
    u = max(0.0, min(1.0, u))
    return (x0 + vx * u, y0 + vy * u)


# ---------------------------------------------------------------------
# o mapa (lei 37: toda regua desenha o que mede)
# ---------------------------------------------------------------------
def mapa_do_corpo(pers, rig, saida):
    """Desenha o personagem com os sockets marcados e numerados."""
    from palito_cutout import desenhar_personagem, W, H
    cam = desenhar_personagem(pers, rig)
    S = sockets(pers, rig)
    fundo = Image.new("RGBA", (W, H), (240, 236, 226, 255))
    fundo.alpha_composite(cam)
    d = ImageDraw.Draw(fundo)
    for i, (nome, p) in enumerate(sorted(k for k in S.items()
                                          if isinstance(k[1], tuple))):
        x, y = p
        d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(220, 40, 40, 255),
                  outline=(0, 0, 0, 255), width=2)
        d.text((x + 10, y - 8), nome, fill=(20, 20, 20, 255))
    fundo.convert("RGB").save(saida)
    return saida


def mapa_do_objeto(caminho_png, saida):
    img, anc = ler(caminho_png)
    tela = Image.new("RGBA", (img.width + 40, img.height + 40), (240, 236, 226, 255))
    tela.alpha_composite(img, (20, 20))
    d = ImageDraw.Draw(tela)
    for nome in ("pega", "pega2", "base", "alvo"):
        if nome in anc:
            x, y = anc[nome][0] + 20, anc[nome][1] + 20
            d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(220, 40, 40, 255))
            d.text((x + 8, y - 6), nome, fill=(20, 20, 20, 255))
    for nome, s in (anc.get("sockets") or {}).items():
        p = ponto_do_socket(s)
        if p:
            x, y = p[0] + 20, p[1] + 20
            d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(40, 90, 220, 255))
            d.text((x + 8, y - 6), nome, fill=(20, 20, 20, 255))
    tela.convert("RGB").save(saida)
    return saida, anc
