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
import os
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


POSE_DE_ESCUTA_DIR = "escutar"


def cartoes_direcao_salto_repetido(cartoes, salto):
    """Dois saltos iguais seguidos sao um so' (o modelo repete o salto na
    frase seguinte quando ela continua a mesma cena)."""
    return bool(cartoes) and str(cartoes[-1].get("salto") or "").upper() == salto.upper()


def _cartao_da_direcao(c, d, tr, spec, elenco, dupla):
    """Preenche o cartao `c` a partir da direcao `d` da frase. Devolve False
    quando a direcao nao tem nada que o motor consiga desenhar (ator fora
    do elenco baixado, sem objeto, sem placa) -- e ai o caminho de sempre
    monta o cartao.

    O que sai daqui e' o mesmo esquema que `ideia.montar_spec` produz para
    as copias manuais: `atores` com x/pose/expressao/objeto, `objetos`
    soltos quando ninguem aparece, `placas` com o dado, `plano`."""
    disponiveis = set((spec.get("elenco") or {}).keys())
    quem_aparece = [a for a in (d.get("atores") or []) if a in disponiveis][:2]
    expr = str(d.get("expressao") or tr.get("expressao") or "neutro")
    obj = str(d.get("objeto") or "").strip()
    # o objeto so' entra se a ARTE esta no disco (o job baixou ou gerou); o
    # que nao deu para gerar fica fora, e o cartao segue sem ele
    pasta = spec.get("pasta_objetos") or ""
    if pasta:
        obj_ok = obj if (obj and os.path.exists(os.path.join(pasta, obj + ".png"))) else ""
    else:
        obj_ok = obj if (obj and obj in (spec.get("objetos") or {})) else ""
    tipo = str(d.get("placa_tipo") or "").strip()
    texto_placa = str(d.get("placa_texto") or "").strip()
    quem_fala = c.get("ator")
    atores = []
    for k, chave in enumerate(quem_aparece):
        pose = str(d.get("pose") or "").strip() if k == 0 else ""
        if not pose:
            pose = POSE_DE_ESCUTA_DIR if (quem_fala and chave != quem_fala) else \
                ("mostrar_objeto" if (k == 0 and obj_ok) else "gesticular")
        a = {"quem": chave,
             "x": 0.5 if len(quem_aparece) == 1 else (0.30 + 0.42 * k),
             "pose": pose,
             "expressao": expr if (not quem_fala or chave == quem_fala) else "neutro"}
        if k == 0 and obj_ok:
            a["objeto"] = obj_ok
            a["mao"] = "d"
        atores.append(a)
    if atores:
        c["atores"] = atores
    elif obj_ok:
        # CARTAO SEM GENTE: a coisa sozinha e grande -- e' a troca de tela do
        # Madrazzo (~40% dos cartoes)
        c["objetos"] = [{"nome": obj_ok, "x": 0.5}]
    if tipo and texto_placa:
        if atores and len(atores) == 1:
            atores[0]["x"] = 0.34          # o boneco sai do centro para a placa
        c["placas"] = [{"tipo": tipo, "texto": texto_placa.upper(),
                        "x": 0.78 if atores else 0.5, "y": 0.30,
                        "escala": 1.0 if atores else 1.3, "entra_em": 0.5}]
    # o plano alterna com o que ha' na tela: gente em close quando esta' so',
    # aberto quando ha' dois ou uma coisa grande
    if atores and len(atores) == 1 and not c.get("placas") and not obj_ok:
        c["plano"] = "close"
    sfx = tr.get("sfx")
    if sfx:
        c["sfx"] = copy.deepcopy(sfx)
    return bool(atores or c.get("objetos") or c.get("placas"))


