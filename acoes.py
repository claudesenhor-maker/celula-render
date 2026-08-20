#!/usr/bin/env python3
"""
acoes — o vocabulário de MOVIMENTO do personagem, e a única fonte de
movimento que o rig aceita.

POR QUE ESTE ARQUIVO EXISTE
    O vídeo de 20/08 não tinha movimento, tinha AGITAÇÃO. O motor pegava
    duas poses estáticas por trecho (`pose` e `pose_saida`), interpolava
    de uma para a outra ao longo da fala inteira e somava um seno no
    quadril. Resultado: o personagem balançava os braços de um jeito que
    não tinha relação nenhuma com o que ele estava dizendo, e nunca saía
    do lugar -- "nada justifica os movimentos, o personagem não anda".

    Duas coisas faltavam, e as duas são estruturais:

    1. NÃO EXISTIA LOCOMOÇÃO. O rig só sabia girar ossos em torno de um
       quadril cravado em x=540. Não havia ciclo de passada, não havia
       câmera, não havia fundo que andasse. Andar era literalmente
       inexprimível -- nenhum valor de `pose` produziria uma caminhada.

    2. NÃO EXISTIA CAUSA. `pose` é um adjetivo ("bracos_abertos"), não um
       verbo. Adjetivo não se liga ao texto. Uma AÇÃO se liga: ela tem
       nome de verbo, tem começo e fim dentro do trecho, e tem um campo
       `motivo` que o roteirista é obrigado a preencher com a razão pela
       qual o personagem faz aquilo naquele instante da fala.

    Então o movimento passa a ser descrito assim, dentro de cada trecho:

        "acoes": [
          {"nome": "entrar_andando", "de": 0.0, "ate": 0.45, "sentido": 1,
           "motivo": "ele chega em cena falando, por isso entra andando"},
          {"nome": "apontar", "de": 0.55, "ate": 1.0,
           "motivo": "aponta para o preco no exato momento em que o cita"}
        ]

    `de` e `ate` são frações da duração do trecho -- o trecho dura o que a
    voz durar, então fração é a única unidade que não desincroniza.

O QUE UMA AÇÃO É, TECNICAMENTE
    Uma função f(u, rig, dur, args) -> cam, onde:
      u     0..1, progresso DENTRO da janela da ação
      rig   dicionário de ângulos, alterado no lugar
      dur   duração em segundos da janela (para ações cíclicas saberem
            quantos ciclos cabem -- passada é por segundo, não por trecho)
      args  o próprio dicionário da ação (sentido, forca, etc.)
      cam   deslocamento de câmera/fundo que a ação provoca

    Ações se acumulam: as janelas podem se sobrepor e cada uma escreve
    nos ossos que lhe interessam. "andar" mexe em pernas e braços;
    "apontar" sobrescreve um braço por cima. É isso que permite
    "andar apontando" sem inventar uma terceira ação.

CONVENÇÃO DE ÂNGULO (a mesma do palito_v4)
    Graus, tela com y para baixo: 0 = direita, 90 = baixo, -90 = cima.
    Perna e braço são [ângulo_do_osso_superior, dobra_da_articulação];
    a dobra é SOMADA ao ângulo do osso superior para desenhar o inferior.
    Joelho e cotovelo humanos dobram para trás: com o personagem andando
    para a direita, a dobra é negativa.
"""
import math

# Câmera neutra: nada de zoom, nada de deslocamento, personagem virado
# para a direita (que é como a folha do personagem foi desenhada).
CAM_NEUTRA = {"fundo_dx": 0.0, "zoom": 1.0, "zoom_y": 0.5,
              "espelhar": False, "escala_y": 1.0, "achatar": 1.0}

# Ações que seguram os primeiros 2 segundos. O motor recusa abrir um
# vídeo sem uma delas -- ver `garantir_gancho`.
ACOES_DE_GANCHO = ("susto", "pular", "tropecar", "entrar_correndo", "cair")


def _suave(u):
    """Ease in-out. Movimento que começa e termina bruscamente parece
    interpolação de computador; com isto parece intenção."""
    return u * u * (3.0 - 2.0 * u)


def _pulso(u):
    """0 -> 1 -> 0. Para ações de impacto, que vão e voltam."""
    return math.sin(math.pi * max(0.0, min(1.0, u)))


