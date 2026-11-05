import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {decodeGif,analyzeTiming} from '../web/community-vendor/gif-analysis.mjs';
try{
 if(!process.argv[2])throw Error('Usage: node tools/analyze_motion_gif.mjs <file.gif>');
 const bytes=readFileSync(process.argv[2]);if(bytes.length>32*1024*1024)throw Error('请选择小于 32MB 的 GIF');
 const result=decodeGif(bytes);if(!result.ok)throw Error(result.error);
 console.log(JSON.stringify({...result,sha256:createHash('sha256').update(bytes).digest('hex'),timing:analyzeTiming(result.frames),semanticStatus:'unverified'},null,2));
}catch(e){console.error(e.message);process.exitCode=1;}
