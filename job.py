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
  SUPABASE_BUCKET       obrigatória (o Action define)
"""
import os, sys, re, time, json, traceback
from pathlib import Path
import requests

# fila_producao.fila_id e uuid no Postgres. Um id legivel de teste
# ("teste-cutout-2208") faz o PostgREST devolver 400/22P02 -- e como
# atualizar_fila roda DEPOIS do upload, isso transformava um render bom
# num job 'failure' com o MP4 ja no bucket. Aconteceu no run #11.
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
                     r"[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from palito_v5 import render_spec

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_KEY"]
BUCKET = os.environ["SUPABASE_BUCKET"]   # o Action define; sem padrao aqui (11/09)
# o cabecalho de leitura do REST, num lugar so' (as duas escritas deste
# arquivo montam o seu porque acrescentam `Prefer`)
CAB = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}


def subir(local, remoto, mime="video/mp4", tentativas=4):
    """Sobe um arquivo para o Storage, COM TENTATIVAS.

    POR QUE (02/09, volta 69)
        O render terminou, o MP4 de 10,6 MB ficou pronto no runner, e o job
        morreu num **504 Gateway Timeout** do Storage. Quinze minutos de
        Action perdidos por uma falha transitoria de rede, sem uma unica
        repeticao -- e o vazio que sobra no bucket vira, no lote, "nao
        baixou o MP4: 400".

        Este e o mesmo desenho de `E6` (o 413 depois de quinze minutos de
        render): o passo mais caro do pipeline e o penultimo, e o ultimo
        nao tinha rede de seguranca nenhuma. Nao ha nada a decidir aqui --
        o arquivo existe e o servidor pediu para tentar de novo.

    SO REPETE O QUE ADIANTA REPETIR. 5xx e timeout sao transitorios; 400,
    401 e 413 sao permanentes (chave errada, nome invalido, arquivo grande
    demais) e repetir so gasta minuto de Action e adia o diagnostico.
    """
    dados = Path(local).read_bytes()
    espera = 5
    for k in range(tentativas):
        try:
            # PUT com x-upsert e o caminho que sobrescreve. POST devolve
            # 400/409 quando o objeto ja existe, e reprocessar o mesmo
            # fila_id e comum.
            r = requests.put(f"{SB}/storage/v1/object/{BUCKET}/{remoto}",
                             data=dados,
                             headers={"apikey": KEY,
                                      "Authorization": f"Bearer {KEY}",
                                      "Content-Type": mime,
                                      "x-upsert": "true"},
                             timeout=300)
        except requests.RequestException as e:
            if k == tentativas - 1:
                raise
            print(f"[upload] rede caiu ({type(e).__name__}); "
                  f"tentativa {k + 2} de {tentativas} em {espera}s")
            time.sleep(espera)
            espera *= 2
            continue
        if r.status_code < 400:
            print(f"[upload] {r.status_code}  {len(dados)/1e6:.2f} MB"
                  + (f"  (tentativa {k + 1})" if k else ""))
            return f"{SB}/storage/v1/object/public/{BUCKET}/{remoto}"
        # sem o corpo da resposta, um 400 do Storage nao diz nada: pode ser
        # chave errada, bucket inexistente ou nome de objeto invalido
        print(f"[upload] {r.status_code} em {remoto}: {r.text[:400]}")
        if r.status_code < 500 and r.status_code != 429:
            r.raise_for_status()          # permanente: nao adianta insistir
        if k == tentativas - 1:
            r.raise_for_status()
        print(f"[upload] transitorio; tentativa {k + 2} de {tentativas} "
              f"em {espera}s")
        time.sleep(espera)
        espera *= 2


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
    if not UUID_RE.match(str(fila_id)):
        # Render de teste: nao existe linha na fila para atualizar. Pular e
        # correto -- e o inverso (deixar o 400 subir) custava o video inteiro.
        print(f"[fila] fila_id '{fila_id}' nao e uuid; render de teste, pulando")
        return
    r = requests.patch(
        f"{SB}/rest/v1/fila_producao?fila_id=eq.{fila_id}",
        json=campos,
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"},
        timeout=60)
    print(f"[fila] {r.status_code} -> {campos.get('status')}")
    r.raise_for_status()


def _baixar_para(url, pasta, nome):
    """Baixa uma arte e devolve o caminho local, ou None se nao veio.

    A extensao sai da URL: o Cenario abre a imagem pelo conteudo, mas quem
    PROCURA o arquivo procura por extensao, entao gravar um JPEG como .png
    faria o motor nao achar o unico cenario que presta."""
    ext = os.path.splitext(url.split("?")[0])[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        ext = ".png"
    os.makedirs(pasta, exist_ok=True)
    destino = os.path.join(pasta, nome + ext)
    try:
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        Path(destino).write_bytes(r.content)
        print(f"[arte] {nome}{ext}  {len(r.content)/1024:.0f} KB")
        return destino
    except Exception as e:
        # arte de fundo e melhoria, nao requisito: falhar aqui nao pode
        # custar o video -- o motor cai na cor chapada e avisa no log
        print(f"[arte] {nome} falhou ({e}); seguindo sem ela")
        return None


MAX_EM_CENA = 2


def baixar_zip(url, tentativas=4):
    """Baixa um `personagem.zip` e devolve os bytes, COM TENTATIVAS.

    POR QUE (06/09, o video das 21:30)
        O download era `requests.get(url).content` cru, sem conferir o
        status. O Storage teve um solucos, a resposta nao era um zip, e o
        `zipfile` estourou com **"File is not a zip file"** -- uma mensagem
        que nao diz nem o codigo HTTP nem o que veio no corpo. O zip do
        `zeca` estava intacto no bucket o tempo todo; UMA repeticao teria
        salvado o video.

        E o estrago nao parou ali, porque a queda em cascata e silenciosa:
        sem as pecas, o motor cut-out cedeu lugar ao rig vetorial, que
        produziu um MP4 de **65 MB** -- acima do teto do bucket --, e o
        upload morreu com 413 depois de nove minutos de Action. Um
        `raise_for_status()` que faltava custou o video inteiro por dois
        caminhos diferentes.

    E' a mesma rede de seguranca do `subir()`, do outro lado do pipeline:
    5xx e timeout sao transitorios, 4xx e permanente. E quando falha, ela
    DIZ o que veio (lei 65) -- status e os primeiros bytes -- em vez de
    deixar o `zipfile` adivinhar.
    """
    espera = 3
    for k in range(tentativas):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code < 400 and r.content[:2] == b"PK":
                if k:
                    print(f"[elenco] baixou na tentativa {k + 1}")
                return r.content
            motivo = (f"HTTP {r.status_code}" if r.status_code >= 400
                      else f"nao e zip (comeca com {r.content[:16]!r})")
            permanente = 400 <= r.status_code < 500 and r.status_code != 429
        except requests.RequestException as e:
            motivo, permanente = f"{type(e).__name__}: {e}", False
        if permanente or k == tentativas - 1:
            raise RuntimeError(f"{url.rsplit('/', 3)[-2]}: {motivo}")
        print(f"[elenco] {motivo}; tentativa {k + 2} de {tentativas} em {espera}s")
        time.sleep(espera)
        espera *= 2


def baixar_elenco(spec, pecas_url):
    """Poe a arte de cada personagem no disco e devolve (pasta_base, KB).

    UM personagem continua sendo o caso normal: com `personagem_url` e sem
    `elenco`, o zip vai para /tmp/personagem e nada muda.

    Com `elenco`, cada personagem ganha a PROPRIA pasta,
    /tmp/personagem/<chave>, e o `pasta` de cada um e' escrito de volta no
    spec -- e assim que `palito_cutout._carregar_elenco` acha as pecas. A
    pasta base devolvida e a do primeiro, porque e' dela que o motor deriva
    onde procurar cenario e objeto.

    NO MAXIMO DOIS EM CENA. Nao e' limitacao tecnica, e' de formato: num
    quadro 9:16 um terceiro boneco ou sai do enquadramento ou obriga um
    recuo em que ninguem mais tem cara. Vem do roteiro, mas o motor
    tambem corta -- um spec errado nao pode virar video ilegivel.
    """
    import io, zipfile
    elenco = spec.get("elenco") or {}
    if not elenco:
        pasta = "/tmp/personagem"
        os.makedirs(pasta, exist_ok=True)
        # UM PERSONAGEM SO TAMBEM PRECISA DE REDE (06/09). Este ramo ficou
        # de fora quando o ramo do `elenco` ganhou tolerancia em 30/08 --
        # e e' justamente ele que nao tem para quem passar a fala, entao
        # aqui a repeticao e o unico recurso que existe.
        dados = baixar_zip(pecas_url)
        zipfile.ZipFile(io.BytesIO(dados)).extractall(pasta)
        if not os.path.exists(os.path.join(pasta, "partes.json")):
            raise RuntimeError("o zip nao tem partes.json na raiz")
        return pasta, len(dados) / 1024.0

    # DOIS EM CENA NAO E DOIS NO VIDEO (30/08, noite).
    #
    # Este corte existia desde que o elenco existe, e ele estava no lugar
    # errado: `MAX_EM_CENA` e o teto do QUADRO (lei 10 -- no 9:16 o terceiro
    # boneco encolhe todo mundo ate a cara sumir), nao o teto do elenco de
    # um episodio. Quem aplica o teto do quadro e o motor, trecho a trecho
    # (`palito_cutout._em_cena`); aqui so se BAIXA arte.
    #
    # Enquanto os dois tetos eram a mesma linha, um spec com troca de
    # personagem no meio perdia a arte do terceiro AQUI, em silencio -- e o
    # video saia com duas pessoas e as falas do terceiro na boca de quem
    # ficou. Foi exatamente o que aconteceu no primeiro render de teste:
    # quatro no spec, dois na tela, e o log dizendo "Fora: zeca, maya".
    if len(elenco) > MAX_EM_CENA:
        print(f"[elenco] {len(elenco)} personagens no video "
              f"({', '.join(elenco)}); {MAX_EM_CENA} por vez em cena, "
              f"decididos trecho a trecho pelo motor")

    publico = f"{SB}/storage/v1/object/public/{BUCKET}"
    total, base = 0.0, None
    for chave, cfg in list(elenco.items()):
        if not isinstance(cfg, dict):
            cfg = {"url": cfg} if str(cfg).startswith("http") else {"pasta": cfg}
            elenco[chave] = cfg
        pasta = os.path.join("/tmp/personagem", chave)
        if not cfg.get("pasta"):
            url = cfg.get("url") or (pecas_url if chave == list(elenco)[0] and pecas_url
                                     else f"{publico}/assets/parte_personagem/{chave}/personagem.zip")
            os.makedirs(pasta, exist_ok=True)
            # UM PERSONAGEM SEM ZIP NAO DERRUBA O VIDEO (30/08). A senhora
            # subiu com as 14 pecas certas e sem `partes.json` -- logo, sem
            # `personagem.zip` --, e o download trouxe a pagina de erro do
            # Storage: `BadZipFile: File is not a zip file` matou o job
            # inteiro, com o outro ator pronto ao lado.
            #
            # Quem falta sai de cena e a esquete continua com quem existe.
            # As falas dele passam para quem ficou (abaixo), que e a mesma
            # regra ja aplicada a personagem citado e nao desenhado: fala na
            # boca errada e melhor que video nenhum.
            try:
                dados = baixar_zip(url)
                zipfile.ZipFile(io.BytesIO(dados)).extractall(pasta)
                if not os.path.exists(os.path.join(pasta, "partes.json")):
                    raise RuntimeError("o zip nao tem partes.json na raiz")
            except Exception as e:
                print(f"[elenco] '{chave}' NAO carregou ({type(e).__name__}: {e}); "
                      f"ele sai de cena e as falas dele passam para quem ficou")
                elenco.pop(chave, None)
                continue
            total += len(dados) / 1024.0
            cfg["pasta"] = pasta
        base = base or cfg["pasta"]
        print(f"[elenco] {chave}: {cfg['pasta']}")

    if not elenco:
        raise RuntimeError("nenhum personagem do elenco carregou: sem arte "
                           "nao ha video")
    # AS FALAS DE QUEM NAO CARREGOU precisam de uma boca. Sem isto o trecho
    # sairia com `ator` apontando para alguem fora de cena, e o motor
    # desenharia a cena sem ninguem mexendo a boca.
    vivos = list(elenco)
    trocados = 0
    for tr in spec.get("trechos", []):
        if tr.get("ator") and tr["ator"] not in elenco:
            tr["ator"] = vivos[0]
            tr["perfil_voz"] = vivos[0]
            trocados += 1
    if trocados:
        print(f"[elenco] {trocados} fala(s) passaram para '{vivos[0]}'")
    return base, total


# =====================================================================
# O ESTILO DO VIDEO: dupla (cena continua) ou CARTAO (18/09)
# =====================================================================
# Ordem do dono: *"suba esse novo estilo para producao em paralelo com o que
# ja esta (...) no comeco faca um video em cada estilo"*.
#
# POR QUE A DECISAO MORA AQUI, E NAO NO n8n
#     O estilo e' escolha de RENDER: o roteiro dos dois e' o mesmo (ver
#     `para_cartao`), e por isso nenhum no precisa saber que existem dois
#     estilos. Pondo a decisao no funil, o experimento nao depende de editar
#     um no de 111 KB nem de uma migracao de coluna -- e o dia em que o
#     cartao sair ou entrar e' uma linha na identidade do canal.
#
# O RODIZIO E' PELA ORDEM DO ITEM NO DIA, e nao por sorteio (lei 34): os
# videos do canal naquele dia sao listados por `horario_post`, e o estilo sai
# do indice. Com `estilo_cartao_em: 2` e dois videos por dia, o primeiro sai
# dupla e o segundo cartao -- "um video em cada estilo", como foi pedido, e
# reproduzivel: dois renders do mesmo item dao o mesmo estilo.
#
# FALHA SEGURA: qualquer erro de consulta, identidade sem a chave, item fora
# da fila (render de teste) -> `dupla`, que e' o estilo que esta no ar. Uma
# decisao de experimento nao pode parar producao.
ESTILO_PADRAO = "dupla"


def estilo_do_item(spec, fila_id, eh_producao):
    if spec.get("estilo") in ("cartao", "dupla"):
        return spec["estilo"], "pedido no spec"
    if not eh_producao:
        return ESTILO_PADRAO, "render de teste (sem fila): estilo padrao"
    try:
        r = requests.get(f"{SB}/rest/v1/fila_producao",
                         params={"fila_id": f"eq.{fila_id}",
                                 "select": "cell_id,horario_post,prompt_video"},
                         headers=CAB, timeout=30)
        item = (r.json() or [None])[0]
        if not item:
            return ESTILO_PADRAO, "item nao esta na fila"
        # QUEM DECIDE E' O PLANEJAMENTO (18/09, §62): `Distribuir Horarios`
        # escolhe o estilo de cada video do dia e escreve no conceito
        # (`| ESTILO: cartao`), porque o ROTEIRO precisa saber antes de
        # escrever -- o cartao pede mais texto para a mesma duracao. Aqui a
        # marca so' e' LIDA: recalcular o rodizio seria uma segunda decisao
        # sobre a mesma coisa, e no dia em que as duas discordassem o video
        # sairia com o texto de um estilo e o render do outro.
        marca = re.search(r"ESTILO:\s*([a-z_]+)",
                          str(item.get("prompt_video") or ""), re.I)
        if marca:
            e = marca.group(1).lower()
            if e in ("cartao", "dupla"):
                return e, "decidido no Planejamento (marca no conceito)"
        cell = item["cell_id"]
        r = requests.get(f"{SB}/rest/v1/identidade_celula",
                         params={"cell_id": f"eq.{cell}",
                                 "select": "identidade_json"},
                         headers=CAB, timeout=30)
        idj = ((r.json() or [{}])[0] or {}).get("identidade_json") or {}
        cada = int(((idj.get("producao") or {}).get("estilo_cartao_em")) or 0)
        if cada < 2:
            return ESTILO_PADRAO, "canal sem `producao.estilo_cartao_em`"
        # os itens do MESMO DIA do canal, por horario -- o indice decide
        dia = str(item["horario_post"])[:10]
        r = requests.get(f"{SB}/rest/v1/fila_producao",
                         params={"cell_id": f"eq.{cell}",
                                 "horario_post": f"gte.{dia}T00:00:00",
                                 "select": "fila_id,horario_post",
                                 "order": "horario_post.asc"},
                         headers=CAB, timeout=30)
        doDia = [x["fila_id"] for x in (r.json() or [])
                 if str(x.get("horario_post", ""))[:10] == dia]
        i = doDia.index(fila_id) if fila_id in doDia else 0
        estilo = "cartao" if (i % cada) == (cada - 1) else "dupla"
        # A RESERVA, para o item que nasceu antes de o Planejamento passar a
        # marcar (ou que foi criado a mao, pela aba Ideia ou por SQL). Ela
        # repete a MESMA regra do nó -- indice do item no dia, 1 cartao a cada
        # `cada` --, e o motivo diz que veio daqui.
        return estilo, (f"rodizio no render (o conceito nao trazia a marca): "
                        f"item {i + 1} de {len(doDia)} do dia, 1 cartao a cada {cada}")
    except Exception as e:                                       # noqa: BLE001
        print(f"[estilo] nao consegui decidir ({type(e).__name__}: {e}); "
              f"seguindo em {ESTILO_PADRAO}")
        return ESTILO_PADRAO, "erro na decisao"


def buscar_cenarios_e_objetos(spec):
    """Poe cenario e objeto no disco, que e onde o motor cut-out procura.

    ISTO FALTAVA, e e a causa real do fundo chapado. palito_cutout sempre
    leu cenario de `<pasta_partes>/../cenarios/` e objeto de `../objetos/`,
    mas NADA no pipeline escrevia nessas pastas -- o zip do personagem so
    traz as pecas do corpo. O `#A5A893` saiu em todo video e passou duas
    sessoes sendo lido como "cenario ainda nao existe", enquanto rua.jpg e
    sala.jpg estavam no bucket.

    Duas fontes, nesta ordem:
      1. o que o spec mandar em `cenarios`/`objetos` (URL explicita)
      2. o padrao do bucket, montado a partir do nome citado nos trechos

    O passo 2 existe porque o no que monta o spec ("3 Producao") ainda nao
    emite `cenarios`. Sem ele, consertar o motor nao mudaria nada nos
    videos de producao ate alguem mexer no n8n.

    Cenario vem do BRUTO (JPEG) de proposito. A versao em `assets/` passou
    pelo rembg, que e segmentador de objeto SALIENTE: num cenario nao ha
    objeto saliente, entao ele apaga quase tudo e devolve um fantasma
    lavado -- conferido em sala.png. Para fundo, alfa nao serve para nada."""
    pasta_cen, pasta_obj = "/tmp/cenarios", "/tmp/objetos"
    publico = f"{SB}/storage/v1/object/public/{BUCKET}"

    import sob_demanda as SD

    # CENARIO REPROVADO NAO SE BAIXA (03/09, item 3 do dono do projeto).
    #
    # `cenarios.REPROVADOS` tira do ar a arte que existe e nao presta -- hoje
    # o `comercio`, que virou um corredor vazio. So que a proibicao mora em
    # `cenarios.resolver`, e ela e' CONTORNADA aqui: o spec traz
    # `cenarios: {comercio: <url>}`, este laco baixa SO o que o spec cita, e
    # entao o motor descobre um inventario com um item so. `resolver` tenta o
    # parecido, nao o encontra no disco (ninguem o baixou) e cai no ramo "o
    # unico que ha" -- devolvendo justamente o cenario proibido.
    #
    # A troca tem de acontecer ANTES do download, que e aqui: o substituto
    # entra no lugar e e' ele que vai para o disco. Sem isto a proibicao e'
    # letra morta, e foi o que o v002 mostrou -- ele saiu no `comercio`
    # depois de o `comercio` ter sido reprovado.
    def _trocar(nome):
        alvo = CEN.normalizar(nome)
        if alvo not in getattr(CEN, "REPROVADOS", {}):
            return nome, None
        # SINONIMO DE REPROVADO GERA O LUGAR EXATO (21/09). "banco" e'
        # sinonimo de `comercio`; o `comercio` esta reprovado; e a troca
        # mandava o banco para o `escritorio`. So que hoje o cenario e'
        # gerado sob demanda: o certo e' pedir um `banco` de verdade, e o
        # `resolver` do motor aceita o literal quando ele esta no disco.
        # So o proprio `comercio` (pedido com esse nome) ainda troca.
        if CEN._limpo(nome).replace(" ", "_") != alvo:
            return nome, None
        for p in CEN.CATALOGO.get(alvo, {}).get("parecidos", ()):
            if p not in getattr(CEN, "REPROVADOS", {}):
                return p, f"'{alvo}' esta reprovado ({CEN.REPROVADOS[alvo]})"
        return nome, None

    import cenarios as CEN

    urls, trocas = {}, {}
    for nome, url in (spec.get("cenarios") or {}).items():
        novo, motivo = _trocar(nome)
        if motivo:
            print(f"[cenario] {nome} -> {novo}: {motivo}")
            trocas[nome] = novo
            urls[novo] = None                # a URL era do reprovado; refaz
        else:
            urls[nome] = url
    for tr in spec.get("trechos") or []:
        nome = tr.get("cenario")
        if not nome:
            continue
        if nome in trocas:
            tr["cenario"] = trocas[nome]     # o trecho passa a pedir o novo
            nome = trocas[nome]
        else:
            novo, motivo = _trocar(nome)
            if motivo:
                print(f"[cenario] {nome} -> {novo}: {motivo}")
                trocas[nome] = novo
                tr["cenario"] = novo
                nome = novo
        if nome not in urls:
            urls[nome] = None                # marca para tentar o padrao
    faltaram = []
    for nome, url in urls.items():
        # a URL do spec primeiro; sem ela, as grafias possiveis do bucket.
        # O `.png` do BRUTO entrou em 28/08: o gerador de imagem devolve ora
        # JPEG ora PNG e o preparar_assets guarda com a extensao que veio,
        # entao procurar so `.jpg` no bruto fazia um cenario novo passar por
        # inexistente e o motor cair na cor chapada.
        for c in ([url] if url else []) + [
                f"{publico}/assets_bruto/cenario/geral/{nome}.jpg",
                f"{publico}/assets_bruto/cenario/geral/{nome}.png",
                f"{publico}/assets/cenario/geral/{nome}.png"]:
            if _baixar_para(c, pasta_cen, nome):
                break
        else:
            faltaram.append(nome)

    # CENARIO SOB DEMANDA (28/08). O que o roteiro pediu e ninguem desenhou
    # e gerado AGORA, e ja entra neste video: cenario vai para o bruto e nao
    # passa por rembg, entao custa ~20s e nao ha por que adiar. Ver
    # sob_demanda.py -- inclusive o teto, que existe porque roteiro que pede
    # tres cenarios novos trocou de lugar tres vezes em vinte segundos.
    for nome in faltaram[:SD.MAX_POR_VIDEO]:
        SD.gerar_cenario(nome, pasta_cen)
    for nome in faltaram[SD.MAX_POR_VIDEO:]:
        print(f"[sob-demanda] '{nome}' passou do teto de "
              f"{SD.MAX_POR_VIDEO} por video; fica para depois")
        SD.encomendar("cenario", nome, "passou do teto num video")
    spec["pasta_cenarios"] = pasta_cen

    objetos = spec.get("objetos") or {}
    locais = {}
    gerados = 0
    for nome, ref in objetos.items():
        alvo = (ref if isinstance(ref, str) and ref.startswith("http")
                else f"{publico}/assets/objeto/geral/{ref or nome}.png")
        if _baixar_para(alvo, pasta_obj, nome):
            locais[nome] = nome
            continue
        # OBJETO SOB DEMANDA PASSOU A SER GERADO AQUI (11/09).
        #
        # Ate hoje ele era ENCOMENDADO: o video de hoje usava um substituto e
        # o de amanha tinha a arte, porque objeto precisa de alfa e alfa vinha
        # do rembg, que so roda no Action `assets`. A decisao era de 28/08 e
        # era defensavel.
        #
        # Duas coisas a derrubaram. A primeira e' que a encomenda NUNCA foi
        # feita: `assets_pendentes` esta vazia, porque o vocabulario de objeto
        # era fechado em dez nomes e nada fora deles chegava ao spec para dar
        # falta -- a engrenagem girava no vacuo. A segunda e' que o rembg
        # deixou de ser necessario: a arte deste canal e vetorial chapada
        # sobre fundo branco liso, e recortar isso e uma conta de cor (ver
        # `sob_demanda._recortar_fundo`), nao um modelo de rede neural.
        #
        # Custa ~15 s, roda com numpy e Pillow que o render ja tem, e poe na
        # tela a coisa que a esquete inteira discute -- que e' a queixa do
        # dono. Falhando, a encomenda continua sendo o plano B.
        if gerados < SD.MAX_POR_VIDEO and SD.gerar_objeto(nome, pasta_obj):
            gerados += 1
            locais[nome] = nome
            continue
        locais[nome] = ref
        SD.encomendar("objeto", nome, "pedido por um roteiro, sem arte, e a "
                                      "geracao na hora nao deu resultado")
    if objetos:
        spec["objetos"] = locais
    spec["pasta_objetos"] = pasta_obj


def baixar_musica(spec):
    """Poe a trilha no disco, em WAV, quando o spec apontar uma faixa.

    A trilha PADRAO e sintetizada no proprio render (sfx.trilha) e nao
    precisa de download nenhum -- esta funcao so existe para o dia em que
    houver uma faixa de verdade no bucket. Duas grafias sao aceitas: o
    `musica.url` do formato de 29/08 e o `musica_url` solto que o job ja
    lia antes.

    Converte para WAV porque o mixador (sfx.mixar) trabalha em PCM, com o
    mesmo sample rate da voz -- entregar um MP3 ali faria o modulo desistir
    da trilha e o video sair so com voz e efeitos, calado sobre o motivo.
    """
    cfg = spec.get("musica")
    url = spec.get("musica_url")
    if isinstance(cfg, dict):
        url = cfg.get("url") or url
    elif isinstance(cfg, str) and cfg.startswith("http"):
        url, cfg = cfg, {}
    if not url:
        return
    bruto, wav = "/tmp/musica_bruta", "/tmp/musica.wav"
    try:
        Path(bruto).write_bytes(requests.get(url, timeout=180).content)
        import subprocess
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", bruto,
                        "-ar", "24000", "-ac", "1", wav], check=True)
        cfg = dict(cfg) if isinstance(cfg, dict) else {}
        cfg["arquivo"] = wav
        spec["musica"] = cfg
        print(f"[musica] faixa baixada de {url.rsplit('/', 1)[-1]}")
    except Exception as e:
        # trilha e melhoria, nao requisito: sem ela o render usa a sintetica
        print(f"[musica] download falhou ({e}); usando a trilha sintetizada")
        if isinstance(spec.get("musica"), str):
            spec["musica"] = True


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

    # O ELEVENLABS E EXCLUSIVO DO CANAL (05/09, decisao do dono do projeto)
    #
    #   *"para testes nunca use o elevenlabs para a voz, deixe exclusivo para
    #    o canal, e ele sempre deve tentar primeiro usar a voz do elevenlabs
    #    no canal antes de ir para o plano b"*
    #
    # A conta tem 40.000 creditos por mes, e o ciclo de video gastava deles
    # como se fossem de graca: cada volta sao 10 a 16 falas, e o ciclo roda
    # dezenas de voltas por dia. Sao os creditos do CANAL sendo queimados
    # para ninguem ouvir -- as voltas do ciclo existem para julgar imagem e
    # texto, e o Edge-TTS fala igual para esse fim.
    #
    # A GUARDA FICA AQUI, e nao no `montar_spec`, porque aqui e' o funil: todo
    # render passa por este ponto, venha ele do ciclo, do painel ou de um
    # disparo a mao. `fila_id` que nao e' uuid E render de teste, por
    # definicao (ver `UUID_RE` e `atualizar_fila`) -- a mesma regra que ja
    # decide nao gravar na fila e nao publicar.
    # E A MESMA REGRA VAI PARA O AMBIENTE (07/09, ordem do dono: a voz paga e'
    # "apenas producao, nunca testes"). Sao duas camadas de proposito:
    #   · aqui, o spec tem os perfis trocados para `edge` -- resolve o caminho
    #     normal, em que o motor le o spec;
    #   · `PRODUCAO` fecha o caminho de quem NAO passa por aqui.
    #     `render_local.py` e `disparar_render.py` montam spec proprio e
    #     chamam `palito_v5.sintetizar` direto; sem a variavel, um teste local
    #     com `motor: eleven` no spec gastaria credito de uma conta que nao
    #     acumula de um mes para o outro.
    eh_producao = bool(UUID_RE.match(str(fila_id)))
    os.environ["PRODUCAO"] = "1" if eh_producao else "0"
    if not eh_producao:
        trocadas = 0
        for _perfil, cfg in (spec.get("vozes") or {}).items():
            if isinstance(cfg, dict) and str(cfg.get("motor", "")).lower() in ("eleven", "elevenlabs"):
                cfg["motor"] = "edge"
                trocadas += 1
        if trocadas:
            print(f"[voz] render de TESTE: {trocadas} perfil(is) de eleven -> edge. "
                  f"Os creditos do ElevenLabs sao exclusivos do canal.")

    baixar_musica(spec)

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
    # O ESTILO vem antes do motor: ele decide QUAL render roda (ver
    # `estilo_do_item`). O cartao exige arte de peca, como o cut-out -- sem
    # ela nao ha cartao, e o video cai no caminho normal.
    estilo, porque_estilo = estilo_do_item(spec, fila_id, eh_producao)
    print(f"[estilo] {estilo} ({porque_estilo})")
    # A COPIA TROCA DE DESENHO A CADA FRASE (21/09): o teto de arte gerada
    # por video e' do estilo (`formatos.cartao.arte_nova_max`), nao do motor
    # -- os 2 de `sob_demanda` sao da dupla, que tem um objeto so'.
    if estilo == "cartao":
        try:
            from config_gerado import formato_de as _fd
            import sob_demanda as _SD
            _SD.MAX_POR_VIDEO = int(_fd("cartao").get("arte_nova_max") or _SD.MAX_POR_VIDEO)
            print(f"[sob-demanda] teto de arte nova neste video: {_SD.MAX_POR_VIDEO}")
        except Exception as e:                                       # noqa: BLE001
            print(f"[sob-demanda] teto do estilo nao lido ({e}); fica o do motor")

    pecas_url = spec.get("personagem_url") or os.environ.get("PERSONAGEM_URL", "")
    motor = "vetor"
    if pecas_url or spec.get("elenco"):
        # FORA do try do cut-out: cada download ja falha sozinho e segue.
        # Se estivesse dentro, um erro aqui derrubaria o motor inteiro para
        # o rig vetorial por causa de um FUNDO -- trocar o video certo pelo
        # video da rede de seguranca e o pior desfecho possivel.
        buscar_cenarios_e_objetos(spec)
        try:
            pasta, kb = baixar_elenco(spec, pecas_url)
            if estilo == "cartao":
                # O MESMO ROTEIRO, EM CARTOES. A arte esta no mesmo lugar
                # (`/tmp/personagem/<chave>`, cenarios e objetos em `../`),
                # que e' onde `cartao.Contexto` tambem procura -- nada a
                # mover. Se a conversao ou o render de cartao falharem, o
                # `except` abaixo cai no vetor como sempre; por isso a
                # conversao esta AQUI dentro e nao antes do try.
                import para_cartao
                from cartao import render as render_cartao
                spec_c = para_cartao.converter(spec, pasta_base=pasta)
                print(f"[motor] CARTAO ({kb:.0f} KB de arte)")
                motor = "cartao"
                _, dur = render_cartao(pasta, spec_c, out, tmpdir="/tmp/render")
            else:
                from palito_cutout import render as render_cutout
                print(f"[motor] cut-out ({kb:.0f} KB de arte)")
                motor = "cutout"
                _, dur = render_cutout(pasta, spec, out, tmpdir="/tmp/render")
        except Exception as e:
            # Traceback completo de proposito: este except engole TUDO, ate
            # ImportError. No run #11 um 'No module named numpy' (dependencia
            # que faltava no requirements.txt) apareceu como uma linha solta e
            # passou por defeito de arte -- o cut-out nunca tinha rodado.
            traceback.print_exc()
            # EM PRODUCAO O VETOR NAO EXISTE (20/09, ordem do dono: *"um de
            # teste que nunca era para ter subido para producao"*). Em 20/09
            # um `config_gerado.py` com `true` em vez de `True` derrubou o
            # import do `para_cartao`, os dois cartoes do dia cairam aqui e um
            # foi PUBLICADO no rig vetorial. "Melhor video feio que producao
            # parada" valia quando o vetor era o unico motor; hoje o vetor e'
            # o motor de TESTE, e video de teste no canal e' pior do que um
            # item que a Manutencao repesca em 2 h. Em producao o job falha
            # com o motivo (status `erro` + callback, no `__main__`); o vetor
            # fica so' para ensaio e teste local.
            if eh_producao:
                raise RuntimeError(f"motor {estilo} falhou em producao "
                                   f"(sem rede vetorial): {e}") from e
            print(f"[motor] cut-out falhou ({e}); caindo para o rig vetorial "
                  "(SO fora de producao)")
            motor = "vetor"
    if motor == "vetor":
        if eh_producao:
            raise RuntimeError("producao sem arte de personagem: o rig vetorial "
                               "nao publica (20/09)")
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
    # O ESTILO VAI NO AVISO (18/09): e' o que permite comparar o rodizio
    # depois. Sem ele, daqui a duas semanas ninguem sabe qual video era
    # cartao e qual era dupla -- e o A/B vira anedota (a mesma exigencia do
    # `gancho_frio_por` em §31.4).
    avisar({"fila_id": fila_id, "status": "ok", "video_url": url,
            "duracao_s": dur, "render_s": round(time.time() - t0),
            "estilo": estilo, "estilo_por": porque_estilo, "motor": motor})


RENDER_TENTATIVAS = 2     # quantas vezes um item volta para a fila depois de falhar


def _registrar_falha_render(fila_id, erro):
    """Grava `render_falhou` em logs_execucao e devolve quantas falhas este
    item ja acumulou (contando esta). Sem cell_id conhecido, le da fila."""
    hdr = {"apikey": KEY, "Authorization": f"Bearer {KEY}",
           "Content-Type": "application/json"}
    try:
        r = requests.get(f"{SB}/rest/v1/fila_producao?fila_id=eq.{fila_id}&select=cell_id",
                         headers=hdr, timeout=30)
        cell = ((r.json() or [{}])[0] or {}).get("cell_id")
        requests.post(f"{SB}/rest/v1/logs_execucao", headers=dict(hdr, Prefer="return=minimal"),
                      json={"cell_id": cell, "workflow": "render", "evento": "render_falhou",
                            "nivel": "error",
                            "detalhe_json": {"fila_id": fila_id, "erro": str(erro)[:400]}},
                      timeout=30)
        r = requests.get(f"{SB}/rest/v1/logs_execucao?select=log_id&evento=eq.render_falhou"
                         f"&detalhe_json->>fila_id=eq.{fila_id}", headers=hdr, timeout=30)
        return len(r.json() or [])
    except Exception as e2:                                      # noqa: BLE001
        print(f"[fila] nao consegui registrar a falha: {e2}")
        return RENDER_TENTATIVAS + 1


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        # Item que fica em 'aguardando_render' para sempre é o bug de "item
        # preso" do §6. NUNCA 'erro_publicacao': é beco sem saída (§7).
        #
        # DESDE 20/09 A FALHA DE RENDER TENTA DE NOVO, ATE DUAS VEZES: sem o
        # vetor como rede (ver a escolha do motor), uma falha em producao
        # deixaria o dia sem video. O item volta a `pendente` e o Dispatcher
        # o produz de novo no proximo ciclo; na terceira falha vira `erro`,
        # que e' terminal -- e o motivo fica em logs_execucao (`render_falhou`)
        # para quem for ler, em vez de so' no log do Action.
        fid = os.environ.get("FILA_ID", "")
        falhas = _registrar_falha_render(fid, e) if UUID_RE.match(str(fid)) else 99
        novo = "pendente" if falhas <= RENDER_TENTATIVAS else "erro"
        print(f"[fila] falha {falhas} de {RENDER_TENTATIVAS} -> {novo}")
        try:
            atualizar_fila(fid, {"status": novo, "video_url": None, "atualizado_em": "now()"})
        except Exception as e2:
            print(f"[fila] nao consegui marcar {novo}: {e2}")
        avisar({"fila_id": fid, "status": "erro", "erro_msg": str(e)[:500],
                "tentativa": falhas, "proximo_status": novo})
        sys.exit(1)
