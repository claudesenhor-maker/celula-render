# -*- coding: utf-8 -*-
"""workers_ai.py -- a Workers AI da Cloudflare a partir desta maquina.

    Duas portas, nesta ordem (a mesma escada de `sob_demanda`):
      1. `CF_API_TOKEN` no ambiente -> chamada direta;
      2. o proxy de laboratorio no n8n (`Celula IA · Lab · Proxy Workers AI
         (TEMP)`, webhook `lab-workers-ai`), que tem a credencial `cloudflare`
         viva. Corpo: {"modelo": "@cf/...", "corpo": {...tal qual a API}};
         devolve a imagem em binario (o no 'Sempre binario' converte o
         base64 do FLUX).

    Modelos que interessam aqui (15/09):
      texto -> imagem   @cf/black-forest-labs/flux-1-schnell (quadrado, base64)
                        @cf/bytedance/stable-diffusion-xl-lightning (w/h, negativo)
      imagem -> imagem  @cf/runwayml/stable-diffusion-v1-5-img2img
      inpainting        @cf/runwayml/stable-diffusion-v1-5-inpainting
                        (prompt, image_b64 | image[], mask[], strength, guidance)

    A imagem vai como `image_b64`; a mascara vai como lista de uint8 (a API
    so aceita assim), branca onde PODE repintar.
"""
import base64
import io
import os

import requests
from PIL import Image

CF_CONTA = os.environ.get("CF_ACCOUNT_ID") or "04483caa8b5f9674b84399fcdd1ef9d5"
CF_TOKEN = os.environ.get("CF_API_TOKEN")
N8N = (os.environ.get("N8N_BASE") or "https://toonzueira.duckdns.org").rstrip("/")
PROXY = f"{N8N}/webhook/lab-workers-ai"

FLUX = "@cf/black-forest-labs/flux-1-schnell"
SDXL = "@cf/bytedance/stable-diffusion-xl-lightning"
IMG2IMG = "@cf/runwayml/stable-diffusion-v1-5-img2img"
INPAINT = "@cf/runwayml/stable-diffusion-v1-5-inpainting"


def _png_b64(img):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _lista_uint8(mask):
    """A API quer a mascara como array de bytes de um PNG, nao pixels."""
    buf = io.BytesIO()
    mask.convert("L").save(buf, "PNG")
    return list(buf.getvalue())


def rodar(modelo, corpo, timeout=240):
    """Bytes da imagem, ou None (com o motivo no print)."""
    if CF_TOKEN:
        url = f"https://api.cloudflare.com/client/v4/accounts/{CF_CONTA}/ai/run/{modelo}"
        try:
            r = requests.post(url, json=corpo, timeout=timeout,
                              headers={"Authorization": f"Bearer {CF_TOKEN}"})
            r.raise_for_status()
            if r.headers.get("content-type", "").startswith("image/"):
                return r.content
            b64 = (r.json().get("result") or {}).get("image")
            return base64.b64decode(b64) if b64 else None
        except Exception as e:                                          # noqa: BLE001
            print(f"[workers-ai] direto falhou ({e}); tentando o proxy")
    try:
        r = requests.post(PROXY, json={"modelo": modelo, "corpo": corpo}, timeout=timeout)
        if r.status_code == 404:
            print("[workers-ai] o proxy `lab-workers-ai` nao esta ATIVO no n8n "
                  "(fluxo iZZpPlmgZJrgQVwD): ligar la, ou exportar CF_API_TOKEN")
            return None
        r.raise_for_status()
        if r.content[:5] == b"ERRO ":
            print(f"[workers-ai] {r.content[:400].decode('utf-8', 'replace')}")
            return None
        return r.content
    except Exception as e:                                              # noqa: BLE001
        print(f"[workers-ai] proxy falhou ({e})")
        return None


def imagem(modelo, corpo, timeout=240):
    dados = rodar(modelo, corpo, timeout)
    if not dados:
        return None
    try:
        return Image.open(io.BytesIO(dados)).convert("RGB")
    except Exception as e:                                              # noqa: BLE001
        print(f"[workers-ai] resposta nao e' imagem ({e}): {dados[:200]!r}")
        return None


def texto_para_imagem(prompt, negativo="", largura=1024, altura=1024, modelo=None, passos=8, semente=None,
                      esteira=None):
    """Texto -> imagem. `esteira=(tipo, chave)` liga o TERCEIRO degrau: a
    esteira `Gerar Assets` do n8n (webhook `gerar-assets`), que tem a
    credencial da Cloudflare e sobe o bruto no bucket -- provada em 13/09
    (`sob_demanda._pela_esteira`). So' texto -> imagem, quadrado, FLUX; o
    prompt vai como `desc_en` e a esteira acrescenta "ISOLATED single object
    on white" + traco/cores da biblia. Use tipo `lab_*` para NAO tocar no
    catalogo de producao (o caminho do bucket e o registro saem do tipo)."""
    modelo = modelo or (FLUX if largura == altura == 1024 else SDXL)
    if modelo == FLUX:
        corpo = {"prompt": prompt[:2040], "steps": min(passos, 8)}
    else:
        corpo = {"prompt": prompt[:2040], "negative_prompt": negativo,
                 "width": largura, "height": altura, "num_steps": passos}
    if semente is not None:
        corpo["seed"] = int(semente)
    # sem token, a esteira vem ANTES do proxy: o proxy (16/09) responde
    # `{"ok":true}` sem a imagem -- o `responseData: firstEntryBinary` do
    # webhook esta' dentro de `options`, onde so' vale para `onReceived` --
    # e cada tentativa nele custa a geracao inteira para nada
    if esteira and not CF_TOKEN:
        return pela_esteira(esteira[0], esteira[1], prompt)
    img = imagem(modelo, corpo)
    if img is None and esteira:
        img = pela_esteira(esteira[0], esteira[1], prompt)
    return img


