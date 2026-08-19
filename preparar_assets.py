#!/usr/bin/env python3
"""
preparar_assets — recorta o fundo das pecas do personagem e calcula,
automaticamente, o pivo (ponto de rotacao) e o comprimento de cada osso
a partir da silhueta alfa. Isso e o que gera o partes.json que o
palito_cutout.py precisa -- sem ninguem medindo pixel na mao.

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
    4. para cada personagem com os 6 ossos essenciais prontos (cabeca,
       tronco, braco_sup, braco_inf, perna_sup, perna_inf), calcula o
       pivo e o comprimento de cada peca por geometria (PCA no alfa para
       os ossos, proporcao para o que nao da pra medir isolado -- ombro e
       pescoco) e sobe partes.json em assets/parte_personagem/<chave>/.
       Isso roda de novo a cada execucao: se o roteirista pedir uma peca
       nova (personagem secundario, por exemplo), na proxima passada por
       aqui o partes.json dele e criado sozinho, sem trabalho manual.
    5. para pecas que NAO sao parte de personagem (objetos que o
       personagem manipula, por exemplo), calcula so um ponto de ancora
       (base central da arte) e grava pontos.json na mesma pasta -- serve
       de base para quando o renderer ganhar suporte a objeto.

Uso:
    python3 preparar_assets.py            # so o que ainda nao tem versao final
    python3 preparar_assets.py --tudo     # refaz todos

Variaveis de ambiente:
    SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_BUCKET (padrao: toonzueira)
"""
import argparse, io, json, os, sys, zipfile
import numpy as np
import requests

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_KEY"]
BUCKET = os.environ.get("SUPABASE_BUCKET", "toonzueira")
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

# Os 6 ossos sem os quais o palito_cutout.py nao consegue montar um frame
# (desenhar() em palito_cutout.py chama pers.p() para estes sem checar se
# existem antes). boca_*, olho_* e sobrancelha sao opcionais -- entram se
# tiverem sido geradas.
PARTES_MINIMAS = ("cabeca", "tronco", "braco_sup", "braco_inf", "perna_sup", "perna_inf")


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


# =========================================================================
# Medicao automatica de pivo e comprimento a partir do alfa
# =========================================================================
def _mascara(img):
    return np.array(img.split()[-1]) > 10


def _medir_osso(img):
    """PCA sobre o alfa: acha o eixo principal do 'osso' e devolve
    (pivo, comprimento). Convencao: braco_sup/braco_inf/perna_sup/
    perna_inf sao desenhados pendurados a partir da articulacao proximal
    (ombro, cotovelo, quadril, joelho), entao o pivo fica na extremidade
    de CIMA do desenho -- e essa extremidade que o rig gruda no corpo."""
    a = _mascara(img)
    ys, xs = np.nonzero(a)
    if len(xs) < 2:
        w, h = img.size
        return (w / 2.0, 0.0), float(h)
    pts = np.column_stack([xs, ys]).astype(float)
    media = pts.mean(axis=0)
    cov = np.cov((pts - media).T)
    autovals, autovecs = np.linalg.eigh(cov)
    eixo = autovecs[:, int(np.argmax(autovals))]
    proj = (pts - media) @ eixo
    faixa = proj.max() - proj.min()
    tolerancia = max(faixa * 0.02, 1.5)   # janela pequena nas pontas
    # Numa ponta reta (ex: topo do braco cortado na horizontal) varios
    # pixels empatam na projecao extrema; usar so um deles jogaria o pivo
    # pra a borda em vez do centro. Faz a media de todos os pixels dentro
    # da tolerancia da ponta.
    ponta_a = pts[proj <= proj.min() + tolerancia].mean(axis=0)
    ponta_b = pts[proj >= proj.max() - tolerancia].mean(axis=0)
    comprimento = float(np.hypot(*(ponta_b - ponta_a)))
    pivo = ponta_a if ponta_a[1] <= ponta_b[1] else ponta_b
    return (float(pivo[0]), float(pivo[1])), comprimento


