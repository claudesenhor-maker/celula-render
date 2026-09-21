# -*- coding: utf-8 -*-
"""para_cartao.py -- o MESMO roteiro da esteira, no estilo CARTAO.

    (18/09, ordem do dono: *"suba esse novo estilo para producao em paralelo
    com o que ja esta (...) no comeco faca um video em cada estilo"*.)

POR QUE CONVERTER O SPEC EM VEZ DE ESCREVER OUTRO ROTEIRO
    O modo cartao (GUIA §54-58) e' um MOTOR de render, nao um roteirista. Ele
    pede uma lista de cartoes; a esteira produz uma lista de trechos. As duas
    listas dizem a mesma coisa -- uma fala, quem fala, onde, com que gesto e
    que objeto na mao --, so' que o trecho e' uma janela de TEMPO e o cartao
    e' um QUADRO.
    Converter tem duas vantagens sobre escrever um roteirista novo:

      1. o experimento fica limpo. Os dois videos do dia saem do MESMO
         roteiro, do mesmo motor comico, do mesmo conceito -- muda so' o
         estilo visual. Se um retiver mais que o outro, a diferenca e' o
         estilo, e nao "o texto daquele dia estava melhor". Um roteirista
         novo mudaria as duas coisas de uma vez, que e' o erro que o §31.9 ja
         registrou;
      2. ela existe HOJE. O roteiro narrado de 45-60 s (o formato do
         Madrazzo, com narrador, saltos de tempo e quem sabe) e' o
         `PLANO-MADRAZZO` A1-A10: cinco dias de trabalho em nos do n8n. O
         estilo visual nao precisa esperar por ele.

    O que esta conversao NAO faz, e esta' dito para ninguem se enganar: ela
    nao produz o formato `historia_narrada`. Ela produz a esquete de 20-28 s
    do canal, contada em cartoes -- corte a cada ~2,5 s, placa com o dado na
    tela, close em quem fala. O formato narrado entra depois, por cima disto.

O QUE ELA APROVEITA DO TRECHO
    | trecho (palito)        | cartao                                        |
    |------------------------|-----------------------------------------------|
    | `fala` + `ator`        | `texto` + `ator` (sem ator = narracao)        |
    | `acoes[]` (janelas)    | `pose` -- a acao que mais dura, que no cartao |
    |                        | e' o quadro inteiro                           |
    | `acoes[].objeto`       | `objeto` na mao do falante                    |
    | `expressao`/`expressoes`| `expressao`                                  |
    | `cenario`              | `fundo: cenario:<nome>`, so' quando MUDA      |
    | `enquadramento`        | `plano` (close/medio/aberto)                  |
    | `sfx[]`                | `sfx[]`, igual                                |
    | valor em dinheiro na fala | `placas[]` -- o dado na tela, que e' o que |
    |                        | o estilo cartao tem e a cena continua nao tem |

USO
    import para_cartao
    spec_cartao = para_cartao.converter(spec)     # nao altera o original
"""
import copy
import json
import re
import unicodedata

# A REGRA DO ESTILO vem do `config.json`, por `config_gerado.py` (18/09, §62):
# respiro, legenda, loudnorm, cadencia e a placa sao numeros de FORMATO, e
# formato mora num lugar so'. Sem o arquivo gerado (um repo de render
# desatualizado, por exemplo) o conversor segue com os mesmos valores, para
# nao parar producao por causa de configuracao -- e diz isso no log.
try:
    from config_gerado import formato_de as _formato_de
    _TEM_CONFIG = True
except ImportError:                                            # pragma: no cover
    _TEM_CONFIG = False

    def _formato_de(_estilo=None):
        return {}


PADRAO = {
    "pausa_trecho_s": 0.3, "pausa_punch_s": 0.5, "legenda_palavras": 1,
    "placa_a_cada": 3, "cenario_lavado": 0.42, "fundo": "#F4EFE4",
    "loudnorm": "loudnorm=I=-13:LRA=13:TP=-1.0",
    "max_palavras_cartao": 9, "cadencia_teto_s": 4.0,
}


def regra(estilo="cartao"):
    """A regra do estilo, com os padroes de reserva por baixo."""
    f = dict(PADRAO)
    f.update({k: v for k, v in (_formato_de(estilo) or {}).items()
              if v is not None})
    return f

