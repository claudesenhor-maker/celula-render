# -*- coding: utf-8 -*-
"""cartao.py -- o MODO CARTAO: um cartao por frase, como o @Madrazzo_MF.

    PLANO-MADRAZZO.md e PLANO-ENCAIXE.md §7. Cada frase (narracao ou fala)
    vira UM cartao: fundo chapado ou cenario lavado, no maximo um ou dois
    props, um ou dois atores em POSE (por acao do catalogo ou por ALVO, via
    IK), objeto na mao com pega de verdade, placas com texto, acessorios e
    roupa pelo papel. Dentro do cartao nada anda; o corte e' seco. A voz
    define a duracao (lei 1) e a legenda sai palavra a palavra.

    Nada aqui toca em `palito_cutout.render`: este e' um caminho paralelo,
    de laboratorio, que reaproveita as primitivas (Personagem, pose_na_tela,
    desenhar_personagem, colar, Cenario, Legenda, Titulo, sfx, palito_v5).

    RENDER POR CARTAO. O corpo e' desenhado UMA vez por cartao; por frame so'
    muda a boca de quem fala (4 niveis, em cache) e a legenda. E' o que torna
    60 s de video uma questao de minutos.

    SPEC (ver `spec_cartao_teste.json`):
      {
        "modo": "cartao", "fila_id": ..., "modo_tts": "demo",
        "elenco": {"pal": {"pasta": ...}}, "vozes": {...},
        "fundo": "#f6f1e6", "faixa": "#7fb27a" (opcional),
        "titulo": "...", "legenda_palavras": 1,
        "cartoes": [
          {"texto": "Pal foi cobrado por uma taxa que nunca pediu.",   # narracao
           "voz": "narrador",
           "atores": [{"quem": "pal", "x": 0.36, "pose": "bracos_cruzados",
                       "expressao": "bravo", "papel": "delegado",
                       "objeto": "boleto", "mao": "d", "duas_maos": false,
                       "alvos": [{"mao": "e", "alvo": "prop:balcao.apoio"}],
                       "sentar": "cadeira", "atras_de": "balcao", "espelhar": false}],
           "props": [{"nome": "balcao", "x": 0.62, "placa": {"tipo": "letreiro", "texto": "BANCO"}}],
           "placas": [{"tipo": "carimbo", "texto": "COBRADO", "x": 0.7, "y": 0.35}],
           "objetos": [{"nome": "boleto", "x": 0.5, "em": "prop:mesa.tampo"}],
           "plano": "aberto" | "medio" | "close",
           "sfx": [{"nome": "thud", "em": 0.3}]},
          {"salto": "2 MESES DEPOIS"},
          {"texto": "Cade o meu dinheiro?", "ator": "pal", ...}          # fala
        ]
      }
"""
import copy
import json
import math
import os
import shutil
import subprocess
import tempfile
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import acoes as ACOES
import ancoras as ANC
import estilo as ESTILO
import expressao as EXPR
import ik as IK
import placas as PLACAS
import props as PROPS
import roupas as ROUPAS
import sfx as SFX
from palito_cutout import (Personagem, desenhar_personagem, pose_na_tela, colar,
                           Cenario, W, H, FPS, _reamostrar, _destacar_objeto,
                           _sombra_de_contato, _folha, _pastas, _achar_arte,
                           _inventario, LOOP_SOM_S)
import cenarios as CENARIOS
from palito_v4 import REST, merge

# ---------------------------------------------------------------------
# constantes do formato cartao
# ---------------------------------------------------------------------
ALTURA_ATOR = 0.40          # fracao de H que o corpo em pe ocupa (Madrazzo ~0,35)
CHAO_REL = 0.665            # linha do chao dos cartoes
LEGENDA_Y = 0.80            # a legenda embaixo do desenho
FUNDO_PADRAO = "#F6F1E6"
NIVEIS_BOCA = (0.0, 0.35, 0.7, 1.0)
POP_S = 0.14                # o cartao entra com um pop curto
POP_FORCA = 0.06
RESPIRO_S = 0.12
RESPIRO_SALTO_S = 0.35

# ---------------------------------------------------------------------
# o objeto do salto de tempo sai do texto do salto (19/09)
# ---------------------------------------------------------------------
# "UMA HORA DEPOIS" saiu com CALENDARIO no video que o dono viu: o tipo era
# `calendario` por padrao e so mudava se o spec dissesse `salto_tipo`. Hora e
# minuto pedem RELOGIO (ponteiros na hora certa); dia, semana, mes e ano pedem
# CALENDARIO (o numero circulado). Portugues e ingles, digito ou extenso.
import re as _re

_NUM_EXTENSO = {
    "meia": 0.5, "meio": 0.5, "half": 0.5,
    "um": 1, "uma": 1, "one": 1, "a": 1, "an": 1,
    "dois": 2, "duas": 2, "two": 2, "tres": 3, "three": 3, "quatro": 4, "four": 4,
    "cinco": 5, "five": 5, "seis": 6, "six": 6, "sete": 7, "seven": 7,
    "oito": 8, "eight": 8, "nove": 9, "nine": 9, "dez": 10, "ten": 10,
    "onze": 11, "eleven": 11, "doze": 12, "twelve": 12, "quinze": 15, "fifteen": 15,
    "vinte": 20, "twenty": 20, "trinta": 30, "thirty": 30, "quarenta": 40, "forty": 40,
    "cinquenta": 50, "fifty": 50,
}
_RE_HORAS = _re.compile(r"\b(hora|horas|hour|hours|hr|hrs|minuto|minutos|minute|minutes|min|mins|"
                        r"manha|tarde|noite|madrugada|meio-dia|meia-noite|midnight|noon|"
                        r"am|pm|o'clock|oclock)\b|\d+\s?h\b")


def _sem_acento(t):
    return (t.replace("ã", "a").replace("á", "a").replace("â", "a").replace("é", "e")
             .replace("ê", "e").replace("í", "i").replace("ó", "o").replace("ô", "o")
             .replace("ú", "u").replace("ç", "c"))


def _numero_do_texto(t):
    """O primeiro numero do texto, em digito ou por extenso; None se nao ha."""
    m = _re.search(r"(\d+)(?:[:h](\d{2}))?", t)
    if m:
        return float(m.group(1)), (float(m.group(2)) if m.group(2) else None)
    for pal in _re.findall(r"[a-z]+", t):
        if pal in _NUM_EXTENSO:
            return float(_NUM_EXTENSO[pal]), None
    return None, None


def ler_salto(texto):
    """Decide o objeto do salto pelo texto. Devolve {tipo, hora, minutos, numero}.

    relogio   -- horas/minutos ("1 HORA DEPOIS", "30 MIN DEPOIS", "6 DA MANHA",
                 "2 HOURS LATER", "MEIA-NOITE"). Hora relativa ("N horas
                 depois") anda a partir das 9h, que e' a hora em que a cena
                 comeca por convencao; hora absoluta ("6 da manha", "3 da
                 tarde") vai direto para o ponteiro.
    calendario -- dias/semanas/meses/anos ("2 MESES DEPOIS", "NO DIA SEGUINTE",
                 "3 YEARS LATER"); o numero circulado e' o do texto (dias) ou
                 um dia fixo para semanas/meses/anos, para o calendario nao
                 mostrar "dia 24" num salto de 24 meses.
    """
    t = _sem_acento(str(texto or "").lower())
    n, mm = _numero_do_texto(t)
    if _RE_HORAS.search(t) and not _re.search(r"\b(dia|dias|day|days|semana|mes|meses|ano|anos)\b", t):
        hora, minutos = 9.0, 0.0
        eh_minuto = bool(_re.search(r"\b(minuto|minutos|minute|minutes|min|mins)\b", t))
        absoluta = bool(_re.search(r"\b(manha|tarde|noite|madrugada|am|pm|o'clock|oclock)\b", t))
        if "meio-dia" in t or "noon" in t:
            hora = 12.0
        elif "meia-noite" in t or "midnight" in t:
            hora = 0.0
        elif n is not None and eh_minuto:
            minutos = n
        elif n is not None and absoluta:
            hora = n + (12.0 if (_re.search(r"\b(tarde|noite|pm)\b", t) and n < 12) else 0.0)
            minutos = mm or 0.0
        elif n is not None and n < 1:          # "meia hora depois"
            minutos = n * 60.0
        elif n is not None:
            hora = (9.0 + n) % 24
            minutos = mm or 0.0
        return {"tipo": "relogio", "hora": hora, "minutos": minutos, "numero": 9}
    numero = 9
    if n is not None and _re.search(r"\b(dia|dias|day|days)\b", t):
        numero = int(max(1, min(14, n)))
    return {"tipo": "calendario", "hora": 9.0, "minutos": 0.0, "numero": numero}
ESCALA_OBJETO_SOZINHO = 2.4  # objeto solto num cartao sem gente
LAVAR_CENARIO = 0.30         # veu da cor do fundo sobre o cenario (0,45 lavava demais)
LAVAR_SEM_GENTE = 0.62       # cartao sem gente: o objeto e' o cartao, o cenario vira sugestao (19/09)
OBJETO_SOZINHO_Y = 0.46      # o objeto sozinho fica no centro do quadro, no ar -- nao deitado no chao (19/09)

# MOVIMENTO DENTRO DO CARTAO (15/09, ordem do dono: "nossa vantagem e' dar
# movimento frame a frame; usaremos isso a nosso favor"). O Madrazzo segura
# um desenho parado por cartao; aqui o boneco ENTRA na pose (do repouso ate'
# o gesto, com um passo alem e volta -- lei 76), respira e balanca o resto
# do cartao em "threes" (tres fases que se revezam a cada ~0,3 s, como
# animacao segurada a mao), o objeto voa da mao ao alvo, a camera avanca
# devagar e a placa da um pulo ao entrar. Tudo em cache por (fase, boca):
# o custo e' um punhado de desenhos por cartao, nao um por quadro.
ENTRADA_S = 0.42            # do repouso ate' a pose
ENTRADA_PASSOS = 7          # quantizacao do k da entrada (7 desenhos)
SOBRA_ENTRADA = 0.07        # overshoot: passa 7% alem da pose e volta
VIDA_CICLO_S = 1.0          # um ciclo de respiracao
VIDA_FASES = 3              # animacao em threes
VIDA_TRONCO = 0.9           # graus
VIDA_CABECA = 1.4
VIDA_BRACO = 2.2
VIDA_QUADRIL = 2.5          # px
PUSH_IN = 0.035             # zoom extra ao longo do cartao
# O GANCHO DE CAMERA (22/09). A bancada da serie mediu o movimento dos 3
# primeiros segundos contra os 12 seguintes (`regua_gancho`, piso 1,0) e ele
# empatava ou perdia: 0,83 e 0,73 em duas de quatro voltas -- o resto do video
# ja corta a cada ~2 s, entao dois cartoes de abertura com um gesto nao se
# destacam. O gancho e' o ponto fraco declarado do canal (memoria do dono: todo
# video precisa de barulho, fala chamativa OU acao). A linguagem de abertura
# de Short e' o empurrao de camera: nos cartoes que COMECAM nos primeiros
# `GANCHO_CAMERA_S`, a camera empurra ~5x mais e o pop de entrada e' mais
# forte. O quadro 0 nao muda (o empurrao comeca em zero), entao o loop, que
# fecha no quadro 0, continua fechando.
GANCHO_CAMERA_S = 2.8
GANCHO_PUSH_IN = 0.16
GANCHO_POP_FORCA = 0.12
POP_PLACA_S = 0.3
POP_PLACA_FORCA = 0.08
VOO_DUR_S = 0.45
VOO_ARCO = 0.35             # altura do arco como fracao da distancia

# NINGUEM SOBREPOE NINGUEM NO CARTAO (16/09, ordem do dono: "evite sobrepor
# os personagens"). As folhas de 15/09 (chave, guarda-chuva, marmita) tinham
# a mao da Maya na cara do Joao, o braco da Vovo' dentro da Maya, o Pal em
# cima da mesa do chefe e meio ator "fantasma" cortado pela borda do plano
# medio. No Madrazzo dois bonecos ficam LADO A LADO com um vao entre eles e
# nenhum cartao mostra metade de alguem. Aqui a guarda mede as SILHUETAS ja'
# desenhadas (lei 33: no frame, nao na largura guardada) e afasta os dois;
# em pose de contato (mao no ombro, entregar, apertar a mao) so' o NUCLEO
# (tronco/cabeca/pernas) precisa estar livre -- o braco cruza, e' a
# linguagem do cut-out. Prop `entre`/`frente` conta como corpo parado.
FOLGA_SILHUETAS = 30.0      # px entre silhuetas de dois atores
FOLGA_PROP = 22.0           # px entre o nucleo do ator e um prop
MARGEM_QUADRO = 16.0        # nenhuma silhueta encosta na borda
MARGEM_JANELA = 0.05        # placas e objetos ficam a 5% da borda da janela do plano
POSES_DE_CONTATO = frozenset(("entregar_objeto", "apertar_mao", "high_five", "cutucar",
                              "empurrar", "bater_no_outro", "mao_no_ombro", "puxar_colarinho"))
ESCALA_OBJETO_SOZINHO_H = 0.26   # cartao sem gente: o objeto mede isto de H (Madrazzo: 25-35%)
OBJETO_MAO_MIN = 0.24            # objeto na mao: no minimo isto da altura do ator (a chave a 8% sumia)


def _ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3.0 - 2.0 * u)


def _k_entrada(t):
    """0 -> 1(+sobra) -> 1: a mao chega, passa um pouco e assenta."""
    if t >= ENTRADA_S:
        return 1.0
    u = t / ENTRADA_S
    if u < 0.72:
        return _ease(u / 0.72) * (1.0 + SOBRA_ENTRADA)
    return 1.0 + SOBRA_ENTRADA * (1.0 - _ease((u - 0.72) / 0.28))


def _kq(k):
    """Quantiza o k da entrada para o cache (ENTRADA_PASSOS desenhos)."""
    if k >= 0.999 and k <= 1.001:
        return 1.0
    return round(k * ENTRADA_PASSOS) / ENTRADA_PASSOS


def _fase(t):
    return int((t / VIDA_CICLO_S) * VIDA_FASES) % VIDA_FASES


def _vida(rig, fase, livres):
    """Os deslocamentos de 'vida' da fase: respiracao no tronco/quadril, a
    cabeca que pende, os bracos LIVRES (sem objeto, sem alvo) que balancam."""
    if fase == 0:
        return rig
    s = 1.0 if fase == 1 else -0.7
    r = dict(rig)
    r["tronco"] = rig.get("tronco", -90.0) + VIDA_TRONCO * s
    r["cabeca"] = rig.get("cabeca", 0.0) + VIDA_CABECA * s
    q = rig["quadril"]
    r["quadril"] = [q[0], q[1] - VIDA_QUADRIL * s]
    for lado in livres:
        b = list(rig.get("braco_" + lado, [90.0, 0.0, 0.0])) + [0.0, 0.0, 0.0]
        sinal = 1.0 if lado == "e" else -1.0
        r["braco_" + lado] = [b[0] + VIDA_BRACO * s * sinal, b[1] + VIDA_BRACO * 0.6 * s * sinal, b[2]]
    return r


CHAVES_ANIMADAS = ("tronco", "cabeca", "braco_e", "braco_d", "perna_e", "perna_d", "quadril")


def _lerp_rig(a, b, k):
    """Interpola so' as chaves animadas; o resto vem de `b` (a pose)."""
    r = dict(b)
    for ch in CHAVES_ANIMADAS:
        va, vb = a.get(ch), b.get(ch)
        if va is None or vb is None:
            continue
        if isinstance(vb, (list, tuple)):
            va = (list(va) + [0.0] * 3)[:len(vb)]
            r[ch] = [x + (y - x) * k for x, y in zip(va, vb)]
        else:
            r[ch] = va + (vb - va) * k
    return r
Z = {"fundo": 0, "faixa": 5, "prop_tras": 10, "ator_atras": 20, "prop_entre": 30,
     "ator": 40, "prop_frente": 50, "objeto_solto": 60, "placa": 70}


# Poses de UM braco escritas com o parceiro a direita (`braco_d`, 0 = direita).
# No modo cena o roteiro nao sabe de que lado esta o outro e o motor injeta
# `lado_alvo` so' nas ACOES_DE_INTERACAO; no cartao a pose e' o cartao inteiro,
# e apontar para fora do quadro (visto na folha de 15/09, cartoes 00 e 05) e'
# o que le como "boneco colado". Quando o outro esta' a esquerda, o braco
# apontado passa para o `braco_e`, refletido.
LOCOMOCAO_NO_CARTAO = {"entrar_andando": "gesticular", "entrar_correndo": "susto", "sair_andando": "dar_de_ombros_virando",
                       "andar": "gesticular", "aproximar": "inclinar_para", "afastar": "recuar", "correr": "susto"}
POSES_PARA_O_OUTRO = frozenset(("apontar", "apresentar"))   # as de interacao ja leem `lado_alvo`


def _espelhar_braco(rig, antes):
    """Reflete no eixo vertical o braco que a pose mexeu: `braco_d` vira
    `braco_e` (e vice-versa). Angulo de tela `a` refletido e' `180 - a`; os
    dois seguintes do osso sao relativos, entao so' trocam de sinal."""
    def _ref(v):
        v = (list(v) + [0.0, 0.0, 0.0])[:3]
        return [180.0 - v[0], -v[1], -v[2]]
    mexeu = {k for k in ("braco_e", "braco_d") if list(rig[k]) != antes[k]}
    if not mexeu:
        return
    novo = {"braco_e": antes["braco_e"], "braco_d": antes["braco_d"]}
    for k in mexeu:
        outro = "braco_e" if k == "braco_d" else "braco_d"
        novo[outro] = _ref(rig[k])
    rig.update(novo)


