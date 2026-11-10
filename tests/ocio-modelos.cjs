const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const src=fs.readFileSync(path.join(__dirname,'../static/ocio/ocio.js'),'utf8');
const scope={dataset:{mode:'juegos'}};
vm.runInNewContext(src+`
for(let d=20767;d<20800;d++)for(let l=0;l<3;l++){
 const [a,s]=sudoku(d,l);assert.equal(count([...a]),1);
 for(let row=0;row<9;row++)assert.equal(new Set(s.slice(row*9,row*9+9)).size,9);
}
for(let d=20767;d<20800;d++){const q=soup(d);
 q.words.forEach((w,i)=>assert.equal(q.paths[i].map(j=>q.letters[j]).join(''),w));
}
sets.forEach(gs=>{assert.equal(gs.length,4);assert.equal(new Set(gs.flatMap(g=>g.slice(1))).size,16)});
`,{document:{querySelector:()=>scope},assert});
console.log('OK: 99 sudokus con solución única; 33 sopas completas; 7 conjuntos sin palabras duplicadas');
