#!/usr/bin/env python3
"""
sfx — efeitos sonoros e trilha, SINTETIZADOS AQUI.

POR QUE ISTO EXISTE
    O vídeo de 28/08 tinha uma faixa de áudio só: a voz. Um Short de humor
    com voz seca soa como recado de secretária eletrônica -- a piada chega
    sem sublinhado nenhum, e o silêncio entre as falas (o respiro de 0,45s
    que o motor insere) vira buraco em vez de virar tempo cômico. Foi a
    queixa do usuário em 29/08, junto com "voz sem emoção".

    Efeito sonoro em desenho animado não é enfeite: é o que diz ao
    espectador ONDE está a piada. A batida seca quando o boneco leva as
    mãos à cabeça é o que transforma um gesto em reação.

POR QUE SINTETIZADO, E NÃO BAIXADO
    Uma biblioteca de SFX seria melhor de ouvir e pior de manter: são
    dezenas de arquivos com licenças diferentes, que precisam viver no
    bucket, ser baixados no runner e conferidos um a um. A regra do
    projeto (§1 do HANDOFF) é que o que roda automático prioriza o
    GRÁTIS -- e um efeito de desenho animado é, acusticamente, uma coisa
    simples: um envelope rápido sobre um oscilador que varre frequência.
    Isso cabe em numpy, roda offline, é determinístico e não tem licença.

    O spec continua podendo apontar `musica_url` para uma faixa de
    verdade no dia em que houver uma; a trilha sintética é o padrão, não
    a única opção.

COMO SE LIGA AO VÍDEO
    Duas fontes de evento, na mesma lógica das expressões faciais:

      1. AUTOMÁTICA -- cada ação do vocabulário (acoes.py) tem um som que
         lhe é próprio: `susto` estala, `cair` bate, `pular` faz boing. O
         roteirista não precisa saber que áudio existe.
      2. EXPLÍCITA -- `sfx: [{"nome": "rimshot", "em": 0.95}]` no trecho,
         com `em` em fração do trecho, igual a `de`/`ate` das ações.

    A mixagem final devolve UM wav: voz + efeitos + trilha, com a trilha
    abaixando sozinha embaixo da fala (ducking). O ffmpeg do render
    continua recebendo um arquivo de áudio só, como antes.
"""
import math
import os
import wave

import numpy as np

SR = 24000                     # o mesmo do palito_v5; misturar exige igualdade

# Ganhos de mixagem, em dB relativos à voz. A voz manda: efeito que compete
# com a fala faz o espectador perder a piada, que é o oposto do objetivo.
GANHO_SFX_DB = -7.0
# -18 dB, não -21: com bateria e baixo a trilha tem que ser OUVIDA nas
# pausas -- é ali que ela segura quem está prestes a rolar o feed. O que a
# mantém fora do caminho da fala é o ducking, não o volume geral.
GANHO_MUSICA_DB = -18.0
# ...e por isso o ducking fundo mais: -11 dB sobre -18 dá -29 dB por baixo
# da voz, mais silencioso do que os -30 que a trilha antiga tinha ali. Mais
# alta na pausa, mais baixa embaixo da fala: é o contraste que prende, não
# o volume médio.
DUCK_DB = -11.0                # o quanto a trilha abaixa quando há voz


def _db(x):
    return 10.0 ** (x / 20.0)


# =====================================================================
# Blocos de síntese
# =====================================================================
def _t(dur, sr=SR):
    return np.arange(int(max(1, dur * sr))) / float(sr)


def _fade(x, ms=6.0, sr=SR):
    """Rampa nas duas pontas. Sem ela todo efeito começa e termina com um
    clique -- o degrau de amplitude é um impulso, e impulso se ouve."""
    n = int(sr * ms / 1000.0)
    if n < 2 or len(x) < 2 * n:
        return x
    r = np.linspace(0.0, 1.0, n)
    x = x.copy()
    x[:n] *= r
    x[-n:] *= r[::-1]
    return x


def _exp(t, tau):
    return np.exp(-t / max(tau, 1e-4))


def _ruido(n, semente=0):
    return np.random.default_rng(semente).uniform(-1.0, 1.0, n)


def _passa_baixa(x, corte, sr=SR):
    """One-pole. Vetorizar isto exigiria scipy; o laço roda sobre alguns
    milhares de amostras por efeito, uma vez por processo (tudo é cacheado),
    e some no tempo de render de um único frame."""
    a = math.exp(-2.0 * math.pi * corte / sr)
    y = np.empty_like(x)
    z = 0.0
    for i in range(len(x)):
        z = (1.0 - a) * x[i] + a * z
        y[i] = z
    return y


def _passa_alta(x, corte, sr=SR):
    return x - _passa_baixa(x, corte, sr)


def _varredura(f0, f1, dur, curva=3.0, sr=SR):
    """Seno que varre de f0 a f1. A varredura é EXPONENCIAL porque altura
    percebida é logarítmica: uma varredura linear de 400 a 100 Hz passa
    quase todo o tempo dela na parte aguda e o ouvido lê como buzina, não
    como queda."""
    t = _t(dur, sr)
    k = np.exp(-curva * t / max(t[-1], 1e-6))
    f = f1 + (f0 - f1) * k
    fase = 2.0 * np.pi * np.cumsum(f) / sr
    return np.sin(fase)


# =====================================================================
# O catálogo
# =====================================================================
def _thud():
    """Batida seca: corpo caindo, mão batendo na testa, objeto no chão."""
    t = _t(0.30)
    corpo = _varredura(150, 42, 0.30, curva=5.0) * _exp(t, 0.055)
    estalo = _passa_baixa(_ruido(len(t), 1), 900) * _exp(t, 0.018) * 0.7
    return _fade(corpo * 0.9 + estalo)


def _boing():
    """Mola de desenho animado. O vibrato é o que faz ler como MOLA e não
    como assobio: é a oscilação em torno da frequência que dá a elasticidade."""
    t = _t(0.45)
    f = 420 * np.exp(-2.6 * t) + 110
    f = f * (1.0 + 0.42 * np.sin(2 * np.pi * 11.0 * t) * np.exp(-3.0 * t))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    return _fade(x * _exp(t, 0.13) * 0.85)


def _whoosh():
    """Passagem rápida: alguém entra correndo, um braço cruza o quadro.
    Ruído com o corte do filtro subindo e descendo -- é o Doppler de
    banda larga que o ouvido reconhece como algo passando."""
    n = int(0.38 * SR)
    t = _t(0.38)
    env = np.sin(np.pi * np.linspace(0, 1, n)) ** 1.6
    base = _ruido(n, 7)
    grave = _passa_baixa(base, 700)
    agudo = _passa_alta(base, 2200)
    k = np.sin(np.pi * np.linspace(0, 1, n))
    return _fade(_fade(grave * (1 - k) + agudo * k) * env * 0.8)


