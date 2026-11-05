// Deterministic speech gestures follow consumed audio, never network arrival time.
export function speechEmotion(text,requested='auto'){
 if(requested!=='auto')return requested;
 if(/害羞|不好意思|逗我|逗笑/.test(text))return 'shy';
 if(/抱歉|注意|重要|认真/.test(text))return 'serious';
 if(/[?？]|为什么|怎么|想知道/.test(text))return 'curious';
 if(/开心|欢迎|太好了|谢谢|恭喜/.test(text))return 'happy';
 if(/休息|晚安|慢慢|陪你|没关系/.test(text))return 'gentle';
 return 'neutral';
}
export function speechPose(styles,{text='',time=0,segmentTime=time,segmentIndex=0,performance={},duration=null}){
 if(performance.motion===false)return null;
 const emotion=speechEmotion(text,performance.emotion||'auto'),s=styles[emotion]||styles.neutral;
 const strength=performance.intensity??.65;
 const enter=Math.min(1,Math.max(0,time)/.35),leave=duration==null?1:Math.min(1,Math.max(0,duration-time)/.4);
 const w=strength*enter*leave,t=Math.max(0,segmentTime),side=segmentIndex%2?-1:1;
 // One soft emphasis per phrase, then relaxed shifts; no repeated pointing hand.
 const nod=t<1.4?Math.sin(t/1.4*Math.PI)*5:Math.sin(t*1.6)*1.2;
 const aside=emotion==='shy'&&t<1.2?Math.sin(t/1.2*Math.PI):0;
 return {emotion,values:{
  AngleX:w*(side*6*Math.sin(t*.65)-aside*7),AngleY:w*(-nod-aside*3),
  AngleZ:w*(s.tilt+side*2*Math.sin(t*.9)),PositionX:w*side*4*Math.sin(t*.5),
  PositionZ:w*side*2*Math.sin(t*.5-.2),LeanInput:w*s.lean,
  ParamEyeBallX:-w*aside*.4,ParamEyeBallY:-w*aside*.3,
  ParamMouthForm:w*s.smile,key7:w*s.blush
 }};
}
