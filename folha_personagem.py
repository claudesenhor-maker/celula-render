#!/usr/bin/env python3
"""
folha_personagem — o que o personagem DEVE ser, e de que peças ele é feito.

A geometria mora em segmentar.py (leitura da folha em peças) e em
fatiar.py (o recorte antigo, mantido como plano B). Aqui está o
vocabulário: a bíblia visual, o esqueleto, a ordem de desenho e o que cada
peça significa. Trocar de personagem mexe só na bíblia; trocar de rig mexe
só no esqueleto.

A DECISÃO QUE ORGANIZA ESTE ARQUIVO (21/08)
    Estilo e recorte viraram a mesma decisão.

    Até aqui o personagem era desenhado como um corpo inteiro e depois
    cortado por geometria: retângulos tirados de uma silhueta, com a
    articulação estimada por proporção. Cada peça terminava numa reta que
    a arte não tinha, e cada tentativa de disfarçar a reta -- sobreposição,
    folga, esfera na junta -- virou um defeito visível no vídeo. A esfera,
    em particular, apareceu como ombreira de armadura.

    Agora o personagem é um BONECO DE PAPEL. Cada parte é desenhada como
    uma peça de papel própria, com contorno inteiro e um vão branco entre
    vizinhas. Três coisas caem no colo de uma vez:

      * o recorte deixa de existir -- o rembg apaga o vão junto com o
        fundo e cada peça já chega isolada no canal alfa;
      * a articulação deixa de ser chute -- o vão É a articulação, e o
        pivô é o meio dele, medido pixel a pixel;
      * a emenda deixa de ser defeito -- o vão é constante em qualquer
        ângulo, e é exatamente o visual de boneco articulado com colchete.

    O número de peças, que antes era limitado pelo número de cicatrizes
    toleráveis, virou escolha de arte. São 24.
"""

# =====================================================================
# BIBLIA VISUAL — o que precisa ser igual em TODAS as peças
# =====================================================================
# Vem de identidade_json.biblia_visual do canal; isto é o fallback. Cada
# chave vira uma frase do prompt da folha, na ordem de ORDEM_BIBLIA.
#
# CURTA DE PROPÓSITO: o endpoint de imagem em uso recusa prompt com mais
# de 2048 caracteres, e a primeira versão escrita por extenso estourou o
# limite -- as sete imagens do lote voltaram 400 de uma vez.
BIBLIA_PADRAO = {
    "tipo_fisico":   "big round head, short chunky limbs, about 3.5 heads tall",
    "estilo":        "PAPER CUT-OUT PUPPET: every body part is a separate flat "
                     "paper shape with its own complete thick black outline",
    "vaos":          "a small clear white gap separates neighbouring parts: head, "
                     "jaw, neck, chest, waist, shoulders, elbows, wrists, hips, "
                     "knees and ankles",
    "cor_pele":      "flat light beige skin",
    "cabelo":        "short dark brown hair as one solid shape",
    "rosto":         "round dot eyes, thick eyebrows, simple wide mouth",
    "maos":          "rounded mitten hands, separate from the sleeve",
    "roupa_cima":    "plain steel-blue t-shirt, one flat colour",
    "roupa_baixo":   "plain dark navy trousers",
    "calcado":       "simple rounded dark grey shoes",
    "traco":         "thick uniform black outline",
    "sombreado":     "100% flat colours, no shading, no gradient, no texture",
    "detalhamento":  "very low detail, few bold shapes",
    "paleta":        "limited high-contrast palette",
}

# Tipo físico, estilo e vãos primeiro: são o que decide a silhueta e o que
# decide se a folha vai ser segmentável.
ORDEM_BIBLIA = ("tipo_fisico", "estilo", "vaos", "cor_pele", "cabelo", "rosto",
                "maos", "roupa_cima", "roupa_baixo", "calcado", "traco",
                "sombreado", "detalhamento", "paleta")


