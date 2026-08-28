#!/usr/bin/env python3
"""
cenarios — que fundo combina com a fala, e o que fazer quando ele falta.

O DEFEITO QUE ORIGINOU ESTE ARQUIVO (visto no vídeo de 28/08)
    A história se passava numa padaria. Três dos quatro trechos pediam o
    cenário `comercio`, que ninguém tinha gerado ainda: `palito_cutout`
    não achou a arte, caiu na cor chapada `#A5A893` e o vídeo passou 19
    dos 24 segundos sobre um retângulo verde-acinzentado, enquanto o texto
    falava de maquininha de cartão e fila. O último trecho, esse sim, tinha
    arte -- e mostrava uma RUA, com o personagem contando que estava dentro
    da loja.

    Duas falhas diferentes com o mesmo sintoma:

      1. a arte não existia (agora existe: oito cenários no bucket);
      2. o motor tratava "não achei" como situação normal, imprimia uma
         linha de log e seguia. Fundo chapado é o último recurso; ele não
         pode ser o primeiro que se encontra pela frente.

    Este módulo resolve a segunda. Nunca mais se cai em cor chapada tendo
    QUALQUER cenário na mão: pede-se `padaria`, chega-se em `comercio`;
    pede-se `comercio` sem tê-lo, chega-se em `cozinha` (o interior mais
    parecido que existe) antes de chegar-se em cor nenhuma.

O CATÁLOGO É FECHADO, DE PROPÓSITO
    As oito chaves aqui são exatamente as que o nó "Montar Pedidos" do
    workflow `nrSxcnZLEH5xoLlt` manda gerar. Quem escreve o roteiro escolhe
    de uma lista fechada; inventar `padaria` como nona chave produziria
    exatamente o vídeo de 28/08 de novo. `normalizar()` existe justamente
    para que a palavra que o roteirista pensou (padaria, mercado,
    trabalho) caia na chave que tem arte.
"""

# A LINHA DO CHÃO (`chao`), em fração da altura do quadro
# ---------------------------------------------------------------------
# É onde os pés do personagem pousam. Sem ela o motor punha todo mundo na
# mesma altura fixa do rig (78% do quadro com dois em cena) e a arte tinha
# o chão em qualquer lugar entre 65% e 90% -- na sala a diferença chegava a
# 192px, e o resultado é o que o dono do projeto viu em 28/08: "os
# personagens parecem que estão flutuando".
#
# POR QUE ISTO É ANOTADO E NÃO MEDIDO. Três detectores automáticos foram
# tentados e os três erraram em pelo menos metade dos oito cenários: cor
# dominante do piso (tábua listrada não tem cor dominante), densidade de
# borda vertical (ladrilho tem borda vertical) e estabilidade da linha
# (carpete é tão estável quanto parede lisa). É a mesma conclusão a que o
# projeto já tinha chegado para o pivô: medida que é UMA por asset e dura
# para sempre se anota, não se adivinha. A régua é
# `ferramentas/regua_chao.py`, e ler o número leva trinta segundos.
#
# O VALOR FICA ABAIXO DE TODO MÓVEL, não no encontro entre parede e chão.
# Esta é a correção de 28/08 à noite, e ela veio de um erro: os primeiros
# valores (0,80 a 0,90) miravam a linha parede-chão, e o personagem saiu de
# pé EM CIMA da mesa de centro. O gerador de cenário oscila entre deixar o
# primeiro plano limpo e mobiliá-lo -- foram três levas de arte e as três
# vezes ele voltou a pôr sofá, balcão ou mesa na frente --, e o motor não
# tem plano de profundidade para resolver isso: o personagem é sempre
# desenhado por cima de uma imagem só.
#
# Então o chão é a faixa de piso LIVRE que sobra na frente de tudo, que
# nestas artes fica entre 90% e 96%. O personagem passa a ficar claramente
# na frente dos móveis, que é a leitura certa, e a cabeça ainda cai por
# volta da metade do quadro -- sobra cenário em cima, que era o objetivo.
#
# Vale igual na arte e na tira: o motor cobre a arte para 1920 de altura e
# todo cenário é mais largo que 9:16, então a altura entra inteira e não há
# corte vertical para deslocar a conta.
CHAO_PADRAO = 0.93