def _sting_susto():
    """O susto. Três notas juntas a meio tom de distância batem entre si e
    produzem a aspereza que se lê como alarme; a varredura para cima e o
    tremolo são a parte 'desenho animado' -- sem eles vira trilha de terror,
    que não é o tom do canal."""
    t = _t(0.55)
    x = np.zeros_like(t)
    for k, f0 in enumerate((523.0, 554.0, 587.0)):
        f = f0 * (1.0 + 0.55 * (1.0 - np.exp(-6.0 * t)))
        x += np.sin(2 * np.pi * np.cumsum(f) / SR + k) / 3.0
    tremolo = 1.0 + 0.35 * np.sin(2 * np.pi * 17.0 * t)
    return _fade(x * tremolo * _exp(t, 0.16) * 0.9)


def _pop():
    """Pontuação curtinha: dedo que aponta, olho que arregala."""
    t = _t(0.12)
    x = _varredura(180, 900, 0.12, curva=-4.0) * _exp(t, 0.030)
    return _fade(x * 0.7, ms=3)


def _plim():
    """Sino: a ideia que acende. Parciais inarmônicos, que é o que
    diferencia sino de flauta."""
    t = _t(0.9)
    x = sum(a * np.sin(2 * np.pi * f * t) * _exp(t, d)
            for f, a, d in ((1046.5, 0.6, 0.35), (2093.0, 0.25, 0.22),
                            (2960.0, 0.15, 0.14)))
    return _fade(x * 0.8)


def _erro():
    """O 'errou'. Duas quadradas desafinadas em terça menor: o intervalo é o
    mesmo do interfone de prédio, e o cérebro brasileiro já sabe que
    significa negativa."""
    t = _t(0.42)
    q = lambda f: np.sign(np.sin(2 * np.pi * f * t))
    x = (q(196.0) + q(233.0)) * 0.5
    env = np.where(t < 0.18, 1.0, np.where(t < 0.22, 0.0, 1.0)) * _exp(t, 0.5)
    return _fade(_passa_baixa(x, 1800) * env * 0.5)


def _rimshot():
    """Ba-dum-tss. O carimbo de piada -- e o motivo pelo qual ele existe
    aqui: o punchline precisa de uma marca sonora, senão a última fala soa
    igual às outras três e ninguém sabe que acabou."""
    total = int(1.5 * SR)
    x = np.zeros(total)

    def por(sinal, em):
        i = int(em * SR)
        n = min(len(sinal), total - i)
        x[i:i + n] += sinal[:n]

    t1 = _t(0.25)
    tom = _varredura(300, 150, 0.25, curva=6.0) * _exp(t1, 0.07)
    tom2 = _varredura(260, 130, 0.25, curva=6.0) * _exp(t1, 0.07)
    # a caixa é mais curta que o tom, então cada uma entra por conta
    # própria em vez de serem somadas antes (arrays de tamanhos diferentes)
    caixa = lambda: _passa_alta(_ruido(int(0.18 * SR), 3), 1200) * _exp(_t(0.18), 0.05)
    por(tom * 0.8, 0.00); por(caixa() * 0.5, 0.00)          # ba
    por(tom2 * 0.8, 0.17); por(caixa() * 0.5, 0.17)         # dum
    t3 = _t(1.1)
    prato = _passa_alta(_ruido(len(t3), 11), 5000) * _exp(t3, 0.34)
    por(prato * 0.42, 0.34)                                 # tss
    return _fade(x * 0.9)


def _passo():
    t = _t(0.09)
    return _fade(_passa_baixa(_ruido(len(t), 5), 1400) * _exp(t, 0.02) * 0.45, ms=3)


def _tremido():
    """Tremor de indecisão/coceira: útil em `cocar_cabeca` e `duvida`."""
    t = _t(0.5)
    f = 230 + 40 * np.sin(2 * np.pi * 9.0 * t)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    return _fade(x * _exp(t, 0.22) * 0.35)


# =====================================================================
# SOM DE COISA (27/08 à noite)
# =====================================================================
# Os dez efeitos acima são de DESENHO: baque, mola, susto, rimshot. Eles
# pontuam o corpo. O que faltava era o som do MUNDO -- "fui cancelar no
# celular" e não se ouve o clique, "andei" e não se ouve o passo. Sem isso
# a faixa continua sabendo o que o personagem SENTE e não sabendo o que ele
# FAZ, e o objeto na mão vira adereço mudo.
#
# Todos continuam sintetizados: uma biblioteca de samples seria melhor de
# ouvir e pior de manter (dezenas de arquivos com licenças diferentes, no
# bucket, baixados no runner), e o que se pede aqui é o som ESQUEMÁTICO que
# o desenho animado usa -- ninguém precisa do clique verdadeiro de um
# iPhone, precisa do clique que se lê como "ele mexeu no telefone".
def _clique():
    """O toque na tela do celular. Curtíssimo: um estalo agudo e um blip.

    Um toque de dedo em vidro não faz som nenhum no mundo real; o que se
    reconhece como "mexeu no celular" é o clique da interface. É o mesmo
    tipo de convenção do rimshot."""
    t = _t(0.06)
    estalo = _passa_alta(_ruido(len(t), 21), 2800) * _exp(t, 0.005)
    blip = np.sin(2 * np.pi * 1900 * t) * _exp(t, 0.012)
    return _fade(estalo * 0.8 + blip * 0.45, ms=2)


def _digitar():
    """Rajada de toques: mexendo no aplicativo, digitando a senha. Um
    clique solto lê como defeito de áudio; a rajada lê como alguém
    operando a coisa."""
    total = int(0.62 * SR)
    x = np.zeros(total)
    c = _clique()
    for k, em in enumerate((0.0, 0.11, 0.19, 0.31, 0.44)):
        i = int(em * SR)
        m = min(len(c), total - i)
        x[i:i + m] += c[:m] * (0.7 + 0.3 * ((k * 7) % 5) / 4.0)
    return _fade(x * 0.85)


def _notificacao():
    """O 'blim' do telefone: duas notas subindo, curtas e limpas."""
    x = np.zeros(int(0.55 * SR))
    for em, f in ((0.0, 1318.5), (0.11, 1760.0)):
        t = _t(0.30)
        nota = (np.sin(2 * np.pi * f * t)
                + 0.3 * np.sin(2 * np.pi * 2 * f * t)) * _exp(t, 0.09)
        i = int(em * SR)
        m = min(len(nota), len(x) - i)
        x[i:i + m] += nota[:m] * 0.55
    return _fade(x)


def _chaves():
    """Molho de chaves. O parcial inarmônico agudo é o que faz ler como
    METAL; a irregularidade dos tempos é o que faz ler como MOLHO -- em
    tempos regulares soaria como sino."""
    n = int(0.75 * SR)
    x = np.zeros(n)
    rng = np.random.default_rng(17)
    for em in rng.uniform(0.0, 0.42, 9):
        t = _t(0.30)
        f = rng.uniform(2400.0, 5200.0)
        tin = (np.sin(2 * np.pi * f * t)
               + 0.6 * np.sin(2 * np.pi * f * 2.73 * t)) * _exp(t, 0.045)
        i = int(em * SR)
        m = min(len(tin), n - i)
        x[i:i + m] += tin[:m] * rng.uniform(0.35, 0.8)
    return _fade(x * 0.55)


