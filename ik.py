# -*- coding: utf-8 -*-
"""ik.py -- pose por ALVO: "ponha a mao AQUI" (PLANO-ENCAIXE.md §5).

    Braco e perna sao dois ossos com comprimentos que JA ESTAO medidos no
    `partes.json` (pivo de cada peca e ponto de saida do filho). Dado um alvo
    na tela, a lei dos cossenos devolve os dois angulos -- no MESMO formato
    que `acoes.CATALOGO` escreve no rig ([ombro, cotovelo, pulso]), entao
    tudo o que ja existe (aplicar, ACOES_QUE_FICAM, _suave) continua igual.
    Uma pose por alvo e' so' uma pose cujo angulo foi calculado em vez de
    digitado.

CONVENCAO DO RIG (ver palito_cutout._angulo e folha_personagem)
    rig["braco_d"] = [sup, ante_rel, pulso], em graus de tela, 90 = para
    baixo, 0 = para a direita da tela, 180 = para a esquerda. O angulo
    ABSOLUTO da peca e' `soma - 90 + CORRECAO_POSE_T`, e a peca e' colada
    girando a arte por ele. Como a arte do braco `_d` aponta +x e a do `_e`
    aponta -x (folha em T), a direcao do osso na tela sai igual para os
    dois: (cos sup, sin sup). Pernas: sem correcao, mesma formula.

    So' que o ponto de saida do filho NAO cai exatamente no eixo +x da arte
    (o cotovelo fica um pouco acima ou abaixo da linha do pivo). `_offset`
    mede esse desvio (phi) e a conta o desconta -- e' isso que faz a mao
    chegar no alvo e nao a 15 px dele.
"""
import math

from folha_personagem import CORRECAO_POSE_T

CADEIAS = {
    "braco_e": ("braco_sup_e", "braco_inf_e", "mao_e"),
    "braco_d": ("braco_sup_d", "braco_inf_d", "mao_d"),
    "perna_e": ("perna_sup_e", "perna_inf_e", "pe_e"),
    "perna_d": ("perna_sup_d", "perna_inf_d", "pe_d"),
}


def _ang(v):
    return math.degrees(math.atan2(v[1], v[0]))


def _dir(graus):
    r = math.radians(graus)
    return (math.cos(r), math.sin(r))


def _norm(a):
    while a > 180:
        a -= 360
    while a <= -180:
        a += 360
    return a


def _osso(pers, pai, filho):
    """(comprimento em px de ARTE, angulo do vetor pivo->saida na arte)."""
    piv = pers.pivos.get(pai)
    sai = (pers.saidas.get(pai) or {}).get(filho)
    if piv is None or sai is None:
        return None, 0.0
    vx, vy = float(sai[0]) - float(piv[0]), float(sai[1]) - float(piv[1])
    return math.hypot(vx, vy), _ang((vx, vy))


def medidas(pers, cadeia):
    """Comprimentos (px de tela) e desvios (graus) dos dois ossos + palma."""
    cache = getattr(pers, "_ik", None)
    if cache is None:
        cache = pers._ik = {}
    if cadeia in cache:
        return cache[cadeia]
    sup, inf, ponta = CADEIAS[cadeia]
    L1, phi1 = _osso(pers, sup, inf)
    L2, phi2 = _osso(pers, inf, ponta)
    corr = float(CORRECAO_POSE_T.get(sup, 0.0))
    e = pers.escala
    m = {"ok": L1 is not None and L2 is not None,
         "L1": (L1 or 0.0) * e, "L2": (L2 or 0.0) * e,
         "phi1": phi1, "phi2": phi2, "corr": corr}
    if cadeia.startswith("braco") and pers.tem(ponta):
        vx, vy = pers.vetor_da_palma(ponta)
        m["Lp"] = math.hypot(vx, vy) * e
        m["phip"] = _ang((vx, vy))
    else:
        # o pe': da junta do tornozelo ate a sola, para baixo na arte
        m["Lp"] = 0.0
        m["phip"] = 90.0
    cache[cadeia] = m
    return m


