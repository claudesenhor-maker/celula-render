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
import os

# Câmera neutra: nada de zoom, nada de deslocamento, personagem virado
# para a direita (que é como a folha do personagem foi desenhada).
CAM_NEUTRA = {"fundo_dx": 0.0, "zoom": 1.0, "zoom_y": 0.5,
              "espelhar": False, "escala_y": 1.0, "achatar": 1.0}

# Ações que seguram os primeiros 2 segundos. O motor recusa abrir um
# vídeo sem uma delas -- ver `garantir_gancho`.
ACOES_DE_GANCHO = ("susto", "pular", "tropecar", "entrar_correndo", "cair")

# Quem entra e quem sai do quadro. O motor usa as duas listas para saber
# se um ator terminou o trecho FORA de cena -- ver `_quem_saiu`.
ACOES_DE_ENTRADA = ("entrar_andando", "entrar_correndo")
ACOES_DE_SAIDA = ("sair_andando",)


# O GESTO NÃO TELEPORTA (31/08, defeitos vistos nos vídeos do ciclo)
#
# A queixa do dono do projeto, olhando os vídeos: *"do nada eles acenam e
# depois o braço teletransporta para baixo"*. As duas metades são o mesmo
# defeito, e ele mora em `aplicar`, não nas ações:
#
#   * o gesto ENTRA de uma vez. `acenar` põe `braco_d` em [-30, ...] já no
#     primeiro frame da janela: de braço caído a braço no alto em 1/24 de
#     segundo, sem nada no meio;
#   * o gesto SAI de uma vez. Passada a janela, a ação deixa de ser
#     aplicada e o corpo volta ao repouso no frame seguinte -- que é
#     exatamente o "teletransporta para baixo".
#
# Nenhum ajuste de ângulo conserta isso: o que falta é TEMPO. Todo gesto
# passa a ter ataque e soltura, misturados com a pose que havia ANTES dele
# (`_pesar`).
#
# O TEMPO NÃO É CONSTANTE: ELE SAI DO PERCURSO. As poses são escritas em
# ângulo ABSOLUTO, então uma que começa depois de `apontar` para cima leva o
# braço de -90 a +80 -- 170 graus --, enquanto `encolher_ombros` anda 20.
# Dar o mesmo tempo aos dois é dar ao primeiro a velocidade de um estalo e
# ao segundo a de um bocejo. O que é constante é a VELOCIDADE: 480 graus por
# segundo é o braço rápido de desenho animado -- 20 graus por frame de
# média, ~40 no pico do ease, que é o teto de `ferramentas/gesto.py`.
#
# Os limites existem para os extremos: gesto de dois graus não pode durar
# zero (viraria um piscar), e troca de pose inteira não pode passar de meio
# segundo (viraria câmera lenta).
VEL_MAX_GS = 480.0
ATAQUE_MIN, ATAQUE_MAX = 0.12, 0.45
SOLTURA_MIN, SOLTURA_MAX = 0.20, 0.55

# QUEM NÃO GANHA ENVELOPE. Locomoção é POSIÇÃO NO MUNDO, não pose: misturar
# `entrar_andando` com o repouso faria o corpo aparecer no meio do caminho,
# e a soltura o levaria de volta à borda depois de ele já ter chegado.
# `parado` e `gesticular` são a base da pilha e valem o trecho inteiro.
# `virar` não volta -- estar virado é estado, e ela só mexe na câmera.
#
# `cair` NÃO está aqui, apesar de também não voltar: quem a segura depois
# da janela é `ACOES_QUE_FICAM`, e o que ela ganha do envelope é o ATAQUE
# -- sem ele, cair depois de `apontar` para cima jogava o braço 126 graus
# num frame, porque a pose de queda é escrita em ângulo absoluto e começa
# do repouso, não de onde o braço está.
#
# `andar` FICA DE FORA DA LISTA de propósito: ela não mexe no quadril (quem
# anda fica no lugar e o fundo é que corre), então misturá-la é misturar só
# a passada -- e uma passada que começa de uma vez é o mesmo salto de braço
# por outro nome.
SEM_ENVELOPE = frozenset(("parado", "gesticular", "escutar", "virar",
                          "segurar"))

# O QUE A FALA PRECISA DIZER PARA O GESTO TER LICENÇA (04/09, ciclo 25).
#
# Não é uma lista de sinônimos do gesto: é o que a fala tem de conter para
# aquele gesto fazer sentido em cima dela. `apontar` quer um alvo; `acenar`
# quer um cumprimento ou uma despedida. Fora disso o gesto é enfeite, e enfeite
# é a metade "não condiz com o roteiro" da queixa 2 do dono do projeto.
#
# MORA AQUI, E NÃO NA RÉGUA, porque agora as duas pontas a usam:
# `ferramentas/regua_movimento.py` a importa para MEDIR, e `palito_cutout`
# para TROCAR o gesto sem licença. Duas cópias divergiriam no primeiro ajuste,
# e o motor passaria a agir por um critério que a régua não mede.
LICENCA = {
    "apontar": ("isso", "isto", "aquilo", "esse", "essa", "aquele", "aquela",
                "olha", "olhe", "ali", "la", "aqui", "ve", "veja", "esta",
                "voce", "ce", "teu", "tua", "seu", "sua"),
    "apontar_para_si": ("eu", "meu", "minha", "mim", "comigo", "me"),
    # "acen" entra porque a fala do v014 é *"essa camisa rasga só quando eu
    # levanto o braço pra acenar"*: quando o texto NOMEIA o gesto, ele está
    # licenciado por definição, e a régua o marcava como enfeite.
    "acenar": ("oi", "ola", "tchau", "bom dia", "boa tarde", "boa noite",
               "e ai", "fala", "opa", "ate", "falou", "valeu", "acen"),
    "negar": ("nao", "nunca", "jamais", "nada", "nenhum", "nenhuma", "sem"),
    "encolher_ombros": ("sei la", "nao sei", "talvez", "sei nao", "vai saber",
                        "qualquer", "tanto faz"),
    "comemorar": ("consegui", "deu certo", "ganhei", "aeee", "boa", "eba",
                  "finalmente", "graças", "gracas", "ufa"),
    "mao_no_queixo": ("acho", "pensa", "penso", "sera", "hmm", "duvida",
                      "estranho", "esquisito"),
}

# QUANDO O GESTO NÃO TEM LICENÇA, QUAL ENTRA NO LUGAR.
#
# Só `acenar` está aqui, e a razão é a lei 37: dos quinze `acenar` do corpus,
# treze não trazem cumprimento nem despedida -- e o campo `motivo` que o
# roteirista escreveu ao lado deles diz o que ele queria de verdade:
#
#     "acena tentando explicar"   "gesticula empatia"   "acena frustrada"
#     "gesto de tranquilizacao"   "confirma a suposicao com um gesto"
#
# Nenhum é um cumprimento. **Isto não é indisciplina, é falta de palavra:**
# o modelo usa `acenar` como verbo genérico de "mexe o braço com ênfase",
# porque é o que o vocabulário oferece. `apresentar` -- a palma aberta para o
# lado, *"é isso aí", "olha só"* -- é exatamente o gesto pedido, está no
# catálogo desde 31/08 e foi usado **zero vezes** em 25 voltas.
#
# Os outros ficam de fora de propósito. Lendo os casos que a régua marca em
# `encolher_ombros` (*"tá osso, né?"*, *"que mico"*, *"o valor voltou, mas o
# ridículo ficou"*), a maioria É um ombro de resignação legítimo: quem está
# errado ali é a lista de licença, que só conhece "sei lá". Trocar o gesto por
# uma régua que marca o certo é o erro que produziu as cem primeiras voltas.
TROCA_SEM_LICENCA = {"acenar": "apresentar"}

# ENTRAR E SAIR MISTURAM OS MEMBROS, NUNCA O LUGAR. A posição no mundo tem
# de ser exata -- misturá-la faria o corpo aparecer no meio do caminho --,
# mas os BRAÇOS de quem começa a andar vinham de uma vez: no v019 um trecho
# aponta para cima e meio segundo depois entra andando, e o braço ia de -8
# para +80 num frame. Quadril de fora, membros dentro.
SO_MEMBROS = frozenset(ACOES_DE_ENTRADA + ACOES_DE_SAIDA)