# chave -> (o que é, sinônimos que o roteirista pode escrever,
#           cenários aceitáveis como substituto, em ordem de preferência,
#           e a linha do chão)
CATALOGO = {
    "rua": {
        "e": "rua de cidade, calçada, prédios baixos",
        "chao": 0.90,
        "sinonimos": ("calcada", "esquina", "cidade", "fora", "bairro",
                      "ponto", "praca", "avenida"),
        "parecidos": ("comercio", "onibus"),
        "palavras": ("rua", "calcada", "esquina", "andando", "saiu", "sai",
                     "cidade", "bairro", "carro", "moto", "buzina", "praca"),
    },
    "sala": {
        "e": "sala de estar com sofá",
        "chao": 0.95,
        "sinonimos": ("casa", "estar", "sofa", "tv", "apartamento"),
        "parecidos": ("quarto", "cozinha"),
        "palavras": ("sofa", "televisao", "tv", "novela", "controle",
                     "sala", "casa", "netflix", "visita"),
    },
    "cozinha": {
        "e": "cozinha com fogão, pia e geladeira",
        "chao": 0.92,
        "sinonimos": ("copa", "fogao", "geladeira", "pia"),
        "parecidos": ("sala", "comercio"),
        "palavras": ("cozinha", "geladeira", "fogao", "panela", "almoco",
                     "janta", "cafe", "comida", "pao", "arroz", "microondas",
                     "louca", "pia"),
    },
    "escritorio": {
        "e": "escritório com mesas e computadores",
        "chao": 0.95,
        "sinonimos": ("trabalho", "empresa", "servico", "reuniao", "coworking"),
        "parecidos": ("comercio", "sala"),
        "palavras": ("trabalho", "chefe", "reuniao", "email", "planilha",
                     "escritorio", "empresa", "expediente", "curriculo",
                     "computador", "prazo", "salario"),
    },
    "comercio": {
        "e": "loja com balcão de atendimento e maquininha",
        "chao": 0.95,
        "sinonimos": ("loja", "padaria", "mercado", "supermercado", "caixa",
                      "balcao", "farmacia", "banco", "fila", "atendimento"),
        "parecidos": ("escritorio", "cozinha"),
        "palavras": ("loja", "padaria", "mercado", "caixa", "fila",
                     "maquininha", "cartao", "senha", "troco", "pix",
                     "atendente", "compra", "preco", "pagar", "balcao",
                     "farmacia", "banco", "cupom", "desconto"),
    },
    "quarto": {
        "e": "quarto com cama e criado-mudo",
        "chao": 0.93,
        "sinonimos": ("cama", "dormir", "sono", "despertador"),
        "parecidos": ("sala", "banheiro"),
        "palavras": ("cama", "dormir", "acordei", "sono", "despertador",
                     "quarto", "travesseiro", "cobertor", "soneca", "pijama"),
    },
    "onibus": {
        "e": "dentro de um ônibus urbano",
        "chao": 0.93,
        "sinonimos": ("busao", "coletivo", "transporte", "metro", "lotacao"),
        "parecidos": ("rua", "comercio"),
        "palavras": ("onibus", "busao", "passagem", "catraca", "motorista",
                     "ponto", "lotado", "metro", "cobrador", "janela"),
    },
    "banheiro": {
        "e": "banheiro com pia, espelho e box",
        "chao": 0.90,
        "sinonimos": ("chuveiro", "box", "espelho", "lavabo"),
        "parecidos": ("quarto", "cozinha"),
        "palavras": ("banho", "chuveiro", "banheiro", "espelho", "escova",
                     "toalha", "sabonete", "papel", "descarga", "barba"),
    },
}

PADRAO = "sala"


def chao_de(chave):
    """A linha do chão de um cenário, em fração da altura do quadro.

    Cenário gerado sob demanda ainda não tem número anotado: cai no
    `CHAO_PADRAO`, que é a mediana dos oito. Errar por 3% põe o pé um pouco
    dentro ou um pouco fora do piso; errar por 10% é o boneco flutuando."""
    return float((CATALOGO.get(normalizar(chave)) or {}).get("chao",
                                                             CHAO_PADRAO))


