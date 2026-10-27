"""Pilotos de ritmo: uma fala contínua, imagens alinhadas à voz, sem publicação.

As amostras são hipóteses editoriais para avaliação humana. As durações só
existem depois da síntese; palavras/gancho fora do contrato interrompem o render.
Este módulo também é copiado como pilotos_t320.py na branch isolada do render.
"""
import copy
import math
import re
import unicodedata


def _letras(texto):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", texto.lower()))


def montar_timeline(cenas, palavras, duracao):
    """Alinha por caracteres para aceitar contrações divididas pelo TTS."""
    if not cenas or not palavras or not math.isfinite(duracao) or duracao <= 0:
        raise ValueError("Fala, cenas e duração real são obrigatórias")
    falado = "".join(_letras(str(m.get("palavra", ""))) for m in palavras)
    esperado = "".join(_letras(c["texto"]) for c in cenas)
    if not esperado or falado != esperado:
        raise ValueError("As marcas não correspondem ao texto completo; não estimar cortes")
    posicoes, pos, anterior = [], 0, -1
    for m in palavras:
        ini, fim = float(m["ini"]), float(m["fim"])
        if not all(math.isfinite(x) for x in (ini, fim)) or ini < anterior or fim <= ini or fim > duracao + .02:
            raise ValueError("Marcas de voz inválidas")
        letras = _letras(str(m["palavra"]))
        if letras:
            posicoes.append((pos, pos + len(letras), ini))
            pos += len(letras)
        anterior = ini
    out, pos = copy.deepcopy(cenas), 0
    for i, cena in enumerate(out):
        cena["ini"] = 0.0 if i == 0 else next(t for a, b, t in posicoes if a <= pos < b)
        pos += len(_letras(cena["texto"]))
    for i, cena in enumerate(out):
        cena["fim"] = out[i + 1]["ini"] if i + 1 < len(out) else duracao
        d = cena["fim"] - cena["ini"]
        if d <= 0 or d > 4.8:
            raise ValueError("Plano sem mudança visual por mais de 4,8 s")
    if out[0]["fim"] > 3:
        raise ValueError("A abertura não muda antes de 3 segundos")
    return out


def eventos_sonoros(cenas):
    """Um efeito por virada; ganho menor que o antigo 0,9 sobre cada fala."""
    ev = []
    for i, c in enumerate(cenas):
        nomes = c.get("sfx") or []
        if nomes:
            ev.append({"nome": nomes[0], "t": c["ini"], "ganho": .45 if i == 0 else .32})
    return ev


def narrar_continuo(spec, tmp, modo_tts):
    """Ponto opt-in do montar_web; uma chamada TTS, sem respiro a cada corte."""
    import os
    from palito_v5 import sintetizar
    from motor_web.montar_web import _aparar_inicio
    texto = " ".join(c["texto"] for c in spec["cenas"])
    wav = os.path.join(tmp, "voz.wav")
    marcas, dur = sintetizar(texto, dict(spec["voz"]), wav, modo_tts)
    marcas, aparada = _aparar_inicio(wav, marcas)
    if aparada:
        dur = aparada
    palavras = [{"palavra": m["palavra"], "ini": m["inicio_s"], "fim": m["fim_s"]} for m in marcas]
    spec["cenas"] = montar_timeline(spec["cenas"], palavras, dur)
    spec["palavras"], spec["dur_s"] = palavras, dur
    if not 40 <= dur <= 65:
        raise ValueError(f"Duração {dur:.1f}s fora do formato dos pilotos (40–65s)")
    print(f"[T320] voz contínua, {len(spec['cenas'])} cortes, {dur:.2f}s; sem aceleração")
    return wav


def _cenas(linhas):
    out = []
    for i, (texto, cenario, acao, hud) in enumerate(linhas):
        out.append({"texto": texto, "cenario": cenario, "acao": acao,
                    "hud": hud, "hora": "noite" if "dark" in texto.lower() else "dia",
                    "camera": ["perto", "sobrevoo", "zoom_in", "zoom_out"][i % 4],
                    "atores": ["pessoa"], "sfx": ["thud" if i == 0 else "plim" if hud else "whoosh"]})
    return out


