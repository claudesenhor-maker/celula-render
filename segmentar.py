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
import math
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


def pivo_entre(a, b, amostra=1400, devolver_faixa=False):
    """O ponto de articulação entre duas peças vizinhas.

    É o meio do VÃO -- mas o meio da FAIXA inteira em que as duas peças se
    encaram, não o par de pontos mais próximo. Girar as duas peças em torno
    desse ponto preserva o vão em qualquer ângulo.

    Isto é o coração da mudança. Antes o pivô vinha de proporção ("o ombro
    fica a 82% da meia-largura do tronco") e errava sempre que a arte não
    era simétrica -- a manga jogava o ombro para fora do osso e o braço
    saía descolado. Agora o pivô sai do desenho: onde a arte deixou o vão,
    é ali que a peça gira.

    POR QUE NÃO É O PAR MAIS PRÓXIMO (corrigido em 27/08, ver `_mapa.png`)
        Num boneco de papel as duas bordas de uma junta são quase
        PARALELAS: ao longo de toda a faixa a distância é praticamente a
        mesma, e qual par ganha o `argmin` é decidido por meio pixel de
        ruído de contorno. O resultado era um pivô encostado numa PONTA da
        faixa -- e ele saía numa ponta diferente em cada junta, o que fazia
        o mapa parecer aleatório: ombro esquerdo na quina de cima, ombro
        direito na quina de baixo, joelho na lateral externa da coxa.
        Girar por ali arranca a peça da junta em vez de dobrá-la.

        A correção é ler a faixa inteira em vez de um par: todos os pares
        cuja distância chega perto da mínima, com peso maior para os mais
        estreitos. O centro dessa nuvem é o meio geométrico do vão, que é
        onde o colchete de um boneco articulado fica. Peças encostadas
        (vão zero, ver `_dividir_por_cor`) já eram tratadas assim desde
        26/08 -- agora vale para toda junta, com vão ou sem.

    Devolve ((x, y), vão medido em pixels).
    """
    pa, pb = _borda(a["mask"]), _borda(b["mask"])
    # subamostra: a distância mínima entre dois contornos não muda de forma
    # relevante com 1400 pontos em vez de 12 mil, e o par a par fica barato
    if len(pa) > amostra:
        pa = pa[np.linspace(0, len(pa) - 1, amostra).astype(int)]
    if len(pb) > amostra:
        pb = pb[np.linspace(0, len(pb) - 1, amostra).astype(int)]
    d2 = ((pa[:, None, :] - pb[None, :, :]) ** 2).sum(axis=2)
    dmin = float(np.sqrt(d2.min()))

    # A FAIXA: pares que chegam perto do mínimo. A tolerância cresce com o
    # vão (uma junta de 12px de folga tem a faixa inteira entre 12 e ~19px)
    # mas nunca abaixo de 2px, que é o ruído de serrilhado do contorno.
    tol = max(2.0, dmin * 0.6)
    ia, ib = np.nonzero(d2 <= (dmin + tol) ** 2)
    meios = (pa[ia] + pb[ib]) / 2.0
    dist = np.sqrt(d2[ia, ib])
    # peso maior para o par mais estreito: se a faixa afunila de um lado
    # (a manga que desce sobre a axila), é ali que a junta está
    peso = np.exp(-(((dist - dmin) / tol) ** 2))

    meios, peso = _um_ponto_por_pixel(meios, peso)
    meios, peso = _faixas_da_junta(meios, peso, dmin)
    w = float(peso.sum())
    if w <= 0:
        i, j = np.unravel_index(int(np.argmin(d2)), d2.shape)
        return ((pa[i][0] + pb[j][0]) / 2.0, (pa[i][1] + pb[j][1]) / 2.0), dmin
    ponto = (float((meios[:, 0] * peso).sum() / w),
             float((meios[:, 1] * peso).sum() / w))
    if devolver_faixa:
        return ponto, dmin, meios
    return ponto, dmin


def _um_ponto_por_pixel(meios, peso):
    """Colapsa a nuvem de pares num ponto por pixel, com o maior peso.

    Sem isto a média é puxada para onde há MAIS PARES, não para onde a
    junta está: um ponto da borda côncava enxerga uma dezena de vizinhos
    dentro da tolerância, um ponto da borda convexa enxerga dois. Na
    fronteira do pescoço isso deslocava o pivô 40px para o lado em que a
    gola é mais funda -- nos dois personagens, sempre para o mesmo lado."""
    chave = np.round(meios).astype(np.int64)
    chave = (chave[:, 0] - chave[:, 0].min()) * 100000 + (chave[:, 1] - chave[:, 1].min())
    ordem = np.argsort(chave, kind="stable")
    chave, meios, peso = chave[ordem], meios[ordem], peso[ordem]
    corte = np.flatnonzero(np.diff(chave)) + 1
    grupos = np.split(np.arange(len(chave)), corte)
    idx = np.array([g[int(np.argmax(peso[g]))] for g in grupos])
    return meios[idx], peso[idx]


