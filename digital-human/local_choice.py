"""A bounded local alternative when the external Jev service is disabled."""
import torch
from router import CATALOG
LABELS='ABCDEFGHIJKLMNOPQRSTUVWXYZ'
KEYS=[None,*[k for k,p in CATALOG.items() if not p.get('exact_only')]]
OPTIONS='\n'.join(f"{LABELS[i]} {CATALOG[k]['description'] if k else '其他：需要知道具体信息、记忆、解释、追问或有多个意图'}" for i,k in enumerate(KEYS))
@torch.inference_mode()
def choose(model,tok,text):
    system='你是直播弹幕分类器。从下面选择唯一能完整回答输入的类别。要求事实、建议、时间或涉及前文，一律选 A。只返回一个英文字母。\n'+OPTIONS
    prompt=tok.apply_chat_template([dict(role='system',content=system),dict(role='user',content=text)],tokenize=False,add_generation_prompt=True)
    ids=tok(prompt,return_tensors='pt').to(model.device)
    output=model(**ids,use_cache=False).logits[0,-1].float()
    labels=[tok.encode(c,add_special_tokens=False)[0] for c in LABELS[:len(KEYS)]]
    probs=output.softmax(-1)[labels];score,idx=probs.max(0)
    return (KEYS[idx.item()] if score.item()>=.88 else None,round(score.item(),4))
