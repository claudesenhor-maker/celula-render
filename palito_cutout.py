#!/usr/bin/env python3
"""
palito_cutout â€” animaÃ§Ã£o CUT-OUT: arte de IA, movimento por rig.

VocÃª pediu para sair do vetor. Esta Ã© a saÃ­da que cabe no orÃ§amento.

O PROBLEMA COM image-to-video (a rota do vÃ­deo de referÃªncia):
    90 vÃ­deos/mÃªs x 4 planos x 5s = 1.800 segundos
    WAN 2.5 (o mais barato):  US$ 90/mÃªs = R$ 486   -> 7x o orÃ§amento
    Kling 2.6 Pro:            US$126/mÃªs = R$ 680   -> 10x
    Dentro de R$70 cabem 259 segundos animados por mÃªs. Isso Ã© 17 vÃ­deos
    com 3 planos, ou 52 clipes. NÃ£o 90 vÃ­deos.

A SAÃDA â€” cut-out (animaÃ§Ã£o de recorte):
    A IA desenha o personagem UMA VEZ, em partes. O rig move as partes.
    Ã‰ como South Park e boa parte da animaÃ§Ã£o de TV Ã© feita hÃ¡ dÃ©cadas.

    arte:       ~US$ 1 por personagem, uma vez
    cenÃ¡rios:   US$ 0,003 cada
    animaÃ§Ã£o:   grÃ¡tis (PIL, no runner do GitHub)
    total:      ~R$ 7/mÃªs para 90 vÃ­deos

O que muda em relaÃ§Ã£o ao vetor: o personagem deixa de ser desenhado por
cÃ³digo e passa a ser ARTE DE VERDADE â€” cabelo, sombreado, roupa, rosto
ilustrado. O que NÃƒO muda: poses, timing, lipsync, consistÃªncia 100%.
As partes sÃ£o sempre as mesmas imagens.

COMO AS PARTES NASCEM
    NÃ£o se pede peÃ§a por peÃ§a ao gerador -- isso falhou nas 13 tentativas
    de 19/08 e voltaram 13 desenhos de um homem inteiro. Pede-se UMA folha
    do personagem em pose T, e o recorte Ã© feito por geometria em
    fatiar.py. Ver folha_personagem.py para a estrutura de requisitos de
    cada peÃ§a (o que inclui, o que exclui, pivÃ´, orientaÃ§Ã£o, tamanho).

O QUE MUDOU EM 21/08 â€” MOVIMENTO COM CAUSA
    O vÃ­deo de 20/08 nÃ£o tinha movimento, tinha agitaÃ§Ã£o: duas poses
    estÃ¡ticas interpoladas ao longo da fala inteira, mais um seno no
    quadril. O personagem nunca saÃ­a do lugar e nada no texto explicava
    o que ele fazia com os braÃ§os.

    Agora o movimento vem de AÃ‡Ã•ES (acoes.py) -- verbos com janela de
    tempo dentro do trecho e um campo `motivo` que amarra a aÃ§Ã£o Ã  fala.
    Entrou junto o que faltava para "andar" sequer existir:

      * ciclo de passada de verdade (pernas em oposiÃ§Ã£o de fase, joelho
        dobrando para trÃ¡s, quique do centro de massa)
      * CÃ‚MERA: o fundo corre ao contrÃ¡rio do sentido da caminhada, em
        ladrilho espelhado (sem emenda visÃ­vel, deslocamento infinito)
      * personagem desenhado numa CAMADA prÃ³pria, o que permite espelhar
        (virar para o outro lado) e dar zoom sem redesenhar nada
      * gancho obrigatÃ³rio: acoes.garantir_gancho() injeta uma aÃ§Ã£o forte
        nos primeiros segundos se o roteirista nÃ£o puser uma

    Specs antigos (com `pose`/`pose_saida` e sem `acoes`) continuam
    rodando pelo caminho de compatibilidade.

Uso:
    python3 palito_cutout.py --partes ./personagem --spec spec.json -o saida.mp4
"""
import argparse, json, math, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from palito_v4 import REST, POSES, EXPRESSOES, merge, blend, pt
import acoes as ACOES
import expressao as EXPR
import cenarios as CENARIOS
import sfx as SFX
from folha_personagem import (ESQUELETO, ORDEM_Z, FONTE_ANGULO,
                              CORRECAO_POSE_T, SEGUE,
                              ENCAIXE_OMBRO, SUBIR_BRACO_HC)

# repouso da cara: o dicionÃ¡rio completo com todo campo em zero, para que
# desenhar_personagem nunca precise checar chave faltando
EXPR_ZERO = EXPR.CATALOGO["neutro"]

W, H, FPS = 1080, 1920, 24

# altura de referencia do personagem no quadro; objetos sao medidos contra ela
ALTURA_ALVO_PX = 1150

# TAMANHO DE CADA OBJETO, em fraÃ§Ã£o da altura do ator
# ---------------------------------------------------------------------
# Era 11% para todos, e 11% Ã© o tamanho de um CELULAR. O vÃ­deo de 28/08 era
# sobre um boleto e o boleto mal se via: uma folha de papel na mÃ£o de uma
# pessoa ocupa perto de um quarto da altura dela, nÃ£o um dÃ©cimo.
#
# O 11% chapado veio de outro erro na direÃ§Ã£o oposta -- a xÃ­cara saiu do
# tamanho do tronco em 27/08 --, e a correÃ§Ã£o de entÃ£o tratou o sintoma
# escolhendo um nÃºmero pequeno o bastante para nada estourar. O tamanho
# certo Ã© por objeto, e Ã© uma medida que se anota uma vez.
#
# `escala_objeto` na aÃ§Ã£o continua multiplicando isto, para o roteiro poder
# exagerar de propÃ³sito (a chave gigante da esquete da bicicleta).
TAMANHO_OBJETO = {
    "celular":               0.11,
    "chave":                 0.09,
    "xicara_de_cafe":        0.11,
    "carteira":              0.12,
    "controle_remoto":       0.13,
    "boleto":                0.22,   # papel A4 na mÃ£o, pelo lado maior
    "marmita":               0.17,
    "sacola_de_compras":     0.26,
    "caixa_de_papelao":      0.30,
    "guarda_chuva_quebrado": 0.40,   # o Ãºnico que Ã© maior que o tronco
}
TAMANHO_OBJETO_PADRAO = 0.13

# A CÃ‚MERA CORTA, NÃƒO DESLIZA (28/08, noite)
# ---------------------------------------------------------------------
# A primeira versÃ£o da arte panorÃ¢mica veio com uma deriva contÃ­nua: a
# cÃ¢mera percorria a faixa devagar ao longo do vÃ­deo inteiro. O dono do
# projeto recusou -- "o cenÃ¡rio estÃ¡ se movimentando andando para o lado
# sem os personagens andarem". Ele estÃ¡ certo, e o motivo Ã© de linguagem:
# num plano fixo, fundo que anda sÃ³ pode significar uma coisa, que Ã© a
# cÃ¢mera acompanhando alguÃ©m que se move. Com todo mundo parado, o cÃ©rebro
# nÃ£o tem a quem atribuir o movimento e a cena inteira parece escorregar.
#
# A arte comprida continua servindo, por outro caminho: cada TRECHO comeÃ§a
# num ponto diferente dela, e dentro do trecho o fundo fica IMÃ“VEL. Isso
# lÃª como troca de Ã¢ngulo -- um corte --, que Ã© exatamente o que o formato
# nÃ£o tinha, e o corte reseta a atenÃ§Ã£o de quem rola o feed.
#
# As posiÃ§Ãµes nÃ£o avanÃ§am em fila (0,2 â†’ 0,4 â†’ 0,6 seria um travelling
# picotado, com o mesmo defeito de leitura): elas saltam de um lado ao
# outro da faixa, como plano e contraplano.
# DEZESSEIS PONTOS (30/08). Eram oito, escolhidos quando a esquete tinha
# cinco ou seis trechos. Com o formato de 40 a 80 s ela tem de 8 a 16, e a
# partir do nono trecho a cÃ¢mera voltava para o ponto do primeiro: num
# vÃ­deo de 13 trechos o fundo se repetia cinco vezes. A lista tem agora um
# ponto por trecho possÃ­vel, e continua saltando de um lado ao outro da
# faixa -- avanÃ§ar em fila Ã© um travelling picotado (lei 26).
PONTOS_DE_CORTE = (0.50, 0.18, 0.74, 0.34, 0.90, 0.08, 0.62, 0.26,
                   0.82, 0.42, 0.14, 0.70, 0.30, 0.96, 0.56, 0.04)

# quantos personagens cabem no quadro ao mesmo tempo. Dois Ã© o teto do
# formato: no 9:16 o terceiro sÃ³ entra encolhendo todo mundo atÃ© a cara
# sumir, e cara Ã© onde a piada acontece.
MAX_EM_CENA = 2


# =====================================================================
# ComposiÃ§Ã£o: girar em torno do pivÃ´ e colar no destino
# =====================================================================
# A MESMA PEÃ‡A, NA MESMA ESCALA, TODO FRAME (29/08). `escala` Ã© a escala
# do personagem: 0,74 com dois em cena, e ela nÃ£o muda durante o render.
# Sem cache, cada uma das ~20 peÃ§as era reduzida com LANCZOS a cada frame
# -- 16 mil reduÃ§Ãµes idÃªnticas num vÃ­deo de 800 frames, e LANCZOS Ã© o
# reamostrador mais caro que existe no Pillow (Ã© o certo aqui: reduzir arte
# de traÃ§o com um filtro barato serrilha o contorno).
#
# A chave guarda a imagem ORIGINAL junto: sem isso a chave seria um id()
# de objeto que pode ser coletado e reciclado, e o cache devolveria a peÃ§a
# de outra coisa. O teto existe porque `cranio_com_cara` produz uma imagem
# por expressÃ£o -- poucas, mas nÃ£o uma sÃ³.
_CACHE_ESCALA = {}
_TETO_CACHE_ESCALA = 400


def _reamostrar(img, tam):
    """Redimensiona escolhendo o filtro pelo SENTIDO da conta (30/08).

    A LINHA BRANCA EM VOLTA DO PERSONAGEM saÃ­a daqui. LANCZOS tem lÃ³bulos
    NEGATIVOS: onde um traÃ§o preto encosta num fundo claro, ele passa do
    valor do vizinho claro e desenha uma linha mais clara que o prÃ³prio
    fundo colada no contorno -- o overshoot clÃ¡ssico de filtro com janela.
    Num quadro inteiro isso vira um fio esbranquiÃ§ado contornando cada
    peÃ§a do boneco e cada mÃ³vel do cenÃ¡rio.

    Por que sÃ³ apareceu agora: enquanto o plano de cÃ¢mera era 1,00 nÃ£o
    havia conta nenhuma -- `montar_frame` devolvia o quadro como ele foi
    desenhado. Desde que `_enquadramento` (27/08) passou a dar um plano
    diferente a cada trecho, quase todo frame do vÃ­deo Ã© uma AMPLIAÃ‡ÃƒO de
    1,05 a 1,30, e o halo passou a existir do primeiro ao Ãºltimo quadro.

    Medido num recorte do Pal ampliado 1,25x, contando pixels mais claros
    que o fundo colados no traÃ§o preto: LANCZOS 204, BICUBIC 179,
    BILINEAR 46. Bilinear nÃ£o tem lÃ³bulo negativo -- ele nÃ£o consegue
    inventar um valor fora do intervalo dos vizinhos, entÃ£o o halo que
    sobra Ã© sÃ³ a mistura honesta do traÃ§o com o fundo.

    REDUZINDO, LANCZOS continua sendo o certo: Ã© onde ele preserva o traÃ§o
    em vez de serrilhÃ¡-lo (arte de contorno reduzida com filtro barato
    pisca entre frames), e ali o overshoot cai dentro do prÃ³prio traÃ§o,
    onde ninguÃ©m vÃª."""
    if tuple(tam) == img.size:
        return img
    ampliando = tam[0] > img.width or tam[1] > img.height
    return img.resize(tuple(tam), Image.BILINEAR if ampliando else Image.LANCZOS)


def _na_escala(img, escala):
    if escala == 1.0:
        return img
    chave = (id(img), round(escala, 4))
    achado = _CACHE_ESCALA.get(chave)
    if achado is not None and achado[0] is img:
        return achado[1]
    if len(_CACHE_ESCALA) >= _TETO_CACHE_ESCALA:
        _CACHE_ESCALA.clear()
    p = _reamostrar(img, (max(int(img.width * escala), 1),
                          max(int(img.height * escala), 1)))
    _CACHE_ESCALA[chave] = (img, p)
    return p


def colar(base, img, pivot, destino, ang, escala=1.0, espelhar=False):
    """Gira `img` em torno de `pivot` e cola de modo que o pivÃ´ caia em `destino`.

    Ã‰ a operaÃ§Ã£o inteira da animaÃ§Ã£o cut-out. Todo o resto Ã© decidir
    quais Ã¢ngulos passar."""
    p = img
    if espelhar:
        p = p.transpose(Image.FLIP_LEFT_RIGHT)
        pivot = (p.width - pivot[0], pivot[1])
    if escala != 1.0:
        p = _na_escala(p, escala)
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
    """A cor do contorno da peÃ§a, amostrada da prÃ³pria arte.

    Cravar preto funcionaria para o Pal e quebraria no primeiro personagem
    com contorno colorido. A casca Ã© o anel de fora do alfa; a mediana dele
    Ã© a cor da linha."""
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


def _cor_de_dentro(img, ponto=None, raio=26):
    """A cor do PREENCHIMENTO da peÃ§a, perto de `ponto`.

    POR QUE (02/09, item 6 do dono do projeto)
        `_fechar_vao` pintava o anel com a cor do CONTORNO, e o resultado
        na tela Ã© uma faixa escura em toda junta -- o joelho, o punho e o
        quadril da Maria leem como tiras sobre a calÃ§a clara. A queixa foi
        literal: *"linhas muito grossas nos personagens"*.

        O anel existe para as duas peÃ§as vizinhas se SOBREPOREM, nÃ£o para
        desenhar linha. Pintado com a cor de dentro, o vÃ£o fecha com a cor
        do braÃ§o ou da calÃ§a, o contorno preto que a arte jÃ¡ tem continua
        por cima, e a junta lÃª como membro contÃ­nuo -- que Ã© como cut-out
        de verdade emenda duas peÃ§as.

    Amostrada PERTO DA JUNTA e nÃ£o na peÃ§a inteira: uma calÃ§a com barra de
    outra cor, ou uma manga sobre pele, tem duas cores, e a que interessa Ã©
    a que estÃ¡ encostando na vizinha. Sem ponto, Ã© a mediana do miolo.
    """
    a = np.asarray(img.convert("RGBA"))
    al = a[..., 3]
    miolo = np.asarray(img.split()[3].filter(ImageFilter.MinFilter(7))) > 128
    if not miolo.any():
        miolo = al > 128
    if not miolo.any():
        return (200, 200, 200)
    lum = a[..., :3].astype(np.float32).mean(axis=2)
    # o contorno fica de fora: o que se quer Ã© a cor de dentro, e num
    # desenho de traÃ§o grosso o preto domina a mediana se entrar na conta
    claro = miolo & (lum > 90)
    alvo = claro if claro.sum() > 40 else miolo
    if ponto is not None:
        ys, xs = np.nonzero(alvo)
        d = (xs - ponto[0]) ** 2 + (ys - ponto[1]) ** 2
        perto = d <= raio * raio * 4
        if perto.sum() > 30:
            return tuple(int(v) for v in
                         np.median(a[ys[perto], xs[perto]][:, :3], axis=0))
    return tuple(int(v) for v in np.median(a[alvo][:, :3], axis=0))


def _e_fiapo(img, limiar=0.22):
    """A peÃ§a Ã© uma mancha cheia ou um pedaÃ§o de contorno?

    Mesma rÃ©gua de folha_personagem.conferir_rosto: feiÃ§Ã£o de verdade
    ocupa boa parte da prÃ³pria caixa; fiapo de contorno ocupa quase nada."""
    a = np.asarray(img.convert("RGBA"))[..., 3] > 10
    return (a.sum() / max(a.size, 1)) < limiar


def _analisar_rosto(img):
    """Onde estÃ¡ o ROSTO dentro da peÃ§a do crÃ¢nio, medido pelos OLHOS.

    POR QUE (a boca da Maya saiu no pescoÃ§o, 27/08)
        AtÃ© aqui as trÃªs funÃ§Ãµes de rosto (`_tapar_entalhe`,
        `_tapar_boca_desenhada`, `_extrair_feicoes`) usavam a caixa da PEÃ‡A
        como rÃ©gua: a boca era "o traÃ§o deitado entre 52% e 92% da altura
        da peÃ§a", a feiÃ§Ã£o era "o que estÃ¡ na metade de cima". Isso vale
        enquanto a peÃ§a do crÃ¢nio for o rosto e mais nada.

        Ela nÃ£o Ã©. Na Maya o crÃ¢nio traz cabelo comprido atÃ© abaixo do
        queixo E o pescoÃ§o inteiro: 62% da altura da peÃ§a cai na altura do
        NARIZ, e o terÃ§o de baixo Ã© pescoÃ§o e gola. `_tapar_entalhe` achou
        ali o vazio entre as duas mechas de cabelo, tomou-o por entalhe de
        boca e pÃ´s a boca animada no pescoÃ§o dela -- com a boca desenhada
        continuando parada no rosto, porque ninguÃ©m foi procurÃ¡-la.

        No Zeca o mesmo erro de rÃ©gua produziu outro sintoma: as
        sobrancelhas grisalhas tÃªm pixel claro e pixel escuro na mesma
        mancha, que era a definiÃ§Ã£o de OLHO, e passaram a ser animadas como
        olhos -- o piscar desenhava um traÃ§o na testa. Os olhos de verdade
        estÃ£o fundidos ao aro do Ã³culos numa mancha que atravessa a cara, e
        eram descartados por tamanho.

        A rÃ©gua certa nÃ£o Ã© fraÃ§Ã£o de peÃ§a nenhuma: Ã© o par de OLHOS. Todo
        rosto frontal tem dois, simÃ©tricos, e a distÃ¢ncia entre eles Ã© a
        Ãºnica medida que dÃ¡ a escala do rosto sem depender de cabelo, de
        pescoÃ§o ou de quanto da figura o desenhista pÃ´s na peÃ§a. Com ela,
        boca e sobrancelha se procuram onde elas ficam num rosto -- e nÃ£o
        onde ficariam se a peÃ§a fosse sÃ³ a cara.

    COMO se acham os olhos sem limiar inventado
        Pela ESCLERA: em arte cut-out o branco do olho Ã© o ponto mais claro
        do rosto, mais claro que a pele por construÃ§Ã£o (Ã© o que faz a pupila
        ler como pupila). Manchas claras dentro do nÃºcleo, pareadas por
        SIMETRIA em torno do eixo da peÃ§a -- mesma altura, mesma Ã¡rea,
        distÃ¢ncias iguais ao eixo. Cabelo grisalho nÃ£o Ã© mais claro que a
        pele e nÃ£o forma par simÃ©trico com nada; sobrancelha nÃ£o tem branco.

        O olho inteiro Ã© o componente de tinta que CONTÃ‰M a esclera (a
        esclera, a pupila e o traÃ§o em volta saem como uma mancha sÃ³). Se
        esse componente for grande demais para ser um olho -- o caso do
        Ã³culos do Zeca --, o olho Ã© a esclera dilatada: recorta-se o globo
        de dentro do aro, que continua desenhado no crÃ¢nio. Ã‰ o que um
        animador faria com a mesma arte.

    Devolve None quando nÃ£o hÃ¡ par de olhos (e aÃ­ cada funÃ§Ã£o cai na rÃ©gua
    antiga, que Ã© o comportamento de antes desta correÃ§Ã£o). SenÃ£o, um dict
    com as mÃ¡scaras jÃ¡ calculadas -- `pele`, `tinta`, `nucleo`, `lum` -- e a
    geometria do rosto: `eixo`, `linha_olhos`, `d_olhos`, `queixo`, e
    `olhos` com a mÃ¡scara e a caixa de cada um.
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

    # o raio de erosÃ£o sai do tamanho do desenho, nÃ£o da tela: `_centralizar`
    # infla a peÃ§a atÃ© um quadrado que caiba qualquer rotaÃ§Ã£o
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
    # abaixo de 690. Cravar 620 (a versÃ£o anterior) deixava passar o cabelo
    # grisalho do Zeca, que tem 600 de luminÃ¢ncia contra 612 da pele; exigir
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
                continue          # o par tem que abraÃ§ar o eixo do desenho
            razao = min(e["area"], d["area"]) / float(max(e["area"], d["area"]))
            if razao < 0.45:
                continue          # dois olhos do mesmo rosto tÃªm o mesmo tamanho
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
            # o componente que contÃ©m a esclera sÃ³ Ã© o olho se tiver tamanho
            # de olho; o aro do Ã³culos atravessa o rosto e reprova aqui
            if cw <= max(lw * 3.0, larg_p * 0.30) and ch <= max(lh * 3.5, larg_p * 0.30):
                m = c["mask"].copy()
            break
        if m is None:
            # sem componente aproveitÃ¡vel, o olho Ã© a prÃ³pria esclera com uma
            # folga: o globo sai de dentro do aro e o aro fica no crÃ¢nio
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

    # A COR DA PELE SAI DO ROSTO, NÃƒO DA PEÃ‡A INTEIRA (30/08)
    #
    # `pele`, lÃ¡ em cima, Ã© a cor mais frequente do nÃºcleo -- e o nÃºcleo Ã© a
    # peÃ§a do crÃ¢nio, que traz o que o desenhista pÃ´s nela. Na enfermeira
    # sÃ£o touca, coque e cabelo dos dois lados: a cor dominante deu
    # [108,84,60], que Ã© o CABELO. Com a pele errada, `tinta` sai invertida
    # -- a face clara inteira vira uma mancha de tinta e as sobrancelhas,
    # castanhas e vizinhas do cabelo, ficam de fora. Resultado: 2/4 feiÃ§Ãµes,
    # olhos que se mexem e sobrancelhas paradas.
    #
    # Ã‰ a lei 13 aplicada a mais um lugar: nada do rosto pode ser medido em
    # fraÃ§Ã£o da peÃ§a. Agora que os olhos existem, a pele se amostra ONDE ELA
    # ESTÃ -- a faixa entre os olhos e logo abaixo deles, que Ã© bochecha e
    # nariz em qualquer cara. Se a cor mudar, `tinta` e os componentes sÃ£o
    # refeitos com ela.
    fy0 = int(max(0, linha))
    fy1 = int(min(nucleo.shape[0], linha + max(d_olhos * 0.9, 4)))
    fx0 = int(max(0, eixo - d_olhos * 0.45))
    fx1 = int(min(nucleo.shape[1], eixo + d_olhos * 0.45))
    janela = np.zeros_like(nucleo)
    janela[fy0:fy1, fx0:fx1] = True
    janela &= nucleo
    if janela.sum() >= 40:
        qf = (rgb[janela] // 24)
        cf, nf = np.unique(qf.reshape(-1, 3), axis=0, return_counts=True)
        pele_rosto = cf[nf.argmax()].astype(np.int16) * 24 + 12
        if np.abs(pele_rosto - pele).sum() > 60:
            print(f"[rosto] a cor dominante da peÃ§a era {tuple(int(v) for v in pele)} "
                  f"(cabelo ou touca); a pele medida no rosto e "
                  f"{tuple(int(v) for v in pele_rosto)}")
            pele = pele_rosto
            tinta = nucleo & (np.abs(rgb - pele).sum(axis=2) > 90)
            if tinta.sum() >= 40:
                comps_tinta = _componentes(
                    tinta, area_min=max(20, int(tinta.sum() * 0.005)))

    # --- atÃ© onde desce o rosto -------------------------------------------
    # O queixo Ã© onde a mancha de pele ESTRANGULA: abaixo dele vem o pescoÃ§o,
    # que Ã© mais estreito por definiÃ§Ã£o de pescoÃ§o. Medir isso Ã© o que impede
    # a boca de ser procurada no colo -- e sai da arte, sem proporÃ§Ã£o
    # inventada. Quando o desenhista fecha o queixo com traÃ§o, a mancha jÃ¡
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
    """Onde a boca pode estar: (y_min, y_max, eixo, tolerÃ¢ncia em x).

    Num rosto a boca fica entre o nariz e o queixo, no eixo. Com o par de
    olhos medido, isso deixa de ser fraÃ§Ã£o da peÃ§a e passa a ser fraÃ§Ã£o da
    distÃ¢ncia entre os olhos -- a rÃ©gua do prÃ³prio rosto. Medida nas trÃªs
    folhas de produÃ§Ã£o, a boca cai a 0,77, 0,78 e 0,81 distÃ¢ncia interocular
    abaixo da linha dos olhos: Ã© a proporÃ§Ã£o mais estÃ¡vel do rosto, e a
    faixa de 0,45 a 1,35 a cobre com folga em qualquer estilo de desenho.

    O QUEIXO MEDIDO sÃ³ entra como teto quando Ã© plausÃ­vel. Ele vem do
    estrangulamento da mancha de pele, e essa mancha pode terminar na
    prÃ³pria linha da boca quando o desenhista a fecha de lado a lado -- foi
    o que aconteceu com o bigode do Zeca, e usar aquele queixo como teto
    apagava a boca da lista de candidatas. Abaixo de uma distÃ¢ncia
    interocular do olho nÃ£o existe queixo de rosto nenhum."""
    d = rosto["d_olhos"]
    linha = rosto["linha_olhos"]
    y_min = linha + d * 0.45
    y_max = linha + d * 1.35
    if rosto["queixo"] > linha + d * 1.0:
        y_max = min(y_max, rosto["queixo"])
    return y_min, y_max, rosto["eixo"], d * 0.55


def _tapar_entalhe(img, cor=None, rosto=None):
    """Fecha o RECORTE DA BOCA no crÃ¢nio, com a cor da prÃ³pria pele.

    POR QUE (o defeito nÂº 1 do projeto, e a causa real dele)
        A folha do Pal desenha a boca como um ENTALHE VAZADO no crÃ¢nio: um
        buraco em U aberto na base da cabeÃ§a, que existe para o segmentador
        poder separar o queixo. O queixo deveria tapÃ¡-lo -- Ã© a mandÃ­bula
        que fica ali, e ela desce quando a boca abre.

        SÃ³ que nesta folha a mandÃ­bula nÃ£o foi segmentada: saiu um punhado
        de pixels soltos. O entalhe ficou permanentemente aberto, o motor
        pintou o interior de boca dentro dele, e o personagem passou todos
        os vÃ­deos parecendo que grita. O HANDOFF registrava isso como
        "defeito de arte: a boca estÃ¡ desenhada aberta". EstÃ¡ mais perto de
        ser verdade que a boca estÃ¡ desenhada FECHADA e Ã© a peÃ§a que a
        fecharia que nÃ£o existe.

        Enquanto a folha nova nÃ£o chega, tapar o entalhe com a cor da pele
        devolve uma cara de boca fechada. O custo Ã© nÃ£o haver lipsync de
        queixo -- que jÃ¡ nÃ£o havia, porque nÃ£o hÃ¡ queixo.

    Como: o entalhe Ã© uma reentrÃ¢ncia estreita e profunda. Um FECHAMENTO
    morfolÃ³gico (dilata e depois erode) preenche reentrÃ¢ncia estreita e
    devolve o contorno externo intacto. O que o fechamento acrescentou Ã©
    exatamente a Ã¡rea do entalhe.

    Tapar SÃ“ o vazio nÃ£o bastou: o entalhe tem contorno preto prÃ³prio (Ã© o
    lÃ¡bio superior desenhado), e preencher o buraco deixava um retÃ¢ngulo de
    pele cercado por um U preto -- lia como queixo quadrado. EntÃ£o a tapa
    cobre o vazio MAIS o traÃ§o em volta dele, e quem devolve a boca Ã©
    `_boca_desenhada`. A cara termina lisa, e a boca passa a ser desenhada
    onde o desenhista pÃ´s a dele.

    Devolve (peÃ§a tapada, caixa da boca em coordenadas da peÃ§a).
    """
    from PIL import ImageChops
    from segmentar import _componentes
    alfa = img.split()[3]
    r = max(3, int(min(img.width, img.height) * 0.11))
    # dilatar+erodir com o MESMO raio: o contorno externo volta ao lugar,
    # a reentrÃ¢ncia nÃ£o
    fechado = alfa.filter(ImageFilter.MaxFilter(2 * r + 1)) \
                  .filter(ImageFilter.MinFilter(2 * r + 1))
    novo = ImageChops.subtract(fechado, alfa)
    arr = np.asarray(novo) > 8
    if arr.sum() < 10:
        return img, None

    # QUAL das reentrÃ¢ncias Ã© a boca. O fechamento preenche TODAS: o vÃ£o
    # entre a orelha e a cabeÃ§a, o recorte em V da franja, o entalhe do
    # queixo. Usar a uniÃ£o (a primeira versÃ£o desta funÃ§Ã£o) pÃµe a "boca" no
    # meio da testa e cobre metade do cabelo de pele -- foi exatamente o que
    # saiu no primeiro teste. A boca Ã© a reentrÃ¢ncia do TERÃ‡O DE BAIXO,
    # perto do eixo do rosto, e Ã© a maior de lÃ¡.
    ys_, xs_ = np.nonzero(np.asarray(alfa) > 8)
    cx_rosto, y_base = float(xs_.mean()), float(ys_.max())
    alt_peca = float(ys_.max() - ys_.min() + 1)
    todos = _componentes(arr, area_min=max(int(arr.sum() * 0.05), 40))
    if rosto:
        # COM OS OLHOS MEDIDOS a faixa Ã© a do rosto, nÃ£o a da peÃ§a. Ã‰ o que
        # impede o vazio entre as mechas de cabelo da Maya -- que fica no
        # pescoÃ§o, dois terÃ§os abaixo dos olhos dela -- de ser lido como
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
    # fora da prÃ³pria peÃ§a: dilatar sem essa trava comeria o queixo
    g = max(2, int((by1 - by0 + 1) * 0.22))
    larga = so_boca.filter(ImageFilter.MaxFilter(2 * g + 1))
    larga = ImageChops.multiply(larga, fechado)
    # A tapa nÃ£o pode passar da coluna do entalhe. Sem esta trava ela
    # crescia para os lados e apagava o contorno da bochecha na altura da
    # boca -- um buraco no perfil do rosto, visÃ­vel em close.
    faixa = np.zeros(np.asarray(larga).shape, dtype=np.uint8)
    faixa[:, max(0, bx0 - g):min(img.width, bx1 + g + 1)] = 255
    larga = ImageChops.multiply(larga, Image.fromarray(faixa))
    # E NUNCA COME O CONTORNO EXTERNO. O entalhe da boca desce atÃ© a base do
    # queixo, e a tapa levava junto o traÃ§o preto de lÃ¡: o rosto ficava com
    # o queixo aberto, sem linha, como se a cabeÃ§a vazasse para o pescoÃ§o.
    # Erodir o alfa pela espessura do traÃ§o deixa o anel de contorno fora do
    # alcance da tapa.
    # Erode-se a SILHUETA FECHADA, nÃ£o o alfa: o entalhe Ã© um vazio, e
    # erodir o alfa protegeria justamente a borda dele -- que Ã© o que a
    # tapa precisa cobrir. O fechamento jÃ¡ nÃ£o tem o entalhe, entÃ£o o que
    # sobra protegido Ã© sÃ³ o perÃ­metro de fora.
    esp_traco = max(2, int(min(img.width, img.height) * 0.022))
    larga = ImageChops.multiply(
        larga, fechado.filter(ImageFilter.MinFilter(2 * esp_traco + 1)))

    # COR AMOSTRADA AO REDOR DO ENTALHE, nÃ£o a mediana da peÃ§a inteira: a
    # bochecha tem sombreado prÃ³prio, e a mediana global deixava um
    # retÃ¢ngulo de tom diferente em volta da boca.
    # PREENCHIMENTO PELA COR DA BOCHECHA AO LADO. Duas outras tentativas
    # ficaram piores e vale registrar por quÃª:
    #   * mediana da peÃ§a inteira -> retÃ¢ngulo de tom errado em volta da
    #     boca, porque a peÃ§a inclui cabelo, olhos e contorno;
    #   * propagaÃ§Ã£o coluna a coluna a partir do pixel de cima -> o que estÃ¡
    #     logo acima do entalhe Ã© o sulco do nariz, mais claro que o queixo,
    #     e a tapa saÃ­a luminosa demais (visÃ­vel no teste de 28/08).
    # A vizinhanÃ§a LATERAL do entalhe Ã© a prÃ³pria bochecha, no tom exato.
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

    # SOMBREADO, E NÃƒO COR CHAPADA. Uma cor sÃ³ deixa um retÃ¢ngulo mais claro
    # no queixo -- ele aparece em todos os frames do vÃ­deo de 28/08, e foi a
    # segunda queixa sobre o rosto. O queixo do Pal escurece de cima para
    # baixo; a bochecha, de onde a cor Ã© amostrada, nÃ£o. Preencher cada
    # coluna interpolando entre o pixel logo ACIMA e o logo ABAIXO da tapa
    # reproduz o gradiente que a arte tem naquele ponto, em vez de inventar
    # um tom mÃ©dio para a Ã¡rea inteira.
    # Coluna a coluna NÃƒO serve: o que estÃ¡ logo acima da tapa Ã© ora pele,
    # ora o traÃ§o escuro do lÃ¡bio, e a tapa sai listrada de vertical (foi a
    # primeira tentativa, conferida em 29/08). O gradiente Ã© medido uma vez,
    # entre a MÃ‰DIA da pele acima e a MÃ‰DIA da pele abaixo do remendo, e
    # aplicado Ã  Ã¡rea inteira.
    ys_m, _xs_m = np.nonzero(m)
    if len(ys_m):
        ya, yb = int(ys_m.min()), int(ys_m.max())
        # Amostrar o pixel ACIMA e o ABAIXO do remendo para montar o
        # gradiente foi tentado e sai pior: os dois vizinhos sÃ£o o traÃ§o do
        # lÃ¡bio e o contorno do queixo, e a tapa saiu cinza-esverdeada
        # (medido em 29/08: 200,184,159 contra os 220,204,184 da bochecha).
        # A bochecha Ã© a Ãºnica vizinhanÃ§a que Ã© pele de verdade -- entÃ£o a
        # cor vem dela, e o sombreado Ã© uma queda suave de 6% atÃ© a base,
        # que Ã© o que um queixo faz e o que tira o aspecto de adesivo.
        n = max(1, yb - ya)
        k = ((np.arange(img.height) - ya) / float(n)).clip(0.0, 1.0)
        escala = (1.0 - 0.06 * k)[ys_m][:, None]
        a[m, :3] = (np.array(pele, dtype=np.float32)[None, :] * escala).astype(np.uint8)
    tapado = Image.fromarray(a)

    # borda macia: mesmo com a cor certa, a emenda dura entrega o remendo.
    # Dois pixels de desvanecimento bastam.
    # 5 Ã© o ponto de equilÃ­brio medido em 28/08: com 2 a emenda aparecia como
    # borda dura; com 9 a tapa fica translÃºcida na borda e o traÃ§o preto do
    # entalhe reaparece por baixo dela.
    suave = Image.composite(tapado, img, larga.filter(ImageFilter.GaussianBlur(5)))
    return suave, caixa


# FraÃ§Ã£o da LARGURA da boca a que ela chega quando aberta ao mÃ¡ximo. Ver o
# comentÃ¡rio na chamada, em `desenhar_personagem`.
BOCA_ABERTURA_MAX = float(os.environ.get("BOCA_ABERTURA_MAX", "0.30"))

# QUANTO DA CURVA DE REPOUSO DESENHADA NA FOLHA ENTRA NA BOCA DE CADA
# EXPRESSÃƒO. Era 1,0 -- somada inteira --, e como toda folha do elenco Ã©
# desenhada sorrindo (+0,85 a +1,00), ela empurrava as doze expressÃµes para o
# sorriso e saturava quatro delas no mesmo desenho. Ver o comentÃ¡rio longo em
# `desenhar_personagem`, onde a conta Ã© feita.
PESO_BOCA_DA_ARTE = float(os.environ.get("PESO_BOCA_DA_ARTE", "0.25"))


def _boca_desenhada(larg, alt_max, nivel, curva, cor_traco, cor_dentro=None,
                    espessura=None):
    """A boca, quando a folha nÃ£o traz queixo articulado.

    Ã‰ a Ãºnica coisa do personagem desenhada por cÃ³digo, e Ã© assim de
    propÃ³sito: a bÃ­blia visual define a boca como "one single short line,
    lips together", e uma linha Ã© justamente o que dÃ¡ para desenhar sem
    inventar estilo. O resto do personagem continua sendo arte.

    O que ela sabe fazer, e por que cada um importa:
      * FECHAR. Em repouso Ã© um traÃ§o. Ã‰ o defeito nÂº 1 do projeto: sem
        isto o Pal passa o vÃ­deo inteiro parecendo que grita.
      * ABRIR com o som. `nivel` vem da mesma envoltÃ³ria do Ã¡udio que
        movia o maxilar, entÃ£o o lipsync volta a existir sem queixo.
      * CURVAR. `curva` positivo sorri, negativo entristece -- o que a
        peÃ§a de queixo, sozinha, nunca conseguiu fazer.

    Desenhada numa telinha prÃ³pria e colada como qualquer outra peÃ§a: aÃ­
    ela gira com a cabeÃ§a de graÃ§a."""
    cor_dentro = cor_dentro or COR_BOCA
    larg = max(6, int(larg))
    alt = max(3, int(alt_max * max(0.0, min(1.0, nivel))))
    # espessura: a medida da linha que a arte tinha, quando existe. A
    # fraÃ§Ã£o da largura Ã© o palpite de quando nÃ£o hÃ¡ arte de boca nenhuma.
    esp = max(2, int(espessura if espessura else larg * 0.065))
    # O TRAÃ‡O Ã‰ FINO, E FINO Ã‰ UM TETO (31/08, pedido do dono do projeto ao
    # ver os vÃ­deos: *"boca com traÃ§o preto em volta; retorne a boca de
    # antes, sÃ³ um traÃ§o fino"*).
    #
    # A espessura medida Ã© a altura MÃ‰DIA da mancha que o desenhista fez, e
    # num traÃ§o encorpado ela dÃ¡ 9px numa boca de 79 -- 11% da largura. Numa
    # LINHA isso ainda passa; desenhada como contorno de elipse, vira um
    # anel preto que ocupa a boca inteira e o rosto fica com um buraco
    # emoldurado no meio. A medida continua mandando enquanto for fina; o
    # teto Ã© 5,5% da largura da boca (4px numa boca de 79), que Ã© a
    # espessura de traÃ§o do resto do desenho.
    esp = max(2, min(esp, int(round(larg * 0.055))))
    # SINAL: y cresce para baixo, entÃ£o sorriso (curva > 0) tem que empurrar
    # o MEIO da linha para baixo. A primeira versÃ£o fazia o contrÃ¡rio e
    # `sorrindo` saÃ­a com cara de choro.
    arco = -curva * larg * 0.16                     # flecha da curva
    pad = int(esp * 2 + abs(arco) + 4)
    tela = Image.new("RGBA", (larg + 2 * pad, int(alt) + 2 * pad + int(abs(arco) * 2)),
                     (0, 0, 0, 0))
    d = ImageDraw.Draw(tela)
    cy = tela.height / 2.0
    x0, x1 = pad, pad + larg

    # QUANDO ELA AINDA Ã‰ UMA LINHA. Era `alt <= esp*1.2`, isto Ã©, o limiar
    # descia junto com a espessura -- e com o traÃ§o fino do teto acima a
    # boca passaria a ABRIR com qualquer sopro de som, o que troca o defeito
    # do anel grosso pelo de uma cara de espanto permanente. O limiar passa
    # a ser tambÃ©m uma fraÃ§Ã£o da abertura MÃXIMA: abaixo de um quarto dela,
    # o que existe Ã© um traÃ§o.
    if alt <= max(esp * 1.2, alt_max * 0.25):
        # BOCA FECHADA: um arco fino. TrÃªs pontos e uma curva quadrÃ¡tica
        # aproximada por segmentos -- ImageDraw nÃ£o tem BÃ©zier, e uma
        # parÃ¡bola de 24 segmentos Ã© indistinguÃ­vel numa boca de 60px.
        pts = []
        for i in range(25):
            u = i / 24.0
            pts.append((x0 + (x1 - x0) * u,
                        cy - arco * 4 * u * (1 - u)))
        d.line(pts, fill=cor_traco + (255,), width=esp, joint="curve")
    else:
        # BOCA ABERTA: elipse com o interior escuro e o mesmo traÃ§o em volta.
        # O centro desce um pouco com a abertura, como um queixo desceria.
        cyy = cy + alt * 0.18 - arco * 0.5
        caixa = [x0, cyy - alt / 2.0, x1, cyy + alt / 2.0]
        # O CONTORNO DA BOCA ABERTA Ã‰ MAIS FINO QUE O DA FECHADA. Na fechada
        # o traÃ§o Ã‰ a boca; na aberta ele Ã© sÃ³ a borda do buraco, e o
        # `width` do PIL cresce para DENTRO -- num vÃ£o de 24px de altura, um
        # contorno de 4px come um terÃ§o dele de cada lado. Metade da
        # espessura desenha a borda sem apagar o buraco.
        d.ellipse(caixa, fill=cor_dentro, outline=cor_traco + (255,),
                  width=max(1, int(round(esp * 0.5))))
    return tela, (tela.width / 2.0, cy)


def _extrair_feicoes(img, piv, rosto=None):
    """Recorta olhos e sobrancelhas de DENTRO da peÃ§a do crÃ¢nio.

    POR QUE (o defeito nÂº 3 da lista de 29/08: "adicionar expressÃµes faciais")
        expressao.py existe desde 28/08 e o rosto continuou parado. A causa
        nÃ£o estava nele: a folha do Pal nÃ£o entrega olho nem sobrancelha
        como peÃ§a. O segmentador devolve `olho_e` com 11x21 px e
        `sobrancelha_d` com 59x15 -- fiapos do contorno --, o carregador os
        descarta com razÃ£o, e sobra um `cranio` de 215x210 com o rosto
        inteiro desenhado dentro. Ou seja: `sobrancelha_rot` e `olho_sy`
        eram aplicados a peÃ§as que nÃ£o estavam em cena, e a Ãºnica coisa que
        se mexia na cara era a inclinaÃ§Ã£o da cabeÃ§a.

        Gerar uma folha nova com feiÃ§Ãµes separadas Ã© a soluÃ§Ã£o de arte, e
        ela estÃ¡ em aberto desde 27/08 (Â§7.1 do HANDOFF) porque o gerador
        nÃ£o desenha os vÃ£os. Enquanto isso, as feiÃ§Ãµes ESTÃƒO desenhadas --
        sÃ³ que dentro de outra peÃ§a. RecortÃ¡-las de lÃ¡ Ã© a mesma manobra
        que a boca jÃ¡ usa: nada Ã© inventado por cÃ³digo, sÃ³ se move o que o
        desenhista entregou.

    COMO (reescrito em 27/08 -- ver `_analisar_rosto`)
        Os OLHOS jÃ¡ vÃªm medidos: `_analisar_rosto` os acha pela esclera e os
        valida por simetria, o que vale para qualquer folha. Aqui sÃ³ se
        recorta o que ele apontou.

        A SOBRANCELHA Ã© o par de manchas logo ACIMA dos olhos, uma de cada
        lado do eixo, mais larga que alta e do tamanho de um olho. A rÃ©gua
        anterior -- "quase toda escura" -- era um limiar de cor e reprovava
        a sobrancelha loira da Maya (48% de pixel escuro contra os 55%
        exigidos) enquanto aprovava o cabelo grisalho do Zeca. PosiÃ§Ã£o e
        tamanho relativos ao olho nÃ£o dependem da cor que o desenhista
        escolheu.

        Sem par de olhos nÃ£o se recorta nada: detecÃ§Ã£o errada aqui apaga
        metade do rosto, e o motor sabe seguir com a cara parada.

    Devolve (crÃ¢nio com as feiÃ§Ãµes apagadas, {nome: sprite}) ou (img, None).
    Cada sprite: {"img": RGBA recortado, "dx","dy": centro da feiÃ§Ã£o
    relativo ao PIVÃ” da peÃ§a, "larg","alt"}. Relativo ao pivÃ´, e nÃ£o ao
    centro da imagem, porque a peÃ§a do crÃ¢nio ainda vai ser recomposta com
    o cabelo depois disto -- o centro muda, o pivÃ´ nÃ£o.
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
            continue                        # Ã© o prÃ³prio olho
        # ACIMA do olho e perto dele: mais de uma distÃ¢ncia interocular acima
        # da linha dos olhos jÃ¡ Ã© franja, nÃ£o sobrancelha
        if not (linha - d_olhos * 1.30 <= reg["cy"] <= alvo["cy"] - reg["h"] * 0.3):
            continue
        # do lado certo, e nÃ£o em cima do eixo (a ruga da testa do Zeca fica
        # no meio da cara e passaria por sobrancelha)
        if not (d_olhos * 0.12 < abs(reg["cx"] - eixo) < d_olhos * 0.95):
            continue
        if reg["w"] < reg["h"] * 1.3:
            continue                        # sobrancelha Ã© deitada
        if not (larg_olho * 0.40 <= reg["w"] <= larg_olho * 1.60):
            continue                        # do tamanho de um olho, nÃ£o do cabelo
        # de cada lado fica a mais BAIXA das candidatas: Ã© a que encosta no
        # olho. Acima dela vem ruga, franja e o contorno do cabelo.
        if nome not in achados or reg["cy"] > achados[nome]["cy"]:
            achados[nome] = reg

    # AS DUAS SOBRANCELHAS PODEM SER UM COMPONENTE SÃ“: em algumas folhas
    # elas se tocam pelo contorno e saem como uma mancha atravessando a
    # testa. Girada como peÃ§a Ãºnica, ela vira uma barra preta cruzando o
    # rosto. Cortar pelo eixo devolve as duas, que Ã© o que a arte desenha.
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

    # --- recorta cada feiÃ§Ã£o e apaga o lugar dela com a cor da pele
    limpo = a.copy()
    sprites = {}
    cx_p, cy_p = float(piv[0]), float(piv[1])
    for nome, reg in achados.items():
        bx0, by0, bx1, by1 = reg["c"]["bbox"]
        folga = 2
        cx0, cy0 = max(0, bx0 - folga), max(0, by0 - folga)
        cx1, cy1 = min(img.width, bx1 + folga + 1), min(img.height, by1 + folga + 1)
        # QUANTA TESTA EXISTE ACIMA DESTA FEIÃ‡ÃƒO. A sobrancelha erguida Ã© o
        # traÃ§o mais forte do espanto, e sem limite ela sobe para cima do
        # cabelo: no primeiro teste, `chocado` colou a sobrancelha na
        # franja e deixou uma mancha de pele onde ela estava. A medida sai
        # da arte -- personagem de testa alta ganha mais curso, o de franja
        # baixa ganha menos, sem ninguÃ©m recalibrar constante nenhuma.
        col = int(min(max(reg["cx"], 0), img.width - 1))
        livre, y = 0, int(by0) - 1
        while y >= 0 and nucleo[y, col] and not tinta[y, col]:
            livre += 1
            y -= 1
        # RECORTE PELA FORMA, nÃ£o pelo retÃ¢ngulo. Com o retÃ¢ngulo vinha
        # junto uma moldura de pele, invisÃ­vel enquanto a feiÃ§Ã£o estÃ¡ no
        # lugar e denunciada assim que ela se move: a sobrancelha erguida
        # de `surpreso` levava um pedaÃ§o de bochecha para cima da franja e
        # deixava uma mancha clara no cabelo. Recortada pela prÃ³pria
        # mÃ¡scara, ela sobe sozinha.
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
        # A COR DA TAPA VEM DE ENCOSTO, nÃ£o do rosto inteiro. A cor
        # dominante do crÃ¢nio Ã© um tom quantizado (a caixa de 24 nÃ­veis em
        # que a pele caiu), e a testa tem sombreado prÃ³prio: com ela, o
        # lugar de onde a sobrancelha saiu ficava mais claro que a testa em
        # volta e virava uma sobrancelha FANTASMA -- visÃ­vel em toda
        # expressÃ£o que ergue o cenho. O anel de pixels em volta da feiÃ§Ã£o Ã©
        # a prÃ³pria testa, no tom exato daquele ponto.
        m = reg["c"]["mask"].astype(np.uint8) * 255
        m = np.asarray(Image.fromarray(m).filter(ImageFilter.MaxFilter(5))) > 8
        limpo[m, :3] = _cor_do_anel(a, m, alfa) or pele
        limpo[m, 3] = 255

    # emenda macia, pelo mesmo motivo da tapa da boca: cor certa com borda
    # dura ainda se lÃª como remendo
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

    Mesmo princÃ­pio de `_cor_em_volta`, mas trabalhando direto no array (Ã©
    chamado uma vez por feiÃ§Ã£o, dentro de `_extrair_feicoes`). SÃ³ entram
    pixels claros: o traÃ§o preto que cerca olho e sobrancelha faria a
    mediana escurecer e a tapa sairia como um borrÃ£o cinza."""
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
        A folha nova consertou o defeito nÂº 1: a boca nÃ£o Ã© mais um entalhe
        vazado, Ã© uma linha desenhada, fechada, com um sorriso de leve. SÃ³
        que `_tapar_entalhe` procura um BURACO no alfa -- e nÃ£o hÃ¡ mais
        buraco nenhum. Sem entalhe, `self.boca` ficava None, e com ela ia
        embora o lipsync inteiro: o Pal passaria o vÃ­deo com a mesma boca
        parada, agora fechada em vez de aberta.

        A boca da arte precisa sair de cena pelo mesmo motivo que as feiÃ§Ãµes
        saem do crÃ¢nio em `_extrair_feicoes`: o que fica parado no desenho
        nÃ£o pode ser animado. Apagada ela, `_boca_desenhada` pÃµe no lugar
        exato dela uma boca que abre com o som e curva com a emoÃ§Ã£o -- e o
        traÃ§o em repouso Ã© praticamente o mesmo que o desenhista fez.

    COMO
        Dentro do crÃ¢nio, longe da borda, o que nÃ£o Ã© pele Ã© traÃ§o. A boca
        Ã© o traÃ§o DEITADO (mais largo que alto) do terÃ§o de baixo, perto do
        eixo do rosto. O queixo (um U que desce atÃ© a base) e as linhas
        verticais das bochechas ficam de fora pela mesma rÃ©gua que as
        distingue: eles nÃ£o sÃ£o deitados, ou nÃ£o estÃ£o no eixo.

    Devolve (crÃ¢nio sem a boca, caixa da boca) ou (img, None).
    """
    from segmentar import _componentes
    a = np.asarray(img.convert("RGBA"))
    alfa = a[..., 3]
    dentro = alfa > 128
    if dentro.sum() < 400:
        return img, None, None

    # o raio de erosÃ£o Ã© medido no ROSTO, nÃ£o na tela inflada por
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
    # A PELE VEM DO ROSTO JÃ MEDIDO, e nÃ£o da moda da peÃ§a (30/08, noite).
    #
    # Esta funÃ§Ã£o media a cor mais comum do nÃºcleo do crÃ¢nio e chamava
    # aquilo de pele. Na senhora, a cor mais comum do crÃ¢nio Ã© o CABELO
    # GRISALHO (180,180,180) -- ele ocupa mais pixels que o rosto. Com o
    # cinza no lugar da pele, `tinta` passou a marcar a pele inteira
    # (|252,204,156 - 180,180,180| = 120 > 90): o rosto todo virou uma
    # mancha sÃ³ de 11 mil px, a boca foi absorvida por ela, e nenhum
    # candidato sobrou. Resultado na tela: a senhora fala 5 falas de boca
    # parada, e a folha ainda assim passa em `conferir_folha`.
    #
    # `_analisar_rosto` JÃ RESOLVE ISSO -- ele avisa no log ("a cor
    # dominante da peÃ§a era (180,180,180) (cabelo ou touca); a pele medida
    # no rosto e (252,204,156)") e guarda a cor certa em `rosto["pele"]`. A
    # medida existia, no lugar certo, e esta funÃ§Ã£o nÃ£o a lia: refazia a
    # conta ingÃªnua ao lado. Ã‰ a armadilha 16 na mesma casa -- medir no
    # lugar errado (a peÃ§a inteira) o que sÃ³ faz sentido medido no rosto.
    pele = None
    if rosto is not None and rosto.get("pele") is not None:
        pele = np.asarray(rosto["pele"]).astype(np.int16)
    if pele is None:
        q = (rgb[nucleo] // 24)
        chaves, contas = np.unique(q.reshape(-1, 3), axis=0, return_counts=True)
        pele = chaves[contas.argmax()].astype(np.int16) * 24 + 12
    tinta = nucleo & (np.abs(rgb - pele).sum(axis=2) > 90)
    if tinta.sum() < 20:
        return img, None, None

    # A FAIXA sai dos olhos quando eles foram medidos (ver `_analisar_rosto`):
    # entre o nariz e o queixo, no eixo, com a largura contada em distÃ¢ncia
    # interocular. Sem olhos, cai na rÃ©gua antiga -- fraÃ§Ãµes da peÃ§a, que sÃ³
    # valem quando a peÃ§a Ã© o rosto e nada mais.
    if rosto:
        ymin, ymax, eixo, tol_x = _faixa_da_boca(rosto)
        # a largura do rosto, contada em distÃ¢ncia interocular: num rosto
        # frontal ela vale por volta de 2,2 vezes o vÃ£o entre os olhos
        larg_ref = rosto["d_olhos"] * 2.2
    else:
        ymin, ymax = y0 + alt_r * 0.52, y0 + alt_r * 0.92
        eixo, tol_x = cx_rosto, larg_r * 0.22
        larg_ref = larg_r

    # A FAIXA Ã‰ RECORTADA ANTES DE ROTULAR, e essa ordem Ã© a correÃ§Ã£o
    # inteira (30/08, noite).
    #
    # `_componentes` rotula tinta CONECTADA, e num rosto desenhado quase
    # todo o traÃ§o escuro se toca: na senhora, o cabelo grisalho emoldura o
    # rosto, encosta no aro dos Ã³culos, o aro encosta nos olhos, e a linha
    # do queixo fecha o caminho atÃ© a boca. Medido: UMA componente de
    # 16.758 px, de y=43 a y=229, com a boca dentro dela. Nenhum filtro
    # adiante salva -- eles julgam a caixa da mancha, e a caixa Ã© a cabeÃ§a
    # inteira. A boca da senhora existe na arte (51x11 px, exatamente no
    # eixo) e nunca chegou a ser candidata.
    #
    # O Pal escapava por sorte: o cabelo dele nÃ£o faz ponte com o queixo, e
    # a boca saÃ­a como componente prÃ³pria. Ou seja, o detector dependia de
    # um detalhe do penteado -- e foi por isso que dois personagens de nove
    # entraram em cena sem boca sem ninguÃ©m notar.
    #
    # Recortando a faixa primeiro, a ponte Ã© cortada junto: dentro de
    # y âˆˆ [ymin, ymax] o cabelo vira duas manchas laterais (que o filtro de
    # eixo descarta) e a boca fica sozinha no meio. Medido depois: a boca
    # aparece nos quatro conferidos (senhora 51x11, enfermeira 55x12,
    # pal 38x11, maya 26x6).
    faixa = np.zeros_like(tinta)
    faixa[max(0, int(ymin)):int(ymax) + 1, :] = True
    tinta_faixa = tinta & faixa
    if tinta_faixa.sum() < 20:
        return img, None, None

    cands = []
    # O LIMIAR DE ÃREA TAMBÃ‰M MUDA DE BASE: 1% da tinta da FAIXA, nÃ£o da
    # peÃ§a inteira. Sobre a peÃ§a, uma mancha dominante (o cabelo) levava o
    # 1% para acima da Ã¡rea da boca -- limiar proporcional Ã  coisa errada,
    # a mesma famÃ­lia da armadilha 16.
    for c in _componentes(tinta_faixa,
                          area_min=max(20, int(tinta_faixa.sum() * 0.01))):
        bx0, by0, bx1, by1 = c["bbox"]
        w, h = bx1 - bx0 + 1, by1 - by0 + 1
        cy = (by0 + by1) / 2.0
        if cy < ymin or cy > ymax:
            continue                       # olho/sobrancelha em cima, pescoÃ§o embaixo
        if abs((bx0 + bx1) / 2.0 - eixo) > tol_x:
            continue                       # fora do eixo: bochecha, orelha
        if w < h * 1.4 or w < larg_ref * 0.10 or w > larg_ref * 0.75:
            continue                       # a boca Ã© deitada, e nÃ£o atravessa a cara
        cands.append(c)
    if not cands:
        return img, None, None

    # a boca Ã© a maior delas; o que estiver logo abaixo e mais estreito Ã© o
    # lÃ¡bio inferior e sai junto -- sobrando, ele vira um risco solto sob a
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

    # O SORRISO DO DESENHISTA NÃƒO SE PERDE. A boca que entra no lugar Ã©
    # desenhada por cÃ³digo, e desenhada reta ela apaga a Ãºnica expressÃ£o que
    # a folha jÃ¡ trazia de fÃ¡brica -- a cara em repouso fica com um traÃ§o
    # de rÃ©gua no meio. Medir a curva da linha original (o meio dela estÃ¡
    # acima ou abaixo das pontas?) e usÃ¡-la como repouso devolve o mesmo
    # rosto, agora animÃ¡vel. A espessura sai pela mesma rÃ©gua: Ã© a altura
    # mÃ©dia da mancha, nÃ£o uma fraÃ§Ã£o inventada da largura.
    so = np.asarray(_altura_por_coluna(m, bx0, bx1))
    curva, esp = 0.0, 0.0
    val = so[so[:, 1] > 0]
    if len(val) >= 6:
        n = len(val)
        pontas = np.concatenate([val[:max(1, n // 5)], val[-max(1, n // 5):]])
        meio = val[n // 3: 2 * n // 3]
        if len(meio):
            # Mesma convenÃ§Ã£o de `_boca_desenhada`: curva > 0 empurra o MEIO
            # da linha para baixo, e Ã© isso que se lÃª como sorriso -- num
            # traÃ§o de boca sÃ£o as PONTAS que sobem. y cresce para baixo,
            # entÃ£o meio - pontas > 0 Ã© sorriso.
            larg_b = max(bx1 - bx0 + 1, 1)
            curva = float((meio[:, 0].mean() - pontas[:, 0].mean()) / (larg_b * 0.16))
            esp = float(val[:, 1].mean())
    return suave, (int(bx0), int(by0), int(bx1), int(by1)), \
        {"curva": max(-1.0, min(1.0, curva)), "esp": esp}


def _altura_por_coluna(mask, x0, x1):
    """(y do centro, espessura) de cada coluna da mancha -- a linha da boca
    lida como funÃ§Ã£o, que Ã© o que permite medir curva e espessura."""
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

    Anel de pixels que fica logo fora da tapa: Ã© a bochecha e o queixo em
    volta da boca, exatamente o tom que a tapa precisa ter para sumir."""
    a = np.asarray(img.convert("RGBA"))
    dentro = np.asarray(tapa_mask) > 8
    fora = np.asarray(tapa_mask.filter(ImageFilter.MaxFilter(2 * folga + 1))) > 8
    anel = fora & ~dentro & (a[..., 3] > 200)
    if anel.sum() < 30:
        return None
    px = a[anel][:, :3]
    claros = px[px.sum(axis=1) > 240]      # fora o traÃ§o preto do contorno
    base = claros if len(claros) > 20 else px
    return tuple(int(v) for v in np.median(base, axis=0))


def _cor_da_pele(img):
    """A cor dominante do MIOLO da peÃ§a -- a pele, nÃ£o o contorno.

    Erodir joga fora a casca preta; o que sobra Ã© o preenchimento."""
    a = np.asarray(img.convert("RGBA"))
    miolo = np.asarray(img.split()[3].filter(ImageFilter.MinFilter(9))) > 128
    if miolo.sum() < 20:
        return _cor_da_casca(img)
    px = a[miolo][:, :3]
    claros = px[px.sum(axis=1) > 200]          # descarta traÃ§o interno escuro
    base = claros if len(claros) > 20 else px
    return tuple(int(v) for v in np.median(base, axis=0))


# QUANTO DO VÃƒO CADA PEÃ‡A FECHA, e por que este nÃºmero foi medido duas
# vezes (01/09, voltas 57 e 58).
#
# Era 0,5: as duas vizinhas cresciam METADE do vÃ£o e ficavam encostadas.
# Encostar basta enquanto a junta nÃ£o gira; girando, elas se tocam num
# ponto sÃ³ e num Ã¢ngulo grande deixam de se tocar -- o antebraÃ§o da VovÃ³
# boiando ao lado do corpo num close do v057.
#
# A primeira correÃ§Ã£o foi para 1,0 (vÃ£o inteiro de cada lado, sobreposiÃ§Ã£o
# de um vÃ£o), e ela resolveu a junta -- `junta.py` foi de 2 para 1 na
# senhora e os dez passam. SÃ³ que o anel cresce com a COR DO CONTORNO, e
# no v058 ele apareceu: na Maria, de camisa azul lisa e calÃ§a clara, o
# ombro, o cotovelo e o JOELHO ganharam uma faixa preta grossa que lÃª como
# tira, nÃ£o como traÃ§o. Na senhora nÃ£o se via, porque o tricÃ´ Ã© ocupado --
# arte de padrÃ£o esconde a emenda, arte de cor chapada denuncia.
#
# 0,75 Ã© o meio-termo MEDIDO, nÃ£o escolhido: dÃ¡ sobreposiÃ§Ã£o de meio vÃ£o
# (~6px na Maria, ~10 na enfermeira), que Ã© o que sobrevive Ã  rotaÃ§Ã£o, com
# um anel 25% mais fino. O teste Ã© `junta.py` no elenco inteiro: se algum
# personagem voltar a dar 2, este nÃºmero sobe de novo -- junta aberta Ã©
# defeito, anel grosso Ã© feiÃºra, e nessa ordem.
# ZERO, E O ANEL POR PEÃ‡A DEIXOU DE EXISTIR (03/09).
#
# Queixa do dono do projeto: *"linhas das cores do personagem para tampar
# vÃ£o, ficou muito ruim, era sÃ³ manter como estava"*. Ela estÃ¡ certa, e o
# A/B mostra que **as duas cores sÃ£o ruins e a escolha entre elas era falsa**:
#
#   Â· anel da cor do CONTORNO (o "como estava"): faixa preta grossa em todo
#     ombro, cotovelo, quadril, joelho e tornozelo. LÃª como boneco
#     articulado de plÃ¡stico â€” foi por isso que 02/09 trocou a cor;
#   Â· anel da cor de DENTRO (o que estava no ar): faixa rosa no cotovelo da
#     Maya, faixa azul no ombro do Pal, e joelheiras nas calÃ§as. LÃª como
#     esparadrapo â€” Ã© a queixa de hoje.
#
# O defeito nÃ£o Ã© a COR: Ã© o anel existir. `_fechar_vao` dilata a peÃ§a em
# todas as direÃ§Ãµes e a arte original volta por cima, entÃ£o o que sobra
# visÃ­vel Ã© justamente a parte do anel que ficou FORA da silhueta da peÃ§a â€”
# uma tira de cor arbitrÃ¡ria ao redor da junta, que nenhuma cor conserta.
#
# O fecho passa a ser feito no CORPO MONTADO, por morfologia, em
# `_fechar_vaos_do_corpo`: uma operaÃ§Ã£o de fechamento tapa qualquer fenda
# mais estreita que o pincel e, por definiÃ§Ã£o, nÃ£o cria nada onde nÃ£o havia
# uma fenda entre duas partes. A cor sai do prÃ³prio entorno, entÃ£o no
# cotovelo ela vem do braÃ§o e na cintura vem da calÃ§a â€” sem escolher cor
# nenhuma. Ver lÃ¡ o porquÃª inteiro.
#
# UM DE VOLTA, E A COR DEIXOU DE SER INVENTADA (04/09, ciclo 25).
#
# Zerar isto em 03/09 se apoiou num A/B (`RAIO_FECHO=0` contra 9) feito no
# spec do v001, que tem **Pal, Zeca e Maya** em cena â€” e nesses trÃªs o vÃ£o da
# folha mede 5 a 6 px, tÃ£o estreito que as peÃ§as jÃ¡ se sobrepÃµem sozinhas. A
# conclusÃ£o *"nas poses e escalas de hoje as peÃ§as jÃ¡ se sobrepÃµem"* foi
# tirada de um caminho e aplicada aos dez: Ã© a lei 60 na geometria.
#
# `ferramentas/junta.py` mede o que sobrou, sobre o elenco inteiro, com o
# fecho do corpo montado (`RAIO_FECHO=4`) jÃ¡ no ar:
#
#     pal, maya, zeca   1 mancha    o corpo inteiro, em dez poses
#     senhora           4 manchas   solta em `comemorar`
#     soldado           7 manchas   solta em `maos_na_cabeca`
#     preso            10 manchas   o corpo em dez pedaÃ§os
#     e ainda astronauta, enfermeira, joao, maria
#
# Sete dos dez REPROVAM, e eles sÃ£o 62% dos trechos do corpus. O fechamento
# morfolÃ³gico do corpo montado nÃ£o podia salvÃ¡-los, e nÃ£o Ã© falha dele: um
# fechamento sÃ³ emenda fenda mais estreita que o pincel, e nunca cria a
# SOBREPOSIÃ‡ÃƒO que sobrevive Ã  rotaÃ§Ã£o (lei 73). Quem faz peÃ§a sobrepor peÃ§a Ã©
# o anel por peÃ§a, e sÃ³ ele.
#
# E O ANEL CONTINUA EM ZERO â€” a QUARTA cor foi tentada e reprovada na mesma
# sessÃ£o. Com `FECHO_DO_VAO = 1.0` e o anel preenchido por `_espalhar`, o
# `junta.py` foi de sete reprovados a ZERO (os dez com uma mancha sÃ³, em dez
# poses) e a prÃ©via do v022 saiu com **cotoveleiras e joelheiras pretas** em
# Pal e Maya: `_espalhar` estende o pixel de arte mais prÃ³ximo, e o mais
# prÃ³ximo da borda de uma peÃ§a Ã© o CONTORNO dela. Estender a peÃ§a Ã© engrossar o
# traÃ§o â€” a faixa de boneco articulado outra vez, por um caminho novo.
#
# Ã‰ o quarto artefato da mesma famÃ­lia, e a liÃ§Ã£o jÃ¡ nÃ£o Ã© sobre cor: **nÃ£o
# existe conteÃºdo certo para o anel, porque o anel aparece FORA da silhueta da
# peÃ§a.** O que a rotaÃ§Ã£o precisa Ã© de sobreposiÃ§Ã£o, e sobreposiÃ§Ã£o de verdade
# se faz na SEGMENTAÃ‡ÃƒO (cortar a peÃ§a com sobra por baixo da vizinha), nÃ£o
# aqui, onde sÃ³ dÃ¡ para pintar por cima.
#
# E A QUINTA TENTATIVA NÃƒO Ã‰ UMA COR: Ã‰ UMA DIREÃ‡ÃƒO (04/09, ciclo 25).
#
# O que as quatro tÃªm em comum nÃ£o Ã© o conteÃºdo do anel -- Ã© `MaxFilter`, que
# cresce a peÃ§a para TODOS os lados. O pedaÃ§o que se vÃª Ã© o que cresce
# PERPENDICULAR ao osso, onde nÃ£o hÃ¡ vizinha para cobri-lo; ali Ã© silhueta, e
# qualquer coisa posta em cima da silhueta aparece. Trocar a tinta de uma
# regiÃ£o que nÃ£o devia existir nunca ia funcionar.
#
# `_estender_para_a_junta` desloca a peÃ§a na direÃ§Ã£o da junta em vez de
# engrossÃ¡-la: ela CONTINUA por baixo da vizinha, que Ã© o que um cut-out de
# papel faz. Ver lÃ¡.
#
# ZERO POR DECISÃƒO DE ESTILO (04/09, do dono do projeto). Ver o bloco de
# `RAIO_FECHO`: o vÃ£o entre as peÃ§as Ã© o traÃ§o do canal e nÃ£o se tapa -- nem
# por anel, nem por extensÃ£o, nem por fechamento. As seis tentativas ficam
# documentadas aqui porque a numeraÃ§Ã£o delas explica por que a queixa voltava
# sempre: **nenhuma estava errada na tÃ©cnica, todas estavam erradas na
# premissa.**
#
# Qualquer valor > 0 devolve o fecho por peÃ§a, e existe para o A/B.
FECHO_DO_VAO = float(os.environ.get("FECHO_DO_VAO", "0"))

# Qual dos dois fechos por peÃ§a estÃ¡ no ar. `estender` Ã© o de 04/09 (a peÃ§a
# continua na direÃ§Ã£o do osso); `anel` Ã© o `MaxFilter` das quatro tentativas
# anteriores, guardado sÃ³ para o A/B poder reproduzir o defeito -- Ã© o mesmo
# recurso de `GANCHO_ENTRA` e `SEPARA_OBJETO_PX`. Sem um jeito de desligar, a
# Ãºnica prova possÃ­vel Ã© "depois", e "depois" sozinho nÃ£o prova nada.
MODO_FECHO = os.environ.get("MODO_FECHO", "estender")


def _estender_para_a_junta(tela, img, juntas, m):
    """A peÃ§a CONTINUA por baixo da vizinha, `m` px alÃ©m de cada junta.

    POR QUE ISTO, DEPOIS DE QUATRO ANÃ‰IS REPROVADOS (04/09, ciclo 25)
        Fechar o vÃ£o engrossando a peÃ§a foi tentado com quatro conteÃºdos e os
        quatro apareceram na tela: cor do contorno (faixa preta de boneco
        articulado), cor de dentro (esparadrapo rosa e azul), desfoque (ponte
        cinza) e `_espalhar` (cotoveleiras pretas). A conclusÃ£o que se repete Ã©
        sempre sobre a cor, e a cor nunca foi o problema.

        O problema Ã© a DIREÃ‡ÃƒO. `MaxFilter` dilata em todas as direÃ§Ãµes, e a
        parte da dilataÃ§Ã£o que fica visÃ­vel Ã© justamente a que cresce para os
        LADOS da junta -- perpendicular ao osso, onde nÃ£o hÃ¡ vizinha nenhuma
        para cobri-la. Qualquer coisa que se ponha ali aparece, porque ali Ã©
        silhueta. Ã‰ por isso que trocar o conteÃºdo do anel nunca resolveu.

        Num cut-out de papel a peÃ§a nÃ£o engorda: ela CONTINUA por baixo da
        vizinha. A continuaÃ§Ã£o acontece numa direÃ§Ã£o sÃ³ -- a do osso -- e some
        atrÃ¡s da peÃ§a de cima.

    COMO
        Para cada junta (o pivÃ´, por onde esta peÃ§a se prende ao pai, e cada
        saÃ­da, por onde um filho se prende nela), a direÃ§Ã£o de saÃ­da Ã© a do
        centro da peÃ§a PARA a junta: Ã© para lÃ¡ que fica a vizinha, por
        definiÃ§Ã£o -- a junta Ã© o ponto de contato entre as duas. Uma cÃ³pia da
        peÃ§a, deslocada `m` px nessa direÃ§Ã£o, entra ATRÃS da original.

        O que isso acrescenta Ã© exatamente o prolongamento do toco alÃ©m da
        junta. Para os lados nÃ£o acrescenta nada mensurÃ¡vel: o deslocamento Ã©
        paralelo Ã  silhueta ali, entÃ£o a cÃ³pia cai em cima da prÃ³pria peÃ§a.

        A mÃ¡scara de disco continua valendo, pela mesma razÃ£o de 02/09: numa
        peÃ§a curva (o tronco, o crÃ¢nio) o deslocamento tambÃ©m empurraria a
        borda do outro lado, e ali nÃ£o hÃ¡ vizinha.

    E a cor nÃ£o Ã© escolhida por ninguÃ©m: o que aparece no prolongamento Ã© a
    arte da prÃ³pria peÃ§a, deslocada. Na manga sai manga, na perna sai perna,
    e o traÃ§o do desenhista continua sendo o traÃ§o."""
    a = np.asarray(tela.split()[3])
    ys, xs = np.nonzero(a > 128)
    if not len(xs):
        return tela
    cx, cy = float(xs.mean()), float(ys.mean())
    raio = max(22.0, m * 4.0, 0.22 * min(img.width, img.height))
    # O TOCO SAI SEM O TRAÃ‡O (04/09, v034). Deslocar a peÃ§a inteira desloca a
    # BORDA ESCURA dela junto, e o que sobra Ã  vista alÃ©m da peÃ§a original Ã©
    # justamente essa borda: um segundo contorno a `m` px do primeiro, que na
    # folha de contato lÃª como a faixa de boneco articulado das quatro
    # tentativas anteriores -- medido em `tinta_junta.py`, 62% do que o fecho
    # acrescenta Ã© pixel escuro. O prolongamento tem de ser a arte de DENTRO
    # da peÃ§a; o contorno continua desenhado uma vez sÃ³, pela original que
    # entra por cima. Custa uma vez por peÃ§a, na carga (`Personagem.__init__`).
    corpo = _sem_traco(tela, m + 4)
    fundo = Image.new("RGBA", tela.size, (0, 0, 0, 0))
    for (jx, jy) in juntas:
        jx, jy = jx + m, jy + m
        dx, dy = jx - cx, jy - cy
        n = math.hypot(dx, dy)
        if n < 1e-6:
            continue
        dx, dy = dx / n * m, dy / n * m
        desl = Image.new("RGBA", tela.size, (0, 0, 0, 0))
        desl.paste(corpo, (int(round(dx)), int(round(dy))))
        mascara = Image.new("L", tela.size, 0)
        ImageDraw.Draw(mascara).ellipse(
            [jx - raio, jy - raio, jx + raio, jy + raio], fill=255)
        desl.putalpha(Image.composite(desl.split()[3],
                                      Image.new("L", tela.size, 0), mascara))
        fundo.alpha_composite(desl)
    fundo.alpha_composite(tela)          # a arte original por cima
    return fundo


def _fechar_vao(img, pivot, px, juntas=None):
    """Engrossa a peÃ§a `px` pixels com a cor do prÃ³prio contorno, PERTO DAS
    JUNTAS.

    `juntas` sÃ£o os pontos, nas coordenadas da prÃ³pria arte, em que esta
    peÃ§a encosta em outra: o pivÃ´ dela e as saÃ­das dos filhos. Sem a lista,
    engrossa a peÃ§a inteira, que Ã© o comportamento antigo.

    POR QUE (defeito visto no run #13 e explicado sÃ³ agora)
        A folha Ã© um BONECO DE PAPEL: cada parte tem contorno prÃ³prio e um
        vÃ£o branco a separa da vizinha. O vÃ£o Ã© o que permite segmentar a
        folha, e o meio dele Ã© a articulaÃ§Ã£o -- Ã© a decisÃ£o estrutural do
        projeto e continua certa.

        SÃ³ que o motor nunca fechou esse vÃ£o ao compor. Enquanto o fundo
        era branco isso nÃ£o aparecia: vÃ£o branco sobre fundo branco Ã©
        invisÃ­vel. Com CENÃRIO atrÃ¡s, cada vÃ£o virou um rasgo por onde a
        rua aparece -- ombro, cintura, punho, joelho e tornozelo abertos,
        o corpo lido como pedaÃ§os soltos. O HANDOFF registrava um caso
        disto ("vÃ£o entre antebraÃ§o e mÃ£o que nÃ£o fecha") como defeito de
        pivÃ´; nÃ£o era: Ã© o vÃ£o desenhado, em todas as juntas.

        PeÃ§a vizinha cresce metade do vÃ£o de cada lado e as duas se
        encostam. Crescer com a COR DO CONTORNO faz a emenda ler como
        linha um pouco mais grossa, que Ã© exatamente como cut-out de
        verdade resolve: as peÃ§as se sobrepÃµem, nÃ£o se tangenciam.

    O pivÃ´ nÃ£o se mexe em relaÃ§Ã£o ao desenho -- a peÃ§a cresce em volta
    dele --, entÃ£o nenhuma medida da folha Ã© invalidada.

    O ANEL SÃ“ EXISTE PERTO DAS JUNTAS (02/09, item 6 do dono do projeto:
    *"linhas muito grossas nos personagens, e nÃ£o sÃ£o constantes; afine
    essa linha e torne padrÃ£o o contorno externo das peÃ§as"*).

    A queixa estÃ¡ certa e a causa Ã© esta funÃ§Ã£o. `ferramentas/contorno.py`
    mediu as duas parcelas separadas:

        arte de origem   3 a 6 px, e CONSISTENTE entre os dez
        anel de _fechar_vao   5 a 11 px, proporcional ao vÃ£o medido

    Ou seja: o contorno que se vÃª Ã© dominado pelo anel, e ele varia DUAS
    VEZES de um personagem para o outro -- palavra por palavra a queixa.

    O erro de projeto Ã© engrossar a peÃ§a INTEIRA quando o problema Ã© sÃ³ a
    JUNTA. O vÃ£o a fechar existe no ombro, no cotovelo, no punho, no
    quadril, no joelho e no tornozelo; na silhueta -- as costas, a barriga,
    o alto da cabeÃ§a -- nÃ£o hÃ¡ vizinha nenhuma e o anel sÃ³ engorda a linha.

    EntÃ£o o anel passa a ser recortado por uma mÃ¡scara: discos em volta do
    PIVÃ” da peÃ§a (por onde ela se prende ao pai) e de cada SAÃDA (por onde
    os filhos se prendem nela). Fora desses discos, a arte sai como foi
    desenhada, e o contorno externo volta a ser o da folha -- que jÃ¡ Ã©
    padrÃ£o.

    Isto NÃƒO Ã© o "disco de articulaÃ§Ã£o" que foi tentado e revertido em
    28/08. Aquele desenhava um disco da COR DA PEÃ‡A POR CIMA, e ele
    aparecia por fora dos tornozelos. Aqui nÃ£o se desenha nada por cima: a
    dilataÃ§Ã£o que jÃ¡ existia Ã© que fica limitada Ã  vizinhanÃ§a da junta, e a
    arte original continua por Ãºltimo.
    """
    if px <= 0:
        return img, pivot
    m = int(px)
    tela = Image.new("RGBA", (img.width + 2 * m, img.height + 2 * m), (0, 0, 0, 0))
    tela.alpha_composite(img, (m, m))
    if juntas and MODO_FECHO == "estender":
        return _estender_para_a_junta(tela, img, juntas, m), \
            (pivot[0] + m, pivot[1] + m)
    alfa = tela.split()[3].filter(ImageFilter.MaxFilter(2 * m + 1))
    if juntas:
        # O raio cobre o vÃ£o inteiro mais a folga da rotaÃ§Ã£o. Generoso o
        # bastante para a junta nunca abrir, pequeno o bastante para nÃ£o
        # alcanÃ§ar a silhueta: uma junta de 10px de vÃ£o pede ~34px de
        # disco, e a peÃ§a mais estreita do rig (a mÃ£o) tem ~90px.
        # O RAIO ESCALA COM A PEÃ‡A (02/09). Com um raio constante de 12 e
        # depois de 22, o astronauta descolava em TODAS as dez poses,
        # `parado` inclusive, e a mancha solta era o CRÃ‚NIO: o capacete dele
        # Ã© uma peÃ§a de 256px e o pescoÃ§o fica longe do pivÃ´, entÃ£o um disco
        # dimensionado para uma mÃ£o de 84px nÃ£o alcanÃ§a a regiÃ£o em que as
        # duas peÃ§as se encontram.
        #
        # A vizinhanÃ§a de uma junta nÃ£o Ã© uma distÃ¢ncia fixa em pixels -- Ã©
        # uma fraÃ§Ã£o da peÃ§a. 22% do lado menor cobre o pescoÃ§o de um
        # capacete e continua sendo um disco pequeno numa mÃ£o. O contorno
        # externo nÃ£o engorda por isso: o que importa Ã© o disco NÃƒO alcanÃ§ar
        # a silhueta, e a silhueta de uma peÃ§a grande estÃ¡ longe do seu
        # pivÃ´ exatamente na mesma proporÃ§Ã£o.
        raio = max(22.0, m * 4.0, 0.22 * min(img.width, img.height))
        mascara = Image.new("L", tela.size, 0)
        d = ImageDraw.Draw(mascara)
        for (jx, jy) in juntas:
            cx, cy = jx + m, jy + m
            d.ellipse([cx - raio, cy - raio, cx + raio, cy + raio], fill=255)
        alfa = Image.composite(alfa, tela.split()[3], mascara)
        # O ANEL Ã‰ DA COR DE DENTRO, NÃƒO DA COR DO CONTORNO (02/09). Ver
        # `_cor_de_dentro`: pintado de escuro, cada junta virava uma faixa
        # preta sobre a calÃ§a clara; pintado com a cor do preenchimento, o
        # vÃ£o fecha com a cor do prÃ³prio membro e o traÃ§o que a arte jÃ¡ tem
        # continua por cima. SÃ³ vale com a mÃ¡scara: sem ela o anel claro
        # apareceria em volta da peÃ§a inteira, como um halo.
        #
        # E `_espalhar` NÃƒO SERVE AQUI â€” tentado e revertido em 04/09 (ciclo
        # 25). Ele estende o pixel de arte mais prÃ³ximo, e o pixel mais prÃ³ximo
        # da BORDA de uma peÃ§a Ã© sempre o CONTORNO PRETO: estender a peÃ§a Ã©
        # estender o traÃ§o dela, e a prÃ©via saiu com cotoveleiras e joelheiras
        # pretas em todo mundo â€” a "faixa de boneco articulado" pela quarta
        # vez, agora por um caminho novo. `_espalhar` continua certo em
        # `_fechar_vaos_do_corpo`, onde o que ele preenche Ã© uma FENDA de
        # poucos pixels entre dois contornos, e sair preto ali Ã© o resultado
        # desejado: lÃª como o traÃ§o da emenda, nÃ£o como um remendo.
        cor = _cor_de_dentro(img, ponto=juntas[0])
    else:
        cor = _cor_da_casca(img)
    grossa = Image.new("RGBA", tela.size, cor + (255,))
    grossa.putalpha(alfa)
    grossa.alpha_composite(tela)          # a arte original por cima do anel
    return grossa, (pivot[0] + m, pivot[1] + m)


class Personagem:
    """Carrega as peÃ§as e as Ã¢ncoras uma vez, na memÃ³ria.

    `pivos` Ã© onde cada peÃ§a gira; `saidas` Ã©, dentro de cada peÃ§a, onde
    cada filho se encaixa. Os dois vÃªm medidos da folha (segmentar.py), e
    Ã© por isso que o motor nÃ£o precisa mais de comprimento de osso nem de
    nenhuma constante anatÃ´mica: a posiÃ§Ã£o do cotovelo Ã© o ponto que o
    desenhista deixou marcado no vÃ£o."""

    def __init__(self, pasta):
        self.pasta = pasta
        cfg = json.load(open(os.path.join(pasta, "partes.json"), encoding="utf-8"))
        self.pivos = cfg["pivos"]
        self.saidas = cfg.get("saidas", {})
        self.escala = cfg.get("escala", 1.0)
        self.comp = cfg.get("comprimentos", {})
        self.vaos = cfg.get("vaos", {})
        # PERSONAGEM SEM EXPRESSÃƒO (30/08): quem tem o rosto coberto -- o
        # astronauta de viseira escura -- nÃ£o pode ter feiÃ§Ãµes animadas nem
        # boca desenhada. Ã‰ DADO da arte, gravado em `partes.json`, e nÃ£o
        # detecÃ§Ã£o: o motor "acha olhos" no reflexo do vidro e a rÃ©gua de
        # simetria os aceita, entÃ£o nenhuma heurÃ­stica resolve isto sozinha.
        # Ver `ferramentas/rosto_vivo.py`, que mede quantas feiÃ§Ãµes saem.
        self.sem_expressao = bool(cfg.get("sem_expressao", False))
        # CORREÃ‡ÃƒO DE FOLHA: a arte vem em pose T; em cena o braÃ§o cai.
        self.corr = dict(CORRECAO_POSE_T)
        for filho, dono in SEGUE.items():
            self.corr.setdefault(filho, self.corr.get(dono, 0.0))
        # O segmentador mede vÃ£o sÃ³ nas juntas do corpo; nas peÃ§as de rosto
        # ele grava 0. Para olho, nariz e sobrancelha isso Ã© certo -- sÃ£o
        # adornos colados no crÃ¢nio e engrossÃ¡-los mudaria a cara. A
        # MANDÃBULA Ã© outra coisa: ela Ã© a Ãºnica peÃ§a de rosto que se MOVE
        # em relaÃ§Ã£o ao pai, e Ã© por ela que a boca abre. Sem fechar o vÃ£o
        # dela, o entalhe do crÃ¢nio fica maior que o queixo e a boca parece
        # permanentemente entreaberta -- foi lido como defeito da arte.
        medidos = [v for v in self.vaos.values() if v > 0.5]
        tipico = sorted(medidos)[len(medidos) // 2] if medidos else 5.0
        self.img, self.piv, self.tam = {}, {}, {}
        self._cache_var = {}          # peÃ§as deformadas pela expressÃ£o facial
        # ROSTO ARTICULADO OU CARA DESENHADA? Se a mandÃ­bula nÃ£o veio como
        # peÃ§a de verdade, nÃ£o hÃ¡ queixo para descer: a boca nÃ£o abre, e o
        # entalhe dela precisa ser tapado (ver _tapar_entalhe). Decidir isto
        # UMA vez, no carregamento, evita testar peÃ§a a peÃ§a em 430 frames.
        self.rosto_articulado = True
        self._off_cranio = (0.0, 0.0)
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
            # metade do vÃ£o de cada lado: as duas vizinhas crescem uma em
            # direÃ§Ã£o Ã  outra e a junta fecha. +1 cobre o arredondamento e a
            # borda macia que o resize da escala deixa.
            vao = float(self.vaos.get(nome, 0.0))
            if nome in FECHA_MESMO_SEM_MEDIDA and vao <= 0.5:
                vao = tipico
                print(f"[personagem] '{nome}' sem vao medido; usando o tipico "
                      f"({tipico:.1f}px) para fechar a junta")
            # O VÃƒO SE FECHA COM SOBRA, NÃƒO NA CONTA EXATA (01/09, volta 57).
            #
            # Era `vao/2 + 1` de cada lado: as duas vizinhas crescem metade
            # do vÃ£o e se ENCOSTAM. Encostar basta enquanto a junta nÃ£o
            # gira. Ao girar, o que estava encostado passa a se tocar num
            # ponto sÃ³, e num Ã¢ngulo grande deixa de se tocar -- o antebraÃ§o
            # da VovÃ³ descola do braÃ§o em `maos_na_cabeca` e `comemorar`
            # (`junta.py`, e visÃ­vel no v057, num close, com a manga de
            # tricÃ´ boiando ao lado do corpo).
            #
            # A prÃ³pria docstring de `_fechar_vao` jÃ¡ dizia como cut-out de
            # verdade resolve: *"as peÃ§as se sobrepÃµem, nÃ£o se tangenciam"*.
            # O cÃ³digo fazia o contrÃ¡rio. Fechar o vÃ£o INTEIRO de cada lado
            # dÃ¡ uma sobreposiÃ§Ã£o de um vÃ£o, que Ã© o que sobrevive Ã 
            # rotaÃ§Ã£o -- e o anel cresce com a COR DO CONTORNO da prÃ³pria
            # peÃ§a, entÃ£o a emenda continua lendo como linha, nÃ£o como
            # remendo.
            #
            # Ã‰ proporcional ao vÃ£o MEDIDO, entÃ£o continua sendo um nÃºmero
            # que vem do desenho: no Pal (vÃ£o de 5 a 6px) a diferenÃ§a Ã© de
            # 3px para 6; na VovÃ³ (8,6) Ã© de 5 para 9; na enfermeira (13,6)
            # de 8 para 14. Nada calibrado Ã  mÃ£o, e vale para folha nova.
            # OS PONTOS EM QUE ESTA PEÃ‡A ENCOSTA EM OUTRA: o pivÃ´ dela (por
            # onde ela se prende ao pai) e cada saÃ­da (por onde um filho se
            # prende nela). Ã‰ sÃ³ perto deles que o fecho precisa existir.
            #
            # E SÃ“ QUEM Ã‰ DESENHADO ANTES ESTENDE (04/09, ciclo 25).
            #
            # A extensÃ£o de `_estender_para_a_junta` Ã© um toco da peÃ§a alÃ©m da
            # junta, e ele SÃ“ pode existir onde a vizinha o cobre. Estender a
            # peÃ§a de cima Ã© o defeito: o `braco_sup_e` Ã© desenhado DEPOIS do
            # `peito` (ver `ORDEM_Z`), entÃ£o o toco dele para o ombro nÃ£o vai
            # parar debaixo do peito -- vai parar EM CIMA da camisa, com o
            # contorno prÃ³prio Ã  vista. Foi essa a faixa escura que apareceu no
            # ombro e no cotovelo da primeira prÃ©via deste conserto.
            #
            # Quem fecha cada vÃ£o Ã©, portanto, o vizinho de BAIXO -- e a
            # `ORDEM_Z` diz qual Ã©. O vÃ£o do ombro Ã© fechado pelo peito
            # (desenhado antes do braÃ§o), o do cotovelo pelo braÃ§o superior
            # (antes do inferior), o do quadril pela coxa (antes do abdÃ´men). O
            # vÃ£o fecha uma vez sÃ³, sempre pelo lado escondido, e a peÃ§a de
            # cima sai da folha como o desenhista a desenhou.
            z = {n: i for i, n in enumerate(ORDEM_Z)}
            meu_z = z.get(nome, len(ORDEM_Z))
            juntas = []
            pai = ESQUELETO.get(nome)
            if pai and z.get(pai, len(ORDEM_Z)) > meu_z:
                juntas.append(tuple(self.pivos[nome]))
            for _f, ponto in (self.saidas.get(nome) or {}).items():
                if z.get(_f, len(ORDEM_Z)) <= meu_z:
                    continue
                try:
                    juntas.append((float(ponto[0]), float(ponto[1])))
                except (TypeError, IndexError, ValueError):
                    pass
            if not juntas:
                # nenhuma junta a fechar por este lado. Sem esta saÃ­da o
                # `if juntas:` de `_fechar_vao` cairia no ramo antigo, que
                # engrossa a PEÃ‡A INTEIRA com a cor da casca -- o halo de
                # 02/09, agora em quem nÃ£o pediu fecho nenhum.
                vao = 0.0
            im, pivo = _fechar_vao(im, self.pivos[nome],
                                   int(round(vao * FECHO_DO_VAO)) + 1
                                   if vao > 0.5 else 0,
                                   juntas=juntas)
            # o tamanho ANTES de centralizar: _centralizar infla a peÃ§a atÃ©
            # um quadrado grande o bastante para qualquer rotaÃ§Ã£o, entÃ£o
            # `self.img[x].size` nÃ£o serve de rÃ©gua. A expressÃ£o facial mede
            # tudo em fraÃ§Ã£o da altura do crÃ¢nio e precisa da altura real.
            self.tam[nome] = im.size
            self.img[nome], self.piv[nome] = _centralizar(im, pivo)
            if nome == "cranio":
                # O DESLOCAMENTO QUE `_centralizar` APLICOU. Ele Ã©
                # `(R - int(px), R - int(py))`, e Ã© o que separa uma
                # coordenada lida no PNG da peÃ§a (que Ã© o que uma pessoa vÃª
                # e clica no painel) de uma coordenada na tela inflada (que
                # Ã© onde o motor trabalha). Guardado aqui porque Ã© o Ãºnico
                # ponto em que os dois sistemas se encontram; recalculÃ¡-lo
                # depois exigiria refazer `_fechar_vao` para achar o pivÃ´.
                self._off_cranio = (self.piv[nome][0] - pivo[0],
                                    self.piv[nome][1] - pivo[1])

        # --- ONDE FICA O ROSTO DENTRO DA PEÃ‡A DO CRÃ‚NIO -----------------
        # Medido UMA vez, pelos olhos, e usado pelas trÃªs funÃ§Ãµes de rosto.
        # Sem isto cada uma inventava a prÃ³pria rÃ©gua a partir da caixa da
        # peÃ§a -- e a peÃ§a do crÃ¢nio traz cabelo e pescoÃ§o em quantidade que
        # Ã© decisÃ£o do desenhista. Ver `_analisar_rosto`.
        self.rosto = _analisar_rosto(self.img["cranio"]) if "cranio" in self.img else None
        # ROSTO MARCADO Ã€ MÃƒO (30/08, noite), pelo mesmo motivo que os pivÃ´s
        # jÃ¡ tinham `pivos.json`: nenhuma medida resolve arte ambÃ­gua. Ã“culos
        # de aro grosso, franja sobre a sobrancelha, viseira meio
        # transparente -- nesses casos sÃ³ quem desenhou sabe onde estÃ¡ o
        # olho. O painel escreve `rosto.json` ao lado da folha, o
        # `preparar_assets.py` o copia para `partes.json` em `rosto_manual`,
        # e ele entra AQUI, por cima do que foi medido.
        #
        # As coordenadas sÃ£o da PEÃ‡A `cranio.png` como ela estÃ¡ no bucket --
        # que Ã© a imagem que a pessoa vÃª e clica no painel. `_centralizar`
        # depois infla a peÃ§a numa tela quadrada com o pivÃ´ no meio, e Ã©
        # esse deslocamento que se soma aqui. Pedir coordenadas da tela
        # inflada seria pedir que alguÃ©m calculasse `R - int(px)` de cabeÃ§a.
        manual = cfg.get("rosto_manual") or {}
        if manual and self.rosto and "cranio" in self.img:
            ox, oy = self._off_cranio
            def _p(v):
                return (float(v[0]) + ox, float(v[1]) + oy)
            usados = []
            if manual.get("olho_e") and manual.get("olho_d"):
                pe, pd = _p(manual["olho_e"]), _p(manual["olho_d"])
                # esquerda/direita sÃ£o as do QUADRO, nÃ£o as do personagem:
                # Ã© assim que o resto do motor as trata.
                if pe[0] > pd[0]:
                    pe, pd = pd, pe
                self.rosto["olhos"]["olho_e"]["cx"], self.rosto["olhos"]["olho_e"]["cy"] = pe
                self.rosto["olhos"]["olho_d"]["cx"], self.rosto["olhos"]["olho_d"]["cy"] = pd
                self.rosto["d_olhos"] = abs(pd[0] - pe[0])
                self.rosto["linha_olhos"] = (pe[1] + pd[1]) / 2.0
                self.rosto["eixo"] = (pe[0] + pd[0]) / 2.0
                usados.append("olhos")
            if manual.get("queixo") is not None:
                self.rosto["queixo"] = float(manual["queixo"]) + oy
                usados.append("queixo")
            if usados:
                print(f"[rosto] rosto.json a mao: {', '.join(usados)} "
                      f"(o resto continua medido)")
        if self.rosto:
            print(f"[rosto] olhos medidos: vao de {self.rosto['d_olhos']:.0f}px, "
                  f"linha em y={self.rosto['linha_olhos']:.0f}, "
                  f"queixo em y={self.rosto['queixo']:.0f}")
        elif "cranio" in self.img:
            print("[rosto] nao achei o par de olhos na peca do cranio; a boca e "
                  "as feicoes vao ser procuradas pela caixa da peca (regra antiga)")

        # --- o queixo existe mesmo? -----------------------------------
        self.boca = None            # (dx, dy, largura) relativos ao pivÃ´ do crÃ¢nio
        # curva e espessura de REPOUSO, medidas da boca que a arte desenhou
        self.boca_estilo = {"curva": 0.0, "esp": 0.0}
        if self.sem_expressao:
            # PERSONAGEM SEM EXPRESSÃƒO (30/08). O astronauta tem a viseira
            # escura: nÃ£o hÃ¡ rosto, e o motor ainda assim "achava olhos"
            # ali -- dois reflexos no vidro que a validaÃ§Ã£o por simetria
            # aceita. AnimÃ¡-los faria os reflexos deslizarem pelo capacete,
            # e desenhar uma boca poria um traÃ§o vermelho no meio do vidro.
            #
            # Com a marca, a cabeÃ§a continua girando e inclinando (Ã© ela que
            # dÃ¡ reaÃ§Ã£o de corpo), e a cara fica como a arte a desenhou. O
            # personagem serve para cena e para fala; o que ele nÃ£o faz Ã©
            # atuar com o rosto -- e quem escreve o roteiro precisa saber
            # disso, porque neste canal a piada costuma acontecer na cara.
            self.rosto_articulado = False
            self.img.pop("mandibula", None)
            print("[rosto] personagem marcado SEM EXPRESSAO: nem feicoes nem "
                  "boca desenhada; a cabeca ainda gira e inclina")
        elif "mandibula" not in self.img or _e_fiapo(self.img["mandibula"]):
            self.rosto_articulado = False
            self.img.pop("mandibula", None)     # fiapo em cena Ã© sujeira solta
            if "cranio" in self.img:
                tapado, caixa = _tapar_entalhe(self.img["cranio"], rosto=self.rosto)
                if caixa:
                    self.img["cranio"] = tapado
                    px, py = self.piv["cranio"]
                    bx0, by0, bx1, by1 = caixa
                    # a boca fica onde o desenhista pÃ´s o entalhe: mesma
                    # largura, mesma altura de centro. Nada Ã© chutado.
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
                    # caso ela Ã© apagada e redesenhada animada, senÃ£o o
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
        # feiÃ§Ãµes que sobraram como fiapo saem de cena pelo mesmo motivo: em
        # repouso elas caem sobre o prÃ³prio desenho e somem, mas qualquer
        # movimento de expressÃ£o as descola e vira traÃ§o solto no rosto
        for f in ("olho_e", "olho_d", "sobrancelha_e", "sobrancelha_d", "nariz"):
            if f in self.img and _e_fiapo(self.img[f]):
                print(f"[rosto] '{f}' e um fiapo de contorno, nao uma feicao; "
                      f"ignorando")
                self.img.pop(f, None)

        # --- as feiÃ§Ãµes estÃ£o desenhadas DENTRO do crÃ¢nio? ---------------
        # Quando a folha nÃ£o entrega olho e sobrancelha como peÃ§a (Ã© o caso
        # do Pal), elas sÃ£o recortadas de lÃ¡ e passam a se mexer como se
        # fossem peÃ§as. Ver _extrair_feicoes.
        self.feicoes = None
        self._cache_cara = {}
        if self.sem_expressao:
            pass                    # nada a recortar: ver o comentÃ¡rio acima
        elif "cranio" in self.img and not (self.tem("olho_e") and self.tem("olho_d")):
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
        """O cabelo vira PARTE do crÃ¢nio, uma peÃ§a sÃ³.

        POR QUE (defeito visto em 29/08, ao ligar a expressÃ£o facial)
            Bastava `cabeca_rot` valer 2 graus para o cabelo escorregar e
            abrir uma faixa de pele na testa. A causa Ã© o encaixe: o crÃ¢nio
            gira em torno do pivÃ´ dele (a base, no pescoÃ§o) e o cabelo em
            torno do DELE (no meio da franja), e os dois sÃ³ coincidem se o
            pivÃ´ do cabelo cair exatamente no ponto de saÃ­da marcado no
            crÃ¢nio. O segmentador nÃ£o mediu vÃ£o entre cabelo e crÃ¢nio
            (`vaos["cabelo"] == 0`), entÃ£o esse ponto Ã© estimado -- e alguns
            pixels de erro viram um degrau visÃ­vel assim que a cabeÃ§a
            inclina.

            NÃ£o hÃ¡ nada a ganhar em manter os dois separados: cabelo nÃ£o
            articula. Fundidos, giram como um bloco por construÃ§Ã£o, e o
            erro de encaixe deixa de existir em vez de ser calibrado.

        O pivÃ´ do crÃ¢nio Ã© preservado -- Ã© ele que o esqueleto usa para
        pendurar a cabeÃ§a no pescoÃ§o.
        """
        if "cabelo" not in self.img or "cranio" not in self.img:
            return
        saida = (self.saidas.get("cranio") or {}).get("cabelo")
        if not saida:
            return
        pc = self.pivos["cranio"]
        # vetor do pivÃ´ do crÃ¢nio atÃ© o ponto onde o cabelo encaixa, medido
        # na arte original: deslocamento Ã© invariante a recorte e a
        # centralizaÃ§Ã£o, entÃ£o vale igual na peÃ§a jÃ¡ processada
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
        """O crÃ¢nio com as feiÃ§Ãµes nas posiÃ§Ãµes que a expressÃ£o pede.

        Compor DENTRO da peÃ§a, e nÃ£o colar cada feiÃ§Ã£o na cena, Ã© o que faz
        a cara acompanhar a cabeÃ§a de graÃ§a: o crÃ¢nio jÃ¡ Ã© girado e
        posicionado pelo esqueleto, e tudo o que estiver desenhado nele vai
        junto. TambÃ©m Ã© o que mantÃ©m a ordem de sobreposiÃ§Ã£o correta sem
        acrescentar peÃ§a nenhuma ao ORDEM_Z.

        Com cache pela expressÃ£o arredondada: um vÃ­deo de 20 segundos tem
        ~430 frames e nÃ£o mais que algumas dezenas de caras distintas."""
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
        # as feiÃ§Ãµes sÃ£o medidas contra o PIVÃ”: o crÃ¢nio foi recomposto com
        # o cabelo dentro depois de elas serem recortadas, e o centro da
        # imagem mudou nessa hora. O pivÃ´, nÃ£o.
        cx, cy = float(base_piv[0]), float(base_piv[1])
        # ordem: sobrancelha depois do olho, para o cenho baixo poder
        # encostar na pÃ¡lpebra sem ficar por baixo dela
        for nome in ("olho_e", "olho_d", "sobrancelha_e", "sobrancelha_d"):
            spr = self.feicoes.get(nome)
            if spr is None:
                continue
            im = spr["img"]
            dx, dy = spr["dx"], spr["dy"]
            if nome.startswith("olho"):
                if piscando:
                    # PISCAR sem peÃ§a de olho fechado: um traÃ§o da largura do
                    # olho, na cor do contorno da prÃ³pria arte. Ã‰ o que a
                    # animaÃ§Ã£o cut-out faz -- e some junto com este remendo
                    # no dia em que a folha trouxer o olho como peÃ§a.
                    im = Image.new("RGBA", (spr["larg"], max(3, spr["alt"] // 3)),
                                   (0, 0, 0, 0))
                    d = ImageDraw.Draw(im)
                    esp = max(2, spr["alt"] // 7)
                    d.line([(1, im.height // 2), (im.width - 2, im.height // 2)],
                           fill=_cor_da_casca(spr["img"]) + (255,), width=esp)
                else:
                    sx, sy = float(ex.get("olho_sx", 1.0)), float(ex.get("olho_sy", 1.0))
                    if abs(sx - 1) > 0.02 or abs(sy - 1) > 0.02:
                        im = _reamostrar(im, (max(2, int(im.width * sx)),
                                              max(2, int(im.height * sy))))
                    dy += float(ex.get("olho_dy", 0.0)) * hc
            else:
                # sobe no mÃ¡ximo atÃ© onde hÃ¡ testa (ver `teto` em
                # _extrair_feicoes): passar disso pÃµe a sobrancelha dentro
                # do cabelo, e o espanto vira defeito
                d = float(ex.get("sobrancelha_dy", 0.0)) * hc
                dy += max(d, -float(spr.get("teto", hc)))
                rot = float(ex.get("sobrancelha_rot", 0.0))
                if abs(rot) > 0.5:
                    # sinal oposto nos dois lados: o que se lÃª como raiva Ã© a
                    # ponta INTERNA descendo nas duas, nÃ£o as duas girando
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
        """RÃ©gua do rosto, em pixels da ARTE (antes da escala de cena).

        Todo deslocamento de expressÃ£o Ã© fraÃ§Ã£o disto. Se a folha nova vier
        maior ou menor, a cara continua na mesma proporÃ§Ã£o sem ninguÃ©m
        reajustar constante nenhuma."""
        return float(self.tam.get("cranio", (1, 120))[1])

    def fracao_da_palma(self, nome):
        """Onde fica a PALMA dentro da peÃ§a da mÃ£o, em fraÃ§Ã£o do osso.

        POR QUE (02/09, item 4 do dono do projeto: *"personagem segurando
        celular pelo pulso"*)
            O motor colava o objeto a **0,30** do comprimento da mÃ£o a
            partir do pivÃ´, e o pivÃ´ Ã© o PUNHO. Medido nas quatro folhas
            disponÃ­veis, o centro de massa da mÃ£o estÃ¡ a **0,42 a 0,47**:

                pal      0,47 / 0,46      maria    0,43 / 0,42
                senhora  0,46 / 0,44      soldado  0,44 / 0,43

            Ou seja, a fraÃ§Ã£o cravada punha o objeto a um terÃ§o do caminho
            entre o punho e a ponta dos dedos -- que Ã©, literalmente,
            segurar pelo pulso.

        A fraÃ§Ã£o passa a ser MEDIDA na arte, como o pivÃ´, a linha do chÃ£o e
        a altura do ator: ela sai do desenho e vale para qualquer folha
        nova, sem ninguÃ©m recalibrar (Ã© a exigÃªncia do dono do projeto de
        que nada seja calibrado Ã  mÃ£o por personagem).

        O limite existe para arte estranha: uma mÃ£o desenhada como um
        risco daria um centro de massa colado no pivÃ´ ou alÃ©m da ponta, e
        os dois extremos sÃ£o piores que o palpite.
        """
        f = getattr(self, "_frac_palma", None)
        if f is None:
            f = self._frac_palma = {}
        if nome in f:
            return f[nome]
        valor = 0.44
        try:
            img, piv = self.p(nome)
            a = np.asarray(img)[..., 3] > 128
            ys, xs = np.nonzero(a)
            comp = float(self.comp.get(nome, 0.0))
            if len(ys) and comp > 1.0:
                d = math.hypot(float(xs.mean()) - piv[0],
                               float(ys.mean()) - piv[1])
                valor = max(0.30, min(0.60, d / comp))
        except Exception:                                     # noqa: BLE001
            pass
        f[nome] = valor
        return valor

    def variar(self, nome, sx, sy):
        """A peÃ§a reescalada em x e y, com o pivÃ´ acompanhando.

        `colar` sÃ³ sabe escala uniforme, e olho semicerrado Ã© achatamento
        vertical puro -- Ã© a diferenÃ§a entre `bravo` e `bravo com os olhos
        do neutro`. Redimensionar a peÃ§a JÃ CENTRALIZADA mantÃ©m o pivÃ´ no
        centro do quadrado, entÃ£o basta escalar a coordenada.

        Com cache: sÃ£o dois olhos por frame e ~430 frames por vÃ­deo, e a
        expressÃ£o muda pouco entre frames vizinhos. Arredondar a chave em
        2 casas colapsa quase tudo em meia dÃºzia de variantes."""
        sx, sy = round(float(sx), 2), round(float(sy), 2)
        if abs(sx - 1.0) < 0.02 and abs(sy - 1.0) < 0.02:
            return self.img[nome], self.piv[nome]
        chave = (nome, sx, sy)
        if chave not in self._cache_var:
            img, piv = self.img[nome], self.piv[nome]
            nl, na = max(2, int(img.width * sx)), max(2, int(img.height * sy))
            self._cache_var[chave] = (_reamostrar(img, (nl, na)),
                                      (piv[0] * sx, piv[1] * sy))
        return self._cache_var[chave]


def _tri(v):
    """Um membro pode vir com 2 ou 3 Ã¢ngulos. Spec antigo manda 2 (ombro,
    cotovelo) porque nÃ£o existia pulso; a terceira articulaÃ§Ã£o entra
    zerada e nada quebra."""
    v = list(v) if isinstance(v, (list, tuple)) else [float(v)]
    return (v + [0.0, 0.0, 0.0])[:3]


ABERTURA_MAXILAR = 0.38     # fraÃ§Ã£o da altura do queixo que a boca desce

# PeÃ§as que fecham a junta mesmo sem vÃ£o medido (ver Personagem.__init__).
#
# `abdomen` entrou em 29/08: ele Ã© a RAIZ do esqueleto, e o segmentador sÃ³
# mede vÃ£o entre uma peÃ§a e o pai dela -- a raiz nÃ£o tem pai, entÃ£o nunca
# ganhou medida. O efeito aparecia como uma faixa branca contornando o
# quadril: o peito e as coxas engrossavam em direÃ§Ã£o a ele, e ele nÃ£o
# engrossava para lado nenhum, deixando meio vÃ£o aberto na cintura e na
# virilha em todos os frames.
FECHA_MESMO_SEM_MEDIDA = ("mandibula", "abdomen")

# Interior da boca: o que se vÃª quando o maxilar desce. Cor de dentro de
# boca de desenho -- escura o bastante para ler como buraco, quente o
# bastante para nÃ£o virar um retÃ¢ngulo preto no meio da cara.
COR_BOCA = (92, 42, 38, 255)


def _angulo(nome, rig, boca_nivel):
    """Ã‚ngulo ABSOLUTO de uma peÃ§a, em graus de tela.

    A tabela FONTE_ANGULO diz de onde cada peÃ§a tira o Ã¢ngulo, entÃ£o
    acrescentar uma peÃ§a nova ao esqueleto nÃ£o exige tocar aqui."""
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



def _destacar_objeto(img, esp=None):
    """PÃµe um contorno escuro em volta do objeto.

    POR QUE (visto no vÃ­deo de 28/08 Ã  noite)
        A esquete era sobre um BOLETO, o boleto ficou a esquete inteira na
        mÃ£o do Pal, e nÃ£o aparece: papel branco com traÃ§o fino, sobre um
        cenÃ¡rio claro, some. O objeto Ã© a Ã¢ncora da piada -- o roteiro Ã©
        cobrado a ter um justamente por isso --, e um objeto invisÃ­vel Ã© o
        mesmo que nÃ£o ter objeto nenhum.

        As peÃ§as do personagem nÃ£o tÃªm esse problema porque a bÃ­blia visual
        exige `thick uniform black outline` nelas. O objeto vem de outro
        pedido ao gerador e nem sempre volta com contorno grosso.

    COMO
        Dilatar o alfa e pintar de escuro por baixo do prÃ³prio objeto. NÃ£o
        Ã© sombra projetada (que precisaria saber de onde vem a luz): Ã© o
        mesmo recurso do desenho animado, a linha que separa a figura do
        fundo. Funciona com qualquer arte e nÃ£o depende da cor dela.

    A espessura sai da MENOR dimensÃ£o e tem teto: pela maior, a carteira --
    que Ã© larga e baixa -- ganhava uma moldura preta de 6px que competia
    com o prÃ³prio desenho. O que se quer Ã© a linha que separa do fundo, nÃ£o
    um quadro em volta.

    A imagem CRESCE `r` de cada lado antes de dilatar. Sem isso o contorno
    Ã© cortado onde o objeto encosta na borda da arte, e o resultado Ã© uma
    linha em trÃªs lados -- pior que nenhuma.
    """
    base = img.convert("RGBA")
    r = esp if esp is not None else max(2, min(4, int(round(min(base.size) * 0.02))))
    folgada = Image.new("RGBA", (base.width + 2 * r, base.height + 2 * r),
                        (0, 0, 0, 0))
    folgada.alpha_composite(base, (r, r))
    alfa = np.asarray(folgada)[..., 3]
    if not alfa.any():
        return img
    # dilataÃ§Ã£o por deslocamento: r Ã© pequeno (2 a 4px), e um max sobre os
    # deslocamentos custa menos que uma convoluÃ§Ã£o
    grosso = alfa.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy > r * r:
                continue
            grosso = np.maximum(grosso, np.roll(np.roll(alfa, dy, 0), dx, 1))
    fora = Image.new("RGBA", folgada.size, (26, 22, 20, 0))
    fora.putalpha(Image.fromarray((grosso * 0.80).astype(np.uint8)))
    fora.alpha_composite(folgada)
    return fora


# A linha de separaÃ§Ã£o clara: quanto ela avanÃ§a PARA FORA do contorno escuro
# que `_destacar_objeto` jÃ¡ assou na arte. Dois pixels bastam para o olho
# separar as duas manchas; mais que isso lÃª como brilho em volta da coisa, e
# halo em volta da figura Ã© queixa registrada do dono do projeto (30/08).
SEPARA_OBJETO_PX = int(os.environ.get("SEPARA_OBJETO_PX", "2"))
# Abaixo desta luminÃ¢ncia o que estÃ¡ atrÃ¡s Ã© ESCURO, e a linha escura do
# objeto desaparece nele. 110 de 255: a calÃ§a da Maya mede 74 e a do Pal 46,
# a pele mede 205 e a camisa dela 150 -- o corte cai na folga entre os dois
# grupos, e nÃ£o no meio de nenhum deles.
FUNDO_ESCURO_LUM = 110


def _colar_objeto(base, oi, opv, palma, ang, esc):
    """Cola o objeto e desenha a separaÃ§Ã£o DELE contra o que estÃ¡ atrÃ¡s.

    POR QUE (02/09, voltas 088 e 091: *o boleto na mÃ£o baixa e o celular
    lendo como adesivo colado Ã  coxa*, em cinco dos dezesseis quadros)
        `_destacar_objeto` pÃµe um contorno ESCURO em volta do objeto, e o
        motivo dele estÃ¡ escrito lÃ¡: em 28/08 um boleto de papel branco, com
        traÃ§o fino, sumia sobre um cenÃ¡rio claro. A linha escura resolveu
        aquilo e passou a valer para tudo.

        SÃ³ que em REPOUSO o que estÃ¡ atrÃ¡s do objeto nÃ£o Ã© o cenÃ¡rio: Ã© a
        ROUPA de quem o segura, e a roupa Ã© escura em quase todo o elenco (a
        calÃ§a da Maya mede 74 de luminÃ¢ncia, a do Pal 46). Linha escura sobre
        calÃ§a escura nÃ£o separa nada -- o celular, o contorno dele e a coxa
        viram uma mancha sÃ³, que Ã© exatamente o adesivo que se vÃª no vÃ­deo.
        A carteira laranja do Pal, na mesma pose e no mesmo lugar, lÃª perfeita:
        o defeito nunca foi a posiÃ§Ã£o, foi o CONTRASTE.

        Uma linha fixa nÃ£o pode separar nos dois fundos, porque os dois fundos
        sÃ£o opostos. EntÃ£o ela deixa de ser fixa: aqui se mede a luminÃ¢ncia do
        que ficou atrÃ¡s, pixel por pixel, e onde ela Ã© escura a separaÃ§Ã£o sai
        CLARA. Onde Ã© clara (ou nÃ£o hÃ¡ nada atrÃ¡s -- o objeto recorta contra o
        cenÃ¡rio, que entra depois em `montar_frame`), fica sÃ³ o contorno
        escuro que jÃ¡ existia, e nada muda.

    O anel sai por bbox, e nÃ£o no quadro inteiro: dilatar 1080x1920 por
    deslocamento custa (2r+1)Â² passadas de dois milhÃµes de pixels, por ator e
    por frame. Na caixa do objeto sÃ£o ~300px de lado.
    """
    camada = Image.new("RGBA", base.size, (0, 0, 0, 0))
    colar(camada, oi, opv, palma, ang, esc)
    bb = camada.getbbox()
    if not bb:
        return
    r = SEPARA_OBJETO_PX
    x0, y0 = max(bb[0] - r - 1, 0), max(bb[1] - r - 1, 0)
    x1, y1 = min(bb[2] + r + 1, base.size[0]), min(bb[3] + r + 1, base.size[1])
    ao = np.asarray(camada)[y0:y1, x0:x1, 3]
    dentro = ao > 32
    grosso = dentro.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy > r * r:
                continue
            grosso |= np.roll(np.roll(dentro, dy, 0), dx, 1)
    anel = grosso & ~dentro
    if anel.any():
        b = np.asarray(base)[y0:y1, x0:x1]
        # SÃ“ ONDE HÃ CORPO ATRÃS. Onde a base Ã© transparente o objeto recorta
        # contra o cenÃ¡rio, e o cenÃ¡rio Ã© o caso que a linha escura jÃ¡
        # resolve -- pÃ´r uma linha clara ali seria inventar halo onde o
        # problema nÃ£o existe.
        atras = b[..., 3] > 32
        lum = (0.299 * b[..., 0] + 0.587 * b[..., 1] + 0.114 * b[..., 2])
        escuro = anel & atras & (lum < FUNDO_ESCURO_LUM)
        if escuro.any():
            fatia = Image.new("RGBA", (x1 - x0, y1 - y0), (238, 236, 230, 0))
            fatia.putalpha(Image.fromarray((escuro * 235).astype(np.uint8)))
            base.alpha_composite(fatia, (x0, y0))
    base.alpha_composite(camada)


def _espalhar(img, r):
    """Estende as cores da arte para FORA do alfa, r pixels.

    Cada passo empurra o que Ã© opaco um pixel em oito direÃ§Ãµes e mantÃ©m o que
    jÃ¡ existia por cima, entÃ£o a cor que sai Ã© a do pixel de arte mais
    prÃ³ximo. Ã‰ isto que diferencia esta funÃ§Ã£o de um desfoque: desfoque
    MISTURA os vizinhos, e num vÃ£o as duas peÃ§as vizinhas apresentam uma Ã 
    outra o prÃ³prio contorno preto -- misturar dois pretos com uma fresta no
    meio dÃ¡ cinza, que foi a "ponte entre as peÃ§as" de 03/09.

    Estender nÃ£o mistura nada: no pescoÃ§o a cor vem da pele, na cintura vem
    da calÃ§a, e o traÃ§o preto do desenhista continua sendo o traÃ§o.
    """
    # SÃ“ PIXEL SÃ“LIDO SERVE DE FONTE (04/09).
    #
    # A primeira versÃ£o estendia a imagem como veio, e as bordas da arte sÃ£o
    # ANTI-SERRILHADAS: a Ãºltima fileira de pixels tem alfa parcial. Ao
    # estender, esses pixels meio transparentes viajavam para dentro do vÃ£o, e
    # a mÃ¡scara do fecho depois os punha em opacidade total -- o que se via era
    # uma faixa PÃLIDA no cotovelo, no punho e no joelho, mais clara que as
    # duas peÃ§as vizinhas. Foi o que sobrou da queixa de 04/09 depois de a
    # ponte cinza sair.
    #
    # Cortando o alfa em 200, a fonte da extensÃ£o passa a ser sÃ³ o miolo da
    # arte, e a cor que preenche o vÃ£o Ã© a cor de verdade da peÃ§a.
    a = np.asarray(img.convert("RGBA")).copy()
    a[..., 3] = np.where(a[..., 3] > 200, 255, 0).astype(np.uint8)
    fora = Image.fromarray(a, "RGBA")
    for _ in range(int(r)):
        base = fora.copy()
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (1, -1), (-1, 1), (1, 1)):
            desl = Image.new("RGBA", fora.size, (0, 0, 0, 0))
            desl.paste(fora, (dx, dy))
            base = Image.alpha_composite(desl, base)
        fora = base
    return fora


# O TRAÃ‡O ACABA AQUI: 32 DE LUMINÃ‚NCIA (04/09, v034).
#
# O nÃºmero Ã© da ARTE, e a primeira tentativa (90) estava errada de um jeito
# que sÃ³ a mediÃ§Ã£o mostrou. Percentis de luminÃ¢ncia por peÃ§a, no elenco:
#
#     pal/peito         p2=1   p10=87   p50=146     a camisa
#     pal/perna_sup     p2=0   p10=6    p50=58      a calÃ§a, escura
#     maya/perna_sup    p2=2   p10=7    p50=90
#     preso/peito       p2=0   p10=225  p50=233
#
# O traÃ§o vive de 0 a 20 em todas elas; o miolo mais escuro do elenco Ã© a
# calÃ§a do Pal, em 56. Com o limiar em 90 a CALÃ‡A INTEIRA virava traÃ§o --
# sobravam 122 pixels de miolo numa peÃ§a de 8.452 --, e o espalhamento
# preenchia a cintura com o cinza desses poucos pixels claros. Era essa a
# granulaÃ§Ã£o cinza sob a camisa. Trinta e dois separa os dois grupos com
# folga dos dois lados.
LUM_TRACO = int(os.environ.get("LUM_TRACO", "32"))


def _fonte_do_miolo(img):
    """A arte com alfa sÃ³ no MIOLO: sem o traÃ§o e sem a borda.

    Ã‰ a fonte de cor de todo fecho deste motor. Sai daqui, e nÃ£o da arte como
    estÃ¡, porque o pixel de arte mais prÃ³ximo de qualquer fenda Ã© o contorno
    da peÃ§a -- ver `_sem_traco`, que conta a histÃ³ria inteira.
    """
    a = np.asarray(img.convert("RGBA"))
    op = a[..., 3] > 200
    # E A FONTE COMEÃ‡A DOIS PIXELS PARA DENTRO (04/09).
    #
    # Cortar o alfa em 200 nÃ£o bastou: a peÃ§a foi recortada de uma folha de
    # fundo BRANCO, e a fileira de transiÃ§Ã£o da borda ficou opaca e clara. Ela
    # passa em `lum >= LUM_TRACO` com folga, vira fonte legÃ­tima, e o
    # espalhamento leva branco de folha para dentro da fenda -- as manchas
    # claras que sobraram na cintura do Pal depois de o preto sair.
    #
    # Erodir o opaco antes de escolher o miolo resolve as duas sujeiras de
    # borda de uma vez, e nÃ£o custa nada: a cor de uma peÃ§a Ã© a mesma dois
    # pixels para dentro.
    op = np.asarray(Image.fromarray((op * 255).astype(np.uint8))
                    .filter(ImageFilter.MinFilter(5))) > 128
    lum = a[..., :3].astype(np.int16).max(axis=2)
    miolo = op & (lum >= LUM_TRACO)
    if not miolo.any():
        return None
    fonte = Image.fromarray(a.copy(), "RGBA")
    fonte.putalpha(Image.fromarray((miolo * 255).astype(np.uint8)))
    return fonte


def _sem_traco(img, r=6):
    """A mesma arte, com o CONTORNO substituÃ­do pela cor de dentro.

    POR QUE ISTO EXISTE, E POR QUE Ã‰ O CONSERTO DAS CINCO TENTATIVAS (04/09)
        Fechar o vÃ£o foi tentado cinco vezes -- anel da cor do contorno, anel
        da cor de dentro, fechamento por desfoque, anel por `_espalhar` e a
        extensÃ£o da peÃ§a na direÃ§Ã£o da junta -- e as cinco produziram a MESMA
        queixa do dono do projeto: uma faixa escura em volta de cada junta. O
        v034 Ã© a quinta, e nela a faixa saiu serrilhada em pescoÃ§o, ombro,
        cotovelo, cintura, quadril e joelho.

        As quatro primeiras foram diagnosticadas como problema de COR, e a
        quinta como problema de DIREÃ‡ÃƒO. Nenhuma das duas leituras estava
        completa, e `ferramentas/tinta_junta.py` mostra o que faltava: dos
        pixels que o fecho ACRESCENTA ao corpo, **62% sÃ£o escuros** (87% na
        Maya). O fecho nÃ£o estÃ¡ tapando o vÃ£o com arte -- estÃ¡ tapando com
        TRAÃ‡O.

        A causa Ã© a mesma nos dois caminhos que sobraram, e Ã© uma frase:
        **o pixel de arte mais prÃ³ximo de qualquer fenda Ã© o contorno da
        peÃ§a.** `_espalhar` estende o vizinho mais prÃ³ximo, e a extensÃ£o
        desloca a peÃ§a inteira com a borda dela junto -- as duas, portanto,
        prolongam o traÃ§o. Enquanto a fonte da cor for a borda, trocar de
        tÃ©cnica sÃ³ troca o formato da faixa preta.

    O QUE ELA FAZ
        Apaga do alfa os pixels escuros (o traÃ§o) e deixa a cor do miolo
        crescer sobre eles. A forma nÃ£o muda -- o alfa que sai Ã© o alfa que
        entrou --, sÃ³ a cor: uma peÃ§a cujo interior chega atÃ© a prÃ³pria
        borda. Usada como FONTE do fecho, o que entra na fenda Ã© pele no
        pescoÃ§o, camisa no ombro e calÃ§a na cintura.

        A arte original continua sendo desenhada por cima, entÃ£o o traÃ§o que
        o desenhista fez segue lÃ¡, uma vez sÃ³, no lugar dele.
    """
    # PEÃ‡A QUE Ã‰ SÃ“ TRAÃ‡O CONTINUA COMO ESTÃ. Um fiapo de contorno (a
    # sobrancelha recortada do crÃ¢nio) nÃ£o tem miolo nenhum, e inventar cor
    # para ele seria pior que deixÃ¡-lo escuro -- ele Ã© escuro mesmo.
    fonte = _fonte_do_miolo(img)
    if fonte is None:
        return img.copy()
    cheio = _espalhar(fonte, int(r))
    saida = Image.new("RGBA", img.size, (0, 0, 0, 0))
    saida.paste(cheio, (0, 0))
    saida.putalpha(img.split()[3])
    return saida


# ZERO: O VÃƒO NÃƒO SE TAPA. TERCEIRA TENTATIVA, E A ÃšLTIMA (03/09, Ã  noite).
#
# Queixa do dono do projeto sobre o v001: *"junÃ§Ã£o de peÃ§as, ele simplesmente
# criou uma 'ligaÃ§Ã£o' entre as peÃ§as, Ã© completamente desnecessÃ¡rio"*.
#
# Ele estÃ¡ certo, e o A/B (`RAIO_FECHO=0` contra 9, mesmo spec do v001) nÃ£o
# deixa dÃºvida: **com o fecho hÃ¡ faixas escuras no punho, no cotovelo, na
# cintura, no joelho e no tornozelo; sem ele, o corpo sai limpo.** A causa do
# escurecimento Ã© direta -- o preenchimento lÃª a cor por desfoque, e no vÃ£o as
# duas peÃ§as vizinhas apresentam uma para a outra o prÃ³prio CONTORNO PRETO;
# desfocar dois traÃ§os pretos separados por uma fresta dÃ¡ cinza escuro, e o
# resultado Ã© uma ponte pintada exatamente onde nÃ£o devia haver nada.
#
# TRÃŠS TENTATIVAS, TRÃŠS ARTEFATOS, E O MESMO ERRO DE PREMISSA:
#
#   Â· anel da cor do CONTORNO (atÃ© 02/09)  -> faixa preta de boneco articulado
#   Â· anel da cor de DENTRO   (02 a 03/09) -> esparadrapo rosa/azul na junta
#   Â· fechamento morfolÃ³gico  (03/09)      -> ponte cinza entre as peÃ§as
#
# A premissa errada Ã© a de que o vÃ£o APARECE. Ela vinha do run #13, quando o
# personagem era desenhado sem cenÃ¡rio e depois com cenÃ¡rio atrÃ¡s -- e a
# conclusÃ£o "cada vÃ£o virou um rasgo por onde a rua aparece" nunca foi
# remedida depois que a geometria dos pivÃ´s melhorou. Nas poses e escalas de
# hoje as peÃ§as vizinhas jÃ¡ se sobrepÃµem o bastante: a prÃ©via com
# `RAIO_FECHO=0` mostra ombro, cotovelo, punho, quadril, joelho e tornozelo
# fechados, com o traÃ§o da prÃ³pria arte fazendo a emenda.
#
# **Cutout de papel se emenda por sobreposiÃ§Ã£o, nÃ£o por remendo pintado.** Se
# um dia uma folha nova trouxer vÃ£o largo demais e ele aparecer de verdade, o
# conserto Ã© na SEGMENTAÃ‡ÃƒO (medir melhor o pivÃ´) ou na arte, nÃ£o aqui: este
# ponto do cÃ³digo sÃ³ sabe pintar por cima, e pintar por cima sempre apareceu.
# QUATRO E DE VOLTA (04/09). Zerar em 03/09 tirou a ponte cinza e devolveu o
# defeito que o fecho existia para resolver -- o dono do projeto viu na volta
# seguinte: *"cortes em algumas pecas do personagem, linhas irregulares
# visiveis"*. Sao os vaos do pescoco, do ombro e da cintura deixando o fundo
# passar.
#
# O que estava errado nunca foi FECHAR: era a COR com que se fechava. As tres
# tentativas pintavam uma cor inventada (contorno, preenchimento, desfoque) e
# as tres apareceram. Agora o vao e' preenchido com o pixel de ARTE mais
# proximo (`_espalhar`), que e' o que um cut-out de papel faz quando as pecas
# se sobrepoem.
#
# Quatro em vez de nove: o raio so precisa cobrir metade da fenda, e as
# fendas medidas vao de 5 a 14 px na escala da folha -- que em cena, com a
# escala de dois em cena, ficam bem menores. Raio grande alcanca separacoes
# legitimas (os dedos, o vao entre as pernas).
# OITO, E MAIS BARATO QUE OS QUATRO DE ONTEM (04/09, ciclo 25). O fechamento
# passou a rodar em meia resoluÃ§Ã£o (ver `_fechar_vaos_do_corpo`), entÃ£o o raio
# que fecha o pescoÃ§o da Maya -- o buraco por onde o azulejo do banheiro
# aparecia debaixo do queixo, na prÃ©via do v022 -- custa um quarto do que o
# raio antigo custava. O A/B: com 4 sobra um quadrado de fundo sob o queixo;
# com 8 o pescoÃ§o fecha e lÃª como sombra, que Ã© o que um cut-out faz.
# ZERO, E DESTA VEZ POR DECISÃƒO DE ESTILO (04/09, do dono do projeto).
#
#   *"vi um video e novamente foi feito algo para tentar 'tampar os vÃ£os',
#    isso Ã© parte do estilo do canal, desfaÃ§a isso"*
#
# **O vÃ£o entre as peÃ§as nÃ£o Ã© defeito: Ã© o traÃ§o do canal.** Ele Ã© o que faz
# a coisa ler como recorte de papel, e Ã© por isso que a queixa voltou toda vez
# que alguÃ©m o fechou -- seis vezes, por seis caminhos diferentes:
#
#   Â· anel da cor do CONTORNO (atÃ© 02/09)   -> faixa preta de boneco articulado
#   Â· anel da cor de DENTRO   (02 a 03/09)  -> esparadrapo rosa e azul na junta
#   Â· fechamento por desfoque (03/09)       -> ponte cinza entre as peÃ§as
#   Â· anel por `_espalhar`    (04/09)       -> cotoveleiras e joelheiras pretas
#   Â· extensÃ£o da peÃ§a na direÃ§Ã£o da junta  -> traÃ§o duplicado, serrilhado
#   Â· fechamento do corpo montado com a cor do miolo -> a emenda some, e com
#                                              ela o estilo
#
# As seis foram lidas como "cor errada", "direÃ§Ã£o errada", "fonte errada".
# Nenhuma dessas leituras estava certa: **a premissa Ã© que estava errada.** O
# vÃ£o devia ficar. As rÃ©guas que mediam isso (`junta.py`, `tinta_junta.py`)
# medem bem o que medem e nÃ£o sabem disto -- nenhuma rÃ©gua deste projeto pode
# dizer que uma escolha de estilo Ã© um defeito.
#
# `RAIO_FECHO=8` reproduz o fechamento antigo para um A/B, e Ã© sÃ³ para isso
# que a variÃ¡vel continua existindo.
RAIO_FECHO = int(os.environ.get("RAIO_FECHO", "0"))


def _fechar_vaos_do_corpo(base):
    """Tapa as fendas ENTRE as peÃ§as, no corpo jÃ¡ montado.

    POR QUE ASSIM, E NÃƒO ENGROSSANDO CADA PEÃ‡A (03/09)
        A folha Ã© um BONECO DE PAPEL: cada parte tem contorno prÃ³prio e um
        vÃ£o branco a separa da vizinha (lei 5). O vÃ£o Ã© o que permite
        segmentar a folha e continua certo. Com cenÃ¡rio atrÃ¡s, porÃ©m, cada
        vÃ£o vira uma fresta por onde a rua aparece.

        AtÃ© hoje o conserto era dilatar CADA PEÃ‡A e devolver a arte original
        por cima (`_fechar_vao`). O problema Ã© geomÃ©trico e nÃ£o tem cor que
        resolva: a dilataÃ§Ã£o cresce em TODAS as direÃ§Ãµes, e o pedaÃ§o dela
        que fica fora da silhueta da peÃ§a Ã© uma tira visÃ­vel em volta da
        junta. Pintada de escuro, vira faixa preta de boneco articulado;
        pintada com a cor de dentro, vira esparadrapo. As duas foram vistas
        e reprovadas pelo dono do projeto, em 02/09 e em 03/09.

    O QUE MUDA
        O fecho passa a ser uma operaÃ§Ã£o de FECHAMENTO (dilatar e depois
        erodir com o mesmo pincel) sobre o alfa do corpo inteiro, depois de
        todas as peÃ§as compostas. Duas propriedades tornam isto correto onde
        o anel era errado:

          1. um fechamento sÃ³ acrescenta pixel onde havia uma CONCAVIDADE
             mais estreita que o pincel. A silhueta externa â€” as costas, a
             barriga, o alto da cabeÃ§a â€” nÃ£o tem vizinha nenhuma e nÃ£o muda;
          2. a cor nÃ£o Ã© escolhida: ela Ã© lida do prÃ³prio entorno, por um
             desfoque do que jÃ¡ estÃ¡ composto. No cotovelo ela vem do braÃ§o,
             na cintura vem da calÃ§a, na manga vem da manga.

        A arte original volta por cima no fim, entÃ£o o traÃ§o que o
        desenhista fez continua sendo o contorno â€” o fecho sÃ³ existe DENTRO
        da fenda, atrÃ¡s de tudo.

    O custo Ã© uma dilataÃ§Ã£o e uma erosÃ£o na caixa do personagem (~600x1200),
    as duas em C dentro do PIL, mais um desfoque: uns poucos milissegundos
    por ator e por frame.
    """
    bb = base.getbbox()
    r = RAIO_FECHO
    if not bb or r <= 0:
        return base
    x0, y0 = max(bb[0] - r, 0), max(bb[1] - r, 0)
    x1, y1 = min(bb[2] + r, base.width), min(bb[3] + r, base.height)
    corte = base.crop((x0, y0, x1, y1))
    alfa = corte.split()[3]
    # O FECHAMENTO SE FAZ NA METADE DA RESOLUÃ‡ÃƒO (04/09, ciclo 25).
    #
    # `MaxFilter(k)` do PIL Ã© um filtro de posto ingÃªnuo: custa kÂ² por pixel.
    # Medido numa caixa de personagem tÃ­pica (620x1300), o par dilata-erode
    # custa **396 ms por ator e por frame** com raio 4 -- vinte e quatro
    # minutos de CPU num vÃ­deo de 1800 quadros com dois em cena. Ele cabe hoje
    # porque o resto Ã© rÃ¡pido, e por isso ninguÃ©m tinha medido; subir o raio
    # para 8, que Ã© o que o pescoÃ§o da Maya pedia, custaria 1,66 s por ator e
    # por frame e derrubaria o render.
    #
    # QUAL Ã‰ O TETO, DE VERDADE (corrigido em 04/09): nÃ£o sÃ£o os 18 minutos do
    # Action -- eles acabaram em 30/08 e o `render.yml` dÃ¡ **90**. Quem manda
    # aqui Ã© `lote_video.TETO_VOLTA_S`, que abandona a volta aos **35 min**, e
    # os renders desta tarde estÃ£o em 23 a 26. A margem Ã© de nove minutos, nÃ£o
    # de nenhum: Ã© pouca do mesmo jeito, mas pela razÃ£o certa.
    #
    # Reduzir o alfa pela metade antes de filtrar troca as duas contas de
    # lugar: sÃ£o quatro vezes menos pixels E um pincel de metade do diÃ¢metro
    # para o mesmo alcance em pixels de tela. Um raio 8 na tela sai por um
    # pincel 4 sobre um quarto da Ã¡rea -- **dezesseis vezes mais barato que
    # fazer o mesmo em tamanho cheio, e quatro vezes mais barato que o raio 4
    # de hoje**.
    #
    # O que se perde Ã© precisÃ£o de um pixel na borda da fenda, e ela nÃ£o
    # importa: o que sai daqui Ã© a mÃ¡scara de uma FRESTA que vai ficar ATRÃS
    # da arte original. Quem decide o que se vÃª continua sendo a peÃ§a.
    meio = ((alfa.width + 1) // 2, (alfa.height + 1) // 2)
    k = 2 * max(1, r // 2) + 1
    fechado = (alfa.resize(meio, Image.BILINEAR)
                   .filter(ImageFilter.MaxFilter(k))
                   .filter(ImageFilter.MinFilter(k))
                   .resize(alfa.size, Image.BILINEAR))
    a0 = np.asarray(alfa)
    a1 = np.asarray(fechado)
    fenda = (a1 > 128) & (a0 <= 128)
    if not fenda.any():
        return base
    # A COR VEM DO PIXEL DE ARTE MAIS PRÃ“XIMO, E NÃƒO DE UM DESFOQUE (04/09).
    #
    # A primeira versÃ£o usava `GaussianBlur` e produziu a queixa de 03/09
    # (*"criou uma ligaÃ§Ã£o entre as peÃ§as"*): desfocar MISTURA os vizinhos, e
    # no vÃ£o as duas peÃ§as apresentam uma Ã  outra o prÃ³prio contorno preto --
    # dois pretos com uma fresta no meio dÃ£o cinza, e o que se via era uma
    # ponte pintada entre as peÃ§as.
    #
    # `_espalhar` estende, nÃ£o mistura: no pescoÃ§o a cor vem da pele, na
    # cintura vem da calÃ§a, e o traÃ§o do desenhista continua sendo o traÃ§o.
    #
    # E A FONTE DELE Ã‰ O MIOLO, NÃƒO A ARTE COMO ESTÃ (04/09, v034). Estender
    # "o pixel de arte mais prÃ³ximo" da fenda entrega sempre o CONTORNO, que Ã©
    # o que estÃ¡ na borda de toda peÃ§a -- e foi assim que a fresta virou faixa
    # preta serrilhada no v034, com 62% de pixel escuro no que o fecho
    # acrescenta (`ferramentas/tinta_junta.py`). `_sem_traco` deixa a cor de
    # dentro crescer sobre a borda ANTES do espalhamento, e aÃ­ o que preenche
    # a fenda Ã© pele, camisa ou calÃ§a. Ver a docstring dela: Ã© o conserto
    # comum das cinco tentativas de fechar o vÃ£o.
    #
    # As duas operaÃ§Ãµes rodam em MEIA RESOLUÃ‡ÃƒO, como o fechamento acima e
    # pelo mesmo motivo -- e aqui isto nÃ£o Ã© sÃ³ economia: `_espalhar` custa r
    # passadas sobre a caixa inteira, entÃ£o o par sai oito vezes mais barato
    # que o espalhamento em tamanho cheio que estava no ar.
    # UMA PASSADA SÃ“, DO MIOLO ATÃ‰ FORA DA FENDA (04/09). A primeira versÃ£o
    # chamava `_sem_traco` (que espalha r para cobrir o traÃ§o) e espalhava
    # outra vez para sair da peÃ§a: 2r iteraÃ§Ãµes, e `_espalhar` Ã© metade do
    # custo desta funÃ§Ã£o no perfil. Aqui a forma da peÃ§a nÃ£o importa -- o que
    # se usa Ã© sÃ³ o pedaÃ§o que cai DENTRO da fenda --, entÃ£o uma passada de
    # `r + 4` do miolo cobre o traÃ§o e a fenda de uma vez. Quatro Ã© a largura
    # do contorno mais grosso do elenco, medida em `contorno.py`.
    meio_img = corte.resize(meio, Image.NEAREST)
    fonte = _fonte_do_miolo(meio_img)
    espalhado = _espalhar(fonte if fonte is not None else meio_img,
                          r + 4).resize(alfa.size, Image.NEAREST)
    tapa = Image.new("RGBA", corte.size, (0, 0, 0, 0))
    tapa.paste(espalhado, (0, 0))
    m = Image.fromarray((fenda * 255).astype(np.uint8))
    tapa.putalpha(m)
    # o tapa entra ATRÃS: a arte original manda no que se vÃª
    novo = Image.new("RGBA", corte.size, (0, 0, 0, 0))
    novo.alpha_composite(tapa)
    novo.alpha_composite(corte)
    base.paste(novo, (x0, y0))
    return base


def _pivo_de_pega(img):
    """Onde a mÃ£o segura o objeto.

    Se a arte trouxer uma marca MAGENTA (o gerador Ã© instruÃ­do a pintar um
    ponto magenta no cabo), o pivÃ´ Ã© o centro dessa marca.

    SEM MARCA, Ã‰ O CENTRO (28/08). Era 72% da altura, na ideia de que o
    cabo fica embaixo -- e isso empurrava 72% do objeto para CIMA do ponto
    de pega. Somado ao ponto da palma, que caÃ­a alÃ©m da ponta da mÃ£o, o
    celular saÃ­a encostado na coxa em vez de dentro da mÃ£o: foi a queixa
    de 28/08 ("estÃ¡ muito deslocado para baixo").

    O centro Ã© o Ãºnico palpite que nÃ£o erra feio em objeto nenhum, e num
    cut-out o que se lÃª Ã© a sobreposiÃ§Ã£o do objeto com a mÃ£o -- nÃ£o a
    anatomia da pega. Modelar "segura pelo cabo" exige saber onde estÃ¡ o
    cabo, e a arte nÃ£o diz: quem quiser precisÃ£o pÃµe a marca magenta.
    """
    a = np.asarray(img.convert("RGBA"), dtype=np.int16)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    marca = (al > 128) & (r > 180) & (b > 180) & (g < 110)
    if marca.any():
        ys, xs = np.nonzero(marca)
        return (float(xs.mean()), float(ys.mean()))
    return (img.width * 0.5, img.height * 0.5)


def desenhar_personagem(pers, rig, boca_nivel=0.0, piscando=False, objeto=None,
                        expr=None, saida_pos=None):
    """Monta o personagem numa CAMADA transparente do tamanho do quadro.

    O corpo Ã© percorrido como ÃRVORE, do quadril para fora: a posiÃ§Ã£o de
    cada peÃ§a sai da posiÃ§Ã£o do pai mais o ponto de saÃ­da que o pai guarda
    para ela, girado pelo Ã¢ngulo do pai. NÃ£o hÃ¡ mais medida cravada, nÃ£o
    hÃ¡ mais `meio_ombro` nem `queda_ombro`, e acrescentar uma peÃ§a ao
    esqueleto nÃ£o mexe em uma linha deste arquivo.

    Camada separada (e nÃ£o direto no fundo) Ã© o que permite espelhar o
    personagem inteiro, achatÃ¡-lo na virada, dar zoom e pÃ´r DOIS
    personagens no mesmo quadro sem um apagar o outro."""
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    e = pers.escala

    # --- EXPRESSÃƒO FACIAL (ver expressao.py) --------------------------
    # Entra ANTES de propagar os Ã¢ngulos porque `cabeca_rot` Ã© giro de
    # cabeÃ§a de verdade: ele arrasta o crÃ¢nio, o cabelo, os olhos, o nariz
    # e a mandÃ­bula juntos, que Ã© o que faz inclinar a cabeÃ§a ler como
    # emoÃ§Ã£o e nÃ£o como peÃ§a solta torta.
    ex = dict(EXPR_ZERO)
    if expr:
        ex.update(expr)
        if abs(ex["cabeca_rot"]) > 0.01:
            rig = dict(rig)
            rig["cabeca"] = rig.get("cabeca", 0.0) + ex["cabeca_rot"]
    boca_nivel = max(float(boca_nivel), float(ex["boca_min"]))
    hc = pers.altura_cranio()          # rÃ©gua do rosto, em pixels da arte

    # --- posiÃ§Ã£o e Ã¢ngulo de cada peÃ§a, do quadril para fora
    pos, ang = {}, {}
    raiz = next((n for n, p in ESQUELETO.items() if p is None), "abdomen")
    # RAIZ EFETIVA (30/08). A raiz do esqueleto Ã© o abdÃ´men, e existe folha
    # que nÃ£o o separa: um colete de tricÃ´ que desce atÃ© o quadril faz peito
    # e abdÃ´men saÃ­rem numa peÃ§a sÃ³, que o segmentador nomeia PEITO. Com a
    # raiz ausente a travessia comeÃ§ava num nÃ³ que nÃ£o existe, ninguÃ©m era
    # visitado, e o personagem saÃ­a INVISÃVEL -- `getbbox()` devolvia None e
    # nenhuma linha de log dizia por quÃª.
    #
    # Ã‰ a mesma liÃ§Ã£o da Ã¡rvore efetiva, logo abaixo, aplicada ao comeÃ§o da
    # cadeia em vez do meio: peÃ§a que a arte nÃ£o separou nÃ£o pode quebrar o
    # rig. Quem assume o quadril Ã© o primeiro descendente que existe.
    if not pers.tem(raiz):
        descida = raiz
        while descida is not None and not pers.tem(descida):
            descida = next((n for n, p in ESQUELETO.items() if p == descida), None)
        if descida:
            print(f"[rig] sem '{raiz}': '{descida}' assume a raiz do esqueleto")
            raiz = descida
    fila = [raiz]
    corr = getattr(pers, "corr", {})
    pos[raiz] = tuple(rig["quadril"])
    ang[raiz] = _angulo(raiz, rig, boca_nivel) + corr.get(raiz, 0.0)
    # ÃRVORE EFETIVA: peÃ§a que a arte nÃ£o separou nÃ£o pode quebrar a cadeia.
    # A folha de 26/08 traz o pescoÃ§o grudado na cabeÃ§a, e com a Ã¡rvore
    # literal do ESQUELETO o crÃ¢nio ficava pendurado num `pescoco` que nÃ£o
    # existe -- ninguÃ©m o visitava e o personagem saÃ­a SEM CABEÃ‡A. O
    # segmentador jÃ¡ grava a saÃ­da no ancestral presente (ver
    # segmentar._ancestral_presente); aqui a travessia faz o mesmo salto.
    filhos = {}
    for n in ESQUELETO:
        pai = ESQUELETO[n]
        while pai is not None and not pers.tem(pai):
            pai = ESQUELETO.get(pai)
        # QUEM SOBE ATÃ‰ O FIM DA CADEIA FICA COM A RAIZ EFETIVA (30/08).
        # Sem isto, a perna de uma folha sem abdÃ´men subia para o abdÃ´men
        # (ausente), dele para `None` -- e virava Ã³rfÃ£: ninguÃ©m a visitava e
        # a senhora saÃ­a do peito para cima, cortada na cintura. Subir a
        # cadeia sÃ³ resolve quando existe alguÃ©m acima; na raiz nÃ£o existe,
        # e Ã© justamente ali que a folha de tronco Ãºnico quebra.
        if pai is None and n != raiz:
            pai = raiz
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
            # ENCAIXE DO OMBRO: a manga sobe, o pivÃ´ medido continua sendo o
            # pivÃ´. Sem isto o braÃ§o baixo deixa uma falha entre a camisa e a
            # manga -- ver folha_personagem.SUBIR_BRACO_HC. O deslocamento Ã©
            # feito no referencial do TRONCO (girado por `ang[pai]`), senÃ£o
            # o personagem inclinado subiria o braÃ§o na vertical da tela e a
            # manga sairia do ombro para o lado.
            if f in ENCAIXE_OMBRO and SUBIR_BRACO_HC:
                s = _girar((0.0, -SUBIR_BRACO_HC * hc * e), ang[pai])
                pos[f] = (pos[f][0] + s[0], pos[f][1] + s[1])
            ang[f] = _angulo(f, rig, boca_nivel) + corr.get(f, 0.0)
            fila.append(f)

    # --- as feiÃ§Ãµes se mexem DENTRO do rosto ---------------------------
    # Deslocamento no referencial da CABEÃ‡A: se a cabeÃ§a estÃ¡ inclinada, a
    # sobrancelha sobe na direÃ§Ã£o da testa, nÃ£o na vertical da tela. Sem
    # isto, cabeÃ§a de lado + sobrancelha erguida desmonta o rosto.
    ang_cabeca = ang.get("cranio", 0.0)
    var = {}                            # {peÃ§a: (escala_x, escala_y)}
    giro = {}                           # {peÃ§a: graus somados ao Ã¢ngulo}

    def _mover(nome, dx, dy):
        if nome in pos and (abs(dx) > 1e-4 or abs(dy) > 1e-4):
            d = _girar((dx * hc * e, dy * hc * e), ang_cabeca)
            pos[nome] = (pos[nome][0] + d[0], pos[nome][1] + d[1])

    if abs(ex["sobrancelha_dy"]) > 1e-4:
        _mover("sobrancelha_e", 0.0, ex["sobrancelha_dy"])
        _mover("sobrancelha_d", 0.0, ex["sobrancelha_dy"])
    if abs(ex["sobrancelha_rot"]) > 0.01:
        # sinais opostos: o que importa Ã© a ponta INTERNA das duas descer
        # (raiva) ou subir (tristeza). SimÃ©trico Ã© a Ãºnica leitura que nÃ£o
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

    # A boca abre por QUEDA do queixo, nÃ£o por rotaÃ§Ã£o: de frente, girar a
    # mandÃ­bula em torno de um ponto no meio do rosto torce o queixo para
    # um lado. Descer mantÃ©m a cara simÃ©trica e Ã© o que se lÃª como fala.
    repouso_mandibula = None
    if "mandibula" in pos and pers.tem("mandibula"):
        queda = boca_nivel * pers.img["mandibula"].size[1] * ABERTURA_MAXILAR * e * 0.5
        if queda > 1.0:
            repouso_mandibula = pos["mandibula"]
        pos["mandibula"] = (pos["mandibula"][0], pos["mandibula"][1] + queda)
        if "boca" in pos:
            pos["boca"] = (pos["boca"][0], pos["boca"][1] + queda)

    # onde cada peÃ§a ficou na TELA. SÃ³ as ferramentas de conferÃªncia
    # pedem (`ombro.py` precisa saber onde estÃ£o as juntas para nÃ£o
    # confundir vÃ£o de articulaÃ§Ã£o com o vÃ£o entre o braÃ§o e o corpo).
    if saida_pos is not None:
        saida_pos.update(pos)

    # --- desenho, de trÃ¡s para frente
    # O QUE ESTÃ NA MÃƒO Ã‰ DESENHADO POR ÃšLTIMO, e por isso ele Ã© guardado
    # aqui e colado depois do laÃ§o (ver o fim desta funÃ§Ã£o).
    objeto_colar = None
    for nome in ORDEM_Z:
        if nome not in pos or not pers.tem(nome):
            continue
        if piscando and nome in ("olho_e", "olho_d"):
            continue        # piscar = simplesmente nÃ£o desenhar o olho


        # INTERIOR DA BOCA. O maxilar desce e deixa um buraco entre ele e o
        # crÃ¢nio -- e por esse buraco aparecia o CENÃRIO, porque o entalhe
        # do crÃ¢nio Ã© vazado (Ã© o vÃ£o que permitiu segmentar a folha).
        # Enche-se o buraco com a silhueta do prÃ³prio maxilar, tingida de
        # escuro, na posiÃ§Ã£o de REPOUSO: assim o formato Ã© exatamente o
        # certo, sem inventar geometria de boca nenhuma, e o que sobra
        # visÃ­vel Ã© sÃ³ a faixa que o queixo desceu.
        if nome == "mandibula" and repouso_mandibula is not None:
            img, piv = pers.p(nome)
            dentro = Image.new("RGBA", img.size, COR_BOCA)
            dentro.putalpha(img.split()[3])
            colar(base, dentro, piv, repouso_mandibula, ang[nome], e)

        if nome == "cranio" and getattr(pers, "feicoes", None):
            # a cara vem montada dentro da prÃ³pria peÃ§a (ver
            # Personagem.cranio_com_cara): Ã© assim que olho e sobrancelha se
            # mexem numa folha que nÃ£o os entregou separados
            img, piv = pers.cranio_com_cara(ex, piscando)
        elif nome in var:
            img, piv = pers.variar(nome, *var[nome])
        else:
            img, piv = pers.p(nome)
        colar(base, img, piv, pos[nome], ang[nome] + giro.get(nome, 0.0), e)

        # BOCA DESENHADA: logo depois do crÃ¢nio, antes das feiÃ§Ãµes, que Ã©
        # onde a boca da arte estaria. SÃ³ existe quando a folha nÃ£o trouxe
        # queixo articulado (ver Personagem.__init__).
        if nome == "cranio" and getattr(pers, "boca", None):
            bdx, bdy, blarg = pers.boca
            estilo = getattr(pers, "boca_estilo", None) or {}
            # A CURVA DO DESENHISTA Ã‰ UM VIÃ‰S, NÃƒO A LINHA DE BASE (04/09,
            # ciclo 25).
            #
            # A conta era `emocao + estilo`, com a ideia de que *"a cara neutra
            # continua sendo a que ele desenhou"*. A ideia estÃ¡ certa e a conta
            # some com onze das doze expressÃµes, porque **as folhas sÃ£o
            # desenhadas SORRINDO**: o estilo medido Ã© +0,87 no Pal, +0,85 na
            # Maya, +0,89 na senhora, +1,00 no preso. Somando:
            #
            #     triste     -0,85 + 0,87 =  +0,02   uma linha reta
            #     bravo      -0,55 + 0,87 =  +0,32   um sorriso
            #     irritado   -0,40 + 0,87 =  +0,47   um sorriso maior
            #     confiante  +0,55 + 0,87 =   1,00   saturado
            #     desdem     +0,35 + 0,87 =   1,00   saturado, igual
            #     sorrindo   +0,95 + 0,87 =   1,00   saturado, igual
            #
            # **A boca deste canal nunca curvou para baixo, e quatro
            # expressÃµes saÃ­am idÃªnticas por saturaÃ§Ã£o.** A folha de
            # `ferramentas/caras.py` mostra as doze e sÃ³ trÃªs se distinguem --
            # surpreso, chocado e desesperado --, e elas se distinguem porque a
            # boca ABRE, nÃ£o porque ela curva. Num canal em que a piada Ã© o
            # sujeito que se ferra, a cara de quem se ferrou nÃ£o existia.
            #
            # O catÃ¡logo de `expressao.py` foi calibrado com a base em ZERO
            # (`triste` pede -0,85, que Ã© uma boca claramente para baixo), entÃ£o
            # a curva da emoÃ§Ã£o Ã© o ALVO e a do desenhista entra como o tempero
            # que sobra: um quarto dela. `neutro` continua sorrindo de leve, que
            # Ã© o que a arte diz do personagem, e `triste` vira -0,63, que Ã© uma
            # boca triste.
            #
            # Um quarto e nÃ£o zero porque a razÃ£o original Ã© boa: a boca de
            # repouso Ã© traÃ§o do desenhista, e apagÃ¡-la faria todo personagem
            # do elenco ter a mesma boca neutra.
            # A ABERTURA MÃXIMA DA BOCA (03/09, queixa 2 do dono do projeto:
            # *"a cara foi completamente deformada pelo efeito da boca"*).
            #
            # Era 0,55 da largura: numa boca de 81 px (o Zeca) isso dÃ¡ 45 px
            # de abertura, e o que aparece na folha de rostos Ã© um buraco
            # escuro ocupando o terÃ§o de baixo da cara. Uma pessoa FALANDO
            # abre a boca a algo como um terÃ§o da largura dela; 0,55 Ã© grito,
            # e o motor a punha aÃ­ em toda sÃ­laba forte.
            #
            # 0,30 Ã© o teto de uma fala normal. O `boca_min` das expressÃµes
            # continua podendo levantar o piso -- Ã© ele que faz o queixo cair
            # no susto --, entÃ£o a cara de espanto nÃ£o se perde: o que se
            # perde Ã© o grito permanente.
            bimg, bpiv = _boca_desenhada(
                blarg * e, blarg * e * BOCA_ABERTURA_MAX, boca_nivel,
                max(-1.0, min(1.0, ex["boca_curva"]
                                   + PESO_BOCA_DA_ARTE
                                   * float(estilo.get("curva", 0.0)))),
                _cor_da_casca(pers.img["cranio"]),
                espessura=float(estilo.get("esp", 0.0)) * e or None)
            d = _girar((bdx * e, bdy * e), ang[nome])
            colar(base, bimg, bpiv,
                  (pos[nome][0] + d[0], pos[nome][1] + d[1]), ang[nome])

        # objeto: a POSIÃ‡ÃƒO sai da mÃ£o que o segura -- Ã© o osso da mÃ£o que
        # tornou isto possÃ­vel --, mas o desenho vai por Ãºltimo (ver
        # `_colar_objeto` no fim desta funÃ§Ã£o).
        if objeto and objeto.get("img") is not None and nome == "mao_" + objeto.get("mao", "e"):
            oi = objeto["img"]
            opv = objeto.get("pivo") or _pivo_de_pega(oi)
            oi, opv = _centralizar(oi, opv)
            # A MÃƒO SEGURA COM A PALMA, NÃƒO COM O PUNHO. `pos[nome]` Ã© o
            # pivÃ´ da mÃ£o, que fica na junta com o antebraÃ§o -- colar o
            # objeto ali o joga para dentro do corpo, e num objeto grande
            # ele aparece flutuando na frente da barriga.
            #
            # 0,30 do comprimento da mÃ£o, nÃ£o 0,55 (28/08). Com 0,55 o
            # ponto caÃ­a ALÃ‰M da ponta dos dedos: em repouso, com o braÃ§o
            # baixo, isso pÃµe o objeto abaixo da mÃ£o, encostado na coxa. O
            # meio da peÃ§a Ã© onde a palma estÃ¡ de verdade, e Ã© ali que o
            # objeto tem que se sobrepor Ã  mÃ£o para ler como segurado.
            # A FRAÃ‡ÃƒO Ã‰ MEDIDA NA ARTE (02/09) -- ver
            # `Personagem.fracao_da_palma`. Era 0,30 cravado, e o centro de
            # massa da mÃ£o estÃ¡ a 0,42-0,47 em todas as folhas: o objeto
            # ficava a um terÃ§o do caminho entre o punho e os dedos, que Ã©
            # o "segurando pelo pulso" que o dono do projeto viu.
            comp = pers.comp.get(nome, 0.0) * pers.escala
            rad = math.radians(ang[nome])
            fp = pers.fracao_da_palma(nome)
            palma = (pos[nome][0] + math.cos(rad) * comp * fp,
                     pos[nome][1] + math.sin(rad) * comp * fp)
            # GUARDADO PARA COLAR NO FIM, e nÃ£o aqui.
            #
            # POR QUE (01/09, volta 36 do ciclo). `ORDEM_Z` desenha o braÃ§o
            # DIREITO antes do esquerdo, e o objeto ia junto do direito --
            # entÃ£o o braÃ§o esquerdo passava por cima dele. No Pal isso
            # nunca apareceu: os braÃ§os dele terminam afastados. Na Maya,
            # `usar_objeto` junta as duas mÃ£os Ã  frente do peito e o
            # esquerdo TAPA o objeto -- medido em `ferramentas/objeto.py`
            # com a folha dela: celular 21% de visÃ­vel, xÃ­cara 24%, chave
            # 15%, contra 96% no Pal. Seis dos dez objetos reprovam.
            #
            # A correÃ§Ã£o nÃ£o Ã© reajustar a pose (ela foi calibrada por
            # varredura, e uma varredura por personagem Ã© a mesma armadilha
            # de novo -- medir num e aplicar em todos). O que Ã© geral: o que
            # se SEGURA fica na frente. NinguÃ©m segura uma xÃ­cara atrÃ¡s do
            # prÃ³prio braÃ§o.
            objeto_colar = (oi, opv, palma, ang[nome],
                            float(objeto.get("escala", 1.0)))
            if saida_pos is not None:
                # ONDE O OBJETO FICOU, para a cÃ¢mera nÃ£o cortÃ¡-lo (31/08).
                # A guarda de enquadramento passou a mirar o NÃšCLEO do corpo
                # -- o braÃ§o deixou de contar, senÃ£o a janela balanÃ§a junto
                # com o gesto --, e sem esta caixa o que estÃ¡ NA MÃƒO ERGUIDA
                # sairia do quadro junto com ela: era o defeito do v013, o
                # celular boiando fora da tela. Um raio em volta da palma
                # basta; o objeto Ã© colado centrado nela.
                r = max(oi.size) * float(objeto.get("escala", 1.0)) / 2.0
                saida_pos["_objeto"] = (palma[0] - r, palma[1] - r,
                                        palma[0] + r, palma[1] + r)

    # O OBJETO, POR ÃšLTIMO -- E ELE NÃƒO ESTAVA SENDO DESENHADO (02/09).
    #
    # Achado medindo o item 4 do dono do projeto (*"personagem segurando
    # celular pelo pulso"*): `ferramentas/objeto.py` devolvia **0% de
    # visÃ­vel para os dez objetos, nas quatro situaÃ§Ãµes, em todos os
    # personagens**, e a diferenÃ§a entre o corpo desenhado com objeto e sem
    # objeto era de ZERO pixels.
    #
    # A causa Ã© uma linha que faltou. Em 01/09 o desenho do objeto foi
    # movido do meio do laÃ§o para o fim da funÃ§Ã£o -- correÃ§Ã£o certa, porque
    # `ORDEM_Z` desenha o braÃ§o direito antes do esquerdo e o esquerdo
    # passava por cima do que a mÃ£o direita segurava. O valor passou a ser
    # guardado em `objeto_colar`... e a colagem no fim nunca foi escrita. O
    # comentÃ¡rio do prÃ³prio cÃ³digo dizia "ver `_colar_objeto` no fim desta
    # funÃ§Ã£o", e nÃ£o havia nada lÃ¡.
    #
    # Python nÃ£o reclama de uma atribuiÃ§Ã£o que ninguÃ©m lÃª, entÃ£o isto
    # passou em silÃªncio: o objeto sumiu de todos os vÃ­deos e o Ãºnico lugar
    # que sabia era uma rÃ©gua que ninguÃ©m rodou. Ã‰ a lei 65 outra vez -- o
    # ramo que falha precisa de um lugar que conte que ele falhou --, e
    # desta vez o lugar existia.
    # AS FENDAS ENTRE AS PEÃ‡AS, TAPADAS NO CORPO MONTADO (03/09). Vem DEPOIS
    # de todas as peÃ§as e ANTES do objeto: o objeto nÃ£o Ã© parte do corpo, e
    # deixÃ¡-lo entrar na conta faria o fechamento tentar emendÃ¡-lo Ã  mÃ£o.
    _fechar_vaos_do_corpo(base)

    if objeto_colar is not None:
        oi, opv, palma, ang_mao, esc = objeto_colar
        # `_colar_objeto` e nÃ£o `colar`: alÃ©m de colar, ele desenha a
        # separaÃ§Ã£o do objeto contra o que ficou ATRÃS dele -- ver lÃ¡ o
        # porquÃª (o celular lendo como adesivo na coxa, voltas 088 e 091).
        _colar_objeto(base, oi, opv, palma, ang_mao, esc)

    return base


# compatibilidade: quem chamava desenhar() e recebia RGB continua funcionando
def desenhar(pers, rig, fundo, boca_nivel=0.0, piscando=False):
    camada = desenhar_personagem(pers, rig, boca_nivel, piscando)
    quadro = fundo.copy().convert("RGBA")
    quadro.alpha_composite(camada)
    return quadro.convert("RGB")


# =====================================================================
# CÃ‚MERA â€” fundo que anda, personagem que vira, zoom
# =====================================================================
# QUANTO O CENÃRIO Ã‰ AVIVADO (04/09, item 5 do dono do projeto: *"no cenÃ¡rio
# colocar cores mais vibrantes, buscando chamar mais atenÃ§Ã£o"*).
#
# O gerador de imagem devolve arte correta e APAGADA -- pastel, contraste
# baixo, tudo na mesma faixa de cinza. Num feed isso Ã© o pior lugar para
# estar: o vÃ­deo compete com miniaturas saturadas, e a primeira coisa que o
# olho descarta Ã© o que tem pouca diferenÃ§a de cor.
#
# Ã‰ um pÃ³s-processo e nÃ£o um pedido ao gerador, de propÃ³sito: pedir "cores
# vibrantes" na descriÃ§Ã£o Ã© loteria (cinco tentativas do `comercio` provaram),
# e saturaÃ§Ã£o Ã© uma operaÃ§Ã£o exata que se aplica sempre igual.
#
# 1,35 de saturaÃ§Ã£o e 1,10 de contraste: o suficiente para a arte ganhar
# corpo sem estourar em nÃ©on. Acima de ~1,5 a pele dos personagens (que NÃƒO
# passa por aqui) comeÃ§a a destoar do fundo, e Ã© aÃ­ que se percebe a
# manipulaÃ§Ã£o. O personagem fica de fora porque a arte dele jÃ¡ foi aprovada
# no olho, e mexer nela mudaria os oito de uma vez.
# O PUNCH-IN: quanto o quadro entra mais fechado no corte, e em quanto tempo
# ele assenta. 7% Ã© perceptÃ­vel e nÃ£o desmonta o enquadramento; 0,25 s Ã© a
# ordem de um corte de montagem -- mais que isso vira zoom, e zoom Ã© o
# contrÃ¡rio de interrupÃ§Ã£o. Ver o uso, no laÃ§o dos trechos.
PUNCH_FORCA = float(os.environ.get("PUNCH_FORCA", "0.07"))
PUNCH_S = 0.25

# O COLD OPEN: quanto o primeiro trecho entra mais fechado, e em quanto tempo
# ele recua. Ver o uso, no laÃ§o dos trechos.
COLD_OPEN_FORCA = float(os.environ.get("COLD_OPEN_FORCA", "0.18"))
COLD_OPEN_S = 0.8

SATURACAO_CENARIO = float(os.environ.get("SATURACAO_CENARIO", "1.35"))
CONTRASTE_CENARIO = float(os.environ.get("CONTRASTE_CENARIO", "1.10"))


def _avivar(img):
    """Sobe saturaÃ§Ã£o e contraste do CENÃRIO. Ver as constantes acima."""
    if SATURACAO_CENARIO == 1.0 and CONTRASTE_CENARIO == 1.0:
        return img
    from PIL import ImageEnhance
    fora = ImageEnhance.Color(img).enhance(SATURACAO_CENARIO)
    if CONTRASTE_CENARIO != 1.0:
        fora = ImageEnhance.Contrast(fora).enhance(CONTRASTE_CENARIO)
    return fora


class Cenario:
    """Um cenÃ¡rio COMPRIDO por onde a cÃ¢mera passeia.

    O QUE MUDOU EM 28/08, E POR QUÃŠ
        AtÃ© aqui a arte era quadrada e o fundo corria em ladrilho
        ESPELHADO: a imagem mais uma cÃ³pia invertida ao lado, deslocamento
        mÃ³dulo 2W, fundo infinito com duas cÃ³pias. O espelho nÃ£o tem
        emenda de PIXEL -- as bordas casam exatamente --, mas tem emenda
        de LEITURA: a mesma janela aparece duas vezes, a porta que estava
        Ã  esquerda reaparece Ã  direita, e o texto na placa sai ao
        contrÃ¡rio. Enquanto a cÃ¢mera ficava parada quase o vÃ­deo inteiro
        ninguÃ©m via; com ela passeando o tempo todo, Ã© a primeira coisa
        que aparece -- foi a queixa de 28/08 ("tentou esticar a imagem
        fazendo uma imagem infinita, os erros ficam evidentes").

        Agora nÃ£o se inventa cenÃ¡rio nenhum: a arte Ã© PANORÃ‚MICA, escalada
        para cobrir a altura do quadro, e sobra material dos dois lados.
        A cÃ¢mera anda dentro desse material, e cada pixel aparece uma vez
        sÃ³. Quem gera a arte Ã© o workflow `gerar-assets`, que passou a
        pedir cenÃ¡rio deitado (ver `Montar Pedidos`).

    O QUE ACONTECE SE A ARTE FOR ESTREITA
        Nada quebra. Um cenÃ¡rio quadrado de 1024, coberto para 1920 de
        altura, vira uma tira de 1920x1920: ainda sobram 840px de passeio
        real -- menos do que um panorÃ¢mico dÃ¡, e sem uma emenda sequer.

    NA BORDA, REFLETE
        Deslocamento que passa do fim da arte volta pelo mesmo caminho, em
        vez de dar a volta. Voltar repete um trajeto que a pessoa jÃ¡ viu;
        dar a volta Ã© um salto no meio do movimento, que Ã© justamente o
        que se estÃ¡ tirando daqui.

    A LINHA DO CHÃƒO vem anotada (`cenarios.CATALOGO[...]["chao"]`), nÃ£o
    medida: ver o comentÃ¡rio longo em cenarios.py. Ã‰ ela que diz onde os
    pÃ©s do personagem pousam.
    """

    def __init__(self, img, chao_rel=None, foco=1.0):
        self.chao_y = H * float(chao_rel if chao_rel is not None
                                else CENARIOS.CHAO_PADRAO)
        # QUANTO ESTA ARTE PRECISA SAIR DE FOCO, em mÃºltiplos do padrÃ£o. Ã‰ uma
        # anotaÃ§Ã£o por asset, como a linha do chÃ£o, e pelo mesmo motivo: Ã© uma
        # propriedade do desenho que dura para sempre e que nenhum detector
        # automÃ¡tico acertou. O `sala` pede 2,2 porque o terÃ§o de baixo dele Ã©
        # um tapete em traÃ§o branco sem cor -- ver `cenarios.CATALOGO`.
        self.foco = max(0.5, min(4.0, float(foco or 1.0)))
        base = img.convert("RGB")
        # COBRIR: a arte precisa preencher a altura do quadro e ter pelo
        # menos a largura dele. Esticar deformaria (prÃ©dio vira torre); o
        # excesso Ã© o que vira faixa de passeio.
        k = max(W / base.width, H / base.height)
        nl, na = max(int(base.width * k), W), max(int(base.height * k), H)
        base = _reamostrar(base, (nl, na))
        # o chÃ£o fica embaixo: cortar pelo centro jogaria a linha do chÃ£o
        # para fora do quadro
        self.tira = base.crop((0, na - H, nl, na))
        self.tira = _avivar(self.tira)
        self.faixa = max(0, self.tira.width - W)      # o quanto dÃ¡ para andar
        self._borrada = None            # a versÃ£o fora de foco, sob demanda
        self._leve = None               # e a de foco brando do plano aberto
        self._corte = None              # os pontos de corte, jÃ¡ puxados

    def ponto_do_trecho(self, i):
        """Onde a cÃ¢mera fica DURANTE o trecho `i`, em pixels da tira.

        Ã‰ a base do enquadramento; a caminhada soma por cima dela, e Ã© a
        Ãºnica coisa que move o fundo dentro de uma fala."""
        if self.faixa <= 0:
            return 0.0
        return self._pontos()[i % len(PONTOS_DE_CORTE)]

    def _pontos(self):
        """Os pontos de corte, PUXADOS PARA ONDE A ARTE TEM COR (04/09).

        POR QUE (ciclo 25, folhas do v026 e do v031)
            `PONTOS_DE_CORTE` sÃ£o dezesseis fraÃ§Ãµes fixas da faixa, escolhidas
            para saltar de um lado ao outro da arte (lei 26). Elas nÃ£o sabem
            NADA sobre a arte -- e a arte deste canal nÃ£o Ã© uniforme: o
            `escritorio` tem uma parede de janela que Ã© cidade em traÃ§o claro,
            o `sala` tem o tapete rabiscado.

            Medido, janela de 1080 px por janela, a saturaÃ§Ã£o mÃ©dia de cada
            corte contra a melhor janela da mesma tira:

                cozinha      melhor 149    nos oito pontos  127 a 147
                escritorio   melhor  78    nos oito pontos   52 a  68
                sala         melhor  80    nos oito pontos   62 a  77

            No `escritorio` -- e ele Ã© o segundo cenÃ¡rio mais usado -- **os
            pontos fixos caem sistematicamente na metade lavada**: o pior deles
            entrega 67% da cor que a melhor janela da mesma arte entrega. NÃ£o
            Ã© defeito da arte inteira; Ã© a cÃ¢mera cortando no lugar errado
            dela.

        O QUE MUDA
            Cada ponto procura, numa vizinhanÃ§a de Â±10% da faixa em volta de
            onde ele jÃ¡ estava, a janela com mais cor. VizinhanÃ§a e nÃ£o a faixa
            inteira: o que faz os cortes lerem como corte Ã© eles saltarem de um
            lado ao outro (lei 26), e uma busca global juntaria todos no mesmo
            pedaÃ§o bom -- o fundo repetido, que Ã© o defeito que a lista de
            dezesseis pontos existe para evitar.

            Dois pontos que caiam a menos de 6% um do outro depois da busca:
            o segundo volta para onde estava, pela mesma razÃ£o.

        Custa uma soma cumulativa por cenÃ¡rio, no primeiro trecho que o usa.
        """
        if self._corte is not None:
            return self._corte
        a = np.asarray(self.tira.convert("RGB")).astype(np.int16)
        mx, mn = a.max(axis=2), a.min(axis=2)
        sat = np.where(mx > 0, (mx - mn) * 255.0 / np.maximum(mx, 1), 0.0)
        cum = np.concatenate([[0.0], np.cumsum(sat.mean(axis=0))])
        viz = max(1, int(self.faixa * 0.10))
        escolhidos, mudou = [], 0
        for p in PONTOS_DE_CORTE:
            x0 = int(self.faixa * p)
            cands = range(max(0, x0 - viz), min(self.faixa, x0 + viz) + 1, 24)
            melhor = max(cands, key=lambda x: cum[x + W] - cum[x], default=x0)
            if any(abs(melhor - e) < self.faixa * 0.06 for e in escolhidos):
                melhor = x0
            mudou += 1 if abs(melhor - x0) > 24 else 0
            escolhidos.append(melhor)
        ganho = (sum(cum[x + W] - cum[x] for x in escolhidos)
                 / max(sum(cum[int(self.faixa * p) + W] - cum[int(self.faixa * p)]
                           for p in PONTOS_DE_CORTE), 1e-6))
        print(f"[cenario] cortes puxados para onde ha cor: {mudou} de "
              f"{len(PONTOS_DE_CORTE)} mudaram, {100 * (ganho - 1):+.0f}% de "
              f"cor no quadro")
        self._corte = escolhidos
        return escolhidos

    def _posicao(self, dx):
        """Deslocamento pedido -> coluna da arte, refletindo nas bordas."""
        if self.faixa <= 0:
            return 0
        m = float(dx) % (2 * self.faixa)
        return int(m if m <= self.faixa else 2 * self.faixa - m)

    def quadro(self, dx, borrado=False):
        x = self._posicao(dx)
        return self._tira(borrado).crop((x, 0, x + W, H))

    def _tira(self, borrado):
        """A tira no grau de foco pedido. Custa UM borrÃ£o por grau, por cenÃ¡rio.

        SÃƒO DOIS GRAUS, E NÃƒO UM (04/09, ciclo 25)
            O foco era binÃ¡rio: nÃ­tido abaixo de 1,35 de zoom, 9 px de borrÃ£o
            acima. Os planos deste formato sÃ£o 1,20, 1,45 e 1,90, entÃ£o o
            **plano aberto â€” o mais usado â€” sai com o cenÃ¡rio em foco total**.

            Ã‰ justamente onde a arte pesa mais: quanto mais aberto o plano,
            mais cenÃ¡rio no quadro. A folha de rostos do v026 mostra a VovÃ³ a
            um sexto da altura, com dois terÃ§os de tela ocupados por um
            `escritorio` que Ã© **cidade e mÃ³veis em puro contorno preto sobre
            branco** â€” a mesma espessura de traÃ§o do personagem, e nenhuma cor
            para separar os dois. Ã‰ a razÃ£o que a lei 72 jÃ¡ dÃ¡ para o close, e
            ela nÃ£o deixa de valer a 1,20: o que a decide Ã© o peso do traÃ§o no
            quadro, nÃ£o o nÃºmero do zoom.

            `sala` e `escritorio` sÃ£o 68% do corpus e os dois tÃªm regiÃ£o grande
            em contorno branco (`ferramentas/regiao_sem_cor.py`, aberto desde
            02/09). Redesenhar a arte Ã© o item 4 de `GUIA 0.3` e nÃ£o estÃ¡ na
            mÃ£o de ninguÃ©m hoje; tirar o fundo de foco Ã© profundidade de campo,
            que Ã© a resposta de sempre e nÃ£o inventa arte nenhuma.

            TrÃªs pixels, e nÃ£o nove: no plano aberto o cenÃ¡rio ainda tem de
            dizer ONDE a cena acontece. Nove tira o lugar junto com o traÃ§o.
        """
        if not borrado:
            if self._leve is None:
                self._leve = self.tira.filter(
                    ImageFilter.GaussianBlur(3.0 * self.foco))
            return self._leve
        return self._tira_borrada()

    def _tira_borrada(self):
        """A mesma tira, fora de foco. Custa UM borrÃ£o por cenÃ¡rio.

        POR QUE (31/08, volta 11 do ciclo de vÃ­deo)
            O v011 Ã© um monÃ³logo no `comercio`, e o cenÃ¡rio Ã© uma parede de
            prateleiras desenhadas em traÃ§o, de cima a baixo, sem cor e sem
            Ã¡rea calma. No plano aberto ela passa; no CLOSE a 1,60 ela Ã©
            ampliada junto e vira um emaranhado de linhas pretas atrÃ¡s da
            cara -- a cara e o fundo tÃªm o mesmo contraste, a mesma
            espessura de traÃ§o, e o olho nÃ£o sabe onde pousar. Num canal em
            que a piada acontece no rosto, isso Ã© o rosto perdendo.

            NÃ£o Ã© defeito de UM cenÃ¡rio: Ã© o que acontece com qualquer arte
            de fundo quando a cÃ¢mera fecha. A resposta Ã© a de sempre em
            animaÃ§Ã£o e em foto -- **profundidade de campo**: quem estÃ¡ longe
            sai de foco, e a separaÃ§Ã£o entre figura e fundo passa a ser
            fÃ­sica, nÃ£o sorte de composiÃ§Ã£o.

        POR QUE ISTO Ã‰ BARATO
            O fundo Ã© IMÃ“VEL dentro do trecho (lei 26), e mesmo com a
            caminhada o que muda Ã© a coluna recortada, nÃ£o a arte. EntÃ£o o
            borrÃ£o se faz UMA vez por cenÃ¡rio, na tira inteira, e todo
            recorte sai dela. SÃ£o ~2 borrÃµes por vÃ­deo, nÃ£o 430.
        """
        if self._borrada is None:
            # 9px numa tira de ~2300 de largura: o bastante para o traÃ§o
            # perder a aresta e nÃ£o tanto que o lugar deixe de ser
            # reconhecÃ­vel -- o cenÃ¡rio ainda tem de dizer onde a cena Ã©.
            self._borrada = self.tira.filter(
                ImageFilter.GaussianBlur(9.0 * self.foco))
        return self._borrada


def _sombra_de_contato(quadro, camada, chao_y):
    """Elipse escura no chÃ£o, sob o personagem.

    Sem ela o personagem Ã© um recorte POUSADO no cenÃ¡rio, nÃ£o alguÃ©m DENTRO
    dele -- foi a primeira coisa que saltou quando o fundo deixou de ser
    cor chapada e virou uma rua. Uma sombra de contato Ã© o sinal mais
    barato de que os pÃ©s tocam o chÃ£o.

    O ponto de apoio Ã© a LINHA DO CHÃƒO da cena, nÃ£o a base da figura: presa
    aos pÃ©s, a sombra subiria junto no pulo -- e sombra que voa denuncia
    mais do que sombra nenhuma. Ela encolhe e clareia conforme a figura se
    afasta do chÃ£o, que Ã© o que dÃ¡ a leitura de altura."""
    bb = camada.getbbox()
    if not bb:
        return
    x0, _, x1, y1 = bb
    voo = max(0.0, chao_y - y1)
    if voo > H * 0.30:
        return                          # alto demais: jÃ¡ nÃ£o hÃ¡ contato a sugerir
    k = 1.0 - min(1.0, voo / (H * 0.30))
    larg = (x1 - x0) * (0.42 + 0.22 * k)
    alt = max(6.0, larg * 0.15)
    cx = (x0 + x1) / 2.0
    # SÃ“ A CAIXA DA ELIPSE, nÃ£o a tela inteira. O borrÃ£o gaussiano custa
    # pelo nÃºmero de pixels, e uma sombra ocupa ~2% de um quadro 1080x1920:
    # borrar o quadro todo era 98% de trabalho em cima de transparÃªncia.
    # Passou a doer quando a sombra virou uma POR ator (29/08) e o custo
    # dobrou -- 1,2s por frame viraram 2s.
    raio = max(2, int(alt * 0.35))
    m = raio * 3 + 4                                   # margem para o borrÃ£o
    cx0, cy0 = int(cx - larg / 2 - m), int(chao_y - alt / 2 - m)
    cw, ch = int(larg + 2 * m), int(alt + 2 * m)
    if cw <= 0 or ch <= 0:
        return
    tinta = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ImageDraw.Draw(tinta).ellipse([m, m, m + larg, m + alt],
                                  fill=(30, 26, 22, int(96 * (0.45 + 0.55 * k))))
    tinta = tinta.filter(ImageFilter.GaussianBlur(raio))
    # o pedaÃ§o que cai dentro do quadro (a sombra de quem estÃ¡ saindo de
    # cena fica meio para fora)
    rx0, ry0 = max(-cx0, 0), max(-cy0, 0)
    rx1, ry1 = min(cw, W - cx0), min(ch, H - cy0)
    if rx1 <= rx0 or ry1 <= ry0:
        return
    quadro.alpha_composite(tinta.crop((rx0, ry0, rx1, ry1)),
                           (cx0 + rx0, cy0 + ry0))


def deformar_ator(camada, cam, quadril_x=W / 2):
    """Espelhar, achatar e o squash da passada -- as trÃªs deformaÃ§Ãµes que
    sÃ£o do CORPO de um ator, nÃ£o do quadro.

    POR QUE ELAS SAÃRAM DE `montar_frame` (29/08)
        LÃ¡ elas se aplicavam Ã  camada JUNTA, e o `cam` que chegava era o do
        falante. Com dois em cena isso Ã© o movimento de um deformando o
        outro: `virar` (espelhar + achatar atÃ© 0,04) achatava a cena
        inteira contra o quadril de quem virou, e o `escala_y` da caminhada
        de um comprimia quem estava parado do lado. NinguÃ©m tinha visto
        porque `virar` nunca havia entrado num spec de dois.
    """
    if cam.get("espelhar"):
        # espelhar em torno do PRÃ“PRIO personagem, nÃ£o do centro da tela:
        # espelhar a tela inteira teleportaria o corpo para o outro lado
        esp = camada.transpose(Image.FLIP_LEFT_RIGHT)
        nova = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        nova.alpha_composite(esp, (int(2 * quadril_x - W), 0))
        camada = nova

    achatar = float(cam.get("achatar", 1.0))
    if achatar < 0.995:
        larg = max(2, int(W * max(achatar, 0.04)))
        red = _reamostrar(camada, (larg, H))
        nova = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        nova.alpha_composite(red, (int(quadril_x - larg * quadril_x / W), 0))
        camada = nova

    # SQUASH & STRETCH: escala vertical em torno do CHÃƒO. Em torno do
    # centro, o personagem afundaria no piso ao achatar; ancorado no pÃ©,
    # ele achata como um corpo com peso.
    esc_y = float(cam.get("escala_y", 1.0))
    if abs(esc_y - 1.0) > 0.004:
        bb = camada.getbbox()
        if bb:
            chao = bb[3]
            alt = max(int(H * esc_y), 2)
            red = _reamostrar(camada, (W, alt))
            nova = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            nova.alpha_composite(red, (0, int(chao - chao * esc_y)))
            camada = nova
    return camada


_ULTIMO_APERTO = {}


def montar_frame(camada, cenario, cam, quadril_x=W / 2, camadas=None,
                 centro_x=None, camada_alvo=None, terco=0, caixa_extra=None):
    """Junta personagem + cenÃ¡rio aplicando o que a cÃ¢mera pediu.

    `camadas` sÃ£o os atores SEPARADOS, e existem por dois motivos. A
    SOMBRA: com dois em cena, a caixa da camada junta vai do braÃ§o de um ao
    braÃ§o do outro, e a elipse virava uma mancha sÃ³ ligando os dois pÃ©s --
    lÃª como um tapete escuro, nÃ£o como contato. Uma sombra por corpo. E as
    DEFORMAÃ‡Ã•ES: quando elas vÃªm, cada ator jÃ¡ chega deformado pelo que ele
    mesmo fez (`deformar_ator`), e aqui nÃ£o se mexe mais nelas."""
    if camadas is None:
        camada = deformar_ator(camada, cam, quadril_x)

    z = float(cam.get("zoom", 1.0))
    # O ZOOM NÃƒO FECHA MAIS DO QUE O CORPO PERMITE (29/08).
    #
    # O teto de plano Ã© 1,30 com um ator em cena, e ele foi escolhido
    # quando o personagem ficava a 78% do quadro e media ~850 px. Com os
    # pÃ©s no chÃ£o desenhado ele mede 1151 px, e uma aÃ§Ã£o que estende o
    # braÃ§o (`tropecar`, `susto`, `comemorar`) pÃµe a silhueta em ~700 px de
    # largura: a janela de 831 px que o zoom 1,30 recorta nÃ£o cabe, e o
    # braÃ§o sai cortado pela borda -- foi o que a rodada 4 do ciclo
    # mostrou.
    #
    # Aqui o teto vem do CORPO, nÃ£o da tabela: mede-se a silhueta que
    # existe neste frame e limita-se o zoom ao que a comporta, com uma
    # margem de respiro. SÃ³ limita, nunca aumenta -- o plano continua
    # sendo o que `_enquadramento` pediu quando ele cabe.
    #
    # DE QUAL CORPO (31/08, volta 6 do ciclo de vÃ­deo). `camada` Ã© a soma
    # dos atores, e com dois em cena ela vai do braÃ§o de um ao braÃ§o do
    # outro: 740 dos 1080 px, o que trava qualquer zoom acima de 1,33. Era
    # essa medida -- e nÃ£o o teto da tabela -- que fazia os dezesseis
    # quadros do v006 saÃ­rem no MESMO plano aberto. Num CLOSE em quem fala,
    # o outro sair pela borda Ã© o efeito pretendido (Ã© o "corte para o
    # personagem" do plano de melhorias), entÃ£o quem limita Ã© a silhueta
    # de QUEM ESTÃ SENDO ENQUADRADO. Sem `camada_alvo`, nada muda.
    enquadrada = camada_alvo if camada_alvo is not None else camada
    # A CAIXA QUE A CÃ‚MERA OBEDECE: o nÃºcleo de quem estÃ¡ sendo enquadrado,
    # mais o que ele estiver segurando. Medida UMA vez por frame e usada
    # pelas trÃªs guardas -- zoom, lateral e alto --, que antes cada uma
    # media a sua (ver `caixa_do_nucleo`). SÃ³ quando hÃ¡ recorte: sem zoom
    # nenhuma guarda tem o que fazer, e a conta custa uma varredura do alfa
    # da tela inteira.
    # DUAS CAIXAS, E NÃƒO UMA (02/09, item 2 do dono do projeto: *"o
    # enquadramento se perde Ã s vezes quando o personagem vai mexer a
    # mÃ£o"*).
    #
    # Desde 31/08 as trÃªs guardas miram o NÃšCLEO -- tronco, cabeÃ§a e pernas
    # --, justamente para a janela nÃ£o subir e descer com o aceno (lei 71).
    # SÃ³ que a caixa do OBJETO era unida a ele antes de qualquer guarda, e
    # o objeto estÃ¡ na MÃƒO: quando a mÃ£o sobe 200px, a caixa sobe junto e
    # as trÃªs guardas vÃ£o atrÃ¡s. A correÃ§Ã£o do v013 continua certa no que
    # ela queria -- objeto meio fora do quadro lÃª como adesivo --, mas ela
    # devolveu o defeito que o nÃºcleo tinha acabado de resolver.
    #
    # A distinÃ§Ã£o Ã© de linguagem, nÃ£o de cÃ³digo: o que nÃ£o se corta NO ALTO
    # Ã© a cabeÃ§a, e o alto Ã© do CORPO; o que nÃ£o se corta PELO LADO inclui
    # o que a mÃ£o segura, porque um objeto cortado ao meio pela borda Ã© o
    # que lÃª como adesivo. E o ZOOM Ã© do corpo: deixar o objeto abrir o
    # plano Ã© a cÃ¢mera recuando toda vez que alguÃ©m levanta o braÃ§o.
    nucleo = caixa_do_nucleo(enquadrada) if abs(z - 1.0) > 0.002 else None
    # A GUARDA LATERAL VOLTA A MIRAR SÃ“ O NÃšCLEO (03/09, item 5 do dono do
    # projeto: *"em momentos que o foco acompanha o movimento da mÃ£o"*).
    #
    # Em 02/09 a caixa do OBJETO foi unida ao nÃºcleo para a guarda lateral,
    # com um argumento correto: objeto cortado ao meio pela borda lÃª como
    # adesivo. SÃ³ que o objeto estÃ¡ NA MÃƒO â€” quando a mÃ£o sobe ou se estende,
    # a caixa vai junto e a janela anda atrÃ¡s dela. O texto de 02/09 jÃ¡
    # separava alto (sÃ³ o corpo) de lateral (corpo + objeto) para nÃ£o repetir
    # o defeito do aceno; o que faltou ver Ã© que **o lado tem o mesmo
    # problema que o alto**: a mÃ£o se mexe nos dois eixos.
    #
    # Fica o nÃºcleo puro nas trÃªs guardas. O que se perde Ã© a garantia de que
    # o objeto nunca encosta na borda â€” e isso Ã© o custo aceito, pela mesma
    # razÃ£o que o projeto jÃ¡ aceita cortar um braÃ§o estendido num close
    # (`caixa_do_nucleo`): **enquadramento que persegue a extremidade Ã©
    # cÃ¢mera tremendo, e cÃ¢mera tremendo estraga o plano inteiro, nÃ£o um
    # objeto.** `caixa_extra` continua chegando aqui e deixou de ser usada de
    # propÃ³sito: apagÃ¡-la do contrato esconderia esta decisÃ£o.
    nucleo_lat = nucleo
    bb = None
    if camadas and z > 1.002:
        bb = nucleo
        if bb:
            larg = max(bb[2] - bb[0], 1)
            alt = max(bb[3] - bb[1], 1)
            # O QUE NÃƒO PODE SER CORTADO Ã‰ O CORPO, NÃƒO A PONTA DO DEDO
            # (31/08, volta 11). A largura era a da SILHUETA, e um braÃ§o
            # estendido a pÃµe em 800 a 1080 px: `1080/(larg*1,10)` derrubava
            # o plano de 1,60 para **1,23, e Ã s vezes para 1,00**. O v005
            # pediu close em quatro trechos e nÃ£o teve nenhum -- e a prova
            # daquela volta nÃ£o pegou porque olhou o plano PEDIDO, que Ã© o
            # que o log imprimia.
            #
            # Pior que o plano perdido: a silhueta muda A CADA FRAME, entÃ£o
            # a guarda **fazia a cÃ¢mera respirar junto com o braÃ§o** -- 1,30
            # enquanto os braÃ§os estÃ£o baixos, 1,00 no frame em que a mÃ£o
            # sobe, e de volta. CÃ¢mera que abre quando alguÃ©m gesticula Ã© o
            # contrÃ¡rio do que o gesto pede.
            #
            # Vale aqui a mesma distinÃ§Ã£o da lei 33: coluna atravessada sÃ³
            # pelo braÃ§o nÃ£o Ã© corpo. O nÃºcleo (tronco, cabeÃ§a, pernas) quase
            # nÃ£o muda de largura entre poses, entÃ£o a guarda para de
            # oscilar; e o gesto pode encostar na borda, que Ã© o que um
            # close faz.
            if camada_alvo is not None:
                # NO CLOSE, CORTAR A PERNA Ã‰ O PONTO (31/08, volta 7).
                #
                # A regra de cima -- "o corpo INTEIRO tem de caber" -- Ã© a
                # certa para o plano do par, e Ã© o que desfazia o close: o
                # v007 pediu 1,90 e saiu em ~1,45, porque a Maria Ã© mais
                # alta que a mÃ©dia do elenco e `H/(alt*1.04)` reduziu o
                # zoom atÃ© o corpo dela caber de cabeÃ§a a pÃ©. E o efeito
                # nÃ£o foi sÃ³ um plano mais aberto: a janela cresceu de 568
                # para 745 px e o parceiro voltou a aparecer pela borda,
                # que Ã© o defeito que o close existe para acabar.
                #
                # Um close Ã© um enquadramento que CORTA -- ninguÃ©m filma
                # close-up mostrando os sapatos. O que nÃ£o pode ser cortado
                # Ã© a LARGURA (o gesto sai pela lateral, e gesto Ã© o que
                # este canal tem de melhor) e o ALTO (a cabeÃ§a, e a mÃ£o
                # erguida acima dela). Do quadril para baixo, cortar Ã© a
                # linguagem. A altura entra abaixo, movendo a janela em vez
                # de abrir o plano.
                cabe = W / (larg * 1.06)
            else:
                cabe = min(W / (larg * 1.10), H / (alt * 1.04))
            if cabe < z:
                # A GUARDA DIZ QUANDO APERTA (31/08). Ela desfazia o plano
                # em silÃªncio: o log imprimia `1.90` e o quadro saÃ­a em
                # 1,33, e a diferenÃ§a entre "o close nÃ£o foi feito" e "o
                # close foi feito e desfeito" Ã© onde se procura o defeito.
                # Fail-open precisa de um lugar que conte que ele abriu
                # (lei 65) -- vale tambÃ©m para uma guarda de composiÃ§Ã£o.
                marca = (round(z, 2), round(cabe, 2))
                if marca != _ULTIMO_APERTO.get("v"):
                    _ULTIMO_APERTO["v"] = marca
                    print(f"[camera] plano {z:.2f} nao cabe no corpo "
                          f"({larg}x{alt}px); vai a {max(1.0, cabe):.2f}")
                z = max(1.0, cabe)

    # PROFUNDIDADE DE CAMPO: FECHOU, O FUNDO SAI DE FOCO (31/08, volta 11).
    # Decidido pelo zoom EFETIVO -- depois da guarda --, e nÃ£o pelo plano
    # pedido: fundo nÃ­tido num quadro que na verdade nÃ£o fechou seria borrar
    # por engano. O limiar de 1,35 nÃ£o Ã© cruzado dentro de um trecho com os
    # nÃºmeros de hoje (o degrau mais alto abaixo dele Ã© 1,30, que com o
    # push-in de 3,5% chega a 1,345), entÃ£o o foco nÃ£o pisca no meio de uma
    # fala. Quem mexer no ciclo de planos precisa refazer esta conta.
    borrar = z >= 1.35
    quadro = cenario.quadro(cam.get("fundo_dx", 0.0), borrado=borrar).convert("RGBA")
    if cam.get("chao_y"):
        for c in (camadas or [camada]):
            _sombra_de_contato(quadro, c, float(cam["chao_y"]))
    quadro.alpha_composite(camada)
    quadro = quadro.convert("RGB")

    if abs(z - 1.0) > 0.002:
        lw, lh = W / z, H / z
        # ONDE A CÃ‚MERA CENTRA NA HORIZONTAL. Era o meio do quadro, sempre,
        # e com dois em cena isso estÃ¡ certo -- eles ficam simÃ©tricos em
        # torno dele. Errado Ã© quando UM sai: o que fica estÃ¡ a 0,27 ou a
        # 0,73 do quadro, e fechar no meio deixa metade da tela de parede
        # vazia com o personagem encostado na borda. `centro_x` Ã© o meio
        # de quem estÃ¡ EM CENA, e vem dos quadris, nÃ£o da silhueta: o bbox
        # muda com cada gesto e faria a cÃ¢mera tremer junto com os braÃ§os.
        cx = W * 0.5 if centro_x is None else float(centro_x)
        # nunca atÃ© o fim: enquadrar exatamente no boneco tira o cenÃ¡rio do
        # quadro e o corte deixa de ter lugar nenhum.
        #
        # NO CLOSE A MIRA Ã‰ QUASE INTEIRA (31/08). Com 0,75, fechar em quem
        # estÃ¡ a x=296 deixa a janela em 73..641 e a BORDA do outro (que
        # comeÃ§a em 634) entra por sete pixels: um pedaÃ§o de ombro colado na
        # lateral, que lÃª como enquadramento errado e nÃ£o como corte. Com
        # `camada_alvo` -- que sÃ³ existe no close -- a mira vai a 0,92 e o
        # outro fica de fora inteiro, continuando a sobrar cenÃ¡rio dos dois
        # lados do falante.
        cx = W * 0.5 + (cx - W * 0.5) * (0.92 if camada_alvo is not None else 0.75)
        # COMPOSIÃ‡ÃƒO EM TERÃ‡OS PARA QUEM ESTÃ SOZINHO (31/08, volta 15).
        #
        # O v015 Ã© um monÃ³logo de nove trechos e a personagem estÃ¡ no MEIO
        # do quadro nos dezesseis quadros da folha. O ciclo de planos varia
        # sÃ³ a ESCALA, e os trÃªs degraus do meio (1,15 / 1,30 / 1,45) sÃ£o
        # quase indistinguÃ­veis quando a composiÃ§Ã£o Ã© sempre a mesma: o
        # resultado lÃª como um plano sÃ³, que Ã© a queixa do v005 outra vez,
        # agora por outro motivo.
        #
        # Deslocar a janela um sexto pÃµe o corpo no terÃ§o da esquerda ou da
        # direita, e o outro terÃ§o fica com o cenÃ¡rio -- que desde 28/08 Ã©
        # arte panorÃ¢mica com conteÃºdo atÃ© o teto, feita para aparecer. Ã‰ a
        # variaÃ§Ã£o de enquadramento do plano de melhorias (item 4) sem
        # inventar plano nenhum, e o clamp do bbox logo abaixo continua
        # garantindo que o corpo inteiro caiba.
        cx += float(terco) * lw / 6.0
        # O GESTO NÃƒO SAI PELA BORDA (31/08). A mira Ã© o QUADRIL, de
        # propÃ³sito -- o bbox muda com cada gesto e a cÃ¢mera tremeria junto
        # com os braÃ§os --, mas num close de 568 px de largura um braÃ§o
        # estendido chega a 300 px do quadril e some pela lateral. A saÃ­da
        # nÃ£o Ã© seguir o bbox: Ã© **empurrar a janela sÃ³ o necessÃ¡rio** para
        # ele caber. Enquanto o gesto couber na janela a cÃ¢mera nÃ£o se mexe,
        # e quando nÃ£o couber ela jÃ¡ estava cortando de qualquer jeito.
        # A GUARDA DO ALTO VALE PARA TODO PLANO FECHADO, nÃ£o sÃ³ para o close
        # em quem fala (31/08, volta 11). Com um ator sozinho a mira vertical
        # Ã© o meio do corpo, e a 1,59 isso pÃµe a linha de cima da janela 34px
        # ABAIXO do topo da cabeÃ§a: o cabelo saÃ­a cortado rente ao crÃ¢nio em
        # todos os closes do v011, e ninguÃ©m tinha olhado porque atÃ© esta
        # volta o close com um ator nÃ£o estava acontecendo.
        # E A GUARDA DA LATERAL TAMBÃ‰M VALE PARA TODO PLANO FECHADO (31/08,
        # volta 13). Ela sÃ³ rodava no close em quem fala, e com UM ator
        # sozinho o resultado apareceu na tira de rostos: braÃ§o erguido para
        # o lado, mÃ£o FORA do quadro e o celular boiando ao lado da cabeÃ§a,
        # sem ninguÃ©m segurando. Objeto sem mÃ£o Ã© pior que objeto cortado --
        # ele deixa de ser um objeto e vira um adesivo.
        #
        # E AS DUAS MIRAM O NÃšCLEO, NÃƒO A SILHUETA (31/08, defeito 4). Com a
        # silhueta, um aceno subia a borda de cima 200px e a trazia de volta
        # duas vezes por segundo -- a janela ia junto, e o enquadramento
        # "quebrava" a cada gesto. O que elas protegem passa a ser o corpo e
        # o que a mÃ£o SEGURA (`caixa_extra`); a mÃ£o vazia pode encostar na
        # borda, que Ã© o que um close faz. Ver `caixa_do_nucleo`.
        # A LATERAL usa a caixa COM o objeto: objeto cortado ao meio pela
        # borda Ã© o que lÃª como adesivo, e empurrar a janela de lado nÃ£o
        # muda o tamanho do plano nem faz a cÃ¢mera balanÃ§ar na vertical.
        bba = nucleo_lat
        if bba and (bba[2] - bba[0]) <= lw:
            cx = min(max(cx, bba[2] - lw / 2), bba[0] + lw / 2)
        # O ALTO usa a caixa SEM o objeto: era daqui que vinha o tilt.
        bba = nucleo
        cy = H * float(cam.get("zoom_y", 0.5))
        # A CABEÃ‡A NUNCA Ã‰ CORTADA. O close mira a cabeÃ§a (`centro_rosto`),
        # mas uma aÃ§Ã£o que ergue a mÃ£o sobe a silhueta acima dela -- e o
        # certo entÃ£o Ã© DESCER a janela (cortando mais perna, que Ã© o que
        # um close corta), nunca abrir o plano.
        if bba:
            cy = min(cy, bba[1] - 0.03 * lh + lh / 2)
        x0 = min(max(cx - lw / 2, 0), W - lw)
        y0 = min(max(cy - lh / 2, 0), H - lh)
        # ampliaÃ§Ã£o: BILINEAR, senÃ£o o zoom desenha um fio branco em volta
        # de cada traÃ§o preto do quadro (ver _reamostrar)
        quadro = _reamostrar(
            quadro.crop((int(x0), int(y0), int(x0 + lw), int(y0 + lh))), (W, H))
    return quadro


# O CLOSE EM QUEM FALA (31/08, volta 6 do ciclo de vÃ­deo).
#
# 1,90 Ã© o plano em que UM dos dois enche o quadro: com dois em cena a
# escala cai para 0,74 e o corpo mede ~852 px de altura por ~300 de largura,
# entÃ£o a janela de 568x1010 que 1,90 recorta o comporta inteiro, com folga
# para o braÃ§o erguido, e a CARA passa de ~85 para ~160 px. Acima disso a
# arte comeÃ§a a aparecer ampliada quatro vezes -- a folha do personagem Ã©
# desenhada uma vez sÃ³, e nÃ£o hÃ¡ de onde tirar mais pixel.
CLOSE_FALANTE = 1.90


def _terco_do_trecho(i, n_atores):
    """Em que terÃ§o do quadro o corpo fica neste trecho: -1, 0 ou +1.

    SÃ“ COM UM ATOR. Com dois, a divisÃ£o do quadro jÃ¡ Ã© a composiÃ§Ã£o (um em
    cada lado), e deslocar a janela tiraria um deles; no close em quem fala
    o lado jÃ¡ Ã© escolhido pelo quadril de quem fala.

    Alterna centro â†’ esquerda â†’ centro â†’ direita, perÃ­odo 4: com perÃ­odo 2
    a composiÃ§Ã£o voltaria a ser sempre a mesma alternÃ¢ncia, e o centro no
    meio dÃ¡ o descanso que faz o deslocamento ser percebido como escolha e
    nÃ£o como tremor.

    ZERADA EM 03/09, e o motivo Ã© que ela deixou de pagar o prÃ³prio custo.

        Queixa do dono do projeto, duas vezes seguidas: *"centralizaÃ§Ã£o do
        personagem, Ã s vezes o personagem fica fora de centro"*. A folha do
        v003 mostra o caso â€” trÃªs quadros com a personagem no canto de baixo Ã 
        esquerda e dois terÃ§os de parede vazia Ã  direita.

        O deslocamento de um sexto Ã© regra de composiÃ§Ã£o legÃ­tima, mas ela
        supÃµe que o outro terÃ§o tenha o que mostrar. O cenÃ¡rio deste canal Ã©
        arte panorÃ¢mica gerada, e o terÃ§o que sobra Ã© parede lisa com muita
        frequÃªncia: o que se vÃª nÃ£o Ã© composiÃ§Ã£o, Ã© um personagem empurrado
        para o canto.

        E o problema que ela veio resolver mudou de tamanho. Em 31/08 (volta
        15) um monÃ³logo era um plano sÃ³, porque o ciclo variava apenas a
        ESCALA e os degraus do meio sÃ£o indistinguÃ­veis. Desde entÃ£o
        entraram o CLOSE NO FALANTE (1,90) e o gancho fechado, que sÃ£o cortes
        de verdade -- a variaÃ§Ã£o existe agora sem precisar deslocar ninguÃ©m.

        Fica em zero, e a funÃ§Ã£o fica de pÃ©: no dia em que houver cenÃ¡rio com
        conteÃºdo nos dois terÃ§os, Ã© um nÃºmero que se muda de volta.
    """
    if n_atores != 1:
        return 0
    return 0


def _close_no_falante(i, n_trechos, n_atores):
    """Este trecho fecha em QUEM FALA, deixando o outro sair do quadro?

    POR QUE ISTO EXISTE
        O v006 saiu com dezesseis quadros no MESMO plano aberto, os dois de
        corpo inteiro, do primeiro ao Ãºltimo segundo -- apesar de o ciclo de
        planos existir desde 27/08. A causa nÃ£o era o ciclo: com dois atores
        o teto Ã© 1,25, e 1,00 â†’ 1,25 Ã© uma variaÃ§Ã£o que ninguÃ©m percebe.
        Subir o teto nÃ£o resolvia, porque `montar_frame` limita o zoom Ã 
        silhueta dos DOIS somados (740 px) e trava tudo em 1,33.

        O plano de melhorias pede outra coisa, e Ã© ela que falta: *"close no
        personagem que estÃ¡ falando; depois, cortar para o outro durante a
        resposta"*. Isso nÃ£o Ã© fechar mais no par -- Ã© enquadrar UM e deixar
        o outro fora. Como o falante alterna a cada trecho, alternar o close
        produz de graÃ§a o corte de conversa que o formato pede.

    A REGRA, E POR QUE ELA NÃƒO Ã‰ "UM SIM, UM NÃƒO"
        A primeira versÃ£o fechava nos Ã­mpares, e a prÃ©via mostrou o defeito
        na hora: **os seis closes saÃ­ram todos na Maya**. O falante alterna
        a cada trecho, entÃ£o fechar com perÃ­odo 2 fecha sempre na mesma
        pessoa -- o JoÃ£o atravessou o vÃ­deo inteiro sem um close, que Ã©
        metade do problema que isto veio resolver.

        O perÃ­odo tem de ser ÃMPAR para cair nas duas paridades. SÃ£o dois
        closes a cada cinco trechos (`i % 5 in (1, 4)`): eles caem em 1, 4,
        6, 9, 11 -- Ã­mpar, par, par, Ã­mpar, Ã­mpar --, e os dois lados da
        conversa ganham cara grande. Dois em cinco tambÃ©m Ã© o espaÃ§amento
        que o plano de melhorias pede (mudanÃ§a visual a cada 2 a 5 s) sem
        que o close vire o plano padrÃ£o.

        A virada (Ãºltimo trecho) fecha sempre, porque a piada acontece na
        cara; e o trecho ANTES dela abre sempre -- sem o contraste, a virada
        chegaria no mesmo tamanho do que veio antes e o fechamento nÃ£o seria
        lido como troca de plano. Com menos de trÃªs trechos nÃ£o hÃ¡
        alternÃ¢ncia que valha: o vÃ­deo inteiro viraria um close sÃ³.
    """
    if n_atores < 2 or n_trechos < 3:
        return False
    # O GANCHO FECHA (01/09, R1 do DIAGNOSTICO.md). Todo vÃ­deo do canal
    # abria em plano ABERTO -- dois bonecos em pÃ©, de corpo inteiro, e a
    # cara a ~7% da altura do quadro. Nos trÃªs primeiros segundos Ã© onde a
    # plataforma decide se distribui o vÃ­deo, e Ã© exatamente onde este
    # formato mostrava menos. Fechar no trecho 0 nÃ£o custa nada: o plano
    # jÃ¡ existe, e o que muda Ã© onde ele cai.
    #
    # Vem ANTES da regra do penÃºltimo porque num vÃ­deo de 2 ou 3 trechos
    # o trecho 0 seria `n_trechos - 2` e o gancho voltaria a abrir.
    if i == 0:
        return True
    # e o trecho 1 ABRE, sempre. `i % 5 in (1, 4)` fechava justamente ele,
    # e dois closes seguidos no comeÃ§o apagam o corte que o gancho acabou
    # de ganhar -- Ã© a mesma razÃ£o pela qual o penÃºltimo abre antes da
    # virada. Os closes restantes caem em 4, 6, 9, 11, que continuam
    # pegando as duas paridades do falante (a regra do perÃ­odo Ã­mpar).
    if i == 1 or i == n_trechos - 2:
        return False
    return i % 5 in (1, 4) or i == n_trechos - 1


def _enquadramento(i, n_trechos, n_atores, t, centro_corpo=None,
                   close=False, centro_rosto=None, teto_par=1.0):
    """Plano do trecho `i`: quanto a cÃ¢mera fecha, e onde ela centra.

    POR QUE ISTO EXISTE
        AtÃ© 27/08 o personagem saÃ­a sempre do mesmo tamanho e sempre no
        meio, do primeiro ao Ãºltimo segundo. Num feed isso lÃª como imagem
        parada com Ã¡udio por cima -- foi a queixa depois do terceiro vÃ­deo
        da esteira ("os dois ficam quase parados"). Gesto e cara resolvem
        metade; a outra metade Ã© a CÃ‚MERA, e ela jÃ¡ existia no motor
        (`cam["zoom"]`), sÃ³ que ninguÃ©m a usava fora de uma aÃ§Ã£o.

    O QUE ELE FAZ
        1. Cada trecho tem um plano diferente do vizinho -- aberto, mÃ©dio,
           fechado, girando. A troca de plano entre trechos Ã© o corte que
           este formato nÃ£o tem: corte reseta a atenÃ§Ã£o de quem rola o
           feed, e Ã© o recurso de retenÃ§Ã£o mais barato que existe.
        2. Dentro do trecho a cÃ¢mera FECHA devagar (push-in). CÃ¢mera que
           anda um pouco o tempo todo Ã© o que separa vÃ­deo de fotografia.
        3. O Ãºltimo trecho Ã© a virada e fecha no rosto: a piada acontece
           na cara, e Ã© para ela que se olha quando a tirada cai.

    O TETO DEPENDE DE QUANTA GENTE ESTÃ EM CENA. Com dois atores (em
    x=296 e x=784 num quadro de 1080) fechar demais corta um deles pela
    borda, entÃ£o o teto cai para 1,12 -- com um ator sozinho, no meio do
    quadro, dÃ¡ para ir a 1,30 sem perder braÃ§o nenhum."""
    # 1,25 COM DOIS (30/08). Eram 1,12, escolhidos no olho quando o teto do
    # frame ainda nÃ£o existia: fechar mais cortava um deles pela borda. Hoje
    # `montar_frame` mede a silhueta REAL de cada frame e limita o zoom ao
    # que ela comporta (29/08), entÃ£o o nÃºmero aqui deixou de ser a Ãºnica
    # proteÃ§Ã£o -- e 1,00 a 1,12 Ã© uma variaÃ§Ã£o que ninguÃ©m percebe num vÃ­deo
    # de 66 s com treze trechos. Os dois ficam em x=296 e 784 e ocupam ~740
    # dos 1080 px: cabe fechar bem mais que 12%.
    # 1,30 -> 1,60 COM UM SÃ“ (31/08, volta 5 do ciclo de vÃ­deo). O v005 foi
    # um monÃ³logo e os dezesseis quadros saÃ­ram no MESMO plano inteiro: um
    # boneco no meio de um 9:16, com um terÃ§o de quadro vazio de cada lado.
    # O teto de 1,30 vinha de quando havia sempre dois em cena, onde ele Ã©
    # o certo -- fechar mais corta um pela borda. Sozinho, no meio, o corpo
    # ocupa ~370 dos 1080 px: 1,30 nem chega a encher metade.
    #
    # O plano de melhorias pede close nas falas importantes (itens 4 e 5), e
    # Ã© aqui que ele cabe sem inventar camada nenhuma: o ciclo de planos jÃ¡
    # existe, sÃ³ faltava alcance para o degrau fechado ser um CLOSE de
    # verdade e nÃ£o outro plano mÃ©dio.
    #
    # 1,60 e nÃ£o mais: acima disso o topo da cabeÃ§a encosta na borda quando
    # a aÃ§Ã£o levanta o braÃ§o, e `montar_frame` passaria a cortar o gesto --
    # que Ã© justamente o que este vÃ­deo tem de melhor.
    # O CLOSE NÃƒO PASSA PELO CICLO. Ele Ã© um plano Ã  parte -- enquadra UM
    # ator, nÃ£o o par --, entÃ£o nem o teto nem os cinco degraus valem para
    # ele. O push-in de 3,5% continua, que Ã© o que separa vÃ­deo de foto.
    if close:
        z = CLOSE_FALANTE * (1.0 + 0.035 * max(0.0, min(1.0, t)))
        meia = 0.5 / z
        alvo = centro_rosto if centro_rosto is not None else centro_corpo
        if alvo is None:
            alvo = 0.5
        return z, max(meia, min(1.0 - meia, float(alvo)))
    # O PLANO DO PAR NÃƒO EXISTE, E PEDI-LO FAZ A CÃ‚MERA PULSAR (31/08,
    # volta 18). O log da guarda mostrou o que o teto de 1,25 vira na
    # prÃ¡tica com dois em cena: `plano 1.15 nao cabe no corpo (933x867px);
    # vai a 1.05`, dezesseis vezes no mesmo trecho, com valores diferentes
    # a cada frame -- 1,05, 1,15, 1,12, 1,08, 1,06. O nÃºcleo dos dois ocupa
    # ~900 dos 1080 px, entÃ£o nada acima de ~1,09 cabe; o ciclo pedia
    # 1,06/1,12/1,19/1,25 e recebia ruÃ­do. Zoom que oscila 10% dentro de
    # uma fala Ã© a cÃ¢mera pulsando junto com os braÃ§os -- o mesmo defeito
    # que o nÃºcleo tinha acabado de resolver com um ator.
    #
    # Com dois em cena a variaÃ§Ã£o de plano Ã© OUTRA: Ã© o close em quem fala
    # (1,90) alternando com o plano dos dois. Os degraus intermediÃ¡rios nÃ£o
    # existem, e pedir o que nÃ£o cabe sÃ³ produz tremor.
    #
    # O QUE MUDOU EM 01/09 (volta 57): o plano do par deixou de ser a
    # CONSTANTE 1,00 e passou a ser o que a largura MEDIDA dos dois
    # comporta (`teto_par`, calculado uma vez por trecho a partir de
    # `meia_esq`/`meia_dir`). A razÃ£o de 1,00 nunca foi estÃ©tica -- era
    # que nada acima de ~1,09 cabia com os dois a 496px um do outro. Com
    # eles a ~346px (ABERTURA_DO_PAR) cabe bem mais, e a diferenÃ§a Ã© entre
    # dois bonecos no rodapÃ© e dois rostos legÃ­veis.
    #
    # O NÃšMERO VEM DE FORA E Ã‰ FIXO DENTRO DO TRECHO -- Ã© isso que separa
    # esta correÃ§Ã£o do tremor do v018. LÃ¡ o valor era recalculado a cada
    # frame pela guarda e oscilava 1,05/1,15/1,12; aqui ele Ã© medido no
    # repouso, uma vez, e a guarda por frame sÃ³ age se alguma pose
    # inesperada estourar.
    #
    # E O CICLO DE PLANOS DO PAR VOLTOU A EXISTIR, com DOIS degraus. Ele
    # tinha sido desligado no v018 porque nada acima de ~1,09 cabia, e
    # pedir o que nÃ£o cabe produz tremor, nÃ£o plano. Com o par a 622px em
    # vez de 900, cabe -- e a alternÃ¢ncia entre trechos Ã© o CORTE que este
    # formato nÃ£o tem. Dois degraus e nÃ£o cinco: a liÃ§Ã£o do v018 continua
    # valendo, degrau intermediÃ¡rio com dois em cena Ã© imperceptÃ­vel.
    if n_atores > 1:
        z = max(1.0, min(TETO_PAR, float(teto_par)))
        # perÃ­odo 2 nos trechos do par. Ele nÃ£o briga com o perÃ­odo 5 do
        # close: o close tira o trecho do par, entÃ£o a alternÃ¢ncia aqui Ã©
        # sobre os que sobraram, e cair na mesma paridade duas vezes
        # seguidas Ã© o que dÃ¡ o descanso (a liÃ§Ã£o do perÃ­odo Ã­mpar do
        # `_close_no_falante` Ã© sobre quem FALA, e aqui nÃ£o hÃ¡ falante).
        if i % 2:
            # o degrau ABERTO: 1,20 quando a largura do par o comporta, e o
            # que ela comportar quando nÃ£o (ver PISO_PAR_ABERTO)
            z = min(PISO_PAR_ABERTO, max(1.0, float(teto_par)))
        return z * (1.0 + 0.035 * max(0.0, min(1.0, t))), \
            (0.5 if centro_corpo is None else
             max(0.0, min(1.0, float(centro_corpo))))
    teto = 1.60
    # O CICLO PRECISOU CRESCER COM A ESQUETE (30/08). Eram trÃªs posiÃ§Ãµes
    # (aberto, mÃ©dio, fechado), e num vÃ­deo de 5 trechos elas davam uma
    # sequÃªncia que nÃ£o se repetia. Com 13 trechos o ciclo roda QUATRO
    # vezes, e a prÃ©via do primeiro vÃ­deo de 88 s mostra o resultado: doze
    # quadros com o mesmo enquadramento, porque 1,00 â†’ 1,12 Ã© uma diferenÃ§a
    # que ninguÃ©m percebe quando volta a cada trÃªs trechos.
    #
    # Cinco degraus em ordem NÃƒO monotÃ´nica: o salto de fechado para aberto
    # Ã© o que se lÃª como corte. Em ordem crescente, o mesmo conjunto viraria
    # um zoom-in lento de treze trechos, que Ã© o contrÃ¡rio de cortar.
    meio = 1.0 + (teto - 1.0) * 0.5
    ciclo = (1.0, teto, 1.0 + (teto - 1.0) * 0.25, meio,
             1.0 + (teto - 1.0) * 0.75)
    if i == 0:
        base = teto                     # o GANCHO fecha (ver _close_no_falante)
    elif i == n_trechos - 1:
        base = teto                     # a virada fecha no rosto
    elif i == n_trechos - 2:
        base = ciclo[0]                 # e o trecho antes dela ABRE: sem o
        # contraste, a virada chegaria no mesmo tamanho do que veio antes e
        # o fechamento nao seria percebido como troca de plano
    else:
        base = ciclo[i % len(ciclo)]
    z = base * (1.0 + 0.035 * max(0.0, min(1.0, t)))
    # ONDE A CÃ‚MERA CENTRA. Fechar no meio do quadro corta pÃ©s e cabeÃ§a em
    # partes iguais; o certo Ã© centrar em quem estÃ¡ em cena.
    #
    # `centro_corpo` Ã© o meio do corpo, em fraÃ§Ã£o da altura, e ele MUDA com
    # o cenÃ¡rio: desde que os pÃ©s passaram a pousar no chÃ£o desenhado, o
    # personagem pode estar a 78% do quadro (rua) ou a 95% (sala com o
    # aparador na frente). O valor fixo que existia aqui puxava o corte
    # para CIMA -- feito quando todo mundo ficava a 78% -- e nos cenÃ¡rios
    # de chÃ£o baixo isso decepava os pÃ©s.
    #
    # Sem o parÃ¢metro, cai no comportamento antigo: Ã© o que os specs de
    # conferÃªncia e o `enquadramento.py` usam.
    if centro_corpo is None:
        fechado = (z - 1.0) / max(teto * 1.035 - 1.0, 1e-6)
        return z, 0.5 - 0.10 * max(0.0, min(1.0, fechado))
    # o clamp mantÃ©m a janela dentro do quadro: centrar em 0,73 com zoom
    # 1,12 pediria uma faixa que comeÃ§a abaixo do topo e acaba fora da
    # base, e o crop de `montar_frame` a empurraria de volta de qualquer
    # jeito -- fazer a conta aqui deixa o nÃºmero honesto no log.
    meia = 0.5 / z
    return z, max(meia, min(1.0 - meia, float(centro_corpo)))


# =====================================================================
def _rig_do_trecho(tr, t, pan_base, acoes_do_ator, x_base, falando=True,
                   semente_gesto=0.0, na_mao=None):
    """Ã‚ngulos do frame de UM ator. Dois caminhos:

    AÃ‡Ã•ES (novo)  -- verbos com janela, somados por cima do repouso.
    POSE (velho)  -- interpolaÃ§Ã£o entre duas poses estÃ¡ticas. Fica sÃ³
                     para nÃ£o quebrar spec antigo; nÃ£o produz caminhada.

    A pilha do caminho novo, de baixo para cima:

        postura da emoÃ§Ã£o -> parado -> gesticular -> aÃ§Ãµes do roteiro

    Postura e gesto de fala sÃ£o o CORPO da emoÃ§Ã£o que o trecho jÃ¡ declarou
    (ver acoes.POSTURA); ficam embaixo porque tudo que o roteirista pedir
    de propÃ³sito tem que ganhar deles.
    """
    rig = merge(REST, EXPRESSOES.get(tr.get("expressao", "neutro"), {}))
    rig["quadril"] = [x_base, REST["quadril"][1]]

    if acoes_do_ator or tr.get("acoes"):
        ACOES.aplicar_postura(rig, tr.get("expressao"), tr.get("intensidade", 1.0))
        lista = [{"nome": "parado", "de": 0.0, "ate": 1.0}]
        if falando:
            lista.append({"nome": "gesticular", "de": 0.0, "ate": 1.0,
                          "semente": semente_gesto,
                          "forca": ACOES.energia_gesto(tr.get("expressao"),
                                                       tr.get("intensidade", 1.0))})
        else:
            # QUEM ESCUTA TAMBÃ‰M ESTÃ EM CENA (01/09, volta 57). Sem isto,
            # em todo trecho um dos dois passa a fala inteira com os braÃ§os
            # mortos ao lado do corpo -- e como o falante alterna, cada
            # personagem fica assim metade do vÃ­deo. `escutar` Ã© de
            # propÃ³sito muito menor que `gesticular`: quem escuta nÃ£o pode
            # disputar a atenÃ§Ã£o com quem fala.
            lista.append({"nome": "escutar", "de": 0.0, "ate": 1.0,
                          "forca": 0.7 + 0.3 * ACOES.energia_gesto(
                              tr.get("expressao"), tr.get("intensidade", 1.0))})
        # QUEM ESTÃ COM ALGUMA COISA NA MÃƒO A SEGURA NA FRENTE DO CORPO
        # (04/09). Depois de `gesticular`/`escutar` porque Ã© o braÃ§o que
        # segura que manda nele, e antes das aÃ§Ãµes do roteiro porque o que o
        # roteirista escrever para esse braÃ§o continua ganhando. Ver
        # `acoes.segurar`: sem isto o objeto desce com o braÃ§o em repouso e
        # vira um adesivo na coxa.
        if na_mao:
            lista.append({"nome": "segurar", "de": 0.0, "ate": 1.0,
                          "mao": na_mao.get("mao", "d")})
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

    Um personagem sÃ³ continua sendo o caso normal: sem `elenco` no spec,
    monta um elenco de um. Assim nada do que jÃ¡ roda precisa saber que
    existe elenco."""
    elenco = spec.get("elenco")
    if not elenco:
        # TRÃŠS VALORES, SEMPRE. Este atalho devolvia `(Personagem, x)` --
        # duas posiÃ§Ãµes --, enquanto o caminho com `elenco` passa por
        # `_alinhar_pelos_pes` e devolve `(Personagem, x, dy)`. Todo o
        # resto do motor desempacota TRÃŠS, entÃ£o um spec de um personagem
        # sÃ³ derrubava o cut-out inteiro com "not enough values to unpack
        # (expected 3, got 2)" -- e o job caÃ­a no rig vetorial, que Ã© a
        # rede de seguranÃ§a.
        #
        # O bug estava aqui desde que o elenco existe e nunca tinha
        # aparecido: TODO spec de produÃ§Ã£o vinha com dois em cena, porque
        # o prompt pedia sempre uma cena de dois. O primeiro vÃ­deo gerado
        # com a forma `monologo_fisico` (o rodÃ­zio de 29/08) o encontrou
        # na primeira tentativa. Ã‰ a lei 34 pelo avesso -- o que a forma
        # nÃ£o exercita nÃ£o falha Ã  vista.
        return _alinhar_pelos_pes({"_": (Personagem(pasta_padrao), W / 2)})
    # DOIS EM CENA, MAS NÃƒO DOIS NO VÃDEO (30/08, noite).
    #
    # AtÃ© aqui este trecho TRUNCAVA o elenco em dois na carga, e o loop de
    # render desenhava o elenco inteiro em todo trecho -- entÃ£o "dois por
    # vez" e "dois no vÃ­deo" eram a mesma coisa, e um elenco de dez servia
    # para escolher a dupla do dia, nunca para trocar de gente no meio.
    #
    # O dono do projeto pediu o contrÃ¡rio: *"pode ter apenas dois
    # personagens por vez no vÃ­deo, mas nÃ£o precisa ter apenas dois no
    # vÃ­deo; ele pode andar e aparecer outro personagem, e assim por
    # diante"*. Isso nÃ£o afrouxa a lei 10 -- o teto de DOIS no quadro
    # continua, porque a razÃ£o dele Ã© o 9:16 e a cara. O que muda Ã© onde ele
    # Ã© aplicado: por TRECHO (`_em_cena`), nÃ£o por vÃ­deo.
    #
    # Aqui, entÃ£o, carrega-se todo mundo. Quem entra em cena em cada trecho
    # Ã© decidido depois, e Ã© `_posicionar` que dÃ¡ o x de cada um dentro do
    # trecho -- porque o lugar de alguÃ©m no quadro depende de com QUEM ele
    # estÃ¡ dividindo a cena naquele momento, nÃ£o do tamanho do elenco.
    n_cena = min(len(elenco), MAX_EM_CENA)
    fora, pedidos = {}, {}
    for i, (chave, cfg) in enumerate(elenco.items()):
        cfg = cfg if isinstance(cfg, dict) else {"pasta": cfg}
        pasta = cfg.get("pasta") or os.path.join(pasta_padrao, "..", chave)
        # posiÃ§Ãµes padrÃ£o bem separadas: duas pessoas no mesmo x viram uma
        # pessoa sÃ³ com quatro braÃ§os
        padrao = W * (0.5 if n_cena == 1 else
                      (0.5 - ABERTURA_DO_PAR / 2.0)
                      + ABERTURA_DO_PAR * (i % n_cena) / max(n_cena - 1, 1))
        p = Personagem(pasta)
        # A ESCALA VEM DE QUANTOS CABEM EM CENA, nÃ£o de quantos existem no
        # vÃ­deo. Com o elenco solto, `len(elenco)` pode ser seis, e usÃ¡-lo
        # aqui encolheria todo mundo a um sexto do quadro para uma cena que
        # nunca tem mais de dois.
        p.escala *= float(cfg.get("escala", 1.0 if n_cena == 1 else 0.74))
        fora[chave] = (p, float(cfg.get("x", padrao)))
        pedidos[chave] = "x" in cfg
    fora = _alinhar_pelos_pes(fora)
    fora = _afastar_o_bastante(fora, pedidos)
    if len(elenco) > MAX_EM_CENA:
        print(f"[elenco] {len(elenco)} personagens no video; "
              f"{MAX_EM_CENA} por vez em cena, decididos trecho a trecho")
    return fora


def _em_cena(tr, elenco, falante, anteriores):
    """Quem aparece NESTE trecho, no mÃ¡ximo `MAX_EM_CENA`.

    A regra, em ordem, e cada passo existe por um motivo:

      1. quem FALA entra sempre -- uma fala sem dono na tela Ã© a lei 15
         (nÃ£o existe narrador) voltando pela porta dos fundos;
      2. depois quem o roteirista pediu em `personagens_em_cena`, na ordem
         em que ele escreveu;
      3. se ainda sobra vaga, quem estava em cena no trecho ANTERIOR. Ã‰ o
         que dÃ¡ continuidade: sem isso, um trecho que sÃ³ nomeia o falante
         esvaziaria a cena e o outro sumiria sem sair andando -- corte de
         gente, que Ã© o defeito que a lei 36 descreve.

    Nome que nÃ£o estÃ¡ no elenco Ã© descartado em silÃªncio de propÃ³sito: ele
    nÃ£o tem arte, e `job.py` jÃ¡ avisou disso ao montar o spec.
    """
    ordem = []
    if falante in elenco:
        ordem.append(falante)
    for c in (tr.get("personagens_em_cena") or []):
        c = str(c)
        if c in elenco and c not in ordem:
            ordem.append(c)
    for c in (anteriores or []):
        if c in elenco and c not in ordem:
            ordem.append(c)
    # NO PRIMEIRO TRECHO NÃƒO HÃ ANTERIOR (31/08, defeito 5 dos vÃ­deos).
    #
    # `anteriores` comeÃ§ava valendo o elenco inteiro, "para o primeiro
    # trecho ter um anterior" -- e com isso a regra 3 punha em cena, jÃ¡ no
    # primeiro segundo do vÃ­deo, alguÃ©m que o roteirista tinha deixado de
    # fora de propÃ³sito porque ele ENTRA depois. O resultado na tela Ã© o
    # teleporte da queixa: a personagem aparece parada no lugar dela, o
    # trecho seguinte comeÃ§a e ela salta para a borda para entrar andando.
    #
    # `anteriores` vazio Ã© a verdade do primeiro trecho, e a continuidade
    # nÃ£o perde nada: ela existe para nÃ£o esvaziar uma cena que jÃ¡ existia.
    # O que fica de fora Ã© o spec ANTIGO, que nÃ£o escreve
    # `personagens_em_cena` -- para ele o elenco carregado continua sendo a
    # cena, como era antes de o campo existir.
    if not tr.get("personagens_em_cena") and not anteriores:
        for c in list(elenco)[:MAX_EM_CENA]:
            if c not in ordem:
                ordem.append(c)
    if not ordem:
        ordem = list(elenco)[:1]
    escolhidos = ordem[:MAX_EM_CENA]
    # A ORDEM DE SAÃDA Ã‰ A DO ELENCO, NÃƒO A DE ENTRADA (31/08, volta 1).
    #
    # Quem entra na lista primeiro Ã© o FALANTE -- e o falante alterna a cada
    # trecho. Como `_posicionar` distribui o quadro pela ordem que recebe,
    # os dois TROCAVAM DE LADO a cada fala: no vÃ­deo 001 a Maya estÃ¡ Ã 
    # esquerda nos trechos 1 a 3, o JoÃ£o no 4, ela de novo no 5. NÃ£o Ã©
    # movimento, Ã© pisca-pisca de posiÃ§Ã£o -- e Ã© pior que o defeito que
    # `_separar` existe para evitar, porque a plateia perde a referÃªncia de
    # quem Ã© quem.
    #
    # A ordem do elenco no spec Ã© estÃ¡vel durante o vÃ­deo inteiro, e Ã© ela
    # que `_carregar_elenco` jÃ¡ usou para dar o x base. Ordenar por ela
    # devolve a regra que existia antes do elenco solto: quem estÃ¡ Ã 
    # esquerda continua Ã  esquerda.
    pos = {c: i for i, c in enumerate(elenco)}
    return sorted(escolhidos, key=lambda c: pos.get(c, 99))


def _posicionar(elenco, chaves):
    """As posiÃ§Ãµes de quem estÃ¡ em cena NESTE trecho.

    Existe porque o x de um personagem nÃ£o Ã© uma propriedade dele: Ã© a
    divisÃ£o do quadro entre quem estÃ¡ lÃ¡ agora. Com o elenco solto, o mesmo
    personagem fica Ã  direita quando divide a cena com um e sozinho no
    centro quando o outro sai -- e o `_afastar_o_bastante` sÃ³ sabe separar
    quem estÃ¡ em cena junto.
    """
    if not chaves:
        return {}
    sub = {c: elenco[c] for c in chaves}
    n = len(sub)
    posto, pedidos = {}, {}
    for i, c in enumerate(chaves):
        pers, _x, dy = sub[c]
        x = W * (0.5 if n == 1 else (0.5 - ABERTURA_DO_PAR / 2.0)
                 + ABERTURA_DO_PAR * i / max(n - 1, 1))
        posto[c] = (pers, x, dy)
        pedidos[c] = False
    return _afastar_o_bastante(posto, pedidos)


def _alinhar_pelos_pes(elenco):
    """Todo mundo pisa na MESMA linha do chÃ£o.

    O rig ancora o personagem pelo QUADRIL -- Ã© a raiz do esqueleto, e Ã© de
    lÃ¡ que a Ã¡rvore de peÃ§as se abre. SÃ³ que a altura do quadril dentro do
    corpo Ã© decisÃ£o do desenhista: no Pal e no Zeca o quadril fica a 66% da
    figura, na Maya a 56% (a legging faz a divisÃ£o subir). Postos com o
    quadril na mesma altura, os pÃ©s dela caÃ­ram 90 px abaixo dos dele -- os
    dois no mesmo cenÃ¡rio, um pisando no chÃ£o e o outro enterrado nele.

    A correÃ§Ã£o nÃ£o Ã© proporÃ§Ã£o nem tabela: Ã© MEDIR. Cada personagem Ã©
    desenhado uma vez em repouso, e o deslocamento vertical que pÃµe a base
    dele na base do primeiro fica guardado. Custa um frame por ator, no
    carregamento, e vale para qualquer folha nova sem ninguÃ©m ajustar nada.

    Devolve {chave: (Personagem, x, dy)}.
    """
    base_ref, fora = None, {}
    for chave, (pers, x) in elenco.items():
        rig = merge(REST, {})
        rig["quadril"] = [W / 2.0, REST["quadril"][1]]
        img = desenhar_personagem(pers, rig)
        bb = img.getbbox()
        base = bb[3] if bb else REST["quadril"][1]
        if base_ref is None:
            base_ref = base
        dy = base_ref - base
        if abs(dy) > 1:
            print(f"[elenco] {chave}: {dy:+.0f}px em y para pisar na mesma "
                  f"linha do chao")
        _medir_corpo(pers, img, bb)
        fora[chave] = (pers, x, float(dy))
    return fora


# NINGUÃ‰M ATRAVESSA NINGUÃ‰M (29/08) ------------------------------------
# Uma coluna da imagem pertence ao CORPO se ela tem pelo menos esta fraÃ§Ã£o
# da altura da figura preenchida. Ã‰ o que separa tronco, cabeÃ§a e pernas
# -- que ocupam a coluna inteira -- de um braÃ§o estendido, que numa coluna
# ocupa a espessura do braÃ§o. Medido nos trÃªs personagens de produÃ§Ã£o: a
# 45% o Pal em repouso dÃ¡ 258px de corpo e 558px de silhueta, e `apontar`
# muda a silhueta de 558 para 689 sem mexer no corpo. Abaixo de 30% o
# braÃ§o caÃ­do entra na conta; acima de 65% a cabeÃ§a sai dela.
LIMIAR_CORPO = 0.45
# O vÃ£o que fica entre dois corpos. NÃ£o Ã© estÃ©tica: encostado, o contorno
# preto de um vira contorno do outro e os dois lÃªem como uma figura sÃ³.
FOLGA_ENTRE_ATORES = 40.0
# ONDE OS DOIS FICAM NO QUADRO -- e por que isto encolheu (01/09, volta 57).
#
# Eram 0,27 e 0,73, ou seja 496px entre os quadris num quadro de 1080. O
# nÃºmero foi escolhido no olho em 28/08, ANTES de existir `_separar` (a
# guarda que mede colisÃ£o frame a frame) e antes de `_afastar_o_bastante`
# (que abre as posiÃ§Ãµes atÃ© os CORPOS MEDIDOS caberem). Escolhido no olho,
# ele errou para o lado caro: com os dois tÃ£o longe um do outro, o nÃºcleo
# do par ocupa ~900 dos 1080px e NENHUM plano acima de ~1,09 cabe -- Ã© a
# aritmÃ©tica do v018, e Ã© ela que faz o plano aberto ser sempre o mesmo
# plano aberto.
#
# O preÃ§o aparece na tira de rostos da volta 57: em oito dos doze quadros
# os dois estÃ£o no rodapÃ©, com a CARA a ~7% da altura do quadro e dois
# terÃ§os de armÃ¡rio de cozinha em cima. Num telefone nÃ£o se lÃª expressÃ£o
# nenhuma ali -- e a cara Ã© onde a piada acontece desde a volta 6.
#
# 0,34/0,66 dÃ¡ ~346px entre os quadris. Isto NÃƒO Ã© uma aposta: quem
# garante que cabe Ã© `_afastar_o_bastante`, que mede meia_esq e meia_dir
# na arte de cada um e reabre para o mÃ­nimo se 346 for pouco. O nÃºmero
# aqui virou o PEDIDO; a medida continua sendo a garantia.
ABERTURA_DO_PAR = 0.32
# a margem que sobra de cada lado do par quando a cÃ¢mera fecha nele. O
# gesto pode encostar na borda (Ã© o que um plano fechado faz), o TRONCO
# nÃ£o pode.
MARGEM_LATERAL_PAR = 60.0
# teto do plano do par. Acima disso a folha -- desenhada uma vez sÃ³ --
# comeÃ§a a aparecer ampliada demais, e Ã© o mesmo limite que segura
# CLOSE_FALANTE em 1,90 com um corpo de 852px.
TETO_PAR = 1.45
# O DEGRAU ABERTO DO PAR DEIXOU DE SER 1,00 (02/09, volta 84).
#
# O ciclo do par alterna dois degraus, e o aberto era a constante 1,00 --
# heranÃ§a de quando nada acima de ~1,09 cabia (v018), antes de a abertura
# cair para 0,32 e o par passar a ocupar ~606px de 1080. Na prÃ©via do v084
# os trÃªs quadros de 1,00 (10,1 s, 28,0 s, 63,8 s) sÃ£o os mesmos trÃªs em que
# os dois aparecem no rodapÃ© com DOIS TERÃ‡OS de quadro vazio em cima -- e o
# que enche esse vazio Ã© a parte fria do cenÃ¡rio, a janela em contorno e a
# estante. Nos quadros de 1,45 e 1,90 as caras sÃ£o grandes e legÃ­veis.
#
# 1,20 e nÃ£o mais: com o par a 606px, 1,20 leva a largura ocupada a ~727px
# de 1080 e ainda sobra a margem lateral que `montar_frame` exige. E nÃ£o
# menos, porque o contraste com o close (1,90) Ã© o que faz a troca de plano
# ler como CORTE -- que Ã© a razÃ£o de o degrau aberto existir.
#
# Ele continua sendo um TETO, nunca um piso forÃ§ado: quando a largura medida
# do par nÃ£o comporta 1,20, vale o que ela comporta.
PISO_PAR_ABERTO = 1.20


def _medir_corpo(pers, img, bb):
    """Quanto o CORPO deste personagem ocupa Ã  esquerda e Ã  direita do
    quadril, em pixels de tela. Guardado no prÃ³prio Personagem.

    POR QUE MEDIR, E POR QUE UMA VEZ SÃ“
        As posiÃ§Ãµes padrÃ£o (0,27 e 0,73 de 1080) deixam 488px entre os dois
        quadris, e esse nÃºmero foi escolhido no olho. Medido: o Pal ocupa
        279px para cada lado em REPOUSO -- os dois jÃ¡ se tocavam parados,
        antes de qualquer aÃ§Ã£o. Supor a largura Ã© o mesmo erro que supor a
        linha do chÃ£o (Â§4.42) e o pivÃ´: mede-se.

        Uma vez sÃ³ porque o corpo quase nÃ£o muda de largura -- Ã© o braÃ§o
        que abre, e braÃ§o que passa na frente do outro Ã© linguagem normal
        de cut-out. O que nÃ£o se aceita Ã© dois troncos no mesmo lugar.
    """
    pers.meia_esq = pers.meia_dir = 130.0
    if not bb:
        return
    alt = max(bb[3] - bb[1], 1)
    col = (np.asarray(img)[..., 3] > 32).sum(axis=0)
    cheias = np.nonzero(col >= alt * LIMIAR_CORPO)[0]
    if not len(cheias):
        cheias = np.nonzero(col)[0]
    if not len(cheias):
        return
    # a passada abre as pernas; a folga cobre o que a medida em repouso nÃ£o vÃª
    pers.meia_esq = max(W / 2.0 - float(cheias[0]), 60.0)
    pers.meia_dir = max(float(cheias[-1]) - W / 2.0, 60.0)


def _afastar_o_bastante(elenco, pedidos=None):
    """Abre as posiÃ§Ãµes padrÃ£o atÃ© os corpos caberem lado a lado.

    SÃ³ mexe em quem NÃƒO teve `x` pedido no spec: posiÃ§Ã£o escrita Ã  mÃ£o Ã©
    decisÃ£o de quem escreveu, e a guarda por frame (`_separar`) continua
    valendo para ela de qualquer jeito."""
    if len(elenco) != 2:
        return elenco
    chaves = sorted(elenco, key=lambda c: elenco[c][1])
    a, b = chaves
    (pa, xa, dya), (pb, xb, dyb) = elenco[a], elenco[b]
    minimo = pa.meia_dir + pb.meia_esq + FOLGA_ENTRE_ATORES
    if xb - xa >= minimo:
        return elenco
    meio = (xa + xb) / 2.0
    nxa, nxb = meio - minimo / 2.0, meio + minimo / 2.0
    # dentro do quadro: o corpo inteiro tem que aparecer
    nxa = max(nxa, pa.meia_esq + 8.0)
    nxb = min(nxb, W - pb.meia_dir - 8.0)
    if (pedidos or {}).get(a):
        nxa = xa
    if (pedidos or {}).get(b):
        nxb = xb
    print(f"[elenco] corpos de {minimo:.0f}px: {a} e {b} de "
          f"({xa:.0f}, {xb:.0f}) para ({nxa:.0f}, {nxb:.0f})")
    elenco[a] = (pa, nxa, dya)
    elenco[b] = (pb, nxb, dyb)
    return elenco


def colunas_de_corpo(img, bb=None):
    """As colunas de tela em que esta figura tem CORPO.

    NÃ£o silhueta: uma coluna atravessada sÃ³ pelo braÃ§o tem a espessura do
    braÃ§o preenchida, e braÃ§o passando na frente do outro personagem Ã©
    linguagem normal de cut-out. Tronco dentro de tronco nÃ£o Ã©."""
    bb = bb or img.getbbox()
    if not bb:
        return np.zeros(W, dtype=bool)
    alt = max(bb[3] - bb[1], 1)
    return (np.asarray(img)[..., 3] > 32).sum(axis=0) >= alt * LIMIAR_CORPO


def caixa_do_nucleo(img, bb=None):
    """A caixa do NÃšCLEO da figura: tronco, cabeÃ§a e pernas, sem os braÃ§os.

    POR QUE (31/08, defeito 4 dos vÃ­deos: *"quando enquadra um Ãºnico
    personagem e ele acena, quebra completamente o enquadramento, e fica
    dando alguns tilts conforme o personagem se mexe"*)
        As duas guardas de janela de `montar_frame` -- a que nÃ£o deixa o
        gesto sair pela lateral e a que nÃ£o deixa a cabeÃ§a ser cortada em
        cima -- miravam o `getbbox()` da camada, isto Ã©, a SILHUETA. Num
        aceno a silhueta muda a cada frame: a mÃ£o sobe 200px acima da
        cabeÃ§a e volta duas vezes por segundo, e a janela subia e descia
        junto. Na tela Ã© o quadro inteiro balanÃ§ando enquanto a personagem
        acena -- e, no frame em que a mÃ£o estÃ¡ no alto, a cara vai parar no
        meio da tela.

        A guarda de ZOOM jÃ¡ tinha aprendido isto na volta 11 (lei 33: uma
        coluna atravessada sÃ³ pelo braÃ§o nÃ£o Ã© corpo). O que faltava era
        levar a mesma distinÃ§Ã£o Ã s guardas de POSIÃ‡ÃƒO da janela. Com o
        nÃºcleo, a referÃªncia Ã© a cabeÃ§a e o tronco -- que oscilam menos de
        um grau -- e a cÃ¢mera para de respirar junto com o braÃ§o.

    O que se perde Ã© a garantia de que a mÃ£o erguida cabe no quadro. Ã‰ de
    propÃ³sito: close Ã© enquadramento que corta, e o que nÃ£o pode ser
    cortado Ã© a cara. O que a mÃ£o estÃ¡ SEGURANDO continua protegido, por
    fora desta funÃ§Ã£o (`caixa_extra` em `montar_frame`).
    """
    bb = bb or img.getbbox()
    if not bb:
        return None
    cols = colunas_de_corpo(img, bb)
    xs = np.nonzero(cols)[0]
    if not len(xs):
        return bb
    linhas = np.nonzero((np.asarray(img)[..., 3] > 32)[:, cols].any(axis=1))[0]
    if not len(linhas):
        return bb
    return (int(xs[0]), int(linhas[0]), int(xs[-1]) + 1, int(linhas[-1]) + 1)


def _unir(a, b):
    """A caixa que contÃ©m as duas. `None` de um lado devolve o outro."""
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _transladar(img, dx):
    """Move a camada em x. Um deslocamento do quadril translada o desenho
    inteiro rigidamente -- toda peÃ§a sai da posiÃ§Ã£o do quadril por somas --,
    entÃ£o mover a imagem pronta dÃ¡ exatamente o mesmo resultado que
    redesenhar, e custa uma cÃ³pia em vez de uma Ã¡rvore de peÃ§as."""
    if abs(dx) < 0.5:
        return img
    nova = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    nova.paste(img, (int(round(dx)), 0))
    return nova


def _separar(camadas, ordem, elenco=None):
    """NINGUÃ‰M ATRAVESSA NINGUÃ‰M. Mede os dois corpos jÃ¡ desenhados e
    devolve `{chave: dx}` -- o quanto cada um tem que ceder neste frame.

    POR QUE MEDIR OS PIXELS, E NÃƒO A LARGURA GUARDADA
        A primeira versÃ£o desta guarda era aritmÃ©tica: meia-largura medida
        uma vez em repouso, contas sobre o x do quadril. Ela cobria as
        aÃ§Ãµes em pÃ© e passou em dez das onze da rÃ©gua -- e falhou em
        `cair`, que DEITA o personagem. Deitado, o corpo mede 700px de
        largura em vez de 250, e nenhuma medida tirada em pÃ© sabe disso.

        Largura de corpo nÃ£o Ã© propriedade do personagem, Ã© do frame. Aqui
        ela Ã© lida do frame: custa uma soma por coluna sobre o canal alfa
        (~2ms), contra os ~200ms de desenhar a Ã¡rvore de peÃ§as.

    A ordem esquerda/direita vem da posiÃ§Ã£o BASE e nunca inverte: sem isso,
    alguÃ©m atravessando seria "corrigido" para o outro lado no meio do
    movimento, o que Ã© pior que a colisÃ£o.
    """
    if len(ordem) != 2:
        return None
    a, b = ordem
    ca, cb = colunas_de_corpo(camadas[a]), colunas_de_corpo(camadas[b])
    xa, xb = np.nonzero(ca)[0], np.nonzero(cb)[0]
    if not len(xa) or not len(xb):
        return None                     # alguÃ©m ainda fora do quadro
    falta = (xa[-1] + FOLGA_ENTRE_ATORES) - xb[0]
    if falta <= 0:
        return None
    # cada um cede metade, e nenhum dos dois sai do quadro
    da, db = -falta / 2.0, falta / 2.0
    folga_esq = float(xa[0])                     # o quanto o da esquerda
    folga_dir = float(W - 1 - xb[-1])            # ainda pode recuar
    if -da > folga_esq:
        db += (-da - folga_esq)
        da = -folga_esq
    if db > folga_dir:
        da -= (db - folga_dir)
        db = folga_dir
    return {a: da, b: db}


def _pastas(spec, pasta_partes, chave_spec, padroes):
    """Onde procurar arte que nÃ£o Ã© do personagem (cenÃ¡rio, objeto).

    Ordem: o que o spec mandar, depois as pastas ao lado da pasta de
    peÃ§as. Aceita singular e plural de propÃ³sito -- o bucket guarda em
    `assets/cenario/` e `assets/objeto/`, e o motor sempre procurou por
    `cenarios/` e `objetos/`. A divergÃªncia nunca apareceu porque NADA
    baixava esses arquivos: o cut-out caÃ­a direto na cor chapada e o
    defeito passou por "cenÃ¡rio ainda nÃ£o existe"."""
    fora = [p for p in [spec.get(chave_spec)] if p]
    fora += [os.path.join(pasta_partes, "..", p) for p in padroes]
    return fora


def _achar_arte(pastas, nome, exts=(".png", ".jpg", ".jpeg", ".webp")):
    """Primeiro arquivo que existir, em qualquer das extensÃµes.

    CenÃ¡rio chega como JPG (o bruto do gerador) ou PNG; procurar sÃ³ por
    .png fazia o motor nÃ£o achar justamente o que presta -- a versÃ£o que
    passou pelo rembg volta lavada, porque rembg Ã© segmentador de objeto
    saliente e um cenÃ¡rio nÃ£o tem objeto saliente nenhum."""
    for p in pastas:
        for e in exts:
            caminho = os.path.join(p, nome + e)
            if os.path.exists(caminho):
                return caminho
    return None


def _inventario(pastas, exts=(".png", ".jpg", ".jpeg", ".webp")):
    """Nomes de arte que existem nessas pastas, sem extensÃ£o.

    O motor precisa saber o que TEM antes de decidir o que usar: sem isso
    a Ãºnica resposta possÃ­vel a um cenÃ¡rio faltante Ã© a cor chapada, que
    foi o defeito de 28/08. Arquivo comeÃ§ado por `_` fica de fora -- Ã© a
    convenÃ§Ã£o dos artefatos de conferÃªncia (`_mapa.png`)."""
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
    """O que este ator estÃ¡ segurando NESTE instante.

    O objeto Ã© um ESTADO, nÃ£o um efeito de janela. AtÃ© 26/08 ele sÃ³ existia
    enquanto a aÃ§Ã£o que o citava estava rodando: o personagem pegava o
    celular, a aÃ§Ã£o terminava e o celular sumia da mÃ£o no meio da fala
    seguinte -- e a Ãºnica saÃ­da era repetir `objeto` em toda aÃ§Ã£o do
    roteiro, o que ninguÃ©m faz.

    Agora quem pega, segura: a partir do inÃ­cio de uma aÃ§Ã£o de pegar
    (`acoes.ACOES_PEGAM_OBJETO`) o objeto fica na mÃ£o, atravessa trechos, e
    sÃ³ sai em `largar_objeto`. Uma aÃ§Ã£o de qualquer outro nome que cite
    `objeto` continua valendo -- Ã© como os specs antigos escrevem.
    """
    for a in acoes_do_ator:
        if float(a.get("de", 0.0)) > t:
            continue
        if a.get("nome") in ACOES.ACOES_LARGAM_OBJETO:
            atual = None
            continue
        # ENTREGAR ESVAZIA A MÃƒO NO FIM DA AÃ‡ÃƒO. Ver
        # ACOES_ENTREGAM_OBJETO: durante o gesto a coisa tem que estar na
        # mÃ£o (Ã© o que se estÃ¡ oferecendo); passado o gesto, ela Ã© de quem
        # recebeu. Sem isto o objeto se duplica e os dois seguram uma
        # marmita cada -- o defeito da rodada 6 do ciclo.
        #
        # A MARGEM NÃƒO Ã‰ ENFEITE (rodada 10). O motor anima "em 2s"
        # (`fh = (f // 2) * 2`), entÃ£o num trecho de nÃºmero par de frames o
        # `t` do Ãºltimo frame Ã© (nf-2)/(nf-1) e NUNCA chega a 1,0. Com
        # `t >= ate` e uma entrega de `ate: 1.0`, a condiÃ§Ã£o jamais era
        # verdadeira: a rodada 6 passou porque lÃ¡ a entrega acabava em 0,6,
        # e a de 1,0 duplicou a caixa de papelÃ£o do mesmo jeito de antes.
        if a.get("nome") in ACOES.ACOES_ENTREGAM_OBJETO \
                and t >= float(a.get("ate", 1.0)) - 0.02:
            atual = None
            continue
        nome = a.get("objeto")
        if nome in objetos:
            atual = {"img": objetos[nome], "mao": a.get("mao", "d"),
                     "escala": float(a.get("escala_objeto", 1.0)),
                     "nome": nome}
    return atual


# QUANTOS TRECHOS UMA COISA FICA NA MÃƒO SEM SER USADA (04/09, v035).
#
# A lei 35 -- quem pega, segura -- resolveu o objeto que sumia no meio da
# fala, e ela continua certa. Mas ela nÃ£o tinha fim: no v035 um
# `mostrar_objeto` de MEIO SEGUNDO no trecho 0 deixou o celular na mÃ£o da
# Maya pelos **78 segundos seguintes**, em quinze trechos que nÃ£o falam de
# celular nenhum. O braÃ§o volta ao repouso entre um gesto e outro, e o que
# se vÃª Ã© a queixa de 02/09 e de 04/09 do dono do projeto: *"adesivo colado
# Ã  coxa"*.
#
# `acoes.segurar` (04/09) atacou a POSTURA -- levantou o antebraÃ§o de quem
# tem algo na mÃ£o -- e melhorou a leitura sem tocar na causa: o objeto nÃ£o
# devia estar lÃ¡. NinguÃ©m anda com o celular na mÃ£o por um minuto inteiro
# depois de guardar o assunto.
#
# Dois trechos Ã© a folga que a lei 35 precisa: ela existe para o objeto
# atravessar a fala em que foi pego e a resposta do outro. Passou disso sem
# ninguÃ©m usar nem CITAR a coisa, ela foi guardada -- e o corte de plano
# entre trechos Ã© o lugar onde isso acontece sem ninguÃ©m ver, do mesmo jeito
# que um corte justifica trocar de plano.
TRECHOS_COM_OBJETO_PARADO = int(os.environ.get("TRECHOS_OBJETO", "2"))


def _guardar_objeto_esquecido(na_mao, sem_uso, por_ator, fala, seg):
    """Quem estÃ¡ com uma coisa na mÃ£o e nÃ£o a usa hÃ¡ dois trechos, guarda.

    "Usar" Ã© qualquer aÃ§Ã£o de objeto no trecho, ou a fala CITAR a coisa --
    uma esquete sobre o boleto continua com o boleto na mÃ£o enquanto se fala
    dele, que Ã© o que a lei 35 quer. Ver `TRECHOS_COM_OBJETO_PARADO`.
    """
    dito = ACOES.sem_acento(str(fala or "").lower())
    for chave, coisa in list(na_mao.items()):
        if not coisa:
            sem_uso[chave] = 0
            continue
        nome = str(coisa.get("nome") or "")
        usada = any(a.get("objeto")
                    or a.get("nome") in ACOES.ACOES_PEGAM_OBJETO
                    or a.get("nome") in ACOES.ACOES_LARGAM_OBJETO
                    for a in (por_ator.get(chave) or []))
        # `xicara_de_cafe` cita quem falar em "xicara" ou em "cafe": as
        # palavras de quatro letras ou mais do nome da arte. As de trÃªs
        # ("de", "do") nÃ£o dizem nada.
        if not usada:
            usada = any(p in dito for p in nome.split("_") if len(p) >= 4)
        if usada:
            sem_uso[chave] = 0
            continue
        sem_uso[chave] = sem_uso.get(chave, 0) + 1
        if sem_uso[chave] > TRECHOS_COM_OBJETO_PARADO:
            na_mao[chave] = None
            sem_uso[chave] = 0
            print(f"[objeto] {chave} guarda o {nome} em {seg:.1f}s: "
                  f"{TRECHOS_COM_OBJETO_PARADO} trecho(s) sem usar nem citar "
                  f"-- na mao ele viraria adesivo na coxa")


def _quem_saiu(por_ator):
    """Quem terminou este trecho FORA do quadro.

    QUALQUER `sair_andando` CONTA, e nÃ£o sÃ³ a que vai atÃ© o fim da fala
    (31/08). A regra antiga exigia `ate >= 0,95` porque quem saÃ­a no meio do
    trecho voltava sozinho -- a aÃ§Ã£o deixava de ser aplicada e o corpo
    reaparecia no lugar dele no frame seguinte, que Ã© o teletransporte do
    defeito 5. Agora a saÃ­da FICA (ver `acoes.aplicar`): quem saiu estÃ¡ fora
    atÃ© o trecho acabar, e portanto tem de voltar entrando no seguinte."""
    return {c for c, acoes in por_ator.items()
            if any(a.get("nome") in ACOES.ACOES_DE_SAIDA for a in acoes)}


def _fazer_voltar(por_ator, fora_de_cena):
    """Quem saiu de cena volta ENTRANDO, nÃ£o aparecendo.

    O primeiro vÃ­deo do ciclo mostrou o defeito inteiro em quatro segundos:
    o Pal sai andando no fim de um trecho e, no trecho seguinte, estÃ¡ de
    volta parado no lugar dele. O corte de plano entre trechos justifica
    muita coisa -- mas nÃ£o alguÃ©m que a plateia acabou de ver indo embora.

    A entrada Ã© curta e no comeÃ§o da fala: ele chega falando, que Ã© como
    uma pessoa volta para discutir."""
    for chave in list(fora_de_cena):
        acoes = por_ator.get(chave)
        if acoes is None:
            continue
        if any(a.get("nome") in ACOES.ACOES_DE_ENTRADA for a in acoes):
            continue
        por_ator[chave] = [{
            "nome": "entrar_andando", "de": 0.0, "ate": 0.3,
            "motivo": "voltou a cena; sem isto ele reapareceria no lugar "
                      "de onde a plateia acabou de ve-lo sair"}] + acoes
        print(f"[cena] {chave} tinha saido: volta entrando")


# UM GESTO DELIBERADO A CADA 3,5 SEGUNDOS, no mÃ¡ximo.
#
# Medido no corpus (voltas 061 a 100, 409 trechos, 1.000 aÃ§Ãµes, 1.646 s de
# vÃ­deo): o motor recebia **uma aÃ§Ã£o a cada 1,65 segundo**. Numa conversa,
# uma pessoa faz um gesto nomeÃ¡vel a cada cinco ou dez segundos; a cada
# segundo e meio ela estÃ¡ tendo um piti. Ã‰ a queixa 2 do dono do projeto em
# 03/09 (*"personagem acena excessivamente sem motivo nenhum"*), e o v098 Ã©
# o retrato: `susto â†’ apontar â†’ encolher_ombros` em quatro segundos, e depois
# `apontar_para_si â†’ comemorar â†’ acenar`, as duas Ãºltimas SOBREPOSTAS.
#
# 3,5 s Ã© o comprimento tÃ­pico de um trecho deste canal, entÃ£o na prÃ¡tica a
# regra vira "um gesto por fala" â€” que Ã© o que uma fala comporta.
INTERVALO_GESTO_S = 3.5


def _trocar_gesto_sem_licenca(por_ator, fala, expressao=None):
    """`acenar` sem cumprimento na fala vira `apresentar`.

    POR QUE (04/09, ciclo 25 -- queixa 2 do dono do projeto, a metade que
    sobrou)
        `_ralear_gestos` derrubou o EXCESSO de gesto: de um a cada 1,65 s para
        um a cada 4,7. O que ele nÃ£o sabe fazer Ã© ESCOLHER qual gesto a fala
        pede, e por isso o que restou no corpus foram 75 gestos que a fala nÃ£o
        pede em 242 -- *"movimentaÃ§Ã£o do personagem nÃ£o condiz com roteiro de
        fala"*, palavra por palavra.

        Nos quinze `acenar` do corpus, treze nÃ£o trazem cumprimento nem
        despedida. E o `motivo` escrito ao lado deles diz o que o roteirista
        queria: *"acena tentando explicar"*, *"gesticula empatia"*, *"acena
        frustrada"*, *"confirma a suposiÃ§Ã£o com um gesto"*. Nenhum Ã© um oi ou
        um tchau. Ele nÃ£o estÃ¡ desobedecendo -- estÃ¡ usando `acenar` como
        verbo genÃ©rico de "mexe o braÃ§o com Ãªnfase", porque Ã© o que a lista
        oferece.

        `apresentar` Ã© esse gesto, existe desde 31/08 (*"a palma aberta para o
        lado: 'Ã© isso aÃ­', 'olha sÃ³'"*) e foi usado ZERO vezes em 25 voltas.

    POR QUE NO CÃ“DIGO E NÃƒO NO PROMPT (lei 16, e P5)
        Ensinar a diferenÃ§a entre acenar e apresentar custaria regra nova num
        prompt que jÃ¡ mede 5808 de 6100 tokens, e regra nova vaza para a
        vizinha (lei 53). Aqui Ã© um `if` sobre a fala que jÃ¡ estÃ¡ escrita.

    POR QUE SÃ“ `acenar`
        Ver `acoes.TROCA_SEM_LICENCA`: nos outros gestos que a rÃ©gua marca, a
        leitura dos casos mostra que quem erra Ã© a lista de licenÃ§a, nÃ£o o
        roteiro. Obedecer a uma rÃ©gua que marca o certo Ã© a lei 37 pelo avesso.
    """
    for chave, acoes in (por_ator or {}).items():
        for a in acoes or []:
            nome = a.get("nome")
            if ACOES.tem_licenca(nome, fala, a.get("motivo")):
                continue
            novo = ACOES.TROCA_SEM_LICENCA.get(nome)
            if novo:
                print(f"[gesto] {chave}: '{nome}' -> '{novo}' -- a fala nao "
                      f"tem cumprimento nem despedida "
                      f"(motivo escrito: {str(a.get('motivo'))[:40]})")
                a["nome"] = novo
                continue
            # O GESTO SEM LICENCA PASSA A DIZER O QUE A CARA DIZ (05/09).
            # Ver `acoes.GESTO_DA_EMOCAO`: medido no corpus, 192 dos 205
            # gestos marcados sao decorativos de verdade -- nao ha alvo em
            # "sistema bloqueou tudo" nem reflexao em "a tela travou". Em vez
            # de deixar o enfeite ou apagar o movimento, ele vira o gesto da
            # EMOCAO do trecho, que o roteiro ja declarou e que a expressao
            # facial ja esta mostrando.
            emo = ACOES.gesto_para(expressao, nome)
            if emo:
                print(f"[gesto] {chave}: '{nome}' -> '{emo}' -- a fala nao "
                      f"pede este gesto; usando o da emocao '{expressao}'")
                a["nome"] = emo


def _ralear_gestos(por_ator, dur_s, gancho=False):
    """Tira do trecho os gestos DECORATIVOS que passam da conta.

    POR QUE ISTO Ã‰ CÃ“DIGO E NÃƒO PROMPT (lei 16)
        O nÃºmero de aÃ§Ãµes por trecho Ã© pedido no prompt (`acoes_min`, nas
        formas: 3 na `dupla_agitada`, 3 no `monologo_fisico`, 2 no
        `monologo_seco`). Esse mÃ­nimo nasceu em 28/08 para consertar *"os dois
        ficam quase parados"* â€” e Ã© a lei 53 outra vez: a regra que consertou
        a imobilidade produziu o piti. Baixar o `acoes_min` Ã© necessÃ¡rio e nÃ£o
        Ã© suficiente, porque mÃ­nimo Ã© pedido e o modelo entrega o que quiser.

    O QUE SE PRESERVA, E POR QUÃŠ
        SÃ³ se rareia o que Ã© DECORATIVO. AÃ§Ã£o que muda o ESTADO da cena nÃ£o
        pode sumir, senÃ£o o vÃ­deo quebra em vez de melhorar:

          Â· entrada e saÃ­da       -- quem entra tem de entrar;
          Â· objeto                -- pegar, mostrar, usar, largar, entregar
                                     movem o objeto de mÃ£o em mÃ£o;
          Â· interaÃ§Ã£o             -- high five, cutucar, empurrar precisam do
                                     outro e sÃ£o a cena acontecendo;
          Â· `andar`               -- Ã© o que move o personagem no mundo, e o
                                     travelling do cenÃ¡rio sai dele.

        O que sobra -- apontar, acenar, cocar_cabeca, maos_na_cintura,
        encolher_ombros, susto, negar, comemorar -- Ã© ilustraÃ§Ã£o da fala, e Ã©
        aÃ­ que estÃ¡ o excesso: `apontar` sozinho aparece 129 vezes em vinte
        voltas, trÃªs vezes mais que a segunda colocada.

    A ESCOLHA DE QUEM FICA Ã© a PRIMEIRA de cada janela, e nÃ£o a "melhor":
        escolher a melhor exigiria saber qual gesto a fala pede, que Ã©
        exatamente o que ninguÃ©m sabe medir hoje. A primeira Ã© a que o
        roteirista pÃ´s mais cedo, e ela costuma ser a que responde ao comeÃ§o
        da fala. Sem informaÃ§Ã£o para ranquear, a regra simples Ã© a honesta.

    E o que continua animando o corpo o tempo todo Ã© `gesticular` (de quem
    fala) e `escutar` (de quem ouve) -- movimento contÃ­nuo e pequeno, que Ã© o
    que o dono do projeto sempre pediu, em vez de um gesto grande por segundo.
    """
    # O GANCHO GANHA UM GESTO A MAIS (03/09, item 3 do dono do projeto:
    # *"nada me prende o comeÃ§o do vÃ­deo"*).
    #
    # O teto foi posto para acabar com o piti de um gesto a cada 1,65 s, e
    # acabou -- sÃ³ que ele valia igual no trecho 0, e a folha do gancho do
    # v005 mostra o custo: trÃªs segundos de personagem parado, mexendo sÃ³ a
    # boca, no Ãºnico trecho em que movimento Ã© o que segura a rolagem.
    #
    # A regra vale para o vÃ­deo e nÃ£o vale para a abertura, pelo mesmo motivo
    # que `gancho_forte` existe: os primeiros segundos sÃ£o um lugar diferente
    # do resto do vÃ­deo, e o que os governa Ã© retenÃ§Ã£o, nÃ£o naturalidade. UM a
    # mais, e nÃ£o "sem teto" -- o piti comeÃ§ava em trÃªs.
    cabem = max(1, int(round(max(dur_s, 0.1) / INTERVALO_GESTO_S)))
    if gancho:
        cabem += 1
    for chave, acoes in list(por_ator.items()):
        if not acoes:
            continue
        estruturais, decorativas = [], []
        for a in acoes:
            nome = a.get("nome")
            if (nome in ACOES.ACOES_DE_ENTRADA or nome in ACOES.ACOES_DE_SAIDA
                    or nome in ACOES.ACOES_PEGAM_OBJETO
                    or nome in ACOES.ACOES_LARGAM_OBJETO
                    or nome in ACOES.ACOES_ENTREGAM_OBJETO
                    or nome in ACOES.ACOES_DE_INTERACAO
                    or nome in ("andar", "parado", "gesticular", "escutar")):
                estruturais.append(a)
            else:
                decorativas.append(a)
        if len(decorativas) <= cabem:
            continue
        decorativas.sort(key=lambda a: float(a.get("de", 0.0)))
        ficam = decorativas[:cabem]
        saiu = [a.get("nome") for a in decorativas[cabem:]]
        # a ordem original importa para `acoes.aplicar` (a precedÃªncia Ã©
        # cronolÃ³gica desde 31/08), entÃ£o reordena pelo inÃ­cio
        por_ator[chave] = sorted(estruturais + ficam,
                                 key=lambda a: float(a.get("de", 0.0)))
        print(f"[gesto] {chave}: {len(decorativas)} gestos em {dur_s:.1f}s "
              f"e cabem {cabem}; saiu {', '.join(saiu)}")


def _gancho_ja_em_cena(por_ator, falante):
    """No PRIMEIRO trecho, quem fala nÃ£o entra andando: ele jÃ¡ estÃ¡ em cena.

    POR QUE (03/09, folha e primeiros frames do v096)
        O v096 abre com ~2,5 s de cenÃ¡rio VAZIO -- uma parede em close, sem
        ninguÃ©m, com a voz jÃ¡ dizendo *"O curso de sobrevivÃªncia custa
        duzentos e cinquenta pra mim"* -- e o Pal sÃ³ entra correndo no fim do
        terceiro segundo. Num Short, esses sÃ£o os segundos em que a
        plataforma decide se distribui o vÃ­deo.

        NÃ£o Ã© um bug de um lugar: sÃ£o DUAS correÃ§Ãµes certas se somando.

          Â· 01/09 (R1 do DIAGNOSTICO): *o gancho FECHA*. `_close_no_falante`
            devolve True para `i == 0`, para a cara aparecer grande no
            primeiro segundo em vez dos dois bonecos de corpo inteiro que
            todo vÃ­deo do canal tinha.
          Â· 31/08 (defeito 5): *quem vai entrar estÃ¡ FORA*. A entrada Ã©
            aplicada com u=0 antes da janela, senÃ£o o ator ficava parado no
            destino e saltava para a borda quando a janela abria.

        Juntas: a cÃ¢mera fecha em quem fala, quem fala estÃ¡ fora do quadro
        porque estÃ¡ entrando, e o close aponta para a parede atÃ© ele chegar.
        Cada metade continua certa; o encontro das duas Ã© que nÃ£o pode.

    E A SAÃDA Ã‰ DESFAZER A ENTRADA, NÃƒO O CLOSE
        A entrada existe por um motivo que **nÃ£o existe no trecho 0**: ela
        impede que alguÃ©m que a plateia acabou de ver sair reapareÃ§a parado
        no lugar dele (ver `_fazer_voltar`). No instante zero nÃ£o hÃ¡ "antes"
        -- ninguÃ©m viu ninguÃ©m sair, e portanto nÃ£o hÃ¡ teletransporte a
        evitar. O close, ao contrÃ¡rio, tem motivo de sobra ali, e ele Ã©
        medido: Ã© o gancho.

        Quem NÃƒO fala continua entrando no trecho 0, e Ã© bom que entre: a
        cÃ¢mera estÃ¡ no falante, e alguÃ©m chegando ao lado dele Ã© movimento
        de graÃ§a. O que se proÃ­be Ã© sÃ³ a contradiÃ§Ã£o -- fechar em quem ainda
        nÃ£o estÃ¡ lÃ¡.
    """
    acoes = por_ator.get(falante)
    if not acoes:
        return
    fica = [a for a in acoes if a.get("nome") not in ACOES.ACOES_DE_ENTRADA]
    if len(fica) != len(acoes):
        tirou = [a.get("nome") for a in acoes
                 if a.get("nome") in ACOES.ACOES_DE_ENTRADA]
        por_ator[falante] = fica
        print(f"[cena] {falante} fala no trecho 0 e nao entra andando "
              f"({', '.join(tirou)} descartada): o gancho fecha nele, e a "
              f"camera nao pode fechar em quem esta fora do quadro")


def _quem_recebe(por_ator, na_mao, t, objetos):
    """Entregar Ã© PASSAR: o que sai de uma mÃ£o entra na outra.

    `_objeto_na_mao` jÃ¡ esvazia a mÃ£o de quem entregou. Falta pÃ´r a coisa
    na mÃ£o de quem recebeu, e isso o spec quase nunca escreve -- o
    roteirista diz "toma" e considera o assunto encerrado. Sem esta parte,
    o objeto simplesmente desaparece da cena no meio da esquete, que Ã© pior
    que a duplicaÃ§Ã£o que ela conserta: a Ã¢ncora da piada some.

    SÃ³ age quando o outro ator estÃ¡ de mÃ£os vazias. Se ele jÃ¡ pegou o
    objeto por conta prÃ³pria (uma aÃ§Ã£o de objeto no trecho dele), o spec
    manda."""
    if len(por_ator) != 2:
        return
    for quem, acoes in por_ator.items():
        outro = next(c for c in por_ator if c != quem)
        if na_mao.get(quem) is not None or na_mao.get(outro) is not None:
            continue
        for a in acoes:
            if a.get("nome") not in ACOES.ACOES_ENTREGAM_OBJETO:
                continue
            if t < float(a.get("ate", 1.0)) - 0.02:   # ver a margem acima
                continue
            nome = a.get("objeto")
            if nome in objetos:
                na_mao[outro] = {"img": objetos[nome],
                                 "mao": "e" if a.get("mao", "d") == "d" else "d",
                                 "escala": float(a.get("escala_objeto", 1.0))}


def _um_dono_so(por_ator, na_mao, t):
    """UM OBJETO ESTÃ NUMA MÃƒO SÃ“. Devolve quem perdeu, ou None.

    `entregar_objeto` resolve o caso em que alguÃ©m DÃ. Falta o caso em que
    alguÃ©m TOMA: a Maya faz `pegar_objeto` com a xÃ­cara que o Pal estÃ¡
    segurando, e nada no spec diz que ele largou -- o roteirista escreveu
    "toma da mÃ£o dele" e considerou o assunto encerrado, do mesmo jeito que
    escreve "toma" na entrega. Sem esta regra os dois seguram a mesma
    xÃ­cara, que Ã© o defeito da rodada 11 do ciclo (e o terceiro membro da
    mesma famÃ­lia: ver as leis 39 e 41).

    Quem fica com a coisa Ã© quem tem uma aÃ§Ã£o de objeto ATIVA agora, e a
    mais recente delas ganha. NÃ£o havendo como decidir -- os dois pegando
    no mesmo instante --, ninguÃ©m perde e o motor avisa: inventar um dono
    aqui esconderia um spec ambÃ­guo.
    """
    chaves = list(na_mao)
    if len(chaves) != 2:
        return None
    a, b = chaves
    ia, ib = na_mao.get(a), na_mao.get(b)
    if ia is None or ib is None or id(ia["img"]) != id(ib["img"]):
        return None

    def pegou_quando(c):
        return max([float(x.get("de", 0.0)) for x in (por_ator.get(c) or [])
                    if x.get("nome") in ACOES.ACOES_PEGAM_OBJETO
                    and x.get("objeto") and float(x.get("de", 0.0)) <= t],
                   default=-1.0)

    da, db = pegou_quando(a), pegou_quando(b)
    if da == db:
        return None
    perdeu = a if da < db else b
    na_mao[perdeu] = None
    return perdeu


def _acoes_por_ator(tr, chaves, falante):
    """Distribui as aÃ§Ãµes do trecho entre os atores.

    AÃ§Ã£o sem dono Ã© do FALANTE -- Ã© o caso comum e mantÃ©m o spec curto.
    O outro ator em cena sÃ³ se mexe se o roteirista disser o que ele faz,
    e Ã© isso que se quer: figurante que gesticula sozinho rouba a cena."""
    por = {c: [] for c in chaves}
    for a in tr.get("acoes") or []:
        dono = a.get("ator") or falante
        if dono in por:
            por[dono].append(a)
    return por


def _folha(colhidos, saida, larg=300):
    """Os quadros da amostra numa grade, com o segundo de cada um."""
    if not colhidos:
        return saida
    saida = os.path.splitext(saida)[0] + "_previa.png"
    alt = int(larg * H / W)
    cols = min(5, len(colhidos))
    linhas = (len(colhidos) + cols - 1) // cols
    folha = Image.new("RGB", (cols * larg, linhas * alt), "#141414")
    try:
        fonte = ImageFont.truetype("segoeuib.ttf", max(13, larg // 16))
    except OSError:
        fonte = ImageFont.load_default()
    for i, (s, q) in enumerate(colhidos):
        x, y = (i % cols) * larg, (i // cols) * alt
        folha.paste(q.resize((larg, alt), Image.LANCZOS), (x, y))
        d = ImageDraw.Draw(folha)
        rot = f"{s:.1f}s"
        cx = d.textbbox((0, 0), rot, font=fonte)
        d.rectangle([x + 4, y + 4, x + 12 + cx[2], y + 10 + cx[3]], fill=(0, 0, 0))
        d.text((x + 8, y + 6), rot, font=fonte, fill="#FFD54A")
    folha.save(saida)
    print(f"[previa] {len(colhidos)} quadros -> {saida}")
    return saida


def render(pasta_partes, spec, saida, tmpdir=None, amostra=0):
    """O vÃ­deo inteiro, ou uma AMOSTRA dele.

    `amostra=N` desenha sÃ³ N frames igualmente espaÃ§ados e devolve uma
    folha de contato em vez do MP4. Existe porque o ciclo de melhoria Ã©
    olhar-corrigir-olhar, e um render completo custa ~12 min para uma
    pergunta que 12 quadros respondem: os personagens se atravessam? a
    cÃ¢mera cortou a cabeÃ§a de alguÃ©m? o objeto estÃ¡ na mÃ£o?

    Tudo o que vem antes do desenho continua rodando igual -- a voz, a
    timeline, a trilha, a legenda, o cenÃ¡rio --, entÃ£o os quadros da
    amostra sÃ£o os quadros do vÃ­deo, no mesmo instante. O que se pula Ã©
    desenhar os outros 550."""
    from palito_v5 import sintetizar, envelope, juntar_com_respiro
    tmp = tmpdir or tempfile.mkdtemp()
    fd = os.path.join(tmp, "frames"); os.makedirs(fd, exist_ok=True)

    elenco = _carregar_elenco(spec, pasta_partes)
    padrao_ator = list(elenco)[0]
    # `chaves` e `ordem_x` passaram a ser DO TRECHO (30/08, noite): com o
    # elenco solto, quem estÃ¡ em cena muda ao longo do vÃ­deo. Estes sÃ£o sÃ³
    # os valores de partida, para o primeiro trecho ter um "anterior".
    chaves = list(elenco)[:MAX_EM_CENA]
    # VAZIO, E NÃƒO O ELENCO (31/08): antes do primeiro trecho ninguÃ©m esteve
    # em cena, e dizer o contrÃ¡rio pÃµe no quadro quem ainda vai entrar. Ver
    # `_em_cena`.
    chaves_ant = []
    posto = _posicionar(elenco, chaves)
    ordem_x = sorted(chaves, key=lambda c: posto[c][1])

    # A ALTURA DE VERDADE DO ATOR, medida num frame de repouso. Ela decide
    # dois nÃºmeros: onde os pÃ©s pousam (o chÃ£o desenhado, Â§4.42) e o
    # TAMANHO DOS OBJETOS.
    #
    # AtÃ© 29/08 o objeto era medido contra `ALTURA_ALVO_PX`, uma constante
    # de 1150. SÃ³ que a altura do ator nÃ£o Ã© constante: com dois em cena a
    # escala cai para 0,74 e o corpo mede 852 px. Todo objeto saÃ­a 35%
    # maior do que a fraÃ§Ã£o pedida -- o guarda-chuva de 40% virava 54% da
    # altura do ator, o que Ã© o "objeto enorme atravessando o corpo" da
    # rodada 3 do ciclo. E como as trÃªs rodadas de 28/08 tinham dois em
    # cena, a calibraÃ§Ã£o de `TAMANHO_OBJETO` foi feita inteira com esse
    # erro embutido.
    base_pes, alt_corpo = None, None
    try:
        pers0, x0_, dy0 = elenco[padrao_ator]
        rig0 = merge(REST, {})
        rig0["quadril"] = [x0_, REST["quadril"][1] + dy0]
        bb0 = desenhar_personagem(pers0, rig0).getbbox()
        if bb0:
            base_pes, alt_corpo = bb0[3], bb0[3] - bb0[1]
        print(f"[chao] pes do elenco em y={base_pes}, corpo de {alt_corpo}px")
    except Exception as e:
        print(f"[chao] nao consegui medir os pes ({e}); "
              f"o personagem fica na altura do rig")
    altura_ator = float(alt_corpo or ALTURA_ALVO_PX)

    pastas_objeto = _pastas(spec, pasta_partes, "pasta_objetos", ("objetos", "objeto"))

    # OBJETOS: PNG solto que gruda na mÃ£o de alguÃ©m. Carregados uma vez.
    objetos = {}
    for nome, caminho in (spec.get("objetos") or {}).items():
        if not os.path.isabs(caminho):
            # o spec pode dar o nome da arte ("celular") ou o arquivo
            # ("celular.png"); os dois tÃªm que achar o mesmo PNG
            base = caminho.rsplit(".", 1)[0] if "." in caminho else caminho
            caminho = _achar_arte(pastas_objeto, base) or caminho
        if not os.path.exists(caminho):
            print(f"[objeto] {nome}: nao achei '{caminho}', seguindo sem ele")
            continue
        im = Image.open(caminho).convert("RGBA")
        # NORMALIZA O TAMANHO. O gerador devolve o objeto ocupando a
        # imagem inteira, seja um celular ou um caminhÃ£o, entÃ£o usar a arte
        # como veio pÃµe um celular de dois metros na mÃ£o do personagem --
        # foi o que aconteceu no primeiro teste. O tamanho vira fraÃ§Ã£o da
        # altura do ator, que Ã© a Ãºnica referÃªncia de escala que existe na
        # cena. `escala_objeto` na aÃ§Ã£o ajusta a partir daÃ­.
        # RECORTE PELO ALFA SÃ“LIDO, nÃ£o por `getbbox()` (28/08). O rembg
        # devolve alfa residual baixo -- 1 ou 2 de 255 -- em quase todo o
        # PNG, e `getbbox()` considera isso conteÃºdo: ele devolvia a imagem
        # INTEIRA em todos os dez objetos do catÃ¡logo. Como a escala Ã©
        # medida sobre a caixa devolvida, o objeto de verdade saÃ­a menor do
        # que o pedido, e quanto mais margem a arte tinha, menor ele ficava:
        # no boleto o desenho ocupa 37% da altura do arquivo, entÃ£o ele
        # aparecia com um terÃ§o do tamanho e sumia na mÃ£o.
        _a = np.asarray(im)[..., 3]
        _ys, _xs = np.nonzero(_a > 128)
        if len(_ys):
            im = im.crop((int(_xs.min()), int(_ys.min()),
                          int(_xs.max()) + 1, int(_ys.max()) + 1))
        # O TAMANHO Ã‰ POR OBJETO (ver TAMANHO_OBJETO). Um nÃºmero sÃ³ para
        # todos errava nas duas pontas: 16% fez a xÃ­cara ficar do tamanho do
        # tronco em 27/08, e os 11% que resolveram aquilo fizeram o boleto
        # sumir em 28/08 -- uma folha de papel na mÃ£o ocupa um quarto da
        # altura de uma pessoa, nÃ£o um dÃ©cimo.
        # contra a altura MEDIDA do ator, nÃ£o contra a constante: ver o
        # comentÃ¡rio em `altura_ator`, logo acima
        alvo = altura_ator * TAMANHO_OBJETO.get(nome, TAMANHO_OBJETO_PADRAO)
        # pela MAIOR dimensÃ£o, nÃ£o pela altura: o boleto e o controle sÃ£o
        # desenhados deitados, e medir a altura deles deixava o objeto do
        # tamanho de um cartÃ£o. O que se lÃª como tamanho Ã© o lado maior.
        k = alvo / max(im.width, im.height, 1)
        im = _reamostrar(im, (max(int(im.width * k), 1),
                              max(int(im.height * k), 1)))
        # CONTORNO, depois de redimensionar: a espessura Ã© fraÃ§Ã£o do
        # tamanho FINAL, senÃ£o ela encolhe junto com a arte e some
        # justamente no objeto pequeno, que Ã© o que mais precisa dela.
        objetos[nome] = _destacar_objeto(im)

    # nenhum vÃ­deo abre sem gatilho -- rede de seguranÃ§a no motor
    ACOES.garantir_gancho(spec)

    # VOZ PRIMEIRO: a duraÃ§Ã£o real vira a timeline (igual ao palito_v5)
    faixas, respiros, marcas_por_trecho, total = [], [], [], 0.0
    # a Ãºltima prosÃ³dia de CADA perfil de voz, para a rampa do item 7
    prosodia_ant = {}
    n_trechos = len(spec["trechos"])
    for i, tr in enumerate(spec["trechos"]):
        wav = os.path.join(tmp, f"v{i:02d}.wav")
        perfil = tr.get("perfil_voz") or tr.get("ator") or "narrador"
        cfg = spec.get("vozes", {}).get(perfil, {})
        # A EMOÃ‡ÃƒO DO TRECHO TAMBÃ‰M MUDA A VOZ. AtÃ© 28/08 a cara mudava e a
        # voz nÃ£o: o mesmo rate e o mesmo pitch do comeÃ§o ao fim, quatro
        # falas com a mesma entonaÃ§Ã£o. O rÃ³tulo Ã© um sÃ³ (`expressao`), e
        # daqui saem os dois -- ver expressao.PROSODIA.
        cfg = EXPR.prosodia(tr.get("expressao"), tr.get("intensidade", 1.0), cfg)
        # A VOZ NÃƒO SALTA NO CORTE (03/09, item 7). A emoÃ§Ã£o Ã© escolhida por
        # trecho e mudava a prosÃ³dia de uma vez; `suavizar` limita o passo
        # por trecho, POR PERFIL DE VOZ -- a continuidade Ã© de cada
        # personagem. Ver `expressao.suavizar`.
        cfg = EXPR.suavizar(cfg, prosodia_ant.get(perfil))
        prosodia_ant[perfil] = cfg
        for k in ("rate", "pitch", "volume"):    # o trecho pode cravar
            if tr.get(k):
                cfg[k] = tr[k]
        # as MARCAS de palavra deixam de ser descartadas: sao elas que dao
        # o tempo exato de cada palavra para a legenda (ver legendas.py)
        marcas, dur = sintetizar(tr["fala"], cfg, wav,
                                 spec.get("modo_tts", os.environ.get("MODO_TTS", "real")))
        # pausa depois da fala: a longa Ã© a que separa a montagem da piada
        # da piada (expressao.respiro_sugerido)
        respiro = float(tr.get("respiro_s", EXPR.respiro_sugerido(i, n_trechos)))
        tr["dur"] = dur + respiro
        tr["_inicio_s"] = total          # tempo global em que este trecho comeÃ§a
        tr["_dur_voz"] = dur             # sem o respiro: Ã© o que tem som
        faixas.append(wav); respiros.append(respiro)
        marcas_por_trecho.append(marcas or [])
        total += tr["dur"]
    print(f"[voz] timeline real: {total:.2f}s")
    # O PLACAR DE MOTOR DE VOZ (03/09, item 6). Ver `palito_v5.USOU_MOTOR`:
    # a queda do ElevenLabs para o Edge sempre avisou numa linha perdida do
    # log. Aqui ela vira uma linha que se procura, e um alarme quando TODAS as
    # falas cairam -- que e o caso em que o video inteiro sai com a voz errada.
    try:
        from palito_v5 import placar_de_voz
        placar = placar_de_voz()
        if placar:
            print("[voz] motor: "
                  + ", ".join(f"{k}={v}" for k, v in sorted(placar.items())))
            pedidos_eleven = placar.get("pedido_eleven", 0)
            usou_eleven = placar.get("usou_eleven", 0)
            if pedidos_eleven and not usou_eleven:
                print("[voz] !! TODAS as falas pediram ElevenLabs e NENHUMA "
                      "conseguiu: o video inteiro esta com a voz de reserva. "
                      "Conferir ELEVEN_API_KEY e os voice_id da identidade.")
            elif pedidos_eleven and usou_eleven < pedidos_eleven:
                print(f"[voz] ! {pedidos_eleven - usou_eleven} de "
                      f"{pedidos_eleven} falas cairam para o Edge")
    except Exception as e:                                    # noqa: BLE001
        print(f"[voz] nao consegui ler o placar de motor ({type(e).__name__})")

    # o respiro entra no Ã¡udio como silÃªncio de verdade. Sem isto o
    # -shortest do fim decepava a cauda de cada trecho -- o vÃ­deo saÃ­a
    # 1,35s mais curto do que o log dizia (ver juntar_com_respiro)
    voz = juntar_com_respiro(faixas, respiros, os.path.join(tmp, "voz.wav"), tmp)
    # O LIPSYNC SAI DA VOZ PURA, e Ã© por isso que o envelope Ã© medido AQUI,
    # antes da mixagem: com efeito e trilha dentro, a boca do personagem
    # abriria no baque da queda e no arpejo da marimba.
    env = envelope(voz)

    # EFEITOS E TRILHA (ver sfx.py). O spec pode desligar com
    # "musica": false / "sfx": false; ligados Ã© o padrÃ£o, porque um Short de
    # humor com faixa de voz seca soa como recado de secretÃ¡ria eletrÃ´nica.
    # O PIIII (28/08). O palavrÃ£o jÃ¡ chega cortado na primeira sÃ­laba do
    # n8n ("Caâ€”"); aqui ele some atrÃ¡s do bipe de 1 kHz e a legenda mostra
    # os sÃ­mbolos. As duas coisas saem do MESMO casamento entre texto e
    # marcas de palavra que a legenda usa, senÃ£o o som e o texto
    # divergiriam justamente na fala em que o TTS perdeu uma palavra.
    from legendas import janelas_censuradas
    bipes = []
    for tr, m in zip(spec["trechos"], marcas_por_trecho):
        bipes += janelas_censuradas(tr["fala"], m, tr["_inicio_s"], tr["_dur_voz"])

    audio = voz
    # `bipes` entra na condiÃ§Ã£o porque a censura nÃ£o Ã© opcional: um spec com
    # trilha e efeitos desligados ainda nÃ£o pode deixar o palavrÃ£o passar
    if bipes or spec.get("sfx", True) is not False or spec.get("musica", True):
        eventos = SFX.eventos_do_spec(spec) if spec.get("sfx", True) is not False else []
        # A TRILHA SEGUE A CENA. Os segmentos saem da emoÃ§Ã£o de cada trecho,
        # que sÃ³ existe depois que a voz definiu a timeline -- por isso sÃ£o
        # montados aqui e nÃ£o no n8n.
        musica = spec.get("musica", True)
        if isinstance(musica, dict) and not musica.get("arquivo"):
            musica = dict(musica)
            musica.setdefault("segmentos", SFX.segmentos_do_spec(spec))
            # a trilha Ã© de ESTE vÃ­deo: o gÃªnero vem do roteiro (`genero`) e
            # a semente do fila_id, para que duas esquetes do mesmo gÃªnero
            # nÃ£o saiam com o mesmo arpejo nota por nota
            musica.setdefault("semente", spec.get("fila_id", "sem-fila"))
            # AS FALAS CHEGAM Ã€ TRILHA (03/09, item 3). `sfx.genero_permitido`
            # escolhe a cama pelo ASSUNTO quando o gÃªnero pedido nÃ£o pode
            # entrar -- uma esquete de call center pede a musiquinha de
            # espera, e quem sabe que ela Ã© de call center Ã© o texto.
            musica.setdefault("falas", [t.get("fala") for t in spec["trechos"]])
        audio = SFX.mixar(voz, eventos, os.path.join(tmp, "mix.wav"),
                          musica=musica, dur_s=total, bipes=bipes)

    # LEGENDA: opcional, mas ligada por padrÃ£o. Short se assiste no mudo.
    # O TÃTULO NO ALTO (03/09, item 1 do dono do projeto). Ver
    # `legendas.Titulo`: a premissa entregue por escrito enquanto a primeira
    # fala ainda estÃ¡ saindo, que Ã© a janela em que o feed decide. O spec pode
    # cravar `titulo`; sem ele, sai da primeira fala por cÃ³digo.
    titulo = None
    if spec.get("titulo") is not False:
        from legendas import Titulo, titulo_da_esquete
        txt_titulo = spec.get("titulo")
        if not isinstance(txt_titulo, str) or not txt_titulo.strip():
            txt_titulo = titulo_da_esquete(
                [t.get("fala") for t in spec["trechos"]])
        if txt_titulo:
            titulo = Titulo(W, H, txt_titulo)
            print(f"[titulo] \"{txt_titulo}\" nos primeiros "
                  f"{titulo.ate:.1f}s, em {len(titulo.linhas)} linha(s)")

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

    # (a altura do ator e a linha dos pÃ©s jÃ¡ foram medidas lÃ¡ em cima, no
    # carregamento: o tamanho dos objetos depende delas)

    pastas_cenario = _pastas(spec, pasta_partes, "pasta_cenarios", ("cenarios", "cenario"))
    # O QUE EXISTE DE VERDADE, medido uma vez. Ã‰ contra esta lista que o
    # pedido do roteiro Ã© resolvido: pedir `padaria` chega em `comercio`,
    # pedir um cenÃ¡rio que ninguÃ©m gerou chega no interior mais parecido --
    # e a cor chapada volta a ser o que sempre deveria ter sido, o Ãºltimo
    # recurso quando NÃƒO HÃ arte nenhuma (ver cenarios.py).
    inventario = _inventario(pastas_cenario)
    print(f"[cenario] disponiveis: {', '.join(sorted(inventario)) or '(nenhum)'}")
    cenarios = {}
    # A CARA. Um Rosto por render: ele guarda com que expressÃ£o cada ator
    # terminou o trecho para o seguinte comeÃ§ar dali, em vez de pular de
    # cara entre trechos (ver expressao.Rosto).
    rosto = EXPR.Rosto(spec)
    caras = []
    n = 0
    # o que cada ator tem na mÃ£o; sobrevive de um trecho para o outro
    na_mao = {c: None for c in chaves}
    n_trechos = len(spec["trechos"])
    planos, cortes = [], []
    n_empurrados = {}
    fora_de_cena = set()          # quem saiu andando no trecho anterior
    dupla_avisada = False         # o aviso de objeto duplicado sai uma vez
    largou_avisado = set()        # quem jÃ¡ teve o objeto tomado da mÃ£o
    objeto_parado = {c: 0 for c in chaves}   # trechos sem usar o que tem na mÃ£o
    # OS FRAMES QUE A AMOSTRA QUER, em Ã­ndice global. `total` jÃ¡ Ã© a
    # duraÃ§Ã£o real da voz, entÃ£o dÃ¡ para escolher antes de desenhar.
    quero, colhidos = None, []
    if amostra:
        n_total = max(int(total * FPS), 1)
        # QUADROS IGUALMENTE ESPAÃ‡ADOS MENTEM SOBRE MOVIMENTO CÃCLICO.
        #
        # A passada tem 1,7 ciclos por segundo e a amostra pega um quadro a
        # cada ~1,5 s: os instantes caem quase sempre na mesma fase do
        # ciclo, e a folha mostra o personagem na mesma pose doze vezes. Foi
        # o que fez a rodada 4 do ciclo concluir que "ele nÃ£o anda" -- e
        # medido depois, o pÃ© percorre 129 px por passada, que se vÃª muito
        # bem no vÃ­deo.
        #
        # O passo Ã¡ureo desalinha a amostra de qualquer perÃ­odo: o
        # deslocamento dentro de cada intervalo nunca se repete, entÃ£o duas
        # fases iguais seguidas deixam de ser o caso comum. Continua
        # determinÃ­stico e continua cobrindo o vÃ­deo inteiro em ordem.
        phi = 0.6180339887
        quero = {min(int(n_total * (i + (i * phi) % 1.0) / amostra),
                     n_total - 1)
                 for i in range(amostra)}
    for i_tr, tr in enumerate(spec["trechos"]):
        pedido = tr.get("cenario") or CENARIOS.escolher(tr.get("fala", ""))
        cen, motivo = CENARIOS.resolver(pedido, inventario, tr.get("fala"))
        if cen is None:
            # fundo chapado Ã© o ÃšLTIMO recurso, e agora ele avisa alto. Foi
            # esta cor saindo calada que fez o cenÃ¡rio faltante passar
            # por "cenÃ¡rio ainda nÃ£o existe" durante duas sessÃµes.
            cen = "_chapado"
            if cen not in cenarios:
                print(f"[cenario] SEM ARTE NENHUMA em "
                      f"{[os.path.normpath(p) for p in pastas_cenario]}; cor chapada")
                cenarios[cen] = Cenario(Image.new("RGB", (W, H), "#A5A893"),
                                        chao_rel=CENARIOS.CHAO_PADRAO)
        elif cen not in cenarios:
            cam_path = _achar_arte(pastas_cenario, cen)
            chao_rel = CENARIOS.chao_de(cen)
            print(f"[cenario] {pedido} -> {cen} ({motivo}, chao a "
                  f"{chao_rel * 100:.0f}%): {cam_path}")
            cenarios[cen] = Cenario(Image.open(cam_path), chao_rel=chao_rel,
                                    foco=CENARIOS.foco_de(cen))
        elif motivo != "pedido":
            print(f"[cenario] {pedido} -> {cen} ({motivo})")

        # OS PÃ‰S NO CHÃƒO DESENHADO. AtÃ© 28/08 o personagem ficava na altura
        # fixa do rig (78% do quadro com dois em cena) e a arte tinha o chÃ£o
        # em qualquer lugar entre 80% e 90% -- na sala isso Ã© 192px de
        # diferenÃ§a, e o resultado Ã© o boneco pairando na frente da parede.
        dy_chao = 0.0
        if base_pes:
            dy_chao = cenarios[cen].chao_y - base_pes
            if i_tr == 0 or abs(dy_chao) > 1:
                print(f"[chao] {cen}: chao em y={cenarios[cen].chao_y:.0f}, "
                      f"pes em y={base_pes} -> {dy_chao:+.0f}px")

        # O CORTE DESTE TRECHO: o fundo fica imÃ³vel aqui dentro, e o prÃ³ximo
        # trecho pega outro pedaÃ§o da arte (ver PONTOS_DE_CORTE).
        corte = cenarios[cen].ponto_do_trecho(i_tr)
        cortes.append(f"{corte / max(cenarios[cen].faixa, 1):.2f}")

        # ONDE A CÃ‚MERA CENTRA neste cenÃ¡rio: o meio do corpo, que depende
        # da linha do chÃ£o dele. Sem isto o zoom mira sempre a mesma altura
        # e corta os pÃ©s nos cenÃ¡rios de chÃ£o baixo.
        centro_corpo = None
        if base_pes and alt_corpo:
            centro_corpo = (cenarios[cen].chao_y - alt_corpo * 0.45) / H

        falante = tr.get("ator") if tr.get("ator") in elenco else padrao_ator
        # QUEM ESTÃ EM CENA MUDA DE TRECHO PARA TRECHO (30/08, noite). Dois
        # por vez continua sendo o teto (lei 10); o elenco do VÃDEO nÃ£o tem
        # teto. `posto` dÃ¡ o lugar de cada um dentro DESTE trecho, porque o
        # x de alguÃ©m Ã© a divisÃ£o do quadro com quem estÃ¡ lÃ¡ agora.
        chaves = _em_cena(tr, elenco, falante, chaves_ant)
        posto = _posicionar(elenco, chaves)
        entraram = [c for c in chaves if c not in chaves_ant]
        sairam = [c for c in chaves_ant if c not in chaves]
        if entraram or sairam:
            print(f"[elenco] trecho {i_tr}: "
                  + (f"entra {', '.join(entraram)}  " if entraram else "")
                  + (f"sai {', '.join(sairam)}  " if sairam else "")
                  + f"em cena: {', '.join(chaves)}")
        chaves_ant = list(chaves)
        # A ORDEM ESQUERDAâ†’DIREITA Ã© do TRECHO: Ã© por ela que `_separar`
        # sabe para que lado empurrar quem invadiu, e ela sÃ³ faz sentido
        # entre quem estÃ¡ dividindo o quadro agora.
        ordem_x = sorted(chaves, key=lambda c: posto[c][1])
        # O PLANO DESTE TRECHO: close em quem fala, ou o par no ciclo de
        # sempre. Decidido aqui porque depende de quantos estÃ£o em cena
        # AGORA, e isso muda de trecho para trecho (lei 10).
        fecha = _close_no_falante(i_tr, n_trechos, len(chaves))
        # O PLANO DO PAR SAI DA LARGURA MEDIDA, e sai UMA VEZ por trecho.
        # `meia_esq`/`meia_dir` sÃ£o o nÃºcleo de cada um, medidos na arte no
        # frame de repouso (lei 33), entÃ£o isto Ã© a mesma disciplina da
        # altura do ator (lei 38): o nÃºmero vem do desenho, nÃ£o de uma
        # constante escolhida no olho. Fixo dentro do trecho porque o que
        # produziu o tremor do v018 foi recalcular por frame.
        teto_par = 1.0
        if len(chaves) > 1:
            esq = min(posto[c][1] - posto[c][0].meia_esq for c in chaves)
            dir_ = max(posto[c][1] + posto[c][0].meia_dir for c in chaves)
            largura = max(dir_ - esq, 1.0)
            teto_par = W / (largura + 2.0 * MARGEM_LATERAL_PAR)
            if i_tr == 0:
                print(f"[camera] par ocupa {largura:.0f}px de {W}: "
                      f"plano do par ate {min(TETO_PAR, teto_par):.2f}")
        # quem entrou agora nÃ£o tem estado de objeto: a mÃ£o comeÃ§a vazia
        for c in chaves:
            na_mao.setdefault(c, None)
        por_ator = _acoes_por_ator(tr, chaves, falante)
        # A MÃƒO QUE SEGURA Ã‰ A DE FORA, e quem decide Ã© o motor: o
        # roteirista escreve `mao` sem saber quem estÃ¡ de que lado (ver
        # `acoes.mao_de_fora`). Feito UMA vez por trecho, sobre as aÃ§Ãµes
        # deste trecho, para que o estado do objeto e a pose do braÃ§o leiam
        # o MESMO valor -- se divergirem, o braÃ§o sobe vazio e o objeto
        # fica na mÃ£o caÃ­da.
        if len(chaves) > 1:
            for chave in chaves:
                fora = ACOES.mao_de_fora(posto[chave][1])
                # DE QUE LADO ESTÃ O OUTRO (02/09, item 1). As aÃ§Ãµes de
                # interaÃ§Ã£o -- high five, cutucar, empurrar, bater no outro,
                # apertar a mÃ£o -- precisam saber para onde estender o
                # braÃ§o, e quem sabe isso Ã© o motor: o roteirista nÃ£o tem
                # como saber quem ficou de que lado do quadro, pela mesma
                # razÃ£o que ele nÃ£o escolhe a mÃ£o que segura o objeto.
                #
                # Decidido UMA vez por trecho, junto com a mÃ£o, porque as
                # duas coisas tÃªm de ler o mesmo estado -- se divergirem, o
                # braÃ§o vai para um lado e o objeto para o outro.
                outros = [posto[c][1] for c in chaves if c != chave]
                lado = 1 if (outros and outros[0] > posto[chave][1]) else -1
                for a in por_ator.get(chave) or []:
                    if a.get("nome") in ACOES.ACOES_OBJETO_MAO_DE_FORA:
                        a["mao"] = fora
                    if a.get("nome") in ACOES.ACOES_DE_INTERACAO:
                        a["lado_alvo"] = lado
        # O GANCHO NÃƒO PODE FECHAR EM QUEM ESTÃ FORA (03/09, v096). Vem antes
        # de `_fazer_voltar` porque no trecho 0 nÃ£o hÃ¡ de onde voltar, e
        # depois de `mao_de_fora` para nÃ£o mexer no que jÃ¡ foi decidido.
        # `GANCHO_ENTRA=1` desliga a guarda, e existe sÃ³ para a prÃ©via A/B
        # poder reproduzir o defeito -- Ã© o mesmo recurso de
        # `SEPARA_OBJETO_PX`. Sem um jeito de desligar, a Ãºnica prova
        # possÃ­vel Ã© "depois", e "depois" sozinho nÃ£o prova nada.
        # O EXCESSO DE GESTO SAI AQUI (03/09, queixa 2). Antes de qualquer
        # outra guarda: as que vÃªm depois olham a lista de aÃ§Ãµes, e olhar uma
        # lista que ainda vai encolher Ã© medir o que nÃ£o vai acontecer.
        # E O GESTO QUE A FALA NÃƒO PEDE TROCA DE NOME ANTES DE TUDO: o
        # raleamento escolhe QUEM FICA pela ordem, e escolher entre gestos que
        # ainda vÃ£o ser trocados Ã© decidir sobre o que nÃ£o vai acontecer.
        _trocar_gesto_sem_licenca(por_ator, tr.get("fala"), tr.get("expressao"))
        _ralear_gestos(por_ator, float(tr.get("dur") or 0.0), gancho=(i_tr == 0))
        if i_tr == 0 and os.environ.get("GANCHO_ENTRA") != "1":
            _gancho_ja_em_cena(por_ator, falante)
        # E A REGRA GERAL, PARA OS OUTROS TRECHOS: a cÃ¢mera nÃ£o fecha em quem
        # estÃ¡ entrando. O trecho 0 Ã© o caso caro (Ã© o gancho, e a correÃ§Ã£o
        # ali Ã© desfazer a entrada, que nÃ£o tem motivo no instante zero), mas
        # o close tambÃ©m cai em `i % 5 in (1, 4)` e na virada -- e num desses
        # o mesmo encontro produz o mesmo quadro vazio, no meio do vÃ­deo.
        #
        # Aqui a entrada FICA e o close cede: no meio do vÃ­deo a entrada tem
        # o motivo que no trecho 0 ela nÃ£o tem (a plateia acabou de ver a
        # pessoa sair), e quem chega andando aparece melhor no plano do par,
        # que mostra de onde ele vem. Decidido UMA vez por trecho, e nÃ£o por
        # frame: recalcular plano por frame Ã© o tremor do v018.
        if fecha and any(a.get("nome") in ACOES.ACOES_DE_ENTRADA
                         for a in (por_ator.get(falante) or [])):
            fecha = False
            print(f"[camera] trecho {i_tr}: o close cede o lugar ao plano do "
                  f"par -- {falante} entra andando neste trecho, e fechar "
                  f"nele mostraria cenario vazio ate ele chegar")
        _fazer_voltar(por_ator, [c for c in fora_de_cena if c in chaves])
        fora_de_cena = _quem_saiu(por_ator)
        # O QUE NINGUÃ‰M USA NEM CITA VOLTA PARA O BOLSO. Uma vez por trecho,
        # e antes dos frames: dentro do trecho o objeto Ã© estado contÃ­nuo, e
        # trocÃ¡-lo no meio faria a coisa sumir da mÃ£o durante a fala -- que Ã©
        # justamente o defeito que a lei 35 consertou.
        _guardar_objeto_esquecido(na_mao, objeto_parado, por_ator,
                                  tr.get("fala"), n / float(FPS))
        nf = max(1, int(tr["dur"] * FPS))
        cam = dict(ACOES.CAM_NEUTRA)
        for f in range(nf):
            fh = (f // 2) * 2                       # animar "em 2s"
            t = fh / max(1, nf - 1)
            nivel = env[n] if n < len(env) else 0.0

            # O QUE CADA UM TEM NA MÃƒO, ANTES do desvio da amostra. O
            # objeto Ã© ESTADO: ele passa de mÃ£o num frame e continua lÃ¡ nos
            # seguintes. Calcular isso sÃ³ nos frames desenhados faz a
            # PRÃ‰VIA mentir -- se nenhum quadro da amostra cair no instante
            # em que a entrega se completa, a mÃ£o de quem deu nunca esvazia
            # e a folha mostra os dois segurando a mesma caixa. Foi
            # exatamente o que aconteceu na rodada 10 do ciclo, e a caÃ§a ao
            # bug foi no motor atÃ© o teste isolado mostrar que o motor
            # estava certo. Custa microssegundos por frame pulado.
            for chave in chaves:
                na_mao[chave] = _objeto_na_mao(por_ator[chave], t, objetos,
                                               na_mao.setdefault(chave, None))
            _quem_recebe(por_ator, na_mao, t, objetos)
            # UM OBJETO, UMA MÃƒO. Quem toma da mÃ£o do outro fica com ele
            # (ver `_um_dono_so`); o que nÃ£o dÃ¡ para decidir vira aviso no
            # log, uma vez por render. O aviso Ã© o que faz esta famÃ­lia de
            # bug parar de depender de alguÃ©m olhar a folha de contato no
            # quadro certo -- ela jÃ¡ apareceu de trÃªs jeitos diferentes.
            _perdeu = _um_dono_so(por_ator, na_mao, t)
            if _perdeu and _perdeu not in largou_avisado:
                largou_avisado.add(_perdeu)
                print(f"[objeto] {_perdeu} larga o objeto em "
                      f"{n / float(FPS):.1f}s: o outro tomou da mao dele")
            _seguram = [c for c in chaves if na_mao.get(c) is not None]
            if len(_seguram) > 1 and not dupla_avisada:
                if len({id(na_mao[c]["img"]) for c in _seguram}) < len(_seguram):
                    print(f"[objeto] AVISO: {' e '.join(_seguram)} seguram o "
                          f"MESMO objeto em {n / float(FPS):.1f}s e o spec "
                          f"nao diz de quem ele e'")
                    dupla_avisada = True

            if quero is not None and n not in quero:
                n += 1                              # amostra: pula o desenho
                continue

            camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            por_ator_camada = []
            # ONDE FICOU CADA PEÃ‡A DE QUEM FALA, para o close mirar no
            # ROSTO e nÃ£o no meio do corpo, e para a guarda de
            # enquadramento saber onde estÃ¡ o OBJETO na mÃ£o dele. SÃ³ do
            # falante, e Ã© um `dict.update` por frame desenhado.
            #
            # Era `{} if fecha else None`: o objeto precisa da caixa em todo
            # plano fechado, nÃ£o sÃ³ no close em quem fala -- foi com UM ator
            # sozinho que o celular saiu do quadro no v013.
            pecas_falante = {}
            cam_falante, x_falante = dict(ACOES.CAM_NEUTRA), W / 2
            # PRIMEIRO O RIG DE TODO MUNDO, DEPOIS O DESENHO. A colisÃ£o sÃ³
            # dÃ¡ para resolver com as duas posiÃ§Ãµes na mÃ£o, e resolver
            # depois de desenhar seria desenhar duas vezes.
            rigs, cams = {}, {}
            for chave in chaves:
                pers, x0, dy = posto[chave]
                # A SEMENTE DO GESTO: quem Ã© este ator, e em que trecho.
                # Sem ela os dois gesticulam em sincronia e o mesmo ator
                # repete o compasso trecho apÃ³s trecho -- ver `gesticular`.
                rig, c = _rig_do_trecho(tr, t, corte, por_ator[chave], x0,
                                        falando=(chave == falante),
                                        semente_gesto=(chaves.index(chave)
                                                       * 3.0 + i_tr),
                                        na_mao=na_mao.get(chave))
                # DOIS deslocamentos verticais, e a ordem importa:
                #  `dy`      pÃµe este ator na mesma linha dos outros
                #            (_alinhar_pelos_pes, mede a folha de cada um);
                #  `dy_chao` pÃµe essa linha no CHÃƒO DESENHADO do cenÃ¡rio.
                # Entram DEPOIS das aÃ§Ãµes porque pular e cair mexem no
                # quadril, e as duas correÃ§Ãµes acompanham o pulo.
                rig["quadril"] = [rig["quadril"][0],
                                  rig["quadril"][1] + dy + dy_chao]
                rigs[chave], cams[chave] = rig, c
            # QUEM FALA FICA NA FRENTE. A ordem Ã© estÃ¡vel dentro do trecho
            # (o falante nÃ£o muda no meio de uma fala), entÃ£o nada pisca de
            # profundidade; e o braÃ§o de quem gesticula passa por cima do
            # outro, que Ã© a leitura certa -- Ã© ele que estÃ¡ agindo.
            atras_na_frente = [c for c in chaves if c != falante] + \
                              [c for c in chaves if c == falante]
            so_dele = {}
            for chave in atras_na_frente:
                pers, x0, dy = posto[chave]
                rig = rigs[chave]
                # a cara de QUEM FALA vem do trecho; quem ouve fica na cara
                # de reaÃ§Ã£o que o roteirista der a ele, ou neutro
                cara = rosto.para(tr, t, tr["dur"], chave) if chave == falante \
                    else EXPR.obter(tr.get("expressao_" + chave, "neutro"))
                pisca = EXPR.piscando(n, FPS, semente=chaves.index(chave),
                                      expr_nome=tr.get("expressao", "neutro")
                                      if chave == falante else "neutro")
                # SÃ“ QUEM FALA MEXE A BOCA. Sem isto os dois abrem o
                # maxilar na mesma envoltÃ³ria e ninguÃ©m sabe quem falou.
                so_dele[chave] = desenhar_personagem(
                    pers, rig, nivel if chave == falante else 0.0,
                    pisca, na_mao[chave], cara,
                    saida_pos=pecas_falante if chave == falante else None)
            # CADA UM SE DEFORMA SOZINHO. Espelhar, achatar e o squash da
            # passada sÃ£o do corpo de quem fez a aÃ§Ã£o, nÃ£o do quadro (ver
            # `deformar_ator`). Vem ANTES da guarda de colisÃ£o porque
            # achatar muda a largura do corpo, e Ã© a largura depois de
            # deformado que nÃ£o pode invadir o outro.
            for chave in chaves:
                so_dele[chave] = deformar_ator(so_dele[chave], cams[chave],
                                               rigs[chave]["quadril"][0])
            # A CÃ‚MERA SEGUE QUEM ANDA, E QUEM FICA PARADO FICA PARA TRÃS
            # (30/08, noite).
            #
            # O defeito, descrito pelo dono do projeto ao ver o vÃ­deo: *"um
            # personagem andou e o cenÃ¡rio se mexeu, o outro flutuou com o
            # cenÃ¡rio mudando e ele ficando no mesmo enquadramento"*. Ele
            # estÃ¡ certo, e eram DOIS erros somados:
            #
            #  1. `cam = cam_falante` -- a cÃ¢mera seguia o `fundo_dx` de
            #     quem FALA, nÃ£o de quem ANDA. Se quem andava estava calado,
            #     o fundo nem se mexia; e o pÃ© andava no lugar, que Ã© o
            #     patinar clÃ¡ssico que `andar` existe para evitar;
            #  2. o deslocamento ia sÃ³ para o CENÃRIO. Quem estÃ¡ parado no
            #     mundo Ã© estÃ¡tico em relaÃ§Ã£o ao chÃ£o, entÃ£o numa cÃ¢mera que
            #     acompanha ele tem de correr na tela junto com o fundo. Sem
            #     isso, os dois ficam colados na mesma posiÃ§Ã£o de tela e a
            #     cena inteira escorrega -- a mesma leitura errada da lei 26,
            #     agora com o personagem no lugar do fundo.
            #
            # A conta Ã© uma linha: cada ator anda na TELA o que a CÃ‚MERA
            # andou menos o que ELE andou. Quem anda dÃ¡ zero (a cÃ¢mera o
            # segue, ele fica no lugar). Quem estÃ¡ parado dÃ¡ o pan inteiro, e
            # sai do quadro se o passeio for longo o bastante -- que Ã©
            # exatamente "ficar para trÃ¡s e sumir do enquadramento".
            #
            # Vem DEPOIS de `deformar_ator` e ANTES de `_separar`: a colisÃ£o
            # tem de medir onde os corpos ficaram de verdade, senÃ£o ela
            # separa duas silhuetas que jÃ¡ nÃ£o estÃ£o mais ali.
            pans = {c: float(cams[c].get("pan_camera", 0.0)) for c in chaves}
            dx_camera = max(pans.values(), key=abs) if pans else 0.0
            if dx_camera:
                for chave in chaves:
                    dx_tela = dx_camera - pans[chave]
                    if abs(dx_tela) >= 1.0:
                        so_dele[chave] = _transladar(so_dele[chave], dx_tela)
                        rigs[chave]["quadril"][0] += dx_tela
            # NINGUÃ‰M ATRAVESSA NINGUÃ‰M: medido no frame pronto, corrigido
            # transladando a camada (ver `_separar`)
            ceder = _separar(so_dele, ordem_x)
            if ceder:
                for chave, dx in ceder.items():
                    so_dele[chave] = _transladar(so_dele[chave], dx)
                    rigs[chave]["quadril"][0] += dx
                    n_empurrados[chave] = n_empurrados.get(chave, 0) + 1
            # NO CLOSE, QUEM NÃƒO ESTÃ SENDO ENQUADRADO NÃƒO ENTRA NO QUADRO
            # (31/08, defeito 3 dos vÃ­deos: *"quando tem dois personagens na
            # cena e dÃ¡ zoom em um Ãºnico personagem andando, o outro buga e
            # aparece vindo no fundo"*).
            #
            # O close jÃ¡ mira sÃ³ o falante e a janela jÃ¡ Ã© estreita o
            # bastante para deixar o outro de fora -- PARADO. Quando alguÃ©m
            # ANDA, a cÃ¢mera acompanha quem anda e quem estÃ¡ parado corre na
            # tela junto com o fundo (Ã© o travelling de 30/08, e estÃ¡
            # certo): o parceiro atravessa a janela do close deslizando, do
            # lado a lado, no meio da fala do outro. Na folha do teste ele
            # aparece inteiro ao lado do falante, depois metade, depois
            # nada.
            #
            # Cortar a cÃ¢mera nÃ£o resolve -- ele estÃ¡ mesmo passando por
            # ali. O que resolve Ã© o que o close SIGNIFICA: este plano
            # enquadra UM ator. Quem nÃ£o Ã© o enquadrado fica fora do
            # composto, e volta no plano seguinte, no lugar dele.
            no_quadro = [falante] if (fecha and falante in so_dele) \
                else atras_na_frente
            for chave in atras_na_frente:
                if chave == falante:
                    cam_falante = cams[chave]
                    x_falante = rigs[chave]["quadril"][0]
                if chave not in no_quadro:
                    continue
                por_ator_camada.append(so_dele[chave])
                camada.alpha_composite(so_dele[chave])
            cam = cam_falante
            # O FUNDO SEGUE A CÃ‚MERA, NÃƒO O FALANTE. `cam_falante` traz o
            # `pan_base` do trecho (o ponto de corte do cenÃ¡rio) somado ao
            # deslocamento de quem fala; o passeio tem de vir de quem ANDA.
            # As duas partes se somam aqui, e uma sÃ³ vez.
            cam["fundo_dx"] = (float(cam.get("fundo_dx", 0.0))
                               - float(cam_falante.get("pan_camera", 0.0))
                               + dx_camera)
            # a sombra de contato mira o chÃ£o DESENHADO, que agora Ã© onde os
            # pÃ©s estÃ£o de verdade
            cam["chao_y"] = cenarios[cen].chao_y
            # ENQUADRAMENTO DO TRECHO, por cima do que a aÃ§Ã£o jÃ¡ pediu: a
            # aÃ§Ã£o usa zoom para pontuar um susto, e isso continua valendo
            # -- os dois se multiplicam em vez de um apagar o outro.
            # A MIRA DO CLOSE Ã‰ A CABEÃ‡A DE QUEM FALA, nÃ£o o meio do corpo.
            # O pivÃ´ do crÃ¢nio Ã© a base dele (Ã© por onde ele se prende ao
            # pescoÃ§o), entÃ£o o alto da cabeÃ§a estÃ¡ uma altura de crÃ¢nio
            # acima; a janela pÃµe esse alto a 12% do topo, e o resto dela
            # desce pelo tronco. Sem o crÃ¢nio -- folha sem cabeÃ§a separada
            # -- cai no centro do corpo, que Ã© o comportamento de antes.
            centro_rosto = None
            if fecha and pecas_falante and "cranio" in pecas_falante:
                pers_f = posto[falante][0]
                z_prev = CLOSE_FALANTE * (1.0 + 0.035 * max(0.0, min(1.0, t)))
                topo = (pecas_falante["cranio"][1]
                        - pers_f.altura_cranio() * pers_f.escala)
                hjan = H / z_prev
                centro_rosto = (topo + (0.5 - 0.12) * hjan) / H
            z_tr, zy = _enquadramento(i_tr, n_trechos, len(chaves), t,
                                      centro_corpo, close=fecha,
                                      centro_rosto=centro_rosto,
                                      teto_par=teto_par)
            # A AÃ‡ÃƒO NÃƒO COMANDA MAIS A CÃ‚MERA (03/09, queixa 5 do dono do
            # projeto: *"enquadramento nÃ£o foi resolvido, o personagem acena
            # e o fundo inteiro vai com ele"*).
            #
            # As guardas de janela miram o nÃºcleo desde 31/08 (lei 71) e o
            # centro horizontal sai do QUADRIL, nÃ£o do bbox â€” entÃ£o nem o
            # aceno nem o braÃ§o estendido mexem o enquadramento por esse
            # caminho. SÃ³ que havia um segundo caminho, e ele nunca foi
            # tocado: **as prÃ³prias aÃ§Ãµes declaram `zoom` e `zoom_y`**.
            # `susto` pede `zoom: 1,28` e `zoom_y: 0,34` â€” 28% de avanÃ§o mais
            # um tilt de 16% da altura â€”, e `susto` aparece 20 vezes nas
            # Ãºltimas 20 voltas, quase sempre como gesto decorativo dentro de
            # um trecho de 4 s. `tropecar` pede 1,10. O que se vÃª Ã© o quadro
            # inteiro dando um tranco a cada poucos segundos.
            #
            # O `zoom_y` da aÃ§Ã£o jÃ¡ estava documentado como nÃºmero velho
            # (o comentÃ¡rio abaixo, de 29/08: 0,34 era "o rosto" quando o
            # personagem ficava a 78% do quadro, e hoje ele pode estar a 95%).
            #
            # A regra passa a ser de LINGUAGEM, e Ã© a mesma do gesto: **o
            # plano Ã© do trecho, nÃ£o da aÃ§Ã£o**. Quem decide enquadramento Ã©
            # `_enquadramento` (um plano por trecho, mais o push-in de 3,5%);
            # a aÃ§Ã£o fica com o que Ã© dela â€” a pose, e o `tremor`, que sacode
            # sem mudar para onde a cÃ¢mera aponta.
            #
            # O avanÃ§o da aÃ§Ã£o nÃ£o some: fica limitado a 4%, que Ã© da ordem
            # do push-in e lÃª como Ãªnfase em vez de tranco.
            z_acao = max(0.96, min(1.04, float(cam.get("zoom", 1.0))))
            cam["zoom"] = z_acao * z_tr
            # O PUNCH-IN NO CORTE (04/09, item 6 do dono do projeto: *"faÃ§a
            # rÃ¡pidas alteraÃ§Ãµes na tela -- tipo zooms bruscos -- que quebram
            # o padrÃ£o estÃ¡tico do vÃ­deo e aumentam a retenÃ§Ã£o"*).
            #
            # O ciclo de planos jÃ¡ corta entre trechos, mas o corte Ã© SECO: o
            # plano novo entra no tamanho final e fica. Um punch-in Ã© o
            # contrÃ¡rio -- o quadro entra ~7% mais fechado e assenta em ~0,25
            # s. O olho lÃª isso como impacto, e Ã© o recurso mais barato que
            # existe para quebrar a leitura de "imagem parada com Ã¡udio".
            #
            # NÃƒO EM TODO TRECHO, e a razÃ£o Ã© a mesma da densidade de efeitos:
            # o que acontece sempre deixa de ser interrupÃ§Ã£o e vira ritmo, e
            # ritmo previsÃ­vel Ã© o que se estava tentando quebrar. Um a cada
            # trÃªs, e nunca no trecho 0 -- ali o quadro jÃ¡ entra fechado pelo
            # gancho, e um punch por cima disso lÃª como falha de player.
            #
            # `t` Ã© a fraÃ§Ã£o do trecho, nÃ£o segundo: a janela em fraÃ§Ã£o Ã©
            # PUNCH_S dividido pela duraÃ§Ã£o da fala. Sem esta conta o punch
            # duraria um quarto do trecho -- um segundo inteiro numa fala de
            # quatro --, que Ã© exatamente o zoom lento que ele nÃ£o pode ser.
            if i_tr > 0 and i_tr % 3 == 0:
                jan = PUNCH_S / max(float(tr.get("dur") or 1.0), 0.2)
                if t < jan:
                    u = t / max(jan, 1e-6)
                    cam["zoom"] *= 1.0 + PUNCH_FORCA * (1.0 - u) ** 2
            # O COLD OPEN (04/09, item 4 do dono do projeto: *"colocar um
            # elemento muito aleatÃ³rio, ou uma primeira cena muito aleatÃ³ria no
            # comeÃ§o pode ser suficiente pra manter alguÃ©m assistindo"*).
            #
            # O vÃ­deo abre MAIS FECHADO do que vai ficar e recua em ~0,8 s. O
            # que isso faz de diferente do gancho que jÃ¡ existia: o gancho pÃµe
            # a cara grande e a mantÃ©m; o cold open faz o quadro SE MEXER no
            # primeiro segundo, e movimento de cÃ¢mera na abertura Ã© o que
            # separa "comeÃ§ou um vÃ­deo" de "tem uma imagem parada aÃ­".
            #
            # Ã‰ o degrau que faltava entre o tÃ­tulo (que informa) e a fala
            # (que demora): nos primeiros 0,8 s o espectador ainda nÃ£o ouviu a
            # premissa inteira, e Ã© a imagem que tem de segurÃ¡-lo.
            #
            # 18% e recuo, nunca avanÃ§o: abrir mais ABERTO e fechar seria um
            # zoom-in, que lÃª como lentidÃ£o. Recuar Ã© revelar -- o quadro
            # abre e mostra onde a pessoa estÃ¡.
            if i_tr == 0:
                jan0 = COLD_OPEN_S / max(float(tr.get("dur") or 1.0), 0.2)
                if t < jan0:
                    u = t / max(jan0, 1e-6)
                    cam["zoom"] *= 1.0 + COLD_OPEN_FORCA * (1.0 - u) ** 1.6
            # A MIRA DA AÃ‡ÃƒO Ã‰ RELATIVA AO CORPO, NÃƒO Ã€ TELA (29/08).
            #
            # Uma aÃ§Ã£o pode querer olhar mais para cima -- o `susto` pede
            # `zoom_y: 0.34`, que era "o rosto" quando o personagem ficava
            # a 78% do quadro. Desde que os pÃ©s passaram a pousar no chÃ£o
            # DESENHADO (Â§4.42), ele pode estar a 95%, e 0,34 deixou de ser
            # o rosto para virar o teto: na rodada 3 do ciclo, dois terÃ§os
            # do quadro eram prateleira e os dois apareciam cortados no
            # rodapÃ©.
            #
            # O que a aÃ§Ã£o sabe Ã© o DESVIO que ela quer (0,34 - 0,50 =
            # subir 0,16), nÃ£o a altura absoluta. O desvio se aplica a
            # partir do centro do corpo que `_enquadramento` calculou para
            # este cenÃ¡rio, e o clamp mantÃ©m a janela dentro do quadro.
            # E O DESVIO VERTICAL DA AÃ‡ÃƒO PASSA A SER ZERO (03/09). Ele Ã© o
            # tilt da queixa 5 â€” o Ãºnico jeito de uma aÃ§Ã£o mover para onde a
            # cÃ¢mera aponta â€”, e o comentÃ¡rio acima jÃ¡ dizia que o nÃºmero
            # dela envelheceu. O alvo vertical Ã© sÃ³ o que `_enquadramento`
            # decidiu para este trecho e este cenÃ¡rio.
            meia = 0.5 / max(cam["zoom"], 1e-6)
            cam["zoom_y"] = max(meia, min(1.0 - meia, zy))
            # O MEIO DE QUEM ESTÃ EM CENA, para a cÃ¢mera fechar ali. SÃ³
            # conta quem tem o corpo dentro do quadro: quem estÃ¡ entrando
            # ou saindo puxaria o enquadramento para fora junto com ele.
            dentro = [rigs[c]["quadril"][0] for c in chaves
                      if 0 < rigs[c]["quadril"][0] < W]
            # NO CLOSE A CÃ‚MERA MIRA UM SÃ“, e Ã© a silhueta DELE que limita
            # o quanto ela fecha (ver `montar_frame`): a do par somado
            # travaria o plano em 1,33 e o close nÃ£o aconteceria.
            quadro = montar_frame(camada, cenarios[cen], cam, x_falante,
                                  camadas=por_ator_camada,
                                  centro_x=(x_falante if fecha else
                                            (sum(dentro) / len(dentro)
                                             if dentro else None)),
                                  camada_alvo=(so_dele.get(falante)
                                               if fecha else None),
                                  terco=_terco_do_trecho(i_tr, len(chaves)),
                                  caixa_extra=pecas_falante.get("_objeto"))
            # O TÃTULO ANTES DA LEGENDA: nos primeiros segundos os dois podem
            # coexistir, e o de baixo Ã© o que acompanha a boca.
            if titulo is not None:
                titulo.desenhar(quadro, n / float(FPS))
            if leg is not None:
                # por cima de tudo, e no tempo GLOBAL: o Ã­ndice do frame Ã©
                # contÃ­nuo entre trechos, entÃ£o n/FPS Ã© o relÃ³gio do vÃ­deo
                leg.desenhar(quadro, n / float(FPS))
            # COMPRESSÃƒO 1, NÃƒO A PADRÃƒO 6. Estes PNG existem por segundos:
            # o ffmpeg os lÃª na linha seguinte e a pasta Ã© temporÃ¡ria.
            # Medido num frame 1080x1920: 614 ms com a compressÃ£o padrÃ£o,
            # que era 31% do tempo TOTAL de render -- mais do que montar o
            # quadro inteiro. Comprimir com afinco um arquivo que ninguÃ©m
            # guarda Ã© trabalho puro.
            quadro.save(os.path.join(fd, f"{n:05d}.png"), compress_level=1)
            if quero is not None:
                # a folha guarda o relÃ³gio: defeito achado numa amostra sem
                # o segundo obriga a reabrir o vÃ­deo para saber onde estÃ¡
                colhidos.append((n / float(FPS), quadro))
            n += 1
        for chave in chaves:
            rosto.fechar(chave)
        caras.append(EXPR.normalizar(tr.get("expressao", "neutro"))
                     + "".join("+" + EXPR.normalizar(j.get("nome") or j.get("valor"))
                               for j in (tr.get("expressoes") or [])))
        # O LOG DIZ QUAL PLANO FOI, nÃ£o sÃ³ o nÃºmero: "1.90*" Ã© o close em
        # quem fala, e Ã© o Ãºnico jeito de ler no log que a alternÃ¢ncia
        # aconteceu sem abrir o MP4.
        planos.append(
            f"{_enquadramento(i_tr, n_trechos, len(chaves), 0.0, close=fecha, teto_par=teto_par)[0]:.2f}"
            + ("*" if fecha else ""))
        # O PAN DA CAMINHADA NÃƒO ATRAVESSA O CORTE. Ele acumulava de trecho
        # em trecho, de quando o fundo era um ladrilho infinito; agora cada
        # trecho comeÃ§a no ponto que `PONTOS_DE_CORTE` manda, e um resto de
        # deslocamento vindo de trÃ¡s sÃ³ desalinharia esse ponto.
    print(f"[cutout] {n} frames ({n/FPS:.1f}s)")
    print(f"[cara] {' -> '.join(caras)}")
    print(f"[camera] plano por trecho: {' -> '.join(planos)}")
    print(f"[camera] corte por trecho: {' -> '.join(cortes)} da faixa do cenario")
    if n_empurrados:
        print("[colisao] " + ", ".join(f"{c}: {q} frames" for c, q
                                       in n_empurrados.items())
              + " cedendo espaco para nao atravessar")

    if quero is not None:
        return _folha(colhidos, saida), round(total, 2)

    # O TAMANHO DO ARQUIVO VIROU RESTRIÃ‡ÃƒO (30/08). O Storage do Supabase
    # recusa objeto acima do teto do plano, e o primeiro vÃ­deo de 88 s
    # voltou `413 Payload too large` DEPOIS de 15 minutos de render: o job
    # inteiro perdido no upload, com o MP4 pronto no runner.
    #
    # Enquanto a esquete tinha 17 s isso nunca aparecia. Com 40 a 80 s o
    # arquivo quadruplica, e o CRF 21 -- escolhido sem pensar em tamanho --
    # passa do teto. Arte chapada de traÃ§o comprime muito bem: 23 Ã©
    # visualmente indistinguÃ­vel aqui e corta perto de um terÃ§o. O
    # `maxrate`/`bufsize` cortam o PICO, que Ã© o que estoura a mÃ©dia num
    # vÃ­deo com corte de plano a cada trecho.
    def _encodar(crf, maxrate):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
                        "-i", os.path.join(fd, "%05d.png"), "-i", audio,
                        "-af", spec.get("loudnorm", "loudnorm=I=-9:LRA=8:TP=-1.5"),
                        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                        "-maxrate", maxrate, "-bufsize", "8M",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                        "-shortest", "-movflags", "+faststart", saida], check=True)

    _encodar(23, "4M")
    # REDE DE SEGURANÃ‡A: se ainda passar do teto, reencoda mais apertado em
    # vez de deixar o upload falhar. Perder qualidade Ã© ruim; perder o vÃ­deo
    # inteiro depois de 15 min de render Ã© pior.
    TETO_MB = 45
    mb = os.path.getsize(saida) / (1024 * 1024)
    for crf, mr in ((27, "2.5M"), (31, "1.6M")):
        if mb <= TETO_MB:
            break
        print(f"[video] {mb:.1f} MB passa do teto de {TETO_MB} MB; "
              f"reencodando com crf {crf}")
        _encodar(crf, mr)
        mb = os.path.getsize(saida) / (1024 * 1024)
    print(f"[video] {mb:.1f} MB, {n / float(FPS):.1f}s")
    # DuraÃ§Ã£o devolvida = a do VÃDEO que saiu, nÃ£o a soma planejada. Com o
    # respiro no Ã¡udio as duas praticamente coincidem, mas `int(dur*FPS)`
    # arredonda para baixo em cada trecho, e Ã© a guarda de duraÃ§Ã£o do
    # job.py que consome este nÃºmero -- ela precisa validar o arquivo, nÃ£o
    # a intenÃ§Ã£o.
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


