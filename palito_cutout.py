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

# repouso da cara: o dicionário completo com todo campo em zero, para que
# desenhar_personagem nunca precise checar chave faltando
EXPR_ZERO = EXPR.CATALOGO["neutro"]

W, H, FPS = 1080, 1920, 24

# altura de referencia do personagem no quadro; objetos sao medidos contra ela
ALTURA_ALVO_PX = 1150

# TAMANHO DE CADA OBJETO, em fração da altura do ator
# ---------------------------------------------------------------------
# Era 11% para todos, e 11% é o tamanho de um CELULAR. O vídeo de 28/08 era
# sobre um boleto e o boleto mal se via: uma folha de papel na mão de uma
# pessoa ocupa perto de um quarto da altura dela, não um décimo.
#
# O 11% chapado veio de outro erro na direção oposta -- a xícara saiu do
# tamanho do tronco em 27/08 --, e a correção de então tratou o sintoma
# escolhendo um número pequeno o bastante para nada estourar. O tamanho
# certo é por objeto, e é uma medida que se anota uma vez.
#
# `escala_objeto` na ação continua multiplicando isto, para o roteiro poder
# exagerar de propósito (a chave gigante da esquete da bicicleta).
TAMANHO_OBJETO = {
    "celular":               0.11,
    "chave":                 0.09,
    "xicara_de_cafe":        0.11,
    "carteira":              0.12,
    "controle_remoto":       0.13,
    "boleto":                0.22,   # papel A4 na mão, pelo lado maior
    "marmita":               0.17,
    "sacola_de_compras":     0.26,
    "caixa_de_papelao":      0.30,
    "guarda_chuva_quebrado": 0.40,   # o único que é maior que o tronco
}
TAMANHO_OBJETO_PADRAO = 0.13

# A CÂMERA CORTA, NÃO DESLIZA (28/08, noite)
# ---------------------------------------------------------------------
# A primeira versão da arte panorâmica veio com uma deriva contínua: a
# câmera percorria a faixa devagar ao longo do vídeo inteiro. O dono do
# projeto recusou -- "o cenário está se movimentando andando para o lado
# sem os personagens andarem". Ele está certo, e o motivo é de linguagem:
# num plano fixo, fundo que anda só pode significar uma coisa, que é a
# câmera acompanhando alguém que se move. Com todo mundo parado, o cérebro
# não tem a quem atribuir o movimento e a cena inteira parece escorregar.
#
# A arte comprida continua servindo, por outro caminho: cada TRECHO começa
# num ponto diferente dela, e dentro do trecho o fundo fica IMÓVEL. Isso
# lê como troca de ângulo -- um corte --, que é exatamente o que o formato
# não tinha, e o corte reseta a atenção de quem rola o feed.
#
# As posições não avançam em fila (0,2 → 0,4 → 0,6 seria um travelling
# picotado, com o mesmo defeito de leitura): elas saltam de um lado ao
# outro da faixa, como plano e contraplano.
# DEZESSEIS PONTOS (30/08). Eram oito, escolhidos quando a esquete tinha
# cinco ou seis trechos. Com o formato de 40 a 80 s ela tem de 8 a 16, e a
# partir do nono trecho a câmera voltava para o ponto do primeiro: num
# vídeo de 13 trechos o fundo se repetia cinco vezes. A lista tem agora um
# ponto por trecho possível, e continua saltando de um lado ao outro da
# faixa -- avançar em fila é um travelling picotado (lei 26).
PONTOS_DE_CORTE = (0.50, 0.18, 0.74, 0.34, 0.90, 0.08, 0.62, 0.26,
                   0.82, 0.42, 0.14, 0.70, 0.30, 0.96, 0.56, 0.04)

# quantos personagens cabem no quadro ao mesmo tempo. Dois é o teto do
# formato: no 9:16 o terceiro só entra encolhendo todo mundo até a cara
# sumir, e cara é onde a piada acontece.
MAX_EM_CENA = 2


# =====================================================================
# Composição: girar em torno do pivô e colar no destino
# =====================================================================
# A MESMA PEÇA, NA MESMA ESCALA, TODO FRAME (29/08). `escala` é a escala
# do personagem: 0,74 com dois em cena, e ela não muda durante o render.
# Sem cache, cada uma das ~20 peças era reduzida com LANCZOS a cada frame
# -- 16 mil reduções idênticas num vídeo de 800 frames, e LANCZOS é o
# reamostrador mais caro que existe no Pillow (é o certo aqui: reduzir arte
# de traço com um filtro barato serrilha o contorno).
#
# A chave guarda a imagem ORIGINAL junto: sem isso a chave seria um id()
# de objeto que pode ser coletado e reciclado, e o cache devolveria a peça
# de outra coisa. O teto existe porque `cranio_com_cara` produz uma imagem
# por expressão -- poucas, mas não uma só.
_CACHE_ESCALA = {}
_TETO_CACHE_ESCALA = 400


def _reamostrar(img, tam):
    """Redimensiona escolhendo o filtro pelo SENTIDO da conta (30/08).

    A LINHA BRANCA EM VOLTA DO PERSONAGEM saía daqui. LANCZOS tem lóbulos
    NEGATIVOS: onde um traço preto encosta num fundo claro, ele passa do
    valor do vizinho claro e desenha uma linha mais clara que o próprio
    fundo colada no contorno -- o overshoot clássico de filtro com janela.
    Num quadro inteiro isso vira um fio esbranquiçado contornando cada
    peça do boneco e cada móvel do cenário.

    Por que só apareceu agora: enquanto o plano de câmera era 1,00 não
    havia conta nenhuma -- `montar_frame` devolvia o quadro como ele foi
    desenhado. Desde que `_enquadramento` (27/08) passou a dar um plano
    diferente a cada trecho, quase todo frame do vídeo é uma AMPLIAÇÃO de
    1,05 a 1,30, e o halo passou a existir do primeiro ao último quadro.

    Medido num recorte do Pal ampliado 1,25x, contando pixels mais claros
    que o fundo colados no traço preto: LANCZOS 204, BICUBIC 179,
    BILINEAR 46. Bilinear não tem lóbulo negativo -- ele não consegue
    inventar um valor fora do intervalo dos vizinhos, então o halo que
    sobra é só a mistura honesta do traço com o fundo.

    REDUZINDO, LANCZOS continua sendo o certo: é onde ele preserva o traço
    em vez de serrilhá-lo (arte de contorno reduzida com filtro barato
    pisca entre frames), e ali o overshoot cai dentro do próprio traço,
    onde ninguém vê."""
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
    """Gira `img` em torno de `pivot` e cola de modo que o pivô caia em `destino`.

    É a operação inteira da animação cut-out. Todo o resto é decidir
    quais ângulos passar."""
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

    # A COR DA PELE SAI DO ROSTO, NÃO DA PEÇA INTEIRA (30/08)
    #
    # `pele`, lá em cima, é a cor mais frequente do núcleo -- e o núcleo é a
    # peça do crânio, que traz o que o desenhista pôs nela. Na enfermeira
    # são touca, coque e cabelo dos dois lados: a cor dominante deu
    # [108,84,60], que é o CABELO. Com a pele errada, `tinta` sai invertida
    # -- a face clara inteira vira uma mancha de tinta e as sobrancelhas,
    # castanhas e vizinhas do cabelo, ficam de fora. Resultado: 2/4 feições,
    # olhos que se mexem e sobrancelhas paradas.
    #
    # É a lei 13 aplicada a mais um lugar: nada do rosto pode ser medido em
    # fração da peça. Agora que os olhos existem, a pele se amostra ONDE ELA
    # ESTÁ -- a faixa entre os olhos e logo abaixo deles, que é bochecha e
    # nariz em qualquer cara. Se a cor mudar, `tinta` e os componentes são
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
            print(f"[rosto] a cor dominante da peça era {tuple(int(v) for v in pele)} "
                  f"(cabelo ou touca); a pele medida no rosto e "
                  f"{tuple(int(v) for v in pele_rosto)}")
            pele = pele_rosto
            tinta = nucleo & (np.abs(rgb - pele).sum(axis=2) > 90)
            if tinta.sum() >= 40:
                comps_tinta = _componentes(
                    tinta, area_min=max(20, int(tinta.sum() * 0.005)))

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
    # O TRAÇO É FINO, E FINO É UM TETO (31/08, pedido do dono do projeto ao
    # ver os vídeos: *"boca com traço preto em volta; retorne a boca de
    # antes, só um traço fino"*).
    #
    # A espessura medida é a altura MÉDIA da mancha que o desenhista fez, e
    # num traço encorpado ela dá 9px numa boca de 79 -- 11% da largura. Numa
    # LINHA isso ainda passa; desenhada como contorno de elipse, vira um
    # anel preto que ocupa a boca inteira e o rosto fica com um buraco
    # emoldurado no meio. A medida continua mandando enquanto for fina; o
    # teto é 5,5% da largura da boca (4px numa boca de 79), que é a
    # espessura de traço do resto do desenho.
    esp = max(2, min(esp, int(round(larg * 0.055))))
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

    # QUANDO ELA AINDA É UMA LINHA. Era `alt <= esp*1.2`, isto é, o limiar
    # descia junto com a espessura -- e com o traço fino do teto acima a
    # boca passaria a ABRIR com qualquer sopro de som, o que troca o defeito
    # do anel grosso pelo de uma cara de espanto permanente. O limiar passa
    # a ser também uma fração da abertura MÁXIMA: abaixo de um quarto dela,
    # o que existe é um traço.
    if alt <= max(esp * 1.2, alt_max * 0.25):
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
        # O CONTORNO DA BOCA ABERTA É MAIS FINO QUE O DA FECHADA. Na fechada
        # o traço É a boca; na aberta ele é só a borda do buraco, e o
        # `width` do PIL cresce para DENTRO -- num vão de 24px de altura, um
        # contorno de 4px come um terço dele de cada lado. Metade da
        # espessura desenha a borda sem apagar o buraco.
        d.ellipse(caixa, fill=cor_dentro, outline=cor_traco + (255,),
                  width=max(1, int(round(esp * 0.5))))
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
    # A PELE VEM DO ROSTO JÁ MEDIDO, e não da moda da peça (30/08, noite).
    #
    # Esta função media a cor mais comum do núcleo do crânio e chamava
    # aquilo de pele. Na senhora, a cor mais comum do crânio é o CABELO
    # GRISALHO (180,180,180) -- ele ocupa mais pixels que o rosto. Com o
    # cinza no lugar da pele, `tinta` passou a marcar a pele inteira
    # (|252,204,156 - 180,180,180| = 120 > 90): o rosto todo virou uma
    # mancha só de 11 mil px, a boca foi absorvida por ela, e nenhum
    # candidato sobrou. Resultado na tela: a senhora fala 5 falas de boca
    # parada, e a folha ainda assim passa em `conferir_folha`.
    #
    # `_analisar_rosto` JÁ RESOLVE ISSO -- ele avisa no log ("a cor
    # dominante da peça era (180,180,180) (cabelo ou touca); a pele medida
    # no rosto e (252,204,156)") e guarda a cor certa em `rosto["pele"]`. A
    # medida existia, no lugar certo, e esta função não a lia: refazia a
    # conta ingênua ao lado. É a armadilha 16 na mesma casa -- medir no
    # lugar errado (a peça inteira) o que só faz sentido medido no rosto.
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

    # A FAIXA É RECORTADA ANTES DE ROTULAR, e essa ordem é a correção
    # inteira (30/08, noite).
    #
    # `_componentes` rotula tinta CONECTADA, e num rosto desenhado quase
    # todo o traço escuro se toca: na senhora, o cabelo grisalho emoldura o
    # rosto, encosta no aro dos óculos, o aro encosta nos olhos, e a linha
    # do queixo fecha o caminho até a boca. Medido: UMA componente de
    # 16.758 px, de y=43 a y=229, com a boca dentro dela. Nenhum filtro
    # adiante salva -- eles julgam a caixa da mancha, e a caixa é a cabeça
    # inteira. A boca da senhora existe na arte (51x11 px, exatamente no
    # eixo) e nunca chegou a ser candidata.
    #
    # O Pal escapava por sorte: o cabelo dele não faz ponte com o queixo, e
    # a boca saía como componente própria. Ou seja, o detector dependia de
    # um detalhe do penteado -- e foi por isso que dois personagens de nove
    # entraram em cena sem boca sem ninguém notar.
    #
    # Recortando a faixa primeiro, a ponte é cortada junto: dentro de
    # y ∈ [ymin, ymax] o cabelo vira duas manchas laterais (que o filtro de
    # eixo descarta) e a boca fica sozinha no meio. Medido depois: a boca
    # aparece nos quatro conferidos (senhora 51x11, enfermeira 55x12,
    # pal 38x11, maya 26x6).
    faixa = np.zeros_like(tinta)
    faixa[max(0, int(ymin)):int(ymax) + 1, :] = True
    tinta_faixa = tinta & faixa
    if tinta_faixa.sum() < 20:
        return img, None, None

    cands = []
    # O LIMIAR DE ÁREA TAMBÉM MUDA DE BASE: 1% da tinta da FAIXA, não da
    # peça inteira. Sobre a peça, uma mancha dominante (o cabelo) levava o
    # 1% para acima da área da boca -- limiar proporcional à coisa errada,
    # a mesma família da armadilha 16.
    for c in _componentes(tinta_faixa,
                          area_min=max(20, int(tinta_faixa.sum() * 0.01))):
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


