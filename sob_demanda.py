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
BUCKET = os.environ.get("SUPABASE_BUCKET", "")   # o Action define; sem padrao aqui (11/09)
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

# ---------------------------------------------------------------------------
# O HUGGINGFACE, PRIMEIRO DEGRAU DESDE 22/09 (chave do dono)
#
# A cota gratuita de Workers AI da Cloudflare (~65 imagens/dia) acabava antes
# do meio-dia: a fabrica de arte fechou 22/09 com 1 acerto e 31 falhas, e a
# copia -- que pede um objeto por frase -- ia para a tela com placa de texto
# no lugar do desenho. O dono abriu uma conta no HuggingFace e mandou usa-la.
#
# QUAL ROTA. O provedor `hf-inference` aposentou os modelos de imagem ("The
# requested model is deprecated"); quem atende hoje e' o ROTEADOR, que fala
# OpenAI (`/v1/images/generations`) e despacha para um provedor parceiro.
# Medido nesta chave em 22/09: `nscale` com FLUX.1-schnell responde em ~5 s,
# nos dois formatos (1024x1024 para objeto, 768x1344 para cenario); `fal-ai`,
# `replicate`, `wavespeed` e `together` recusam o modelo ou pedem partilha de
# dados. Por isso o provedor e' NOMEADO em vez de `auto`.
#
# E' o MESMO FLUX que a Cloudflare servia, entao o traco do canal nao muda --
# a arte gerada hoje continua irma da que ja esta no bucket.
HF_ROTEADOR = "https://router.huggingface.co/{provedor}/v1/images/generations"
HF_PROVEDOR = os.environ.get("HF_PROVEDOR", "nscale")
HF_MODELO = os.environ.get("HF_MODELO", "black-forest-labs/FLUX.1-schnell")
HF_TAMANHO_OBJETO = "1024x1024"
HF_TAMANHO_CENARIO = "768x1344"


def _hf_token():
    """A chave do HuggingFace: ambiente, arquivo do laboratorio ou banco.

    Tres portas pela mesma razao das outras credenciais do projeto: o Action
    tem ambiente, esta maquina tem o arquivo, e a producao tem o
    `config_sistema` (assim o dono nao precisa mexer em segredo do GitHub
    para a producao passar a gerar arte)."""
    t = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if t:
        return t.strip()
    aqui = os.path.dirname(os.path.abspath(__file__))
    for arq in (os.path.join(os.path.dirname(aqui), "lab", "chave_hf.txt"),
                os.path.join(aqui, "chave_hf.txt")):
        try:
            with open(arq, encoding="utf-8") as fh:
                s = fh.read().strip()
            if s:
                return s
        except OSError:
            pass
    for bloco in (_hf_config(),):
        if bloco.get("token"):
            return str(bloco["token"]).strip()
    return ""


_HF_CFG = {}


def _hf_config():
    """O bloco `huggingface` do `config_sistema` (token, provedor, modelo).

    DUAS PORTAS, E A SEGUNDA E' A QUE VALE NA PRODUCAO (23/09).

    No laboratorio existe `config.py`, que le o banco pelo proxy do n8n. No
    REPO DE RENDER ele NAO EXISTE -- a lista de arquivos que `subir_render`
    manda tem `config_gerado.py`, e so'. Com apenas a primeira porta, o
    `import config` falhava dentro do Action, `_hf_token` devolvia vazio e a
    arte caia de volta na Cloudflare (sem cota) SEM UMA LINHA DIZENDO POR QUE.
    Era um defeito calado, do tipo que a lei 65 existe para impedir.

    A segunda porta e' o mesmo REST que o `job.py` ja usa para a fila e a
    identidade, com a chave de servico que o Action tem: uma linha de
    `config_sistema`. Sem as duas, avisa -- e ai quem chama desce a escada.
    """
    if _HF_CFG:
        return _HF_CFG
    try:
        import config as C
        bloco = dict(C.config_sistema().get("huggingface") or {})
        if bloco:
            _HF_CFG.update(bloco)
            return _HF_CFG
    except Exception:                                               # noqa: BLE001
        pass
    if SB and KEY:
        try:
            r = requests.get(f"{SB}/rest/v1/config_sistema",
                             params={"select": "config_json", "limit": 1,
                                     "order": "id.asc"},
                             headers={"apikey": KEY,
                                      "Authorization": f"Bearer {KEY}"},
                             timeout=30)
            linhas = r.json() if r.status_code == 200 else []
            bloco = ((linhas or [{}])[0].get("config_json") or {}).get("huggingface")
            if bloco:
                _HF_CFG.update(bloco)
                return _HF_CFG
        except Exception as e:                                      # noqa: BLE001
            print(f"[sob-demanda] nao li config_sistema pelo REST "
                  f"({type(e).__name__}: {str(e)[:80]})")
    print("[sob-demanda] sem bloco `huggingface` no config_sistema e sem "
          "HF_TOKEN no ambiente: a arte vai tentar o degrau seguinte")
    return {}


