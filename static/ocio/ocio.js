'use strict';
const scope=document.querySelector('#nt-ocio'), mode=scope.dataset.mode, $=s=>scope.querySelector(s);
const el=(tag,value)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=value;return e};
const button=(v,fn)=>{const e=el('button',v);e.type='button';e.onclick=fn;return e};
const mod=(x,n)=>((x%n)+n)%n;
const day=key=>Math.floor(Date.parse(key+'T00:00:00Z')/86400000);
const today=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Madrid',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
function rng(s){return ()=>{s=(Math.imul(1664525,s)+1013904223)>>>0;return s/4294967296}}
function shuffle(a,r){a=[...a];for(let i=a.length-1;i>0;i--){const j=Math.floor(r()*(i+1));[a[i],a[j]]=[a[j],a[i]]}return a}
function read(k){try{return JSON.parse(localStorage.getItem(k))}catch{return null}}
function save(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch{}}
function board(n){const e=el('div');e.className='grid';e.style.setProperty('--n',n);return e}
function count(a,limit=2){let best=-1,candidates;
 for(let p=0;p<81;p++)if(!a[p]){const row=Math.floor(p/9),col=p%9,br=Math.floor(row/3)*3,bc=Math.floor(col/3)*3,used=new Set();
 for(let j=0;j<9;j++){used.add(a[row*9+j]);used.add(a[j*9+col]);used.add(a[(br+Math.floor(j/3))*9+bc+j%3])}
 const next=[1,2,3,4,5,6,7,8,9].filter(x=>!used.has(x));if(!next.length)return 0;if(!candidates||next.length<candidates.length){best=p;candidates=next}}
 if(best<0)return 1;
 let n=0;for(const x of candidates){a[best]=x;n+=count(a,limit-n);a[best]=0;if(n>=limit)return n}return n
}
function sudoku(seed,level){const r=rng(seed*19+level), perm=()=>shuffle([0,1,2],r).flatMap(b=>shuffle([0,1,2],r).map(x=>3*b+x)), rows=perm(),cols=perm(),d=shuffle([1,2,3,4,5,6,7,8,9],r), full=rows.flatMap(y=>cols.map(x=>d[(y*3+Math.floor(y/3)+x)%9])), a=[...full];
 let remaining=81;for(const i of shuffle(a.keys(),r)){const v=a[i];a[i]=0;if(count(a)!==1)a[i]=v;else if(--remaining===[44,37,31][level])break}return [a,full]
}
function showSudoku(root,key){const label=el('label','Dificultad '),select=el('select');['Fácil','Media','Difícil'].forEach((t,i)=>{const o=el('option',t);o.value=i;select.append(o)});label.append(select);root.append(label);const area=el('div');root.append(area);
 function render(){const level=+select.value,k='nt-ocio:v1:sudoku:'+key+':'+level,[p,sol]=sudoku(day(key),level),stored=read(k),grid=board(9);area.replaceChildren();const cells=p.map((v,i)=>{const e=el('input');e.inputMode='numeric';e.maxLength=1;e.value=v||stored?.[i]||'';e.readOnly=!!v;e.setAttribute('aria-label','Fila '+(Math.floor(i/9)+1)+', columna '+(i%9+1));if(i%3===2&&i%9!==8)e.classList.add('b-r');if([2,5].includes(Math.floor(i/9)))e.classList.add('b-b');e.oninput=()=>{e.value=e.value.replace(/[^1-9]/g,'').slice(0,1);e.classList.remove('err');save(k,cells.map(c=>c.value));status('')};grid.append(e);return e});
 area.append(grid,button('Comprobar',()=>{let errors=0,empty=0;cells.forEach((e,i)=>{const wrong=e.value&&+e.value!==sol[i];e.classList.toggle('err',!!wrong);if(wrong)errors++;if(!e.value)empty++});status(errors?'Casillas a revisar: '+errors:empty?'Vas bien. Casillas pendientes: '+empty:'¡Sudoku resuelto!')}));
 area.append(' ',button('Reiniciar',()=>{save(k,null);render();status('Sudoku reiniciado.')}))}
 select.onchange=()=>{status('');render()};render()
}
const soups=[
 ['Astronomía','COMETA','PLANETA','GALAXIA','ORBITA','NEBULOSA','ESTRELLA'],
 ['Naturaleza','BOSQUE','LAGUNA','CORDILLERA','CASCADA','SENDERO','ACANTILADO'],
 ['Música','GUITARRA','TROMPETA','VIOLIN','MELODIA','COMPAS','PERCUSION'],
 ['Mercado','CALABAZA','TOMATE','ALMENDRA','PIMIENTO','MANZANA','LECHUGA'],
 ['Transporte','AUTOBUS','ESTACION','BICICLETA','TRANVIA','AEROPUERTO','ANDEN'],
 ['Cocina','CUCHARA','SARTEN','BANDEJA','BATIDORA','COLADOR','ESPATULA'],
 ['Lectura','NOVELA','POESIA','CUENTO','CAPITULO','PORTADA','BIBLIOTECA']];