def sem_acento(s):
    """Minúsculas e sem acento. A licença se procura no texto assim."""
    s = str(s or "").lower()
    for a, b in (("á", "a"), ("à", "a"), ("ã", "a"), ("â", "a"), ("é", "e"),
                 ("ê", "e"), ("í", "i"), ("ó", "o"), ("ô", "o"), ("õ", "o"),
                 ("ú", "u"), ("ç", "c")):
        s = s.replace(a, b)
    return s


# O MOTIVO ANCORA O GESTO DÊITICO (04/09, ciclo 25).
#
# `apontar` é o gesto mais usado do canal (61 vezes em 25 voltas) e a régua
# marcava 25 deles como "a fala não pede". Lendo os 25 -- lei 37, ver o que ela
# marcou antes de obedecer --, o `motivo` que o roteirista escreveu ao lado
# quase sempre nomeia um alvo que ESTÁ na fala:
#
#     "aponta para o aviso"     :: Colocaram um AVISO enorme no meu lugar
#     "aponta para a porta"     :: O juiz tá batendo na PORTA agora
#     "aponta para o celular"   :: ... a foto já rodou no grupo
#
# Quem está errado é a lista de licença, que só conhece demonstrativo e
# pronome de segunda pessoa. Apontar precisa é de UM ALVO, e a lei 7 já diz
# que toda ação carrega a razão dela escrita: se o alvo que o `motivo` nomeia
# aparece na fala, o gesto está ancorado no texto e não é enfeite.
#
# Isto vale só para o dêitico. `acenar` continua exigindo cumprimento -- lá o
# `motivo` é justamente o que denuncia o erro (*"acena tentando explicar"*), e
# aceitá-lo como âncora aprovaria o que se quer trocar.
GESTO_ANCORA_NO_MOTIVO = ("apontar",)
_VAZIAS = {"para", "pelo", "pela", "ao", "aos", "com", "que", "onde", "esta",
           "aponta", "apontando", "mostra", "mostrando", "gesto", "mao",
           "dedo", "indica", "indicando", "enquanto", "quando", "sobre",
           "imaginario", "imaginaria", "lado", "cima", "baixo", "frente"}


def tem_licenca(nome, fala, motivo=None):
    """A fala pede este gesto? Gesto fora de `LICENCA` não exige nada."""
    palavras = LICENCA.get(nome)
    if not palavras:
        return True
    limpa = sem_acento(fala)
    if any(p in limpa for p in palavras):
        return True
    if nome in GESTO_ANCORA_NO_MOTIVO and motivo:
        for w in sem_acento(motivo).replace(",", " ").split():
            w = w.strip(".;:!?\"'()")
            if len(w) >= 4 and w not in _VAZIAS and w[:5] in limpa:
                return True
    return False


def _suave(u):
    """Ease in-out. Movimento que começa e termina bruscamente parece
    interpolação de computador; com isto parece intenção."""
    return u * u * (3.0 - 2.0 * u)


def _pulso(u):
    """0 -> 1 -> 0. Para ações de impacto, que vão e voltam."""
    return math.sin(math.pi * max(0.0, min(1.0, u)))


# Quanto o gesto PASSA do alvo antes de assentar. 6% de um percurso de 90
# graus são 5,4 graus -- invisível como erro, e é justamente ele que faz o
# braço ler com peso.
SOBRA_ATAQUE = 0.06
FIM_DA_SOBRA = 0.78


def _ataque(u):
    """Ease-in-out que PASSA DO ALVO e volta (overshoot + settle).

    POR QUE (01/09, volta 57)
        `_suave` chega ao alvo e para, exatamente no alvo. Isso é o que um
        computador faz e não é o que um corpo faz: uma massa que acelera
        passa do ponto e assenta. Nos doze princípios da animação isso tem
        nome -- *follow through* e *overlapping action* -- e a literatura
        de percepção mostra que exagerar levemente a mecânica é o que faz
        o movimento ser lido como VIVO, não como interpolado.

        É a resposta mais barata que existe para "o vídeo é de gente
        parada": não acrescenta ação nenhuma, não gasta LLM, não mexe no
        roteiro. Só muda a CURVA com que as ações que já existem chegam.

    A sobra é pequena de propósito (6%) e some até o fim da janela, então
    a pose final continua sendo exatamente a que a ação escreveu -- o que
    importa para `ACOES_QUE_FICAM`, que congela essa pose depois.
    """
    u = max(0.0, min(1.0, u))
    if u <= FIM_DA_SOBRA:
        return _suave(u / FIM_DA_SOBRA) * (1.0 + SOBRA_ATAQUE)
    return (1.0 + SOBRA_ATAQUE) - SOBRA_ATAQUE * _suave(
        (u - FIM_DA_SOBRA) / (1.0 - FIM_DA_SOBRA))


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

# O quadro, e o quanto uma entrada começa FORA dele. Vive aqui para que
# `entrar_andando`/`sair_andando` não voltem a cravar 540 (ver lá).
LARG_QUADRO = 1080.0
FORA_DO_QUADRO = 340.0


def _pernas_retas(rig):
    rig["perna_e"] = list(PERNA_RETA_E)
    rig["perna_d"] = list(PERNA_RETA_D)


def _ciclo_passo_lateral(rig, fase, amp=24.0, sentido=1):
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
    juntas = 1.0 - abs(s)              # 1 quando as duas estão embaixo do corpo

    # UMA PERNA DE CADA VEZ. As duas abertas ao mesmo tempo escancaram a
    # VIRILHA: as coxas giram em torno do pivô do quadril e, afastadas as
    # duas, abre-se entre elas uma faixa por onde o cenário aparece -- o
    # mesmo vão desenhado que `_fechar_vao` tapa nas juntas, aqui exposto
    # pela abertura. Com `max(0, ...)` a perna de apoio fica RETA embaixo do
    # corpo e tapa a virilha, que é também o que um passo lateral de verdade
    # faz: abre uma perna, transfere o peso, junta a outra.
    guia = max(0.0, s)                 # a perna do lado do movimento
    tras = max(0.0, -s) * 0.6          # a outra abre menos: ela só acompanha
    ab_e = amp * (guia if sentido < 0 else tras)
    ab_d = amp * (guia if sentido > 0 else tras)

    # A perna que está FECHANDO é a que sai do chão: o joelho dobra para
    # dentro e a canela vem junto com o corpo. Derivada da abertura -- se
    # ela está diminuindo, o pé está no ar.
    c = math.cos(fase)
    fecha_guia = max(0.0, -c) * max(0.0, s)
    fecha_tras = max(0.0, c) * max(0.0, -s)
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
                                 amp=min(float(a.get("amplitude", 24.0)), 30.0),
                                 sentido=sentido)
    # o fundo anda o mesmo tanto que o pé andaria: sem isto o personagem
    # patina, que é o erro clássico de walk cycle
    dx = -sentido * passada * passos * u * dur
    # `pan_camera` DIZ QUE A CÂMERA ACOMPANHA ESTE ATOR (30/08, noite), e é
    # uma informação diferente de `fundo_dx`.
    #
    # O defeito que ele conserta: até aqui só o CENÁRIO recebia o
    # deslocamento, então quem andava ficava parado na tela (certo, a câmera
    # o segue) e quem estava PARADO também ficava parado na tela (errado --
    # ele deveria ficar para trás e sair do quadro). O dono do projeto viu e
    # descreveu exatamente assim: *"o outro flutuou com o cenário mudando e
    # ele ficando no mesmo enquadramento"*.
    #
    # Com a câmera declarada, `desenhar_cena` translada cada ator por
    # `dx_camera - dx_dele`: quem anda dá zero, quem está parado anda junto
    # com o fundo. Um travelling de verdade, em vez de um fundo que desliza.
    #
    # Fica FORA de `entrar_andando`/`sair_andando` de propósito: ali a
    # câmera NÃO segue, senão quem sai de cena nunca sai do quadro.
    return {"fundo_dx": dx, "pan_camera": dx, "escala_y": esc_y}


