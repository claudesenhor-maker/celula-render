"""Narração do Estilo Copy pelo ElevenLabs (13/11, dono: "escolha uma voz melhor, mais suave, que pareça narrador").

Por que aqui: as chaves do ElevenLabs só existem como secrets do render (render.yml -> job.py). O estilo-copy-voz.yml
(Chatterbox, clone) não as recebe -- e o clone era a voz com sotaque. job.py desvia para cá SÓ quando o spec pede
`modo: estilo_copy_narracao`; nenhum render de canal passa por este arquivo.

Entrada (spec): {modo, falas: [str], voz: {eleven_voice_id, stability, similarity, style, speed, eleven_model?}}
Saída (artefato `video` do render.yml): /tmp/final.mp4.previas/nNN.mp3 + /tmp/final_spec_render.json (manifesto:
duração e palavras com tempo de cada fala, conta usada, plano/créditos de cada conta). Sem queda para outra voz:
se a voz pedida não puder ser usada, o manifesto diz por quê e o job falha -- trocar a voz é decisão do dono.
"""
import json, os, subprocess, sys, urllib.request

PREVIAS = "/tmp/final.mp4.previas"
MANIFESTO = "/tmp/final_spec_render.json"


def _chaves():
    out = []
    for var in ("ELEVEN_API_KEY", "ELEVEN_API_KEY_2", "ELEVEN_API_KEY_3", "ELEVEN_API_KEY2"):
        v = (os.environ.get(var) or "").strip()
        if v and v not in [c for _, c in out]:
            out.append((var, v))
    return out


def _assinatura(chave):
    try:
        req = urllib.request.Request("https://api.elevenlabs.io/v1/user/subscription", headers={"xi-api-key": chave})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode())
        return {k: d.get(k) for k in ("tier", "status", "character_count", "character_limit", "next_character_count_reset_unix")}
    except Exception as e:                                     # noqa: BLE001
        return {"erro": str(e)[:160]}


def _duracao(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def rodar(spec):
    import palito_v5 as P
    os.makedirs(PREVIAS, exist_ok=True)
    voz = dict(spec.get("voz") or {})
    vid = voz.get("eleven_voice_id")
    falas = [str(f).strip() for f in spec.get("falas") or []]
    chaves = _chaves()
    man = {"modo": "estilo_copy_narracao", "voz": voz, "contas": [{"vaga": n, **_assinatura(c)} for n, c in chaves],
           "vagas_vazias": [v for v in ("ELEVEN_API_KEY", "ELEVEN_API_KEY_2", "ELEVEN_API_KEY_3") if not (os.environ.get(v) or "").strip()],
           "falas": [], "erro": None}
    try:
        if not vid or not falas:
            raise RuntimeError("spec sem eleven_voice_id ou sem falas")
        if not chaves:
            raise RuntimeError("nenhuma chave do ElevenLabs chegou ao runner")
        for i, texto in enumerate(falas):
            mp3 = f"{PREVIAS}/n{i:02}.mp3"; ultimo = None
            for vaga, chave in chaves:
                try:
                    marcas = P._eleven(texto, voz, mp3, chave, vid)
                    man["falas"].append({"i": i, "texto": texto, "vaga": vaga, "dur_s": round(_duracao(mp3), 3), "palavras": marcas})
                    ultimo = None; break
                except P.PlanoNaoPermiteVoz as e:
                    ultimo = f"plano: {e}"; continue
                except Exception as e:                     # noqa: BLE001 -- cota/rede: tenta a próxima conta
                    ultimo = f"{vaga}: {e}"; continue
            if ultimo:
                raise RuntimeError(f"fala {i}: {ultimo}")
            print(f"[narracao] {i:02} {man['falas'][-1]['dur_s']:.2f}s {man['falas'][-1]['vaga']}", flush=True)
    except Exception as e:                                     # noqa: BLE001
        man["erro"] = str(e)[:600]
    json.dump(man, open(MANIFESTO, "w"), ensure_ascii=False, indent=1)
    print("[narracao] contas:", json.dumps(man["contas"], ensure_ascii=False))
    if man["erro"]:
        print("[narracao] ERRO:", man["erro"]); sys.exit(1)
    print(f"[narracao] ok: {len(man['falas'])} falas, {sum(f['dur_s'] for f in man['falas']):.1f} s")
