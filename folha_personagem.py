#!/usr/bin/env python3
"""
folha_personagem — a ESTRUTURA DE REQUISITOS de cada peça do personagem,
e o fatiador que transforma UMA folha de personagem nas peças do rig.

POR QUE ESTE ARQUIVO EXISTE
    Até 19/08 as 13 peças eram pedidas ao gerador uma a uma
    ("a single upper arm segment, shoulder to elbow"). Deu errado das
    treze vezes: voltaram treze DESENHOS DE UM HOMEM INTEIRO. O rig
    empilhou sete homens e girou cada um em torno de um pivô -- foi o
    vídeo de 20/08.

    Duas causas, as duas estruturais:

    1. O prompt abria com a descrição da pessoa inteira e só depois
       pedia a peça. Todo gerador ancora no começo do prompt: lê
       "a cartoon man with a round head", desenha o homem, e trata
       "head and face only" como detalhe secundário.

    2. Mesmo com a ordem corrigida, modelo de imagem tem uma prior
       fortíssima para figura humana completa. Pedir "só um antebraço"
       é remar contra o treinamento inteiro do modelo. Some a isso que
       cada uma das 13 chamadas inventava a própria cor de camisa e o
       próprio rosto: as peças nunca iam formar UMA pessoa.

    A saída é inverter quem faz o quê. O gerador desenha o que ele sabe
    desenhar -- UMA pessoa inteira, de frente, em pose T. O recorte das
    partes vira etapa nossa, aqui, por geometria. Isso resolve os dois
    problemas de uma vez: a pose T é fatiável por código, e como todas
    as peças saem da MESMA imagem, cor de pele, roupa, traço e paleta
    são idênticos por construção -- não por sorte.

O QUE É A "ESTRUTURA DE REQUISITOS"
    Duas camadas:

    BIBLIA (global, vale para a folha inteira) -- cor de pele, cabelo,
        roupa, paleta, espessura de traço, nível de detalhe. É global
        de propósito: são exatamente os atributos que precisam ser
        IGUAIS entre as peças. Atributo compartilhado não se repete
        peça a peça, senão volta a divergir.

    ESPEC_PARTES (por peça) -- o que a peça inclui, o que ela não pode
        incluir, onde ela é cortada da folha, onde fica o pivô, qual a
        orientação final e qual o tamanho esperado em relação à figura.
        É o contrato que o fatiador cumpre e que o validador cobra.
"""
import numpy as np
from PIL import Image


# =====================================================================
# BIBLIA VISUAL — o que precisa ser igual em TODAS as peças
# =====================================================================
# Vem de identidade_json.biblia_visual do canal; isto aqui é só o
# fallback. Cada chave vira uma frase do prompt da folha, na ordem.
BIBLIA_PADRAO = {
    "tipo_fisico":   "adult man, slim build, about 6 heads tall",
    "cor_pele":      "light warm beige skin (#E8B98A)",
    "cabelo":        "short dark brown hair, simple flat shape, no strands",
    "rosto":         "small dot eyes, thin eyebrows, simple closed mouth, no nose shading",
    "roupa_cima":    "plain steel-blue short-sleeved t-shirt, no logo, no pattern",
    "roupa_baixo":   "plain dark navy trousers",
    "calcado":       "simple dark grey shoes",
    "traco":         "uniform 4px clean black outline on every shape",
    "sombreado":     "flat cel shading, exactly two tones per colour, no gradient, no texture",
    "detalhamento":  "low detail, no wrinkles, no fabric folds, no background elements",
    "paleta":        "muted palette, desaturated",
}

# Ordem em que a bíblia entra no prompt. Tipo físico e roupa primeiro:
# são o que o modelo usa para decidir a silhueta.
ORDEM_BIBLIA = ("tipo_fisico", "cor_pele", "cabelo", "rosto", "roupa_cima",
                "roupa_baixo", "calcado", "traco", "sombreado",
                "detalhamento", "paleta")


