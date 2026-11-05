"""Garante a qualidade do banco de vozes (05/11, pedido do dono: "garantir a qualidade das vozes clonadas").

Para cada voz de `banco_vozes`, o Chatterbox clona uma frase de TESTE (diferente do texto da referência) e mede:
  similaridade  cosseno entre a voz da referência e a voz clonada (Resemblyzer, 0-1; >=0,80 = mesma pessoa ao ouvido)
  wer           erro de palavras da fala clonada, transcrita pelo Whisper (0 = disse tudo certo)
  ritmo         palavras por segundo (fora de 1,8-3,6 soa arrastado/atropelado)
Nota 0-10 = 6*sim_norm + 3*(1-wer) + 1*ritmo_ok. Aprovada: sim>=0,78, wer<=0,15 e ritmo ok.
Grava em banco_vozes.qualidade/status e sobe a amostra clonada (vozes_banco/<id>.amostra.mp3) para ouvir no painel.

Roda no venv do voz_livre (mesmo Chatterbox do render). Uso: python vozes_avaliar.py [--ids a,b] [--shard i/n] [--todas]
"""
import argparse, json, os, re, subprocess, sys, tempfile, time, urllib.parse, urllib.request

TESTE = {
    "en": "Nobody expected the bridge to hold that much weight, but the numbers tell a different story.",
    "pt": "Ninguém esperava que a ponte aguentasse tanto peso, mas os números contam outra história.",
    "es": "Nadie esperaba que el puente aguantara tanto peso, pero los números cuentan otra historia.",
    "fr": "Personne ne pensait que le pont tiendrait autant de poids, mais les chiffres racontent autre chose.",
    "de": "Niemand hat erwartet, dass die Brücke so viel Gewicht trägt, aber die Zahlen erzählen etwas anderes.",
    "it": "Nessuno si aspettava che il ponte reggesse tanto peso, ma i numeri raccontano un'altra storia.",
}
URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
BUCKET = os.environ.get("SUPABASE_BUCKET", "toonzueira")


def rest(caminho, metodo="GET", corpo=None):
    h = {"apikey": KEY, "Authorization": "Bearer " + KEY, "Content-Type": "application/json", "Prefer": "return=minimal"}
    req = urllib.request.Request(f"{URL}/rest/v1/{caminho}", method=metodo, headers=h,
                                 data=None if corpo is None else json.dumps(corpo).encode())
    with urllib.request.urlopen(req, timeout=60) as f:
        t = f.read()
        return json.loads(t) if t else None


def subir(caminho, arq):
    req = urllib.request.Request(f"{URL}/storage/v1/object/{BUCKET}/{caminho}", data=open(arq, "rb").read(), method="POST",
                                 headers={"apikey": KEY, "Authorization": "Bearer " + KEY, "Content-Type": "audio/mpeg",
                                          "x-upsert": "true"})
    urllib.request.urlopen(req, timeout=120).read()
    return f"{URL}/storage/v1/object/public/{BUCKET}/{caminho}"


def norm_palavras(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", t).split()


def wer(ref, hip):
    r, h = norm_palavras(ref), norm_palavras(hip)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        ant, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, ant + (r[i - 1] != h[j - 1]))
            ant = cur
    return d[len(h)] / max(1, len(r))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="")
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--todas", action="store_true")
    a = ap.parse_args()
    import numpy as np
    import voz_livre
    from resemblyzer import VoiceEncoder, preprocess_wav
    from faster_whisper import WhisperModel

    filtro = "select=*&order=banco_id"
    if a.ids:
        filtro += "&banco_id=in.(" + ",".join(urllib.parse.quote(x, safe="/") for x in a.ids.split(",")) + ")"
    elif not a.todas:
        filtro += "&status=eq.gerada"
    vozes = rest("banco_vozes?" + filtro) or []
    i, n = map(int, a.shard.split("/"))
    vozes = [v for k, v in enumerate(vozes) if k % n == i]
    print(f"[avaliar] {len(vozes)} vozes neste pedaço", flush=True)
    enc = VoiceEncoder("cpu")
    wh = {}
    tmp = tempfile.mkdtemp()
    os.environ["VOZ_LIVRE_TMP"] = tmp
    for v in vozes:
        t0 = time.time()
        lingua = (v.get("idioma") or "en")[:2]
        frase = TESTE.get(lingua, TESTE["en"])
        cfg = {"motor": "chatterbox", "ref_url": v["ref_url"], "lingua": lingua, "cfg_weight": 0.5, "exaggeration": 0.5}
        saida = os.path.join(tmp, re.sub(r"\W", "_", v["banco_id"]) + ".wav")
        q = {"avaliado_em": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "frase": frase}
        try:
            voz_livre._sintetizar_local(frase, cfg, saida)
            ref = voz_livre._referencia(cfg, tmp)
            e1 = enc.embed_utterance(preprocess_wav(ref))
            e2 = enc.embed_utterance(preprocess_wav(saida))
            sim = float(np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2)))
            nome = "base.en" if lingua == "en" else "small"
            if nome not in wh:
                wh[nome] = WhisperModel(nome, device="cpu", compute_type="int8")
            segs, _ = wh[nome].transcribe(saida, language=lingua, beam_size=3)
            ouvido = " ".join(s.text for s in segs).strip()
            w = wer(frase, ouvido)
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", saida],
                                       capture_output=True, text=True).stdout.strip() or 0)
            pps = len(frase.split()) / max(0.1, dur)
            ritmo_ok = 1.8 <= pps <= 3.6
            sim_n = min(1.0, max(0.0, (sim - 0.60) / 0.30))
            nota = round(6 * sim_n + 3 * max(0.0, 1 - w) + (1 if ritmo_ok else 0), 1)
            mp3 = saida[:-4] + ".mp3"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", saida, "-b:a", "128k", mp3], check=True)
            amostra = subir(f"vozes_banco/{v['banco_id']}.amostra.mp3", mp3)
            q.update({"similaridade": round(sim, 3), "wer": round(w, 3), "palavras_s": round(pps, 2), "ouvido": ouvido[:300],
                      "nota": nota, "amostra_url": amostra, "segundos": round(time.time() - t0, 1)})
            status = "aprovada" if (sim >= 0.78 and w <= 0.15 and ritmo_ok) else "reprovada"
        except Exception as e:  # noqa: BLE001
            q["erro"] = f"{type(e).__name__}: {e}"[:400]
            status = "reprovada"
        rest("banco_vozes?banco_id=eq." + urllib.parse.quote(v["banco_id"], safe="/"), "PATCH",
             {"qualidade": q, "status": status, "atualizado_em": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        print(f"[avaliar] {v['banco_id']}: {status} {json.dumps({k: q.get(k) for k in ('similaridade', 'wer', 'palavras_s', 'nota', 'erro')})}",
              flush=True)


if __name__ == "__main__":
    main()