def _faixas_da_junta(meios, peso, dmin, fracao=0.4):
    """Os trechos de aproximação que formam a junta, sem os que não formam.

    Duas peças raramente se encaram por uma faixa só. Uma junta em
    ferradura -- a cabeça dentro do decote -- toca a vizinha nos DOIS
    cantos da gola e se afasta no meio do V: são dois trechos de peso
    parecido, e a junta é o centro entre eles, não um dos cantos. Já a mão
    que volta a chegar perto do antebraço pelo polegar produz um trecho
    minúsculo ao lado do vão de verdade, e esse não pode entrar na conta.

    A diferença entre os dois casos é o PESO: entram os trechos que chegam
    a `fracao` do mais forte, e o resto é descartado. Sem esta regra, o
    pivô do pescoço ia parar num canto do decote -- 40px fora do eixo, no
    mesmo lado nos dois personagens, porque a gola é assimétrica no
    desenho."""
    if len(meios) < 3:
        return meios, peso
    base = meios.min(axis=0)
    gx = np.round(meios[:, 0] - base[0]).astype(int)
    gy = np.round(meios[:, 1] - base[1]).astype(int)
    m = np.zeros((int(gy.max()) + 1, int(gx.max()) + 1), dtype=bool)
    m[gy, gx] = True
    for _ in range(int(max(2.0, dmin))):
        m = _dilatar(m)
    rot, n = _rotular(m)
    if n <= 1:
        return meios, peso
    r = rot[gy, gx]
    pesos = {k: float(peso[r == k].sum()) for k in range(1, n + 1)}
    corte = max(pesos.values()) * fracao
    sel = np.isin(r, [k for k, v in pesos.items() if v >= corte])
    if not sel.any():
        return meios, peso
    return meios[sel], peso[sel]


# =====================================================================
# Peça que a arte deixou grudada: separar pela FRONTEIRA DE COR
# =====================================================================
def _dilatar(m):
    """Dilatação por 4-vizinhança, em numpy puro (não há scipy no runner)."""
    d = m.copy()
    d[1:, :] |= m[:-1, :]
    d[:-1, :] |= m[1:, :]
    d[:, 1:] |= m[:, :-1]
    d[:, :-1] |= m[:, 1:]
    return d


def _dilatar_n(m, n):
    for _ in range(int(n)):
        m = _dilatar(m)
    return m


def _cheia(c):
    """Quanto da própria caixa a mancha ocupa.

    Separa MANCHA de CASCA: o cabelo, a pele e a camisa enchem a caixa
    delas; o traço preto que envolve a peça inteira ocupa menos de 15% da
    sua, porque é uma casca oca. A mesma régua que `nomear_rosto` usa para
    não batizar o contorno de cabelo."""
    bx0, by0, bx1, by1 = c["bbox"]
    return c["area"] / max((bx1 - bx0 + 1) * (by1 - by0 + 1), 1)


def _grupos_de_cor(manchas, tol=20):
    """Manchas da MESMA cor viram um grupo só, ainda que separadas.

    POR QUE (27/08 à noite, o cabelo da Maya)
        O cabelo dela não é uma mancha: é quatro. O topo da cabeça vem
        partido em dois pelo risco do penteado, e cada mecha lateral que
        desce até o ombro é uma ilha à parte. Todas com a mesma cor --
        (216,174,61), (216,173,61), (216,174,61), (214,172,59) -- porque
        são a mesma coisa desenhada.

        Tratadas uma a uma, as mechas ficam à mercê da distância: elas
        param a 3px do topo da camisa e a 40 do rosto, então a semente da
        camisa as alcança primeiro e o cabelo vira tronco. Agrupadas pela
        cor, o cabelo é decidido UMA vez, pelo lado com que ele tem mais
        fronteira -- e a fronteira longa é a do rosto.

    O agrupamento é ganancioso e por proximidade de canal: a maior mancha
    abre o grupo e as seguintes entram na primeira cujo canal mais distante
    esteja a `tol` dela. Serve igual para barba, gola, boné ou cachecol.
    """
    grupos = []
    for c in sorted(manchas, key=lambda c: -c["area"]):
        for g in grupos:
            if max(abs(int(c["cor"][i]) - int(g["cor"][i])) for i in range(3)) <= tol:
                g["mask"] = g["mask"] | c["mask"]
                g["area"] += c["area"]
                break
        else:
            grupos.append({"mask": c["mask"].copy(), "area": c["area"],
                           "cor": c["cor"]})
    for g in grupos:
        ys, xs = np.nonzero(g["mask"])
        g["bbox"] = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
        g["cx"], g["cy"] = float(xs.mean()), float(ys.mean())
    return grupos


