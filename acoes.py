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
# PERNAS RETAS é o repouso, e é daqui que toda ação parte. A folha desenha
# as duas pernas apontando para baixo; qualquer ângulo diferente de 90 é
# perna aberta. O REST do palito_v4 traz [97, 5] e [83, -5] -- 7 graus de
# abertura e 5 de joelho dobrado --, que num rig vetorial de traço fino
# passava despercebido e num boneco de papel de perna grossa lê como
# personagem de pernas tortas, parado.
PERNA_RETA_E = [90.0, 0.0, 0.0]
PERNA_RETA_D = [90.0, 0.0, 0.0]


def _pernas_retas(rig):
    rig["perna_e"] = list(PERNA_RETA_E)
    rig["perna_d"] = list(PERNA_RETA_D)


def _ciclo_passo_lateral(rig, fase, amp=26.0, sentido=1):
    """A caminhada do boneco frontal: PASSO LATERAL, sem cruzar as pernas.

    POR QUE A CAMINHADA ANTIGA NÃO PODIA DAR CERTO (26/08)
        O ciclo anterior era um walk cycle de PERFIL: coxas em oposição de
        fase, uma indo para a frente enquanto a outra vai para trás. Só que
        a folha do Pal é desenhada DE FRENTE, e o motor gira as peças no
        plano da tela -- não existe "para a frente" ali. Girar a coxa 34
        graus não põe a perna à frente do corpo: põe a perna PARA O LADO.
        Com as duas em oposição de fase, uma abria para a esquerda enquanto
        a outra abria para a direita e, meio ciclo depois, trocavam. O olho
        lê isso como tesoura -- "cruzando as pernas" foi exatamente a
        descrição de quem assistiu.

        Não é defeito de ajuste: nenhuma amplitude conserta um ciclo de
        perfil rodando numa figura frontal. Ou a arte ganha um perfil (uma
        folha inteira nova por personagem), ou a caminhada passa a ser uma
        que EXISTE de frente.

    O QUE ELA É
        O passo lateral: o personagem encara a câmera e se desloca de lado,
        como um boneco articulado de papel faria. Cada perna abre para o
        SEU lado e volta -- nenhuma delas cruza o eixo do corpo em momento
        nenhum, e é isso que mata a tesoura por construção, não por
        calibragem.

        O ritmo é o de quem dá um passo e puxa o outro pé: a perna do lado
        para onde ele vai abre primeiro, a de trás fecha em seguida. Nos
        instantes em que as duas estão juntas, o corpo sobe (é o único
        momento em que os dois pés poderiam sair do chão) e desce ao abrir
        de novo. É o quique da animação cartoon, na fase certa.

    Devolve a escala vertical (squash & stretch) do frame.
    """
    # abertura de cada perna, 0..1, sempre para o próprio lado
    s = math.sin(fase)
    guia = 0.5 + 0.5 * s               # a perna do lado do movimento
    tras = 0.5 - 0.5 * s               # a outra, meio ciclo atrás
    juntas = 1.0 - abs(s)              # 1 quando as duas estão embaixo do corpo

    # PISO DE ABERTURA: uma perna nunca chega a colar na outra. Sem ele o
    # boneco junta os pés a cada meio passo e parece que bate continência.
    ab_e = amp * (0.18 + 0.82 * (guia if sentido < 0 else tras))
    ab_d = amp * (0.18 + 0.82 * (guia if sentido > 0 else tras))

    # A perna que está FECHANDO é a que sai do chão: o joelho dobra para
    # dentro e a canela vem junto com o corpo. Derivada da abertura -- se
    # ela está diminuindo, o pé está no ar.
    c = math.cos(fase)
    fecha_guia = max(0.0, -c)
    fecha_tras = max(0.0, c)
    lev_e = fecha_guia if sentido < 0 else fecha_tras
    lev_d = fecha_guia if sentido > 0 else fecha_tras

    # sinais: +ângulo leva o pé para a ESQUERDA da tela, -ângulo para a
    # direita (y cresce para baixo). O joelho dobra para DENTRO, na direção
    # do corpo, que é o que lê como pé levantado numa figura frontal.
    #
    # O TORNOZELO DESFAZ o que a perna fez: o pé é desenhado apoiado no
    # chão, e os ângulos do rig se somam ao longo da cadeia -- sem
    # compensar, a sola acompanha a coxa e o boneco anda de pé torto. O que
    # sobra é um resto pequeno no pé que está no ar, que é a ponta caindo.
    joelho_e, joelho_d = -18.0 * lev_e, 18.0 * lev_d
    rig["perna_e"] = [90.0 + ab_e, joelho_e, -(ab_e + joelho_e) + 8.0 * lev_e]
    rig["perna_d"] = [90.0 - ab_d, joelho_d, (ab_d - joelho_d) - 8.0 * lev_d]

    # braços: contrapeso lateral no mesmo compasso, cotovelo sempre um
    # pouco dobrado para dentro (braço reto é pose de soldado)
    b = 0.42 * amp
    _braco(rig, "e", 98.0 + b * s, 78.0 + b * s + 6.0 * juntas, 5.0 * s)
    _braco(rig, "d", 82.0 - b * s, 102.0 - b * s - 6.0 * juntas, -5.0 * s)

    # o tronco pende para o lado do pé de apoio, e o corpo sobe quando os
    # dois pés se encontram
    rig["tronco"] = -90.0 + 2.4 * s
    rig["quadril"] = [rig["quadril"][0], rig["quadril"][1] - juntas * 16.0]
    return 1.0 + 0.03 * juntas - 0.02 * (1.0 - juntas)


