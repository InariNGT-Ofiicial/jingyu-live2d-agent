import {lowerFrameToIntents} from './community-vendor/motion-intent.mjs';
import {normalizeServerMessage} from './community-vendor/maibot-protocol.mjs';

const bindings = [
  ['head.yaw','AngleX',30], ['head.pitch','AngleY',30], ['head.roll','AngleZ',30],
  ['gaze.x','ParamEyeBallX',1], ['gaze.y','ParamEyeBallY',1],
  ['torso.lean','LeanInput',20], ['torso.sway','PositionX',20],
].map(([controlId,paramId,scale])=>({controlId,paramId,scale}));
const expression = name => ({kind:'expression',name});
export function communityPlan(source, payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw Error('输入需要 JSON 对象');
  let actions, title;
  if (source==='tuner') {
    if (payload.format !== 'live2d-tuner/timeline-v1') throw Error('请选择 timeline-v1 录制文件');
    actions=[{kind:'recorded',duration:payload.duration,frames:payload.keyframes}];
    title=String(payload.name || '手调录制');
  } else if (source==='dsh') {
    const {intents,rejected}=lowerFrameToIntents(payload,bindings);
    if (rejected.length || !intents.length) throw Error('无法绑定 DSH 控制项：'+JSON.stringify(rejected));
    actions=[{kind:'pose',values:Object.assign({},...intents.map(i=>i.params))}];
    title='DSH 语义姿态';
  } else if (source==='maibot') {
    const e=normalizeServerMessage(payload);
    const emotions={happy:{kind:'smile'},shy:expression('脸红'),sad:expression('流泪')};
    if(e?.kind==='emotion' && !e.controls && Object.hasOwn(emotions,e.emotion)) actions=[emotions[e.emotion]];
    else if(e?.kind==='thinking') actions=[{kind:'tilt',direction:'left'}];
    else if(e?.kind==='animation' && !e.loop && ['nod','blink','smile'].includes(e.name)) actions=[{kind:e.name}];
    else throw Error('此 MaiBot 消息尚未绑定一次性动作：'+payload.type);
    title='MaiBot · '+(e.emotion || e.name || e.kind);
  } else throw Error('未知社区来源');
  return {version:1,title,intent:title,actions};
}
