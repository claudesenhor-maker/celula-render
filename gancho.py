# -*- coding: utf-8 -*-
"""gancho.py -- os tres primeiros segundos, garantidos em codigo.

    (18/09, ordem do dono: *"para os testes locais tente melhorar muito a
    qualidade do gancho, fazendo um barulho alto, uma fala chamativa, uma cena
    de acao; e' obrigatorio pelo menos um desses tres (...) esse e' o nosso
    maior ponto fraco"*.)

A REGRA, EM UMA LINHA
    O primeiro trecho do video tem de ter **pelo menos um** destes tres, e o
    codigo confere antes de renderizar:

      SOM    um efeito ALTO no instante zero -- o ataque dele chega antes do
             onset da voz, que e' lento por natureza;
      FALA   uma fala chamativa -- curta, com uma coisa que se segura, e que
             nao anuncia intencao;
      ACAO   um corpo fazendo alguma coisa que se ve no mudo.

    Faltando os tres, o motor POE o que der (som e acao; fala nao se escreve
    em codigo) e grava o que fez em `spec["gancho"]`. E' a lei 16: o que nao
    pode faltar e' garantia, nao linha de prompt -- prompt o modelo
    desobedece, motor nao.

POR QUE O SOM VEM EM t=0, E NAO JUNTO COM A IMAGEM
    Medida que se repete em todo material serio sobre retencao de video
    curto: o ouvido resolve antes do olho. O som chega primeiro e diz "alguma
    coisa aconteceu" enquanto o quadro ainda esta sendo entendido -- e por
    isso um efeito no frame do corte le como intencao, e nao como acidente.
    Ele ja existia aqui como ideia (GUIA §31.2: *"som no primeiro instante
    (em: 0.02) -- e' a metade do gancho que ninguem ve"*), mas so' no caminho
    do palito, e so' quando o roteirista lembrava de pedir.

E POR QUE ELE PRECISA SER ALTO
    O efeito comum sai em `GANHO_SFX_DB` (-7 dB) vezes o peso do catalogo, o
    que o deixa POR BAIXO da fala de proposito (sfx.GANHO_BASE: *"clique alto
    demais rouba a fala"*). No trecho 0 isso se inverte: nao ha fala anterior
    para roubar, e o que se quer e' exatamente o susto. `GANHO_DO_GANCHO`
    (1,6) poe o pico do efeito acima do da voz. O limitador de `sfx.mixar`
    cuida do resto -- nada estoura.

O QUE ESTE ARQUIVO NAO FAZ
    Nao reescreve fala. Texto e' do roteirista (e no laboratorio, do
    `ferramentas/ideia.py`, que manda a acusacao de volta para o LLM como
    correcao dirigida). Aqui a fala e' MEDIDA e acusada; quem conserta e'
    quem escreve.

O QUE A PESQUISA DE FORA ACRESCENTOU (18/09)
    Tres coisas que o motor ja sabia fazer e nao fazia no cartao:
      1. nada de estabelecimento -- plano aberto no cartao 0 vira fechado
         (o "wide establishing shot" e' citado como uma das causas do tombo
         entre o primeiro e o terceiro segundo);
      2. cara extrema no primeiro quadro -- `neutro` desperdica o unico
         quadro que todo mundo ve;
      3. abrir no meio da acao: quando o spec traz `abrir_no_auge`, o cartao
         de maior impacto vai para a frente (e o resto continua na ordem).
    As duas primeiras sao automaticas; a terceira so' acontece se o spec
    pedir, porque reordenar historia e' decisao de roteiro.

USO
    import gancho
    gancho.garantir(spec)                 # no render (cartao ja chama)
    gancho.medir(spec)                    # so' mede, nao muda nada

    python work/gancho.py serie/spec_serie_01_posto.json ...   # a regua
"""
import json
import os
import re
import sys
import unicodedata

# O catalogo de acoes e' a fonte do que o corpo sabe fazer (lei 11): a lista
# de acoes de impacto sai DE LA, e nao de uma copia aqui.
try:
    from acoes import ACOES_DE_GANCHO, ACOES_DE_INTERACAO
