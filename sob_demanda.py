#!/usr/bin/env python3
"""
sob_demanda — a arte que o roteiro pediu e ninguém desenhou ainda.

O DEFEITO QUE ORIGINOU ISTO
    O vocabulário de cenário e de objeto é fechado de propósito (lei 6 e
    lei 11 do MAPA): o que o roteirista escreve tem que existir em arte,
    senão vira defeito na tela. Mas "fechado" virou "congelado": oito
    cenários e cinco objetos, escolhidos numa tarde de agosto, decidindo
    para sempre sobre o que este canal consegue fazer piada. Uma esquete
    numa praia, numa fila de banco com guichê, com um boleto na mão, não
    tinha como existir -- e o roteirista, obrigado a escolher do menu,
    escrevia outra história.

    O catálogo continua fechado NO INSTANTE em que o spec é montado. O que
    muda é que ele CRESCE: pedido novo vira arte, e a arte entra no
    catálogo para todos os vídeos seguintes.

AS DUAS METADES, QUE TÊM CUSTOS DIFERENTES
    CENÁRIO é imediato. Ele vai para `assets_bruto/` e o motor lê o bruto
    direto -- não passa por rembg, porque rembg destrói cenário (lei 8).
    São ~20 segundos entre pedir e ter, então o vídeo de hoje já sai com
    ele.

    OBJETO precisa de ALFA, e alfa vem do rembg, que só roda no Action
    `assets` (a VM não aguenta). São 5 a 20 minutos, e prender a esteira
    nisso trocaria um defeito pequeno (o objeto errado numa esquete) por um
    grande (a fila parada). Então o objeto novo é ENCOMENDADO: o vídeo de
    hoje usa o substituto mais próximo do catálogo, e o de amanhã tem a
    arte. É a decisão que o dono do projeto tomou em 28/08.

O QUE IMPEDE ISTO DE VIRAR UM RALO DE COTA
    - só se pede o que NÃO existe (o inventário é consultado antes);
    - um teto por vídeo (`MAX_POR_VIDEO`), porque um roteiro que pede seis
      cenários novos não é um roteiro ambicioso, é um roteiro quebrado;
    - a encomenda de objeto é gravada em `assets_pendentes` no Supabase,
      que deduplica sozinho pela chave.
"""
import json, os, re, time

import requests

SB = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
BUCKET = os.environ.get("SUPABASE_BUCKET", "toonzueira")
CF_CONTA = os.environ.get("CF_ACCOUNT_ID", "04483caa8b5f9674b84399fcdd1ef9d5")
CF_TOKEN = os.environ.get("CF_API_TOKEN", "")

# o mesmo modelo que o workflow `Gerar Assets` usa para cenário: é o único
# gratuito do catálogo da Cloudflare que aceita largura e altura
MODELO_CENARIO = "@cf/bytedance/stable-diffusion-xl-lightning"
LARGURA, ALTURA = 2048, 1152

# O objeto vai pelo FLUX, e não pelo SDXL: ele desenha coisa isolada muito
# melhor e devolve base64 num JSON em vez de imagem binária -- os dois
# formatos já são tratados em `_cloudflare`. É a mesma escolha que o
# `Montar Pedidos` do `Gerar Assets` faz, e ela tem de ser a mesma nos dois
# lugares, senão metade dos objetos do canal sai num traço e metade noutro.
MODELO_OBJETO = "@cf/black-forest-labs/flux-1-schnell"

# Teto por vídeo. Um roteiro que pede três cenários novos trocou de lugar
# duas vezes numa esquete de vinte segundos -- o defeito está no roteiro, e
# gerar arte para ele só o esconderia.
MAX_POR_VIDEO = 2

# Só letra, número e underscore viram chave de asset: o nome vira caminho
# no bucket e chave de catálogo, e um acento ali quebra as duas coisas.
_LIMPO = re.compile(r"[^a-z0-9_]+")


def chave_valida(nome):
    """O que o roteirista escreveu -> uma chave de asset, ou None.

    Devolve None para nome vazio, com mais de três palavras ou com mais de
    24 caracteres: a essa altura não é o nome de uma coisa, é uma descrição
    de cena, e mandá-la ao gerador produz uma ilustração de história em vez
    de um cenário."""
    tabela = str.maketrans("áàâãäéèêëíìîïóòôõöúùûüçñ",
                           "aaaaaeeeeiiiiooooouuuucn")
    n = str(nome or "").strip().lower().translate(tabela)
    n = _LIMPO.sub("_", n).strip("_")
    if not n or len(n) > 24 or n.count("_") > 2:
        return None
    return n


