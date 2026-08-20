#!/usr/bin/env python3
"""
fatiar — a GEOMETRIA que transforma a folha do personagem nas peças do rig.

Separado de folha_personagem.py de propósito: aqui não há nenhuma opinião
sobre COMO o personagem deve ser (cor de pele, roupa, traço). Aqui só há
silhueta. Quem diz o que a peça precisa ter é folha_personagem.py; este
arquivo só sabe achar pescoço, virilha, tronco e braço numa máscara alfa,
e cortar.

Por isso as funções recebem a especificação por parâmetro em vez de
importá-la: assim este módulo serve para qualquer personagem, de qualquer
canal, sem depender do vocabulário de nenhum.
"""
import numpy as np
from PIL import Image


# =====================================================================
# Marcos anatômicos na silhueta
# =====================================================================
def _mascara(img, limiar=10):
    return np.array(img.convert("RGBA").split()[-1]) > limiar


def _faixas(linha):
    """Trechos contínuos de True numa linha -> [(ini, fim), ...]."""
    idx = np.flatnonzero(linha)
    if len(idx) == 0:
        return []
    quebras = np.flatnonzero(np.diff(idx) > 1)
    ini = np.concatenate(([idx[0]], idx[quebras + 1]))
    fim = np.concatenate((idx[quebras], [idx[-1]]))
    return list(zip(ini.tolist(), fim.tolist()))


def achar_marcos(mask):
    """Acha as linhas que separam as peças. Mede em vez de assumir
    proporção fixa: personagem de cabeça grande e personagem realista têm
    proporções muito diferentes, e o mesmo número chapado erraria num dos
    dois.

    NÃO exige que o braço esteja exatamente na horizontal. A primeira
    versão exigia, e quebrou na primeira folha real: o gerador entregou os
    braços caídos ~15 graus, o que é uma pose T perfeitamente legítima aos
    olhos de qualquer pessoa. Com braço inclinado, "linha mais larga da
    figura" cai na altura das MÃOS, não dos ombros, e todo o resto sai
    errado em cascata. Agora nada aqui depende do ângulo do braço."""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        raise ValueError("folha vazia: nenhum pixel opaco")
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    alt = y1 - y0 + 1
    larguras = mask.sum(axis=1)

    # PESCOÇO: linha mais estreita do terço superior. É o gargalo entre
    # a cabeça e os ombros -- mínimo local garantido, e acima da altura
    # onde o braço passa, então o ângulo do braço não interfere.
    ini = y0 + max(int(alt * 0.06), 1)
    fim = y0 + max(int(alt * 0.38), ini + 2)
    faixa = larguras[ini:fim].astype(float)
    faixa[faixa == 0] = np.inf
    y_pescoco = ini + int(np.argmin(faixa))

    # VIRILHA: procurada DE BAIXO PARA CIMA, e não de cima para baixo.
    # De cima, a primeira linha com duas faixas seria a linha onde o
    # braço descola do tronco -- na altura do peito. De baixo, as duas
    # primeiras faixas são sempre as duas pernas, e o ponto onde elas se
    # fundem é a virilha. Braço nenhum aparece nesse caminho.
    largura_min = max(alt * 0.01, 2)
    y_virilha = None
    for y in range(y1, y0, -1):
        f = [r for r in _faixas(mask[y]) if r[1] - r[0] > largura_min]
        if len(f) == 1:
            y_virilha = y
            break
    if y_virilha is None or y_virilha <= y_pescoco:
        raise ValueError("não achei a virilha: as pernas não se separam")

    # TRONCO em x. Medir numa linha só não serve, e é sutil o porquê:
    # na altura em que o braço se encaixa, braço e tronco viram UMA faixa
    # contínua (não há vão), então ali a medida sai larga demais; e uma
    # linha do quadril sai estreita demais, o que faz o corte do braço
    # levar junto uma tira da lateral do tronco por ~100 linhas -- foi
    # isso que entortou o eixo do braço em 19 graus na primeira versão.
    #
    # Então: mede a faixa do tronco em TODAS as linhas do tronco, joga
    # fora as que estão visivelmente infladas pelo braço, e fica com o
    # contorno mais apertado do que sobrou.
    centro_x = int(round(xs.mean()))
    medidas = []
    for y in range(y_pescoco, y_virilha):
        r = next((r for r in _faixas(mask[y]) if r[0] <= centro_x <= r[1]), None)
        if r:
            medidas.append(r)
    if not medidas:
        raise ValueError("não achei o tronco entre o pescoço e a virilha")
    larguras_tronco = np.array([r[1] - r[0] for r in medidas])
    med = float(np.median(larguras_tronco))
    # fora as linhas infladas pelo braço (largas) e as do pescoço (estreitas)
    limpo = [r for r, w in zip(medidas, larguras_tronco) if 0.6 * med <= w <= 1.5 * med]
    if not limpo:
        limpo = medidas
    # MEDIANA, não o extremo: o extremo seria decidido por uma única linha
    # atípica, e uma linha basta para estragar o corte do braço inteiro.
    tx0 = int(np.median([r[0] for r in limpo]))
    tx1 = int(np.median([r[1] for r in limpo]))

    return {
        "bbox": (x0, y0, x1, y1),
        "altura": alt,
        "y_pescoco": y_pescoco,
        "tronco_x": (tx0, tx1),
        "y_virilha": y_virilha,
        "centro_x": centro_x,
    }


