#!/usr/bin/env python3
"""
esboco — desenha no log, em ASCII, a silhueta da folha do personagem e de
cada peca recortada dela.

POR QUE EXISTE
    Dois videos sairam errados (19 e 20/08) e nos dois o erro so apareceu
    depois de 13 minutos de render, no video pronto: as "pecas" eram
    treze desenhos de um homem inteiro. Numero nenhum denuncia isso --
    largura e altura de um homem inteiro sao numeros perfeitamente
    plausiveis para uma peca. O desenho denuncia.

    Entao roda como etapa separada, DEPOIS do preparar_assets.py: le o
    que ficou gravado no Storage e imprime. Se a silhueta da folha nao
    tiver cara de T (cabeca, barra horizontal dos bracos, tronco, duas
    pernas), da para parar antes de gastar o render.

    E diagnostico puro: nao grava nada, nao falha o job.

Uso:
    python3 esboco.py
"""
import io, os
import numpy as np
import requests
from PIL import Image

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_KEY"]
BUCKET = os.environ.get("SUPABASE_BUCKET", "toonzueira")
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

# ordem de leitura: como o corpo se monta, de cima para baixo
ORDEM = ("cabeca", "tronco", "braco_sup", "braco_inf", "perna_sup", "perna_inf",
         "boca_0", "boca_1", "boca_2", "boca_3",
         "olho_aberto", "olho_fechado", "sobrancelha")


def listar(prefixo):
    """Objetos diretamente sob um prefixo (sem recursao: basta aqui)."""
    r = requests.post(f"{SB}/storage/v1/object/list/{BUCKET}",
                      json={"prefix": prefixo, "limit": 200,
                            "sortBy": {"column": "name", "order": "asc"}},
                      headers={**H, "Content-Type": "application/json"}, timeout=60)
    r.raise_for_status()
    itens = r.json()
    arquivos = [prefixo + i["name"] for i in itens if i.get("id") or i.get("metadata")]
    pastas = [i["name"] for i in itens if not (i.get("id") or i.get("metadata"))]
    return arquivos, pastas


def baixar(caminho):
    r = requests.get(f"{SB}/storage/v1/object/{BUCKET}/{caminho}", headers=H, timeout=120)
    r.raise_for_status()
    return r.content


def esboco(img, largura=44):
    m = np.array(img.convert("RGBA").split()[-1]) > 10
    h, w = m.shape
    # 0.5 compensa o caractere de terminal ser ~2x mais alto que largo
    alt = max(int(largura * h / w * 0.5), 1)
    linhas = []
    for i in range(alt):
        y0 = int(i * h / alt)
        y1 = max(int((i + 1) * h / alt), y0 + 1)
        linha = ""
        for k in range(largura):
            x0 = int(k * w / largura)
            x1 = max(int((k + 1) * w / largura), x0 + 1)
            linha += "#" if m[y0:y1, x0:x1].mean() > 0.25 else "."
        linhas.append("    " + linha)
    return "\n".join(linhas)


def mostrar(caminho, largura, rotulo=None):
    try:
        img = Image.open(io.BytesIO(baixar(caminho))).convert("RGBA")
    except Exception as e:
        print(f"  [x] {caminho}: {e}")
        return
    print(f"  {rotulo or caminho}  {img.width}x{img.height}")
    print(esboco(img, largura))


def main():
    _, personagens = listar("assets/folha_personagem/")
    if not personagens:
        print("[esboco] nenhuma folha em assets/folha_personagem/")
        return

    for chave in personagens:
        print(f"\n{'=' * 60}\n== FOLHA RECEBIDA: {chave}\n{'=' * 60}")
        folhas, _ = listar(f"assets/folha_personagem/{chave}/")
        for f in folhas:
            if f.lower().endswith(".png"):
                mostrar(f, 60 if f.endswith("rosto.png") else 44)

        print(f"\n{'-' * 60}\n-- PECAS RECORTADAS: {chave}\n{'-' * 60}")
        pecas, _ = listar(f"assets/parte_personagem/{chave}/")
        achadas = {p.rsplit("/", 1)[-1].rsplit(".", 1)[0]: p
                   for p in pecas if p.lower().endswith(".png")}
        for nome in ORDEM:
            if nome in achadas:
                mostrar(achadas[nome], 14, rotulo=nome)
        sobrando = sorted(set(achadas) - set(ORDEM))
        if sobrando:
            print(f"  (pecas fora do vocabulario do rig: {sobrando})")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # diagnostico nunca derruba o job
        print(f"[esboco] falhou, seguindo mesmo assim: {e}")
