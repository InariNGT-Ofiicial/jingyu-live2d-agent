import json
import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError
from planner import Planner, PlannerError, endpoint, parse_plan, output_text

PLAN={'version':1,'title':'回应','actions':[{'kind':'nod','at':0,'duration':2.5,'count':1,'strength':.4}]}

class Response(BytesIO):
    def __enter__(self): return self
    def __exit__(self,*args): self.close()

class PlannerTests(unittest.TestCase):
    def configured(self, protocol='chat_completions'):
        p=Planner();p.configure({'provider':'openai','model':'any-vendor/custom-model-2026','apiKey':'test-secret','baseUrl':'http://127.0.0.1:61955/v1','protocol':protocol})
        return p

    def test_normalize_base_and_full_endpoints(self):
        for base in ['https://example.com/v1/','https://example.com/v1/chat/completions','https://example.com/v1/responses']:
            self.assertEqual(endpoint(base,'chat_completions'),'https://example.com/v1/chat/completions')
            self.assertEqual(endpoint(base,'responses'),'https://example.com/v1/responses')

    def test_reject_invalid_or_credential_bearing_endpoint(self):
        for x in ['file:///x','https://user:key@example.com/v1','https://example.com/v1?key=x','https://example.com/#x','http://example.com/v1']:
            with self.subTest(x=x),self.assertRaises(PlannerError): endpoint(x,'responses')

    def test_no_model_whitelist_and_redact_config(self):
        p=self.configured();r=p.public();self.assertEqual(r['model'],'any-vendor/custom-model-2026');self.assertTrue(r['hasApiKey']);self.assertNotIn('test-secret',json.dumps(r));self.assertNotIn('apiKey',r)

    def test_minimal_chat_payload_and_unicode(self):
        p=self.configured();seen=[]
        class Opener:
            def open(self,req,timeout):
                seen.append(req);return Response(json.dumps({'choices':[{'message':{'content':json.dumps(PLAN)}}]}).encode())
        with patch('planner.build_opener',return_value=Opener()): r=p.plan('微笑着点头')
        payload=json.loads(seen[0].data);self.assertEqual(payload['model'],'any-vendor/custom-model-2026');self.assertEqual(payload['messages'][-1]['content'],'微笑着点头');self.assertNotIn('temperature',payload);self.assertNotIn('max_tokens',payload);self.assertNotIn('response_format',payload);self.assertEqual(seen[0].get_header('Authorization'),'Bearer test-secret');self.assertEqual(r['planner']['attempts'],1)

    def test_responses_payload_and_output_parts(self):
        p=self.configured('responses');seen=[]
        class Opener:
            def open(self,req,timeout):
                seen.append(req);return Response(json.dumps({'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(PLAN)}]}]}).encode())
        with patch('planner.build_opener',return_value=Opener()): r=p.plan('点头')
        payload=json.loads(seen[0].data);self.assertIn('input',payload);self.assertNotIn('messages',payload);self.assertFalse(payload['store']);self.assertTrue(seen[0].full_url.endswith('/responses'));self.assertEqual(r['plan'],PLAN)

    def test_optional_json_mode_only_when_selected(self):
        p=self.configured();p.configure({'jsonMode':True});seen=[]
        class Opener:
            def open(self,req,timeout):seen.append(json.loads(req.data));return Response(json.dumps({'choices':[{'message':{'content':json.dumps(PLAN)}}]}).encode())
        with patch('planner.build_opener',return_value=Opener()):p.plan('点头')
        self.assertEqual(seen[0]['response_format'],{'type':'json_object'})

    def test_http_error_does_not_echo_provider_secrets(self):
        p=self.configured()
        with patch('planner.build_opener') as b:
            b.return_value.open.side_effect=HTTPError('https://example.com',401,'unauthorized',{},BytesIO(b'test-secret'))
            with self.assertRaises(PlannerError) as e:p.plan('点头')
        self.assertIn('401',str(e.exception));self.assertNotIn('test-secret',str(e.exception))

    def test_one_repair_after_semantic_compile_failure(self):
        p=self.configured();bad={**PLAN,'actions':[{'kind':'walk','at':0,'duration':3}]}
        with patch.object(p,'chat',side_effect=[json.dumps(bad),json.dumps(PLAN)]) as c:r=p.plan('点头')
        self.assertEqual(r['planner']['attempts'],2);self.assertEqual(c.call_count,2);self.assertIn('本地校验未通过',c.call_args[0][0][-1]['content'])

    def test_repeated_invalid_plan_never_executes(self):
        p=self.configured()
        with patch.object(p,'chat',return_value='{"version":1,"actions":[{"kind":"run"}]}') as c:
            with self.assertRaises(PlannerError):p.plan('跑步')
        self.assertEqual(c.call_count,2)

    def test_explicit_unsupported_returns_reason_once(self):
        p=self.configured()
        with patch.object(p,'chat',return_value='{"unsupported":true,"reason":"当前模型不能自由走路"}') as c:
            with self.assertRaisesRegex(PlannerError,'不能自由走路'):p.plan('走路')
        self.assertEqual(c.call_count,1)

    def test_fenced_json_and_plan_wrapper(self):
        self.assertEqual(parse_plan('```json\n'+json.dumps({'plan':PLAN})+'\n```'),PLAN)
        for text in ['解释后 {"version":1}','[]','{"version":NaN}']:
            with self.assertRaises(PlannerError):parse_plan(text)

    def test_truncation_and_refusal_not_parsed_as_plan(self):
        for obj in [{'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}, {'choices':[{'message':{'refusal':'denied'}}]}]:
            with self.assertRaises(PlannerError):output_text(obj,'chat_completions')
        with self.assertRaises(PlannerError):output_text({'status':'incomplete'},'responses')

    def test_dsh_keeps_credentials_in_own_launcher(self):
        p=Planner();p.dsh_command='dsh';p.configure({'provider':'dsh'})
        class Result:returncode=0;stdout='[llm-deepseek-account] model listing loaded\n'+json.dumps(PLAN);stderr=''
        with patch('planner.subprocess.run',return_value=Result()) as run:r=p.plan('点头')
        args=run.call_args[0][0];self.assertIn('--patch',args);self.assertIn('--profile',args);self.assertNotIn('apiKey',str(run.call_args));self.assertEqual(r['planner']['provider'],'dsh')

if __name__=='__main__':unittest.main()
