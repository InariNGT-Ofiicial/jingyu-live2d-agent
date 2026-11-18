"""Local action preview using the same player, policy and clips as a call."""
import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from settings import LOCAL, ROOT

HTML = """<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>鲸语 · 动作预览</title><style>*{box-sizing:border-box}body{margin:0;background:#0e1925;color:#edf2f5;font:18px system-ui;display:flex;justify-content:center;align-items:center;min-height:100vh;gap:4vw}#figure{position:relative;overflow:hidden;width:min(45vw,44vh);aspect-ratio:9/16;background:#193043}canvas,video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}.motionSurface{opacity:0}.motionSurface.current{opacity:1}main{max-width:45vw}button{margin:5px;padding:10px 14px;border:0;border-radius:5px;cursor:pointer}h1{font-size:clamp(20px,4vw,44px)}#msg{color:#a5d6d5}</style>
<div id="figure"></div><main><h1>角色动作预览</h1><p>点选动作，当前片段结束后切换。</p><div id="buttons"></div><p id="msg" role="status"></p></main>
<script type="module">
import {createMotionPlayer} from '/motions/phone/motion-player.js';
const el=id=>document.getElementById(id), msg=s=>el('msg').textContent=s;
const player=await createMotionPlayer(el('figure'),true,msg);
const p=await(await fetch('/motions/phone/motion-policy.json')).json();let id=0;
for(const [key,clip] of Object.entries(p.clips)){const b=document.createElement('button');b.textContent=clip.label;b.onclick=()=>{player.request(key,++id,performance.now(),{explicit:true,priority:5});msg('已选择：'+clip.label)};el('buttons').append(b)}
</script></html>"""

class Preview(SimpleHTTPRequestHandler):
    def do_GET(self):
        url=urlsplit(self.path).path
        if url=="/":
            data=HTML.encode();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data);return
        if url not in self.server.files:
            self.send_error(404);return
        super().do_GET()
    def translate_path(self,path):
        return str(self.server.files.get(urlsplit(path).path,ROOT/"__missing__"))

def files():
    result={"/motions/phone/"+p.name:p for p in (ROOT/"web").iterdir() if p.suffix in (".js",".json")}
    base=LOCAL/"assets"
    result.update({"/motions/"+p.relative_to(base).as_posix():p for p in base.rglob("*") if p.suffix in (".mp4",".webp")})
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--port",type=int,default=18980);args=p.parse_args()
    assets=files()
    policy=json.loads((ROOT/"web/motion-policy.json").read_text(encoding="utf8"))
    if not all("/motions/"+c["file"] in assets for c in policy["clips"].values()):raise SystemExit("请先执行 python avatar.py --demo，或使用 --clips 导入自己的九段动作。")
    server=ThreadingHTTPServer(("127.0.0.1",args.port),Preview);server.files=assets
    print(f"http://127.0.0.1:{args.port}/",flush=True);server.serve_forever()
