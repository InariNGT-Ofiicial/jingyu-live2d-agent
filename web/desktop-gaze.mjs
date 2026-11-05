// Electron supplies device-independent desktop coordinates, including negative monitor origins.
const clamp=x=>Math.max(-1,Math.min(1,x));
export function desktopGaze(point,model){
 const headX=point.window.x+model.x+model.width*.5;
 const headY=point.window.y+model.y+model.height*.16;
 return {x:clamp((point.x-headX)/Math.max(1,model.width,point.desktop.width*.28)),
  y:clamp((headY-point.y)/Math.max(1,model.height*.65,point.desktop.height*.4))};
}
export function bindDesktopGaze({native,engine,geometry,enabled}){
 return native.onPointer(point=>{
  if(!enabled()){engine.gaze=null;return;}
  const model=geometry();
  if(model.width>0&&model.height>0)engine.gaze=desktopGaze(point,model);
 });
}