def entrar_andando(u, rig, dur, a):
    """Entra pela borda do quadro andando até O LUGAR DELE em cena. Serve
    de gancho fraco: alguma coisa acontece já no primeiro frame.

    O DESTINO É O X DO ATOR, NÃO O CENTRO DO QUADRO (29/08). Até aqui a
    função escrevia `540` cravado nos dois extremos -- ela nasceu quando só
    existia um personagem, e para um só o lugar dele É o centro. Com dois em
    cena isso é atravessamento garantido: quem entra vai parar no meio do
    quadro, a 244px de quem já estava a 784, e as duas silhuetas se cruzam
    (o corpo de cada um ocupa ~250px de meia-largura). Foi o defeito visto
    no vídeo da rodada 3 -- o Pal entrando correndo e passando dentro do
    Zeca. `rig["quadril"][0]` já traz o x do ator, posto por
    `_rig_do_trecho`; a ação só precisa não jogá-lo fora."""
    alvo = rig["quadril"][0]
    sentido = _lado_de_entrada(a, alvo)
    cam = andar(u, rig, dur, dict(a, sentido=sentido))
    borda = -FORA_DO_QUADRO if sentido > 0 else LARG_QUADRO + FORA_DO_QUADRO
    rig["quadril"] = [borda + (alvo - borda) * _suave(u), rig["quadril"][1]]
    cam["fundo_dx"] *= 0.25          # entrando, quase todo o avanço é do corpo
    # A CÂMERA NÃO SEGUE QUEM ENTRA: ela está na cena que já existe, e quem
    # chega atravessa o quadro até o lugar dele. Seguir seria manter o
    # recém-chegado imóvel no centro e empurrar a cena inteira para o lado.
    cam.pop("pan_camera", None)
    return cam


def _lado_de_entrada(a, alvo):
    """CADA UM ENTRA E SAI PELO SEU LADO. Sem `sentido` no spec, quem fica
    à esquerda usa a borda esquerda: pelo lado oposto ele teria que
    atravessar quem já está em cena, e nenhuma guarda de colisão conserta
    isso -- a travessia seria o que o roteiro pediu."""
    padrao = 1 if alvo <= LARG_QUADRO / 2 else -1
    return 1 if a.get("sentido", padrao) >= 0 else -1


