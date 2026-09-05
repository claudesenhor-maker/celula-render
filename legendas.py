#!/usr/bin/env python3
"""
legendas — legenda queimada, palavra por palavra, no ritmo real da fala.

POR QUE ISTO EXISTE
    Short se assiste no mudo. Legenda nao e acessibilidade opcional aqui,
    e o que faz o video ser entendido antes de o espectador decidir subir
    o dedo -- e o formato "uma palavra estourando por vez" e o que segura
    atencao no feed. Estava listado como F5 no HANDOFF e nunca foi feito.

DE ONDE VEM O TEMPO
    O Edge-TTS devolve WordBoundary: para cada palavra sintetizada, o
    offset e a duracao em unidades de 100ns. Ou seja, o tempo exato de
    cada palavra ja existia -- `palito_cutout.render` simplesmente jogava
    fora as marcas (`_, dur = sintetizar(...)`). Nao se estima nada aqui,
    pelo mesmo motivo pelo qual a timeline vem da duracao real do audio:
    estimativa desincroniza, e legenda fora de sincronia e pior que
    legenda nenhuma.

    O ElevenLabs nao devolve marcas, e o Edge as vezes devolve audio sem
    nenhum WordBoundary. Nesses casos cai no reparto proporcional ao
    tamanho das palavras -- pior, mas ainda legivel, e nunca deixa o
    video mudo de texto.

COMO SE LE NA TELA
    Blocos de ate 3 palavras, porque uma palavra so obriga o olho a
    resetar a cada 300ms e a linha inteira vira parede de texto. Dentro do
    bloco, a palavra que esta soando fica em destaque -- e isso que da a
    leitura de "acompanhando a fala" sem precisar animar nada.

O QUE MUDOU EM 29/08
    1. TAMANHO. A legenda ocupava 3,8% da altura e no feed, num telefone,
       ela competia em tamanho com a costura da camisa do personagem.
       Passou para 4,8% -- que e a faixa em que os canais de corte de
       podcast trabalham -- e a palavra que esta soando cresce mais 12%.
    2. A ULTIMA PALAVRA. No video de 28/08 o punchline ("bloqueado") ficou
       sem legenda: o edge-tts devolveu 9 WordBoundary para uma fala de 10
       palavras, e o codigo confiava cegamente na contagem de marcas. Uma
       fala pode perder qualquer palavra pelo caminho, mas perder a ULTIMA
       e perder a piada. Agora o texto manda: `_casar` garante uma entrada
       por palavra escrita, estimando o tempo das que faltarem.
"""
import os
from PIL import Image, ImageDraw, ImageFont

# Fica ACIMA da faixa de baixo: no app do YouTube o titulo, o @canal e os
# botoes comem os ultimos ~18% da tela, e legenda embaixo demais e legenda
# tapada.
#
# DESCEU DE 0,74 PARA 0,80 EM 31/08 (volta 1 do ciclo de video). Em 0,74 ela
# caia sobre o TRONCO dos personagens e, pior, na altura em que a MAO fica
# quando o braco esta caido -- entao todo gesto de mao acontecia atras do
# texto. O plano de melhorias pedia exatamente isso ("evitar cobrir maos,
# celulares ou gestos; manter a regiao central mais livre").
#
# 0,80 e o maior valor que ainda sobra: os ultimos ~18% sao da interface do
# YouTube, entao 0,82 ja e risco de legenda tapada. O que se ganha e a faixa
# das maos; o que se perde e nada -- ali embaixo so ha perna.
#
# Este numero so faz sentido porque os pes pousam no chao DESENHADO (lei 27,
# §4.42): com o personagem a 95% da altura, o corpo ocupa de ~45% a ~95% e a
# legenda tem de escolher em que parte dele encostar. Antes de 28/08, com o
# boneco flutuando a 78%, 0,74 caia abaixo dos pes.
Y_RELATIVO = 0.80

