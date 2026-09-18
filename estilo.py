# -*- coding: utf-8 -*-
"""estilo.py -- ACHATA a arte de objeto para o traco do canal.

    Os objetos do catalogo vieram do FLUX semi-realistas (chave de metal com
    reflexo, celular fotografico, boleto com texto ilegivel) e destoam do
    boneco de papel e das placas vetoriais -- o dono chamou de "objetos mal
    feitos" (16/09). A arte de verdade so' se refaz com o modelo (GUIA
    §55.3, `props_gerados.py`, que espera a porta da Cloudflare). Ate' la',
    o que da' para fazer por codigo, e vale para qualquer PNG com alfa:

      1. tirar o gradiente (filtro de moda: cada pixel vira a cor mais comum
         em volta -- fica chapado, como pintura de cel);
      2. reduzir a uns poucos tons (median cut) e saturar um pouco;
      3. contorno preto grosso em volta (o `_destacar_objeto` do motor, mais
         largo do que no modo cena);
      4. traco INTERNO onde a cor muda de repente (as bordas entre os tons),
         que e' o que faz ler como desenho e nao como foto lavada.

    Sem IA, em ~50 ms por objeto, com cache por arquivo.
"""
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

TRACO = (28, 24, 22, 255)


def achatar(img, tons=10, saturacao=1.25, traco_interno=True):
    """Devolve o PNG achatado (RGBA), mesmo tamanho."""
    base = img.convert("RGBA")
    # alfa BINARIO: o halo de 1-40 do rembg (lei 32) vira serrilha no
    # contorno dilatado, e o corpo semi-transparente da sacola sumia
    # (a sacola branca tem o corpo em alfa 5-120: o rembg achou que era
    # fundo; o limiar e' baixo e a abertura morfologica tira o halo fino)
    a = np.asarray(base.getchannel("A"))
    alfa = Image.fromarray(np.where(a > 6, 255, 0).astype(np.uint8), "L")
    k = max(3, int(round(min(base.size) * 0.008)) | 1)
    alfa = alfa.filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k)).filter(ImageFilter.MedianFilter(5))
    rgb = base.convert("RGB")
    # 1. sem gradiente
    lado = max(3, int(round(min(base.size) * 0.012)) | 1)
    rgb = rgb.filter(ImageFilter.ModeFilter(lado))
    rgb = rgb.filter(ImageFilter.MedianFilter(3))
    # 2. poucos tons, mais saturados
    q = rgb.quantize(colors=tons, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")
    q = ImageEnhance.Color(q).enhance(saturacao)
    out = q.convert("RGBA")
    out.putalpha(alfa)
    if traco_interno:
        out = _traco_interno(out, q, alfa)
    return out


def _traco_interno(out, q, alfa):
    """Linha escura onde dois tons se encontram dentro da figura."""
    a = np.asarray(q).astype(np.int16)
    al = np.asarray(alfa) > 64
    # diferenca com o vizinho da direita e de baixo
    dx = np.abs(a[:, 1:, :] - a[:, :-1, :]).sum(axis=2)
    dy = np.abs(a[1:, :, :] - a[:-1, :, :]).sum(axis=2)
    borda = np.zeros(al.shape, dtype=bool)
    borda[:, 1:] |= dx > 180
    borda[1:, :] |= dy > 180
    borda &= al
    # so' a borda entre dois pixels OPACOS (a de fora ja' e' o contorno)
    dentro = al.copy()
    dentro[:, 1:] &= al[:, :-1]
    dentro[1:, :] &= al[:-1, :]
    borda &= dentro
    if not borda.any():
        return out
    esp = max(1, int(round(min(out.size) * 0.006)))
    m = Image.fromarray((borda * 255).astype(np.uint8), "L")
    if esp > 1:
        m = m.filter(ImageFilter.MaxFilter(esp * 2 - 1))
    # traco semi-transparente: escurece o tom, nao apaga
    linha = Image.new("RGBA", out.size, TRACO[:3] + (0,))
    linha.putalpha(Image.fromarray((np.asarray(m) * 0.75).astype(np.uint8), "L"))
    out = out.copy()
    out.alpha_composite(linha)
    return out