def andar(u, rig, dur, a):
    """Passo lateral no lugar + fundo correndo ao contrário. O personagem
    fica perto do centro do quadro e o CENÁRIO é que anda: é assim que
    animação 2D resolve locomoção sem precisar de um cenário infinito.

    O personagem NÃO é espelhado ao mudar de sentido. Espelhar existia para
    virar um boneco de perfil; este anda de frente para a câmera, e
    espelhar uma figura frontal só troca o lado do cabelo -- o que se lê
    como corte de continuidade, não como mudança de direção. Quem indica a
    direção é o fundo correndo e a perna que abre primeiro."""
    passos = float(a.get("passos_por_s", 1.7))
    sentido = 1 if a.get("sentido", 1) >= 0 else -1
    passada = float(a.get("passada_px", 150.0))     # avanço por passo
    esc_y = _ciclo_passo_lateral(rig, 2 * math.pi * passos * u * dur,
                                 amp=float(a.get("amplitude", 26.0)),
                                 sentido=sentido)
    # o fundo anda o mesmo tanto que o pé andaria: sem isto o personagem
    # patina, que é o erro clássico de walk cycle
    return {"fundo_dx": -sentido * passada * passos * u * dur,
            "escala_y": esc_y}


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
    b.setdefault("amplitude", 34.0)
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
    """O repouso: pernas retas, pés no chão, e o mínimo de vida possível.

    O QUE MUDOU, E POR QUÊ (26/08)
        A versão anterior somava um seno de 5px ao QUADRIL para simular
        respiração. Só que o quadril é a raiz do esqueleto: mover o quadril
        move o corpo inteiro, pés inclusive. O personagem subia e descia
        cinco pixels a cada dois segundos, com os pés soltos do chão -- lido
        na tela como "ele fica flutuando", que é exatamente o que era.

        Personagem imóvel de verdade também não serve: lê como imagem
        congelada. A saída é respirar com o que NÃO carrega o corpo. A
        cabeça é a única peça leve que se mexe sem arrastar ninguém, e uma
        oscilação de menos de um grau já basta para o quadro não parecer
        travado -- ainda mais com a piscada e a boca andando por conta.

        As pernas ficam RETAS. Todo ângulo de perna em repouso é abertura
        lateral (o boneco é frontal, ver `_ciclo_passo_lateral`), e os 7
        graus que o REST trazia deixavam o Pal parado em posição de quem
        vai montar a cavalo.
    """
    _pernas_retas(rig)
    rig["cabeca"] = rig.get("cabeca", 0.0) + math.sin(2 * math.pi * 0.24 * u * dur) * 0.7
    return {}