def _medir_tronco(img):
    """Pivo no quadril (base da arte), comprimento ate a linha do ombro.
    A linha do ombro e estimada a 82% da altura, de baixo pra cima --
    sobra ~18% de peito/pescoco no topo, que e onde braco e cabeca se
    encaixam."""
    w, h = img.size
    return (w / 2.0, float(h - 1)), h * 0.82


def _linha_ombro(img, frac=0.12):
    """Largura do alfa numa linha perto do topo do tronco: da meio_ombro
    (metade da largura ali) e queda_ombro (o quanto essa linha esta
    abaixo do topo da arte -- o "arredondado" natural do ombro)."""
    a = _mascara(img)
    h = a.shape[0]
    linha = min(max(int(h * frac), 0), h - 1)
    cols = np.nonzero(a[linha])[0]
    if len(cols) == 0:
        w = img.size[0]
        return w * 0.35, h * frac
    largura = float(cols.max() - cols.min())
    return largura / 2.0, float(linha)


def _pivo_base(img):
    """Peca sem convencao de osso propria (rosto, objeto): ancora na
    base central da arte. Serve tanto para 'apoiado no chao' (objeto)
    quanto para 'encostado no rosto' (boca/olho/sobrancelha sao coladas
    exatamente onde a cabeca e colada, entao precisam da mesma logica de
    ancoragem que a cabeca usa)."""
    w, h = img.size
    return (w / 2.0, float(h - 1))


def medir_partes(pecas):
    """pecas: {nome: PIL.Image RGBA ja recortada}. Devolve (pivos, comp)
    prontos para o partes.json.

    O que da pra medir direto da silhueta: pivo e comprimento de cada
    osso, e o pivo da cabeca e das pecas de rosto. O que NAO tem como
    medir olhando uma peca isolada -- meio_ombro, queda_ombro, pescoco --
    e estimado por proporcao a partir do proprio tronco e cabeca. Sao
    heuristicas, nao anatomia exata: servem de ponto de partida e podem
    ser corrigidas a mao depois de ver o primeiro render (o arquivo
    continua sendo um JSON normal, editar um numero nao quebra nada)."""
    pivos, comp = {}, {}

    for nome in ("braco_sup", "braco_inf", "perna_sup", "perna_inf"):
        if nome in pecas:
            pivos[nome], comp[nome] = _medir_osso(pecas[nome])

    if "tronco" in pecas:
        pivos["tronco"], comp["tronco"] = _medir_tronco(pecas["tronco"])
        meio_ombro, linha_y = _linha_ombro(pecas["tronco"])
        comp["meio_ombro"] = meio_ombro
        comp["queda_ombro"] = linha_y

    if "cabeca" in pecas:
        pivos["cabeca"] = _pivo_base(pecas["cabeca"])
        # pescoco: gap entre o topo do tronco e o pivo da cabeca. Sem
        # medida melhor disponivel, uso uma fracao pequena da altura da
        # cabeca -- pescoco curto, que e o padrao em boneco palito.
        comp["pescoco"] = pecas["cabeca"].size[1] * 0.15

    for nome, img in pecas.items():
        if nome.startswith("boca_") or nome in ("olho_aberto", "olho_fechado", "sobrancelha"):
            pivos[nome] = _pivo_base(img)

    return pivos, comp