def _dividir_por_cor(img, comp, min_frac=0.10, iteracoes=200):
    """Uma peça grudada -> duas peças, cortadas onde a ARTE troca de cor.

    POR QUE ISTO EXISTE (folha de 26/08)
        A folha nova consertou a boca -- ela vem fechada, sem o entalhe
        vazado que fazia o Pal parecer que gritava o vídeo inteiro -- mas
        veio sem o vão do pescoço: cabeça, pescoço e camisa saíram como uma
        peça de papel só. Com um bloco desses, a cabeça não gira, e sem giro
        de cabeça não há inclinação, não há reação e a expressão facial
        perde metade da leitura.

        Recusar a folha devolveria a boca aberta; aceitá-la como está
        devolveria um boneco de cabeça soldada. A terceira saída é olhar
        para o que a arte TEM: entre o pescoço e a camisa existe uma
        fronteira desenhada -- a pele acaba, o azul começa, com o traço
        preto da gola no meio. Essa fronteira é tão explícita quanto um vão
        branco; só não é vazia.

    O QUE NÃO É
        Não é o recorte por geometria que o projeto abandonou. Ali a peça
        terminava numa RETA inventada por proporção; aqui ela termina na
        linha que o desenhista traçou. Nenhuma medida é chutada.

    COMO (em três passos, desde 27/08 à noite)
        1. As manchas de cor da peça são agrupadas POR COR: o cabelo em
           quatro pedaços vira um cabelo só, a pele do rosto e a do pescoço
           viram a mesma pele. Ver `_grupos_de_cor`.
        2. Os dois maiores grupos EMPILHADOS abrem as sementes -- em cima a
           cabeça, embaixo o tronco. Cada grupo que sobra é entregue
           INTEIRO ao lado com que tem mais fronteira, e um grupo já
           entregue serve de fronteira para o próximo (é assim que a pele
           puxa o cabelo, ou o cabelo puxa a pele, sem que a ordem importe).
        3. Só o que não é mancha -- o traço preto do contorno, que é casca e
           não região -- é dividido pixel a pixel, com as duas sementes
           crescendo ao mesmo tempo. O traço acaba partido ao meio, que é o
           resultado certo: cada peça fica com a metade que lhe pertence.

    O passo 1 e o 2 são a correção da noite de 27/08. Antes, TUDO era
    decidido no passo 3, e distância era o único critério: as mechas da
    Maya paravam a 3px do decote e a 40px do rosto, então a semente da
    camisa as alcançava primeiro e o cabelo dela saía grudado no tronco --
    girando com o peito e não com a cabeça.

    Devolve (peça_de_cima, peça_de_baixo) ou None se não houver duas
    manchas de cor grandes e empilhadas -- e aí a folha é grudada mesmo.
    """
    m = comp["mask"]
    manchas = [c for c in _regioes_de_cor(img, comp, min_frac=0.004)
               if _cheia(c) >= 0.25]
    grupos = _grupos_de_cor(manchas)
    grandes = [g for g in grupos if g["area"] >= comp["area"] * min_frac]
    if len(grandes) < 2:
        return None
    # os dois maiores grupos de cor; têm que estar EMPILHADOS (um acima do
    # outro), senão não são "cabeça e tronco" e sim duas metades laterais
    grandes.sort(key=lambda g: -g["area"])
    a, b = sorted(grandes[:2], key=lambda g: g["cy"])
    if a["bbox"][3] > b["bbox"][3] or abs(a["cy"] - b["cy"]) < comp["area"] ** 0.5 * 0.25:
        return None

    cima, baixo = a["mask"].copy(), b["mask"].copy()

    # --- passo 2: cada grupo de cor restante vai INTEIRO para um lado.
    # A fronteira é medida com folga de `esp`, a espessura do contorno: o
    # pescoço não encosta na camisa nem no rosto, encosta no traço preto
    # que separa os dois. Sem a folga ele não tocaria em nada.
    esp = max(3, int(round(comp["area"] ** 0.5 * 0.02)))
    pendentes = [g for g in grupos if g is not a and g is not b]
    while pendentes:
        alvo, destino, forca = None, None, 0
        for g in pendentes:
            viz = _dilatar_n(g["mask"], esp)
            cc, cb = int((viz & cima).sum()), int((viz & baixo).sum())
            if max(cc, cb) > forca:
                alvo, destino, forca = g, (cc >= cb), max(cc, cb)
        if alvo is None:
            break                       # o que sobrou não toca em nada
        if destino:
            cima |= alvo["mask"]
        else:
            baixo |= alvo["mask"]
        pendentes = [g for g in pendentes if g is not alvo]

    # --- passo 3: o contorno, pixel a pixel
    livre = m & ~cima & ~baixo
    for _ in range(iteracoes):
        if not livre.any():
            break
        da = _dilatar(cima) & livre
        db = _dilatar(baixo) & livre & ~da
        if not (da.any() or db.any()):
            break
        cima |= da
        baixo |= db
        livre &= ~(da | db)
    baixo |= livre            # sobra (ilha isolada dentro da peça) fica embaixo

    fora = []
    for mask in (cima, baixo):
        ys, xs = np.nonzero(mask)
        if len(xs) == 0:
            return None
        fora.append({"mask": mask, "area": int(mask.sum()),
                     "bbox": (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())),
                     "cx": float(xs.mean()), "cy": float(ys.mean())})
    return fora[0], fora[1]


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
    # DUAS BASTAM (30/08). A guarda pedia três -- cabeça, peito e abdômen --
    # e reprovava a folha da senhora, que tem os catorze componentes, braços
    # e pernas separados e vão medido em joelho e tornozelo. O que falta
    # nela é UMA divisão: o colete de tricô cobre a cintura e cola peito e
    # abdômen num bloco só, e `_dividir_por_cor` não vence um padrão
    # listrado de quatro cores (ele procura DUAS regiões dominantes).
    #
    # Trinta linhas abaixo o código já sabe o que fazer com isso: "se a
    # folha vier com um tronco só, ele é o peito e o abdômen vira o mesmo
    # componente -- o rig aguenta, perde a torção". A guarda de entrada é
    # que não deixava chegar lá.
    #
    # Folha REALMENTE grudada continua reprovando, e antes daqui: quem tem o
    # corpo num bloco só não chega a oito componentes, e `segmentar_corpo`
    # levanta FolhaGrudada com a contagem. Aqui, menos de duas peças na
    # coluna significa que nem a cabeça se separou.
    if len(centrais) < 2:
        raise FolhaGrudada(
            f"achei só {len(centrais)} peça(s) na coluna central: nem a "
            f"cabeça se separou do tronco. A folha veio com o corpo grudado")

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
    # pescoço: a peça mais estreita da coluna acima do tronco. Só existe se
    # AINDA SOBRAREM peito e abdômen depois dele -- numa folha que grudou o
    # pescoço na cabeça (26/08) a coluna tem três peças, e promover a
    # primeira a pescoço fazia o peito virar pescoço, o abdômen virar peito
    # e o quadril desaparecer.
    if i < len(resto) - 2 and \
            (resto[i]["bbox"][2] - resto[i]["bbox"][0]) < larg_cab * 0.7:
        nomes[id(resto[i])] = "pescoco"
        i += 1
    # peito e abdômen: as duas maiores que sobram na coluna, de cima
    # para baixo. Se a folha vier com um tronco só, ele é o peito e o
    # abdômen vira o mesmo componente -- o rig aguenta, perde a torção.
    tronco = sorted(sorted(resto[i:], key=lambda c: -c["area"])[:2],
                    key=lambda c: c["cy"])
    # TRONCO ÚNICO (30/08): o código antigo duplicava o componente
    # (`tronco = tronco * 2`) para dar os dois nomes ao mesmo objeto -- e o
    # dicionário é indexado por `id`, então o segundo nome SOBRESCREVIA o
    # primeiro. Sobrava um abdômen e nenhum peito, e a folha era reprovada
    # duas linhas abaixo por "não achei peito e abdômen". O caminho nunca
    # tinha rodado: a guarda de três peças na coluna barrava antes.
    #
    # Com um tronco só ele é o PEITO, e o abdômen não existe. O rig sabe
    # lidar com peça ausente -- `_ancestral_presente` sobe a cadeia até
    # quem existe, que é como toda peça que a arte não separou já é
    # tratada. Perde-se a torção da cintura, não o personagem.
    tronco_unico = len(tronco) == 1
    for nome, c in zip(("peito", "abdomen"), tronco):
        nomes[id(c)] = nome

    peito = next((c for c in comps if nomes.get(id(c)) == "peito"), None)
    abdomen = next((c for c in comps if nomes.get(id(c)) == "abdomen"), None)
    if peito is None:
        raise FolhaGrudada("não achei o peito como peça separada")
    if abdomen is None and not tronco_unico:
        raise FolhaGrudada("não achei peito e abdômen como peças separadas")

    y_ombro = peito["bbox"][1]
    # sem abdômen, o quadril é a base do próprio tronco: é dali que as
    # pernas descem, e é essa a linha que separa braço de perna abaixo
    y_quadril = (abdomen or peito)["bbox"][3]

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

    # O CONTORNO NÃO É UMA FEIÇÃO. O traço preto que envolve a cabeça inteira
    # é, para o quantizador de cor, uma região escura enorme -- e era ele que
    # vinha sendo batizado de "cabelo", empurrando o crânio para uma tira de
    # 68px. Cabelo é uma mancha CHEIA; contorno é uma casca: ocupa pouco da
    # própria caixa. É essa diferença que separa os dois.
    def _cheio(c):
        bx0, by0, bx1, by1 = c["bbox"]
        return c["area"] / max((bx1 - bx0 + 1) * (by1 - by0 + 1), 1)

    regioes = [c for c in regioes
               if not (sum(c["cor"]) / 3.0 < 90 and _cheio(c) < 0.35
                       and c["area"] > cabeca["area"] * 0.08)]

    def lum(c):
        return sum(c["cor"]) / 3.0

    resto = sorted(regioes, key=lambda c: -c["area"])
    if not resto:
        return nomes

    # SÓ CHAMA DE CRÂNIO SE FOR MESMO A CARA INTEIRA. Num desenho com muito
    # traço interno (barba, orelha, sulco do nariz) a pele chega quebrada em
    # dez manchas, e a maior delas é um pedaço de bochecha. Batizar essa
    # mancha de crânio joga fora o resto da cabeça. Quando nenhuma região
    # domina, quem devolve None aqui faz o chamador usar a cabeça inteira
    # como uma peça só -- que é a leitura honesta do que o desenho tem.
    if resto[0]["area"] >= cabeca["area"] * 0.45:
        nomes[id(resto[0])] = "cranio"
        resto = resto[1:]

    escuras = [c for c in resto if lum(c) < 120]
    # cabelo: a maior mancha escura que encosta no topo da cabeça
    topo = [c for c in escuras if c["bbox"][1] <= y0 + alt * 0.18]
    if topo:
        cabelo = max(topo, key=lambda c: c["area"])
        nomes[id(cabelo)] = "cabelo"

    # OLHOS PODEM SER CLAROS. Num traço com esclera branca o olho é a
    # mancha CLARA cercada de contorno, não a escura; a regra antiga só
    # olhava para manchas escuras e perdia o par inteiro.
    pequenas = [c for c in regioes
                if id(c) not in nomes and c["area"] < cabeca["area"] * 0.05]
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
             and c["area"] < cabeca["area"] * 0.05
             # nariz é feição pequena: um traço de barba que atravessa meia
             # cara também cai perto do eixo, e era ele que vinha sendo
             # batizado de nariz e reprovando a folha inteira na conferência
             and (c["bbox"][3] - c["bbox"][1]) < alt * 0.20]
    if perto:
        nomes[id(max(perto, key=lambda c: c["area"]))] = "nariz"

    # ---------------------------------------------------------------
    # SE A CARA NÃO SE ABRIU, NÃO EXISTEM FEIÇÕES.
    #
    # Quando nenhuma região chega a 45% da cabeça, o chamador usa a CABEÇA
    # INTEIRA como crânio -- decisão certa e já registrada. Só que as
    # feições continuavam sendo nomeadas e exportadas, e aí o motor
    # desenhava olho, sobrancelha e nariz POR CIMA de um crânio que já os
    # continha. Duas consequências, as duas descobertas em 28/08 olhando
    # `cranio.png` da folha do Pal, que é a cara inteira:
    #
    #   * a duplicação é invisível em repouso (a peça cai exatamente sobre
    #     o desenho dela) e vira defeito assim que algo a move -- foi o
    #     "traço solto na testa" que apareceu ao inclinar a sobrancelha;
    #   * o pipeline parecia ter rosto articulado quando não tinha. As
    #     peças `olho_e`, `sobrancelha_e` e `mandibula` do Pal são fiapos
    #     de 11x21, 40x12 e um punhado de pixels de pele -- pedaços do
    #     contorno do cabelo, não feições.
    #
    # Sem crânio próprio, devolver feição nenhuma é a leitura honesta: a
    # cara é um desenho só, e quem quiser expressão precisa de uma folha
    # em que ela venha separada.
    if not any(n == "cranio" for n in nomes.values()):
        return {}
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
def _fundo(img, limiar=232):
    """O FUNDO é o branco que encosta na borda da folha -- não todo pixel claro.

    O gerador entrega a arte sobre branco com um halo suave em volta de cada
    contorno: no vão entre duas peças o branco chega a ~238, longe do 255
    ideal. Cortar por "pixel claro" resolveria o vão e apagaria junto o
    branco do olho, que é arte. Inundar a partir da borda separa os dois: o
    olho está cercado de contorno preto e a inundação não chega nele.

    Quando a folha já vem com alfa (rembg), o transparente entra como fundo
    do mesmo jeito.
    """
    a = np.asarray(img.convert("RGBA"), dtype=np.int16)
    r, g, b, alfa = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    claro = (r > limiar) & (g > limiar) & (b > limiar)
    candidato = claro | (alfa <= 10)
    if not candidato.any():
        return np.zeros(candidato.shape, dtype=bool)
    rot, n = _rotular(candidato)
    fundo = np.zeros(candidato.shape, dtype=bool)
    borda = set(rot[0, :]) | set(rot[-1, :]) | set(rot[:, 0]) | set(rot[:, -1])
    borda.discard(0)
    for r_ in borda:
        fundo |= rot == r_
    return fundo


