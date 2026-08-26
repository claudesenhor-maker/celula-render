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

COMO AS PECAS NASCEM (mudou em 20/08)
    Antes: uma geracao por peca, 13 no total. Falhou nas 13 -- voltaram
    13 desenhos de um HOMEM INTEIRO, e o rig empilhou sete homens. Ver
    folha_personagem.py para o diagnostico completo.

    Agora: o gerador desenha UMA folha do personagem inteiro em pose T,
    e o recorte das partes acontece aqui, por geometria. O modelo faz o
    que sabe fazer; a anatomia vira problema nosso. De quebra, cor de
    pele, roupa e traco ficam iguais entre as pecas porque saem todas da
    MESMA imagem.

O QUE FAZ
    1. lista assets_bruto/ no Storage (JPEG com fundo branco)
    2. roda rembg em cada um
    3. grava o PNG com alfa em assets/, que e de onde o cut-out le
    3b. para cada folha em assets/folha_personagem/<chave>/, valida a
       pose, fatia nas 6 pecas do corpo (+ as de rosto, se houver tira)
       e grava tudo em assets/parte_personagem/<chave>/
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

from folha_personagem import (ESPEC_ROSTO, PARTES_ESSENCIAIS, FolhaGrudada,
                              conferir_pecas, fatiar_rosto, segmentar_folha)
import segmentar as SEG

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_KEY"]
BUCKET = os.environ.get("SUPABASE_BUCKET", "toonzueira")
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

# Os 6 ossos sem os quais o palito_cutout.py nao consegue montar um frame
# (desenhar() em palito_cutout.py chama pers.p() para estes sem checar se
# existem antes). boca_*, olho_* e sobrancelha sao opcionais -- entram se
# tiverem sido geradas.
# Os ossos sem os quais o cut-out nao monta um frame. Vem de
# folha_personagem para nao existirem duas listas divergindo: quando o rig
# ganhou pulso, tornozelo e mandibula (21/08), esta lista teria ficado
# para tras e o partes.json seria gerado sem as pecas novas.
PARTES_MINIMAS = PARTES_ESSENCIAIS

# Altura do personagem no quadro de 1080x1920. 1150px ~= 60% da altura:
# corpo inteiro visivel com folga em cima e embaixo para o personagem
# pular e agachar sem sair do quadro.
ALTURA_ALVO_PX = 1150


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


def _pivo_base(img):
    """Peca sem convencao de osso propria (rosto, objeto): ancora na
    base central da arte. Serve tanto para 'apoiado no chao' (objeto)
    quanto para 'encostado no rosto' (boca/olho/sobrancelha sao coladas
    exatamente onde a cabeca e colada, entao precisam da mesma logica de
    ancoragem que a cabeca usa)."""
    w, h = img.size
    return (w / 2.0, float(h - 1))


