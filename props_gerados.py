# -*- coding: utf-8 -*-
"""props_gerados.py -- props de cenario GERADOS no estilo dos cenarios do
canal, com as ancoras herdadas do prop vetorial de mesmo nome.

    (15/09, ordem 3 do dono: "melhorar a qualidade dos objetos, talvez usar
    no fundo".) Os cenarios do canal saem do sdxl-lightning com um prompt
    de estilo que da arte boa e consistente; os props em PIL
    (`props_vetor.py`) ficam abaixo disso. Aqui cada prop e' pedido ao MESMO
    modelo, com o MESMO estilo, isolado sobre branco puro e visto de frente;
    o alfa sai por cor (`sob_demanda._recortar_fundo`, lei 103) e as
    ANCORAS vem do prop vetorial homonimo, reescaladas para a caixa da arte
    gerada -- o vetorial vira o gabarito de encaixe, e a arte gerada, a
    pele. O contrato (`<nome>.png` + `<nome>.ancoras.json`) e' o mesmo:
    `cartao.py` nao muda uma linha.

    "No fundo": um prop com z `tras` (fachada, porta, parede de guiche) e'
    desenhado atras dos atores como parte do lugar; com `fundo:
    "cenario:<chave>"` no cartao o cenario lavado entra por baixo de tudo.
    As duas coisas juntas sao o "lugar" do Madrazzo com a arte do canal.

USO
    python props_gerados.py balcao lixeira            # gera so' esses
    python props_gerados.py --todos                   # os 11 do catalogo
    python props_gerados.py balcao --semente 3 --forca
    Saida: lab/props_gerados/<nome>.png + .ancoras.json (nao sobrescreve
    lab/props/ -- quem escolher qual usar e' `pastas_props` no spec).
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

import props_vetor as PV      # noqa: E402  (as ancoras-gabarito)
import workers_ai as WAI      # noqa: E402

ESTILO = ("flat cartoon vector illustration, thick black outline, flat colours, "
          "few large simple shapes, very little detail, soft muted colours, "
          "every surface clearly coloured")
NEGATIVO = ("people, person, man, woman, character, face, hands, text, letters, "
            "numbers, watermark, logo, frame, border, vignette, photo, 3d render, "
            "realistic, gradient, shading, shadow on the ground, floor, wall, room, "
            "scenery, background objects, perspective, two objects, cropped, "
            "unfinished sketch, line art only")

# descricao + tamanho da arte (proporcao parecida com a do vetorial)
PROPS = {
    "balcao":      ("a wooden shop counter: a wide rectangular wooden cabinet with a thick flat top surface and a front made of vertical wooden planks, seen straight from the front, no screen", (1152, 768)),
    "porta":       ("a closed interior door with a grey frame and a round yellow handle, seen straight from the front", (640, 1024)),
    "porta_aberta": ("an open interior door with a grey frame, the door leaf swung inward showing a dark opening, seen straight from the front", (768, 1024)),
    "lixeira":     ("a grey metal trash can with a lid, seen straight from the front", (704, 1024)),
    "cadeira":     ("a simple wooden chair with a straight back, seen straight from the front", (640, 1024)),
    "mesa":        ("an office desk seen straight from the front: a thick wooden top and two solid wooden side panels, with a drawer in the middle", (1152, 640)),
    "fachada":     ("the front facade of a small police station building with a sign board above the door, a door in the middle and two windows, seen straight from the front", (1024, 1024)),
    "caixa_eletronico": ("an ATM cash machine with a screen, a keypad and a cash slot, seen straight from the front", (640, 1024)),
    "sofa":        ("a three-seat sofa with cushions, seen straight from the front", (1152, 576)),
    "cama":        ("a single bed with a pillow and a blanket, seen from the side", (1152, 640)),
    "computador":  ("a desktop computer monitor on a small stand with a keyboard in front, seen straight from the front", (768, 640)),
}


def prompt_prop(nome):
    desc = PROPS[nome][0]
    return ". ".join([
        "simple flat 2D cartoon drawing, not a photo: " + desc,
        "ONE single object, ISOLATED, centred on a plain flat pure white background",
        "the whole object inside the frame, nothing cut by the border",
        "no scenery, no floor, no wall, no ground line, no shadow, no people, no text",
        ESTILO,
    ])


EXTRA = {}     # nome -> (desc, escala, z, sockets) dos props pedidos pela serie


def garantir(pedidos, forca=False):
    """{nome: (desc_en, escala, z)} -> gera o que ainda nao existe em
    lab/props_gerados. Escala = fracao da altura do ator; z tras|entre|frente.
    Sockets: `apoio` no alto e `alvo` no meio, para a mao chegar."""
    for nome, (desc, escala, z) in pedidos.items():
        EXTRA[nome] = (desc, float(escala), z)
        PROPS.setdefault(nome, (desc, (1024, 1024)))
        png = os.path.join(LAB, "props_gerados", nome + ".png")
        if os.path.exists(png) and not forca:
            continue
        gerar(nome, forca=forca)


def _ancoras_gabarito(nome, largura, altura):
    """As ancoras do prop vetorial homonimo, reescaladas para (largura, altura)
    da arte gerada (a caixa do alfa). O vetorial tem margem `m` em volta:
    as fracoes sao medidas contra a caixa do desenho, sem a margem."""
    fn = getattr(PV, nome, None)
    if fn is None:
        if nome in EXTRA:
            desc, escala, z = EXTRA[nome]
            return {"base": [largura / 2.0, float(altura)], "escala": escala, "z": z,
                    "sockets": {"apoio": [[largura * 0.15, altura * 0.12], [largura * 0.85, altura * 0.12]],
                                "alvo": [largura / 2.0, altura * 0.5],
                                "texto": {"rect": [[largura * 0.25, altura * 0.05], [largura * 0.75, altura * 0.25]]}},
                    "origem": "gerado pela serie (props_gerados.garantir)"}
        return {"base": [largura / 2.0, float(altura)], "escala": 0.6, "z": "frente", "sockets": {}}
    tela, anc = fn()
    bb = tela.getbbox() or (0, 0, tela.width, tela.height)
    x0, y0, x1, y1 = bb
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    kx, ky = largura / float(w), altura / float(h)

    def pt(p):
        return [round((p[0] - x0) * kx, 1), round((p[1] - y0) * ky, 1)]

    def conv(v):
        if isinstance(v, dict) and v.get("rect"):
            return {"rect": [pt(v["rect"][0]), pt(v["rect"][1])]}
        if isinstance(v, (list, tuple)) and v and isinstance(v[0], (list, tuple)):
            return [pt(v[0]), pt(v[1])]
        return pt(v)
    novo = {"base": [largura / 2.0, float(altura)], "escala": anc.get("escala", 0.6),
            "z": anc.get("z", "frente"), "sockets": {k: conv(v) for k, v in (anc.get("sockets") or {}).items()},
            "origem": "gerado; ancoras do props_vetor." + nome}
    if anc.get("corte_z") is not None:
        novo["corte_z"] = round((anc["corte_z"] - y0) * ky, 1)
    return novo


def gerar(nome, destino=None, semente=None, forca=False, passos=8):
    destino = destino or os.path.join(LAB, "props_gerados")
    os.makedirs(destino, exist_ok=True)
    png = os.path.join(destino, nome + ".png")
    if os.path.exists(png) and not forca:
        print(f"[props] {nome}: ja existe em {destino} (--forca refaz)")
        return png
    desc, (lg, al) = PROPS[nome]
    print(f"[props] {nome}: pedindo ao sdxl-lightning {lg}x{al} (ou a esteira, tipo lab_prop)...")
    # 16/09: sem token e com o proxy respondendo sem imagem, a esteira
    # `gerar-assets` atende (FLUX, quadrado -- a caixa do alfa decide o tamanho)
    img = WAI.texto_para_imagem(prompt_prop(nome), NEGATIVO, lg, al, modelo=WAI.SDXL, passos=passos,
                                semente=semente, esteira=("lab_prop", nome))
    if img is None:
        print(f"[props] {nome}: sem imagem")
        return None
    buf = io.BytesIO()
    img.save(buf, "PNG")
    from sob_demanda import _recortar_fundo
    rec = _recortar_fundo(buf.getvalue())
    if rec is None:
        img.save(os.path.join(destino, nome + "_bruto.png"))
        print(f"[props] {nome}: o recorte por cor reprovou; bruto salvo para o olho")
        return None
    from objetos_estilo import so_o_objeto
    prop = so_o_objeto(Image.open(io.BytesIO(rec)).convert("RGBA"))
    prop.save(png)
    anc = _ancoras_gabarito(nome, prop.width, prop.height)
    anc["achatado"] = True
    json.dump(anc, open(os.path.join(destino, nome + ".ancoras.json"), "w", encoding="utf-8"), indent=1)
    print(f"[props] {nome}: {prop.width}x{prop.height}, z {anc['z']}, sockets {', '.join(anc['sockets']) or '-'}")
    return png


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = sys.argv[1:]
    nomes = list(PROPS) if "--todos" in opts else args
    if not nomes:
        raise SystemExit(__doc__)
    sem = int(opts[opts.index("--semente") + 1]) if "--semente" in opts else None
    for n in nomes:
        if n not in PROPS:
            print(f"[props] '{n}' nao esta no catalogo: {', '.join(PROPS)}")
            continue
        gerar(n, semente=sem, forca="--forca" in opts)
