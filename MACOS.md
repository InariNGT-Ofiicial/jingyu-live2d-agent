# 鲸语 · macOS 适配说明

Windows 版的行为没有改动：平台判断是并列分支，Windows 仍然走原来的注册表、DPAPI 与 Spout2。
这份文档只说明 macOS 上哪些能用、哪些换了实现、哪些本来就不可能。

## 平台矩阵

| 能力 | Windows | macOS |
|---|---|---|
| 网页舞台、动作编排、预设、重播 | ✅ | ✅ 已实测 |
| 网页渲染导出 GIF / MP4 | ✅ | ✅ 已实测（FFmpeg 需带 `gif`、`libx264`、`palettegen`、`paletteuse`、`overlay`） |
| VTS 连接、鉴权、参数实时注入 | ✅ | ✅ 已实机验证（macOS 27.2 / VTS 1.35.10） |
| VTS 热部署（写专用副本 + 触发原生动作） | ✅ | ✅ 已实机验证（热键 + 参数轨迹） |
| VTS 原生帧流采集（Spout2） | ✅ | ❌ 不可能：Spout2 是 DirectX 共享纹理 |
| 显卡偏好设置 `setup_capture_gpu.py` | ✅ | — 无需该步骤，脚本会直接说明并退出 |

## 安装

```bash
brew install python@3.12 node ffmpeg      # Python 3.10+ 即可
cd jingyu-live2d-agent
curl -o web/vendor/live2dcubismcore.min.js \
  https://cubism.live2d.com/sdk-web/cubismcore/live2dcubismcore.min.js
python3 launch.py --model-dir "/path/to/DeepSeek"   # 首次指定，之后记住
```

也可以双击 `Start-Beta.command`（等同于 Windows 的 `Start-Beta.cmd`）。
依赖路径不标准时，参考 `runtime-config.macos.example.json` 创建 `runtime-config.json`。

`web/vendor/live2dcubismcore.min.js` 与模型目录都不能进仓库：前者被 `.gitignore` 排除，后者本来就在仓库之外，
用 `L2D_MODEL_DIR` 或 `--model-dir` 指定。

## VTS

### 安装位置识别

按顺序查找，命中即用：

1. `L2D_VTS_DIR` 指定的目录（可指向安装目录，也可直接指向 `VTube Studio.app`）
2. `~/Library/Application Support/Steam/steamapps/common/VTube Studio`
3. `steamapps/libraryfolders.vdf` 里登记的其它 Steam 库

`Live2DModels` 在两个平台位置不同，程序会自动取对应布局：

- Windows：`VTube Studio_Data/StreamingAssets/Live2DModels`
- macOS：`VTube Studio.app/Contents/Resources/Data/StreamingAssets/Live2DModels`

### 插件令牌

Windows 用 DPAPI 加密后写到 `.local/vts-token.dpapi`；macOS 默认写入登录钥匙串
（服务名 `Jingyu Motion Bridge`，账户 `jingyu-vts-token`），钥匙串不可用时自动降级为 `0600` 权限文件。

- `L2D_VTS_TOKEN_BACKEND=file|keychain`：强制存储方式
- `L2D_VTS_TOKEN_FILE=/path/to/token`：改文件位置（设置后两平台都用文件）

清除令牌：删除 `.local/vts-token.dpapi`，或
`security delete-generic-password -s "Jingyu Motion Bridge"`。

### 首次联调清单（macOS）

1. 用 Steam 安装 macOS 版 VTS，先手动启动一次，让它生成模型目录。
2. VTS 设置里打开插件 API（默认 `127.0.0.1:8001`）。
3. `python3 vts_doctor.py` —— 只读体检，逐项告诉你还差什么。
4. `python3 vts_setup.py` —— 复制一份作者模型为 `Jingyu-Author-Comparison`（不改原目录）。
5. 重启一次 VTS，让它扫描到新副本。
6. `python3 vts_doctor.py --approve` —— 触发插件授权，在 VTS 弹窗点允许，令牌进钥匙串。
7. `python3 bridge_cli.py execute examples/hotdeploy-left.json --backend vts --wait`

第 7 步走的是插件 API 的 `HotkeyTriggerRequest`，不依赖键盘热键；但 VTS 窗口保持可见更稳。
`vts_doctor.py` 是只读的：不写文件、不复制模型、不触发播放（`--approve` 只做正常的授权弹窗）。

### 原生录制为什么没有 macOS 版

Spout2 是 DirectX 共享纹理，macOS 没有等价 API；`requirements-capture.txt` 里的 SpoutGL 只有 Windows 轮子
（`pip install SpoutGL` 在 macOS 上无法构建）。VTS 官方也是同样的结论：Spout2 标注 Windows only，
macOS 建议用普通采集或 NDI，并且 OBS 的 “Transparent in capture” 在 macOS 不支持。

