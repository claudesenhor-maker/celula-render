"""Sentido frase -> imagem (T199/T217, A8) para a silhueta.

Quando a frase cita clima, lugar ou hora explicitos e a imagem diz outra coisa,
o espectador ve a contradicao (ex.: "fog hid Kiska" com raio). Conservador: so
age quando a frase tem a pista. Copia de videos-auto/motor-realista/videos_realistas/sentido_cena.py.
"""
import copy
import re

_REGRAS = {
    "objeto": [
        (r"\b(fog|mist|misty|foggy|nevoa|neblina|nevoeiro)\b", "nevoa", {"nevoa"}),
        (r"\b(rain|rained|raining|rains|chuva|chovia|choveu)\b", "chuva", {"chuva", "raio"}),
        (r"\b(snow|snowed|snowing|snowy|blizzard|neve|nevasca)\b", "neve", {"neve"}),
        (r"\b(lightning|thunderstorm|raio|trovao|relampago)\b", "raio", {"raio", "chuva"}),
    ],
    "cenario": [
        (r"\b(sea|ocean|ship|island|coast|mar|oceano|navio|ilha|costa)\b", "mar", {"mar", "farol", "praia", "oceano"}),
    ],
    "hora": [
        (r"\b(night|midnight|noite|madrugada|meia-noite)\b", "noite", {"noite", "tempestade"}),
    ],
}


def _pistas(texto):
    t = (texto or "").lower()
    achados = {}
    for campo, regras in _REGRAS.items():
        for padrao, ideal, aceitos in regras:
            if re.search(padrao, t):
                achados[campo] = (ideal, aceitos)
                break
    return achados


def conferir_cenas(cenas):
    """[{indice, alertas:[campo:ideal]}] so das cenas que contradizem a frase."""
    out = []
    for i, c in enumerate(cenas or []):
        alertas = []
        for campo, (ideal, aceitos) in _pistas((c or {}).get("texto")).items():
            if (c.get(campo) or "") not in aceitos:
                alertas.append(f"{campo}:{ideal}")
        if alertas:
            out.append({"indice": i, "alertas": alertas})
    return out


def corrigir_cenas(cenas):
    """(novas_cenas, n_cenas_corrigidas): aplica o valor ideal em cada campo que contradiz."""
    novas = copy.deepcopy(list(cenas or []))
    n = 0
    for r in conferir_cenas(novas):
        for a in r["alertas"]:
            campo, ideal = a.split(":")
            novas[r["indice"]][campo] = ideal
        n += 1
    return novas, n


ESTILOS = ("silhueta",)  # os valores ideais (nevoa/mar/noite) so existem nesse estilo


def aplicar_no_spec(spec):
    """No render: corrige `spec['cenas']` no lugar, so no estilo silhueta; devolve quantas mudou.
    Nunca derruba o render: spec invalido fica como veio."""
    try:
        if (spec or {}).get("estilo") not in ESTILOS:
            return 0
        novas, n = corrigir_cenas(spec.get("cenas"))
        if n:
            spec["cenas"] = novas
        return n
    except Exception:  # noqa: BLE001
        return 0
