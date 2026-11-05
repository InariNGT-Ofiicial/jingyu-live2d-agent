"""Incremental semantic segmentation shared by the local voice bridge and tests."""
import re


class Segments:
    def __init__(self):
        self.pending = ''

    def feed(self, text, done=False):
        self.pending += text
        output = []
        while self.pending:
            # Keep a natural phrase together; don't split decimal points or Latin words.
            ends = [m.end() for m in re.finditer(r'[。！？!?；;\n]|\.(?=\s|$)', self.pending)]
            cut = next((i for i in ends if 24 <= i <= 80), None)
            if cut is None and len(self.pending) >= 80:
                cuts = [m.end() for m in re.finditer(r'[，,、\s。！？!?；;]', self.pending[:80])]
                cut = next((i for i in reversed(cuts) if i >= 24), 80)
            if cut is None:
                if not done:
                    break
                cut = len(self.pending)
            part, self.pending = self.pending[:cut].strip(), self.pending[cut:]
            if part:
                output.append(part)
        return output