def _dois_ossos(S, T, L1, L2, preferencia, centro_x):
    """Angulos absolutos (psi1, psi2) de tela para o osso 1 e 2, e o erro."""
    dx, dy = T[0] - S[0], T[1] - S[1]
    d = math.hypot(dx, dy)
    dmax = (L1 + L2) * 0.995
    dmin = abs(L1 - L2) + 0.5
    erro = 0.0
    if d > dmax:
        erro = d - dmax
        d = dmax
    elif d < dmin:
        erro = dmin - d
        d = dmin
    if d < 1e-6:
        return 90.0, 90.0, erro
    base = _ang((dx, dy))
    cosA = (L1 * L1 + d * d - L2 * L2) / (2.0 * L1 * d)
    A = math.degrees(math.acos(max(-1.0, min(1.0, cosA))))
    cands = []
    for sinal in (+1, -1):
        psi1 = base + sinal * A
        E = (S[0] + L1 * math.cos(math.radians(psi1)),
             S[1] + L1 * math.sin(math.radians(psi1)))
        Tc = (S[0] + d * math.cos(math.radians(base)),
              S[1] + d * math.sin(math.radians(base)))
        psi2 = _ang((Tc[0] - E[0], Tc[1] - E[1]))
        cands.append((psi1, psi2, E))
    if preferencia == "fora":
        cx = centro_x if centro_x is not None else S[0]
        # cotovelo para o lado de fora do corpo; se o ombro esta' no centro
        # (folha sem tronco), o lado de fora e' o oposto ao alvo
        if abs(S[0] - cx) < 2.0:
            cx = T[0]
        esc = max(cands, key=lambda c: (c[2][0] - cx) * (1 if S[0] >= cx else -1))
    elif preferencia == "dentro":
        cx = centro_x if centro_x is not None else T[0]
        esc = min(cands, key=lambda c: (c[2][0] - cx) * (1 if S[0] >= cx else -1))
    elif preferencia == "cima":
        esc = min(cands, key=lambda c: c[2][1])
    else:                                   # "baixo"
        esc = max(cands, key=lambda c: c[2][1])
    return esc[0], esc[1], erro


def membro_para(pers, rig, cadeia, alvo, cotovelo="fora", centro_x=None,
                ponto="palma", pos=None, ang=None, k=1.0):
    """Leva a ponta da cadeia ate `alvo` (px de tela). Escreve no rig.

    `ponto`: "palma" (o objeto na mao), "punho" (a junta), "dedos" (a ponta).
    `k` mistura com o que o rig tinha (1 = chega; 0,5 = metade do caminho),
    para animar a chegada com `_suave` de quem chama.
    Devolve o erro em px (0 = alcancou; >0 = alvo fora do alcance, a mao
    ficou no ponto mais proximo)."""
    from palito_cutout import pose_na_tela
    m = medidas(pers, cadeia)
    if not m["ok"]:
        return float("inf")
    if pos is None or ang is None:
        pos, ang = pose_na_tela(pers, rig)
    sup = CADEIAS[cadeia][0]
    if sup not in pos:
        return float("inf")
    S = pos[sup]
    L1, L2 = m["L1"], m["L2"]
    if cadeia.startswith("perna"):
        # a perna vai ate' o TORNOZELO; a sola fica `Lp` abaixo (cadeia reta)
        Lp = 0.0
    else:
        Lp = {"palma": m["Lp"], "dedos": m["Lp"] * 1.7, "punho": 0.0}.get(ponto, m["Lp"])
    # a palma nao esta' exatamente no eixo do antebraco: o desvio e' phip-phi2
    desvio_palma = _norm(m["phip"] - m["phi2"]) if Lp else 0.0
    # ITERACAO: o punho e' o alvo menos o vetor da palma, e o vetor da palma
    # depende do angulo do antebraco, que so' se sabe depois de resolver.
    psi2 = _ang((alvo[0] - S[0], alvo[1] - S[1]))
    psi1 = psi2
    erro = 0.0
    for _ in range(3 if Lp else 1):
        dp = _dir(psi2 + desvio_palma)
        Wr = (alvo[0] - dp[0] * Lp, alvo[1] - dp[1] * Lp)
        psi1, psi2, erro = _dois_ossos(S, Wr, L1, L2, cotovelo, centro_x)
    # de angulo de tela para o formato do rig (ver a docstring do modulo)
    corr = m["corr"]
    r0 = _norm(psi1 - m["phi1"] + 90.0 - corr)
    soma = _norm(psi2 - m["phi2"] + 90.0 - corr)
    r1 = _norm(soma - r0)
    atual = (list(rig.get(cadeia) or [90.0, 0.0, 0.0]) + [0.0, 0.0, 0.0])[:3]
    novo = [r0, r1, 0.0]
    if k < 1.0:
        novo = [a + _norm(b - a) * k for a, b in zip(atual, novo)]
    rig[cadeia] = novo
    return erro


