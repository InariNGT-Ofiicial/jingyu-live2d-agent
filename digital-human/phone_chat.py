"""Greedy Qwen2 phone replies with a reusable single-token replay graph."""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, StaticCache
from phone_context import complete_reply,needs_brief,needs_detail,phone_messages


class PhoneChat:
    def __init__(self,path):
        self.tok=AutoTokenizer.from_pretrained(path)
        self.lm=AutoModelForCausalLM.from_pretrained(path,torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval()
        self.capacity=1024
        self.cache=StaticCache(config=self.lm.config,max_batch_size=1,max_cache_len=self.capacity,device='cuda',dtype=torch.bfloat16)
        self.pos=torch.zeros(1,device='cuda',dtype=torch.long)
        self.token=torch.zeros((1,1),device='cuda',dtype=torch.long)
        self.slots=torch.arange(self.capacity,device='cuda')
        self.graph=None

    def step(self,ids,pos,mask):
        y=self.lm.model(input_ids=ids,position_ids=pos.view(1,-1),cache_position=pos,
                        attention_mask=mask,past_key_values=self.cache,use_cache=True)
        return self.lm.lm_head(y.last_hidden_state[:,-1]).argmax(-1)

    @torch.inference_mode()
    def answer(self,text,history):
        turns=phone_messages(text,history)
        prompt=self.tok.apply_chat_template(turns,tokenize=False,add_generation_prompt=True)
        ids=self.tok(prompt,return_tensors='pt').input_ids.to('cuda')
        brief=needs_brief(text)
        limit=60 if brief else (256 if needs_detail(text) else 160)
        if ids.size(1)+limit>=self.capacity:
            out=self.lm.generate(ids,max_new_tokens=limit,do_sample=False,pad_token_id=self.tok.eos_token_id)
            tokens=out[0,ids.size(1):]
            return complete_reply(self.tok.decode(tokens,skip_special_tokens=True).strip(),len(tokens)==limit)
        self.cache.reset()
        n=ids.size(1);p=torch.arange(n,device='cuda')
        mask=torch.where(self.slots[None,:]<=p[:,None],0.,-65504.).bfloat16()[None,None,:,:]
        token=self.step(ids,p,mask);result=[]
        for i in range(limit):
            t=token.item()
            if t in [self.tok.eos_token_id,151643]:break
            result.append(t)
            if brief and self.tok.decode([t]).rstrip().endswith(('。','！','？','!','?')):break
            self.pos.fill_(n+i);self.token.copy_(token)
            if self.graph is None:
                self.step(self.token,self.pos,torch.where(self.slots<=self.pos,0.,-65504.).bfloat16().view(1,1,1,-1))
                self.graph=torch.cuda.CUDAGraph()
                with torch.cuda.graph(self.graph):
                    mask=torch.where(self.slots<=self.pos,0.,-65504.).bfloat16().view(1,1,1,-1)
                    self.next=self.step(self.token,self.pos,mask)
            self.graph.replay()
            token=self.next
        return complete_reply(self.tok.decode(result,skip_special_tokens=True).strip(),len(result)==limit)