def _limpo(s):
    """Sem acento, minúsculo. O roteirista escreve `comércio` e o nome do
    arquivo no bucket é `comercio` -- comparar sem normalizar transformaria
    um acento em fundo verde."""
    tabela = str.maketrans("áàâãäéèêëíìîïóòôõöúùûüçñ", "aaaaaeeeeiiiiooooouuuucn")
    return str(s or "").strip().lower().translate(tabela)


_SINONIMO = {}
for _chave, _d in CATALOGO.items():
    _SINONIMO[_chave] = _chave
    for _s in _d["sinonimos"]:
        _SINONIMO[_limpo(_s)] = _chave


def normalizar(nome):
    """O que o roteirista escreveu -> chave do catálogo. `padaria` vira
    `comercio`. Nome desconhecido volta como veio: quem chama decide se
    cai no padrão ou avisa, e a diferença importa (ver `resolver`)."""
    n = _limpo(nome).replace(" ", "_").replace("-", "_")
    return _SINONIMO.get(n, n)


def escolher(fala, padrao=PADRAO):
    """O cenário que a FALA pede, por palavra-chave.

    Existe para dois casos: um spec antigo que não traz `cenario` nenhum, e
    conferência local de roteiro antes de gastar render. Não substitui a
    escolha do roteirista -- que enxerga a história inteira e sabe que a
    piada da fila de banco acontece no comércio mesmo quando a palavra
    'banco' não aparece."""
    # comparação por PREFIXO de palavra: "maquininha" tem que casar com
    # "maquininhas", e "pao" NÃO pode casar com "campeao". Substring solta
    # (a primeira versão) fazia exatamente isso.
    palavras = [_limpo(p).strip(".,!?;:()\"'") for p in str(fala or "").split()]
    melhor, pontos = padrao, 0
    for chave, d in CATALOGO.items():
        p = sum(1 for w in d["palavras"]
                for t in palavras if t == w or (len(t) > 3 and t.startswith(w)))
        if p > pontos:
            melhor, pontos = chave, p
    return melhor


def resolver(pedido, disponiveis, fala=None):
    """A melhor chave DISPONÍVEL para o que foi pedido.

    `disponiveis` é o conjunto de cenários que existem de fato (o motor
    passa o que achou em disco). A ordem de tentativa:

      1. o pedido, normalizado  -- `padaria` -> `comercio`
      2. os `parecidos` dele    -- interior por interior, rua por rua
      3. o que a fala sugerir   -- último palpite com alguma informação
      4. `sala`, e depois qualquer um

    Devolve (chave, motivo). O motivo entra no log: quando o cenário sai
    diferente do que o roteiro pediu, isso tem que aparecer, senão vira o
    silêncio que escondeu o fundo verde por duas sessões.
    """
    disp = {_limpo(d) for d in (disponiveis or ())}
    if not disp:
        return None, "nenhum cenario disponivel"

    alvo = normalizar(pedido)
    if alvo in disp:
        return alvo, "pedido" if _limpo(pedido) == alvo else f"sinonimo de '{pedido}'"

    for p in CATALOGO.get(alvo, {}).get("parecidos", ()):
        if p in disp:
            return p, f"'{pedido}' nao existe; o mais parecido e '{p}'"

    if fala:
        sug = escolher(fala, padrao=None)
        if sug and sug in disp:
            return sug, f"'{pedido}' nao existe; a fala sugere '{sug}'"

    if PADRAO in disp:
        return PADRAO, f"'{pedido}' nao existe; caindo no padrao"
    qualquer = sorted(disp)[0]
    return qualquer, f"'{pedido}' nao existe; usando o unico que ha ('{qualquer}')"


def url_padrao(chave, bucket=None):
    """URL do cenário no bucket público, para o job.py baixar quando o spec
    citar o nome e não a URL. O caminho é o BRUTO de propósito: o rembg
    destrói cenário (ver HANDOFF §6.2), e fundo não precisa de alfa."""
    base = bucket or ("https://fejivjwyadbawjdhldbj.supabase.co"
                      "/storage/v1/object/public/toonzueira")
    return f"{base}/assets_bruto/cenario/geral/{normalizar(chave)}.jpg"


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        fala = " ".join(sys.argv[1:])
        print(f"{escolher(fala)}   <- {fala!r}")
    else:
        for c, d in CATALOGO.items():
            print(f"{c:11s} {d['e']}")
