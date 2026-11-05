# 直播间工具层

入口 `/scene-experiment.html`，OBS 浏览器源使用 `/scene-experiment.html?clean=1`（1280×720，30 FPS）。这一层提供确定性的场景、动作、音频与录制控制；不包含人格、记忆或自主发言循环。

## 运行与接口

沿用工作台 server.py。CLI 默认连接 `http://127.0.0.1:61944`，其他端口设置 `JINGYU_STUDIO_URL`。

```powershell
python studio_cli.py state
python studio_cli.py set --theme cool --camera close
python studio_cli.py play --client <state中的clientId> --plan plan.json --silent
python studio_cli.py stop --client <clientId>
python studio_cli.py obs --obs-action status
python studio_cli.py obs --obs-action switch --obs-scene "Jingyu Scene Wide"
python studio_cli.py obs --obs-action record
python studio_cli.py obs --obs-action stop
```

HTTP：GET `/api/studio/state`；POST `/api/studio/command`（action=set/play/stop）；POST `/api/studio/obs`（action=status/switch/record/stop）。动作计划沿用现有 version:1 编译器。播放需指定在线 renderer；只有唯一网页 renderer 时可省略。OBS renderer 不会被自动选中。

命令返回 accepted 后，通过 state 中 jobs 的同一 id 读取 playing/completed/interrupted/error。客户端离线或未确认会产生错误；接受命令不等于执行成功。场景状态保存在当前服务进程内，重启恢复默认。

音频示例需先点击“启用声音”。播放与停止同步控制音频和动作；嘴型使用音量幅度驱动。字幕为演示音频专用，自定义 silent 计划不代表语音合成。

## 讲话表演（2026-11-05）

直播间的语音面板提供自动、自然、开心、温柔、好奇、含笑害羞、认真七个选项，以及自动动作开关、幅度和讲话音量。固定语气为 TTS 与动作使用同一个选项，自定义语气指令优先。自动模式是本地关键词规则，只切换表情动作，不调用额外模型，也不声称能理解任意台词的情绪。

动作跟随实际消费的音频样本时钟，包含短句强调点头、侧看、重心变化、微笑和脸红；优先级为待机 / 注视 < 讲话动作 < 明确编排的动作。保留作者物理和手臂通道，不随机触发竖指手势。讲话期间触摸语音让位，停止后恢复待机。新 take 保存 `performance` 和分句样本位置，重播使用同样的语气、动作时钟及分句字幕；旧 take 没有分句位置时按整句播放。

一次调用自动合成并在目标直播间表演：

```powershell
python studio_cli.py speak --client <clientId> --text "欢迎来到雨夜书房，今天想聊什么？" --emotion happy --intensity 0.7
```

HTTP `POST /api/studio/speak`，字段为 `clientId`、`text`、可选 `instruction`、`performance: {emotion, intensity, motion}`。返回执行任务及 `speech.id`，通过 `/api/studio/state` 查看 accepted → preparing → playing → completed / interrupted / error。目标必须在线且已经点击启用声音；未解锁时直接报错，不启动合成。`inputComplete:false` 可创建自动播放的增量会话，后续沿用 voice/append 并最终 done=true。MCP 对应 `speech_perform`；停止沿用 playback_stop。

稳妥缓冲默认 3 秒，可选择 1 秒快速模式；页面分别显示请求到首包、请求到起播及等待音频块数。冷启动时间包含在指标内，不与热启动混为一谈。语音历史只保存语音和表演设置，音量与缓冲属于播放端设置。当前自动讲话表演与一键 speak 的目标是网页直播间 / OBS 场景页；桌宠和 VTS 继续使用现有动作与触摸通道，尚未加入这条实时讲话输出链路。

## MCP

用安装了 `mcp` 的 Python 启动 `studio_mcp.py`（stdio）。配置示例中的路径需替换成本机绝对路径：

```json
{"mcpServers":{"jingyu-studio":{"command":"C:/path/to/python.exe","args":["D:/path/to/studio_mcp.py"],"env":{"JINGYU_STUDIO_URL":"http://127.0.0.1:61944"}}}}
```

