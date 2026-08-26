#!/usr/bin/env python3
"""
palito_cutout — animação CUT-OUT: arte de IA, movimento por rig.

Você pediu para sair do vetor. Esta é a saída que cabe no orçamento.

O PROBLEMA COM image-to-video (a rota do vídeo de referência):
    90 vídeos/mês x 4 planos x 5s = 1.800 segundos
    WAN 2.5 (o mais barato):  US$ 90/mês = R$ 486   -> 7x o orçamento
    Kling 2.6 Pro:            US$126/mês = R$ 680   -> 10x
    Dentro de R$70 cabem 259 segundos animados por mês. Isso é 17 vídeos
    com 3 planos, ou 52 clipes. Não 90 vídeos.

A SAÍDA — cut-out (animação de recorte):
    A IA desenha o personagem UMA VEZ, em partes. O rig move as partes.
    É como South Park e boa parte da animação de TV é feita há décadas.

    arte:       ~US$ 1 por personagem, uma vez
    cenários:   US$ 0,003 cada
    animação:   grátis (PIL, no runner do GitHub)
    total:      ~R$ 7/mês para 90 vídeos

O que muda em relação ao vetor: o personagem deixa de ser desenhado por
código e passa a ser ARTE DE VERDADE — cabelo, sombreado, roupa, rosto
ilustrado. O que NÃO muda: poses, timing, lipsync, consistência 100%.
As partes são sempre as mesmas imagens.

COMO AS PARTES NASCEM
    Não se pede peça por peça ao gerador -- isso falhou nas 13 tentativas
    de 19/08 e voltaram 13 desenhos de um homem inteiro. Pede-se UMA folha
    do personagem em pose T, e o recorte é feito por geometria em
    fatiar.py. Ver folha_personagem.py para a estrutura de requisitos de
    cada peça (o que inclui, o que exclui, pivô, orientação, tamanho).

O QUE MUDOU EM 21/08 — MOVIMENTO COM CAUSA
    O vídeo de 20/08 não tinha movimento, tinha agitação: duas poses
    estáticas interpoladas ao longo da fala inteira, mais um seno no
    quadril. O personagem nunca saía do lugar e nada no texto explicava
    o que ele fazia com os braços.

    Agora o movimento vem de AÇÕES (acoes.py) -- verbos com janela de
    tempo dentro do trecho e um campo `motivo` que amarra a ação à fala.
    Entrou junto o que faltava para "andar" sequer existir:

      * ciclo de passada de verdade (pernas em oposição de fase, joelho
        dobrando para trás, quique do centro de massa)
      * CÂMERA: o fundo corre ao contrário do sentido da caminhada, em
        ladrilho espelhado (sem emenda visível, deslocamento infinito)
      * personagem desenhado numa CAMADA própria, o que permite espelhar
        (virar para o outro lado) e dar zoom sem redesenhar nada
      * gancho obrigatório: acoes.garantir_gancho() injeta uma ação forte
        nos primeiros segundos se o roteirista não puser uma

    Specs antigos (com `pose`/`pose_saida` e sem `acoes`) continuam
    rodando pelo caminho de compatibilidade.

Uso:
    python3 palito_cutout.py --partes ./personagem --spec spec.json -o saida.mp4
"""
import argparse, json, math, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from palito_v4 import REST, POSES, EXPRESSOES, merge, blend, pt
import acoes as ACOES
import expressao as EXPR
from folha_personagem import (ESQUELETO, ORDEM_Z, FONTE_ANGULO,
                              CORRECAO_POSE_T, SEGUE)

# repouso da cara: o dicionário completo com todo campo em zero, para que
# desenhar_personagem nunca precise checar chave faltando
EXPR_ZERO = EXPR.CATALOGO["neutro"]

W, H, FPS = 1080, 1920, 24

# altura de referencia do personagem no quadro; objetos sao medidos contra ela
ALTURA_ALVO_PX = 1150


# =====================================================================
# Composição: girar em torno do pivô e colar no destino
# =====================================================================
def colar(base, img, pivot, destino, ang, escala=1.0, espelhar=False):
    """Gira `img` em torno de `pivot` e cola de modo que o pivô caia em `destino`.

    É a operação inteira da animação cut-out. Todo o resto é decidir
    quais ângulos passar."""
    p = img
    if espelhar:
        p = p.transpose(Image.FLIP_LEFT_RIGHT)
        pivot = (p.width - pivot[0], pivot[1])
    if escala != 1.0:
        nw, nh = int(p.width * escala), int(p.height * escala)
        p = p.resize((nw, nh), Image.LANCZOS)
        pivot = (pivot[0] * escala, pivot[1] * escala)

    # expand=False mantem o sistema de coordenadas: o pivo nao se move
    rot = p.rotate(-ang, resample=Image.BICUBIC, center=pivot, expand=False)
    base.alpha_composite(rot, (int(destino[0] - pivot[0]), int(destino[1] - pivot[1])))


def _centralizar(img, pivot):
    """Coloca a arte numa tela QUADRADA com o pivo no centro.

    Sem isto, girar um braco para a horizontal CORTA o membro: o rotate
    com expand=False mantem o tamanho original da imagem, e uma tela de
    120x190 nao comporta 190px na horizontal. Foi exatamente esse o
    defeito que fazia o antebraco parecer descolado.

    Com o pivo no centro de um quadrado de lado 2*R (R = maior distancia
    do pivo a um canto), qualquer angulo cabe."""
    px, py = pivot
    R = int(math.ceil(max(
        math.hypot(px, py), math.hypot(img.width - px, py),
        math.hypot(px, img.height - py),
        math.hypot(img.width - px, img.height - py)))) + 2
    tela = Image.new("RGBA", (2 * R, 2 * R), (0, 0, 0, 0))
    tela.alpha_composite(img, (R - int(px), R - int(py)))
    return tela, (R, R)


def _cor_da_casca(img):
    """A cor do contorno da peça, amostrada da própria arte.

    Cravar preto funcionaria para o Pal e quebraria no primeiro personagem
    com contorno colorido. A casca é o anel de fora do alfa; a mediana dele
    é a cor da linha."""
    a = np.asarray(img)
    al = a[..., 3]
    dentro = al > 128
    if not dentro.any():
        return (26, 24, 20)
    erodido = np.asarray(img.split()[3].filter(ImageFilter.MinFilter(5))) > 128
    anel = dentro & ~erodido
    if anel.sum() < 20:
        anel = dentro
    return tuple(int(v) for v in np.median(a[anel][:, :3], axis=0))


def _e_fiapo(img, limiar=0.22):
    """A peça é uma mancha cheia ou um pedaço de contorno?

    Mesma régua de folha_personagem.conferir_rosto: feição de verdade
    ocupa boa parte da própria caixa; fiapo de contorno ocupa quase nada."""
    a = np.asarray(img.convert("RGBA"))[..., 3] > 10
    return (a.sum() / max(a.size, 1)) < limiar