def gesticular(u, rig, dur, a):
    """A mão que acompanha a fala. Não é uma ação do roteiro: é o que o
    corpo faz sozinho enquanto a boca trabalha.

    POR QUE (26/08, "melhorar linguagem corporal")
        Fora das janelas de ação, o Pal falava com os dois braços mortos ao
        lado do corpo, do primeiro ao último frame do trecho. Ninguém fala
        assim, e num Short de 20 segundos o efeito é de boneco de vitrine
        que dubla.

        O gesto aqui é pequeno de propósito e fica NA BASE da pilha de
        ações (ver `aplicar`): qualquer ação escrita pelo roteirista
        sobrescreve o braço que ela usa. `apontar` continua apontando; o
        que some é o braço parado ao lado dele.

    `forca` sai da intensidade do trecho: quem está bravo gesticula mais.
    """
    f = max(0.0, min(1.6, float(a.get("forca", 1.0))))
    if f < 0.01:
        return {}
    w = 2 * math.pi * 0.62 * u * dur          # ~0,6 gesto por segundo
    # Antebraços LEVEMENTE para dentro, subindo e descendo em contratempo.
    # A primeira versão dobrava 26 graus para dentro e as duas mãos se
    # encontravam na frente da barriga -- lido como mãos postas, ou pior,
    # como algemado. O limite é a mão não cruzar o eixo do corpo: o gesto
    # de quem conta um caso acontece na frente do PRÓPRIO ombro.
    _braco(rig, "e", 102.0 + 5.0 * f * math.sin(w),
           92.0 - 13.0 * f * (0.5 + 0.5 * math.sin(w + 0.9)),
           5.0 * f * math.sin(w + 1.6))
    _braco(rig, "d", 78.0 - 5.0 * f * math.sin(w + 2.3),
           88.0 + 13.0 * f * (0.5 + 0.5 * math.sin(w + 3.1)),
           -5.0 * f * math.sin(w + 3.9))
    return {}


# =====================================================================
# LINGUAGEM CORPORAL — poses que o roteirista pede pelo nome
# =====================================================================
# Cada uma existe porque uma emoção do catálogo de expressões precisava de
# um corpo: cara de dúvida com braço caído lê como cara de dúvida em cima
# de um manequim. Todas seguram a pose depois de entrar (gesto que volta ao
# neutro no meio da frase lê como tique), e todas mexem no mínimo de ossos
# possível, para poderem se combinar com `andar`.
#
# A CONVENÇÃO DE BRAÇO, medida no motor e não deduzida da anatomia:
# somando a correção de pose T, o ângulo de cada osso do braço é a DIREÇÃO
# EM QUE ELE APONTA NA TELA, igual nos dois lados -- 0 para a direita, 90
# para baixo, 180 para a esquerda, -90 para cima. O segundo número continua
# sendo a dobra do cotovelo, somada à do ombro; escrever a pose pela direção
# do antebraço e deixar a subtração para `_braco` evita o erro que saiu na
# primeira versão destes gestos, em que todo cotovelo dobrava para FORA e
# ninguém conseguia pôr a mão na cintura.
def _braco(rig, lado, sup, ante, pulso=0.0, k=1.0):
    """Aponta o braço `lado` ('e'/'d'): `sup` e `ante` em graus de tela."""
    osso = "braco_" + lado
    base = (list(rig.get(osso) or [90.0, 0.0, 0.0]) + [0.0, 0.0, 0.0])[:3]
    alvo = [sup, ante - sup, pulso]
    rig[osso] = [b + (v - b) * k for b, v in zip(base, alvo)]


