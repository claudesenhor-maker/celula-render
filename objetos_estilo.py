# -*- coding: utf-8 -*-
"""objetos_estilo.py -- os objetos do catalogo REFEITOS no traco do canal.

    (16/09, ordem do dono: "objetos mal feitos".) Os PNGs de `lab/objetos/`
    vieram do FLUX semi-realistas (chave de metal com reflexo, celular de
    foto, boleto ilegivel). Aqui cada um e' pedido de novo pela esteira
    `gerar-assets` do n8n (que tem a credencial da Cloudflare -- ver
    `workers_ai.pela_esteira`), com o prompt abrindo por "simple flat 2D
    cartoon drawing" -- o modelo ancora no comeco (licao do `a tv remote`) --
    e com a ORIENTACAO dita: a parte que se segura em BAIXO, o objeto em pe'.
    E' o que faz `ancoras.ler` achar a pega certa (ponta de baixo do eixo
    maior) e `cartao.py` erguer a chave com os dentes para cima.

    Tipo `lab_objeto` no bucket: nao toca no catalogo de producao.
    Saida: lab/objetos_lab/<nome>.png (alfa por cor, lei 103) +
    <nome>.ancoras.json com `achatado: true` (o motor nao re-achata).

USO
    python objetos_estilo.py chave celular          # so' esses
    python objetos_estilo.py --todos [--forca]
"""
import io
import json
import os
import sys

from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
LAB = os.path.join(RAIZ, "lab")
sys.path.insert(0, AQUI)

import workers_ai as WAI      # noqa: E402

ABERTURA = "simple flat 2D cartoon drawing, NOT a photo, of ONE "
FECHO = ("big and simple, few bold shapes, 100% flat colours, thick uniform black outline, "
         "no shading, no gradient, no texture, no reflections, "
         "floating in mid-air with nothing under it, "
         "upright and centred, the whole object inside the frame")

OBJETOS = {
    "chave":       "large old-fashioned door key, golden yellow, drawn perfectly VERTICAL like a tall letter I: the teeth at the TOP, the round ring at the BOTTOM",
    "celular":     "smartphone seen from the front, dark blue body with a light screen, held vertically",
    "carteira":    "folded brown leather wallet with a few green banknotes sticking out of the top",
    "marmita":     "plastic lunch box with a lid and a handle on top, light orange, seen from the front",
    "boleto":      "brazilian payment slip: a tall white paper bill with a black barcode at the bottom and a few thick grey lines as text, held vertically",
    "carta":       "sealed envelope, cream paper with a red wax seal, seen from the front",
    "xicara_de_cafe": "white coffee mug with a handle on the right and a small cloud of steam",
    "guarda_chuva_quebrado": "BROKEN black umbrella turned inside out by the wind, the canopy flipped upward like a bowl, ribs poking out, the curved handle at the BOTTOM",
    "controle_remoto": "small black tv remote control with a few round coloured buttons, held vertically",
    "sacola_de_compras": "white paper shopping bag with two handles, a few groceries sticking out of the top",
    "caixa_de_papelao": "closed brown cardboard box with tape on top, seen from the front",
}


def prompt(nome):
    return ABERTURA + OBJETOS[nome] + ". " + FECHO