const sets=[
 [['Instrumentos','ARPA','OBOE','TUBA','VIOLA'],['Frutas','PERA','KIWI','MANGO','UVA'],['Mares','BÁLTICO','EGEO','ADRIÁTICO','CARIBE'],['Puntuación','COMA','PUNTO','TILDE','DIÉRESIS']],
 [['Árboles','ABEDUL','ROBLE','CEDRO','OLIVO'],['Cortes de cocina','JULIANA','BRUNOISE','RODAJAS','BASTONES'],['Planetas','MARTE','VENUS','URANO','SATURNO'],['Tejidos','LINO','SEDA','TERCIOPELO','SATÉN']],
 [['Unidades de tiempo','HORA','SEMANA','SIGLO','LUSTRO'],['Piezas de ajedrez','ALFIL','PEÓN','TORRE','REINA'],['Quesos','GOUDA','BRIE','MANCHEGO','CHEDDAR'],['Vientos','CIERZO','TRAMONTANA','LEVANTE','SIROCO']],
 [['Tipos de nube','CIRRO','CÚMULO','ESTRATO','NIMBOESTRATO'],['Formas geométricas','ROMBO','ÓVALO','HEXÁGONO','TRAPECIO'],['Calzado','SANDALIA','BOTA','MOCASÍN','ZUECO'],['Legumbres','LENTEJA','GARBANZO','GUISANTE','ALUBIA']],
 [['Elementos de una bicicleta','PEDAL','MANILLAR','SILLÍN','RADIO'],['Aves marinas','GAVIOTA','ALBATROS','CORMORÁN','FRAILECILLO'],['Especias','COMINO','CANELA','CLAVO','CÚRCUMA'],['Partes de una flor','PÉTALO','SÉPALO','ESTAMBRE','PISTILO']],
 [['Capitales','OSLO','LIMA','RIGA','DAKAR'],['Colores','MALVA','OCRE','GRANATE','CARMESÍ'],['Modalidades de atletismo','MARTILLO','JABALINA','PÉRTIGA','RELEVOS'],['Acciones en un libro','SUBRAYAR','HOJEAR','MARCAR','RELEER']],
 [['Géneros teatrales','COMEDIA','TRAGEDIA','SAINETE','ENTREMÉS'],['Herramientas','TENAZAS','LIMA','SIERRA','LLAVE'],['Piedras preciosas','RUBÍ','ZAFIRO','ESMERALDA','DIAMANTE'],['Postres','FLAN','SORBETE','NATILLAS','ARROZ CON LECHE']]];