def _hex(cor, alfa=255):
    if isinstance(cor, (tuple, list)):
        return tuple(int(c) for c in cor[:3]) + (alfa,)
    s = str(cor).lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (alfa,)


# ---------------------------------------------------------------------
class Contexto:
    """O que dura o video inteiro: elenco carregado, medidas, caches."""

    def __init__(self, spec, pasta_partes):
        self.spec = spec
        self.pasta_partes = pasta_partes
        self.chao_y = H * float(spec.get("chao_rel", CHAO_REL))
        self.alt_frac = float(spec.get("altura_ator", ALTURA_ATOR))
        self._pers = {}             # (chave, roupa_json) -> Personagem
        self._natural = {}          # chave -> altura natural em escala 1
        self._pe = {}               # id(pers) -> (base_pes - quadril_y) em repouso
        self.altura_ator = H * self.alt_frac
        self.pastas_objeto = _pastas(spec, pasta_partes, "pasta_objetos", ("objetos", "objeto"))
        self.pastas_prop = list(spec.get("pastas_props") or [])
        self.pastas_acessorio = list(spec.get("pastas_acessorios") or [])
        self.pastas_cenario = _pastas(spec, pasta_partes, "pasta_cenarios", ("cenarios", "cenario"))
        self._cenarios = {}
        self._objetos = {}
        self._placas = {}
        self.inventario_cen = None

    # -- elenco ----------------------------------------------------------
    def _pasta_de(self, chave):
        cfg = (self.spec.get("elenco") or {}).get(chave)
        if isinstance(cfg, str):
            return cfg
        if isinstance(cfg, dict) and cfg.get("pasta"):
            return cfg["pasta"]
        return os.path.join(self.pasta_partes, "..", chave)

    def personagem(self, chave, roupa=None):
        """Personagem carregado, escalado para `altura_ator`, com a roupa."""
        rj = json.dumps(roupa, sort_keys=True) if roupa else ""
        k = (chave, rj)
        if k in self._pers:
            return self._pers[k]
        pasta = self._pasta_de(chave)
        pers = Personagem(pasta)
        if roupa:
            trocadas = ROUPAS.recolorir(pers, roupa)
            print(f"[roupa] {chave}: {', '.join(trocadas) or 'nada recolorido'}")
        if chave not in self._natural:
            pers.escala = 1.0
            rig = merge(REST, {})
            rig["quadril"] = [W / 2.0, H * 0.6]
            bb = desenhar_personagem(pers, rig).getbbox()
            self._natural[chave] = (bb[3] - bb[1]) if bb else 1150.0
        pers.escala = self.altura_ator / self._natural[chave]
        # onde os pes caem em relacao ao quadril, nesta escala
        rig = merge(REST, {})
        rig["quadril"] = [W / 2.0, H * 0.6]
        bb = desenhar_personagem(pers, rig).getbbox()
        self._pe[id(pers)] = (bb[3] - H * 0.6) if bb else self.altura_ator * 0.34
        self._pers[k] = pers
        return pers

    def pe_offset(self, pers):
        return self._pe.get(id(pers), self.altura_ator * 0.34)

    # -- objetos ---------------------------------------------------------
    def objeto(self, nome, escala=1.0, alvo_px=None):
        """(img, ancoras) do objeto do catalogo, na escala do ator -- ou com
        `alvo_px` de lado maior (o objeto sozinho no cartao, que nao tem
        ator para servir de medida)."""
        k = (nome, round(escala, 3), int(alvo_px or 0))
        if k in self._objetos:
            return self._objetos[k]
        from palito_cutout import TAMANHO_OBJETO, TAMANHO_OBJETO_PADRAO
        caminho = _achar_arte(self.pastas_objeto, nome)
        if caminho is None:
            print(f"[objeto] '{nome}' nao existe; seguindo sem ele")
            self._objetos[k] = None
            return None
        img, anc = ANC.ler(caminho)
        # A ARTE DO OBJETO E' ACHATADA PARA O TRACO DO CANAL (16/09, "objetos
        # mal feitos"): sem gradiente, poucos tons, contorno grosso -- ver
        # `estilo.achatar`. E O OBJETO NA MAO E' GRANDE: no Madrazzo a chave
        # tem o tamanho do tronco; a nossa, a 8% do ator, nao aparecia
        if self.spec.get("achatar_objetos", True) and not anc.get("achatado"):
            img = ESTILO.achatar(img)
        frac = max(OBJETO_MAO_MIN, TAMANHO_OBJETO.get(nome, TAMANHO_OBJETO_PADRAO))
        alvo = alvo_px * escala if alvo_px else self.altura_ator * frac * escala
        kk = alvo / max(img.width, img.height, 1)
        img = _reamostrar(img, (max(1, int(img.width * kk)), max(1, int(img.height * kk))))
        anc = ANC.escalar(anc, kk)
        r = max(3, min(7, int(round(min(img.size) * 0.035))))
        img2 = _destacar_objeto(img, esp=r)
        # `_destacar_objeto` cresce r de cada lado: as ancoras andam junto
        anc = ANC._deslocar(anc, r, r)
        self._objetos[k] = (img2, anc)
        return self._objetos[k]

    def placa(self, cfg, tam=None):
        tipo = cfg.get("tipo", "cartaz")
        texto = cfg.get("texto", "")
        extra = {kk: v for kk, v in cfg.items()
                 if kk not in ("tipo", "texto", "x", "y", "escala", "rot", "z", "em", "tam", "mao")}
        if tam is None:
            tam = self.altura_ator * 0.55 * float(cfg.get("escala", 1.0))
        chave = (tipo, texto, int(tam), json.dumps(extra, sort_keys=True))
        if chave in self._placas:
            return self._placas[chave]
        try:
            img, anc = PLACAS.gerar(tipo, texto, tam=int(tam), **extra)
        except TypeError:
            img, anc = PLACAS.gerar(tipo, texto, tam=int(tam))
        rot = float(cfg.get("rot", 0.0))
        if rot:
            img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
            anc = dict(anc)
            anc["pega"] = [img.width / 2.0, img.height * 0.9]
            anc["base"] = [img.width / 2.0, float(img.height)]
        self._placas[chave] = (img, anc)
        return img, anc

    def prop(self, cfg):
        nome = cfg["nome"] if isinstance(cfg, dict) else str(cfg)
        p = PROPS.carregar(nome, self.pastas_prop, self.altura_ator,
                           float(cfg.get("escala", 1.0)) if isinstance(cfg, dict) else 1.0,
                           destacar=bool(cfg.get("destacar")) if isinstance(cfg, dict) else False)
        if p is None:
            return None
        if isinstance(cfg, dict) and cfg.get("z"):
            p.anc = dict(p.anc)
            p.anc["z"] = cfg["z"]
        return p

    def cenario(self, nome):
        if self.inventario_cen is None:
            self.inventario_cen = _inventario(self.pastas_cenario)
        if nome in self._cenarios:
            return self._cenarios[nome]
        cen, motivo = CENARIOS.resolver(nome, self.inventario_cen, "")
        if cen is None:
            self._cenarios[nome] = None
            return None
        caminho = _achar_arte(self.pastas_cenario, cen)
        c = Cenario(Image.open(caminho), chao_rel=CENARIOS.chao_de(cen), foco=CENARIOS.foco_de(cen))
        self._cenarios[nome] = c
        return c


# ---------------------------------------------------------------------
# um ator dentro do cartao
# ---------------------------------------------------------------------
class Ator:
    def __init__(self, ctx, cfg, i, n, props, cartao):
        self.ctx = ctx
        self.cfg = cfg
        self.quem = cfg["quem"]
        acs, roupa = ROUPAS.expandir_papel(cfg.get("papel"), cfg.get("acessorios"), cfg.get("roupa"))
        self.acessorios = acs
        self.pers = ctx.personagem(self.quem, roupa)
        self.expressao = cfg.get("expressao") or cartao.get("expressao") or "neutro"
        self.intensidade = float(cfg.get("intensidade", cartao.get("intensidade", 1.0)))
        # posicao: pedida, ou dividindo o quadro
        if "x" in cfg:
            self.x = float(cfg["x"]) * W
        else:
            self.x = W * (0.5 if n == 1 else (0.30 + 0.40 * i / max(n - 1, 1)))
        self.escala_extra = float(cfg.get("escala", 1.0))
        self.espelhar = bool(cfg.get("espelhar", False))
        self.atras_de = cfg.get("atras_de")
        self.props = props
        self.rig = None
        self.S = None
        self.layer = None
        self.layer_desenhada = None
        self.objeto_mao = None
        self.erro_ik = 0.0
        self.mao_fora, self.lado_outro = "d", 0

    # -- pose --------------------------------------------------------------
    def montar_rig(self, outros):
        pers = self.pers
        if self.escala_extra != 1.0:
            # escala extra por cartao (um close no cartao inteiro, p.ex.)
            pass
        # COPIA FUNDA DO REPOUSO (16/09). `merge` e' rasa e `escutar` soma no
        # `braco_e[1]` NO LUGAR: o REST global ia abrindo os bracos a cada
        # cartao montado (dedos_e a 1, -24, -46 px nas tres tentativas do
        # mesmo cartao), e todo ouvinte do fim do video estava de bracos abertos
        rig = {k: (list(v) if isinstance(v, list) else v) for k, v in REST.items()}
        pe = self.ctx.pe_offset(pers)
        rig["quadril"] = [self.x, self.ctx.chao_y - pe]
        ACOES.aplicar_postura(rig, self.expressao, self.intensidade)
        # o REPOUSO de onde o gesto parte (a entrada interpola daqui ate' a pose)
        self.rig_rest = {k: (list(v) if isinstance(v, list) else v) for k, v in rig.items()}
        # a mao de fora, pela MESMA funcao do modo cena (a copia daqui estava
        # invertida -- lei 91: uma regra, um lugar)
        lado_outro = 0
        if outros:
            ox = outros[0].x
            lado_outro = 1 if ox > self.x else -1
        mao_fora = ACOES.mao_de_fora(self.x)
        self.mao_fora, self.lado_outro = mao_fora, lado_outro
        # poses do catalogo (estado: u=1; gesto: o pico, u=0,5)
        poses = self.cfg.get("poses") or ([self.cfg["pose"]] if self.cfg.get("pose") else [])
        for p in poses:
            a = dict(p) if isinstance(p, dict) else {"nome": p}
            nome = a.get("nome")
            # NO CARTAO NINGUEM ANDA (25/09). `entrar_andando` no pico (u=0,5)
            # deixa o corpo NO MEIO DO CAMINHO, metade fora do quadro -- o Pal
            # cortado na borda do cartao 14 do `serie_v101`. A entrada do
            # cartao ja' e' o movimento; a pose e' o gesto de quem chegou.
            if nome in LOCOMOCAO_NO_CARTAO:
                print(f"[pose] {self.quem}: '{nome}' e' locomocao; no cartao vira '{LOCOMOCAO_NO_CARTAO[nome]}'")
                nome = LOCOMOCAO_NO_CARTAO[nome]
                a = {"nome": nome}
            f = ACOES.CATALOGO.get(nome)
            if f is None:
                print(f"[pose] {self.quem}: '{nome}' nao existe no catalogo; ignorada")
                continue
            a.setdefault("mao", self.cfg.get("mao", mao_fora))
            a.setdefault("lado_alvo", lado_outro or 1)
            if lado_outro:
                a.setdefault("sentido", float(lado_outro))     # entregar_objeto
            a.setdefault("de", 0.0)
            a.setdefault("ate", 1.0)
            a.setdefault("motivo", "cartao")
            u = float(a.get("u", 1.0 if nome in ACOES.ACOES_QUE_FICAM else 0.5))
            antes = {k: list(rig[k]) for k in ("braco_e", "braco_d")}
            try:
                f(u, rig, 2.0, a)
            except Exception as e:                                  # noqa: BLE001
                print(f"[pose] {self.quem}: '{nome}' falhou ({e})")
            if nome in POSES_PARA_O_OUTRO and lado_outro < 0:
                _espelhar_braco(rig, antes)
        self.rig = rig
        # sentar / ajoelhar
        if self.cfg.get("sentar"):
            alvo = self._resolver_ponto("prop:" + str(self.cfg["sentar"]) + ".sentar", outros)
            if alvo is not None:
                IK.sentar(pers, rig, self.ctx.chao_y, max(40.0, self.ctx.chao_y - alvo[1]))
                rig["quadril"][0] = alvo[0] if "x" not in self.cfg else self.x
                self.x = rig["quadril"][0]
            else:
                IK.sentar(pers, rig, self.ctx.chao_y, self.ctx.altura_ator * 0.30)
        elif self.cfg.get("ajoelhar"):
            IK.ajoelhar(pers, rig, self.ctx.chao_y)
        elif self.cfg.get("deitar"):
            ACOES.CATALOGO["cair"](1.0, rig, 2.0, {"nome": "cair", "de": 0, "ate": 1})
        self.rig = rig
        return rig

    def _resolver_ponto(self, ref, outros):
        """'prop:balcao.apoio' | 'ator:zeca.ombro_d' | 'self.peito' | [x, y]"""
        if ref is None:
            return None
        if isinstance(ref, (list, tuple)):
            return (float(ref[0]) * (W if ref[0] <= 1.0 else 1.0),
                    float(ref[1]) * (H if ref[1] <= 1.0 else 1.0))
        ref = str(ref)
        if ref.startswith("prop:"):
            nome, _, sock = ref[5:].partition(".")
            p = self.props.get(nome)
            if p is None:
                print(f"[alvo] {self.quem}: prop '{nome}' nao esta' no cartao")
                return None
            perto = self.S.get("ombro_" + ("d" if p.x > self.x else "e")) if self.S else (self.x, self.rig["quadril"][1])
            return p.socket(sock or "apoio", perto_de=perto)
        if ref.startswith("ator:"):
            nome, _, sock = ref[5:].partition(".")
            for o in outros:
                if o.quem == nome and o.S:
                    p = o.S.get(sock or "ombro_e")
                    if p is None:
                        return None
                    # A MAO POUSA NA BORDA DO OUTRO, NAO DENTRO DELE. O socket
                    # e' o pivo da peca (o ombro e' o centro da junta), e a mao
                    # levada ate' la' entra pelo pescoco do outro (folha de
                    # 15/09, cartao "O RH"). Recua o ponto na direcao de quem
                    # toca, meia largura de mao.
                    if sock in ("ombro_e", "ombro_d", "pescoco", "peito", "topo_peito", "barriga"):
                        rec = 0.055 * self.ctx.altura_ator
                        sinal = -1.0 if o.x > self.x else 1.0
                        p = (p[0] + sinal * rec, p[1] - rec * 0.25)
                    return p
            print(f"[alvo] {self.quem}: ator '{nome}' sem sockets ainda")
            return None
        if ref.startswith("self."):
            return self.S.get(ref[5:]) if self.S else None
        return None

    def aplicar_alvos(self, outros):
        """IK: cada `alvos[]` leva uma mao ate um ponto."""
        self.erro_ik = 0.0
        for a in self.cfg.get("alvos") or []:
            alvo = self._resolver_ponto(a.get("alvo"), outros)
            if alvo is None:
                continue
            mao = a.get("mao") or ("d" if alvo[0] > self.x else "e")
            erro = IK.mao_para(self.pers, self.rig, mao, alvo,
                               cotovelo=a.get("cotovelo", "fora"), centro_x=self.x,
                               ponto=a.get("ponto", "palma"))
            self.erro_ik = max(self.erro_ik, erro)
            if erro > 8:
                print(f"[ik] {self.quem}: mao {mao} ficou a {erro:.0f}px do alvo {a.get('alvo')}")
        self.S = ANC.sockets(self.pers, self.rig)

    def sockets(self):
        self.S = ANC.sockets(self.pers, self.rig)
        return self.S

    # -- desenho -------------------------------------------------------------
    def _objeto_cfg(self):
        ob = self.cfg.get("objeto")
        if not ob:
            return None
        if isinstance(ob, dict) and ob.get("tipo"):
            img, anc = self.ctx.placa(ob, tam=self.ctx.altura_ator * 0.42 * float(ob.get("escala", 1.0)))
            return img, anc
        nome = ob["nome"] if isinstance(ob, dict) else str(ob)
        esc = float(ob.get("escala", 1.0)) if isinstance(ob, dict) else 1.0
        return self.ctx.objeto(nome, esc)

    def fechar_pose(self):
        """Depois dos alvos: o que ainda mexe no rig FINAL (duas maos no
        objeto). Separado do desenho para o rig final existir uma vez so' e
        a entrada poder interpolar ate' ele."""
        objeto = self._objeto_cfg()
        self.duas_canto = None
        if objeto is not None and bool(self.cfg.get("duas_maos")):
            img, anc = objeto
            S = self.S or self.sockets()
            hc = S.get("altura_cranio", 150.0)
            cx, cy = S["peito"][0], S["peito"][1] + hc * 0.35
            pega = anc["pega"]
            pega2 = anc.get("pega2") or [img.width - pega[0], pega[1]]
            canto = (cx - img.width / 2.0, cy - img.height / 2.0)
            p1 = (canto[0] + pega[0], canto[1] + pega[1])
            p2 = (canto[0] + pega2[0], canto[1] + pega2[1])
            if p1[0] > p2[0]:
                p1, p2 = p2, p1
            IK.mao_para(self.pers, self.rig, "e", p1, cotovelo="fora", centro_x=self.x)
            IK.mao_para(self.pers, self.rig, "d", p2, cotovelo="fora", centro_x=self.x)
            self.S = ANC.sockets(self.pers, self.rig)
            self.duas_canto = canto
        # bracos LIVRES: os que a vida pode balancar (sem objeto, sem alvo,
        # sem pose que os ocupe)
        ocupados = set()
        if objeto is not None:
            ocupados.add(self.cfg.get("mao") or self.mao_fora)
            if self.cfg.get("duas_maos"):
                ocupados.update("ed")
        for a in self.cfg.get("alvos") or []:
            ocupados.add(a.get("mao") or "d")
        for lado in "ed":
            if list(self.rig.get("braco_" + lado, [])) != list(self.rig_rest.get("braco_" + lado, [])):
                ocupados.add(lado)
        self.livres = tuple(l for l in "ed" if l not in ocupados)
        self.solta_em = float(self.cfg.get("solta_em", -1.0))
        self.cache = {}

    def rig_em(self, t):
        """O rig no instante `t` do cartao: entrada (repouso -> pose) e vida."""
        k = _kq(_k_entrada(t))
        rig = self.rig if k == 1.0 else _lerp_rig(self.rig_rest, self.rig, k)
        return _vida(rig, _fase(t), self.livres), k

    def camada(self, t, nivel=0.0, pisca=False):
        """A camada do ator no instante t, em cache por (k, fase, boca, pisca, objeto)."""
        k = _kq(_k_entrada(t))
        fase = _fase(t)
        nq = min(NIVEIS_BOCA, key=lambda v: abs(v - nivel))
        com_objeto = not (0.0 <= self.solta_em <= t)
        chave = (k, fase, nq, bool(pisca), com_objeto)
        if chave not in self.cache:
            rig, _ = self.rig_em(t)
            self.cache[chave] = self.desenhar(nq, pisca, rig=rig, com_objeto=com_objeto)
        return self.cache[chave]

    def desenhar(self, nivel=0.0, pisca=False, rig=None, com_objeto=True):
        pers = self.pers
        rig = rig if rig is not None else self.rig
        cara = EXPR.obter(self.expressao, self.intensidade)
        objeto = self._objeto_cfg() if com_objeto else None
        duas = bool(self.cfg.get("duas_maos"))
        S = ANC.sockets(pers, rig)
        pos, ang = S["_pos"], S["_ang"]
        camada = desenhar_personagem(pers, rig, nivel, pisca, None, cara)
        if objeto is not None and duas and getattr(self, "duas_canto", None):
            # o objeto entre as duas maos: segue o meio das palmas
            img, anc = objeto
            pe_, pd_ = S.get("palma_e"), S.get("palma_d")
            if pe_ and pd_:
                pega = anc["pega"]
                pega2 = anc.get("pega2") or [img.width - pega[0], pega[1]]
                mx = (pe_[0] + pd_[0]) / 2.0 - (pega[0] + pega2[0]) / 2.0
                my = (pe_[1] + pd_[1]) / 2.0 - (pega[1] + pega2[1]) / 2.0
                canto = (mx, my)
            else:
                canto = self.duas_canto
            camada.alpha_composite(img, (int(round(canto[0])), int(round(canto[1]))))
            for lado in ("e", "d"):
                self._mao_por_cima(camada, pos, ang, lado, frac=0.0)
        elif objeto is not None:
            img, anc = objeto
            mao = self.cfg.get("mao") or self.mao_fora
            palma = S.get("palma_" + mao)
            if palma is not None:
                pega = anc["pega"]
                # em pe' na palma (compacto) ou continuando o antebraco
                # (alongado: a chave erguida aponta para cima, nao deita
                # atras da mao)
                if anc.get("gravidade"):
                    ang_obj = 0.0
                elif anc.get("alongado"):
                    ang_obj = ang.get("mao_" + mao, -90.0) + 90.0
                else:
                    ang_obj = ang.get("mao_" + mao, 0.0)
                colar(camada, img, (float(pega[0]), float(pega[1])), palma, ang_obj)
                # A MAO INTEIRA POR CIMA (25/09, dono: *"metade da mao do
                # personagem aparece, outra nao"*). Era so' a metade distal
                # (`frac=0,5`): no cabo de uma chave isso le como dedos
                # fechando, mas no objeto CHATO e largo do cartao (carta,
                # boleto, celular) o papel cortava a mao ao meio -- palma
                # sumida atras, dedos boiando na frente. A mao toda sobre o
                # objeto le como "segurando pela frente" em qualquer forma.
                self._mao_por_cima(camada, pos, ang, mao, frac=0.0)
                self.objeto_mao = (img, anc, palma)
        # acessorios por cima de tudo
        if self.acessorios:
            ROUPAS.colar_acessorios(camada, pers, S, self.acessorios, self.ctx.pastas_acessorio)
        if self.espelhar:
            camada = camada.transpose(Image.FLIP_LEFT_RIGHT)
            dx = int(round(2 * self.x - W))
            if dx:
                m = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                m.alpha_composite(camada, (dx, 0)) if dx > 0 else m.alpha_composite(camada.crop((-dx, 0, W, H)), (0, 0))
                camada = m
        return camada

    def _mao_por_cima(self, camada, pos, ang, lado, frac=0.5):
        """A metade DISTAL da mao, redesenhada por cima do objeto: os dedos
        aparecem sobre o cabo e a coisa le como segurada (PLANO-ENCAIXE §2.3)."""
        nome = "mao_" + lado
        if nome not in pos or not self.pers.tem(nome):
            return
        img, piv = self.pers.p(nome)
        if frac > 0.0:
            vx, vy = self.pers.vetor_da_palma(nome)
            n = math.hypot(vx, vy) or 1.0
            ux, uy = vx / n, vy / n
            a = np.asarray(img)
            ys, xs = np.mgrid[0:a.shape[0], 0:a.shape[1]]
            proj = (xs - piv[0]) * ux + (ys - piv[1]) * uy
            comp = float(self.pers.comp.get(nome, n * 2.0)) or n * 2.0
            mask = (proj >= comp * frac).astype(np.uint8) * 255
            recorte = img.copy()
            recorte.putalpha(Image.fromarray(np.minimum(a[..., 3], mask).astype(np.uint8)))
            img = recorte
        colar(camada, img, piv, pos[nome], ang[nome], self.pers.escala)