def so_o_objeto(rgba):
    """Tira a sombra no chao e os brilhos que o FLUX poe mesmo proibidos:
    fica o maior componente do alfa e o que for grande, ao lado dele ou
    acima (o vapor da xicara); some o que e' pequeno ou esta' DEBAIXO."""
    import numpy as np
    from PIL import ImageDraw
    from PIL import ImageFilter
    a = np.asarray(rgba)[..., 3] > 64
    h, w = a.shape
    # abertura morfologica: os pontinhos de anti-serrilha em volta viram
    # milhares de componentes se nao forem tirados antes
    rot = Image.fromarray((a * 255).astype(np.uint8), "L").filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))
    a = np.asarray(rot) > 127
    comps = []
    rest = a.copy()
    minimo = 0.004 * h * w                       # menor que isto e' ruido: nem guarda
    while rest.any():
        ys, xs = np.nonzero(rest)
        seed = (int(xs[0]), int(ys[0]))
        ImageDraw.floodfill(rot, seed, 128)
        m = np.asarray(rot) == 128
        rest &= ~m
        ImageDraw.floodfill(rot, seed, 64)       # marca como visto
        if m.sum() >= minimo:
            comps.append(m)
    if not comps:
        return rgba
    comps.sort(key=lambda m: m.sum(), reverse=True)
    principal = comps[0]
    ys, xs = np.nonzero(principal)
    px0, px1, py1 = xs.min(), xs.max(), ys.max()
    area = principal.sum()
    manter = principal.copy()
    for m in comps[1:]:
        cy, cx = np.nonzero(m)
        if m.sum() < 0.02 * area:
            continue                             # brilho, ponto, risco
        if cy.min() > py1 - 0.06 * h:
            continue                             # esta' debaixo: sombra
        if cx.max() < px0 or cx.min() > px1:
            continue                             # ao lado, solto
        manter |= m
    # devolve a borda que a abertura comeu (3 px) e aplica sobre o alfa original
    mi = Image.fromarray((manter * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(7))
    manter = np.asarray(mi) > 127
    arr = np.asarray(rgba).copy()
    arr[..., 3] = np.where(manter, arr[..., 3], 0)
    out = Image.fromarray(arr, "RGBA")
    bb = out.getbbox()
    return out.crop(bb) if bb else out


def gerar(nome, destino=None, forca=False):
    destino = destino or os.path.join(LAB, "objetos_lab")
    os.makedirs(destino, exist_ok=True)
    png = os.path.join(destino, nome + ".png")
    if os.path.exists(png) and not forca:
        print(f"[objetos] {nome}: ja existe ({png}); --forca refaz")
        return png
    img = WAI.texto_para_imagem(prompt(nome), esteira=("lab_objeto", nome))
    if img is None:
        print(f"[objetos] {nome}: sem imagem")
        return None
    buf = io.BytesIO()
    img.save(buf, "PNG")
    from sob_demanda import _recortar_fundo
    rec = _recortar_fundo(buf.getvalue())
    if rec is None:
        img.save(os.path.join(destino, nome + "_bruto.png"))
        print(f"[objetos] {nome}: o recorte por cor reprovou; bruto salvo para o olho")
        return None
    obj = so_o_objeto(Image.open(io.BytesIO(rec)).convert("RGBA"))
    obj.save(png)
    json.dump({"achatado": True, "origem": "esteira gerar-assets, lab_objeto, 16/09"},
              open(os.path.join(destino, nome + ".ancoras.json"), "w", encoding="utf-8"), indent=1)
    print(f"[objetos] {nome}: {obj.width}x{obj.height}")
    return png


def gerar_novo(nome, desc_en, forca=False):
    """Objeto fora do catalogo (a serie minerada pede o que a historia tem:
    garrafa de cachaca, moeda, bomba de gasolina). Entra em OBJETOS na hora
    e sai pela mesma porta. Lei 28: o catalogo e' fechado, mas cresce."""
    OBJETOS[nome] = desc_en
    return gerar(nome, forca=forca)


def garantir(pedidos, forca=False):
    """{nome: desc_en} -> gera o que ainda nao existe em lab/objetos_lab."""
    destino = os.path.join(LAB, "objetos_lab")
    for nome, desc in pedidos.items():
        if os.path.exists(os.path.join(destino, nome + ".png")) and not forca:
            continue
        gerar_novo(nome, desc, forca=forca)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--novo" in sys.argv:
        # python objetos_estilo.py --novo garrafa_de_cachaca "a glass bottle of cachaca..."
        i = sys.argv.index("--novo")
        gerar_novo(sys.argv[i + 1], sys.argv[i + 2], forca="--forca" in sys.argv)
        raise SystemExit(0)
    nomes = list(OBJETOS) if "--todos" in sys.argv else args
    if not nomes:
        raise SystemExit(__doc__)
    for n in nomes:
        if n not in OBJETOS:
            print(f"[objetos] '{n}' nao esta no catalogo: {', '.join(OBJETOS)}")
            continue
        gerar(n, forca="--forca" in sys.argv)
