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
from folha_personagem import (ESQUELETO, ORDEM_Z, FONTE_ANGULO,
                              CORRECAO_POSE_T, SEGUE)

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
        self.img, self.piv = {}, {}
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
            self.img[nome], self.piv[nome] = _centralizar(im, pivo)

    def p(self, nome):
        return self.img[nome], self.piv[nome]

    def tem(self, nome):
        return nome in self.img


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


def desenhar_personagem(pers, rig, boca_nivel=0.0, piscando=False, objeto=None):
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

        img, piv = pers.p(nome)
        colar(base, img, piv, pos[nome], ang[nome], e)

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
            piscando = (n % 82) in (0, 1)

            camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            cam_falante, x_falante = dict(ACOES.CAM_NEUTRA), W / 2
            for chave in chaves:
                pers, x0 = elenco[chave]
                rig, c = _rig_do_trecho(tr, t, pan, por_ator[chave], x0)
                # SÓ QUEM FALA MEXE A BOCA. Sem isto os dois abrem o
                # maxilar na mesma envoltória e ninguém sabe quem falou.
                obj = None
                for a in por_ator[chave]:
                    if a.get("objeto") in objetos and float(a.get("de", 0)) <= t <= float(a.get("ate", 1)):
                        obj = {"img": objetos[a["objeto"]], "mao": a.get("mao", "d"),
                               "escala": a.get("escala_objeto", 1.0)}
                camada.alpha_composite(
                    desenhar_personagem(pers, rig, nivel if chave == falante else 0.0,
                                        piscando, obj))
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
        pan = cam.get("fundo_dx", pan)              # continua de onde parou
    print(f"[cutout] {n} frames ({n/FPS:.1f}s)")

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
