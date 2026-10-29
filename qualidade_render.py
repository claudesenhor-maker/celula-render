"""Perfil de codificação comum aos motores Pillow/SVG, respeitando teto de upload.

Não muda a reamostragem do cut-out: o bilinear de ampliação evita halos já
medidos no projeto. A melhora atua na compressão, sem desmanchar o traço.
"""
import math
import os


def conferir_quadros(spec, pasta, quantidade, fps, saida):
    """Prévias dos motores Pillow/SVG; visão opcional sem executar correções.

    Sem endpoint, registra somente métricas técnicas. A revisão de conteúdo
    depende de um backend multimodal configurado, como no motor web.
    """
    import base64
    import io
    import json
    from pathlib import Path
    import urllib.request
    from PIL import Image, ImageStat

    if quantidade < 1:
        raise ValueError('nenhum quadro para conferir')
    destino = Path(str(saida) + '.previas')
    destino.mkdir(parents=True, exist_ok=True)
    quadros, imagens = [], []
    for indice in sorted({round((quantidade - 1) * p) for p in (0, .2, .5, .8, .98)}):
        with Image.open(Path(pasta) / f'{indice:05d}.png') as original:
            imagem = original.convert('RGB')
            tamanho = list(imagem.size)
            imagem.thumbnail((360, 640), Image.Resampling.LANCZOS)
            estatistica = ImageStat.Stat(imagem.convert('L'))
            buffer = io.BytesIO()
            imagem.save(buffer, 'JPEG', quality=88)
        nome = f'legado-{indice:05d}.jpg'
        (destino / nome).write_bytes(buffer.getvalue())
        quadro = {'t': round(indice / fps, 4), 'dimensoes': tamanho,
                  'luma': estatistica.mean[0], 'variancia': estatistica.var[0],
                  'arquivo': destino.name + '/' + nome}
        quadros.append(quadro)
        imagens.append({**{k: v for k, v in quadro.items() if k != 'arquivo'},
                        'imagem': 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')})
    endpoint = os.environ.get('VIDEO_REVISOR_URL')
    rodada = {'rodada': 0, 'modo': 'visao-configurada' if endpoint else 'tecnico-local', 'quadros': quadros}
    relatorio = {'versao': 1, 'historico': [rodada]}
    caminho_relatorio = Path(str(saida) + '.direcao.json')

    def salvar():
        caminho_relatorio.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding='utf-8')

    salvar()
    if not endpoint:
        return relatorio
    # Só contexto visual/narrativo: não enviar configuração de voz nem credenciais.
    cenas = spec.get('cenas') or spec.get('trechos') or []
    contexto = {'estilo': spec.get('estilo') or spec.get('formato') or 'legado',
                'titulo': spec.get('titulo'), 'cenas': [
                    {k: c[k] for k in ('texto', 'acao', 'cenario', 'camera', 'gesto') if k in c}
                    for c in cenas if isinstance(c, dict)]}
    dados = {'versao': 1, 'spec': contexto, 'quadros': imagens,
             'capacidades': {'cameras': [], 'plano': []},
             'instrucao': 'Compare os quadros ordenados com a narração/ação. Avalie reconhecimento, contato, continuidade e legibilidade. '
             'Não invente fatos. Este motor legado não aplica correções: reprove problemas de conteúdo. '
             'Retorne JSON {aprovado:boolean,problemas:[string],correcoes:[]}.'}
    headers = {'Content-Type': 'application/json'}
    token = os.environ.get('VIDEO_REVISOR_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        pedido = urllib.request.Request(endpoint, data=json.dumps(dados).encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(pedido, timeout=60) as resposta:
            bruto = resposta.read(100001)
        if len(bruto) > 100000:
            raise ValueError('resposta do revisor excedeu limite')
        revisao = json.loads(bruto)
        rodada['revisao'] = revisao
        if (not isinstance(revisao, dict) or type(revisao.get('aprovado')) is not bool
                or not isinstance(revisao.get('problemas'), list) or not isinstance(revisao.get('correcoes'), list)):
            raise ValueError('resposta do revisor fora do contrato')
        if not revisao['aprovado'] or revisao['correcoes']:
            raise ValueError('revisão visual não aprovada para o motor legado')
    except Exception as erro:
        rodada['erro'] = str(erro)
        salvar()
        raise
    salvar()
    return relatorio


def codificacao(spec, duracao, teto_mb=45):
    perfil = spec.get('qualidade') or os.environ.get('VIDEO_QUALIDADE', 'detalhado')
    valor = spec.get('crf', 23 if perfil == 'rapido' else 20)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or not 0 <= valor <= 40:
        raise ValueError('crf deve ser número entre 0 e 40')
    if not math.isfinite(float(duracao)) or duracao <= 0:
        raise ValueError('duração inválida para orçamento de vídeo')
    # Reserva para áudio, contêiner e variação do encoder; fallback de upload permanece.
    taxa = max(.25, min(4 if perfil == 'rapido' else 12,
                        teto_mb * 1024 * 1024 * 8 * .90 / duracao / 1_000_000 - .192))
    return {'crf': str(round(valor)), 'maxrate': f'{taxa:.3f}M', 'bufsize': f'{taxa * 2:.3f}M'}