def _gole():
    """Gole: duas deglutições. Ruído grave com o corte do filtro caindo --
    é a queda de altura que se lê como líquido descendo."""
    n = int(0.62 * SR)
    x = np.zeros(n)
    for em, dur in ((0.0, 0.22), (0.26, 0.18)):
        t = _t(dur)
        env = np.sin(np.pi * np.linspace(0, 1, len(t))) ** 1.4
        base = _passa_baixa(_ruido(len(t), 31), 520) * 1.2
        f = 180.0 * np.exp(-3.0 * t) + 70.0
        tom = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.5
        i = int(em * SR)
        m = min(len(t), n - i)
        x[i:i + m] += ((base + tom) * env)[:m]
    return _fade(x * 0.7)


def _papel():
    """Sacola / papel amassado: rajadas curtas de ruído agudo em tempos
    irregulares. A irregularidade é o que separa 'papel' de 'chuveiro'."""
    n = int(0.55 * SR)
    rng = np.random.default_rng(5)
    base = _passa_alta(_ruido(n, 13), 1800)
    env = np.zeros(n)
    for em in rng.uniform(0.0, 0.45, 14):
        i = int(em * SR)
        d = max(3, int(rng.uniform(0.010, 0.045) * SR))
        janela = np.hanning(d) * rng.uniform(0.4, 1.0)
        m = min(d, n - i)
        if m > 0:
            env[i:i + m] += janela[:m]
    return _fade(base * np.minimum(env, 1.4) * 0.5)


def _louca():
    """Xícara pousada: batida curta com ressonância de cerâmica."""
    t = _t(0.35)
    x = sum(a * np.sin(2 * np.pi * f * t) * _exp(t, d)
            for f, a, d in ((760.0, 0.6, 0.10), (1930.0, 0.3, 0.06),
                            (3410.0, 0.15, 0.04)))
    estalo = _passa_alta(_ruido(len(t), 9), 2000) * _exp(t, 0.006)
    return _fade(x * 0.7 + estalo * 0.4)


def _rangido():
    """Dobradiça emperrada, guarda-chuva que não abre. Onda quadrada com
    a altura tremendo devagar: é assim que soa atrito de coisa presa."""
    t = _t(0.7)
    f = 320.0 + 180.0 * np.sin(2 * np.pi * 2.3 * t) + 60.0 * np.sin(2 * np.pi * 13.0 * t)
    x = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR))
    env = np.sin(np.pi * np.linspace(0, 1, len(t))) ** 1.2
    return _fade(_passa_baixa(x, 2200) * env * 0.35)


def _caixa():
    """Caixa registradora: o sino e a gaveta. É o som de dinheiro saindo, e
    metade das esquetes deste canal é sobre dinheiro saindo."""
    n = int(1.0 * SR)
    x = np.zeros(n)
    t = _t(0.8)
    sino = sum(a * np.sin(2 * np.pi * f * t) * _exp(t, d)
               for f, a, d in ((1568.0, 0.5, 0.30), (2349.0, 0.3, 0.20),
                               (3136.0, 0.2, 0.12)))
    x[:len(sino)] += sino * 0.6
    gaveta = _varredura(220, 90, 0.30, curva=4.0) * _exp(_t(0.30), 0.08)
    i = int(0.22 * SR)
    m = min(len(gaveta), n - i)
    x[i:i + m] += gaveta[:m] * 0.7
    return _fade(x * 0.85)


CATALOGO = {
    "thud": _thud, "batida": _thud,
    "boing": _boing, "mola": _boing,
    "whoosh": _whoosh, "passagem": _whoosh,
    "susto": _sting_susto, "sting": _sting_susto, "surpresa": _sting_susto,
    "pop": _pop,
    "plim": _plim, "ideia": _plim, "ding": _plim,
    "erro": _erro, "errou": _erro,
    "rimshot": _rimshot, "piada": _rimshot,
    "passo": _passo,
    "tremido": _tremido,
    # som de coisa
    "clique": _clique, "toque": _clique,
    "digitar": _digitar, "teclado": _digitar,
    "notificacao": _notificacao, "blim": _notificacao,
    "chaves": _chaves, "tilintar": _chaves,
    "gole": _gole, "sorver": _gole,
    "papel": _papel, "sacola": _papel,
    "louca": _louca, "xicara": _louca,
    "rangido": _rangido, "porta": _rangido,
    "caixa": _caixa, "dinheiro": _caixa, "registradora": _caixa,
}

# Peso de cada efeito na mistura, depois de todos serem levados ao mesmo
# pico. É aqui que se decide o que é PONTUAÇÃO e o que é ACONTECIMENTO: o
# baque de uma queda tem que assustar, o pop de um dedo apontando não pode
# tirar o ouvido da fala. Um lugar só para calibrar.
GANHO_BASE = {
    "susto": 1.00, "thud": 1.00, "boing": 0.85, "whoosh": 0.70,
    "rimshot": 0.95, "erro": 0.80, "plim": 0.70,
    "pop": 0.40, "tremido": 0.35, "passo": 0.30,
    # SOM DE COISA fica ABAIXO do som de desenho, de propósito: ele existe
    # para dar textura ao que está acontecendo, não para pontuar. Clique
    # alto demais rouba a fala que está por cima dele.
    "caixa": 0.85, "notificacao": 0.62, "chaves": 0.55, "louca": 0.55,
    "gole": 0.50, "digitar": 0.45, "papel": 0.45, "rangido": 0.45,
    "clique": 0.42,
}

_CACHE = {}


def efeito(nome):
    """A onda do efeito, sintetizada uma vez por processo.

    Nunca levanta: efeito faltando é vídeo sem um som, efeito que derruba o
    render é vídeo nenhum -- a mesma regra de expressao.normalizar."""
    n = str(nome or "").strip().lower()
    if n not in CATALOGO:
        return None
    if n not in _CACHE:
        x = CATALOGO[n]().astype(np.float32)
        # PICO IGUAL PARA TODOS. Sem isto o ganho de cada efeito dependeria
        # de quantos osciladores a receita dele soma, e equilibrar a mistura
        # viraria adivinhação: o rimshot saía em 1,05 e o passo em 0,22.
        p = float(np.max(np.abs(x))) or 1.0
        _CACHE[n] = x * (0.9 / p)
    return _CACHE[n]


