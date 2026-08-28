#!/usr/bin/env python3
"""
topo -- a faixa de cima do quadro, que estava vazia.

POR QUE ISTO EXISTE (27/08 a noite)
    Com dois personagens em cena o corpo dos dois ocupa da metade da altura
    para baixo, e a legenda mora a 74%. Sobra um quinto da tela -- de 0 a
    ~22% -- de parede lisa, do primeiro ao ultimo frame. Num formato em que
    a pessoa decide em dois segundos se continua rolando, esse quinto e o
    pedaco que o olho encontra primeiro e o unico que nunca teve nada.

O QUE A REFERENCIA DIZ (pesquisa de 27/08)
    Tres coisas se repetem em quem faz esquete curta que retem:

    1. a zona segura do 9:16 vai de ~15% a ~75% da altura -- acima disso a
       UI do app come o quadro, abaixo os botoes de curtir e compartilhar.
       O que entrar no alto tem que comecar depois de ~9%;
    2. o texto de GANCHO no alto e o que segura quem assiste no mudo: ele
       diz do que e a piada antes de a fala chegar la, e uma enfase bem
       posta entre 2 e 4 segundos e o que evita a saida;
    3. texto parado nao conta como movimento. O que prende e tipografia
       CINETICA -- algo que entra, respira e troca.

O QUE ENTROU, E POR QUE ESTAS DUAS COISAS
    1. CARTAO DE TRECHO. Uma tarja com tres a cinco palavras que nomeiam o
       que esta acontecendo agora ("A ASSINATURA FANTASMA", "TENTANDO
       CANCELAR", "A CONTA FINAL"). Ela ENTRA a cada trecho -- com
       deslize e passada do ponto -- e nunca fica parada: respira de leve
       e inclina de leve o tempo todo. E o equivalente barato do corte de
       plano: alguma coisa muda quando o assunto muda.

       O texto vem do roteirista (`manchete` no trecho ou no spec). Sem
       ele, o motor monta a tarja com as primeiras palavras da fala -- e
       um cartao com a propria frase ainda e melhor que parede lisa.

    2. PICTOGRAMAS DE REACAO. Simbolos desenhados em codigo -- raio,
       gota, exclamacao, interrogacao, estrela, cifrao -- que sobem pela
       faixa vazia e somem, disparados pela EMOCAO do trecho e do lado de
       quem esta sentindo. E a mesma regra que vale para o som (§4.16 do
       ESTADO): so sai o que tem causa na tela. Nao ha arte nova nenhuma:
       tudo e poligono e glifo da mesma fonte da legenda.

O QUE ISTO NAO E
    Nao e legenda no alto. Por o texto da fala aqui em cima resolveria o
    vazio e quebraria a leitura -- o olho perseguiria a boca embaixo e a
    palavra em cima. A legenda continua a 74%, e mover para o alto so
    acontece se o spec pedir (`legenda_y`), que era o ultimo caso.
"""
import math

from PIL import Image, ImageDraw

from legendas import _fonte

# --- geometria da faixa (fracoes da altura do quadro) ------------------
# O cartao comeca depois da UI do app: em Shorts a barra de cima come
# cerca de 8% da tela.
CARTAO_Y = 0.135                 # centro do cartao
# Os pictogramas sobem ABAIXO da tarja, nunca por tras dela: na primeira
# previa a exclamacao passava por dentro do cartao e as duas coisas se
# anulavam. A faixa deles comeca onde o cartao acaba e para antes da
# cabeca de quem esta em cena.
FAIXA_ALTA, FAIXA_BAIXA = 0.205, 0.325

COR_FUNDO = (22, 19, 17, 226)
COR_BORDA = (255, 211, 77, 255)      # o mesmo ambar da palavra ativa
COR_TEXTO = (255, 255, 255, 255)

# --- reacao por emocao -------------------------------------------------
# So emocao com reacao FISICA reconhecivel entra. `neutro`, `sorrindo` e
# `pensando` nao disparam nada: pictograma sem causa e o mesmo defeito que
# o som decorativo tinha (ESTADO §4.16), e aqui ele custaria mais, porque
# fica na parte do quadro para onde o olho vai primeiro.
DA_EMOCAO = {
    "bravo":       ("raio", (255, 92, 74)),
    "irritado":    ("raio", (255, 138, 74)),
    "chocado":     ("exclamacao", (255, 211, 77)),
    "surpreso":    ("exclamacao", (255, 233, 120)),
    "desesperado": ("gota", (146, 214, 255)),
    "triste":      ("gota", (126, 168, 224)),
    # branco e cinza somem contra parede clara, e metade dos cenarios e
    # parede clara: toda cor daqui tem que sobreviver ao fundo mais claro
    # que existe no catalogo
    "duvida":      ("interrogacao", (108, 196, 255)),
    "confiante":   ("estrela", (255, 211, 77)),
    "desdem":      ("estrela", (176, 152, 232)),
}