def maos_na_cintura(u, rig, dur, a):
    """Mão na cintura: cobrança, impaciência, "eu avisei".

    O antebraço aponta para BAIXO e um pouco para dentro, não para o meio
    do corpo: com dobra demais as duas mãos se encontravam na barriga."""
    k = _suave(min(1.0, u * 2.5))
    _braco(rig, "e", 118.0, 62.0, 10.0, k)
    _braco(rig, "d", 62.0, 118.0, -10.0, k)
    rig["tronco"] = -90.0
    return {}


def bracos_cruzados(u, rig, dur, a):
    """Fechado, na defensiva, ou esperando explicação.

    O ombro abre para o lado antes de o antebraço cruzar: é isso que põe o
    cotovelo alto o bastante para os braços se cruzarem no PEITO. Com o
    ombro caído os dois antebraços se encontram na barriga e a pose lê como
    mãos postas."""
    k = _suave(min(1.0, u * 2.5))
    _braco(rig, "e", 136.0, -14.0, 4.0, k)
    _braco(rig, "d", 44.0, 194.0, -4.0, k)
    rig["tronco"] = -90.0 - 1.5 * k
    return {}


def mao_no_queixo(u, rig, dur, a):
    """Pensando: o braço sobe à frente e o antebraço aponta para o rosto."""
    k = _suave(min(1.0, u * 2.2))
    _braco(rig, "d", 22.0, -104.0, -10.0, k)
    _braco(rig, "e", 100.0, 118.0, 0.0, k * 0.6)
    return {}


def apresentar(u, rig, dur, a):
    """A palma aberta para o lado: "é isso aí", "olha só". O gesto de
    apresentação é o mais usado por quem conta caso, e faltava."""
    k = _suave(min(1.0, u * 2.4))
    alt = float(a.get("altura", 14.0))          # 0 = braço na horizontal
    _braco(rig, "d", alt, alt - 22.0, -14.0, k)
    return {}


def apontar_para_si(u, rig, dur, a):
    """"Eu?" -- a mão volta para o peito. Vale ouro em piada de vítima."""
    k = _suave(min(1.0, u * 2.6))
    _braco(rig, "d", 46.0, 186.0, -10.0, k)
    rig["tronco"] = -90.0 + 2.0 * k
    return {}


def comemorar(u, rig, dur, a):
    """Os dois braços para cima, com um quique. Fim feliz, ou ironia."""
    k = _pulso(min(1.0, u * 1.3)) if u > 0.6 else _suave(min(1.0, u * 2.2))
    rig["braco_e"] = [90.0 + 128.0 * k, 20.0 * k]
    rig["braco_d"] = [90.0 - 128.0 * k, -20.0 * k]
    rig["quadril"] = [rig["quadril"][0], rig["quadril"][1] - 26.0 * k]
    return {}


def negar(u, rig, dur, a):
    """Balança a cabeça: "não". A única negativa que uma figura frontal
    consegue fazer sem arte nova -- e ela é lida na hora."""
    rig["cabeca"] = rig.get("cabeca", 0.0) + 9.0 * math.sin(2 * math.pi * 1.4 * u * dur)
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
    "maos_na_cintura": maos_na_cintura,
    "bracos_cruzados": bracos_cruzados,
    "mao_no_queixo": mao_no_queixo,
    "apresentar": apresentar,
    "apontar_para_si": apontar_para_si,
    "comemorar": comemorar,
    "negar": negar,
    "susto": susto,
    "pular": pular,
    "tropecar": tropecar,
    "cair": cair,
    "virar": virar,
    "parado": parado,
    "gesticular": gesticular,
}