SB_PUBLICO = "https://fejivjwyadbawjdhldbj.supabase.co/storage/v1/object/public/toonzueira"
ESPERA_ESTEIRA_S = 360
COTA_ESGOTADA = [False]      # por processo: depois de tres 429, ninguem mais pede hoje


def cota_livre():
    """Um pedido minimo ao proxy so' para ler a resposta da Cloudflare:
    True se ela atende, False se ainda esta' em 429 (cota do dia)."""
    try:
        r = requests.post(PROXY, json={"modelo": FLUX, "corpo": {"prompt": "a red dot", "steps": 1}}, timeout=120)
        return b"429" not in r.content[:600]
    except Exception:                                                   # noqa: BLE001
        return False


def pela_esteira(tipo, chave, desc_en, forcar=True):
    """Pede UMA arte a esteira `gerar-assets` e baixa o bruto (JPG, fundo
    branco) do bucket. Devolve PIL RGB ou None."""
    import time
    alvo = f"{SB_PUBLICO}/assets_bruto/{tipo}/geral/{chave}.jpg"
    if COTA_ESGOTADA[0]:
        print(f"[workers-ai] {tipo}|{chave}: cota da Cloudflare esgotada hoje; nao pedi")
        return None
    print(f"[workers-ai] esteira gerar-assets: {tipo}|{chave} ...")
    # A CLOUDFLARE DEVOLVE 429 DE DOIS JEITOS (16/09): capacidade momentanea
    # (passa em segundos) e a COTA DO DIA (10 mil neurons; ~65 imagens FLUX
    # de 1024; zera as 00:00 UTC). A esteira responde 500 "No item to
    # return" nos dois. Duas tentativas com espera; na terceira recusa, e'
    # cota: marca e para de pedir -- esperar 3 min por objeto e' desperdicio.
    ok = False
    for tentativa in range(3):
        try:
            r = requests.post(f"{N8N}/webhook/gerar-assets", timeout=ESPERA_ESTEIRA_S,
                              json={"forcar": bool(forcar), "apenas": [f"{tipo}|{chave}"],
                                    "pecas": [{"tipo": tipo, "chave": chave, "desc_en": desc_en[:1500]}]})
            if r.status_code == 500 and "No item" in r.text:
                if tentativa == 2:
                    COTA_ESGOTADA[0] = True
                    print("[workers-ai] a Cloudflare recusou tres vezes: cota do dia esgotada "
                          "(zera as 00:00 UTC). Os proximos pedidos nao serao feitos.")
                    return None
                print(f"[workers-ai] a Cloudflare recusou (429 por tras do 500); "
                      f"tentativa {tentativa + 1}/3, esperando {30 * (tentativa + 1)}s")
                time.sleep(30 * (tentativa + 1))
                continue
            r.raise_for_status()
            ok = True
            break
        except Exception as e:                                          # noqa: BLE001
            print(f"[workers-ai] a esteira nao respondeu ({e}); tentativa {tentativa + 1}/3")
            time.sleep(20)
    if not ok:
        return None
    time.sleep(6)                                    # respiro para o pedido seguinte
    for tentativa in range(4):
        try:
            g = requests.get(alvo, timeout=90, headers={"Cache-Control": "no-cache"},
                             params={"t": int(time.time())})
            if g.status_code == 200 and len(g.content) > 2000:
                return Image.open(io.BytesIO(g.content)).convert("RGB")
        except Exception:                                               # noqa: BLE001
            pass
        time.sleep(6)
    print(f"[workers-ai] a esteira disse ok mas {alvo} nao apareceu")
    return None


def inpaint(img, mask, prompt, negativo="", forca=1.0, guia=7.5, passos=20, semente=None, modelo=INPAINT):
    """Repinta `img` onde `mask` e' branca. `img` e `mask` PIL, mesmo tamanho."""
    corpo = {"prompt": prompt[:2040], "negative_prompt": negativo,
             "image_b64": _png_b64(img), "mask": _lista_uint8(mask),
             "width": img.width, "height": img.height,
             "strength": float(forca), "guidance": float(guia), "num_steps": int(passos)}
    if semente is not None:
        corpo["seed"] = int(semente)
    return imagem(modelo, corpo, timeout=300)


def img2img(img, prompt, negativo="", forca=0.6, guia=7.5, passos=20, semente=None, modelo=IMG2IMG):
    corpo = {"prompt": prompt[:2040], "negative_prompt": negativo,
             "image_b64": _png_b64(img), "width": img.width, "height": img.height,
             "strength": float(forca), "guidance": float(guia), "num_steps": int(passos)}
    if semente is not None:
        corpo["seed"] = int(semente)
    return imagem(modelo, corpo, timeout=300)
