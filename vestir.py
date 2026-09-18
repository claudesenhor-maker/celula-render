# -*- coding: utf-8 -*-
"""vestir.py -- troca a ROUPA de um personagem repintando a folha por
inpainting, dentro da silhueta das pecas de tecido. (15/09, pedido do dono:
"uma forma melhor de gerar e trocar as roupas com melhor qualidade".)

POR QUE ASSIM, E NAO GERANDO OUTRA FOLHA
    Gerar uma folha nova "de uniforme" muda tudo: proporcao, cara, vaos,
    pivos -- e o `parecidos.py` ja mostrou que a mesma descricao rende
    outra pessoa. Recolorir por matiz (`roupas.recolorir`) preserva tudo,
    mas so muda a cor: nao poe gola, botao, distintivo, bolso, textura.

    O meio-termo que fica com o melhor dos dois: a folha ORIGINAL vai para
    o modelo de inpainting com uma mascara que cobre so o INTERIOR das
    pecas de tecido (peito, abdomen, mangas, pernas), com o contorno preto
    de fora. O modelo repinta o tecido -- uniforme, jaleco, terno, avental
    -- e nao pode mexer em silhueta, contorno, vao, cabeca, mao ou pe. As
    pecas repintadas sao recortadas com as MESMAS mascaras e caixas, entao
    o `partes.json` (pivos, saidas, comprimentos, vaos) e' o mesmo arquivo.
    O personagem continua sendo ele; so a roupa e' outra.

O QUE SAI
    lab/prod_<chave>__<traje>/  com as pecas de tecido trocadas, as outras
    copiadas, e o partes.json identico. `cartao.py` (e o motor de cena, se
    quiser) usam a pasta como se fosse outro personagem.

USO
    python vestir.py pal delegado                 # traje do catalogo TRAJES
    python vestir.py pal "white lab coat" --nome medico
    python vestir.py pal delegado --so-mascara    # so' desenha a mascara (sem IA)
    python vestir.py pal delegado --forca 0.9 --semente 7

    Precisa da Workers AI (workers_ai.py): CF_API_TOKEN ou o proxy do n8n.
"""
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageFilter

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
LAB = os.path.join(RAIZ, "lab")
sys.path.insert(0, AQUI)

# pecas que sao TECIDO na folha em T (as mangas curtas ficam no braco_sup;
# `--mangas-longas` inclui o antebraco)
PECAS_TECIDO = ("peito", "abdomen", "braco_sup_e", "braco_sup_d",
                "perna_sup_e", "perna_sup_d", "perna_inf_e", "perna_inf_d")
PECAS_MANGA_LONGA = ("braco_inf_e", "braco_inf_d")

# O contorno preto fica FORA da mascara: e' ele que segura o estilo do canal
# e a leitura da silhueta. Medido pelo contorno.py: 3-6 px nas folhas atuais.
CONTORNO_PX = 5

ESTILO = ("flat 2D cartoon character sheet, thick clean black outlines, flat solid "
          "colors, simple cel shading, no gradients, plain white background, "
          "same character, same pose, ")
NEGATIVO = ("photo, photorealistic, 3d render, realistic skin, gradient, blur, "
            "noise, text, watermark, extra limbs, extra arms, different pose, "
            "nudity, muscles, complex pattern")

TRAJES = {
    "delegado": "wearing a dark blue police uniform shirt with a silver badge and "
                "shoulder patches, and dark navy uniform trousers",
    "policial": "wearing a dark blue police uniform shirt with a silver badge, "
                "and dark navy uniform trousers",
    "medico": "wearing a white doctor's lab coat over a light blue shirt, and "
              "light gray trousers",
    "enfermeiro": "wearing light blue medical scrubs top and light blue scrub pants",
    "chefe": "wearing a black business suit jacket over a white shirt with a red "
             "tie, and black suit trousers",
    "advogado": "wearing a black formal suit jacket, white shirt, red tie, and "
                "black trousers",
    "rh": "wearing a green sleeveless vest over a light shirt, with a name badge, "
          "and gray trousers",
    "atendente": "wearing a white short-sleeve polo shirt with a small company "
                 "logo, and beige trousers",
    "gerente": "wearing a gray-blue bank uniform shirt with a name tag, and dark "
               "trousers",
    "pedreiro": "wearing an orange construction work overall with reflective "
                "stripes",
    "cozinheiro": "wearing a white chef jacket with an apron, and checkered "
                  "black-and-white trousers",
    "garcom": "wearing a black vest over a white shirt with a bow tie, and black "
              "trousers",
    "mecanico": "wearing a blue mechanic's coverall with grease stains and a "
                "name patch",
    "preso": "wearing an orange prison jumpsuit with a number on the chest",
    "soldado": "wearing a green camouflage military uniform shirt and trousers",
    "carteiro": "wearing a yellow-and-blue postal service uniform shirt and "
                "dark blue trousers",
    "entregador": "wearing a red delivery service t-shirt with a logo and black "
                  "shorts",
    "professor": "wearing a brown tweed blazer over a shirt with an elbow patch, "
                 "and khaki trousers",
    "noivo": "wearing a black tuxedo with a bow tie and white shirt",
    "rei": "wearing a red royal robe with white fur trim and gold details",
}


