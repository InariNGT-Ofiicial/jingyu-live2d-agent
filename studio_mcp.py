"""MCP facade over the same studio API. No persona, memory or autonomous loop."""
from mcp.server.fastmcp import FastMCP
from studio_cli import request

mcp=FastMCP('Jingyu Studio Tools')
@mcp.tool()
def studio_state() -> dict:
    """Read online renderers and command receipts. accepted is not completed."""
    return request('/api/studio/state')
@mcp.tool()
def scene_set(scene: str='study-v2', theme: str='warm', camera: str='wide') -> dict:
    """Set the scene, warm/cool lighting and wide/close camera on connected stages."""
    return request('/api/studio/command',{'action':'set','scene':{'id':scene,'theme':theme,'camera':camera}})
@mcp.tool()
def playback_start(client_id: str, plan: dict | None=None, audio: str='silent') -> dict:
    """Play a validated version:1 plan on one renderer. greeting audio requires user audio unlock."""
    data={'action':'play','clientId':client_id,'audio':audio}
    if plan is not None:data['plan']=plan
    return request('/api/studio/command',data)
@mcp.tool()
def playback_stop(client_id: str) -> dict:
    """Cancel audio and motion together on one renderer."""
    return request('/api/studio/command',{'action':'stop','clientId':client_id})
@mcp.tool()
def speech_synthesize(text: str, instruction: str='', emotion: str='auto', intensity: float=.65) -> dict:
    """Synthesize DS voice asynchronously. Poll speech_status until ready, then speech_play."""
    return request('/api/studio/voice',{'text':text,'instruction':instruction,'performance':{'emotion':emotion,'intensity':intensity}})
@mcp.tool()
def speech_perform(text: str, client_id: str='', emotion: str='auto', intensity: float=.65, instruction: str='') -> dict:
    """Speak and perform on an audio-enabled studio. Returns an execution receipt and speech ID.
    emotion: auto/neutral/happy/gentle/curious/shy/serious. Poll studio_state for actual completion.
    """
    return request('/api/studio/speak',{'text':text,'clientId':client_id,'instruction':instruction,'performance':{'emotion':emotion,'intensity':intensity}})
@mcp.tool()
def speech_status(speech_id: str='') -> dict:
    """Read local voice availability or synthesis status."""
    from urllib.parse import urlencode
    return request('/api/studio/voice?'+urlencode({'id':speech_id}))
@mcp.tool()
def speech_stream_start(text: str='', instruction: str='', input_complete: bool=False, emotion: str='auto', intensity: float=.65) -> dict:
    """Start incremental synthesis. For audible browser playback, click Wait for Agent in the studio first,
    read speech_status().activeId and append to that session instead of starting another one."""
    return request('/api/studio/voice/start',{'text':text,'instruction':instruction,'inputComplete':input_complete,'performance':{'emotion':emotion,'intensity':intensity}})
@mcp.tool()
def speech_stream_append(speech_id: str, text: str='', done: bool=False) -> dict:
    """Feed spoken text to a live voice session; done=True flushes the last phrase and saves WAV."""
    return request('/api/studio/voice/append',{'id':speech_id,'text':text,'done':done})
@mcp.tool()
def speech_stream_cancel(speech_id: str) -> dict:
    """Cancel active synthesis and its connected stream. After synthesis is ready, use playback_stop
    to stop a browser that is still draining audio. The model segment drains before reuse."""
    return request('/api/studio/voice/cancel',{'id':speech_id})
@mcp.tool()
def speech_play(client_id: str, speech_id: str, plan: dict | None=None) -> dict:
    """Play a ready speech take with optional motion plan. Renderer audio must be unlocked."""
    data={'action':'play','clientId':client_id,'audio':'speech','speechId':speech_id}
    if plan is not None:data['plan']=plan
    return request('/api/studio/command',data)
@mcp.tool()
def danmaku_state() -> dict:
    """Read the local simulated live chat queue. Messages are test data, not real viewers."""
    return request('/api/studio/danmaku')
@mcp.tool()
def danmaku_claim() -> dict:
    """Claim the next comment only when the previous reply has finished playing. Returns recent context."""
    return request('/api/studio/danmaku/claim',{})
@mcp.tool()
def danmaku_reply(message_id: str, text: str) -> dict:
    """Reply to a claimed comment with short spoken text. The target studio plays DS voice automatically."""
    return request('/api/studio/danmaku/reply',{'id':message_id,'text':text})
@mcp.tool()
def minecraft_state() -> dict:
    """Read the local Minecraft bot, inventory, active target, projected attention and action receipts."""
    return request('/api/minecraft')
@mcp.tool()
def minecraft_action(action: str, client_id: str='', block: str='oak_log', world: str='survival', goal: str='starter', max_steps: int=160, max_minutes: float=15) -> dict:
    """Local worlds only. Actions: start, survival, survival-step, inspect, walk, dig, place, demo, stop, shutdown.
    world: survival (normal terrain, normal difficulty) / demo (flat test arena); close before switching.
    goal: starter / sustain / return-home. Survival observes, plans, acts and verifies repeatedly.
    Read survival.observation/decision/receipts/status to assess progress. Budget exhaustion pauses.
    block: oak_log/stone. Supply an audio-enabled studio client for narration. Poll minecraft_state.
    demo resets only the isolated test arena and bot inventory, then collects and places blocks.
    """
    return request('/api/minecraft',{'action':action,'clientId':client_id,'block':block,'world':world,'goal':goal,'maxSteps':max_steps,'maxMinutes':max_minutes})
@mcp.tool()
def obs_control(action: str='status', scene: str | None=None) -> dict:
    """Read OBS status, switch scene, record, or stop recording. Returns actual recording state."""
    return request('/api/studio/obs',{'action':action,'scene':scene})
if __name__=='__main__':mcp.run(transport='stdio')