def _huggingface(prompt, negativa, quadrado=False):
    """Uma imagem pelo roteador do HuggingFace, em bytes. None se nao deu."""
    token = _hf_token()
    if not token:
        return None
    cfg = _hf_config()
    url = HF_ROTEADOR.format(provedor=cfg.get("provedor") or HF_PROVEDOR)
    corpo = {"model": cfg.get("modelo") or HF_MODELO, "prompt": prompt[:2040],
             "response_format": "b64_json",
             "size": HF_TAMANHO_OBJETO if quadrado else HF_TAMANHO_CENARIO}
    for tentativa in range(3):
        try:
            r = requests.post(url, json=corpo, timeout=180,
                              headers={"Authorization": f"Bearer {token}"})
            if r.status_code in (429, 503):
                print(f"[sob-demanda] HF {r.status_code} (fila/cota); tentativa "
                      f"{tentativa + 1}/3")
                time.sleep(15)
                continue
            if r.status_code != 200:
                print(f"[sob-demanda] HF {r.status_code}: {r.text[:140]}")
                return None
            if r.headers.get("content-type", "").startswith("image/"):
                return r.content
            import base64
            dados = (r.json().get("data") or [{}])[0].get("b64_json")
            return base64.b64decode(dados) if dados else None
        except Exception as e:                                      # noqa: BLE001
            print(f"[sob-demanda] HF falhou ({e})")
            time.sleep(8)
    return None

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
             "bottom of the frame, food close-up, sandwich, burger, plate "
             "of food, a single big product filling the picture, still life")


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
        # OS LUGARES QUE A COPIA PEDE (21/09). A copia fiel escolhe o lugar
        # de cada frase livremente ("lanchonete", "banco", "delegacia"...),
        # e o generico de antes ("a simple everyday brazilian lanchonete")
        # rendeu, no video 8c85105e, UM SANDUICHE GIGANTE ocupando o quadro
        # -- o gerador nao sabe o que e' lanchonete e desenhou a comida.
        # Cada lugar aqui e' descrito como SALA (balcao, mesas, parede do
        # fundo), nunca pelo produto que se vende nela.
        "lanchonete": "a small snack bar interior: a long service counter "
                      "along the far wall, stools, a menu board and a "
                      "drinks fridge",
        "banco": "a bank branch hall: teller counters with glass along the "
                 "far wall, a queue ticket display and a row of chairs",
        "delegacia": "a police station front desk room: a high counter, a "
                     "notice board, filing cabinets and a wall clock",
        "ponte": "a wide city bridge seen from the pavement, railings, "
                 "lamp posts and the river and skyline far behind",
        "loja": "a small shop interior with shelves of boxes along the far "
                "wall and a checkout counter",
        "loja_de_suco": "a juice bar interior: a counter with a row of "
                        "blenders, a fruit display on the far wall and a "
                        "price board",
        "mercado": "a supermarket aisle: tall shelves along the far wall, a "
                   "checkout lane and hanging price signs",
        "supermercado": "a supermarket aisle: tall shelves along the far "
                        "wall, a checkout lane and hanging price signs",
        "feira": "an open-air street market: stalls with awnings in a row "
                 "along the back, crates and hanging signs",
        "shopping": "a shopping mall corridor: shop fronts with signs along "
                    "the far side, a bench and potted plants",
        "hotel": "a hotel lobby: a reception desk on the far wall, a key "
                 "rack, a luggage trolley and a sofa pushed back",
        "consultorio": "a doctor's consulting room: a desk, an examination "
                       "bed against the far wall and an eye chart",
        "dentista": "a dentist's room: a dental chair against the far wall, "
                    "a lamp arm and a cabinet of instruments",
        "cinema": "a cinema auditorium: rows of red seats along the back "
                  "and a big blank screen on the far wall",
        "estadio": "a football stadium seen from the pitch: stands full of "
                   "colour blocks far behind and a goal at the side",
        "parque": "a city park: lawn, a path, trees and a bench along the "
                  "back, a lamp post",
        "floresta": "a forest clearing: tree trunks along the back, bushes "
                    "and a path",
        "fazenda": "a farm yard: a barn, a fence and a water tower along "
                   "the back",
        "cadeia": "a prison cell block corridor: barred cell doors along "
                  "the far wall and a bench",
        "prisao": "a prison cell block corridor: barred cell doors along "
                  "the far wall and a bench",
        "tribunal": "a courtroom: the judge's high bench on the far wall, a "
                    "witness stand and wooden benches",
        "faculdade": "a university lecture hall: rows of desks along the "
                     "back and a big whiteboard on the far wall",
        "garagem": "a home garage: a workbench, tool board and shelves "
                   "along the far wall, a rolled-up door",
        "oficina": "a car repair workshop: a car lift with a car raised "
                   "against the far wall, tool boards and tyres",
        "sorveteria": "an ice cream parlour: a display counter along the "
                      "far wall, a flavour board and stools",
        "pizzaria": "a pizzeria dining room: tables with checked cloths "
                    "along the back, a brick oven and a menu board",
        "churrascaria": "a steakhouse dining room: tables along the back, "
                        "a grill counter and a wall of skewers",
        "loterica": "a lottery shop: a service counter along the far wall, "
                    "a numbers display and a queue ticket machine",
        "correios": "a post office hall: counters along the far wall, a "
                    "parcel scale and a wall of PO boxes",
        "cemiterio": "a cemetery: rows of gravestones and a chapel along "
                     "the back, a cypress tree",
        "aeroporto_pista": "an airport runway seen from the apron, a plane "
                           "far back and the terminal building",
        "praia_quiosque": "a beach kiosk: a thatched bar counter, stools, "
                          "the sea far behind",
        "quadra": "a sports court: painted lines, a hoop on the far wall "
                  "and a bench",
        "piscina": "a swimming pool area: the pool along the back, sun "
                   "loungers and a diving board",
        "ponto_de_onibus": "a bus stop on a pavement: a shelter with a bench, "
                           "a timetable and a low wall behind",
        "corredor": "an apartment building corridor: numbered doors along "
                    "the far wall, a lift door and a fire hose box",
        "portaria": "an apartment building lobby: a doorman's desk, a "
                    "mailbox wall and a glass door on the far wall",
        "terraco": "a rooftop terrace: a low parapet, a water tank and the "
                   "city skyline far behind",
        "loja_de_roupa": "a clothes shop: racks of clothes along the far "
                         "wall, a mirror and a fitting room curtain",
        "pet_shop": "a pet shop: shelves of pet food along the far wall, "
                    "a grooming table and a fish tank",
        "casa_de_cambio": "a currency exchange booth hall: a counter with "
                          "glass and a rates board on the far wall",
        "escritorio_do_chefe": "a boss's office: a big desk against the "
                               "far wall, a leather chair, a diploma and a "
                               "window with blinds",
        "sala_de_reuniao": "a meeting room: a long table pushed back, "
                           "chairs, a whiteboard and a screen on the far wall",
        "recepcao": "a reception hall: a front desk on the far wall, a "
                    "logo sign, a plant and a row of chairs",
    }
    if chave in d:
        return d[chave]
    # LUGAR FORA DO DICIONARIO: traduz palavra a palavra o que da' para
    # traduzir e descreve o lugar como SALA -- o quadro precisa ser a
    # arquitetura do lugar, nunca o produto dele.
    palavras = {"loja": "shop", "casa": "house", "sala": "room", "bar": "bar",
                "clube": "club", "escola": "school", "centro": "centre",
                "posto": "station", "praca": "square", "beco": "alley",
                "rua": "street", "quarto": "bedroom", "cozinha": "kitchen",
                "de": "of", "da": "of the", "do": "of the", "e": "and",
                "suco": "juice", "carro": "car", "moto": "motorbike",
                "pao": "bread", "carne": "meat", "peixe": "fish",
                "roupa": "clothes", "sapato": "shoe", "celular": "phone",
                "bolo": "cake", "cafe": "coffee", "doce": "sweets",
                "brinquedo": "toy", "livro": "book", "movel": "furniture",
                "tinta": "paint", "flor": "flower", "bicicleta": "bicycle",
                "pizza": "pizza", "sorvete": "ice cream", "acai": "acai",
                "espera": "waiting", "aula": "class", "jogo": "games",
                "festa": "party", "casamento": "wedding", "velorio": "funeral",
                "vizinho": "neighbour", "chefe": "boss", "mae": "mother"}
    nome = " ".join(palavras.get(p, p) for p in chave.split("_") if p)
    # "the room and its walls only" rendeu um rascunho CINZA para 'casa'
    # (21/09); o gerador precisa de moveis nomeados e de cor pedida.
    return (f"the inside of a {nome}, a wide colourful interior seen from "
            f"across the room: a counter, shelves and furniture along the "
            f"far wall, a hanging sign, a door and a window; no product "
            f"close-up, no food, no single big object")