# QUANTO DO VÃO CADA PEÇA FECHA, e por que este número foi medido duas
# vezes (01/09, voltas 57 e 58).
#
# Era 0,5: as duas vizinhas cresciam METADE do vão e ficavam encostadas.
# Encostar basta enquanto a junta não gira; girando, elas se tocam num
# ponto só e num ângulo grande deixam de se tocar -- o antebraço da Vovó
# boiando ao lado do corpo num close do v057.
#
# A primeira correção foi para 1,0 (vão inteiro de cada lado, sobreposição
# de um vão), e ela resolveu a junta -- `junta.py` foi de 2 para 1 na
# senhora e os dez passam. Só que o anel cresce com a COR DO CONTORNO, e
# no v058 ele apareceu: na Maria, de camisa azul lisa e calça clara, o
# ombro, o cotovelo e o JOELHO ganharam uma faixa preta grossa que lê como
# tira, não como traço. Na senhora não se via, porque o tricô é ocupado --
# arte de padrão esconde a emenda, arte de cor chapada denuncia.
#
# 0,75 é o meio-termo MEDIDO, não escolhido: dá sobreposição de meio vão
# (~6px na Maria, ~10 na enfermeira), que é o que sobrevive à rotação, com
# um anel 25% mais fino. O teste é `junta.py` no elenco inteiro: se algum
# personagem voltar a dar 2, este número sobe de novo -- junta aberta é
# defeito, anel grosso é feiúra, e nessa ordem.
FECHO_DO_VAO = 0.75


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
        # PERSONAGEM SEM EXPRESSÃO (30/08): quem tem o rosto coberto -- o
        # astronauta de viseira escura -- não pode ter feições animadas nem
        # boca desenhada. É DADO da arte, gravado em `partes.json`, e não
        # detecção: o motor "acha olhos" no reflexo do vidro e a régua de
        # simetria os aceita, então nenhuma heurística resolve isto sozinha.
        # Ver `ferramentas/rosto_vivo.py`, que mede quantas feições saem.
        self.sem_expressao = bool(cfg.get("sem_expressao", False))
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
            # metade do vão de cada lado: as duas vizinhas crescem uma em
            # direção à outra e a junta fecha. +1 cobre o arredondamento e a
            # borda macia que o resize da escala deixa.
            vao = float(self.vaos.get(nome, 0.0))
            if nome in FECHA_MESMO_SEM_MEDIDA and vao <= 0.5:
                vao = tipico
                print(f"[personagem] '{nome}' sem vao medido; usando o tipico "
                      f"({tipico:.1f}px) para fechar a junta")
            # O VÃO SE FECHA COM SOBRA, NÃO NA CONTA EXATA (01/09, volta 57).
            #
            # Era `vao/2 + 1` de cada lado: as duas vizinhas crescem metade
            # do vão e se ENCOSTAM. Encostar basta enquanto a junta não
            # gira. Ao girar, o que estava encostado passa a se tocar num
            # ponto só, e num ângulo grande deixa de se tocar -- o antebraço
            # da Vovó descola do braço em `maos_na_cabeca` e `comemorar`
            # (`junta.py`, e visível no v057, num close, com a manga de
            # tricô boiando ao lado do corpo).
            #
            # A própria docstring de `_fechar_vao` já dizia como cut-out de
            # verdade resolve: *"as peças se sobrepõem, não se tangenciam"*.
            # O código fazia o contrário. Fechar o vão INTEIRO de cada lado
            # dá uma sobreposição de um vão, que é o que sobrevive à
            # rotação -- e o anel cresce com a COR DO CONTORNO da própria
            # peça, então a emenda continua lendo como linha, não como
            # remendo.
            #
            # É proporcional ao vão MEDIDO, então continua sendo um número
            # que vem do desenho: no Pal (vão de 5 a 6px) a diferença é de
            # 3px para 6; na Vovó (8,6) é de 5 para 9; na enfermeira (13,6)
            # de 8 para 14. Nada calibrado à mão, e vale para folha nova.
            im, pivo = _fechar_vao(im, self.pivos[nome],
                                   int(round(vao * FECHO_DO_VAO)) + 1
                                   if vao > 0.5 else 0)
            # o tamanho ANTES de centralizar: _centralizar infla a peça até
            # um quadrado grande o bastante para qualquer rotação, então
            # `self.img[x].size` não serve de régua. A expressão facial mede
            # tudo em fração da altura do crânio e precisa da altura real.
            self.tam[nome] = im.size
            self.img[nome], self.piv[nome] = _centralizar(im, pivo)
            if nome == "cranio":
                # O DESLOCAMENTO QUE `_centralizar` APLICOU. Ele é
                # `(R - int(px), R - int(py))`, e é o que separa uma
                # coordenada lida no PNG da peça (que é o que uma pessoa vê
                # e clica no painel) de uma coordenada na tela inflada (que
                # é onde o motor trabalha). Guardado aqui porque é o único
                # ponto em que os dois sistemas se encontram; recalculá-lo
                # depois exigiria refazer `_fechar_vao` para achar o pivô.
                self._off_cranio = (self.piv[nome][0] - pivo[0],
                                    self.piv[nome][1] - pivo[1])

        # --- ONDE FICA O ROSTO DENTRO DA PEÇA DO CRÂNIO -----------------
        # Medido UMA vez, pelos olhos, e usado pelas três funções de rosto.
        # Sem isto cada uma inventava a própria régua a partir da caixa da
        # peça -- e a peça do crânio traz cabelo e pescoço em quantidade que
        # é decisão do desenhista. Ver `_analisar_rosto`.
        self.rosto = _analisar_rosto(self.img["cranio"]) if "cranio" in self.img else None
        # ROSTO MARCADO À MÃO (30/08, noite), pelo mesmo motivo que os pivôs
        # já tinham `pivos.json`: nenhuma medida resolve arte ambígua. Óculos
        # de aro grosso, franja sobre a sobrancelha, viseira meio
        # transparente -- nesses casos só quem desenhou sabe onde está o
        # olho. O painel escreve `rosto.json` ao lado da folha, o
        # `preparar_assets.py` o copia para `partes.json` em `rosto_manual`,
        # e ele entra AQUI, por cima do que foi medido.
        #
        # As coordenadas são da PEÇA `cranio.png` como ela está no bucket --
        # que é a imagem que a pessoa vê e clica no painel. `_centralizar`
        # depois infla a peça numa tela quadrada com o pivô no meio, e é
        # esse deslocamento que se soma aqui. Pedir coordenadas da tela
        # inflada seria pedir que alguém calculasse `R - int(px)` de cabeça.
        manual = cfg.get("rosto_manual") or {}
        if manual and self.rosto and "cranio" in self.img:
            ox, oy = self._off_cranio
            def _p(v):
                return (float(v[0]) + ox, float(v[1]) + oy)
            usados = []
            if manual.get("olho_e") and manual.get("olho_d"):
                pe, pd = _p(manual["olho_e"]), _p(manual["olho_d"])
                # esquerda/direita são as do QUADRO, não as do personagem:
                # é assim que o resto do motor as trata.
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
        self.boca = None            # (dx, dy, largura) relativos ao pivô do crânio
        # curva e espessura de REPOUSO, medidas da boca que a arte desenhou
        self.boca_estilo = {"curva": 0.0, "esp": 0.0}
        if self.sem_expressao:
            # PERSONAGEM SEM EXPRESSÃO (30/08). O astronauta tem a viseira
            # escura: não há rosto, e o motor ainda assim "achava olhos"
            # ali -- dois reflexos no vidro que a validação por simetria
            # aceita. Animá-los faria os reflexos deslizarem pelo capacete,
            # e desenhar uma boca poria um traço vermelho no meio do vidro.
            #
            # Com a marca, a cabeça continua girando e inclinando (é ela que
            # dá reação de corpo), e a cara fica como a arte a desenhou. O
            # personagem serve para cena e para fala; o que ele não faz é
            # atuar com o rosto -- e quem escreve o roteiro precisa saber
            # disso, porque neste canal a piada costuma acontecer na cara.
            self.rosto_articulado = False
            self.img.pop("mandibula", None)
            print("[rosto] personagem marcado SEM EXPRESSAO: nem feicoes nem "
                  "boca desenhada; a cabeca ainda gira e inclina")
        elif "mandibula" not in self.img or _e_fiapo(self.img["mandibula"]):
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
        if self.sem_expressao:
            pass                    # nada a recortar: ver o comentário acima
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
                        im = _reamostrar(im, (max(2, int(im.width * sx)),
                                              max(2, int(im.height * sy))))
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
            self._cache_var[chave] = (_reamostrar(img, (nl, na)),
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



def _destacar_objeto(img, esp=None):
    """Põe um contorno escuro em volta do objeto.

    POR QUE (visto no vídeo de 28/08 à noite)
        A esquete era sobre um BOLETO, o boleto ficou a esquete inteira na
        mão do Pal, e não aparece: papel branco com traço fino, sobre um
        cenário claro, some. O objeto é a âncora da piada -- o roteiro é
        cobrado a ter um justamente por isso --, e um objeto invisível é o
        mesmo que não ter objeto nenhum.

        As peças do personagem não têm esse problema porque a bíblia visual
        exige `thick uniform black outline` nelas. O objeto vem de outro
        pedido ao gerador e nem sempre volta com contorno grosso.

    COMO
        Dilatar o alfa e pintar de escuro por baixo do próprio objeto. Não
        é sombra projetada (que precisaria saber de onde vem a luz): é o
        mesmo recurso do desenho animado, a linha que separa a figura do
        fundo. Funciona com qualquer arte e não depende da cor dela.

    A espessura sai da MENOR dimensão e tem teto: pela maior, a carteira --
    que é larga e baixa -- ganhava uma moldura preta de 6px que competia
    com o próprio desenho. O que se quer é a linha que separa do fundo, não
    um quadro em volta.

    A imagem CRESCE `r` de cada lado antes de dilatar. Sem isso o contorno
    é cortado onde o objeto encosta na borda da arte, e o resultado é uma
    linha em três lados -- pior que nenhuma.
    """
    base = img.convert("RGBA")
    r = esp if esp is not None else max(2, min(4, int(round(min(base.size) * 0.02))))
    folgada = Image.new("RGBA", (base.width + 2 * r, base.height + 2 * r),
                        (0, 0, 0, 0))
    folgada.alpha_composite(base, (r, r))
    alfa = np.asarray(folgada)[..., 3]
    if not alfa.any():
        return img
    # dilatação por deslocamento: r é pequeno (2 a 4px), e um max sobre os
    # deslocamentos custa menos que uma convolução
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


def _pivo_de_pega(img):
    """Onde a mão segura o objeto.

    Se a arte trouxer uma marca MAGENTA (o gerador é instruído a pintar um
    ponto magenta no cabo), o pivô é o centro dessa marca.

    SEM MARCA, É O CENTRO (28/08). Era 72% da altura, na ideia de que o
    cabo fica embaixo -- e isso empurrava 72% do objeto para CIMA do ponto
    de pega. Somado ao ponto da palma, que caía além da ponta da mão, o
    celular saía encostado na coxa em vez de dentro da mão: foi a queixa
    de 28/08 ("está muito deslocado para baixo").

    O centro é o único palpite que não erra feio em objeto nenhum, e num
    cut-out o que se lê é a sobreposição do objeto com a mão -- não a
    anatomia da pega. Modelar "segura pelo cabo" exige saber onde está o
    cabo, e a arte não diz: quem quiser precisão põe a marca magenta.
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
    # RAIZ EFETIVA (30/08). A raiz do esqueleto é o abdômen, e existe folha
    # que não o separa: um colete de tricô que desce até o quadril faz peito
    # e abdômen saírem numa peça só, que o segmentador nomeia PEITO. Com a
    # raiz ausente a travessia começava num nó que não existe, ninguém era
    # visitado, e o personagem saía INVISÍVEL -- `getbbox()` devolvia None e
    # nenhuma linha de log dizia por quê.
    #
    # É a mesma lição da árvore efetiva, logo abaixo, aplicada ao começo da
    # cadeia em vez do meio: peça que a arte não separou não pode quebrar o
    # rig. Quem assume o quadril é o primeiro descendente que existe.
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
        # QUEM SOBE ATÉ O FIM DA CADEIA FICA COM A RAIZ EFETIVA (30/08).
        # Sem isto, a perna de uma folha sem abdômen subia para o abdômen
        # (ausente), dele para `None` -- e virava órfã: ninguém a visitava e
        # a senhora saía do peito para cima, cortada na cintura. Subir a
        # cadeia só resolve quando existe alguém acima; na raiz não existe,
        # e é justamente ali que a folha de tronco único quebra.
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
            # ENCAIXE DO OMBRO: a manga sobe, o pivô medido continua sendo o
            # pivô. Sem isto o braço baixo deixa uma falha entre a camisa e a
            # manga -- ver folha_personagem.SUBIR_BRACO_HC. O deslocamento é
            # feito no referencial do TRONCO (girado por `ang[pai]`), senão
            # o personagem inclinado subiria o braço na vertical da tela e a
            # manga sairia do ombro para o lado.
            if f in ENCAIXE_OMBRO and SUBIR_BRACO_HC:
                s = _girar((0.0, -SUBIR_BRACO_HC * hc * e), ang[pai])
                pos[f] = (pos[f][0] + s[0], pos[f][1] + s[1])
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

    # onde cada peça ficou na TELA. Só as ferramentas de conferência
    # pedem (`ombro.py` precisa saber onde estão as juntas para não
    # confundir vão de articulação com o vão entre o braço e o corpo).
    if saida_pos is not None:
        saida_pos.update(pos)

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

        # objeto: a POSIÇÃO sai da mão que o segura -- é o osso da mão que
        # tornou isto possível --, mas o desenho vai por último (ver
        # `_colar_objeto` no fim desta função).
        if objeto and objeto.get("img") is not None and nome == "mao_" + objeto.get("mao", "e"):
            oi = objeto["img"]
            opv = objeto.get("pivo") or _pivo_de_pega(oi)
            oi, opv = _centralizar(oi, opv)
            # A MÃO SEGURA COM A PALMA, NÃO COM O PUNHO. `pos[nome]` é o
            # pivô da mão, que fica na junta com o antebraço -- colar o
            # objeto ali o joga para dentro do corpo, e num objeto grande
            # ele aparece flutuando na frente da barriga.
            #
            # 0,30 do comprimento da mão, não 0,55 (28/08). Com 0,55 o
            # ponto caía ALÉM da ponta dos dedos: em repouso, com o braço
            # baixo, isso põe o objeto abaixo da mão, encostado na coxa. O
            # meio da peça é onde a palma está de verdade, e é ali que o
            # objeto tem que se sobrepor à mão para ler como segurado.
            comp = pers.comp.get(nome, 0.0) * pers.escala
            rad = math.radians(ang[nome])
            palma = (pos[nome][0] + math.cos(rad) * comp * 0.30,
                     pos[nome][1] + math.sin(rad) * comp * 0.30)
            # GUARDADO PARA COLAR NO FIM, e não aqui.
            #
            # POR QUE (01/09, volta 36 do ciclo). `ORDEM_Z` desenha o braço
            # DIREITO antes do esquerdo, e o objeto ia junto do direito --
            # então o braço esquerdo passava por cima dele. No Pal isso
            # nunca apareceu: os braços dele terminam afastados. Na Maya,
            # `usar_objeto` junta as duas mãos à frente do peito e o
            # esquerdo TAPA o objeto -- medido em `ferramentas/objeto.py`
            # com a folha dela: celular 21% de visível, xícara 24%, chave
            # 15%, contra 96% no Pal. Seis dos dez objetos reprovam.
            #
            # A correção não é reajustar a pose (ela foi calibrada por
            # varredura, e uma varredura por personagem é a mesma armadilha
            # de novo -- medir num e aplicar em todos). O que é geral: o que
            # se SEGURA fica na frente. Ninguém segura uma xícara atrás do
            # próprio braço.
            objeto_colar = (oi, opv, palma, ang[nome],
                            float(objeto.get("escala", 1.0)))
            if saida_pos is not None:
                # ONDE O OBJETO FICOU, para a câmera não cortá-lo (31/08).
                # A guarda de enquadramento passou a mirar o NÚCLEO do corpo
                # -- o braço deixou de contar, senão a janela balança junto
                # com o gesto --, e sem esta caixa o que está NA MÃO ERGUIDA
                # sairia do quadro junto com ela: era o defeito do v013, o
                # celular boiando fora da tela. Um raio em volta da palma
                # basta; o objeto é colado centrado nela.
                r = max(oi.size) * float(objeto.get("escala", 1.0)) / 2.0
                saida_pos["_objeto"] = (palma[0] - r, palma[1] - r,
                                        palma[0] + r, palma[1] + r)

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
    """Um cenário COMPRIDO por onde a câmera passeia.

    O QUE MUDOU EM 28/08, E POR QUÊ
        Até aqui a arte era quadrada e o fundo corria em ladrilho
        ESPELHADO: a imagem mais uma cópia invertida ao lado, deslocamento
        módulo 2W, fundo infinito com duas cópias. O espelho não tem
        emenda de PIXEL -- as bordas casam exatamente --, mas tem emenda
        de LEITURA: a mesma janela aparece duas vezes, a porta que estava
        à esquerda reaparece à direita, e o texto na placa sai ao
        contrário. Enquanto a câmera ficava parada quase o vídeo inteiro
        ninguém via; com ela passeando o tempo todo, é a primeira coisa
        que aparece -- foi a queixa de 28/08 ("tentou esticar a imagem
        fazendo uma imagem infinita, os erros ficam evidentes").

        Agora não se inventa cenário nenhum: a arte é PANORÂMICA, escalada
        para cobrir a altura do quadro, e sobra material dos dois lados.
        A câmera anda dentro desse material, e cada pixel aparece uma vez
        só. Quem gera a arte é o workflow `gerar-assets`, que passou a
        pedir cenário deitado (ver `Montar Pedidos`).

    O QUE ACONTECE SE A ARTE FOR ESTREITA
        Nada quebra. Um cenário quadrado de 1024, coberto para 1920 de
        altura, vira uma tira de 1920x1920: ainda sobram 840px de passeio
        real -- menos do que um panorâmico dá, e sem uma emenda sequer.

    NA BORDA, REFLETE
        Deslocamento que passa do fim da arte volta pelo mesmo caminho, em
        vez de dar a volta. Voltar repete um trajeto que a pessoa já viu;
        dar a volta é um salto no meio do movimento, que é justamente o
        que se está tirando daqui.

    A LINHA DO CHÃO vem anotada (`cenarios.CATALOGO[...]["chao"]`), não
    medida: ver o comentário longo em cenarios.py. É ela que diz onde os
    pés do personagem pousam.
    """

    def __init__(self, img, chao_rel=None):
        self.chao_y = H * float(chao_rel if chao_rel is not None
                                else CENARIOS.CHAO_PADRAO)
        base = img.convert("RGB")
        # COBRIR: a arte precisa preencher a altura do quadro e ter pelo
        # menos a largura dele. Esticar deformaria (prédio vira torre); o
        # excesso é o que vira faixa de passeio.
        k = max(W / base.width, H / base.height)
        nl, na = max(int(base.width * k), W), max(int(base.height * k), H)
        base = _reamostrar(base, (nl, na))
        # o chão fica embaixo: cortar pelo centro jogaria a linha do chão
        # para fora do quadro
        self.tira = base.crop((0, na - H, nl, na))
        self.faixa = max(0, self.tira.width - W)      # o quanto dá para andar
        self._borrada = None            # a versão fora de foco, sob demanda

    def ponto_do_trecho(self, i):
        """Onde a câmera fica DURANTE o trecho `i`, em pixels da tira.

        É a base do enquadramento; a caminhada soma por cima dela, e é a
        única coisa que move o fundo dentro de uma fala."""
        if self.faixa <= 0:
            return 0.0
        return self.faixa * PONTOS_DE_CORTE[i % len(PONTOS_DE_CORTE)]

    def _posicao(self, dx):
        """Deslocamento pedido -> coluna da arte, refletindo nas bordas."""
        if self.faixa <= 0:
            return 0
        m = float(dx) % (2 * self.faixa)
        return int(m if m <= self.faixa else 2 * self.faixa - m)

    def quadro(self, dx, borrado=False):
        x = self._posicao(dx)
        if borrado:
            return self._tira_borrada().crop((x, 0, x + W, H))
        return self.tira.crop((x, 0, x + W, H))

    def _tira_borrada(self):
        """A mesma tira, fora de foco. Custa UM borrão por cenário.

        POR QUE (31/08, volta 11 do ciclo de vídeo)
            O v011 é um monólogo no `comercio`, e o cenário é uma parede de
            prateleiras desenhadas em traço, de cima a baixo, sem cor e sem
            área calma. No plano aberto ela passa; no CLOSE a 1,60 ela é
            ampliada junto e vira um emaranhado de linhas pretas atrás da
            cara -- a cara e o fundo têm o mesmo contraste, a mesma
            espessura de traço, e o olho não sabe onde pousar. Num canal em
            que a piada acontece no rosto, isso é o rosto perdendo.

            Não é defeito de UM cenário: é o que acontece com qualquer arte
            de fundo quando a câmera fecha. A resposta é a de sempre em
            animação e em foto -- **profundidade de campo**: quem está longe
            sai de foco, e a separação entre figura e fundo passa a ser
            física, não sorte de composição.

        POR QUE ISTO É BARATO
            O fundo é IMÓVEL dentro do trecho (lei 26), e mesmo com a
            caminhada o que muda é a coluna recortada, não a arte. Então o
            borrão se faz UMA vez por cenário, na tira inteira, e todo
            recorte sai dela. São ~2 borrões por vídeo, não 430.
        """
        if self._borrada is None:
            # 9px numa tira de ~2300 de largura: o bastante para o traço
            # perder a aresta e não tanto que o lugar deixe de ser
            # reconhecível -- o cenário ainda tem de dizer onde a cena é.
            self._borrada = self.tira.filter(ImageFilter.GaussianBlur(9))
        return self._borrada


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
    # SÓ A CAIXA DA ELIPSE, não a tela inteira. O borrão gaussiano custa
    # pelo número de pixels, e uma sombra ocupa ~2% de um quadro 1080x1920:
    # borrar o quadro todo era 98% de trabalho em cima de transparência.
    # Passou a doer quando a sombra virou uma POR ator (29/08) e o custo
    # dobrou -- 1,2s por frame viraram 2s.
    raio = max(2, int(alt * 0.35))
    m = raio * 3 + 4                                   # margem para o borrão
    cx0, cy0 = int(cx - larg / 2 - m), int(chao_y - alt / 2 - m)
    cw, ch = int(larg + 2 * m), int(alt + 2 * m)
    if cw <= 0 or ch <= 0:
        return
    tinta = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ImageDraw.Draw(tinta).ellipse([m, m, m + larg, m + alt],
                                  fill=(30, 26, 22, int(96 * (0.45 + 0.55 * k))))
    tinta = tinta.filter(ImageFilter.GaussianBlur(raio))
    # o pedaço que cai dentro do quadro (a sombra de quem está saindo de
    # cena fica meio para fora)
    rx0, ry0 = max(-cx0, 0), max(-cy0, 0)
    rx1, ry1 = min(cw, W - cx0), min(ch, H - cy0)
    if rx1 <= rx0 or ry1 <= ry0:
        return
    quadro.alpha_composite(tinta.crop((rx0, ry0, rx1, ry1)),
                           (cx0 + rx0, cy0 + ry0))


def deformar_ator(camada, cam, quadril_x=W / 2):
    """Espelhar, achatar e o squash da passada -- as três deformações que
    são do CORPO de um ator, não do quadro.

    POR QUE ELAS SAÍRAM DE `montar_frame` (29/08)
        Lá elas se aplicavam à camada JUNTA, e o `cam` que chegava era o do
        falante. Com dois em cena isso é o movimento de um deformando o
        outro: `virar` (espelhar + achatar até 0,04) achatava a cena
        inteira contra o quadril de quem virou, e o `escala_y` da caminhada
        de um comprimia quem estava parado do lado. Ninguém tinha visto
        porque `virar` nunca havia entrado num spec de dois.
    """
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
        red = _reamostrar(camada, (larg, H))
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
            red = _reamostrar(camada, (W, alt))
            nova = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            nova.alpha_composite(red, (0, int(chao - chao * esc_y)))
            camada = nova
    return camada


_ULTIMO_APERTO = {}


def montar_frame(camada, cenario, cam, quadril_x=W / 2, camadas=None,
                 centro_x=None, camada_alvo=None, terco=0, caixa_extra=None):
    """Junta personagem + cenário aplicando o que a câmera pediu.

    `camadas` são os atores SEPARADOS, e existem por dois motivos. A
    SOMBRA: com dois em cena, a caixa da camada junta vai do braço de um ao
    braço do outro, e a elipse virava uma mancha só ligando os dois pés --
    lê como um tapete escuro, não como contato. Uma sombra por corpo. E as
    DEFORMAÇÕES: quando elas vêm, cada ator já chega deformado pelo que ele
    mesmo fez (`deformar_ator`), e aqui não se mexe mais nelas."""
    if camadas is None:
        camada = deformar_ator(camada, cam, quadril_x)

    z = float(cam.get("zoom", 1.0))
    # O ZOOM NÃO FECHA MAIS DO QUE O CORPO PERMITE (29/08).
    #
    # O teto de plano é 1,30 com um ator em cena, e ele foi escolhido
    # quando o personagem ficava a 78% do quadro e media ~850 px. Com os
    # pés no chão desenhado ele mede 1151 px, e uma ação que estende o
    # braço (`tropecar`, `susto`, `comemorar`) põe a silhueta em ~700 px de
    # largura: a janela de 831 px que o zoom 1,30 recorta não cabe, e o
    # braço sai cortado pela borda -- foi o que a rodada 4 do ciclo
    # mostrou.
    #
    # Aqui o teto vem do CORPO, não da tabela: mede-se a silhueta que
    # existe neste frame e limita-se o zoom ao que a comporta, com uma
    # margem de respiro. Só limita, nunca aumenta -- o plano continua
    # sendo o que `_enquadramento` pediu quando ele cabe.
    #
    # DE QUAL CORPO (31/08, volta 6 do ciclo de vídeo). `camada` é a soma
    # dos atores, e com dois em cena ela vai do braço de um ao braço do
    # outro: 740 dos 1080 px, o que trava qualquer zoom acima de 1,33. Era
    # essa medida -- e não o teto da tabela -- que fazia os dezesseis
    # quadros do v006 saírem no MESMO plano aberto. Num CLOSE em quem fala,
    # o outro sair pela borda é o efeito pretendido (é o "corte para o
    # personagem" do plano de melhorias), então quem limita é a silhueta
    # de QUEM ESTÁ SENDO ENQUADRADO. Sem `camada_alvo`, nada muda.
    enquadrada = camada_alvo if camada_alvo is not None else camada
    # A CAIXA QUE A CÂMERA OBEDECE: o núcleo de quem está sendo enquadrado,
    # mais o que ele estiver segurando. Medida UMA vez por frame e usada
    # pelas três guardas -- zoom, lateral e alto --, que antes cada uma
    # media a sua (ver `caixa_do_nucleo`). Só quando há recorte: sem zoom
    # nenhuma guarda tem o que fazer, e a conta custa uma varredura do alfa
    # da tela inteira.
    nucleo = _unir(caixa_do_nucleo(enquadrada), caixa_extra) \
        if abs(z - 1.0) > 0.002 else None
    bb = None
    if camadas and z > 1.002:
        bb = nucleo
        if bb:
            larg = max(bb[2] - bb[0], 1)
            alt = max(bb[3] - bb[1], 1)
            # O QUE NÃO PODE SER CORTADO É O CORPO, NÃO A PONTA DO DEDO
            # (31/08, volta 11). A largura era a da SILHUETA, e um braço
            # estendido a põe em 800 a 1080 px: `1080/(larg*1,10)` derrubava
            # o plano de 1,60 para **1,23, e às vezes para 1,00**. O v005
            # pediu close em quatro trechos e não teve nenhum -- e a prova
            # daquela volta não pegou porque olhou o plano PEDIDO, que é o
            # que o log imprimia.
            #
            # Pior que o plano perdido: a silhueta muda A CADA FRAME, então
            # a guarda **fazia a câmera respirar junto com o braço** -- 1,30
            # enquanto os braços estão baixos, 1,00 no frame em que a mão
            # sobe, e de volta. Câmera que abre quando alguém gesticula é o
            # contrário do que o gesto pede.
            #
            # Vale aqui a mesma distinção da lei 33: coluna atravessada só
            # pelo braço não é corpo. O núcleo (tronco, cabeça, pernas) quase
            # não muda de largura entre poses, então a guarda para de
            # oscilar; e o gesto pode encostar na borda, que é o que um
            # close faz.
            if camada_alvo is not None:
                # NO CLOSE, CORTAR A PERNA É O PONTO (31/08, volta 7).
                #
                # A regra de cima -- "o corpo INTEIRO tem de caber" -- é a
                # certa para o plano do par, e é o que desfazia o close: o
                # v007 pediu 1,90 e saiu em ~1,45, porque a Maria é mais
                # alta que a média do elenco e `H/(alt*1.04)` reduziu o
                # zoom até o corpo dela caber de cabeça a pé. E o efeito
                # não foi só um plano mais aberto: a janela cresceu de 568
                # para 745 px e o parceiro voltou a aparecer pela borda,
                # que é o defeito que o close existe para acabar.
                #
                # Um close é um enquadramento que CORTA -- ninguém filma
                # close-up mostrando os sapatos. O que não pode ser cortado
                # é a LARGURA (o gesto sai pela lateral, e gesto é o que
                # este canal tem de melhor) e o ALTO (a cabeça, e a mão
                # erguida acima dela). Do quadril para baixo, cortar é a
                # linguagem. A altura entra abaixo, movendo a janela em vez
                # de abrir o plano.
                cabe = W / (larg * 1.06)
            else:
                cabe = min(W / (larg * 1.10), H / (alt * 1.04))
            if cabe < z:
                # A GUARDA DIZ QUANDO APERTA (31/08). Ela desfazia o plano
                # em silêncio: o log imprimia `1.90` e o quadro saía em
                # 1,33, e a diferença entre "o close não foi feito" e "o
                # close foi feito e desfeito" é onde se procura o defeito.
                # Fail-open precisa de um lugar que conte que ele abriu
                # (lei 65) -- vale também para uma guarda de composição.
                marca = (round(z, 2), round(cabe, 2))
                if marca != _ULTIMO_APERTO.get("v"):
                    _ULTIMO_APERTO["v"] = marca
                    print(f"[camera] plano {z:.2f} nao cabe no corpo "
                          f"({larg}x{alt}px); vai a {max(1.0, cabe):.2f}")
                z = max(1.0, cabe)

    # PROFUNDIDADE DE CAMPO: FECHOU, O FUNDO SAI DE FOCO (31/08, volta 11).
    # Decidido pelo zoom EFETIVO -- depois da guarda --, e não pelo plano
    # pedido: fundo nítido num quadro que na verdade não fechou seria borrar
    # por engano. O limiar de 1,35 não é cruzado dentro de um trecho com os
    # números de hoje (o degrau mais alto abaixo dele é 1,30, que com o
    # push-in de 3,5% chega a 1,345), então o foco não pisca no meio de uma
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
        # ONDE A CÂMERA CENTRA NA HORIZONTAL. Era o meio do quadro, sempre,
        # e com dois em cena isso está certo -- eles ficam simétricos em
        # torno dele. Errado é quando UM sai: o que fica está a 0,27 ou a
        # 0,73 do quadro, e fechar no meio deixa metade da tela de parede
        # vazia com o personagem encostado na borda. `centro_x` é o meio
        # de quem está EM CENA, e vem dos quadris, não da silhueta: o bbox
        # muda com cada gesto e faria a câmera tremer junto com os braços.
        cx = W * 0.5 if centro_x is None else float(centro_x)
        # nunca até o fim: enquadrar exatamente no boneco tira o cenário do
        # quadro e o corte deixa de ter lugar nenhum.
        #
        # NO CLOSE A MIRA É QUASE INTEIRA (31/08). Com 0,75, fechar em quem
        # está a x=296 deixa a janela em 73..641 e a BORDA do outro (que
        # começa em 634) entra por sete pixels: um pedaço de ombro colado na
        # lateral, que lê como enquadramento errado e não como corte. Com
        # `camada_alvo` -- que só existe no close -- a mira vai a 0,92 e o
        # outro fica de fora inteiro, continuando a sobrar cenário dos dois
        # lados do falante.
        cx = W * 0.5 + (cx - W * 0.5) * (0.92 if camada_alvo is not None else 0.75)
        # COMPOSIÇÃO EM TERÇOS PARA QUEM ESTÁ SOZINHO (31/08, volta 15).
        #
        # O v015 é um monólogo de nove trechos e a personagem está no MEIO
        # do quadro nos dezesseis quadros da folha. O ciclo de planos varia
        # só a ESCALA, e os três degraus do meio (1,15 / 1,30 / 1,45) são
        # quase indistinguíveis quando a composição é sempre a mesma: o
        # resultado lê como um plano só, que é a queixa do v005 outra vez,
        # agora por outro motivo.
        #
        # Deslocar a janela um sexto põe o corpo no terço da esquerda ou da
        # direita, e o outro terço fica com o cenário -- que desde 28/08 é
        # arte panorâmica com conteúdo até o teto, feita para aparecer. É a
        # variação de enquadramento do plano de melhorias (item 4) sem
        # inventar plano nenhum, e o clamp do bbox logo abaixo continua
        # garantindo que o corpo inteiro caiba.
        cx += float(terco) * lw / 6.0
        # O GESTO NÃO SAI PELA BORDA (31/08). A mira é o QUADRIL, de
        # propósito -- o bbox muda com cada gesto e a câmera tremeria junto
        # com os braços --, mas num close de 568 px de largura um braço
        # estendido chega a 300 px do quadril e some pela lateral. A saída
        # não é seguir o bbox: é **empurrar a janela só o necessário** para
        # ele caber. Enquanto o gesto couber na janela a câmera não se mexe,
        # e quando não couber ela já estava cortando de qualquer jeito.
        # A GUARDA DO ALTO VALE PARA TODO PLANO FECHADO, não só para o close
        # em quem fala (31/08, volta 11). Com um ator sozinho a mira vertical
        # é o meio do corpo, e a 1,59 isso põe a linha de cima da janela 34px
        # ABAIXO do topo da cabeça: o cabelo saía cortado rente ao crânio em
        # todos os closes do v011, e ninguém tinha olhado porque até esta
        # volta o close com um ator não estava acontecendo.
        # E A GUARDA DA LATERAL TAMBÉM VALE PARA TODO PLANO FECHADO (31/08,
        # volta 13). Ela só rodava no close em quem fala, e com UM ator
        # sozinho o resultado apareceu na tira de rostos: braço erguido para
        # o lado, mão FORA do quadro e o celular boiando ao lado da cabeça,
        # sem ninguém segurando. Objeto sem mão é pior que objeto cortado --
        # ele deixa de ser um objeto e vira um adesivo.
        #
        # E AS DUAS MIRAM O NÚCLEO, NÃO A SILHUETA (31/08, defeito 4). Com a
        # silhueta, um aceno subia a borda de cima 200px e a trazia de volta
        # duas vezes por segundo -- a janela ia junto, e o enquadramento
        # "quebrava" a cada gesto. O que elas protegem passa a ser o corpo e
        # o que a mão SEGURA (`caixa_extra`); a mão vazia pode encostar na
        # borda, que é o que um close faz. Ver `caixa_do_nucleo`.
        bba = nucleo
        if bba and (bba[2] - bba[0]) <= lw:
            cx = min(max(cx, bba[2] - lw / 2), bba[0] + lw / 2)
        cy = H * float(cam.get("zoom_y", 0.5))
        # A CABEÇA NUNCA É CORTADA. O close mira a cabeça (`centro_rosto`),
        # mas uma ação que ergue a mão sobe a silhueta acima dela -- e o
        # certo então é DESCER a janela (cortando mais perna, que é o que
        # um close corta), nunca abrir o plano.
        if bba:
            cy = min(cy, bba[1] - 0.03 * lh + lh / 2)
        x0 = min(max(cx - lw / 2, 0), W - lw)
        y0 = min(max(cy - lh / 2, 0), H - lh)
        # ampliação: BILINEAR, senão o zoom desenha um fio branco em volta
        # de cada traço preto do quadro (ver _reamostrar)
        quadro = _reamostrar(
            quadro.crop((int(x0), int(y0), int(x0 + lw), int(y0 + lh))), (W, H))
    return quadro


# O CLOSE EM QUEM FALA (31/08, volta 6 do ciclo de vídeo).
#
# 1,90 é o plano em que UM dos dois enche o quadro: com dois em cena a
# escala cai para 0,74 e o corpo mede ~852 px de altura por ~300 de largura,
# então a janela de 568x1010 que 1,90 recorta o comporta inteiro, com folga
# para o braço erguido, e a CARA passa de ~85 para ~160 px. Acima disso a
# arte começa a aparecer ampliada quatro vezes -- a folha do personagem é
# desenhada uma vez só, e não há de onde tirar mais pixel.
CLOSE_FALANTE = 1.90


def _terco_do_trecho(i, n_atores):
    """Em que terço do quadro o corpo fica neste trecho: -1, 0 ou +1.

    SÓ COM UM ATOR. Com dois, a divisão do quadro já é a composição (um em
    cada lado), e deslocar a janela tiraria um deles; no close em quem fala
    o lado já é escolhido pelo quadril de quem fala.

    Alterna centro → esquerda → centro → direita, período 4: com período 2
    a composição voltaria a ser sempre a mesma alternância, e o centro no
    meio dá o descanso que faz o deslocamento ser percebido como escolha e
    não como tremor.
    """
    if n_atores != 1:
        return 0
    return (0, 1, 0, -1)[i % 4]


def _close_no_falante(i, n_trechos, n_atores):
    """Este trecho fecha em QUEM FALA, deixando o outro sair do quadro?

    POR QUE ISTO EXISTE
        O v006 saiu com dezesseis quadros no MESMO plano aberto, os dois de
        corpo inteiro, do primeiro ao último segundo -- apesar de o ciclo de
        planos existir desde 27/08. A causa não era o ciclo: com dois atores
        o teto é 1,25, e 1,00 → 1,25 é uma variação que ninguém percebe.
        Subir o teto não resolvia, porque `montar_frame` limita o zoom à
        silhueta dos DOIS somados (740 px) e trava tudo em 1,33.

        O plano de melhorias pede outra coisa, e é ela que falta: *"close no
        personagem que está falando; depois, cortar para o outro durante a
        resposta"*. Isso não é fechar mais no par -- é enquadrar UM e deixar
        o outro fora. Como o falante alterna a cada trecho, alternar o close
        produz de graça o corte de conversa que o formato pede.

    A REGRA, E POR QUE ELA NÃO É "UM SIM, UM NÃO"
        A primeira versão fechava nos ímpares, e a prévia mostrou o defeito
        na hora: **os seis closes saíram todos na Maya**. O falante alterna
        a cada trecho, então fechar com período 2 fecha sempre na mesma
        pessoa -- o João atravessou o vídeo inteiro sem um close, que é
        metade do problema que isto veio resolver.

        O período tem de ser ÍMPAR para cair nas duas paridades. São dois
        closes a cada cinco trechos (`i % 5 in (1, 4)`): eles caem em 1, 4,
        6, 9, 11 -- ímpar, par, par, ímpar, ímpar --, e os dois lados da
        conversa ganham cara grande. Dois em cinco também é o espaçamento
        que o plano de melhorias pede (mudança visual a cada 2 a 5 s) sem
        que o close vire o plano padrão.

        A virada (último trecho) fecha sempre, porque a piada acontece na
        cara; e o trecho ANTES dela abre sempre -- sem o contraste, a virada
        chegaria no mesmo tamanho do que veio antes e o fechamento não seria
        lido como troca de plano. Com menos de três trechos não há
        alternância que valha: o vídeo inteiro viraria um close só.
    """
    if n_atores < 2 or n_trechos < 3:
        return False
    # O GANCHO FECHA (01/09, R1 do DIAGNOSTICO.md). Todo vídeo do canal
    # abria em plano ABERTO -- dois bonecos em pé, de corpo inteiro, e a
    # cara a ~7% da altura do quadro. Nos três primeiros segundos é onde a
    # plataforma decide se distribui o vídeo, e é exatamente onde este
    # formato mostrava menos. Fechar no trecho 0 não custa nada: o plano
    # já existe, e o que muda é onde ele cai.
    #
    # Vem ANTES da regra do penúltimo porque num vídeo de 2 ou 3 trechos
    # o trecho 0 seria `n_trechos - 2` e o gancho voltaria a abrir.
    if i == 0:
        return True
    # e o trecho 1 ABRE, sempre. `i % 5 in (1, 4)` fechava justamente ele,
    # e dois closes seguidos no começo apagam o corte que o gancho acabou
    # de ganhar -- é a mesma razão pela qual o penúltimo abre antes da
    # virada. Os closes restantes caem em 4, 6, 9, 11, que continuam
    # pegando as duas paridades do falante (a regra do período ímpar).
    if i == 1 or i == n_trechos - 2:
        return False
    return i % 5 in (1, 4) or i == n_trechos - 1


def _enquadramento(i, n_trechos, n_atores, t, centro_corpo=None,
                   close=False, centro_rosto=None, teto_par=1.0):
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
    # 1,25 COM DOIS (30/08). Eram 1,12, escolhidos no olho quando o teto do
    # frame ainda não existia: fechar mais cortava um deles pela borda. Hoje
    # `montar_frame` mede a silhueta REAL de cada frame e limita o zoom ao
    # que ela comporta (29/08), então o número aqui deixou de ser a única
    # proteção -- e 1,00 a 1,12 é uma variação que ninguém percebe num vídeo
    # de 66 s com treze trechos. Os dois ficam em x=296 e 784 e ocupam ~740
    # dos 1080 px: cabe fechar bem mais que 12%.
    # 1,30 -> 1,60 COM UM SÓ (31/08, volta 5 do ciclo de vídeo). O v005 foi
    # um monólogo e os dezesseis quadros saíram no MESMO plano inteiro: um
    # boneco no meio de um 9:16, com um terço de quadro vazio de cada lado.
    # O teto de 1,30 vinha de quando havia sempre dois em cena, onde ele é
    # o certo -- fechar mais corta um pela borda. Sozinho, no meio, o corpo
    # ocupa ~370 dos 1080 px: 1,30 nem chega a encher metade.
    #
    # O plano de melhorias pede close nas falas importantes (itens 4 e 5), e
    # é aqui que ele cabe sem inventar camada nenhuma: o ciclo de planos já
    # existe, só faltava alcance para o degrau fechado ser um CLOSE de
    # verdade e não outro plano médio.
    #
    # 1,60 e não mais: acima disso o topo da cabeça encosta na borda quando
    # a ação levanta o braço, e `montar_frame` passaria a cortar o gesto --
    # que é justamente o que este vídeo tem de melhor.
    # O CLOSE NÃO PASSA PELO CICLO. Ele é um plano à parte -- enquadra UM
    # ator, não o par --, então nem o teto nem os cinco degraus valem para
    # ele. O push-in de 3,5% continua, que é o que separa vídeo de foto.
    if close:
        z = CLOSE_FALANTE * (1.0 + 0.035 * max(0.0, min(1.0, t)))
        meia = 0.5 / z
        alvo = centro_rosto if centro_rosto is not None else centro_corpo
        if alvo is None:
            alvo = 0.5
        return z, max(meia, min(1.0 - meia, float(alvo)))
    # O PLANO DO PAR NÃO EXISTE, E PEDI-LO FAZ A CÂMERA PULSAR (31/08,
    # volta 18). O log da guarda mostrou o que o teto de 1,25 vira na
    # prática com dois em cena: `plano 1.15 nao cabe no corpo (933x867px);
    # vai a 1.05`, dezesseis vezes no mesmo trecho, com valores diferentes
    # a cada frame -- 1,05, 1,15, 1,12, 1,08, 1,06. O núcleo dos dois ocupa
    # ~900 dos 1080 px, então nada acima de ~1,09 cabe; o ciclo pedia
    # 1,06/1,12/1,19/1,25 e recebia ruído. Zoom que oscila 10% dentro de
    # uma fala é a câmera pulsando junto com os braços -- o mesmo defeito
    # que o núcleo tinha acabado de resolver com um ator.
    #
    # Com dois em cena a variação de plano é OUTRA: é o close em quem fala
    # (1,90) alternando com o plano dos dois. Os degraus intermediários não
    # existem, e pedir o que não cabe só produz tremor.
    #
    # O QUE MUDOU EM 01/09 (volta 57): o plano do par deixou de ser a
    # CONSTANTE 1,00 e passou a ser o que a largura MEDIDA dos dois
    # comporta (`teto_par`, calculado uma vez por trecho a partir de
    # `meia_esq`/`meia_dir`). A razão de 1,00 nunca foi estética -- era
    # que nada acima de ~1,09 cabia com os dois a 496px um do outro. Com
    # eles a ~346px (ABERTURA_DO_PAR) cabe bem mais, e a diferença é entre
    # dois bonecos no rodapé e dois rostos legíveis.
    #
    # O NÚMERO VEM DE FORA E É FIXO DENTRO DO TRECHO -- é isso que separa
    # esta correção do tremor do v018. Lá o valor era recalculado a cada
    # frame pela guarda e oscilava 1,05/1,15/1,12; aqui ele é medido no
    # repouso, uma vez, e a guarda por frame só age se alguma pose
    # inesperada estourar.
    #
    # E O CICLO DE PLANOS DO PAR VOLTOU A EXISTIR, com DOIS degraus. Ele
    # tinha sido desligado no v018 porque nada acima de ~1,09 cabia, e
    # pedir o que não cabe produz tremor, não plano. Com o par a 622px em
    # vez de 900, cabe -- e a alternância entre trechos é o CORTE que este
    # formato não tem. Dois degraus e não cinco: a lição do v018 continua
    # valendo, degrau intermediário com dois em cena é imperceptível.
    if n_atores > 1:
        z = max(1.0, min(TETO_PAR, float(teto_par)))
        # período 2 nos trechos do par. Ele não briga com o período 5 do
        # close: o close tira o trecho do par, então a alternância aqui é
        # sobre os que sobraram, e cair na mesma paridade duas vezes
        # seguidas é o que dá o descanso (a lição do período ímpar do
        # `_close_no_falante` é sobre quem FALA, e aqui não há falante).
        if i % 2:
            z = 1.0
        return z * (1.0 + 0.035 * max(0.0, min(1.0, t))), \
            (0.5 if centro_corpo is None else
             max(0.0, min(1.0, float(centro_corpo))))
    teto = 1.60
    # O CICLO PRECISOU CRESCER COM A ESQUETE (30/08). Eram três posições
    # (aberto, médio, fechado), e num vídeo de 5 trechos elas davam uma
    # sequência que não se repetia. Com 13 trechos o ciclo roda QUATRO
    # vezes, e a prévia do primeiro vídeo de 88 s mostra o resultado: doze
    # quadros com o mesmo enquadramento, porque 1,00 → 1,12 é uma diferença
    # que ninguém percebe quando volta a cada três trechos.
    #
    # Cinco degraus em ordem NÃO monotônica: o salto de fechado para aberto
    # é o que se lê como corte. Em ordem crescente, o mesmo conjunto viraria
    # um zoom-in lento de treze trechos, que é o contrário de cortar.
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
    # ONDE A CÂMERA CENTRA. Fechar no meio do quadro corta pés e cabeça em
    # partes iguais; o certo é centrar em quem está em cena.
    #
    # `centro_corpo` é o meio do corpo, em fração da altura, e ele MUDA com
    # o cenário: desde que os pés passaram a pousar no chão desenhado, o
    # personagem pode estar a 78% do quadro (rua) ou a 95% (sala com o
    # aparador na frente). O valor fixo que existia aqui puxava o corte
    # para CIMA -- feito quando todo mundo ficava a 78% -- e nos cenários
    # de chão baixo isso decepava os pés.
    #
    # Sem o parâmetro, cai no comportamento antigo: é o que os specs de
    # conferência e o `enquadramento.py` usam.
    if centro_corpo is None:
        fechado = (z - 1.0) / max(teto * 1.035 - 1.0, 1e-6)
        return z, 0.5 - 0.10 * max(0.0, min(1.0, fechado))
    # o clamp mantém a janela dentro do quadro: centrar em 0,73 com zoom
    # 1,12 pediria uma faixa que começa abaixo do topo e acaba fora da
    # base, e o crop de `montar_frame` a empurraria de volta de qualquer
    # jeito -- fazer a conta aqui deixa o número honesto no log.
    meia = 0.5 / z
    return z, max(meia, min(1.0 - meia, float(centro_corpo)))


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
        else:
            # QUEM ESCUTA TAMBÉM ESTÁ EM CENA (01/09, volta 57). Sem isto,
            # em todo trecho um dos dois passa a fala inteira com os braços
            # mortos ao lado do corpo -- e como o falante alterna, cada
            # personagem fica assim metade do vídeo. `escutar` é de
            # propósito muito menor que `gesticular`: quem escuta não pode
            # disputar a atenção com quem fala.
            lista.append({"nome": "escutar", "de": 0.0, "ate": 1.0,
                          "forca": 0.7 + 0.3 * ACOES.energia_gesto(
                              tr.get("expressao"), tr.get("intensidade", 1.0))})
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
        # TRÊS VALORES, SEMPRE. Este atalho devolvia `(Personagem, x)` --
        # duas posições --, enquanto o caminho com `elenco` passa por
        # `_alinhar_pelos_pes` e devolve `(Personagem, x, dy)`. Todo o
        # resto do motor desempacota TRÊS, então um spec de um personagem
        # só derrubava o cut-out inteiro com "not enough values to unpack
        # (expected 3, got 2)" -- e o job caía no rig vetorial, que é a
        # rede de segurança.
        #
        # O bug estava aqui desde que o elenco existe e nunca tinha
        # aparecido: TODO spec de produção vinha com dois em cena, porque
        # o prompt pedia sempre uma cena de dois. O primeiro vídeo gerado
        # com a forma `monologo_fisico` (o rodízio de 29/08) o encontrou
        # na primeira tentativa. É a lei 34 pelo avesso -- o que a forma
        # não exercita não falha à vista.
        return _alinhar_pelos_pes({"_": (Personagem(pasta_padrao), W / 2)})
    # DOIS EM CENA, MAS NÃO DOIS NO VÍDEO (30/08, noite).
    #
    # Até aqui este trecho TRUNCAVA o elenco em dois na carga, e o loop de
    # render desenhava o elenco inteiro em todo trecho -- então "dois por
    # vez" e "dois no vídeo" eram a mesma coisa, e um elenco de dez servia
    # para escolher a dupla do dia, nunca para trocar de gente no meio.
    #
    # O dono do projeto pediu o contrário: *"pode ter apenas dois
    # personagens por vez no vídeo, mas não precisa ter apenas dois no
    # vídeo; ele pode andar e aparecer outro personagem, e assim por
    # diante"*. Isso não afrouxa a lei 10 -- o teto de DOIS no quadro
    # continua, porque a razão dele é o 9:16 e a cara. O que muda é onde ele
    # é aplicado: por TRECHO (`_em_cena`), não por vídeo.
    #
    # Aqui, então, carrega-se todo mundo. Quem entra em cena em cada trecho
    # é decidido depois, e é `_posicionar` que dá o x de cada um dentro do
    # trecho -- porque o lugar de alguém no quadro depende de com QUEM ele
    # está dividindo a cena naquele momento, não do tamanho do elenco.
    n_cena = min(len(elenco), MAX_EM_CENA)
    fora, pedidos = {}, {}
    for i, (chave, cfg) in enumerate(elenco.items()):
        cfg = cfg if isinstance(cfg, dict) else {"pasta": cfg}
        pasta = cfg.get("pasta") or os.path.join(pasta_padrao, "..", chave)
        # posições padrão bem separadas: duas pessoas no mesmo x viram uma
        # pessoa só com quatro braços
        padrao = W * (0.5 if n_cena == 1 else
                      (0.5 - ABERTURA_DO_PAR / 2.0)
                      + ABERTURA_DO_PAR * (i % n_cena) / max(n_cena - 1, 1))
        p = Personagem(pasta)
        # A ESCALA VEM DE QUANTOS CABEM EM CENA, não de quantos existem no
        # vídeo. Com o elenco solto, `len(elenco)` pode ser seis, e usá-lo
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
    """Quem aparece NESTE trecho, no máximo `MAX_EM_CENA`.

    A regra, em ordem, e cada passo existe por um motivo:

      1. quem FALA entra sempre -- uma fala sem dono na tela é a lei 15
         (não existe narrador) voltando pela porta dos fundos;
      2. depois quem o roteirista pediu em `personagens_em_cena`, na ordem
         em que ele escreveu;
      3. se ainda sobra vaga, quem estava em cena no trecho ANTERIOR. É o
         que dá continuidade: sem isso, um trecho que só nomeia o falante
         esvaziaria a cena e o outro sumiria sem sair andando -- corte de
         gente, que é o defeito que a lei 36 descreve.

    Nome que não está no elenco é descartado em silêncio de propósito: ele
    não tem arte, e `job.py` já avisou disso ao montar o spec.
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
    # NO PRIMEIRO TRECHO NÃO HÁ ANTERIOR (31/08, defeito 5 dos vídeos).
    #
    # `anteriores` começava valendo o elenco inteiro, "para o primeiro
    # trecho ter um anterior" -- e com isso a regra 3 punha em cena, já no
    # primeiro segundo do vídeo, alguém que o roteirista tinha deixado de
    # fora de propósito porque ele ENTRA depois. O resultado na tela é o
    # teleporte da queixa: a personagem aparece parada no lugar dela, o
    # trecho seguinte começa e ela salta para a borda para entrar andando.
    #
    # `anteriores` vazio é a verdade do primeiro trecho, e a continuidade
    # não perde nada: ela existe para não esvaziar uma cena que já existia.
    # O que fica de fora é o spec ANTIGO, que não escreve
    # `personagens_em_cena` -- para ele o elenco carregado continua sendo a
    # cena, como era antes de o campo existir.
    if not tr.get("personagens_em_cena") and not anteriores:
        for c in list(elenco)[:MAX_EM_CENA]:
            if c not in ordem:
                ordem.append(c)
    if not ordem:
        ordem = list(elenco)[:1]
    escolhidos = ordem[:MAX_EM_CENA]
    # A ORDEM DE SAÍDA É A DO ELENCO, NÃO A DE ENTRADA (31/08, volta 1).
    #
    # Quem entra na lista primeiro é o FALANTE -- e o falante alterna a cada
    # trecho. Como `_posicionar` distribui o quadro pela ordem que recebe,
    # os dois TROCAVAM DE LADO a cada fala: no vídeo 001 a Maya está à
    # esquerda nos trechos 1 a 3, o João no 4, ela de novo no 5. Não é
    # movimento, é pisca-pisca de posição -- e é pior que o defeito que
    # `_separar` existe para evitar, porque a plateia perde a referência de
    # quem é quem.
    #
    # A ordem do elenco no spec é estável durante o vídeo inteiro, e é ela
    # que `_carregar_elenco` já usou para dar o x base. Ordenar por ela
    # devolve a regra que existia antes do elenco solto: quem está à
    # esquerda continua à esquerda.
    pos = {c: i for i, c in enumerate(elenco)}
    return sorted(escolhidos, key=lambda c: pos.get(c, 99))


def _posicionar(elenco, chaves):
    """As posições de quem está em cena NESTE trecho.

    Existe porque o x de um personagem não é uma propriedade dele: é a
    divisão do quadro entre quem está lá agora. Com o elenco solto, o mesmo
    personagem fica à direita quando divide a cena com um e sozinho no
    centro quando o outro sai -- e o `_afastar_o_bastante` só sabe separar
    quem está em cena junto.
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


# NINGUÉM ATRAVESSA NINGUÉM (29/08) ------------------------------------
# Uma coluna da imagem pertence ao CORPO se ela tem pelo menos esta fração
# da altura da figura preenchida. É o que separa tronco, cabeça e pernas
# -- que ocupam a coluna inteira -- de um braço estendido, que numa coluna
# ocupa a espessura do braço. Medido nos três personagens de produção: a
# 45% o Pal em repouso dá 258px de corpo e 558px de silhueta, e `apontar`
# muda a silhueta de 558 para 689 sem mexer no corpo. Abaixo de 30% o
# braço caído entra na conta; acima de 65% a cabeça sai dela.
LIMIAR_CORPO = 0.45
# O vão que fica entre dois corpos. Não é estética: encostado, o contorno
# preto de um vira contorno do outro e os dois lêem como uma figura só.
FOLGA_ENTRE_ATORES = 40.0
# ONDE OS DOIS FICAM NO QUADRO -- e por que isto encolheu (01/09, volta 57).
#
# Eram 0,27 e 0,73, ou seja 496px entre os quadris num quadro de 1080. O
# número foi escolhido no olho em 28/08, ANTES de existir `_separar` (a
# guarda que mede colisão frame a frame) e antes de `_afastar_o_bastante`
# (que abre as posições até os CORPOS MEDIDOS caberem). Escolhido no olho,
# ele errou para o lado caro: com os dois tão longe um do outro, o núcleo
# do par ocupa ~900 dos 1080px e NENHUM plano acima de ~1,09 cabe -- é a
# aritmética do v018, e é ela que faz o plano aberto ser sempre o mesmo
# plano aberto.
#
# O preço aparece na tira de rostos da volta 57: em oito dos doze quadros
# os dois estão no rodapé, com a CARA a ~7% da altura do quadro e dois
# terços de armário de cozinha em cima. Num telefone não se lê expressão
# nenhuma ali -- e a cara é onde a piada acontece desde a volta 6.
#
# 0,34/0,66 dá ~346px entre os quadris. Isto NÃO é uma aposta: quem
# garante que cabe é `_afastar_o_bastante`, que mede meia_esq e meia_dir
# na arte de cada um e reabre para o mínimo se 346 for pouco. O número
# aqui virou o PEDIDO; a medida continua sendo a garantia.
ABERTURA_DO_PAR = 0.32
# a margem que sobra de cada lado do par quando a câmera fecha nele. O
# gesto pode encostar na borda (é o que um plano fechado faz), o TRONCO
# não pode.
MARGEM_LATERAL_PAR = 60.0
# teto do plano do par. Acima disso a folha -- desenhada uma vez só --
# começa a aparecer ampliada demais, e é o mesmo limite que segura
# CLOSE_FALANTE em 1,90 com um corpo de 852px.
TETO_PAR = 1.45


def _medir_corpo(pers, img, bb):
    """Quanto o CORPO deste personagem ocupa à esquerda e à direita do
    quadril, em pixels de tela. Guardado no próprio Personagem.

    POR QUE MEDIR, E POR QUE UMA VEZ SÓ
        As posições padrão (0,27 e 0,73 de 1080) deixam 488px entre os dois
        quadris, e esse número foi escolhido no olho. Medido: o Pal ocupa
        279px para cada lado em REPOUSO -- os dois já se tocavam parados,
        antes de qualquer ação. Supor a largura é o mesmo erro que supor a
        linha do chão (§4.42) e o pivô: mede-se.

        Uma vez só porque o corpo quase não muda de largura -- é o braço
        que abre, e braço que passa na frente do outro é linguagem normal
        de cut-out. O que não se aceita é dois troncos no mesmo lugar.
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
    # a passada abre as pernas; a folga cobre o que a medida em repouso não vê
    pers.meia_esq = max(W / 2.0 - float(cheias[0]), 60.0)
    pers.meia_dir = max(float(cheias[-1]) - W / 2.0, 60.0)


def _afastar_o_bastante(elenco, pedidos=None):
    """Abre as posições padrão até os corpos caberem lado a lado.

    Só mexe em quem NÃO teve `x` pedido no spec: posição escrita à mão é
    decisão de quem escreveu, e a guarda por frame (`_separar`) continua
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

    Não silhueta: uma coluna atravessada só pelo braço tem a espessura do
    braço preenchida, e braço passando na frente do outro personagem é
    linguagem normal de cut-out. Tronco dentro de tronco não é."""
    bb = bb or img.getbbox()
    if not bb:
        return np.zeros(W, dtype=bool)
    alt = max(bb[3] - bb[1], 1)
    return (np.asarray(img)[..., 3] > 32).sum(axis=0) >= alt * LIMIAR_CORPO


def caixa_do_nucleo(img, bb=None):
    """A caixa do NÚCLEO da figura: tronco, cabeça e pernas, sem os braços.

    POR QUE (31/08, defeito 4 dos vídeos: *"quando enquadra um único
    personagem e ele acena, quebra completamente o enquadramento, e fica
    dando alguns tilts conforme o personagem se mexe"*)
        As duas guardas de janela de `montar_frame` -- a que não deixa o
        gesto sair pela lateral e a que não deixa a cabeça ser cortada em
        cima -- miravam o `getbbox()` da camada, isto é, a SILHUETA. Num
        aceno a silhueta muda a cada frame: a mão sobe 200px acima da
        cabeça e volta duas vezes por segundo, e a janela subia e descia
        junto. Na tela é o quadro inteiro balançando enquanto a personagem
        acena -- e, no frame em que a mão está no alto, a cara vai parar no
        meio da tela.

        A guarda de ZOOM já tinha aprendido isto na volta 11 (lei 33: uma
        coluna atravessada só pelo braço não é corpo). O que faltava era
        levar a mesma distinção às guardas de POSIÇÃO da janela. Com o
        núcleo, a referência é a cabeça e o tronco -- que oscilam menos de
        um grau -- e a câmera para de respirar junto com o braço.

    O que se perde é a garantia de que a mão erguida cabe no quadro. É de
    propósito: close é enquadramento que corta, e o que não pode ser
    cortado é a cara. O que a mão está SEGURANDO continua protegido, por
    fora desta função (`caixa_extra` em `montar_frame`).
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
    """A caixa que contém as duas. `None` de um lado devolve o outro."""
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _transladar(img, dx):
    """Move a camada em x. Um deslocamento do quadril translada o desenho
    inteiro rigidamente -- toda peça sai da posição do quadril por somas --,
    então mover a imagem pronta dá exatamente o mesmo resultado que
    redesenhar, e custa uma cópia em vez de uma árvore de peças."""
    if abs(dx) < 0.5:
        return img
    nova = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    nova.paste(img, (int(round(dx)), 0))
    return nova


def _separar(camadas, ordem, elenco=None):
    """NINGUÉM ATRAVESSA NINGUÉM. Mede os dois corpos já desenhados e
    devolve `{chave: dx}` -- o quanto cada um tem que ceder neste frame.

    POR QUE MEDIR OS PIXELS, E NÃO A LARGURA GUARDADA
        A primeira versão desta guarda era aritmética: meia-largura medida
        uma vez em repouso, contas sobre o x do quadril. Ela cobria as
        ações em pé e passou em dez das onze da régua -- e falhou em
        `cair`, que DEITA o personagem. Deitado, o corpo mede 700px de
        largura em vez de 250, e nenhuma medida tirada em pé sabe disso.

        Largura de corpo não é propriedade do personagem, é do frame. Aqui
        ela é lida do frame: custa uma soma por coluna sobre o canal alfa
        (~2ms), contra os ~200ms de desenhar a árvore de peças.

    A ordem esquerda/direita vem da posição BASE e nunca inverte: sem isso,
    alguém atravessando seria "corrigido" para o outro lado no meio do
    movimento, o que é pior que a colisão.
    """
    if len(ordem) != 2:
        return None
    a, b = ordem
    ca, cb = colunas_de_corpo(camadas[a]), colunas_de_corpo(camadas[b])
    xa, xb = np.nonzero(ca)[0], np.nonzero(cb)[0]
    if not len(xa) or not len(xb):
        return None                     # alguém ainda fora do quadro
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
        # ENTREGAR ESVAZIA A MÃO NO FIM DA AÇÃO. Ver
        # ACOES_ENTREGAM_OBJETO: durante o gesto a coisa tem que estar na
        # mão (é o que se está oferecendo); passado o gesto, ela é de quem
        # recebeu. Sem isto o objeto se duplica e os dois seguram uma
        # marmita cada -- o defeito da rodada 6 do ciclo.
        #
        # A MARGEM NÃO É ENFEITE (rodada 10). O motor anima "em 2s"
        # (`fh = (f // 2) * 2`), então num trecho de número par de frames o
        # `t` do último frame é (nf-2)/(nf-1) e NUNCA chega a 1,0. Com
        # `t >= ate` e uma entrega de `ate: 1.0`, a condição jamais era
        # verdadeira: a rodada 6 passou porque lá a entrega acabava em 0,6,
        # e a de 1,0 duplicou a caixa de papelão do mesmo jeito de antes.
        if a.get("nome") in ACOES.ACOES_ENTREGAM_OBJETO \
                and t >= float(a.get("ate", 1.0)) - 0.02:
            atual = None
            continue
        nome = a.get("objeto")
        if nome in objetos:
            atual = {"img": objetos[nome], "mao": a.get("mao", "d"),
                     "escala": float(a.get("escala_objeto", 1.0))}
    return atual


def _quem_saiu(por_ator):
    """Quem terminou este trecho FORA do quadro.

    QUALQUER `sair_andando` CONTA, e não só a que vai até o fim da fala
    (31/08). A regra antiga exigia `ate >= 0,95` porque quem saía no meio do
    trecho voltava sozinho -- a ação deixava de ser aplicada e o corpo
    reaparecia no lugar dele no frame seguinte, que é o teletransporte do
    defeito 5. Agora a saída FICA (ver `acoes.aplicar`): quem saiu está fora
    até o trecho acabar, e portanto tem de voltar entrando no seguinte."""
    return {c for c, acoes in por_ator.items()
            if any(a.get("nome") in ACOES.ACOES_DE_SAIDA for a in acoes)}


def _fazer_voltar(por_ator, fora_de_cena):
    """Quem saiu de cena volta ENTRANDO, não aparecendo.

    O primeiro vídeo do ciclo mostrou o defeito inteiro em quatro segundos:
    o Pal sai andando no fim de um trecho e, no trecho seguinte, está de
    volta parado no lugar dele. O corte de plano entre trechos justifica
    muita coisa -- mas não alguém que a plateia acabou de ver indo embora.

    A entrada é curta e no começo da fala: ele chega falando, que é como
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


def _quem_recebe(por_ator, na_mao, t, objetos):
    """Entregar é PASSAR: o que sai de uma mão entra na outra.

    `_objeto_na_mao` já esvazia a mão de quem entregou. Falta pôr a coisa
    na mão de quem recebeu, e isso o spec quase nunca escreve -- o
    roteirista diz "toma" e considera o assunto encerrado. Sem esta parte,
    o objeto simplesmente desaparece da cena no meio da esquete, que é pior
    que a duplicação que ela conserta: a âncora da piada some.

    Só age quando o outro ator está de mãos vazias. Se ele já pegou o
    objeto por conta própria (uma ação de objeto no trecho dele), o spec
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
    """UM OBJETO ESTÁ NUMA MÃO SÓ. Devolve quem perdeu, ou None.

    `entregar_objeto` resolve o caso em que alguém DÁ. Falta o caso em que
    alguém TOMA: a Maya faz `pegar_objeto` com a xícara que o Pal está
    segurando, e nada no spec diz que ele largou -- o roteirista escreveu
    "toma da mão dele" e considerou o assunto encerrado, do mesmo jeito que
    escreve "toma" na entrega. Sem esta regra os dois seguram a mesma
    xícara, que é o defeito da rodada 11 do ciclo (e o terceiro membro da
    mesma família: ver as leis 39 e 41).

    Quem fica com a coisa é quem tem uma ação de objeto ATIVA agora, e a
    mais recente delas ganha. Não havendo como decidir -- os dois pegando
    no mesmo instante --, ninguém perde e o motor avisa: inventar um dono
    aqui esconderia um spec ambíguo.
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
    """O vídeo inteiro, ou uma AMOSTRA dele.

    `amostra=N` desenha só N frames igualmente espaçados e devolve uma
    folha de contato em vez do MP4. Existe porque o ciclo de melhoria é
    olhar-corrigir-olhar, e um render completo custa ~12 min para uma
    pergunta que 12 quadros respondem: os personagens se atravessam? a
    câmera cortou a cabeça de alguém? o objeto está na mão?

    Tudo o que vem antes do desenho continua rodando igual -- a voz, a
    timeline, a trilha, a legenda, o cenário --, então os quadros da
    amostra são os quadros do vídeo, no mesmo instante. O que se pula é
    desenhar os outros 550."""
    from palito_v5 import sintetizar, envelope, juntar_com_respiro
    tmp = tmpdir or tempfile.mkdtemp()
    fd = os.path.join(tmp, "frames"); os.makedirs(fd, exist_ok=True)

    elenco = _carregar_elenco(spec, pasta_partes)
    padrao_ator = list(elenco)[0]
    # `chaves` e `ordem_x` passaram a ser DO TRECHO (30/08, noite): com o
    # elenco solto, quem está em cena muda ao longo do vídeo. Estes são só
    # os valores de partida, para o primeiro trecho ter um "anterior".
    chaves = list(elenco)[:MAX_EM_CENA]
    # VAZIO, E NÃO O ELENCO (31/08): antes do primeiro trecho ninguém esteve
    # em cena, e dizer o contrário põe no quadro quem ainda vai entrar. Ver
    # `_em_cena`.
    chaves_ant = []
    posto = _posicionar(elenco, chaves)
    ordem_x = sorted(chaves, key=lambda c: posto[c][1])

    # A ALTURA DE VERDADE DO ATOR, medida num frame de repouso. Ela decide
    # dois números: onde os pés pousam (o chão desenhado, §4.42) e o
    # TAMANHO DOS OBJETOS.
    #
    # Até 29/08 o objeto era medido contra `ALTURA_ALVO_PX`, uma constante
    # de 1150. Só que a altura do ator não é constante: com dois em cena a
    # escala cai para 0,74 e o corpo mede 852 px. Todo objeto saía 35%
    # maior do que a fração pedida -- o guarda-chuva de 40% virava 54% da
    # altura do ator, o que é o "objeto enorme atravessando o corpo" da
    # rodada 3 do ciclo. E como as três rodadas de 28/08 tinham dois em
    # cena, a calibração de `TAMANHO_OBJETO` foi feita inteira com esse
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
        # RECORTE PELO ALFA SÓLIDO, não por `getbbox()` (28/08). O rembg
        # devolve alfa residual baixo -- 1 ou 2 de 255 -- em quase todo o
        # PNG, e `getbbox()` considera isso conteúdo: ele devolvia a imagem
        # INTEIRA em todos os dez objetos do catálogo. Como a escala é
        # medida sobre a caixa devolvida, o objeto de verdade saía menor do
        # que o pedido, e quanto mais margem a arte tinha, menor ele ficava:
        # no boleto o desenho ocupa 37% da altura do arquivo, então ele
        # aparecia com um terço do tamanho e sumia na mão.
        _a = np.asarray(im)[..., 3]
        _ys, _xs = np.nonzero(_a > 128)
        if len(_ys):
            im = im.crop((int(_xs.min()), int(_ys.min()),
                          int(_xs.max()) + 1, int(_ys.max()) + 1))
        # O TAMANHO É POR OBJETO (ver TAMANHO_OBJETO). Um número só para
        # todos errava nas duas pontas: 16% fez a xícara ficar do tamanho do
        # tronco em 27/08, e os 11% que resolveram aquilo fizeram o boleto
        # sumir em 28/08 -- uma folha de papel na mão ocupa um quarto da
        # altura de uma pessoa, não um décimo.
        # contra a altura MEDIDA do ator, não contra a constante: ver o
        # comentário em `altura_ator`, logo acima
        alvo = altura_ator * TAMANHO_OBJETO.get(nome, TAMANHO_OBJETO_PADRAO)
        # pela MAIOR dimensão, não pela altura: o boleto e o controle são
        # desenhados deitados, e medir a altura deles deixava o objeto do
        # tamanho de um cartão. O que se lê como tamanho é o lado maior.
        k = alvo / max(im.width, im.height, 1)
        im = _reamostrar(im, (max(int(im.width * k), 1),
                              max(int(im.height * k), 1)))
        # CONTORNO, depois de redimensionar: a espessura é fração do
        # tamanho FINAL, senão ela encolhe junto com a arte e some
        # justamente no objeto pequeno, que é o que mais precisa dela.
        objetos[nome] = _destacar_objeto(im)

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
    # O PIIII (28/08). O palavrão já chega cortado na primeira sílaba do
    # n8n ("Ca—"); aqui ele some atrás do bipe de 1 kHz e a legenda mostra
    # os símbolos. As duas coisas saem do MESMO casamento entre texto e
    # marcas de palavra que a legenda usa, senão o som e o texto
    # divergiriam justamente na fala em que o TTS perdeu uma palavra.
    from legendas import janelas_censuradas
    bipes = []
    for tr, m in zip(spec["trechos"], marcas_por_trecho):
        bipes += janelas_censuradas(tr["fala"], m, tr["_inicio_s"], tr["_dur_voz"])

    audio = voz
    # `bipes` entra na condição porque a censura não é opcional: um spec com
    # trilha e efeitos desligados ainda não pode deixar o palavrão passar
    if bipes or spec.get("sfx", True) is not False or spec.get("musica", True):
        eventos = SFX.eventos_do_spec(spec) if spec.get("sfx", True) is not False else []
        # A TRILHA SEGUE A CENA. Os segmentos saem da emoção de cada trecho,
        # que só existe depois que a voz definiu a timeline -- por isso são
        # montados aqui e não no n8n.
        musica = spec.get("musica", True)
        if isinstance(musica, dict) and not musica.get("arquivo"):
            musica = dict(musica)
            musica.setdefault("segmentos", SFX.segmentos_do_spec(spec))
            # a trilha é de ESTE vídeo: o gênero vem do roteiro (`genero`) e
            # a semente do fila_id, para que duas esquetes do mesmo gênero
            # não saiam com o mesmo arpejo nota por nota
            musica.setdefault("semente", spec.get("fila_id", "sem-fila"))
        audio = SFX.mixar(voz, eventos, os.path.join(tmp, "mix.wav"),
                          musica=musica, dur_s=total, bipes=bipes)

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

    # (a altura do ator e a linha dos pés já foram medidas lá em cima, no
    # carregamento: o tamanho dos objetos depende delas)

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
    n_trechos = len(spec["trechos"])
    planos, cortes = [], []
    n_empurrados = {}
    fora_de_cena = set()          # quem saiu andando no trecho anterior
    dupla_avisada = False         # o aviso de objeto duplicado sai uma vez
    largou_avisado = set()        # quem já teve o objeto tomado da mão
    # OS FRAMES QUE A AMOSTRA QUER, em índice global. `total` já é a
    # duração real da voz, então dá para escolher antes de desenhar.
    quero, colhidos = None, []
    if amostra:
        n_total = max(int(total * FPS), 1)
        # QUADROS IGUALMENTE ESPAÇADOS MENTEM SOBRE MOVIMENTO CÍCLICO.
        #
        # A passada tem 1,7 ciclos por segundo e a amostra pega um quadro a
        # cada ~1,5 s: os instantes caem quase sempre na mesma fase do
        # ciclo, e a folha mostra o personagem na mesma pose doze vezes. Foi
        # o que fez a rodada 4 do ciclo concluir que "ele não anda" -- e
        # medido depois, o pé percorre 129 px por passada, que se vê muito
        # bem no vídeo.
        #
        # O passo áureo desalinha a amostra de qualquer período: o
        # deslocamento dentro de cada intervalo nunca se repete, então duas
        # fases iguais seguidas deixam de ser o caso comum. Continua
        # determinístico e continua cobrindo o vídeo inteiro em ordem.
        phi = 0.6180339887
        quero = {min(int(n_total * (i + (i * phi) % 1.0) / amostra),
                     n_total - 1)
                 for i in range(amostra)}
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
                cenarios[cen] = Cenario(Image.new("RGB", (W, H), "#A5A893"),
                                        chao_rel=CENARIOS.CHAO_PADRAO)
        elif cen not in cenarios:
            cam_path = _achar_arte(pastas_cenario, cen)
            chao_rel = CENARIOS.chao_de(cen)
            print(f"[cenario] {pedido} -> {cen} ({motivo}, chao a "
                  f"{chao_rel * 100:.0f}%): {cam_path}")
            cenarios[cen] = Cenario(Image.open(cam_path), chao_rel=chao_rel)
        elif motivo != "pedido":
            print(f"[cenario] {pedido} -> {cen} ({motivo})")

        # OS PÉS NO CHÃO DESENHADO. Até 28/08 o personagem ficava na altura
        # fixa do rig (78% do quadro com dois em cena) e a arte tinha o chão
        # em qualquer lugar entre 80% e 90% -- na sala isso é 192px de
        # diferença, e o resultado é o boneco pairando na frente da parede.
        dy_chao = 0.0
        if base_pes:
            dy_chao = cenarios[cen].chao_y - base_pes
            if i_tr == 0 or abs(dy_chao) > 1:
                print(f"[chao] {cen}: chao em y={cenarios[cen].chao_y:.0f}, "
                      f"pes em y={base_pes} -> {dy_chao:+.0f}px")

        # O CORTE DESTE TRECHO: o fundo fica imóvel aqui dentro, e o próximo
        # trecho pega outro pedaço da arte (ver PONTOS_DE_CORTE).
        corte = cenarios[cen].ponto_do_trecho(i_tr)
        cortes.append(f"{corte / max(cenarios[cen].faixa, 1):.2f}")

        # ONDE A CÂMERA CENTRA neste cenário: o meio do corpo, que depende
        # da linha do chão dele. Sem isto o zoom mira sempre a mesma altura
        # e corta os pés nos cenários de chão baixo.
        centro_corpo = None
        if base_pes and alt_corpo:
            centro_corpo = (cenarios[cen].chao_y - alt_corpo * 0.45) / H

        falante = tr.get("ator") if tr.get("ator") in elenco else padrao_ator
        # QUEM ESTÁ EM CENA MUDA DE TRECHO PARA TRECHO (30/08, noite). Dois
        # por vez continua sendo o teto (lei 10); o elenco do VÍDEO não tem
        # teto. `posto` dá o lugar de cada um dentro DESTE trecho, porque o
        # x de alguém é a divisão do quadro com quem está lá agora.
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
        # A ORDEM ESQUERDA→DIREITA é do TRECHO: é por ela que `_separar`
        # sabe para que lado empurrar quem invadiu, e ela só faz sentido
        # entre quem está dividindo o quadro agora.
        ordem_x = sorted(chaves, key=lambda c: posto[c][1])
        # O PLANO DESTE TRECHO: close em quem fala, ou o par no ciclo de
        # sempre. Decidido aqui porque depende de quantos estão em cena
        # AGORA, e isso muda de trecho para trecho (lei 10).
        fecha = _close_no_falante(i_tr, n_trechos, len(chaves))
        # O PLANO DO PAR SAI DA LARGURA MEDIDA, e sai UMA VEZ por trecho.
        # `meia_esq`/`meia_dir` são o núcleo de cada um, medidos na arte no
        # frame de repouso (lei 33), então isto é a mesma disciplina da
        # altura do ator (lei 38): o número vem do desenho, não de uma
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
        # quem entrou agora não tem estado de objeto: a mão começa vazia
        for c in chaves:
            na_mao.setdefault(c, None)
        por_ator = _acoes_por_ator(tr, chaves, falante)
        # A MÃO QUE SEGURA É A DE FORA, e quem decide é o motor: o
        # roteirista escreve `mao` sem saber quem está de que lado (ver
        # `acoes.mao_de_fora`). Feito UMA vez por trecho, sobre as ações
        # deste trecho, para que o estado do objeto e a pose do braço leiam
        # o MESMO valor -- se divergirem, o braço sobe vazio e o objeto
        # fica na mão caída.
        if len(chaves) > 1:
            for chave in chaves:
                fora = ACOES.mao_de_fora(posto[chave][1])
                for a in por_ator.get(chave) or []:
                    if a.get("nome") in ACOES.ACOES_OBJETO_MAO_DE_FORA:
                        a["mao"] = fora
        _fazer_voltar(por_ator, [c for c in fora_de_cena if c in chaves])
        fora_de_cena = _quem_saiu(por_ator)
        nf = max(1, int(tr["dur"] * FPS))
        cam = dict(ACOES.CAM_NEUTRA)
        for f in range(nf):
            fh = (f // 2) * 2                       # animar "em 2s"
            t = fh / max(1, nf - 1)
            nivel = env[n] if n < len(env) else 0.0

            # O QUE CADA UM TEM NA MÃO, ANTES do desvio da amostra. O
            # objeto é ESTADO: ele passa de mão num frame e continua lá nos
            # seguintes. Calcular isso só nos frames desenhados faz a
            # PRÉVIA mentir -- se nenhum quadro da amostra cair no instante
            # em que a entrega se completa, a mão de quem deu nunca esvazia
            # e a folha mostra os dois segurando a mesma caixa. Foi
            # exatamente o que aconteceu na rodada 10 do ciclo, e a caça ao
            # bug foi no motor até o teste isolado mostrar que o motor
            # estava certo. Custa microssegundos por frame pulado.
            for chave in chaves:
                na_mao[chave] = _objeto_na_mao(por_ator[chave], t, objetos,
                                               na_mao.setdefault(chave, None))
            _quem_recebe(por_ator, na_mao, t, objetos)
            # UM OBJETO, UMA MÃO. Quem toma da mão do outro fica com ele
            # (ver `_um_dono_so`); o que não dá para decidir vira aviso no
            # log, uma vez por render. O aviso é o que faz esta família de
            # bug parar de depender de alguém olhar a folha de contato no
            # quadro certo -- ela já apareceu de três jeitos diferentes.
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
            # ONDE FICOU CADA PEÇA DE QUEM FALA, para o close mirar no
            # ROSTO e não no meio do corpo, e para a guarda de
            # enquadramento saber onde está o OBJETO na mão dele. Só do
            # falante, e é um `dict.update` por frame desenhado.
            #
            # Era `{} if fecha else None`: o objeto precisa da caixa em todo
            # plano fechado, não só no close em quem fala -- foi com UM ator
            # sozinho que o celular saiu do quadro no v013.
            pecas_falante = {}
            cam_falante, x_falante = dict(ACOES.CAM_NEUTRA), W / 2
            # PRIMEIRO O RIG DE TODO MUNDO, DEPOIS O DESENHO. A colisão só
            # dá para resolver com as duas posições na mão, e resolver
            # depois de desenhar seria desenhar duas vezes.
            rigs, cams = {}, {}
            for chave in chaves:
                pers, x0, dy = posto[chave]
                rig, c = _rig_do_trecho(tr, t, corte, por_ator[chave], x0,
                                        falando=(chave == falante))
                # DOIS deslocamentos verticais, e a ordem importa:
                #  `dy`      põe este ator na mesma linha dos outros
                #            (_alinhar_pelos_pes, mede a folha de cada um);
                #  `dy_chao` põe essa linha no CHÃO DESENHADO do cenário.
                # Entram DEPOIS das ações porque pular e cair mexem no
                # quadril, e as duas correções acompanham o pulo.
                rig["quadril"] = [rig["quadril"][0],
                                  rig["quadril"][1] + dy + dy_chao]
                rigs[chave], cams[chave] = rig, c
            # QUEM FALA FICA NA FRENTE. A ordem é estável dentro do trecho
            # (o falante não muda no meio de uma fala), então nada pisca de
            # profundidade; e o braço de quem gesticula passa por cima do
            # outro, que é a leitura certa -- é ele que está agindo.
            atras_na_frente = [c for c in chaves if c != falante] + \
                              [c for c in chaves if c == falante]
            so_dele = {}
            for chave in atras_na_frente:
                pers, x0, dy = posto[chave]
                rig = rigs[chave]
                # a cara de QUEM FALA vem do trecho; quem ouve fica na cara
                # de reação que o roteirista der a ele, ou neutro
                cara = rosto.para(tr, t, tr["dur"], chave) if chave == falante \
                    else EXPR.obter(tr.get("expressao_" + chave, "neutro"))
                pisca = EXPR.piscando(n, FPS, semente=chaves.index(chave),
                                      expr_nome=tr.get("expressao", "neutro")
                                      if chave == falante else "neutro")
                # SÓ QUEM FALA MEXE A BOCA. Sem isto os dois abrem o
                # maxilar na mesma envoltória e ninguém sabe quem falou.
                so_dele[chave] = desenhar_personagem(
                    pers, rig, nivel if chave == falante else 0.0,
                    pisca, na_mao[chave], cara,
                    saida_pos=pecas_falante if chave == falante else None)
            # CADA UM SE DEFORMA SOZINHO. Espelhar, achatar e o squash da
            # passada são do corpo de quem fez a ação, não do quadro (ver
            # `deformar_ator`). Vem ANTES da guarda de colisão porque
            # achatar muda a largura do corpo, e é a largura depois de
            # deformado que não pode invadir o outro.
            for chave in chaves:
                so_dele[chave] = deformar_ator(so_dele[chave], cams[chave],
                                               rigs[chave]["quadril"][0])
            # A CÂMERA SEGUE QUEM ANDA, E QUEM FICA PARADO FICA PARA TRÁS
            # (30/08, noite).
            #
            # O defeito, descrito pelo dono do projeto ao ver o vídeo: *"um
            # personagem andou e o cenário se mexeu, o outro flutuou com o
            # cenário mudando e ele ficando no mesmo enquadramento"*. Ele
            # está certo, e eram DOIS erros somados:
            #
            #  1. `cam = cam_falante` -- a câmera seguia o `fundo_dx` de
            #     quem FALA, não de quem ANDA. Se quem andava estava calado,
            #     o fundo nem se mexia; e o pé andava no lugar, que é o
            #     patinar clássico que `andar` existe para evitar;
            #  2. o deslocamento ia só para o CENÁRIO. Quem está parado no
            #     mundo é estático em relação ao chão, então numa câmera que
            #     acompanha ele tem de correr na tela junto com o fundo. Sem
            #     isso, os dois ficam colados na mesma posição de tela e a
            #     cena inteira escorrega -- a mesma leitura errada da lei 26,
            #     agora com o personagem no lugar do fundo.
            #
            # A conta é uma linha: cada ator anda na TELA o que a CÂMERA
            # andou menos o que ELE andou. Quem anda dá zero (a câmera o
            # segue, ele fica no lugar). Quem está parado dá o pan inteiro, e
            # sai do quadro se o passeio for longo o bastante -- que é
            # exatamente "ficar para trás e sumir do enquadramento".
            #
            # Vem DEPOIS de `deformar_ator` e ANTES de `_separar`: a colisão
            # tem de medir onde os corpos ficaram de verdade, senão ela
            # separa duas silhuetas que já não estão mais ali.
            pans = {c: float(cams[c].get("pan_camera", 0.0)) for c in chaves}
            dx_camera = max(pans.values(), key=abs) if pans else 0.0
            if dx_camera:
                for chave in chaves:
                    dx_tela = dx_camera - pans[chave]
                    if abs(dx_tela) >= 1.0:
                        so_dele[chave] = _transladar(so_dele[chave], dx_tela)
                        rigs[chave]["quadril"][0] += dx_tela
            # NINGUÉM ATRAVESSA NINGUÉM: medido no frame pronto, corrigido
            # transladando a camada (ver `_separar`)
            ceder = _separar(so_dele, ordem_x)
            if ceder:
                for chave, dx in ceder.items():
                    so_dele[chave] = _transladar(so_dele[chave], dx)
                    rigs[chave]["quadril"][0] += dx
                    n_empurrados[chave] = n_empurrados.get(chave, 0) + 1
            # NO CLOSE, QUEM NÃO ESTÁ SENDO ENQUADRADO NÃO ENTRA NO QUADRO
            # (31/08, defeito 3 dos vídeos: *"quando tem dois personagens na
            # cena e dá zoom em um único personagem andando, o outro buga e
            # aparece vindo no fundo"*).
            #
            # O close já mira só o falante e a janela já é estreita o
            # bastante para deixar o outro de fora -- PARADO. Quando alguém
            # ANDA, a câmera acompanha quem anda e quem está parado corre na
            # tela junto com o fundo (é o travelling de 30/08, e está
            # certo): o parceiro atravessa a janela do close deslizando, do
            # lado a lado, no meio da fala do outro. Na folha do teste ele
            # aparece inteiro ao lado do falante, depois metade, depois
            # nada.
            #
            # Cortar a câmera não resolve -- ele está mesmo passando por
            # ali. O que resolve é o que o close SIGNIFICA: este plano
            # enquadra UM ator. Quem não é o enquadrado fica fora do
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
            # O FUNDO SEGUE A CÂMERA, NÃO O FALANTE. `cam_falante` traz o
            # `pan_base` do trecho (o ponto de corte do cenário) somado ao
            # deslocamento de quem fala; o passeio tem de vir de quem ANDA.
            # As duas partes se somam aqui, e uma só vez.
            cam["fundo_dx"] = (float(cam.get("fundo_dx", 0.0))
                               - float(cam_falante.get("pan_camera", 0.0))
                               + dx_camera)
            # a sombra de contato mira o chão DESENHADO, que agora é onde os
            # pés estão de verdade
            cam["chao_y"] = cenarios[cen].chao_y
            # ENQUADRAMENTO DO TRECHO, por cima do que a ação já pediu: a
            # ação usa zoom para pontuar um susto, e isso continua valendo
            # -- os dois se multiplicam em vez de um apagar o outro.
            # A MIRA DO CLOSE É A CABEÇA DE QUEM FALA, não o meio do corpo.
            # O pivô do crânio é a base dele (é por onde ele se prende ao
            # pescoço), então o alto da cabeça está uma altura de crânio
            # acima; a janela põe esse alto a 12% do topo, e o resto dela
            # desce pelo tronco. Sem o crânio -- folha sem cabeça separada
            # -- cai no centro do corpo, que é o comportamento de antes.
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
            cam["zoom"] = float(cam.get("zoom", 1.0)) * z_tr
            # A MIRA DA AÇÃO É RELATIVA AO CORPO, NÃO À TELA (29/08).
            #
            # Uma ação pode querer olhar mais para cima -- o `susto` pede
            # `zoom_y: 0.34`, que era "o rosto" quando o personagem ficava
            # a 78% do quadro. Desde que os pés passaram a pousar no chão
            # DESENHADO (§4.42), ele pode estar a 95%, e 0,34 deixou de ser
            # o rosto para virar o teto: na rodada 3 do ciclo, dois terços
            # do quadro eram prateleira e os dois apareciam cortados no
            # rodapé.
            #
            # O que a ação sabe é o DESVIO que ela quer (0,34 - 0,50 =
            # subir 0,16), não a altura absoluta. O desvio se aplica a
            # partir do centro do corpo que `_enquadramento` calculou para
            # este cenário, e o clamp mantém a janela dentro do quadro.
            zy_acao = float(cam.get("zoom_y", 0.5))
            alvo = zy + (zy_acao - 0.5)
            meia = 0.5 / max(cam["zoom"], 1e-6)
            cam["zoom_y"] = max(meia, min(1.0 - meia, alvo))
            # O MEIO DE QUEM ESTÁ EM CENA, para a câmera fechar ali. Só
            # conta quem tem o corpo dentro do quadro: quem está entrando
            # ou saindo puxaria o enquadramento para fora junto com ele.
            dentro = [rigs[c]["quadril"][0] for c in chaves
                      if 0 < rigs[c]["quadril"][0] < W]
            # NO CLOSE A CÂMERA MIRA UM SÓ, e é a silhueta DELE que limita
            # o quanto ela fecha (ver `montar_frame`): a do par somado
            # travaria o plano em 1,33 e o close não aconteceria.
            quadro = montar_frame(camada, cenarios[cen], cam, x_falante,
                                  camadas=por_ator_camada,
                                  centro_x=(x_falante if fecha else
                                            (sum(dentro) / len(dentro)
                                             if dentro else None)),
                                  camada_alvo=(so_dele.get(falante)
                                               if fecha else None),
                                  terco=_terco_do_trecho(i_tr, len(chaves)),
                                  caixa_extra=pecas_falante.get("_objeto"))
            if leg is not None:
                # por cima de tudo, e no tempo GLOBAL: o índice do frame é
                # contínuo entre trechos, então n/FPS é o relógio do vídeo
                leg.desenhar(quadro, n / float(FPS))
            # COMPRESSÃO 1, NÃO A PADRÃO 6. Estes PNG existem por segundos:
            # o ffmpeg os lê na linha seguinte e a pasta é temporária.
            # Medido num frame 1080x1920: 614 ms com a compressão padrão,
            # que era 31% do tempo TOTAL de render -- mais do que montar o
            # quadro inteiro. Comprimir com afinco um arquivo que ninguém
            # guarda é trabalho puro.
            quadro.save(os.path.join(fd, f"{n:05d}.png"), compress_level=1)
            if quero is not None:
                # a folha guarda o relógio: defeito achado numa amostra sem
                # o segundo obriga a reabrir o vídeo para saber onde está
                colhidos.append((n / float(FPS), quadro))
            n += 1
        for chave in chaves:
            rosto.fechar(chave)
        caras.append(EXPR.normalizar(tr.get("expressao", "neutro"))
                     + "".join("+" + EXPR.normalizar(j.get("nome") or j.get("valor"))
                               for j in (tr.get("expressoes") or [])))
        # O LOG DIZ QUAL PLANO FOI, não só o número: "1.90*" é o close em
        # quem fala, e é o único jeito de ler no log que a alternância
        # aconteceu sem abrir o MP4.
        planos.append(
            f"{_enquadramento(i_tr, n_trechos, len(chaves), 0.0, close=fecha, teto_par=teto_par)[0]:.2f}"
            + ("*" if fecha else ""))
        # O PAN DA CAMINHADA NÃO ATRAVESSA O CORTE. Ele acumulava de trecho
        # em trecho, de quando o fundo era um ladrilho infinito; agora cada
        # trecho começa no ponto que `PONTOS_DE_CORTE` manda, e um resto de
        # deslocamento vindo de trás só desalinharia esse ponto.
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

    # O TAMANHO DO ARQUIVO VIROU RESTRIÇÃO (30/08). O Storage do Supabase
    # recusa objeto acima do teto do plano, e o primeiro vídeo de 88 s
    # voltou `413 Payload too large` DEPOIS de 15 minutos de render: o job
    # inteiro perdido no upload, com o MP4 pronto no runner.
    #
    # Enquanto a esquete tinha 17 s isso nunca aparecia. Com 40 a 80 s o
    # arquivo quadruplica, e o CRF 21 -- escolhido sem pensar em tamanho --
    # passa do teto. Arte chapada de traço comprime muito bem: 23 é
    # visualmente indistinguível aqui e corta perto de um terço. O
    # `maxrate`/`bufsize` cortam o PICO, que é o que estoura a média num
    # vídeo com corte de plano a cada trecho.
    def _encodar(crf, maxrate):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
                        "-i", os.path.join(fd, "%05d.png"), "-i", audio,
                        "-af", spec.get("loudnorm", "loudnorm=I=-9:LRA=8:TP=-1.5"),
                        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                        "-maxrate", maxrate, "-bufsize", "8M",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                        "-shortest", "-movflags", "+faststart", saida], check=True)

    _encodar(23, "4M")
    # REDE DE SEGURANÇA: se ainda passar do teto, reencoda mais apertado em
    # vez de deixar o upload falhar. Perder qualidade é ruim; perder o vídeo
    # inteiro depois de 15 min de render é pior.
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