# ---------------------------------------------------------------------
# a montagem do cartao
# ---------------------------------------------------------------------
class CartaoPronto:
    """Camadas abaixo e acima de quem fala, e a fabrica da camada do falante."""

    def __init__(self):
        self.fundo = None            # RGBA com a sombra de contato ja pintada
        self.estaticas = []          # (z, img, canto): props, objetos parados
        self.vivos = []              # (z, Ator): desenhados por instante
        self.voos = []               # objetos em voo
        self.placas = []             # (z, img, centro, entra_em)
        self.falante = None          # Ator
        self.foco = None             # (cx, cy) para o plano fechado
        self.zoom = 1.0


def _fundo(ctx, cartao, i):
    f = cartao.get("fundo", ctx.spec.get("fundo", FUNDO_PADRAO))
    if isinstance(f, str) and f.startswith("cenario:"):
        cen = ctx.cenario(f[8:])
        if cen is not None:
            x0 = int(cen.ponto_do_trecho(i))
            img = cen.tira.crop((x0, 0, x0 + W, H)).convert("RGBA")
            # O CHAO DO CENARIO VAI PARA O CHAO DO CARTAO. O cenario e' arte
            # de 9:16 com o chao la' embaixo (a legenda do formato dupla
            # fica a 74%); no cartao a legenda vai a 80% e o boneco tem de
            # ficar acima dela. Em vez de descer o boneco, sobe-se o
            # cenario ate' as duas linhas coincidirem e o piso e' replicado
            # por baixo -- piso continua piso.
            dy = int(round(cen.chao_y - ctx.chao_y))
            if dy > 0:
                sub = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                sub.paste(img.crop((0, dy, W, H)), (0, 0))
                # O PISO POR BAIXO E' PISO DE VERDADE, ESPELHADO (22/09).
                #
                # Ele era COR CHAPADA (a media das ultimas linhas) porque
                # esticar 2 linhas de textura virava listras (folha da bet,
                # 16/09) -- mas chapado tambem tem custo, e ele e' grande: o
                # cenario do catalogo tem o chao a ~90% da altura e o cartao o
                # quer a ~66%, entao `dy` passa de 400 px e um quinto do quadro
                # sai sem desenho nenhum. Medido no video `serie_v01` de
                # 22/09: uma faixa lisa de ~20% embaixo, em TODOS os cartoes --
                # e' a mesma queixa que a memoria do canal registra ("nada de
                # faixa vazia no quadro") e o oposto de "o quadro se preenche
                # com arte de cenario de verdade".
                #
                # O que resolve sem esticar nada: a tira de chao que esta
                # colada na borda de baixo do proprio cenario e' piso puro
                # (tabua, tapete, calcada). Ela se repete para baixo
                # ESPELHADA -- espelhar mata a emenda (a ultima linha de uma
                # peca e a primeira da seguinte sao a mesma) e a textura
                # continua textura. O cenario ja vai lavado a 30-62%, entao a
                # inversao da perspectiva nao se le.
                # O CHAO SE ESTICA, NAO SE ESPELHA (22/09). Ladrilhar a tira
                # devolvia a listra (o tapete do quarto tres vezes); espelhar
                # uma vez matou a listra e criou SIMETRIA -- uma borboleta na
                # borda de baixo, visivel no `serie_v007`. O que um chao de
                # verdade faz perto da camera e' ESTICAR: a mesma tabua ocupa
                # mais pixels. Entao a tira de piso colada na borda do cenario
                # e' redimensionada para preencher o vao inteiro. Sem repeticao
                # e sem simetria, porque nao ha copia nenhuma -- ha' uma tira
                # so', maior.
                alt = H - dy
                # A TIRA E' FINA, E ISSO NAO E' DETALHE (22/09, noite).
                #
                # Ela era `dy * 0,8` -- com `dy` passando de 400 px, quase
                # meio quadro de cenario (movel, parede, porta) era esticado
                # para baixo e coberto pelo veu. Queixa do dono, palavra por
                # palavra: *"todos os cenarios do estilo copy estao
                # simplesmente dobrados, onde a parte de cima dobra a parte de
                # baixo porem meio transparente, cortando ele em dois"*. Era
                # isso: o vao nao estava ganhando chao, estava ganhando uma
                # copia fantasma da cena.
                #
                # O que preenche o vao e' PISO, e piso mora nas ultimas linhas
                # do cenario (tabua, tapete, calcada) -- nunca a meia altura.
                # Uma tira fina esticada nao carrega desenho nenhum: vira
                # textura alongada, que e' o que um chao perto da camera e'.
                # O desfoque e o veu logo abaixo terminam o servico.
                # `dy // 8`, e nao `dy // 20`: com a tira fina demais o vao
                # virava COR CHAPADA (a faixa lilas do `serie_v107`), que e' a
                # "faixa vazia no quadro" que o dono ja tinha proibido. Um
                # oitavo do vao ainda e' so' piso -- as ultimas linhas do
                # cenario -- e chega com textura suficiente para o alongamento
                # nao virar tinta.
                k = max(10, min(alt, dy // 8))
                tira = sub.crop((0, alt - k, W, alt))
                banda_bruta = tira.resize((W, dy), Image.BILINEAR)
                # a EMENDA se dissolve: os primeiros pixels da banda sao a
                # continuacao do que esta em cima, nao um corte
                emenda = max(8, dy // 12)
                alfa_e = Image.fromarray(
                    (np.linspace(0, 1, emenda).reshape(-1, 1)
                     .repeat(W, axis=1) * 255).astype(np.uint8), "L")
                topo_real = sub.crop((0, alt - emenda, W, alt))
                banda_bruta.paste(Image.composite(banda_bruta.crop((0, 0, W, emenda)),
                                                  topo_real, alfa_e), (0, 0))
                sub.paste(banda_bruta, (0, alt))
                # O CHAO PERTO DA CAMERA SAI DE FOCO, e e' isso que apaga o
                # espelho. Num cenario de piso liso o espelho e' invisivel; num
                # piso com desenho (o ladrilho da cozinha, o tapete) ele vira
                # simetria -- uma borboleta na borda de baixo, que foi o que a
                # prova do `serie_v007` mostrou. Desfocar resolve as duas
                # coisas de uma vez: mata a simetria e e' o que uma lente faz
                # com o chao a um palmo dela. Por cima, o veu para a cor media,
                # de 0,2 na emenda a 0,85 na borda -- assim os ultimos pixels
                # sao cor, e nao desenho invertido.
                banda = sub.crop((0, alt, W, H)).filter(
                    ImageFilter.GaussianBlur(4))
                media = np.asarray(banda.convert("RGB")).reshape(-1, 3).mean(axis=0)
                veu_cor = tuple(int(c) for c in media)
                # 0,15 a 0,55 desde 23/09: com 0,85 na borda os ultimos pixels
                # eram TINTA, e o rodape do `serie_v107` saiu como uma faixa
                # lilas lisa -- o oposto de "o quadro se preenche com arte de
                # cenario de verdade". O veu existe para matar a inversao de
                # perspectiva, nao para apagar o chao.
                grad = np.linspace(0.15, 0.55, dy).reshape(-1, 1)
                alfa = Image.fromarray((np.repeat(grad, W, axis=1) * 255)
                                       .astype(np.uint8), "L")
                chapado = Image.new("RGBA", (W, dy), veu_cor + (255,))
                sub.paste(Image.composite(chapado, banda, alfa), (0, alt))
                img = sub
            elif dy < 0:
                sub = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                sub.paste(img, (0, -dy))
                teto = img.crop((0, 0, W, 2)).resize((W, -dy), Image.BILINEAR)
                sub.paste(teto, (0, 0))
                img = sub
            lav = float(cartao.get("lavar", ctx.spec.get("cenario_lavado", LAVAR_CENARIO)))
            # CARTAO SEM GENTE LAVA MAIS (19/09): o boleto sozinho num banheiro
            # a 30% lia como lixo no chao -- o cenario disputava com o objeto,
            # que E' o cartao. No Madrazzo o objeto sozinho fica sobre fundo
            # quase liso. O spec pode mandar por cima com `lavar`.
            if "lavar" not in cartao and not (cartao.get("atores") or []):
                lav = max(lav, LAVAR_SEM_GENTE)
            if lav > 0:
                veu = Image.new("RGBA", (W, H), _hex(ctx.spec.get("fundo", FUNDO_PADRAO), int(255 * lav)))
                img.alpha_composite(veu)
            return img, ctx.chao_y
        f = ctx.spec.get("fundo", FUNDO_PADRAO)
    img = Image.new("RGBA", (W, H), _hex(f))
    return img, None


def _faixa(img, cor, chao_y, alt_ator):
    """A faixa de cor atras dos atores (o verde-dinheiro do Madrazzo)."""
    d = ImageDraw.Draw(img)
    y1 = int(chao_y + alt_ator * 0.04)
    y0 = int(chao_y - alt_ator * 0.62)
    d.rectangle([-10, y0, W + 10, y1], fill=_hex(cor), outline=(24, 20, 18, 255), width=7)
    # um padrao leve de listras para nao ser cor chapada pura
    for x in range(0, W, 46):
        d.line([x, y0 + 8, x + 18, y0 + 8], fill=_hex(cor, 0), width=1)
    return img


def compor(ctx, cartao, i):
    """Monta o cartao `i` e devolve um CartaoPronto."""
    pronto = CartaoPronto()
    fundo, chao_cen = _fundo(ctx, cartao, i)
    # COM CENARIO O CHAO E' O DESENHADO (lei 27): atores e props pousam na
    # linha que `cenarios.py` anotou, nao na linha padrao do cartao -- na
    # tira de 15/09 os pes ficavam meio metro acima das mesas do fundo
    chao_y = float(chao_cen) if chao_cen else ctx.chao_y
    chao_padrao = ctx.chao_y
    ctx.chao_y = chao_y
    camadas = []                   # (z, imagem, canto)

    if cartao.get("faixa") or (ctx.spec.get("faixa") and cartao.get("faixa") is not False):
        _faixa(fundo, cartao.get("faixa") or ctx.spec.get("faixa"), chao_y, ctx.altura_ator)

    # -- props e atores ------------------------------------------------------------
    # A guarda de sobreposicao pode pedir um prop MENOR (a mesa que nao deixa
    # lado livre para o Pal) ou um objeto de mao menor (o documento erguido
    # que sai pelo alto): ai' props e atores sao montados de novo, uma vez.
    cfgs = cartao.get("atores") or []
    fatores = {}
    for tentativa in range(4):
        props, camadas_props = _montar_props(ctx, cartao, chao_y, fatores)
        atores = [Ator(ctx, _cfg_com_fator(c, fatores), k, len(cfgs), props, cartao) for k, c in enumerate(cfgs)]
        _montar_atores(atores)
        pedido = _afastar(atores, props, i)
        if not pedido:
            break
        for k, f in pedido.items():
            fatores[k] = fatores.get(k, 1.0) * f
    camadas += camadas_props
    falante = None
    quem_fala = cartao.get("ator")
    if quem_fala and not cartao.get("narracao"):
        falante = next((a for a in atores if a.quem == quem_fala), None)
    pronto.falante = falante
    # a camada FINAL de cada ator (pose assentada): sombra, enquadramento
    pronto.vivos = []                 # (z, ator)
    for a in atores:
        z = Z["ator_atras"] if a.atras_de else Z["ator"]
        pronto.vivos.append((z + 0.001 * atores.index(a), a))

    # -- objetos soltos (parados, ou em VOO da mao ao lugar) ---------------------
    pronto.voos = []                  # (z, img, origem, destino, inicio, dur, giro)
    for oc in cartao.get("objetos") or []:
        oc = oc if isinstance(oc, dict) else {"nome": oc}
        # cartao SEM GENTE: o objeto e' o cartao, e sai grande (o celular a
        # 13% da altura do ator, sozinho no quadro, era um pingo na folha).
        # Medido do Madrazzo (16/09): o objeto sozinho ocupa 25-35% de H.
        esc = float(oc.get("escala", 1.0))
        if not oc.get("tipo"):
            ob = ctx.objeto(oc["nome"], esc, alvo_px=None if cfgs else H * ESCALA_OBJETO_SOZINHO_H)
        else:
            ob = ctx.placa(oc, tam=(ctx.altura_ator * 0.45 if cfgs else H * ESCALA_OBJETO_SOZINHO_H * 0.9) * esc)
        if ob is None:
            continue
        img, anc = ob
        x = float(oc.get("x", 0.5)) * W
        y = chao_y
        # SEM GENTE E SEM APOIO O OBJETO FLUTUA NO CENTRO (19/09): pousado na
        # linha do chao ele saia pequeno e baixo, ao lado do vaso sanitario,
        # como coisa caida. O Madrazzo mostra o objeto solto no meio do quadro,
        # como icone. Com `em` (prop) ou `y` explicito, o spec manda.
        if not cfgs and not oc.get("em") and "y" not in oc and not oc.get("tipo"):
            y = OBJETO_SOZINHO_Y * H + img.height / 2.0
        if oc.get("em"):
            nome, _, sock = str(oc["em"]).replace("prop:", "").partition(".")
            base = props.get(nome)
            if base is not None:
                pt = base.socket(sock or "tampo", perto_de=(x, chao_y))
                if pt:
                    x = pt[0] if "x" not in oc else x
                    y = pt[1]
        if "y" in oc:
            y = float(oc["y"]) * H
        b = anc["base"]
        rot = float(oc.get("rot", 0.0))
        if rot:
            img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
            b = [img.width / 2.0, float(img.height)]
        canto = (int(x - b[0]), int(y - b[1]))
        voo = oc.get("voo")
        if voo:
            # de onde sai: 'ator:pal.palma_d' (a mao que solta), ou [x, y]
            voo = voo if isinstance(voo, dict) else {"de": voo}
            origem = None
            de = voo.get("de")
            if isinstance(de, str) and de.startswith("ator:"):
                nome, _, sock = de[5:].partition(".")
                for a in atores:
                    if a.quem == nome and a.S:
                        origem = a.S.get(sock or "palma_d")
            elif isinstance(de, (list, tuple)):
                origem = (float(de[0]) * W, float(de[1]) * H)
            if origem is not None:
                inicio = float(voo.get("inicio", ENTRADA_S))
                # quem solta, solta na hora em que o objeto parte
                for a in atores:
                    if isinstance(de, str) and de.startswith("ator:" + a.quem) and a.solta_em < 0:
                        a.solta_em = inicio
                        a.cache = {}
                pronto.voos.append((Z["objeto_solto"], img, (origem[0] - img.width / 2.0, origem[1] - img.height / 2.0),
                                    canto, inicio, float(voo.get("dur", VOO_DUR_S)), float(voo.get("giro", rot))))
                continue
        camadas.append((Z["objeto_solto"], img, canto))

    # -- placas soltas (com o pulo de entrada) ------------------------------------
    pronto.placas = []                # (z, img, centro)
    for pc in cartao.get("placas") or []:
        # sem gente no cartao a placa E' o cartao: sai maior (Madrazzo: o
        # documento sozinho toma o terco central)
        img, anc = ctx.placa(pc, tam=None if cfgs else ctx.altura_ator * 0.72 * float(pc.get("escala", 1.0)))
        x = float(pc.get("x", 0.5)) * W
        y = float(pc.get("y", 0.30)) * H
        pronto.placas.append((Z["placa"], img, (x, y), float(pc.get("entra_em", 0.0))))

    # -- salto de tempo: cartao sem gente com o calendario OU o relogio -------------
    # O objeto do salto sai do TEXTO (19/09): "UMA HORA DEPOIS" com calendario
    # foi o que o dono viu no video. `salto_tipo`/`salto_hora`/`salto_numero`
    # no spec continuam mandando por cima; sem eles, `ler_salto` decide.
    if cartao.get("salto") and not cfgs and not cartao.get("placas"):
        lido = ler_salto(cartao["salto"])
        tipo_s = cartao.get("salto_tipo") or lido["tipo"]
        cfg_s = {"tipo": tipo_s, "texto": cartao["salto"]}
        if tipo_s == "relogio":
            cfg_s["hora"] = float(cartao.get("salto_hora", lido["hora"]))
            cfg_s["minutos"] = float(cartao.get("salto_minutos", lido["minutos"]))
        else:
            cfg_s["numero"] = int(cartao.get("salto_numero", lido["numero"]))
        img, anc = ctx.placa(cfg_s, tam=ctx.altura_ator * 0.9)
        pronto.placas.append((Z["placa"], img, (W / 2.0, H * 0.42), 0.0))

    # -- sombras de contato, sob os pes de cada ator (no fundo, antes de tudo) ----
    if cartao.get("sombra", ctx.spec.get("sombra", True)):
        for a in atores:
            if a.layer_desenhada is not None:
                _sombra_de_contato(fundo, a.layer_desenhada, chao_y)

    # -- composicao: o estatico fica pronto; ator, voo e placa entram por instante -----
    camadas.sort(key=lambda c: c[0])
    pronto.fundo = fundo
    pronto.estaticas = camadas

    # -- plano ---------------------------------------------------------------------
    plano = cartao.get("plano", "aberto")
    zoom = {"aberto": 1.0, "medio": 1.35, "close": 1.9}.get(plano, float(plano) if str(plano).replace(".", "").isdigit() else 1.0)
    # O QUE TEM TEXTO OU E' A PIADA FICA INTEIRO NA JANELA (16/09, "muitos
    # objetos cortados"): placas, o letreiro do prop, o objeto na mao
    extras = [(c[0] - im.width / 2.0, c[1] - im.height / 2.0, c[0] + im.width / 2.0, c[1] + im.height / 2.0)
              for z, im, c, e in pronto.placas]
    for p in props.values():
        r = p.rect_socket("texto")
        if r and (cartao.get("props") and any((pc.get("placa") if isinstance(pc, dict) else None)
                                                 and (pc.get("nome") == p.nome) for pc in cartao["props"])):
            a_, b_ = p.para_tela((r[0], r[1])), p.para_tela((r[2], r[3]))
            extras.append((a_[0], a_[1], b_[0], b_[1]))
    pronto.zoom, pronto.foco = _janela(atores, falante, plano, zoom, i, extras)
    # PLACAS E OBJETOS SOLTOS DENTRO DA JANELA (folha de 15/09: etiqueta de
    # R$ 350 e o X sobre a nota cortados pela borda; o calendario do salto
    # encostado no alto). O que o roteiro pediu para ler tem de estar inteiro.
    x0, y0, x1, y1 = _caixa_da_janela(pronto.zoom, pronto.foco)
    y_leg = H * float(ctx.spec.get("legenda_y", LEGENDA_Y)) - H * 0.06
    # a faixa do cartaz de titulo (alto do quadro) fica livre: o balao
    # "DE NOVO?" subiu para cima da cabeca e bateu no titulo (16/09)
    caixa = (x0, max(y0, H * 0.13), x1, min(y1, y_leg))
    cabecas = [c for c in (_cabeca(a) for a in atores) if c]
    pronto.placas = [(z, im, _longe_das_caras(_dentro(centro, im, caixa), im, caixa, cabecas), e)
                     for z, im, centro, e in pronto.placas]
    pronto.placas = _sem_se_cobrir(pronto.placas, caixa)
    if atores:
        antes = list(pronto.placas)
        pronto.placas, pior = _fora_dos_corpos(antes, caixa, atores, i)
        # no plano FECHADO nao ha onde por a placa sem tapar o boneco: o plano
        # abre (a placa e' o dado da frase, o close e' so' enquadramento)
        if pior > PLACA_COBRE_MAX and pronto.foco is not None:
            print(f"[cartao {i:02d}] placa cobre {pior:.0%} do corpo no plano fechado: abrindo o plano")
            pronto.zoom, pronto.foco = 1.0, None
            caixa = (MARGEM_JANELA * W, max(MARGEM_JANELA * H, H * 0.13), W * (1 - MARGEM_JANELA), min(H * (1 - MARGEM_JANELA), y_leg))
            pronto.placas, pior = _fora_dos_corpos(antes, caixa, atores, i)
    if not cfgs:
        pronto.estaticas = [(z, im, _dentro_canto(canto, im, caixa))
                            if z == Z["objeto_solto"] else (z, im, canto)
                            for z, im, canto in pronto.estaticas]
    pronto.atores = atores
    pronto.props = props
    ctx.chao_y = chao_padrao
    return pronto


# ---------------------------------------------------------------------
# a guarda de sobreposicao e a janela do plano
# ---------------------------------------------------------------------
def _montar_props(ctx, cartao, chao_y, fatores):
    """Os props do cartao, pousados no chao; `fatores['prop:<nome>']` encolhe
    um prop que a guarda pediu menor. Devolve (props, camadas)."""
    props, camadas = {}, []
    for j, pc in enumerate(cartao.get("props") or []):
        pc = dict(pc) if isinstance(pc, dict) else {"nome": pc}
        f = fatores.get("prop:" + str(pc["nome"]))
        if f:
            pc["escala"] = float(pc.get("escala", 1.0)) * f
        p = ctx.prop(pc)
        if p is None:
            continue
        x = float(pc.get("x", 0.5)) * W
        y = chao_y + float(pc.get("dy", 0.0)) * ctx.altura_ator
        if pc.get("em"):
            # em cima de outro prop: 'prop:mesa.tampo'
            ref = str(pc["em"])
            nome, _, sock = ref.replace("prop:", "").partition(".")
            base = props.get(nome)
            if base is not None:
                pt = base.socket(sock or "tampo", perto_de=(x, chao_y))
                if pt:
                    x, y = (pt[0] if "x" not in pc else x), pt[1]
        p.colocar(x, y)
        if pc.get("placa"):
            pl, _ = ctx.placa(pc["placa"], tam=ctx.altura_ator * 0.9)
            p = p.com_placa(pl, pc["placa"].get("em", "texto"))
        props[p.nome] = p
        for znome, im, canto in p.camadas():
            camadas.append((Z["prop_" + znome] + j * 0.01, im, canto))
    return props, camadas


def _cfg_com_fator(cfg, fatores):
    """O cfg do ator com o objeto de mao encolhido, se a guarda pediu."""
    if fatores.get("fechar:" + str(cfg.get("quem"))):
        # a guarda pediu pose fechada: `escutar`, sem alvo, o objeto fica
        cfg = {k: v for k, v in cfg.items() if k not in ("pose", "poses", "alvos")}
        cfg["pose"] = "escutar"
        cfg["_fechado"] = True
    f = fatores.get("objeto:" + str(cfg.get("quem")))
    if not f or not cfg.get("objeto"):
        return cfg
    ob = cfg["objeto"]
    ob = dict(ob) if isinstance(ob, dict) else {"nome": ob}
    ob["escala"] = float(ob.get("escala", 1.0)) * f
    return dict(cfg, objeto=ob)


def _montar_atores(atores):
    """Rig, sockets, IK (dois passes: quem mira o outro precisa dos sockets
    do outro), pose fechada e a camada FINAL de cada um."""
    for a in atores:
        a.montar_rig([o for o in atores if o is not a])
        a.sockets()
    for _ in range(2):
        for a in atores:
            a.aplicar_alvos([o for o in atores if o is not a])
    for a in atores:
        a.fechar_pose()
        a.layer_desenhada = a.camada(ENTRADA_S + 1.0, 0.0, False)


def _colunas(img, nucleo=False):
    """Colunas de tela ocupadas pela figura: silhueta inteira, ou so' o
    NUCLEO (tronco/cabeca/pernas -- lei 33, `colunas_de_corpo`)."""
    if img is None:
        return np.zeros(W, dtype=bool)
    if nucleo:
        from palito_cutout import colunas_de_corpo
        return colunas_de_corpo(img)
    return (np.asarray(img)[..., 3] > 32).any(axis=0)


def _extremos(cols):
    xs = np.nonzero(cols)[0]
    return (int(xs[0]), int(xs[-1])) if len(xs) else None


def _toca_o_outro(a):
    """Pose de CONTATO: a mao vai ate' o outro, e o braco pode cruzar."""
    if any(str(x.get("alvo", "")).startswith("ator:") for x in (a.cfg.get("alvos") or [])):
        return True
    poses = a.cfg.get("poses") or ([a.cfg["pose"]] if a.cfg.get("pose") else [])
    nomes = {(p.get("nome") if isinstance(p, dict) else p) for p in poses}
    return bool(nomes & POSES_DE_CONTATO)


def _mira_o_prop(a, nome):
    return any(str(x.get("alvo", "")).startswith("prop:" + nome) for x in (a.cfg.get("alvos") or []))


def _cabeca(a):
    """(x0, y0, x1, y1) da cabeca do ator na tela, pelos sockets."""
    S = a.S or {}
    if not S.get("olhos"):
        return None
    hc = S.get("altura_cranio", 150.0)
    lc = S.get("largura_cabeca", hc * 0.8)
    topo = S.get("topo_cabeca", (S["olhos"][0], S["olhos"][1] - hc * 0.55))[1]
    queixo = S.get("queixo", (S["olhos"][0], S["olhos"][1] + hc * 0.5))[1]
    return (S["olhos"][0] - lc / 2.0, topo, S["olhos"][0] + lc / 2.0, queixo)


def _mover(a, dx):
    a.x += dx
    a.cfg = dict(a.cfg, x=a.x / W)


def _afastar(atores, props, i):
    """NINGUEM SOBREPOE NINGUEM NO CARTAO. Mede as silhuetas desenhadas e
    afasta: ator de prop (`entre`/`frente`, so' quem nao esta' atras dele,
    sentado nele ou mirando nele com a mao) e ator de ator. Quem cede move
    o quadril e e' montado de novo -- a pose por alvo depende do x. Ate' 3
    voltas; o que sobrar e' dito no log com endereco."""
    pedidos = {}
    if not atores:
        return pedidos
    for volta in range(3):
        mexeu = False
        # -- ninguem cortado pela borda do quadro (a etiqueta na mao conta) -------
        for a in atores:
            sil = _extremos(_colunas(a.layer_desenhada))
            if sil is None:
                continue
            # pelo ALTO: o documento erguido em `mostrar_objeto` saia do quadro
            # (folha da marmita, "O CHEFE"). O ator nao desce (os pes sao do
            # chao), entao o objeto na mao encolhe ate' caber
            bb = a.layer_desenhada.getbbox()
            if bb and bb[1] < MARGEM_QUADRO and a.objeto_mao is not None and "objeto:" + a.quem not in pedidos:
                img = a.objeto_mao[0]
                f = max(0.45, (img.height - (MARGEM_QUADRO - bb[1]) * 1.15) / max(1.0, img.height))
                pedidos["objeto:" + a.quem] = f
                print(f"[cartao {i:02d}] o objeto na mao de {a.quem} sai pelo alto: encolhendo para {f:.2f}")
            sil = list(sil)
            # a camada e' do tamanho do quadro: o que a mao segura pode ja'
            # estar CORTADO nela (a etiqueta de R$ 350 do Joao). Se a silhueta
            # encosta na borda, o alcance do objeto entra na conta pelo raio
            # em volta da pega
            if sil[0] <= 1 or sil[1] >= W - 2:
                # cortado na camada: o que se sabe e' onde estao as juntas
                xs = [p[0] for k, p in (a.S or {}).items() if not k.startswith("_") and isinstance(p, tuple)]
                if xs:
                    folga = 0.06 * a.ctx.altura_ator
                    sil[0] = min(sil[0], min(xs) - folga)
                    sil[1] = max(sil[1], max(xs) + folga)
                if a.objeto_mao is not None:
                    img, anc, palma = a.objeto_mao[:3]
                    px, py = anc["pega"]
                    r = max(math.hypot(x - px, y - py) for x, y in ((0, 0), (img.width, 0), (0, img.height), (img.width, img.height)))
                    sil[0] = min(sil[0], palma[0] - r * 0.8)
                    sil[1] = max(sil[1], palma[0] + r * 0.8)
            dx = 0.0
            if sil[0] < MARGEM_QUADRO:
                dx = MARGEM_QUADRO - sil[0]
            elif sil[1] > W - MARGEM_QUADRO:
                dx = (W - MARGEM_QUADRO) - sil[1]
            if abs(dx) >= 6.0 and (sil[1] - sil[0]) < W - 2 * MARGEM_QUADRO:
                print(f"[cartao {i:02d}] {a.quem} saia pela borda: x {a.x:.0f} -> {a.x + dx:.0f}")
                _mover(a, dx)
                mexeu = True
        if mexeu:
            _montar_atores(atores)
            mexeu = False
        # -- alvo num prop fora do alcance: o ator chega mais perto ---------------
        for a in atores:
            if a.erro_ik <= 8 or a.cfg.get("sentar"):
                continue
            for x in (a.cfg.get("alvos") or []):
                ref = str(x.get("alvo", ""))
                if not ref.startswith("prop:"):
                    continue
                p = props.get(ref[5:].partition(".")[0])
                if p is None:
                    continue
                sinal = 1.0 if p.x > a.x else -1.0
                dx = sinal * a.erro_ik * 1.05
                # chega perto, mas o NUCLEO para antes do prop (nao se entra
                # na porta para alcancar a maçaneta)
                nuc = _extremos(_colunas(a.layer_desenhada, nucleo=True))
                pc = _extremos((np.asarray(p.img)[..., 3] > 32).any(axis=0))
                if nuc and pc:
                    cx0, cx1 = p.canto()[0] + pc[0], p.canto()[0] + pc[1]
                    if sinal > 0:
                        dx = min(dx, max(0.0, (cx0 - FOLGA_PROP) - nuc[1]))
                    else:
                        dx = max(dx, min(0.0, (cx1 + FOLGA_PROP) - nuc[0]))
                if abs(dx) < 1.0:
                    continue
                print(f"[cartao {i:02d}] {a.quem} nao alcanca '{p.nome}' ({a.erro_ik:.0f}px): "
                      f"x {a.x:.0f} -> {a.x + dx:.0f}")
                _mover(a, dx)
                a.erro_ik = 0.0
                mexeu = True
                break
        if mexeu:
            _montar_atores(atores)
            mexeu = False
        # -- props como corpo parado -------------------------------------------
        for a in atores:
            if a.atras_de or a.cfg.get("sentar"):
                continue
            nuc = _extremos(_colunas(a.layer_desenhada, nucleo=True))
            sil = _extremos(_colunas(a.layer_desenhada))
            if nuc is None or sil is None:
                continue
            for p in props.values():
                # prop `tras` e' pano de fundo (fachada, porta encostada na
                # parede) -- a nao ser que o ator o esteja TOCANDO: ai' ele fica
                # ao lado, nunca na frente
                if (p.z == "tras" and not _mira_o_prop(a, p.nome)) or p.nome == a.cfg.get("sentar"):
                    continue
                pc = _extremos((np.asarray(p.img)[..., 3] > 32).any(axis=0))
                if pc is None:
                    continue
                cx0, cx1 = p.canto()[0] + pc[0], p.canto()[0] + pc[1]
                if nuc[1] + FOLGA_PROP < cx0 or nuc[0] - FOLGA_PROP > cx1:
                    continue
                # para que lado e' mais perto sair
                esq = (cx0 - FOLGA_PROP) - nuc[1]          # negativo: recua para a esquerda
                dir_ = (cx1 + FOLGA_PROP) - nuc[0]         # positivo: avanca para a direita
                cabe_esq = sil[0] + esq >= MARGEM_QUADRO
                cabe_dir = sil[1] + dir_ <= W - MARGEM_QUADRO
                if cabe_esq and (not cabe_dir or abs(esq) <= dir_):
                    dx = esq
                elif cabe_dir:
                    dx = dir_
                else:
                    # sem lado livre: o prop e' que encolhe (a mesa de 700 px
                    # nao deixava o Pal ficar em frente a ela com o Zeca atras)
                    if "prop:" + p.nome not in pedidos:
                        larg = float(cx1 - cx0)
                        preciso = min(abs(esq), dir_) + FOLGA_PROP
                        f = max(0.55, (larg - preciso) / max(1.0, larg))
                        pedidos["prop:" + p.nome] = f
                        print(f"[cartao {i:02d}] {a.quem} sobrepoe o prop '{p.nome}' e nao ha lado livre: "
                              f"prop encolhe para {f:.2f}")
                    continue
                print(f"[cartao {i:02d}] {a.quem} sobre o prop '{p.nome}': x {a.x:.0f} -> {a.x + dx:.0f}")
                a.x += dx
                a.cfg = dict(a.cfg, x=a.x / W)
                mexeu = True
        if mexeu:
            _montar_atores(atores)
        # -- ator com ator ---------------------------------------------------------
        if len(atores) == 2:
            A, B = sorted(atores, key=lambda a: a.x)
            contato = _toca_o_outro(A) or _toca_o_outro(B) or getattr(A, "_so_nucleo", False)
            ea = _extremos(_colunas(A.layer_desenhada, nucleo=contato))
            eb = _extremos(_colunas(B.layer_desenhada, nucleo=contato))
            sa = _extremos(_colunas(A.layer_desenhada))
            sb = _extremos(_colunas(B.layer_desenhada))
            if ea and eb and sa and sb:
                falta = (ea[1] + FOLGA_SILHUETAS) - eb[0]
                if falta > 0 and not contato:
                    # O QUADRO NAO TEM ESPACO para as duas silhuetas (bracos
                    # abertos dos dois lados): degrada para a regra de contato
                    # -- nucleo livre, braco pode cruzar -- em vez de empurrar
                    # alguem para fora do quadro ou cortar o que esta' na mao
                    sobra = (sa[0] - MARGEM_QUADRO) + ((W - MARGEM_QUADRO) - sb[1])
                    # SEM ESPACO, QUEM ABRE MAIS OS BRACOS FECHA A POSE (25/09).
                    # Aceitar o braco cruzando era a "sobreposicao errada" que o
                    # dono viu: o braco do Pal passando por cima da Maria no
                    # cartao de abertura. Antes de ceder, o ator de gesto mais
                    # largo (silhueta menos nucleo) e que nao fala passa a
                    # `escutar` -- uma vez so'; se ainda faltar, a regra velha.
                    if sobra < falta:
                        def _abre(a):
                            s_, n_ = _extremos(_colunas(a.layer_desenhada)), _extremos(_colunas(a.layer_desenhada, nucleo=True))
                            return (s_[1] - s_[0]) - (n_[1] - n_[0]) if s_ and n_ else 0
                        cands = [a for a in (A, B) if not a.cfg.get("_fechado") and "fechar:" + a.quem not in pedidos]
                        if cands:
                            X = max(cands, key=lambda a: (not getattr(a, "fala", False), _abre(a)))
                            pedidos["fechar:" + X.quem] = 1.0
                            print(f"[cartao {i:02d}] {A.quem} e {B.quem}: faltam {falta - sobra:.0f}px no quadro; "
                                  f"{X.quem} fecha a pose (escutar) em vez de cruzar o braco")
                            return pedidos
                        A._so_nucleo = True
                        print(f"[cartao {i:02d}] {A.quem} e {B.quem}: faltam {falta - sobra:.0f}px no quadro "
                              f"para as silhuetas; aceitando braco cruzando (nucleos livres)")
                        contato = True
                        ea = _extremos(_colunas(A.layer_desenhada, nucleo=True))
                        eb = _extremos(_colunas(B.layer_desenhada, nucleo=True))
                        falta = (ea[1] + FOLGA_SILHUETAS) - eb[0]
                if contato:
                    # o braco pode cruzar o tronco do outro, nunca a CARA dele
                    # (folha de 15/09: a mao da Maya na cara do Joao ao entregar)
                    for quem, outro, lado in ((A, B, +1), (B, A, -1)):
                        cab = _cabeca(outro)
                        if cab is None or quem.layer_desenhada is None:
                            continue
                        y0, y1 = max(0, int(cab[1])), min(H, int(cab[3]))
                        faixa = (np.asarray(quem.layer_desenhada)[y0:y1, :, 3] > 32).any(axis=0)
                        ext = _extremos(faixa)
                        if ext is None:
                            continue
                        f2 = (ext[1] + FOLGA_SILHUETAS) - cab[0] if lado > 0 else (cab[2] + FOLGA_SILHUETAS) - ext[0]
                        falta = max(falta, f2)
                if falta > 0:
                    da, db = -falta / 2.0, falta / 2.0
                    sobra_a = max(0.0, sa[0] - MARGEM_QUADRO)            # quanto A ainda recua
                    sobra_b = max(0.0, (W - MARGEM_QUADRO) - sb[1])      # quanto B ainda avanca
                    if -da > sobra_a:
                        db += (-da - sobra_a)
                        da = -sobra_a
                    if db > sobra_b:
                        da -= (db - sobra_b)
                        db = sobra_b
                    da = max(da, -sobra_a)
                    resto = falta - (db - da)
                    print(f"[cartao {i:02d}] {A.quem} e {B.quem} se sobrepoem em {falta:.0f}px"
                          f"{' (contato: so o nucleo conta)' if contato else ''}: "
                          f"x {A.x:.0f}/{B.x:.0f} -> {A.x + da:.0f}/{B.x + db:.0f}"
                          + (f"; faltam {resto:.0f}px que o quadro nao tem" if resto > 1 else ""))
                    if abs(da) > 1.5 or abs(db) > 1.5:
                        A.x += da
                        B.x += db
                        A.cfg = dict(A.cfg, x=A.x / W)
                        B.cfg = dict(B.cfg, x=B.x / W)
                        _montar_atores(atores)
                        mexeu = True
                    else:
                        return pedidos
        if not mexeu:
            return pedidos
    return pedidos


def _caixa_da_janela(zoom, foco):
    """(x0, y0, x1, y1) da janela do plano no FIM do cartao (com o push-in),
    com a margem interna: o que ficar dentro esta' inteiro o cartao todo."""
    z = zoom * (1.0 + PUSH_IN)
    jw, jh = W / z, H / z
    cx, cy = foco if foco else (W / 2.0, H / 2.0)
    x0 = max(0.0, min(W - jw, cx - jw / 2.0))
    y0 = max(0.0, min(H - jh, cy - jh / 2.0))
    mx, my = jw * MARGEM_JANELA, jh * MARGEM_JANELA
    return (x0 + mx, y0 + my, x0 + jw - mx, y0 + jh - my)


def _dentro(centro, im, caixa):
    """O centro da placa movido para a imagem caber na caixa."""
    x0, y0, x1, y1 = caixa
    hw, hh = im.width / 2.0, im.height / 2.0
    cx = min(max(centro[0], x0 + hw), x1 - hw) if x1 - x0 > im.width else (x0 + x1) / 2.0
    cy = min(max(centro[1], y0 + hh), y1 - hh) if y1 - y0 > im.height else (y0 + y1) / 2.0
    return (cx, cy)


def _longe_das_caras(centro, im, caixa, cabecas):
    """A placa nao cobre cara de ninguem (lei 23: nada flutua sobre o
    personagem). Se cobre, vai para o lado com mais espaco na janela; se
    nao ha lado, sobe ate' ficar acima da cabeca."""
    hw, hh = im.width / 2.0, im.height / 2.0
    x0, y0, x1, y1 = caixa
    cx, cy = centro
    for cab in cabecas:
        folga = 12.0
        if (cx + hw < cab[0] - folga or cx - hw > cab[2] + folga
                or cy + hh < cab[1] - folga or cy - hh > cab[3] + folga):
            continue
        # primeiro para CIMA (placa acima da cabeca e' a composicao natural),
        # aceitando encostar um pouco no cabelo; so' se nao houver teto, para
        # o lado com mais espaco -- e so' se o lado couber inteiro
        acima = cab[1] - folga - hh
        if acima >= y0 + hh - im.height * 0.2:
            cy = min(cy, max(acima, y0 + hh))
            continue
        esq = (cab[0] - folga - hw) - x0            # espaco para caber a esquerda da cabeca
        dir_ = x1 - (cab[2] + folga + hw)           # e a direita
        if max(esq, dir_) >= 0:
            cx = (cab[0] - folga - hw) if (esq >= dir_) else (cab[2] + folga + hw)
        else:
            cy = max(y0 + hh, acima)
    return _dentro((cx, cy), im, caixa)


PLACA_COBRE_MAX = 0.02      # fracao da placa que pode cair sobre um corpo
PLACA_ENCOLHE_MIN = 0.52    # a placa encolhe ate' isto antes de aceitar cobrir


def _fora_dos_corpos(placas, caixa, atores, i=0):
    """A PLACA NAO COBRE CORPO NENHUM (25/09, dono: *"muitos objetos com
    sobreposicao errada, metade aparece outra nao"*). `_longe_das_caras` so'
    olhava a CABECA: o selo "TUDO CERTO" caia no peito do Pal (33% da placa
    sobre ele), o "?" gigante do close tapava o tronco inteiro, o carimbo
    ficava atras do braco erguido. Aqui a mascara e' a silhueta DESENHADA de
    todos os atores (a pose final, que e' a que fica na tela) e a placa
    procura, na janela do plano, o lugar de menor cobertura -- e, empatado,
    o mais perto de onde o roteiro a pediu. Se nenhum lugar fica abaixo de
    `PLACA_COBRE_MAX`, a placa ENCOLHE (ate' `PLACA_ENCOLHE_MIN`) e procura
    de novo. Cada placa posta entra na mascara: duas placas nao se cobrem."""
    if not placas:
        return placas, 0.0
    red = 4
    mask = np.zeros((H // red, W // red), bool)
    for a in atores:
        if a.layer_desenhada is not None:
            al = np.asarray(a.layer_desenhada.resize((W // red, H // red), Image.NEAREST))[..., 3] > 48
            mask |= al
    x0, y0, x1, y1 = caixa
    saida = []
    pior = 0.0
    for z, im, centro, e in placas:
        esc = 1.0
        melhor = None
        while True:
            cand = im if esc == 1.0 else im.resize((max(1, int(im.width * esc)), max(1, int(im.height * esc))),
                                                   Image.LANCZOS)
            pw, ph = cand.width / red, cand.height / red
            pa = np.asarray(cand.resize((max(1, int(pw)), max(1, int(ph))), Image.NEAREST))[..., 3] > 48
            area = max(1, int(pa.sum()))
            hw, hh = cand.width / 2.0, cand.height / 2.0
            xs = np.linspace(x0 + hw, max(x0 + hw, x1 - hw), 9)
            ys = np.linspace(y0 + hh, max(y0 + hh, y1 - hh), 11)
            pedidos = [_dentro(centro, cand, caixa)] + [(float(cx), float(cy)) for cy in ys for cx in xs]
            diag = math.hypot(W, H)
            for cx, cy in pedidos:
                gx, gy = int((cx - hw) / red), int((cy - hh) / red)
                ph_, pw_ = pa.shape
                sx0, sy0 = max(0, gx), max(0, gy)
                sx1, sy1 = min(mask.shape[1], gx + pw_), min(mask.shape[0], gy + ph_)
                cob = 0
                if sx1 > sx0 and sy1 > sy0:
                    cob = int((pa[sy0 - gy:sy1 - gy, sx0 - gx:sx1 - gx] & mask[sy0:sy1, sx0:sx1]).sum())
                frac = cob / area
                custo = (max(0.0, frac - PLACA_COBRE_MAX) * 10.0 + frac * 0.5
                         + math.hypot(cx - centro[0], cy - centro[1]) / diag * 0.2)
                if melhor is None or custo < melhor[0]:
                    melhor = (custo, frac, cand, (cx, cy), esc)
            if melhor[1] <= PLACA_COBRE_MAX or esc * 0.86 < PLACA_ENCOLHE_MIN:
                break
            # o melhor de TODAS as escalas continua valendo: a menor so'
            # ganha se de fato cobrir menos
            esc *= 0.86
        _, frac, cand, pos, esc_f = melhor
        if esc_f < 1.0 or frac > PLACA_COBRE_MAX or math.hypot(pos[0] - centro[0], pos[1] - centro[1]) > 40:
            print(f"[cartao {i:02d}] placa fora dos corpos: ({centro[0]:.0f},{centro[1]:.0f}) -> "
                  f"({pos[0]:.0f},{pos[1]:.0f}), escala {esc_f:.2f}, cobre {frac:.0%}")
        # a placa posta vira obstaculo para a proxima
        gx, gy = int((pos[0] - cand.width / 2.0) / red), int((pos[1] - cand.height / 2.0) / red)
        pa = np.asarray(cand.resize((max(1, cand.width // red), max(1, cand.height // red)), Image.NEAREST))[..., 3] > 48
        sx0, sy0 = max(0, gx), max(0, gy)
        sx1, sy1 = min(mask.shape[1], gx + pa.shape[1]), min(mask.shape[0], gy + pa.shape[0])
        if sx1 > sx0 and sy1 > sy0:
            mask[sy0:sy1, sx0:sx1] |= pa[sy0 - gy:sy1 - gy, sx0 - gx:sx1 - gx]
        saida.append((z, cand, pos, e))
        pior = max(pior, frac)
    return saida, pior


def _sem_se_cobrir(placas, caixa):
    """Duas placas no mesmo cartao nao se cobrem: afasta na horizontal se
    cabe, senao uma sobe e a outra desce."""
    x0, y0, x1, y1 = caixa
    out = list(placas)
    for i in range(len(out)):
        for j in range(i + 1, len(out)):
            zi, imi, ci, ei = out[i]
            zj, imj, cj, ej = out[j]
            wi, hi = imi.width / 2.0, imi.height / 2.0
            wj, hj = imj.width / 2.0, imj.height / 2.0
            if abs(ci[0] - cj[0]) >= wi + wj + 16 or abs(ci[1] - cj[1]) >= hi + hj + 16:
                continue
            total = imi.width + imj.width + 24
            if total <= (x1 - x0):
                esq, dir_ = (i, j) if ci[0] <= cj[0] else (j, i)
                meio = (ci[0] + cj[0]) / 2.0
                meio = min(max(meio, x0 + total / 2.0), x1 - total / 2.0)
                we = out[esq][1].width
                out[esq] = (out[esq][0], out[esq][1], (meio - total / 2.0 + we / 2.0, out[esq][2][1]), out[esq][3])
                out[dir_] = (out[dir_][0], out[dir_][1], (meio + total / 2.0 - out[dir_][1].width / 2.0, out[dir_][2][1]), out[dir_][3])
            else:
                cima, baixo = (i, j) if ci[1] <= cj[1] else (j, i)
                hc, hb = out[cima][1].height, out[baixo][1].height
                yc = max(y0 + hc / 2.0, min(out[cima][2][1], y1 - hb - 16 - hc / 2.0))
                out[cima] = (out[cima][0], out[cima][1], (out[cima][2][0], yc), out[cima][3])
                out[baixo] = (out[baixo][0], out[baixo][1], (out[baixo][2][0], yc + hc / 2.0 + 16 + hb / 2.0), out[baixo][3])
    return out


def _dentro_canto(canto, im, caixa):
    c = _dentro((canto[0] + im.width / 2.0, canto[1] + im.height / 2.0), im, caixa)
    return (int(round(c[0] - im.width / 2.0)), int(round(c[1] - im.height / 2.0)))


def _janela(atores, falante, plano, zoom, i, extras=()):
    """(zoom, foco) do plano. Com UM ator: centra nele (close: na cara), sem
    cortar o alto da cabeca (lei 71). Com DOIS: ninguem aparece pela metade
    -- a janela centra no falante e, se o outro entraria cortado, desliza
    ate' deixa-lo fora inteiro; se nao da', abre ate' os dois caberem
    (o "meio ator fantasma" das folhas de 15/09 nasce aqui). `extras` sao
    caixas (placas, letreiro do prop) que tambem tem de caber inteiras: o
    plano abre ate' elas caberem."""
    if zoom <= 1.0 or not atores:
        return 1.0, None
    foco_ator = falante or atores[0]
    if not foco_ator.S:
        return 1.0, None
    S = foco_ator.S

    def _cy(z):
        jh = H / (z * (1.0 + PUSH_IN))
        cy = S["olhos"][1] + S["altura_cranio"] * 0.6 if plano == "close" else S["peito"][1] - S["altura_cranio"] * 0.3
        topo = S.get("topo_cabeca", (0, S["olhos"][1] - S["altura_cranio"]))[1]
        # nem o alto da cabeca nem o que a mao ergue (o documento de "justa
        # causa" saia pelo alto do plano medio) -- a janela sobe ate' caber
        bb = foco_ator.layer_desenhada.getbbox() if foco_ator.layer_desenhada is not None else None
        if bb and foco_ator.objeto_mao is not None:
            topo = min(topo, bb[1])
        for e in extras:
            topo = min(topo, e[1])
        # nunca corta o alto -- e deixa a faixa do cartaz de titulo livre
        # (no close do cartao 1 o titulo caia em cima da testa da Maya)
        cy = max(cy, topo - jh * 0.14 + jh / 2.0)
        return cy

    def _sil(a):
        bb = a.layer_desenhada.getbbox() if a.layer_desenhada is not None else None
        return (bb[0], bb[2]) if bb else (a.x - 1, a.x + 1)

    fx0, fx1 = _sil(foco_ator)
    # as caixas extras entram na caixa do falante: e' o que tem de ficar inteiro
    for e in extras:
        fx0, fx1 = min(fx0, e[0]), max(fx1, e[2])
    jw = W / (zoom * (1.0 + PUSH_IN))
    if fx1 - fx0 > jw * 0.94:
        zoom = max(1.0, (W * 0.94) / max(fx1 - fx0, 1.0) / (1.0 + PUSH_IN))
        jw = W / (zoom * (1.0 + PUSH_IN))
        print(f"[cartao {i:02d}] plano {plano}: abrindo para {zoom:.2f} para caber placa/objeto")
        if zoom <= 1.02:
            return 1.0, None
    outros = [a for a in atores if a is not foco_ator]
    cx = foco_ator.x
    if outros:
        ox0, ox1 = _sil(outros[0])
        x0 = max(0.0, min(W - jw, cx - jw / 2.0))
        corta = ox0 < x0 + jw and ox1 > x0          # o outro entra na janela
        if corta:
            # desliza a janela para o lado oposto ao outro, mantendo o falante inteiro
            if outros[0].x > foco_ator.x:
                x0_novo = min(x0, ox0 - jw - 4.0)
                cabe = x0_novo >= 0.0 and fx0 >= x0_novo
            else:
                x0_novo = max(x0, ox1 + 4.0)
                cabe = x0_novo + jw <= W and fx1 <= x0_novo + jw
            if cabe:
                cx = x0_novo + jw / 2.0
                print(f"[cartao {i:02d}] plano {plano}: janela deslizada para deixar {outros[0].quem} fora")
            else:
                uniao = max(fx1, ox1) - min(fx0, ox0)
                zoom = max(1.0, min(zoom, (W * 0.94) / max(uniao, 1.0) / (1.0 + PUSH_IN)))
                cx = (min(fx0, ox0) + max(fx1, ox1)) / 2.0
                print(f"[cartao {i:02d}] plano {plano}: {outros[0].quem} sairia cortado; "
                      f"abrindo para {zoom:.2f} com os dois inteiros")
                if zoom <= 1.02:
                    return 1.0, None
    else:
        # a uniao ator + objeto na mao + o que esta' nas placas cabe? centra nela
        cx = (fx0 + fx1) / 2.0 if fx1 - fx0 <= jw * 0.96 else foco_ator.x
    return zoom, (cx, _cy(zoom))


def _placa_em(img, centro, t, entra_em=0.0):
    """A placa no instante t: some antes de `entra_em`, pula ao entrar."""
    dt = t - entra_em
    if dt < 0:
        return None
    if dt < POP_PLACA_S:
        u = dt / POP_PLACA_S
        esc = 1.0 + POP_PLACA_FORCA * math.sin(math.pi * u) * (1.0 - u * 0.5)
        im = img.resize((max(1, int(img.width * esc)), max(1, int(img.height * esc))), Image.BILINEAR)
    else:
        im = img
    return im, (int(centro[0] - im.width / 2.0), int(centro[1] - im.height / 2.0))


def _voo_em(voo, t):
    """(img, canto) do objeto em voo no instante t; None antes de partir."""
    z, img, origem, destino, inicio, dur, giro = voo
    if t < inicio:
        return None
    u = min(1.0, (t - inicio) / max(dur, 1e-3))
    ue = _ease(u)
    x = origem[0] + (destino[0] - origem[0]) * ue
    y = origem[1] + (destino[1] - origem[1]) * ue
    d = math.hypot(destino[0] - origem[0], destino[1] - origem[1])
    y -= VOO_ARCO * d * math.sin(math.pi * ue)          # o arco
    if u < 1.0 and giro:
        im = img.rotate(giro * (1.0 - ue) * 2.0, resample=Image.BILINEAR, expand=False)
    else:
        im = img
    return im, (int(round(x)), int(round(y)))


def quadro_do_cartao(pronto, t, nivel=0.0, pisca=False):
    """O quadro composto (RGBA) no instante `t` do cartao."""
    q = pronto.fundo.copy()
    vivas = []                                  # (z, img, canto)
    for z, a in pronto.vivos:
        n = nivel if a is pronto.falante else 0.0
        vivas.append((z, a.camada(t, n, pisca), (0, 0)))
    for voo in pronto.voos:
        r = _voo_em(voo, t)
        if r is not None:
            vivas.append((voo[0], r[0], r[1]))
    for z, img, centro, entra_em in pronto.placas:
        r = _placa_em(img, centro, t, entra_em)
        if r is not None:
            vivas.append((z, r[0], r[1]))
    for z, im, canto in sorted(pronto.estaticas + vivas, key=lambda c: c[0]):
        q.alpha_composite(im, canto)
    return q


def _push_que_cabe(pronto, push, i=0):
    """O EMPURRAO DO GANCHO NAO CORTA NINGUEM (25/09). Com dois em cena o
    plano e' aberto (`foco=None`) e os 16% de empurrao cortavam PELO CENTRO:
    na copia `serie_v101` o Pal saiu pela metade na borda esquerda do quadro
    de abertura e a cabeca dele subiu para baixo do cartaz de titulo. Aqui o
    empurrao mira no CENTRO DO GRUPO (atores + placas) e para no maior valor
    em que ninguem sai pelos lados e o alto das cabecas fica abaixo da faixa
    do titulo (14% da janela). Devolve (push, foco)."""
    caixas = []
    topo = None
    for a in pronto.atores or []:
        bb = a.layer_desenhada.getbbox() if a.layer_desenhada is not None else None
        if bb:
            caixas.append(bb)
            cab = _cabeca(a)
            t_ = cab[1] if cab else bb[1]
            topo = t_ if topo is None else min(topo, t_)
    for z, im, c, e in pronto.placas or []:
        caixas.append((c[0] - im.width / 2.0, c[1] - im.height / 2.0, c[0] + im.width / 2.0, c[1] + im.height / 2.0))
    if not caixas:
        return push, None
    ux0 = min(b[0] for b in caixas)
    ux1 = max(b[2] for b in caixas)
    z0 = pronto.zoom or 1.0
    cx = (ux0 + ux1) / 2.0
    cy0 = pronto.foco[1] if pronto.foco else H / 2.0
    p = push
    while p > 0.0:
        z = z0 * (1.0 + p)
        jw, jh = W / z, H / z
        x0 = max(0.0, min(W - jw, cx - jw / 2.0))
        cy = cy0
        if topo is not None:
            # a janela desce ate' a cabeca ficar abaixo do titulo
            cy = max(cy, (topo - 0.14 * jh) + jh / 2.0)
        y0 = max(0.0, min(H - jh, cy - jh / 2.0))
        cabe_lados = ux0 >= x0 + 8 and ux1 <= x0 + jw - 8
        cabe_topo = topo is None or topo >= y0 + 0.14 * jh
        if cabe_lados and cabe_topo:
            if p < push:
                print(f"[cartao {i:02d}] gancho: empurrao {push:.2f} -> {p:.2f} para ninguem sair do quadro")
            return p, (x0 + jw / 2.0, y0 + jh / 2.0)
        p = round(p - 0.02, 3)
    print(f"[cartao {i:02d}] gancho: sem empurrao que caiba; so' o pop")
    return 0.0, pronto.foco


def _enquadrar(q, zoom, foco, u=0.0, push=None):
    """Recorte do plano; `u` (0..1 no cartao) avanca a camera devagar.
    `push` troca o empurrao padrao: o do gancho e' mais forte e e' SNAP --
    acontece no primeiro quarto do cartao, desacelerando, e segura (ver
    `palito_cutout.curva_push`: o empurrao lento espalhado nao vencia os
    cortes do resto do video)."""
    if push is None:
        zoom = zoom * (1.0 + PUSH_IN * _ease(u))
    else:
        s = min(1.0, max(0.0, u) / 0.25)
        # snap + tremor do impacto (ver `palito_cutout._enquadramento`): o
        # seno comeca em zero, entao o quadro 0 -- onde o loop fecha -- nao muda
        zoom = zoom * (1.0 + push * (1.0 - (1.0 - s) ** 3)
                       + 0.02 * math.sin(s * math.pi * 4.0) * (1.0 - s))
    if zoom <= 1.001:
        return q
    jw, jh = W / zoom, H / zoom
    cx, cy = foco if foco else (W / 2.0, H / 2.0)
    x0 = max(0.0, min(W - jw, cx - jw / 2.0))
    y0 = max(0.0, min(H - jh, cy - jh / 2.0))
    return q.crop((int(x0), int(y0), int(x0 + jw), int(y0 + jh))).resize((W, H), Image.BILINEAR)


def _pop(q, t_s, forca=None):
    if t_s >= POP_S:
        return q
    u = t_s / POP_S
    esc = 1.0 - (POP_FORCA if forca is None else forca) * (1.0 - u) ** 2
    nw, nh = int(W * esc), int(H * esc)
    p = q.resize((nw, nh), Image.BILINEAR)
    fundo = Image.new(q.mode, (W, H), q.getpixel((2, 2)))
    fundo.paste(p, ((W - nw) // 2, (H - nh) // 2))
    return fundo


# ---------------------------------------------------------------------
# TROCA DE TELAS (16/09, ordem do dono: "pouca troca de telas"). O video da
# chave tinha 18 cartoes em 62 s -- 3,4 s por cartao, e quatro seguidos com
# os mesmos dois bonecos no mesmo lugar. O Madrazzo corta a cada ~1,9 s e
# ALTERNA: gente, objeto, placa, close. Aqui todo cartao com duas oracoes
# (ou mais de 9 palavras) e' DESDOBRADO em dois, e o segundo e' uma variacao
# do primeiro, nesta ordem: as placas que entrariam atrasadas viram um cartao
# so' delas, grande; o objeto que esta' na mao vira um cartao so' dele; senao
# o falante ganha um close. O spec nao muda; e' o motor que corta.
# ---------------------------------------------------------------------
import re as _re

MAX_PALAVRAS_CARTAO = 9


def _partir_frase(texto):
    """[parte1, parte2] ou [texto]. Corta no fim de oracao; sem oracao, no
    virgula mais perto do meio; sem virgula, no meio -- so' se cada lado
    ficar com >= 2 palavras."""
    t = " ".join(str(texto or "").split())
    if not t:
        return [t]
    m = list(_re.finditer(r"[.!?:;…]\s+", t))
    if m:
        # o primeiro corte que deixa >= 2 palavras dos dois lados
        for k in m:
            a, b = t[:k.end()].strip(), t[k.end():].strip()
            if len(a.split()) >= 2 and len(b.split()) >= 2:
                return [a, b]
    palavras = t.split()
    if len(palavras) <= MAX_PALAVRAS_CARTAO:
        return [t]
    meio = len(palavras) // 2
    virgulas = [j for j, p in enumerate(palavras) if p.endswith(",")]
    if virgulas:
        j = min(virgulas, key=lambda v: abs(v - meio))
        if 2 <= j + 1 <= len(palavras) - 2:
            return [" ".join(palavras[:j + 1]), " ".join(palavras[j + 1:])]
    return [" ".join(palavras[:meio]), " ".join(palavras[meio:])]


def _variacao(c, texto_b):
    """O segundo cartao do desdobramento: outra tela para a mesma frase."""
    base = {k: v for k, v in c.items() if k not in ("texto", "sfx", "placas", "atores", "objetos", "props", "plano")}
    base["texto"] = texto_b
    placas = list(c.get("placas") or [])
    atrasadas = [p for p in placas if float(p.get("entra_em", 0.0)) > 0]
    atores = list(c.get("atores") or [])
    com_objeto = next((a for a in atores if a.get("objeto")), None)
    if atrasadas:
        # A: fica com as placas imediatas; B: so' as atrasadas, grandes, no centro
        a = dict(c, texto=None, placas=[p for p in placas if p not in atrasadas])
        n = len(atrasadas)
        bp = []
        for j, p in enumerate(atrasadas):
            q = dict(p, entra_em=0.0, escala=float(p.get("escala", 1.0)) * (1.6 if n == 1 else 1.3 if n == 2 else 1.1))
            if n == 1:
                q["x"], q["y"] = 0.5, 0.42
            elif n == 2:
                q["x"], q["y"] = 0.28 + 0.44 * j, 0.40
            else:
                # tres ou mais: em coluna (lado a lado nao cabe -- as tres
                # etiquetas "300 X / 60 X / 48 X" se cobriam)
                q["x"], q["y"] = 0.5, 0.22 + 0.18 * j
            bp.append(q)
        b = dict(base, placas=bp, tipo_var="placa")
        return a, b
    if com_objeto is not None:
        ob = com_objeto["objeto"]
        oc = dict(ob) if isinstance(ob, dict) else {"nome": ob}
        oc.pop("escala", None)
        oc["x"] = 0.5
        b = dict(base, objetos=[oc], placas=placas, tipo_var="objeto")
        return dict(c, texto=None), b
    if atores:
        # close em UM: com dois em cena o close abre ate' os dois caberem (e
        # vira o mesmo cartao); fica so' quem fala, ou o primeiro
        quem = c.get("ator")
        um = next((a for a in atores if a.get("quem") == quem), atores[0])
        um = dict(um, x=0.5)
        um.pop("alvos", None)
        um.pop("atras_de", None)
        plano = c.get("plano", "aberto")
        b = dict(base, atores=[um], placas=placas,
                 plano="close" if plano != "close" else "medio", tipo_var="close")
        return dict(c, texto=None), b
    return dict(c, texto=None), dict(base, placas=placas, objetos=c.get("objetos"), tipo_var="igual")


PECA_REPETE_MAX = 2         # um tipo de placa aparece no maximo isto por video
_SALTO_ALTERNATIVAS = {"calendario": ("ampulheta", "post_it"), "relogio": ("ampulheta",)}
_TEXTO_DO_SIMBOLO = {"interrogacao": "?", "exclamacao": "!", "check": "OK", "x": "NAO"}


def _variar_pecas(cartoes, falar=print):
    """POUCA VARIACAO DE PECAS (25/09, dono). A copia `serie_v101` usou 12
    pecas em 43 cartoes e o CALENDARIO 7 vezes (todo salto de tempo e todo
    prazo), o "?" duas vezes seguidas. O roteiro escolhe a placa frase a
    frase e nao ve as outras; aqui o video inteiro e' visto de uma vez: um
    tipo que ja' saiu `PECA_REPETE_MAX` vezes, ou que repete o cartao
    anterior, troca pela alternativa menos usada que diz a mesma coisa
    (`placas.ALTERNATIVAS`: prazo -> ampulheta/post-it, valor -> recibo,
    veredito -> documento/envelope/alerta, subir -> grafico). Muda o spec no
    lugar e devolve quantas trocas fez."""
    uso = {}
    ultimo = None
    trocas = 0

    def _escolher(tipo, opcoes):
        livres = [o for o in opcoes if o in PLACAS.GERADORES and o != ultimo]
        if not livres:
            return tipo
        return min(livres, key=lambda o: (uso.get(o, 0), opcoes.index(o)))

    for i, c in enumerate(cartoes):
        tipos_aqui = []
        for pc in c.get("placas") or []:
            if not isinstance(pc, dict):
                continue
            tipo = str(pc.get("tipo") or "cartaz")
            if uso.get(tipo, 0) >= PECA_REPETE_MAX or tipo == ultimo:
                novo = _escolher(tipo, PLACAS.ALTERNATIVAS.get(tipo, ()))
                if novo != tipo:
                    if not str(pc.get("texto") or "").strip():
                        pc["texto"] = _TEXTO_DO_SIMBOLO.get(tipo, "")
                    if str(pc.get("texto") or "").strip() or novo in ("ampulheta", "grafico", "alerta"):
                        falar(f"[pecas] cartao {i:02d}: {tipo} ja' saiu {uso.get(tipo, 0)}x -> {novo}")
                        pc["tipo"] = novo
                        tipo = novo
                        trocas += 1
            uso[tipo] = uso.get(tipo, 0) + 1
            tipos_aqui.append(tipo)
        if c.get("salto") and not (c.get("atores") or []) and not c.get("placas"):
            tipo = str(c.get("salto_tipo") or ler_salto(c["salto"])["tipo"])
            if uso.get(tipo, 0) >= PECA_REPETE_MAX or tipo == ultimo:
                novo = _escolher(tipo, _SALTO_ALTERNATIVAS.get(tipo, ()))
                if novo != tipo:
                    falar(f"[pecas] cartao {i:02d}: salto em {tipo} ja' saiu {uso.get(tipo, 0)}x -> {novo}")
                    c["salto_tipo"] = novo
                    tipo = novo
                    trocas += 1
            uso[tipo] = uso.get(tipo, 0) + 1
            tipos_aqui.append(tipo)
        ultimo = tipos_aqui[-1] if tipos_aqui else None
    return trocas


def desdobrar(cartoes, spec):
    """A lista de cartoes com os longos partidos em dois -- e os que continuam
    longos partidos de novo (22/09).

    UMA PASSADA NAO BASTAVA. `_partir_frase` corta UMA vez: uma frase de 24
    palavras virava dois cartoes de 12, e 12 palavras a 3 p/s sao 4 s de tela
    parada -- exatamente o `[cadencia] cartao acima do teto de 4.0s` que
    apareceu em 1 a 3 cartoes por video na serie (o pior com 6,5 s). O estilo
    existe para trocar de tela a cada 1,7-3,0 s; cartao de 6 s e' o defeito que
    o dono chamou de *"pouca troca de telas"*. Entao a partida repete enquanto
    sobrar cartao acima do teto de palavras, ate' tres voltas (a quarta ja
    seria picotar a frase em pedaco sem sentido).
    """
    if spec.get("desdobrar", True) is False:
        return list(cartoes)
    saida = list(cartoes)
    for _ in range(3):
        nova = _uma_partida(saida)
        if len(nova) == len(saida):
            break
        saida = nova
    if len(saida) != len(cartoes):
        print(f"[cartao] desdobrados: {len(cartoes)} -> {len(saida)} cartoes "
              f"({sum(1 for c in saida if c.get('tipo_var'))} variacoes: "
              + ", ".join(f"{k}={sum(1 for c in saida if c.get('tipo_var') == k)}"
                          for k in ("placa", "objeto", "close", "igual")) + ")")
    return _alternar_gente(saida)


def _uma_partida(cartoes):
    """Uma passada do desdobramento: cada cartao longo vira dois."""
    out = []
    for c in cartoes:
        if c.get("salto") or c.get("nao_desdobrar"):
            out.append(c)
            continue
        partes = _partir_frase(c.get("texto") or c.get("fala") or "")
        if len(partes) < 2:
            out.append(c)
            continue
        a, b = _variacao(c, partes[1])
        a["texto"] = partes[0]
        a.pop("fala", None)
        # METADE SEM NADA NAO E' CARTAO (22/09). Quando a unica coisa do
        # cartao e' uma placa que entra depois (`entra_em > 0`), a metade A
        # fica sem ator, sem objeto e sem placa -- um cenario vazio com
        # legenda. Foi o primeiro quadro do video `serie_v001`: um escritorio
        # sem ninguem, que e' justamente o quadro que decide a retencao.
        # Nesses casos nao se parte: o cartao inteiro vale mais que duas
        # metades, uma delas vazia.
        if not (a.get("atores") or a.get("objetos") or a.get("placas")
                or a.get("props")):
            out.append(c)
            continue
        out += [a, b]
    return out


def _gente_na_tela(cartoes, trechos, regra):
    """Ninguem fica mais de `sem_gente_max_s` SEGUNDOS sem ver um personagem,
    e o primeiro cartao nunca e' sem gente (22/09).

    POR QUE ELA NAO E' A `_alternar_gente`
        Aquela conta CARTOES ("nunca dois seguidos sem gente"), e cartao nao
        e' unidade de tempo: na copia `serie_v011` um unico cartao sem gente
        durou 9,4 s -- dentro da regra e insuportavel na tela. A ordem do dono
        e' em tempo: *"nao deixar apenas objetos por tanto tempo na tela sem
        aparecer um personagem"*.

        Por isso ela roda DEPOIS da timeline da voz, que e' quando a duracao
        de cada cartao existe de verdade, e antes do desenho.

    O QUE ELA NAO FAZ
        Nao tira o objeto nem a placa: o personagem entra EM CLOSE ao lado do
        que ja estava ali, e o objeto solto vai para a mao dele (a mesma
        conversao da `_alternar_gente`). O cartao sem gente continua existindo
        -- ele e' a troca de tela do canal de referencia --, so' deixou de
        poder virar um trecho.
    """
    teto = float((regra or {}).get("sem_gente_max_s") or 0.0)
    if teto <= 0 or not cartoes:
        return cartoes
    ultimo_ator = None
    for c in cartoes:
        if c.get("atores"):
            quem = c.get("ator")
            ultimo_ator = next((a for a in c["atores"] if a.get("quem") == quem),
                               c["atores"][0])
            break
    if ultimo_ator is None:
        return cartoes
    acumulado = 0.0
    postos = []
    for i, c in enumerate(cartoes):
        dur = float(trechos[i]["dur"]) if i < len(trechos) else 0.0
        if c.get("atores"):
            quem = c.get("ator")
            ultimo_ator = next((a for a in c["atores"] if a.get("quem") == quem),
                               c["atores"][0])
            acumulado = 0.0
            continue
        if c.get("salto"):
            acumulado = 0.0
            continue
        # o PRIMEIRO cartao nunca e' sem gente: ele e' o quadro que decide a
        # retencao, e desde 22/09 tambem e' o quadro em que o loop fecha
        if i == 0 or acumulado + dur > teto:
            um = dict(ultimo_ator, x=0.5)
            um.pop("alvos", None)
            um.pop("atras_de", None)
            soltos = [o for o in (c.get("objetos") or [])
                      if not (isinstance(o, dict) and o.get("tipo"))]
            if soltos:
                o0 = soltos[0]
                um["objeto"] = o0["nome"] if isinstance(o0, dict) else o0
                um.pop("mao", None)
                c["objetos"] = [o for o in (c.get("objetos") or []) if o is not o0]
            c["atores"] = [um]
            c["plano"] = "close"
            c["tipo_var"] = "close"
            postos.append(i)
            acumulado = 0.0
            continue
        acumulado += dur
    if postos:
        print(f"[tela] {len(postos)} cartao(oes) sem gente passaram de {teto:.1f}s "
              f"(ou abriam o video): {ultimo_ator['quem']} entrou em "
              + ", ".join(f"#{i}" for i in postos[:8]))
    return cartoes


def _alternar_gente(cartoes):
    """Nunca dois cartoes SEM GENTE seguidos (19/09).

    O cartao PT de 19/09 saiu com tres cartoes seguidos de um boleto no chao
    de um banheiro vazio ("DE BARRAS", "ESPERA,", "TA PAGO."). O Madrazzo tem
    ~40% de cartoes sem gente, mas ALTERNADOS com o boneco: o objeto e' a
    consequencia da frase anterior, nao uma sequencia de naturezas-mortas.
    Quando dois seguidos vem sem ator (e nao sao salto), o segundo ganha quem
    falou por ultimo, em close, e guarda os objetos e placas que ja tinha.
    """
    # QUEM ENTRA ANTES DE QUALQUER UM TER ENTRADO (22/09). `ultimo_ator` comeca
    # vazio, e enquanto ele esta vazio a guarda nao tem quem por na tela --
    # entao uma abertura em que as tres primeiras frases falam de COISAS
    # continua sendo tres cenarios vazios seguidos. Foi o comeco do `serie_v009`
    # (cartoes 0, 1 e 2 "sem gente"), e o primeiro quadro e' justamente o que
    # decide a retencao. O ator de partida e' o do primeiro cartao que tem um:
    # ele e' quem a historia vai mostrar de qualquer jeito.
    ultimo_ator = None
    for c in cartoes:
        if c.get("atores"):
            quem = c.get("ator")
            ultimo_ator = next((a for a in c["atores"] if a.get("quem") == quem),
                               c["atores"][0])
            break
    anterior_sem_gente = False
    for c in cartoes:
        atores = c.get("atores") or []
        if atores:
            quem = c.get("ator")
            ultimo_ator = next((a for a in atores if a.get("quem") == quem), atores[0])
            anterior_sem_gente = False
            continue
        if c.get("salto"):
            anterior_sem_gente = False
            continue
        if anterior_sem_gente and ultimo_ator is not None:
            um = dict(ultimo_ator, x=0.5)
            um.pop("alvos", None)
            um.pop("atras_de", None)
            # o objeto solto do cartao vai para a mao dele: e' o mesmo objeto,
            # agora segurado -- e nao um boneco ao lado de uma coisa no chao
            soltos = [o for o in (c.get("objetos") or []) if not (isinstance(o, dict) and o.get("tipo"))]
            if soltos:
                o0 = soltos[0]
                um["objeto"] = o0["nome"] if isinstance(o0, dict) else o0
                um.pop("mao", None)
                c["objetos"] = [o for o in (c.get("objetos") or []) if o is not o0]
            c["atores"] = [um]
            c["plano"] = "close"
            c["tipo_var"] = "close"
            anterior_sem_gente = False
            continue
        anterior_sem_gente = True
    return cartoes


def render(pasta_partes, spec, saida, tmpdir=None, amostra=0):
    from palito_v5 import sintetizar, envelope, juntar_com_respiro
    t0 = time.time()
    tmp = tmpdir or tempfile.mkdtemp()
    fd = os.path.join(tmp, "frames")
    os.makedirs(fd, exist_ok=True)
    ctx = Contexto(spec, pasta_partes)
    # O GANCHO ANTES DE TUDO (18/09, ordem do dono: *"e' obrigatorio pelo
    # menos um desses tres -- barulho alto, fala chamativa, cena de acao"*).
    # `abrir_no_auge` roda antes do desdobramento porque ele ACRESCENTA um
    # cartao; `garantir` roda depois, para medir o cartao que o espectador
    # vai realmente ver -- uma frase longa vira dois cartoes, e o gancho e' a
    # primeira metade, nao a frase inteira. Ver `work/gancho.py`.
    import gancho as GANCHO
    GANCHO.abrir_no_auge(spec)
    cartoes = desdobrar(spec.get("cartoes") or [], spec)
    if not cartoes:
        raise ValueError("spec sem `cartoes`")
    spec["cartoes"] = cartoes
    GANCHO.garantir(spec)
    cartoes = spec["cartoes"]
    _variar_pecas(cartoes)
    # O LOOP DO CARTAO: O ULTIMO RECEBE A TELA DO PRIMEIRO (22/09)
    #
    # O cartao nunca teve loop -- `cartao.py` nao tinha a palavra em 94 KB, e
    # 1 em 3 videos do canal sai neste estilo (§73.3). Medido no `serie_v01`:
    # razao 24,5 e 15% de pixels iguais entre o ultimo quadro e o primeiro.
    #
    # ELE NAO PODE SER O DA DUPLA. La' a cena e' continua e o rig INTERPOLA de
    # volta a pose do quadro 0 nos ultimos 2,5 s; aqui sao telas com corte seco
    # entre elas, e nao ha o que interpolar. O que fecha um slideshow e' o que
    # ele ja faz: TROCAR DE TELA. A ultima frase e' dita sobre a tela de
    # abertura, e o video acaba no desenho em que comecou -- em historia
    # narrada isso nem e' truque, e' o fecho que volta ao comeco.
    #
    # E TEM DE SER AQUI, e nao no `para_cartao`. Entre um e outro passam tres
    # etapas que reescrevem justamente o primeiro e o ultimo cartao:
    # `abrir_no_auge` (acrescenta um cartao na frente), `desdobrar` (parte os
    # longos em dois -- o video acabaria na VARIACAO do ultimo) e `garantir`
    # (poe acao e troca o plano do cartao 0). Na primeira versao a copia
    # morava la' e o resultado foi razao 28: o quadro 0 era um escritorio
    # vazio e o ultimo tinha o soldado que `_alternar_gente` havia posto.
    _loop_cfg = spec.get("loop")
    _loop_on = bool(_loop_cfg.get("ativo")) if isinstance(_loop_cfg, dict) else bool(_loop_cfg)
    print(f"[cartao] {len(cartoes)} cartoes; ator a {ctx.alt_frac:.0%} de H, chao em y={ctx.chao_y:.0f}")

    # -- voz primeiro (lei 1) -------------------------------------------------------
    modo = spec.get("modo_tts", os.environ.get("MODO_TTS", "real"))

    def _vozes(rate=None, respiro_fator=1.0):
        trechos = []
        faixas, respiros, marcas_por, total = [], [], [], 0.0
        for i, c in enumerate(cartoes):
            texto = c.get("texto") or c.get("fala") or (c.get("salto") or "")
            if c.get("salto") and not c.get("texto") and c.get("mudo", False):
                texto = ""
            ator = c.get("ator")
            narracao = not ator or bool(c.get("narracao"))
            perfil = c.get("voz") or (ator if ator else "narrador")
            cfg = dict(spec.get("vozes", {}).get(perfil, {}))
            # o rate da copia vira o rate do PERFIL: a emocao (`prosodia`)
            # soma o desvio dela por cima, em vez de ser apagada por ele
            if rate:
                cfg["rate"] = rate
            cfg = EXPR.prosodia(c.get("expressao"), c.get("intensidade", 1.0), cfg)
            wav = os.path.join(tmp, f"c{i:02d}.wav")
            if texto.strip():
                marcas, dur = sintetizar(texto, cfg, wav, modo)
                # O SILENCIO DAS PONTAS SAI (16/09, serie): o Edge devolve cada
                # frase com 0,3-0,5 s de nada antes e depois; em 42 cartoes sao
                # ~20 s de video parado -- a serie estava em 96 s para 250
                # palavras, e o Madrazzo diz as mesmas 250 em 60. Apara ate' 60 ms
                # do som e desloca as marcas de palavra junto.
                marcas, dur = _aparar_silencio(wav, marcas, dur)
            else:
                marcas, dur = [], float(c.get("dur", 1.2))
                _silencio(wav, dur)
            respiro = float(c.get("respiro_s", RESPIRO_SALTO_S if c.get("salto") else RESPIRO_S))
            respiro *= respiro_fator
            tr = {"fala": texto, "ator": ator or "narrador", "narracao": narracao,
                  "expressao": c.get("expressao", "neutro"), "sfx": c.get("sfx") or [],
                  "acoes": [], "dur": dur + respiro, "_inicio_s": total, "_dur_voz": dur}
            trechos.append(tr)
            faixas.append(wav)
            respiros.append(respiro)
            marcas_por.append(marcas or [])
            total += tr["dur"]
        return trechos, faixas, respiros, marcas_por, total

    trechos, faixas, respiros, marcas_por, total = _vozes()
    # A DURACAO DA COPIA, EM MALHA FECHADA NA VOZ GRATUITA (22/09).
    #
    # `para_cartao.casar_duracao` casa a copia com o original ANTES de falar:
    # estima a fala (`wps_copia`) e, se passar de 105%, sobe o `speed` da
    # ElevenLabs. Na voz gratuita dos testes isso nao funciona duas vezes: o
    # Edge ignora `speed`, e o Edge em portugues e' mais lento que a estimativa
    # (calibrada na ElevenLabs em ingles). Medido na serie de 22/09: copias em
    # 117% e 124% da duracao original, com a estimativa dizendo "sem acelerar".
    # Ordem do dono: *"verifique que duracao... esta fiel ao video copiado"*.
    #
    # Aqui a duracao REAL ja existe, entao a conta e' exata: passou de 105% do
    # original, a voz e' refeita uma vez com o `rate` do Edge que fecha a
    # diferenca (teto +35%, acima disso a fala atropela) e o respiro encolhe
    # junto. So' no Edge: refazer na ElevenLabs pagaria duas vezes a mesma fala.
    alvo = float(spec.get("copia_dur_s") or 0)
    so_edge = all(str((v or {}).get("motor", "edge")).lower() == "edge"
                  for v in (spec.get("vozes") or {}).values() if isinstance(v, dict))
    if alvo > 0 and so_edge and total > 1.05 * alvo and not amostra:
        fator = total / alvo
        pct = int(round(min(35.0, (fator - 1.0) * 100.0 * 1.15)))
        print(f"[copia] voz gratuita deu {total:.1f}s para {alvo:.0f}s do original "
              f"({100 * fator:.0f}%): refazendo com rate +{pct}%")
        trechos, faixas, respiros, marcas_por, total = _vozes(
            rate=f"+{pct}%", respiro_fator=max(0.5, 1.0 / fator))
        print(f"[copia] agora {total:.1f}s ({100 * total / alvo:.0f}% do original)")
    spec["trechos"] = trechos          # para sfx/legenda, no formato de sempre
    print(f"[voz] timeline real: {total:.2f}s em {len(cartoes)} cartoes "
          f"({total / len(cartoes):.2f}s por cartao)")
    # A CADENCIA, MEDIDA CONTRA A REGRA DO ESTILO (18/09, §62)
    #
    # A troca de tela e' a razao de existir deste modo: o Madrazzo troca a
    # cada 1,7-1,9 s, e "pouca troca de telas" foi queixa do dono em 16/09
    # (§57). A regra vive no `config.json` (`formatos.cartao.cadencia_*`) e
    # chega aqui pelo spec (`regra_estilo`, que `para_cartao` grava) ou pelos
    # padroes do proprio modo. Isto AVISA e nao corrige: o conserto e' no
    # roteiro (mais falas) ou no desdobramento, e nenhum dos dois se faz aqui
    # sem mexer no que o roteirista pediu.
    _re_ = spec.get("regra_estilo") or {}
    _lo = float(_re_.get("cadencia_min_s", 1.8))
    _hi = float(_re_.get("cadencia_max_s", 3.2))
    _teto = float(_re_.get("cadencia_teto_s", 4.0))
    _med = total / max(1, len(cartoes))
    if not (_lo <= _med <= _hi):
        print(f"[cadencia] {_med:.2f}s por cartao, fora da faixa {_lo}-{_hi}s "
              f"do estilo: {'corte rapido demais para a legenda' if _med < _lo else 'pouca troca de tela'}")
    _longos = [(i, t["dur"]) for i, t in enumerate(trechos) if t["dur"] > _teto]
    if _longos:
        print(f"[cadencia] {len(_longos)} cartao(oes) acima do teto de {_teto}s: "
              + ", ".join(f"#{i} ({d:.1f}s)" for i, d in _longos[:6]))
    _gente_na_tela(cartoes, trechos, _re_)
    # O LOOP DO CARTAO: O ULTIMO RECEBE A TELA DO PRIMEIRO
    #
    # O cartao nunca teve loop -- `cartao.py` nao tinha a palavra em 94 KB, e
    # 1 em 3 videos do canal sai neste estilo (§73.3). Medido no `serie_v01`:
    # razao 24,5 e 15% de pixels iguais entre o ultimo quadro e o primeiro.
    #
    # ELE NAO PODE SER O DA DUPLA. La' a cena e' continua e o rig INTERPOLA de
    # volta a pose do quadro 0 nos ultimos 2,5 s; aqui sao telas com corte seco
    # entre elas, e nao ha o que interpolar. O que fecha um slideshow e' o que
    # ele ja faz: TROCAR DE TELA. A ultima frase e' dita sobre a tela de
    # abertura, e o video acaba no desenho em que comecou -- em historia
    # narrada isso nem e' truque, e' o fecho que volta ao comeco.
    #
    # E TEM DE SER AQUI, DEPOIS DE TUDO O QUE REESCREVE O CARTAO 0. Entre o
    # `para_cartao` e este ponto passam `abrir_no_auge` (acrescenta um cartao
    # na frente), `desdobrar` (parte os longos em dois -- o video acabaria na
    # VARIACAO do ultimo), `garantir` (poe acao e troca o plano do cartao 0) e
    # `_gente_na_tela` (poe gente no cartao 0 quando ele abria sem ninguem).
    # Em 22/09 a copia foi feita antes desta ultima e o `serie_v013` acabou
    # numa sala vazia: o cartao 0 ainda nao tinha o ator quando a tela dele foi
    # copiada.
    if _loop_on and len(cartoes) >= 4 and not amostra:
        VISUAL = ("fundo", "atores", "objetos", "placas", "plano", "zoom",
                  "foco", "lavar", "faixa", "props")
        pri, ult = cartoes[0], cartoes[-1]
        for k in VISUAL:
            ult.pop(k, None)
            if k in pri:
                ult[k] = copy.deepcopy(pri[k])
        # a placa que entra depois nao esta no quadro 0; no fim ela estaria
        ult["placas"] = [p for p in (ult.get("placas") or [])
                         if float(p.get("entra_em", 0.0)) <= 0.0]
        print("[loop] o ultimo cartao recebeu a tela do primeiro: "
              + ", ".join(k for k in VISUAL if k in ult))
    elif _loop_on:
        print(f"[loop] pedido, mas so' ha {len(cartoes)} cartao(oes): sem volta")
    voz = juntar_com_respiro(faixas, respiros, os.path.join(tmp, "voz.wav"), tmp)
    env = envelope(voz)

    from legendas import janelas_censuradas, Legenda, Titulo, titulo_da_esquete
    bipes = []
    for tr, m in zip(trechos, marcas_por):
        bipes += janelas_censuradas(tr["fala"], m, tr["_inicio_s"], tr["_dur_voz"])
    audio = voz
    if spec.get("sfx", True) is not False or spec.get("musica", True):
        eventos = SFX.eventos_do_spec(spec) if spec.get("sfx", True) is not False else []
        musica = spec.get("musica", True)
        if isinstance(musica, dict) and not musica.get("arquivo"):
            musica = dict(musica)
            musica.setdefault("segmentos", SFX.segmentos_do_spec(spec))
            musica.setdefault("semente", spec.get("fila_id", "cartao"))
            musica.setdefault("falas", [t.get("fala") for t in trechos])
        elif musica is True:
            musica = {"genero": spec.get("genero", "leve"), "segmentos": SFX.segmentos_do_spec(spec),
                      "semente": spec.get("fila_id", "cartao"), "falas": [t.get("fala") for t in trechos]}
        try:
            # A CAMA TAMBEM EMENDA NO LACO (22/09). `sfx._emendar_bed` existe
            # desde 13/09 e o cartao nunca o pediu: `mixar` era chamado sem
            # `loop_cauda_s`, entao a trilha do cartao terminava no decaimento
            # do ultimo compasso e recomecava no ataque do primeiro. Medido no
            # `serie_v009`: 0,013 no fim contra 0,026 nos respiros do proprio
            # video (0,47 do vale). O quadro emendava e o ouvido cortava, que
            # e' exatamente a queixa que criou a funcao.
            audio = SFX.mixar(voz, eventos, os.path.join(tmp, "mix.wav"), musica=musica,
                              dur_s=total, bipes=bipes,
                              loop_cauda_s=(LOOP_SOM_S if _loop_on else 0.0))
        except Exception as e:                                          # noqa: BLE001
            print(f"[sfx] mixagem falhou ({e}); seguindo so' com a voz")
            audio = voz

    # O LOOP DO CARTAO (22/09) -- ver `para_cartao.converter`, que ja deu ao
    # ultimo cartao a tela do primeiro. Aqui falta o alto do quadro: sem a
    # reprise do cartaz, o ultimo quadro tem o mesmo desenho do primeiro e
    # NAO tem o titulo, e a regua acusa a diferenca justamente na faixa de
    # cima. `laco=True` tambem tira o pop de entrada do quadro 0 -- com ele,
    # o primeiro quadro seria o unico sem cartaz.
    _loop = spec.get("loop")
    loop_on = bool(_loop.get("ativo")) if isinstance(_loop, dict) else bool(_loop)
    titulo = None
    if spec.get("titulo") is not False:
        txt = spec.get("titulo")
        if not isinstance(txt, str) or not txt.strip():
            txt = titulo_da_esquete([t.get("fala") for t in trechos])
        if txt:
            titulo = Titulo(W, H, txt, dur_total=(total if loop_on else 0.0),
                            laco=loop_on)
            print(f"[titulo] \"{txt}\" nos primeiros {titulo.ate:.1f}s"
                  + (f"; reprise do laco a partir de {titulo.volta:.1f}s"
                     if loop_on and titulo.volta else ""))
    leg = None
    if spec.get("legenda", True):
        leg = Legenda(W, H, tamanho=spec.get("legenda_px") or int(H * 0.052),
                      por_bloco=int(spec.get("legenda_palavras", 1)),
                      y_rel=float(spec.get("legenda_y", LEGENDA_Y)))
        for c, tr, m in zip(cartoes, trechos, marcas_por):
            # o salto de tempo ja' esta' escrito no calendario; a legenda
            # palavra a palavra dele saia "1" / "HORA" / "DEPOIS" (folha de 15/09)
            if c.get("salto") and not c.get("texto"):
                continue
            if tr["fala"].strip():
                leg.adicionar(tr["fala"], m, tr["_inicio_s"], tr["_dur_voz"])
        print(f"[legenda] {len(leg.blocos)} blocos")

    # -- os cartoes ------------------------------------------------------------------
    n = 0
    colhidos = []
    for i, c in enumerate(cartoes):
        tr = trechos[i]
        pronto = compor(ctx, c, i)
        nf = max(1, int(tr["dur"] * FPS))
        resumo = (f"{'narr' if tr['narracao'] else tr['ator']:>8} | "
                  f"{', '.join(a.quem + (':' + str(a.cfg.get('pose') or a.cfg.get('poses') or '-')) for a in pronto.atores) or '(sem gente)'} | "
                  f"{', '.join(pronto.props) or '-'} | {tr['dur']:.1f}s")
        print(f"[cartao {i:02d}] {resumo}")
        if amostra:
            f_meio = nf // 2
            nivel = env[n + f_meio] if n + f_meio < len(env) else 0.0
            q = quadro_do_cartao(pronto, f_meio / float(FPS), nivel, False)
            q = _enquadrar(q, pronto.zoom, pronto.foco, f_meio / float(nf)).convert("RGB")
            if titulo is not None:
                titulo.desenhar(q, (n + f_meio) / float(FPS))
            if leg is not None:
                leg.desenhar(q, (n + f_meio) / float(FPS))
            colhidos.append(((n + f_meio) / float(FPS), q))
            n += nf
            continue
        # OS ULTIMOS QUADROS DO VIDEO SAO O QUADRO 0 (22/09) -- a segunda
        # metade do loop do cartao.
        #
        # Dar ao ultimo cartao a tela do primeiro (ver `[loop]` la' em cima)
        # aproximou, mas nao fechou: razao 16,6 e 18,8% de pixels iguais no
        # `serie_v003`. A causa nao e' a composicao, e' o TEMPO dentro do
        # cartao -- `_enquadrar` recebe `f/nf` (o plano deriva do comeco ao
        # fim do cartao) e `_pop` recebe `f/FPS` (o solavanco de entrada).
        # O primeiro quadro do video esta em f=0 dos dois; o ultimo quadro de
        # qualquer cartao esta em f=nf-1. Duas telas iguais, dois enquadramentos
        # diferentes.
        #
        # O que fecha e' o que o proprio spec ja pedia e o cartao nunca
        # cumpriu: `loop.segurar_s` -- segurar o primeiro quadro no fim. Ele
        # nao ACRESCENTA tempo (isso desencontraria video e mixagem, e a copia
        # tem de durar o que o original dura): ele ocupa o fim do respiro do
        # ultimo cartao, onde ninguem mais fala. O quadro repetido e' o
        # arquivo do quadro 0, byte a byte -- entao o ultimo quadro do video
        # E' o primeiro, e nao uma reconstrucao dele.
        eh_ultimo = (i == len(cartoes) - 1)
        segurar = 0
        if _loop_on and eh_ultimo and n > 0:
            seg_s = float(_loop_cfg.get("segurar_s", 0.2)) if isinstance(_loop_cfg, dict) else 0.2
            # nunca mais que metade do cartao: o fecho ainda e' fala
            segurar = max(1, min(int(round(seg_s * FPS)), nf // 2))
        # o cartao que COMECA dentro do gancho ganha a camera do gancho
        no_gancho = (n / float(FPS)) < GANCHO_CAMERA_S and not eh_ultimo
        push_c = GANCHO_PUSH_IN if no_gancho else None
        pop_c = GANCHO_POP_FORCA if no_gancho else None
        if no_gancho:
            push_c, foco_g = _push_que_cabe(pronto, push_c, i)
            if foco_g is not None:
                pronto.foco = foco_g
        for f in range(nf):
            if segurar and f >= nf - segurar:
                shutil.copyfile(os.path.join(fd, "00000.png"),
                                os.path.join(fd, f"{n:05d}.png"))
                n += 1
                continue
            nivel = env[n] if n < len(env) else 0.0
            pisca = EXPR.piscando(n, FPS, semente=i % 5, expr_nome=tr.get("expressao", "neutro"))
            q = quadro_do_cartao(pronto, f / float(FPS), nivel if not tr["narracao"] else 0.0, pisca)
            q = _enquadrar(q, pronto.zoom, pronto.foco, f / float(nf), push=push_c).convert("RGB")
            # o quadro 0 do VIDEO fica sem pop: e' nele que o loop fecha, e o
            # ultimo quadro (a copia dele) tem de ser o mesmo desenho
            if spec.get("pop", True) and n > 0:
                q = _pop(q, f / float(FPS), forca=pop_c)
            if titulo is not None:
                titulo.desenhar(q, n / float(FPS))
            if leg is not None:
                leg.desenhar(q, n / float(FPS))
            q.save(os.path.join(fd, f"{n:05d}.png"), compress_level=1)
            n += 1
        if segurar:
            print(f"[loop] os ultimos {segurar} quadro(s) ({segurar / FPS:.2f}s) "
                  "sao o quadro 0 do video")
    print(f"[cartao] {n} frames ({n / FPS:.1f}s) montados em {time.time() - t0:.0f}s")
    if amostra:
        return _folha(colhidos, saida, larg=360), round(total, 2)

    # O LOUDNORM ESTAVA COMENDO O GANCHO, E O ALVO DELE NUNCA FOI ENTREGUE
    #
    # `I=-9:LRA=8` (o que estava aqui) foi medido em 18/09 sobre o mix de um
    # video deste modo, e o resultado e' o pior dos dois mundos:
    #
    #   mix cru                 razao gancho/normal 2,91   -20,8 LUFS
    #   I=-9  LRA=8  TP=-1,5    razao 1,15                 -13,9 LUFS  <- antes
    #   I=-13 LRA=13 TP=-1,0    razao 1,40                 -14,7 LUFS  <- agora
    #   I=-14 LRA=14 TP=-1,0    razao 1,57                 -15,3 LUFS
    #
    # Duas leituras, e as duas importam. Primeira: o alvo de -9 LUFS NAO
    # acontece -- o proprio filtro chega a -13,9, porque nao da' para subir
    # tanto sem passar do true peak. O numero -9 nunca foi entregue em video
    # nenhum deste canal; ele so' pagou o preco de pedir. Segunda: o que -9
    # com LRA=8 faz de verdade e' SUBIR O NIVEL NORMAL do video (0,27 ->
    # 0,71) sem mexer no pico -- e quando tudo fica alto, nada e' alto. O
    # barulho do gancho e' exatamente o que essa compressao apaga.
    #
    # -13/LRA=13 entrega o MESMO volume percebido (0,8 dB de diferenca,
    # dentro do que o YouTube normaliza para -14 de qualquer forma) e devolve
    # 22% de destaque ao gancho. O spec continua podendo mandar outro
    # (`loudnorm`), e o motor do palito -- que e' o da PRODUCAO -- nao foi
    # tocado: mexer no audio do que vai ao ar pede medida em video publicado,
    # nao em laboratorio.
    cmd = ["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
           "-i", os.path.join(fd, "%05d.png"), "-i", audio,
           "-af", spec.get("loudnorm", "loudnorm=I=-13:LRA=13:TP=-1.0"),
           "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-maxrate", "4M",
           "-bufsize", "8M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
           "-shortest", "-movflags", "+faststart", saida]
    subprocess.run(cmd, check=True)
    # Os quadros so servem ao ffmpeg: ~2.000 PNG (3-5 GB) por video, e a serie
    # local chegou a 208 GB em tmp/ (23/09). GUARDAR_QUADROS=1 os mantem.
    if os.environ.get("GUARDAR_QUADROS") != "1":
        shutil.rmtree(fd, ignore_errors=True)
    mb = os.path.getsize(saida) / (1024 * 1024)
    print(f"[video] {mb:.1f} MB, {n / float(FPS):.1f}s, em {time.time() - t0:.0f}s")
    return saida, round(n / float(FPS), 2)


def _aparar_silencio(wav, marcas, dur, limiar=0.012, margem_s=0.06):
    """Corta o silencio do comeco e do fim do wav (mono 16 bit) e desloca as
    marcas. Devolve (marcas, dur) novos; se nao houver o que cortar, os
    mesmos."""
    import wave
    try:
        with wave.open(wav, "rb") as w:
            sr, n, sw, ch = w.getframerate(), w.getnframes(), w.getsampwidth(), w.getnchannels()
            raw = w.readframes(n)
        if sw != 2 or ch != 1 or n < sr // 10:
            return marcas, dur
        a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        jan = max(1, sr // 200)                       # 5 ms
        env = np.abs(a[: (len(a) // jan) * jan].reshape(-1, jan)).max(axis=1)
        som = np.nonzero(env > limiar)[0]
        if not len(som):
            return marcas, dur
        i0 = max(0, int(som[0] * jan - margem_s * sr))
        i1 = min(len(a), int((som[-1] + 1) * jan + margem_s * sr))
        if i0 < sr * 0.05 and i1 > len(a) - sr * 0.05:
            return marcas, dur
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(raw[i0 * 2:i1 * 2])
        desloca = i0 / float(sr)
        nova_dur = (i1 - i0) / float(sr)
        novas = []
        for m in marcas or []:
            novas.append(dict(m, inicio_s=max(0.0, float(m["inicio_s"]) - desloca),
                              fim_s=min(nova_dur, max(0.0, float(m["fim_s"]) - desloca))))
        return novas, nova_dur
    except Exception as e:                                              # noqa: BLE001
        print(f"[voz] nao aparei {os.path.basename(wav)} ({e})")
        return marcas, dur


def _silencio(wav, dur):
    import wave
    sr = 24000
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"\x00\x00" * int(sr * dur))