def casar_duracao(spec, cartoes, F, falar=print):
    """A copia dura o que o original dura (21/09). Estima a fala (2,6
    palavras/s a velocidade 1,0, medido na dupla) mais os respiros; se
    passar do original em mais de 5%, sobe `speed` de todo perfil ElevenLabs
    ate' `speed_max` e encurta o respiro na mesma proporcao. A ElevenLabs
    aceita 0,7-1,2 em `voice_settings.speed`; o Edge ignora (usa `rate`)."""
    alvo = float(spec.get("copia_dur_s") or 0)
    if alvo <= 0:
        return None
    palavras = sum(len(str(c.get("texto") or "").split()) for c in cartoes)
    respiros = sum(float(c.get("respiro_s") or 0) for c in cartoes)
    saltos = sum(1.2 for c in cartoes if c.get("salto"))
    wps = float(F.get("wps_copia") or 2.6)
    est = palavras / wps + respiros + saltos
    if est < alvo * 0.92 and cartoes:
        # CURTA DEMAIS (21/09): a voz le mais rapido que o narrador original,
        # e o dono pediu a duracao do original. O que falta vira RESPIRO
        # espalhado pelos cartoes (ate' +0,9 s cada): o ritmo do original e'
        # feito dessas pausas entre uma tela e outra.
        falta = alvo - est
        extra = min(0.9, falta / len(cartoes))
        for c in cartoes:
            c["respiro_s"] = round(float(c.get("respiro_s") or 0) + extra, 2)
        falar(f"[copia] duracao estimada {est:.0f}s para {alvo:.0f}s do original: "
              f"+{extra:.2f}s de respiro por cartao")
        return None
    if est <= alvo * 1.05:
        falar(f"[copia] duracao estimada {est:.0f}s para {alvo:.0f}s do original: sem acelerar")
        return None
    speed = min(float(F.get("speed_max") or 1.2), max(1.0, est / alvo))
    for k, cfg in (spec.get("vozes") or {}).items():
        if isinstance(cfg, dict) and cfg.get("motor", "eleven") == "eleven":
            cfg["speed"] = round(speed, 2)
    for c in cartoes:
        if c.get("respiro_s"):
            c["respiro_s"] = round(max(0.12, float(c["respiro_s"]) / speed), 2)
    falar(f"[copia] duracao estimada {est:.0f}s para {alvo:.0f}s do original: "
          f"voz a {speed:.2f}x e respiro /{speed:.2f}")
    return speed


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

        # A DIRECAO POR FRASE (21/09, copia fiel) -- ver `formatos.cartao.
        # _direcao`. Quando o trecho traz `cartao`, o cartao sai DELA (quem
        # aparece, pose, objeto, placa, salto), e nao da coreografia da dupla.
        d = tr.get("cartao") if isinstance(tr.get("cartao"), dict) else None
        if d is not None:
            salto = str(d.get("salto") or "").strip()
            if salto and not cartoes_direcao_salto_repetido(cartoes, salto):
                cartoes.append({"salto": salto.upper(), "fundo": c.get("fundo")})
            c["respiro_s"] = float(F["pausa_trecho_s"])
            if i == len(trechos) - 1:
                c["respiro_s"] = float(F["pausa_punch_s"])
            if _cartao_da_direcao(c, d, tr, spec, elenco, dupla):
                cartoes.append(c)
                if c.get("placas"):
                    placas_postas += 1
                continue
            # direcao sem nada aproveitavel: cai no caminho de sempre

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
    # O LOOP DO CARTAO (22/09) mora em `cartao.render`, e nao aqui: entre este
    # ponto e o desenho passam `gancho.abrir_no_auge`, `desdobrar` e
    # `gancho.garantir`, e as tres reescrevem justamente o primeiro e o ultimo
    # cartao. Ver o bloco `[loop]` la'.
    spec["cartoes"] = cartoes
    # a copia fiel dura o que o original dura (21/09)
    if spec.get("copia_dur_s"):
        casar_duracao(spec, cartoes, F, falar)
    n_dir = sum(1 for tr in trechos if isinstance(tr.get("cartao"), dict))
    if n_dir:
        falar(f"[para_cartao] direcao por frase em {n_dir}/{len(trechos)} trechos: "
              f"{sum(1 for c in cartoes if c.get('salto'))} salto(s), "
              f"{sum(1 for c in cartoes if c.get('placas'))} placa(s), "
              f"{sum(1 for c in cartoes if c.get('objetos'))} cartao(oes) so' de objeto, "
              f"{len({c.get('fundo') for c in cartoes if c.get('fundo')})} fundo(s)")
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