def gerar_partes_json(prefixo_personagem):
    """Junta as pecas + ancoras num partes.json e num personagem.zip.

    Nao mede nada: quem mediu foi o segmentador, olhando a folha inteira.
    Aqui so se calcula a ESCALA -- a folha vem em ~1024px e o quadro do
    Shorts tem 1920, entao sem esticar o personagem sai do tamanho de um
    dedo no meio da tela (foi o que 'escala: 1.0' cravado produziu no
    primeiro teste)."""
    pecas_prontas = [c for c in listar(prefixo_personagem) if c.lower().endswith(".png")]
    if not pecas_prontas:
        return False

    imagens = {}
    for caminho in pecas_prontas:
        nome = caminho.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if nome.startswith("_"):
            continue                      # _mapa.png e conferencia, nao peca
        try:
            imagens[nome] = Image.open(io.BytesIO(baixar(caminho))).convert("RGBA")
        except Exception as e:
            print(f"[partes.json] nao consegui baixar {caminho}: {e}")

    try:
        ancoras = json.loads(baixar(prefixo_personagem + "ancoras.json"))
    except Exception as e:
        print(f"[partes.json] {prefixo_personagem}: sem ancoras.json ({e}); "
              f"sem elas o rig nao tem pivo -- refaca a leitura da folha")
        return False

    # SO entra em partes.json o que o segmentador MEDIU. A pasta do bucket
    # acumula PNG de rodadas antigas: o recorte geometrico deixou la boca_0..3,
    # olho_aberto, tronco, braco_sup, perna_inf... -- nomes que nem existem no
    # ESQUELETO de hoje. Nenhum deles tem pivo, e sem pivo o rig nao sabe onde
    # a peca gira: o cut-out morria com KeyError na primeira que encontrava.
    # Peca sem pivo medido nao e peca. Filtrar ANTES de conferir as essenciais,
    # senao uma sobra antiga faz a conferencia passar por engano.
    pivos = ancoras["pivos"]
    sobras = sorted(n for n in imagens if n not in pivos)
    if sobras:
        print(f"[partes.json] {prefixo_personagem}: {len(sobras)} peca(s) sem "
              f"pivo medido, ficam de fora: {', '.join(sobras)}")
        imagens = {n: im for n, im in imagens.items() if n in pivos}

    faltando = [p for p in PARTES_MINIMAS if p not in imagens]
    if faltando:
        print(f"[partes.json] {prefixo_personagem}: ainda faltam {faltando}, nao gerei")
        return False

    alt = max(ancoras.get("altura_figura", 0), 1)
    cfg = {
        "escala": round(ALTURA_ALVO_PX / alt, 3) if alt > 1 else 1.0,
        "partes": sorted(imagens.keys()),
        "pivos": pivos,
        "saidas": ancoras.get("saidas", {}),
        "comprimentos": ancoras.get("comprimentos", {}),
        "vaos": ancoras.get("vaos", {}),
    }
    partes_json_bytes = json.dumps(cfg, ensure_ascii=False, indent=2).encode("utf-8")
    subir(prefixo_personagem + "partes.json", partes_json_bytes, mime="application/json")
    print(f"[partes.json] {prefixo_personagem}: {len(imagens)} pecas, escala {cfg['escala']}")

    # job.py so liga o cut-out se receber spec.personagem_url apontando
    # para um .zip com partes.json + os PNG na RAIZ. Empacota aqui, na
    # mesma passada, para o zip nunca ficar desatualizado.
    buf_zip = io.BytesIO()
    with zipfile.ZipFile(buf_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("partes.json", partes_json_bytes)
        for nome, img in imagens.items():
            b = io.BytesIO()
            img.save(b, "PNG", optimize=True)
            zf.writestr(f"{nome}.png", b.getvalue())
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


def _salvar_peca(prefixo, nome, img):
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    subir(f"{prefixo}{nome}.png", buf.getvalue())


def fatiar_folha(chave):
    """assets/folha_personagem/<chave>/ -> assets/parte_personagem/<chave>/

    Refaz a leitura toda vez que roda. Ler nao custa chamada de API (o caro
    e gerar a folha, e a folha ja esta pronta), e assim uma folha corrigida
    vale na passada seguinte sem ninguem lembrar de limpar as pecas velhas.

    DOIS CAMINHOS, E O LOG DIZ QUAL RODOU
        Principal: a folha veio como boneco de papel, com vao entre as
        partes, e o segmentar.py le as pecas prontas com o pivo medido.
        Plano B: a folha veio grudada e nao ha o que segmentar -- a peca
        e recusada. Nao ha meio-termo silencioso, porque foi exatamente
        aceitar folha ruim em silencio que produziu os videos errados.
    """
    # LÊ A FOLHA CRUA, NÃO A DO REMBG. O rembg é um segmentador de objeto
    # saliente: ele marca a PESSOA inteira como frente, e os vãos entre as
    # peças -- que são o desenho todo -- vêm preenchidos junto. A folha
    # recortada por ele volta como uma mancha só e a segmentação morre com
    # "1 peça solta".
    #
    # Na folha crua o branco do fundo encosta na borda da imagem, e é
    # justamente isso que o segmentador usa para separar as peças: ele
    # inunda a partir da borda e o vão some junto com o fundo. Ou seja, o
    # recorte que interessa aqui já é feito por segmentar.py, de graça.
    origem = f"assets_bruto/folha_personagem/{chave}/"
    destino = f"assets/parte_personagem/{chave}/"
    achados = {c.rsplit("/", 1)[-1].rsplit(".", 1)[0]: c
               for c in listar(origem)
               if c.lower().endswith((".png", ".jpg", ".jpeg"))}
    if "corpo" not in achados:
        # folha antiga, que só existe já recortada
        achados = {c.rsplit("/", 1)[-1].rsplit(".", 1)[0]: c
                   for c in listar(f"assets/folha_personagem/{chave}/")
                   if c.lower().endswith(".png")}
    if "corpo" not in achados:
        print(f"[folha] {chave}: sem corpo.png, nao fatiei")
        return False

    folha = Image.open(io.BytesIO(baixar(achados["corpo"]))).convert("RGBA")
    try:
        pecas, ancoras = segmentar_folha(folha)
    except FolhaGrudada as e:
        print(f"[folha] {chave}: RECUSADA -- {e}")
        print(f"        a arte precisa vir com vao branco entre as partes; "
              f"mantive as pecas anteriores")
        return False

    problemas = conferir_pecas(pecas, ancoras)
    if problemas:
        # Nao sobrescreve o que ja esta la. Peca ruim que sobe so aparece
        # 13 minutos depois, no video pronto -- foi assim que o erro de
        # 19/08 passou batido.
        print(f"[folha] {chave}: REPROVADA na conferencia, mantive as pecas anteriores")
        for p in problemas:
            print(f"        - {p}")
        return False

    for nome, img in pecas.items():
        _salvar_peca(destino, nome, img)
    print(f"[folha] {chave}: {len(pecas)} pecas lidas da folha "
          f"({', '.join(sorted(pecas))})")

    # MAPA DE PECAS: a conferencia que um JSON de 24 entradas nao faz.
    # Cada peca de uma cor, o pivo marcado. Em um olhar da para ver se o
    # ombro foi parar no cotovelo, antes dos 13 minutos de render.
    buf = io.BytesIO()
    SEG.mapa_de_pecas(folha, pecas, ancoras).save(buf, "PNG", optimize=True)
    subir(destino + "_mapa.png", buf.getvalue())

    # As ancoras (pivo e ponto de encaixe de cada filho) valem mais que
    # qualquer medicao feita depois nas pecas soltas, e so existem aqui.
    subir(destino + "ancoras.json",
          json.dumps(ancoras, ensure_ascii=False).encode("utf-8"),
          mime="application/json")

    # Tira de rosto: opcional. Sem ela o personagem ainda fala, porque o
    # maxilar da folha ja abre.
    if "rosto" in achados:
        tira = Image.open(io.BytesIO(baixar(achados["rosto"]))).convert("RGBA")
        try:
            for nome, img in fatiar_rosto(tira).items():
                _salvar_peca(destino, nome, img)
            print(f"[folha] {chave}: {len(ESPEC_ROSTO)} pecas de rosto")
        except ValueError as e:
            print(f"[folha] {chave}: tira de rosto ignorada ({e})")

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

            # CENARIO NAO PASSA PELO REMBG.
            #
            # rembg e segmentador de OBJETO SALIENTE: decide qual e a figura
            # principal e apaga o resto. Num cenario nao ha figura principal
            # -- e essa a graca, o centro fica vazio para o personagem
            # ocupar -- entao ele apaga quase tudo e devolve um fantasma
            # lavado. Conferido em assets/cenario/geral/sala.png: a sala
            # inteira voltou como linha palida sobre transparencia.
            #
            # E fundo nao precisa de alfa: ele fica ATRAS de tudo. Aqui o
            # bruto so e reembalado como PNG, sem recorte nenhum.
            if bruto.startswith("assets_bruto/cenario/"):
                buf = io.BytesIO()
                img.save(buf, "PNG", optimize=True)
                subir(final, buf.getvalue())
                print(f"[ok] {final}  {img.width}x{img.height}  (cenario, sem rembg)")
                feitos += 1
                continue

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
    # Folha -> pecas. Roda antes do partes.json porque e ele que produz
    # os PNG que o partes.json vai medir.
    chaves_folha = sorted({
        b.split("/")[2] for b in brutos
        if b.startswith("assets_bruto/folha_personagem/") and len(b.split("/")) > 3
    })
    for chave in chaves_folha:
        fatiar_folha(chave)

    # Personagem pode chegar por folha (o caminho novo) ou por peca solta
    # em assets_bruto (personagem antigo, ou peca avulsa que o roteirista
    # pediu). Os dois caminhos convergem no mesmo partes.json.
    chaves_soltas = {
        b.split("/")[2] for b in brutos
        if b.startswith("assets_bruto/parte_personagem/") and len(b.split("/")) > 3
    }
    for chave in sorted(set(chaves_folha) | chaves_soltas):
        gerar_partes_json(f"assets/parte_personagem/{chave}/")

    prefixos_outros = sorted({
        b.split("/", 2)[1] + "/" + (b.split("/")[2] if len(b.split("/")) > 3 else "geral") + "/"
        for b in brutos
        if b.startswith("assets_bruto/")
        and not b.startswith("assets_bruto/parte_personagem/")
        and not b.startswith("assets_bruto/folha_personagem/")
    })
    for sufixo in prefixos_outros:
        gerar_pontos_json("assets/" + sufixo)

    if feitos == 0 and pulados == 0:
        print("[aviso] nada processado — rode o workflow 'Gerar Assets' antes")
        sys.exit(1)


if __name__ == "__main__":
    main()
