#!/usr/bin/env python3
"""
fatiar — recorta a TIRA DE ROSTO da folha do personagem em peças.

Separado de folha_personagem.py de propósito: aqui não há nenhuma opinião
sobre COMO o personagem deve ser (cor de pele, roupa, traço). Aqui só há
silhueta. Quem diz o que a peça precisa ter é folha_personagem.py; este
arquivo só sabe achar coluna vazia numa máscara alfa e cortar.

Por isso as funções recebem a especificação por parâmetro em vez de
importá-la: assim este módulo serve para qualquer personagem, de qualquer
canal, sem depender do vocabulário de nenhum.

O QUE SAIU DAQUI (05/09, varredura de código morto)
    Este arquivo tinha 403 linhas e oito funções a mais, que fatiavam o
    CORPO por geometria: `achar_marcos` procurava pescoço, virilha e
    cintura na silhueta e `fatiar_corpo` cortava as peças a partir de
    proporções fixas (cotovelo em 45% do braço, joelho em 50% da perna).

    Esse caminho foi aposentado quando `segmentar.py` passou a ler a folha
    já desenhada em peças separadas e a MEDIR o pivô de cada uma, em vez de
    supor onde ele deveria estar. Desde então nenhuma linha do sistema
    chamava as oito funções -- nem a produção, nem o painel, nem o lab.

    A documentação, porém, ainda anunciava um plano B que não existia:
    dizia que `preparar_assets.py` escolhia entre `segmentar.py` e
    `fatiar.py` conforme a folha viesse solta ou grudada. Ele nunca
    escolheu. Diante de uma folha grudada ele levanta `FolhaGrudada`,
    recusa a arte e mantém as peças anteriores -- e isso está certo: uma
    folha grudada cortada por proporção fixa renderiza um boneco com o
    ombro no lugar do cotovelo, e o defeito só apareceria treze minutos
    depois, no vídeo pronto. Recusar e avisar é melhor que entregar torto.

    O corpo velho está guardado em lab/morto-0509/fatiar-completo.py.
"""
import numpy as np
from PIL import Image                                        # noqa: F401


# =====================================================================
# Marcos anatômicos na silhueta
# =====================================================================
def _mascara(img, limiar=10):
    return np.array(img.convert("RGBA").split()[-1]) > limiar


def _faixas(linha):
    """Trechos contínuos de True numa linha -> [(ini, fim), ...]."""
    idx = np.flatnonzero(linha)
    if len(idx) == 0:
        return []
    quebras = np.flatnonzero(np.diff(idx) > 1)
    ini = np.concatenate(([idx[0]], idx[quebras + 1]))
    fim = np.concatenate((idx[quebras], [idx[-1]]))
    return list(zip(ini.tolist(), fim.tolist()))


# =====================================================================
# Recorte
# =====================================================================
def _recortar(img, caixa):
    """Corta e aperta no conteúdo. Apertar importa: o pivô é medido em
    coordenada da peça, então moldura transparente sobrando desloca o
    pivô do desenho de verdade."""
    peca = img.crop(caixa)
    bb = peca.getbbox()
    return peca.crop(bb) if bb else peca


def fatiar_rosto(img, nomes):
    """Tira de rosto -> peças, uma por célula, na ordem de ESPEC_ROSTO.
    nomes: os rótulos das células, na ordem da esquerda para a direita.
    Separa por coluna vazia, não por proporção: o gerador nunca espaça
    as células exatamente igual."""
    img = img.convert("RGBA")
    mask = _mascara(img)
    colunas = mask.any(axis=0)
    blocos = _faixas(colunas)
    # descarta respingo: célula de verdade tem largura mínima
    largura_min = max(int(mask.shape[1] * 0.02), 3)
    blocos = [b for b in blocos if b[1] - b[0] >= largura_min]
    if len(blocos) != len(nomes):
        raise ValueError(
            f"a tira de rosto tem {len(blocos)} celulas, esperava "
            f"{len(nomes)} -- regere a tira")
    pecas = {}
    for nome, (bx0, bx1) in zip(nomes, blocos):
        pecas[nome] = _recortar(img, (bx0, 0, bx1 + 1, mask.shape[0]))
    return pecas