def sair_andando(u, rig, dur, a):
    """Sai DO LUGAR DELE para fora do quadro (ver `entrar_andando`)."""
    origem = rig["quadril"][0]
    # sair é o espelho de entrar: quem está à esquerda sai pela esquerda
    sentido = -_lado_de_entrada(a, origem) if "sentido" not in a \
        else (1 if a["sentido"] >= 0 else -1)
    cam = andar(u, rig, dur, dict(a, sentido=sentido))
    borda = LARG_QUADRO + FORA_DO_QUADRO if sentido > 0 else -FORA_DO_QUADRO
    rig["quadril"] = [origem + (borda - origem) * _suave(u), rig["quadril"][1]]
    cam["fundo_dx"] *= 0.25
    # A CÂMERA FICA. Se ela seguisse quem sai, o personagem nunca sairia do
    # quadro -- é a definição de "sair de cena" que se perderia.
    cam.pop("pan_camera", None)
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
    """A mão que acena, COM O COTOVELO DOBRADO e perto do corpo.

    POR QUE MUDOU (31/08, defeitos 2 e 4 dos vídeos)
        A versão anterior era `[-30, -18 + 26 sen]`: os dois ossos apontando
        para cima e para a direita, ou seja, o braço ESTICADO na diagonal.
        Duas coisas erradas saíam disso, e as duas apareceram na prévia:

          * a mão ia parar a 360px do núcleo do corpo, e num plano fechado
            (janela de 683px sobre um corpo de 332) ela não cabe. Antes, a
            guarda de enquadramento corria atrás dela e o quadro inteiro
            balançava; com a guarda mirando o núcleo (ver
            `palito_cutout.caixa_do_nucleo`), o que balançava agora corta.
            Medido: com o cotovelo dobrado a mão passa 129px do núcleo, e
            cabe nos 175px de folga do plano fechado;
          * braço esticado na diagonal, parado, não lê como aceno -- lê
            como saudação militar. O aceno acontece no ANTEBRAÇO.

        A frequência caiu de 2,2 para 1,8 Hz pelo mesmo motivo que o
        envelope existe: a 2,2 Hz o antebraço andava 15 graus por frame só
        na oscilação, e somado ao ataque estourava o teto da régua.
    """
    # O BALANÇO É DO PULSO TANTO QUANTO DO ANTEBRAÇO: com a oscilação toda
    # no antebraço, o extremo de dentro levava a mão para a frente da CARA
    # -- visto na prévia, e cara tapada é pior que gesto pequeno. Medido no
    # Pal: a mão passa 133px do núcleo do corpo no extremo de fora, contra
    # os 175px de folga que o plano fechado tem.
    bal = 12.0 * math.sin(2 * math.pi * 1.8 * u * dur)
    _braco(rig, "d", 64.0, -98.0 + bal * 0.6, bal * 2.2)
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
    virada -- o truque de cut-out para não precisar de arte de perfil.

    DUAS CORREÇÕES DE 29/08, as duas vistas na rodada 8 do ciclo, em que
    esta ação entrou num vídeo pela primeira vez:

    1. O ACHATAMENTO NÃO CHEGA A ZERO. `abs(cos(pi*k))` passa por zero no
       meio da virada, e um cut-out achatado a zero não vira: ele SOME. Na
       tela o Zeca virou um poste de uma coluna de largura. Com piso, o que
       se vê é o corpo estreitando até uma faixa e voltando pelo outro
       lado, que é o que uma figura de papel virando faz.

    2. ELA É RÁPIDA, E DEPOIS FICA. Virar-se leva meio segundo; a janela do
       roteiro pode ser de dois. Interpolando pela janela inteira, o
       personagem passa metade da fala esmagado. Agora ele vira na primeira
       METADE da janela e fica virado no resto.
    """
    k = _suave(min(1.0, u * 2.0))
    return {"espelhar": k > 0.5,
            "achatar": max(abs(math.cos(math.pi * k)), 0.34)}


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
    t = u * dur
    rig["cabeca"] = rig.get("cabeca", 0.0) + math.sin(2 * math.pi * 0.24 * t) * 0.7
    # RESPIRAÇÃO E TROCA DE APOIO (01/09, volta 57).
    #
    # A oscilação de cabeça acima é de 1980 e resolve "a imagem não está
    # congelada". Não resolve "o corpo está vivo": na folha de contato da
    # volta 57, doze quadros de dois idosos em pé, braços caídos, na mesma
    # pose. O defeito está catalogado como `E8` desde 30/08 e a explicação
    # aceita era a FORMA sorteada (uma ação por trecho). Ela é metade: a
    # outra metade é que, fora de uma ação, o corpo não faz absolutamente
    # nada -- e um corpo humano parado nunca está parado.
    #
    # São dois movimentos, os dois pequenos e os dois em frequências
    # DIFERENTES, para não baterem em fase e virarem um balanço só:
    #
    #   * RESPIRAÇÃO, ~0,22 Hz, nos OMBROS. Ela não pode ir no quadril --
    #     o quadril é a raiz e mover a raiz solta os pés do chão, que foi
    #     o defeito de 26/08 ("ele fica flutuando"). O ombro é a junta que
    #     sobe quando o peito enche, e mexê-la arrasta só o braço;
    #   * TROCA DE APOIO, ~0,09 Hz (um ciclo a cada 11 s), no TRONCO. Quem
    #     fica de pé muda o peso de perna de tempos em tempos, e é isso que
    #     separa "de pé" de "empalhado". 0,6 grau é o bastante: o corpo
    #     tem 850px de altura, então o topo da cabeça anda ~9px.
    #
    # Amplitudes escolhidas para caber MUITO abaixo do teto de `gesto.py`
    # (480 graus/s): a respiração anda 1,1 grau por ciclo de 4,5 s.
    rig["tronco"] = rig.get("tronco", -90.0) \
        + math.sin(2 * math.pi * 0.09 * t + 1.1) * 0.6
    resp = math.sin(2 * math.pi * 0.22 * t) * 0.55
    for lado in ("e", "d"):
        b = rig.get("braco_" + lado)
        if isinstance(b, list) and b:
            b[0] = b[0] + (resp if lado == "e" else -resp)
    return {}


def escutar(u, rig, dur, a):
    """O corpo de quem NÃO está falando.

    POR QUE ISTO EXISTE (01/09, volta 57)
        `gesticular` é injetado em quem FALA, e só nele. Com dois em cena
        isso quer dizer que, em todo trecho, UM dos dois atravessa a fala
        inteira com os dois braços mortos ao lado do corpo -- e, como o
        falante alterna, cada personagem passa metade do vídeo assim. Na
        tira de rostos da volta 57 dá para ver: o que escuta está sempre
        na mesma pose, do primeiro ao último quadro.

        Não é um detalhe de acabamento. Numa conversa, quem escuta é
        metade da cena, e quem escuta imóvel lê como boneco -- o que
        estraga também a atuação de quem fala, porque ele parece falar
        sozinho para um manequim.

    O QUE ELA FAZ, E POR QUE É TÃO POUCO
        Um ACENO DE CABEÇA lento, e um leve balanço do antebraço. Nada
        mais: quem escuta não pode competir com quem fala pela atenção --
        o olho vai para o que se mexe mais, e se o ouvinte gesticular
        junto a cena vira duas pessoas falando ao mesmo tempo.

        Fica na BASE da pilha, como `gesticular`: qualquer ação que o
        roteirista tenha escrito para o ouvinte ganha dela.

    A cabeça balança em torno de 0,31 Hz -- devagar o bastante para ler
    como concordância, e primo com a respiração de `parado` (0,22) para os
    dois não entrarem em fase.
    """
    f = max(0.0, min(1.5, float(a.get("forca", 1.0))))
    if f < 0.01:
        return {}
    t = u * dur
    # o aceno não é senoidal puro: um seno passa metade do tempo com a
    # cabeça para trás, o que lê como estranheza. Elevado ao quadrado com
    # sinal, ele desce rápido e volta devagar, que é como se acena.
    s = math.sin(2 * math.pi * 0.31 * t)
    rig["cabeca"] = rig.get("cabeca", 0.0) + abs(s) * s * 2.6 * f
    w = 2 * math.pi * 0.17 * t
    for lado in ("e", "d"):
        b = rig.get("braco_" + lado)
        if isinstance(b, list) and len(b) >= 2:
            b[1] = b[1] + math.sin(w + (0.0 if lado == "e" else 2.4)) * 3.2 * f
    return {}


# QUANTO O OMBRO ABRE E FECHA ENQUANTO SE FALA, em graus. Era 5, e a mão
# percorria 2,8% da altura do corpo num trecho inteiro -- gesto que não
# existe. Escolhido por medida e não por olho: ver `gesticular`, e a régua é
# o percurso da peça `mao_d` na tela.
BALANCO_OMBRO = float(os.environ.get("BALANCO_OMBRO", "13"))


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
    # CADA UM GESTICULA NO SEU RITMO (02/09, item 1 do dono do projeto:
    # *"personagens sempre acenam"*).
    #
    # Este gesto é injetado em QUEM FALA, em TODO trecho, e era idêntico
    # para todo mundo: mesma frequência, mesma fase, mesma amplitude. Com
    # dois em cena e o falante alternando, o espectador vê sempre o mesmo
    # balanço de antebraço -- e é ele, muito mais que `acenar` (4,9% das
    # ações), que lê como "eles estão sempre acenando".
    #
    # A semente vem do motor (o índice do ator em cena). Um desvio de ±18%
    # na frequência e meia volta de fase bastam: duas pessoas nunca
    # gesticulam em sincronia, e a mesma pessoa não repete o compasso do
    # trecho anterior. A amplitude do antebraço caiu de 13 para 9 graus --
    # gesto de quem conversa, não de quem sinaliza.
    sem = float(a.get("semente", 0.0))
    hz = 0.62 * (1.0 + 0.18 * math.sin(sem * 2.399))
    fase = sem * 1.7
    w = 2 * math.pi * hz * u * dur + fase     # ~0,6 gesto por segundo
    # Antebraços LEVEMENTE para dentro, subindo e descendo em contratempo.
    # A primeira versão dobrava 26 graus para dentro e as duas mãos se
    # encontravam na frente da barriga -- lido como mãos postas, ou pior,
    # como algemado. O limite é a mão não cruzar o eixo do corpo: o gesto
    # de quem conta um caso acontece na frente do PRÓPRIO ombro.
    #
    # O BALANÇO É DO OMBRO, E ELE ESTAVA EM 2,8% DA ALTURA (04/09, ciclo 25).
    #
    # As folhas de contato dos v020 a v032 mostram os dois com os braços
    # esticados ao lado do corpo em dez de cada dezesseis quadros, e a
    # objeção óbvia é a lei 40: folha de contato é imagem parada e não mostra
    # oscilação. Então a oscilação foi MEDIDA, sem render -- o percurso do
    # centro da peça `mao_d` na tela ao longo de um trecho inteiro:
    #
    #     a mao percorre  x: 32 px   y: 10 px      (2,8% da altura do corpo)
    #
    # Trinta e dois pixels num corpo de 1160. Não é a folha que engana: o
    # gesto realmente não existe.
    #
    # Como ele foi parar aí: em 02/09 a amplitude caiu de 26 para 9 graus
    # contra *"os personagens sempre acenam"*. A causa que aquele dia
    # DIAGNOSTICOU foi outra -- o gesto era idêntico para todo mundo, mesma
    # frequência e mesma fase --, e ela foi consertada pela semente. A queda
    # de amplitude veio junto, por precaução, e é ela que sobrou.
    #
    # O balanço volta pelo OMBRO e não pelo antebraço, e a diferença importa:
    # dobrar mais o antebraço leva a mão para o EIXO do corpo (as duas mãos se
    # encontrando na frente da virilha -- tentado nesta mesma sessão, e é pior
    # que o braço caído). Abrir pelo ombro leva a mão para FORA, que é para
    # onde ela vai quando alguém conta um caso, e os dois lados andam em
    # contratempo, então eles nunca se aproximam.
    _braco(rig, "e", 102.0 + BALANCO_OMBRO * f * math.sin(w),
           92.0 - 9.0 * f * (0.5 + 0.5 * math.sin(w + 0.9)),
           5.0 * f * math.sin(w + 1.6))
    _braco(rig, "d", 78.0 - BALANCO_OMBRO * f * math.sin(w + 2.3),
           88.0 + 9.0 * f * (0.5 + 0.5 * math.sin(w + 3.1)),
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


def segurar(u, rig, dur, a):
    """A mão que está com alguma coisa a LEVANTA. Não é gesto do roteiro.

    POR QUE (04/09, ciclo 25 -- folhas dos v024 e v027)
        `_objeto_na_mao` faz o que a lei 35 manda -- quem pega, segura, e o
        objeto atravessa os trechos. Só que o BRAÇO volta ao repouso quando a
        ação de pegar acaba, e repouso é o braço esticado ao lado do corpo.
        Resultado: em cinco dos dezesseis quadros do v024 e em quatro do v027 o
        celular é um retângulo escuro grudado na COXA, meio em cima da perna.
        Foi lido como *"adesivo na coxa"* pelo dono do projeto em 02/09, e a
        correção daquele dia atacou o CONTRASTE (`_destacar_objeto`) -- a
        borda ficou visível e a posição continuou a mesma.

        O contraste não era o problema inteiro: **ninguém segura um celular
        pendurado na coxa.** Quem está com uma coisa na mão a mantém na frente
        do corpo, na altura da cintura -- e é aí, na frente do tronco, que ela
        aparece inteira e não se confunde com a perna.

    E POR QUE SÓ A MÃO QUE SEGURA
        Levantar os DOIS antebraços foi tentado no mesmo dia, como conserto
        genérico de *"o personagem está parado"*, e a prévia do v022 mostrou as
        duas mãos se encontrando na frente da virilha -- as "mãos postas" que
        02/09 já tinha reprovado. Com uma mão só não há encontro, e o
        levantamento tem um motivo que se vê na tela: tem coisa nela.

    Fica na base da pilha, junto de `gesticular`: qualquer ação que o
    roteirista escreva para este braço ganha dela. `mostrar_objeto` continua
    erguendo o objeto acima da cabeça quando o roteiro pedir.
    """
    if str(a.get("mao", "d")) == "e":
        _braco(rig, "e", 112.0, 52.0, 8.0)
    else:
        _braco(rig, "d", 68.0, 128.0, -8.0)
    return {}


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
    mãos postas.

    ELES NÃO CRUZAM DE VERDADE, E NÃO TEM COMO (medido em 29/08). Para os
    antebraços se cruzarem, cada mão precisa passar do eixo do corpo para o
    lado oposto -- e com o comprimento de braço destas folhas ela não
    chega. Varridas nove combinações de ombro e antebraço nos três
    personagens: no Pal a mão direita fica 137 a 321 px À DIREITA da
    esquerda (deveria ficar à esquerda), no Zeca 90 a 260. Só na Maya, de
    braço curto e tronco estreito, o dx chega a passar de zero -- e ali as
    mãos se ENCOSTAM, que é o "nó" que a rodada 11 mostrou.

    O que a pose entrega é o antebraço horizontal à frente do peito, e isso
    lê como espera/defensiva -- um dos três sentidos da docstring, não os
    três. Cruzar de verdade pede arte: um braço desenhado por cima do
    outro, como peça. Fica anotado em vez de ajustado, porque ajustar
    ângulo aqui só move o defeito de um personagem para outro.
    """
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
    # O QUIQUE NÃO PODE SER UM CORTE (31/08). Os dois ramos não se
    # encontravam em u=0,6: o de baixo chega a 1,00 e o de cima começava em
    # 0,64, e o braço andava 46 graus num único frame -- o "teletransporta"
    # da queixa do dono do projeto, aqui dentro da própria ação e não em
    # `aplicar`. Achado pela régua nova (`ferramentas/gesto.py`), que mede
    # justamente isto. Agora o quique é uma cedida A PARTIR DO ALTO, e quem
    # desce o braço no fim é a soltura.
    k = _suave(min(1.0, u * 2.2)) if u <= 0.6 else \
        1.0 - 0.30 * _pulso((u - 0.6) / 0.4)
    rig["braco_e"] = [90.0 + 128.0 * k, 20.0 * k]
    rig["braco_d"] = [90.0 - 128.0 * k, -20.0 * k]
    rig["quadril"] = [rig["quadril"][0], rig["quadril"][1] - 26.0 * k]
    return {}