except ImportError:                                            # pragma: no cover
    ACOES_DE_GANCHO = ("susto", "pular", "tropecar", "entrar_correndo", "cair")
    ACOES_DE_INTERACAO = ("high_five", "cutucar", "empurrar", "bater_no_outro")

# =====================================================================
# 1. SOM
# =====================================================================
# O QUAL sai da cena, e nao de um sorteio: o som que nao tem causa na tela e'
# a queixa que o dono ja fez quatro vezes (GUIA §50.2). A tabela vai do mais
# especifico ao mais generico, e o ultimo caso -- `susto` -- e' o unico que
# vale sem causa nenhuma, porque ele E' a reacao de quem esta em cena.
GANHO_DO_GANCHO = 1.6          # acima da fala, so' aqui (ver o cabecalho)
QUANDO = 0.0                   # no instante zero do video

# E ELE SAI NO MESMO NIVEL, QUALQUER QUE SEJA O EFEITO
#
# `sfx.GANHO_BASE` poe cada efeito no seu lugar na mistura, e faz isso muito
# bem: som de COISA (chaves 0,55, papel 0,45, clique 0,42) fica por baixo do
# som de DESENHO (susto e thud em 1,00), porque "clique alto demais rouba a
# fala". No trecho 0 isso trabalha contra o que se quer: com o ganho fixo em
# 1,6, um gancho de `chaves` sairia a 0,88 e um de `susto` a 1,60 -- quase o
# dobro. O mesmo pedido ("um barulho alto") produziria dois videos com
# ganchos de volume diferente, e a diferenca dependeria de qual objeto a cena
# tinha, que e' o mais arbitrario possivel.
#
# Dividindo pelo peso do catalogo, TODO gancho chega ao mesmo nivel. O piso
# de 0,3 no divisor existe para nao multiplicar por cinco um efeito que
# alguem deixe com peso minusculo.
try:
    from sfx import GANHO_BASE as _PESO_SFX
except ImportError:                                            # pragma: no cover
    _PESO_SFX = {}


def ganho_para(nome, nivel=None):
    # `nivel` vem do estilo (`formatos.<estilo>.gancho_ganho`, fonte unica):
    # o cartao precisa de mais que a dupla, medido em 22/09 -- ver `garantir`.
    return round(float(nivel or GANHO_DO_GANCHO)
                 / max(0.3, float(_PESO_SFX.get(nome, 0.7))), 2)

SOM_DA_CENA = (
    # (o que tem de aparecer no cartao, efeito)
    (("cair", "tropecar", "bater_no_outro", "empurrar", "largar_objeto"), "thud"),
    (("pular", "boing"), "boing"),
    (("entrar_correndo", "correr"), "whoosh"),
    (("dinheiro", "nota", "preco", "etiqueta", "caixa", "conta", "boleto"), "caixa"),
    (("celular", "tela", "notificacao", "app", "mensagem"), "notificacao"),
    (("chave", "chaves"), "chaves"),
    (("papel", "documento", "contrato", "sacola"), "papel"),
    (("porta", "rangido"), "rangido"),
    (("erro", "negado", "recusado", "bloqueado"), "erro"),
    (("garrafa", "cachaca", "copo", "xicara", "cerveja", "louca", "prato"), "louca"),
    (("marmita", "comida", "almoco", "janta"), "louca"),
)
SOM_PADRAO = "susto"

# =====================================================================
# 2. FALA
# =====================================================================
# As duas primeiras reguas SAO as do roteirista (`roteirista/reguas.py`,
# calibradas contra o corpus de 88 videos): importadas, nunca copiadas. As
# outras tres sao novas -- elas medem o que nenhuma regua media ainda, que e'
# se a fala CHAMA (grito, pergunta, interjeicao).
_ANUNCIA = None
_NUMERO = None
try:                                                            # pragma: no cover
    _raiz_lab = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _raiz_lab not in sys.path:
        sys.path.insert(0, _raiz_lab)
    from roteirista.reguas import GANCHO_ANUNCIA as _ANUNCIA
    from roteirista.reguas import GANCHO_NUMERO as _NUMERO