# =====================================================================
# De AÇÃO para SOM
# =====================================================================
# Cada entrada: (efeito, onde na janela da ação, ganho).
# `onde` é fração da janela `de`..`ate`: o baque de `cair` toca no fim da
# queda, o boing de `pular` no impulso, o whoosh de quem entra correndo
# junto com a entrada.
#
# SÓ EVENTO FÍSICO ENTRA AQUI (revisto em 27/08). A tabela anterior dava som
# a gesto: `apontar` fazia pop, `acenar` fazia pop, `encolher_ombros` fazia
# pop, `cocar_cabeca` fazia tremido. Nada disso produz barulho no mundo, e o
# resultado era um vídeo de 20 segundos com oito efeitos, metade deles
# decorativos, disparando em cima de gente parada falando -- que é
# exatamente a queixa de "efeito sonoro sem sentido". Som que não tem causa
# na tela não vira ênfase: vira ruído, e ainda gasta o impacto do som que
# TEM causa.
#
# A régua para entrar: alguém, vendo o quadro no mudo, entenderia de onde
# veio o som? Corpo batendo no chão, sim. Mão apontando, não.
DA_ACAO = {
    "susto":           ("susto", 0.05, 1.0),
    "pular":           ("boing", 0.12, 0.9),
    "cair":            ("thud", 0.75, 1.0),
    "tropecar":        ("thud", 0.45, 0.7),
    "entrar_correndo": ("whoosh", 0.05, 0.8),
    "maos_na_cabeca":  ("thud", 0.25, 0.6),
    # objeto que encosta em alguma coisa: aqui há contato de verdade.
    # Estas linhas são o GENÉRICO -- o objeto que tem som próprio manda
    # sobre elas (ver DO_OBJETO).
    "pegar_objeto":    ("pop", 0.55, 0.5),
    "largar_objeto":   ("thud", 0.60, 0.5),
    "entregar_objeto": ("pop", 0.70, 0.4),
    "usar_objeto":     ("pop", 0.35, 0.4),
}

# Expressões que merecem marca sonora própria, quando entram como JANELA de
# reação no meio da fala (`expressoes: []`). Cara que muda sem som muda
# menos: é o mesmo motivo pelo qual o susto tem sting.
#
# Encolhida em 27/08 pela mesma razão da tabela acima: `duvida` e `pensando`
# disparavam um `tremido` toda vez que o roteirista pedia uma cara pensativa,
# e cara pensativa é o que mais aparece numa esquete de alguém confuso. Ficam
# só as reações de CHOQUE, que são as que um público espera ouvir sublinhadas.
DA_EXPRESSAO = {
    "chocado": ("susto", 0.9),
    "surpreso": ("susto", 0.6),
}

# =====================================================================
# O OBJETO MANDA NO SOM DA AÇÃO (27/08 à noite)
# =====================================================================
# `usar_objeto` não tem som próprio: usar um CELULAR é um clique, usar uma
# XÍCARA é um gole, usar uma CHAVE é o tilintar. A tabela acima só sabia da
# ação, então a esquete inteira sobre cancelar assinatura pelo aplicativo
# passava sem um único toque de tela -- que é exatamente a queixa de "som
# que não tem a ver com o que está acontecendo".
#
# O vocabulário de objeto é fechado (LEI 11), então esta tabela é fechada
# junto: objeto novo entra aqui no mesmo dia em que entra no bucket. Objeto
# sem linha aqui cai no som genérico de contato de `DA_ACAO`.
DO_OBJETO = {
    "celular": {
        "usar_objeto":     ("digitar", 0.30, 0.9),
        "pegar_objeto":    ("clique", 0.60, 0.6),
        "mostrar_objeto":  ("notificacao", 0.45, 0.7),
        "entregar_objeto": ("clique", 0.70, 0.5),
    },
    "xicara_de_cafe": {
        "usar_objeto":     ("gole", 0.35, 1.0),
        "pegar_objeto":    ("louca", 0.55, 0.7),
        "largar_objeto":   ("louca", 0.60, 0.9),
        "entregar_objeto": ("louca", 0.70, 0.6),
    },
    "chave": {
        "usar_objeto":     ("chaves", 0.35, 1.0),
        "pegar_objeto":    ("chaves", 0.55, 0.8),
        "mostrar_objeto":  ("chaves", 0.40, 0.7),
        "entregar_objeto": ("chaves", 0.65, 0.8),
        "largar_objeto":   ("chaves", 0.60, 0.9),
    },
    "sacola_de_compras": {
        "usar_objeto":     ("papel", 0.35, 0.9),
        "pegar_objeto":    ("papel", 0.55, 0.7),
        "largar_objeto":   ("papel", 0.60, 0.8),
        "entregar_objeto": ("papel", 0.65, 0.6),
    },
    "guarda_chuva_quebrado": {
        "usar_objeto":     ("rangido", 0.30, 1.0),
        "pegar_objeto":    ("rangido", 0.55, 0.6),
        "mostrar_objeto":  ("rangido", 0.40, 0.7),
    },
}

# Locomoção: som em CADÊNCIA, não um som só. Ver `_cadencia_de_passos`.
ANDANDO = {
    "andar":           (1.7, 1.00),
    "entrar_andando":  (1.7, 1.00),
    "sair_andando":    (1.7, 1.00),
    "entrar_correndo": (3.2, 1.25),
}


def _cadencia_de_passos(a, t0, dur):
    """Um som por PISADA, na fase em que o pé encosta no chão.

    POR QUE ISTO É DIFERENTE DO RESTO DA TABELA
        Todo o resto aqui é pontuação: um evento, um som. Andar não é um
        evento, é um estado -- e um baque solto no meio de uma caminhada de
        três segundos soa como tropeço, não como passo. Foi por isso que
        `passo` existia no catálogo desde 29/08 e nunca tocou: não havia
        como pendurá-lo em `DA_ACAO`, que só sabe disparar uma vez.

    ONDE CAI CADA PISADA
        `acoes._ciclo_passo_lateral` recebe `fase = 2*pi*passos*u*dur` e os
        dois pés estão juntos no chão quando `sin(fase) = 0`, ou seja a cada
        meia volta. As pisadas são, então, em `k / (2*passos)` segundos
        depois do início da ação -- medido no mesmo ciclo que desenha a
        perna, e não estimado. Som de passo fora da pisada é pior que
        silêncio: denuncia que o áudio e o vídeo não se conhecem.
    """
    nome = str(a.get("nome", "")).strip().lower()
    padrao = ANDANDO.get(nome)
    if not padrao:
        return []
    passos = float(a.get("passos_por_s", padrao[0]))
    de, ate = float(a.get("de", 0.0)), float(a.get("ate", 1.0))
    janela = max(0.0, (ate - de) * dur)
    if passos <= 0 or janela < 0.25:
        return []
    intervalo = 1.0 / (2.0 * passos)
    base = t0 + de * dur
    fora = []
    k = 1
    while k * intervalo < janela and len(fora) < 40:
        fora.append({"nome": "passo", "t": base + k * intervalo,
                     # pé alternado soa mais pesado que o outro; sem essa
                     # variação a cadência vira metrônomo
                     "ganho": padrao[1] * (1.0 if k % 2 else 0.75),
                     "cadencia": True})
        k += 1
    return fora


