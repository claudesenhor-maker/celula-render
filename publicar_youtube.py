# -*- coding: utf-8 -*-
"""publicar_youtube.py -- o upload do canal EN sai dos EUA (30/09, HISTORICO §87).

POR QUE
    O maior publico do PAPERCUT (EN) era a Africa do Sul (Analytics: ZA 1.113
    views, EUA nenhuma). A causa: o n8n roda numa VM da Azure em JOANESBURGO
    (South Africa North), e o upload saia de um IP sul-africano -- o YouTube
    testa o Short primeiro no pais de onde ele vem. O PT nao sofre (o portugues
    puxa o Brasil); o ingles cai no pais do IP.

    Este script roda no GitHub Actions (runners nos EUA), chamado pelo
    `Adapter YouTube` via `repository_dispatch` (tipo `publicar`). Ele baixa o
    MP4 do bucket, sobe no canal com titulo, descricao, tags, idiomas e
    `publishAt`, e devolve o id ao n8n (`resume_url` do no Wait).

CADA CANAL SAI PELO PAIS DO SEU PUBLICO (02/10, HISTORICO §93)
    Ordem do dono: "mesmo que nao precise, quero o Brasil para o PT, por
    garantia; a VPN varia conforme o video". O payload traz `canal` (escolhe
    os segredos YT<canal>_*) e `saida` = {pais, metodo, segredo, exigir}, que
    e' `identidade_json.publicacao.saida` do canal:
      metodo `direto`    o proprio runner (EUA)
             `wireguard` o `publicar.yml` sobe o tunel com o segredo antes
             `proxy`     PROXY_URL (segredo) em todas as chamadas daqui
    O pais da saida e' CONFERIDO antes de subir. Diferente do pedido:
    `exigir: true` recusa (nada sobe); `false` sobe assim mesmo e avisa --
    o PT nao perde o video porque a VPN caiu (o portugues ja puxa o Brasil).

ENTRADA (variaveis de ambiente)
    PAYLOAD            o `client_payload` do dispatch, em JSON
    YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN   segredos do canal
    PROXY_URL          so' com `metodo: proxy` (http:// ou socks5h://)
    `ensaio: true` no payload faz tudo menos o upload (confere IP, token,
    canal e download) -- e' a prova sem publicar nada.
"""
import json
import os
import sys
import tempfile
import time

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"

# toda chamada daqui passa pela mesma sessao: com `metodo: proxy` ela leva o
# proxy do pais; com wireguard o tunel ja e' a rota da maquina inteira
S = requests.Session()
if os.environ.get("PROXY_URL"):
    S.proxies = {"http": os.environ["PROXY_URL"], "https": os.environ["PROXY_URL"]}


def pais_da_saida():
    try:
        j = S.get("https://ipinfo.io/json", timeout=15).json()
        return j.get("country", "?"), j.get("region", "?"), j.get("ip", "?")
    except Exception as e:                                          # noqa: BLE001
        return "?", str(e)[:60], "?"


def conferir_saida(saida, pais):
    """None = pode subir; texto = recusa (so' com `exigir`)."""
    alvo = str((saida or {}).get("pais") or "").upper()
    if not alvo or alvo == pais:
        return None
    msg = f"saida por {pais}, o canal pede {alvo} (metodo {(saida or {}).get('metodo', '?')})"
    if (saida or {}).get("exigir"):
        return msg
    print(f"[publicar] AVISO: {msg}; subindo assim mesmo (exigir=false)")
    return None


def token_de_acesso():
    r = S.post(TOKEN_URL, data={
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def devolver(p, corpo):
    url = p.get("resume_url")
    print("[publicar] resposta:", json.dumps({k: v for k, v in corpo.items() if k != "detalhe"})[:300])
    if not url:
        return
    for _ in range(3):
        try:
            # o callback ao n8n sai SEM o proxy: e' a nossa VM, nao o YouTube
            requests.post(url, json=corpo, timeout=30).raise_for_status()
            return
        except Exception as e:                                      # noqa: BLE001
            print("[publicar] callback falhou:", str(e)[:120])
            time.sleep(5)


def main():
    p = json.loads(os.environ.get("PAYLOAD") or "{}")
    saida = p.get("saida") or {}
    pais, regiao, ip = pais_da_saida()
    print(f"[publicar] canal {p.get('canal', '2')}: saida por {ip} ({pais}, {regiao}); "
          f"pedido {saida.get('pais', '-')} via {saida.get('metodo', 'direto')}")
    recusa = conferir_saida(saida, pais)
    if recusa:
        devolver(p, {"status": "erro", "erro": "pais errado: " + recusa, "pais_saida": pais})
        return 1
    try:
        tok = token_de_acesso()
        h = {"Authorization": "Bearer " + tok}
        canal = S.get("https://www.googleapis.com/youtube/v3/channels",
                             params={"part": "snippet", "mine": "true"}, headers=h, timeout=30).json()
        nome = ((canal.get("items") or [{}])[0].get("snippet") or {}).get("title", "?")
        print(f"[publicar] canal: {nome}")
        if p.get("ensaio") and not p.get("video_url"):
            devolver(p, {"status": "ensaio", "pais_saida": pais, "canal": nome})
            return 0
        # o MP4 vem do NOSSO bucket: sem proxy (nao gasta o tunel)
        mp4 = requests.get(p["video_url"], timeout=300)
        mp4.raise_for_status()
        print(f"[publicar] video: {len(mp4.content) // 1024} KB")
        if p.get("ensaio"):
            devolver(p, {"status": "ensaio", "pais_saida": pais, "canal": nome})
            return 0
        idioma = p.get("idioma") or "en-US"
        meta = {
            "snippet": {"title": p["titulo"][:100], "description": p.get("descricao") or "",
                        "tags": [t for t in str(p.get("tags") or "").split(",") if t.strip()][:30],
                        "categoryId": "23", "defaultLanguage": idioma, "defaultAudioLanguage": idioma},
            "status": {"privacyStatus": "private" if p.get("publicar_em") else "public",
                       "selfDeclaredMadeForKids": False},
        }
        if p.get("publicar_em"):
            meta["status"]["publishAt"] = p["publicar_em"]
        ini = S.post(UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status",
                                                "notifySubscribers": "true"},
                            headers=dict(h, **{"Content-Type": "application/json; charset=UTF-8",
                                               "X-Upload-Content-Type": "video/mp4",
                                               "X-Upload-Content-Length": str(len(mp4.content))}),
                            data=json.dumps(meta), timeout=60)
        ini.raise_for_status()
        up = S.put(ini.headers["Location"], data=mp4.content,
                          headers={"Content-Type": "video/mp4"}, timeout=600)
        up.raise_for_status()
        vid = up.json()["id"]
        print(f"[publicar] ok: https://www.youtube.com/shorts/{vid}")
        devolver(p, {"status": "ok", "id": vid, "pais_saida": pais, "canal": nome})
        return 0
    except Exception as e:                                          # noqa: BLE001
        devolver(p, {"status": "erro", "erro": f"{type(e).__name__}: {str(e)[:300]}", "pais_saida": pais})
        return 1


if __name__ == "__main__":
    sys.exit(main())