# =====================================================================
# LOCOMOÇÃO
# =====================================================================
def _ciclo_passada(rig, fase, amp=34.0):
    """Uma passada em linguagem de DESENHO, não de anatomia.

    A primeira versão era um walk cycle naturalista: pernas em oposição
    de fase, joelho dobrando pouco, quique de 7px. Estava tecnicamente
    correto e não combinava com o personagem -- boneco cartoon de cabeça
    grande andando como um adulto real parece um adulto real fantasiado.

    O que muda numa caminhada cartoon:
      * QUIQUE GRANDE. O corpo sobe uns 4% da própria altura na passagem
        e afunda no contato. É o que dá o ritmo, e é a primeira coisa que
        o olho lê como "desenho animado".
      * ARCOS AMPLOS. A perna abre muito mais e o joelho dobra muito mais
        do que um humano dobraria. Amplitude é o que sobra de expressão
        quando a figura tem cinco formas no total.
      * SQUASH & STRETCH. Achata no contato, estica no ar. Sem isso o
        quique parece elevador.
      * ATRASO NAS PONTAS. Pulso e tornozelo chegam DEPOIS do osso que os
        arrasta. É o detalhe que separa articulado de rígido -- e é a
        razão de o rig ter ganhado pulso e tornozelo.

    A fase avança 2*pi por passada completa (dois passos).
    """
    s_, sd = math.sin(fase), math.sin(fase + math.pi)
    passagem = abs(s_)                   # 1 no meio do passo, 0 no contato

    coxa_e = 90.0 + amp * s_
    coxa_d = 90.0 + amp * sd
    joelho_e = -max(0.0, 66.0 * math.sin(fase - 0.7))
    joelho_d = -max(0.0, 66.0 * math.sin(fase + math.pi - 0.7))
    # tornozelo: o pé tende a ficar paralelo ao chão (o desenho do pé já
    # está na horizontal) e a ponta cai no balanço, com atraso
    pe_e = (90.0 - (coxa_e + joelho_e)) + 24.0 * max(0.0, math.sin(fase - 1.1))
    pe_d = (90.0 - (coxa_d + joelho_d)) + 24.0 * max(0.0, math.sin(fase + math.pi - 1.1))
    rig["perna_e"] = [coxa_e, joelho_e, pe_e]
    rig["perna_d"] = [coxa_d, joelho_d, pe_d]

    # braços contrabalançam a perna oposta; cotovelo sempre um pouco
    # dobrado (braço reto é pose de soldado) e pulso atrasado
    b = 0.62 * amp
    rig["braco_e"] = [90.0 - b * s_, 16.0 + 14.0 * passagem, 12.0 * math.sin(fase - 0.6)]
    rig["braco_d"] = [90.0 + b * s_, -16.0 - 14.0 * passagem, -12.0 * math.sin(fase - 0.6)]

    rig["tronco"] = -90.0 + 4.0
    rig["quadril"] = [rig["quadril"][0], rig["quadril"][1] - passagem * 42.0]
    # squash no contato, stretch no ar
    return 1.0 + 0.06 * passagem - 0.05 * (1.0 - passagem)


def andar(u, rig, dur, a):
    """Caminhada no lugar + fundo correndo ao contrário. O personagem fica
    perto do centro do quadro e o CENÁRIO é que anda: é assim que animação
    2D resolve locomoção sem precisar de um cenário infinito."""
    passos = float(a.get("passos_por_s", 1.7))
    sentido = 1 if a.get("sentido", 1) >= 0 else -1
    passada = float(a.get("passada_px", 210.0))     # avanço por passo
    esc_y = _ciclo_passada(rig, 2 * math.pi * passos * u * dur,
                           amp=float(a.get("amplitude", 34.0)))
    # o fundo anda o mesmo tanto que o pé andaria: sem isto o personagem
    # patina, que é o erro clássico de walk cycle
    return {"fundo_dx": -sentido * passada * passos * u * dur,
            "espelhar": sentido < 0, "escala_y": esc_y}


def entrar_andando(u, rig, dur, a):
    """Entra pela borda do quadro andando até o centro. Serve de gancho
    fraco: alguma coisa acontece já no primeiro frame."""
    cam = andar(u, rig, dur, a)
    sentido = 1 if a.get("sentido", 1) >= 0 else -1
    borda = 540 - sentido * 760
    rig["quadril"] = [borda + (540 - borda) * _suave(u), rig["quadril"][1]]
    cam["fundo_dx"] *= 0.25          # entrando, quase todo o avanço é do corpo
    return cam


def sair_andando(u, rig, dur, a):
    cam = andar(u, rig, dur, a)
    sentido = 1 if a.get("sentido", 1) >= 0 else -1
    rig["quadril"] = [540 + sentido * 760 * _suave(u), rig["quadril"][1]]
    cam["fundo_dx"] *= 0.25
    return cam


