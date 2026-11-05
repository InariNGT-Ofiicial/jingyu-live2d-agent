// Persistent PCM queue. The audio thread keeps playing when the page's RAF is throttled.
class VoicePCM extends AudioWorkletProcessor {
 constructor(){
  super();this.queue=[];this.offset=0;this.rate=24000;this.bufferSeconds=3;
  this.available=0;this.played=0;this.started=false;this.finished=false;this.closed=false;this.underruns=0;this.counter=0;this.firstPCMAt=null;
  this.port.onmessage=({data:m})=>{
   if(m.type==='config'){this.rate=m.sampleRate;this.bufferSeconds=m.bufferSeconds??3;}
   if(m.type==='pcm'){this.firstPCMAt??=currentTime;this.queue.push(m.samples);this.available+=m.samples.length;}
   if(m.type==='end')this.finished=true;
   if(m.type==='stop'){this.queue=[];this.available=0;this.closed=true;}
  };
 }
 process(inputs,outputs){
  const out=outputs[0][0];out.fill(0);if(this.closed)return false;
  if(!this.started&&((this.available>=this.rate*this.bufferSeconds&&currentTime-this.firstPCMAt>=this.bufferSeconds)||(this.finished&&this.available>0)))this.started=true;
  let starved=false;
  if(this.started){
   const step=this.rate/sampleRate;
   for(let i=0;i<out.length;i++){
    while(this.queue.length&&this.offset>=this.queue[0].length){this.offset-=this.queue[0].length;this.queue.shift();}
    if(!this.queue.length){starved=!this.finished;break;}
    const chunk=this.queue[0],index=Math.floor(this.offset),fraction=this.offset-index;
    const next=chunk[index+1]??this.queue[1]?.[0]??chunk[index];
    out[i]=chunk[index]+(next-chunk[index])*fraction;
    const used=Math.min(step,this.available);this.available-=used;this.played+=used;this.offset+=step;
   }
  }
  if(starved)this.underruns++;
  if(++this.counter%20===0)this.port.postMessage({type:'progress',playedSamples:this.played,queuedSeconds:this.available/this.rate,underrunBlocks:this.underruns,started:this.started});
  if(this.finished&&this.available<=0){
   this.port.postMessage({type:'ended',playedSamples:this.played,underrunBlocks:this.underruns});return false;
  }
  return true;
 }
}
registerProcessor('jingyu-voice-pcm',VoicePCM);
