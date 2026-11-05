export class VoiceStreamPlayer {
 constructor(ctx,destination,onUpdate=()=>{},options={}){
  this.ctx=ctx;this.destination=destination;this.onUpdate=onUpdate;
  this.segments=[];this.stats={playedSamples:0,queuedSeconds:0,underrunBlocks:0,started:false};
  this.active=false;this.finished=false;this.cancelled=false;this.rate=24000;
  this.bufferSeconds=options.bufferSeconds??3;this.requestedAt=options.requestedAt??performance.now();
 }
 async play(url){
  await this.ctx.audioWorklet.addModule('./voice-pcm-worklet.mjs');
  if(this.cancelled)return;
  this.node=new AudioWorkletNode(this.ctx,'jingyu-voice-pcm',{numberOfInputs:0,numberOfOutputs:1,outputChannelCount:[1]});
  this.node.connect(this.destination);this.active=true;
  const drained=new Promise(resolve=>{this.resolve=resolve;});
  this.node.port.onmessage=({data})=>{
   if(data.started&&!this.stats.started)this.stats.startPlaybackSeconds=(performance.now()-this.requestedAt)/1000;
   this.stats={...this.stats,...data};this.onUpdate(this.status());
   if(data.type==='ended'){this.active=false;this.node.disconnect();this.resolve();}
  };
  this.controller=new AbortController();
  try{
   const response=await fetch(url,{signal:this.controller.signal});
   if(!response.ok)throw Error((await response.json()).error||'音频流连接失败');
   const reader=response.body.getReader(),decoder=new TextDecoder();let pending='';
   while(true){
    const {value,done}=await reader.read();
    pending+=decoder.decode(value,{stream:!done});
    let index;
    while((index=pending.indexOf('\n'))>=0){const line=pending.slice(0,index);pending=pending.slice(index+1);if(line)this.receive(JSON.parse(line));}
    if(done)break;
   }
   if(!this.finished&&!this.cancelled)throw Error('音频流中断，请重试');
   await drained;
  }catch(e){this.stop();if(e.name!=='AbortError')throw e;}
 }
 receive(event){
  if(this.cancelled)return;
  if(event.type==='start'){
   this.rate=event.sampleRate;
   this.node.port.postMessage({type:'config',sampleRate:this.rate,bufferSeconds:this.bufferSeconds});
  }
  if(event.type==='segment')this.segments.push(event);
  if(event.type==='pcm'){
   this.stats.firstPCMSeconds??=(performance.now()-this.requestedAt)/1000;
   const binary=atob(event.data),bytes=Uint8Array.from(binary,c=>c.charCodeAt(0));
   const view=new DataView(bytes.buffer),samples=new Float32Array(event.samples);
   if(bytes.length!==samples.length*2)throw Error('音频帧长度不匹配');
   for(let i=0;i<samples.length;i++)samples[i]=view.getInt16(i*2,true)/32768;
   this.node.port.postMessage({type:'pcm',samples},[samples.buffer]);
  }
  if(event.type==='done'){this.finished=true;this.take=event;this.node.port.postMessage({type:'end'});}
  if(event.type==='error')throw Error(event.error);
  if(event.type==='cancelled')this.stop();
 }
 status(){
  const segment=this.stats.started?[...this.segments].reverse().find(s=>s.offsetSamples<=this.stats.playedSamples):null;
  return {...this.stats,active:this.active,finished:this.finished,text:segment?.text||'',time:this.stats.playedSamples/this.rate,
   segmentIndex:Math.max(0,this.segments.indexOf(segment)),segmentTime:segment?(this.stats.playedSamples-segment.offsetSamples)/this.rate:0};
 }
 stop(){
  this.cancelled=true;this.active=false;this.controller?.abort();
  this.node?.port.postMessage({type:'stop'});this.node?.disconnect();this.resolve?.();
 }
}
