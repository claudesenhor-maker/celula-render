# -*- coding: utf-8 -*-
"""efeitos.py -- as gags de desenho animado: explodir, voar, perder um braco.

    Pedido do dono (10/09): *"criar efeitos especiais no video, personagem
    explodir, voar, cair, perder um braco, coisas nesse sentido. A ideia nao e
    usar sempre, e sim TER A POSSIBILIDADE de usar"*.

POR QUE ISTO CABE NESTE MOTOR, E CABE BARATO
    O cut-out ja desenha o corpo como PECAS SOLTAS presas por uma arvore de
    pivos -- e' assim que o braco levanta e a cabeca inclina. Explodir um
    personagem, num motor desses, nao e' um efeito novo: e' a mesma colagem
    com um deslocamento a mais por peca. Nada aqui gera pixel novo, nada
    baixa asset, nada custa render extra alem do que ja se gasta.

    Por isso o modulo e' pequeno e nao tem nenhum desenho dentro: ele so
    responde ONDE cada peca vai parar, e quem cola continua sendo o
    `desenhar_personagem`.

A REGRA DE OURO: E' TUDO FUNCAO DE `p`
    Cada efeito recebe o progresso `p` (0 no comeco, 1 no fim) e devolve, por
    peca, um deslocamento, um giro e uma opacidade. Nao ha estado guardado
    entre quadros.

    Isso nao e' preciosismo: um efeito com memoria daria imagem diferente se
    um quadro fosse recalculado, e o render deste projeto ja teve um defeito
    dessa familia (a mistura da trilha mudando a cada render por causa de
    normalizacao dependente de sobreposicao). Sem estado, o quadro 137 e'
    sempre o mesmo quadro 137.

O VAO ENTRE AS PECAS CONTINUA SENDO O ESTILO
    `_fechar_vaos_do_corpo` roda no corpo montado, DEPOIS das pecas e ANTES do
    objeto. Um corpo explodido nao tem junta para fechar, e tentar fechar
    juntaria pecas que deveriam estar voando. Por isso `desenhar_personagem`
    pula o fechamento quando ha efeito em curso -- e so entao, para que o
    vao normal, que e' assinatura do canal (GUIA §0.5), nunca mude.

QUEM DECIDE QUE UM VIDEO TEM EFEITO
    Nao e' este arquivo, e nao e' o modelo sozinho. O roteirista so pode pedir
    efeito quando a volta permite (rodizio), e no maximo UM por esquete --
    *"a ideia nao e usar sempre"*. Ver `roteirista2.js`, `efeitoPermitido`.
"""
import math

# =====================================================================
# O CATALOGO
# =====================================================================
# Cada efeito tem uma DURACAO TIPICA em segundos, e ela existe porque a gag
# tem tempo proprio: uma explosao que dura quatro segundos deixa de ser
# explosao e vira uma peca boiando. Quem monta o spec usa este numero quando
# o roteiro nao disser outro.
#
# `destrutivo` marca o que desmonta o corpo. Ele importa por uma razao
# pratica: efeito destrutivo tem de ser o ULTIMO gesto do trecho, senao o
# personagem continua gesticulando com um braco que ja caiu no chao.
EFEITOS = {
    "explodir":      {"dur": 1.1, "destrutivo": True},
    "voar":          {"dur": 1.4, "destrutivo": False},
    "perder_braco":  {"dur": 1.2, "destrutivo": True},
    "derreter":      {"dur": 1.6, "destrutivo": True},
}
NOMES = tuple(EFEITOS)

# As pecas de cada braco, na ordem em que se soltam do corpo.
BRACO = {"d": ("braco_sup_d", "braco_inf_d", "mao_d"),
         "e": ("braco_sup_e", "braco_inf_e", "mao_e")}


def _semente(nome):
    """Um numero estavel por peca, entre 0 e 1.

    Serve para que as pecas nao saiam todas igual na explosao -- e para que
    saiam SEMPRE do mesmo jeito. `hash()` do Python nao serve: ele e'
    aleatorizado por processo desde a 3.3, entao o mesmo quadro sairia
    diferente entre dois renders, que e' exatamente o que a nota do topo diz
    que nao pode acontecer.
    """
    h = 2166136261
    for ch in nome:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return (h % 1000) / 1000.0