因此 macOS 上 `导出源 → VTS 原生画面` 会被禁用，接口会返回明确原因。想要“原生画面 + 透明”，可用的路子是
VTS 自带 NDI 输出 + OBS（NDI 保留 alpha），再把 OBS 录制结果当外部素材；这条不在本项目实现范围内。
只想要动作视频的话，直接用网页渲染导出即可，画面与预设一致。

## 上游限制（VTube Studio 自己的 macOS 状态）

引用 VTS 官方 FAQ，与本项目无关但会影响体验：

- macOS 版是实验性支持，webcam 追踪不稳定，声音口型支持有限。
- 后台热键在 macOS 无效——窗口不聚焦时键盘热键不触发。本项目通过插件 API 触发 `HotkeyTriggerRequest`，
  不依赖键盘热键，但请在 VTS 窗口可见的状态下执行热部署。
- 透明背景只能靠 NDI 或抠像，见上一节。

## 与 Windows 版本的差异清单

| 项目 | 处理 |
|---|---|
| `vts_setup.find_vts()` | 抽出 `platform_support.find_vts()`，Windows 顺序与原先一致（`winreg` 的 SteamPath 优先，其后 `ProgramFiles(x86)`） |
| DPAPI | 原实现原样保留，只是移到 `platform_support._dpapi()`；Windows 文件路径仍是 `.local/vts-token.dpapi` |
| `VTube Studio_Data/...` | 由 `platform_support.vts_models_dir()` 按布局探测，Windows 结果不变 |
| `CREATE_NO_WINDOW` | 统一为 `no_window_flags()`：Windows 仍是该常量，POSIX 返回 0 |
| Spout2 采集 | Windows 逻辑未改；非 Windows 在入口处直接给出可操作的错误 |
| 运行时探测 | Windows 候选不变；POSIX 额外加入 `.local/vts-capture/bin/python` 与 `/opt/homebrew/bin`、`/usr/local/bin` |

## 故障排查

| 现象 | 处理 |
|---|---|
| `缺少 大肥鱼.cdi3.json` | 没指定模型，或直接跑了 `server.py`。用 `launch.py`，或 `export L2D_MODEL_DIR=...` |
| 页面提示「本地 Live2D 运行库未能加载」 | `web/vendor/live2dcubismcore.min.js` 没放进去 |
| `缺少 ffmpeg` | `brew install ffmpeg`，或写 `runtime-config.json` |
| `未找到 VTube Studio` | 用 Steam 安装 macOS 版，或设置 `L2D_VTS_DIR` 指向 `.app` 或安装目录 |
| 钥匙串写入失败 | 会提示并自动用 `0600` 文件；也可直接 `L2D_VTS_TOKEN_BACKEND=file` |
| 端口被占用 | `python3 launch.py --port 62000` |

## 验证

```bash
L2D_MODEL_DIR="/path/to/DeepSeek" python3 launch.py --check
L2D_MODEL_DIR="/path/to/DeepSeek" python3 -m unittest test_compiler test_driver_integration test_planner test_beta test_vts_deploy test_presets test_vts_capture test_platform
node test_engine.mjs && node test_driver_integration.mjs
```

本机（macOS 27.2 / arm64、Python 3.14.7、Node 24.22.1、FFmpeg 9.0.2、VTube Studio 1.35.10）实测：

- Python 67 项通过（含 20 项平台契约测试、10 项 RGBA 录制测试），Node 2 组通过。
- 网页舞台渲染 509 参数 / 131 物理 / 715 画元；7.2 秒计划执行到 `completed`；256×384 / 10 FPS 透明 GIF 导出成功。
- VTS 真机链路：安装识别 → 专用副本导入 → 插件授权（令牌入钥匙串）→ 热部署 → 原生动作播放 → 回收，
  全链路 `completed`。轨迹（35 个采样）显示 `AngleX` 到 -24、`AngleZ` -12…+5.9、
  作者手势参数 `Movement2` 0→1→0、`key7` 0.5、`ParamMouthForm` 0.52、`EyeSmile` 0.42，
  8.13 秒后回到待机；VTS 端 `Jingyu Agent Live` 热键指向部署的 `Jingyu-Auto-*.motion3.json`，
  副本 `ModelID` 未被改写，模型位置在部署后被还原。

### 真机暴露并已修复的问题

| 问题 | 原因 | 处理 |
|---|---|---|
| 明明装了 VTS 却"未找到" | Steam 实际装的是 `VTubeStudio.app`，官方 wiki 写的是 `VTube Studio.app` | 改为探测安装根目录下任意 `*.app` |
| 热部署子进程报 `No module named 'websocket'` | `runtime_tools.executable()` 用了 `resolve()`，把 venv 的软链 python 解析回基础解释器，丢掉 site-packages | 改为只做绝对化、不跟随软链（补了回归测试） |
| 体检把已授权的会话报成"等待授权" | `APIStateResponse` 用的是 `currentSessionAuthenticated`，不是 `authenticationRequired` | 按实际字段判断，并在授权后重读 |

另外 VTS 端口被占用时会顺延到 8002，体检现在在 8001–8005 之间自动探测。