def _abrir_coluna_grudada(img, comps, figura):
    """Se a coluna central vier com menos de três peças, tenta abri-la.

    A coluna precisa de cabeça, peito e abdômen para o rig existir. Quando a
    arte gruda cabeça e tronco (folha de 26/08), a peça maior é cortada pela
    fronteira de cor -- ver `_dividir_por_cor`. Uma tentativa só: se a
    divisão não render duas peças plausíveis, quem chama levanta
    FolhaGrudada como antes, e a folha volta para a arte."""
    x0, _, x1, _ = figura
    centro_x = (x0 + x1) / 2.0
    centrais = [c for c in comps if c["bbox"][0] <= centro_x <= c["bbox"][2]]
    if len(centrais) >= 3:
        return comps
    alvo = max(centrais, key=lambda c: c["area"], default=None)
    if alvo is None:
        return comps
    par = _dividir_por_cor(img, alvo)
    if not par:
        return comps
    print(f"[segmentar] a coluna central veio com {len(centrais)} peça(s): "
          f"a maior foi separada pela fronteira de cor em duas "
          f"({par[0]['area']}px e {par[1]['area']}px)")
    return [c for c in comps if c is not alvo] + list(par)


# As peças que giram no PLANO DE SIMETRIA do corpo. Todas as outras giram
# onde a arte deixou o vão; estas giram onde o corpo tem eixo.
NO_EIXO = ("pescoco", "cranio", "cabeca", "mandibula")

