# 面捕 MCP 与桌宠实验

使用安装了 requirements-tracking-mcp.txt 的 Python，以 stdio 运行 tracking_mcp.py。服务端从启动器保存的模型路径或 L2D_MODEL_DIR 读取作者配置。首次连接允许 Jingyu Motion Bridge，已有本机授权可用 L2D_VTS_TOKEN_FILE 指向自己的加密令牌文件。

| MCP 工具 | 输入和输出 |
|---|---|
| tracking_inputs | 返回跟踪器是否找到脸，以及头角、眼睛和嘴部共 11 个通道的当前值与量程。 |
| capture_plan | 传入 seconds（0.3 至 10）。采样 VTS 当前有效输入和同一时段模型输出，返回原始输入序列及可交给鲸语 /api/execute 的 plan。两次读取有时间差。 |
| inject_face | 指定 channel、value 和 seconds（0.2 至 3）。短暂接管单个通道，释放权重后读回结果。 |
| compile_tracking | 将 plan 按作者映射反算为 InjectParameterDataRequest 序列；一个输入连动多个输出时返回无法表示的原因。 |

本模型的 FaceAngleX 同时驱动 AngleX 和 PositionX。向两个输出指定相同目标的 pose 可以反算；只指定 AngleX 的计划会报告缺少联动输出。采样计划使用 VTS 已计算的模型值，因此能保留采样时实际发生的平滑变化。

## 网页透明桌宠（默认）

工作台的「开启网页桌宠」现在直接使用 Electron 透明窗口加载 `/pet.html`，由 Pixi / Cubism 在 GPU 上渲染。无需 VTS、Spout、采集 Python，也不截取工作台页面或转发截图。动作通过同一服务的 SSE 接收；仅执行 web 后端计划。

首次安装：`npm install --prefix desktop-pet`（固定 Electron 45.2.2，安装脚本下载官方运行文件）。需要 Node.js 22.12+。之后使用工作台开关，或 `./Start-Pet.ps1 -Port 61944`；关闭用 `./Start-Pet.ps1 -Port 61944 -Stop`。端口随当前服务自动传入，含模型包的 61945 也可使用。运行时也可通过 `ELECTRON` 或 runtime-config.json 的 electron 字段指定。

- 真透明、置顶、无边框，默认 480 × 700，按屏幕 DPI 渲染，最高 2 倍，目标 60 FPS；后台保持绘制。
- 鼠标移入出现工具条：拖动「移动」、放大、缩小、穿透和关闭；滚轮缩放，Esc 关闭。
- 桌宠工具条的「互动」面板包含普通点击、胸部 / 大腿分区反馈、长按头部与胸部拖动、上身跟随、袜口拖拽及恢复；与工作台复用同一套模块。身体摇晃、随机待机、物理增益也可调。
- 「注视整个桌面的鼠标」通过系统桌面坐标驱动眼睛和头部；鼠标移到其他应用、桌面空白或其他显示器时仍跟随。按屏幕和角色头部位置归一化，并保留动作 / 长按的优先级；关闭开关立即停止跟随。
- 穿透后在系统托盘右键选择「恢复交互」，或双击托盘图标恢复；也可在工作台关闭。
- 工作台服务需要运行，工作台浏览器标签页可以关闭。网页源 `/pet.html` 可直接加入 OBS 浏览器源，默认无工具条和背景。

接口：GET `/api/pet` 返回 running、ready、renderer=web、requiresVts=false、sourceUrl 及帧率 / 分辨率；POST `/api/pet` 使用 `{"enabled":true}` / `{"enabled":false}`。启动成功需等待实际模型载入，日志在 `logs/web-pet-<port>.log`。状态和 Electron 配置保存在 `.local/web-pet/`。

透明窗口和后台绘制采用 [Electron BrowserWindow](https://www.electronjs.org/docs/latest/api/browser-window)；桌面操作通过隔离的 preload 接口传入，网页不开启 Node.js。

## 保留的 VTS 原生路径

需要采集作者原始 VTS 画面时，仍可单独运行 `spout_pet.py` 和 requirements-pet.txt 环境。该旧路径依赖 VTS Spout / 透明捕获，已不再是工作台开关的默认后端。

双显卡机器默认使用 Electron 的 [force_high_performance_gpu](https://www.electronjs.org/docs/latest/api/command-line-switches#--force_high_performance_gpu)；需要恢复系统默认显卡时设置 JINGYU_PET_GPU=default 再启动。此机核显初测 24–59 FPS，改用独显后同尺寸连续采样 58–59 FPS（726 × 1056 左右，DPI 1.5）。