def negar(u, rig, dur, a):
    """Balança a cabeça: "não". A única negativa que uma figura frontal
    consegue fazer sem arte nova -- e ela é lida na hora."""
    rig["cabeca"] = rig.get("cabeca", 0.0) + 9.0 * math.sin(2 * math.pi * 1.4 * u * dur)
    return {}


# =====================================================================
# OBJETOS — o corpo que interage com uma coisa, não só com o ar
# =====================================================================
# O motor já sabia grudar um PNG na mão (`objeto` na ação, ver
# `_pivo_de_pega`), e mesmo assim nenhum vídeo teve objeto: faltava o
# GESTO. Uma xícara colada numa mão que gesticula lê como erro de colagem;
# o que faz o objeto existir é o braço se comportar como se ele pesasse --
# descer para pegar, subir para mostrar, esticar para entregar.
#
# Todas as ações daqui aceitam `objeto` (o nome da arte no spec) e `mao`
# ("d" por padrão). A partir do instante em que uma delas começa, o objeto
# FICA na mão do personagem até `largar_objeto` -- inclusive atravessando
# trechos. Antes, ele só aparecia dentro da janela `de..ate` da ação que o
# citava, e o roteirista tinha que repetir `objeto` em toda ação seguinte
# para o celular não sumir da mão no meio da fala.
def pegar_objeto(u, rig, dur, a):
    """Desce a mão, pega e traz o objeto para a altura do peito.

    A descida importa: sem ela o objeto simplesmente aparece na mão, e
    aparecer é o que faz o público ler colagem em vez de ação."""
    lado = a.get("mao", "d")
    desce = _suave(min(1.0, u * 2.2))
    sobe = _suave(max(0.0, (u - 0.45) / 0.55))
    # desce até junto do quadril, depois recolhe à frente do peito.
    #
    # PEITO BAIXO, NÃO PEITO ALTO (29/08). Os números antigos (ombro 66,
    # antebraço 168) punham a mão à altura do esterno, e isso está certo
    # para uma chave -- mas a caixa de papelão, a sacola e o guarda-chuva
    # ocupam 25 a 40% da altura do ator, então o objeto subia junto e
    # encostava no queixo. Medido em `ferramentas/objeto.py`: os três
    # grandes tapavam o rosto em `pegar_objeto`, e nenhum dos sete
    # pequenos. Descer o alvo resolve para os dez de uma vez, e não muda
    # nada visível nos pequenos.
    ombro = 92.0 - 14.0 * sobe
    ante = 96.0 * (1.0 - sobe) + (148.0 if lado == "d" else 32.0) * sobe
    _braco(rig, lado, ombro if lado == "d" else 180.0 - ombro,
           ante if lado == "d" else 180.0 - ante, 0.0, max(desce, sobe))
    rig["tronco"] = -90.0 + 4.0 * desce * (1.0 - sobe)
    return {}


def mostrar_objeto(u, rig, dur, a):
    """Ergue o objeto à frente, na altura do rosto: "olha ISSO".

    É o gesto de prova -- o que transforma um objeto de cena em argumento
    da piada."""
    lado = a.get("mao", "d")
    k = _suave(min(1.0, u * 2.4))
    alt = float(a.get("altura", 34.0))    # quanto acima da horizontal
    if lado == "d":
        _braco(rig, "d", -alt, -alt - 30.0, -8.0, k)
    else:
        _braco(rig, "e", 180.0 + alt, 210.0 + alt, 8.0, k)
    rig["tronco"] = -90.0 - 1.5 * k
    return {}


def usar_objeto(u, rig, dur, a):
    """As duas mãos à frente do peito, cabeça baixa: mexendo no celular,
    lendo, contando dinheiro. O personagem some do mundo, que é a piada.

    OS COTOVELOS FICAM JUNTO AO CORPO (29/08). Os ângulos antigos (braço
    superior a 34 graus) erguiam o braço para CIMA e para fora: na tela os
    dois braços abriam num V e o personagem parecia estar se rendendo, não
    olhando uma tela. Quem mexe no celular encolhe os cotovelos contra as
    costelas e traz as mãos para a frente do esterno -- é uma pose fechada,
    e é isso que lê como "sumiu do mundo". Visto na rodada 9 do ciclo.

    74/130 saiu de uma VARREDURA, não do olho: fechar mais que isso põe a
    mão atrás do tronco e o objeto some -- medido, 22% de visível com
    80/152, contra 96% aqui. O cotovelo continua colado nas costelas.
    """
    k = _suave(min(1.0, u * 2.2))
    _braco(rig, "d", 74.0, 130.0, -8.0, k)
    _braco(rig, "e", 106.0, 50.0, 8.0, k * 0.85)
    rig["cabeca"] = rig.get("cabeca", 0.0) + 5.0 * k
    rig["tronco"] = -90.0 + 3.0 * k
    return {}


def entregar_objeto(u, rig, dur, a):
    """Estica o braço para o outro ator, oferecendo o objeto.

    `sentido` diz para que lado ele estende (-1 esquerda, 1 direita); o
    padrão é para o lado da mão que segura."""
    lado = a.get("mao", "d")
    sentido = float(a.get("sentido", 1.0 if lado == "d" else -1.0))
    k = _suave(min(1.0, u * 2.0))
    alt = 8.0
    if sentido >= 0:
        _braco(rig, "d", alt, alt - 6.0, -4.0, k)
    else:
        _braco(rig, "e", 180.0 - alt, 186.0 - alt, 4.0, k)
    rig["tronco"] = -90.0 - 2.0 * k
    return {}


def largar_objeto(u, rig, dur, a):
    """Abaixa o braço e SOLTA: daqui em diante a mão volta a estar vazia.

    Existe para fechar o estado que `pegar_objeto` abre. Sem uma ação de
    largar, o objeto acompanharia o personagem até o fim do vídeo -- e o
    celular ficaria na mão dele durante a queda."""
    lado = a.get("mao", "d")
    k = _suave(min(1.0, u * 2.6))
    _braco(rig, lado, 92.0 if lado == "d" else 88.0,
           94.0 if lado == "d" else 86.0, 0.0, k)
    return {}