# O braço em pose T está DEITADO: ombro e cotovelo na mesma linha.
# Ver `_ombro_na_linha_do_cotovelo`.
OMBROS = {"braco_sup_e": "braco_inf_e", "braco_sup_d": "braco_inf_d"}


def _ombro_na_linha_do_cotovelo(pivos, caixas, por_nome, esqueleto, vaos,
                                manuais=()):
    """O ombro fica na ALTURA DO COTOVELO, na quina interna da peça do braço.

    POR QUE (27/08 à noite, medido nas três folhas de produção)
        A faixa em que a manga encosta no tronco não diz onde o ombro está,
        e as duas tentativas de tirá-lo dali erraram para lados opostos.
        Pelo MEIO da faixa, o pivô caía na axila -- 20px baixo demais no
        Pal, o braço nascendo do meio do peito. Pelo QUINTO SUPERIOR dela
        (a correção da tarde), passou a cair alto demais: 13px acima do
        cotovelo no Pal, 15 no Zeca e 28 na Maya, cuja manga curta encosta
        no tronco só lá em cima e por isso nem entrava na regra.

        Ombro acima do cotovelo faz o osso do braço nascer INCLINADO numa
        folha desenhada em T. Como o motor trata "não girar" como "braço na
        horizontal" (`CORRECAO_POSE_T` é contrato com a arte, não medição),
        a diferença aparece na tela como articulação fora do lugar: o braço
        sai da altura do pescoço.

        A referência que não depende de como a manga foi desenhada é o
        COTOVELO. A bíblia visual exige `arms stretched perfectly
        horizontal`, então ombro e cotovelo estão, por contrato, na mesma
        linha -- e o cotovelo tem vão curto e limpo, medido sem ambiguidade.
        A altura do ombro deixa de ser medida: passa a ser a do cotovelo.

        Sobra o X, e aí sim quem manda é a arte: o ombro é a parte
        TANGENCIAL do braço, o ponto em que a peça chega mais perto do
        tronco, recuado metade do vão -- para o pivô cair no meio da folga,
        como em toda outra junta.
    """
    for nome, antebraco in OMBROS.items():
        if nome not in por_nome or nome not in pivos or nome in manuais:
            continue
        lado = nome[-1]
        bx, by = caixas[nome]
        ys, xs = np.nonzero(por_nome[nome].get("hospedeiro",
                                               por_nome[nome])["mask"])
        if not len(xs):
            continue
        # 1. A ALTURA: o cotovelo. Sem antebraço na folha, o meio da massa
        #    do próprio braço -- que numa peça deitada é a mesma linha.
        if antebraco in pivos and antebraco in caixas:
            alvo_y = pivos[antebraco][1] + caixas[antebraco][1]
        else:
            alvo_y = float(np.median(ys))
        alvo_y = float(np.clip(alvo_y, ys.min(), ys.max()))
        # 2. O X: a quina interna, lida numa FAIXA de linhas em torno do
        #    cotovelo. Numa linha só, o serrilhado do contorno decide.
        janela = max(3.0, (ys.max() - ys.min() + 1) * 0.15)
        perto = np.abs(ys - alvo_y) <= janela
        if not perto.any():
            continue
        # o tronco está do lado do centro do corpo: a peça 'e' é a da
        # esquerda da tela, e a borda interna dela é o maior x; em 'd', o
        # menor. Recuar meio vão nessa direção põe o pivô no meio da folga.
        dentro = 1.0 if lado == "e" else -1.0
        borda_x = float(xs[perto].max() if lado == "e" else xs[perto].min())
        alvo = (borda_x + dentro * max(float(vaos.get(nome, 0.0)), 0.0) / 2.0,
                alvo_y)
        d = (alvo[0] - (pivos[nome][0] + bx), alvo[1] - (pivos[nome][1] + by))
        if abs(d[0]) < 0.5 and abs(d[1]) < 0.5:
            continue
        pivos[nome] = [alvo[0] - bx, alvo[1] - by]
        pai = _ancestral_presente(nome, esqueleto, por_nome)
        saidas = (por_nome.get(pai) or {}).get("saidas") or {}
        if nome in saidas:
            sx, sy = saidas[nome]
            saidas[nome] = (sx + d[0], sy + d[1])
        print(f"[segmentar] ombro '{nome}' foi para a linha do cotovelo "
              f"({d[1]:+.0f}px em y, {d[0]:+.0f}px em x)")


