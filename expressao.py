#!/usr/bin/env python3
"""
expressao — a CARA do personagem no motor cut-out.

POR QUE ESTE ARQUIVO EXISTE
    Até 27/08 o cut-out não tinha expressão nenhuma. O spec mandava
    `expressao: "surpreso"` desde sempre, `_rig_do_trecho` fazia

        rig = merge(REST, EXPRESSOES.get(tr.get("expressao"), {}))

    e o dicionário EXPRESSOES vem do palito_v4 -- o rig VETORIAL, onde a
    cara é desenhada por código e as chaves são `sobrancelha`, `boca`,
    `olho`. O motor cut-out não lê nenhuma dessas chaves: ele só percorre
    o esqueleto girando peças. As chaves entravam no rig e morriam ali.

    Efeito prático: o personagem passava o vídeo inteiro com a mesma cara,
    mexendo só o maxilar pela envoltória do áudio. `susto` chegava a
    escrever `rig["sobrancelha"] = 1.0` e nada acontecia. O roteirista
    escolhia expressão a cada trecho, a expressão era validada contra uma
    lista fechada, gravada na ficha técnica -- e nunca chegava à tela.

O QUE UMA EXPRESSÃO É AQUI
    Um punhado de deslocamentos aplicados às PEÇAS DE ROSTO que a folha
    trouxer separadas: as duas sobrancelhas, os dois olhos, a mandíbula e a
    inclinação da cabeça. Nada é desenhado por código -- só se move o que o
    desenhista já entregou, que é a regra do projeto inteiro.

    Todas as medidas de deslocamento são FRAÇÃO DA ALTURA DO CRÂNIO, nunca
    pixels. Uma folha nova, gerada em outro tamanho, continua valendo sem
    reajuste -- o mesmo motivo pelo qual o objeto na mão é medido contra a
    altura do ator.

A EXCEÇÃO: A BOCA
    A folha do Pal não traz boca nem queixo como peça -- a cara inteira saiu
    como uma peça só, e o que o segmentador batizou de `mandibula`,
    `olho_e` e `sobrancelha_e` são fiapos de contorno (ver
    folha_personagem.conferir_rosto). Enquanto for assim, `palito_cutout`
    tapa o entalhe da boca e DESENHA uma boca no lugar exato dele, e é ela
    que `boca_curva` curva. É a única coisa do personagem desenhada por
    código, e some sozinha no dia em que a folha trouxer o queixo.
"""
import math

# =====================================================================
# CATÁLOGO — os campos, todos opcionais e todos com 0 como repouso
# =====================================================================
# cabeca_rot       graus somados ao giro da cabeça (+ = inclina para a direita
#                  de quem assiste). Inclinação de cabeça carrega mais emoção
#                  do que qualquer coisa que se faça com a sobrancelha.
# sobrancelha_dy   fração da altura do crânio; NEGATIVO sobe (y cresce para
#                  baixo, como em todo o resto do motor)
# sobrancelha_rot  graus; POSITIVO abaixa a ponta INTERNA (o lado do nariz),
#                  que é o desenho universal de raiva. Negativo levanta a
#                  ponta interna, que é o de tristeza e de súplica.
# olho_sx/olho_sy  escala da peça do olho. sy < 1 semicerra, sy > 1 arregala.
# olho_dy          fração da altura do crânio; sobe ou desce o par de olhos
# boca_min         piso da abertura da boca, 0..1. É o que deixa o queixo
#                  caído no susto mesmo quando não há som nenhum.
# mandibula_dx     fração da altura do crânio; empurra o queixo para o lado
#                  (boca torta -- dúvida, desdém)
# boca_curva       -1..+1. Positivo curva a boca para cima (sorriso),
#                  negativo para baixo. Vale para a boca desenhada; com uma
#                  folha de queixo articulado, é ignorado.
_Z = {"cabeca_rot": 0.0, "sobrancelha_dy": 0.0, "sobrancelha_rot": 0.0,
      "olho_sx": 1.0, "olho_sy": 1.0, "olho_dy": 0.0,
      "boca_min": 0.0, "mandibula_dx": 0.0, "boca_curva": 0.0}


def _e(**kw):
    d = dict(_Z)
    d.update(kw)
    return d