# =====================================================================
# ESPEC_PARTES — requisitos por peça
# =====================================================================
# Campos:
#   inclui        o que TEM que estar dentro do recorte
#   exclui        o que NÃO pode entrar (é isto que o validador cobra)
#   corte         de onde sai na folha, em linguagem de marco anatômico
#   pivo          onde o rig gruda a peça no corpo
#   orientacao    como a peça precisa ficar depois do recorte. O rig
#                 desenha ângulo 0 = pendurado para baixo, então braço
#                 recortado da pose T (horizontal) precisa girar.
#   frac_altura   altura esperada da peça / altura da figura. Serve de
#                 sanidade: peça fora da faixa = recorte errado.
#   essencial     palito_cutout.desenhar() chama pers.p() para estas
#                 sem checar antes; sem qualquer uma delas não há frame.
ESPEC_PARTES = {
    "cabeca": {
        "inclui":      "crânio inteiro, cabelo, orelhas, rosto neutro",
        "exclui":      "pescoço, ombro, tronco",
        "corte":       "acima da linha do pescoço",
        "pivo":        "base_central",       # encaixa no topo do pescoço
        "orientacao":  "nenhuma",
        "frac_altura": (0.12, 0.28),
        "essencial":   True,
    },
    "tronco": {
        "inclui":      "peito, barriga e quadril com a roupa",
        "exclui":      "cabeça, braços, pernas",
        "corte":       "da linha do ombro até a virilha, só a coluna central",
        "pivo":        "base_central",       # quadril
        "orientacao":  "nenhuma",
        "frac_altura": (0.28, 0.52),
        "essencial":   True,
    },
    "braco_sup": {
        "inclui":      "ombro até cotovelo, com manga",
        "exclui":      "mão, antebraço, tronco",
        "corte":       "faixa horizontal dos braços, metade interna (junto ao tronco)",
        "pivo":        "ponta_do_ombro",
        "orientacao":  "pendurar",           # gira 90°: ombro em cima
        "frac_altura": (0.14, 0.30),
        "essencial":   True,
    },
    "braco_inf": {
        "inclui":      "cotovelo até a ponta dos dedos, com a mão junto",
        "exclui":      "ombro, tronco",
        "corte":       "faixa horizontal dos braços, metade externa (ponta)",
        "pivo":        "ponta_do_cotovelo",
        "orientacao":  "pendurar",
        "frac_altura": (0.16, 0.34),
        "essencial":   True,
    },
    "perna_sup": {
        "inclui":      "quadril até joelho, com a calça",
        "exclui":      "pé, panturrilha, tronco",
        "corte":       "abaixo da virilha, metade de cima de uma perna",
        "pivo":        "topo_central",       # quadril
        "orientacao":  "nenhuma",
        "frac_altura": (0.16, 0.32),
        "essencial":   True,
    },
    "perna_inf": {
        "inclui":      "joelho até o pé, com o sapato junto",
        "exclui":      "coxa, quadril",
        "corte":       "metade de baixo de uma perna",
        "pivo":        "topo_central",       # joelho
        "orientacao":  "nenhuma",
        "frac_altura": (0.16, 0.32),
        "essencial":   True,
    },
}

# Peças de rosto: saem de uma TIRA separada, em fila, e são coladas por
# cima da cabeça. Opcionais no rig (só entram se existirem), mas é o que
# dá lipsync e expressão. A ordem aqui é a ordem das células na tira.
ESPEC_ROSTO = (
    ("boca_0",       "boca fechada, uma linha simples"),
    ("boca_1",       "boca pouco aberta"),
    ("boca_2",       "boca aberta falando"),
    ("boca_3",       "boca bem aberta, surpresa"),
    ("olho_aberto",  "par de olhos abertos"),
    ("olho_fechado", "par de olhos fechados, duas linhas curvas"),
    ("sobrancelha",  "par de sobrancelhas"),
)

PARTES_ESSENCIAIS = tuple(n for n, e in ESPEC_PARTES.items() if e["essencial"])


# =====================================================================
# Prompts montados A PARTIR da estrutura
# =====================================================================
def _biblia(identidade=None):
    b = dict(BIBLIA_PADRAO)
    b.update(identidade or {})
    return b


def prompt_folha_corpo(identidade=None):
    """Folha do corpo. A pose T não é estética, é requisito de recorte:
    com os braços na horizontal e as pernas na vertical, todo corte vira
    um retângulo alinhado aos eixos. Em pose A (braços a 45°) o braço sai
    na diagonal e o recorte retangular pega pedaço de fundo e de tronco."""
    b = _biblia(identidade)
    return ". ".join([
        "full body character reference sheet of ONE single person",
        "strict T-pose: standing straight, both arms extended perfectly "
        "horizontally out to the sides, palms down, legs straight and "
        "slightly apart, feet flat",
        "front view, facing the viewer, perfectly symmetrical",
        "the whole body fits inside the frame with a margin, nothing cropped",
        *[b[k] for k in ORDEM_BIBLIA if b.get(k)],
        "plain flat pure white background",
        "no shadow, no ground line, no floor, no scenery, no props, no text",
        "only ONE person in the image",
    ])