def _alinhar_ao_eixo(pivos, caixas, por_nome, esqueleto, manuais=()):
    """O X da cabeça vem do TRONCO, não da fronteira da gola.

    POR QUE (27/08)
        O pivô do pescoço é medido na fronteira desenhada entre a pele e a
        camisa. Essa fronteira é um decote, e decote é assimétrico: um lado
        da gola desce mais que o outro, um ombro tem mais tecido. O centro
        da faixa de contato caía 16px à esquerda do eixo do corpo no Pal e
        9px no Zeca -- sempre para o mesmo lado, porque o desenho tem o
        mesmo viés nos dois.

        Deslocado, o pivô faz a cabeça DESCREVER UM ARCO ao inclinar: em vez
        de girar sobre o pescoço, ela varre para o lado. Numa figura frontal
        isso lê como cabeça solta.

        A cabeça não gira sobre o desenho da gola, gira sobre a coluna. E a
        coluna está onde o tronco diz que está: o X do pivô da cintura
        (peito->abdomen) e o do quadril (a raiz). É a única referência do
        eixo de simetria que a folha oferece de forma confiável, porque
        tronco e quadril são peças largas e simétricas.

    Só o X muda. A altura do pescoço continua sendo a que a arte mostra, e
    a posição da cabeça na tela não se move: o ponto de encaixe no pai anda
    junto com o pivô.

    Pivô escrito à mão manda: quem digitou a coordenada não quer que ela
    seja corrigida por regra nenhuma.
    """
    refs = [pivos[n][0] + caixas[n][0]
            for n in ("peito", "abdomen") if n in pivos and n in caixas]
    if not refs:
        return
    eixo = sum(refs) / len(refs)
    for nome in NO_EIXO:
        if nome not in pivos or nome in manuais:
            continue
        bx = caixas[nome][0]
        desloc = eixo - (pivos[nome][0] + bx)
        if abs(desloc) < 0.5:
            continue
        pivos[nome][0] = eixo - bx
        pai = _ancestral_presente(nome, esqueleto, por_nome)
        if pai and pai in por_nome:
            saidas = por_nome[pai].get("saidas") or {}
            if nome in saidas:
                sx, sy = saidas[nome]
                saidas[nome] = (sx + desloc, sy)
        print(f"[segmentar] pivo de '{nome}' alinhado ao eixo do tronco "
              f"({desloc:+.1f}px em x)")