CATALOGO = {
    # repouso
    "neutro":     _e(),

    # olhos arregalados, sobrancelhas no alto, queixo caído. É a cara do
    # gancho: o pico dos 2 primeiros segundos é visual antes de ser verbal.
    "surpreso":   _e(sobrancelha_dy=-0.085, sobrancelha_rot=-6.0,
                     olho_sx=1.22, olho_sy=1.30, olho_dy=-0.008,
                     boca_min=0.34, cabeca_rot=-2.0, boca_curva=-0.15),

    # o mesmo susto levado ao extremo, para o frame de impacto
    "chocado":    _e(sobrancelha_dy=-0.105, sobrancelha_rot=-9.0,
                     olho_sx=1.34, olho_sy=1.48, olho_dy=-0.012,
                     boca_min=0.52, cabeca_rot=-4.0, boca_curva=-0.25),

    # sobrancelha em V e olho apertado: a leitura é imediata mesmo num
    # rosto de cinco formas
    "bravo":      _e(sobrancelha_dy=0.030, sobrancelha_rot=19.0,
                     olho_sx=1.04, olho_sy=0.74, boca_min=0.10,
                     boca_curva=-0.55, cabeca_rot=2.0),
    "irritado":   _e(sobrancelha_dy=0.020, sobrancelha_rot=13.0,
                     olho_sx=1.0, olho_sy=0.82, mandibula_dx=0.012,
                     boca_curva=-0.40, cabeca_rot=1.5),

    # ponta interna para cima é o desenho de tristeza em qualquer escola
    "triste":     _e(sobrancelha_dy=0.008, sobrancelha_rot=-15.0,
                     olho_sy=0.88, olho_dy=0.006, cabeca_rot=3.0,
                     boca_curva=-0.85),
    "desesperado": _e(sobrancelha_dy=-0.055, sobrancelha_rot=-18.0,
                      olho_sx=1.18, olho_sy=1.24, boca_min=0.40,
                      cabeca_rot=-3.0, boca_curva=-0.55),

    # com a boca desenhada, sorrir finalmente é sorrir
    "sorrindo":   _e(sobrancelha_dy=-0.020, sobrancelha_rot=-3.0,
                     olho_sx=1.02, olho_sy=0.80, cabeca_rot=4.0,
                     boca_curva=0.95),
    "confiante":  _e(sobrancelha_dy=-0.030, sobrancelha_rot=4.0,
                     olho_sy=0.86, cabeca_rot=-3.0, mandibula_dx=0.006,
                     boca_curva=0.55),

    # uma sobrancelha sobe -- é o que `duvida` sempre quis ser e o rig
    # vetorial nunca conseguiu, porque lá a cara era simétrica por código
    "duvida":     _e(sobrancelha_dy=-0.030, sobrancelha_rot=8.0,
                     olho_sy=0.90, mandibula_dx=0.014, cabeca_rot=5.0,
                     boca_curva=-0.25),
    "pensando":   _e(sobrancelha_dy=-0.015, sobrancelha_rot=6.0,
                     olho_sy=0.86, olho_dy=-0.006, cabeca_rot=6.0,
                     boca_curva=-0.20),
    "desdem":     _e(sobrancelha_dy=-0.025, sobrancelha_rot=5.0,
                     olho_sy=0.78, mandibula_dx=0.016, cabeca_rot=-4.0,
                     boca_curva=0.35),
}

# Apelidos: o roteirista e a identidade do canal usam rótulos que não são
# exatamente estes. Mapear é mais barato do que exigir que todo mundo mude
# de vocabulário ao mesmo tempo -- e é o mesmo motivo pelo qual o spec
# antigo continua rodando.
APELIDOS = {
    "feliz": "sorrindo", "alegre": "sorrindo", "rindo": "sorrindo",
    "assustado": "surpreso", "espantado": "surpreso", "susto": "surpreso",
    "raiva": "bravo", "furioso": "bravo", "nervoso": "irritado",
    "confuso": "duvida", "desconfiado": "duvida", "duvidando": "duvida",
    "pensativo": "pensando", "resignado": "triste", "chateado": "triste",
    "panico": "desesperado", "aflito": "desesperado",
    "orgulhoso": "confiante", "convencido": "confiante",
    "neutra": "neutro", "": "neutro",
}

# Expressões que NÃO piscam: quem levou um susto fica de olho arregalado, e
# uma piscada no meio disso desmonta o frame de impacto.
SEM_PISCAR = ("surpreso", "chocado", "desesperado")


def normalizar(nome):
    """Rótulo do roteirista -> chave do catálogo. Nunca levanta erro: cara
    errada é defeito de vídeo, cara faltando é vídeo nenhum."""
    n = str(nome or "").strip().lower().replace("-", "_").replace(" ", "_")
    n = APELIDOS.get(n, n)
    return n if n in CATALOGO else "neutro"