# =====================================================================
# Recorte
# =====================================================================
def _recortar(img, caixa):
    """Corta e aperta no conteúdo. Apertar importa: o pivô é medido em
    coordenada da peça, então moldura transparente sobrando desloca o
    pivô do desenho de verdade."""
    peca = img.crop(caixa)
    bb = peca.getbbox()
    return peca.crop(bb) if bb else peca


def _erodir(m):
    e = m.copy()
    e[1:, :] &= m[:-1, :]
    e[:-1, :] &= m[1:, :]
    e[:, 1:] &= m[:, :-1]
    e[:, :-1] &= m[:, 1:]
    return e


def _dilatar(m):
    d = m.copy()
    d[1:, :] |= m[:-1, :]
    d[:-1, :] |= m[1:, :]
    d[:, 1:] |= m[:, :-1]
    d[:, :-1] |= m[:, 1:]
    return d


def _limpar_braco(m, raio):
    """Erode, fica com o maior blob, dilata de volta e reintersecta.

    Serve para soltar do braço o espigão fino que sobra da costura do
    ombro. Erodir sozinho emagreceria o braço (e o pivô é medido no
    desenho, então emagrecer desloca o pivô); erodir-limpar-dilatar tira
    o espigão e devolve a espessura original."""
    fino = m
    for _ in range(raio):
        fino = _erodir(fino)
    if not fino.any():
        return _maior_componente(m)
    grosso = _maior_componente(fino)
    for _ in range(raio):
        grosso = _dilatar(grosso)
    return grosso & m


def _maior_componente(m):
    """Fica só com o maior blob conectado da máscara.

    O recorte do braço por coluna deixa passar uma tira de 1-3 px da
    lateral do tronco ao longo de ~100 linhas. É pouca tinta, mas fica
    longe do braço e alonga a caixa: o eixo do braço saía torto e o
    braço superior vinha girado errado. A tira não encosta no braço,
    então basta ficar com o blob maior.

    BFS na mão em vez de scipy.ndimage: só percorre pixel aceso, e o
    Action instala apenas rembg/pillow/requests -- não dá para contar
    com scipy estar lá."""
    from collections import deque
    h, w = m.shape
    visto = np.zeros_like(m)
    melhor = np.zeros_like(m)
    melhor_n = 0
    for sy, sx in zip(*np.nonzero(m)):
        if visto[sy, sx]:
            continue
        comp = []
        fila = deque([(sy, sx)])
        visto[sy, sx] = True
        while fila:
            y, x = fila.popleft()
            comp.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and m[ny, nx] and not visto[ny, nx]:
                    visto[ny, nx] = True
                    fila.append((ny, nx))
        if len(comp) > melhor_n:
            melhor_n = len(comp)
            melhor = np.zeros_like(m)
            for y, x in comp:
                melhor[y, x] = True
    return melhor