def _sobre_branco(img):
    """A folha tem alfa; para o modelo (e para o olho) o fundo e' BRANCO,
    como a folha foi gerada -- `convert('RGB')` daria preto."""
    base = Image.new("RGB", img.size, (255, 255, 255))
    base.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
    return base


def _pasta_prod(chave):
    for cand in (f"prod_{chave}", f"pecas_{chave}", chave):
        p = os.path.join(LAB, cand)
        if os.path.exists(os.path.join(p, "partes.json")):
            return p
    raise SystemExit(f"nao achei a pasta de pecas de '{chave}' em lab/")


def _folha(chave):
    for cand in (os.path.join(LAB, "folhas", chave + ".png"),
                 os.path.join(LAB, "folhas_novas", chave + ".png")):
        if os.path.exists(cand):
            return cand
    raise SystemExit(f"nao achei a folha de '{chave}' em lab/folhas/")


def localizar_pecas(folha, pasta):
    """{peca: (x, y)} -- onde cada PNG de producao esta' dentro da folha.

    As pecas de producao sao recortes diretos da folha (mesma escala): a
    segmentacao da folha devolve as mesmas caixas. Quando o tamanho bate,
    a caixa e' aceita; senao a peca e' procurada por igualdade de pixels.
    """
    from folha_personagem import segmentar_folha
    pecas_seg, anc = segmentar_folha(folha)
    caixas = anc["caixas"]
    onde = {}
    fa = np.asarray(folha.convert("RGBA"))
    for nome in os.listdir(pasta):
        if not nome.endswith(".png") or nome.startswith("_"):
            continue
        n = nome[:-4]
        p = Image.open(os.path.join(pasta, nome)).convert("RGBA")
        if n in pecas_seg and pecas_seg[n].size == p.size:
            onde[n] = tuple(caixas[n])
            continue
        # procura por pixels: 40 amostras opacas da peca contra a folha
        pa = np.asarray(p)
        ys, xs = np.nonzero(pa[..., 3] > 200)
        if len(xs) == 0:
            continue
        idx = np.linspace(0, len(xs) - 1, 40).astype(int)
        H, W = fa.shape[:2]
        h, w = pa.shape[:2]
        ok = np.ones((H - h + 1, W - w + 1), dtype=bool)
        for i in idx:
            x, y = xs[i], ys[i]
            cor = pa[y, x, :3]
            janela = fa[y:y + H - h + 1, x:x + W - w + 1, :3]
            ok &= np.all(np.abs(janela.astype(int) - cor.astype(int)) <= 8, axis=-1)
            if not ok.any():
                break
        pos = np.argwhere(ok)
        if len(pos):
            onde[n] = (int(pos[0][1]), int(pos[0][0]))
    return onde


def mascara_tecido(folha, pasta, onde, pecas=PECAS_TECIDO, contorno=CONTORNO_PX):
    """Mascara branca no INTERIOR das pecas de tecido (contorno de fora)."""
    m = np.zeros((folha.height, folha.width), dtype=np.uint8)
    for n in pecas:
        if n not in onde:
            continue
        p = Image.open(os.path.join(pasta, n + ".png")).convert("RGBA")
        a = np.asarray(p)[..., 3] > 128
        # o contorno preto da peca e' a borda escura; erodindo pela
        # espessura dele a mascara fica so' no tecido
        pm = Image.fromarray(a.astype(np.uint8) * 255)
        for _ in range(max(1, contorno)):
            pm = pm.filter(ImageFilter.MinFilter(3))
        x, y = onde[n]
        sub = m[y:y + p.height, x:x + p.width]
        sub |= np.asarray(pm)[:sub.shape[0], :sub.shape[1]]
    return Image.fromarray(m)