# ---------------------------------------------------------------------
# CENÁRIO: gerado agora, usado neste vídeo
# ---------------------------------------------------------------------
# O prompt é o MESMO do workflow `Gerar Assets`, e isso não é preguiça: se
# os dois divergirem, metade dos cenários do canal sai com o chão numa
# altura e metade noutra, e o personagem passa a flutuar em metade dos
# vídeos. Mudou lá, muda aqui.
_BASE = [
    "flat cartoon vector illustration, thick black outline, flat colours",
    "very wide panoramic view, whole width filled with scenery",
    "few large simple shapes, very little detail, no clutter, "
    "pale washed-out colours",
    "eye level view from a few metres away, the furniture is big in the frame",
    "completely empty scene, nobody in it, no people, no characters, no animals",
    "straight-on eye level view from across the room, no perspective floor "
    "receding towards the viewer",
    "ALL furniture pushed back flat against the far wall, nothing in the "
    "foreground",
    "the bottom third of the picture is bare empty floor from edge to edge, "
    "completely clear, no rug, no table, no sofa, no objects in front",
    "floor line at about 62 percent of the height",
    "the upper third is full of scenery as well: ceiling, ceiling lamps, "
    "shelves, framed pictures, signs or hanging things, never a blank empty wall",
    "the scene continues past the left and right edges, no vignette, no "
    "border, no frame, no text",
    "slightly desaturated and lower contrast than the characters, so a "
    "foreground character reads clearly",
]
_NEGATIVA = ("people, person, man, woman, character, face, hands, text, "
             "letters, numbers, watermark, logo, frame, border, vignette, "
             "photo, 3d render, realistic, gradient, shading, furniture in "
             "the foreground, sofa in front, coffee table, rug in front, "
             "objects close to the camera, low angle, floor filling the "
             "bottom of the frame")


def _descricao_en(chave):
    """Uma frase em inglês descrevendo o lugar, a partir da chave.

    Sem tradutor e sem LLM: a chave já é uma ou duas palavras concretas, e
    o que o gerador precisa é do substantivo mais um punhado de objetos
    típicos. O dicionário cobre o que aparece em esquete de cotidiano
    brasileiro; o que não estiver nele cai no genérico, que ainda produz
    um cenário utilizável."""
    d = {
        "praia": "a wide empty beach, sand, sea and horizon, a few beach "
                 "umbrellas and a kiosk far back",
        "praca": "a public square with benches, trees and a bandstand",
        "academia": "a gym with treadmills and weight racks along the walls",
        "hospital": "a hospital waiting room with chairs along the walls "
                    "and a reception desk",
        "posto": "a petrol station forecourt with pumps and a shop behind",
        "padaria": "a bakery with a glass counter full of bread and a "
                   "coffee machine",
        "bar": "a simple neighbourhood bar with a counter, bottles on "
               "shelves and small tables",
        "elevador": "the inside of a small lift, metal walls, buttons panel",
        "carro": "the inside of a car seen from the back seat, windscreen "
                 "and dashboard",
        "salao": "a hair salon with mirrors, chairs and a washbasin",
        "farmacia": "a pharmacy with shelves of boxes and a service counter",
        "restaurante": "a small restaurant with tables, chairs and a counter",
        "cartorio": "a public office with a counter, numbered queue display "
                    "and stacks of paper",
        "escola": "a classroom with desks, a blackboard and a teacher's table",
        "estacionamento": "an underground car park with painted bays and "
                          "concrete pillars",
        "varanda": "an apartment balcony with a clothes line and a plant",
        "lavanderia": "a laundromat with a row of washing machines",
        "igreja": "the inside of a simple church with wooden pews",
        "metro": "a metro platform with a bench and a route map on the wall",
        "aeroporto": "an airport check-in hall with counters and a "
                     "departures board",
    }
    if chave in d:
        return d[chave]
    return f"a simple everyday brazilian {chave.replace('_', ' ')}, seen from inside"


