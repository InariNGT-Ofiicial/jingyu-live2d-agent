# CosyVoice 流式直出研究

目标：保留 DS 娘晓伊 A3 声线，让文本生成、语音合成、播放三个过程重叠。

## 视频证据与适用范围

[BV1aRq6BtE2M](https://www.bilibili.com/video/BV1aRq6BtE2M/) 的 03:33–04:27 对比串行等待与提前送入半句文本；05:04–05:26 描述将完整短句送入 GPT-SoVITS，再交给播放器。它提供流水线思路，不是 CosyVoice 的实现或延迟基准。复用已经取回的逐字稿，识别稿中的模型名存在转写错误。

[CosyVoice 官方示例](https://github.com/QwenAudio/CosyVoice/blob/main/example.py) 提供音频分块与生成器文本输入示例。本地安装的 CosyVoice2 源码也包含 `inference_bistream`，无需先升级模型。

## 当前工作台的三个等待点

- `planner.py`：HTTP 模型请求使用 `stream=False`；DSH CLI 等待进程完整输出。当前主要输出是动作计划 JSON，不能把其任意增量直接朗读。
- `studio_voice.py` / `studio_voice_worker.py`：每个任务启动 Python 并加载模型，使用 `stream=False`，最后拼接全部音频写 WAV。
- `web/scene-experiment.mjs`：轮询任务到 ready，再用完整音频播放。

## 可复现实验

`tools/cosyvoice_stream_probe.py` 复用预设的参考音频、语气、种子和线程设置，核验参考音频哈希。模型在进程内复用，声线条件通过 `add_zero_shot_spk` 缓存在内存，不写模型目录。

四轮分别为：完整文本完整合成（原 1.035 倍速）、完整文本音频流式、重复的热态流式、定时输入文字的双流式。最后一轮可用 `--play` 通过 sounddevice 回调播放，并记录设备下溢和队列缺粮帧数。文字每 0.8 秒到达一段，是模拟输入，未调用真实 LLM。

输出 `results.json`、四份 WAV。指标包含首个 PCM 包时间、完整合成时间、音频时长、实时率、分块时序与按时序计算的额外起播缓冲。首包时间不包含模型加载或声线缓存时间；两者单独记录。首轮模型计算存在冷启动开销，不能把全部差异归因于 streaming 开关。WAV 是留档，实时播放直接消费 PCM 队列。

## 本地源码约束

1. 文本生成器会绕过 `text_normalize`。上游应保留标点、合并语义短片段并处理数字读法；不要逐字启动新合成任务。
2. 本地 CosyVoice2 流式分支没有把 `speed` 传给 `token2wav`，因此原来的 1.035 不会生效。实验明确用 1.0；正式播放若要保留速度，应独立评估播放器变速的音色影响。
3. `token_hop_len` 从 25 增长到 100，且会留在模型实例上。常驻单任务服务应在每轮开始恢复为 25，避免后续请求首包变大。不要随意减小训练要求的块大小。
4. 生成器路径不支持本地源码的 vLLM 分支。不要把开启 vLLM 当作本方案的无条件优化。
5. 缓存条件包含语气提示词。若更换语气，需要相应更新缓存，不能只改调用参数却沿用旧缓存。

## 2026-11-05 本机实测

设备：RTX 5060 Laptop 8 GB；PyTorch 2.8.0+cu128；CosyVoice2-0.5B；24 kHz 单声道。PyTorch 使用 CUDA，但本机 ONNX Runtime 只有 CPU/Azure provider，声线条件提取走 CPU，已经在计时前缓存。

| 实验 | 首个 PCM 包 | 合成耗时 / 音频时长 | 实际播放结果 |
|---|---:|---:|---|
| FP32 完整输出 | 11.65 s | 11.65 / 12.04 s | 留档，未播放 |
| FP32 热态音频流 | 2.34 s | 15.58 / 12.68 s | 时序估计需额外 3.63 s 缓冲 |
| FP16 热态音频流 | 1.92 s | 13.34 / 12.44 s | 时序估计需额外 2.62 s 缓冲 |
| FP16 原生生成器双流 | 2.16 s | 19.11 / 18.84 s | 队列缺粮 1.56 s；内容检查失败 |
| FP16 语义短句流水线 | 3.85 s | 16.65 / 14.16 s | 6.38 s 首次送音频到设备；未记录队列缺粮或设备下溢 |

**关键失败：直接把原来的 instruct2 接到文本生成器，会把语气指令也合成为语音。** 两种精度的 ASR 均识别出“用自然、平稳……句间自然停顿”，FP32 一轮还未识别到开场白。结合本地 `inference_bistream` 将 `prompt_text` 放入 `text_cache` 的实现，不应直接将此路径用于现有 A3 指令声线。

短句流水线逐段调用原来的 instruct2 音频流，每段恢复 hop=25；文字按 0.8 s 间隔模拟到达，不等待全部文字结束才启动合成。第一段在 1.60 s 开始合成，最后文字约 4.00 s 到达，首包 3.85 s。播放器在首包后预留 2.5 s 起播缓冲，实际首个含音频回调 6.38 s。ASR 内容完整，名字有“小衣”同音转写；主观音色、自然度仍需试听。

这个有限长度样本没有断粮，但合成总耗时仍大于音频长度，不能持续无限供音。下一步需要降低每段生成耗时，并在真实长回复和 L2D/OBS 同时运行条件下测量队列增长或耗尽。1.92 s 不是完整产品的首声延迟：它排除了模型加载、条件提取、LLM 等待和播放缓冲。

实验开始曾卡在 Numba 向外部依赖目录创建缓存文件；设置工作区 `NUMBA_CACHE_DIR` 后解除。正常模型加载实测 7.39–10.50 s，尚不包含 Python 依赖导入。常驻服务应显式提供“加载中 / 已就绪”，而不是每句重复付出这项开销。

本机结果目录：`outputs/cosyvoice-stream-study-20261105/`（工作区根目录下）。原始 FP32、`fp16/`、`segmented/` 各有 JSON 和 WAV；`asr-check.json` 是离线 CPU/int8 Whisper-small 辅助转写。

## 接入工作台的建议顺序

先采用已验证的语义短句路线，暂不把 instruct2 的原生生成器路径用于产品。做常驻、单任务的本地 CosyVoice worker：加载、预热一次，提供开始、文本增量、文本结束、取消四类消息。沿用现有 Python 环境与离线补丁。请求编号隔离上一轮余音，取消时立即停止消费旧 PCM；模型侧只能在已知生成边界释放任务。

再加本地 PCM 流通道：开始消息声明采样率、通道数和格式，随后发送有序 PCM 帧，结束消息包含总样本数。保留现有 WAV 留档、下载和重播。首轮以已有 HTTP 服务的流式响应验证；双向控制可用独立 POST，无需同时重造整套服务。

网页使用 Web Audio 的连续 PCM 队列与一个播放时钟；用实测数据选择起播缓冲。嘴型取实际播放音频的能量，字幕按播放进度推进。不能对每包单独创建 Audio 标签，也不能等待整份 WAV 后再声称流式。

最后接真实 LLM：新增聊天用的可朗读文本流，复用现有服务配置，动作计划仍独立完整校验。支持中途打断；验证首声延迟、队列断流、文本完整性以及数字/中英文混排。外部模型请求的延迟必须与本地 TTS 首包分开统计。

## 工作台接入（2026-11-05）

直播间右侧「实时语音」提供加载声线、边合成边播放、等待 Agent 台词、停止说话。主工作台导航可进入直播间。场景预览在桌面布局保持可见。

常驻进程使用原有声线环境和参考音频，CUDA 可用时启用半精度；声线条件仅在内存缓存，语气令牌按任务更新。模型加载成功后才启动 stdin 接收线程，避免本机 NumPy 原生模块初始化与阻塞输入线程发生停滞。进程异常时任务明确失败，下次请求重新加载。

网页通过 HTTP NDJSON 直接接收 24 kHz PCM16，AudioWorklet 连续播放并转换到声卡采样率。起播时预留 3 秒和至少 3 秒音频；短台词全部生成后可直接起播。字幕随实际消费样本数推进，嘴型分析同一个播放节点。合成期间直播间渲染上限 30 FPS，合成完成恢复 60 FPS，为同一块笔记本 GPU 留出推理时间。结束保存 WAV，历史下载和重播入口继续可用。

「等待 Agent 台词」会创建空会话并启用本页播放。当前 Codex 或其他 agent 查询状态里的 `activeId`，然后逐段 append；最后必须发送 `done: true`，否则尾句不会收尾。无输入超过 120 秒自动取消。每轮最多 500 字，单任务串行；较长文本按语义切分，单个片段最长 80 字。停止按钮立即切断本页音频；后台丢弃后续 PCM，并让正在推理的片段收尾后复用模型。

| HTTP | 用途 |
|---|---|
| `GET /api/studio/voice` | 历史、`engineState`、`activeId`、是否忙 |
| `POST /api/studio/voice/warmup` `{}` | 加载常驻声线 |
| `POST /api/studio/voice/start` | `{text?, instruction?, inputComplete: false}` 创建增量会话；返回 id 和 streamUrl |
| `POST /api/studio/voice/append` | `{id, text, done: false}` 追加可朗读台词；最后一次 `done: true` |
| `GET /api/studio/voice/stream?id=…` | 有序 NDJSON：start、segment、pcm、done / cancelled / error |
| `POST /api/studio/voice/cancel` | `{id}` 取消尚在合成的会话 |
| `POST /api/studio/voice` | 原整段合成接口，仍返回异步任务和最终 WAV |

`pcm` 包声明样本数量、起始样本偏移和 base64 PCM16LE 数据；`segment` 包给出该句台词及音频起点。流事件保留最近 8 个任务供连接恢复/检查，历史 WAV 独立保存在 `.local/studio-voice`。合成已完成但网页仍在播时，使用网页停止按钮或现有 `/api/studio/command` 的 `stop`（指定 clientId）。

CLI 使用 `JINGYU_STUDIO_URL` 选择地址，新增 `voice-warmup / voice-start / voice-append / voice-cancel`。例如在网页点击等待 Agent 后：

```powershell
$env:JINGYU_STUDIO_URL='http://127.0.0.1:61944'
python studio_cli.py voice
python studio_cli.py voice-append --speech-id <activeId> --text '你好，接下来我会分段介绍今天的内容。'
python studio_cli.py voice-append --speech-id <activeId> --text '现在是最后一句。' --done
```

MCP 新增 `speech_stream_start / speech_stream_append / speech_stream_cancel`；`speech_status` 可读取 activeId。不会直接朗读动作计划 JSON，也不会自动产生付费模型请求。OpenAI / DSH 可朗读 delta 应交给 append，当前没有新增上游聊天模型客户端。

验证包含分句、500 字限制、收尾、取消、缓存播放、24→48 kHz 转换的基础测试，以及 Edge 调试 API 驱动的真实页面播放、字幕、嘴型、WAV、取消后复用、历史重播。脚本为 `tools/verify_voice_browser.py`，结果位于 `.local/checks/voice-stream/`。测试使用独立浏览器调试实例并授予播放权限，正常页面仍需点击按钮启用声音。长时间直播、其他 GPU 负载与不同声卡设备尚需实测，当前声线听感仍需试听。

最终页面验收样本 `35647c6d657b`：首个 PCM 3.62 s（包括模拟文字分批到达时间），音频 12.52 s，AudioWorklet 缺粮块数 0；字幕跨两个语义段，嘴型随播放变化。取消样本 `96cf4bbf2652` 后成功生成下一句 `40db07803fdc`，并完成历史重播。重启新版服务后原样本仍为 ready。基础测试 10 项及 PCM 缓冲/采样率/停止测试通过。
