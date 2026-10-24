"""T269: clima literal da silhueta; regras únicas para Python/render e n8n.

Não infere lugar pela mera menção (ilha pode ter montanhas), nem objeto por
texto de diálogo/notificação. O módulo T199/T259 permanece experimental.
"""
import json
import re
import unicodedata

VERSAO = 't269-v1'
REGRAS = [
    (r'\b(fog|mist|misty|foggy|nevoa|neblina|nevoeiro|niebla|neblina)\b', 'nevoa', ['nevoa']),
    (r'\b(rain|rained|raining|rains|chuva|chovia|choveu|lluvia|llovia|llovio)\b', 'chuva', ['chuva', 'raio']),
    (r'\b(snow|snowed|snowing|snowy|blizzard|neve|nevasca|nieve|nevada)\b', 'neve', ['neve']),
    (r'\b(lightning|thunderstorm|raio|trovao|relampago|rayo|trueno)\b', 'raio', ['raio', 'chuva']),
]
# Na dúvida, conserva a direção escolhida. Não é um juiz semântico nem visual.
ABSTER = (r'\b(no|not|never|without|sem|nao|sin|nunca|if|se|si|would|could|might|'
          r'puede|podria|talvez|poderia)\b|\?|fog of war|rain check|snow job')


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto.lower())
                   if unicodedata.category(c) != 'Mn')


def corrigir(estilo, cenas):
    """Corrige só objeto meteorológico inequívoco; registra diferenças por cena."""
    if estilo != 'silhueta' or not isinstance(cenas, list):
        return []
    ajustes = []
    for i, cena in enumerate(cenas):
        if not isinstance(cena, dict) or not isinstance(cena.get('texto'), str):
            continue
        texto = normalizar(cena['texto'])
        trechos = re.findall(r'[^.!?]+[.!?]?', texto)
        achadas = [(ideal, aceitos) for padrao, ideal, aceitos in REGRAS
                   if any(re.search(padrao, t) and not re.search(ABSTER, t) for t in trechos)]
        if len(achadas) != 1:
            continue
        ideal, aceitos = achadas[0]
        if cena.get('objeto') not in aceitos:
            ajustes.append(dict(indice=i, campo='objeto', antes=cena.get('objeto'), depois=ideal))
            cena['objeto'] = ideal
    return ajustes


def javascript():
    """Gera o mesmo algoritmo para o Code node, sem uma segunda lista de regras."""
    return ('// T269: gerado de videos_realistas/sentido_visual.py; ' + VERSAO + '\n'
            + 'const SENTIDO_REGRAS = ' + json.dumps(REGRAS, ensure_ascii=False) + ';\n'
            + 'const SENTIDO_ABSTER = new RegExp(' + json.dumps(ABSTER) + ');\n' + r'''
function corrigirSentidoVisual(estilo, cenas) {
  if (estilo !== 'silhueta' || !Array.isArray(cenas)) return [];
  const ajustes = [];
  cenas.forEach((c, indice) => {
    if (!c || typeof c !== 'object' || Array.isArray(c) || typeof c.texto !== 'string') return;
    const texto = c.texto.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    const trechos = texto.match(/[^.!?]+[.!?]?/g) || [];
    const achadas = SENTIDO_REGRAS.filter(([padrao]) => trechos.some(t =>
      new RegExp(padrao).test(t) && !SENTIDO_ABSTER.test(t)));
    if (achadas.length !== 1) return;
    const [, ideal, aceitos] = achadas[0];
    if (!aceitos.includes(c.objeto)) {
      ajustes.push({indice, campo:'objeto', antes:c.objeto == null ? null : c.objeto, depois:ideal});
      c.objeto = ideal;
    }
  });
  return ajustes;
}
''')