def _cloudflare(prompt, negativa, quadrado=False):
    """Uma imagem da Workers AI, em bytes. Erro devolve None e avisa.

    `quadrado=True` é o caminho do OBJETO, e ele usa outro modelo de
    propósito: o FLUX desenha objeto isolado muito melhor que o SDXL e
    devolve sempre 1024x1024, que é o enquadramento que menos desperdiça
    para uma coisa que cabe na mão. Ele não aceita largura, altura nem
    prompt negativo -- é a mesma divisão que o `Montar Pedidos` do workflow
    `Gerar Assets` faz, e pelo mesmo motivo (ver lá o bloco QUAL MODELO
    ATENDE CADA PEDIDO)."""
    if not CF_TOKEN:
        print("[sob-demanda] sem CF_API_TOKEN no ambiente; nao da para gerar")
        return None
    modelo = MODELO_OBJETO if quadrado else MODELO_CENARIO
    url = (f"https://api.cloudflare.com/client/v4/accounts/{CF_CONTA}"
           f"/ai/run/{modelo}")
    corpo = ({"prompt": prompt[:2040], "steps": 8} if quadrado else
             {"prompt": prompt[:2040], "negative_prompt": negativa,
              "width": LARGURA, "height": ALTURA, "num_steps": 8})
    for tentativa in range(3):
        try:
            r = requests.post(url, json=corpo, timeout=180,
                              headers={"Authorization": f"Bearer {CF_TOKEN}"})
            if r.status_code == 429:
                # 429 aqui é capacidade momentânea, não cota do dia: o
                # workflow de assets vive com isso e resolve esperando
                print(f"[sob-demanda] 429 da Cloudflare; tentativa "
                      f"{tentativa + 1}/3")
                time.sleep(20)
                continue
            r.raise_for_status()
            # o SDXL devolve a imagem binária; o FLUX devolveria base64
            if r.headers.get("content-type", "").startswith("image/"):
                return r.content
            import base64
            b64 = (r.json().get("result") or {}).get("image")
            return base64.b64decode(b64) if b64 else None
        except Exception as e:
            print(f"[sob-demanda] Cloudflare falhou ({e})")
            time.sleep(8)
    return None


def _subir(caminho_bucket, dados, mime):
    if not (SB and KEY):
        print("[sob-demanda] sem credencial do Supabase; a arte fica so "
              "neste render e nao entra no catalogo")
        return False
    try:
        r = requests.put(f"{SB}/storage/v1/object/{BUCKET}/{caminho_bucket}",
                         data=dados, timeout=180,
                         headers={"apikey": KEY,
                                  "Authorization": f"Bearer {KEY}",
                                  "Content-Type": mime, "x-upsert": "true"})
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[sob-demanda] upload falhou ({e})")
        return False


def gerar_cenario(chave, pasta_destino):
    """Gera o cenário `chave`, grava em `pasta_destino` e sobe no bucket.

    Devolve o caminho local, ou None. O upload é o que faz o próximo vídeo
    não pagar de novo por esta imagem -- e se ele falhar, o render de hoje
    continua, porque a arte já está no disco."""
    chave = chave_valida(chave)
    if not chave:
        return None
    prompt = ". ".join([_BASE[0], _descricao_en(chave)] + _BASE[1:])
    print(f"[sob-demanda] gerando cenario '{chave}'...")
    dados = _cloudflare(prompt, _NEGATIVA)
    if not dados:
        return None
    os.makedirs(pasta_destino, exist_ok=True)
    local = os.path.join(pasta_destino, chave + ".jpg")
    with open(local, "wb") as f:
        f.write(dados)
    ok = _subir(f"assets_bruto/cenario/geral/{chave}.jpg", dados, "image/jpeg")
    print(f"[sob-demanda] cenario '{chave}': {len(dados)/1024:.0f} KB"
          + ("  (no bucket, ja vale para os proximos videos)" if ok
             else "  (so local)"))
    return local


# ---------------------------------------------------------------------
# OBJETO: gerado AGORA, e usado neste vídeo (11/09)
# ---------------------------------------------------------------------
# Queixa do dono: *"o roteiro fala sobre objetos que não aparecem na cena;
# quando o vídeo falar muito de um objeto ou ele for o ponto central do
# vídeo, ele precisa ser gerado"*.
#
# ATÉ AQUI OBJETO ERA ENCOMENDA, e a docstring lá em cima explica por quê:
# objeto precisa de ALFA, alfa vinha do rembg, e o rembg só roda no Action
# `assets` (5 a 20 min, e um modelo de 200 MB). A decisão de 28/08 era
# defensável — o vídeo de hoje usava um substituto e o de amanhã tinha a
# arte.
#
# SÓ QUE A ENCOMENDA NUNCA FOI FEITA UMA ÚNICA VEZ. `assets_pendentes` está
# **vazia**, e o motivo é que ninguém podia PEDIR: o vocabulário de objeto
# era uma lista fechada de dez, então um objeto fora dela nem chegava ao
# spec para dar falta. A engrenagem inteira girava no vácuo.
#
# E A PREMISSA TÉCNICA TAMBÉM CAIU. O rembg é segmentador de objeto
# saliente — necessário para foto, e caro demais para o que este canal
# gera: o prompt de objeto deste projeto pede, desde agosto, *"ISOLATED
# single object centred on a plain flat white background"*, em arte vetorial
# chapada com contorno preto grosso. Recortar isso é uma **conta de cor**,
# não um modelo de rede neural: parte-se das quatro quinas, que são fundo
# por construção, e derrama-se por vizinhança enquanto a cor for a do fundo.
# Custa milissegundos, roda com numpy e Pillow — que o render já tem — e
# não acrescenta uma linha ao `requirements.txt`.
#
# O QUE ISSO MUDA NA TELA: o objeto que a esquete inteira discute entra no
# vídeo de HOJE, na mão de quem fala dele. `MAX_POR_VIDEO` continua valendo,
# e a encomenda continua existindo como reserva — para quando a geração
# falhar, e para o dia em que alguém quiser refazer a arte com calma.