# Quantos cartoes seguidos podem repetir o mesmo fundo antes de valer a pena
# repetir a marca `fundo` (o cartao herda o anterior quando ela falta).
# ---------------------------------------------------------------------
# de enquadramento do palito para plano do cartao
PLANO = {
    "close": "close", "plano detalhe": "close", "primeiro plano": "close",
    "plano medio": "medio", "plano médio": "medio",
    "plano aberto": "aberto",
}
# As poses que valem como pose de cartao sao as do catalogo do motor -- a
# lista nao se escreve aqui (lei 11). O que se decide aqui e' a PREFERENCIA
# quando o trecho tem varias acoes: a que ocupa mais tempo e' a que o olho
# associa aquela fala.
POSE_DE_FALA = "gesticular"
POSE_DE_ESCUTA = "escutar"

# O VALOR VIRA PLACA. E' a unica coisa que o estilo cartao acrescenta ao
# roteiro, e ela nao e' invencao: o `detalhe_concreto` do Planejamento (valor,
# prazo, estrago) e' justamente o que o Madrazzo poe na tela
# (`PLANO-MADRAZZO` §0 e A5). Aqui ele e' LIDO da fala, nao inventado.
#
# O VALOR POR EXTENSO TAMBEM CONTA, e essa foi a correcao que a prova pediu:
# rodada sobre quatro specs de producao, a regex de digitos achou ZERO valores
# -- porque o roteirista do canal escreve "trinta mil", "quarenta e cinco
# reais", "dois e cinquenta". O numero por extenso e' o normal aqui (a propria
# regua de gancho conta numero por extenso como ancora desde 09/09), e uma
# placa que so' reconhece "R$ 30.000" nunca apareceria em video nenhum.
_EXT = (r"(?:um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|onze|"
        r"doze|treze|quatorze|catorze|quinze|dezesseis|dezessete|dezoito|"
        r"dezenove|vinte|trinta|quarenta|cinquenta|sessenta|setenta|oitenta|"
        r"noventa|cem|cento|duzentos|trezentos|quatrocentos|quinhentos|mil)")
VALOR = re.compile(
    r"(R\$\s?\d[\d\.,]*"                       # R$ 30,00
    r"|\$\s?\d[\d\.,]*"                        # $45
    r"|\b\d[\d\.,]*\s?(?:reais|real|conto|contos|pila|dolares|dollars|bucks|mil)\b"
    r"|\b" + _EXT + r"(?:\s+e\s+" + _EXT + r")*"
    r"\s+(?:mil\s+)?(?:reais|real|conto|contos|pila|mil)\b"    # trinta mil reais
    r"|\b" + _EXT + r"\s+mil\b)",                              # trinta mil
    re.IGNORECASE)
PLACA_A_CADA = 3          # no maximo uma placa a cada tres cartoes


def _limpo(t):
    t = unicodedata.normalize("NFD", str(t or ""))
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


def _pose_do_trecho(tr):
    """A acao que mais dura no trecho -- ela e' a pose do cartao."""
    melhor, maior = None, -1.0
    for a in (tr.get("acoes") or []):
        nome = str(a.get("nome") or "").strip()
        if not nome:
            continue
        dur = float(a.get("ate", 1.0)) - float(a.get("de", 0.0))
        # acao de LOCOMOCAO nao e' pose: no cartao ninguem anda, e um
        # `andar` congelado e' um boneco de perna aberta no meio do quadro
        if nome in ("andar", "entrar_andando", "sair_andando", "aproximar",
                    "afastar", "virar"):
            dur -= 0.5
        if dur > maior:
            melhor, maior = nome, dur
    return melhor


def _objeto_do_trecho(tr):
    for a in (tr.get("acoes") or []):
        if a.get("objeto"):
            return str(a["objeto"])
    if tr.get("objeto"):
        return str(tr["objeto"])
    return None


def _expressao(tr):
    if tr.get("expressoes"):
        e = tr["expressoes"][0]
        nome = e.get("nome") or e.get("valor")
        if nome:
            return str(nome)
    return str(tr.get("expressao") or "neutro")


