"""Fixed-size KV cache and CUDA graph for the one-token CosyVoice2 inference path."""
import torch
from transformers import StaticCache


class SpeechDecoder:
    def __init__(self, voice, capacity=1024):
        self.voice=voice
        self.net=voice.llm.model.model
        self.net.bfloat16()
        self.voice.llm_decoder.bfloat16()
        self.capacity=capacity
        self.cache=StaticCache(config=self.net.config,max_batch_size=1,max_cache_len=capacity,device='cuda',dtype=torch.bfloat16)
        self.pos=torch.zeros(1,device='cuda',dtype=torch.long)
        self.x=torch.zeros((1,1,self.net.config.hidden_size),device='cuda',dtype=torch.bfloat16)
        self.slots=torch.arange(capacity,device='cuda')
        self.graph=None
        self.original=voice.inference_wrapper

    @torch.autocast("cuda",enabled=False)
    def forward(self):
        valid=self.slots<=self.pos
        mask=torch.where(valid,0.,-65504.).bfloat16().view(1,1,1,-1)
        y=self.net(inputs_embeds=self.x,attention_mask=mask,position_ids=self.pos.view(1,1),
                   cache_position=self.pos,past_key_values=self.cache,use_cache=True,return_dict=True)
        return self.voice.llm_decoder(y.last_hidden_state[:,-1]).float().log_softmax(-1)

    @torch.autocast("cuda",enabled=False)
    def prefill(self,lm_input,pos,mask):
        y=self.net(inputs_embeds=lm_input.bfloat16(),attention_mask=mask,position_ids=pos[None,:],cache_position=pos,past_key_values=self.cache,use_cache=True,return_dict=True)
        return self.voice.llm_decoder(y.last_hidden_state[:,-1]).float().log_softmax(-1)

    @torch.inference_mode()
    def decode(self,lm_input,sampling,min_len,max_len,uuid):
        n=lm_input.size(1)
        if n+max_len>=self.capacity:
            yield from self.original(lm_input,sampling,min_len,max_len,uuid)
            return
        pos=torch.arange(n,device='cuda')
        mask=torch.where(self.slots[None,:]<=pos[:,None],0.,-65504.).bfloat16()[None,None,:,:]
        self.cache.reset()
        logits=self.prefill(lm_input,pos,mask)
        history=[]
        for i in range(max_len):
            token=self.voice.sampling_ids(logits[0],history,sampling,ignore_eos=i<min_len)
            if token in self.voice.stop_token_ids:break
            history.append(token)
            yield token
            self.x.copy_(self.voice.speech_embedding.weight[token].reshape_as(self.x))
            self.pos.fill_(n+i)
            if self.graph is None:
                self.forward()
                self.graph=torch.cuda.CUDAGraph()
                with torch.cuda.graph(self.graph):self.logits=self.forward()
            self.graph.replay()
            logits=self.logits