# Tolerância de cor do fundo, em 0..255 por canal. 28 é folgado o bastante
# para o "branco" que o gerador devolve (que nunca é 255,255,255 exato) e
# apertado o bastante para não comer o miolo claro de um objeto branco --
# e o que protege esse miolo é a busca por VIZINHANÇA: cor de fundo que não
# encosta na borda não é fundo, é desenho.
_TOLERANCIA_FUNDO = 28
# O contorno fica com meio pixel de fundo grudado quando o corte é binário.
# Uma erosão de um pixel na máscara tira a franja clara sem comer a linha
# preta, que tem 6 a 10 px nesta arte.
_FRANJA_PX = 1


def _descricao_objeto_en(chave):
    """Uma frase em inglês para o gerador, a partir da chave.

    As três exceções vêm do `Montar Pedidos` do workflow `Gerar Assets`, e
    ficam aqui pelo mesmo motivo que o prompt de cenário: se os dois
    divergirem, metade dos objetos do canal sai num estilo e metade noutro.
    Cada uma delas foi escrita depois de um desenho errado -- *"a tv remote
    control"* fez o modelo desenhar a TELEVISÃO com o controle na frente,
    porque o substantivo que ancora o desenho é o maior da frase."""
    d = {
        "boleto": "a brazilian payment slip, a long paper bill with a barcode",
        "carteira": "a folded leather wallet",
        "controle_remoto": "a small black handheld remote control with rubber "
                           "buttons, alone",
        "caixa_de_papelao": "a closed cardboard box",
        "marmita": "a plastic lunch box with a lid",
        "guarda_chuva_quebrado": "a broken umbrella with bent ribs",
    }
    return d.get(chave, "a " + chave.replace("_", " "))


def _recortar_fundo(dados):
    """PNG com alfa, a partir da imagem opaca do gerador.

    O fundo é achado pelas QUATRO QUINAS e derramado por vizinhança (BFS em
    quatro direções). Duas propriedades disso importam, e nenhuma delas vale
    para um corte por cor simples:

      * **buraco branco no meio do objeto continua opaco** -- a folha de um
        boleto, o mostrador de um relógio. Cor de fundo que não encosta na
        borda não é fundo;
      * **o objeto não precisa estar centrado.** Se ele toca uma borda, só o
        que estiver do lado de fora do contorno some.

    Devolve None quando o corte não faz sentido -- fundo que come mais de
    99% ou menos de 20% da imagem é sinal de que o gerador não devolveu um
    objeto isolado, e arte assim é pior que arte nenhuma: ela entra na mão
    do personagem como um borrão e ninguém descobre por quê."""
    import io
    import numpy as np
    from PIL import Image

    img = Image.open(io.BytesIO(dados)).convert("RGB")
    a = np.asarray(img).astype(np.int16)
    h, w, _ = a.shape

    quinas = [a[0, 0], a[0, w - 1], a[h - 1, 0], a[h - 1, w - 1]]
    fundo = np.median(np.stack(quinas), axis=0)
    parecido = (np.abs(a - fundo).max(axis=2) <= _TOLERANCIA_FUNDO)

    # derrame a partir da moldura, por vizinhança, sem recursão: uma pilha de
    # índices e uma varredura. `scipy.ndimage.label` faria isto em uma linha
    # e o render não tem scipy -- e não vale um pacote a mais por 30 linhas.
    visto = np.zeros((h, w), dtype=bool)
    pilha = []
    for x in range(w):
        for y in (0, h - 1):
            if parecido[y, x]:
                pilha.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if parecido[y, x]:
                pilha.append((y, x))
    while pilha:
        y, x = pilha.pop()
        if visto[y, x] or not parecido[y, x]:
            continue
        visto[y, x] = True
        if y > 0:
            pilha.append((y - 1, x))
        if y < h - 1:
            pilha.append((y + 1, x))
        if x > 0:
            pilha.append((y, x - 1))
        if x < w - 1:
            pilha.append((y, x + 1))

    corpo = ~visto
    frac = float(corpo.mean())
    if frac < 0.01 or frac > 0.80:
        print(f"[sob-demanda] o recorte deixaria {frac * 100:.0f}% da imagem; "
              f"o gerador nao devolveu um objeto isolado")
        return None

    # a franja: um pixel de erosão, feito com deslocamentos (sem scipy)
    for _ in range(_FRANJA_PX):
        e = corpo.copy()
        e[1:, :] &= corpo[:-1, :]
        e[:-1, :] &= corpo[1:, :]
        e[:, 1:] &= corpo[:, :-1]
        e[:, :-1] &= corpo[:, 1:]
        corpo = e

    rgba = np.dstack([np.asarray(img), (corpo * 255).astype(np.uint8)])
    saida = Image.fromarray(rgba, "RGBA")
    # SEM MARGEM MORTA. O motor escala o objeto pela altura do ator e o
    # ancora pela base da arte (`preparar_assets._pivo_base`): 400px de
    # branco em volta viram 400px de nada colados na mão.
    caixa = saida.getbbox()
    if caixa:
        saida = saida.crop(caixa)
    buf = io.BytesIO()
    saida.save(buf, format="PNG")
    return buf.getvalue()