工具：studio_state、scene_set、playback_start、playback_stop、obs_control。使用的是同一套 HTTP 回执，尚未自动注册到用户的 MCP 配置。

## OBS 与场景资产

OBS WebSocket 使用本机 4455，密码来自 `JINGYU_OBS_PASSWORD` 或忽略提交的 `.local/obs-experiment-password`。服务通过现有 capture_python 启动带 websocket-client 的桥接进程。场景需预先在 OBS 创建；record/stop 控制 OBS 当前配置的输出，stop 返回真实文件路径。

本机验证时 OBS 浏览器硬件加速导致黑屏，关闭后恢复。新场景使用 Blender 预渲染的暖/冷背景与前景 PNG，中间实时叠加 Live2D；不是浏览器实时运行 Blender。资产在 `web/scene-assets/study-v2`，渲染生成脚本为 `tools/build_studio_scene.py`。静态雨纹、书架与灯光可在 Blender 中继续修改。

当前实时角色画布为 720p；静态层为 1080p。网页后台节流仍影响画面帧率，播放结束另外用定时器判定。VTS 原生画面输入尚未接入本场景页；本页目前使用网页 Live2D renderer。

## 视线与身体摇晃

工作台网页和演播室共用自然动态：视线跟随鼠标，眼球先响应、头部稍后跟随；离开窗口或失去焦点时平滑回正。周期身体摇晃默认 65% / 8 秒，可单独开关，幅度 0–100%、周期 4–16 秒。设置保存在本机浏览器；工作台关闭自然待机也会停止身体摆动。显式动作和表情位于更高优先级，不被跟随覆盖。只写作者的头身输入参数，再由原物理驱动头发、衣饰等，未覆盖物理输出。

这些控制作用于网页渲染器；切到 VTS 时工作台禁用对应控件。离线导出及对比模式不读取鼠标或这组浏览器设置。

随机待机事件提供换脚调整重心、轻微前倾、舒展上身、放松回落、深呼吸、轻轻侧身六类。事件使用平滑起落，随机方向/时长，事件之间休息 3–9 秒且不连续重复；正式表演期间暂停随机触发。幅度沿用摇晃幅度滑块。可单独关闭“随机待机事件”。

胸部物理增益默认为 1.3×，可调 1.0–1.8×，1.0 恢复作者原始输出。网页物理计算完成后，只对 ChestX1/2/3/BS 与 ChestY1/2/3/4 的相对默认值增加增益，并限制在模型参数范围内。原始模型文件、物理 JSON 不修改；关闭作者物理后此增强不运行。导出和 VTS 不使用此网页增益设置。

## 点击反馈

工作台与直播间支持“点击互动”和“分区反馈”开关。普通点击触发点头/微笑，胸口触发快速后撤侧闪，大腿上侧触发更明显的侧身闪避；随后抚胸、脸红、低头侧目停留，再缓慢回正，特殊反馈完整时长约 7.5 秒。短句以气泡显示，并播放缓存的 DS 情感语音。关闭分区反馈后统一使用普通回应，关闭点击互动则不触发。

3.5 秒冷却；15 秒内再次点击同一区域会使用另一句回应。拖动、长按、控件点击不触发；播放表演时只提示等待，不打断动作或音频。直播间桌面遮挡的下部区域不可点击。设置保存在本地浏览器。

命中区域以模型边界和画布实际显示尺寸换算，适应近景/全身和 CSS 缩放；目前是近似椭圆分区，不是逐画元网格命中，大幅姿态变化仍需后续校准。网页三种区域实际点击已通过；VTS 原生窗口尚无此交互。

