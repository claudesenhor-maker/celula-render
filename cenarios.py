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

# chave -> (o que é, sinônimos que o roteirista pode escrever,
#           cenários aceitáveis como substituto, em ordem de preferência)
CATALOGO = {
    "rua": {
        "e": "rua de cidade, calçada, prédios baixos",
        "sinonimos": ("calcada", "esquina", "cidade", "fora", "bairro",
                      "ponto", "praca", "avenida"),
        "parecidos": ("comercio", "onibus"),
        "palavras": ("rua", "calcada", "esquina", "andando", "saiu", "sai",
                     "cidade", "bairro", "carro", "moto", "buzina", "praca"),
    },
    "sala": {
        "e": "sala de estar com sofá",
        "sinonimos": ("casa", "estar", "sofa", "tv", "apartamento"),
        "parecidos": ("quarto", "cozinha"),
        "palavras": ("sofa", "televisao", "tv", "novela", "controle",
                     "sala", "casa", "netflix", "visita"),
    },
    "cozinha": {
        "e": "cozinha com fogão, pia e geladeira",
        "sinonimos": ("copa", "fogao", "geladeira", "pia"),
        "parecidos": ("sala", "comercio"),
        "palavras": ("cozinha", "geladeira", "fogao", "panela", "almoco",
                     "janta", "cafe", "comida", "pao", "arroz", "microondas",
                     "louca", "pia"),
    },
    "escritorio": {
        "e": "escritório com mesas e computadores",
        "sinonimos": ("trabalho", "empresa", "servico", "reuniao", "coworking"),
        "parecidos": ("comercio", "sala"),
        "palavras": ("trabalho", "chefe", "reuniao", "email", "planilha",
                     "escritorio", "empresa", "expediente", "curriculo",
                     "computador", "prazo", "salario"),
    },
    "comercio": {
        "e": "loja com balcão de atendimento e maquininha",
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
        "sinonimos": ("cama", "dormir", "sono", "despertador"),
        "parecidos": ("sala", "banheiro"),
        "palavras": ("cama", "dormir", "acordei", "sono", "despertador",
                     "quarto", "travesseiro", "cobertor", "soneca", "pijama"),
    },
    "onibus": {
        "e": "dentro de um ônibus urbano",
        "sinonimos": ("busao", "coletivo", "transporte", "metro", "lotacao"),
        "parecidos": ("rua", "comercio"),
        "palavras": ("onibus", "busao", "passagem", "catraca", "motorista",
                     "ponto", "lotado", "metro", "cobrador", "janela"),
    },
    "banheiro": {
        "e": "banheiro com pia, espelho e box",
        "sinonimos": ("chuveiro", "box", "espelho", "lavabo"),
        "parecidos": ("quarto", "cozinha"),
        "palavras": ("banho", "chuveiro", "banheiro", "espelho", "escova",
                     "toalha", "sabonete", "papel", "descarga", "barba"),
    },
}

PADRAO = "sala"


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