# =====================================================================
# INTERAÇÃO — as ações que envolvem O OUTRO PERSONAGEM
# =====================================================================
# POR QUE ESTA FAMÍLIA EXISTE (02/09, item 1 do dono do projeto:
# *"personagens sempre acenam, a movimentação está fechada; o certo seria
# alterar conforme o roteiro... faça vários tipos: pulo, andar, acenar,
# high five, falar, usar objeto, bater no outro personagem"*).
#
# Medido nos 59 specs já produzidos: o catálogo É usado, e com variedade --
# 24 ações diferentes, 2,33 por trecho, nenhum trecho vazio. O que a medida
# mostrou é outra coisa, e explica a queixa melhor que "o catálogo é
# pequeno":
#
#     das 1361 ações, ~60% são POSE DE BRAÇO de um personagem sozinho
#     (apontar 17,6%, mostrar_objeto 11,5%, encolher_ombros 8,6%,
#      maos_na_cabeca 6,9%, maos_na_cintura 5,6%, cocar_cabeca 5,2%,
#      acenar 4,9%, negar 3,7%, ...)
#
# e, sobretudo: **NENHUMA ação do catálogo tocava no outro personagem.**
# `entregar_objeto` era a única que sequer o alcançava, e ela nunca foi
# usada em 59 vídeos. Duas pessoas dividem o quadro e gesticulam cada uma
# para o nada -- é isso que lê como "sempre acenam", mesmo com o vocabulário
# variando.
#
# COMO ELAS SABEM ONDE ESTÁ O OUTRO
# O roteirista não sabe de que lado cada um está -- e não deve saber, é
# divisão de quadro, não encenação (é a mesma razão de `mao_de_fora`). O
# motor injeta `lado_alvo` (+1 se o outro está à direita, -1 se à esquerda)
# uma vez por trecho, e as ações abaixo se escrevem em função dele.
ACOES_DE_INTERACAO = ("high_five", "cutucar", "empurrar", "bater_no_outro",
                      "apertar_mao")


def _para_o_outro(ang, lado):
    """Espelha um ângulo de tela quando o outro está à esquerda.

    Os ângulos das poses abaixo são escritos como se o parceiro estivesse à
    DIREITA (0 = direita, -90 = cima). Refletir no eixo vertical é
    `180 - ang`, e é isso que faz a mesma pose servir dos dois lados sem
    ninguém escrever duas versões."""
    return ang if lado >= 0 else 180.0 - ang


def _lado_e_mao(a):
    """(+1/-1, 'd'/'e') -- para que lado está o outro, e que braço usar.

    Sem `lado_alvo` a ação ainda funciona: ela assume o parceiro à direita,
    que é o que acontece num monólogo (ninguém para alcançar) e não quebra
    nada. Quem injeta o valor de verdade é o motor."""
    lado = 1.0 if float(a.get("lado_alvo", 1)) >= 0 else -1.0
    return lado, ("d" if lado > 0 else "e")


def high_five(u, rig, dur, a):
    """Bate na mão do outro, no alto.

    A mão sobe acima da cabeça e vai ao ENCONTRO do parceiro -- é o único
    gesto do catálogo em que os dois corpos se apontam. Vai e volta
    (`_pulso`), porque high five não é uma pose: é um impacto.

    O braço que sobe é o de DENTRO, ao contrário de tudo o mais aqui: para
    as duas mãos se encontrarem no meio do quadro, cada um tem de erguer o
    braço voltado para o outro. É a exceção que confirma `mao_de_fora` --
    lá o objeto tem de ficar longe do parceiro, aqui ele É o parceiro.
    """
    lado, mao = _lado_e_mao(a)
    p = _pulso(u)
    # -58 é a diagonal para cima e para o lado do outro; o antebraço sobe
    # mais que o ombro, senão a mão fica na altura do peito e o gesto lê
    # como cumprimento, não como high five.
    _braco(rig, mao, _para_o_outro(-42.0, lado), _para_o_outro(-72.0, lado),
           0.0, _suave(min(1.0, u * 2.2)))
    # o corpo acompanha um pouco: um high five move o tronco
    rig["tronco"] = rig.get("tronco", -90.0) + lado * 4.0 * p
    return {"zoom": 1.0 + 0.03 * p}


def bater_no_outro(u, rig, dur, a):
    """Um tapa no ombro do outro -- de leve, duas vezes.

    É a ação que o dono do projeto pediu por último e a que mais muda a
    leitura da cena: dois personagens que se TOCAM param de parecer dois
    monólogos lado a lado. De leve de propósito: o humor da casa é o do
    sujeito que se ferra sozinho (lei 30), e violência de verdade troca o
    alvo da piada.

    O braço sobe e desce num arco em direção ao parceiro, duas vezes na
    janela -- um tapa só se perde numa amostra e lê como braço solto.
    """
    lado, mao = _lado_e_mao(a)
    fase = math.sin(2 * math.pi * (u * 2.0) - math.pi / 2) * 0.5 + 0.5
    sup = -34.0 + 62.0 * fase          # de erguido a horizontal
    _braco(rig, mao, _para_o_outro(sup, lado),
           _para_o_outro(sup + 16.0, lado), 0.0,
           _suave(min(1.0, u * 3.0)))
    return {"tremor": 0.4 * _pulso(u)}


def cutucar(u, rig, dur, a):
    """Cutuca o outro com o dedo, duas vezes.

    O braço fica horizontal na direção do parceiro e o antebraço avança e
    volta. É o gesto de quem cobra -- e ele existe porque `apontar` (17,6%
    das ações de todo o canal) aponta para o NADA: aqui o alvo é uma
    pessoa, e o corpo diz isso."""
    lado, mao = _lado_e_mao(a)
    jab = math.sin(2 * math.pi * (u * 2.0)) * 0.5 + 0.5
    _braco(rig, mao, _para_o_outro(8.0, lado),
           _para_o_outro(-6.0 - 14.0 * jab, lado), 0.0,
           _suave(min(1.0, u * 3.0)))
    rig["tronco"] = rig.get("tronco", -90.0) + lado * 2.5 * jab
    return {}


def empurrar(u, rig, dur, a):
    """Empurra o outro com as duas mãos.

    Os dois braços vão para a frente na direção do parceiro e o tronco se
    inclina junto -- empurrar com o braço e o corpo parado lê como quem
    apresenta um produto. `_pulso` porque o empurrão tem impacto e recuo."""
    lado, _mao = _lado_e_mao(a)
    p = _pulso(u)
    k = _suave(min(1.0, u * 2.4))
    for m, base in (("d", 12.0), ("e", -6.0)):
        _braco(rig, m, _para_o_outro(base, lado),
               _para_o_outro(base - 8.0 - 10.0 * p, lado), 0.0, k)
    rig["tronco"] = rig.get("tronco", -90.0) + lado * 7.0 * p
    return {"tremor": 0.6 * p, "zoom": 1.0 + 0.02 * p}


def apertar_mao(u, rig, dur, a):
    """Aperta a mão do outro: braço na direção dele, na altura da cintura,
    subindo e descendo devagar.

    É o gesto de acordo -- e num canal em que quase toda esquete termina em
    alguém sendo passado para trás, ele serve de ironia física."""
    lado, mao = _lado_e_mao(a)
    bal = math.sin(2 * math.pi * (u * 1.6)) * 6.0
    _braco(rig, mao, _para_o_outro(38.0 + bal, lado),
           _para_o_outro(14.0 + bal, lado), 0.0,
           _suave(min(1.0, u * 2.4)))
    return {}


# quais ações põem e quais tiram o objeto da mão. O motor lê esta lista,
# não o nome da ação, para não espalhar string mágica pelo render.
ACOES_PEGAM_OBJETO = ("pegar_objeto", "mostrar_objeto", "usar_objeto",
                      "entregar_objeto")
