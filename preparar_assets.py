#!/usr/bin/env python3
"""
preparar_assets — recorta o fundo das pecas do personagem.

POR QUE ESTA ETAPA EXISTE
    Nenhum gerador de imagem gratuito devolve canal alfa. Testamos quatro:

      ElevenLabs  /v1/flows/image  -> 402, exige plano Pro
      Gemini      2.5-flash-image  -> 429, limite 0 no free
      Recraft     API              -> cobra (o free e so no app)
      Together    FLUX schnell     -> gratuito, mas sem alfa

    O padrao e claro: no app o freio e o clique humano; na API um laco mal
    escrito queima mil chamadas. Todo mundo fecha a API.

    A saida foi separar os dois problemas. O gerador so precisa desenhar
    bem; o recorte vira etapa nossa, aqui, de graca. Isso tambem torna o
    gerador intercambiavel -- trocar a Cloudflare por outro provedor nao
    mexe em nada deste arquivo.

O QUE FAZ
    1. lista assets_bruto/ no Storage (JPEG com fundo branco)
    2. roda rembg em cada um
    3. grava o PNG com alfa em assets/, que e de onde o cut-out le

Uso:
    python3 preparar_assets.py            # so o que ainda nao tem versao final
    python3 preparar_assets.py --tudo     # refaz todos

Variaveis de ambiente:
    SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_BUCKET (padrao: toonzueira)
"""
import argparse, io, os, sys
import requests

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_KEY"]
BUCKET = os.environ.get("SUPABASE_BUCKET", "toonzueira")
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}


def listar(prefixo):
    """Lista recursivamente os objetos sob um prefixo."""
    achados = []
    fila = [prefixo]
    while fila:
        pasta = fila.pop()
        r = requests.post(f"{SB}/storage/v1/object/list/{BUCKET}",
                          json={"prefix": pasta, "limit": 200,
                                "sortBy": {"column": "name", "order": "asc"}},
                          headers={**H, "Content-Type": "application/json"}, timeout=60)
        r.raise_for_status()
        for it in r.json():
            nome = it.get("name", "")
            caminho = f"{pasta}{nome}" if pasta.endswith("/") else f"{pasta}/{nome}"
            # objeto de verdade tem metadata; sem metadata e "pasta"
            if it.get("id") or it.get("metadata"):
                achados.append(caminho)
            else:
                fila.append(caminho + "/")
    return achados


def baixar(caminho):
    r = requests.get(f"{SB}/storage/v1/object/{BUCKET}/{caminho}", headers=H, timeout=120)
    r.raise_for_status()
    return r.content


def subir(caminho, dados, mime="image/png"):
    r = requests.put(f"{SB}/storage/v1/object/{BUCKET}/{caminho}", data=dados,
                       headers={**H, "Content-Type": mime, "x-upsert": "true"}, timeout=180)
    if r.status_code >= 400:
        print(f"[erro] upload {caminho}: {r.status_code} {r.text[:200]}")
        r.raise_for_status()


def existe(caminho):
    r = requests.head(f"{SB}/storage/v1/object/{BUCKET}/{caminho}", headers=H, timeout=30)
    return r.status_code == 200


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tudo", action="store_true", help="refaz mesmo o que ja existe")
    a = ap.parse_args()

    from rembg import remove, new_session
    from PIL import Image

    # u2netp: modelo leve (~4 MB contra ~176 MB do u2net). Para desenho com
    # contorno preto sobre fundo branco chapado o resultado e equivalente, e
    # ele baixa em segundos em vez de minutos.
    sessao = new_session("u2netp")

    brutos = [c for c in listar("assets_bruto/") if c.lower().endswith((".jpg", ".jpeg", ".png"))]
    print(f"[assets] {len(brutos)} imagens brutas encontradas")

    feitos, pulados = 0, 0
    for bruto in brutos:
        final = bruto.replace("assets_bruto/", "assets/", 1).rsplit(".", 1)[0] + ".png"
        if not a.tudo and existe(final):
            pulados += 1
            continue
        try:
            img = Image.open(io.BytesIO(baixar(bruto))).convert("RGB")
            recortada = remove(img, session=sessao).convert("RGBA")

            # Corta a moldura vazia: o gerador centraliza a peca num quadrado
            # e sobra muito transparente em volta. Sem este corte, o pivo
            # anotado em partes.json fica deslocado do desenho de verdade.
            caixa = recortada.getbbox()
            if caixa:
                recortada = recortada.crop(caixa)

            buf = io.BytesIO()
            recortada.save(buf, "PNG", optimize=True)
            subir(final, buf.getvalue())
            print(f"[ok] {final}  {recortada.width}x{recortada.height}")
            feitos += 1
        except Exception as e:
            print(f"[falhou] {bruto}: {e}")

    print(f"[assets] {feitos} recortadas, {pulados} ja existiam")
    if feitos == 0 and pulados == 0:
        print("[aviso] nada processado — rode o workflow 'Gerar Assets' antes")
        sys.exit(1)


if __name__ == "__main__":
    main()