def obter(nome, intensidade=1.0):
    """A expressão, opcionalmente diluída.

    Intensidade existe para a ESCALADA: o roteirista escolhe `bravo` no
    trecho 2 e no trecho 5, e sem graduação os dois têm exatamente a mesma
    cara -- que é a queixa de "expressão parada" com outro nome."""
    base = CATALOGO.get(normalizar(nome), CATALOGO["neutro"])
    k = max(0.0, min(1.6, float(intensidade)))
    if abs(k - 1.0) < 1e-3:
        return dict(base)
    return {c: _Z[c] + (v - _Z[c]) * k for c, v in base.items()}


def misturar(a, b, k):
    """Interpolação linear entre duas expressões. k=0 -> a, k=1 -> b."""
    k = max(0.0, min(1.0, k))
    return {c: a.get(c, _Z[c]) + (b.get(c, _Z[c]) - a.get(c, _Z[c])) * k for c in _Z}


# =====================================================================
# Resolução ao longo do trecho
# =====================================================================
# TRANSIÇÃO: trocar de cara num frame lê como corte de plano dentro do
# mesmo plano. Um quarto de segundo é o bastante para o olho aceitar a
# mudança como reação -- e é curto o bastante para a reação ainda cair
# sobre a palavra que a causou.
TRANSICAO_S = 0.22


class Rosto:
    """Decide qual cara o personagem tem em cada frame do trecho.

    Duas fontes, na ordem:

      1. `expressao` do trecho -- a cara base, que vale do começo ao fim.
      2. `expressoes`: [] -- janelas `de`/`ate` com `motivo`, exatamente
         como as ações. É por aqui que a cara MUDA NO MEIO DA FALA, que é
         o que separa reação de ilustração: a piada vira na palavra
         "ontem" e é ali que a sobrancelha tem que subir, não no começo
         do trecho seguinte.

    A cara do trecho anterior entra como ponto de partida da transição: o
    corte entre trechos deixa de ser um pulo de expressão."""

    def __init__(self, spec):
        self.anterior = {}          # {chave_do_ator: expressão do fim do trecho}
        self.ultima = {}            # {chave_do_ator: expressão do frame corrente}
        self.spec = spec

    def para(self, tr, t, dur, ator="_"):
        """Expressão efetiva em t (0..1 dentro do trecho)."""
        base_nome = tr.get("expressao") or tr.get("expressao_facial") or "neutro"
        base = obter(base_nome, tr.get("intensidade", 1.0))

        # 1. entrada suave a partir da cara com que o trecho anterior terminou
        anterior = self.anterior.get(ator)
        atual = base
        if anterior is not None and dur > 0.01:
            k = min(1.0, (t * dur) / TRANSICAO_S)
            atual = misturar(anterior, base, k)

        # 2. janelas de reação, aplicadas por cima, com entrada e saída suaves
        for j in (tr.get("expressoes") or []):
            de, ate = float(j.get("de", 0.0)), float(j.get("ate", 1.0))
            if ate <= de or not (de <= t <= ate):
                continue
            alvo = obter(j.get("nome") or j.get("valor"), j.get("intensidade", 1.0))
            janela_s = max(0.05, (ate - de) * dur)
            sobe = min(1.0, ((t - de) * dur) / min(TRANSICAO_S, janela_s * 0.5))
            desce = min(1.0, ((ate - t) * dur) / min(TRANSICAO_S, janela_s * 0.5))
            atual = misturar(atual, alvo, min(sobe, desce))

        self.ultima[ator] = atual
        return atual

    def fechar(self, ator="_"):
        """Guarda a cara do fim do trecho para o próximo começar dela.

        Por ator, e não uma variável só: com dois personagens em cena, um
        `ultima` compartilhado faria o segundo ator herdar a cara do
        primeiro no trecho seguinte."""
        self.anterior[ator] = self.ultima.get(ator) or dict(_Z)