ACOES_LARGAM_OBJETO = ("largar_objeto",)
# QUEM SEGURA, SEGURA COM A MÃO DE FORA. `entregar_objeto` fica de fora
# desta lista de propósito: ela existe para esticar o braço ATÉ o outro.
ACOES_OBJETO_MAO_DE_FORA = ("pegar_objeto", "mostrar_objeto", "usar_objeto")


def mao_de_fora(x):
    """A mão que ergue o objeto, para quem está no x `x` do quadro.

    POR QUE (31/08, volta 9 do ciclo de vídeo)
        No v009 o Pal está à ESQUERDA e segura a caixa de papelão com a mão
        `d`, que é a que `mostrar_objeto` ergue para cima e para a DIREITA
        (0 é direita, -90 é cima). O braço dele atravessou o meio do quadro
        e a caixa foi parar **em cima da cara da Vovó**, no último plano do
        vídeo -- que é o close da tirada, onde a piada acontece.

        O roteirista escreve `mao` sem saber quem está de que lado: no mesmo
        spec ele pediu `d`, depois `e`, depois `d`, e nada disso é escolha
        de encenação. Quem sabe o lado é o motor, e é ele quem decide --
        prompt é pedido, código é garantia (lei 16).

        É a mesma regra de `_lado_de_entrada`, na mão em vez do pé: quem
        está à esquerda usa a mão de fora, porque pelo lado de dentro o
        gesto atravessa quem divide a cena. E ela vale para o vídeo inteiro,
        não só durante o gesto: a mão que pega é a mão que continua
        segurando, então o objeto passa a viver do lado de fora.
    """
    return "e" if float(x) <= LARG_QUADRO / 2 else "d"
# ENTREGAR É PASSAR, NÃO COPIAR (29/08). `entregar_objeto` estica o braço
# oferecendo a coisa, e por isso ela precisa estar na mão DURANTE a ação --
# mas ao fim dela a mão fica vazia, senão o objeto se duplica. Foi o que a
# rodada 6 do ciclo mostrou: o Zeca entrega a marmita ao Pal no terceiro
# trecho e no quarto os DOIS aparecem segurando uma. Larga no fim, não no
# começo, e por isso a ação está numa lista só dela.
ACOES_ENTREGAM_OBJETO = ("entregar_objeto",)


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
    # Injetada pelo MOTOR quando a mão está com alguma coisa, nunca pelo
    # roteirista -- ele já diz `objeto` na ação de pegar, e quem sabe que a
    # coisa continua lá é `_objeto_na_mao`. Ver `segurar`.
    "segurar": segurar,
    "parado": parado,
    "gesticular": gesticular,
    "escutar": escutar,
    # as que tocam no OUTRO personagem (02/09, item 1)
    "high_five": high_five,
    "bater_no_outro": bater_no_outro,
    "cutucar": cutucar,
    "empurrar": empurrar,
    "apertar_mao": apertar_mao,
    "pegar_objeto": pegar_objeto,
    "mostrar_objeto": mostrar_objeto,
    "usar_objeto": usar_objeto,
    "entregar_objeto": entregar_objeto,
    "largar_objeto": largar_objeto,
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
# POSTURA É ESTADO, GESTO É EVENTO (29/08)
#
# Um gesto vai e volta: acenar, encolher os ombros, levar um susto, coçar a
# cabeça. Uma POSTURA o corpo assume e mantém: mão na cintura, braços
# cruzados, mão no queixo, mãos na cabeça, e -- literalmente -- estar caído
# no chão.
#
# Até 29/08 as duas eram tratadas igual: fora da janela `de/ate`, a ação
# simplesmente não era aplicada e o corpo voltava ao repouso no frame
# seguinte. O efeito na tela é o defeito que sobreviveu a todas as sessões
# de "movimento": o roteiro pede duas ações por trecho, elas acontecem, e
# mesmo assim o vídeo é de dois bonecos parados de braços caídos -- porque
# cada pose dura o pedaço da fala que a janela cobre e o resto do trecho é
# repouso. Numa fala de 5 s, `maos_na_cintura` de 0 a 0,45 aparece por
# UM segundo.
#
# É a mesma lição que o objeto já tinha ensinado (`_objeto_na_mao`): quem
# pega, segura. Aqui, quem cruza os braços continua de braços cruzados até
# fazer outra coisa. `cair` é o caso que denuncia sozinho -- a docstring
# dele diz "termina deitado, não volta", e fora da janela ele levantava.
ACOES_QUE_FICAM = frozenset((
    "maos_na_cintura", "bracos_cruzados", "mao_no_queixo", "maos_na_cabeca",
    "apontar", "apresentar", "cair",
))

# E O QUE FICA NEM SEMPRE FICA INTEIRO (04/09, ciclo 25).
#
# `apontar` está aqui em cima porque largá-lo ao fim da janela devolvia o braço
# ao repouso no meio da fala, e isso é o boneco parado. Só que congelar a pose
# a 100% tem o defeito oposto, e a prova do gancho do v028 o mostra inteiro: o
# roteiro pede `apontar` de 0,2 a 0,4 e **o braço fica esticado na horizontal
# pelos 2,4 s seguintes, cortado pela borda do quadro**, em oito dos doze
# quadros dos três segundos que decidem a distribuição do vídeo.
#
# Ninguém aponta e fica apontando. Aponta-se, e a mão DESCE um pouco e fica
# no ar -- é o *settle* dos doze princípios, o mesmo que a lei 76 já aplica ao
# ataque do gesto, agora aplicado à saída dele. A pose assentada continua bem
# acima do repouso (o braço não morre ao lado do corpo) e não alcança mais a
# borda do quadro.
#
# Só os dois GESTOS da lista assentam. `maos_na_cintura`, `bracos_cruzados`,
# `mao_no_queixo` e `maos_na_cabeca` são POSTURAS pela lei 35 -- o corpo as
# assume e as mantém, e assentá-las seria desfazer o que a lei 35 conserta.
# `cair` fica inteira pelo motivo óbvio: quem caiu está no chão.
ASSENTA_EM = {"apontar": 0.5, "apresentar": 0.55}

# Em quanto tempo a pose assenta, depois que a janela da ação fecha.
TEMPO_DE_ASSENTAR_S = 0.7


def _percurso(antes, rig):
    """Quantos graus o osso que mais andou andou, entre dois rigs.

    O quadril fica de fora: ele é medido em pixels e quem o move é
    locomoção, que não passa pelo envelope."""
    pior = 0.0
    for osso, v in rig.items():
        if osso == "quadril":
            continue
        v0 = antes.get(osso)
        if v0 is None:
            continue
        if isinstance(v, list) and isinstance(v0, list):
            n = min(len(v), len(v0))
            pior = max([pior] + [abs(v[i] - v0[i]) for i in range(n)])
        elif isinstance(v, (int, float)) and isinstance(v0, (int, float)):
            pior = max(pior, abs(v - v0))
    return pior


def _pesar(rig, antes, k, exceto=None):
    """Mistura o rig com o de ANTES da ação: k=1 é a ação inteira, k=0 é
    como se ela não tivesse acontecido.

    É o que dá ao gesto um começo e um fim em vez de dois saltos. Mistura
    osso a osso e só o que existe nos dois lados -- ação que criou um osso
    novo (o `sobrancelha` do susto) entra inteira, porque não há de onde
    interpolar.

    OS BRAÇOS TÊM DOIS OU TRÊS NÚMEROS, e a primeira versão desta função
    exigia o mesmo comprimento nos dois lados: o repouso traz
    `[ombro, cotovelo]` e toda pose escrita com `_braco` traz
    `[ombro, cotovelo, pulso]`. Com a igualdade exigida, NENHUM braço era
    misturado -- a soltura existia e não fazia nada, e o salto continuava
    inteiro. Falta de pulso é pulso zero, que é a mesma convenção de
    `_braco`; os dois lados são completados com zero antes da conta."""
    if k >= 0.999:
        return
    k = max(0.0, k)
    for osso, v in list(rig.items()):
        v0 = antes.get(osso)
        if v0 is None or osso in (exceto or ()):
            continue
        if isinstance(v, list) and isinstance(v0, list):
            n = max(len(v), len(v0))
            a = (list(v0) + [0.0] * n)[:n]
            b = (list(v) + [0.0] * n)[:n]
            rig[osso] = [x + (y - x) * k for x, y in zip(a, b)]
        elif isinstance(v, (int, float)) and isinstance(v0, (int, float)):
            rig[osso] = v0 + (v - v0) * k