# PALAVRA QUE NAO FECHA BLOCO (31/08, volta 3 do ciclo de video).
#
# A legenda quebrava a cada 3 palavras contadas, e o video 003 mostrou o
# resultado na tela: "MEU PIX PRA" / "FALHOU, O APP", "AINDA SALVAR O" /
# "O PRAZO ACABE?". O bloco terminava em preposicao, artigo ou conjuncao --
# palavras que so fazem sentido colada na seguinte --, e quem le tem de
# segurar meia expressao ate o proximo bloco aparecer.
#
# Num Short cada bloco fica ~0,8 s no ar. Terminar em "pra" custa a leitura
# inteira daquele bloco, e o plano de melhorias pedia exatamente isto:
# "quebrar frases em blocos menores" que se leiam sozinhos.
#
# A regra e so uma: se a ULTIMA palavra do bloco e uma destas, ela desce
# junto com a proxima. Nao e analise sintatica -- e a lista fechada das
# palavras que, em portugues, nunca terminam uma unidade de leitura.
PRESAS = frozenset("""
a o as os um uma uns umas de do da dos das em no na nos nas por pra pro
para com sem sob sobre entre ate ate' e ou mas que se ao aos a` as` num numa
meu minha meus minhas teu tua seu sua nosso nossa este esta esse essa aquele
aquela isso isto seu ja nao muito mais tao
""".split())

COR_TEXTO = (255, 255, 255, 255)


def _agrupar(palavras, por_bloco):
    """Blocos de `por_bloco` palavras que NAO terminam em palavra presa.

    O bloco pode crescer ate `por_bloco + 2`: parar de crescer em algum
    ponto importa mais que a regra, senao uma sequencia de preposicoes
    ("de um dos das") juntaria a fala inteira num bloco so e a legenda
    deixaria de acompanhar a voz.
    """
    saida, i, n = [], 0, len(palavras)
    while i < n:
        fim = min(i + por_bloco, n)
        # cresce enquanto a ultima for presa e ainda houver folga
        while (fim < n and fim - i < por_bloco + 2
               and str(palavras[fim - 1].get("txt", "")).strip(",.!?;:—-").lower()
               in PRESAS):
            fim += 1
        # a sobra de UMA palavra nao vira bloco proprio: ela entra neste
        if n - fim == 1:
            fim = n
        saida.append(palavras[i:fim])
        i = fim
    return saida
COR_ATIVA = (255, 211, 77, 255)      # ambar: destaca sem competir com a pele
COR_BORDA = (16, 14, 12, 255)
COR_SOMBRA = (0, 0, 0, 150)

# A palavra que esta soando e desenhada maior. O destaque so por cor
# desaparece quando o fundo do quadro e claro (a rua de 28/08 e rosa), e
# tamanho e uma diferenca que sobrevive a qualquer cenario.
ESCALA_ATIVA = 1.12

# Fontes na ordem em que se acha uma: runner Ubuntu primeiro (e onde a
# producao roda), depois Windows (e onde se confere antes de gastar render).
CANDIDATAS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
]


# A FONTE DO TÍTULO É OUTRA, DE PROPÓSITO (04/09, item 2 do dono do projeto:
# *"no texto superior colocar uma fonte diferente com fundo para chamar
# atenção"*).
#
# Legenda e título fazem trabalhos diferentes e por isso não podem ter a mesma
# cara: a legenda acompanha a boca e se lê no impulso; o título é um cartaz --
# ele para o polegar. Duas famílias na mesma tela só ficam ruins quando as
# duas disputam a mesma função; aqui elas se dividem.
#
# A ordem prefere CONDENSADA e depois BLACK/HEAVY: letra estreita cabe mais
# palavra na largura de um 9:16, e peso alto é o que sobrevive a uma faixa de
# fundo. Se nada disso existir, cai na mesma da legenda -- o título continua
# existindo, só sem o contraste de família.
CANDIDATAS_TITULO = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf",
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/ariblk.ttf",
    "C:/Windows/Fonts/seguibl.ttf",
]


def _fonte_titulo(tamanho):
    for c in CANDIDATAS_TITULO:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, tamanho)
            except Exception:
                pass
    return _fonte(tamanho)


def _fonte(tamanho):
    for c in CANDIDATAS:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, tamanho)
            except Exception:
                pass
    # load_default ignora o tamanho e sai minusculo; melhor uma legenda
    # feia que nenhuma, mas o log precisa dizer que foi por aqui
    print("[legenda] nenhuma fonte TTF encontrada; usando a fonte padrao do PIL")
    return ImageFont.load_default()


