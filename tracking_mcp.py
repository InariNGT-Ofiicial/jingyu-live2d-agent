"""Local stdio MCP for bounded VTS tracking experiments."""
import contextlib
import math
import os
import sys
import time
from pathlib import Path

saved = Path(__file__).resolve().parent / ".local/model-path.txt"
if saved.is_file():
    os.environ.setdefault("L2D_MODEL_DIR", saved.read_text(encoding="utf-8").strip())
from compiler import compile_plan
from model_profile import MODEL_ROOT, PRIMARY, read_json
from vts_client import VTS
from vts_adapter import export_calibration

face = {"FaceAngleX", "FaceAngleY", "FaceAngleZ", "EyeOpenLeft", "EyeOpenRight",
        "EyeRightX", "EyeRightY", "EyeLeftX", "EyeLeftY", "MouthOpen", "MouthSmile"}

@contextlib.contextmanager
def connection():
    v = VTS()
    try:
        with contextlib.redirect_stdout(sys.stderr):
            v.authenticate()
        yield v
    finally:
        v.close()

def current_inputs(v):
    data = v.call("InputParameterListRequest")
    return {p["name"]:p for p in data["defaultParameters"] if p["name"] in face}

def tracking_inputs() -> dict:
    """Read current effective face inputs, ranges, and tracker detection."""
    with connection() as v:
        return {"found":v.call("FaceFoundRequest")["found"],"inputs":current_inputs(v)}

def compile_tracking(plan: dict, fps: int = 15) -> dict:
    """Compile a Jingyu plan to VTS input frames using the author's inverse mappings."""
    return export_calibration(plan, fps)

def capture_plan(seconds: float = 2) -> dict:
    """Sample effective face inputs and their author-mapped Live2D outputs at up to 10 Hz."""
    if not .3 <= seconds <= 10:
        raise ValueError("seconds must be 0.3..10")
    config=read_json(MODEL_ROOT/"大肥鱼.vtube.json")
    channels={m["OutputLive2D"] for m in config["ParameterSettings"]
              if m["Input"] in face and m["OutputLive2D"] in PRIMARY}
    frames=[]; inputs=[]
    with connection() as v:
        v.require_model(config["ModelID"])
        start=time.monotonic()
        while True:
            t=round(min(seconds,time.monotonic()-start),4)
            current=current_inputs(v)
            values=v.call("Live2DParameterListRequest")
            if values.get("modelID") != config["ModelID"]:
                raise RuntimeError("model changed during capture")
            frame={p["name"]:p["value"] for p in values["parameters"] if p["name"] in channels}
            frames.append({"t":t,"v":frame})
            inputs.append({"t":t,"found":v.call("FaceFoundRequest")["found"],
                           "v":{k:p["value"] for k,p in current.items()}})
            if t>=seconds:break
            time.sleep(min(.1,seconds-t))
    plan={"version":1,"title":"VTS 面捕采样","actions":[{"kind":"recorded","duration":seconds,"frames":frames}]}
    compiled=compile_plan(plan)
    return {"plan":plan,"inputs":inputs,"tracks":len(compiled["tracks"])}

def inject_face(channel: str, value: float, seconds: float = 1) -> dict:
    """Temporarily override one face input, read its effective value, then relinquish it."""
    if channel not in face or not .2<=seconds<=3 or not math.isfinite(value):
        raise ValueError("unsupported input, value or duration")
    with connection() as v:
        p=current_inputs(v)[channel]
        if not p["min"]<=value<=p["max"]:raise ValueError("value outside VTS range")
        def send(weight):
            data={"mode":"set","parameterValues":[{"id":channel,"value":value,"weight":weight}]}
            if weight: data["faceFound"]=True
            v.call("InjectParameterDataRequest",data)
        try:
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                send(1);time.sleep(.05)
            during=v.call("ParameterValueRequest",{"name":channel})["value"]
        finally:
            send(0)
        time.sleep(1.1)
        after=v.call("ParameterValueRequest",{"name":channel})["value"]
        return {"channel":channel,"before":p["value"],"requested":value,"during":during,"after":after}

if __name__=="__main__":
    from mcp.server.fastmcp import FastMCP
    mcp=FastMCP("jingyu-tracking")
    for tool in (tracking_inputs,capture_plan,inject_face,compile_tracking):
        mcp.tool()(tool)
    mcp.run(transport="stdio")