def prompt_folha_rosto(identidade=None):
    """Tira de rosto: uma fileira de peças pequenas, bem separadas.
    Peça de rosto isolada o modelo desenha bem -- o que ele resiste a
    desenhar é MEMBRO isolado."""
    b = _biblia(identidade)
    itens = ", then ".join(d for _, d in ESPEC_ROSTO)
    return ". ".join([
        f"a single horizontal row of {len(ESPEC_ROSTO)} small separate "
        f"cartoon face parts, evenly spaced, with clear empty white gaps "
        f"between them",
        f"from left to right: {itens}",
        "each item is a floating detached facial feature only",
        "NO face, NO head, NO skin, NO circle, NO person, NO body around them",
        b["traco"], b["sombreado"], b["paleta"],
        "plain flat pure white background",
        "no text, no labels, no numbers, no frames, no boxes",
    ])


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
    """Acha, na silhueta de uma figura em pose T, as linhas que separam
    as peças. Mede em vez de assumir proporção fixa: personagem de
    cabeça grande e personagem realista têm proporções muito diferentes,
    e o mesmo número chapado erraria num dos dois."""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        raise ValueError("folha vazia: nenhum pixel opaco")
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    alt = y1 - y0 + 1
    larguras = mask.sum(axis=1)
    larg_max = int(larguras.max())

    # PESCOÇO: linha mais estreita do terço superior. É o gargalo entre
    # a cabeça (larga) e os ombros (largos) -- mínimo local garantido.
    ini = y0 + max(int(alt * 0.06), 1)
    fim = y0 + max(int(alt * 0.38), ini + 2)
    faixa = larguras[ini:fim].astype(float)
    faixa[faixa == 0] = np.inf
    y_pescoco = ini + int(np.argmin(faixa))

    # FAIXA DOS BRAÇOS: onde a largura chega perto do vão total. Na pose
    # T isso só acontece na altura dos ombros.
    limiar_braco = larg_max * 0.75
    linhas_largas = np.flatnonzero(larguras >= limiar_braco)
    linhas_largas = linhas_largas[linhas_largas > y_pescoco]
    if len(linhas_largas) == 0:
        raise ValueError("não achei a faixa dos braços: a figura não está em pose T")
    y_braco_topo = int(linhas_largas.min())
    y_braco_base = int(linhas_largas.max())

    # TRONCO em x: medido LOGO ABAIXO dos braços, onde só existe tronco.
    y_sonda = min(y_braco_base + max(int(alt * 0.03), 2), y1)
    faixas_tronco = _faixas(mask[y_sonda])
    if not faixas_tronco:
        raise ValueError("não achei o tronco abaixo dos braços")
    # a maior faixa dessa linha é o tronco
    tx0, tx1 = max(faixas_tronco, key=lambda f: f[1] - f[0])

    # VIRILHA: primeira linha, de cima para baixo, em que o corpo se
    # parte em duas pernas.
    y_virilha = None
    for y in range(y_sonda, y1 + 1):
        f = [r for r in _faixas(mask[y]) if r[1] - r[0] > alt * 0.01]
        if len(f) >= 2:
            y_virilha = y
            break
    if y_virilha is None:
        raise ValueError("não achei a virilha: as pernas não se separam")

    return {
        "bbox": (x0, y0, x1, y1),
        "altura": alt,
        "y_pescoco": y_pescoco,
        "y_braco_topo": y_braco_topo,
        "y_braco_base": y_braco_base,
        "tronco_x": (tx0, tx1),
        "y_virilha": y_virilha,
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


def fatiar_corpo(img, cotovelo=0.45, joelho=0.5):
    """Folha em pose T -> as 6 peças essenciais.

    cotovelo/joelho: onde o membro se divide, medido do encaixe para a
    ponta. 0.45 no braço porque antebraço+mão é um pouco mais longo que
    o braço superior."""
    img = img.convert("RGBA")
    m = achar_marcos(_mascara(img))
    x0, y0, x1, y1 = m["bbox"]
    tx0, tx1 = m["tronco_x"]
    pecas = {}

    # --- cabeça: tudo acima do pescoço
    pecas["cabeca"] = _recortar(img, (x0, y0, x1 + 1, m["y_pescoco"]))

    # --- tronco: coluna central, do ombro à virilha
    pecas["tronco"] = _recortar(img, (tx0, m["y_braco_topo"], tx1 + 1, m["y_virilha"]))

    # --- braços: a faixa horizontal, do lado de fora do tronco.
    # Uso um lado só; o rig espelha para o outro.
    fita = (m["y_braco_topo"], m["y_braco_base"] + 1)
    lado_esq = tx0 - x0
    lado_dir = x1 - tx1
    if lado_esq >= lado_dir:
        # braço à esquerda da imagem: ombro na ponta DIREITA da peça
        corte_cotovelo = int(tx0 - lado_esq * cotovelo)
        cx_sup, cx_inf = (corte_cotovelo, tx0), (x0, corte_cotovelo)
        giro = 90          # anti-horário leva a ponta direita para cima
    else:
        # braço à direita da imagem: ombro na ponta ESQUERDA da peça
        corte_cotovelo = int(tx1 + lado_dir * cotovelo)
        cx_sup, cx_inf = (tx1 + 1, corte_cotovelo), (corte_cotovelo, x1 + 1)
        giro = -90         # horário leva a ponta esquerda para cima
    pecas["braco_sup"] = _recortar(img, (cx_sup[0], fita[0], cx_sup[1], fita[1]))
    pecas["braco_inf"] = _recortar(img, (cx_inf[0], fita[0], cx_inf[1], fita[1]))
    # Pendurar: o rig desenha ângulo 0 = para baixo. Braço recortado da
    # pose T está deitado; sem girar, o personagem fica com os braços
    # saindo do ombro na horizontal em toda pose.
    for nome in ("braco_sup", "braco_inf"):
        pecas[nome] = pecas[nome].rotate(giro, expand=True)

    # --- pernas: abaixo da virilha, uma delas
    faixas_perna = [r for r in _faixas(_mascara(img)[m["y_virilha"]])
                    if r[1] - r[0] > m["altura"] * 0.01]
    px0, px1 = max(faixas_perna, key=lambda f: f[1] - f[0])
    corte_joelho = int(m["y_virilha"] + (y1 - m["y_virilha"]) * joelho)
    pecas["perna_sup"] = _recortar(img, (px0, m["y_virilha"], px1 + 1, corte_joelho))
    pecas["perna_inf"] = _recortar(img, (px0, corte_joelho, px1 + 1, y1 + 1))

    return pecas, m


def fatiar_rosto(img):
    """Tira de rosto -> peças, uma por célula, na ordem de ESPEC_ROSTO.
    Separa por coluna vazia, não por proporção: o gerador nunca espaça
    as células exatamente igual."""
    img = img.convert("RGBA")
    mask = _mascara(img)
    colunas = mask.any(axis=0)
    blocos = _faixas(colunas)
    # descarta respingo: célula de verdade tem largura mínima
    largura_min = max(int(mask.shape[1] * 0.02), 3)
    blocos = [b for b in blocos if b[1] - b[0] >= largura_min]
    if len(blocos) != len(ESPEC_ROSTO):
        raise ValueError(
            f"a tira de rosto tem {len(blocos)} celulas, esperava "
            f"{len(ESPEC_ROSTO)} -- regere a tira")
    pecas = {}
    for (nome, _), (bx0, bx1) in zip(ESPEC_ROSTO, blocos):
        pecas[nome] = _recortar(img, (bx0, 0, bx1 + 1, mask.shape[0]))
    return pecas


# =====================================================================
# Validação
# =====================================================================
def validar_folha_corpo(img):
    """Devolve lista de problemas; vazia = folha aprovada.

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
        "tronco":    (m["y_virilha"] - m["y_braco_topo"]) / alt,
        "perna_sup": (m["bbox"][3] - m["y_virilha"]) * 0.5 / alt,
    }
    for nome, frac in alturas.items():
        lo, hi = ESPEC_PARTES[nome]["frac_altura"]
        if not (lo <= frac <= hi):
            problemas.append(
                f"{nome} ficou com {frac:.0%} da altura, esperado "
                f"{lo:.0%}-{hi:.0%}: marco anatômico provavelmente errado")
    return problemas