# =====================================================================
# CENSURA -- o "piiii" da TV (28/08)
# =====================================================================
# Ate 28/08 o palavrao era so cortado na primeira silaba ("Ca—"), e era
# isso que o espectador ouvia e lia. O dono do projeto pediu o BIPE
# classico, que e outra convencao: o audio some atras de um tom e a
# legenda mostra os simbolos. Ela funciona melhor por dois motivos --
# o bipe e um som que ninguem confunde com outra coisa (a silaba cortada
# soava como o TTS engasgando), e ele marca a piada com uma batida.
#
# QUEM MARCA O QUE E PALAVRAO continua sendo o n8n ("Montar Spec do
# Palito"), que troca a palavra pela primeira silaba mais o travessao
# ANTES de o texto chegar aqui. Isso e de proposito: assim nenhum palavrao
# inteiro existe no texto que vai para o TTS, e mesmo que o bipe caia um
# decimo fora do lugar, o que se ouve por baixo dele e uma silaba.
SUFIXO_CENSURA = "—"
MASCARA = "#@%&!"
# Quanto da sílaba se ouve antes de o bipe entrar. Ver `janelas_censuradas`.
FRACAO_SILABA = 0.60


def censurada(txt):
    """A palavra foi cortada pela censura? (termina em travessao)"""
    return str(txt or "").rstrip(".,!?;:").endswith(SUFIXO_CENSURA)


def mascarar(txt):
    """A PRIMEIRA LETRA fica; o resto vira símbolo (05/09).

    Pedido do dono do projeto: *"deve ser caracteres especiais na legenda,
    mostrando apenas a primeira letra"*. Até aqui a legenda trocava a palavra
    inteira por `#@%&!`, e a diferença não é de estilo: com a inicial, o
    espectador SABE qual palavrão foi dito e a piada continua de pé; sem
    ela, a censura apaga também a informação e o remate perde a graça.

    É a convenção do quadrinho e a do jornal impresso ("p***"), e continua
    segura para a monetização: o que está escrito na tela é uma letra e
    quatro símbolos, e o que se ouve é sílaba mais bipe.
    """
    s = str(txt or "").rstrip(".,!?;:").rstrip(SUFIXO_CENSURA)
    pontos = str(txt or "")[len(str(txt or "").rstrip(".,!?;:")):]
    return (s[:1].upper() if s else "") + MASCARA[:4] + pontos


def _reparto(texto, inicio, dur):
    """Sem WordBoundary: divide a janela entre as palavras na proporcao do
    numero de letras. Palavra longa demora mais que palavra curta, e isso
    sozinho ja e melhor do que dividir por igual."""
    palavras = [p for p in texto.split() if p]
    if not palavras:
        return []
    total = sum(len(p) for p in palavras) or 1
    fora, t = [], inicio
    for p in palavras:
        d = dur * len(p) / total
        fora.append({"txt": p, "inicio": t, "fim": t + d})
        t += d
    return fora


def _so_letras(s):
    return "".join(c for c in s.lower() if c.isalnum())


