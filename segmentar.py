#!/usr/bin/env python3
"""
segmentar — lê a folha do personagem e devolve as peças JÁ SEPARADAS, com o
pivô de cada articulação medido, não estimado.

POR QUE ESTE ARQUIVO SUBSTITUI O RECORTE POR GEOMETRIA
    Até 21/08 as peças saíam de fatiar.py: retângulos cortados de uma
    silhueta, com a articulação chutada por proporção ("o cotovelo fica a
    38% do braço"). Isso produziu, em cascata, quase toda a lista de
    defeitos do vídeo de teste:

      * toda peça terminava numa RETA que a arte não tinha;
      * a reta aparecia como canto assim que o osso girava;
      * a esfera desenhada para disfarçar a reta virou ombreira;
      * o "maxilar" era a cabeça cortada ao meio, com a linha de corte
        atravessando o rosto;
      * e cada peça nova só acrescentava mais uma cicatriz, então subir de
        9 para 22 peças pioraria o personagem em vez de melhorar.

    A saída não foi um recorte melhor: foi parar de recortar. A bíblia
    visual passou a pedir BONECO DE PAPEL -- cada parte do corpo desenhada
    como uma peça de papel separada, com contorno próprio e um vão branco
    entre vizinhas. O rembg apaga o vão junto com o fundo, e a folha chega
    aqui com cada peça já isolada no canal alfa.

    Duas consequências que mudam o projeto inteiro:

    1. NÃO EXISTE MAIS CORTE. A peça termina exatamente onde o desenho
       termina, com o contorno preto inteiro em volta. Não há reta para
       disfarçar, não há esfera de remendo, não há folga de sobreposição.

    2. O PIVÔ É MEDIDO. A articulação é o vão entre duas peças vizinhas:
       o ponto mais próximo entre a borda de uma e a borda da outra. Girar
       as duas em torno desse ponto mantém o vão constante em qualquer
       ângulo -- que é justamente o visual de boneco de papel articulado
       com colchete, e não um defeito a esconder.

    O número de peças deixou de ser limite técnico. Hoje são 24; passar
    para 40 é só a arte trazer mais peças separadas.

QUANDO A ARTE NÃO COLABORA
    Se a folha vier com o corpo todo grudado (o gerador ignorou os vãos),
    `segmentar_corpo` levanta FolhaGrudada. Quem chama decide se cai no
    fatiar.py antigo ou recusa a folha -- este módulo não finge que deu
    certo, porque foi exatamente fingir que produziu os vídeos ruins.
"""
import numpy as np
from PIL import Image


class FolhaGrudada(Exception):
    """A folha não veio em peças separadas: não dá para segmentar."""


# =====================================================================
# Componentes conexos
# =====================================================================
def _rotular(mask):
    """Rotula componentes conexos por RUNS, não pixel a pixel.

    Uma folha de 1024x1024 tem um milhão de pixels e algumas centenas de
    runs por linha. Percorrer runs em vez de pixels é o que faz isto rodar
    em menos de um segundo no runner do GitHub, sem scipy (o Action instala
    só rembg/pillow/numpy)."""
    h, w = mask.shape
    pai = [0]                       # union-find; 0 = fundo

    def raiz(a):
        while pai[a] != a:
            pai[a] = pai[pai[a]]
            a = pai[a]
        return a

    def unir(a, b):
        ra, rb = raiz(a), raiz(b)
        if ra != rb:
            pai[max(ra, rb)] = min(ra, rb)

    rot = np.zeros((h, w), dtype=np.int32)
    anterior = []                   # runs da linha de cima: (ini, fim, rotulo)
    for y in range(h):
        linha = mask[y]
        idx = np.flatnonzero(linha)
        if len(idx) == 0:
            anterior = []
            continue
        quebras = np.flatnonzero(np.diff(idx) > 1)
        inis = np.concatenate(([idx[0]], idx[quebras + 1]))
        fims = np.concatenate((idx[quebras], [idx[-1]]))
        atual = []
        for i0, i1 in zip(inis.tolist(), fims.tolist()):
            vizinhos = [r for r in anterior if r[0] <= i1 and r[1] >= i0]
            if vizinhos:
                r = min(v[2] for v in vizinhos)
                for v in vizinhos:
                    unir(r, v[2])
            else:
                r = len(pai)
                pai.append(r)
            rot[y, i0:i1 + 1] = r
            atual.append((i0, i1, r))
        anterior = atual

    # achata a união e renumera de 1..n
    mapa = {}
    saida = np.zeros_like(rot)
    for r in range(1, len(pai)):
        rr = raiz(r)
        if rr not in mapa:
            mapa[rr] = len(mapa) + 1
    if mapa:
        tabela = np.zeros(len(pai), dtype=np.int32)
        for r in range(1, len(pai)):
            tabela[r] = mapa[raiz(r)]
        saida = tabela[rot]
    return saida, len(mapa)


