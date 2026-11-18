import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from phone_context import phone_messages

class InterruptedTurn(unittest.TestCase):
    def test_only_audible_words_are_in_the_assistant_history(self):
        history=[dict(text="窗外很亮，怎么拍猫？",reply="把窗帘",interrupted=True)]
        turns=phone_messages("要拉多少？",history)
        self.assertEqual([t["content"] for t in turns if t["role"]=="assistant"],["把窗帘"])