def _casar(texto, marcas, inicio, dur):
    """Uma entrada por PALAVRA ESCRITA, custe o que custar.

    O texto e a verdade sobre o que tem que aparecer na tela; as marcas sao
    a melhor informacao sobre QUANDO. Quando as duas discordam -- e elas
    discordam, o edge-tts perdeu a ultima palavra da fala de 28/08 -- quem
    ganha e o texto: legenda com tempo estimado ainda se le, legenda que
    nao existe custou o punchline.

    Casamento guloso, em ordem: cada palavra do texto procura a proxima
    marca que combine com ela (comparando so letras e numeros, porque a
    marca vem sem pontuacao). Palavra sem marca fica com tempo INTERPOLADO
    entre a marca anterior e a proxima -- ou, no fim da fala, entre a
    ultima marca e o fim do audio."""
    palavras = [p for p in texto.split() if p]
    if not palavras:
        return []
    marcas = [m for m in (marcas or []) if m.get("palavra")]
    if not marcas:
        return _reparto(texto, inicio, dur)

    fora, j = [], 0
    for p in palavras:
        alvo = _so_letras(p)
        achou = None
        # janela curta: a marca certa esta logo adiante, e procurar ate o
        # fim faria a palavra "de" casar com um "de" tres frases depois
        for k in range(j, min(j + 3, len(marcas))):
            if _so_letras(marcas[k].get("palavra", "")) == alvo and alvo:
                achou = k
                break
        if achou is None:
            fora.append({"txt": p, "inicio": None, "fim": None})
        else:
            m = marcas[achou]
            fora.append({"txt": p,
                         "inicio": inicio + float(m.get("inicio_s", 0.0)),
                         "fim": inicio + float(m.get("fim_s", 0.0))})
            j = achou + 1

    # tempo das que ficaram sem marca, por interpolacao entre as vizinhas
    fim_fala = inicio + max(dur, 0.05)
    ancoras = [(i, w) for i, w in enumerate(fora) if w["inicio"] is not None]
    if not ancoras:
        return _reparto(texto, inicio, dur)
    for i, w in enumerate(fora):
        if w["inicio"] is not None:
            continue
        antes = [a for a in ancoras if a[0] < i]
        depois = [a for a in ancoras if a[0] > i]
        t0 = antes[-1][1]["fim"] if antes else inicio
        t1 = depois[0][1]["inicio"] if depois else fim_fala
        n = (depois[0][0] if depois else len(fora)) - (antes[-1][0] + 1 if antes else 0)
        passo = max((t1 - t0) / max(n, 1), 0.12)
        k = i - (antes[-1][0] + 1 if antes else 0)
        w["inicio"] = t0 + passo * k
        w["fim"] = w["inicio"] + passo
    return fora


def janelas_censuradas(texto, marcas, inicio_s, dur_s, folga=0.07, minimo=0.30):
    """[(inicio, fim)] de cada palavra censurada, em tempo GLOBAL.

    É o que o render usa para pôr o bipe em cima e apagar a voz por baixo
    (ver sfx.mixar). Usa o mesmo casamento texto x marcas da legenda, para
    que o que se ouve e o que se lê estejam no mesmo instante -- se
    fossem duas contas diferentes, elas divergiriam justamente na fala em
    que o TTS perdeu uma palavra.

    A PRIMEIRA SÍLABA SE OUVE, E O BIPE VEM DEPOIS DELA (05/09)
        Pedido do dono do projeto: *"a primeira sílaba e o piiiiiii no
        áudio"*. Até aqui a janela cobria a palavra inteira -- e a palavra,
        neste ponto, já É a sílaba (o n8n cortou antes do TTS). O resultado
        era bipe puro: o espectador não ouvia nem o começo, e a censura
        deixava de ser uma piada de TV para virar um apagão.

        Agora o bipe entra em `FRACAO_SILABA` da palavra: ouve-se "por",
        entra o "piiii" e o resto some. É a convenção da televisão aberta, e
        é o que faz a censura ser engraçada em vez de só esconder.

        Não dá para ouvir a sílaba INTEIRA e ainda bipar dentro do mesmo
        tempo: a fala já foi sintetizada e esticá-la desalinharia a legenda,
        a boca e todos os efeitos do trecho. Sessenta por cento é o que sobra
        para o bipe cumprir os 0,30 s do `minimo` sem invadir a palavra
        seguinte.

    `folga` cobre a imprecisão do alinhamento no fim e `minimo` garante um
    bipe audível: uma sílaba dura ~0,15s, e um bipe de 0,15s lê como clique,
    não como censura."""
    fora = []
    for p in _casar(texto, marcas, inicio_s, dur_s):
        if not censurada(p["txt"]):
            continue
        ini, fim = float(p["inicio"]), float(p["fim"])
        t0 = max(0.0, ini + (fim - ini) * FRACAO_SILABA)
        t1 = max(fim + folga, t0 + minimo)
        fora.append((t0, t1))
    return fora


