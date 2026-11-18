import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from router import select,CATALOG,normal
from decision import control,behavior

class Decisions(unittest.TestCase):
    def test_explicit_actions_and_modes(self):
        cases={'DeepseekChan，挥挥手！':'wave','点点头':'nod','笑一个':'smile','做个思考表情':'think',
               '认真听我说':'listen','安静陪我一会儿':'quiet','继续聊吧':'resume'}
        for text,intent in cases.items():
            with self.subTest(text=text):self.assertEqual(control(text),intent)
        self.assertEqual(behavior('quiet')['mode'],'quiet')
        self.assertEqual(behavior('resume')['mode'],'chat')

    def test_questions_are_not_swallowed_by_presets(self):
        for text in ['谢谢，但为什么会下雨？','你好，我的鞋湿了怎么办？','挥手是什么意思？',
                     '不要挥手，帮我想想晚饭吃什么','你能一边笑一边解释这道题吗',
                     '安静陪我一会儿，然后告诉我怎么煮面','刚才说到哪儿了','继续聊吧，刚才第二种是什么',
                     '你看到我的钥匙了吗','如果给小猫起名字，你会叫它什么？']:
            with self.subTest(text=text):
                self.assertIsNone(control(text))
                self.assertIsNone(select(text,[],False)[0])

    def test_aliases_are_unambiguous(self):
        seen={}
        for key,preset in CATALOG.items():
            for alias in preset['aliases']:
                value=normal(alias)
                self.assertIn(seen.get(value,key),[key])
                seen[value]=key

    def test_clarify_a_reference_only_without_a_prior_answer(self):
        text='刚才那个办法有什么缺点？'
        self.assertEqual(control(text,[]),'clarify_reference')
        greeting=[dict(text='你好',reply='你好呀。',kind='preset')]
        self.assertEqual(control(text,greeting),'clarify_reference')
        self.assertIsNone(control(text,greeting+[dict(text='午饭怎么做',reply='试试鸡蛋面。',kind='answer')]))
        self.assertIsNone(control('我说的办法是随身带把伞，有什么缺点？',[]))

if __name__=='__main__':unittest.main()
