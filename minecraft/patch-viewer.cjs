// Compatibility fix for prismarine-viewer 1.33.0's pre-1.18 height assumptions.
// Keep source and shipped browser bundles aligned, without rebuilding its 63 MB data bundle.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
function apply(){
 const root=path.dirname(require.resolve('prismarine-viewer/package.json')),stamp=path.join(root,'.jingyu-height.json');
 if(fs.existsSync(stamp))return;
 if(require(path.join(root,'package.json')).version!=='1.33.0')throw Error('Recheck viewer height patch for this version');
 const changes=[
  ['viewer/lib/worldrenderer.js',[[/for \(let y = 0; y < 256; y \+= 16\)/g,'for (let y = -64; y < 320; y += 16)',2]]],
  ['viewer/lib/worker.js',[[/chunk.sections\[Math.floor\(y \/ 16\)\]/g,'chunk.sections[Math.floor((y - (chunk.minY ?? 0)) / 16)]',2]]],
  ['viewer/lib/models.js',[[/if \(neighbor.position.y < 0\) continue/g,'// Negative Y is valid in modern overworlds.',2]]],
  ['public/index.js',[[/for\(let (\w+)=0;\1<256;\1\+=16\)/g,(_,v)=>`for(let ${v}=-64;${v}<320;${v}+=16)`,2]]],
  ['public/worker.js',[[/(\w+)\.sections\[Math\.floor\((\w+)\/16\)\]/g,(_,c,y)=>`${c}.sections[Math.floor((${y}-(${c}.minY??0))/16)]`,2],[/\w+\.position\.y<0/g,'false',2]]]
 ];
 const sha=s=>crypto.createHash('sha256').update(s).digest('hex'),records=[];
 for(const [file,edits] of changes){
  const full=path.join(root,file);let code=fs.readFileSync(full,'utf8');const before=sha(code);
  for(const [pattern,replacement,count] of edits){
   if([...code.matchAll(pattern)].length!==count)throw Error('Viewer patch source differs: '+file);
   code=code.replace(pattern,replacement);
  }
  fs.writeFileSync(full,code);records.push({file,before,after:sha(code)});
 }
 fs.writeFileSync(stamp,JSON.stringify({version:'1.33.0',reason:'Render -64..319 and offset chunk sections by minY',records},null,2));
 console.log('Viewer modern-height compatibility applied');
}
module.exports=apply;if(require.main===module)apply();