except Exception:                                               # noqa: BLE001
    pass

# Fora do laboratorio (o render roda num Action que so' leva `work/`) o
# pacote `roteirista` nao existe. Ai a medida da fala usa so' o que esta
# aqui, e `medir` diz isso em `fala.por` -- medida com regua reduzida e' um
# fato a declarar, nao um detalhe.
_ANUNCIA_RESERVA = re.compile(
    r"^\s*(oi|ol[áa]|e a[ií]|gente|pessoal|hi|hey|hello|guys)\b"
    r"|^\s*(eu\s+)?(quero|preciso|vou|tenho que|vim|i want|i need|i'm going)\b",
    re.IGNORECASE)
_NUMERO_RESERVA = re.compile(r"\d|\b(um|dois|tr[êe]s|dez|vinte|cem|mil|"
                             r"milh[ãa]o|one|two|three|ten|fifty|hundred|"
                             r"thousand|million)\b", re.IGNORECASE)

# GRITO: ponto de exclamacao, palavra inteira em maiusculas (3+ letras) ou
# uma interjeicao de abertura. Nao e' estilo: a fala gritada muda a prosodia
# do TTS (`expressao.prosodia`) e e' ouvida como acontecimento.
_GRITO = re.compile(r"!|\b[A-ZÀ-Ú]{3,}\b")
_INTERJEICAO = re.compile(
    r"^\s*(ei|ai|ui|eita|opa|caramba|socorro|nossa|puta|porra|meu deus|"
    r"n[ãa]o|para|peraí|pera|espera|calma|hey|whoa|oh|damn|what|no way|stop)\b",
    re.IGNORECASE)
_PERGUNTA = re.compile(r"\?")
# O teto de palavras e' o do formato (config.json: gancho_max_palavras = 6),
# com a folga de 3 que o cartao precisa -- uma frase de cartao carrega o
# sujeito ("Pal abasteceu o carro com cachaca") e a do palito nao.
TETO_PALAVRAS_FALA = 9

# O FATO CONCRETO -- e por que ele entrou depois de a regua reprovar tudo
#
# A primeira versao desta medida exigia numero, pergunta, grito ou
# interjeicao, e reprovou a abertura de 10 dos 10 specs de cartao do
# laboratorio -- inclusive as seis da serie minerada, que sao COPIA FIEL de
# Shorts com 400 a 900 mil views. Regua que reprova tudo nao separa nada
# (GUIA §31.1), e aqui ela estava medindo a coisa errada.
#
# O corpus diz qual e' a coisa certa: em `padroes_externos`, o `gancho_tipo`
# mais comum do nicho e' **"afirmacao absurda"** (33 dos 43 classificados,
# mediana de 104 views/hora, 4,0 palavras) -- e "Pal abasteceu o carro com
# cachaca" e' exatamente isso. O que uma afirmacao absurda tem, e uma frase
# morna nao, e' um FATO: uma coisa que da' para ver (objeto, lugar, bicho) e
# um verbo que aconteceu. "Ele estava com um problema" nao tem nenhum dos
# dois; "explodiu uma marmita no micro-ondas" tem os dois.
#
# O absurdo em si NAO E' MEDIVEL aqui, e este arquivo nao finge medir: ele
# credita o fato concreto e deixa a graca para o dono, como sempre (P1).
_CONCRETO = re.compile(
    r"\b(carro|moto|onibus|busao|porta|chave|celular|telefone|marmita|"
    r"comida|almoco|janta|cerveja|cachaca|garrafa|copo|xicara|cafe|bolo|"
    r"frango|galinha|dinheiro|nota|boleto|conta|fatura|cartao|maquininha|"
    r"caixa|sacola|bolsa|mochila|guarda-chuva|sapato|roupa|camisa|cama|"
    r"sofa|geladeira|fogao|micro-ondas|maquina|elevador|escada|janela|"
    r"cachorro|gato|rato|barata|bomba|gasolina|banco|loja|mercado|hospital|"
    r"delegacia|policia|ladrao|chefe|sogra|vizinho|filho|mulher|marido|"
    r"car|door|key|phone|lunch|food|beer|bottle|cup|coffee|money|bill|"
    r"card|box|bag|shoe|bed|fridge|stove|microwave|elevator|dog|cat|rat|"
    r"boss|neighbor|cop|thief)\w*\b", re.IGNORECASE)