def _quem_contracena(spec):
    """Quem fala mais, em ordem -- o primeiro e' o protagonista da cena.

    O palito decide quem esta em cena trecho a trecho (`_em_cena`); o cartao
    pede a lista pronta. Dois em cena e' a lei 10, e aqui ela e' aplicada
    escolhendo os DOIS que mais falam: um elenco de quatro num spec sai com
    os dois que carregam a esquete, e nao com os dois primeiros do dicionario.
    """
    conta = {}
    for tr in (spec.get("trechos") or []):
        a = tr.get("ator")
        if a and a != "narrador" and not tr.get("narracao"):
            conta[a] = conta.get(a, 0) + 1
    # A COPIA FIEL E' NARRADA (20/09): sem fala de personagem, quem conta e'
    # `personagens_em_cena` de cada trecho -- os dois que o nucleo escolheu
    # dos cartoes adaptados. Sem isso a dupla sairia da ORDEM do dicionario.
    if not conta:
        for tr in (spec.get("trechos") or []):
            for a in (tr.get("personagens_em_cena") or []):
                if a and a != "narrador":
                    conta[a] = conta.get(a, 0) + 1
    existentes = list((spec.get("elenco") or {}).keys())
    ordem = sorted(conta, key=lambda k: -conta[k])
    for k in existentes:
        if k not in ordem:
            ordem.append(k)
    return [k for k in ordem if not existentes or k in existentes][:2]


