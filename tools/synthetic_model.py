"""Invented test data, never a substitute for the author's model or physics.

Only names and parameter ranges already present in the public source are used.
Curves, expression values and mappings below were written for contract tests;
no files are read from a local model installation.
"""
import json


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def create_model(stage):
    model = stage / 'synthetic-model'
    inventory_path = stage / 'core-inventory.json'
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    # Separate invented channels keep test expressions independent of gestures.
    names = ['体型2', '兔牙', '加载', '屑屑眼', '流冷汗', '流泪',
             '脸红', '裙子切换', '黑框眼镜', '＞＜']
    for index, name in enumerate(names):
        pid = f'TestExpression{index}'
        inventory['parameters'].append({'id': pid, 'min': -1, 'max': 1, 'default': 0})
        write_json(model / 'Exp3' / f'{name}.exp3.json', {
            'Parameters': [{'Id': pid, 'Value': .5, 'Blend': 'Add'}]})
    inventory['parameterCount'] = len(inventory['parameters'])
    write_json(inventory_path, inventory)
    for name, pid, value in [('前倾', 'LeanInput', -30), ('竖食指开', 'Param36', 1)]:
        write_json(model / 'Exp3' / f'{name}.exp3.json', {
            'Parameters': [{'Id': pid, 'Value': value, 'Blend': 'Add'}]})
    write_json(model / '大肥鱼.cdi3.json', {'Parameters': []})
    write_json(model / '大肥鱼.physics3.json', {'PhysicsSettings': [{
        'Input': [{'Source': {'Id': 'AngleX'}}],
        'Output': [{'Destination': {'Id': pid}} for pid in
                   ['ParamAngleX', 'ParamBrowLAngle', 'ParamBrowLAngleSmoothing']]}]})
    gestures = [
        ('默认手切举手', '举手切默认手', ['Param62', 'Param59', 'Param60', 'Param61']),
        ('竖手指切出来动画', '竖手指切回默认', ['Param36', 'Param39', 'Param41', 'Param42', 'Param43']),
        ('狗尾草切换出来', '狗尾草切回默认手', ['Param36', 'Param39', 'Param41', 'Param42']),
    ]
    for enter, exit_name, ids in gestures:
        for name, start, end in [(enter, 0, .25), (exit_name, .25, 0)]:
            write_json(model / 'Animation' / f'{name}.motion3.json', {
                'Meta': {'Duration': 1.5},
                'Curves': [{'Target': 'Parameter', 'Id': pid,
                            'Segments': [0, start, 0, 1.5, end]} for pid in ids]})
    write_json(model / 'Animation' / 'IDLE.motion3.json', {
        'Meta': {'Duration': 2}, 'Curves': []})
    write_json(model / '大肥鱼.vtube.json', {'ParameterSettings': [
        {'Input': 'FaceAngleX', 'OutputLive2D': pid, 'InputRangeLower': -30,
         'InputRangeUpper': 30, 'OutputRangeLower': -30, 'OutputRangeUpper': 30}
        for pid in ['AngleX', 'PositionX']]})
    return model