def _ancestral_presente(nome, esqueleto, presentes):
    """O pai mais próximo que existe de fato como peça.

    Uma peça que a arte não separou (o pescoço, nesta folha) não pode
    quebrar a cadeia: sem isto, `cranio` fica com o pai ausente, ninguém
    grava a saída do peito para ele e a cabeça simplesmente não é
    desenhada."""
    pai = esqueleto.get(nome)
    while pai is not None and pai not in presentes:
        pai = esqueleto.get(pai)
    # A CADEIA PODE ACABAR SEM ACHAR NINGUÉM (30/08). Subir só resolve
    # quando existe alguém acima; quem pendura na RAIZ não tem para onde
    # subir. Numa folha sem abdômen -- o colete que cobre a cintura --, a
    # perna subia para o abdômen ausente, dele para `None`, e era tratada
    # como se fosse ela mesma uma raiz: ninguém gravava a saída do tronco
    # para ela, e o personagem saía cortado na cintura.
    #
    # Nesse caso o pai certo é a RAIZ EFETIVA: descendo da raiz do
    # esqueleto até a primeira peça que existe de fato.
    if pai is None and esqueleto.get(nome) is not None:
        raiz = next((n for n, p in esqueleto.items() if p is None), None)
        while raiz is not None and raiz not in presentes:
            raiz = next((n for n, p in esqueleto.items() if p == raiz), None)
        if raiz is not None and raiz != nome:
            return raiz
    return pai