def _pendurar_braco(img, mascara_braco):
    """Recorta o braço e o gira até ficar PENDURADO: ombro em cima, mão
    embaixo, eixo na vertical.

    Girar em vez de cortar retângulo é o que torna o fatiador indiferente
    ao ângulo do braço na folha. Braço a 0, 15 ou 40 graus sai igual
    aqui, e é isso que importa: o rig desenha ângulo 0 = pendurado para
    baixo, e depois gira a peça ele mesmo conforme a pose."""
    ys, xs = np.nonzero(mascara_braco)
    if len(xs) < 10:
        raise ValueError("braço não encontrado ao lado do tronco")

    pts = np.column_stack([xs, ys]).astype(float)
    media = pts.mean(axis=0)
    autovals, autovecs = np.linalg.eigh(np.cov((pts - media).T))
    eixo = autovecs[:, int(np.argmax(autovals))]      # (dx, dy) do eixo longo

    # Qual ponta é o ombro? A mais perto do tronco -- ou seja, a de x
    # maior num braço à esquerda da imagem, e vice-versa.
    proj = (pts - media) @ eixo
    ponta_a = pts[proj <= proj.min() + max((proj.max() - proj.min()) * 0.05, 1.5)].mean(axis=0)
    ponta_b = pts[proj >= proj.max() - max((proj.max() - proj.min()) * 0.05, 1.5)].mean(axis=0)
    esquerda = media[0] < mascara_braco.shape[1] / 2
    ombro, mao = (ponta_a, ponta_b) if (ponta_a[0] > ponta_b[0]) == esquerda else (ponta_b, ponta_a)

    # Angulo que leva o vetor ombro->mao a apontar para BAIXO.
    # PIL.rotate(a) gira no sentido anti-horario visual; em coordenadas
    # de imagem (y para baixo) isso e [[cos,sen],[-sen,cos]].
    dx, dy = (mao - ombro)
    ang = np.degrees(np.arctan2(-dx, dy))
    if (-dx * np.sin(np.radians(ang)) + dy * np.cos(np.radians(ang))) < 0:
        ang += 180.0

    # recorta a caixa do braço, apagando o que não é braço
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    recorte = img.crop((x0, y0, x1 + 1, y1 + 1)).copy()
    alfa = np.array(recorte.split()[-1])
    alfa[~mascara_braco[y0:y1 + 1, x0:x1 + 1]] = 0
    recorte.putalpha(Image.fromarray(alfa))

    girado = recorte.rotate(ang, expand=True, resample=Image.BICUBIC)
    bb = girado.getbbox()
    return girado.crop(bb) if bb else girado


def fatiar_corpo(img, cotovelo=0.45, joelho=0.5):
    """Folha do personagem -> as 6 peças essenciais.

    cotovelo/joelho: onde o membro se divide, medido do encaixe para a
    ponta. 0.45 no braço porque antebraço+mão é um pouco mais longo que
    o braço superior."""
    img = img.convert("RGBA")
    mask = _mascara(img)
    m = achar_marcos(mask)
    x0, y0, x1, y1 = m["bbox"]
    tx0, tx1 = m["tronco_x"]
    pecas = {}

    # --- cabeça: tudo acima do pescoço
    pecas["cabeca"] = _recortar(img, (x0, y0, x1 + 1, m["y_pescoco"]))

    # --- tronco: coluna central, do pescoço à virilha
    pecas["tronco"] = _recortar(img, (tx0, m["y_pescoco"], tx1 + 1, m["y_virilha"]))

    # --- braço: o que sobra de um lado do tronco, entre pescoço e
    # virilha. O corte é LINHA A LINHA, seguindo o contorno do próprio
    # tronco -- não uma coluna fixa. Coluna fixa não serve porque o
    # tronco muda de largura: medido no quadril, ela deixaria metade do
    # peito dentro do "braço"; medida no peito, cortaria o quadril fora.
    # Foi esse erro que inclinou o eixo do braço em ~19 graus e fez o
    # braço superior sair torto mesmo depois de girado.
    faixa = np.zeros_like(mask)
    faixa[m["y_pescoco"]:m["y_virilha"], :] = True
    raio = max(int(round(m["altura"] * 0.006)), 1)
    colunas = np.arange(mask.shape[1])[None, :]
    lado_esq = _limpar_braco(mask & faixa & (colunas < tx0), raio)
    lado_dir = _limpar_braco(mask & faixa & (colunas > tx1), raio)
    # Uso um lado só; o rig espelha para o outro. Escolho o mais completo:
    # um dos braços pode estar parcialmente cortado pela borda da folha.
    braco = _pendurar_braco(img, lado_esq if lado_esq.sum() >= lado_dir.sum() else lado_dir)

    # Já pendurado, dividir em ombro->cotovelo e cotovelo->mão é só
    # cortar na horizontal. Era isso que o corte retangular na folha
    # tentava fazer, e só funcionava com o braço exatamente deitado.
    lb, ab = braco.size
    corte = max(int(ab * cotovelo), 1)
    pecas["braco_sup"] = _recortar(braco, (0, 0, lb, corte))
    pecas["braco_inf"] = _recortar(braco, (0, corte, lb, ab))

    # --- perna: abaixo da virilha, uma delas
    largura_min = max(m["altura"] * 0.01, 2)
    linha_pernas = min(m["y_virilha"] + max(int(m["altura"] * 0.02), 2), y1)
    faixas_perna = [r for r in _faixas(mask[linha_pernas]) if r[1] - r[0] > largura_min]
    if not faixas_perna:
        raise ValueError("não achei as pernas abaixo da virilha")
    px0, px1 = max(faixas_perna, key=lambda f: f[1] - f[0])
    corte_joelho = int(m["y_virilha"] + (y1 - m["y_virilha"]) * joelho)
    pecas["perna_sup"] = _recortar(img, (px0, m["y_virilha"], px1 + 1, corte_joelho))
    pecas["perna_inf"] = _recortar(img, (px0, corte_joelho, px1 + 1, y1 + 1))

    return pecas, m


