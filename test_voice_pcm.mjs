import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
let Processor;
const messages=[];
const runtime={
 sampleRate:48000,currentTime:0,AudioWorkletProcessor:class{constructor(){this.port={postMessage:m=>messages.push(m)};}},
 registerProcessor:(name,klass)=>{Processor=klass;}
};
vm.runInNewContext(fs.readFileSync(new URL('./web/voice-pcm-worklet.mjs',import.meta.url),'utf8'),runtime);
const pcm=new Processor(),send=m=>pcm.port.onmessage({data:m});
const tick=()=>{const output=new Float32Array(128);const alive=pcm.process([],[[output]]);return {output,alive};};
send({type:'config',sampleRate:24000,bufferSeconds:.01});
send({type:'pcm',samples:new Float32Array(128).fill(.5)});
assert.ok(tick().output.every(x=>x===0),'must buffer before starting');
send({type:'pcm',samples:new Float32Array(128).fill(.5)});
assert.ok(tick().output.every(x=>x===0),'queued audio must also respect the initial time reserve');
runtime.currentTime=.02;
send({type:'end'});
let total=0;
for(let i=0;i<8;i++){const {output,alive}=tick();total+=output.reduce((a,v)=>a+v,0);if(!alive)break;}
assert.equal(total,256,'24 kHz input must play for twice as many 48 kHz frames');
assert.equal(messages.at(-1).type,'ended');assert.equal(messages.at(-1).underrunBlocks,0);
const stop=new Processor();stop.port.onmessage({data:{type:'pcm',samples:new Float32Array(500).fill(1)}});
stop.port.onmessage({data:{type:'stop'}});const output=new Float32Array(128);
assert.equal(stop.process([],[[output]]),false);assert.ok(output.every(x=>x===0));
console.log('PCM buffering, resampling, completion, and immediate stop passed');