# =====================================================================
# ESQUELETO — quem pendura em quem
# =====================================================================
# {peça: peça_pai}. A raiz tem None. O segmentador usa isto para saber
# entre quais pares medir o vão; o motor usa para propagar posição e
# ângulo. Acrescentar uma peça é acrescentar uma linha aqui e garantir que
# a arte a traga separada.
#
# Lados: "e" e "d" são esquerda e direita DE QUEM ASSISTE. A folha em pose
# T traz os dois braços e as duas pernas desenhados, então acabou o
# espelhamento -- cada lado usa a própria arte. Era o espelhamento que
# fazia a manga do braço da frente aparecer invertida.
ESQUELETO = {
    "abdomen":        None,        # raiz: o quadril
    "peito":          "abdomen",
    "pescoco":        "peito",
    "cranio":         "pescoco",
    "mandibula":      "cranio",
    "boca":           "mandibula",
    "cabelo":         "cranio",
    "olho_e":         "cranio",
    "olho_d":         "cranio",
    "sobrancelha_e":  "cranio",
    "sobrancelha_d":  "cranio",
    "nariz":          "cranio",
    "braco_sup_e":    "peito",
    "braco_inf_e":    "braco_sup_e",
    "mao_e":          "braco_inf_e",
    "braco_sup_d":    "peito",
    "braco_inf_d":    "braco_sup_d",
    "mao_d":          "braco_inf_d",
    "perna_sup_e":    "abdomen",
    "perna_inf_e":    "perna_sup_e",
    "pe_e":           "perna_inf_e",
    "perna_sup_d":    "abdomen",
    "perna_inf_d":    "perna_sup_d",
    "pe_d":           "perna_inf_d",
}

# Sem estas o motor não monta um frame. O rosto inteiro é opcional: um
# personagem sem olhos recortados ainda anda, ainda gesticula e ainda abre
# a boca -- só perde expressão.
PARTES_ESSENCIAIS = ("abdomen", "peito", "cranio",
                     "braco_sup_e", "braco_inf_e",
                     "braco_sup_d", "braco_inf_d",
                     "perna_sup_e", "perna_inf_e",
                     "perna_sup_d", "perna_inf_d")

# ORDEM DE DESENHO, de trás para frente. É ela que define quem tapa quem.
#
# OS DOIS BRAÇOS FICAM NA FRENTE (26/08). A ordem anterior punha o braço
# direito atrás do tronco para dar um ar de três quartos. O que ela deu, na
# prática, foi um braço que SOME: em repouso ele cai colado ao corpo e o
# tronco o engole até o cotovelo, e em qualquer gesto que cruze a frente do
# peito o antebraço desaparece no meio do movimento. Com a folha desenhada
# de frente não há três quartos para preservar -- a profundidade vem do
# gesto, não da ordem de pilha.
#
# As pernas mantêm o lado "d" atrás: elas não cruzam o corpo (ver o passo
# lateral em acoes.py) e a diferença de plano ali é o que separa uma perna
# da outra quando as duas estão embaixo do quadril.
ORDEM_Z = (
    "perna_sup_d", "perna_inf_d", "pe_d",
    "perna_sup_e", "perna_inf_e", "pe_e",
    "abdomen", "peito", "pescoco",
    "mandibula", "boca",
    "cranio", "nariz", "olho_e", "olho_d",
    "sobrancelha_e", "sobrancelha_d", "cabelo",
    "braco_sup_d", "braco_inf_d", "mao_d",
    "braco_sup_e", "braco_inf_e", "mao_e",
)

# Onde cada peça pega o ângulo. O motor não inventa: consulta esta tabela.
#   tronco      segue a inclinação do tronco
#   cabeca      tronco + giro da cabeça
#   maxilar     cabeça + abertura da boca (é isto que dá fala de verdade)
#   braco_e/d   os três ângulos do braço, somados ao longo da cadeia
#   perna_e/d   idem
FONTE_ANGULO = {
    "abdomen": ("tronco", 0), "peito": ("tronco", 0), "pescoco": ("tronco", 0),
    "cranio": ("cabeca", 0), "cabelo": ("cabeca", 0), "nariz": ("cabeca", 0),
    "olho_e": ("cabeca", 0), "olho_d": ("cabeca", 0),
    "sobrancelha_e": ("cabeca", 0), "sobrancelha_d": ("cabeca", 0),
    "mandibula": ("maxilar", 0), "boca": ("maxilar", 0),
    "braco_sup_e": ("braco_e", 0), "braco_inf_e": ("braco_e", 1), "mao_e": ("braco_e", 2),
    "braco_sup_d": ("braco_d", 0), "braco_inf_d": ("braco_d", 1), "mao_d": ("braco_d", 2),
    "perna_sup_e": ("perna_e", 0), "perna_inf_e": ("perna_e", 1), "pe_e": ("perna_e", 2),
    "perna_sup_d": ("perna_d", 0), "perna_inf_d": ("perna_d", 1), "pe_d": ("perna_d", 2),
}