def eventos_do_spec(spec):
    """Percorre os trechos e devolve [{nome, t, ganho}] em tempo GLOBAL.

    Depende de `_inicio_s` e `_dur_voz`, que `palito_cutout.render` grava em
    cada trecho quando sintetiza a voz -- ou seja, roda depois da voz e
    antes do vídeo, que é exatamente onde a timeline real já existe.
    """
    fora = []
    trechos = spec.get("trechos") or []
    for i, tr in enumerate(trechos):
        t0 = float(tr.get("_inicio_s", 0.0))
        dur = float(tr.get("_dur_voz", 0.0))
        if dur <= 0.0:
            continue

        for a in (tr.get("acoes") or []):
            acao = str(a.get("nome", "")).strip().lower()
            # PISADAS primeiro: locomoção rende uma cadência, não um evento
            fora.extend(_cadencia_de_passos(a, t0, dur))
            # o objeto na mão manda sobre a tabela da ação: usar um celular
            # é um clique, usar uma xícara é um gole
            obj = str(a.get("objeto") or "").strip().lower()
            reg = (DO_OBJETO.get(obj) or {}).get(acao) or DA_ACAO.get(acao)
            if not reg:
                continue
            nome, onde, g = reg
            de, ate = float(a.get("de", 0.0)), float(a.get("ate", 1.0))
            fora.append({"nome": nome, "t": t0 + (de + (ate - de) * onde) * dur,
                         "ganho": g * float(a.get("forca", 1.0))})

        for j in (tr.get("expressoes") or []):
            reg = DA_EXPRESSAO.get(str(j.get("nome") or j.get("valor") or "").strip().lower())
            if not reg:
                continue
            nome, g = reg
            fora.append({"nome": nome, "t": t0 + float(j.get("de", 0.0)) * dur, "ganho": g})

        # explícitos: sempre por último, para o roteirista poder pôr um som
        # exatamente onde quiser sem lutar contra o automático
        for s in (tr.get("sfx") or []):
            nome = s.get("nome") if isinstance(s, dict) else s
            em = float(s.get("em", 0.0)) if isinstance(s, dict) else 0.0
            g = float(s.get("ganho", 1.0)) if isinstance(s, dict) else 1.0
            fora.append({"nome": nome, "t": t0 + em * dur, "ganho": g})

    # DOIS SONS QUASE JUNTOS viram barulho, não ênfase. Fica o de maior
    # ganho. A janela é de 250ms porque o caso real não é empate exato: o
    # `susto` que o motor injeta como gancho e o `susto` que o roteirista
    # escreveu caíram a 200ms um do outro no teste de 29/08, e o resultado
    # foi um estalo duplo que soa como defeito de áudio.
    # A CADÊNCIA NÃO PASSA POR AQUI. Passo é um som de textura, contínuo por
    # construção: fundir passos a 250ms um do outro apagaria a caminhada
    # inteira, e cortá-los por densidade apagaria a única coisa que dá peso
    # a quem anda. Eles têm teto próprio (40 por ação) e ganho baixo.
    passos = [e for e in fora if e.get("cadencia")]
    fora = [e for e in fora if not e.get("cadencia")]

    fora.sort(key=lambda e: e["t"])
    limpos = []
    for e in fora:
        if limpos and e["t"] - limpos[-1]["t"] < 0.6:
            if e["ganho"] > limpos[-1]["ganho"]:
                limpos[-1] = e
            continue
        limpos.append(e)

    # DENSIDADE. Efeito demais é a mesma doença do efeito sem causa: quando
    # tudo é sublinhado, nada é. Num Short de 20 segundos, mais de oito
    # sons transformam a faixa em desenho dos anos 40 -- e o punchline, que
    # é o único que PRECISA ser ouvido, some no meio dos outros.
    #
    # O corte é por ganho, não por ordem: fica o que o roteiro marcou de
    # propósito e o impacto forte, sai o pop de encosto.
    teto = max(4, int(_duracao_total(trechos) / 2.5))
    if len(limpos) > teto:
        fortes = sorted(limpos, key=lambda e: -e["ganho"])[:teto]
        cortados = len(limpos) - len(fortes)
        limpos = sorted(fortes, key=lambda e: e["t"])
        print(f"[sfx] {cortados} efeito(s) cortado(s) por densidade "
              f"(teto de {teto} num video de {_duracao_total(trechos):.0f}s)")
    if passos:
        print(f"[sfx] {len(passos)} pisada(s) em cadencia")
    return sorted(limpos + passos, key=lambda e: e["t"])


def _duracao_total(trechos):
    if not trechos:
        return 20.0
    ult = trechos[-1]
    return float(ult.get("_inicio_s", 0.0)) + float(ult.get("dur", 0.0)) or 20.0


# =====================================================================
# TRILHA
# =====================================================================
# Progressão I-V-vi-IV: a mesma de metade da música pop do século, e por um
# motivo -- ela não resolve em lugar nenhum, então dá para cortar em
# qualquer compasso sem soar interrompida. Um Short dura 20 segundos e
# termina no meio de tudo.
_GRAUS = {
    # maior, aberta: o mundo está bem e nada foi revelado ainda
    "leve":     [(0, 4, 7), (7, 11, 14), (9, 12, 16), (5, 9, 12)],
    # menor com o VI napolitano: não resolve e não relaxa
    "tenso":    [(0, 3, 7), (8, 12, 15), (5, 8, 12), (7, 11, 14)],
    # menor plagal, lenta: derrota, o personagem perdeu
    "triste":   [(0, 3, 7), (5, 8, 12), (0, 3, 7), (7, 10, 14)],
    # dois acordes a um semitom: a coisa mais próxima de "algo vem aí"
    "suspense": [(0, 3, 6), (1, 4, 7), (0, 3, 6), (11, 2, 5)],
    # maior com sétima e trítono: o soar de quem se acha, deslizando
    "deboche":  [(0, 4, 10), (5, 9, 15), (0, 4, 10), (6, 10, 16)],
    # cadência autêntica: só para quando a piada FECHA em vitória
    "triunfo":  [(0, 4, 7), (5, 9, 12), (7, 11, 14), (0, 4, 7)],
}
_TONICA = 261.63          # dó central

# A EMOÇÃO DO TRECHO ESCOLHE A TRILHA. O roteirista já rotula cada trecho com
# uma expressão (é ela que move a cara e a prosódia da voz); a trilha passa a
# ler o MESMO rótulo. Sem isto ela tocava a mesma progressão alegre do começo
# ao fim, inclusive por baixo do desespero -- e era isso que a fazia soar
# colada por cima do vídeo em vez de dentro dele.
ESTILO_DA_EMOCAO = {
    "neutro": "leve", "sorrindo": "leve", "confiante": "triunfo",
    "surpreso": "suspense", "duvida": "suspense", "pensando": "suspense",
    "bravo": "tenso", "irritado": "tenso", "chocado": "tenso",
    "desesperado": "tenso", "triste": "triste", "desdem": "deboche",
}

