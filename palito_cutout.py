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

COMO PRODUZIR AS PARTES
    Peça ao gerador (Nano Banana Pro, FLUX, Recraft) uma folha de
    personagem com fundo transparente, uma parte por imagem:
      cabeca.png        (de frente, boca fechada, olhos abertos)
      tronco.png        (com a roupa)
      braco_sup.png     (ombro -> cotovelo)
      braco_inf.png     (cotovelo -> mão, mão incluída)
      perna_sup.png     (quadril -> joelho)
      perna_inf.png     (joelho -> pé, pé incluído)
      boca_0..3.png     (fechada, meia, aberta, muito aberta)
      olho_aberto.png / olho_fechado.png
      sobrancelha.png

    Cada PNG precisa do PIVÔ anotado em partes.json: o ponto onde ela
    gira. Ombro na parte do braço superior, cotovelo na do inferior.

Uso:
    python3 palito_cutout.py --partes ./personagem --spec spec.json -o saida.mp4
"""
import argparse, json, math, os, subprocess, sys, tempfile
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from palito_v4 import REST, POSES, EXPRESSOES, merge, blend, pt

W, H, FPS = 1080, 1920, 24


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


class Personagem:
    """Carrega as partes e o arquivo de pivôs uma vez, na memória."""

    def __init__(self, pasta):
        self.pasta = pasta
        cfg = json.load(open(os.path.join(pasta, "partes.json"), encoding="utf-8"))
        self.pivos = cfg["pivos"]
        self.escala = cfg.get("escala", 1.0)
        # COMPRIMENTO de cada osso, em pixels da arte: distancia do pivo
        # ate a proxima articulacao. Sem isto o rig usa medidas cravadas
        # que nao batem com o desenho, e o antebraco descola do cotovelo.
        self.comp = cfg["comprimentos"]
        self.img, self.piv = {}, {}
        for nome in cfg["partes"]:
            caminho = os.path.join(pasta, nome + ".png")
            if not os.path.exists(caminho):
                raise FileNotFoundError(f"parte '{nome}.png' nao existe em {pasta}")
            im = Image.open(caminho).convert("RGBA")
            self.img[nome], self.piv[nome] = _centralizar(im, self.pivos[nome])

    def p(self, nome):
        return self.img[nome], self.piv[nome]


def desenhar(pers, rig, fundo, boca_nivel=0.0, piscando=False):
    """Monta um frame. A ORDEM importa: é ela que define quem fica na frente."""
    base = fundo.copy().convert("RGBA")
    e = pers.escala
    C = pers.comp                      # comprimentos vindos da ARTE
    q = rig["quadril"]
    ombro = pt(q, rig["tronco"], C["tronco"] * e)
    cabeca = pt(ombro, rig["tronco"], C["pescoco"] * e)

    # ---- membros do lado de tras (z atras do tronco) ----
    for lado, chave, esp in (("e", "perna_e", False), ("d", "perna_d", True)):
        c = rig[chave]
        joelho = pt(q, c[0], C["perna_sup"] * e)
        img, piv = pers.p("perna_sup")
        colar(base, img, piv, q, c[0] - 90, e, esp)
        img, piv = pers.p("perna_inf")
        colar(base, img, piv, joelho, c[0] + c[1] - 90, e, esp)

    braco_tras = rig["braco_e"]
    base_o = [ombro[0] - C["meio_ombro"] * e, ombro[1] + C["queda_ombro"] * e]
    cot = pt(base_o, braco_tras[0], C["braco_sup"] * e)
    img, piv = pers.p("braco_sup")
    colar(base, img, piv, base_o, braco_tras[0] - 90, e)
    img, piv = pers.p("braco_inf")
    colar(base, img, piv, cot, braco_tras[0] + braco_tras[1] - 90, e)

    # ---- tronco ----
    img, piv = pers.p("tronco")
    colar(base, img, piv, q, rig["tronco"] + 90, e)

    # ---- braço da frente ----
    bf = rig["braco_d"]
    base_d = [ombro[0] + C["meio_ombro"] * e, ombro[1] + C["queda_ombro"] * e]
    cotd = pt(base_d, bf[0], C["braco_sup"] * e)
    img, piv = pers.p("braco_sup")
    colar(base, img, piv, base_d, bf[0] - 90, e, True)
    img, piv = pers.p("braco_inf")
    colar(base, img, piv, cotd, bf[0] + bf[1] - 90, e, True)

    # ---- cabeça e rosto ----
    ang_cab = rig["tronco"] + 90
    img, piv = pers.p("cabeca")
    colar(base, img, piv, cabeca, ang_cab, e)

    # olhos: 2 estados. Piscar é o que mais barato dá vida.
    olho = "olho_fechado" if piscando and "olho_fechado" in pers.img else "olho_aberto"
    if olho in pers.img:
        img, piv = pers.p(olho)
        colar(base, img, piv, cabeca, ang_cab, e)

    # boca: 4 visemas escolhidos pela envoltória do áudio
    n_boca = sum(1 for k in pers.img if k.startswith("boca_"))
    if n_boca:
        idx = min(n_boca - 1, int(boca_nivel * n_boca))
        img, piv = pers.p(f"boca_{idx}")
        colar(base, img, piv, cabeca, ang_cab, e)

    if "sobrancelha" in pers.img:
        img, piv = pers.p("sobrancelha")
        dy = -rig["sobrancelha"] * 14 * e          # sobe quando surpreso
        colar(base, img, piv, (cabeca[0], cabeca[1] + dy), ang_cab, e)

    return base.convert("RGB")


# =====================================================================
def render(pasta_partes, spec, saida, tmpdir=None):
    from palito_v5 import sintetizar, envelope
    tmp = tmpdir or tempfile.mkdtemp()
    fd = os.path.join(tmp, "frames"); os.makedirs(fd, exist_ok=True)
    pers = Personagem(pasta_partes)

    # VOZ PRIMEIRO: a duração real vira a timeline (igual ao palito_v5)
    faixas, total = [], 0.0
    for i, tr in enumerate(spec["trechos"]):
        wav = os.path.join(tmp, f"v{i:02d}.wav")
        cfg = spec.get("vozes", {}).get(tr.get("perfil_voz", "narrador"), {})
        # 'real' e o padrao aqui, ao contrario do modo de teste: em producao
        # o spec sempre traz modo_tts, e cair em 'demo' por engano produziria
        # um video com voz sintetica de formantes no ar.
        _, dur = sintetizar(tr["fala"], cfg, wav,
                            spec.get("modo_tts", os.environ.get("MODO_TTS", "real")))
        tr["dur"] = dur + tr.get("respiro_s", 0.45)
        faixas.append(wav); total += tr["dur"]
    print(f"[voz] timeline real: {total:.2f}s")

    lista = os.path.join(tmp, "a.txt")
    open(lista, "w").write("\n".join(f"file '{a}'" for a in faixas))
    voz = os.path.join(tmp, "voz.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", lista, "-ar", "24000", "-ac", "1", voz], check=True)
    env = envelope(voz)

    fundos = {}
    n = 0
    for tr in spec["trechos"]:
        cen = tr.get("cenario", "sala")
        if cen not in fundos:
            cam = os.path.join(pasta_partes, "..", "cenarios", cen + ".png")
            fundos[cen] = (Image.open(cam).convert("RGB").resize((W, H))
                           if os.path.exists(cam) else Image.new("RGB", (W, H), "#A5A893"))
        p1 = merge(REST, POSES[tr["pose"]], EXPRESSOES[tr["expressao"]])
        p2 = merge(REST, POSES[tr.get("pose_saida", tr["pose"])], EXPRESSOES[tr["expressao"]])
        for f in range(max(1, int(tr["dur"] * FPS))):
            fh = (f // 2) * 2                       # animar "em 2s"
            t = fh / max(1, int(tr["dur"] * FPS) - 1)
            rig = blend(p1, p2, t * t * (3 - 2 * t))
            rig["quadril"] = [rig["quadril"][0], rig["quadril"][1] + math.sin(f * 0.13) * 6]
            nivel = env[n] if n < len(env) else 0.0
            desenhar(pers, rig, fundos[cen], nivel, (n % 82) in (0, 1)).save(
                os.path.join(fd, f"{n:05d}.png"))
            n += 1
    print(f"[cutout] {n} frames ({n/FPS:.1f}s)")

    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
                    "-i", os.path.join(fd, "%05d.png"), "-i", voz,
                    "-af", spec.get("loudnorm", "loudnorm=I=-9:LRA=8:TP=-1.5"),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "21",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", saida], check=True)
    return saida, round(total, 2)


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
