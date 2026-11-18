// Use the hardware-rate context for both capture and playback (including iOS).
// The ASR and turn detector always receive 64 ms blocks of 16 kHz mono.
export function micBlocks(rate, consume) {
 let phase=0, sum=0, count=0, block=new Float32Array(1024), used=0;
 return (input,endTime)=>{
  for(let i=0;i<input.length;i++){
   sum+=input[i]; count++; phase+=16000;
   if(phase<rate)continue;
   phase-=rate;block[used++]=sum/count;sum=0;count=0;
   if(used===block.length){
    consume(block,endTime-(input.length-1-i)/rate);
    block=new Float32Array(1024);used=0;
   }
  }
 };
}

// A short, low-rate copy of scheduled output is enough to recognize delayed
// loudspeaker leakage. Native AEC still handles the full-rate microphone.
const referenceRate=2000;
function reduce(samples,rate) {
 const ratio=rate/referenceRate, out=new Float32Array(Math.floor(samples.length/ratio));
 for(let i=0;i<out.length;i++){
  const begin=Math.floor(i*ratio),end=Math.floor((i+1)*ratio);
  for(let j=begin;j<end;j++)out[i]+=samples[j];
  out[i]/=end-begin;
 }
 return out;
}
export class PlaybackReference {
 clips=[];
 add(samples,rate,start){
  this.clips.push({start,end:start+samples.length/rate,data:reduce(samples,rate)});
 }
 stop(now){
  for(const c of this.clips)c.end=Math.min(c.end,now);
 }
 matches(samples,end){
  this.clips=this.clips.filter(c=>c.end>end-.75);
  if(!this.clips.length)return false;
  const mic=reduce(samples,16000),first=end-samples.length/16000;
  let power=0;for(const x of mic)power+=x*x;
  if(power<1e-7)return false;
  for(const c of this.clips){
   const valid=Math.min(c.data.length,Math.round((c.end-c.start)*referenceRate));
   const lo=Math.max(0,Math.floor((first-.48-c.start)*referenceRate));
   const hi=Math.min(valid-mic.length,Math.ceil((first+.10-c.start)*referenceRate));
   for(let offset=lo;offset<=hi;offset++){
    let dot=0,ref=0;
    for(let j=0;j<mic.length;j++){const x=c.data[offset+j];dot+=x*mic[j];ref+=x*x}
    // Strongly correlated output alone is discarded. Independent overlapping
    // speech leaves enough residual energy to open the microphone.
    if(ref>1e-6 && dot*dot>.56*ref*power && (power-dot*dot/ref)/mic.length<.00032)return true;
   }
  }
  return false;
 }
}