# verbo que ACONTECEU: as terminacoes do preterito perfeito (3a pessoa) mais
# os irregulares que o canal usa toda hora. Presente narrativo tambem conta
# ("o forno explode") -- e' como o Madrazzo narra.
_VERBO_FATO = re.compile(
    # `ia` entra pelo imperfeito ("alguem COMIA a marmita"), e ele custa
    # algum falso positivo (dia, familia, energia). No lugar em que esta
    # medida e' usada -- creditar um fato -- o custo e' aceitavel: ela so'
    # conta junto com uma coisa concreta na mesma frase.
    r"\b\w{3,}(ou|eu|iu|aram|eram|iram|ava|iam|ia)\b"
    r"|\b(foi|veio|deu|pos|pos|fez|viu|teve|disse|trouxe|perdeu|quebrou|"
    r"explode|quebra|cai|some|trava|para|vira|chega|entra|sai|paga|cobra|"
    r"morde|bate|joga|pega|leva|traz|abre|fecha|liga|desliga|derruba|"
    r"broke|exploded|lost|paid|charged|hit|dropped|stole|took|left)\b",
    re.IGNORECASE)

# =====================================================================
# 3. ACAO
# =====================================================================
# O que conta como "cena de acao" para o primeiro cartao. As cinco primeiras
# sao as de `acoes.ACOES_DE_GANCHO` (as mesmas que o palito injeta desde
# agosto); as de interacao entram porque um empurrao ou um tapa e' acao pelo
# mesmo criterio -- alguem, vendo no mudo, entende que aconteceu.
ACOES_DE_IMPACTO = frozenset(tuple(ACOES_DE_GANCHO) + tuple(ACOES_DE_INTERACAO)
                             + ("comemorar", "maos_na_cabeca"))
# Poses que NAO sao acao, por mais que o spec as chame de pose: sao posturas
# (lei 35). Um boneco de bracos cruzados no cartao 0 e' um boneco parado.
POSES_PARADAS = frozenset(("parado", "bracos_cruzados", "maos_na_cintura",
                           "mao_no_queixo", "escutar", "neutro", ""))
# A acao injetada quando nao ha nenhuma. `susto` pelo mesmo motivo do
# `garantir_gancho` do motor: e' a unica que qualquer cena justifica.
ACAO_PADRAO = "susto"

EXPRESSOES_FORTES = ("chocado", "desesperado", "bravo", "irritado", "surpreso")


def _limpo(t):
    t = unicodedata.normalize("NFD", str(t or ""))
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


def _texto_do(cartao):
    return str(cartao.get("texto") or cartao.get("fala") or
               cartao.get("salto") or "")


def _primeiro(spec):
    """O primeiro trecho do video, seja spec de cartao ou de palito.

    Devolve (lista, indice, tipo). O indice nem sempre e' 0: um cartao de
    SALTO de tempo ("2 MESES DEPOIS") na frente e' cartela, nao gancho -- se
    o video abre com ele, quem decide o gancho e' o cartao seguinte, e o som
    continua caindo no instante zero.
    """
    cartoes = spec.get("cartoes")
    if isinstance(cartoes, list) and cartoes:
        i = 0
        while i < len(cartoes) - 1 and cartoes[i].get("salto") and not cartoes[i].get("texto"):
            i += 1
        return cartoes, i, "cartao"
    trechos = spec.get("trechos")
    if isinstance(trechos, list) and trechos:
        return trechos, 0, "trecho"
    return None, 0, "vazio"


