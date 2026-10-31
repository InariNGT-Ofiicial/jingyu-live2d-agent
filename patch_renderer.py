"""Reproducible Cubism 4.2+ drawable-color backport for pinned display 0.4.0.

Formula follows Live2D CubismWebFramework 5-r.1 cubismshader_webgl.ts.
No source textures, drawable opacity, or model data are modified.
"""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent
source = ROOT/'web/vendor/cubism4.min.js'
text = source.read_text(encoding='utf-8')

def replace(old, new, count=1):
    global text
    assert text.count(old) == count, f'Unexpected vendor build: {old[:60]}'
    text = text.replace(old, new)

# The visible-draw pass carries the current index; mask setup remains alpha-only.
replace('this.setIsCulling(this.getModel().getDrawableCulling(t)),this.drawMesh(',
        'this.setIsCulling(this.getModel().getDrawableCulling(t)),this._drawableColorIndex=t,this.drawMesh(')

# Install the uniforms only on the three color fragment shaders.
for old in ['texture2D(s_texture0 , v_texCoord) * u_baseColor',
            'texture2D(s_texture0, v_texCoord) * u_baseColor']:
    replace(old, 'bridgeColor(v_texCoord) * u_baseColor', 2 if '0 ,' in old else 1)

helper = ('uniform vec4 u_multiplyColor;uniform vec4 u_screenColor;'
          'vec4 bridgeColor(vec2 uv){vec4 c=texture2D(s_texture0,uv);'
          'c.rgb*=u_multiplyColor.rgb;'
          'c.rgb=c.rgb+u_screenColor.rgb*c.a-c.rgb*u_screenColor.rgb;return c;}')
for name in ['Gt','Xt','zt']:
    start = text.index(name+'="')
    at = text.index('void main()', start)
    text = text[:at]+helper+text[at:]

replace('if(this.gl.useProgram(n.shaderProgram),n',
        'if(this.gl.useProgram(n.shaderProgram),'
        'n.bridgeMultiply??=this.gl.getUniformLocation(n.shaderProgram,"u_multiplyColor"),'
        'n.bridgeScreen??=this.gl.getUniformLocation(n.shaderProgram,"u_screenColor"),'
        'this.gl.uniform4fv(n.bridgeMultiply,t.getModel()._model.drawables.multiplyColors.subarray(t._drawableColorIndex*4,t._drawableColorIndex*4+4)),'
        'this.gl.uniform4fv(n.bridgeScreen,t.getModel()._model.drawables.screenColors.subarray(t._drawableColorIndex*4,t._drawableColorIndex*4+4)),n')

# The vendor build hard-codes the clipping-mask framebuffer at 256x256
# (CubismClippingManager_WebGL: `this._clippingMaskBufferSize=256`). A drawable that is
# mostly hidden — a tail behind a skirt is the usual case — takes its visible edge from
# that mask instead of from its own texture alpha, so a 256 buffer stretched over a
# ~800x1600 character lands one mask texel on 3~6 screen pixels and the cut edge comes
# out as a staircase. No amount of MSAA/SSAA or texture filtering helps there, which is
# why the artifact only shows on those parts. Live2D's own CubismRenderer_WebGL exposes
# setClippingMaskBufferSize() for the application to raise this; the minified vendor
# build keeps the default. One RGBA target: 4 MB at 1024, 16 MB at 2048.
CLIPPING_MASK_BUFFER_SIZE = 2048
replace('this._clippingMaskBufferSize=256',
        f'this._clippingMaskBufferSize={CLIPPING_MASK_BUFFER_SIZE}')

output=ROOT/'web/vendor/cubism4.colors.min.js'
output.write_text(text, encoding='utf-8')
record={'sourceSHA256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'patchedSHA256':hashlib.sha256(output.read_bytes()).hexdigest(),
        'reference':'https://github.com/Live2D/CubismWebFramework/blob/5-r.1/src/rendering/cubismshader_webgl.ts',
        'scope':'Dynamic per-drawable multiply/screen colors, including clipped and inverted-mask fragments; plus a 2048x2048 clipping-mask framebuffer in place of the hard-coded 256x256.'}
(ROOT/'renderer-patch.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record,indent=2))