function soup(seed){const [name,...words]=soups[mod(seed,soups.length)],r=rng(seed),n=12,letters=Array(n*n).fill(''), paths=[];
 for(const word of words){const options=[];for(let i=0;i<n*n;i++)for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){if(!dx&&!dy)continue;const y=Math.floor(i/n),x=i%n,ye=y+dy*(word.length-1),xe=x+dx*(word.length-1);if(ye<0||ye>=n||xe<0||xe>=n)continue;const cells=[...word].map((_,j)=>i+j*(dy*n+dx));if(cells.every((p,j)=>!letters[p]||letters[p]===word[j]))options.push(cells)}
 if(!options.length)throw Error('No se pudo colocar '+word);const cells=options[Math.floor(r()*options.length)];cells.forEach((p,j)=>letters[p]=word[j]);paths.push(cells)}
 return {name,words,paths,n,letters:letters.map(x=>x||'ABCDEFGHIJKLMNÑOPQRSTUVWXYZ'[Math.floor(r()*27)])}
}
function showSoup(root,key){const {name,words,paths,n,letters}=soup(day(key)),k='nt-ocio:v1:sopa:'+key;let start=null,found=new Set(read(k)||[]);const grid=board(n),list=el('p');list.className='palabras';root.append(el('h2',name),list,grid);
 const cells=letters.map((v,i)=>{const e=button(v,()=>{if(start===null){start=i;paint();return}const hit=paths.findIndex(p=>(p[0]===start&&p.at(-1)===i)||(p.at(-1)===start&&p[0]===i));start=null;if(hit>=0){found.add(hit);save(k,[...found]);status(found.size===words.length?'¡Encontraste todas las palabras!':'Encontraste '+words[hit]+'.')}else status('Esa selección no coincide con la lista.');paint()});e.setAttribute('aria-label',v+', fila '+(Math.floor(i/n)+1)+', columna '+(i%n+1));grid.append(e);return e});
 function paint(){list.textContent=words.map((w,i)=>found.has(i)?'✓ '+w:w).join(' · ');cells.forEach((e,i)=>{e.classList.toggle('hallada',[...found].some(j=>paths[j]?.includes(i)));e.setAttribute('aria-pressed',String(start===i))})}paint()
}
function showSets(root,key){const d=day(key),groups=sets[mod(d,sets.length)],k='nt-ocio:v1:conex:'+key,done=new Set(read(k)||[]),chosen=new Set(),order=shuffle(groups.flatMap((g,i)=>g.slice(1).map(v=>({v,i}))),rng(d)), results=el('div'), grid=board(4);grid.classList.add('conex');root.append(results,grid);
 const verify=button('Comprobar grupo',()=>{if(chosen.size!==4)return;const arr=[...chosen];if(arr.every(j=>order[j].i===order[arr[0]].i)){done.add(order[arr[0]].i);save(k,[...done]);status(done.size===4?'¡Encontraste los cuatro grupos!':'Grupo correcto.')}else status('Estas cuatro palabras no forman un grupo.');chosen.clear();paint()});root.append(verify,' ',button('Quitar selección',()=>{chosen.clear();paint();status('')}));
 function paint(){results.replaceChildren();for(const i of done){if(!groups[i])continue;const p=el('p',groups[i][0]+': '+groups[i].slice(1).join(' · '));p.className='solved';results.append(p)}for(let j=0;j<order.length;j++){const item=order[j];cells[j].hidden=done.has(item.i);cells[j].setAttribute('aria-pressed',String(chosen.has(j)))}verify.disabled=chosen.size!==4}
 const cells=order.map(({v},j)=>{const e=button(v,()=>{if(chosen.has(j))chosen.delete(j);else if(chosen.size<4)chosen.add(j);paint()});grid.append(e);return e});paint()
}
const signs=['Aries','Tauro','Géminis','Cáncer','Leo','Virgo','Libra','Escorpio','Sagitario','Capricornio','Acuario','Piscis'];
const lines=[
 ['Si tienes mucho por hacer, elige qué puede esperar.','Una pausa antes de responder puede aclararte lo que quieres decir.','Vuelve a una idea que dejaste a medias y dale veinte minutos.','Fíjate en lo que te da energía y reserva un rato para ello.','Haz una pregunta concreta antes de sacar conclusiones.','Cambia de ambiente para mirar con otros ojos lo que te preocupa.','Un pequeño gesto de atención vale más que una promesa grande.'],
 ['Deja un hueco en la agenda para conversar sin prisas.','Escribe la primera idea antes de exigirle que sea perfecta.','Un paseo corto puede separar el trabajo del resto del día.','Pon en orden una cosa que te ahorre tiempo mañana.','Si necesitas ayuda, pide algo específico.','Agradece un gesto que se te había pasado por alto.','Prueba una forma más sencilla de hacer una tarea habitual.']];
function horoscope(root,key){const r=rng(day(key)*79),list=el('div');list.className='tarjetas';signs.forEach(s=>{const a=el('article');a.append(el('h2',s),el('p',lines.map(l=>l[Math.floor(r()*l.length)]).join(' ')));list.append(a)});root.append(list)}
const status=v=>{$('#estado').textContent=v};
if(mode!=='juegos'){const date=$('#fecha');date.max=today();date.min='2026-11-10';date.value=date.max;
 const paint=()=>{const k=date.value;if(!/^\d{4}-\d\d-\d\d$/.test(k)||k>date.max||k<date.min){status('Elige una fecha del calendario disponible.');return}const root=$('#tablero');root.replaceChildren();status('');({sudoku:showSudoku,'sopa-de-letras':showSoup,conexiones:showSets,horoscopo:horoscope})[mode](root,k)};
 date.onchange=paint;$('#hoy').onclick=()=>{date.max=today();date.value=date.max;paint()};paint()}