def fatiar_rosto(img, nomes):
    """Tira de rosto -> peças, uma por célula, na ordem de ESPEC_ROSTO.
    nomes: os rótulos das células, na ordem da esquerda para a direita.
    Separa por coluna vazia, não por proporção: o gerador nunca espaça
    as células exatamente igual."""
    img = img.convert("RGBA")
    mask = _mascara(img)
    colunas = mask.any(axis=0)
    blocos = _faixas(colunas)
    # descarta respingo: célula de verdade tem largura mínima
    largura_min = max(int(mask.shape[1] * 0.02), 3)
    blocos = [b for b in blocos if b[1] - b[0] >= largura_min]
    if len(blocos) != len(nomes):
        raise ValueError(
            f"a tira de rosto tem {len(blocos)} celulas, esperava "
            f"{len(nomes)} -- regere a tira")
    pecas = {}
    for nome, (bx0, bx1) in zip(nomes, blocos):
        pecas[nome] = _recortar(img, (bx0, 0, bx1 + 1, mask.shape[0]))
    return pecas


# =====================================================================
# Validação
# =====================================================================
def validar_folha_corpo(img, faixas_altura):
    """Devolve lista de problemas; vazia = folha aprovada.

    faixas_altura: {nome_da_peça: (fração_mínima, fração_máxima)} --
    vem de ESPEC_PARTES, mas chega por parâmetro para este módulo não
    precisar conhecer o vocabulário de peças.

    Existe para que uma folha ruim não substitua peças boas que já estão
    no Storage. O caso que motivou: a peça errada subiu, o render rodou
    13 minutos e só no vídeo pronto deu para ver o erro."""
    problemas = []
    mask = _mascara(img)
    if not mask.any():
        return ["folha vazia"]
    ys, xs = np.nonzero(mask)
    alt = ys.max() - ys.min() + 1
    larg = xs.max() - xs.min() + 1

    # Pose T: vão dos braços ~ altura. Figura de pé com braços baixados
    # dá algo perto de 0.4, e é justamente o que não dá para fatiar.
    prop = larg / max(alt, 1)
    if not (0.70 <= prop <= 1.70):
        problemas.append(
            f"proporção largura/altura {prop:.2f} fora de 0.70-1.70: "
            f"provavelmente não está em pose T")

    # UMA figura só. O gerador entregou um turnaround (frente, lado,
    # costas) na primeira tentativa, e sem esta checagem o erro chegava
    # aqui disfarçado de "marco anatômico errado", que não diz a ninguém
    # o que aconteceu de verdade. Três figuras lado a lado dão três
    # faixas separadas em quase toda linha do tronco.
    # Conta na altura da CABEÇA, a ~15% do topo, e não no meio da figura:
    # no meio pode cair abaixo da virilha, e aí duas pernas passariam por
    # duas figuras. Na altura da cabeça, uma figura tem sempre uma faixa.
    linha_cabeca = int(ys.min() + alt * 0.15)
    cabecas = [r for r in _faixas(mask[linha_cabeca]) if r[1] - r[0] > larg * 0.03]
    if len(cabecas) > 1:
        problemas.append(
            f"achei {len(cabecas)} cabeças lado a lado, esperava 1: o gerador "
            f"provavelmente desenhou um turnaround (frente/lado/costas) em "
            f"vez de uma figura só")

    # Figura recortada na borda: falta membro, e o corte sai truncado.
    h, w = mask.shape
    for nome, borda in (("topo", mask[0]), ("base", mask[-1]),
                        ("esquerda", mask[:, 0]), ("direita", mask[:, -1])):
        if borda.mean() > 0.02:
            problemas.append(f"a figura encosta na borda {nome}: enquadramento cortado")

    try:
        m = achar_marcos(mask)
    except ValueError as e:
        problemas.append(str(e))
        return problemas

    # Cada peça dentro da faixa de tamanho declarada em ESPEC_PARTES.
    alturas = {
        "cabeca":    (m["y_pescoco"] - m["bbox"][1]) / alt,
        "tronco":    (m["y_virilha"] - m["y_pescoco"]) / alt,
        "perna_sup": (m["bbox"][3] - m["y_virilha"]) * 0.5 / alt,
    }
    for nome, frac in alturas.items():
        lo, hi = faixas_altura[nome]
        if not (lo <= frac <= hi):
            problemas.append(
                f"{nome} ficou com {frac:.0%} da altura, esperado "
                f"{lo:.0%}-{hi:.0%}: marco anatômico provavelmente errado")
    return problemas
