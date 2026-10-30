"""Persistent, validated user presets. Built-in performances are kept separately."""
import json,threading,uuid
from copy import deepcopy
from datetime import datetime,timezone
from compiler import compile_plan,CompileError

class PresetStore:
    def __init__(self,path):
        self.path=path;self.lock=threading.RLock()
    def _read(self):
        if not self.path.exists():return []
        try:
            data=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data,list):raise ValueError()
            return data
        except (ValueError,OSError):raise CompileError('预设文件无法读取，未覆盖原文件')
    def _write(self,items):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(items,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
        tmp.replace(self.path)
    def list(self):
        with self.lock:return deepcopy(self._read())
    def get(self,pid):
        with self.lock:
            item=next((x for x in self._read() if x['id']==pid),None)
            if item is None:raise CompileError('预设不存在或已删除')
            return deepcopy(item)
    def save(self,name,plan):
        if not isinstance(name,str) or not 1<=len(name.strip())<=60:raise CompileError('预设名称需要 1..60 个字')
        name=name.strip();compiled=compile_plan(plan)
        with self.lock:
            items=self._read()
            if any(x['name'].casefold()==name.casefold() for x in items):raise CompileError('已有同名预设，请换一个名称')
            if len(items)>=500:raise CompileError('预设已达 500 个，请删除不再需要的预设')
            item={'id':uuid.uuid4().hex[:12],'name':name,'createdAt':datetime.now(timezone.utc).isoformat(),'duration':compiled['duration'],'plan':deepcopy(compiled['sourcePlan'])}
            items.insert(0,item);self._write(items);return deepcopy(item)
    def delete(self,pid):
        with self.lock:
            item=self.get(pid);items=[x for x in self._read() if x['id']!=pid]
            self._write(items);return {'deleted':item['id'],'name':item['name']}