def aplicar(folha_nova, folha, pasta, onde, mask, destino, pecas=PECAS_TECIDO):
    """Copia a pasta e troca o RGB das pecas de tecido pelo da folha nova
    onde a mascara permite. Alfa e partes.json nao mudam."""
    os.makedirs(destino, exist_ok=True)
    for nome in os.listdir(pasta):
        src = os.path.join(pasta, nome)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(destino, nome))
    fn = np.asarray(folha_nova.convert("RGB").resize(folha.size, Image.LANCZOS))
    mk = np.asarray(mask) > 128
    trocadas = []
    for n in pecas:
        if n not in onde:
            continue
        x, y = onde[n]
        p = Image.open(os.path.join(pasta, n + ".png")).convert("RGBA")
        pa = np.array(p)
        h, w = pa.shape[:2]
        novo = fn[y:y + h, x:x + w]
        m = mk[y:y + h, x:x + w] & (pa[..., 3] > 0)
        pa[..., :3][m] = novo[m]
        Image.fromarray(pa).save(os.path.join(destino, n + ".png"))
        trocadas.append(n)
    return trocadas


def vestir(chave, traje, nome=None, forca=1.0, guia=8.0, passos=25, semente=None,
           mangas_longas=False, so_mascara=False, modelo=None):
    pasta = _pasta_prod(chave)
    folha = Image.open(_folha(chave)).convert("RGBA")
    pecas = PECAS_TECIDO + (PECAS_MANGA_LONGA if mangas_longas else ())
    onde = localizar_pecas(folha, pasta)
    faltam = [p for p in pecas if p not in onde]
    if faltam:
        print(f"[vestir] nao localizei na folha: {', '.join(faltam)}")
    mask = mascara_tecido(folha, pasta, onde, pecas)
    nome = nome or (traje if traje in TRAJES else "traje")
    saida_dir = os.path.join(RAIZ, "tmp", "vestir")
    os.makedirs(saida_dir, exist_ok=True)
    prova = _sobre_branco(folha)
    veu = Image.new("RGB", folha.size, (255, 0, 200))
    prova = Image.composite(Image.blend(prova, veu, 0.55), prova, mask)
    prova.save(os.path.join(saida_dir, f"{chave}_{nome}_mascara.png"))
    frac = float(np.asarray(mask).mean() / 255.0)
    print(f"[vestir] mascara: {frac:.1%} da folha, {len(onde)} pecas localizadas "
          f"-> tmp/vestir/{chave}_{nome}_mascara.png")
    if so_mascara:
        return None
    import workers_ai as WAI
    prompt = ESTILO + (TRAJES.get(traje, traje))
    # a folha nao e' quadrada nem multipla de 64: o modelo trabalha numa
    # copia ajustada e o resultado volta ao tamanho original
    W64 = (folha.width // 64) * 64
    H64 = (folha.height // 64) * 64
    base = _sobre_branco(folha).resize((W64, H64), Image.LANCZOS)
    mk = mask.resize((W64, H64), Image.NEAREST)
    print(f"[vestir] inpainting {W64}x{H64}: {prompt[len(ESTILO):]}")
    nova = WAI.inpaint(base, mk, prompt, NEGATIVO, forca=forca, guia=guia,
                       passos=passos, semente=semente, modelo=modelo or WAI.INPAINT)
    if nova is None:
        print("[vestir] sem imagem; nada foi escrito")
        return None
    nova.save(os.path.join(saida_dir, f"{chave}_{nome}_folha.png"))
    destino = os.path.join(LAB, f"{os.path.basename(pasta)}__{nome}")
    trocadas = aplicar(nova, folha, pasta, onde, mask, destino, pecas)
    # a folha inteira remontada, para o olho: o que o modelo pintou, so'
    # dentro da mascara
    monta = np.array(_sobre_branco(folha))
    fn = np.asarray(nova.resize(folha.size, Image.LANCZOS))
    mkk = np.asarray(mask) > 128
    monta[mkk] = fn[mkk]
    Image.fromarray(monta).save(os.path.join(saida_dir, f"{chave}_{nome}_montada.png"))
    print(f"[vestir] {destino}: {', '.join(trocadas)}; conferir tmp/vestir/{chave}_{nome}_montada.png")
    return destino


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        raise SystemExit(__doc__)
    opts = sys.argv[1:]

    def _opt(nome, padrao=None):
        if f"--{nome}" in opts:
            i = opts.index(f"--{nome}")
            return opts[i + 1] if i + 1 < len(opts) else padrao
        return padrao
    vestir(args[0], args[1], nome=_opt("nome"),
           forca=float(_opt("forca", 1.0)), guia=float(_opt("guia", 8.0)),
           passos=int(_opt("passos", 25)),
           semente=int(_opt("semente")) if _opt("semente") else None,
           mangas_longas="--mangas-longas" in opts, so_mascara="--so-mascara" in opts,
           modelo=_opt("modelo"))