def _componentes(mask, area_min):
    rot, n = _rotular(mask)
    fora = []
    for r in range(1, n + 1):
        m = rot == r
        area = int(m.sum())
        if area < area_min:
            continue
        ys, xs = np.nonzero(m)
        fora.append({
            "mask": m, "area": area,
            "bbox": (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())),
            "cx": float(xs.mean()), "cy": float(ys.mean()),
        })
    return fora


def _borda(m):
    """Pixels de contorno do componente, como (N,2) em (x, y)."""
    e = m.copy()
    e[1:, :] &= m[:-1, :]
    e[:-1, :] &= m[1:, :]
    e[:, 1:] &= m[:, :-1]
    e[:, :-1] &= m[:, 1:]
    ys, xs = np.nonzero(m & ~e)
    if len(xs) == 0:
        ys, xs = np.nonzero(m)
    return np.column_stack([xs, ys]).astype(float)


def pivo_entre(a, b, amostra=1400):
    """O ponto de articulação entre duas peças vizinhas.

    É o meio do VÃO: o par de pontos mais próximo entre a borda de uma peça
    e a borda da outra, e o ponto médio entre eles. Girar as duas peças em
    torno desse ponto preserva o vão em qualquer ângulo.

    Isto é o coração da mudança. Antes o pivô vinha de proporção ("o ombro
    fica a 82% da meia-largura do tronco") e errava sempre que a arte não
    era simétrica -- a manga jogava o ombro para fora do osso e o braço
    saía descolado. Agora o pivô sai do desenho: onde a arte deixou o vão,
    é ali que a peça gira."""
    pa, pb = _borda(a["mask"]), _borda(b["mask"])
    # subamostra: a distância mínima entre dois contornos não muda de forma
    # relevante com 1400 pontos em vez de 12 mil, e o par a par fica barato
    if len(pa) > amostra:
        pa = pa[np.linspace(0, len(pa) - 1, amostra).astype(int)]
    if len(pb) > amostra:
        pb = pb[np.linspace(0, len(pb) - 1, amostra).astype(int)]
    d2 = ((pa[:, None, :] - pb[None, :, :]) ** 2).sum(axis=2)
    i, j = np.unravel_index(int(np.argmin(d2)), d2.shape)
    return ((pa[i][0] + pb[j][0]) / 2.0, (pa[i][1] + pb[j][1]) / 2.0), float(np.sqrt(d2[i, j]))


# =====================================================================
# Nomeação das peças macro
# =====================================================================
def _lado(c, centro_x):
    return "e" if c["cx"] < centro_x else "d"