def segmentar_corpo(img, esqueleto, min_frac_area=0.0012, pivos_manuais=None):
    """Folha -> (peças, âncoras).

    esqueleto: {peça: peça_pai}, com None na raiz. Vem de
    folha_personagem.py -- este módulo não conhece vocabulário de rig, só
    sabe achar ilhas e medir vãos.

    pivos_manuais: {peça: [x, y]} em pixels DA FOLHA -- as mesmas
    coordenadas que o `_mapa.png` mostra. É a saída de emergência quando a
    arte não deixa a junta clara (uma manga que cobre metade do braço, um
    casaco que engole o quadril): o ponto medido é substituído pelo ponto
    escrito, e o resto da cadeia -- comprimento do osso, saída no pai --
    é recalculado a partir dele. Ver PIVOS-MANUAIS.md."""
    img = img.convert("RGBA")
    mask = ~_fundo(img)
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

    comps = _abrir_coluna_grudada(img, comps, figura)
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
        else:
            # A cara não se abriu em feições. Avisar ALTO: uma folha assim
            # roda -- o boneco anda, gesticula e a legenda funciona -- mas
            # não tem expressão facial nenhuma, e isso passou despercebido
            # por semanas justamente porque o vídeo saía.
            print("[rosto] a cabeca veio como UMA peca so: sem olho, "
                  "sobrancelha ou mandibula separados. O personagem nao vai "
                  "ter expressao facial nem lipsync de queixo com esta folha")
            por_nome["cranio"] = por_nome.pop("cabeca")

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
    manuais = {k: (float(v[0]), float(v[1]))
               for k, v in (pivos_manuais or {}).items() if k in por_nome}
    if manuais:
        print(f"[segmentar] {len(manuais)} pivô(s) escritos à mão: "
              f"{', '.join(sorted(manuais))}")
    pivos, vaos = {}, {}
    for nome in esqueleto:
        if nome not in por_nome:
            continue
        pai = _ancestral_presente(nome, esqueleto, por_nome)
        if pai is None or pai not in por_nome:
            # raiz (ou pai ausente): ancora na base central da própria peça,
            # salvo se a mão disser outra coisa
            p = pecas[nome]
            bx, by = caixas[nome]
            ponto = manuais.get(nome)
            pivos[nome] = ([ponto[0] - bx, ponto[1] - by] if ponto
                           else [p.size[0] / 2.0, p.size[1] - 1.0])
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
        if nome in manuais:
            ponto = manuais[nome]
        bx, by = caixas[nome]
        pivos[nome] = [ponto[0] - bx, ponto[1] - by]
        vaos[nome] = round(folga, 1)
        # o pai guarda, em coordenada dele, o mesmo ponto: é lá que o filho
        # vai ser colado, e é assim que o comprimento do osso sai medido
        pbx, pby = caixas[pai]
        por_nome[pai].setdefault("saidas", {})[nome] = (ponto[0] - pbx, ponto[1] - pby)

    _alinhar_ao_eixo(pivos, caixas, por_nome, esqueleto, manuais)
    _ombro_na_linha_do_cotovelo(pivos, caixas, por_nome, esqueleto, vaos, manuais)

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

    # ÂNGULO DESENHADO. A folha vem em T: o braço está deitado na
    # horizontal porque foi assim que o desenhista o desenhou, não porque o
    # personagem esteja com o braço aberto. Sem registrar a direção em que
    # cada peça FOI DESENHADA, o motor trata "não girar" como "braço
    # aberto" e o boneco anda de braços abertos o vídeo inteiro.
    #
    # A direção é medida, não suposta: é o vetor que sai do pivô e vai ao
    # centro de massa da peça.
    angulos = {}
    for nome, c in por_nome.items():
        piv = pivos.get(nome)
        cx0, cy0 = caixas.get(nome, (0, 0))
        if piv is None:
            continue
        # pivos são locais à peça recortada; a máscara é global
        px, py = piv[0] + cx0, piv[1] + cy0
        ys, xs = np.nonzero(c["mask"])
        # EIXO PRINCIPAL, não vetor até o centro de massa: o pivô cai na
        # borda da peça e quase nunca no eixo dela, então o vetor pivô ->
        # centro sai torto (o tronco media -130 graus e o boneco inteiro
        # nascia inclinado). O eixo principal é a direção em que a peça é
        # comprida -- e é isso que "a perna aponta para baixo" quer dizer.
        dx = xs - xs.mean()
        dy = ys - ys.mean()
        cov = np.array([[float((dx * dx).mean()), float((dx * dy).mean())],
                        [float((dx * dy).mean()), float((dy * dy).mean())]])
        vals, vecs = np.linalg.eigh(cov)
        vx, vy = vecs[:, int(np.argmax(vals))]
        # o eixo não tem sentido; quem dá o sentido é "longe do pivô"
        if vx * (xs.mean() - px) + vy * (ys.mean() - py) < 0:
            vx, vy = -vx, -vy
        angulos[nome] = round(math.degrees(math.atan2(vy, vx)), 1)

    ancoras = {
        "angulos": angulos,
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


def mapa_de_pecas(img, pecas, ancoras, grade=0):
    """Imagem de conferência: cada peça pintada de uma cor, o pivô marcado.

    Existe porque um partes.json com 24 entradas não diz a ninguém se o
    ombro foi parar no cotovelo. O mapa diz, em um olhar, antes dos treze
    minutos de render.

    `grade` em pixels desenha uma régua de coordenadas por cima: é o que
    torna possível LER um pivô da imagem e escrevê-lo no `pivos.json`
    quando a arte não deixa a junta clara."""
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
    if grade:
        for gx in range(0, img.size[0], grade):
            d.line([gx, 0, gx, img.size[1]], fill=(70, 78, 74), width=1)
            d.text((gx + 2, 2), str(gx), fill=(150, 160, 155))
        for gy in range(0, img.size[1], grade):
            d.line([0, gy, img.size[0], gy], fill=(70, 78, 74), width=1)
            d.text((2, gy + 2), str(gy), fill=(150, 160, 155))
    # o pivô marcado em cima da peça é o que denuncia ombro virando cotovelo
    for nome, piv in ancoras.get("pivos", {}).items():
        ox, oy = caixas.get(nome, (0, 0))
        x, y = ox + piv[0], oy + piv[1]
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(255, 255, 255), outline=(0, 0, 0), width=2)
        if grade:
            d.text((x + 8, y - 5), f"{nome} {x:.0f},{y:.0f}", fill=(255, 255, 255))
    return tela
