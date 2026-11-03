# 面捕 MCP 与桌宠实验

使用安装了 requirements-tracking-mcp.txt 的 Python，以 stdio 运行 tracking_mcp.py。服务端从启动器保存的模型路径或 L2D_MODEL_DIR 读取作者配置。首次连接允许 Jingyu Motion Bridge，已有本机授权可用 L2D_VTS_TOKEN_FILE 指向自己的加密令牌文件。

| MCP 工具 | 输入和输出 |
|---|---|
| tracking_inputs | 返回跟踪器是否找到脸，以及头角、眼睛和嘴部共 11 个通道的当前值与量程。 |
| capture_plan | 传入 seconds（0.3 至 10）。采样 VTS 当前有效输入和同一时段模型输出，返回原始输入序列及可交给鲸语 /api/execute 的 plan。两次读取有时间差。 |
| inject_face | 指定 channel、value 和 seconds（0.2 至 3）。短暂接管单个通道，释放权重后读回结果。 |
| compile_tracking | 将 plan 按作者映射反算为 InjectParameterDataRequest 序列；一个输入连动多个输出时返回无法表示的原因。 |

本模型的 FaceAngleX 同时驱动 AngleX 和 PositionX。向两个输出指定相同目标的 pose 可以反算；只指定 AngleX 的计划会报告缺少联动输出。采样计划使用 VTS 已计算的模型值，因此能保留采样时实际发生的平滑变化。

运行集成版工作台后，Windows 执行 Start-Pet.ps1 可打开置顶的网页桌宠。指定 -Port 可更换服务端口。pet.html 也可作为透明浏览器源；在同一服务执行网页动作时，桌宠会回报自己的播放状态。

VTS 原生桌宠使用安装了 requirements-pet.txt 的 Python 运行 spout_pet.py。开启 VTS 的 Spout 和透明捕获，采集 Python 与 VTS 选择同一 GPU。窗口直接显示 GPU 纹理，保留逐像素透明度。默认宽度 960 像素，目标 60 FPS；滚轮缩放，左键拖动，右键退出。可传 --width 和 --fps 调整。网页桌宠按屏幕像素密度（最高 2 倍）渲染。最小化时浏览器可暂停绘制，再次运行 Start-Pet.ps1 可恢复窗口。