# Quanto a trilha "aperta" em cada emoção: andamento e volume relativos.
INTENSIDADE_DA_EMOCAO = {
    "neutro": 1.00, "sorrindo": 1.00, "confiante": 1.05,
    "surpreso": 1.06, "duvida": 0.92, "pensando": 0.88,
    "bravo": 1.16, "irritado": 1.12, "chocado": 1.18,
    "desesperado": 1.22, "triste": 0.80, "desdem": 0.95,
}


def segmentos_do_spec(spec):
    """A trilha, trecho a trecho: [{inicio, dur, estilo, intensidade}].

    O ARCO. Uma esquete de 20 segundos tem começo, escalada e virada, e a
    trilha precisa acompanhar isso -- é o que separa música de fundo de
    música em cima. Cada trecho vira um segmento com o estilo que a emoção
    dele pede.

    O BREQUE DO PUNCHLINE. O último trecho entra com a música cortada: o
    silêncio antes da tirada é o instrumento mais barato da comédia, e é
    o mesmo motivo pelo qual `expressao.respiro_sugerido` dá 0,85 s de
    pausa ali. A trilha volta junto com o rimshot.
    """
    trechos = spec.get("trechos") or []
    fora = []
    for i, tr in enumerate(trechos):
        dur = float(tr.get("_dur_voz", 0.0))
        if dur <= 0:
            continue
        emo = str(tr.get("expressao", "neutro")).strip().lower()
        seg = {"inicio": float(tr.get("_inicio_s", 0.0)),
               "dur": float(tr.get("dur", dur)),
               "estilo": ESTILO_DA_EMOCAO.get(emo, "leve"),
               "intensidade": INTENSIDADE_DA_EMOCAO.get(emo, 1.0)}
        if i == len(trechos) - 1 and len(trechos) > 1:
            seg["breque"] = True
        fora.append(seg)
    return fora


# Quanto de BATERIA cada estilo aguenta. Groove por baixo de derrota soa
# como deboche do personagem, e a trilha triste é a única que precisa
# respirar; o resto do arco pede pulso.
PESO_RITMO = {"leve": 1.00, "tenso": 1.05, "triste": 0.30,
              "suspense": 0.55, "deboche": 0.95, "triunfo": 1.10}

BPM_PADRAO = 122.0


def _nota(f, dur, sr=SR, brilho=0.30):
    """Uma nota de marimba: fundamental, oitava e uma quinta acima, com
    envelope percussivo. Instrumento de barra é quase só fundamental --
    é por isso que ele não briga com a voz, que vive nos harmônicos."""
    t = _t(dur, sr)
    x = (np.sin(2 * np.pi * f * t)
         + brilho * np.sin(2 * np.pi * 2 * f * t)
         + brilho * 0.35 * np.sin(2 * np.pi * 3 * f * t))
    ataque = np.minimum(1.0, t / 0.006)
    return x * ataque * _exp(t, 0.16 + 0.4 * (200.0 / max(f, 60.0)))


# ---------------------------------------------------------------------
# A SEÇÃO RÍTMICA (27/08 à noite)
# ---------------------------------------------------------------------
# A trilha antiga era só marimba: harmonia bonita, andamento de sala de
# espera e nada abaixo de 130 Hz. Ela cumpria o que se pediu dela em 29/08
# -- "tirar o silêncio de estúdio de trás da voz" -- e não cumpre o que se
# pede agora, que é PRENDER. O que segura alguém que está rolando o feed é
# pulso: bumbo, chimbal e um baixo andando.
#
# E é a maneira de encher a faixa sem estourar nada: a voz mora entre 200 e
# 4000 Hz, o baixo mora abaixo de 130 e o chimbal acima de 6 kHz. As três
# coisas ocupam sentidos diferentes do mesmo ouvido, e nenhuma delas
# disputa espectro com a fala -- que é o que faz "mais música" virar "menos
# inteligível" quando se erra a faixa.
def _bumbo():
    """Bumbo: varredura grave rápida, mais um estalo de pele."""
    t = _t(0.24)
    corpo = _varredura(115, 44, 0.24, curva=6.5) * _exp(t, 0.055)
    pele = _passa_baixa(_ruido(len(t), 41), 2400) * _exp(t, 0.004) * 0.30
    return _fade(corpo + pele, ms=3)


def _chimbal(aberto=False):
    dur = 0.17 if aberto else 0.045
    t = _t(dur)
    x = _passa_alta(_ruido(len(t), 43 if aberto else 47), 6500)
    return _fade(x * _exp(t, 0.055 if aberto else 0.012) * 0.5, ms=2)


def _palma():
    """Palma no 2 e no 4. As três cópias muito juntas são o que faz soar
    como VÁRIAS mãos em vez de um estalo só -- é assim que a palma de
    música gravada é feita."""
    n = int(0.24 * SR)
    x = np.zeros(n)
    for em, g in ((0.0, 1.0), (0.008, 0.7), (0.017, 0.5)):
        t = _t(0.20)
        c = _passa_alta(_passa_baixa(_ruido(len(t), 53), 5200), 1100) * _exp(t, 0.035)
        i = int(em * SR)
        m = min(len(c), n - i)
        x[i:i + m] += c[:m] * g
    return _fade(x * 0.45)


def _baixo(f, dur, sr=SR):
    """Nota de baixo: quase só fundamental. Ele vive abaixo de 130 Hz, que
    é a faixa que o vídeo inteiro tinha vazia -- e é a faixa que dá a
    sensação física de "tem música tocando" sem tapar uma sílaba."""
    t = _t(dur, sr)
    x = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t)
    ataque = np.minimum(1.0, t / 0.008)
    corte = np.minimum(1.0, np.maximum(0.0, (dur - t) / 0.03))
    return x * ataque * corte * _exp(t, 0.5)


