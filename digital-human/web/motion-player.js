import {MotionDirector} from './motion-director.js';
export async function createMotionPlayer(figure,portrait,onError){
 const policy=portrait?await (await fetch('/motions/phone/motion-policy.json')).json():{
  idleAfterMs:45000,clips:Object.fromEntries(['front-breathe','h3-shoulders','h3-ribbon','acknowledge','read-request'].map(n=>[n,{file:'frontal/'+n+'.mp4',cooldownMs:18000}])),
  pools:{idle:['front-breathe','h3-shoulders','front-breathe','h3-ribbon']}
 };
 const director=new MotionDirector(policy),log=window.motionLog=[];
 if(portrait && policy.mobileDirectory && navigator.maxTouchPoints>0 && 'requestVideoFrameCallback' in HTMLVideoElement.prototype){
  const {mobileMotion}=await import('./mobile-motion.js');
  return mobileMotion(figure,policy,director,onError);
 }
 const canvas=document.createElement('canvas'),surface=canvas.getContext('2d',{alpha:false});
 const anchor=new Image();anchor.src=portrait?'/motions/phone-delivery-v2/anchor.webp':'/motions/frontal/anchor.png';await anchor.decode();
 canvas.width=anchor.naturalWidth;canvas.height=anchor.naturalHeight;surface.drawImage(anchor,0,0);figure.append(canvas);
 const videos=new Map(),failed=new Set();let closed=false,callback,playing,watchdog;
 for(const [name,c] of Object.entries(policy.clips)){
  const v=document.createElement('video');v.muted=true;v.playsInline=true;v.preload='none';v.src='/motions/'+c.file;
  v.addEventListener('error',()=>{failed.add(name);onError('动作暂不可用');if(v===playing)advance(true)});
  videos.set(name,v);
 }
 function warm(name){
  const v=videos.get(name);
  if(v&&v.preload!=='auto'){v.preload='auto';v.load()}
 }
 let warmed=false;
 function advance(failure=false){
  if(closed)return;clearTimeout(watchdog);
  if(playing){playing.cancelVideoFrameCallback(callback);playing.pause();playing.onended=null;playing=null}
  if(failed.size===videos.size){onError('动作资源不可用');return}
  const choice=director.next(name=>{
   if(failed.has(name))return false;
   warm(name);
   return videos.get(name).readyState>=3 || (!log.length && name==='front-breathe');
  });
  if(!choice){watchdog=setTimeout(()=>advance(failure),100);return}
  play(choice,failure);
 }
 function play(choice,recovery){
  const video=videos.get(choice.name);playing=video;video.currentTime=0;
  const entry={name:choice.name,reason:choice.reason,start:performance.now(),recovery,turnIds:choice.turnId==null?[]:[choice.turnId]};log.push(entry);if(log.length>400)log.shift();
  let first=true;
  function paint(now,meta){
   if(closed||playing!==video)return;
   surface.drawImage(video,0,0);
   if(first){
    entry.firstFrame=performance.now();first=false;clearTimeout(watchdog);
    if(!warmed){warmed=true;warm('h3-shoulders');warm('wave')}
   }
   entry.lastMediaTime=meta.mediaTime;callback=video.requestVideoFrameCallback(paint);
  }
  callback=video.requestVideoFrameCallback(paint);
  video.onended=()=>{entry.end=performance.now();entry.lastTime=video.currentTime;entry.duration=video.duration;advance()};
  // Preserve the last decoded image while another decoder becomes ready.
  watchdog=setTimeout(()=>{if(first){failed.add(choice.name);onError('动作载入较慢');advance(true)}},8000);
  video.play().catch(()=>{if(!closed && playing===video){failed.add(choice.name);advance(true)}});
 }
 advance();
 function request(name,turnId,since,options){
  warm(name);
  // The microphone can select the listening pose before ASR returns the command.
  const shown=log.findLast(entry=>entry.name===name && !failed.has(name) &&
   (entry.end ? entry.end>since : entry===log.at(-1) && playing===videos.get(name)));
  if(shown && !shown.turnIds.includes(turnId))shown.turnIds.push(turnId);
  director.request(name,{...options,turnId,covered:Boolean(shown)});
 }
 return {director,warm,request,close(){closed=true;clearTimeout(watchdog);for(const v of videos.values()){v.pause();v.cancelVideoFrameCallback(callback)}},canvas};
}