# =====================================================================
# CORRECAO_POSE_T — a folha é desenhada em T; a cena não é
# =====================================================================
# A bíblia EXIGE pose T ("arms stretched perfectly horizontal"), porque é
# a pose em que o gerador acerta a anatomia e em que nenhuma peça encobre
# outra. Só que ninguém fica de braço aberto o vídeo inteiro: em repouso o
# braço cai. Esses 90 graus são contrato com a arte, não chute -- e por
# isso ficam aqui, ao lado do texto do prompt que os garante, e não
# escondidos no motor.
#
# Tronco, cabeça e pernas já vêm desenhados como ficam em pé: correção 0.
CORRECAO_POSE_T = {
    "braco_sup_e": -90, "braco_inf_e": -90, "mao_e": -90,
    "braco_sup_d": 90, "braco_inf_d": 90, "mao_d": 90,
}

# =====================================================================
# ENCAIXE_OMBRO — a manga sobe, o pivô fica onde está (28/08)
# =====================================================================
# O pivô do ombro passou a vir da linha do cotovelo (lei 20) e gira no
# lugar certo. O que sobrou foi de ARTE: a folha é desenhada em T, e com o
# braço horizontal a manga encosta no tronco pela borda de BAIXO dela. Ao
# cair para a vertical, essa mesma borda vira a lateral do braço, e o topo
# da manga -- que na folha era a ponta do ombro -- fica abaixo da linha do
# ombro do tronco. Resultado: uma falha entre a camisa e a manga em todo
# frame de braço baixo, exatamente onde o olho procura a articulação.
#
# A correção é deslocar a CADEIA INTEIRA do braço (manga, antebraço e mão)
# para cima no referencial do tronco. Só a arte sobe: o pivô continua
# sendo o que o segmentador mediu, e por isso o giro não muda -- era o que
# estava certo e não podia ser mexido.
#
# A medida é fração da altura do CRÂNIO porque essa é a única régua de
# escala que existe dentro do personagem (a mesma que a expressão facial
# usa): folha nova, maior ou menor, encaixa sem ninguém recalibrar.
SUBIR_BRACO_HC = 0.10
ENCAIXE_OMBRO = ("braco_sup_e", "braco_sup_d")

# feições seguem a cabeça: giram com ela, não por conta própria
SEGUE = {
    "cabelo": "cranio", "nariz": "cranio", "boca": "mandibula",
    "olho_e": "cranio", "olho_d": "cranio",
    "sobrancelha_e": "cranio", "sobrancelha_d": "cranio",
    "mandibula": "cranio",
}


# =====================================================================
# ESPEC_PARTES — o que cada peça é, para o gerador e para o validador
# =====================================================================
# inclui/exclui é o contrato com a ARTE: é o que o prompt precisa garantir
# e o que a conferência visual cobra. frac_altura é sanidade de tamanho,
# em fração da altura da figura -- peça fora da faixa é peça mal nomeada.
def _p(inclui, exclui, frac, essencial=False):
    return {"inclui": inclui, "exclui": exclui, "frac_altura": frac,
            "essencial": essencial}


ESPEC_PARTES = {
    "cranio":        _p("testa, bochechas, base do rosto", "cabelo, queixo, pescoço", (0.10, 0.34), True),
    "cabelo":        _p("o cabelo como uma forma só", "orelha, testa", (0.03, 0.18)),
    "olho_e":        _p("um olho", "sobrancelha, o outro olho", (0.008, 0.08)),
    "olho_d":        _p("um olho", "sobrancelha, o outro olho", (0.008, 0.08)),
    "sobrancelha_e": _p("uma sobrancelha", "olho", (0.004, 0.06)),
    "sobrancelha_d": _p("uma sobrancelha", "olho", (0.004, 0.06)),
    "nariz":         _p("o nariz", "boca, olhos", (0.004, 0.07)),
    "mandibula":     _p("queixo e maxilar inferior", "olhos, nariz, cabelo, pescoço", (0.02, 0.14)),
    "boca":          _p("a boca", "queixo, dentes soltos", (0.004, 0.07)),
    "pescoco":       _p("o pescoço", "queixo, ombro", (0.01, 0.10)),
    "peito":         _p("peito e costelas com a roupa", "ombro do braço, barriga", (0.10, 0.34), True),
    "abdomen":       _p("barriga e quadril", "peito, coxa", (0.05, 0.26), True),
    "braco_sup_e":   _p("ombro até cotovelo, com manga", "antebraço, mão", (0.05, 0.24), True),
    "braco_inf_e":   _p("cotovelo até o pulso", "mão, ombro", (0.05, 0.24), True),
    "mao_e":         _p("a mão inteira", "antebraço", (0.02, 0.16)),
    "braco_sup_d":   _p("ombro até cotovelo, com manga", "antebraço, mão", (0.05, 0.24), True),
    "braco_inf_d":   _p("cotovelo até o pulso", "mão, ombro", (0.05, 0.24), True),
    "mao_d":         _p("a mão inteira", "antebraço", (0.02, 0.16)),
    "perna_sup_e":   _p("quadril até joelho", "canela, pé", (0.06, 0.28), True),
    "perna_inf_e":   _p("joelho até tornozelo", "pé, coxa", (0.06, 0.28), True),
    "pe_e":          _p("o pé com o sapato", "canela", (0.015, 0.14)),
    "perna_sup_d":   _p("quadril até joelho", "canela, pé", (0.06, 0.28), True),
    "perna_inf_d":   _p("joelho até tornozelo", "pé, coxa", (0.06, 0.28), True),
    "pe_d":          _p("o pé com o sapato", "canela", (0.015, 0.14)),
}