# O n8n TEM A CREDENCIAL QUE FALTA AQUI (13/09).
#
# O DEFEITO, MEDIDO NO VIDEO QUE FOI AO AR. O `317c0b76` chama-se "He Tried
# Paying Rent With A Controller", a esquete inteira gira em volta de um
# controle de video game, e o log do Action diz:
#
#     CF_API_TOKEN:
#     [sob-demanda] gerando objeto 'game_controller'...
#     [sob-demanda] sem CF_API_TOKEN no ambiente; nao da para gerar
#     [objeto] game_controller: nao achei, seguindo sem ele
#
# O video foi publicado SEM a coisa de que ele fala. E nao e' um caso: o
# catalogo esta em 8 cenarios e 10 objetos desde agosto, e `assets_gerados`
# prova que nada novo foi gerado uma unica vez -- e' a queixa do dono em
# 13/09 (*"ate o momento nao vi um video que um objeto novo foi feito
# conforme solicitacao do roteiro"*), e ela e' inteiramente verdadeira.
#
# O segredo `CF_API_TOKEN` esta pendente na lista do dono desde 11/09. Mas
# ele NAO E' a unica porta para a Cloudflare: o fluxo `Gerar Assets` do n8n
# (`nrSxcnZLEH5xoLlt`) tem a credencial `cloudflare` viva e o webhook publico
# `gerar-assets`, e ele faz mais do que gerar -- ja sobe no bucket e registra
# em `assets_gerados`. Provado em 13/09: um `controle_video_game` pedido por
# ali voltou em 114 s, no estilo do canal, e o recorte por cor daqui aceitou.
#
# Entao a escada fica: token no ambiente (mais rapido, uma chamada) -> a
# esteira (sem segredo nenhum) -> encomenda. O dono continua ganhando com o
# segredo, e a esteira deixa de depender dele.
N8N = (os.environ.get("N8N_BASE") or "https://toonzueira.duckdns.org").rstrip("/")
PUBLICO = f"{SB}/storage/v1/object/public/{BUCKET}" if SB and BUCKET else ""
# 114 s foi o medido para um objeto; o cenario e' maior. O teto existe para a
# esteira nunca ficar presa aqui: estourado, cai na encomenda, que e' o
# comportamento de antes desta mudanca.
ESPERA_ESTEIRA_S = 300


