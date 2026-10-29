const parte=(nome,forma,pos,tam,cor,extra={})=>({nome,forma,pos,tam,cor,...extra});
const gato=[parte('tronco','esfera',[0,.8,0],[1.7,.7,.6],'#BC8C53',{material:'pele'}),parte('cabeca','esfera',[.9,1,0],[.6,.6,.55],'#BC8C53'),
 ...[-1,1].flatMap(l=>[parte('orelha'+l,'cone',[.9,1.35,l*.17],[.2,.3,.2],'#875A39'),parte('olho'+l,'esfera',[1.14,1.08,l*.18],[.045,.07,.045],'#26231C')]),
 parte('focinho','esfera',[1.18,.95,0],[.3,.2,.35],'#DEC7A0'),parte('nariz','esfera',[1.32,1,0],[.08,.07,.1],'#40322B'),
 parte('cauda','capsula',[-1.0,.8,0],[.13,.85,.13],'#9A744A',{giro:[0,0,75],pivo:[0,.4,0]}),
 ...[-.6,.6].flatMap((x,i)=>[-.23,.23].map((z,j)=>parte('pata'+i+j,'cilindro',[x,.35,z],[.14,.7,.14],'#A77B49')))
];
export const FIXTURES={
 lowpoly:{cenas:[{cenario:'cidade',acao:'mostra',atores:['pessoa'],texto:'People move through a city.'},{cenario:'cidade',acao:'vento',atores:['pessoa'],texto:'Strong wind pushes the trees.'}]},
 mecanismo:{ambiente:'oficina',modelo:{partes:[
 parte('vidro','esfera',[0,2,0],[1.65,1.9,1.65],'#B8DCEB',{material:'vidro',casca:true,explode:[0,1.8,0]}),
 parte('base','cilindro',[0,.5,0],[.72,.85,.72],'#BDBCC2',{material:'aco'}),
 parte('pescoço','cilindro',[0,1.05,0],[.58,.45,.58],'#CBDEE6',{material:'vidro',casca:true}),
 parte('isolante','disco',[0,.05,0],[.7,1,.7],'#444653',{material:'borracha'}),
 parte('filamento','mola',[0,2.15,0],[.6,.2,.17],'#FFBD65',{material:'latao'}),
 ...[-1,1].map(l=>parte('suporte'+l,'cilindro',[l*.23,1.65,0],[.035,.9,.035],'#B5AD9D',{material:'aco'})),
 ...Array.from({length:5},(_,i)=>parte('rosca'+i,'anel',[0,.25+i*.12,0],[.76,.76,.76],'#A1A2AA',{giro:[90,0,0],material:'aco'}))
 ]},cenas:[{acao:'mostra'},{acao:'corte',alvo:['filamento'],rotulos:[{parte:'filamento',texto:'Filament'}]}]},
 escala:{itens:[{nome:'Person',modelo:'pessoa',tamanho_m:1.75},{nome:'Tower',modelo:'torre',tamanho_m:30}],cenas:[{alvo:0},{alvo:1}]},
 animal:{animal:{nome:'Cat',tamanho_m:1.1,habitat:'floresta',partes:gato},stats:[{nome:'Speed',valor:30,unidade:'km/h',humano:15}],cenas:[{acao:'mostra'},{acao:'corre',stat:0}]},
 orbita:{data_referencia:'2026-10-26T12:00:00Z',cenas:[{acao:'foco',alvo:'earth'},{acao:'compara',alvo:'earth',alvo2:'moon'}]},
 micro:{ativo:{nome:'Active',cor:'#5BC0EB',forma:'cadeia'},cenas:[{acao:'corte'},{acao:'aplica'}]},
 pixel:{hud_inicial:{hp:80,energia:60,ouro:120,nivel:27},cenas:[{acao:'digita',cenario:'escritorio',atores:['heroi'],texto:'Another meeting. Energy -50.',quem:'System',hud:{energia:10}},{acao:'batalha',atores:['heroi','chefe'],texto:'BOSS used: QUICK SYNC.',quem:'System',dano:40}]},
 mangueira:{cenas:[{acao:'entra_andando',cenario:'rua',atores:['hank','dottie'],objeto:'banana'},{acao:'escorrega',cenario:'rua',atores:['hank','dottie'],objeto:'banana'}]},
 silhueta:{cenas:[{acao:'anda',cenario:'cidade',hora:'noite',atores:['homem'],objeto:'nevoa',texto:'Fog filled the streets.'},{acao:'corre',cenario:'cidade',hora:'tempestade',atores:['homem'],objeto:'chuva',texto:'Rain reached the town.'}]},
 mapa:{cenas:[{acao:'destaca',paises:['Brazil'],ano:'2026',texto:'Brazil in South America.'},{acao:'rota',paises:['Brazil','Portugal'],rota:{pontos:[[-43,-23],[-9,39]],rotulo:'Atlantic'},texto:'A route across the Atlantic.'}]},
 linha_tempo:{cenas:[{acao:'marco',ano:1903,evento:'First powered flight',icone:'aviao'},{acao:'zoom',ano:1969,evento:'People reach the Moon',icone:'atomo'}]},
 quiz:{cenas:[{tipo:'icones',base:'relogio',diferente:'hora',colunas:6,linhas:8,dificuldade:3,texto:'Find the clock'},{tipo:'formas',base:'estrela',diferente:'girado',colunas:7,linhas:9,dificuldade:4,texto:'Find the star'}]},
 fisica:{fisica:{modo:'plinko',bolas:4},cenas:[{texto:'Which color wins?'},{texto:'Watch the final bounce'}]},
 enem:{cenas:[{acao:'fato',area:'natureza',lousa:'A luz transporta energia',icone:'atomo',texto:'A luz transporta energia.'},{acao:'esquema',area:'natureza',lousa:'Transferência de energia',itens:['Fonte','Transformação','Efeito'],esquema:'cadeia',texto:'A energia se transforma.'}]}
};
export function fixture(estilo){const f=structuredClone(FIXTURES[estilo]);return {w:1080,h:1920,fps:30,dur_s:8,titulo:estilo.toUpperCase(),semente:'qualidade-v2',palavras:[],...f,estilo,cenas:f.cenas.map((c,i)=>({ini:i*4,fim:(i+1)*4,...c}))};}