# Peças de rosto que ainda podem vir de uma TIRA gerada à parte, para quem
# quiser mais estados de boca do que a folha traz. Opcional: com o maxilar
# articulado, a fala já funciona sem elas.
ESPEC_ROSTO = (
    ("boca_0",       "boca fechada, uma linha simples"),
    ("boca_1",       "boca pouco aberta"),
    ("boca_2",       "boca aberta falando"),
    ("boca_3",       "boca bem aberta, surpresa"),
    ("olho_aberto",  "par de olhos abertos"),
    ("olho_fechado", "par de olhos fechados, duas linhas curvas"),
    ("sobrancelha",  "par de sobrancelhas"),
)


# =====================================================================
# Prompts montados A PARTIR da estrutura
# =====================================================================
def _biblia(identidade=None):
    b = dict(BIBLIA_PADRAO)
    b.update(identidade or {})
    return b


def prompt_folha_corpo(identidade=None):
    """Folha do corpo em pose T, desenhada como boneco de papel.

    A pose T continua sendo requisito, agora por outro motivo: com os
    braços na horizontal nenhuma peça encosta na vizinha por acidente, e
    os vãos ficam todos visíveis para o segmentador."""
    b = _biblia(identidade)
    return ". ".join([
        # NÃO escrever "character reference sheet": esse termo É o nome do
        # turnaround, e foi o que voltou na primeira folha real.
        "ONE single cartoon man in a strict T-POSE",
        "arms stretched perfectly horizontal to the sides, hands open",
        "legs straight and apart, feet flat and pointing sideways",
        "front view, symmetrical, whole body inside the frame",
        *[b[k] for k in ORDEM_BIBLIA if b.get(k)],
        # sem esta frase o modelo entende "peças separadas" como diagrama
        # explodido e espalha os membros pela folha, o que não dá para rigar
        "the pieces stay assembled in place as one standing figure, "
        "not exploded, not scattered, not a diagram",
        "the face is drawn as flat shapes: hair, eyes, eyebrows, nose and "
        "mouth each a distinct shape",
        "plain pure white background",
        "only one figure, no turnaround, no model sheet, no side view, "
        "no back view, no second person",
        "arms must NOT hang down, no relaxed pose, no arms at the sides",
        "no shadow, no floor, no scenery, no props, no text",
    ])


def prompt_folha_rosto(identidade=None):
    """Tira de rosto: uma fileira de peças pequenas, bem separadas."""
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
# Ligação com a geometria
# =====================================================================
# Caminho principal: segmentar.py lê a folha já em peças. Plano B:
# fatiar.py, o recorte por geometria, para folha que veio grudada. Quem
# decide entre os dois é o preparar_assets.py -- e ele avisa no log qual
# caminho rodou, porque a diferença de qualidade entre os dois é grande
# demais para ficar invisível.
from segmentar import segmentar_corpo as _segmentar, FolhaGrudada   # noqa: F401
from fatiar import fatiar_rosto as _fatiar_rosto                    # noqa: F401

def segmentar_folha(img, pivos_manuais=None):
    """Folha -> (peças, âncoras), usando o esqueleto declarado aqui.

    `pivos_manuais` vem do `pivos.json` que pode acompanhar a folha no
    bucket, e sobrescreve o pivô medido peça por peça (ver
    lab-celula/PIVOS-MANUAIS.md)."""
    return _segmentar(img, ESQUELETO, pivos_manuais=pivos_manuais)


def fatiar_rosto(img):
    """Tira de rosto -> peças nomeadas conforme ESPEC_ROSTO."""
    return _fatiar_rosto(img, [n for n, _ in ESPEC_ROSTO])