def entrar_correndo(u, rig, dur, a):
    b = dict(a)
    b.setdefault("passos_por_s", 3.2)
    b.setdefault("amplitude", 40.0)
    cam = entrar_andando(u, rig, dur, b)
    cam["zoom"] = 1.10 - 0.10 * _suave(u)      # a câmera "recebe" o corpo
    return cam


# =====================================================================
# GESTO
# =====================================================================
def apontar(u, rig, dur, a):
    """Aponta e SEGURA. Gesto que volta ao neutro no meio da frase lê
    como tique nervoso; gesto que fica lê como ênfase."""
    alvo = float(a.get("altura", -8.0))        # -90 = apontando para cima
    k = _suave(min(1.0, u * 3.0))              # sobe rápido, segura o resto
    rig["braco_d"] = [90.0 + (alvo - 90.0) * k, -6.0 * k]
    return {}


def acenar(u, rig, dur, a):
    rig["braco_d"] = [-30.0, -18.0 + 26.0 * math.sin(2 * math.pi * 2.2 * u * dur)]
    return {}


def encolher_ombros(u, rig, dur, a):
    k = _pulso(u)
    rig["braco_e"] = [90.0 + 62.0 * k, 56.0 * k]
    rig["braco_d"] = [90.0 - 62.0 * k, -56.0 * k]
    rig["tronco"] = -90.0 - 3.0 * k
    return {}


def maos_na_cabeca(u, rig, dur, a):
    k = _suave(min(1.0, u * 2.5))
    rig["braco_e"] = [90.0 + 105.0 * k, 62.0 * k]
    rig["braco_d"] = [90.0 - 105.0 * k, -62.0 * k]
    return {}


def cocar_cabeca(u, rig, dur, a):
    k = _suave(min(1.0, u * 2.5))
    rig["braco_d"] = [90.0 - 112.0 * k, -70.0 * k + 8.0 * math.sin(2 * math.pi * 3 * u * dur)]
    return {}


# =====================================================================
# IMPACTO — é daqui que sai o gancho dos 2 primeiros segundos
# =====================================================================
def susto(u, rig, dur, a):
    """Leva um susto: recua, joga os braços para cima, arregala. A câmera
    dá um soco para trás junto. É a ação mais barata que segura os 2
    primeiros segundos, porque o pico acontece no frame ~3."""
    forca = float(a.get("forca", 1.0))
    k = _pulso(min(1.0, u * 1.6)) * forca      # pico bem no começo
    rig["braco_e"] = [90.0 + 118.0 * k, 40.0 * k]
    rig["braco_d"] = [90.0 - 118.0 * k, -40.0 * k]
    rig["perna_e"] = [90.0 + 16.0 * k, -10.0 * k]
    rig["perna_d"] = [90.0 - 16.0 * k, -10.0 * k]
    rig["tronco"] = -90.0 - 12.0 * k
    rig["sobrancelha"] = 1.0
    rig["quadril"] = [rig["quadril"][0] - 34.0 * k, rig["quadril"][1] - 26.0 * k]
    return {"zoom": 1.0 + 0.28 * k, "zoom_y": 0.34}


def pular(u, rig, dur, a):
    """Parábola de verdade: sobe, desagacha no ar, aterrissa agachando.
    O agachamento antes e depois é o que faz o pulo ter peso."""
    alt = float(a.get("altura_px", 300.0))
    ar = max(0.0, math.sin(math.pi * u))
    agacha = max(0.0, math.sin(math.pi * u) ** 8) * 0  # (ver abaixo)
    # agachamento nas pontas: 1 no começo/fim, 0 no ápice
    agacha = (1.0 - ar) ** 3
    rig["quadril"] = [rig["quadril"][0], rig["quadril"][1] - alt * ar + 30.0 * agacha]
    rig["perna_e"] = [90.0 + 22.0 * ar + 26.0 * agacha, -66.0 * ar - 52.0 * agacha]
    rig["perna_d"] = [90.0 - 22.0 * ar + 26.0 * agacha, -66.0 * ar - 52.0 * agacha]
    rig["braco_e"] = [90.0 + 96.0 * ar, 24.0 * ar]
    rig["braco_d"] = [90.0 - 96.0 * ar, -24.0 * ar]
    return {}