def amostras():
    """Inglês do TINY WHAT IF; não altera a identidade dos canais."""
    roteiros = [
        ("salt", "The Rain That Makes Drought Worse", [
            ("This rain destroys your food.", "campo", "murcha", "WHAT IF?"),
            ("What if clouds dumped seawater instead?", "cidade", "chove", "SEAWATER RAIN"),
            ("Your umbrella helps you. What about farms?", "campo", "chove", ""),
            ("One liter carries roughly thirty five grams of salt.", "praia", "compara", "35 G / L"),
            ("Ten liters? Roughly three hundred fifty grams.", "cidade", "compara", "350 G"),
            ("Now spread that over an entire field.", "campo", "mostra", ""),
            ("Water evaporates. The salt stays behind.", "praia", "seca", "SALT STAYS"),
            ("The next rainstorm brings another salty delivery.", "cidade", "chove", ""),
            ("And another. This is the real trap.", "floresta", "mostra", ""),
            ("Wet soil doesn't guarantee roots can drink.", "campo", "mostra", "WET ≠ USABLE"),
            ("Salt makes absorbing that water much harder.", "floresta", "mostra", ""),
            ("Sensitive crops wither, surrounded by soaking ground.", "campo", "murcha", ""),
            ("A drought you can't fix with more rain.", "cidade", "chove", ""),
            ("Runoff also carries salt into freshwater habitats.", "oceano", "mostra", ""),
            ("The damage depends on drainage and repeated storms.", "montanha", "mostra", ""),
            ("This isn't how normal rain actually works.", "praia", "chove", "REAL RAIN"),
            ("Evaporation usually leaves ocean salt behind.", "oceano", "mostra", "SALT STAYS"),
            ("Good thing clouds don't deliver the whole ocean.", "cidade", "chove", ""),
        ], ["https://www.noaa.gov/jetstream/ocean/sea-water", "https://www.fao.org/4/t0234e/t0234e04.htm"]),
        ("sun", "The Sun Goes Dark. Why Are You Still in Daylight?", [
            ("The Sun switched off. Nobody noticed.", "cidade", "mostra", "WHAT IF?"),
            ("Why are the streets still bright?", "campo", "anda", ""),
            ("Imagine sunlight stopped leaving the Sun right now.", "praia", "mostra", "LIGHT OFF"),
            ("No explosion. Just no new light coming out.", "montanha", "mostra", ""),
            ("You'd still see daylight for about eight minutes.", "cidade", "anda", "ABOUT 8 MIN"),
            ("The last sunlight is already on its way.", "campo", "mostra", "IN TRANSIT"),
            ("Light is fast. Space is ridiculously big.", "oceano", "compara", ""),
            ("Sunlight crosses roughly one hundred fifty million kilometers.", "montanha", "compara", "150 MILLION KM"),
            ("So the view outside is slightly out of date.", "cidade", "anda", ""),
            ("Then the final light reaches your street.", "campo", "mostra", "LAST LIGHT"),
            ("Daylight disappears. Now everyone notices the dark.", "cidade", "noite_eterna", "LIGHT ARRIVES"),
            ("But the ground doesn't instantly freeze solid.", "praia", "mostra", "NOT INSTANT"),
            ("Land and oceans have stored enormous amounts of heat.", "oceano", "mostra", "STORED ENERGY"),
            ("They lose that energy over time, not instantly.", "montanha", "mostra", ""),
            ("Plants also lose the sunlight powering photosynthesis.", "floresta", "mostra", ""),
            ("That's another problem after our eight minute delay.", "campo", "mostra", ""),
            ("This thought experiment switches off light, not gravity.", "praia", "compara", "LIGHT ONLY"),
            ("That bright sky? You're always seeing the past.", "cidade", "anda", "8 MIN AGO"),
        ], ["https://science.nasa.gov/earth/facts/", "https://science.nasa.gov/exoplanets/what-is-a-light-year/"]),
        ("trees", "Every Tree Vanishes. What Reaches Your House?", [
            ("Every tree vanished. Your house next?", "floresta", "mostra", "WHAT IF?"),
            ("Watch what happens when the rain arrives.", "cidade", "chove", ""),
            ("Imagine the trunks, leaves, and roots disappeared overnight.", "floresta", "mostra", "NO TREES"),
            ("First, animals lose food and places to hide.", "campo", "mostra", ""),
            ("Your street also loses shade and leafy shelter.", "cidade", "anda", ""),
            ("But here's the threat you might overlook.", "montanha", "mostra", ""),
            ("Tree roots help hold soil in place.", "floresta", "mostra", "ROOTS MATTER"),
            ("Leaves intercept some rain before it hits the ground.", "campo", "chove", ""),
            ("Without them, a downpour can send more water downhill.", "montanha", "chove", ""),
            ("Loose soil can travel with that runoff.", "praia", "mostra", "SOIL + WATER"),
            ("Where does the muddy water go next?", "cidade", "compara", ""),
            ("Into streams, drains, and places people live.", "oceano", "mostra", ""),
            ("Flood risks depend on terrain and the storm.", "cidade", "inunda", "LOCAL RISK"),
            ("It doesn't mean every house suddenly washes away.", "montanha", "mostra", ""),
            ("And wind loses some of its natural barriers.", "campo", "vento", ""),
            ("Trees were doing work you barely noticed.", "floresta", "mostra", ""),
            ("Shelter. Shade. Soil protection. More than scenery.", "cidade", "compara", ""),
            ("Next downpour, notice what's standing uphill from you.", "montanha", "chove", "LOOK UPHILL"),
        ], ["https://www.epa.gov/soakuptherain/soak-rain-trees-help-reduce-runoff"]),
    ]
    specs = [{"motor": "web", "estilo": "lowpoly", "piloto_t320": True,
             "amostra": nome, "titulo": titulo, "idioma": "en-US", "narrado": True,
             "w": 1080, "h": 1920, "fps": 30, "semente": "t320-" + nome,
             "voz": {"motor": "edge", "voice": "en-US-AndrewMultilingualNeural", "rate": "+0%", "pitch": "+0Hz"},
             "musica": {"genero": "suspense", "registro": "serio", "ganho_db": -26},
             "qa_t260": {"dur_min": 40, "dur_max": 65},
             "cenas": _cenas(linhas), "metadados": {"fontes": fontes, "avaliacao": "T320 — aguarda feedback do dono"}}
            for nome, titulo, linhas, fontes in roteiros]
    # O mundo mantém a consequência da hipótese depois do corte.
    for spec in specs:
        if spec["amostra"] == "sun":
            for c in spec["cenas"][11:]:
                c["hora"] = "noite"
        if spec["amostra"] == "trees":
            spec["cenas"][0]["arvores_desaparecem"] = True
            for c in spec["cenas"][1:]:
                c["sem_arvores"] = True
    return specs
