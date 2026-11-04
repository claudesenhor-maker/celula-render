import {fixture} from './fixtures_graficos.mjs';
const lamp=fixture('mecanismo');
lamp.titulo='POR DENTRO DA LÂMPADA';lamp.dur_s=6;
lamp.cenas=[
 {ini:0,fim:1.5,acao:'mostra',camera:'frente'},
 {ini:1.5,fim:3,acao:'corte',corte_modo:'secao',camera:'frente',alvo:['filamento'],rotulos:[{parte:'filamento',texto:'Filamento'}]},
 {ini:3,fim:6,acao:'destaque',corte_modo:'secao',camera:'perto',alvo:['filamento'],rotulos:[{parte:'filamento',texto:'Filamento de tungstênio'},{parte:'suporte1',texto:'Suporte metálico'}]}
];
const pixel=fixture('pixel');pixel.titulo='PAUSA PARA O CAFÉ';pixel.dur_s=6;
pixel.cenas=[{ini:0,fim:6,acao:'come',objeto:'cafe',cenario:'cozinha',atores:['heroi'],quem:'Sistema',texto:'Você usou café. Energia recuperada.',hud:{energia:80}}];
const escala=fixture('enem');escala.titulo='O DOBRO DO TAMANHO';escala.dur_s=6;
escala.cenas=[{ini:0,fim:6,acao:'esquema',area:'matematica',esquema:'escala',itens:['Bloco A','Bloco B','Bloco C'],valores:[1,2,4],unidade:'cm',lousa:'Mesma unidade, mesma escala'}];
export const COMPARACOES={mecanismo:lamp,pixel,escala};
