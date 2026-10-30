鲸语 Live2D 动作工作台 1.4.0-beta.1 · Windows 本地测试版

启动
1. 安装 Python 3.10+，并按 README.md 准备模型与 Live2D Cubism Core。公开仓库不含模型或 Core。
2. 双击 Start-Beta.cmd，完整版自动使用 model/DeepSeek，参数映射与预设已配置。
   代码包首次粘贴包含“大肥鱼.model3.json”的模型目录。
   或：python launch.py --model-dir "模型目录" --port 61942
3. 浏览器打开 http://127.0.0.1:61942/。预设与网页播放无需模型 API。
   启动前自检：python launch.py --model-dir "模型目录" --check
   本 beta 绑定现有 DeepSeek 模型参数目录，尚不是通用任意模型导入器。

选择编排来源
OpenAI 兼容 API：在“选择 / 配置”填写 Base URL、模型 ID、Key，选择
Chat Completions 或 Responses；JSON 模式仅在服务支持时勾选。
DSH：安装并登录桌面 DSH，选择“本机 DSH”。调用独立 headless 会话，
复用 DSH 自己管理的登录，不读取或复制其凭据，不改动其全局配置。
可用 L2D_DSH_COMMAND 指定 CLI 启动器，L2D_DSH_MODEL 指定模型。
配置保存在 .local；API Key 只在服务内存，重启需重填或设置
L2D_LLM_API_KEY / OPENAI_API_KEY。更换 Base URL 会清除旧 Key。
发送给模型服务的内容是表演要求与动作能力目录，不上传纹理、MOC、PSD。

使用流程
选择执行后端 → 输入情境 → 生成动作计划 → 本地校验 → 播放已校验计划。
生成的计划记住当时的执行后端。模型拒绝、无效 JSON、冲突和越界会报错；
最多修正一次，不会自动换成预设冒充生成。取消编排仅丢弃结果，已发出的
服务请求可能继续到结束，不保证撤回远程计费。
外部 Codex/Agent 可用指令箱、bridge_cli.py 或 agent_tool.py；不依赖内置模型。

保存与重播
已校验计划和当前舞台均有“保存为预设”。命名后进入“我的预设”，重启仍保留。
点击预设按当前网页/VTS 后端播放；删除需确认名称，内置组合不受影响。
已执行计划可“重新播放”，不会再次请求模型。播放中需先停止或等待结束。
保存的是计划的动作、节奏与幅度，不含网页待机/镜头/实时幅度滑杆状态。
用户预设保存在 .local/presets.json，升级时保留此文件；发行包不含个人预设。

VTS（可选）
安装 VTube Studio，开启本机插件 API，首次手动允许 Jingyu Motion Bridge。
安装 python -m pip install -r requirements-vts.txt，并准备 Node.js。
首次执行会自动查找 Steam 安装的 VTS，并创建或复用 Jingyu-Author-Comparison
专用副本，保留作者参数与物理配置，无需手工建通道。非 Steam 位置可设置
L2D_VTS_DIR 为安装目录；也可先运行 python vts_setup.py 初始化。
新的机器仍需首次 API 授权。
API 热部署会短暂卸载/重载专用模型；不会修改原始包。

导出
完整 FFmpeg 需包含 gif、libx264、palettegen、paletteuse、overlay。
将 ffmpeg/ffprobe 加入 PATH，或参考 runtime-config.example.json 创建
runtime-config.json；也可设置 FFMPEG、FFPROBE 环境变量。
舞台需保持打开。选择 GIF 或 MP4 后导出当前已执行的动作计划；CLI 可直接
指定计划导出。GIF 透明度为二值，MP4 合成背景、没有透明通道。
两者都由网页渲染器离屏采样；VTS 原生帧缓冲导出尚未接入。

接口示例（在工程目录）
python bridge_cli.py planner-config
python bridge_cli.py plan "先侧目，再抚胸微笑，最后自然回正" --backend web --wait
python bridge_cli.py play-plan <taskId>
python bridge_cli.py state
python bridge_cli.py stop
python bridge_cli.py execute examples/hotdeploy-left.json --backend vts --wait
python bridge_cli.py export examples/hotdeploy-left.json --format gif --wait
python agent_tool.py --schemas
详细 HTTP API 见 BETA-API.txt。

边界
这是本机 beta：会话任务、指令箱在重启后清空；导出文件与配置保留。
自由走路、背面转身、真实语音生成不在当前模型能力内。兼容 API 协议不保证
每个模型都能稳定编排。不要把开发端口暴露到公网。
本机完整版包含原模型、PSD 与原始使用说明；作者说明禁止擅自重新分发完整模型。
代码包不含模型。两种包都不含个人日志、API Key、DSH/VTS 凭据和第三方可执行文件。
Live2D/Pixi 依赖来源与适用许可见 vendor-sources.json 与 THIRD-PARTY.txt。
原画及拆分：神宫凉子；Live2D 建模：霓虹猫_NeonNeko。