def duracao(nome):
    return float((EFEITOS.get(nome) or {}).get("dur") or 1.2)


def destrutivo(nome):
    return bool((EFEITOS.get(nome) or {}).get("destrutivo"))


def existe(nome):
    return str(nome or "").strip().lower() in EFEITOS


# =====================================================================
# A CONTA
# =====================================================================
def aplicar(nome, p, pos, ang, quadril, altura, lado="d"):
    """Onde cada peca fica, no instante `p` do efeito `nome`.

    `pos` e `ang` sao os que a pose normal produziu -- ou seja, o efeito
    monta EM CIMA da atuacao, e nao no lugar dela. A peca continua na pose
    que o roteiro pediu enquanto voa.

    `quadril` e' o ponto de origem (o centro do corpo) e `altura` a altura do
    ator em pixels de tela: as duas coisas que dao ESCALA ao efeito. Sem elas
    a explosao seria calibrada em pixels e um personagem baixo espalharia
    pecas ate a borda enquanto um alto mal se mexeria (e' a lei 38 -- medir no
    corpo, e nao numa constante).

    Devolve `(novo_pos, novo_ang, alfa)`. `alfa` e' do corpo INTEIRO: nenhum
    efeito daqui apaga uma peca sozinha, e essa e a razao de ele ser um numero
    so em vez de um por peca.
    """
    nome = str(nome or "").strip().lower()
    p = max(0.0, min(1.0, float(p)))
    if nome not in EFEITOS or p <= 0.0:
        return pos, ang, 1.0
    return _CONTA[nome](p, pos, ang, quadril, altura, lado)


def _explodir(p, pos, ang, quadril, altura, lado):
    """As pecas saem do quadril para fora, girando, e caem.

    A DIRECAO DE CADA PECA E' A DELA MESMA -- do quadril ate onde ela ja
    estava. Assim a cabeca sobe, os pes descem e os bracos abrem, que e' a
    silhueta que se le como explosao. Sortear a direcao daria uma nuvem sem
    forma, e o olho perderia de quem era o corpo.

    A GRAVIDADE ENTRA DEPOIS DA FORCA: `p*p` no arremesso e `p*p*p` na queda.
    Sem a queda o boneco vira confete subindo; com ela, a explosao tem peso, e
    peso e' o que faz uma gag de desenho ler como fisica de desenho.
    """
    novo_pos, novo_ang = {}, {}
    forca = altura * 1.25
    for k, (x, y) in pos.items():
        s = _semente(k)
        dx, dy = x - quadril[0], y - quadril[1]
        d = math.hypot(dx, dy) or 1.0
        # Peca colada no quadril nao tem direcao propria: manda para cima, que
        # e' de onde a explosao empurra o que esta no centro.
        if d < altura * 0.05:
            dx, dy, d = 0.0, -1.0, 1.0
        ux, uy = dx / d, dy / d
        # de 0,7 a 1,3 da forca: as pecas nao chegam juntas, e chegar junto e'
        # o que faz uma explosao parecer um zoom.
        k_forca = forca * (0.7 + 0.6 * s)
        arremesso = p * p
        queda = altura * 1.1 * (p ** 3)
        novo_pos[k] = (x + ux * k_forca * arremesso,
                       y + uy * k_forca * arremesso + queda)
        novo_ang[k] = ang.get(k, 0.0) + (720.0 * (s - 0.5)) * p
    # some no fim, e nao no comeco: o desaparecimento e' o que evita a peca
    # parada na borda quando o trecho seguinte comeca.
    alfa = 1.0 if p < 0.65 else max(0.0, 1.0 - (p - 0.65) / 0.35)
    return novo_pos, novo_ang, alfa


