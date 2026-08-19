#!/usr/bin/env python3
"""
job.py — ponto de entrada do render node no GitHub Actions.

Baixa o spec, renderiza com palito_v5 (VOZ PRIMEIRO), sobe o MP4 no
Supabase Storage e avisa o n8n pelo callback.

Variáveis de ambiente:
  SPEC_URL              URL pública do spec.json
  CALLBACK_URL          webhook do n8n que retoma o nó Wait
  SUPABASE_URL          https://SEUPROJETO.supabase.co
  SUPABASE_SERVICE_KEY  service_role key
  SUPABASE_BUCKET       padrão: toonzueira
"""
import os, sys, time, json, traceback
from pathlib import Path
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from palito_v5 import render_spec

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_KEY"]
BUCKET = os.environ.get("SUPABASE_BUCKET", "toonzueira")


def subir(local, remoto, mime="video/mp4"):
    dados = Path(local).read_bytes()
    # PUT com x-upsert e o caminho que sobrescreve. POST devolve 400/409
    # quando o objeto ja existe, e reprocessar o mesmo fila_id e comum.
    r = requests.put(f"{SB}/storage/v1/object/{BUCKET}/{remoto}",
                     data=dados,
                     headers={"apikey": KEY, "Authorization": f"Bearer {KEY}",
                              "Content-Type": mime, "x-upsert": "true"},
                     timeout=300)
    if r.status_code >= 400:
        # sem o corpo da resposta, um 400 do Storage nao diz nada: pode ser
        # chave errada, bucket inexistente ou nome de objeto invalido
        print(f"[upload] {r.status_code} em {remoto}: {r.text[:400]}")
        r.raise_for_status()
    print(f"[upload] {r.status_code}  {len(dados)/1e6:.2f} MB")
    return f"{SB}/storage/v1/object/public/{BUCKET}/{remoto}"


def atualizar_fila(fila_id, campos):
    """Escreve o resultado DIRETO na fila_producao do Supabase.

    Por que assim, e nao por webhook de volta para o n8n:
      - o certificado do Caddy esta quebrado (§2 do HANDOFF); clientes TLS
        rigorosos nao alcancam toonzueira.duckdns.org
      - dispensa o no Wait, que prendia uma execucao por ate 20 min numa
        VM de 892 MB
      - o Dispatcher ja repesca 'pronto_para_publicar' a cada 10 min, entao
        a publicacao acontece sozinha, sem codigo novo
    """
    if not fila_id or fila_id == "sem-id":
        print("[fila] sem fila_id, pulando"); return
    r = requests.patch(
        f"{SB}/rest/v1/fila_producao?fila_id=eq.{fila_id}",
        json=campos,
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"},
        timeout=60)
    print(f"[fila] {r.status_code} -> {campos.get('status')}")
    r.raise_for_status()


def avisar(payload):
    """Callback opcional. Se o certificado do n8n estiver ok, avisa tambem."""
    cb = os.environ.get("CALLBACK_URL")
    if not cb:
        return
    try:
        requests.post(cb, json=payload, timeout=30)
        print(f"[callback] {payload.get('status')}")
    except Exception as e:
        print(f"[callback] falhou (nao e critico): {e}")


def main():
    t0 = time.time()
    spec_json = os.environ.get("SPEC_JSON")
    if spec_json:
        spec = json.loads(spec_json)
    else:
        spec = requests.get(os.environ["SPEC_URL"], timeout=60).json()
    fila_id = spec.get("fila_id", "sem-id")
    print(f"[job] fila_id={fila_id}  trechos={len(spec['trechos'])}")

    # trilha opcional, vinda do bucket
    if spec.get("musica_url"):
        m = "/tmp/mus.mp3"
        Path(m).write_bytes(requests.get(spec["musica_url"], timeout=120).content)
        spec["musica"] = m

    out = "/tmp/final.mp4"

    # ---- ESCOLHA DO MOTOR --------------------------------------------
    # Se existir arte do personagem (um .zip com os PNG das pecas), roda o
    # CUT-OUT: pecas desenhadas de verdade, giradas e compostas pelo rig.
    # Sem arte, cai no rig VETORIAL, que desenha tudo por codigo.
    #
    # O vetor resolve consistencia, mas nao resolve: personagem sem chao,
    # traco oscilando, ausencia de partes moveis. O cut-out resolve os tres
    # -- e por isso ele e o alvo. O vetor fica como rede de seguranca para
    # o dia em que a arte faltar; melhor video feio que producao parada.
    pecas_url = spec.get("personagem_url") or os.environ.get("PERSONAGEM_URL", "")
    motor = "vetor"
    if pecas_url:
        try:
            import zipfile, io
            pasta = "/tmp/personagem"
            os.makedirs(pasta, exist_ok=True)
            dados = requests.get(pecas_url, timeout=120).content
            zipfile.ZipFile(io.BytesIO(dados)).extractall(pasta)
            if not os.path.exists(os.path.join(pasta, "partes.json")):
                raise RuntimeError("o zip nao tem partes.json na raiz")
            from palito_cutout import render as render_cutout
            print(f"[motor] cut-out ({len(dados)/1024:.0f} KB de arte)")
            motor = "cutout"
            _, dur = render_cutout(pasta, spec, out, tmpdir="/tmp/render")
        except Exception as e:
            print(f"[motor] cut-out falhou ({e}); caindo para o rig vetorial")
            motor = "vetor"
    if motor == "vetor":
        print("[motor] rig vetorial")
        # modo 'real' = Edge-TTS. O runner do GitHub tem rede.
        _, dur = render_spec(spec, out, modo=os.environ.get("MODO_TTS", "real"),
                             tmpdir="/tmp/render")

    # guarda de duração: 15-25s é o alvo do formato
    if not (12.0 <= dur <= 30.0):
        print(f"[aviso] duracao {dur}s fora da faixa 15-25s")

    url = subir(out, f"videos/{fila_id}.mp4")
    print(f"[ok] {url}  {dur}s  render={time.time()-t0:.0f}s")

    # Devolve o item para a fila. O Dispatcher pega no proximo ciclo de 10 min.
    atualizar_fila(fila_id, {
        "status": "pronto_para_publicar",
        "video_url": url,
        "atualizado_em": "now()",
    })
    avisar({"fila_id": fila_id, "status": "ok", "video_url": url,
            "duracao_s": dur, "render_s": round(time.time() - t0)})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        # Item que fica em 'aguardando_render' para sempre é o bug de "item
        # preso" do §6. Marca 'erro' — que a Manutenção sabe repescar.
        # NUNCA 'erro_publicacao': é beco sem saída (§7).
        fid = os.environ.get("FILA_ID", "")
        try:
            atualizar_fila(fid, {"status": "erro", "atualizado_em": "now()"})
        except Exception as e2:
            print(f"[fila] nao consegui marcar erro: {e2}")
        avisar({"fila_id": fid, "status": "erro", "erro_msg": str(e)[:500]})
        sys.exit(1)