def _apagar(caminho):
    """Tira um objeto do bucket. Usado quando o bruto guardado nao presta
    (recorte impossivel): deixa-lo la' faz TODO video seguinte tropecar no
    mesmo arquivo ruim -- foi o `dinheiro` no 8c85105e (21/09)."""
    if not (SB and KEY):
        return False
    try:
        r = requests.delete(f"{SB}/storage/v1/object/{BUCKET}/{caminho}",
                            timeout=60, headers={"apikey": KEY,
                                                 "Authorization": f"Bearer {KEY}"})
        return r.status_code < 300
    except Exception:
        return False


def _pela_esteira(tipo, chave, desc_en, quadrado=False, ignorar_cache=False):
    """Pede a arte ao fluxo `Gerar Assets` do n8n e baixa o bruto do bucket.

    Devolve os bytes da imagem, ou None. Ver o comentario longo acima: este
    caminho existe porque a credencial da Cloudflare mora no n8n, e o Action
    de render nao a tem. `ignorar_cache` pula o passo 1 -- e' para refazer
    um bruto que existe e nao serve.
    """
    alvo = f"{PUBLICO}/assets_bruto/{tipo}/geral/{chave}.jpg"
    # 1. JA ESTA LA? Outro video pode ter pedido a mesma coisa hoje -- e o
    #    bucket e' o catalogo, entao consultar antes de gerar e' a mesma
    #    disciplina do `jaTem` do `Montar Pedidos`.
    if ignorar_cache:
        _apagar(f"assets_bruto/{tipo}/geral/{chave}.jpg")
    else:
        try:
            r = requests.get(alvo, timeout=60)
            if r.status_code == 200 and len(r.content) > 2000:
                print(f"[sob-demanda] '{chave}' ja estava no bucket "
                      f"({len(r.content)/1024:.0f} KB); nao gerei de novo")
                return r.content
        except Exception:
            pass
    # 2. PEDE. `pecas` e' o contrato do `Montar Pedidos` para arte avulsa.
    print(f"[sob-demanda] pedindo '{chave}' a esteira (o n8n tem a "
          f"credencial da Cloudflare)...")
    try:
        r = requests.post(f"{N8N}/webhook/gerar-assets", timeout=ESPERA_ESTEIRA_S,
                          json={"pecas": [{"tipo": tipo, "chave": chave,
                                           "desc_en": desc_en}]})
        r.raise_for_status()
    except Exception as e:
        print(f"[sob-demanda] a esteira nao respondeu ({e})")
        return None
    # 3. BAIXA O QUE ELA SUBIU. O fluxo responde depois de subir, entao o
    #    arquivo ja existe -- mas o CDN do Storage as vezes atrasa alguns
    #    segundos, e tres tentativas custam menos que perder a arte.
    for tentativa in range(3):
        try:
            # `?t=` fura o cache do CDN: depois de refazer um bruto, a URL
            # limpa devolveu o arquivo antigo por mais de um minuto (21/09)
            r = requests.get(f"{alvo}?t={int(time.time())}", timeout=90)
            if r.status_code == 200 and len(r.content) > 2000:
                print(f"[sob-demanda] '{chave}' gerado pela esteira: "
                      f"{len(r.content)/1024:.0f} KB")
                return r.content
        except Exception:
            pass
        time.sleep(5)
    print(f"[sob-demanda] a esteira disse ok mas '{chave}' nao apareceu no bucket")
    return None


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
    # A ESCADA DA ARTE (22/09): HuggingFace, Cloudflare, esteira do n8n. O
    # primeiro degrau e' o que tem cota -- ver `_huggingface`.
    dados = _huggingface(prompt, _NEGATIVA)
    if not dados:
        dados = _cloudflare(prompt, _NEGATIVA)
    if not dados:
        # SEM O TOKEN, PELA ESTEIRA (13/09) -- ver `_pela_esteira`.
        dados = _pela_esteira("cenario", chave, _descricao_en(chave))
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
        # 11/09: "a carta" desenhou uma ESPATULA -- a palavra em portugues
        # nao ancora nada no modelo, e o pedido de "cabo" completou o resto.
        # PARDO e nao branco: objeto branco em fundo branco e' apagado pelo
        # recorte por cor (a segunda tentativa perdeu o miolo do envelope)
        "carta": "a cartoon brown paper envelope drawn with thick black "
                 "outlines, with a small red stamp",
        # AS COISAS DA COPIA (21/09). A copia fiel pede um objeto por frase
        # e o mundo do canal copiado e' dinheiro, multa, loja, policia. O
        # generico ("the object called 'dinheiro' in Portuguese") rendeu um
        # bruto que o recorte deixa em 1%. Cores ESCURAS de proposito: o
        # recorte e' por cor a partir das quinas, e objeto branco some.
        "dinheiro": "a thick stack of green paper banknotes tied with a "
                    "brown paper band",
        "saco_de_dinheiro": "a bulging brown money sack tied at the top "
                            "with a dollar sign printed on it",
        "caixa_de_dinheiro": "an open wooden chest overflowing with green "
                             "banknotes and gold coins",
        "mala_de_dinheiro": "an open brown suitcase full of stacks of green "
                            "banknotes",
        "moedas": "a pile of gold coins",
        "cofre": "a dark grey steel safe with a round dial on the door",
        "multa": "a yellow paper fine ticket with a red stamp on it",
        "iate": "a white and dark blue luxury yacht seen from the side",
        "carro": "a red compact car seen from the side",
        "carro_de_luxo": "a black luxury sports car seen from the side",
        "mansao": "a big white mansion with columns and a red roof",
        "casa": "a small orange house with a red roof and a door",
        "loja": "a small shop front with a striped awning and a sign",
        "loja_de_suco": "a small juice shop front with a striped awning and "
                        "a big orange fruit on the sign",
        "caixa_registradora": "a dark green cash register with a drawer "
                              "open and banknotes inside",
        "documento": "a white paper document with black lines of text and "
                     "a red seal",
        "contrato": "a white paper contract with black lines of text and a "
                    "signature line",
        "celular": "a black smartphone with a bright screen",
        "notebook": "an open dark grey laptop computer",
        "algemas": "a pair of grey steel handcuffs",
        "distintivo": "a gold police badge in the shape of a shield",
        # o corpo branco do carrinho sumiu no recorte por cor (21/09): cor
        # dita explicitamente em toda superficie
        "barraca_de_comida": "a small street food cart with a dark blue "
                             "wooden body, a yellow counter, a red and white "
                             "striped awning and two black wheels",
        "suco": "a tall glass of orange juice with a straw",
        "lanche": "a hamburger with lettuce and cheese in a bun",
        "flores": "a bouquet of red and yellow flowers wrapped in brown paper",
        "chave": "a big brass door key",
        "calendario": "a wall calendar with a red circle around one day",
        "relogio": "a round wall clock with black hands",
        "cerveja": "a brown glass beer bottle with a red label",
        "pizza": "a whole round pizza in an open cardboard box",
        "computador": "a dark grey desktop computer monitor and keyboard",
        "televisao": "a flat black television set",
        "conta": "a long white paper bill with a barcode and a red 'due' stamp",
        "cartao": "a blue plastic credit card",
        "maquininha": "a small black card payment machine with a screen",
    }
    if chave in d:
        return d[chave]
    # TRADUZIR ANTES DE DESENHAR (23/09). Ver `_traduzir_objeto`: a frase
    # "o objeto chamado X em portugues" nao ancora nada, e o gerador desenhava
    # outra coisa -- medido nos 22 objetos do laboratorio, 8 estavam errados
    # (a `fatura` virou uma colher; o `martelo`, uma faca com a palavra
    # "martello" escrita nela; a `pilha_de_dinheiro`, uma MAO segurando uma
    # placa, que e' a "mao sobreposta" que o dono viu no video).
    traduzida = _traduzir_objeto(chave)
    if traduzida:
        return traduzida
    return (f"the everyday hand-held object called \"{chave.replace('_', ' ')}\" "
            f"in Brazilian Portuguese")


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


