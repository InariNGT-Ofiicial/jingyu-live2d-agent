# 鲸语 · Jingyu Live2D Agent

**1.4.0-beta.1 · Windows 本地动作工作台**

把自然语言编排为可检查的 Live2D 动作时间线，在网页或 VTube Studio 播放。
可接 OpenAI 兼容 API、已登录的本机 DSH，也可由 Codex / 外部 Agent 通过 HTTP 或 CLI 驱动。

## 已有功能

- OpenAI Chat Completions / Responses 两种接口；模型 ID 自行填写。
- DSH headless 编排；本地校验参数、时间、通道冲突，失败最多修正一次。
- 网页 / VTS 后端切换；VTS 原生动作编译与热部署，保留作者物理。
- 头眼、表情、连续头身轨迹、抚胸 / 竖指 / 持草手势及组合预设。
- 命名保存个人预设、重启保留、确认删除；已执行计划可直接重播，无需再次调用模型。
- 透明 GIF 和背景合成 MP4 导出；两种格式均由网页渲染器采样。
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
导出时保持网页舞台打开。GIF 是二值透明；普通 H.264 MP4 **不含透明通道**。
目前不是 VTS 原生帧缓冲录制。

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

在取得模型后设置 `L2D_MODEL_DIR` 并执行 `python launch.py --check`，再执行：

```powershell
python -c "from model_profile import write_profile; write_profile()"
python -m unittest test_compiler test_driver_integration test_planner test_beta test_vts_deploy test_presets
node test_engine.mjs
node test_driver_integration.mjs
```

本地已通过 38 项 Python 测试和 2 组 Node 引擎测试，DSH → 网页 / VTS、导出、
预设持久化与重播已实测。OpenAI 两种协议通过本地 HTTP fixture 验证，
尚未用真实 OpenAI 账号验证。网页后台可能被浏览器限速。

此模型不支持自由行走、背面转身；口型动作不生成音频。
动作任务和编排历史存于内存，重启清空；个人预设、配置与导出文件保留。
服务只监听本机，勿将端口直接暴露到公网。

## 第三方依赖

第三方库、原始版权头与许可见 [THIRD-PARTY.txt](THIRD-PARTY.txt) 和 `licenses/`。
VTS、DSH、Python、Node、FFmpeg 和角色资产各自遵循其适用条款。
本仓库不含任何用户的 API Key、VTS/DSH 凭据、个人预设或运行记录。