# Ação que merece pictograma: o mesmo teste do som -- quem visse o quadro
# no mudo entenderia de onde veio.
DA_ACAO = {
    "susto":        ("exclamacao", (255, 211, 77)),
    "cair":         ("estrela", (255, 233, 120)),
    "tropecar":     ("estrela", (255, 233, 120)),
    "comemorar":    ("estrela", (255, 211, 77)),
    "maos_na_cabeca": ("gota", (146, 214, 255)),
    "negar":        ("raio", (255, 138, 74)),
}

DENSIDADE_S = 1.2        # nunca dois disparos a menos disto um do outro
VIDA_S = 1.15            # quanto tempo um pictograma fica no ar


# =====================================================================
# Desenho dos pictogramas (nenhuma arte externa)
# =====================================================================
def _tile(lado):
    im = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def _glifo(lado, texto, cor):
    """Simbolo que a fonte da legenda ja tem, com contorno grosso."""
    im, d = _tile(lado)
    f = _fonte(int(lado * 0.92))
    d.text((lado / 2, lado / 2), texto, font=f, anchor="mm", fill=cor + (255,),
           stroke_width=max(3, lado // 14), stroke_fill=(18, 15, 13, 255))
    return im


def _raio(lado, cor):
    im, d = _tile(lado)
    u = lado / 100.0
    pts = [(58 * u, 4 * u), (24 * u, 54 * u), (46 * u, 54 * u),
           (38 * u, 96 * u), (78 * u, 40 * u), (54 * u, 40 * u), (70 * u, 4 * u)]
    d.polygon(pts, fill=cor + (255,), outline=(18, 15, 13, 255),
              width=max(3, lado // 16))
    return im


def _gota(lado, cor):
    """Gota de suor: a ponta em cima, a barriga embaixo -- e o desenho que
    se le como gota mesmo com 60px de lado."""
    im, d = _tile(lado)
    u = lado / 100.0
    d.polygon([(50 * u, 6 * u), (22 * u, 58 * u), (78 * u, 58 * u)],
              fill=cor + (255,))
    d.ellipse([20 * u, 34 * u, 80 * u, 94 * u], fill=cor + (255,))
    # contorno por cima das duas formas, senao a emenda aparece
    d.polygon([(50 * u, 6 * u), (20 * u, 62 * u), (80 * u, 62 * u)],
              outline=(18, 15, 13, 255), width=max(3, lado // 18))
    d.ellipse([20 * u, 34 * u, 80 * u, 94 * u],
              outline=(18, 15, 13, 255), width=max(3, lado // 18))
    # brilho: sem ele a gota lê como pingo de tinta
    d.ellipse([34 * u, 52 * u, 47 * u, 68 * u], fill=(255, 255, 255, 190))
    return im


def _estrela(lado, cor):
    im, d = _tile(lado)
    r, c = lado * 0.46, lado / 2.0
    pts = []
    for k in range(10):
        ang = math.radians(-90 + k * 36)
        raio = r if k % 2 == 0 else r * 0.44
        pts.append((c + raio * math.cos(ang), c + raio * math.sin(ang)))
    d.polygon(pts, fill=cor + (255,), outline=(18, 15, 13, 255),
              width=max(3, lado // 18))
    return im


def _pictograma(tipo, lado, cor):
    if tipo == "raio":
        return _raio(lado, cor)
    if tipo == "gota":
        return _gota(lado, cor)
    if tipo == "estrela":
        return _estrela(lado, cor)
    return _glifo(lado, {"exclamacao": "!", "interrogacao": "?",
                         "cifrao": "$"}.get(tipo, "!"), cor)


# =====================================================================
def _quebrar(d, texto, fonte, util):
    """Ate duas linhas. Tarja de tres linhas deixa de ser tarja e vira
    paragrafo -- e paragrafo no alto do quadro ninguem le."""
    palavras = texto.split()
    linhas, atual = [], ""
    for p in palavras:
        tenta = (atual + " " + p).strip()
        if atual and d.textlength(tenta, font=fonte) > util:
            linhas.append(atual)
            atual = p
            if len(linhas) == 2:
                break
        else:
            atual = tenta
    if atual and len(linhas) < 2:
        linhas.append(atual)
    return linhas or [texto]


def _suave(k):
    """Entrada com passada do ponto: sobe rapido, passa um pouco e volta.
    E o que faz o cartao parecer que tem peso em vez de aparecer."""
    if k >= 1.0:
        return 1.0
    return 1.0 - (2 ** (-9 * k)) * math.cos(k * 11.0)


class Topo:
    """A camada de cima. Desenhada DEPOIS do zoom, como a legenda: ela e
    grudada na tela, nao na cena -- se acompanhasse o enquadramento,
    fecharia junto com a camera e sairia pela borda."""

    def __init__(self, largura, altura, cartoes=(), reacoes=(), tamanho=None):
        self.W, self.H = largura, altura
        # ~73px em 1920: menor que a legenda (92px), que continua sendo a
        # informacao principal, e grande o bastante para se ler no feed
        self.tam = tamanho or int(altura * 0.038)
        self.fonte = _fonte(self.tam)
        self.cartoes = [c for c in cartoes if (c.get("texto") or "").strip()]
        self.reacoes = list(reacoes)
        self._arte = {}                                 # cartao -> tile pronto
        self._pict = {}                                 # (tipo, cor) -> tile

    # --- cartao --------------------------------------------------------
    def _tarja(self, texto):
        """Monta a tarja UMA vez. Refazer o texto a cada frame custa mais
        que compor o quadro inteiro num video de 400 frames."""
        if texto in self._arte:
            return self._arte[texto]
        medida = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        util = self.W * 0.76
        linhas = _quebrar(medida, texto.upper(), self.fonte, util)
        larg = max(medida.textlength(s, font=self.fonte) for s in linhas)
        pad_x, pad_y = self.tam * 0.75, self.tam * 0.42
        alt_linha = self.tam * 1.22
        cw = int(min(larg + 2 * pad_x, self.W * 0.92))
        ch = int(alt_linha * len(linhas) + 2 * pad_y)
        # folga em volta para o contorno e a inclinacao nao serem cortados
        folga = int(self.tam * 0.6)
        im = Image.new("RGBA", (cw + 2 * folga, ch + 2 * folga), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        raio = int(ch * 0.34)
        d.rounded_rectangle([folga, folga, folga + cw, folga + ch], radius=raio,
                            fill=COR_FUNDO, outline=COR_BORDA,
                            width=max(3, self.tam // 14))
        y = folga + pad_y + alt_linha / 2
        for s in linhas:
            d.text((folga + cw / 2, y), s, font=self.fonte, anchor="mm",
                   fill=COR_TEXTO)
            y += alt_linha
        self._arte[texto] = im
        return im

    def _desenhar_cartao(self, quadro, t):
        atual = None
        for c in self.cartoes:
            if c["de"] <= t < c["ate"]:
                atual = c
                break
        if atual is None:
            return
        im = self._tarja(atual["texto"])
        dentro = t - atual["de"]
        restante = atual["ate"] - t
        # entra deslizando de cima com passada do ponto; sai subindo
        k = _suave(min(1.0, dentro / 0.42))
        alfa = 1.0
        if restante < 0.22:
            k += (1.0 - max(restante, 0.0) / 0.22) * 0.9
            alfa = max(0.0, restante / 0.22)
        dy = (1.0 - k) * -(self.H * 0.14)
        # RESPIRO: o cartao nunca fica parado. Duas ondas de periodo
        # diferente para o movimento nao virar metronomo.
        dy += math.sin(t * 2.6) * self.tam * 0.09
        tilt = math.sin(t * 1.7 + 0.9) * 1.1

        tile = im.rotate(tilt, Image.BICUBIC, expand=False)
        if alfa < 0.999:
            a = tile.split()[-1].point(lambda v: int(v * alfa))
            tile = tile.copy()
            tile.putalpha(a)
        x = int((self.W - tile.width) / 2)
        y = int(self.H * CARTAO_Y - tile.height / 2 + dy)
        quadro.paste(tile, (x, y), tile)

    # --- pictogramas ---------------------------------------------------
    def _tile_pict(self, tipo, cor):
        chave = (tipo, cor)
        if chave not in self._pict:
            self._pict[chave] = _pictograma(tipo, int(self.H * 0.075), cor)
        return self._pict[chave]

    def _desenhar_reacoes(self, quadro, t):
        for r in self.reacoes:
            k = (t - r["em"]) / VIDA_S
            if not (0.0 <= k <= 1.0):
                continue
            base = self._tile_pict(r["tipo"], r["cor"])
            # pop na entrada, subida constante, some no ultimo terco
            esc = 1.15 * _suave(min(1.0, k / 0.16)) if k < 0.16 else \
                1.15 - 0.15 * min(1.0, (k - 0.16) / 0.3)
            alfa = 1.0 if k < 0.58 else max(0.0, 1.0 - (k - 0.58) / 0.42)
            lado = max(8, int(base.width * esc))
            tile = base.resize((lado, lado), Image.LANCZOS)
            tile = tile.rotate(math.sin(k * 6.0 + r["fase"]) * 13.0,
                               Image.BICUBIC, expand=False)
            a = tile.split()[-1].point(lambda v: int(v * alfa))
            tile.putalpha(a)
            y0 = self.H * FAIXA_BAIXA
            y = y0 - (y0 - self.H * FAIXA_ALTA) * k
            x = self.W * r["x"] + math.sin(k * 4.2 + r["fase"]) * self.W * 0.022
            quadro.paste(tile, (int(x - lado / 2), int(y - lado / 2)), tile)

    def desenhar(self, quadro, t):
        self._desenhar_cartao(quadro, t)
        self._desenhar_reacoes(quadro, t)
        return quadro


# =====================================================================
def _resumo(fala, palavras=5):
    """Tarja de emergencia quando o roteirista nao mandou manchete."""
    p = [w for w in (fala or "").split() if w][:palavras]
    return " ".join(p).rstrip(",.;:!?") if p else ""


def do_spec(spec, largura, altura):
    """Monta a camada de cima a partir do que o spec ja diz.

    Nada aqui e novo pedido ao roteirista: `manchete` e opcional, e a
    emocao de cada trecho ja e obrigatoria desde 28/08. Sem manchete
    nenhuma o motor ainda monta a tarja com o comeco da fala."""
    if not spec.get("topo", True):
        return None
    cartoes, reacoes, ultimo = [], [], -99.0
    n = len(spec.get("trechos") or [])
    for i, tr in enumerate(spec.get("trechos") or []):
        t0 = float(tr.get("_inicio_s", 0.0))
        dur = float(tr.get("dur", 0.0))
        texto = (tr.get("manchete") or "").strip()
        if not texto and i == 0:
            texto = (spec.get("manchete") or "").strip() or _resumo(tr.get("fala"))
        elif not texto:
            texto = _resumo(tr.get("fala"))
        # A tarja e CONTINUA: cada uma vai ate o comeco da seguinte, e a
        # troca acontece na emenda -- a que sai sobe enquanto a que entra
        # desce. Na primeira previa elas tinham folga entre si e a faixa de
        # cima voltava a ficar vazia justamente na virada de assunto.
        # A ULTIMA e a excecao: ela larga o quadro antes do fim para a
        # tirada ficar so com a cara e a legenda, que e onde a piada cai.
        fim = t0 + dur * (0.80 if i == n - 1 else 1.0)
        cartoes.append({"de": t0, "ate": fim, "texto": texto})

        # De que lado o simbolo sai: em cima de QUEM ESTA SENTINDO -- e quem
        # sente nem sempre e quem fala. Na esquete de teste, o Pal levava as
        # maos a cabeca enquanto o Zeca dava a tirada, e as gotas de suor
        # subiam do lado do Zeca. A acao ja diz de quem ela e (`ator`); a
        # emocao do trecho e de quem fala.
        ordem = list(spec.get("elenco") or {})

        def _lado(ator):
            if len(ordem) < 2:
                return 0.5
            k = ordem.index(ator) if ator in ordem else 0
            return 0.29 if k == 0 else 0.71

        falante = tr.get("ator")
        marcas = [(t0 + dur * 0.10, tr.get("expressao"), DA_EMOCAO, falante)]
        for e in (tr.get("expressoes") or []):
            marcas.append((t0 + dur * float(e.get("de", 0.0)) + 0.05,
                           e.get("nome") or e.get("valor"), DA_EMOCAO,
                           e.get("ator") or falante))
        for a in (tr.get("acoes") or []):
            marcas.append((t0 + dur * float(a.get("de", 0.0)) + 0.05,
                           a.get("nome"), DA_ACAO, a.get("ator") or falante))
        for em, nome, tabela, ator in sorted(marcas, key=lambda m: m[0]):
            par = tabela.get((nome or "").strip().lower())
            if not par or em - ultimo < DENSIDADE_S:
                continue
            ultimo = em
            tipo, cor = par
            lado = _lado(ator)
            # tres de uma vez: um simbolo solitario lê como erro de render,
            # tres leem como reacao de desenho animado
            for j in range(3):
                reacoes.append({"em": em + j * 0.09, "tipo": tipo, "cor": cor,
                                "x": lado + (j - 1) * 0.075,
                                "fase": j * 2.1 + em})
    t = Topo(largura, altura, cartoes, reacoes)
    print(f"[topo] {len(cartoes)} cartoes e {len(reacoes)//3} reacoes na faixa de cima")
    return t