def tropecar(u, rig, dur, a):
    """Tropeça e se equilibra. Metade do tempo caindo, metade voltando."""
    k = _pulso(u)
    rig["tronco"] = -90.0 + 26.0 * k
    rig["quadril"] = [rig["quadril"][0] + 60.0 * k, rig["quadril"][1] + 18.0 * k]
    rig["perna_d"] = [90.0 - 46.0 * k, -30.0 * k]
    rig["perna_e"] = [90.0 + 30.0 * k, -14.0 * k]
    rig["braco_e"] = [90.0 + 92.0 * k, 30.0 * k]
    rig["braco_d"] = [90.0 - 92.0 * k, -30.0 * k]
    return {"zoom": 1.0 + 0.10 * k}


def cair(u, rig, dur, a):
    """Cai de vez e fica caído. Termina deitado, não volta."""
    k = _suave(min(1.0, u * 1.4))
    rig["tronco"] = -90.0 + 82.0 * k
    rig["quadril"] = [rig["quadril"][0] + 40.0 * k, rig["quadril"][1] + 150.0 * k]
    rig["perna_e"] = [90.0 + 62.0 * k, -70.0 * k]
    rig["perna_d"] = [90.0 - 20.0 * k, -40.0 * k]
    rig["braco_e"] = [90.0 + 70.0 * k, 20.0 * k]
    rig["braco_d"] = [90.0 - 70.0 * k, -20.0 * k]
    return {}


def virar(u, rig, dur, a):
    """Vira de costas para o outro lado. Achata na horizontal no meio da
    virada -- o truque de cut-out para não precisar de arte de perfil."""
    k = _suave(u)
    return {"espelhar": k > 0.5, "achatar": abs(math.cos(math.pi * k))}


# =====================================================================
# ESPERA
# =====================================================================
def parado(u, rig, dur, a):
    """Respiração. Não é decoração: personagem 100% imóvel lê como
    imagem congelada e o espectador acha que o vídeo travou."""
    rig["quadril"] = [rig["quadril"][0],
                      rig["quadril"][1] + math.sin(2 * math.pi * 0.28 * u * dur) * 5.0]
    return {}


CATALOGO = {
    "andar": andar,
    "entrar_andando": entrar_andando,
    "sair_andando": sair_andando,
    "entrar_correndo": entrar_correndo,
    "apontar": apontar,
    "acenar": acenar,
    "encolher_ombros": encolher_ombros,
    "maos_na_cabeca": maos_na_cabeca,
    "cocar_cabeca": cocar_cabeca,
    "susto": susto,
    "pular": pular,
    "tropecar": tropecar,
    "cair": cair,
    "virar": virar,
    "parado": parado,
}


# =====================================================================
def aplicar(acoes, t_rel, rig, dur_trecho):
    """Aplica, em ordem, todas as ações cuja janela contém t_rel (0..1).

    Ordem = precedência: a última ação da lista escreve por cima. É como
    "andar apontando" funciona -- `andar` mexe nos dois braços, `apontar`
    vem depois e sobrescreve um deles.
    """
    cam = dict(CAM_NEUTRA)
    for a in acoes or []:
        f = CATALOGO.get(a.get("nome"))
        if f is None:
            continue
        de = float(a.get("de", 0.0))
        ate = float(a.get("ate", 1.0))
        if not (de <= t_rel <= ate) or ate <= de:
            continue
        u = (t_rel - de) / (ate - de)
        d = f(u, rig, dur_trecho * (ate - de), a) or {}
        for k, v in d.items():
            # deslocamento de fundo é cumulativo; o resto, o último manda
            cam[k] = cam.get(k, 0.0) + v if k == "fundo_dx" else v
    return cam


def garantir_gancho(spec):
    """Nenhum vídeo abre sem gatilho. Se o roteirista não pôs uma ação
    forte nos 2 primeiros segundos do primeiro trecho, o motor injeta uma.

    Isto é de propósito uma rede de segurança no MOTOR e não só uma
    instrução no prompt: prompt o modelo desobedece, motor não.
    """
    trechos = spec.get("trechos") or []
    if not trechos:
        return spec
    t0 = trechos[0]
    acoes = t0.get("acoes") or []
    tem = any(a.get("nome") in ACOES_DE_GANCHO and float(a.get("de", 0.0)) <= 0.15
              for a in acoes)
    if not tem:
        t0["acoes"] = [{"nome": "susto", "de": 0.0, "ate": 0.42, "forca": 1.0,
                        "motivo": "gancho automatico: o motor exige uma acao "
                                  "forte nos primeiros segundos"}] + acoes
        print("[acoes] trecho 0 sem gancho -- injetado 'susto'")
    return spec