# ---------------------------------------------------------------------------
# A TRADUCAO DO NOME DO OBJETO (23/09)
#
# O roteirista escreve o objeto em portugues (`caixa_de_dinheiro`,
# `conta_de_luz`) e o gerador de imagem pensa em ingles. O dicionario acima
# cobre as duas duzias de sempre; o resto -- e a copia pede um objeto POR
# FRASE, entao o resto e' a maioria -- caia numa frase generica que nao
# ancorava nada, e o desenho saia errado. Aqui o nome e' traduzido UMA vez,
# por um modelo barato, e guardado: o mesmo objeto nunca se traduz duas vezes,
# e o cache vale para a producao e para o laboratorio.
_CACHE_EN = {}
_ARQ_EN = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "objetos_en.json")


def _cache_en():
    if not _CACHE_EN:
        for arq in (_ARQ_EN, os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "lab", "objetos_en.json")):
            try:
                with open(arq, encoding="utf-8") as fh:
                    _CACHE_EN.update(json.load(fh))
            except Exception:                                       # noqa: BLE001
                pass
        _CACHE_EN.setdefault("_", "")
    return _CACHE_EN


def _traduzir_objeto(chave, timeout=60):
    """Uma frase curta em ingles para `chave`. Cache primeiro; depois o
    modelo mecanico pela esteira do n8n. Falhou, devolve "" e quem chama usa
    a frase generica de antes -- traducao nao pode travar um render."""
    cache = _cache_en()
    if chave in cache:
        return cache[chave]
    termo = chave.replace("_", " ")
    try:
        # A URL SAI DE `N8N`, E NAO DE `config.py` (23/09). Ver `_hf_config`:
        # `config.py` nao existe no repo de render, e um `import config` aqui
        # faria a producao pular a traducao em silencio -- e' o mesmo defeito
        # calado que a chave do HuggingFace teve, no mesmo arquivo, no mesmo
        # dia. `N8N` ja vive neste modulo e ja e' o que `_pela_esteira` usa.
        url = N8N + "/webhook/px-groq"
        modelo = os.environ.get("MODELO_GROQ_MECANICO") or "openai/gpt-oss-20b"
        pedido = (
            "Traduza para o ingles o nome deste objeto brasileiro e devolva "
            "UMA frase curta (ate 12 palavras) descrevendo COMO DESENHA-LO, "
            "no formato 'a <coisa> <detalhe visual>'. Sem aspas, sem "
            "explicacao, sem texto escrito no desenho. Se for um papel, diga "
            "que papel e'. Objeto: " + termo)
        # `reasoning_effort` E `max_tokens` FOLGADO (23/09): o gpt-oss gasta a
        # saida inteira raciocinando e devolve `content` VAZIO com 200 -- foi
        # o que aconteceu na primeira versao desta funcao, e o objeto continuou
        # saindo errado sem ninguem saber por que. E' a mesma lei 59/86 que o
        # `teto_por_etapa` do roteirista documenta.
        r = requests.post(url, timeout=timeout, json={
            "model": modelo, "max_tokens": 400, "reasoning_effort": "low",
            "messages": [{"role": "user", "content": pedido}]})
        j = r.json()
        msg = ((j.get("choices") or [{}])[0].get("message") or {})
        txt = msg.get("content") or ""
        if not str(txt).strip():
            # sobrou so' o raciocinio: a ultima linha dele costuma ser a
            # resposta ("a hammer with a wooden handle")
            bruto = str(msg.get("reasoning") or "").strip().splitlines()
            txt = bruto[-1] if bruto else ""
        txt = " ".join(str(txt).strip().strip('"').split())[:120]
        if txt and len(txt.split()) >= 2:
            cache[chave] = txt
            try:
                with open(_ARQ_EN, "w", encoding="utf-8") as fh:
                    json.dump({k: v for k, v in cache.items() if k != "_"},
                              fh, ensure_ascii=False, indent=1, sort_keys=True)
            except OSError:
                pass
            print(f"[sob-demanda] '{termo}' -> \"{txt}\"")
            return txt
    except Exception as e:                                          # noqa: BLE001
        print(f"[sob-demanda] nao traduzi '{termo}' ({type(e).__name__})")
    return ""