def gerar_objeto(chave, pasta_destino):
    """Gera o objeto `chave` com alfa, grava em `pasta_destino` e sobe.

    Devolve o caminho local, ou None -- e None aqui não é falha de esteira:
    o vídeo segue sem o objeto, exatamente como seguia antes de 11/09.
    Quem chama decide se encomenda no lugar."""
    chave = chave_valida(chave)
    if not chave:
        return None
    prompt = ". ".join([
        _descricao_objeto_en(chave),
        "ISOLATED single object centred on a plain flat pure white background",
        # o rig gruda o objeto no osso da mão por um ponto de pega; objeto sem
        # cabo ou alça legível fica flutuando ao lado do corpo
        "seen from the side, with a clear handle or graspable part pointing "
        "to the lower left",
        "no scenery, no shadow, no ground line, no hands holding it, no person",
        "no other object next to it, nothing else in the picture",
        "thick uniform black outline",
        "100% flat colours, no shading, no gradient, no texture",
        "limited high-contrast palette",
    ])
    print(f"[sob-demanda] gerando objeto '{chave}'...")
    dados = _cloudflare(prompt, "photo, 3d render, realistic, gradient, "
                                "shading, text, letters, watermark, frame, "
                                "border, hands, person, background scenery, "
                                "multiple objects", quadrado=True)
    if not dados:
        return None
    try:
        recortado = _recortar_fundo(dados)
    except Exception as e:
        print(f"[sob-demanda] o recorte de '{chave}' falhou ({e})")
        recortado = None
    if not recortado:
        return None
    os.makedirs(pasta_destino, exist_ok=True)
    local = os.path.join(pasta_destino, chave + ".png")
    with open(local, "wb") as f:
        f.write(recortado)
    ok = _subir(f"assets/objeto/geral/{chave}.png", recortado, "image/png")
    print(f"[sob-demanda] objeto '{chave}': {len(recortado) / 1024:.0f} KB"
          + ("  (no bucket, ja vale para os proximos videos)" if ok
             else "  (so local)"))
    return local


def encomendar(tipo, chave, motivo=""):
    """Grava um pedido de arte em `assets_pendentes`.

    A tabela existe para que o pedido sobreviva ao fim deste job: quem a
    consome é o workflow `Gerar Assets`, na próxima passada. Chave repetida
    não vira linha nova -- ela só ganha um `pedidos + 1`, e é essa contagem
    que diz qual objeto o canal mais sentiu falta."""
    chave = chave_valida(chave)
    if not chave or not (SB and KEY):
        return False
    try:
        r = requests.post(
            f"{SB}/rest/v1/assets_pendentes",
            json={"tipo": tipo, "chave": chave, "motivo": motivo[:300],
                  "pedidos": 1},
            headers={"apikey": KEY, "Authorization": f"Bearer {KEY}",
                     "Content-Type": "application/json",
                     "Prefer": "resolution=merge-duplicates,return=minimal"},
            timeout=60)
        if r.status_code >= 400:
            print(f"[sob-demanda] encomenda de {tipo}:{chave} -> "
                  f"{r.status_code} {r.text[:200]}")
            return False
        print(f"[sob-demanda] {tipo} '{chave}' encomendado para os proximos "
              f"videos")
        return True
    except Exception as e:
        print(f"[sob-demanda] encomenda falhou ({e})")
        return False