# ============================================================================
# O TÍTULO — a frase que fica no alto enquanto a história se apresenta
# ============================================================================
#
# Pedido do dono do projeto em 03/09: *"título, frase logo acima do início de
# contextualização"*, junto com *"o gancho precisa ser melhorado, nada me
# prende o começo do vídeo"*.
#
# POR QUE O TÍTULO É UM RECURSO DE RETENÇÃO, E NÃO ENFEITE
#     Quem rola o feed decide em dois ou três segundos, e nesses segundos a
#     fala mal começou -- no v003 a primeira frase termina aos 4,1 s. O texto
#     no alto entrega a PREMISSA inteira antes de a primeira frase acabar, e é
#     por isso que praticamente todo Short de comédia tem um. Ele não repete a
#     legenda: a legenda vai palavra a palavra, embaixo, acompanhando a boca;
#     o título fica parado, em cima, dizendo do que é o vídeo.
#
# ONDE ELE FICA, E POR QUE ALI
#     No alto -- que é justamente a faixa que a lei 23 proíbe encher de
#     gráfico flutuando sobre o personagem e que o dono já cobrou não deixar
#     vazia. A cabeça fica em torno de 15% a 45% da altura, dependendo do
#     plano; 0,085 põe o título acima disso em todos os planos que o motor
#     faz. Ele sai antes de a segunda fala começar, então nunca disputa a
#     tela com a piada.
TITULO_Y = 0.085
TITULO_SEGUNDOS = 4.5
# Duas linhas no máximo: três já é parágrafo, e parágrafo no alto de um Short
# não se lê -- se lê a boca de quem fala.
TITULO_LINHAS = 2
TITULO_COR = (255, 255, 255, 255)         # branco sobre a faixa escura
# A FAIXA: quase preta e quase opaca. Escura porque o texto é claro e o
# contraste tem de sobreviver a qualquer cenário atrás; quase opaca (e não
# opaca) porque uma tarja 100% chapada lê como erro de player, e deixar o
# cenário insinuado atrás mantém a tela viva.
TITULO_FUNDO = (18, 16, 22, 224)


