"""Deterministic phone controls; broad semantic input stays with the answering model."""
from router import CATALOG,normal,addressed_match
CONTROL={normal(alias):item['id'] for item in CATALOG.values() if item.get('exact_only') for alias in item['aliases']}
def control(text,history=None):
    n=normal(text)
    direct=addressed_match(CONTROL,text)
    if direct:return direct
    if history is not None and n in CATALOG['clarify_reference']['without_context']:
        if not any(turn.get('kind','answer')=='answer' for turn in history):
            return 'clarify_reference'
    return None
def behavior(intent):
    p=CATALOG.get(intent,{})
    gesture={'nod':'acknowledge','read':'read-request','greet':'wave','smile':'smile',
             'listen':'listen','think':'think','wave':'wave'}.get(p.get('action'))
    return {'gesture':gesture,'explicit':bool(p.get('exact_only')),'mode':p.get('mode')}