def mao_para(pers, rig, lado, alvo, **kw):
    return membro_para(pers, rig, "braco_" + lado, alvo, **kw)


def pe_para(pers, rig, lado, alvo, **kw):
    kw.setdefault("cotovelo", "fora")
    kw.setdefault("ponto", "punho")
    return membro_para(pers, rig, "perna_" + lado, alvo, **kw)


def altura_da_perna(pers):
    """Do quadril ate' a sola, com a perna reta (px de tela)."""
    m = medidas(pers, "perna_d") if pers.tem("perna_sup_d") else medidas(pers, "perna_e")
    from ancoras import medir_locais
    L = medir_locais(pers)
    sola = L.get("sola_d") or L.get("sola_e") or (0.0, 0.0)
    return m["L1"] + m["L2"] + abs(sola[1]) * pers.escala


def sentar(pers, rig, chao_y, altura_assento, abrir=0.55):
    """Quadril desce ao assento; os pes continuam no chao, joelhos para fora.

    `altura_assento` em px de tela acima do chao. Frontal, o que se le como
    sentado e' o corpo mais baixo com as coxas abrindo e as canelas descendo."""
    from palito_cutout import pose_na_tela
    m = medidas(pers, "perna_d") if pers.tem("perna_sup_d") else medidas(pers, "perna_e")
    from ancoras import medir_locais
    L = medir_locais(pers)
    sola = L.get("sola_d") or L.get("sola_e") or (0.0, 0.0)
    pe = abs(sola[1]) * pers.escala
    rig["quadril"] = [rig["quadril"][0], chao_y - altura_assento]
    pos, ang = pose_na_tela(pers, rig)
    for lado, sinal in (("e", -1), ("d", +1)):
        sup = "perna_sup_" + lado
        if sup not in pos:
            continue
        Sx = pos[sup][0]
        alvo = (Sx + sinal * m["L1"] * abrir, chao_y - pe)
        pe_para(pers, rig, lado, alvo, cotovelo="fora", centro_x=rig["quadril"][0],
                pos=pos, ang=ang)
    return rig


def ajoelhar(pers, rig, chao_y, lado_no_chao="ambos"):
    """Joelhos no chao: coxa vertical, canela para o lado (frontal)."""
    m = medidas(pers, "perna_d") if pers.tem("perna_sup_d") else medidas(pers, "perna_e")
    from ancoras import medir_locais
    L = medir_locais(pers)
    sola = L.get("sola_d") or L.get("sola_e") or (0.0, 0.0)
    pe = abs(sola[1]) * pers.escala
    rig["quadril"] = [rig["quadril"][0], chao_y - m["L1"] - pe * 0.3]
    for lado, sinal in (("e", -1), ("d", +1)):
        # coxa para baixo e um pouco aberta; canela horizontal para fora
        # e (esquerda da tela): canela para 180; d: para 0 -- ambos "para fora"
        rig["perna_" + lado] = [90.0 + sinal * 6.0, -sinal * 84.0, 0.0]
    return rig