# =====================================================================
def medir(spec):
    """O que o gancho deste spec TEM, dos tres. Nao muda nada."""
    lista, i, tipo = _primeiro(spec)
    if not lista:
        return {"ok": False, "quantos": 0, "tipo": tipo, "erro": "spec sem trechos"}
    c = lista[i]
    texto = _texto_do(c)

    # -- som ---------------------------------------------------------------
    som = {"tem": False}
    for s in (c.get("sfx") or []):
        nome = s.get("nome") if isinstance(s, dict) else s
        em = float(s.get("em", 0.0)) if isinstance(s, dict) else 0.0
        g = float(s.get("ganho", 1.0)) if isinstance(s, dict) else 1.0
        # so' conta o que cai NO COMECO e e' alto: um `plim` de ganho 0,4 a
        # 1,2 s nao e' gancho, e chamar de gancho seria aprovar o que nao
        # segura ninguem
        if em <= 0.20 and g >= 1.0:
            som = {"tem": True, "nome": nome, "em": em, "ganho": g}
            break

    # -- fala --------------------------------------------------------------
    anuncia = _ANUNCIA or _ANUNCIA_RESERVA
    numero = _NUMERO or _NUMERO_RESERVA
    palavras = len(re.findall(r"\w+", texto))
    porques = []
    if numero.search(texto):
        porques.append("ancora (numero/valor)")
    if _PERGUNTA.search(texto):
        porques.append("pergunta")
    if _GRITO.search(texto):
        porques.append("grito")
    if _INTERJEICAO.search(_limpo(texto)):
        porques.append("interjeicao")
    limpo = _limpo(texto)
    if (_CONCRETO.search(limpo) and _VERBO_FATO.search(limpo)
            and palavras <= TETO_PALAVRAS_FALA):
        porques.append("fato concreto (coisa + verbo que aconteceu)")
    acusacoes = []
    if anuncia.search(texto):
        acusacoes.append("ANUNCIA a intencao ou cumprimenta -- o formato exato "
                         "do gancho fraco (GUIA §31.1)")
    if palavras > TETO_PALAVRAS_FALA:
        acusacoes.append(f"{palavras} palavras: o teto do gancho e' "
                         f"{TETO_PALAVRAS_FALA}")
    if not porques:
        acusacoes.append("nao tem fato concreto, numero, pergunta, grito nem "
                         "interjeicao: nao ha o que segurar")
    fala = {"tem": bool(porques) and not acusacoes, "texto": texto,
            "palavras": palavras, "por": porques, "acusacoes": acusacoes,
            "regua": "roteirista.reguas" if _ANUNCIA else "reserva local"}

    # -- acao --------------------------------------------------------------
    acao = {"tem": False}
    if tipo == "cartao":
        for a in (c.get("atores") or []):
            poses = a.get("poses") or ([a.get("pose")] if a.get("pose") else [])
            for p in poses:
                if str(p or "") in ACOES_DE_IMPACTO:
                    acao = {"tem": True, "nome": p, "quem": a.get("quem")}
                    break
            if acao["tem"]:
                break
    else:
        for a in (c.get("acoes") or []):
            if (str(a.get("nome") or "") in ACOES_DE_IMPACTO
                    and float(a.get("de", 0.0)) <= 0.15):
                acao = {"tem": True, "nome": a.get("nome"), "quem": c.get("ator")}
                break

    quantos = sum(1 for x in (som, fala, acao) if x["tem"])
    return {"ok": quantos >= 1, "quantos": quantos, "tipo": tipo, "indice": i,
            "som": som, "fala": fala, "acao": acao, "texto": texto}


# =====================================================================
def _som_para(cartao):
    """Qual efeito esta cena justifica."""
    alvo = _limpo(json.dumps(cartao, ensure_ascii=False))
    for chaves, efeito in SOM_DA_CENA:
        if any(k in alvo for k in chaves):
            return efeito
    return SOM_PADRAO