def converter(spec, pasta_base=None, falar=print):
    """O spec de trechos da esteira, virado spec de cartoes. Nao altera o
    original.

    `pasta_base` e' onde a arte foi baixada (no Action,
    `/tmp/personagem/<chave>`). Ela so' e' usada no caso do spec de UM
    personagem, que vem com `personagem_url` e sem `elenco`: o cartao acha a
    arte por `elenco[chave].pasta`, e sem esse campo procuraria em
    `pasta_partes/../<chave>` -- um diretorio que nao existe. Spec com elenco
    (o normal desde 30/08) nao precisa dela.
    """
    spec = copy.deepcopy(spec)
    F = regra("cartao")
    trechos = spec.get("trechos") or []
    if not trechos:
        raise ValueError("spec sem `trechos` para converter")

    dupla = _quem_contracena(spec)
    if not dupla:
        raise ValueError("spec sem ator nas falas: o cartao precisa de quem "
                         "desenhar")
    elenco = spec.setdefault("elenco", {})
    for chave in dupla:
        cfg = elenco.get(chave)
        if not isinstance(cfg, dict):
            cfg = {"pasta": cfg} if isinstance(cfg, str) else {}
        if not cfg.get("pasta") and pasta_base:
            cfg["pasta"] = pasta_base
        elenco[chave] = cfg

    cartoes = []
    fundo_atual = None
    placa_a_cada = int(F["placa_a_cada"])
    desde_placa = placa_a_cada         # a primeira placa pode entrar logo
    placas_postas = 0
    for i, tr in enumerate(trechos):
        fala = str(tr.get("fala") or "").strip()
        if not fala:
            continue
        ator = tr.get("ator")
        # `narrador` NAO e' um boneco (20/09): e' a voz que conta. O trecho
        # vira cartao narrado -- os dois em pose, ninguem abre a boca -- com
        # o perfil de voz `narrador` do canal.
        if ator == "narrador":
            ator = None
        narracao = bool(tr.get("narracao")) or not ator
        c = {"texto": fala}
        if not narracao:
            c["ator"] = ator

        # O FUNDO VAI EM TODO CARTAO, e nao so' quando muda: o `cartao.py` NAO
        # herda o fundo do cartao anterior -- sem a marca, ele usa a cor
        # chapada do spec. A primeira versao desta funcao marcava so' a
        # mudanca e a prova mostrou o defeito na cara: o cartao 0 com o
        # escritorio e os cinco seguintes num creme vazio, com os bonecos
        # soltos no nada.
        cen = str(tr.get("cenario") or "").strip() or fundo_atual
        if cen:
            c["fundo"] = f"cenario:{cen}"
            fundo_atual = cen

        expr = _expressao(tr)
        pose = _pose_do_trecho(tr)
        objeto = _objeto_do_trecho(tr)

        # QUEM APARECE. O falante primeiro, na esquerda; o outro na direita.
        # Com narracao, os dois ficam (ninguem abre a boca -- lei 96), e e'
        # disso que sai o cartao "de situacao" do estilo.
        quem = ator if not narracao else dupla[0]
        outro = next((k for k in dupla if k != quem), None)
        atores = []
        for k, chave in enumerate([q for q in (quem, outro) if q]):
            a = {"quem": chave,
                 "x": 0.5 if not outro else (0.30 + 0.42 * k),
                 "pose": (pose or POSE_DE_FALA) if k == 0 else POSE_DE_ESCUTA,
                 "expressao": expr if k == 0 else "neutro"}
            if k == 0 and objeto:
                a["objeto"] = objeto
                a["mao"] = "d"
            atores.append(a)
        c["atores"] = atores

        plano = PLANO.get(_limpo(tr.get("enquadramento") or ""))
        if plano:
            c["plano"] = plano

        sfx = tr.get("sfx")
        if sfx:
            c["sfx"] = copy.deepcopy(sfx)

        # O RESPIRO ENTRE CARTOES (medido em 18/09). O cartao usa 0,12 s entre
        # frases e o palito usa 0,35 (`formato.pausa_trecho_s`): com o mesmo
        # roteiro de quatro falas, o cartao saiu com 12,7 s e o palito faz
        # ~15 s. Parte da diferenca e' estilo (corte seco e' mais enxuto,
        # e' para isso que ele serve), mas 0,12 s entre duas falas de gente
        # diferente atropela a conversa -- e no A/B a duracao e' uma variavel
        # que atrapalha, nao uma que se quer medir. 0,3 s devolve ~1,8 s ao
        # video de seis cartoes e deixa o corte ser ouvido.
        c["respiro_s"] = float(F["pausa_trecho_s"])
        if tr.get("punch") or i == len(trechos) - 1:
            c["respiro_s"] = float(F["pausa_punch_s"])   # depois da tirada

        # A PLACA COM O DADO. Uma a cada tres cartoes no maximo: placa em todo
        # cartao vira poluicao e rouba o lugar da legenda.
        desde_placa += 1
        m = VALOR.search(fala)
        if m and desde_placa >= placa_a_cada:
            texto_placa = m.group(1).upper().strip()
            # A NOTA DE DINHEIRO SO' SERVE PARA NUMERO. O gerador `nota`
            # repete o texto no padrao da cedula (como uma nota de verdade
            # repete o valor nos cantos), e "TRINTA MIL" repetido cinco vezes
            # numa cedula verde nao se le -- foi o que a prova mostrou.
            # Valor por extenso vai na `etiqueta`, que e' uma etiqueta de
            # preco: uma linha, fundo claro, texto grande.
            tipo = "nota" if re.search(r"\d", texto_placa) else "etiqueta"
            c["placas"] = [{"tipo": tipo, "texto": texto_placa,
                            "x": 0.74, "y": 0.28, "escala": 0.9,
                            "entra_em": 0.45}]
            desde_placa = 0
            placas_postas += 1

        cartoes.append(c)

    spec["modo"] = "cartao"
    spec["estilo"] = "cartao"
    spec["cartoes"] = cartoes
    # O QUE O CARTAO LE DIFERENTE DO PALITO
    #   `legenda_palavras`: 1 (palavra a palavra e' o estilo; a producao usa 3)
    #   `cenario_lavado`: o veu que poe o desenho na frente do cenario
    #   `titulo`: ausente = o motor escreve pelo `titulo_da_esquete`, como o
    #             palito ja faz
    spec["legenda_palavras"] = int(F["legenda_palavras"])
    spec["loudnorm"] = F["loudnorm"]
    # A VOZ DO ESTILO (19/09, `formatos.cartao.voz`): a dinamica da voz do
    # original e' 6 dB maior que a nossa (27 x 21 dB, ver `_som` no config).
    # Abre a expressividade da ElevenLabs SO neste estilo -- a dupla continua
    # com o perfil de voz da identidade.
    voz_estilo = F.get("voz") if isinstance(F.get("voz"), dict) else {}
    if voz_estilo and isinstance(spec.get("vozes"), dict):
        for nome, cfg in spec["vozes"].items():
            if isinstance(cfg, dict) and cfg.get("motor", "eleven") == "eleven":
                cfg.update({k: v for k, v in voz_estilo.items() if not k.startswith("_")})
        falar(f"[para_cartao] voz do estilo aplicada a {len(spec['vozes'])} perfil(is): "
              + ", ".join(f"{k}={v}" for k, v in voz_estilo.items() if not k.startswith("_")))
    spec.setdefault("cenario_lavado", float(F["cenario_lavado"]))
    spec.setdefault("fundo", F["fundo"])
    # a regra viaja no spec: quem for medir o video depois nao precisa
    # adivinhar com que parametros ele foi feito
    spec["regra_estilo"] = {k: F[k] for k in sorted(F) if not k.startswith("_")}
    # `trechos` sai: o `cartao.render` reescreve esse campo com a timeline da
    # voz, e um spec com os dois seria dois roteiros no mesmo arquivo
    spec.pop("trechos", None)
    falar(f"[para_cartao] {len(trechos)} trechos -> {len(cartoes)} cartoes; "
          f"dupla: {', '.join(dupla)}; {placas_postas} placa(s) de valor; "
          f"regra do estilo: {'config.json' if _TEM_CONFIG else 'RESERVA (config_gerado.py nao esta aqui)'}")
    return spec
