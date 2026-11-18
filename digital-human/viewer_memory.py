import re

# Only an explicit self-introduction by the same viewer may populate this value.
intro=re.compile(r'(?:我(?:的名字是|叫)|请叫我)\s*([\u3400-\u9fffA-Za-z0-9·_-]{1,16})(?=[，。！？、,!.?\s]|$)')
recall=re.compile(r'(?:我叫什么|我的名字(?:是什么|是啥)|我.{0,8}(?:告诉|说过|说的).{0,6}名字|还记得我的名字)')
def recall_name(history,author,question):
    if not author or not recall.search(question):return None
    for turn in reversed(history):
        if turn.get('author')!=author:continue
        match=intro.search(turn['text'])
        if match and not re.search('什么|啥|谁|吗|呢',match[1]):
            return match[1]+'。'
    return None