def _voar(p, pos, ang, quadril, altura, lado):
    """O corpo inteiro sobe e sai de quadro, inclinado, sem se desmontar.

    E' o unico efeito nao destrutivo do catalogo, e por isso o unico que pode
    acontecer no meio de um trecho sem estragar o resto dele.

    A SUBIDA E' `p*p` (acelerando) e o giro e' linear: um corpo que sobe rapido
    e gira devagar le como "foi puxado", que e' a gag; girando junto com a
    subida leria como "foi arremessado", que e' outra coisa e ja e' a
    explosao.
    """
    # A ALTURA E O EXPOENTE SAIRAM DA TIRA DE PREVIA, E NAO DO PALPITE.
    # A primeira versao era `2,2 alturas * p*p`, e a tira de
    # `ferramentas/efeito.py` mostrou o corpo INTEIRO fora do quadro em
    # p = 0,4: os tres ultimos instantes da gag eram quadro vazio, ou seja,
    # metade do tempo do efeito nao mostrava efeito nenhum.
    #
    # Com 1,3 altura e expoente 1,7 o corpo sobe visivelmente do comeco ao fim
    # e so escapa perto de p = 1 -- que e' o instante em que ele DEVE escapar,
    # porque e' ai que o trecho acaba.
    novo_pos, novo_ang = {}, {}
    sobe = altura * 1.3 * (p ** 1.7)
    lateral = altura * 0.5 * p * (1.0 if lado == "d" else -1.0)
    giro = 26.0 * p
    for k, (x, y) in pos.items():
        novo_pos[k] = (x + lateral, y - sobe)
        novo_ang[k] = ang.get(k, 0.0) + giro
    return novo_pos, novo_ang, 1.0


def _perder_braco(p, pos, ang, quadril, altura, lado):
    """Um braco se solta e cai; o resto do corpo continua atuando.

    A GAG DEPENDE DO RESTO FICAR PARADO. Se o corpo inteiro reagisse, o olho
    leria "caiu" em vez de "perdeu o braco" -- entao aqui so as tres pecas
    daquele lado se mexem, e a atuacao do trecho segue por baixo.

    O braco cai com um leve empurrao para fora antes de despencar, senao ele
    desce colado no tronco e some atras da perna.
    """
    novo_pos = dict(pos)
    novo_ang = dict(ang)
    fora = altura * 0.18 * p
    queda = altura * 1.3 * (p * p)
    sinal = 1.0 if lado == "d" else -1.0
    for i, k in enumerate(BRACO.get(lado, BRACO["d"])):
        if k not in pos:
            continue
        # a mao cai um pouco na frente da manga: a corrente se abre no ar
        atraso = 1.0 + 0.12 * i
        x, y = pos[k]
        novo_pos[k] = (x + sinal * fora * atraso, y + queda * atraso)
        novo_ang[k] = ang.get(k, 0.0) + sinal * 200.0 * p
    return novo_pos, novo_ang, 1.0


def _derreter(p, pos, ang, quadril, altura, lado):
    """O corpo escorre para a linha do chao e vira uma poca.

    CADA PECA DESCE EM PROPORCAO A ALTURA DELA. A cabeca, que esta longe do
    chao, percorre muito; o pe, que ja esta la, quase nao anda. E' isso que
    faz o corpo AFUNDAR em vez de descer inteiro -- descer inteiro seria o
    personagem caindo pelo alcapao.

    O giro cresce com a mesma proporcao: o que derrete tomba.
    """
    novo_pos, novo_ang = {}, {}
    # O chao e' o ponto mais baixo do corpo na pose atual. Medir aqui, e nao
    # receber de fora, mantem o efeito valido em qualquer enquadramento --
    # inclusive num close, onde o "chao" da tela nao e o chao da cena.
    chao = max((y for _x, y in pos.values()), default=quadril[1])
    for k, (x, y) in pos.items():
        acima = max(0.0, chao - y)
        novo_pos[k] = (x + (x - quadril[0]) * 0.35 * p, y + acima * 0.92 * p)
        novo_ang[k] = ang.get(k, 0.0) + (acima / max(altura, 1.0)) * 55.0 * p
    return novo_pos, novo_ang, 1.0


_CONTA = {
    "explodir": _explodir,
    "voar": _voar,
    "perder_braco": _perder_braco,
    "derreter": _derreter,
}
