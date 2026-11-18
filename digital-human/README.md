# 鲸语数字人视频电话

给自己的角色搭一部可以直接说话的视频电话。手机播放预生成的竖屏动作，云端识别语音、保留本次通话上下文并合成回答。来电者开口可以打断播放。单个实例提供一个通话席位。

## 快速开始：先让角色动起来

从仓库首页选择 `codex/digital-human` 分支。以下命令也可以直接检出这个分支。

```sh
git clone --branch codex/digital-human https://github.com/InariNGT-Ofiicial/jingyu-live2d-agent.git
cd jingyu-live2d-agent/digital-human
python -m pip install Pillow
python avatar.py --demo
python preview.py
```

需要 Python 3.10+ 和带 libx264 编码器的 FFmpeg。把 `ffmpeg` 加入 PATH，或将 `FFMPEG` 环境变量设为可执行文件路径。打开 <http://127.0.0.1:18980/>，点「轻挥手」，等当前动作自然播完。示例机器人由代码在本机生成。这一步可以在普通电脑上运行。

## 换成自己的形象

1. 在 `character.json` 填角色呼号。准备一张正视来电图和九段相同机位、相同画幅的动作。首尾使用同一个回正姿势，前后片段才能自然衔接。
2. 素材目录中按下表命名 MP4，执行 `python avatar.py --clips "/path/to/my-clips" --poster "/path/to/front.png"`。命令会在本地数据目录生成桌面、手机和首播版本。再次打开预览，分别点选每个动作。
3. 在 `dialogue-bank.json` 修改台词、别名和关联动作。`web/motion-policy.json` 控制状态可选动作和最短重复间隔。更换呼号或改词后重新生成预设语音。更换参考音色时执行 `python prepare_lines.py --refresh`。

| 动作 | MP4 文件名 | 动作 | MP4 文件名 |
|---|---|---|---|
| 正视呼吸 | front-breathe.mp4 | 舒展肩膀 | h3-shoulders.mp4 |
| 整理领结 | h3-ribbon.mp4 | 点头 | acknowledge.mp4 |
| 看消息 | read-request.mp4 | 挥手 | wave.mp4 |
| 倾听 | listen.mp4 | 托腮思考 | think.mp4 |
| 浅笑 | smile.mp4 | | |

已有视频可以直接导入。需要自己生成动作时，看 [H3 挥手工作流](workflows/README.md)。

## 接入语音和对话

已验证的参考部署为 Linux、NVIDIA 48 GB vGPU、CUDA 12.8 和 PyTorch 2.8.0。动作预生成与电话服务可以分时运行，通话阶段直接解码 H.264。模型、参考声音和角色素材由搭建者自行准备。

| 模型 | 实际职责 | 默认目录 |
|---|---|---|
| [Qwen3-ASR-1.7B-hf](https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf) | 将浏览器的 16 kHz 单声道语音转成文字 | .local/models/asr |
| [Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct) | 判断短句是否适合预设，为连续追问生成带上下文的回答 | .local/models/decision |
| [CosyVoice2-0.5B](https://huggingface.co/FunAudioLLM/CosyVoice2-0.5B) | 从文字、参考音色生成 24 kHz 语音，整句按语义分段衔接播放 | .local/models/cosyvoice |

在 Linux 上单独准备两个 Python 环境。电话环境使用 Transformers 5.16.1，语音环境使用 Transformers 4.51.3。以下命令从 `digital-human/` 执行，`python3.10` 也可换成兼容的解释器。

```sh
python3.10 -m venv .local/call-env
.local/call-env/bin/pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128
.local/call-env/bin/pip install -r requirements-call.txt
.local/call-env/bin/hf download Qwen/Qwen3-ASR-1.7B-hf --local-dir .local/models/asr
.local/call-env/bin/hf download Qwen/Qwen2.5-1.5B-Instruct --local-dir .local/models/decision
.local/call-env/bin/hf download FunAudioLLM/CosyVoice2-0.5B --local-dir .local/models/cosyvoice
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git .local/CosyVoice
git -C .local/CosyVoice checkout 074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc
git -C .local/CosyVoice submodule update --init --recursive
```

按 [CosyVoice 安装说明](https://github.com/FunAudioLLM/CosyVoice/tree/074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc) 配好独立语音环境，包括 Matcha-TTS、语音前端与 CUDA 版 PyTorch。确认该环境能用 `CosyVoice2-0.5B` 生成一段声音，然后安装 `aiohttp==3.12.15`、`transformers==4.51.3`。把一段有权使用的人声 WAV 放到 `.local/reference.wav`。

离线运行时，从 [WeText 规则库](https://modelscope.cn/models/pengzhendong/wetext) 取得 `zh/tn` 和 `en/tn` 下的 `tagger.fst`、`verbalizer.fst`，保留相对目录放入 `.local/models/wetext`。已有规则可设置 `JINGYU_WETEXT`。这样首次启动就能直接加载中英文规范化规则。

按顺序启动。下表中的 Python 分别指相应环境里的解释器。第一个和第三个进程保持运行。

| 顺序 | 环境和命令 | 成功时看到 |
|---|---|---|
| 1 | 语音环境：`python synthesis.py` | 预热后输出 READY，语音与快速回答服务监听本机 18983 |
| 2 | 电话环境：`python prepare_lines.py` | 本地生成台词 WAV 和校验清单 |
| 3 | 电话环境：`python server.py` | 输出 READY，在电脑打开 <http://127.0.0.1:18982/> |

语音合成采用与演示相同的 CosyVoice 2 链路，实际音色取决于参考录音和 `JINGYU_VOICE_STYLE`。已有权重可设置 `JINGYU_ASR`、`JINGYU_DECISION`、`JINGYU_COSY_MODEL`、`JINGYU_COSY_SOURCE`、`JINGYU_VOICE_REFERENCE` 指向本机路径。自定义数据目录用 `JINGYU_DATA`。设置和默认值见 [settings.py](settings.py)。运行前请完成动作导入或生成示例。

## 手机接听和验收

1. 在本机数据目录 `.local/mobile-origin.txt` 中写一行自己的 HTTPS 源地址，例如 `https://call.example.org`，结尾不带斜杠。重启 `server.py`，它会生成 `.local/mobile-invite`。
2. 将该 HTTPS 源反向代理到 `127.0.0.1:6006`，启用 WebSocket 升级，保留原浏览器 Origin。18982 和 18983 只供本机使用。手机访问 `https://call.example.org/#你的邀请码`，允许麦克风后接听。
3. 围绕同一主题连续追问，在角色回答时开口插话。挂断后进入「通话复盘」查看识别文本、末音到首声的逐轮估算和打断次数。录音、实际网络、浏览器和 GPU 都影响延迟。

只开动作预览和运行文本逻辑测试均无需 GPU。运行测试：`python -m unittest discover -s tests`。代码许可见仓库根目录 [LICENSE.txt](../LICENSE.txt)，模型及自行导入的角色素材遵循各自许可。
