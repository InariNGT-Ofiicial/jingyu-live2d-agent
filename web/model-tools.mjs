// Adapted concepts from DSH-L2D 1ab1f84 (MIT): model adapter and hard/soft bounds.
export function windowFor(p){
 if(!p||![p.min,p.max,p.default].every(Number.isFinite)||p.min>p.max||p.default<p.min||p.default>p.max)throw Error('缺少有效模型范围或默认值');
 return [p.min,p.max];
}
export function checkValue(p,value,soft=null,strict=false){
 const [min,max]=windowFor(p);
 if(!Number.isFinite(value)||value<min||value>max)throw Error(`${p.id} 超出真实范围 ${min}..${max}`);
 if(soft&&(!Array.isArray(soft)||soft.length!==2||!soft.every(Number.isFinite)||soft[0]>soft[1]||soft[0]<min||soft[1]>max))throw Error('推荐范围必须位于真实范围之内');
 const exceeded=!!soft&&(value<soft[0]||value>soft[1]);
 return {value:exceeded&&strict?Math.max(soft[0],Math.min(soft[1],value)):value,softExceeded:exceeded};
}
export function normalizedValue(p,value){
 windowFor(p);if(!Number.isFinite(value)||Math.abs(value)>1)throw Error('归一化值必须为 -1..1');
 return value<0?p.default+value*(p.default-p.min):p.default+value*(p.max-p.default);
}
export function parameterDiff(before,after){
 const a=new Map(before.map(p=>[p.id,p])),b=new Map(after.map(p=>[p.id,p]));
 return {added:[...b.keys()].filter(id=>!a.has(id)),removed:[...a.keys()].filter(id=>!b.has(id)),
  changed:[...b].filter(([id,p])=>a.has(id)&&['min','max','default'].some(k=>a.get(id)[k]!==p[k])).map(([id])=>id)};
}
export function bindFrame(frame,mapping,parameters){
 if(!frame?.controls||!Array.isArray(mapping)||!mapping.length)throw Error('需要 frame.controls 和 mapping');
 const params=new Map(parameters.map(p=>[p.id,p])),values={},used=new Set();
 for(const [control,value]of Object.entries(frame.controls)){
  const rows=mapping.filter(m=>m.controlId===control);if(rows.length!==1)throw Error('映射缺失或重复：'+control);
  const m=rows[0],p=params.get(m.paramId);if(!p||used.has(p.id))throw Error('参数缺失或被重复绑定：'+m.paramId);
  if(!m.expected||['min','max','default'].some(k=>m.expected[k]!==p[k]))throw Error('模型范围已变化或缺少 expected：'+m.paramId);
  values[p.id]=normalizedValue(p,value);used.add(p.id);
 }
 if(!used.size)throw Error('没有可执行控制项');return values;
}
