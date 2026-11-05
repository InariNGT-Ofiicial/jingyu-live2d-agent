const fs=require('node:fs'),path=require('node:path');
module.exports=function(runtime,folder,mode){
 runtime={...runtime};
 for(const key of ['java','jar','cwd'])if(!path.isAbsolute(runtime[key]))runtime[key]=path.resolve(folder,'../..',runtime[key]);
 if(mode==='demo')return runtime;
 if(mode!=='survival')throw Error('Unknown world mode');
 const cwd=path.join(folder,'survival-server');fs.mkdirSync(cwd,{recursive:true});
 const properties=path.join(cwd,'server.properties');
 if(!fs.existsSync(properties))fs.writeFileSync(properties,[
  'server-ip=127.0.0.1','server-port=25566','online-mode=false','enforce-secure-profile=false',
  'level-name=jingyu-survival','level-type=minecraft:normal','level-seed=20261105',
  'generate-structures=true','gamemode=survival','difficulty=normal','spawn-protection=0',
  'view-distance=5','simulation-distance=5','max-players=3','enable-rcon=false',
  'max-tick-time=60000','sync-chunk-writes=false','motd=Jingyu survival development world',''
 ].join('\n'));
 if(!fs.existsSync(path.join(cwd,'eula.txt')))fs.copyFileSync(path.join(runtime.cwd,'eula.txt'),path.join(cwd,'eula.txt'));
 return {...runtime,cwd};
};