def _tapar_entalhe(img, cor=None):
    """Fecha o RECORTE DA BOCA no crânio, com a cor da própria pele.

    POR QUE (o defeito nº 1 do projeto, e a causa real dele)
        A folha do Pal desenha a boca como um ENTALHE VAZADO no crânio: um
        buraco em U aberto na base da cabeça, que existe para o segmentador
        poder separar o queixo. O queixo deveria tapá-lo -- é a mandíbula
        que fica ali, e ela desce quando a boca abre.

        Só que nesta folha a mandíbula não foi segmentada: saiu um punhado
        de pixels soltos. O entalhe ficou permanentemente aberto, o motor
        pintou o interior de boca dentro dele, e o personagem passou todos
        os vídeos parecendo que grita. O HANDOFF registrava isso como
        "defeito de arte: a boca está desenhada aberta". Está mais perto de
        ser verdade que a boca está desenhada FECHADA e é a peça que a
        fecharia que não existe.

        Enquanto a folha nova não chega, tapar o entalhe com a cor da pele
        devolve uma cara de boca fechada. O custo é não haver lipsync de
        queixo -- que já não havia, porque não há queixo.

    Como: o entalhe é uma reentrância estreita e profunda. Um FECHAMENTO
    morfológico (dilata e depois erode) preenche reentrância estreita e
    devolve o contorno externo intacto. O que o fechamento acrescentou é
    exatamente a área do entalhe.

    Tapar SÓ o vazio não bastou: o entalhe tem contorno preto próprio (é o
    lábio superior desenhado), e preencher o buraco deixava um retângulo de
    pele cercado por um U preto -- lia como queixo quadrado. Então a tapa
    cobre o vazio MAIS o traço em volta dele, e quem devolve a boca é
    `_boca_desenhada`. A cara termina lisa, e a boca passa a ser desenhada
    onde o desenhista pôs a dele.

    Devolve (peça tapada, caixa da boca em coordenadas da peça).
    """
    from PIL import ImageChops
    from segmentar import _componentes
    alfa = img.split()[3]
    r = max(3, int(min(img.width, img.height) * 0.11))
    # dilatar+erodir com o MESMO raio: o contorno externo volta ao lugar,
    # a reentrância não
    fechado = alfa.filter(ImageFilter.MaxFilter(2 * r + 1)) \
                  .filter(ImageFilter.MinFilter(2 * r + 1))
    novo = ImageChops.subtract(fechado, alfa)
    arr = np.asarray(novo) > 8
    if arr.sum() < 10:
        return img, None

    # QUAL das reentrâncias é a boca. O fechamento preenche TODAS: o vão
    # entre a orelha e a cabeça, o recorte em V da franja, o entalhe do
    # queixo. Usar a união (a primeira versão desta função) põe a "boca" no
    # meio da testa e cobre metade do cabelo de pele -- foi exatamente o que
    # saiu no primeiro teste. A boca é a reentrância do TERÇO DE BAIXO,
    # perto do eixo do rosto, e é a maior de lá.
    ys_, xs_ = np.nonzero(np.asarray(alfa) > 8)
    cx_rosto, y_base = float(xs_.mean()), float(ys_.max())
    alt_peca = float(ys_.max() - ys_.min() + 1)
    cands = [c for c in _componentes(arr, area_min=max(int(arr.sum() * 0.05), 40))
             if c["cy"] > y_base - alt_peca * 0.45
             and abs(c["cx"] - cx_rosto) < img.width * 0.22]
    if not cands:
        return img, None
    boca = max(cands, key=lambda c: c["area"])
    so_boca = Image.fromarray((boca["mask"] * 255).astype(np.uint8))
    bx0, by0, bx1, by1 = boca["bbox"]
    caixa = (int(bx0), int(by0), int(bx1), int(by1))

    # engorda a tapa para engolir o contorno do entalhe, mas nunca para
    # fora da própria peça: dilatar sem essa trava comeria o queixo
    g = max(2, int((by1 - by0 + 1) * 0.22))
    larga = so_boca.filter(ImageFilter.MaxFilter(2 * g + 1))
    larga = ImageChops.multiply(larga, fechado)
    # A tapa não pode passar da coluna do entalhe. Sem esta trava ela
    # crescia para os lados e apagava o contorno da bochecha na altura da
    # boca -- um buraco no perfil do rosto, visível em close.
    faixa = np.zeros(np.asarray(larga).shape, dtype=np.uint8)
    faixa[:, max(0, bx0 - g):min(img.width, bx1 + g + 1)] = 255
    larga = ImageChops.multiply(larga, Image.fromarray(faixa))

    # COR AMOSTRADA AO REDOR DO ENTALHE, não a mediana da peça inteira: a
    # bochecha tem sombreado próprio, e a mediana global deixava um
    # retângulo de tom diferente em volta da boca.
    # PREENCHIMENTO PELA COR DA BOCHECHA AO LADO. Duas outras tentativas
    # ficaram piores e vale registrar por quê:
    #   * mediana da peça inteira -> retângulo de tom errado em volta da
    #     boca, porque a peça inclui cabelo, olhos e contorno;
    #   * propagação coluna a coluna a partir do pixel de cima -> o que está
    #     logo acima do entalhe é o sulco do nariz, mais claro que o queixo,
    #     e a tapa saía luminosa demais (visível no teste de 28/08).
    # A vizinhança LATERAL do entalhe é a própria bochecha, no tom exato.
    a = np.asarray(img.convert("RGBA")).copy()
    m = np.asarray(larga) > 8
    lados = []
    for y in range(by0, by1 + 1):
        lin = np.nonzero(m[y])[0]
        if not len(lin):
            continue
        for x in (int(lin.min()) - g - 3, int(lin.max()) + g + 3):
            if 0 <= x < img.width and a[y, x, 3] > 200 and not m[y, x] \
                    and int(a[y, x, :3].sum()) > 300:
                lados.append(a[y, x, :3])
    if len(lados) >= 8:
        pele = tuple(int(v) for v in np.median(np.array(lados), axis=0))
    else:
        pele = cor or _cor_em_volta(img, larga, so_boca) or _cor_da_pele(img)
    a[m, :3] = pele
    a[m, 3] = 255
    tapado = Image.fromarray(a)

    # borda macia: mesmo com a cor certa, a emenda dura entrega o remendo.
    # Dois pixels de desvanecimento bastam.
    # 5 é o ponto de equilíbrio medido em 28/08: com 2 a emenda aparecia como
    # borda dura; com 9 a tapa fica translúcida na borda e o traço preto do
    # entalhe reaparece por baixo dela.
    suave = Image.composite(tapado, img, larga.filter(ImageFilter.GaussianBlur(5)))
    return suave, caixa