def garantir(spec, falar=print):
    """Poe no primeiro trecho o que faltar, e devolve a medida final.

    Tres regras de convivencia, e cada uma existe porque a alternativa ja deu
    errado neste projeto:

      1. `gancho_forte: false` no spec desliga tudo (a mesma chave que
         `acoes.garantir_gancho` respeita desde 29/08): um episodio escrito
         para abrir parado nao pode levar um susto que nada justifica -- e' a
         lei 34, o codigo desmentindo o pedido;
      2. o que o roteiro JA escreveu nunca e' trocado. Faltando, poe-se; tendo,
         deixa-se;
      3. mesmo com um dos tres presente, o SOM entra -- ele e' o mais barato
         dos tres e o unico que nao disputa espaco com nada na tela. Dois
         canais no primeiro segundo e' o que a pesquisa de fora chama de
         "corte intencional"; um so' e' o minimo que o dono pediu.
    """
    if spec.get("gancho_forte") is False:
        falar("[gancho] spec pede abertura parada; garantia desligada")
        return medir(spec)
    lista, i, tipo = _primeiro(spec)
    if not lista:
        return medir(spec)
    c = lista[i]
    antes = medir(spec)
    posto = []

    # -- 1. SOM, sempre (regra 3) -----------------------------------------
    #
    # O NIVEL E' DO ESTILO (22/09). A regua de gancho compara a energia dos 3
    # primeiros segundos com a dos 12 seguintes, e pede 1,15. A dupla passa
    # folgada (mediana 1,63); a COPIA raspava -- 5 de 20 reprovaram entre 1,12
    # e 1,14 --, porque ela troca de tela a cada 2 s e o resto do video e' um
    # corte atras do outro, com cama de musica por baixo. O mesmo efeito, no
    # mesmo instante, precisa de mais nivel para se destacar do que vem
    # depois. O numero vive em `formatos.<estilo>.gancho_ganho`.
    nivel = float((spec.get("regra_estilo") or {}).get("gancho_ganho")
                  or GANHO_DO_GANCHO)
    if not antes["som"]["tem"] and spec.get("gancho_som") is not False:
        nome = _som_para(c)
        g = ganho_para(nome, nivel)
        c.setdefault("sfx", [])
        c["sfx"] = [{"nome": nome, "em": QUANDO, "ganho": g,
                     "gancho": True}] + list(c["sfx"])
        posto.append(f"som '{nome}' em t=0, ganho {g} "
                     f"(nivel {GANHO_DO_GANCHO} no mix)")

    # -- 2. ACAO ------------------------------------------------------------
    # Ela entra em dois casos, e a diferenca entre eles importa:
    #
    #   a) o gancho estaria VAZIO sem ela (nenhum dos tres). Ai entra de
    #      qualquer jeito, no ator que houver;
    #   b) o ator do primeiro cartao esta numa POSTURA (bracos cruzados, mao
    #      na cintura, escutar, ou pose nenhuma). Postura no cartao 0 nao e'
    #      uma escolha de encenacao, e' a ausencia de uma -- e o unico quadro
    #      que todo mundo ve fica com um boneco parado de bracos cruzados.
    #
    # O QUE ELA NUNCA TOCA: pose com `alvos` (a mao esta indo a um lugar
    # medido, por IK), com `objeto` na mao (o objeto E' a cena), `sentar` ou
    # `atras_de` (o corpo esta preso a um prop) -- e qualquer pose que nao
    # seja postura, que e' encenacao que alguem escolheu.
    def _mexivel(a):
        return not (a.get("alvos") or a.get("objeto") or a.get("sentar")
                    or a.get("atras_de"))

    vazio = not (antes["fala"]["tem"] or antes["som"]["tem"] or antes["acao"]["tem"])
    if not antes["acao"]["tem"]:
        if tipo == "cartao":
            atores = c.get("atores") or []
            parados = [a for a in atores
                       if str(a.get("pose") or "") in POSES_PARADAS and _mexivel(a)]
            if parados:
                alvo = parados[0]
                alvo["pose"] = ACAO_PADRAO
                posto.append(f"acao '{ACAO_PADRAO}' em {alvo.get('quem')} "
                             f"(estava em postura)")
            elif vazio and atores:
                # sem ninguem livre e sem nenhum canal: o objeto na mao vira o
                # que a cena mostra, que e' a acao mais forte que sobra
                alvo = atores[0]
                alvo["pose"] = "mostrar_objeto" if alvo.get("objeto") else ACAO_PADRAO
                posto.append(f"acao '{alvo['pose']}' em {alvo.get('quem')}")
        else:
            if vazio or not (c.get("acoes") or []):
                c["acoes"] = [{"nome": ACAO_PADRAO, "de": 0.0, "ate": 0.42,
                               "forca": 1.0,
                               "motivo": "gancho: o trecho 0 abria sem acao"}] \
                             + list(c.get("acoes") or [])
                posto.append(f"acao '{ACAO_PADRAO}'")

    # -- 3. os acabamentos que a pesquisa cobra ----------------------------
    # CARA EXTREMA: abrir em `neutro` gasta o unico quadro que todos veem.
    if tipo == "cartao":
        for a in (c.get("atores") or []):
            if not a.get("expressao") or a.get("expressao") == "neutro":
                a["expressao"] = EXPRESSOES_FORTES[0]
                posto.append(f"expressao '{EXPRESSOES_FORTES[0]}' em {a.get('quem')}")
        # NADA DE ESTABELECIMENTO: plano aberto no cartao 0 e' o "wide
        # establishing shot" que a literatura de retencao aponta como causa
        # do tombo do primeiro para o terceiro segundo. `_janela` reabre o
        # zoom sozinho se as placas nao couberem -- entao pedir fechado aqui
        # nao corta nada, so' aproxima o que da' para aproximar.
        if str(c.get("plano") or "aberto") == "aberto":
            c["plano"] = "medio"
            posto.append("plano 'aberto' -> 'medio'")
    else:
        if str(c.get("enquadramento") or "") in ("plano aberto", ""):
            c["enquadramento"] = "primeiro plano"
            posto.append("enquadramento -> 'primeiro plano'")
        if not c.get("expressao") or c.get("expressao") == "neutro":
            c["expressao"] = EXPRESSOES_FORTES[0]
            posto.append(f"expressao '{EXPRESSOES_FORTES[0]}'")

    depois = medir(spec)
    depois["posto_pelo_motor"] = posto
    # A FICHA TECNICA. O mesmo que o palito faz com `gancho_acao`/`gancho_sfx`
    # (GUIA §31.4): sem isto, daqui a um mes ninguem sabe se aquele video
    # abriu com som porque o roteiro pediu ou porque o motor pos -- e ai a
    # comparacao entre os dois vira anedota.
    spec["gancho"] = {
        "som": depois["som"].get("nome") if depois["som"]["tem"] else None,
        "acao": depois["acao"].get("nome") if depois["acao"]["tem"] else None,
        "fala": depois["fala"]["por"],
        "canais": depois["quantos"],
        "posto_pelo_motor": posto,
    }
    if posto:
        falar("[gancho] " + "; ".join(posto))
    falar(f"[gancho] {depois['quantos']}/3 canais no trecho {depois['indice']}: "
          f"som={'sim' if depois['som']['tem'] else 'nao'} "
          f"fala={'sim' if depois['fala']['tem'] else 'nao'} "
          f"acao={'sim' if depois['acao']['tem'] else 'nao'}")
    for a in depois["fala"]["acusacoes"]:
        falar(f"[gancho] a fala de abertura: {a}")
    if not depois["ok"]:
        falar("[gancho] ! NENHUM dos tres canais -- o video abre fraco de "
              "proposito ou o spec nao tem onde por")
    return depois