class Titulo:
    """A frase de premissa, no alto, nos primeiros segundos.

    Desenhada com a mesma família de fonte e o mesmo contorno da legenda: é
    o mesmo canal falando, e duas tipografias diferentes na mesma tela leem
    como dois vídeos colados."""

    def __init__(self, largura, altura, texto, segundos=TITULO_SEGUNDOS):
        self.W, self.H = largura, altura
        self.texto = str(texto or "").strip().upper()
        self.ate = float(segundos)
        # ENCOLHER ANTES DE CORTAR (03/09). A primeira versão fixava o corpo
        # em 4,3% da altura e depois tirava palavras até caber em duas linhas
        # -- e o título perdia justamente o fim, que é onde mora a
        # desproporção: "O BOLETO DO PLANO DE SAUDE CHEGOU" sem o "COM JUROS".
        #
        # A ordem certa é a inversa: **a frase manda, o corpo cede.** Título é
        # texto de apoio e aguenta ser menor que a legenda (que acompanha a
        # boca e precisa ser lida no impulso); só quando nem no menor corpo
        # couber é que se tira palavra.
        self.tam = int(altura * 0.043)
        self.linhas = []
        for frac in (0.043, 0.039, 0.035, 0.032):
            self.tam = int(altura * frac)
            self.fonte = _fonte_titulo(self.tam)
            self.borda = max(4, self.tam // 7)
            linhas = self._linhas_de(self.texto.split()) if self.texto else []
            if linhas and len(linhas) <= TITULO_LINHAS:
                self.linhas = linhas
                break
        else:
            # nem no menor corpo coube: aí sim tira palavras
            self.linhas = self._quebrar()
        # vírgula pendurada no fim: ela sobra quando o corte tirou o que vinha
        # depois dela, e no título não separa mais nada
        if self.linhas:
            self.linhas[-1] = self.linhas[-1].rstrip(",;:- ")

    def _linhas_de(self, palavras):
        larg_max = int(self.W * 0.88)
        linhas, atual = [], ""
        for p in palavras:
            tenta = (atual + " " + p).strip()
            if self.fonte.getlength(tenta) <= larg_max or not atual:
                atual = tenta
            else:
                linhas.append(atual)
                atual = p
        if atual:
            linhas.append(atual)
        return linhas

    def _quebrar(self):
        """Quebra em até duas linhas — TIRANDO PALAVRAS, não cortando linhas.

        A primeira versão montava as linhas e ficava com as duas primeiras
        (`linhas[:2]`). O v004 mostrou o que isso faz: o título saiu
        **"CHEFE MANDOU TIRAR URGENTE O"**, terminando num artigo solto,
        porque a terceira linha foi jogada fora no meio da frase.

        Cortar por LINHA corta onde a fonte quis; cortar por PALAVRA corta
        onde a frase permite. Então tiram-se palavras do fim até caber, e
        depois aplica-se a mesma regra do fim pendurado que
        `titulo_da_esquete` já usa -- ela tem de valer aqui também, porque é
        aqui que o corte final acontece.
        """
        if not self.texto:
            return []
        palavras = self.texto.split()
        while palavras:
            linhas = self._linhas_de(palavras)
            if len(linhas) <= TITULO_LINHAS:
                return linhas
            palavras.pop()
            while len(palavras) > 3 and \
                    palavras[-1].strip(".,!?;:").lower() in _NAO_TERMINA:
                palavras.pop()
        return []

    def desenhar(self, quadro, t):
        if not self.linhas or t > self.ate:
            return quadro
        # some suavemente no último meio segundo, para não piscar
        alfa = 255
        if t > self.ate - 0.5:
            alfa = max(0, int(255 * (self.ate - t) / 0.5))
        # A FAIXA DE FUNDO (04/09, item 2). Sem ela o título depende do que
        # estiver atrás: sobre a parede clara de um cenário ele some, e o
        # contorno sozinho não resolve porque ele é uma linha, não uma
        # superfície. A faixa dá ao título o mesmo que um cartaz tem -- um
        # plano próprio -- e é o que o faz parar o polegar.
        #
        # Desenhada numa camada à parte e composta: o `quadro` chega em RGB e
        # `d.rectangle` com alfa não mistura, ele substitui. Sem isto a faixa
        # sairia opaca no primeiro frame e o fade final não existiria.
        cx = self.W / 2.0
        alt_linha = int(self.tam * 1.18)
        larg = max(self.fonte.getlength(l) for l in self.linhas)
        pad_x, pad_y = int(self.tam * 0.55), int(self.tam * 0.34)
        y0 = int(self.H * TITULO_Y) - pad_y
        x0 = int(cx - larg / 2.0) - pad_x
        x1 = int(cx + larg / 2.0) + pad_x
        y1 = y0 + alt_linha * len(self.linhas) + pad_y * 2 - int(self.tam * 0.16)
        faixa = Image.new("RGBA", quadro.size, (0, 0, 0, 0))
        df = ImageDraw.Draw(faixa)
        raio = int(self.tam * 0.30)
        df.rounded_rectangle([x0, y0, x1, y1], radius=raio,
                             fill=TITULO_FUNDO[:3] + (int(TITULO_FUNDO[3] * alfa / 255),))
        quadro.paste(Image.alpha_composite(
            quadro.crop((0, 0, self.W, self.H)).convert("RGBA"), faixa
        ).convert(quadro.mode), (0, 0))

        d = ImageDraw.Draw(quadro)
        y = int(self.H * TITULO_Y)
        for linha in self.linhas:
            w = self.fonte.getlength(linha)
            x = (self.W - w) / 2.0
            # o contorno CONTINUA, mesmo com a faixa: ela é escura e o texto é
            # claro, mas o fade final passa por valores intermediários em que
            # os dois se aproximam
            d.text((x, y), linha, font=self.fonte,
                   fill=TITULO_COR[:3] + (alfa,),
                   stroke_width=max(2, self.borda // 2),
                   stroke_fill=COR_BORDA[:3] + (alfa,))
            y += alt_linha
        return quadro


# PONTUAÇÃO TIPOGRÁFICA -> ASCII (04/09, ciclo 25).
#
# O título do v008 saiu **"SEU E□MAIL PRO CHEFE CAIU"**, com um retângulo vazio
# no lugar do hífen: o modelo escreveu `e‑mail` com HÍFEN NÃO SEPARÁVEL
# (U+2011), e a fonte do título não tem esse glifo. O PIL não avisa -- ele
# desenha a caixa de "glifo ausente" e segue.
#
# Não é um caso: é uma família. Todo LLM devolve travessão, aspas curvas e
# reticências de um caractere, e a fonte condensada/black que o título prefere
# costuma trazer só o repertório latino básico. A legenda corre o mesmo risco
# com a mesma fonte.
#
# A troca é por ASCII e não por remoção: o hífen tem de continuar existindo em
# "e-mail". Roda no texto que entra, uma vez por fala, não por frame.
_TIPOGRAFICO = {
    "‐": "-", "‑": "-", "‒": "-", "–": "-",
    "—": "-", "―": "-", "−": "-",
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "″": '"',
    "…": "...", " ": " ", " ": " ", " ": " ",
    "​": "", "﻿": "",
}


def so_ascii_tipografico(texto):
    """Troca a pontuação tipográfica do LLM pela equivalente em ASCII."""
    s = str(texto or "")
    for a, b in _TIPOGRAFICO.items():
        if a in s:
            s = s.replace(a, b)
    return s


# PALAVRAS QUE NÃO ENTRAM NO TÍTULO. Interjeição e vocativo são o tempero da
# fala e ruído no título -- "oxe", "mano", "meu rei" não dizem do que é o
# vídeo. Tirá-las é o que faz caber a parte concreta nas duas linhas.
_RUIDO_TITULO = {
    "oxe", "mano", "velho", "bicho", "rapaz", "uai", "vixe", "eita",
    "né", "ne", "pô", "po", "viu", "ué", "ue", "poxa", "nossa",
    "firmeza", "beleza", "vacilei", "sério", "serio",
}

# NÃO ENTRAM NO FIM DO TÍTULO. Um título cortado em "por", "de" ou "com" fica
# pendurado no ar — é a mesma regra que `_agrupar` já aplica aos blocos de
# legenda desde a volta 3, e pelo mesmo motivo: o olho lê o fim da linha como
# fim de ideia.
_NAO_TERMINA = {
    "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas", "por",
    "pra", "para", "com", "sem", "que", "e", "o", "a", "os", "as", "um",
    "uma", "meu", "minha", "seu", "sua", "ao", "aos", "à", "às", "num",
    "numa", "pelo", "pela", "se", "mas", "ou",
}


def titulo_da_esquete(falas, max_palavras=9):
    """A premissa, tirada da PRIMEIRA fala.

    POR QUE DA PRIMEIRA, E POR QUE POR CÓDIGO
        A primeira fala é o setup -- ela diz o que aconteceu, e é isso que um
        título precisa dizer. O remate seria spoiler.

        E ela é comprimida por CÓDIGO, e não pedida ao roteirista, por uma
        razão registrada: um campo novo teria de sobreviver a três passadas de
        LLM (rascunho, reescrita, estruturação), e foi exatamente assim que o
        rótulo `NOME:` se perdeu e custou vinte voltas ao ciclo. O que o
        modelo escreve uma vez, o modelo esquece na passada seguinte; o que o
        código faz, acontece sempre.

    Tira interjeição e vocativo, corta na pontuação forte e limita o tamanho.
    Devolve '' quando não sobrar coisa que preste -- título ruim é pior que
    nenhum, porque ele ocupa os segundos que decidem o vídeo.
    """
    if not falas:
        return ""
    txt = so_ascii_tipografico(falas[0]).strip()
    # corta na primeira pontuação forte: a oração principal é o título
    for sep in (". ", "? ", "! ", "; "):
        if sep in txt:
            txt = txt.split(sep)[0]
            break
    txt = txt.rstrip(".?!;:, ")
    palavras = [p for p in txt.split()
                if p.strip(".,!?;:").lower() not in _RUIDO_TITULO]
    palavras = palavras[:max_palavras]
    # não termina em palavra pendurada (ver `_NAO_TERMINA`)
    while len(palavras) > 3 and \
            palavras[-1].strip(".,!?;:").lower() in _NAO_TERMINA:
        palavras.pop()
    if len(palavras) < 3:
        return ""
    return " ".join(palavras).strip(".,!?;: ")


class Legenda:
    """Pre-monta os blocos e desenha o que estiver no ar em cada instante.

    A fonte e carregada uma vez: `truetype` por frame custa mais que o
    desenho em si num video de 400 frames."""

    def __init__(self, largura, altura, tamanho=None, por_bloco=3, y_rel=None):
        self.W, self.H = largura, altura
        # `y_rel` existe para o caso em que se queira subir a legenda. Nao e o
        # padrao: a fala em cima obriga o olho a largar a boca de quem esta
        # falando embaixo.
        self.y_rel = float(y_rel) if y_rel else Y_RELATIVO
        self.tam = tamanho or int(altura * 0.048)     # ~92px em 1920
        self.fonte = _fonte(self.tam)
        self.fonte_ativa = _fonte(int(self.tam * ESCALA_ATIVA))
        self.borda = max(5, self.tam // 7)
        self.por_bloco = max(1, int(por_bloco))
        self.blocos = []

    def adicionar(self, texto, marcas, inicio_s, dur_s):
        """Acrescenta a fala de UM trecho, ja deslocada para o tempo global.

        `marcas` sao as do edge-tts (inicio_s/fim_s relativos ao trecho).
        Quem manda no QUE aparece e o texto; as marcas mandam no QUANDO --
        ver `_casar`."""
        # a mesma fonte do título, o mesmo risco de glifo ausente: ver
        # `so_ascii_tipografico`
        palavras = _casar(so_ascii_tipografico(texto), marcas, inicio_s, dur_s)
        if not palavras:
            return
        for grupo in _agrupar(palavras, self.por_bloco):
            self.blocos.append({"inicio": grupo[0]["inicio"],
                                "fim": grupo[-1]["fim"],
                                "palavras": grupo})

    def desenhar(self, quadro, t):
        """Queima na imagem o bloco que contem o instante `t` (segundos).

        Recebe e devolve o quadro RGB ja montado -- a legenda vai por cima
        de tudo, inclusive do personagem, que e como Short faz."""
        bloco = None
        for b in self.blocos:
            # a margem para tras segura o bloco no ar durante a pausa entre
            # palavras; sem ela a legenda pisca a cada respiro do TTS
            if b["inicio"] - 0.08 <= t <= b["fim"] + 0.28:
                bloco = b
                break
        if bloco is None:
            return quadro

        d = ImageDraw.Draw(quadro)
        # palavra censurada vira INICIAL + símbolos de quadrinho ("P#@%&"):
        # escrever "PORNO" na tela entregaria de volta o que o bipe acabou de
        # esconder, e escrever só os símbolos apagaria a piada junto com a
        # palavra. Ver `mascarar`.
        textos = [mascarar(p["txt"]) if censurada(p["txt"]) else p["txt"].upper()
                  for p in bloco["palavras"]]
        ativas = [p["inicio"] - 0.02 <= t <= p["fim"] + 0.12 for p in bloco["palavras"]]

        # A LARGURA E MEDIDA COM A FONTE QUE SERA USADA em cada palavra: a
        # ativa cresce 12%, e medir todas com a fonte normal faria o bloco
        # inteiro escorregar para a direita a cada troca de palavra ativa --
        # legenda que anda sozinha e mais chamativa que o destaque.
        fontes = [self.fonte_ativa if a else self.fonte for a in ativas]
        espaco = d.textlength(" ", font=self.fonte)
        larguras = [d.textlength(s, font=f) for s, f in zip(textos, fontes)]
        total = sum(larguras) + espaco * (len(textos) - 1)

        # uma palavra muito longa nao pode vazar do quadro
        margem = self.W * 0.06
        util = self.W - 2 * margem
        if total > util:
            escala = util / total
            fontes = [_fonte(max(18, int(self.tam * ESCALA_ATIVA * escala))) if a
                      else _fonte(max(18, int(self.tam * escala))) for a in ativas]
            espaco = d.textlength(" ", font=fontes[0])
            larguras = [d.textlength(s, font=f) for s, f in zip(textos, fontes)]
            total = sum(larguras) + espaco * (len(textos) - 1)

        x = (self.W - total) / 2.0
        y = self.H * self.y_rel
        desl = max(3, self.tam // 16)
        for s, larg, f, ativa in zip(textos, larguras, fontes, ativas):
            # sombra deslocada: o contorno preto sozinho some quando o
            # cenario atras e escuro (o onibus), e a sombra descola o texto
            # do fundo em vez de so cerca-lo
            d.text((x + desl, y + desl), s, font=f, anchor="lm",
                   fill=COR_SOMBRA, stroke_width=self.borda, stroke_fill=COR_SOMBRA)
            d.text((x, y), s, font=f, anchor="lm",
                   fill=COR_ATIVA if ativa else COR_TEXTO,
                   stroke_width=self.borda, stroke_fill=COR_BORDA)
            x += larg + espaco
        return quadro
