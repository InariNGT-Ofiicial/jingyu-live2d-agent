"""Build the same grounded conversation for both telephone answer engines."""
import re
from settings import NAME

PHONE_ROLE = (
    '你是和朋友通电话的DeepseekChan。追问沿用对方前面说的目的和条件，以最新纠正为准。'
    '用自然的口语直接回答。简单问题简短回答；需要解释或建议时把原因、做法讲完整。不要复述问题，不用开场白。'
)
EXPAND=re.compile(r'详细|具体(?:怎么|如何|讲|说)|展开|举例|解释|比较|对比|区别|分别|利弊|优缺点|原理|方案|攻略|有哪些|步骤|讲.{0,5}故事|讲讲|说说|为什么|怎么(?:安排|准备|规划|做)|如何|从头|多说|接着讲|然后呢|还有呢|怎么办|注意什么')
BRIEF=re.compile(r'简单说|简短|一句话|长话短说|直接告诉我.{0,3}(?:是|选|答案)')
RECALL_DETAIL=re.compile(r'最终|最后.{0,8}(?:哪|什么|几)|还记得|刚才.{0,8}(?:哪|什么|几)|几点|什么颜色|叫什么名字')


def needs_brief(text):
    return bool(BRIEF.search(text) or (RECALL_DETAIL.search(text) and not EXPAND.search(text)))


def needs_detail(text):
    return bool(EXPAND.search(text) and not BRIEF.search(text))
NEW_TOPIC=re.compile(r'换个话题|另一个话题|先不(?:说|聊)|不聊这个了|说点别的')
CORRECTION=re.compile(r'改(?:到|为|成|叫|在)|换(?:成|到|为)|更正|纠正一下|我(?:刚才)?说错了|不是.{1,24}[，,]?是')
FOLLOWUP=re.compile(r'刚才|最终|最后|还记得|后来|说好|到底|^那|^所以|^还是|^然后|^我(?:几|该|要|应该|得)')


def phone_messages(text, history):
    instruction=PHONE_ROLE
    if needs_brief(text):
        instruction=('你是和朋友通电话的DeepseekChan。追问沿用对方前面说的目的和条件，以最新纠正为准。'
                     '用一句自然的短句直接回答，给出具体信息或选择，约十到十五个汉字。不要复述问题，不用开场白。')
    elif needs_detail(text):
        instruction+='这次对方需要展开。先用短句回应核心问题，再用三到五句讲清具体原因、步骤或例子。每句适合直接说出口。'
    turns = [{'role': 'system', 'content': instruction.replace('DeepseekChan',NAME)}]
    topic=[]
    for item in history:
        if NEW_TOPIC.search(item['text']):
            topic.clear()
        topic.append(item)
    if NEW_TOPIC.search(text):
        topic=[]
    recent = topic[-10:]
    if len(topic)>10:
        recent=[topic[0],*recent]
    if FOLLOWUP.search(text) and not CORRECTION.search(text):
        updates=[]
        for item in topic:
            line=item['text'].strip()
            if CORRECTION.search(line) and not re.search(r'[？?]|好不好|要不要|能不能|怎么样|吗[。！]?$',line):
                updates.append(line[:100])
        if updates:
            text='我之前更正过：“'+'；'.join(updates[-2:])+'”。'+text
    for item in recent:
        question = item['text']
        reply = item.get('reply', '')
        if turns[-1]['role'] == 'user':
            turns[-1]['content'] += '\n' + question
        else:
            turns.append({'role': 'user', 'content': question})
        if reply:
            turns.append({'role': 'assistant', 'content': reply})
    if turns[-1]['role'] == 'user':
        turns[-1]['content'] += '\n' + text
    else:
        turns.append({'role': 'user', 'content': text})
    return turns


def complete_reply(text,exhausted):
    if exhausted and not re.search(r'[。！？!?][”’」]?$',text):
        ending=list(re.finditer(r'[。！？!?][”’」]?',text))
        if ending:return text[:ending[-1].end()]
    return text


def speech_parts(text):
    """Split at speech boundaries without discarding any of the answer."""
    clauses=re.findall(r'[^，、,。！？!?；;\n]+[，、,。！？!?；;\n]*|[，、,。！？!?；;\n]+',text)
    parts=[];pending=''
    for clause in clauses:
        if pending and len(pending)+len(clause)>55:
            parts.append(pending);pending=''
        pending+=clause
        while len(pending)>140:
            parts.append(pending[:140]);pending=pending[140:]
        if len(pending)>= (12 if not parts else 26) or (len(pending)>=6 and pending[-1] in '。！？!?；;\n'):
            parts.append(pending);pending=''
    if pending:
        if parts and len(pending)<7 and len(parts[-1])+len(pending)<=55:parts[-1]+=pending
        else:parts.append(pending)
    return parts
