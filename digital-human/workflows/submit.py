"""Submit a reviewed ComfyUI API graph to the user's local ComfyUI."""
import argparse, json
from pathlib import Path
from urllib.request import Request, urlopen

p=argparse.ArgumentParser();p.add_argument("graph",type=Path);p.add_argument("--url",default="http://127.0.0.1:8188")
a=p.parse_args();graph=json.loads(a.graph.read_text(encoding="utf8"))
with urlopen(a.url.rstrip("/")+"/object_info",timeout=15) as r:classes=json.load(r)
missing=sorted({n["class_type"] for n in graph.values()}-classes.keys())
if missing:raise SystemExit("当前 ComfyUI 缺少节点："+"，".join(missing))
req=Request(a.url.rstrip("/")+"/prompt",data=json.dumps({"prompt":graph}).encode(),headers={"Content-Type":"application/json"})
with urlopen(req,timeout=30) as r:print(json.load(r)["prompt_id"])
