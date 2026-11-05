# IndexTTS 接入探索 · 2026-11-04

结论：保留已跑通的 CosyVoice DS 娘声线作为默认。IndexTTS 2.5 作为第二个本地语音后端候选，先做同文本、同参考音色的对照，再决定是否替换。

官方源码已拉取并检查，commit `d9e41aac89fd00b3d71497fddb287b7f24613712`。已安装到 `E:/Apps/IndexTTS`，主模型、QwenEmotion、w2v-bert、CampPlus、BigVGAN 下载完成并核验权重 SHA-256。独立 `.venv310` 的官方推理模块导入通过，识别 RTX 5060 Laptop；尚未进行实际语音推理和听审。

启动入口为 `E:/Apps/IndexTTS/start-webui.cmd`，本机端口 7865。Torch 2.8.0+cu128、torchaudio 2.8.0+cpu 从本机已有安装复制，其他包通过 uv 安装；原有 CosyVoice 包未升级。此前 `.venv` 是未完成的 Python 3.11 尝试，启动脚本使用 `.venv310`。

## 值得试的能力

官方 2.5 接口支持参考音色与八维情绪向量分开输入，也支持情绪参考音频。`duration_factor` 大于 1 放慢，小于 1 加快；不是给定绝对秒数。文字情绪描述需要额外启用 QwenEmotion。优先用显式情绪向量验证，方便日后让动作计划和声音共享情绪参数。[官方说明](https://github.com/index-tts/index-tts)

## 本机适配

本机实测为 RTX 5060 Laptop / 8 GiB、CosyVoice Python 3.10.18、Torch 2.8.0+cu128。IndexTTS 当前要求 Python 3.10/3.11、Torch 2.8、Transformers 4.52.1、NumPy 2.2.6；现有 CosyVoice 的后两项为 4.51.3 / 1.26.4，应该建独立环境，避免升级破坏已有声线。[官方依赖](https://github.com/index-tts/index-tts/blob/main/pyproject.toml)

首轮用 BF16，关闭 DeepSpeed、自定义 CUDA kernel、accel、torch.compile 和 QwenEmotion。8 GiB 是否能与 OBS/Live2D 同时流畅运行需要实测；不能用参数量估算代替显存峰值。除主权重外，源码还会准备 w2v-bert、CampPlus 与 BigVGAN 辅助资产。[下载实现](https://github.com/index-tts/index-tts/blob/main/indextts/utils/model_download.py)

## 下一步可复现试验

在独立官方 uv 环境下载 `IndexTeam/IndexTTS-2.5` 后，运行本项目 `tools/index_tts_probe.py`。不带 `--run` 只检查，不加载模型；带 `--run` 生成 neutral、happy、slow 三段同文本音频，记录时长、RTF、峰值显存、音频指纹。模型首启可能下载辅助资产。

```powershell
python tools/index_tts_probe.py --repo D:/path/to/index-tts --model D:/path/to/checkpoints --preset D:/AI-Voice/音色预设/DS娘_晓伊A3/preset.json
# 在 IndexTTS 独立环境中，确认权重齐全后：
python tools/index_tts_probe.py --repo D:/path/to/index-tts --model D:/path/to/checkpoints --preset D:/AI-Voice/音色预设/DS娘_晓伊A3/preset.json --output D:/path/to/comparison --run
```

三段测试均保持原参考音频，使用同一句欢迎语。听审关注音色漂移、漏读、中文与 DS 字母读法、情绪强度和自然停顿；另测冷启动与预热延迟、连续十段成功率，再测 OBS 同时运行的掉帧。首轮通过后适配同一个 `/api/studio/voice` 作业接口即可复用播放器、口型、字幕和停止逻辑。

当前官方采用 bilibili Model Use License Agreement；发布依赖说明应链接原协议，不能把当前版本写成 Apache-2.0。[官方许可证](https://github.com/index-tts/index-tts/blob/main/LICENSE)