def trilha(dur_s, estilo="leve", bpm=BPM_PADRAO, semente=3, sr=SR, segmentos=None):
    """Bed instrumental do tamanho exato do vídeo, em três camadas.

    O QUE MUDOU EM 27/08 À NOITE
        A trilha era só marimba, a 104 bpm: calma, relaxante e exatamente o
        contrário do que um Short precisa. "Tirar o silêncio de estúdio",
        que era o pedido de 29/08, ela cumpria; PRENDER quem está rolando o
        feed, não -- para isso é preciso PULSO, e pulso é bumbo, chimbal e
        um baixo andando em colcheias.

        Entraram três camadas separadas, e é a separação que impede o
        estouro:

        HARMONIA  marimba, o arpejo que já existia -- 200 Hz a 2 kHz
        RITMO     bumbo, chimbal e palma -- grave curto e agudo curto
        GRAVE     baixo em colcheias -- abaixo de 130 Hz

        Cada uma é normalizada SOZINHA antes de se somarem, em proporção
        fixa. Sem isso a proporção entre elas dependeria de quantas notas
        por acaso se sobrepuseram, e a mesma esquete sairia com mistura
        diferente a cada render.

        E as três ocupam faixas diferentes do ouvido: a voz mora de 200 Hz
        a 4 kHz, o baixo abaixo de 130 e o chimbal acima de 6k. É por isso
        que dá para encher mais o áudio sem tapar uma sílaba -- "mais
        música" só vira "menos inteligível" quando se põe mais coisa NA
        FAIXA DA VOZ.

    `segmentos` (ver `segmentos_do_spec`) faz a trilha SEGUIR A CENA: cada
    trecho toca no estilo que a emoção dele pede, com o andamento, o volume
    e o PESO DE BATERIA daquela emoção, e o último entra depois de um
    breque."""
    n = int(dur_s * sr)
    harmonia = np.zeros(n + sr, dtype=np.float32)
    ritmo = np.zeros(n + sr, dtype=np.float32)
    grave = np.zeros(n + sr, dtype=np.float32)
    rng = np.random.default_rng(semente)

    # a percussão é a mesma onda toda vez: sintetizar por batida custaria
    # mais que o resto da trilha inteira num vídeo de 20 segundos
    bumbo, palma = _bumbo(), _palma()
    chimbal, chimbal_ab = _chimbal(False), _chimbal(True)

    def por(bus, sinal, em, g=1.0):
        i = int(em * sr)
        if i >= len(bus):
            return
        m = min(len(sinal), len(bus) - i)
        bus[i:i + m] += sinal[:m].astype(np.float32) * g

    if not segmentos:
        segmentos = [{"inicio": 0.0, "dur": dur_s, "estilo": estilo,
                      "intensidade": 1.0}]

    c = 0
    for seg in segmentos:
        est = seg.get("estilo", estilo)
        acordes = _GRAUS.get(est, _GRAUS["leve"])
        k_int = float(seg.get("intensidade", 1.0))
        k_bat = PESO_RITMO.get(est, 1.0) * k_int
        compasso = 4 * 60.0 / (bpm * (0.85 + 0.15 * k_int))
        colcheia = compasso / 8.0
        t = float(seg.get("inicio", 0.0))
        fim = min(t + float(seg.get("dur", 0.0)), dur_s)
        # BREQUE: a música cai antes da tirada e volta com ela. O silêncio
        # antes do punchline é o instrumento mais barato da comédia.
        if seg.get("breque"):
            t += min(0.85, max(0.0, (fim - t) * 0.35))
        while t < fim:
            grau = acordes[c % len(acordes)]
            # --- RITMO. Bumbo no 1, no 3 e na síncope antes do 4; palma no
            # 2 e no 4; chimbal em todas as colcheias, aberto na última --
            # o chimbal aberto no fim do compasso é o que faz a volta do
            # laço soar como decisão e não como emenda.
            for j, g in ((0.0, 1.00), (0.5, 0.85), (0.75, 0.50)):
                por(ritmo, bumbo, t + j * compasso, g * k_bat)
            for j in (0.25, 0.75):
                por(ritmo, palma, t + j * compasso, 0.75 * k_bat)
            for j in range(8):
                por(ritmo, chimbal_ab if j == 7 else chimbal, t + j * colcheia,
                    (0.55 if j % 2 == 0 else 0.32) * k_bat)
            # --- GRAVE. Colcheias na raiz e a quinta no fim do compasso,
            # que é o mínimo que faz um baixo ANDAR em vez de segurar nota.
            for j in range(8):
                semi = grau[0] + (7 if j >= 6 else 0)
                por(grave, _baixo(_TONICA * 2 ** (semi / 12.0) / 4.0,
                                  colcheia * 0.9, sr),
                    t + j * colcheia, (0.9 if j % 2 == 0 else 0.55) * k_int)
            # --- HARMONIA. Arpejo de colcheias, com uma nota trocada de vez
            # em quando para o laço de 4 compassos não ficar óbvio.
            ordem = [0, 1, 2, 1, 2, 1, 0, 1]
            for j, idx in enumerate(ordem):
                if rng.random() < 0.12:
                    continue
                semi = grau[idx] + (12 if rng.random() < 0.18 else 0)
                por(harmonia, _nota(_TONICA * 2 ** (semi / 12.0), colcheia * 2.2, sr),
                    t + j * colcheia, (0.30 if j % 2 else 0.42) * k_int)
            t += compasso
            c += 1

    def _nivelar(bus, alvo):
        x = bus[:n]
        p = float(np.max(np.abs(x)))
        return x * (alvo / p) if p > 1e-6 else x

    # proporção fixa entre as camadas: a harmonia continua sendo a que se
    # ouve, o baixo dá o corpo e a bateria dá o pulso sem virar o assunto
    out = (_nivelar(harmonia, 0.60) + _nivelar(grave, 0.52)
           + _nivelar(ritmo, 0.46))
    # LIMITADOR ANTES do nível final. A tangente arredonda os picos em vez
    # de cortá-los, e é o que permite subir a energia média da trilha sem
    # que o pico suba junto -- "prende sem estourar" é exatamente isto.
    out = np.tanh(out * 0.9) / math.tanh(0.9)
    p = float(np.max(np.abs(out))) or 1.0
    out = (out * (0.8 / p)).astype(np.float32)
    # entrada e saída: a trilha nasce e morre fora do quadro
    fi, fo = int(0.9 * sr), int(1.4 * sr)
    if n > fi + fo:
        out[:fi] *= np.linspace(0, 1, fi)
        out[-fo:] *= np.linspace(1, 0, fo)
    return out


# =====================================================================
# MIXAGEM
# =====================================================================
def _ler_wav(caminho):
    with wave.open(caminho) as w:
        sr, n, larg, canais = (w.getframerate(), w.getnframes(),
                               w.getsampwidth(), w.getnchannels())
        raw = w.readframes(n)
    if larg != 2:
        raise RuntimeError(f"{caminho}: esperava 16 bits, veio {larg * 8}")
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if canais > 1:
        x = x.reshape(-1, canais).mean(axis=1)
    return x, sr


def _escrever_wav(caminho, x, sr=SR):
    x = np.clip(x, -1.0, 1.0)
    with wave.open(caminho, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32000.0).astype("<i2").tobytes())
    return caminho


def _ajustar(x, n):
    """Exatamente n amostras: corta o que sobra, completa o que falta.

    POR QUE (run #15, 29/08): a trilha morreu com "operands could not be
    broadcast together with shapes (486960,) (486720,)" e o vídeo saiu sem
    música, com a falha registrada só numa linha do log. Três comprimentos
    passam por aqui -- a voz, a trilha e a curva de ducking -- e cada um é
    calculado de um jeito (duração x taxa, blocos inteiros de 20ms,
    arredondamento de float). Bater sozinhos é coincidência; 240 amostras
    de diferença, um centésimo de segundo, custaram a trilha inteira."""
    if len(x) == n:
        return x
    if len(x) > n:
        return x[:n]
    return np.pad(x, (0, n - len(x)), mode="edge" if len(x) else "constant")