def prompt_objeto(chave):
    """O pedido de imagem de um objeto -- UM lugar só, para quem gera fora do
    render (ferramentas, n8n) pedir exatamente o mesmo texto."""
    return ". ".join([
        # DESENHO, DITO NA FRENTE (11/09): sem isto o FLUX devolveu FOTO de um
        # envelope -- o estilo pedido no fim do prompt perde para o substantivo
        # do começo, que é onde o modelo ancora (a mesma lição do `a tv remote`)
        "simple flat 2D cartoon drawing, not a photo: "
        + _descricao_objeto_en(chave),
        "ISOLATED single object centred on a plain flat pure white background",
        # o rig gruda o objeto no osso da mão por um ponto de pega, e o objeto
        # na DIAGONAL deixa uma ponta para isso. NEM "CABO" NEM "MÃO" (11/09):
        # "with a clear handle" fez de um envelope uma ESPÁTULA, e "the part a
        # hand would hold" desenhou a MÃO segurando -- o modelo desenha o
        # substantivo que aparece, e a negação "no hands" não o apaga.
        "lying diagonally, from the lower left to the upper right",
        "no scenery, no shadow, no ground line",
        "no other object next to it, nothing else in the picture",
        # A MAO E O TEXTO (23/09, queixa do dono: *"metade da mao sobrepoe a
        # mao do personagem"*). A arte de `pilha_de_dinheiro` era uma MAO
        # segurando uma placa: colada na mao do boneco, viravam duas maos. E
        # o `martelo` saiu com a palavra "martello" escrita na lamina -- o
        # gerador escreve o nome quando nao sabe desenhar a coisa. O rig ja
        # poe a mao; a arte traz so' o objeto.
        "the object alone, nobody holding it, no hand, no fingers, no arm",
        "no writing, no letters, no numbers, no label, no logo",
        "thick uniform black outline",
        "100% flat colours, no shading, no gradient, no texture",
        "limited high-contrast palette",
    ])


