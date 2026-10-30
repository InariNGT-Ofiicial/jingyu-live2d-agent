"""Curated, explicit demonstration plans; these are not a natural-language parser."""
import json
from pathlib import Path
DEMOS = {
 'hello': {'title':'温柔打招呼','version':1,'intent':'看向我，微笑着点头两次，最后轻轻歪头。','summary':'先注视你，微笑点头，再以轻微歪头收尾。','actions':[
  {'kind':'look','direction':'center','at':0,'duration':1.3}, {'kind':'smile','at':.4,'duration':5.5,'strength':.7},
  {'kind':'nod','at':1.1,'duration':2.5,'count':2,'strength':.55}, {'kind':'tilt','at':3.7,'duration':2.3,'direction':'right','strength':.45}]},
 'curious': {'title':'好奇地打量','version':1,'intent':'先看向左边，再看向右边，然后歪头想一想。','summary':'眼神先移动，头部随后跟随，最后歪头停顿。','actions':[
  {'kind':'look','direction':'left','at':0,'duration':2.1,'strength':.7}, {'kind':'look','direction':'right','at':2.2,'duration':2.1,'strength':.65},
  {'kind':'tilt','at':4.2,'duration':2.3,'strength':.55}, {'kind':'pose','at':4.3,'duration':2.1,'values':{'BrowInnerUp':.4}}]},
 'shy': {'title':'有点害羞','version':1,'intent':'有点害羞，低头眨眼，脸微微红。','summary':'收起视线，轻轻低头，以短暂脸红和眨眼表达害羞。','actions':[
  {'kind':'look','direction':'down','at':0,'duration':4.3,'strength':.5}, {'kind':'expression','name':'脸红','at':.3,'duration':4.2,'strength':.65},
  {'kind':'blink','at':1,'duration':.8}, {'kind':'smile','at':.5,'duration':3.8,'strength':.3}, {'kind':'tilt','at':1.5,'duration':2.7,'strength':.3}]},
 'explain': {'title':'认真讲解','version':1,'intent':'抬起食指，认真解释一下，然后把手收回。','summary':'使用作者的食指动画进入，配合注视与轻微点头，最后完整收手。','actions':[
  {'kind':'gesture','name':'point','at':.3,'duration':5.5}, {'kind':'smile','at':.2,'duration':5.5,'strength':.3},
  {'kind':'nod','at':2.3,'duration':1.8,'strength':.25}, {'kind':'talk','at':1.6,'duration':2.5,'strength':.45}]},
 'no': {'title':'轻声说不','version':1,'intent':'轻轻摇头两次，带一点歉意，不要夸张。','summary':'小幅摇头、眉心略抬；留出停顿，再回到待机。','actions':[
  {'kind':'shake_head','at':.4,'duration':3.5,'count':2,'strength':.4}, {'kind':'pose','at':.2,'duration':4.3,'values':{'BrowInnerUp':.35,'ParamMouthForm':-.25}}]},
 'thanks': {'title':'诚恳地致谢','version':1,'intent':'微笑着把手放在胸前，轻轻点头致谢。','summary':'抚胸致意与温和笑容叠加，用一次缓慢点头收尾。','actions':[
  {'kind':'gesture','name':'hand_on_chest','at':.2,'duration':5.5}, {'kind':'smile','at':.1,'duration':5.7,'strength':.65},
  {'kind':'nod','at':1.7,'duration':2.5,'strength':.55}]},
}

# Authored multi-channel scenes that completed on the real browser stage.
for _key, _icon, _caption in [
    ('01-curiosity','✦','疑惑 · 思考 · 竖指讲解 / 20s'),
    ('02-vulnerable','♡','委屈 · 抚胸 · 鼓起勇气 / 20s'),
    ('03-pride','◡','得意 · 冷汗 · 害羞否认 / 20s'),
    ('04-playful','❧','拿草 · 逗趣 · 前倾致意 / 20s'),
]:
    _plan=json.loads((Path(__file__).parent/'performances'/f'{_key}.json').read_text(encoding='utf-8'))
    _plan.update(group='performance',icon=_icon,caption=_caption)
    DEMOS[_key]=_plan

for _key in ['05-weight-shift','06-finger-articulation','07-left-articulation','08-grass-articulation']:
    DEMOS[_key]=json.loads((Path(__file__).parent/'performances'/f'{_key}.json').read_text(encoding='utf-8'))

for _key in ['09-composure','10-resolution','11-mischief']:
    DEMOS[_key]=json.loads((Path(__file__).parent/'performances'/f'{_key}.json').read_text(encoding='utf-8'))

_bold=json.loads((Path(__file__).parent/'performances/12-bold-performance.json').read_text(encoding='utf-8'))
_bold['group']='expressive'
DEMOS['12-bold-performance']=_bold

DEMOS['15-flirt-layered']=json.loads((Path(__file__).parent/'performances/15-flirt-layered.json').read_text(encoding='utf-8'))