参考的是角色互动动作与回应的组织方式，不使用崩坏3素材或台词。官方舰桥互动动作/语音示例来源：[8.7 版本公告](https://bh3.mihoyo.com/news/694/162560)。

## DS 娘本地语音

在 `.local/studio-voice.json` 写入 `{"preset":"D:/AI-Voice/音色预设/DS娘_晓伊A3/preset.json"}`。沿用预设的解释器、模型、参考音频哈希、指令、seed 和 speed；不复制参考音频到公开目录。

演播室右侧可输入台词、可选语气指令，点击“合成 DS 声音”，完成后“播放 / 重播”。停止按钮同时终止当前音频和动作。字幕显示整段台词，口型使用音量驱动，尚非音素级对齐。当前由常驻 CosyVoice 进程合成，支持预制 WAV 与增量文本 / PCM 播放；流式播放可取消，已完成的 WAV 可重播。详见下文及 cosyvoice-streaming.md。

```powershell
python studio_cli.py voice --text "晚上好，我是 DS 娘。"
python studio_cli.py voice --speech-id <合成任务id>
python studio_cli.py play --client <clientId> --speech-id <合成任务id>
```

HTTP：POST `/api/studio/voice` 提交 text 和可选 instruction，GET `/api/studio/voice?id=...` 查询 synthesizing/ready/error；ready 后以 `audio:"speech",speechId:"..."` 调用原有播放接口，可同时传入 plan。GET 无 id 返回声线配置状态。MCP 增加 speech_synthesize、speech_status、speech_play，合计八个工具。

新 take 和回执在 `.local/studio-voice/<id>/`，包含 WAV、台词、参数、指纹、时间和 worker.log；修改台词另建 take。主进程不加载 Torch，同一时刻只接受一个合成请求。

“已保存的台词”自动读取最近 50 个任务中的成功结果，刷新或服务重启后仍可选择、重播、下载 WAV。刷新时若后台仍在合成，会继续查询状态。选择历史台词会恢复该 take 的文本和语气；编辑后需要重新合成，重播始终使用所选 take 的原音频。

2026-11-04 实测：5.16 秒 / 24 kHz 单声道欢迎语，模型加载约 13.52 秒、推理约 6.72 秒（不包含 Python/Torch 导入开销），参考哈希与本地 A3 预设一致。HTTP 合成、网页字幕/停止/重播和 MCP 状态调用通过；新音频等待用户试听，未做自动 ASR 内容验收。

### 多组触摸反馈

2026-11-05 加入 13 条 DS 娘 A3 情感短语音，工作台、演播室与网页桌宠共用。音频在 `web/assets/touch-voice/`，点击时直接播放缓存，不等待现场合成；字幕使用对应音频原文，嘴型按音量驱动。「触摸情感语音」开关和音量独立保存。重新生成使用 `python tools/build_touch_voice.py`（本地语音服务需在线）。

胸部按住约 450 毫秒进入拖拽，持续脸红、微笑，先短暂移开视线、约 1.6 秒后主动回望，长按期间按 6 秒周期轻微变化，并保留上半身跟随；松手后平滑回正。三句含笑的日常回应轮换，每句播完再间隔 4 秒，不叠音；松手、窗口失焦、隐藏页面或新动作接管时结束，松手音频淡出约 120 毫秒。台词采用亲近、俏皮的聊天语气与自然换气，不添加独立喘息音效。关闭互动语音仍保留动作和表情。原生 VTS 窗口不支持这套网页指针交互。

三个网页表面已通过实际鼠标点击、拖拽、口型与松手恢复检查；演播室长按跨过两句语音周期。检查记录在 `.local/checks/touch-voice/`。语气自然度仍以实际试听为准。

普通点击、胸口、大腿上侧各有 4 组编排，同一区域不会连续抽到相同动作。普通动作包含点头、侧身、双手招呼和眨眼；特殊反馈包含后撤、侧闪、摇头与回望，持续约 5.9 秒后收回。双手动作通过 `hand_on_chest` 加 `pair: "point"` 同时驱动作者两侧独立手臂通道，共享光影通道只保留一份。忙碌时仍不打断当前表演。

### 连续表情与动作节奏

新生成计划默认使用较快侧转、回望和缓收尾；提示词明确共享绝对时间轴，不将脸红串行接在肢体动作之后。`expression.duration` 可为 0.2..59 秒，可用一条表情轨道跨过多段身体动作，只在整段首尾淡入淡出；计划总长仍不超过 60 秒。同参数冲突规则保持不变。已有保存计划不会自动重写时间或参数，需要重新编排后另存。

### 预设动作差异

触摸反馈每个区域按四组一轮轮换，每轮不重复，并优先避开上次使用的手势类型。12 组中仅普通双手招呼使用双手组合，其余分配持草、单手或默认垂手。6 组长表演移除了重复的竖指开场或抚胸收尾，保留各自头身轨迹与情绪线；用户保存的个人预设未修改。

### 模拟弹幕读取与回复

直播间「模拟弹幕」面板支持随机间隔（2..60 秒）、本轮条数（1..20）和手动单条发送。页面与消息记录明确标注模拟来源。默认回复端为当前 Codex / 外部 Agent：模拟器仅发观众文本；Agent 领取消息、结合最近四轮已完成上下文生成回复，再调用 reply 进入现有 DS 娘流式语音。无人值守使用时，需要持续轮询接口的常驻 Agent；本功能不会自动调用付费模型，也尚未接入直播平台弹幕源。

所有路由位于 `/api/studio/danmaku`：GET 读取状态；POST `/start` 传 clientId、minInterval、maxInterval、count；`/message` 传 author、text；`/claim` 传空对象领取一条；`/reply` 传 id、text（1..160 字）；`/report` 是网页播放回执；`/stop` 停止定时器、排队消息和当前回复。领取是串行的：必须等网页实际播完，不能只等 TTS 生成完。最多 8 条排队，超出标为 skipped。停止后迟到的回复不能重新触发声音。

CLI：`studio_cli.py danmaku`、`danmaku-claim`、`danmaku-reply --message-id <id> --text <回复>`、`danmaku-stop`。MCP：`danmaku_state`、`danmaku_claim`、`danmaku_reply`。沿用 `JINGYU_STUDIO_URL`。如果当前消息被领取后 Agent 退出，点击停止测试并重新开始即可清除占用。

2026-11-05 实测使用 4..7 秒随机间隔出现三条消息，分别是完成拖延事项、自我介绍、作业后鼓励。由当前 Codex 通过 CLI 逐条读取并现场生成回复，目标页面自动播放，排队期间保留消息和上下文。验收记录位于 `.local/checks/danmaku/`；队列、重复回复、播放完成回执与突发上限有独立基础测试。

## Minecraft 最小实玩闭环

直播间选择「Minecraft 实验场」，点击启用声音，再使用「Minecraft · 本地试验」面板。支持启动 / 关闭独立世界、观察、靠近、采集木头或石头、放置木板和完整演示。演示会重置专用试验区域和机器人背包，不连接已有存档。完整流程为寻找目标 → 走近 → 挖掘 → 确认拾取 → 放置 → 确认结果；游戏事件与语音播放均有回执。

这是 Minecraft Java 1.20.1 官方本地服务器中的真实机器人操作，搭配固定采集策略与预置试验场，不是自主生存 Agent。注意力来自当前方块的世界坐标，经相机 yaw/pitch/FOV 投影到第一人称画面；再按游戏窗口与角色头部的相对位置驱动眼睛和头部。绿色标记显示关注位置，关闭注视或停止动作后回正。尚未通过图像识别决定目标，也没有连接公共服务器或基岩版。

安装：在根目录运行 `python tools/setup_minecraft.py`，再 `npm install --prefix minecraft`；前者下载并校验官方服务端与 Adoptium Java 17，保存在 `.local/minecraft`，为新建的本机测试服务配置 EULA 和仅本机监听。工作台语音服务就绪后运行 `python tools/build_minecraft_voice.py` 缓存八条 DS 解说。已完成这些步骤的本机可直接从面板启动。正常关闭世界会保存地图。

官方 Java 端口 25566、控制接口 61946、第一人称画面 61947 均只监听 127.0.0.1。世界、运行时、事件日志和解说缓存清单位于 `.local/minecraft/`；不随公开源码分发 Minecraft 服务端、Java 运行时或游戏存档。

HTTP：GET `/api/minecraft`；POST 同一路径 `{action, clientId?, block?}`。action 为 start/inspect/walk/dig/place/demo/stop/shutdown，block 为 oak_log/stone；clientId 指定已经启用声音的直播间，否则仅记录文本解说。返回 running/ready/run/inventory/attention/narration/events。动作受理后轮询 run.status；completed 代表动作已执行完成，不是仅提交成功。CLI：`python studio_cli.py minecraft --game-action demo --client <id>`；MCP 为 minecraft_state、minecraft_action。

常见解说使用已生成的短音频，避免每次现场合成。开始解说确认播放后再执行相应动作；只有背包确实增加或方块状态确实改变后才说完成。播放忙时等待上一句结束，记录 requestedAt/playedAt/delayMs。缓存缺失时回退到现有流式语音接口，起播会更慢。

适配基于 [Mineflayer](https://github.com/PrismarineJS/mineflayer)、[Pathfinder](https://github.com/PrismarineJS/mineflayer-pathfinder) 和 [Prismarine Viewer](https://github.com/PrismarineJS/prismarine-viewer)。Viewer 1.33.0 源码仍假设 0..255 世界高度；`minecraft/patch-viewer.cjs` 对源文件和已发布浏览器包应用同一负高度修复，修正区段索引和面剔除，保留前后哈希。补丁绑定该版本，首次启动自动应用。

2026-11-05 实测完成两轮约 26 秒的采集演示，背包增加 oak_log ×1、cobblestone ×1，oak_planks 从 5 减至 4，世界收到木板放置回执。已验证左右 / 高低投影、注视优先级、负高度网格与真实网页联动；停止操作会取消游戏动作、中断语音并释放视线。验收文件在 `.local/checks/minecraft/`。

### 生存接口验证与职责边界

工作台负责游戏状态/操作接口、角色注意力和语音呈现；复杂生存决策属于外部 Agent，不继续作为工作台产品能力扩展。已编写的 `minecraft/survival-*.cjs` 与 `survival.cjs` 保留为独立验证策略，只有显式调用才运行，面板收在默认折叠的「生存策略验证 · 实验」中。

`start` 支持 `world: "survival"`，使用 `.local/minecraft/survival-server` 中的普通地形、正常难度独立存档；不会执行试验场的传送、补给或重置命令。切换 world 前先 shutdown。实验动作 survival/survival-step 支持 goal（starter/sustain/return-home）、maxSteps、maxMinutes；状态中 survival.observation/decision/receipts 分别给出观测、下一步及结果。预算用完为 paused，连续失败为 needs-attention；停止不会宣称目标完成。

本轮自然地形试跑确认空手采木、合成并放置工作台、合成木镐，以及网页注视和 DS 解说；陡峭水岸寻路未通过，已保存存档并停止运行。自然地形完整开局、营地、夜间生存与长期自主生存均未验收。隔离的真实服务端试验场用于进一步核对采集、石制工具、工作站、熔炼和火把接口；其预置资源、固定白天，与自然世界测试分开记录。证据在 `.local/checks/minecraft/survival-natural.json` 和 `survival-fixture/`，以 checks.json 中已通过项目为准。

开发检查：`node minecraft/test-survival.cjs`；真实服务端验证脚本 `minecraft/verify-survival.cjs` 默认完整实验，`JINGYU_QA_RESUME=1` 与 `JINGYU_QA_SCOPE=interfaces` 可在已有隔离存档上仅验证熔炼/火把接口。验证器使用独立端口 25567，不操作正式存档。Mineflayer 4.39 会由其他实体的 air_supply 覆盖共享 oxygenLevel；本适配读取固定版本 1.20.1 的玩家自身 metadata[1]，并有串扰回归检查。