# =====================================================================
# A MESMA EMOÇÃO, NA VOZ
# =====================================================================
# POR QUE ISTO MORA AQUI, e não num módulo de voz: a emoção do trecho já é
# escolhida uma vez, pelo roteirista, no campo `expressao`. Se a voz
# tivesse um vocabulário próprio, o roteirista teria que escolher duas
# vezes e as duas escolhas divergiriam no primeiro trecho em que alguém
# esquecesse de mexer numa delas -- cara de espanto com voz de tédio, que é
# pior do que não ter nenhuma das duas.
#
# O Edge-TTS aceita três controles: `rate` (velocidade), `pitch` (altura) e
# `volume`. Não é SSML completo, não há ênfase por palavra -- mas quem já
# ouviu alguém contar um caso sabe que a diferença entre susto e tristeza
# está quase toda em velocidade e altura, e essas duas o serviço dá.
#
# Os valores são DELTAS sobre o perfil de voz do personagem: o perfil diz
# como o Pal fala (rate +12%, pitch +18Hz), a emoção diz o quanto ele se
# desvia disso neste trecho. Assim trocar a voz do personagem não obriga a
# refazer a tabela de emoções.
PROSODIA = {
    "neutro":      (0, 0, 0),
    # susto: rápido e agudo, que é o que a adrenalina faz com a fala
    "surpreso":    (+14, +22, +6),
    "chocado":     (+20, +30, +8),
    # raiva: rápido, mas GRAVE -- agudo com raiva sai como esganiçado
    "bravo":       (+10, -10, +8),
    "irritado":    (+6, -6, +5),
    # tristeza é o oposto de tudo: devagar, baixo, mais fraco
    "triste":      (-14, -14, -6),
    "desesperado": (+16, +18, +6),
    "sorrindo":    (+6, +8, +2),
    "confiante":   (-4, -6, +3),
    # dúvida e reflexão pedem freio: o ouvinte precisa de tempo para
    # perceber que o personagem está pensando
    "duvida":      (-8, +4, 0),
    "pensando":    (-12, -2, -2),
    # desdém é a piada dita como quem não quer nada -- é o timing seco
    "desdem":      (-6, -8, -2),
}


def _sinal(v, unidade):
    return f"{v:+.0f}{unidade}"


def prosodia(nome, intensidade=1.0, base=None):
    """cfg de voz do trecho: o perfil do personagem mais a emoção.

    `base` é o perfil (`spec["vozes"][perfil]`), e volta intacto no que a
    emoção não toca -- `voice`, `motor`, `eleven_voice_id`. O que a emoção
    mexe é somado ao rate/pitch do perfil, em vez de substituí-los.

    Um trecho pode ainda cravar `rate`/`pitch` próprios; eles ganham de
    tudo, porque escolha explícita do roteirista é decisão, não sugestão."""
    cfg = dict(base or {})
    dr, dp, dv = PROSODIA.get(normalizar(nome), (0, 0, 0))
    k = max(0.0, min(1.6, float(intensidade)))
    dr, dp, dv = dr * k, dp * k, dv * k

    def _num(txt, unidade):
        try:
            return float(str(txt or "0").replace(unidade, "").replace("+", "").strip())
        except ValueError:
            return 0.0

    cfg["rate"] = _sinal(_num(cfg.get("rate"), "%") + dr, "%")
    cfg["pitch"] = _sinal(_num(cfg.get("pitch"), "Hz") + dp, "Hz")
    if abs(dv) > 0.5:
        cfg["volume"] = _sinal(_num(cfg.get("volume"), "%") + dv, "%")
    return cfg


# TEMPO CÔMICO. A pausa antes da tirada é o instrumento mais barato da
# comédia -- e o motor já sabe inserir silêncio de verdade entre trechos
# (juntar_com_respiro). O que faltava era usar isso de propósito em vez de
# repetir 0,45s quatro vezes, que é o que faz quatro falas soarem como uma
# lista de itens.
RESPIRO_PADRAO = 0.34
RESPIRO_ANTES_DA_TIRADA = 0.85
RESPIRO_FINAL = 0.60


def respiro_sugerido(i, total):
    """Quanto silêncio DEPOIS do trecho `i` de `total`.

    O penúltimo respiro é o longo: é a pausa que separa a montagem da
    piada da piada. O último segura o quadro por meio segundo depois do
    fim -- sem ele o vídeo corta na sílaba final e o YouTube já emenda no
    próximo antes de a graça cair."""
    if total >= 2 and i == total - 2:
        return RESPIRO_ANTES_DA_TIRADA
    if i == total - 1:
        return RESPIRO_FINAL
    return RESPIRO_PADRAO


# =====================================================================
# PISCAR
# =====================================================================
def piscando(n_frame, fps, semente=0, expr_nome="neutro"):
    """Piscada com intervalo irregular.

    A piscada antiga era `n % 82 in (0, 1)`: exatamente a cada 3,42s, para
    sempre. Regularidade de metrônomo é justamente o que o olho identifica
    como máquina -- e num Short de 18 segundos dá cinco piscadas no mesmo
    compasso. Gente pisca a cada 2 a 6 segundos, sem padrão.

    Determinístico de propósito (seno com dois períodos incomensuráveis):
    o mesmo render produz o mesmo vídeo, o que importa para conferir
    mudança de código quadro a quadro."""
    if normalizar(expr_nome) in SEM_PISCAR:
        return False
    s = n_frame / float(fps)
    r = 0.5 * (math.sin(s * 1.13 + semente) + math.sin(s * 0.41 + 2.1 * semente))
    return r > 0.93