def gerar_partes_json(prefixo_personagem):
    """Baixa tudo que existe em assets/parte_personagem/<chave>/, mede e
    sobe o partes.json. So gera se os 6 ossos essenciais existirem --
    caso contrario o cut-out nem consegue montar um frame."""
    pecas_prontas = [c for c in listar(prefixo_personagem) if c.lower().endswith(".png")]
    if not pecas_prontas:
        return False

    imagens = {}
    for caminho in pecas_prontas:
        nome = caminho.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        try:
            imagens[nome] = Image.open(io.BytesIO(baixar(caminho))).convert("RGBA")
        except Exception as e:
            print(f"[partes.json] nao consegui baixar {caminho}: {e}")

    faltando = [p for p in PARTES_MINIMAS if p not in imagens]
    if faltando:
        print(f"[partes.json] {prefixo_personagem}: ainda faltam {faltando}, nao gerei")
        return False

    pivos, comp = medir_partes(imagens)
    cfg = {
        "escala": 1.0,
        "partes": sorted(imagens.keys()),
        "pivos": {k: [round(v[0], 1), round(v[1], 1)] for k, v in pivos.items()},
        "comprimentos": {k: round(v, 1) for k, v in comp.items()},
    }
    partes_json_bytes = json.dumps(cfg, ensure_ascii=False, indent=2).encode("utf-8")
    subir(prefixo_personagem + "partes.json", partes_json_bytes, mime="application/json")
    print(f"[partes.json] {prefixo_personagem}: {len(imagens)} pecas medidas e salvas")

    # job.py (SELECAO DO MOTOR) so liga o cut-out se receber spec.personagem_url
    # apontando para um .zip com partes.json + os PNG das pecas na RAIZ do
    # arquivo. Empacota aqui, na mesma passada, para o zip nunca ficar
    # desatualizado em relacao ao partes.json que acabou de subir.
    buf_zip = io.BytesIO()
    with zipfile.ZipFile(buf_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("partes.json", partes_json_bytes)
        for nome, img in imagens.items():
            buf_png = io.BytesIO()
            img.save(buf_png, "PNG", optimize=True)
            zf.writestr(f"{nome}.png", buf_png.getvalue())
    subir(prefixo_personagem + "personagem.zip", buf_zip.getvalue(), mime="application/zip")
    print(f"[personagem.zip] {prefixo_personagem}: {len(imagens)} pecas empacotadas")
    return True


def gerar_pontos_json(prefixo):
    """Para pastas que NAO sao parte_personagem (objetos, por exemplo):
    so um ponto de ancora por peca (base central), sem rig de osso. Fica
    pronto para quando o renderer ganhar suporte a compor objeto sobre a
    cena -- hoje so grava o dado, nao muda o video."""
    pecas_prontas = [c for c in listar(prefixo) if c.lower().endswith(".png")]
    if not pecas_prontas:
        return False
    pontos = {}
    for caminho in pecas_prontas:
        nome = caminho.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        try:
            img = Image.open(io.BytesIO(baixar(caminho))).convert("RGBA")
        except Exception as e:
            print(f"[pontos.json] nao consegui baixar {caminho}: {e}")
            continue
        pivo = _pivo_base(img)
        pontos[nome] = {"pivo": [round(pivo[0], 1), round(pivo[1], 1)],
                         "largura": img.size[0], "altura": img.size[1]}
    if not pontos:
        return False
    subir(prefixo + "pontos.json", json.dumps(pontos, ensure_ascii=False, indent=2).encode("utf-8"),
          mime="application/json")
    print(f"[pontos.json] {prefixo}: {len(pontos)} pecas com ancora calculada")
    return True


def main():
    global Image
    ap = argparse.ArgumentParser()
    ap.add_argument("--tudo", action="store_true", help="refaz mesmo o que ja existe")
    a = ap.parse_args()

    from rembg import remove, new_session
    from PIL import Image as _Image
    Image = _Image

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

    # ---------------------------------------------------------------
    # partes.json / pontos.json: roda sempre, mesmo se nada foi recortado
    # agora (--tudo=False e tudo ja existia) -- garante que uma peca nova
    # pedida pelo roteirista, assim que estiver recortada, ganhe pivo e
    # comprimento sem ninguem precisar rodar nada a mais.
    prefixos_personagem = sorted({
        b.split("/", 2)[1] + "/" + b.split("/")[2] + "/"
        for b in brutos
        if b.startswith("assets_bruto/parte_personagem/") and len(b.split("/")) > 3
    })
    for sufixo in prefixos_personagem:
        gerar_partes_json("assets/" + sufixo)

    prefixos_outros = sorted({
        b.split("/", 2)[1] + "/" + (b.split("/")[2] if len(b.split("/")) > 3 else "geral") + "/"
        for b in brutos
        if b.startswith("assets_bruto/") and not b.startswith("assets_bruto/parte_personagem/")
    })
    for sufixo in prefixos_outros:
        gerar_pontos_json("assets/" + sufixo)

    if feitos == 0 and pulados == 0:
        print("[aviso] nada processado — rode o workflow 'Gerar Assets' antes")
        sys.exit(1)


if __name__ == "__main__":
    main()