def aplicar(acoes, t_rel, rig, dur_trecho):
    """Aplica, em ordem, todas as ações cuja janela contém t_rel (0..1) --
    e mantém a pose final das que são POSTURA e já terminaram.

    Ordem = precedência: quem vem depois escreve por cima. É como "andar
    apontando" funciona -- `andar` mexe nos dois braços, `apontar` vem
    depois e sobrescreve um deles. É também o que faz uma postura que ficou
    ceder para a ação seguinte, sem regra nenhuma a mais.

    A PRECEDÊNCIA É CRONOLÓGICA, NÃO A DA LISTA (31/08). Quem COMEÇOU
    depois escreve por cima, e a ordem da lista só desempata quem começa no
    mesmo instante. Três razões, e a terceira é um defeito de verdade:

      * a lista do roteirista não vem em ordem cronológica -- no v023 um
        trecho traz `maos_na_cabeca` 0,6-1 antes de `maos_na_cintura`
        0,05-0,32 --, e com a ordem da lista a pose velha ganhava da nova;
      * `parado` e `gesticular` são injetados pelo motor com `de: 0`, então
        eles continuam sendo a base da pilha de graça;
      * com a ordem da lista, o VENCEDOR TROCAVA no instante em que uma
        ação terminava: enquanto as duas estavam ativas mandava a de baixo
        da lista, e quando ela virava "postura que ficou" a de cima
        reassumia o braço -- um salto de 55 graus num frame, no meio da
        fala. Ordenado pelo começo, nada troca de dono com o tempo.
    """
    cam = dict(CAM_NEUTRA)
    pilha = []                              # (ordem, aplicação)
    # SOLTURA E ATAQUE CORREM JUNTOS quando um gesto emenda no outro, e as
    # duas rampas se somam -- o braço volta ao repouso em três frames em vez
    # de sete. Tentei cortar a soltura de quem já tem sucessor e o resultado
    # foi pior: o ataque do sucessor mistura A PARTIR do rig de agora, e sem
    # a pose do antecessor nele o primeiro frame do sucessor vira o salto
    # inteiro de volta. As duas rampas ficam; três frames de emenda é
    # movimento desenhado, não corte (ver o teto de `ferramentas/gesto.py`).
    for i_a, a in enumerate(acoes or []):
        nome = a.get("nome")
        f = CATALOGO.get(nome)
        if f is None:
            continue
        de = float(a.get("de", 0.0))
        ate = float(a.get("ate", 1.0))
        if ate <= de:
            continue
        env = nome not in SEM_ENVELOPE
        so_membros = nome in SO_MEMBROS
        if t_rel < de:
            # A ENTRADA COMEÇA FORA DO QUADRO (31/08, defeito 5 dos vídeos).
            #
            # Enquanto a janela não chega, a ação não é aplicada e o ator
            # fica no `x` de destino -- ou seja, DENTRO da cena, no lugar
            # exato onde ele vai parar. Aí a janela abre, ele salta para a
            # borda e entra andando: *"ele dá um teleporte para o local que
            # ele vai estar quando terminar de entrar"*, com o salto visto
            # do outro lado. Quem ainda vai entrar tem de estar FORA, e é o
            # que o próprio u=0 da ação faz.
            if nome in ACOES_DE_ENTRADA:
                f(0.0, rig, dur_trecho * (ate - de), a)
            continue
        if t_rel > ate:
            # QUEM SAIU CONTINUA FORA. `sair_andando` termina com o corpo
            # na borda de fora, e largá-la ao fim da janela devolvia o ator
            # ao lugar dele no frame seguinte -- 880px num frame, o
            # teletransporte do defeito 5 pelo avesso. Ela fica pelo mesmo
            # motivo que uma postura fica: onde o corpo ESTÁ é estado.
            fica = nome in ACOES_QUE_FICAM or nome in ACOES_DE_SAIDA
            sobra = (t_rel - ate) * dur_trecho
            if not fica and (not env or sobra >= SOLTURA_MAX):
                continue
            u, decorrido, passou = 1.0, sobra, True
            env = env and not fica
        else:
            u = (t_rel - de) / (ate - de)
            decorrido, passou = (t_rel - de) * dur_trecho, False
        pilha.append(((de, i_a),
                      (f, u, env, so_membros, decorrido, de, ate, a, passou,
                       nome)))

    for _o, (f, u, env, so_membros, decorrido, de, ate, a, passou,
             nome) in sorted(pilha, key=lambda p: p[0]):
        # O GESTO QUE FICA ASSENTA (04/09). Ver `ASSENTA_EM`: `apontar` e
        # `apresentar` continuam valendo depois da janela, mas a meio caminho
        # do repouso, e não congelados no extremo -- ninguém aponta e fica
        # apontando com o braço esticado pelos dois segundos seguintes.
        assenta = ASSENTA_EM.get(nome) if passou else None
        antes = None
        if env or assenta is not None:
            antes = {o: (list(v) if isinstance(v, list) else v)
                     for o, v in rig.items()}
        d = f(u, rig, dur_trecho * (ate - de), a) or {}
        if assenta is not None:
            k = assenta + (1.0 - assenta) * (
                1.0 - _suave(min(1.0, decorrido / TEMPO_DE_ASSENTAR_S)))
            _pesar(rig, antes, k,
                   exceto=("quadril",) if so_membros else None)
            continue
        if antes is not None:
            # A JANELA DO ENVELOPE SAI DO PERCURSO, não de uma constante:
            # o braço tem uma velocidade máxima, e o tempo que ele leva
            # depende de quanto ele tem de andar. Fixo em 0,28 s, uma troca
            # de pose de 173 graus (largar o objeto e cruzar os braços, no
            # v020) ainda dava 52 graus por frame; medido em velocidade, ela
            # leva 0,36 s e nada mais estoura o teto da régua.
            janela = _percurso(antes, rig) / VEL_MAX_GS
            if passou:
                janela = min(SOLTURA_MAX, max(SOLTURA_MIN, janela * 1.2))
                peso = 1.0 - _suave(min(1.0, decorrido / janela))
            else:
                janela = min(ATAQUE_MAX, max(ATAQUE_MIN, janela))
                peso = _ataque(min(1.0, decorrido / janela))
            _pesar(rig, antes, peso,
                   exceto=("quadril",) if so_membros else None)
        if passou:
            # a POSE fica; o que a ação pediu de CÂMERA, não. Zoom e
            # deslocamento de fundo são do instante em que a coisa
            # aconteceu -- congelar o zoom de um susto pelo resto do
            # trecho seria a câmera parada em cima do nada.
            continue
        for k, v in d.items():
            # deslocamento de fundo é cumulativo; o resto, o último manda.
            # `pan_camera` acompanha `fundo_dx` porque é a mesma grandeza
            # vista de outro lugar -- somar um e sobrescrever o outro faria
            # a câmera discordar do chão em qualquer trecho com duas ações
            # de locomoção.
            cam[k] = (cam.get(k, 0.0) + v
                      if k in ("fundo_dx", "pan_camera") else v)
    return cam


def garantir_gancho(spec):
    """Nenhum vídeo abre sem gatilho. Se o roteirista não pôs uma ação
    forte nos 2 primeiros segundos do primeiro trecho, o motor injeta uma.

    Isto é de propósito uma rede de segurança no MOTOR e não só uma
    instrução no prompt: prompt o modelo desobedece, motor não.

    MAS ELA OBEDECE À FORMA (29/08). `gancho_forte: false` no spec desliga
    a injeção. Um episódio escrito para ser parado -- em que o gancho está
    na FRASE e não no corpo -- abria com a personagem levando um susto que
    nada na cena justifica: exatamente o defeito que a lei 34 descreve, o
    código desmentindo o pedido, e o código ganhando. Quem escreve o spec
    diz o que quer; a rede de segurança vale para quem não disse nada.
    """
    trechos = spec.get("trechos") or []
    if not trechos:
        return spec
    if spec.get("gancho_forte") is False:
        print("[acoes] spec pede abertura sem susto; gancho automatico "
              "desligado")
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