def conferir_pecas(pecas, ancoras):
    """Confere as peças segmentadas contra ESPEC_PARTES.

    Roda DEPOIS da segmentação, não antes: o validador antigo checava a
    folha inteira por proporção e não tinha como saber se o ombro foi
    parar no cotovelo. Aqui cada peça já existe e cada pivô já foi medido,
    então dá para cobrar o contrato de verdade.

    Devolve só o que REPROVA a folha. O estado do rosto sai por
    `conferir_rosto` e é AVISO: uma folha que desenha a cara dentro do
    crânio (as duas do Pal, a de 21/08 e a de 26/08) rende vídeo com
    expressão -- o motor recorta as feições em tempo de carga
    (`palito_cutout._extrair_feicoes`). Enquanto os dois vinham na mesma
    lista, o `preparar_assets` recusava por aviso e a arte boa não subia."""
    problemas = []
    alt = max(ancoras.get("altura_figura", 1), 1)

    faltando = [p for p in PARTES_ESSENCIAIS if p not in pecas]
    if faltando:
        problemas.append(f"faltam peças essenciais: {', '.join(faltando)}")

    for nome, p in pecas.items():
        esp = ESPEC_PARTES.get(nome)
        if not esp:
            continue
        frac = p.size[1] / alt
        lo, hi = esp["frac_altura"]
        if not (lo <= frac <= hi):
            problemas.append(
                f"{nome} ficou com {frac:.0%} da altura da figura, esperado "
                f"{lo:.0%}-{hi:.0%}: provavelmente foi nomeada errado")

    # vão gigante entre peças vizinhas = peça no lugar errado da cadeia
    for nome, vao in (ancoras.get("vaos") or {}).items():
        if vao > alt * 0.06:
            problemas.append(
                f"o vão entre {nome} e o pai dela é de {vao:.0f}px "
                f"({vao / alt:.0%} da figura): as duas não são vizinhas")

    return problemas


# Rosto: o que precisa existir para haver EXPRESSÃO e LIPSYNC.
# Não entra em PARTES_ESSENCIAIS de propósito -- uma folha sem rosto
# articulado ainda rende vídeo, só rende vídeo de cara parada. É aviso,
# não impedimento; quem decide se aceita é quem olha a conferência.
PARTES_DE_ROSTO = ("mandibula", "olho_e", "olho_d",
                   "sobrancelha_e", "sobrancelha_d")


def conferir_rosto(pecas):
    """A cara veio em peças de verdade, ou em fiapos?

    POR QUE ISTO EXISTE (28/08)
        A folha do Pal foi aprovada em produção com 23 peças e passou por
        toda a conferência. Só que `cranio.png` era a CARA INTEIRA -- olhos,
        sobrancelhas, nariz e orelhas desenhados dentro dela -- e as peças
        `olho_e` (11x21), `sobrancelha_e` (40x12) e `mandibula` eram
        pedaços do contorno do cabelo e um punhado de pixels de pele.

        A conferência antiga não pegou porque só media a FRAÇÃO DA ALTURA
        da figura, e um fiapo de 12px de altura cai dentro da faixa
        legítima de uma sobrancelha. O que denuncia o fiapo é outra coisa:
        ele é RALO -- ocupa pouco da própria caixa -- e é minúsculo em área
        perto do que uma feição de verdade tem.

        Sem esta checagem, a folha nova (a de boca fechada, §7.1) pode ser
        aceita com o mesmo defeito, e a expressão facial continuaria sem
        peça em que agir.
    """
    problemas = []
    from PIL import Image  # noqa: F401  (só para deixar a dependência explícita)
    import numpy as np

    faltando = [p for p in PARTES_DE_ROSTO if p not in pecas]
    if len(faltando) == len(PARTES_DE_ROSTO):
        problemas.append(
            "o rosto não foi segmentado: nenhuma feição saiu como peça. O "
            "personagem não terá expressão facial nem lipsync de queixo -- a "
            "arte precisa desenhar olhos, sobrancelhas e queixo como formas "
            "separadas, com vão entre elas")
        return problemas
    if faltando:
        problemas.append("faltam peças de rosto: " + ", ".join(faltando)
                         + " (sem elas a expressão facial fica pela metade)")

    for nome in PARTES_DE_ROSTO:
        p = pecas.get(nome)
        if p is None:
            continue
        a = np.asarray(p.convert("RGBA"))[..., 3] > 10
        area = int(a.sum())
        densidade = area / max(a.size, 1)
        if densidade < 0.22:
            problemas.append(
                f"{nome} é um fiapo: só {densidade:.0%} da própria caixa tem "
                f"desenho. Feição de verdade é uma mancha cheia; isto é um "
                f"pedaço de contorno que foi batizado errado")
    return problemas