def gerar_objeto(chave, pasta_destino):
    """Gera o objeto `chave` com alfa, grava em `pasta_destino` e sobe.

    Devolve o caminho local, ou None -- e None aqui não é falha de esteira:
    o vídeo segue sem o objeto, exatamente como seguia antes de 11/09.
    Quem chama decide se encomenda no lugar."""
    chave = chave_valida(chave)
    if not chave:
        return None
    prompt = prompt_objeto(chave)
    print(f"[sob-demanda] gerando objeto '{chave}'...")
    _NEG_OBJ = ("photo, 3d render, realistic, gradient, shading, text, "
                "letters, watermark, frame, border, hands, person, "
                "background scenery, multiple objects")
    # a escada da arte (22/09): HuggingFace primeiro -- ver `_huggingface`
    dados = _huggingface(prompt, _NEG_OBJ, quadrado=True)
    if not dados:
        dados = _cloudflare(prompt, _NEG_OBJ, quadrado=True)
    if not dados:
        # SEM O TOKEN, PELA ESTEIRA (13/09) -- ver `_pela_esteira`. O recorte
        # por cor continua sendo feito AQUI: o `Gerar Assets` sobe o bruto, e
        # o alfa e' conta de cor, nao de rede neural.
        dados = _pela_esteira("objeto", chave, _descricao_objeto_en(chave),
                              quadrado=True)
    if not dados:
        return None

    def _recortar(d):
        try:
            return _recortar_fundo(d)
        except Exception as e:
            print(f"[sob-demanda] o recorte de '{chave}' falhou ({e})")
            return None
    recortado = _recortar(dados)
    if not recortado:
        # BRUTO RUIM NAO FICA (21/09): o `dinheiro` estava no bucket como um
        # bruto que o recorte deixa em 1%, e todo video pedia, achava, e
        # seguia sem ele. Apaga e pede de novo, uma vez.
        print(f"[sob-demanda] refazendo o bruto de '{chave}' (o guardado nao recorta)")
        dados = _pela_esteira("objeto", chave, _descricao_objeto_en(chave),
                              quadrado=True, ignorar_cache=True)
        recortado = _recortar(dados) if dados else None
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