def _ducking(voz, sr, ataque=0.05, saida=0.32):
    """Ganho 0..1 para a trilha, a partir de onde há voz.

    Envelope com ATAQUE rápido e SAÍDA lenta: a trilha tem que sumir na
    hora em que a fala começa e voltar devagar depois que ela termina. Se
    subir rápido, ela bombeia dentro das pausas entre palavras e o
    resultado chama mais atenção do que a trilha inteira."""
    jan = max(1, int(0.02 * sr))
    n = len(voz) // jan
    if n < 2:
        return np.ones(len(voz), dtype=np.float32)
    blocos = np.abs(voz[:n * jan]).reshape(n, jan).max(axis=1)
    piso = max(blocos.max() * 0.06, 0.01)
    alvo = np.where(blocos > piso, 1.0, 0.0)
    ka = math.exp(-jan / (ataque * sr))
    ks = math.exp(-jan / (saida * sr))
    suave = np.empty(n, dtype=np.float32)
    z = 0.0
    for i, v in enumerate(alvo):
        k = ka if v > z else ks
        z = v + (z - v) * k
        suave[i] = z
    g = 1.0 + (_db(DUCK_DB) - 1.0) * suave
    # np.repeat devolve blocos inteiros: o resto da divisão fica de fora, e
    # a curva sai mais curta que a voz. _ajustar completa com o último valor
    return _ajustar(np.repeat(g, jan), len(voz))


def mixar(voz_wav, eventos, destino, musica=None, dur_s=None, sr=SR):
    """Voz + efeitos + trilha -> um WAV só, que é o que o ffmpeg recebe.

    `musica` é o bloco `musica` do spec (ou None/False para desligar):
        {"estilo": "leve", "bpm": 104, "ganho_db": -21, "url": "..."}
    Com `url` a faixa é lida do disco (job.py baixa); sem ela, sintetizada.

    Devolve o caminho do mix. Falha em qualquer etapa devolve a voz
    original: o vídeo pode sair sem trilha, não pode sair sem voz."""
    try:
        voz, sr_voz = _ler_wav(voz_wav)
    except Exception as e:
        print(f"[sfx] nao consegui ler a voz ({e}); seguindo sem mixagem")
        return voz_wav
    if sr_voz != sr:
        sr = sr_voz
    n = len(voz)
    if dur_s:
        n = max(n, int(dur_s * sr))
    mix = np.zeros(n, dtype=np.float32)
    mix[:len(voz)] += voz

    usados = []
    g_sfx = _db(GANHO_SFX_DB)
    for e in (eventos or []):
        onda = efeito(e.get("nome"))
        if onda is None:
            print(f"[sfx] efeito desconhecido: {e.get('nome')!r}")
            continue
        i = int(max(0.0, float(e.get("t", 0.0))) * sr)
        if i >= n:
            continue
        m = min(len(onda), n - i)
        base = GANHO_BASE.get(str(e.get("nome", "")).strip().lower(), 0.7)
        mix[i:i + m] += onda[:m] * (g_sfx * base * float(e.get("ganho", 1.0)))
        if not e.get("cadencia"):        # a cadência já se anunciou em bloco
            usados.append(f"{e['nome']}@{float(e.get('t', 0)):.1f}s")
    if usados:
        print(f"[sfx] {len(usados)} efeitos: {', '.join(usados)}")

    if musica:
        cfg = musica if isinstance(musica, dict) else {}
        try:
            caminho = cfg.get("arquivo")
            if caminho and os.path.exists(caminho):
                faixa, sr_m = _ler_wav(caminho)
                if sr_m != sr:
                    # reamostragem linear: a trilha é bed, não solo -- o
                    # erro de interpolação some 21 dB abaixo da voz
                    faixa = np.interp(np.arange(n) * sr_m / float(sr),
                                      np.arange(len(faixa)), faixa).astype(np.float32)
                while len(faixa) < n:                    # loop até cobrir
                    faixa = np.concatenate([faixa, faixa])
                faixa = faixa[:n]
                print(f"[musica] faixa do disco: {os.path.basename(caminho)}")
            else:
                segs = cfg.get("segmentos") or None
                faixa = trilha(n / float(sr), cfg.get("estilo", "leve"),
                               float(cfg.get("bpm", BPM_PADRAO)), sr=sr, segmentos=segs)
                if segs:
                    print("[musica] trilha por trecho: "
                          + " -> ".join(s.get("estilo", "leve") for s in segs)
                          + (" (com breque no punchline)"
                             if any(s.get("breque") for s in segs) else ""))
                else:
                    print(f"[musica] trilha sintetizada ({cfg.get('estilo', 'leve')}, "
                          f"{float(cfg.get('bpm', 104.0)):.0f} bpm)")
            g = _db(float(cfg.get("ganho_db", GANHO_MUSICA_DB)))
            duck = _ducking(_ajustar(voz, n), sr)
            mix += _ajustar(faixa, n) * g * _ajustar(duck, n)
        except Exception as e:
            print(f"[musica] falhou ({e}); seguindo sem trilha")

    # LIMITADOR, não normalizador. Escalar a mistura inteira para caber
    # abaixaria a voz sempre que houvesse um efeito alto -- e a voz é o que
    # não pode variar. A tangente só dobra os picos que passariam de 1.
    pico = float(np.max(np.abs(mix))) if len(mix) else 0.0
    if pico > 0.98:
        mix = np.tanh(mix * 0.9) / np.tanh(0.9)
    return _escrever_wav(destino, mix, sr)


if __name__ == "__main__":
    # Demonstração: um wav com todos os efeitos em fila, para ouvir de uma
    # vez o que existe. `python sfx.py [saida.wav]`
    import sys
    saida = sys.argv[1] if len(sys.argv) > 1 else "sfx_demo.wav"
    nomes = ["susto", "thud", "boing", "whoosh", "pop", "plim", "erro",
             "tremido", "passo", "rimshot",
             "clique", "digitar", "notificacao", "chaves", "gole",
             "papel", "louca", "rangido", "caixa"]
    dur = len(nomes) * 1.6 + 2.0
    x = trilha(dur, "leve") * _db(GANHO_MUSICA_DB + 8)
    for i, nm in enumerate(nomes):
        onda = efeito(nm)
        j = int((1.0 + i * 1.6) * SR)
        x[j:j + len(onda)] += onda[:max(0, len(x) - j)] * _db(GANHO_SFX_DB + 6)
    _escrever_wav(saida, x)
    print(f"[ok] {saida}  ({dur:.0f}s)  ordem: {', '.join(nomes)}")