def nomear_corpo(comps, figura):
    """Componentes soltos -> nomes de osso, pela posição em pose T.

    Nada aqui depende de proporção do personagem: depende de topologia.
    Cabeça é a peça mais alta; braço é o que está fora da coluna do tronco
    na altura dos ombros; ordem dentro do membro é distância crescente do
    centro. Personagem de cabeça grande e personagem realista caem no mesmo
    caminho."""
    x0, y0, x1, y1 = figura
    centro_x = (x0 + x1) / 2.0
    alt = y1 - y0 + 1
    nomes = {}

    # a coluna central: peças que cruzam o centro horizontal
    centrais = sorted([c for c in comps if c["bbox"][0] <= centro_x <= c["bbox"][2]],
                      key=lambda c: c["cy"])
    if len(centrais) < 3:
        raise FolhaGrudada(
            f"achei só {len(centrais)} peças na coluna central; a folha "
            f"provavelmente veio com o corpo grudado")

    # cabeça é a mais alta da coluna. Mandíbula, se existir, é a peça
    # central logo abaixo dela e mais estreita.
    nomes[id(centrais[0])] = "cabeca"
    resto = centrais[1:]

    # Mandíbula e pescoço são os dois candidatos logo abaixo da cabeça, e
    # se distinguem pela LARGURA: o queixo é quase tão largo quanto o
    # crânio, o pescoço é bem mais estreito. Sem esta distinção o pescoço
    # era promovido a mandíbula e todo o resto da coluna descia um degrau.
    larg_cab = centrais[0]["bbox"][2] - centrais[0]["bbox"][0]
    i = 0
    if resto and (resto[i]["bbox"][2] - resto[i]["bbox"][0]) > larg_cab * 0.45 \
            and (resto[i]["bbox"][3] - resto[i]["bbox"][1]) < alt * 0.12:
        nomes[id(resto[i])] = "mandibula"
        i += 1
    # pescoço: a peça mais estreita da coluna acima do tronco
    if i < len(resto):
        nomes[id(resto[i])] = "pescoco"
        i += 1
    # peito e abdômen: as duas maiores que sobram na coluna, de cima
    # para baixo. Se a folha vier com um tronco só, ele é o peito e o
    # abdômen vira o mesmo componente -- o rig aguenta, perde a torção.
    tronco = sorted(sorted(resto[i:], key=lambda c: -c["area"])[:2],
                    key=lambda c: c["cy"])
    if len(tronco) == 1:
        nomes[id(tronco[0])] = "peito"
        nomes.setdefault(id(tronco[0]), "peito")
        tronco = tronco * 2
    for nome, c in zip(("peito", "abdomen"), tronco):
        nomes[id(c)] = nome

    peito = next((c for c in comps if nomes.get(id(c)) == "peito"), None)
    abdomen = next((c for c in comps if nomes.get(id(c)) == "abdomen"), None)
    if peito is None or abdomen is None:
        raise FolhaGrudada("não achei peito e abdômen como peças separadas")

    y_ombro = peito["bbox"][1]
    y_quadril = abdomen["bbox"][3]

    # braços: fora da coluna do tronco, acima da virilha. Ordem dentro do
    # membro = distância crescente do centro do corpo.
    for lado in ("e", "d"):
        membro = [c for c in comps if id(c) not in nomes
                  and _lado(c, centro_x) == lado
                  and c["cy"] < (y_ombro + y_quadril) / 2 + alt * 0.06]
        membro.sort(key=lambda c: abs(c["cx"] - centro_x))
        for nome, c in zip(("braco_sup_", "braco_inf_", "mao_"), membro):
            nomes[id(c)] = nome + lado

    # pernas: abaixo do quadril, ordem = de cima para baixo
    for lado in ("e", "d"):
        membro = [c for c in comps if id(c) not in nomes
                  and _lado(c, centro_x) == lado and c["cy"] > y_quadril]
        membro.sort(key=lambda c: c["cy"])
        for nome, c in zip(("perna_sup_", "perna_inf_", "pe_"), membro):
            nomes[id(c)] = nome + lado

    return nomes


