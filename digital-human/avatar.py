"""Build the example robot locally or import a creator's nine portrait clips."""
import argparse,json,math,os,shutil,subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from PIL import Image,ImageDraw
from settings import LOCAL,ROOT

FF=os.environ.get("FFMPEG","ffmpeg")
POLICY=json.loads((ROOT/"web/motion-policy.json").read_text(encoding="utf8"))
def demo(name,dest):
    size=(270,480)
    cmd=[FF,"-v","error","-y","-f","rawvideo","-pixel_format","rgb24","-video_size","270x480","-framerate","24","-i","-","-c:v","libx264","-pix_fmt","yuv420p",str(dest)]
    pipe=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    try:
        for i in range(73):
            phase=i/72;w=math.sin(math.pi*phase)**2;dy=round(w*(10 if name in ("acknowledge","read-request") else 3))
            im=Image.new("RGB",size,"#172c40");d=ImageDraw.Draw(im)
            d.ellipse((25,355,245,405),fill="#122739");d.rounded_rectangle((65,263,205,380),30,fill="#65859d")
            x=round(5*w) if name=="think" else 0
            d.rounded_rectangle((42+x,112+dy,228+x,281+dy),44,fill="#b3d3db")
            d.rounded_rectangle((58+x,142+dy,212+x,238+dy),28,fill="#223c50")
            for eye in (94,173):
                h=round(11*(1-w)) if name=="smile" else 9
                d.rounded_rectangle((eye-7+x,184+dy-h,eye+7+x,184+dy+h),5,fill="#9fe4e0")
            left=round(w*82) if name in ("wave","listen","think") else round(6*w)
            d.line((73,303,43,328-left),fill="#8ab2c0",width=18);d.ellipse((32,314-left,54,336-left),fill="#c6e8e9")
            d.line((195,303,224,324-round(w*13)),fill="#8ab2c0",width=18);d.ellipse((213,314-round(w*13),235,336-round(w*13)),fill="#c6e8e9")
            pipe.stdin.write(im.tobytes())
    finally:
        pipe.stdin.close()
        if pipe.wait():raise RuntimeError("FFmpeg 无法生成示例动作")
def run(*args):subprocess.run([FF,"-v","error","-y",*map(str,args)],check=True)
def main():
    p=argparse.ArgumentParser();mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--demo",action="store_true");mode.add_argument("--clips",type=Path)
    p.add_argument("--poster",type=Path);a=p.parse_args()
    if not shutil.which(FF):raise SystemExit("请安装 FFmpeg 并加入 PATH，或设置 FFMPEG 环境变量。")
    if a.clips:
        missing=[n for n in POLICY["clips"] if not (a.clips/(n+".mp4")).is_file()]
        if missing:raise SystemExit("缺少动作："+"、".join(missing))
    LOCAL.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(dir=LOCAL) as tmp:
        base=Path(tmp);mobile=base/POLICY["mobileDirectory"];mobile.mkdir()
        for name,entry in POLICY["clips"].items():
            dst=base/entry["file"];dst.parent.mkdir(parents=True,exist_ok=True)
            if a.demo:demo(name,dst)
            else:run("-i",a.clips/(name+".mp4"),"-an","-vf","fps=24,scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1","-c:v","libx264","-crf","19","-pix_fmt","yuv420p","-movflags","+faststart",dst)
            slim=mobile/(name+".mp4")
            if a.demo:shutil.copyfile(dst,slim)
            else:run("-i",dst,"-an","-c:v","libx264","-crf","25","-pix_fmt","yuv420p","-movflags","+faststart",slim)
            if name in ("front-breathe","h3-shoulders"):
                run("-i",slim,"-an","-c:v","libx264","-crf","32","-movflags","+faststart",mobile/(name+"-start.mp4"))
        poster=base/"phone-delivery-v2/anchor.webp"
        if a.poster:
            from PIL import ImageOps
            with Image.open(a.poster) as im:ImageOps.fit(im.convert("RGB"),(720,1280)).save(poster,quality=94)
        else:run("-i",base/POLICY["clips"]["front-breathe"]["file"],"-frames:v","1",poster)
        for file in base.rglob("*"):
            if file.is_file():
                out=LOCAL/"assets"/file.relative_to(base);out.parent.mkdir(parents=True,exist_ok=True);os.replace(file,out)
    print("九段动作已就绪。运行 python preview.py。")
if __name__=="__main__":main()