# =====================================================================
# POSTURA — o corpo que cada emoção pede
# =====================================================================
# O roteirista já escolhe UMA emoção por trecho (`expressao`), e até aqui
# ela só chegava ao rosto. Postura é a mesma escolha lida pelo corpo: a
# diferença entre um personagem triste e um personagem neutro de cara
# triste são os ombros. São deltas somados ao repouso, aplicados ANTES das
# ações -- então qualquer ação do roteiro passa por cima.
#
# tronco: graus somados a -90 (positivo inclina para a frente/direita da
# tela). braco_*: [ombro, cotovelo, pulso] absolutos, como no rig.
#
# Os braços vão escritos como [direção do ombro, direção do antebraço] na
# tela (a convenção de `_braco`), e `aplicar_postura` faz a conta da dobra.
POSTURA = {
    "neutro":      {},
    "sorrindo":    {"tronco": -1.5, "braco_e": [102.0, 88.0],
                    "braco_d": [78.0, 92.0]},
    "confiante":   {"tronco": -2.5, "braco_e": [105.0, 86.0],
                    "braco_d": [75.0, 94.0]},
    # ombros para dentro, peso à frente: quem está bravo ocupa menos espaço
    # lateral e mais espaço para a frente
    "bravo":       {"tronco": 3.5, "braco_e": [96.0, 62.0],
                    "braco_d": [84.0, 118.0]},
    "irritado":    {"tronco": 2.5, "braco_e": [97.0, 70.0],
                    "braco_d": [83.0, 110.0]},
    # ombros caídos e braços quase retos, colados: a tristeza encolhe a
    # silhueta -- é o oposto exato do peito aberto do confiante
    "triste":      {"tronco": 5.0, "braco_e": [93.0, 89.0],
                    "braco_d": [87.0, 91.0]},
    "desesperado": {"tronco": -3.0, "braco_e": [116.0, 74.0],
                    "braco_d": [64.0, 106.0]},
    "surpreso":    {"tronco": -3.0, "braco_e": [110.0, 80.0],
                    "braco_d": [70.0, 100.0]},
    "chocado":     {"tronco": -5.0, "braco_e": [120.0, 72.0],
                    "braco_d": [60.0, 108.0]},
    "duvida":      {"tronco": 1.0, "braco_e": [99.0, 84.0],
                    "braco_d": [82.0, 104.0]},
    "pensando":    {"tronco": 1.5, "braco_e": [98.0, 84.0],
                    "braco_d": [84.0, 110.0]},
    "desdem":      {"tronco": -1.0, "braco_e": [101.0, 85.0],
                    "braco_d": [80.0, 96.0]},
}


# O QUANTO cada emoção gesticula enquanto fala. Multiplica a `forca` de
# `gesticular`. Quem está triste quase não move as mãos; quem está bravo
# move mais do que o normal -- é a mesma informação que a prosódia já usa
# para a voz (expressao.PROSODIA), lida pelos braços.
ENERGIA_GESTO = {
    "triste": 0.35, "pensando": 0.45, "desdem": 0.55, "duvida": 0.7,
    "neutro": 0.85, "confiante": 1.0, "sorrindo": 1.05,
    "irritado": 1.2, "bravo": 1.3, "surpreso": 1.15,
    "chocado": 1.25, "desesperado": 1.35,
}


def energia_gesto(expressao, intensidade=1.0):
    import expressao as _EX
    base = ENERGIA_GESTO.get(_EX.normalizar(expressao), 0.85)
    return base * max(0.0, min(1.6, float(intensidade)))


def aplicar_postura(rig, expressao, intensidade=1.0):
    """Soma ao rig a postura da emoção do trecho, diluída pela intensidade.

    Fica fora de `aplicar` de propósito: postura é ESTADO do trecho, não um
    verbo com janela. Ações continuam sendo a única coisa que se move com
    tempo próprio."""
    import expressao as _EX
    p = POSTURA.get(_EX.normalizar(expressao), {})
    if not p:
        return rig
    k = max(0.0, min(1.6, float(intensidade)))
    for osso, valor in p.items():
        if osso == "tronco":
            rig["tronco"] = rig.get("tronco", -90.0) + valor * k
        elif osso.startswith("braco_"):
            _braco(rig, osso[-1], valor[0], valor[1],
                   valor[2] if len(valor) > 2 else 0.0, k)
        else:
            base = (list(rig.get(osso) or [90.0, 0.0, 0.0]) + [0.0, 0.0, 0.0])[:3]
            alvo = (list(valor) + [0.0, 0.0, 0.0])[:3]
            rig[osso] = [b + (v - b) * k for b, v in zip(base, alvo)]
    return rig


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