def _boca_desenhada(larg, alt_max, nivel, curva, cor_traco, cor_dentro=None):
    """A boca, quando a folha não traz queixo articulado.

    É a única coisa do personagem desenhada por código, e é assim de
    propósito: a bíblia visual define a boca como "one single short line,
    lips together", e uma linha é justamente o que dá para desenhar sem
    inventar estilo. O resto do personagem continua sendo arte.

    O que ela sabe fazer, e por que cada um importa:
      * FECHAR. Em repouso é um traço. É o defeito nº 1 do projeto: sem
        isto o Pal passa o vídeo inteiro parecendo que grita.
      * ABRIR com o som. `nivel` vem da mesma envoltória do áudio que
        movia o maxilar, então o lipsync volta a existir sem queixo.
      * CURVAR. `curva` positivo sorri, negativo entristece -- o que a
        peça de queixo, sozinha, nunca conseguiu fazer.

    Desenhada numa telinha própria e colada como qualquer outra peça: aí
    ela gira com a cabeça de graça."""
    cor_dentro = cor_dentro or COR_BOCA
    larg = max(6, int(larg))
    alt = max(3, int(alt_max * max(0.0, min(1.0, nivel))))
    esp = max(2, int(larg * 0.065))                 # espessura do traço
    # SINAL: y cresce para baixo, então sorriso (curva > 0) tem que empurrar
    # o MEIO da linha para baixo. A primeira versão fazia o contrário e
    # `sorrindo` saía com cara de choro.
    arco = -curva * larg * 0.16                     # flecha da curva
    pad = int(esp * 2 + abs(arco) + 4)
    tela = Image.new("RGBA", (larg + 2 * pad, int(alt) + 2 * pad + int(abs(arco) * 2)),
                     (0, 0, 0, 0))
    d = ImageDraw.Draw(tela)
    cy = tela.height / 2.0
    x0, x1 = pad, pad + larg

    if alt <= esp * 1.2:
        # BOCA FECHADA: um arco fino. Três pontos e uma curva quadrática
        # aproximada por segmentos -- ImageDraw não tem Bézier, e uma
        # parábola de 24 segmentos é indistinguível numa boca de 60px.
        pts = []
        for i in range(25):
            u = i / 24.0
            pts.append((x0 + (x1 - x0) * u,
                        cy - arco * 4 * u * (1 - u)))
        d.line(pts, fill=cor_traco + (255,), width=esp, joint="curve")
    else:
        # BOCA ABERTA: elipse com o interior escuro e o mesmo traço em volta.
        # O centro desce um pouco com a abertura, como um queixo desceria.
        cyy = cy + alt * 0.18 - arco * 0.5
        caixa = [x0, cyy - alt / 2.0, x1, cyy + alt / 2.0]
        d.ellipse(caixa, fill=cor_dentro, outline=cor_traco + (255,), width=esp)
    return tela, (tela.width / 2.0, cy)


def _cor_em_volta(img, tapa_mask, nucleo_mask, folga=6):
    """A cor da pele COLADA no entalhe.

    Anel de pixels que fica logo fora da tapa: é a bochecha e o queixo em
    volta da boca, exatamente o tom que a tapa precisa ter para sumir."""
    a = np.asarray(img.convert("RGBA"))
    dentro = np.asarray(tapa_mask) > 8
    fora = np.asarray(tapa_mask.filter(ImageFilter.MaxFilter(2 * folga + 1))) > 8
    anel = fora & ~dentro & (a[..., 3] > 200)
    if anel.sum() < 30:
        return None
    px = a[anel][:, :3]
    claros = px[px.sum(axis=1) > 240]      # fora o traço preto do contorno
    base = claros if len(claros) > 20 else px
    return tuple(int(v) for v in np.median(base, axis=0))


def _cor_da_pele(img):
    """A cor dominante do MIOLO da peça -- a pele, não o contorno.

    Erodir joga fora a casca preta; o que sobra é o preenchimento."""
    a = np.asarray(img.convert("RGBA"))
    miolo = np.asarray(img.split()[3].filter(ImageFilter.MinFilter(9))) > 128
    if miolo.sum() < 20:
        return _cor_da_casca(img)
    px = a[miolo][:, :3]
    claros = px[px.sum(axis=1) > 200]          # descarta traço interno escuro
    base = claros if len(claros) > 20 else px
    return tuple(int(v) for v in np.median(base, axis=0))


def _fechar_vao(img, pivot, px):
    """Engrossa a peça `px` pixels com a cor do próprio contorno.

    POR QUE (defeito visto no run #13 e explicado só agora)
        A folha é um BONECO DE PAPEL: cada parte tem contorno próprio e um
        vão branco a separa da vizinha. O vão é o que permite segmentar a
        folha, e o meio dele é a articulação -- é a decisão estrutural do
        projeto e continua certa.

        Só que o motor nunca fechou esse vão ao compor. Enquanto o fundo
        era branco isso não aparecia: vão branco sobre fundo branco é
        invisível. Com CENÁRIO atrás, cada vão virou um rasgo por onde a
        rua aparece -- ombro, cintura, punho, joelho e tornozelo abertos,
        o corpo lido como pedaços soltos. O HANDOFF registrava um caso
        disto ("vão entre antebraço e mão que não fecha") como defeito de
        pivô; não era: é o vão desenhado, em todas as juntas.

        Peça vizinha cresce metade do vão de cada lado e as duas se
        encostam. Crescer com a COR DO CONTORNO faz a emenda ler como
        linha um pouco mais grossa, que é exatamente como cut-out de
        verdade resolve: as peças se sobrepõem, não se tangenciam.

    O pivô não se mexe em relação ao desenho -- a peça cresce em volta
    dele --, então nenhuma medida da folha é invalidada."""
    if px <= 0:
        return img, pivot
    m = int(px)
    tela = Image.new("RGBA", (img.width + 2 * m, img.height + 2 * m), (0, 0, 0, 0))
    tela.alpha_composite(img, (m, m))
    alfa = tela.split()[3].filter(ImageFilter.MaxFilter(2 * m + 1))
    grossa = Image.new("RGBA", tela.size, _cor_da_casca(img) + (255,))
    grossa.putalpha(alfa)
    grossa.alpha_composite(tela)          # a arte original por cima do anel
    return grossa, (pivot[0] + m, pivot[1] + m)