# =====================================================================
def abrir_no_auge(spec, falar=print):
    """Poe na frente o cartao de maior impacto (a abertura fria do modo
    cartao). So' roda quando o spec pede `abrir_no_auge: true`.

    E' o mesmo recurso do §31.3 -- "o que aconteceu aqui?" em vez de "sobre o
    que e' isso?" -- com as mesmas guardas de la, traduzidas para cartao:
    nunca o remate (entregar a virada na abertura queima a unica coisa que o
    video tem para dar no fim), nunca um cartao de salto, e o escolhido e'
    COPIADO para a frente, nao movido: a historia continua inteira, e o
    espectador reencontra a cena sabendo o que ela significa.
    """
    if not spec.get("abrir_no_auge"):
        return spec
    cartoes = spec.get("cartoes") or []
    if len(cartoes) < 5:
        falar("[gancho] abertura no auge pedida, mas o video tem menos de 5 "
              "cartoes: ignorada")
        return spec
    # A QUINTA GUARDA, e ela e' a que faltava (18/09, medida)
    #
    # Rodado sobre tres specs, o recorte melhorou os dois longos (o soco na
    # cara do posto; o "Depois de quatro anos? Tu foi roubado." da rescisao) e
    # PIOROU o curto: num video de 10 cartoes o auge de verdade e' o remate,
    # que esta fora do recorte por regra, e o que sobrou foi "Eu... nao tenho
    # dinheiro" na frente de um "A marmita explodiu no micro-ondas!" que ja
    # era um gancho de tres canais.
    #
    # Abertura fria e' uma TROCA -- ela custa ~2 s e o direito de abrir pela
    # primeira fala (GUIA §31.6). Fazer a troca quando o gancho atual ja tem
    # dois dos tres canais e' pagar para piorar.
    ja = medir(spec)
    if ja["quantos"] >= 2:
        falar(f"[gancho] abertura no auge pedida, mas o primeiro cartao ja tem "
              f"{ja['quantos']}/3 canais (\"{ja['texto'][:40]}\"): mantida a "
              f"abertura que existe")
        return spec
    # o auge e' medido, nao escolhido: o cartao com mais sinal de impacto no
    # meio do video (o ultimo terco e' remate e fica de fora)
    fim = int(len(cartoes) * 0.8)
    melhor, nota_melhor = None, 0.0
    for j, c in enumerate(cartoes[1:fim], start=1):
        if c.get("salto"):
            continue
        n = 0.0
        alvo = _limpo(json.dumps(c, ensure_ascii=False))
        for a in (c.get("atores") or []):
            if str(a.get("pose") or "") in ACOES_DE_IMPACTO:
                n += 2.0
        n += 1.0 * len(c.get("sfx") or [])
        if any(k in alvo for k in ("chocado", "desesperado", "bravo")):
            n += 0.5
        if n > nota_melhor:
            melhor, nota_melhor = j, n
    if melhor is None:
        falar("[gancho] abertura no auge: nenhum cartao com impacto medivel")
        return spec
    recorte = json.loads(json.dumps(cartoes[melhor]))
    recorte["flash"] = True
    recorte["nao_desdobrar"] = True
    spec["cartoes"] = [recorte] + cartoes
    falar(f"[gancho] abertura no auge: o cartao {melhor} (\"{_texto_do(recorte)[:40]}\") "
          f"foi copiado para a frente; a historia segue inteira depois dele")
    return spec


# =====================================================================
if __name__ == "__main__":
    # A REGUA: mede os specs passados na linha de comando e diz o que cada um
    # tem de gancho, sem mexer em nada. E' como a calibracao foi feita.
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(0)
    print(f"{'spec':38} {'canais':>6}  som / fala / acao")
    print("-" * 78)
    for caminho in sys.argv[1:]:
        try:
            spec = json.load(open(caminho, encoding="utf-8-sig"))
        except Exception as e:                                  # noqa: BLE001
            print(f"{os.path.basename(caminho):38} ! {e}")
            continue
        m = medir(spec)
        if not m.get("som"):
            print(f"{os.path.basename(caminho):38} ! {m.get('erro')}")
            continue
        print(f"{os.path.basename(caminho):38} {m['quantos']:>4}/3  "
              f"{'S' if m['som']['tem'] else '-'} / "
              f"{'F' if m['fala']['tem'] else '-'} / "
              f"{'A' if m['acao']['tem'] else '-'}   "
              f"\"{m['texto'][:40]}\"")
        for a in m["fala"]["acusacoes"]:
            print(f"{'':38}        fala: {a}")
