#!/usr/bin/env python3
"""
folha_personagem — a ESTRUTURA DE REQUISITOS de cada peça do personagem.

A geometria do recorte mora em fatiar.py. A divisão é proposital: aqui
está o que o personagem DEVE ser (cor de pele, roupa, o que cada peça
inclui e exclui); lá está apenas como achar pescoço, virilha e braço numa
silhueta. Trocar o personagem mexe só aqui.

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
# =====================================================================
# BIBLIA VISUAL — o que precisa ser igual em TODAS as peças
# =====================================================================
# Vem de identidade_json.biblia_visual do canal; isto aqui é só o
# fallback. Cada chave vira uma frase do prompt da folha, na ordem.
#
# ESTILO: cartoon chapado, desenhado PARA SER RECORTADO (21/08).
#     A primeira bíblia pedia arte semi-realista -- traço fino, sombreado
#     em dois tons, proporção humana de 6 cabeças. Ficou bonita e ficou
#     errada: recorte de arte realista denuncia o recorte. Cada junta
#     virava uma aresta reta no meio de um braço anatômico, e nenhum
#     ajuste de pivô conserta isso, porque o problema é a arte, não o
#     encaixe.
#
#     Animação cut-out tem um estilo próprio e ele existe por um motivo
#     mecânico: contorno de espessura constante (a linha não afina no
#     corte), cor 100% chapada (não há gradiente para quebrar na emenda),
#     formas grandes e poucas (leem em tela de celular), e ARTICULAÇÕES
#     DESENHADAS COMO ESFERAS. A esfera é a peça-chave: cortada ao meio,
#     as duas metades continuam sendo círculos, então a junta gira em
#     qualquer ângulo sem nunca mostrar canto.
# CURTA DE PROPÓSITO: o endpoint de imagem em uso recusa prompt com mais
# de 2048 caracteres ("Length of '/prompt' must be <= 2048"). A primeira
# versão desta bíblia, escrita por extenso, estourou o limite e as sete
# imagens do lote voltaram 400 de uma vez. Cada chave diz uma coisa só.
BIBLIA_PADRAO = {
    "tipo_fisico":   "big round head, short chunky limbs, about 3.5 heads tall",
    "juntas":        "VISIBLE ROUND BALL JOINTS at shoulders, elbows, wrists, "
                     "hips, knees and ankles",
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

# Ordem em que a bíblia entra no prompt. Tipo físico, juntas e roupa
# primeiro: são o que o modelo usa para decidir a silhueta.
ORDEM_BIBLIA = ("tipo_fisico", "juntas", "cor_pele", "cabelo", "rosto", "maos",
                "roupa_cima", "roupa_baixo", "calcado", "traco", "sombreado",
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
#
# DEZ OSSOS, NÃO SEIS (21/08)
#     Seis ossos dão um boneco de madeira: o braço é um bastão único do
#     ombro à mão, a perna vai do quadril ao chão sem tornozelo, e a
#     cabeça é um bloco rígido que não fala. Falta articulação é o que
#     faz o movimento parecer de manequim mesmo quando o timing está
#     certo.
#
#     Os quatro que entraram e o que cada um compra:
#       mao        -- pulso. É o osso que dá gesto (a mão para de ser um
#                     apêndice rígido do antebraço) e é ONDE OBJETO GRUDA:
#                     sem osso de mão, "segurar alguma coisa" não tem
#                     ponto de encaixe.
#       pe         -- tornozelo. Sem ele o pé acompanha a canela e a
#                     caminhada fica com passo de perna de pau.
#       mandibula  -- a fala. A boca deixa de ser um adesivo trocado em
#                     4 estados e passa a ser um maxilar que ABRE com a
#                     envoltória do áudio.
#       cranio     -- o resto da cabeça, que fica parado enquanto o
#                     maxilar se mexe (é o par obrigatório da mandíbula).
ESPEC_PARTES = {
    "cabeca": {
        "inclui":      "crânio, cabelo, orelhas, olhos, sobrancelhas, nariz",
        "exclui":      "queixo, boca, mandíbula, pescoço, tronco",
        "corte":       "do topo da cabeça até a linha da mandíbula",
        "pivo":        "base_central",       # assenta em cima da mandíbula
        "orientacao":  "nenhuma",
        "frac_altura": (0.08, 0.22),
        "essencial":   True,
    },
    "mandibula": {
        "inclui":      "queixo, boca, bochecha inferior",
        "exclui":      "olhos, nariz, cabelo, pescoço",
        "corte":       "da linha da mandíbula até o pescoço",
        "pivo":        "topo_central",       # desce quando a boca abre
        "orientacao":  "nenhuma",
        "frac_altura": (0.03, 0.13),
        "essencial":   True,
    },
    "tronco": {
        "inclui":      "peito, barriga e quadril com a roupa",
        "exclui":      "cabeça, braços, pernas",
        "corte":       "da linha do ombro até a virilha, só a coluna central",
        "pivo":        "base_central",       # quadril
        "orientacao":  "nenhuma",
        "frac_altura": (0.22, 0.50),
        "essencial":   True,
    },
    "braco_sup": {
        "inclui":      "ombro até cotovelo, com manga",
        "exclui":      "antebraço, mão, tronco",
        "corte":       "braço pendurado, primeiro terço",
        "pivo":        "ponta_do_ombro",
        "orientacao":  "pendurar",           # gira 90°: ombro em cima
        "frac_altura": (0.08, 0.24),
        "essencial":   True,
    },
    "braco_inf": {
        "inclui":      "cotovelo até o pulso",
        "exclui":      "mão, ombro, tronco",
        "corte":       "braço pendurado, terço do meio",
        "pivo":        "ponta_do_cotovelo",
        "orientacao":  "pendurar",
        "frac_altura": (0.08, 0.24),
        "essencial":   True,
    },
    "mao": {
        "inclui":      "mão inteira, do pulso à ponta dos dedos",
        "exclui":      "antebraço, manga",
        "corte":       "braço pendurado, ponta",
        "pivo":        "ponta_do_pulso",
        "orientacao":  "pendurar",
        "frac_altura": (0.04, 0.16),
        "essencial":   True,
    },
    "perna_sup": {
        "inclui":      "quadril até joelho, com a calça",
        "exclui":      "panturrilha, pé, tronco",
        "corte":       "abaixo da virilha, primeira metade de uma perna",
        "pivo":        "topo_central",       # quadril
        "orientacao":  "nenhuma",
        "frac_altura": (0.10, 0.28),
        "essencial":   True,
    },
    "perna_inf": {
        "inclui":      "joelho até o tornozelo",
        "exclui":      "pé, coxa, quadril",
        "corte":       "segunda metade de uma perna, sem o pé",
        "pivo":        "topo_central",       # joelho
        "orientacao":  "nenhuma",
        "frac_altura": (0.10, 0.28),
        "essencial":   True,
    },
    "pe": {
        "inclui":      "pé inteiro com o sapato",
        "exclui":      "canela, joelho",
        "corte":       "base da perna, abaixo do tornozelo",
        "pivo":        "topo_traseiro",      # tornozelo
        "orientacao":  "nenhuma",
        "frac_altura": (0.02, 0.12),
        "essencial":   True,
    },
}

# Peças de rosto: saem de uma TIRA separada, em fila. Olhos e sobrancelha
# são coladas no CRÂNIO (ficam paradas quando a boca fala); as bocas são
# coladas na MANDÍBULA (descem junto com o queixo). Opcionais no rig --
# sem elas o personagem ainda tem fala, porque o maxilar abre sozinho.
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

# Onde cada peça de rosto é colada. É isto que separa o que fala do que
# não fala: olho parado, boca junto do queixo.
ANCORA_ROSTO = {
    "boca_0": "mandibula", "boca_1": "mandibula",
    "boca_2": "mandibula", "boca_3": "mandibula",
    "olho_aberto": "cabeca", "olho_fechado": "cabeca", "sobrancelha": "cabeca",
}


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
        # NÃO escrever "character reference sheet" aqui: esse termo É o
        # nome do turnaround, e foi o que voltou na primeira folha real.
        # A pose vem primeiro porque o modelo ancora na abertura.
        "ONE single cartoon man in a strict T-POSE",
        "arms stretched perfectly horizontal to the sides, hands open",
        "legs straight and apart, feet flat and pointing sideways",
        "front view, symmetrical, whole body inside the frame",
        "flat vector cartoon style",
        *[b[k] for k in ORDEM_BIBLIA if b.get(k)],
        # o recorte separa cabeça de mandíbula e mão de antebraço por
        # geometria; sem essas fronteiras visíveis o corte cai no meio de
        # uma forma chapada e a emenda aparece
        "chin and jaw clearly defined below the eyes, shoes separate from the legs",
        "plain pure white background",
        "only one figure, no turnaround, no model sheet, no side view, "
        "no back view, no second person",
        "arms must NOT hang down, no relaxed pose, no arms at the sides",
        "no shadow, no floor, no scenery, no props, no text",
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
# Ligação com a geometria
# =====================================================================
# fatiar.py não conhece o vocabulário de peças -- recebe tudo por
# parâmetro. Os invólucros abaixo amarram a especificação deste arquivo
# à geometria de lá, e mantêm a interface que o preparar_assets.py já
# usa (fatiar_corpo, fatiar_rosto, validar_folha_corpo).
from fatiar import (achar_marcos, fatiar_corpo,          # noqa: F401
                    fatiar_rosto as _fatiar_rosto,
                    validar_folha_corpo as _validar_folha_corpo)

FAIXAS_ALTURA = {n: e["frac_altura"] for n, e in ESPEC_PARTES.items()}


def fatiar_rosto(img):
    """Tira de rosto -> peças nomeadas conforme ESPEC_ROSTO."""
    return _fatiar_rosto(img, [n for n, _ in ESPEC_ROSTO])


def validar_folha_corpo(img):
    """Confere a folha contra os tamanhos declarados em ESPEC_PARTES."""
    return _validar_folha_corpo(img, FAIXAS_ALTURA)