class Personagem:
    """Carrega as peças e as âncoras uma vez, na memória.

    `pivos` é onde cada peça gira; `saidas` é, dentro de cada peça, onde
    cada filho se encaixa. Os dois vêm medidos da folha (segmentar.py), e
    é por isso que o motor não precisa mais de comprimento de osso nem de
    nenhuma constante anatômica: a posição do cotovelo é o ponto que o
    desenhista deixou marcado no vão."""

    def __init__(self, pasta):
        self.pasta = pasta
        cfg = json.load(open(os.path.join(pasta, "partes.json"), encoding="utf-8"))
        self.pivos = cfg["pivos"]
        self.saidas = cfg.get("saidas", {})
        self.escala = cfg.get("escala", 1.0)
        self.comp = cfg.get("comprimentos", {})
        self.vaos = cfg.get("vaos", {})
        # CORREÇÃO DE FOLHA: a arte vem em pose T; em cena o braço cai.
        self.corr = dict(CORRECAO_POSE_T)
        for filho, dono in SEGUE.items():
            self.corr.setdefault(filho, self.corr.get(dono, 0.0))
        # O segmentador mede vão só nas juntas do corpo; nas peças de rosto
        # ele grava 0. Para olho, nariz e sobrancelha isso é certo -- são
        # adornos colados no crânio e engrossá-los mudaria a cara. A
        # MANDÍBULA é outra coisa: ela é a única peça de rosto que se MOVE
        # em relação ao pai, e é por ela que a boca abre. Sem fechar o vão
        # dela, o entalhe do crânio fica maior que o queixo e a boca parece
        # permanentemente entreaberta -- foi lido como defeito da arte.
        medidos = [v for v in self.vaos.values() if v > 0.5]
        tipico = sorted(medidos)[len(medidos) // 2] if medidos else 5.0
        self.img, self.piv, self.tam = {}, {}, {}
        self._cache_var = {}          # peças deformadas pela expressão facial
        # ROSTO ARTICULADO OU CARA DESENHADA? Se a mandíbula não veio como
        # peça de verdade, não há queixo para descer: a boca não abre, e o
        # entalhe dela precisa ser tapado (ver _tapar_entalhe). Decidir isto
        # UMA vez, no carregamento, evita testar peça a peça em 430 frames.
        self.rosto_articulado = True
        for nome in cfg["partes"]:
            if nome not in self.pivos:
                # Rede de seguranca contra partes.json desatualizado: sem pivo
                # medido o rig nao sabe onde a peca gira, entao ela nao entra
                # em cena. Pular e' muito melhor que derrubar o render -- foi
                # um KeyError('boca_0') aqui que mandou o run #12 inteiro para
                # o rig vetorial.
                print(f"[personagem] '{nome}' nao tem pivo medido; ignorando")
                continue
            caminho = os.path.join(pasta, nome + ".png")
            if not os.path.exists(caminho):
                raise FileNotFoundError(f"parte '{nome}.png' nao existe em {pasta}")
            im = Image.open(caminho).convert("RGBA")
            # metade do vão de cada lado: as duas vizinhas crescem uma em
            # direção à outra e a junta fecha. +1 cobre o arredondamento e a
            # borda macia que o resize da escala deixa.
            vao = float(self.vaos.get(nome, 0.0))
            if nome in FECHA_MESMO_SEM_MEDIDA and vao <= 0.5:
                vao = tipico
                print(f"[personagem] '{nome}' sem vao medido; usando o tipico "
                      f"({tipico:.1f}px) para fechar a junta")
            im, pivo = _fechar_vao(im, self.pivos[nome],
                                   int(round(vao / 2.0)) + 1 if vao > 0.5 else 0)
            # o tamanho ANTES de centralizar: _centralizar infla a peça até
            # um quadrado grande o bastante para qualquer rotação, então
            # `self.img[x].size` não serve de régua. A expressão facial mede
            # tudo em fração da altura do crânio e precisa da altura real.
            self.tam[nome] = im.size
            self.img[nome], self.piv[nome] = _centralizar(im, pivo)

        # --- o queixo existe mesmo? -----------------------------------
        self.boca = None            # (dx, dy, largura) relativos ao pivô do crânio
        if "mandibula" not in self.img or _e_fiapo(self.img["mandibula"]):
            self.rosto_articulado = False
            self.img.pop("mandibula", None)     # fiapo em cena é sujeira solta
            if "cranio" in self.img:
                tapado, caixa = _tapar_entalhe(self.img["cranio"])
                if caixa:
                    self.img["cranio"] = tapado
                    px, py = self.piv["cranio"]
                    bx0, by0, bx1, by1 = caixa
                    # a boca fica onde o desenhista pôs o entalhe: mesma
                    # largura, mesma altura de centro. Nada é chutado.
                    self.boca = ((bx0 + bx1) / 2.0 - px,
                                 (by0 + by1) / 2.0 - py,
                                 (bx1 - bx0) * 1.02)
                    print(f"[rosto] sem mandibula segmentada; entalhe tapado e "
                          f"boca DESENHADA no lugar dele "
                          f"({int(bx1 - bx0)}px de largura). Lipsync mantido, "
                          f"agora pela linha da boca")
                else:
                    print("[rosto] sem mandibula segmentada e sem entalhe "
                          "detectado; seguindo com a cara como veio")
        # feições que sobraram como fiapo saem de cena pelo mesmo motivo: em
        # repouso elas caem sobre o próprio desenho e somem, mas qualquer
        # movimento de expressão as descola e vira traço solto no rosto
        for f in ("olho_e", "olho_d", "sobrancelha_e", "sobrancelha_d", "nariz"):
            if f in self.img and _e_fiapo(self.img[f]):
                print(f"[rosto] '{f}' e um fiapo de contorno, nao uma feicao; "
                      f"ignorando")
                self.img.pop(f, None)

    def p(self, nome):
        return self.img[nome], self.piv[nome]

    def tem(self, nome):
        return nome in self.img

    def altura_cranio(self):
        """Régua do rosto, em pixels da ARTE (antes da escala de cena).

        Todo deslocamento de expressão é fração disto. Se a folha nova vier
        maior ou menor, a cara continua na mesma proporção sem ninguém
        reajustar constante nenhuma."""
        return float(self.tam.get("cranio", (1, 120))[1])

    def variar(self, nome, sx, sy):
        """A peça reescalada em x e y, com o pivô acompanhando.

        `colar` só sabe escala uniforme, e olho semicerrado é achatamento
        vertical puro -- é a diferença entre `bravo` e `bravo com os olhos
        do neutro`. Redimensionar a peça JÁ CENTRALIZADA mantém o pivô no
        centro do quadrado, então basta escalar a coordenada.

        Com cache: são dois olhos por frame e ~430 frames por vídeo, e a
        expressão muda pouco entre frames vizinhos. Arredondar a chave em
        2 casas colapsa quase tudo em meia dúzia de variantes."""
        sx, sy = round(float(sx), 2), round(float(sy), 2)
        if abs(sx - 1.0) < 0.02 and abs(sy - 1.0) < 0.02:
            return self.img[nome], self.piv[nome]
        chave = (nome, sx, sy)
        if chave not in self._cache_var:
            img, piv = self.img[nome], self.piv[nome]
            nl, na = max(2, int(img.width * sx)), max(2, int(img.height * sy))
            self._cache_var[chave] = (img.resize((nl, na), Image.LANCZOS),
                                      (piv[0] * sx, piv[1] * sy))
        return self._cache_var[chave]


def _tri(v):
    """Um membro pode vir com 2 ou 3 ângulos. Spec antigo manda 2 (ombro,
    cotovelo) porque não existia pulso; a terceira articulação entra
    zerada e nada quebra."""
    v = list(v) if isinstance(v, (list, tuple)) else [float(v)]
    return (v + [0.0, 0.0, 0.0])[:3]


ABERTURA_MAXILAR = 0.38     # fração da altura do queixo que a boca desce

# Peças que fecham a junta mesmo sem vão medido (ver Personagem.__init__)
FECHA_MESMO_SEM_MEDIDA = ("mandibula",)

# Interior da boca: o que se vê quando o maxilar desce. Cor de dentro de
# boca de desenho -- escura o bastante para ler como buraco, quente o
# bastante para não virar um retângulo preto no meio da cara.
COR_BOCA = (92, 42, 38, 255)


def _angulo(nome, rig, boca_nivel):
    """Ângulo ABSOLUTO de uma peça, em graus de tela.

    A tabela FONTE_ANGULO diz de onde cada peça tira o ângulo, então
    acrescentar uma peça nova ao esqueleto não exige tocar aqui."""
    fonte, i = FONTE_ANGULO.get(nome, ("tronco", 0))
    base = rig.get("tronco", -90.0) + 90.0
    if fonte == "tronco":
        return base
    if fonte in ("cabeca", "maxilar"):
        return base + rig.get("cabeca", 0.0)
    return sum(_tri(rig.get(fonte, [90.0, 0.0, 0.0]))[:i + 1]) - 90.0


def _girar(v, graus):
    r = math.radians(graus)
    return (v[0] * math.cos(r) - v[1] * math.sin(r),
            v[0] * math.sin(r) + v[1] * math.cos(r))



def _pivo_de_pega(img):
    """Onde a mão segura o objeto.

    Se a arte trouxer uma marca MAGENTA (o gerador é instruído a pintar um
    ponto magenta no cabo), o pivô é o centro dessa marca. Sem marca, cai no
    centro da metade de baixo do objeto -- que é onde fica o cabo de quase
    tudo que se segura (xícara, celular, martelo, placa).
    """
    a = np.asarray(img.convert("RGBA"), dtype=np.int16)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    marca = (al > 128) & (r > 180) & (b > 180) & (g < 110)
    if marca.any():
        ys, xs = np.nonzero(marca)
        return (float(xs.mean()), float(ys.mean()))
    return (img.width * 0.5, img.height * 0.72)


def desenhar_personagem(pers, rig, boca_nivel=0.0, piscando=False, objeto=None,
                        expr=None):
    """Monta o personagem numa CAMADA transparente do tamanho do quadro.

    O corpo é percorrido como ÁRVORE, do quadril para fora: a posição de
    cada peça sai da posição do pai mais o ponto de saída que o pai guarda
    para ela, girado pelo ângulo do pai. Não há mais medida cravada, não
    há mais `meio_ombro` nem `queda_ombro`, e acrescentar uma peça ao
    esqueleto não mexe em uma linha deste arquivo.

    Camada separada (e não direto no fundo) é o que permite espelhar o
    personagem inteiro, achatá-lo na virada, dar zoom e pôr DOIS
    personagens no mesmo quadro sem um apagar o outro."""
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    e = pers.escala

    # --- EXPRESSÃO FACIAL (ver expressao.py) --------------------------
    # Entra ANTES de propagar os ângulos porque `cabeca_rot` é giro de
    # cabeça de verdade: ele arrasta o crânio, o cabelo, os olhos, o nariz
    # e a mandíbula juntos, que é o que faz inclinar a cabeça ler como
    # emoção e não como peça solta torta.
    ex = dict(EXPR_ZERO)
    if expr:
        ex.update(expr)
        if abs(ex["cabeca_rot"]) > 0.01:
            rig = dict(rig)
            rig["cabeca"] = rig.get("cabeca", 0.0) + ex["cabeca_rot"]
    boca_nivel = max(float(boca_nivel), float(ex["boca_min"]))
    hc = pers.altura_cranio()          # régua do rosto, em pixels da arte

    # --- posição e ângulo de cada peça, do quadril para fora
    pos, ang = {}, {}
    raiz = next((n for n, p in ESQUELETO.items() if p is None), "abdomen")
    fila = [raiz]
    corr = getattr(pers, "corr", {})
    pos[raiz] = tuple(rig["quadril"])
    ang[raiz] = _angulo(raiz, rig, boca_nivel) + corr.get(raiz, 0.0)
    filhos = {}
    for n, pai in ESQUELETO.items():
        filhos.setdefault(pai, []).append(n)

    while fila:
        pai = fila.pop(0)
        for f in filhos.get(pai, []):
            if not pers.tem(f) or not pers.tem(pai):
                continue
            saida = (pers.saidas.get(pai) or {}).get(f)
            if saida is None:
                continue
            pv = pers.pivos[pai]
            d = _girar(((saida[0] - pv[0]) * e, (saida[1] - pv[1]) * e), ang[pai])
            pos[f] = (pos[pai][0] + d[0], pos[pai][1] + d[1])
            ang[f] = _angulo(f, rig, boca_nivel) + corr.get(f, 0.0)
            fila.append(f)

    # --- as feições se mexem DENTRO do rosto ---------------------------
    # Deslocamento no referencial da CABEÇA: se a cabeça está inclinada, a
    # sobrancelha sobe na direção da testa, não na vertical da tela. Sem
    # isto, cabeça de lado + sobrancelha erguida desmonta o rosto.
    ang_cabeca = ang.get("cranio", 0.0)
    var = {}                            # {peça: (escala_x, escala_y)}
    giro = {}                           # {peça: graus somados ao ângulo}

    def _mover(nome, dx, dy):
        if nome in pos and (abs(dx) > 1e-4 or abs(dy) > 1e-4):
            d = _girar((dx * hc * e, dy * hc * e), ang_cabeca)
            pos[nome] = (pos[nome][0] + d[0], pos[nome][1] + d[1])

    if abs(ex["sobrancelha_dy"]) > 1e-4:
        _mover("sobrancelha_e", 0.0, ex["sobrancelha_dy"])
        _mover("sobrancelha_d", 0.0, ex["sobrancelha_dy"])
    if abs(ex["sobrancelha_rot"]) > 0.01:
        # sinais opostos: o que importa é a ponta INTERNA das duas descer
        # (raiva) ou subir (tristeza). Simétrico é a única leitura que não
        # parece defeito de recorte.
        giro["sobrancelha_e"] = ex["sobrancelha_rot"]
        giro["sobrancelha_d"] = -ex["sobrancelha_rot"]
    if abs(ex["olho_dy"]) > 1e-4:
        _mover("olho_e", 0.0, ex["olho_dy"])
        _mover("olho_d", 0.0, ex["olho_dy"])
    if abs(ex["olho_sx"] - 1.0) > 0.02 or abs(ex["olho_sy"] - 1.0) > 0.02:
        var["olho_e"] = var["olho_d"] = (ex["olho_sx"], ex["olho_sy"])
    if abs(ex["mandibula_dx"]) > 1e-4:
        _mover("mandibula", ex["mandibula_dx"], 0.0)

    # A boca abre por QUEDA do queixo, não por rotação: de frente, girar a
    # mandíbula em torno de um ponto no meio do rosto torce o queixo para
    # um lado. Descer mantém a cara simétrica e é o que se lê como fala.
    repouso_mandibula = None
    if "mandibula" in pos and pers.tem("mandibula"):
        queda = boca_nivel * pers.img["mandibula"].size[1] * ABERTURA_MAXILAR * e * 0.5
        if queda > 1.0:
            repouso_mandibula = pos["mandibula"]
        pos["mandibula"] = (pos["mandibula"][0], pos["mandibula"][1] + queda)
        if "boca" in pos:
            pos["boca"] = (pos["boca"][0], pos["boca"][1] + queda)

    # --- desenho, de trás para frente
    for nome in ORDEM_Z:
        if nome not in pos or not pers.tem(nome):
            continue
        if piscando and nome in ("olho_e", "olho_d"):
            continue        # piscar = simplesmente não desenhar o olho

        # INTERIOR DA BOCA. O maxilar desce e deixa um buraco entre ele e o
        # crânio -- e por esse buraco aparecia o CENÁRIO, porque o entalhe
        # do crânio é vazado (é o vão que permitiu segmentar a folha).
        # Enche-se o buraco com a silhueta do próprio maxilar, tingida de
        # escuro, na posição de REPOUSO: assim o formato é exatamente o
        # certo, sem inventar geometria de boca nenhuma, e o que sobra
        # visível é só a faixa que o queixo desceu.
        if nome == "mandibula" and repouso_mandibula is not None:
            img, piv = pers.p(nome)
            dentro = Image.new("RGBA", img.size, COR_BOCA)
            dentro.putalpha(img.split()[3])
            colar(base, dentro, piv, repouso_mandibula, ang[nome], e)

        if nome in var:
            img, piv = pers.variar(nome, *var[nome])
        else:
            img, piv = pers.p(nome)
        colar(base, img, piv, pos[nome], ang[nome] + giro.get(nome, 0.0), e)

        # BOCA DESENHADA: logo depois do crânio, antes das feições, que é
        # onde a boca da arte estaria. Só existe quando a folha não trouxe
        # queixo articulado (ver Personagem.__init__).
        if nome == "cranio" and getattr(pers, "boca", None):
            bdx, bdy, blarg = pers.boca
            bimg, bpiv = _boca_desenhada(
                blarg * e, blarg * e * 0.55, boca_nivel,
                ex["boca_curva"], _cor_da_casca(pers.img["cranio"]))
            d = _girar((bdx * e, bdy * e), ang[nome])
            colar(base, bimg, bpiv,
                  (pos[nome][0] + d[0], pos[nome][1] + d[1]), ang[nome])

        # objeto: entra logo depois da mão que o segura, para ficar na
        # frente dela. É o osso da mão que tornou isto possível.
        if objeto and objeto.get("img") is not None and nome == "mao_" + objeto.get("mao", "e"):
            oi = objeto["img"]
            opv = objeto.get("pivo") or _pivo_de_pega(oi)
            oi, opv = _centralizar(oi, opv)
            colar(base, oi, opv, pos[nome], ang[nome],
                  float(objeto.get("escala", 1.0)))

    return base


# compatibilidade: quem chamava desenhar() e recebia RGB continua funcionando
def desenhar(pers, rig, fundo, boca_nivel=0.0, piscando=False):
    camada = desenhar_personagem(pers, rig, boca_nivel, piscando)
    quadro = fundo.copy().convert("RGBA")
    quadro.alpha_composite(camada)
    return quadro.convert("RGB")


# =====================================================================
# CÂMERA — fundo que anda, personagem que vira, zoom
# =====================================================================
class Cenario:
    """Um fundo que pode correr para os lados sem fim e sem emenda.

    O truque é ladrilhar a imagem com uma cópia ESPELHADA ao lado: a
    borda direita do original encosta na borda direita da cópia, então
    os pixels casam exatamente e não existe a linha vertical que denuncia
    um fundo repetido. O ladrilho tem 2W de largura e o deslocamento é
    tomado módulo 2W -- deslocamento infinito com duas imagens.

    O enquadramento é COBRIR, não esticar. O gerador de imagem em uso (o
    endpoint gratuito da Cloudflare) aceita só prompt e steps: não tem
    largura nem altura, e devolve sempre 1024x1024. Esticar um quadrado
    para 9:16 deforma tudo -- prédio vira torre, sofá vira pilar. Cobrir
    mantém a proporção e corta o excesso, que num cenário (feito de
    propósito com o centro vazio) é a parte que menos importa."""

    def __init__(self, img):
        base = img.convert("RGB")
        k = max(W / base.width, H / base.height)
        nl, na = max(int(base.width * k), W), max(int(base.height * k), H)
        base = base.resize((nl, na), Image.LANCZOS)
        # o chão fica na parte de baixo do cenário: cortar pelo centro
        # jogaria a linha do chão para fora do quadro
        cx = (nl - W) // 2
        base = base.crop((cx, na - H, cx + W, na))
        self.tile = Image.new("RGB", (2 * W, H))
        self.tile.paste(base, (0, 0))
        self.tile.paste(base.transpose(Image.FLIP_LEFT_RIGHT), (W, 0))

    def quadro(self, dx):
        x = int(dx) % (2 * W)
        out = Image.new("RGB", (W, H))
        primeiro = min(W, 2 * W - x)
        out.paste(self.tile.crop((x, 0, x + primeiro, H)), (0, 0))
        if primeiro < W:
            out.paste(self.tile.crop((0, 0, W - primeiro, H)), (primeiro, 0))
        return out


def _sombra_de_contato(quadro, camada, chao_y):
    """Elipse escura no chão, sob o personagem.

    Sem ela o personagem é um recorte POUSADO no cenário, não alguém DENTRO
    dele -- foi a primeira coisa que saltou quando o fundo deixou de ser
    cor chapada e virou uma rua. Uma sombra de contato é o sinal mais
    barato de que os pés tocam o chão.

    O ponto de apoio é a LINHA DO CHÃO da cena, não a base da figura: presa
    aos pés, a sombra subiria junto no pulo -- e sombra que voa denuncia
    mais do que sombra nenhuma. Ela encolhe e clareia conforme a figura se
    afasta do chão, que é o que dá a leitura de altura."""
    bb = camada.getbbox()
    if not bb:
        return
    x0, _, x1, y1 = bb
    voo = max(0.0, chao_y - y1)
    if voo > H * 0.30:
        return                          # alto demais: já não há contato a sugerir
    k = 1.0 - min(1.0, voo / (H * 0.30))
    larg = (x1 - x0) * (0.42 + 0.22 * k)
    alt = max(6.0, larg * 0.15)
    cx = (x0 + x1) / 2.0
    tinta = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(tinta).ellipse(
        [cx - larg / 2, chao_y - alt / 2, cx + larg / 2, chao_y + alt / 2],
        fill=(30, 26, 22, int(96 * (0.45 + 0.55 * k))))
    tinta = tinta.filter(ImageFilter.GaussianBlur(max(2, int(alt * 0.35))))
    quadro.alpha_composite(tinta)


def montar_frame(camada, cenario, cam, quadril_x=W / 2):
    """Junta personagem + cenário aplicando o que a câmera pediu."""
    if cam.get("espelhar"):
        # espelhar em torno do PRÓPRIO personagem, não do centro da tela:
        # espelhar a tela inteira teleportaria o corpo para o outro lado
        esp = camada.transpose(Image.FLIP_LEFT_RIGHT)
        nova = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        nova.alpha_composite(esp, (int(2 * quadril_x - W), 0))
        camada = nova

    achatar = float(cam.get("achatar", 1.0))
    if achatar < 0.995:
        larg = max(2, int(W * max(achatar, 0.04)))
        red = camada.resize((larg, H), Image.LANCZOS)
        nova = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        nova.alpha_composite(red, (int(quadril_x - larg * quadril_x / W), 0))
        camada = nova

    # SQUASH & STRETCH: escala vertical em torno do CHÃO. Em torno do
    # centro, o personagem afundaria no piso ao achatar; ancorado no pé,
    # ele achata como um corpo com peso.
    esc_y = float(cam.get("escala_y", 1.0))
    if abs(esc_y - 1.0) > 0.004:
        bb = camada.getbbox()
        if bb:
            chao = bb[3]
            alt = max(int(H * esc_y), 2)
            red = camada.resize((W, alt), Image.LANCZOS)
            nova = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            nova.alpha_composite(red, (0, int(chao - chao * esc_y)))
            camada = nova

    quadro = cenario.quadro(cam.get("fundo_dx", 0.0)).convert("RGBA")
    if cam.get("chao_y"):
        _sombra_de_contato(quadro, camada, float(cam["chao_y"]))
    quadro.alpha_composite(camada)
    quadro = quadro.convert("RGB")

    z = float(cam.get("zoom", 1.0))
    if abs(z - 1.0) > 0.002:
        lw, lh = W / z, H / z
        cx, cy = W * 0.5, H * float(cam.get("zoom_y", 0.5))
        x0 = min(max(cx - lw / 2, 0), W - lw)
        y0 = min(max(cy - lh / 2, 0), H - lh)
        quadro = quadro.crop((int(x0), int(y0), int(x0 + lw), int(y0 + lh))
                             ).resize((W, H), Image.LANCZOS)
    return quadro


# =====================================================================
def _rig_do_trecho(tr, t, pan_base, acoes_do_ator, x_base):
    """Ângulos do frame de UM ator. Dois caminhos:

    AÇÕES (novo)  -- verbos com janela, somados por cima do repouso.
    POSE (velho)  -- interpolação entre duas poses estáticas. Fica só
                     para não quebrar spec antigo; não produz caminhada.
    """
    rig = merge(REST, EXPRESSOES.get(tr.get("expressao", "neutro"), {}))
    rig["quadril"] = [x_base, REST["quadril"][1]]

    if acoes_do_ator:
        lista = [{"nome": "parado", "de": 0.0, "ate": 1.0}] + list(acoes_do_ator)
        cam = ACOES.aplicar(lista, t, rig, tr["dur"])
    elif tr.get("acoes"):
        cam = ACOES.aplicar([{"nome": "parado", "de": 0.0, "ate": 1.0}], t, rig, tr["dur"])
    else:
        p1 = merge(REST, POSES.get(tr.get("pose", "parado_falando"), {}),
                   EXPRESSOES.get(tr.get("expressao", "neutro"), {}))
        p2 = merge(REST, POSES.get(tr.get("pose_saida", tr.get("pose", "parado_falando")), {}),
                   EXPRESSOES.get(tr.get("expressao", "neutro"), {}))
        s = t * t * (3 - 2 * t)
        rig = blend(p1, p2, s)
        rig["quadril"] = [x_base, rig["quadril"][1] + math.sin(t * 40) * 6]
        cam = dict(ACOES.CAM_NEUTRA)

    cam["fundo_dx"] = pan_base + cam.get("fundo_dx", 0.0)
    return rig, cam


def _carregar_elenco(spec, pasta_padrao):
    """{chave: (Personagem, x_base)}.

    Um personagem só continua sendo o caso normal: sem `elenco` no spec,
    monta um elenco de um. Assim nada do que já roda precisa saber que
    existe elenco."""
    elenco = spec.get("elenco")
    if not elenco:
        return {"_": (Personagem(pasta_padrao), W / 2)}
    fora = {}
    n = len(elenco)
    for i, (chave, cfg) in enumerate(elenco.items()):
        cfg = cfg if isinstance(cfg, dict) else {"pasta": cfg}
        pasta = cfg.get("pasta") or os.path.join(pasta_padrao, "..", chave)
        # posições padrão bem separadas: duas pessoas no mesmo x viram uma
        # pessoa só com quatro braços
        padrao = W * (0.5 if n == 1 else 0.26 + 0.48 * i / max(n - 1, 1))
        p = Personagem(pasta)
        # Com mais de um personagem em cena, cada um encolhe: dois bonecos
        # na altura de protagonista não cabem lado a lado num quadro 9:16
        # sem se atravessarem. O recuo também dá a leitura de "plano
        # aberto, dois na cena" em vez de "close que deu errado".
        p.escala *= float(cfg.get("escala", 1.0 if n == 1 else 0.78))
        fora[chave] = (p, float(cfg.get("x", padrao)))
    return fora


def _pastas(spec, pasta_partes, chave_spec, padroes):
    """Onde procurar arte que não é do personagem (cenário, objeto).

    Ordem: o que o spec mandar, depois as pastas ao lado da pasta de
    peças. Aceita singular e plural de propósito -- o bucket guarda em
    `assets/cenario/` e `assets/objeto/`, e o motor sempre procurou por
    `cenarios/` e `objetos/`. A divergência nunca apareceu porque NADA
    baixava esses arquivos: o cut-out caía direto na cor chapada e o
    defeito passou por "cenário ainda não existe"."""
    fora = [p for p in [spec.get(chave_spec)] if p]
    fora += [os.path.join(pasta_partes, "..", p) for p in padroes]
    return fora


def _achar_arte(pastas, nome, exts=(".png", ".jpg", ".jpeg", ".webp")):
    """Primeiro arquivo que existir, em qualquer das extensões.

    Cenário chega como JPG (o bruto do gerador) ou PNG; procurar só por
    .png fazia o motor não achar justamente o que presta -- a versão que
    passou pelo rembg volta lavada, porque rembg é segmentador de objeto
    saliente e um cenário não tem objeto saliente nenhum."""
    for p in pastas:
        for e in exts:
            caminho = os.path.join(p, nome + e)
            if os.path.exists(caminho):
                return caminho
    return None


def _acoes_por_ator(tr, chaves, falante):
    """Distribui as ações do trecho entre os atores.

    Ação sem dono é do FALANTE -- é o caso comum e mantém o spec curto.
    O outro ator em cena só se mexe se o roteirista disser o que ele faz,
    e é isso que se quer: figurante que gesticula sozinho rouba a cena."""
    por = {c: [] for c in chaves}
    for a in tr.get("acoes") or []:
        dono = a.get("ator") or falante
        if dono in por:
            por[dono].append(a)
    return por


def render(pasta_partes, spec, saida, tmpdir=None):
    from palito_v5 import sintetizar, envelope, juntar_com_respiro
    tmp = tmpdir or tempfile.mkdtemp()
    fd = os.path.join(tmp, "frames"); os.makedirs(fd, exist_ok=True)

    elenco = _carregar_elenco(spec, pasta_partes)
    chaves = list(elenco)
    padrao_ator = chaves[0]

    pastas_objeto = _pastas(spec, pasta_partes, "pasta_objetos", ("objetos", "objeto"))

    # OBJETOS: PNG solto que gruda na mão de alguém. Carregados uma vez.
    objetos = {}
    for nome, caminho in (spec.get("objetos") or {}).items():
        if not os.path.isabs(caminho):
            # o spec pode dar o nome da arte ("celular") ou o arquivo
            # ("celular.png"); os dois têm que achar o mesmo PNG
            base = caminho.rsplit(".", 1)[0] if "." in caminho else caminho
            caminho = _achar_arte(pastas_objeto, base) or caminho
        if not os.path.exists(caminho):
            print(f"[objeto] {nome}: nao achei '{caminho}', seguindo sem ele")
            continue
        im = Image.open(caminho).convert("RGBA")
        # NORMALIZA O TAMANHO. O gerador devolve o objeto ocupando a
        # imagem inteira, seja um celular ou um caminhão, então usar a arte
        # como veio põe um celular de dois metros na mão do personagem --
        # foi o que aconteceu no primeiro teste. O tamanho vira fração da
        # altura do ator, que é a única referência de escala que existe na
        # cena. `escala_objeto` na ação ajusta a partir daí.
        bb = im.getbbox()
        if bb:
            im = im.crop(bb)
        alvo = ALTURA_ALVO_PX * 0.16
        k = alvo / max(im.height, 1)
        im = im.resize((max(int(im.width * k), 1), max(int(im.height * k), 1)),
                       Image.LANCZOS)
        objetos[nome] = im

    # nenhum vídeo abre sem gatilho -- rede de segurança no motor
    ACOES.garantir_gancho(spec)

    # VOZ PRIMEIRO: a duração real vira a timeline (igual ao palito_v5)
    faixas, respiros, marcas_por_trecho, total = [], [], [], 0.0
    for i, tr in enumerate(spec["trechos"]):
        wav = os.path.join(tmp, f"v{i:02d}.wav")
        perfil = tr.get("perfil_voz") or tr.get("ator") or "narrador"
        cfg = spec.get("vozes", {}).get(perfil, {})
        # as MARCAS de palavra deixam de ser descartadas: sao elas que dao
        # o tempo exato de cada palavra para a legenda (ver legendas.py)
        marcas, dur = sintetizar(tr["fala"], cfg, wav,
                                 spec.get("modo_tts", os.environ.get("MODO_TTS", "real")))
        respiro = float(tr.get("respiro_s", 0.45))
        tr["dur"] = dur + respiro
        tr["_inicio_s"] = total          # tempo global em que este trecho começa
        tr["_dur_voz"] = dur             # sem o respiro: é o que tem som
        faixas.append(wav); respiros.append(respiro)
        marcas_por_trecho.append(marcas or [])
        total += tr["dur"]
    print(f"[voz] timeline real: {total:.2f}s")

    # o respiro entra no áudio como silêncio de verdade. Sem isto o
    # -shortest do fim decepava a cauda de cada trecho -- o vídeo saía
    # 1,35s mais curto do que o log dizia (ver juntar_com_respiro)
    voz = juntar_com_respiro(faixas, respiros, os.path.join(tmp, "voz.wav"), tmp)
    env = envelope(voz)

    # LEGENDA: opcional, mas ligada por padrão. Short se assiste no mudo.
    leg = None
    if spec.get("legenda", True):
        from legendas import Legenda
        leg = Legenda(W, H, tamanho=spec.get("legenda_px"),
                      por_bloco=spec.get("legenda_palavras", 3))
        for tr, m in zip(spec["trechos"], marcas_por_trecho):
            leg.adicionar(tr["fala"], m, tr["_inicio_s"], tr["_dur_voz"])
        print(f"[legenda] {len(leg.blocos)} blocos"
              + ("" if any(marcas_por_trecho) else " (sem WordBoundary: tempo repartido)"))

    # LINHA DO CHÃO: onde os pés do personagem pousam em repouso. Sai de um
    # frame de teste, uma vez por render -- é a única referência estável de
    # chão que existe, já que o cenário é arte e não traz cota nenhuma.
    chao_y = None
    try:
        pers0, x0_ = elenco[padrao_ator]
        rig0 = merge(REST, {})
        rig0["quadril"] = [x0_, REST["quadril"][1]]
        bb0 = desenhar_personagem(pers0, rig0).getbbox()
        chao_y = bb0[3] if bb0 else None
        print(f"[chao] linha do chao em y={chao_y}")
    except Exception as e:
        print(f"[chao] nao consegui medir ({e}); seguindo sem sombra de contato")

    pastas_cenario = _pastas(spec, pasta_partes, "pasta_cenarios", ("cenarios", "cenario"))
    cenarios = {}
    # A CARA. Um Rosto por render: ele guarda com que expressão cada ator
    # terminou o trecho para o seguinte começar dali, em vez de pular de
    # cara entre trechos (ver expressao.Rosto).
    rosto = EXPR.Rosto(spec)
    caras = []
    n = 0
    pan = 0.0            # o quanto o fundo já andou; NÃO zera entre trechos
    for tr in spec["trechos"]:
        cen = tr.get("cenario", "sala")
        if cen not in cenarios:
            cam_path = _achar_arte(pastas_cenario, cen)
            if cam_path:
                print(f"[cenario] {cen}: {cam_path}")
                img = Image.open(cam_path)
            else:
                # fundo chapado é o ÚLTIMO recurso, e agora ele avisa. Foi
                # esta cor saindo calada que fez o cenário faltante passar
                # por "cenário ainda não existe" durante duas sessões.
                print(f"[cenario] {cen}: nao achei arte em "
                      f"{[os.path.normpath(p) for p in pastas_cenario]}; cor chapada")
                img = Image.new("RGB", (W, H), "#A5A893")
            cenarios[cen] = Cenario(img)
        falante = tr.get("ator") if tr.get("ator") in elenco else padrao_ator
        por_ator = _acoes_por_ator(tr, chaves, falante)
        nf = max(1, int(tr["dur"] * FPS))
        cam = dict(ACOES.CAM_NEUTRA)
        for f in range(nf):
            fh = (f // 2) * 2                       # animar "em 2s"
            t = fh / max(1, nf - 1)
            nivel = env[n] if n < len(env) else 0.0

            camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            cam_falante, x_falante = dict(ACOES.CAM_NEUTRA), W / 2
            for chave in chaves:
                pers, x0 = elenco[chave]
                rig, c = _rig_do_trecho(tr, t, pan, por_ator[chave], x0)
                # a cara de QUEM FALA vem do trecho; quem ouve fica na cara
                # de reação que o roteirista der a ele, ou neutro
                cara = rosto.para(tr, t, tr["dur"], chave) if chave == falante \
                    else EXPR.obter(tr.get("expressao_" + chave, "neutro"))
                pisca = EXPR.piscando(n, FPS, semente=chaves.index(chave),
                                      expr_nome=tr.get("expressao", "neutro")
                                      if chave == falante else "neutro")
                # SÓ QUEM FALA MEXE A BOCA. Sem isto os dois abrem o
                # maxilar na mesma envoltória e ninguém sabe quem falou.
                obj = None
                for a in por_ator[chave]:
                    if a.get("objeto") in objetos and float(a.get("de", 0)) <= t <= float(a.get("ate", 1)):
                        obj = {"img": objetos[a["objeto"]], "mao": a.get("mao", "d"),
                               "escala": a.get("escala_objeto", 1.0)}
                camada.alpha_composite(
                    desenhar_personagem(pers, rig, nivel if chave == falante else 0.0,
                                        pisca, obj, cara))
                if chave == falante:
                    cam_falante, x_falante = c, rig["quadril"][0]
            cam = cam_falante
            if chao_y:
                cam["chao_y"] = chao_y
            quadro = montar_frame(camada, cenarios[cen], cam, x_falante)
            if leg is not None:
                # por cima de tudo, e no tempo GLOBAL: o índice do frame é
                # contínuo entre trechos, então n/FPS é o relógio do vídeo
                leg.desenhar(quadro, n / float(FPS))
            quadro.save(os.path.join(fd, f"{n:05d}.png"))
            n += 1
        for chave in chaves:
            rosto.fechar(chave)
        caras.append(EXPR.normalizar(tr.get("expressao", "neutro"))
                     + "".join("+" + EXPR.normalizar(j.get("nome") or j.get("valor"))
                               for j in (tr.get("expressoes") or [])))
        pan = cam.get("fundo_dx", pan)              # continua de onde parou
    print(f"[cutout] {n} frames ({n/FPS:.1f}s)")
    print(f"[cara] {' -> '.join(caras)}")

    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
                    "-i", os.path.join(fd, "%05d.png"), "-i", voz,
                    "-af", spec.get("loudnorm", "loudnorm=I=-9:LRA=8:TP=-1.5"),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "21",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", saida], check=True)
    # Duração devolvida = a do VÍDEO que saiu, não a soma planejada. Com o
    # respiro no áudio as duas praticamente coincidem, mas `int(dur*FPS)`
    # arredonda para baixo em cada trecho, e é a guarda de duração do
    # job.py que consome este número -- ela precisa validar o arquivo, não
    # a intenção.
    return saida, round(n / float(FPS), 2)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--partes", required=True, help="pasta com os PNG e partes.json")
    ap.add_argument("--spec", help="spec.json; usa o exemplo do v5 se omitido")
    ap.add_argument("-o", "--saida", default="/tmp/cutout.mp4")
    a = ap.parse_args()
    if a.spec:
        spec = json.load(open(a.spec, encoding="utf-8"))
    else:
        from palito_v5 import SPEC_EXEMPLO
        spec = dict(SPEC_EXEMPLO)
    out, dur = render(a.partes, spec, a.saida)
    print(f"[ok] {out}  {dur}s")
