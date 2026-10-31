# 鲸语 · Jingyu Live2D Agent

**1.4.0-beta.2 · Windows 本地动作工作台**

把自然语言编排为可检查的 Live2D 动作时间线，在网页或 VTube Studio 播放。
可接 OpenAI 兼容 API、已登录的本机 DSH，也可由 Codex / 外部 Agent 通过 HTTP 或 CLI 驱动。

## 已有功能

- OpenAI Chat Completions / Responses 两种接口；模型 ID 自行填写。
- DSH headless 编排；本地校验参数、时间、通道冲突，失败最多修正一次。
- 网页 / VTS 后端切换；VTS 原生动作编译与热部署，保留作者物理。
- 头眼、表情、连续头身轨迹、抚胸 / 竖指 / 持草手势及组合预设。
- 命名保存个人预设、重启保留、确认删除；已执行计划可直接重播，无需再次调用模型。
- 透明 GIF 和背景合成 MP4 导出；可选择网页渲染或 VTS 原生 Spout2 RGBA 帧流。
- HTTP、CLI、Agent 工具协议及逐任务完成回执。

## 先准备模型与运行库

本仓库**不包含角色模型、贴图、PSD 或 Live2D Cubism Core**。
角色原画及拆分：**神宫凉子**；Live2D 建模：**霓虹猫_NeonNeko**。
请从作者渠道取得 DeepSeek「大肥鱼」模型并保留原始使用说明。
[作者发布视频](https://www.bilibili.com/video/BV1KmxY66EZ3/)。
作者说明禁止擅自重新分发完整模型；使用本项目不授予角色资产的再分发权利。

此 beta 的能力目录和通道映射针对该模型，尚不支持任意模型自动适配。

1. 安装 Python 3.10+。
2. 从 [Live2D 官方 Cubism SDK for Web](https://www.live2d.com/en/sdk/download/web/) 获取
   `live2dcubismcore.min.js`，放入 `web/vendor/`；遵循官方许可。
   `vendor-sources.json` 记录了本机验证过的运行库来源与 SHA-256。
3. 把完整模型目录放入 `model/DeepSeek/`，或启动时用 `--model-dir` 指定目录。
   目录需含 `大肥鱼.model3.json`、MOC、全部贴图、物理、`Exp3/`、`Animation/` 和 VTS 配置。
4. 启动：

```powershell
python launch.py --model-dir "D:/your-model/DeepSeek" --check
python launch.py --model-dir "D:/your-model/DeepSeek"
```

也可双击 `Start-Beta.cmd`。默认舞台为 <http://127.0.0.1:61942/>。
`model/DeepSeek/` 存在时会自动加载，已配置的路径记在 `.local/`。
模型配置生成的 `web/data/model-profile.json` 和压力测试目录在启动时重建，不进入 Git。

## 编排来源

**OpenAI 兼容服务**：在“选择 / 配置”填写 Base URL、模型 ID、Key 和接口格式。
仅在服务支持时启用 JSON 模式。Key 只在进程内存或由环境变量提供，不写入设置文件。
支持 `L2D_LLM_BASE_URL`、`L2D_LLM_MODEL`、`L2D_LLM_API_KEY` / `OPENAI_API_KEY`。

**DSH**：安装并登录 DSH，确保 `dsh` 在 PATH，或设置 `L2D_DSH_COMMAND`
指向其 CLI。可用 `L2D_DSH_MODEL` 指定模型。不会复制 DSH 凭据或改全局配置。

选择后端 → 描述表演 → 生成并校验 → 播放 → 保存预设或重新播放。
发送给模型服务的是动作要求和能力目录，不上传贴图、MOC 或 PSD。

## VTube Studio

安装 [VTube Studio](https://store.steampowered.com/app/1325860/VTube_Studio/) 和 Node.js，执行：

```powershell
python -m pip install -r requirements-vts.txt
```

开启 VTS 插件 API（默认 `127.0.0.1:8001`），首次允许 `Jingyu Motion Bridge`。
程序自动查找 Steam 中的 VTS，创建或复用 `Jingyu-Author-Comparison` 专用副本。
无需手工重建映射；非 Steam 路径用 `L2D_VTS_DIR` 指定。
新机器仍需首次授权。热部署短暂卸载 / 重载专用副本，原模型只读。

## 导出与预设

安装完整 FFmpeg / ffprobe 并放入 PATH，或按 `runtime-config.example.json`
创建本机 `runtime-config.json`。FFmpeg 需提供 GIF、libx264、palettegen、paletteuse、overlay。
网页导出时保持网页舞台打开。GIF 是二值透明；普通 H.264 MP4 **不含透明通道**。

### VTS 原生录制（Windows，可选）

原生路径接收 VTS 发布的 GPU 共享纹理，保留作者物理、表情与当前 VTS 镜头。
不采集桌面或窗口 UI，不使用绿幕抠像，也不会在失败时替换为网页画面。
按 [VTS 官方 Spout 指南](https://github.com/DenchiSoft/VTubeStudio/wiki/Recording-Streaming-with-OBS)
打开 Spout2，选择 ColorPicker 背景并启用透明捕获。保持 VTS 可见、不要最小化。

采集依赖独立安装，推荐 64 位 Python 3.12（SpoutGL 0.1.1 提供 Windows 3.8–3.13 轮子）：

```powershell
py -3.12 -m venv .local/vts-capture
.local/vts-capture/Scripts/python.exe -m pip install -r requirements-capture.txt
.local/vts-capture/Scripts/python.exe vts_capture.py --probe
```

该路径自动识别；其他位置可设 `CAPTURE_PYTHON` 或 runtime-config.json 的 `capture_python`。
前台“导出源”选择“VTS 原生帧流”，点击“检查 VTS 帧流”，再导出。
API / CLI 无需网页在线：

```powershell
python bridge_cli.py export examples/hotdeploy-left.json --renderer vts --format gif --fps 15 --wait
python bridge_cli.py export examples/hotdeploy-left.json --renderer vts --format mp4 --background "#f5f7f5" --wait
```

VTS 与采集 Python 必须使用**同一块 GPU**。双显卡电脑若能发现发送器但读不到帧，
先检查 VTS 使用哪块 GPU；如果它使用独显，可主动执行：

```powershell
.local/vts-capture/Scripts/python.exe setup_capture_gpu.py --gpu high-performance
```

此命令设置 Windows 应用图形偏好，影响该虚拟环境及其基础 Python 解释器；随后重启采集进程。
用 `--gpu system` 恢复系统选择。也可在 Windows 图形设置中手工将两者设为同一 GPU。
程序不会自动更改图形偏好。`--probe` 返回接收 GPU、源尺寸、alpha 范围和实际发送器名称；
多实例时用导出选项 `sender` / CLI `--sender` 指定。

原生录制会先热部署，再触发完整表演并实时采样；整个过程独占动作执行，取消时等待 VTS 恢复。
输出按比例缩放并居中留边，保留 VTS 构图；需要更大的角色占比时在 VTS 调整镜头。
录制期间不要调整窗口尺寸、切换模型或关闭透明背景。建议从 10–15 FPS 开始；
高分辨率下持续采样落后、尺寸改变、断流或整段静止都会返回错误。
这是实时采样，不是逐帧离线推进 VTS；不承诺每个渲染帧都被采集。
`exports/<id>/capture-report.json` 保留采样时间、重复帧和迟到帧统计。
部分 VTS 版本不发布 Spout 帧计数，此时用像素哈希判断整段变化，并在回执标注计数不可用。

个人预设存储在 `.local/presets.json`，升级时保留该文件。
保存的是计划中的动作、节奏和幅度，不包含网页待机开关、镜头或实时滑杆状态。
内置预设和个人预设分开管理；“我的预设”可播放、删除。

## API / CLI

```powershell
python bridge_cli.py capabilities
python bridge_cli.py plan "先侧目，再抚胸微笑，最后回正" --backend web --wait
python bridge_cli.py play-plan <taskId>
python bridge_cli.py execute examples/hotdeploy-left.json --backend vts --wait
python bridge_cli.py state
python bridge_cli.py stop
python agent_tool.py --schemas
```

完整接口见 [BETA-API.txt](BETA-API.txt)，依赖与设置见 [BETA-README.txt](BETA-README.txt)。
`GET /api/presets`；`POST /api/presets/save`、`/play`、`/delete`；
`POST /api/replay` 或 `/api/planner/replay` 可重播。
HTTP 入队成功不等于表演完成；以任务 `completed / error / interrupted` 回执为准。

## 验证与限制

外部贡献无需取得模型即可运行合成契约测试：

```powershell
python -m pip install -r requirements-test.txt
python tools/check_public_tree.py
python tools/run_checks.py
```

需要 Python 3.10+ 和 Node.js 24。检查在临时副本中执行，不读取个人状态或连接真实服务。
这不代替真实模型、VTS / GPU 或视觉验收。贡献要求见 [CONTRIBUTING.md](CONTRIBUTING.md)，
发布前执行 [回归清单](docs/RELEASE-CHECKLIST.md)。

在取得模型后设置 `L2D_MODEL_DIR` 并执行 `python launch.py --check`，再执行：

```powershell
python -c "from model_profile import write_profile; write_profile()"
python -m unittest test_compiler test_driver_integration test_planner test_beta test_vts_deploy test_presets
.local/vts-capture/Scripts/python.exe -m unittest test_vts_capture
node test_engine.mjs
node test_driver_integration.mjs
```

本地已通过 48 项 Python 测试（其中 10 项原生采集测试）和 2 组 Node 引擎测试，DSH → 网页 / VTS、导出、
预设持久化与重播已实测。OpenAI 两种协议通过本地 HTTP fixture 验证，
尚未用真实 OpenAI 账号验证。网页后台可能被浏览器限速。
VTS Spout 2560×1600 源已实测透明 GIF 与 512×768 / 15 FPS MP4；
新硬件上的可用帧率仍需由采样报告确认。

此模型不支持自由行走、背面转身；口型动作不生成音频。
动作任务和编排历史存于内存，重启清空；个人预设、配置与导出文件保留。
服务只监听本机，勿将端口直接暴露到公网。

## 第三方依赖

第三方库、原始版权头与许可见 [THIRD-PARTY.txt](THIRD-PARTY.txt) 和 `licenses/`。
VTS、DSH、Python、Node、FFmpeg 和角色资产各自遵循其适用条款。
本仓库不含任何用户的 API Key、VTS/DSH 凭据、个人预设或运行记录。
