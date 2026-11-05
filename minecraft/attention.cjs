// Minecraft yaw 0 faces -Z. Project a world target into the first-person viewport.
function project(target,eye,yaw,pitch,{fov=75,aspect=16/9}={}){
 const d={x:target.x-eye.x,y:target.y-eye.y,z:target.z-eye.z};
 const sy=Math.sin(yaw),cy=Math.cos(yaw),sp=Math.sin(pitch),cp=Math.cos(pitch);
 const right=d.x*cy-d.z*sy,up=d.x*sy*sp+d.y*cp+d.z*cy*sp;
 const depth=-d.x*sy*cp+d.y*sp-d.z*cy*cp,tan=Math.tan(fov*Math.PI/360);
 if(depth<=.05)return {visible:false,x:right>=0?1:0,y:.5,depth};
 const x=.5+right/(depth*tan*aspect)*.5,y=.5-up/(depth*tan)*.5;
 return {x:Math.max(0,Math.min(1,x)),y:Math.max(0,Math.min(1,y)),visible:x>=0&&x<=1&&y>=0&&y<=1,depth};
}
module.exports={project};
