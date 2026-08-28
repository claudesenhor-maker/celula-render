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
import cenarios as CENARIOS
import sfx as SFX
from folha_personagem import (ESQUELETO, ORDEM_Z, FONTE_ANGULO,
                              CORRECAO_POSE_T, SEGUE)

# repouso da cara: o dicionário completo com todo campo em zero, para que
# desenhar_personagem nunca precise checar chave faltando
EXPR_ZERO = EXPR.CATALOGO["neutro"]

W, H, FPS = 1080, 1920, 24

# altura de referencia do personagem no quadro; objetos sao medidos contra ela
ALTURA_ALVO_PX = 1150

# quantos personagens cabem no quadro ao mesmo tempo. Dois é o teto do
# formato: no 9:16 o terceiro só entra encolhendo todo mundo até a cara
# sumir, e cara é onde a piada acontece.
MAX_EM_CENA = 2


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


def _analisar_rosto(img):
    """Onde está o ROSTO dentro da peça do crânio, medido pelos OLHOS.

    POR QUE (a boca da Maya saiu no pescoço, 27/08)
        Até aqui as três funções de rosto (`_tapar_entalhe`,
        `_tapar_boca_desenhada`, `_extrair_feicoes`) usavam a caixa da PEÇA
        como régua: a boca era "o traço deitado entre 52% e 92% da altura
        da peça", a feição era "o que está na metade de cima". Isso vale
        enquanto a peça do crânio for o rosto e mais nada.

        Ela não é. Na Maya o crânio traz cabelo comprido até abaixo do
        queixo E o pescoço inteiro: 62% da altura da peça cai na altura do
        NARIZ, e o terço de baixo é pescoço e gola. `_tapar_entalhe` achou
        ali o vazio entre as duas mechas de cabelo, tomou-o por entalhe de
        boca e pôs a boca animada no pescoço dela -- com a boca desenhada
        continuando parada no rosto, porque ninguém foi procurá-la.

        No Zeca o mesmo erro de régua produziu outro sintoma: as
        sobrancelhas grisalhas têm pixel claro e pixel escuro na mesma
        mancha, que era a definição de OLHO, e passaram a ser animadas como
        olhos -- o piscar desenhava um traço na testa. Os olhos de verdade
        estão fundidos ao aro do óculos numa mancha que atravessa a cara, e
        eram descartados por tamanho.

        A régua certa não é fração de peça nenhuma: é o par de OLHOS. Todo
        rosto frontal tem dois, simétricos, e a distância entre eles é a
        única medida que dá a escala do rosto sem depender de cabelo, de
        pescoço ou de quanto da figura o desenhista pôs na peça. Com ela,
        boca e sobrancelha se procuram onde elas ficam num rosto -- e não
        onde ficariam se a peça fosse só a cara.

    COMO se acham os olhos sem limiar inventado
        Pela ESCLERA: em arte cut-out o branco do olho é o ponto mais claro
        do rosto, mais claro que a pele por construção (é o que faz a pupila
        ler como pupila). Manchas claras dentro do núcleo, pareadas por
        SIMETRIA em torno do eixo da peça -- mesma altura, mesma área,
        distâncias iguais ao eixo. Cabelo grisalho não é mais claro que a
        pele e não forma par simétrico com nada; sobrancelha não tem branco.

        O olho inteiro é o componente de tinta que CONTÉM a esclera (a
        esclera, a pupila e o traço em volta saem como uma mancha só). Se
        esse componente for grande demais para ser um olho -- o caso do
        óculos do Zeca --, o olho é a esclera dilatada: recorta-se o globo
        de dentro do aro, que continua desenhado no crânio. É o que um
        animador faria com a mesma arte.

    Devolve None quando não há par de olhos (e aí cada função cai na régua
    antiga, que é o comportamento de antes desta correção). Senão, um dict
    com as máscaras já calculadas -- `pele`, `tinta`, `nucleo`, `lum` -- e a
    geometria do rosto: `eixo`, `linha_olhos`, `d_olhos`, `queixo`, e
    `olhos` com a máscara e a caixa de cada um.
    """
    from segmentar import _componentes
    a = np.asarray(img.convert("RGBA"))
    alfa = a[..., 3]
    dentro = alfa > 128
    if dentro.sum() < 400:
        return None
    ys, xs = np.nonzero(dentro)
    x0, x1 = float(xs.min()), float(xs.max())
    y0, y1 = float(ys.min()), float(ys.max())
    larg_p, alt_p = x1 - x0 + 1, y1 - y0 + 1

    # o raio de erosão sai do tamanho do desenho, não da tela: `_centralizar`
    # infla a peça até um quadrado que caiba qualquer rotação
    r = max(3, int(min(larg_p, alt_p) * 0.045))
    nucleo = np.asarray(img.split()[3].filter(ImageFilter.MinFilter(2 * r + 1))) > 128
    if nucleo.sum() < 200:
        return None

    rgb = a[..., :3].astype(np.int16)
    q = (rgb[nucleo] // 24)
    chaves, contas = np.unique(q.reshape(-1, 3), axis=0, return_counts=True)
    pele = chaves[contas.argmax()].astype(np.int16) * 24 + 12
    tinta = nucleo & (np.abs(rgb - pele).sum(axis=2) > 90)
    if tinta.sum() < 40:
        return None
    lum = rgb.sum(axis=2)

    # --- a esclera: o branco do olho -------------------------------------
    # O limiar fica no MEIO DO CAMINHO entre a pele e o branco puro, e nunca
    # abaixo de 690. Cravar 620 (a versão anterior) deixava passar o cabelo
    # grisalho do Zeca, que tem 600 de luminância contra 612 da pele; exigir
    # branco puro perderia a esclera de qualquer folha com sombreado.
    lum_pele = float(pele.sum())
    lim_claro = max(690.0, (lum_pele + 765.0) / 2.0)
    claro = nucleo & (lum > lim_claro)
    area_min = max(15, int(nucleo.sum() * 0.0015))
    escleras = _componentes(claro, area_min=area_min)
    if len(escleras) < 2:
        return None

    eixo_peca = (x0 + x1) / 2.0
    melhor, nota_melhor = None, 0.0
    for i in range(len(escleras)):
        for j in range(i + 1, len(escleras)):
            e, d = sorted((escleras[i], escleras[j]), key=lambda c: c["cx"])
            dist = d["cx"] - e["cx"]
            if dist < larg_p * 0.12 or dist > larg_p * 0.95:
                continue
            if abs(e["cy"] - d["cy"]) > dist * 0.30:
                continue          # olhos ficam na mesma linha
            meio = (e["cx"] + d["cx"]) / 2.0
            if abs(meio - eixo_peca) > larg_p * 0.16:
                continue          # o par tem que abraçar o eixo do desenho
            razao = min(e["area"], d["area"]) / float(max(e["area"], d["area"]))
            if razao < 0.45:
                continue          # dois olhos do mesmo rosto têm o mesmo tamanho
            nota = (e["area"] + d["area"]) * razao
            if nota > nota_melhor:
                melhor, nota_melhor = (e, d), nota
    if melhor is None:
        return None
    esc_e, esc_d = melhor

    # --- o olho inteiro em volta da esclera -------------------------------
    comps_tinta = _componentes(tinta, area_min=max(20, int(tinta.sum() * 0.005)))
    olhos = {}
    for chave, esc in (("olho_e", esc_e), ("olho_d", esc_d)):
        bx0, by0, bx1, by1 = esc["bbox"]
        lw, lh = bx1 - bx0 + 1, by1 - by0 + 1
        m = None
        for c in comps_tinta:
            if not (c["mask"] & esc["mask"]).any():
                continue
            cw = c["bbox"][2] - c["bbox"][0] + 1
            ch = c["bbox"][3] - c["bbox"][1] + 1
            # o componente que contém a esclera só é o olho se tiver tamanho
            # de olho; o aro do óculos atravessa o rosto e reprova aqui
            if cw <= max(lw * 3.0, larg_p * 0.30) and ch <= max(lh * 3.5, larg_p * 0.30):
                m = c["mask"].copy()
            break
        if m is None:
            # sem componente aproveitável, o olho é a própria esclera com uma
            # folga: o globo sai de dentro do aro e o aro fica no crânio
            g = max(2, int(min(lw, lh) * 0.30))
            m = np.asarray(Image.fromarray((esc["mask"] * 255).astype(np.uint8))
                           .filter(ImageFilter.MaxFilter(2 * g + 1))) > 8
            m &= nucleo
        ys_m, xs_m = np.nonzero(m)
        olhos[chave] = {
            "mask": m, "area": int(m.sum()),
            "bbox": (int(xs_m.min()), int(ys_m.min()), int(xs_m.max()), int(ys_m.max())),
            "cx": float(xs_m.mean()), "cy": float(ys_m.mean()),
        }

    eixo = (olhos["olho_e"]["cx"] + olhos["olho_d"]["cx"]) / 2.0
    linha = (olhos["olho_e"]["cy"] + olhos["olho_d"]["cy"]) / 2.0
    d_olhos = olhos["olho_d"]["cx"] - olhos["olho_e"]["cx"]

    # --- até onde desce o rosto -------------------------------------------
    # O queixo é onde a mancha de pele ESTRANGULA: abaixo dele vem o pescoço,
    # que é mais estreito por definição de pescoço. Medir isso é o que impede
    # a boca de ser procurada no colo -- e sai da arte, sem proporção
    # inventada. Quando o desenhista fecha o queixo com traço, a mancha já
    # termina ali e a medida concorda.
    pele_m = nucleo & ~tinta
    comp_rosto = None
    faixa_olhos = pele_m[int(round(linha))] if 0 <= linha < pele_m.shape[0] else None
    for c in _componentes(pele_m, area_min=max(100, int(nucleo.sum() * 0.02))):
        if faixa_olhos is not None and c["mask"][int(round(linha)),
                                                int(round(eixo))]:
            comp_rosto = c
            break
        if comp_rosto is None or c["area"] > comp_rosto["area"]:
            comp_rosto = c
    queixo = y1
    if comp_rosto is not None:
        larguras = comp_rosto["mask"].sum(axis=1).astype(float)
        i0, i1 = int(round(linha)), int(round(linha + d_olhos * 0.6))
        i1 = min(i1, len(larguras) - 1)
        ref = float(np.median(larguras[i0:i1 + 1])) if i1 > i0 else larguras[i0]
        queixo = float(comp_rosto["bbox"][3])
        if ref > 0:
            for y in range(i1 + 1, len(larguras)):
                if larguras[y] < ref * 0.5:
                    queixo = float(y)
                    break
    return {
        "alfa": alfa, "rgb": rgb, "lum": lum, "nucleo": nucleo,
        "tinta": tinta, "pele": pele, "comps_tinta": comps_tinta,
        "peca": (x0, y0, x1, y1), "larg_peca": larg_p, "alt_peca": alt_p,
        "eixo": eixo, "linha_olhos": linha, "d_olhos": d_olhos,
        "queixo": queixo, "olhos": olhos,
    }


def _faixa_da_boca(rosto):
    """Onde a boca pode estar: (y_min, y_max, eixo, tolerância em x).

    Num rosto a boca fica entre o nariz e o queixo, no eixo. Com o par de
    olhos medido, isso deixa de ser fração da peça e passa a ser fração da
    distância entre os olhos -- a régua do próprio rosto. Medida nas três
    folhas de produção, a boca cai a 0,77, 0,78 e 0,81 distância interocular
    abaixo da linha dos olhos: é a proporção mais estável do rosto, e a
    faixa de 0,45 a 1,35 a cobre com folga em qualquer estilo de desenho.

    O QUEIXO MEDIDO só entra como teto quando é plausível. Ele vem do
    estrangulamento da mancha de pele, e essa mancha pode terminar na
    própria linha da boca quando o desenhista a fecha de lado a lado -- foi
    o que aconteceu com o bigode do Zeca, e usar aquele queixo como teto
    apagava a boca da lista de candidatas. Abaixo de uma distância
    interocular do olho não existe queixo de rosto nenhum."""
    d = rosto["d_olhos"]
    linha = rosto["linha_olhos"]
    y_min = linha + d * 0.45
    y_max = linha + d * 1.35
    if rosto["queixo"] > linha + d * 1.0:
        y_max = min(y_max, rosto["queixo"])
    return y_min, y_max, rosto["eixo"], d * 0.55


def _tapar_entalhe(img, cor=None, rosto=None):
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
    todos = _componentes(arr, area_min=max(int(arr.sum() * 0.05), 40))
    if rosto:
        # COM OS OLHOS MEDIDOS a faixa é a do rosto, não a da peça. É o que
        # impede o vazio entre as mechas de cabelo da Maya -- que fica no
        # pescoço, dois terços abaixo dos olhos dela -- de ser lido como
        # entalhe de boca.
        ymin, ymax, eixo, tol = _faixa_da_boca(rosto)
        cands = [c for c in todos if ymin <= c["cy"] <= ymax
                 and abs(c["cx"] - eixo) < tol]
    else:
        cands = [c for c in todos
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
    # E NUNCA COME O CONTORNO EXTERNO. O entalhe da boca desce até a base do
    # queixo, e a tapa levava junto o traço preto de lá: o rosto ficava com
    # o queixo aberto, sem linha, como se a cabeça vazasse para o pescoço.
    # Erodir o alfa pela espessura do traço deixa o anel de contorno fora do
    # alcance da tapa.
    # Erode-se a SILHUETA FECHADA, não o alfa: o entalhe é um vazio, e
    # erodir o alfa protegeria justamente a borda dele -- que é o que a
    # tapa precisa cobrir. O fechamento já não tem o entalhe, então o que
    # sobra protegido é só o perímetro de fora.
    esp_traco = max(2, int(min(img.width, img.height) * 0.022))
    larga = ImageChops.multiply(
        larga, fechado.filter(ImageFilter.MinFilter(2 * esp_traco + 1)))

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

    # SOMBREADO, E NÃO COR CHAPADA. Uma cor só deixa um retângulo mais claro
    # no queixo -- ele aparece em todos os frames do vídeo de 28/08, e foi a
    # segunda queixa sobre o rosto. O queixo do Pal escurece de cima para
    # baixo; a bochecha, de onde a cor é amostrada, não. Preencher cada
    # coluna interpolando entre o pixel logo ACIMA e o logo ABAIXO da tapa
    # reproduz o gradiente que a arte tem naquele ponto, em vez de inventar
    # um tom médio para a área inteira.
    # Coluna a coluna NÃO serve: o que está logo acima da tapa é ora pele,
    # ora o traço escuro do lábio, e a tapa sai listrada de vertical (foi a
    # primeira tentativa, conferida em 29/08). O gradiente é medido uma vez,
    # entre a MÉDIA da pele acima e a MÉDIA da pele abaixo do remendo, e
    # aplicado à área inteira.
    ys_m, _xs_m = np.nonzero(m)
    if len(ys_m):
        ya, yb = int(ys_m.min()), int(ys_m.max())
        # Amostrar o pixel ACIMA e o ABAIXO do remendo para montar o
        # gradiente foi tentado e sai pior: os dois vizinhos são o traço do
        # lábio e o contorno do queixo, e a tapa saiu cinza-esverdeada
        # (medido em 29/08: 200,184,159 contra os 220,204,184 da bochecha).
        # A bochecha é a única vizinhança que é pele de verdade -- então a
        # cor vem dela, e o sombreado é uma queda suave de 6% até a base,
        # que é o que um queixo faz e o que tira o aspecto de adesivo.
        n = max(1, yb - ya)
        k = ((np.arange(img.height) - ya) / float(n)).clip(0.0, 1.0)
        escala = (1.0 - 0.06 * k)[ys_m][:, None]
        a[m, :3] = (np.array(pele, dtype=np.float32)[None, :] * escala).astype(np.uint8)
    tapado = Image.fromarray(a)

    # borda macia: mesmo com a cor certa, a emenda dura entrega o remendo.
    # Dois pixels de desvanecimento bastam.
    # 5 é o ponto de equilíbrio medido em 28/08: com 2 a emenda aparecia como
    # borda dura; com 9 a tapa fica translúcida na borda e o traço preto do
    # entalhe reaparece por baixo dela.
    suave = Image.composite(tapado, img, larga.filter(ImageFilter.GaussianBlur(5)))
    return suave, caixa


def _boca_desenhada(larg, alt_max, nivel, curva, cor_traco, cor_dentro=None,
                    espessura=None):
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
    # espessura: a medida da linha que a arte tinha, quando existe. A
    # fração da largura é o palpite de quando não há arte de boca nenhuma.
    esp = max(2, int(espessura if espessura else larg * 0.065))
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


def _extrair_feicoes(img, piv, rosto=None):
    """Recorta olhos e sobrancelhas de DENTRO da peça do crânio.

    POR QUE (o defeito nº 3 da lista de 29/08: "adicionar expressões faciais")
        expressao.py existe desde 28/08 e o rosto continuou parado. A causa
        não estava nele: a folha do Pal não entrega olho nem sobrancelha
        como peça. O segmentador devolve `olho_e` com 11x21 px e
        `sobrancelha_d` com 59x15 -- fiapos do contorno --, o carregador os
        descarta com razão, e sobra um `cranio` de 215x210 com o rosto
        inteiro desenhado dentro. Ou seja: `sobrancelha_rot` e `olho_sy`
        eram aplicados a peças que não estavam em cena, e a única coisa que
        se mexia na cara era a inclinação da cabeça.

        Gerar uma folha nova com feições separadas é a solução de arte, e
        ela está em aberto desde 27/08 (§7.1 do HANDOFF) porque o gerador
        não desenha os vãos. Enquanto isso, as feições ESTÃO desenhadas --
        só que dentro de outra peça. Recortá-las de lá é a mesma manobra
        que a boca já usa: nada é inventado por código, só se move o que o
        desenhista entregou.

    COMO (reescrito em 27/08 -- ver `_analisar_rosto`)
        Os OLHOS já vêm medidos: `_analisar_rosto` os acha pela esclera e os
        valida por simetria, o que vale para qualquer folha. Aqui só se
        recorta o que ele apontou.

        A SOBRANCELHA é o par de manchas logo ACIMA dos olhos, uma de cada
        lado do eixo, mais larga que alta e do tamanho de um olho. A régua
        anterior -- "quase toda escura" -- era um limiar de cor e reprovava
        a sobrancelha loira da Maya (48% de pixel escuro contra os 55%
        exigidos) enquanto aprovava o cabelo grisalho do Zeca. Posição e
        tamanho relativos ao olho não dependem da cor que o desenhista
        escolheu.

        Sem par de olhos não se recorta nada: detecção errada aqui apaga
        metade do rosto, e o motor sabe seguir com a cara parada.

    Devolve (crânio com as feições apagadas, {nome: sprite}) ou (img, None).
    Cada sprite: {"img": RGBA recortado, "dx","dy": centro da feição
    relativo ao PIVÔ da peça, "larg","alt"}. Relativo ao pivô, e não ao
    centro da imagem, porque a peça do crânio ainda vai ser recomposta com
    o cabelo depois disto -- o centro muda, o pivô não.
    """
    from PIL import ImageChops
    if rosto is None:
        rosto = _analisar_rosto(img)
    if not rosto or not rosto.get("olhos"):
        return img, None
    a = np.asarray(img.convert("RGBA"))
    alfa = rosto["alfa"]
    nucleo, tinta, pele = rosto["nucleo"], rosto["tinta"], rosto["pele"]
    eixo, linha, d_olhos = rosto["eixo"], rosto["linha_olhos"], rosto["d_olhos"]

    def _reg(c):
        bx0, by0, bx1, by1 = c["bbox"]
        return {"c": c, "w": bx1 - bx0 + 1, "h": by1 - by0 + 1,
                "cx": (bx0 + bx1) / 2.0, "cy": (by0 + by1) / 2.0}

    achados = {"olho_e": _reg(rosto["olhos"]["olho_e"]),
               "olho_d": _reg(rosto["olhos"]["olho_d"])}

    # --- as sobrancelhas, medidas contra os olhos ------------------------
    larg_olho = max(achados["olho_e"]["w"], achados["olho_d"]["w"])
    for c in rosto["comps_tinta"]:
        reg = _reg(c)
        alvo = achados["olho_e"] if reg["cx"] < eixo else achados["olho_d"]
        nome = "sobrancelha_" + ("e" if reg["cx"] < eixo else "d")
        if (c["mask"] & alvo["c"]["mask"]).any():
            continue                        # é o próprio olho
        # ACIMA do olho e perto dele: mais de uma distância interocular acima
        # da linha dos olhos já é franja, não sobrancelha
        if not (linha - d_olhos * 1.30 <= reg["cy"] <= alvo["cy"] - reg["h"] * 0.3):
            continue
        # do lado certo, e não em cima do eixo (a ruga da testa do Zeca fica
        # no meio da cara e passaria por sobrancelha)
        if not (d_olhos * 0.12 < abs(reg["cx"] - eixo) < d_olhos * 0.95):
            continue
        if reg["w"] < reg["h"] * 1.3:
            continue                        # sobrancelha é deitada
        if not (larg_olho * 0.40 <= reg["w"] <= larg_olho * 1.60):
            continue                        # do tamanho de um olho, não do cabelo
        # de cada lado fica a mais BAIXA das candidatas: é a que encosta no
        # olho. Acima dela vem ruga, franja e o contorno do cabelo.
        if nome not in achados or reg["cy"] > achados[nome]["cy"]:
            achados[nome] = reg

    # AS DUAS SOBRANCELHAS PODEM SER UM COMPONENTE SÓ: em algumas folhas
    # elas se tocam pelo contorno e saem como uma mancha atravessando a
    # testa. Girada como peça única, ela vira uma barra preta cruzando o
    # rosto. Cortar pelo eixo devolve as duas, que é o que a arte desenha.
    if "sobrancelha_e" not in achados and "sobrancelha_d" not in achados:
        for c in rosto["comps_tinta"]:
            reg = _reg(c)
            bx0, by0, bx1, by1 = c["bbox"]
            if not (bx0 < eixo < bx1 and reg["w"] > d_olhos * 0.9):
                continue
            if not (linha - d_olhos * 1.30 <= reg["cy"]
                    <= achados["olho_e"]["cy"] - reg["h"] * 0.3):
                continue
            if reg["w"] < reg["h"] * 1.6:
                continue
            m = c["mask"].astype(bool)
            for lado, nome in ((m & (np.arange(m.shape[1]) < eixo), "sobrancelha_e"),
                               (m & (np.arange(m.shape[1]) >= eixo), "sobrancelha_d")):
                if lado.sum() < 20:
                    continue
                ys_l, xs_l = np.nonzero(lado)
                cb = (int(xs_l.min()), int(ys_l.min()), int(xs_l.max()), int(ys_l.max()))
                achados[nome] = _reg({"mask": lado, "area": int(lado.sum()), "bbox": cb,
                                      "cx": float(xs_l.mean()), "cy": float(ys_l.mean())})
            break

    # --- recorta cada feição e apaga o lugar dela com a cor da pele
    limpo = a.copy()
    sprites = {}
    cx_p, cy_p = float(piv[0]), float(piv[1])
    for nome, reg in achados.items():
        bx0, by0, bx1, by1 = reg["c"]["bbox"]
        folga = 2
        cx0, cy0 = max(0, bx0 - folga), max(0, by0 - folga)
        cx1, cy1 = min(img.width, bx1 + folga + 1), min(img.height, by1 + folga + 1)
        # QUANTA TESTA EXISTE ACIMA DESTA FEIÇÃO. A sobrancelha erguida é o
        # traço mais forte do espanto, e sem limite ela sobe para cima do
        # cabelo: no primeiro teste, `chocado` colou a sobrancelha na
        # franja e deixou uma mancha de pele onde ela estava. A medida sai
        # da arte -- personagem de testa alta ganha mais curso, o de franja
        # baixa ganha menos, sem ninguém recalibrar constante nenhuma.
        col = int(min(max(reg["cx"], 0), img.width - 1))
        livre, y = 0, int(by0) - 1
        while y >= 0 and nucleo[y, col] and not tinta[y, col]:
            livre += 1
            y -= 1
        # RECORTE PELA FORMA, não pelo retângulo. Com o retângulo vinha
        # junto uma moldura de pele, invisível enquanto a feição está no
        # lugar e denunciada assim que ela se move: a sobrancelha erguida
        # de `surpreso` levava um pedaço de bochecha para cima da franja e
        # deixava uma mancha clara no cabelo. Recortada pela própria
        # máscara, ela sobe sozinha.
        forma = np.zeros(alfa.shape, dtype=np.uint8)
        forma[reg["c"]["mask"].astype(bool)] = 255
        forma = Image.fromarray(forma).filter(ImageFilter.MaxFilter(3)) \
                                      .filter(ImageFilter.GaussianBlur(0.6))
        recorte = img.crop((cx0, cy0, cx1, cy1)).copy()
        recorte.putalpha(ImageChops.multiply(recorte.split()[3],
                                             forma.crop((cx0, cy0, cx1, cy1))))
        sprites[nome] = {
            "img": recorte,
            "dx": (cx0 + cx1) / 2.0 - cx_p,
            "dy": (cy0 + cy1) / 2.0 - cy_p,
            "larg": cx1 - cx0, "alt": cy1 - cy0,
            "teto": max(0.0, livre - 2.0),
        }
        # A COR DA TAPA VEM DE ENCOSTO, não do rosto inteiro. A cor
        # dominante do crânio é um tom quantizado (a caixa de 24 níveis em
        # que a pele caiu), e a testa tem sombreado próprio: com ela, o
        # lugar de onde a sobrancelha saiu ficava mais claro que a testa em
        # volta e virava uma sobrancelha FANTASMA -- visível em toda
        # expressão que ergue o cenho. O anel de pixels em volta da feição é
        # a própria testa, no tom exato daquele ponto.
        m = reg["c"]["mask"].astype(np.uint8) * 255
        m = np.asarray(Image.fromarray(m).filter(ImageFilter.MaxFilter(5))) > 8
        limpo[m, :3] = _cor_do_anel(a, m, alfa) or pele
        limpo[m, 3] = 255

    # emenda macia, pelo mesmo motivo da tapa da boca: cor certa com borda
    # dura ainda se lê como remendo
    tapa = np.zeros(alfa.shape, dtype=np.uint8)
    for nome, reg in achados.items():
        m = np.asarray(Image.fromarray(reg["c"]["mask"].astype(np.uint8) * 255)
                       .filter(ImageFilter.MaxFilter(5)))
        tapa = np.maximum(tapa, m)
    suave = Image.composite(Image.fromarray(limpo), img,
                            Image.fromarray(tapa).filter(ImageFilter.GaussianBlur(2)))
    return suave, sprites


def _cor_do_anel(arr, mascara, alfa, folga=5):
    """A cor da pele que ENCOSTA na mancha a ser tapada.

    Mesmo princípio de `_cor_em_volta`, mas trabalhando direto no array (é
    chamado uma vez por feição, dentro de `_extrair_feicoes`). Só entram
    pixels claros: o traço preto que cerca olho e sobrancelha faria a
    mediana escurecer e a tapa sairia como um borrão cinza."""
    fora = np.asarray(Image.fromarray((mascara * 255).astype(np.uint8))
                      .filter(ImageFilter.MaxFilter(2 * folga + 1))) > 8
    anel = fora & ~mascara & (alfa > 200)
    if anel.sum() < 20:
        return None
    px = arr[anel][:, :3].astype(np.int16)
    claros = px[px.sum(axis=1) > 300]
    base = claros if len(claros) > 12 else px
    return tuple(int(v) for v in np.median(base, axis=0))


def _tapar_boca_desenhada(img, rosto=None):
    """Apaga a boca que a ARTE desenhou e devolve onde ela estava.

    POR QUE (folha de 26/08)
        A folha nova consertou o defeito nº 1: a boca não é mais um entalhe
        vazado, é uma linha desenhada, fechada, com um sorriso de leve. Só
        que `_tapar_entalhe` procura um BURACO no alfa -- e não há mais
        buraco nenhum. Sem entalhe, `self.boca` ficava None, e com ela ia
        embora o lipsync inteiro: o Pal passaria o vídeo com a mesma boca
        parada, agora fechada em vez de aberta.

        A boca da arte precisa sair de cena pelo mesmo motivo que as feições
        saem do crânio em `_extrair_feicoes`: o que fica parado no desenho
        não pode ser animado. Apagada ela, `_boca_desenhada` põe no lugar
        exato dela uma boca que abre com o som e curva com a emoção -- e o
        traço em repouso é praticamente o mesmo que o desenhista fez.

    COMO
        Dentro do crânio, longe da borda, o que não é pele é traço. A boca
        é o traço DEITADO (mais largo que alto) do terço de baixo, perto do
        eixo do rosto. O queixo (um U que desce até a base) e as linhas
        verticais das bochechas ficam de fora pela mesma régua que as
        distingue: eles não são deitados, ou não estão no eixo.

    Devolve (crânio sem a boca, caixa da boca) ou (img, None).
    """
    from segmentar import _componentes
    a = np.asarray(img.convert("RGBA"))
    alfa = a[..., 3]
    dentro = alfa > 128
    if dentro.sum() < 400:
        return img, None, None

    # o raio de erosão é medido no ROSTO, não na tela inflada por
    # `_centralizar` -- ver a mesma nota em `_extrair_feicoes`
    ys, xs = np.nonzero(dentro)
    x0, x1 = float(xs.min()), float(xs.max())
    y0, y1 = float(ys.min()), float(ys.max())
    larg_r, alt_r = x1 - x0 + 1, y1 - y0 + 1
    cx_rosto = (x0 + x1) / 2.0

    r = max(3, int(min(larg_r, alt_r) * 0.045))
    nucleo = np.asarray(img.split()[3].filter(ImageFilter.MinFilter(2 * r + 1))) > 128
    if nucleo.sum() < 200:
        return img, None, None

    rgb = a[..., :3].astype(np.int16)
    q = (rgb[nucleo] // 24)
    chaves, contas = np.unique(q.reshape(-1, 3), axis=0, return_counts=True)
    pele = chaves[contas.argmax()].astype(np.int16) * 24 + 12
    tinta = nucleo & (np.abs(rgb - pele).sum(axis=2) > 90)
    if tinta.sum() < 20:
        return img, None, None

    # A FAIXA sai dos olhos quando eles foram medidos (ver `_analisar_rosto`):
    # entre o nariz e o queixo, no eixo, com a largura contada em distância
    # interocular. Sem olhos, cai na régua antiga -- frações da peça, que só
    # valem quando a peça é o rosto e nada mais.
    if rosto:
        ymin, ymax, eixo, tol_x = _faixa_da_boca(rosto)
        # a largura do rosto, contada em distância interocular: num rosto
        # frontal ela vale por volta de 2,2 vezes o vão entre os olhos
        larg_ref = rosto["d_olhos"] * 2.2
    else:
        ymin, ymax = y0 + alt_r * 0.52, y0 + alt_r * 0.92
        eixo, tol_x = cx_rosto, larg_r * 0.22
        larg_ref = larg_r

    cands = []
    for c in _componentes(tinta, area_min=max(20, int(tinta.sum() * 0.01))):
        bx0, by0, bx1, by1 = c["bbox"]
        w, h = bx1 - bx0 + 1, by1 - by0 + 1
        cy = (by0 + by1) / 2.0
        if cy < ymin or cy > ymax:
            continue                       # olho/sobrancelha em cima, pescoço embaixo
        if abs((bx0 + bx1) / 2.0 - eixo) > tol_x:
            continue                       # fora do eixo: bochecha, orelha
        if w < h * 1.4 or w < larg_ref * 0.10 or w > larg_ref * 0.75:
            continue                       # a boca é deitada, e não atravessa a cara
        cands.append(c)
    if not cands:
        return img, None, None

    # a boca é a maior delas; o que estiver logo abaixo e mais estreito é o
    # lábio inferior e sai junto -- sobrando, ele vira um risco solto sob a
    # boca nova
    boca = max(cands, key=lambda c: c["area"])
    bx0, by0, bx1, by1 = boca["bbox"]
    m = boca["mask"].copy()
    for c in cands:
        if c is boca:
            continue
        cx0, cy0, cx1, cy1 = c["bbox"]
        if cy0 > by0 and cy1 < by1 + (by1 - by0 + 1) * 1.2 and (cx1 - cx0) <= (bx1 - bx0):
            m |= c["mask"]
            bx0, by0 = min(bx0, cx0), min(by0, cy0)
            bx1, by1 = max(bx1, cx1), max(by1, cy1)

    limpo = a.copy()
    grosso = np.asarray(Image.fromarray((m * 255).astype(np.uint8))
                        .filter(ImageFilter.MaxFilter(5))) > 8
    grosso &= dentro
    limpo[grosso, :3] = pele
    limpo[grosso, 3] = 255
    suave = Image.composite(
        Image.fromarray(limpo), img,
        Image.fromarray((grosso * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)))

    # O SORRISO DO DESENHISTA NÃO SE PERDE. A boca que entra no lugar é
    # desenhada por código, e desenhada reta ela apaga a única expressão que
    # a folha já trazia de fábrica -- a cara em repouso fica com um traço
    # de régua no meio. Medir a curva da linha original (o meio dela está
    # acima ou abaixo das pontas?) e usá-la como repouso devolve o mesmo
    # rosto, agora animável. A espessura sai pela mesma régua: é a altura
    # média da mancha, não uma fração inventada da largura.
    so = np.asarray(_altura_por_coluna(m, bx0, bx1))
    curva, esp = 0.0, 0.0
    val = so[so[:, 1] > 0]
    if len(val) >= 6:
        n = len(val)
        pontas = np.concatenate([val[:max(1, n // 5)], val[-max(1, n // 5):]])
        meio = val[n // 3: 2 * n // 3]
        if len(meio):
            # Mesma convenção de `_boca_desenhada`: curva > 0 empurra o MEIO
            # da linha para baixo, e é isso que se lê como sorriso -- num
            # traço de boca são as PONTAS que sobem. y cresce para baixo,
            # então meio - pontas > 0 é sorriso.
            larg_b = max(bx1 - bx0 + 1, 1)
            curva = float((meio[:, 0].mean() - pontas[:, 0].mean()) / (larg_b * 0.16))
            esp = float(val[:, 1].mean())
    return suave, (int(bx0), int(by0), int(bx1), int(by1)), \
        {"curva": max(-1.0, min(1.0, curva)), "esp": esp}


def _altura_por_coluna(mask, x0, x1):
    """(y do centro, espessura) de cada coluna da mancha -- a linha da boca
    lida como função, que é o que permite medir curva e espessura."""
    fora = []
    for x in range(int(x0), int(x1) + 1):
        col = np.nonzero(mask[:, x])[0]
        if len(col):
            fora.append(((float(col.min()) + float(col.max())) / 2.0, float(len(col))))
        else:
            fora.append((0.0, 0.0))
    return fora


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

        # --- ONDE FICA O ROSTO DENTRO DA PEÇA DO CRÂNIO -----------------
        # Medido UMA vez, pelos olhos, e usado pelas três funções de rosto.
        # Sem isto cada uma inventava a própria régua a partir da caixa da
        # peça -- e a peça do crânio traz cabelo e pescoço em quantidade que
        # é decisão do desenhista. Ver `_analisar_rosto`.
        self.rosto = _analisar_rosto(self.img["cranio"]) if "cranio" in self.img else None
        if self.rosto:
            print(f"[rosto] olhos medidos: vao de {self.rosto['d_olhos']:.0f}px, "
                  f"linha em y={self.rosto['linha_olhos']:.0f}, "
                  f"queixo em y={self.rosto['queixo']:.0f}")
        elif "cranio" in self.img:
            print("[rosto] nao achei o par de olhos na peca do cranio; a boca e "
                  "as feicoes vao ser procuradas pela caixa da peca (regra antiga)")

        # --- o queixo existe mesmo? -----------------------------------
        self.boca = None            # (dx, dy, largura) relativos ao pivô do crânio
        # curva e espessura de REPOUSO, medidas da boca que a arte desenhou
        self.boca_estilo = {"curva": 0.0, "esp": 0.0}
        if "mandibula" not in self.img or _e_fiapo(self.img["mandibula"]):
            self.rosto_articulado = False
            self.img.pop("mandibula", None)     # fiapo em cena é sujeira solta
            if "cranio" in self.img:
                tapado, caixa = _tapar_entalhe(self.img["cranio"], rosto=self.rosto)
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
                    # Sem entalhe: ou a folha nunca teve um, ou (folha de
                    # 26/08) a boca virou uma LINHA desenhada. No segundo
                    # caso ela é apagada e redesenhada animada, senão o
                    # lipsync some junto com o buraco.
                    limpo, caixa, estilo = _tapar_boca_desenhada(self.img["cranio"],
                                                                 rosto=self.rosto)
                    if caixa:
                        self.img["cranio"] = limpo
                        px, py = self.piv["cranio"]
                        bx0, by0, bx1, by1 = caixa
                        self.boca = ((bx0 + bx1) / 2.0 - px,
                                     (by0 + by1) / 2.0 - py,
                                     (bx1 - bx0) * 1.02)
                        self.boca_estilo = estilo
                        print(f"[rosto] boca DESENHADA na arte "
                              f"({int(bx1 - bx0)}px, curva "
                              f"{estilo['curva']:+.2f}): apagada e "
                              f"substituida por uma que abre com o som e "
                              f"curva com a emocao")
                    else:
                        print("[rosto] sem mandibula segmentada e sem boca "
                              "detectada; seguindo com a cara como veio")
        # feições que sobraram como fiapo saem de cena pelo mesmo motivo: em
        # repouso elas caem sobre o próprio desenho e somem, mas qualquer
        # movimento de expressão as descola e vira traço solto no rosto
        for f in ("olho_e", "olho_d", "sobrancelha_e", "sobrancelha_d", "nariz"):
            if f in self.img and _e_fiapo(self.img[f]):
                print(f"[rosto] '{f}' e um fiapo de contorno, nao uma feicao; "
                      f"ignorando")
                self.img.pop(f, None)

        # --- as feições estão desenhadas DENTRO do crânio? ---------------
        # Quando a folha não entrega olho e sobrancelha como peça (é o caso
        # do Pal), elas são recortadas de lá e passam a se mexer como se
        # fossem peças. Ver _extrair_feicoes.
        self.feicoes = None
        self._cache_cara = {}
        if "cranio" in self.img and not (self.tem("olho_e") and self.tem("olho_d")):
            limpo, feic = _extrair_feicoes(self.img["cranio"], self.piv["cranio"],
                                           rosto=self.rosto)
            if feic:
                self.img["cranio"] = limpo
                self.feicoes = feic
                print(f"[rosto] feicoes recortadas do cranio: "
                      f"{', '.join(sorted(feic))} -- a cara passa a se mexer")
            else:
                print("[rosto] nao consegui separar olhos e sobrancelhas do "
                      "cranio; a expressao fica so na cabeca e na boca")

        self._fundir_cabelo()

    def _fundir_cabelo(self):
        """O cabelo vira PARTE do crânio, uma peça só.

        POR QUE (defeito visto em 29/08, ao ligar a expressão facial)
            Bastava `cabeca_rot` valer 2 graus para o cabelo escorregar e
            abrir uma faixa de pele na testa. A causa é o encaixe: o crânio
            gira em torno do pivô dele (a base, no pescoço) e o cabelo em
            torno do DELE (no meio da franja), e os dois só coincidem se o
            pivô do cabelo cair exatamente no ponto de saída marcado no
            crânio. O segmentador não mediu vão entre cabelo e crânio
            (`vaos["cabelo"] == 0`), então esse ponto é estimado -- e alguns
            pixels de erro viram um degrau visível assim que a cabeça
            inclina.

            Não há nada a ganhar em manter os dois separados: cabelo não
            articula. Fundidos, giram como um bloco por construção, e o
            erro de encaixe deixa de existir em vez de ser calibrado.

        O pivô do crânio é preservado -- é ele que o esqueleto usa para
        pendurar a cabeça no pescoço.
        """
        if "cabelo" not in self.img or "cranio" not in self.img:
            return
        saida = (self.saidas.get("cranio") or {}).get("cabelo")
        if not saida:
            return
        pc = self.pivos["cranio"]
        # vetor do pivô do crânio até o ponto onde o cabelo encaixa, medido
        # na arte original: deslocamento é invariante a recorte e a
        # centralização, então vale igual na peça já processada
        dx, dy = float(saida[0]) - float(pc[0]), float(saida[1]) - float(pc[1])
        cranio, pcr = self.img["cranio"], self.piv["cranio"]
        cab, pcb = self.img["cabelo"], self.piv["cabelo"]
        x0 = pcr[0] + dx - pcb[0]
        y0 = pcr[1] + dy - pcb[1]
        minx, miny = min(0.0, x0), min(0.0, y0)
        maxx = max(float(cranio.width), x0 + cab.width)
        maxy = max(float(cranio.height), y0 + cab.height)
        tela = Image.new("RGBA", (int(math.ceil(maxx - minx)),
                                  int(math.ceil(maxy - miny))), (0, 0, 0, 0))
        tela.alpha_composite(cranio, (int(round(-minx)), int(round(-miny))))
        tela.alpha_composite(cab, (int(round(x0 - minx)), int(round(y0 - miny))))
        self.img["cranio"], self.piv["cranio"] = _centralizar(
            tela, (pcr[0] - minx, pcr[1] - miny))
        self.img.pop("cabelo", None)
        self.piv.pop("cabelo", None)

    def cranio_com_cara(self, ex, piscando=False):
        """O crânio com as feições nas posições que a expressão pede.

        Compor DENTRO da peça, e não colar cada feição na cena, é o que faz
        a cara acompanhar a cabeça de graça: o crânio já é girado e
        posicionado pelo esqueleto, e tudo o que estiver desenhado nele vai
        junto. Também é o que mantém a ordem de sobreposição correta sem
        acrescentar peça nenhuma ao ORDEM_Z.

        Com cache pela expressão arredondada: um vídeo de 20 segundos tem
        ~430 frames e não mais que algumas dezenas de caras distintas."""
        base_img, base_piv = self.img["cranio"], self.piv["cranio"]
        if not self.feicoes:
            return base_img, base_piv
        chave = (round(float(ex.get("sobrancelha_dy", 0.0)), 3),
                 round(float(ex.get("sobrancelha_rot", 0.0)), 1),
                 round(float(ex.get("olho_sx", 1.0)), 2),
                 round(float(ex.get("olho_sy", 1.0)), 2),
                 round(float(ex.get("olho_dy", 0.0)), 3),
                 bool(piscando))
        if chave in self._cache_cara:
            return self._cache_cara[chave], base_piv

        hc = self.altura_cranio()
        cara = base_img.copy()
        # as feições são medidas contra o PIVÔ: o crânio foi recomposto com
        # o cabelo dentro depois de elas serem recortadas, e o centro da
        # imagem mudou nessa hora. O pivô, não.
        cx, cy = float(base_piv[0]), float(base_piv[1])
        # ordem: sobrancelha depois do olho, para o cenho baixo poder
        # encostar na pálpebra sem ficar por baixo dela
        for nome in ("olho_e", "olho_d", "sobrancelha_e", "sobrancelha_d"):
            spr = self.feicoes.get(nome)
            if spr is None:
                continue
            im = spr["img"]
            dx, dy = spr["dx"], spr["dy"]
            if nome.startswith("olho"):
                if piscando:
                    # PISCAR sem peça de olho fechado: um traço da largura do
                    # olho, na cor do contorno da própria arte. É o que a
                    # animação cut-out faz -- e some junto com este remendo
                    # no dia em que a folha trouxer o olho como peça.
                    im = Image.new("RGBA", (spr["larg"], max(3, spr["alt"] // 3)),
                                   (0, 0, 0, 0))
                    d = ImageDraw.Draw(im)
                    esp = max(2, spr["alt"] // 7)
                    d.line([(1, im.height // 2), (im.width - 2, im.height // 2)],
                           fill=_cor_da_casca(spr["img"]) + (255,), width=esp)
                else:
                    sx, sy = float(ex.get("olho_sx", 1.0)), float(ex.get("olho_sy", 1.0))
                    if abs(sx - 1) > 0.02 or abs(sy - 1) > 0.02:
                        im = im.resize((max(2, int(im.width * sx)),
                                        max(2, int(im.height * sy))), Image.LANCZOS)
                    dy += float(ex.get("olho_dy", 0.0)) * hc
            else:
                # sobe no máximo até onde há testa (ver `teto` em
                # _extrair_feicoes): passar disso põe a sobrancelha dentro
                # do cabelo, e o espanto vira defeito
                d = float(ex.get("sobrancelha_dy", 0.0)) * hc
                dy += max(d, -float(spr.get("teto", hc)))
                rot = float(ex.get("sobrancelha_rot", 0.0))
                if abs(rot) > 0.5:
                    # sinal oposto nos dois lados: o que se lê como raiva é a
                    # ponta INTERNA descendo nas duas, não as duas girando
                    # para o mesmo lado
                    g = rot if nome.endswith("_e") else -rot
                    im = im.rotate(-g, resample=Image.BICUBIC, expand=True)
            cara.alpha_composite(im, (int(round(cx + dx - im.width / 2.0)),
                                      int(round(cy + dy - im.height / 2.0))))
        self._cache_cara[chave] = cara
        return cara, base_piv

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

# Peças que fecham a junta mesmo sem vão medido (ver Personagem.__init__).
#
# `abdomen` entrou em 29/08: ele é a RAIZ do esqueleto, e o segmentador só
# mede vão entre uma peça e o pai dela -- a raiz não tem pai, então nunca
# ganhou medida. O efeito aparecia como uma faixa branca contornando o
# quadril: o peito e as coxas engrossavam em direção a ele, e ele não
# engrossava para lado nenhum, deixando meio vão aberto na cintura e na
# virilha em todos os frames.
FECHA_MESMO_SEM_MEDIDA = ("mandibula", "abdomen")

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
    # ÁRVORE EFETIVA: peça que a arte não separou não pode quebrar a cadeia.
    # A folha de 26/08 traz o pescoço grudado na cabeça, e com a árvore
    # literal do ESQUELETO o crânio ficava pendurado num `pescoco` que não
    # existe -- ninguém o visitava e o personagem saía SEM CABEÇA. O
    # segmentador já grava a saída no ancestral presente (ver
    # segmentar._ancestral_presente); aqui a travessia faz o mesmo salto.
    filhos = {}
    for n in ESQUELETO:
        pai = ESQUELETO[n]
        while pai is not None and not pers.tem(pai):
            pai = ESQUELETO.get(pai)
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

        if nome == "cranio" and getattr(pers, "feicoes", None):
            # a cara vem montada dentro da própria peça (ver
            # Personagem.cranio_com_cara): é assim que olho e sobrancelha se
            # mexem numa folha que não os entregou separados
            img, piv = pers.cranio_com_cara(ex, piscando)
        elif nome in var:
            img, piv = pers.variar(nome, *var[nome])
        else:
            img, piv = pers.p(nome)
        colar(base, img, piv, pos[nome], ang[nome] + giro.get(nome, 0.0), e)

        # BOCA DESENHADA: logo depois do crânio, antes das feições, que é
        # onde a boca da arte estaria. Só existe quando a folha não trouxe
        # queixo articulado (ver Personagem.__init__).
        if nome == "cranio" and getattr(pers, "boca", None):
            bdx, bdy, blarg = pers.boca
            estilo = getattr(pers, "boca_estilo", None) or {}
            # a curva da emoção SOMA à curva de repouso que o desenhista deu
            # à boca: a cara neutra continua sendo a que ele desenhou
            bimg, bpiv = _boca_desenhada(
                blarg * e, blarg * e * 0.55, boca_nivel,
                max(-1.0, min(1.0, ex["boca_curva"] + float(estilo.get("curva", 0.0)))),
                _cor_da_casca(pers.img["cranio"]),
                espessura=float(estilo.get("esp", 0.0)) * e or None)
            d = _girar((bdx * e, bdy * e), ang[nome])
            colar(base, bimg, bpiv,
                  (pos[nome][0] + d[0], pos[nome][1] + d[1]), ang[nome])

        # objeto: entra logo depois da mão que o segura, para ficar na
        # frente dela. É o osso da mão que tornou isto possível.
        if objeto and objeto.get("img") is not None and nome == "mao_" + objeto.get("mao", "e"):
            oi = objeto["img"]
            opv = objeto.get("pivo") or _pivo_de_pega(oi)
            oi, opv = _centralizar(oi, opv)
            # A MÃO SEGURA COM A PALMA, NÃO COM O PUNHO. `pos[nome]` é o
            # pivô da mão, que fica na junta com o antebraço -- colar o
            # objeto ali o joga para dentro do corpo, e num objeto grande
            # ele aparece flutuando na frente da barriga. O ponto certo
            # fica adiante, na direção em que a mão aponta.
            comp = pers.comp.get(nome, 0.0) * pers.escala
            rad = math.radians(ang[nome])
            palma = (pos[nome][0] + math.cos(rad) * comp * 0.55,
                     pos[nome][1] + math.sin(rad) * comp * 0.55)
            colar(base, oi, opv, palma, ang[nome],
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


def _enquadramento(i, n_trechos, n_atores, t):
    """Plano do trecho `i`: quanto a câmera fecha, e onde ela centra.

    POR QUE ISTO EXISTE
        Até 27/08 o personagem saía sempre do mesmo tamanho e sempre no
        meio, do primeiro ao último segundo. Num feed isso lê como imagem
        parada com áudio por cima -- foi a queixa depois do terceiro vídeo
        da esteira ("os dois ficam quase parados"). Gesto e cara resolvem
        metade; a outra metade é a CÂMERA, e ela já existia no motor
        (`cam["zoom"]`), só que ninguém a usava fora de uma ação.

    O QUE ELE FAZ
        1. Cada trecho tem um plano diferente do vizinho -- aberto, médio,
           fechado, girando. A troca de plano entre trechos é o corte que
           este formato não tem: corte reseta a atenção de quem rola o
           feed, e é o recurso de retenção mais barato que existe.
        2. Dentro do trecho a câmera FECHA devagar (push-in). Câmera que
           anda um pouco o tempo todo é o que separa vídeo de fotografia.
        3. O último trecho é a virada e fecha no rosto: a piada acontece
           na cara, e é para ela que se olha quando a tirada cai.

    O TETO DEPENDE DE QUANTA GENTE ESTÁ EM CENA. Com dois atores (em
    x=296 e x=784 num quadro de 1080) fechar demais corta um deles pela
    borda, então o teto cai para 1,12 -- com um ator sozinho, no meio do
    quadro, dá para ir a 1,30 sem perder braço nenhum."""
    teto = 1.12 if n_atores > 1 else 1.30
    ciclo = (1.0, 1.0 + (teto - 1.0) * 0.5, teto)
    if i == n_trechos - 1:
        base = teto                     # a virada fecha no rosto
    elif i == n_trechos - 2:
        base = ciclo[0]                 # e o trecho antes dela ABRE: sem o
        # contraste, a virada chegaria no mesmo tamanho do que veio antes e
        # o fechamento nao seria percebido como troca de plano
    else:
        base = ciclo[i % len(ciclo)]
    z = base * (1.0 + 0.035 * max(0.0, min(1.0, t)))
    # fechar centrado no meio do quadro subiria o corte pelos pés e pela
    # cabeça em partes iguais; puxar o centro para cima mantém a cara
    # dentro do quadro, que é onde a piada acontece
    fechado = (z - 1.0) / max(teto * 1.035 - 1.0, 1e-6)
    return z, 0.5 - 0.10 * max(0.0, min(1.0, fechado))


# =====================================================================
def _rig_do_trecho(tr, t, pan_base, acoes_do_ator, x_base, falando=True):
    """Ângulos do frame de UM ator. Dois caminhos:

    AÇÕES (novo)  -- verbos com janela, somados por cima do repouso.
    POSE (velho)  -- interpolação entre duas poses estáticas. Fica só
                     para não quebrar spec antigo; não produz caminhada.

    A pilha do caminho novo, de baixo para cima:

        postura da emoção -> parado -> gesticular -> ações do roteiro

    Postura e gesto de fala são o CORPO da emoção que o trecho já declarou
    (ver acoes.POSTURA); ficam embaixo porque tudo que o roteirista pedir
    de propósito tem que ganhar deles.
    """
    rig = merge(REST, EXPRESSOES.get(tr.get("expressao", "neutro"), {}))
    rig["quadril"] = [x_base, REST["quadril"][1]]

    if acoes_do_ator or tr.get("acoes"):
        ACOES.aplicar_postura(rig, tr.get("expressao"), tr.get("intensidade", 1.0))
        lista = [{"nome": "parado", "de": 0.0, "ate": 1.0}]
        if falando:
            lista.append({"nome": "gesticular", "de": 0.0, "ate": 1.0,
                          "forca": ACOES.energia_gesto(tr.get("expressao"),
                                                       tr.get("intensidade", 1.0))})
        cam = ACOES.aplicar(lista + list(acoes_do_ator or []), t, rig, tr["dur"])
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
    if len(elenco) > MAX_EM_CENA:
        # DOIS, NO MAXIMO. Num quadro 9:16 o terceiro boneco ou sai do
        # enquadramento ou obriga um recuo em que ninguem mais tem cara --
        # e cara é onde a piada acontece. A regra vem do roteiro; aqui ela
        # é aplicada de novo porque spec errado não pode virar vídeo
        # ilegível.
        print(f"[elenco] {len(elenco)} personagens no spec; a cena aceita "
              f"{MAX_EM_CENA}: fico com "
              f"{', '.join(list(elenco)[:MAX_EM_CENA])}")
        elenco = {k: elenco[k] for k in list(elenco)[:MAX_EM_CENA]}
    fora = {}
    n = len(elenco)
    for i, (chave, cfg) in enumerate(elenco.items()):
        cfg = cfg if isinstance(cfg, dict) else {"pasta": cfg}
        pasta = cfg.get("pasta") or os.path.join(pasta_padrao, "..", chave)
        # posições padrão bem separadas: duas pessoas no mesmo x viram uma
        # pessoa só com quatro braços
        padrao = W * (0.5 if n == 1 else 0.27 + 0.46 * i / max(n - 1, 1))
        p = Personagem(pasta)
        # Com mais de um personagem em cena, cada um encolhe: dois bonecos
        # na altura de protagonista não cabem lado a lado num quadro 9:16
        # sem se atravessarem. O recuo também dá a leitura de "plano
        # aberto, dois na cena" em vez de "close que deu errado".
        p.escala *= float(cfg.get("escala", 1.0 if n == 1 else 0.74))
        fora[chave] = (p, float(cfg.get("x", padrao)))
    return _alinhar_pelos_pes(fora)


def _alinhar_pelos_pes(elenco):
    """Todo mundo pisa na MESMA linha do chão.

    O rig ancora o personagem pelo QUADRIL -- é a raiz do esqueleto, e é de
    lá que a árvore de peças se abre. Só que a altura do quadril dentro do
    corpo é decisão do desenhista: no Pal e no Zeca o quadril fica a 66% da
    figura, na Maya a 56% (a legging faz a divisão subir). Postos com o
    quadril na mesma altura, os pés dela caíram 90 px abaixo dos dele -- os
    dois no mesmo cenário, um pisando no chão e o outro enterrado nele.

    A correção não é proporção nem tabela: é MEDIR. Cada personagem é
    desenhado uma vez em repouso, e o deslocamento vertical que põe a base
    dele na base do primeiro fica guardado. Custa um frame por ator, no
    carregamento, e vale para qualquer folha nova sem ninguém ajustar nada.

    Devolve {chave: (Personagem, x, dy)}.
    """
    base_ref, fora = None, {}
    for chave, (pers, x) in elenco.items():
        rig = merge(REST, {})
        rig["quadril"] = [W / 2.0, REST["quadril"][1]]
        bb = desenhar_personagem(pers, rig).getbbox()
        base = bb[3] if bb else REST["quadril"][1]
        if base_ref is None:
            base_ref = base
        dy = base_ref - base
        if abs(dy) > 1:
            print(f"[elenco] {chave}: {dy:+.0f}px em y para pisar na mesma "
                  f"linha do chao")
        fora[chave] = (pers, x, float(dy))
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


def _inventario(pastas, exts=(".png", ".jpg", ".jpeg", ".webp")):
    """Nomes de arte que existem nessas pastas, sem extensão.

    O motor precisa saber o que TEM antes de decidir o que usar: sem isso
    a única resposta possível a um cenário faltante é a cor chapada, que
    foi o defeito de 28/08. Arquivo começado por `_` fica de fora -- é a
    convenção dos artefatos de conferência (`_mapa.png`)."""
    fora = set()
    for p in pastas:
        try:
            for f in os.listdir(p):
                base, ext = os.path.splitext(f)
                if ext.lower() in exts and not base.startswith("_"):
                    fora.add(base.lower())
        except OSError:
            continue
    return fora


def _objeto_na_mao(acoes_do_ator, t, objetos, atual):
    """O que este ator está segurando NESTE instante.

    O objeto é um ESTADO, não um efeito de janela. Até 26/08 ele só existia
    enquanto a ação que o citava estava rodando: o personagem pegava o
    celular, a ação terminava e o celular sumia da mão no meio da fala
    seguinte -- e a única saída era repetir `objeto` em toda ação do
    roteiro, o que ninguém faz.

    Agora quem pega, segura: a partir do início de uma ação de pegar
    (`acoes.ACOES_PEGAM_OBJETO`) o objeto fica na mão, atravessa trechos, e
    só sai em `largar_objeto`. Uma ação de qualquer outro nome que cite
    `objeto` continua valendo -- é como os specs antigos escrevem.
    """
    for a in acoes_do_ator:
        if float(a.get("de", 0.0)) > t:
            continue
        if a.get("nome") in ACOES.ACOES_LARGAM_OBJETO:
            atual = None
            continue
        nome = a.get("objeto")
        if nome in objetos:
            atual = {"img": objetos[nome], "mao": a.get("mao", "d"),
                     "escala": float(a.get("escala_objeto", 1.0))}
    return atual


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
        # 11% da altura do ator, não 16%: com 16% a xícara ficou do tamanho
        # do tronco no primeiro vídeo com objeto em cena. Uma caneca tem
        # ~10 cm contra 1,75 m de gente, e mesmo exagerando para cartoon o
        # que se lê como "objeto de mão" para de ler bem acima de 12%.
        alvo = ALTURA_ALVO_PX * 0.11
        k = alvo / max(im.height, 1)
        im = im.resize((max(int(im.width * k), 1), max(int(im.height * k), 1)),
                       Image.LANCZOS)
        objetos[nome] = im

    # nenhum vídeo abre sem gatilho -- rede de segurança no motor
    ACOES.garantir_gancho(spec)

    # VOZ PRIMEIRO: a duração real vira a timeline (igual ao palito_v5)
    faixas, respiros, marcas_por_trecho, total = [], [], [], 0.0
    n_trechos = len(spec["trechos"])
    for i, tr in enumerate(spec["trechos"]):
        wav = os.path.join(tmp, f"v{i:02d}.wav")
        perfil = tr.get("perfil_voz") or tr.get("ator") or "narrador"
        cfg = spec.get("vozes", {}).get(perfil, {})
        # A EMOÇÃO DO TRECHO TAMBÉM MUDA A VOZ. Até 28/08 a cara mudava e a
        # voz não: o mesmo rate e o mesmo pitch do começo ao fim, quatro
        # falas com a mesma entonação. O rótulo é um só (`expressao`), e
        # daqui saem os dois -- ver expressao.PROSODIA.
        cfg = EXPR.prosodia(tr.get("expressao"), tr.get("intensidade", 1.0), cfg)
        for k in ("rate", "pitch", "volume"):    # o trecho pode cravar
            if tr.get(k):
                cfg[k] = tr[k]
        # as MARCAS de palavra deixam de ser descartadas: sao elas que dao
        # o tempo exato de cada palavra para a legenda (ver legendas.py)
        marcas, dur = sintetizar(tr["fala"], cfg, wav,
                                 spec.get("modo_tts", os.environ.get("MODO_TTS", "real")))
        # pausa depois da fala: a longa é a que separa a montagem da piada
        # da piada (expressao.respiro_sugerido)
        respiro = float(tr.get("respiro_s", EXPR.respiro_sugerido(i, n_trechos)))
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
    # O LIPSYNC SAI DA VOZ PURA, e é por isso que o envelope é medido AQUI,
    # antes da mixagem: com efeito e trilha dentro, a boca do personagem
    # abriria no baque da queda e no arpejo da marimba.
    env = envelope(voz)

    # EFEITOS E TRILHA (ver sfx.py). O spec pode desligar com
    # "musica": false / "sfx": false; ligados é o padrão, porque um Short de
    # humor com faixa de voz seca soa como recado de secretária eletrônica.
    audio = voz
    if spec.get("sfx", True) is not False or spec.get("musica", True):
        eventos = SFX.eventos_do_spec(spec) if spec.get("sfx", True) is not False else []
        # A TRILHA SEGUE A CENA. Os segmentos saem da emoção de cada trecho,
        # que só existe depois que a voz definiu a timeline -- por isso são
        # montados aqui e não no n8n.
        musica = spec.get("musica", True)
        if isinstance(musica, dict) and not musica.get("arquivo"):
            musica = dict(musica)
            musica.setdefault("segmentos", SFX.segmentos_do_spec(spec))
        audio = SFX.mixar(voz, eventos, os.path.join(tmp, "mix.wav"),
                          musica=musica, dur_s=total)

    # A FAIXA DE CIMA. Com dois em cena, um quinto do quadro era parede
    # lisa do primeiro ao último frame -- ver topo.py.
    import topo as TOPO
    faixa_topo = TOPO.do_spec(spec, W, H)

    # LEGENDA: opcional, mas ligada por padrão. Short se assiste no mudo.
    leg = None
    if spec.get("legenda", True):
        from legendas import Legenda
        leg = Legenda(W, H, tamanho=spec.get("legenda_px"),
                      por_bloco=spec.get("legenda_palavras", 3),
                      y_rel=spec.get("legenda_y"))
        for tr, m in zip(spec["trechos"], marcas_por_trecho):
            leg.adicionar(tr["fala"], m, tr["_inicio_s"], tr["_dur_voz"])
        print(f"[legenda] {len(leg.blocos)} blocos"
              + ("" if any(marcas_por_trecho) else " (sem WordBoundary: tempo repartido)"))

    # LINHA DO CHÃO: onde os pés do personagem pousam em repouso. Sai de um
    # frame de teste, uma vez por render -- é a única referência estável de
    # chão que existe, já que o cenário é arte e não traz cota nenhuma.
    chao_y = None
    try:
        pers0, x0_, dy0 = elenco[padrao_ator]
        rig0 = merge(REST, {})
        rig0["quadril"] = [x0_, REST["quadril"][1] + dy0]
        bb0 = desenhar_personagem(pers0, rig0).getbbox()
        chao_y = bb0[3] if bb0 else None
        print(f"[chao] linha do chao em y={chao_y}")
    except Exception as e:
        print(f"[chao] nao consegui medir ({e}); seguindo sem sombra de contato")

    pastas_cenario = _pastas(spec, pasta_partes, "pasta_cenarios", ("cenarios", "cenario"))
    # O QUE EXISTE DE VERDADE, medido uma vez. É contra esta lista que o
    # pedido do roteiro é resolvido: pedir `padaria` chega em `comercio`,
    # pedir um cenário que ninguém gerou chega no interior mais parecido --
    # e a cor chapada volta a ser o que sempre deveria ter sido, o último
    # recurso quando NÃO HÁ arte nenhuma (ver cenarios.py).
    inventario = _inventario(pastas_cenario)
    print(f"[cenario] disponiveis: {', '.join(sorted(inventario)) or '(nenhum)'}")
    cenarios = {}
    # A CARA. Um Rosto por render: ele guarda com que expressão cada ator
    # terminou o trecho para o seguinte começar dali, em vez de pular de
    # cara entre trechos (ver expressao.Rosto).
    rosto = EXPR.Rosto(spec)
    caras = []
    n = 0
    # o que cada ator tem na mão; sobrevive de um trecho para o outro
    na_mao = {c: None for c in chaves}
    pan = 0.0            # o quanto o fundo já andou; NÃO zera entre trechos
    n_trechos = len(spec["trechos"])
    planos = []
    for i_tr, tr in enumerate(spec["trechos"]):
        pedido = tr.get("cenario") or CENARIOS.escolher(tr.get("fala", ""))
        cen, motivo = CENARIOS.resolver(pedido, inventario, tr.get("fala"))
        if cen is None:
            # fundo chapado é o ÚLTIMO recurso, e agora ele avisa alto. Foi
            # esta cor saindo calada que fez o cenário faltante passar
            # por "cenário ainda não existe" durante duas sessões.
            cen = "_chapado"
            if cen not in cenarios:
                print(f"[cenario] SEM ARTE NENHUMA em "
                      f"{[os.path.normpath(p) for p in pastas_cenario]}; cor chapada")
                cenarios[cen] = Cenario(Image.new("RGB", (W, H), "#A5A893"))
        elif cen not in cenarios:
            cam_path = _achar_arte(pastas_cenario, cen)
            print(f"[cenario] {pedido} -> {cen} ({motivo}): {cam_path}")
            cenarios[cen] = Cenario(Image.open(cam_path))
        elif motivo != "pedido":
            print(f"[cenario] {pedido} -> {cen} ({motivo})")
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
                pers, x0, dy = elenco[chave]
                rig, c = _rig_do_trecho(tr, t, pan, por_ator[chave], x0,
                                        falando=(chave == falante))
                # o deslocamento que põe este ator na linha do chão comum
                # (ver _alinhar_pelos_pes) entra DEPOIS das ações: pular e
                # cair mexem no quadril, e a correção acompanha o pulo
                rig["quadril"] = [rig["quadril"][0], rig["quadril"][1] + dy]
                # a cara de QUEM FALA vem do trecho; quem ouve fica na cara
                # de reação que o roteirista der a ele, ou neutro
                cara = rosto.para(tr, t, tr["dur"], chave) if chave == falante \
                    else EXPR.obter(tr.get("expressao_" + chave, "neutro"))
                pisca = EXPR.piscando(n, FPS, semente=chaves.index(chave),
                                      expr_nome=tr.get("expressao", "neutro")
                                      if chave == falante else "neutro")
                # SÓ QUEM FALA MEXE A BOCA. Sem isto os dois abrem o
                # maxilar na mesma envoltória e ninguém sabe quem falou.
                obj = _objeto_na_mao(por_ator[chave], t, objetos,
                                     na_mao.setdefault(chave, None))
                na_mao[chave] = obj
                camada.alpha_composite(
                    desenhar_personagem(pers, rig, nivel if chave == falante else 0.0,
                                        pisca, obj, cara))
                if chave == falante:
                    cam_falante, x_falante = c, rig["quadril"][0]
            cam = cam_falante
            if chao_y:
                cam["chao_y"] = chao_y
            # ENQUADRAMENTO DO TRECHO, por cima do que a ação já pediu: a
            # ação usa zoom para pontuar um susto, e isso continua valendo
            # -- os dois se multiplicam em vez de um apagar o outro.
            z_tr, zy = _enquadramento(i_tr, n_trechos, len(chaves), t)
            cam["zoom"] = float(cam.get("zoom", 1.0)) * z_tr
            # ação que mira o quadro em outra altura (o `susto` mira 0,34)
            # manda: ela sabe o que está pontuando. Fora isso, vale a altura
            # do plano do trecho.
            if abs(float(cam.get("zoom_y", 0.5)) - 0.5) < 0.001:
                cam["zoom_y"] = zy
            quadro = montar_frame(camada, cenarios[cen], cam, x_falante)
            # a faixa de cima vai ANTES da legenda e depois do zoom: as duas
            # são grudadas na tela, não na cena
            if faixa_topo is not None:
                faixa_topo.desenhar(quadro, n / float(FPS))
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
        planos.append(f"{_enquadramento(i_tr, n_trechos, len(chaves), 0.0)[0]:.2f}")
        pan = cam.get("fundo_dx", pan)              # continua de onde parou
    print(f"[cutout] {n} frames ({n/FPS:.1f}s)")
    print(f"[cara] {' -> '.join(caras)}")
    print(f"[camera] plano por trecho: {' -> '.join(planos)}")

    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
                    "-i", os.path.join(fd, "%05d.png"), "-i", audio,
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