# =====================================================================
# Rosto: sub-regiões dentro da peça da cabeça
# =====================================================================
def _regioes_de_cor(img, comp, min_frac=0.004):
    """Ilhas de cor sólida dentro de uma peça.

    O rosto não vem em peças separadas -- olho, sobrancelha e nariz são
    desenhados DENTRO do crânio. Mas em arte chapada cada um deles é uma
    região de cor uniforme, então basta agrupar por cor e rotular. Não é
    chute: é a mesma leitura de pixel que separou as peças macro."""
    a = np.array(img.convert("RGB"))
    m = comp["mask"]
    # quantiza grosso: variação de compressão JPEG não pode virar região
    q = (a // 26).astype(np.int16)
    chave = q[..., 0] * 10000 + q[..., 1] * 100 + q[..., 2]
    area_min = max(int(comp["area"] * min_frac), 24)
    fora = []
    for cor in np.unique(chave[m]):
        sub = m & (chave == cor)
        if sub.sum() < area_min:
            continue
        for c in _componentes(sub, area_min):
            c["cor"] = tuple(int(v) for v in a[c["mask"]].mean(axis=0))
            fora.append(c)
    return fora


def nomear_rosto(regioes, cabeca):
    """Regiões do rosto -> cabelo, crânio, olhos, sobrancelhas, nariz.

    Classifica por luminância e posição, que é como um humano faria de
    relance: o cabelo é a mancha escura que encosta no topo; os olhos são
    o par escuro e pequeno na metade de cima; a sobrancelha é o par escuro
    e achatado acima deles; o crânio é o que sobrou, e é o maior."""
    x0, y0, x1, y1 = cabeca["bbox"]
    alt = max(y1 - y0, 1)
    cx = (x0 + x1) / 2.0
    nomes = {}

    def lum(c):
        return sum(c["cor"]) / 3.0

    resto = sorted(regioes, key=lambda c: -c["area"])
    if not resto:
        return nomes
    nomes[id(resto[0])] = "cranio"

    escuras = [c for c in resto[1:] if lum(c) < 120]
    # cabelo: a maior mancha escura que encosta no topo da cabeça
    topo = [c for c in escuras if c["bbox"][1] <= y0 + alt * 0.18]
    if topo:
        cabelo = max(topo, key=lambda c: c["area"])
        nomes[id(cabelo)] = "cabelo"

    pequenas = [c for c in escuras if id(c) not in nomes]
    # olhos: par mais próximo em y, na metade de cima, tamanho parecido
    meio = [c for c in pequenas if y0 + alt * 0.22 < c["cy"] < y0 + alt * 0.72]
    meio.sort(key=lambda c: c["cx"])
    par = _achar_par(meio, cx)
    if par:
        nomes[id(par[0])] = "olho_e"
        nomes[id(par[1])] = "olho_d"
        acima = [c for c in pequenas if id(c) not in nomes
                 and c["cy"] < min(par[0]["cy"], par[1]["cy"])]
        acima.sort(key=lambda c: c["cx"])
        p2 = _achar_par(acima, cx)
        if p2:
            nomes[id(p2[0])] = "sobrancelha_e"
            nomes[id(p2[1])] = "sobrancelha_d"

    # MANDÍBULA: quando o queixo é uma peça de papel própria, ele aparece
    # aqui como uma região clara e grande no terço de baixo da cabeça. É a
    # diferença entre um maxilar de verdade e a cabeça cortada ao meio que
    # apareceu no vídeo de teste.
    sobrou = [c for c in regioes if id(c) not in nomes]
    queixo = [c for c in sobrou
              if lum(c) >= 120 and c["cy"] > y0 + alt * 0.60
              and c["area"] > cabeca["area"] * 0.03]
    if queixo:
        mand = max(queixo, key=lambda c: c["area"])
        nomes[id(mand)] = "mandibula"

    # BOCA: mancha escura na metade de baixo (dentro do queixo, se houver)
    sobrou = [c for c in regioes if id(c) not in nomes]
    bocas = [c for c in sobrou if lum(c) < 150 and c["cy"] > y0 + alt * 0.55]
    if bocas:
        nomes[id(max(bocas, key=lambda c: c["area"]))] = "boca"

    # NARIZ: o que sobrou perto do eixo, no meio da cara
    sobrou = [c for c in regioes if id(c) not in nomes]
    perto = [c for c in sobrou if abs(c["cx"] - cx) < (x1 - x0) * 0.16
             and y0 + alt * 0.30 < c["cy"] < y0 + alt * 0.75
             and c["area"] < cabeca["area"] * 0.05]
    if perto:
        nomes[id(max(perto, key=lambda c: c["area"]))] = "nariz"
    return nomes


def _achar_par(cands, cx, tol_y=0.35, tol_area=2.2):
    """O par simétrico mais convincente de uma lista de regiões."""
    melhor, melhor_erro = None, None
    for i in range(len(cands)):
        for j in range(i + 1, len(cands)):
            a, b = cands[i], cands[j]
            if (a["cx"] - cx) * (b["cx"] - cx) >= 0:      # tem que ser um de cada lado
                continue
            alt = max(abs(a["bbox"][3] - a["bbox"][1]), 1)
            if abs(a["cy"] - b["cy"]) > alt * tol_y:
                continue
            r = max(a["area"], b["area"]) / max(min(a["area"], b["area"]), 1)
            if r > tol_area:
                continue
            erro = abs(abs(a["cx"] - cx) - abs(b["cx"] - cx)) + abs(a["cy"] - b["cy"])
            if melhor_erro is None or erro < melhor_erro:
                melhor_erro, melhor = erro, (a, b) if a["cx"] < b["cx"] else (b, a)
    return melhor


# =====================================================================
# Entrada principal
# =====================================================================
def segmentar_corpo(img, esqueleto, min_frac_area=0.0012):
    """Folha -> (peças, âncoras).

    esqueleto: {peça: peça_pai}, com None na raiz. Vem de
    folha_personagem.py -- este módulo não conhece vocabulário de rig, só
    sabe achar ilhas e medir vãos."""
    img = img.convert("RGBA")
    mask = np.array(img.split()[-1]) > 10
    if not mask.any():
        raise FolhaGrudada("folha vazia")
    ys, xs = np.nonzero(mask)
    figura = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    area_fig = (figura[2] - figura[0] + 1) * (figura[3] - figura[1] + 1)

    comps = _componentes(mask, area_min=max(int(area_fig * min_frac_area), 40))
    if len(comps) < 8:
        raise FolhaGrudada(
            f"a folha veio com {len(comps)} peças soltas; um boneco de papel "
            f"tem pelo menos 14. O gerador provavelmente ignorou os vãos "
            f"entre as partes")

    nomes = nomear_corpo(comps, figura)
    por_nome = {n: c for c, n in ((c, nomes.get(id(c))) for c in comps) if n}

    # rosto: regiões de cor dentro da peça da cabeça
    if "cabeca" in por_nome:
        regs = _regioes_de_cor(img, por_nome["cabeca"])
        rotulos = nomear_rosto(regs, por_nome["cabeca"])
        for c in regs:
            n = rotulos.get(id(c))
            if n:
                # a região de cor mede o vão pela PEÇA que a contém: o
                # crânio não faz fronteira com o pescoço, quem faz é a
                # cabeça inteira. Sem isto o "vão" do crânio dava 87px e
                # o pivô da cabeça ia parar no meio da testa.
                c["hospedeiro"] = por_nome["cabeca"]
                por_nome[n] = c
        # a peça inteira da cabeça deixa de ser desenhada: quem entra é o
        # crânio, e as feições vêm por cima
        if "cranio" in por_nome:
            por_nome.pop("cabeca", None)

    # Mandíbula como peça de papel separada (o gerador deixou vão no
    # queixo): a boca está dentro dela, não dentro do crânio.
    if "mandibula" in por_nome and "boca" not in por_nome:
        regs = _regioes_de_cor(img, por_nome["mandibula"])
        if len(regs) > 1:
            por_nome["boca"] = min(regs[1:], key=lambda c: sum(c["cor"]))

    pecas, caixas = {}, {}
    for nome, c in por_nome.items():
        bx0, by0, bx1, by1 = c["bbox"]
        recorte = img.crop((bx0, by0, bx1 + 1, by1 + 1)).copy()
        alfa = np.array(recorte.split()[-1])
        alfa[~c["mask"][by0:by1 + 1, bx0:bx1 + 1]] = 0
        recorte.putalpha(Image.fromarray(alfa))
        pecas[nome] = recorte
        caixas[nome] = (bx0, by0)

    # --- pivôs: o meio do vão entre cada peça e o pai dela
    pivos, vaos = {}, {}
    for nome, pai in esqueleto.items():
        if nome not in por_nome:
            continue
        if pai is None or pai not in por_nome:
            # raiz (ou pai ausente): ancora na base central da própria peça
            p = pecas[nome]
            pivos[nome] = [p.size[0] / 2.0, p.size[1] - 1.0]
            continue
        hp = por_nome[pai].get("hospedeiro", por_nome[pai])
        hf = por_nome[nome].get("hospedeiro", por_nome[nome])
        if hp is hf:
            # peças desenhadas DENTRO da mesma peça de papel (olho no
            # crânio, boca no queixo) não articulam: acompanham. O ponto
            # de encaixe é o próprio centro delas, e assim a feição cai
            # exatamente onde o desenhista a pôs.
            c = por_nome[nome]
            ponto = ((c["bbox"][0] + c["bbox"][2]) / 2.0,
                     (c["bbox"][1] + c["bbox"][3]) / 2.0)
            folga = 0.0
        else:
            ponto, folga = pivo_entre(hp, hf)
        bx, by = caixas[nome]
        pivos[nome] = [ponto[0] - bx, ponto[1] - by]
        vaos[nome] = round(folga, 1)
        # o pai guarda, em coordenada dele, o mesmo ponto: é lá que o filho
        # vai ser colado, e é assim que o comprimento do osso sai medido
        pbx, pby = caixas[pai]
        por_nome[pai].setdefault("saidas", {})[nome] = (ponto[0] - pbx, ponto[1] - pby)

    comprimentos = {}
    for nome, c in por_nome.items():
        saidas = c.get("saidas", {})
        piv = pivos.get(nome)
        if piv is None:
            continue
        if saidas:
            # comprimento até a próxima articulação (a mais distante, se
            # houver mais de um filho: é ela que define o alcance do osso)
            comprimentos[nome] = max(
                float(np.hypot(sx - piv[0], sy - piv[1])) for sx, sy in saidas.values())
        else:
            a = np.array(pecas[nome].split()[-1]) > 10
            ys2, xs2 = np.nonzero(a)
            comprimentos[nome] = float(np.hypot(xs2 - piv[0], ys2 - piv[1]).max()) if len(xs2) else 1.0

    ancoras = {
        "caixas": {k: [int(v[0]), int(v[1])] for k, v in caixas.items()},
        "pivos": {k: [round(v[0], 1), round(v[1], 1)] for k, v in pivos.items()},
        "comprimentos": {k: round(v, 1) for k, v in comprimentos.items()},
        "saidas": {n: {f: [round(p[0], 1), round(p[1], 1)]
                       for f, p in c.get("saidas", {}).items()}
                   for n, c in por_nome.items() if c.get("saidas")},
        "vaos": vaos,
        "altura_figura": figura[3] - figura[1] + 1,
    }
    return pecas, ancoras


def mapa_de_pecas(img, pecas, ancoras):
    """Imagem de conferência: cada peça pintada de uma cor, o pivô marcado.

    Existe porque um partes.json com 24 entradas não diz a ninguém se o
    ombro foi parar no cotovelo. O mapa diz, em um olhar, antes dos treze
    minutos de render."""
    from PIL import ImageDraw
    paleta = [(228, 87, 74), (240, 154, 82), (233, 196, 78), (129, 181, 106),
              (86, 170, 158), (92, 141, 200), (140, 116, 198), (206, 106, 168),
              (176, 140, 96), (120, 160, 120), (200, 120, 120), (110, 170, 200)]
    tela = Image.new("RGB", img.size, (24, 28, 26))
    d = ImageDraw.Draw(tela)
    caixas = ancoras.get("caixas", {})
    for i, (nome, p) in enumerate(sorted(pecas.items())):
        cor = paleta[i % len(paleta)]
        ox, oy = caixas.get(nome, (0, 0))
        tela.paste(Image.new("RGB", p.size, cor), (ox, oy), p)
    # o pivô marcado em cima da peça é o que denuncia ombro virando cotovelo
    for nome, piv in ancoras.get("pivos", {}).items():
        ox, oy = caixas.get(nome, (0, 0))
        x, y = ox + piv[0], oy + piv[1]
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(255, 255, 255), outline=(0, 0, 0), width=2)
    return tela
